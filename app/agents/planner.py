"""行程编排 Agent（规则引擎版）。

算法核心：先把候选景点按「片区」聚类，再以片区为单位分配每天行程，
避免同一天在城里来回穿城 —— 这是人工规划师和随机推荐最大的差别。

产出结构固定，便于评测脚本逐字段校验：
{
  "city": ..., "days": [...], "budget": {...}, "assumptions": [...]
}
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.intent import TripIntent
from app.tools import attractions

PACE_SPOTS_PER_DAY = {"relaxed": 2, "normal": 3, "packed": 4}
DAY_START_HOUR = 9
LUNCH_HOUR = 12
DINNER_HOUR = 18

MEAL_COST = {"午餐": 60, "晚餐": 80}
HOTEL_PER_NIGHT = 400
LOCAL_TRANSPORT_PER_DAY = 100


@dataclass
class PlanResult:
    city: str
    days: list[dict] = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    uncovered: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "city": self.city,
            "days": self.days,
            "budget": self.budget,
            "assumptions": self.assumptions,
            "uncovered": self.uncovered,
        }


def _pick_areas(candidates: list[dict], day_count: int, spots_per_day: int) -> list[list[dict]]:
    """按片区聚合并分配每日行程。

    策略：优先把同片区景点塞进同一天（减少穿城），
    该片区景点不够一天的量时，再从下一个片区补足，保证天数不缺失。
    """
    grouped = attractions.group_by_area(candidates)
    scored = sorted(
        grouped.items(),
        key=lambda kv: len(kv[1]) * (sum(s["rating"] for s in kv[1]) / len(kv[1])),
        reverse=True,
    )
    pool = [s for _, spots in scored for s in spots]

    days: list[list[dict]] = []
    # 宁可一天少排一个景点，也不要跨城凑数：不足时才补到下限
    min_per_day = 2 if spots_per_day <= 3 else 3
    for _ in range(day_count):
        if not pool:
            break
        anchor_area = pool[0]["area"]
        bucket = [s for s in pool if s["area"] == anchor_area][:spots_per_day]
        if len(bucket) < min_per_day:
            picked = {s["id"] for s in bucket}
            bucket += [s for s in pool if s["id"] not in picked][: min_per_day - len(bucket)]
        days.append(bucket)
        used = {s["id"] for s in bucket}
        pool = [s for s in pool if s["id"] not in used]

    return days


def _hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _build_timeline(spots: list[dict], day_index: int) -> dict:
    """生成当天时间轴。

    固定骨架：上午 09:00 起 → 12:00 午餐 → 13:00 起下午 → 18:00 晚餐。
    景点按容量分配到上午/下午两个时段，避免出现时间倒挂。
    """
    morning_cap = LUNCH_HOUR * 60 - DAY_START_HOUR * 60  # 180 分钟
    afternoon_cap = DINNER_HOUR * 60 - (LUNCH_HOUR + 1) * 60  # 300 分钟

    morning: list[dict] = []
    afternoon: list[dict] = []
    used = 0
    for spot in spots:
        minutes = int(spot["duration_h"] * 60)
        if used + minutes <= morning_cap and not afternoon:
            morning.append(spot)
            used += minutes
        else:
            afternoon.append(spot)

    items: list[dict] = []
    ticket_cost = 0.0
    meal_cost = 0.0

    cursor = DAY_START_HOUR * 60
    for spot in morning:
        items.append({
            "time": _hm(cursor), "type": "景点", "name": spot["name"],
            "area": spot["area"], "duration_h": spot["duration_h"],
            "cost": spot["ticket"], "note": spot["open"],
        })
        ticket_cost += spot["ticket"]
        cursor += int(spot["duration_h"] * 60)

    items.append({"time": "12:00", "type": "餐饮", "name": "午餐（就近）",
                  "duration_h": 1.0, "cost": MEAL_COST["午餐"], "area": ""})
    meal_cost += MEAL_COST["午餐"]

    cursor = (LUNCH_HOUR + 1) * 60
    for spot in afternoon:
        items.append({
            "time": _hm(cursor), "type": "景点", "name": spot["name"],
            "area": spot["area"], "duration_h": spot["duration_h"],
            "cost": spot["ticket"], "note": spot["open"],
        })
        ticket_cost += spot["ticket"]
        cursor += int(spot["duration_h"] * 60)

    # 晚餐：正常 18:00；下午行程拖过 18:00 则顺延，保证时间轴单调递增
    dinner_at = max(DINNER_HOUR * 60, cursor)
    items.append({"time": _hm(dinner_at), "type": "餐饮", "name": "晚餐（本地特色）",
                  "duration_h": 1.0, "cost": MEAL_COST["晚餐"], "area": ""})
    meal_cost += MEAL_COST["晚餐"]

    areas = sorted({s["area"] for s in spots})
    return {
        "day": day_index,
        "areas": areas,
        "items": items,
        "total_hours": round(sum(i["duration_h"] for i in items), 1),
        "ticket_cost": round(ticket_cost, 1),
        "meal_cost": round(meal_cost, 1),
    }


def plan(intent: TripIntent, llm=None) -> PlanResult:  # llm 预留：后续接文案润色
    if not intent.city:
        raise ValueError("缺少城市信息，无法规划：请补充目的地")

    days = intent.days or 3
    spots_per_day = PACE_SPOTS_PER_DAY.get(intent.pace, 3)

    candidates = attractions.search(intent.city, intent.people)
    need = days * spots_per_day
    if len(candidates) < need:
        # 人群匹配的景点不够时，用同城其他景点补足，而不是直接放弃偏好排序
        picked = {c["id"] for c in candidates}
        extra = [a for a in attractions.load_all() if a["city"] == intent.city and a["id"] not in picked]
        candidates = candidates + extra

    # 偏好加权：命中偏好类型的景点提前
    if intent.preferences:
        pref_types = set(intent.preferences) & {"自然", "人文", "美食"}
        candidates.sort(key=lambda a: (a["type"] in pref_types), reverse=True)

    buckets = _pick_areas(candidates, days, spots_per_day)
    result = PlanResult(city=intent.city)
    for i, bucket in enumerate(buckets, start=1):
        result.days.append(_build_timeline(bucket, i))

    ticket_total = sum(d["ticket_cost"] for d in result.days)
    meal_total = sum(d["meal_cost"] for d in result.days)
    nights = max(days - 1, 0)
    hotel_total = nights * HOTEL_PER_NIGHT
    transport_total = days * LOCAL_TRANSPORT_PER_DAY
    total = ticket_total + meal_total + hotel_total + transport_total

    result.budget = {
        "currency": "CNY",
        "per_person_estimate": round(total, 0),
        "breakdown": {
            "tickets": round(ticket_total, 0),
            "meals": round(meal_total, 0),
            "hotel": hotel_total,
            "local_transport": transport_total,
        },
        "user_budget": intent.budget,
        "within_budget": None if intent.budget is None else total <= intent.budget,
    }
    result.assumptions = list(intent.assumed.values())
    if intent.missing:
        result.assumptions.append(f"缺少必要信息：{', '.join(intent.missing)}")

    # 景点库撑不满用户要的天数时，必须显式说明，不能静默截断
    if len(result.days) < days:
        result.uncovered.append(f"requested {days} days, planned {len(result.days)} days")
        result.assumptions.append(
            f"当前景点库仅能支撑 {len(result.days)} 天，已按 {len(result.days)} 天规划；"
            f"如需 {days} 天，建议补充周边城市或增加自由活动日"
        )
    return result


def render_markdown(plan_result: PlanResult) -> str:
    """把结构化行程渲染成可直接发给客户的行程单。"""
    lines = [f"# {plan_result.city} {len(plan_result.days)} 日行程", ""]
    for day in plan_result.days:
        lines.append(f"## 第 {day['day']} 天　{(' / '.join(day['areas'])) or '市区'}")
        for item in day["items"]:
            tag = "🍽" if item["type"] == "餐饮" else "📍"
            note = f"（{item.get('note')}）" if item.get("note") else ""
            lines.append(f"- {item['time']}　{tag} {item['name']}　{item['duration_h']}h{note}")
        lines.append("")
    b = plan_result.budget
    lines.append(f"**人均预估：¥{b['per_person_estimate']:.0f}**　"
                 f"（门票 ¥{b['breakdown']['tickets']:.0f} / 餐饮 ¥{b['breakdown']['meals']:.0f} / "
                 f"住宿 ¥{b['breakdown']['hotel']:.0f} / 市内交通 ¥{b['breakdown']['local_transport']:.0f}）")
    if b.get("user_budget") is not None:
        flag = "在预算内" if b["within_budget"] else "超出预算，建议下调住宿标准或减少付费景点"
        lines.append(f"预算对照：用户 ¥{b['user_budget']:.0f} → {flag}")
    if plan_result.assumptions:
        lines.append("")
        lines.append("假设与提示：" + "；".join(plan_result.assumptions))
    return "\n".join(lines)
