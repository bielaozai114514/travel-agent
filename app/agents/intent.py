"""意图解析 Agent：把一句自然语言需求转成结构化行程参数。

两级实现：
- 有 LLM：走 JSON 结构化抽取，鲁棒性更好；
- 无 LLM：走规则引擎（城市词表 + 数字/中文数字解析 + 人群关键词），保证链路可跑。
两者输出同一个 TripIntent，下游无感知。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.llm.client import LLMClient, LLMUnavailable
from app.tools import attractions

CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
CN_UNIT = {"千": 1000, "万": 10000, "百": 100}

PEOPLE_KEYWORDS = {
    "亲子": ["孩子", "小孩", "亲子", "儿子", "女儿", "带娃", "一家三"],
    "老年": ["老人", "父母", "爸妈", "长辈", "爷爷", "奶奶", "退休"],
    "情侣": ["情侣", "女朋友", "男朋友", "老婆", "老公", "对象", "蜜月", "两人世界"],
    "商务": ["商务", "出差", "客户", "会议", "团建"],
    "独自": ["一个人", "独自", "自己", "solo"],
}

PACE_KEYWORDS = {
    "relaxed": ["轻松", "不要太累", "别太累", "悠闲", "慢", "休闲", "带娃累", "不赶", "不要太赶", "安静"],
    "packed": ["打卡", "紧凑", "暴走", "多看", "尽量多"],
}


@dataclass
class TripIntent:
    city: str | None = None
    days: int | None = None
    budget: float | None = None
    people: str = "独自"
    pace: str = "normal"
    preferences: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    assumed: dict[str, str] = field(default_factory=dict)
    source: str = "rule"

    def to_dict(self) -> dict:
        return {
            "city": self.city,
            "days": self.days,
            "budget": self.budget,
            "people": self.people,
            "pace": self.pace,
            "preferences": self.preferences,
            "missing": self.missing,
            "assumed": self.assumed,
            "source": self.source,
        }


def _parse_days(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(?:天|日)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"([一二两三四五六七八九十])\s*(?:天|日)", text)
    if m:
        return CN_NUM.get(m.group(1))
    return None


def _parse_budget(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:k|K|千)", text)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:万|w|W)", text)
    if m:
        return float(m.group(1)) * 10000
    m = re.search(r"([一二两三四五六七八九十])\s*([千万])", text)
    if m:
        return CN_NUM.get(m.group(1), 0) * CN_UNIT.get(m.group(2), 1)
    m = re.search(r"预算\s*(\d{3,6})", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d{3,6})\s*(?:元|块)", text)
    if m:
        return float(m.group(1))
    return None


def _parse_people(text: str) -> str:
    for people, kws in PEOPLE_KEYWORDS.items():
        if any(k in text for k in kws):
            return people
    return "独自"


def _parse_pace(text: str) -> str:
    for pace, kws in PACE_KEYWORDS.items():
        if any(k in text for k in kws):
            return pace
    return "normal"


def _parse_preferences(text: str) -> list[str]:
    mapping = {
        "美食": ["吃", "美食", "小吃"],
        "自然": ["自然", "风景", "爬山", "公园", "海"],
        "人文": ["博物馆", "历史", "文化", "古建", "寺庙"],
        "购物": ["购物", "逛街", "商场"],
        "拍照": ["拍照", "出片", "打卡"],
    }
    return [k for k, kws in mapping.items() if any(w in text for w in kws)]


def parse_with_rules(text: str) -> TripIntent:
    city = next((c for c in attractions.list_cities() if c in text), None)
    intent = TripIntent(
        city=city,
        days=_parse_days(text),
        budget=_parse_budget(text),
        people=_parse_people(text),
        pace=_parse_pace(text),
        preferences=_parse_preferences(text),
        source="rule",
    )
    _fill_defaults(intent)
    return intent


def _fill_defaults(intent: TripIntent) -> None:
    """缺失参数不直接报错，而是补默认值并记录 assumed，便于在输出里标注。"""
    if intent.days is None:
        intent.days = 3
        intent.assumed["days"] = "未提供天数，默认按 3 天规划"
    if intent.city is None:
        intent.missing.append("city")
    if intent.budget is None:
        intent.assumed["budget"] = "未提供预算，按中等预算估算"


SYSTEM_PROMPT = """你是旅游需求解析器。把用户的一句话需求抽取成 JSON。
字段：
- city: 城市名，只从给定城市列表中选择；无法确定填 null
- days: 整数天数；未提及填 null
- budget: 数字，人民币总预算；未提及填 null
- people: 只能是 亲子 / 老年 / 情侣 / 商务 / 独自 之一
- pace: 只能是 relaxed / normal / packed 之一
- preferences: 数组，可含 美食/自然/人文/购物/拍照
只输出 JSON，不要解释。"""

# LLM 常把人群说成「父母」「带娃」这类自然表达，必须归一到 5 类枚举，
# 否则会被下游当成非法值丢弃（早期版本会直接降级为「独自」）。
PEOPLE_ALIAS = {
    "父母": "老年", "爸妈": "老年", "老人": "老年", "长辈": "老年", "老年人": "老年",
    "孩子": "亲子", "小孩": "亲子", "带娃": "亲子", "亲子游": "亲子", "家庭": "亲子",
    "情侣": "情侣", "夫妻": "情侣", "恋人": "情侣", "对象": "情侣", "蜜月": "情侣",
    "出差": "商务", "商务": "商务", "客户": "商务", "团建": "商务",
    "独自": "独自", "一个人": "独自", "单人": "独自", "solo": "独自",
}


def _normalize_people(raw: str | None) -> str:
    if not raw:
        return "独自"
    raw = str(raw).strip()
    if raw in PEOPLE_KEYWORDS:
        return raw
    if raw in PEOPLE_ALIAS:
        return PEOPLE_ALIAS[raw]
    for alias, target in PEOPLE_ALIAS.items():
        if alias in raw:
            return target
    return "独自"


def parse(text: str, llm: LLMClient | None = None) -> TripIntent:
    llm = llm or LLMClient()
    if llm.available:
        try:
            data = llm.complete_json(
                SYSTEM_PROMPT,
                f"可选城市：{', '.join(attractions.list_cities())}\n用户需求：{text}",
                temperature=0.1,
            )
            intent = TripIntent(
                city=data.get("city"),
                days=data.get("days"),
                budget=data.get("budget"),
                people=_normalize_people(data.get("people")),
                pace=data.get("pace") or "normal",
                preferences=data.get("preferences") or [],
                source="llm",
            )
            if intent.pace not in {"relaxed", "normal", "packed"}:
                intent.pace = "normal"
            _fill_defaults(intent)
            return intent
        except (LLMUnavailable, RuntimeError, ValueError):
            pass  # 统一降级到规则引擎
    return parse_with_rules(text)
