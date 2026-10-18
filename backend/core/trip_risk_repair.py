"""RC-LRA: Risk-Constrained Local Repair Algorithm

面向旅游行程的风险约束局部调整算法。
在不重新调用 LLM 的前提下，基于天气、路线距离、单日负载、住宿位置和坐标完整性等约束，
对结构化行程进行风险检测，并通过路线重排、跨日景点交换和过载景点迁移等局部操作降低行程风险。
"""

from __future__ import annotations

import math
from typing import Optional, Dict, List, Tuple

from core.logger import logger
from core.planning_context import TripPlanningContext
from schemas.trip import TripPlan, DayPlan, Attraction, Hotel, WeatherInfo, Location


# ========== 常量 ==========

BAD_WEATHER_KEYWORDS = [
    "雨", "中雨", "大雨", "暴雨", "雷阵雨",
    "雪", "大雪", "暴雪", "大风", "台风", "高温", "严寒",
]

OUTDOOR_KEYWORDS = [
    "湖", "山", "公园", "湿地", "古城", "城墙", "沙滩", "海滩",
    "街", "巷", "广场", "夜市", "步道", "环岛路", "长城",
]

INDOOR_KEYWORDS = [
    "博物馆", "美术馆", "纪念馆", "商场", "购物中心",
    "剧院", "展览馆", "科技馆", "室内", "馆",
]

LIGHT_TRAVEL_KEYWORDS = ["老人", "父母", "亲子", "小孩", "轻松", "慢游", "不赶"]

LOW_PRIORITY_KEYWORDS = ["购物", "商业街", "夜市", "广场"]

# 固定景点集合（优先于关键词判断）
KNOWN_OUTDOOR_ATTRACTIONS = {
    "西湖", "断桥", "苏堤", "雷峰塔", "环岛路", "白城沙滩",
    "长城", "天安门", "大唐不夜城", "西安城墙", "城墙",
    "青城山", "都江堰", "鼓浪屿", "曾厝垵", "宽窄巷子",
    "回民街", "中山路", "南锣鼓巷", "什刹海",
    "西溪湿地", "千岛湖", "湘湖", "九溪",
}

KNOWN_INDOOR_ATTRACTIONS = {
    "陕西历史博物馆", "金沙遗址", "碑林博物馆", "中国国家博物馆",
    "成都博物馆", "杭州博物馆", "厦门市博物馆", "科技馆", "美术馆",
    "纪念馆", "展览馆", "故宫博物院", "兵马俑",
}

# 阈值
NORMAL_MAX_ATTRACTIONS = 4
LIGHT_MAX_ATTRACTIONS = 3
NORMAL_MAX_ADJACENT_KM = 10.0
LIGHT_MAX_ADJACENT_KM = 8.0
NORMAL_MAX_DAILY_KM = 25.0
LIGHT_MAX_DAILY_KM = 20.0
NORMAL_HOTEL_MAX_KM = 12.0
LIGHT_HOTEL_MAX_KM = 10.0
EXTREME_HEAT_TEMP = 35


# ========== 工具函数 ==========

def _safe_int(value) -> Optional[int]:
    """安全地将温度值转为 int，兼容 str/int/float/None。无法解析时返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = (
            value.replace("°C", "")
            .replace("℃", "")
            .replace("°", "")
            .replace("度", "")
            .strip()
        )
        if not cleaned:
            return None
        try:
            return int(float(cleaned))
        except Exception:
            return None
    return None


def _haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 公式计算两点间距离（千米）"""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _is_bad_weather(weather: WeatherInfo) -> bool:
    """判断是否为恶劣天气，同时检查 day_weather + night_weather + wind_power + 温度"""
    text = f"{weather.day_weather} {weather.night_weather} {weather.wind_power}"
    if any(k in text for k in BAD_WEATHER_KEYWORDS):
        return True
    day_temp = _safe_int(weather.day_temp)
    night_temp = _safe_int(weather.night_temp)
    # 高温：明确 >= 35
    if day_temp is not None and day_temp >= EXTREME_HEAT_TEMP:
        return True
    if night_temp is not None and night_temp >= EXTREME_HEAT_TEMP:
        return True
    # 低温：严格 < 0，避免 schema 默认 0 误判
    if day_temp is not None and day_temp < 0:
        return True
    if night_temp is not None and night_temp < 0:
        return True
    return False


def _is_indoor_attraction(name: str, category: Optional[str] = None, description: str = "") -> bool:
    """判断是否为室内景点：先查固定集合，再查名称/描述关键词，再查 category。

    注意：不把 category="景点" 作为室内依据，因为"景点"是默认值不含语义。
    """
    text = f"{name} {category or ''} {description or ''}"
    if name in KNOWN_INDOOR_ATTRACTIONS:
        return True
    if name in KNOWN_OUTDOOR_ATTRACTIONS:
        return False
    if any(k in text for k in INDOOR_KEYWORDS):
        return True
    if category and any(k in category for k in ("室内", "博物馆", "美术馆", "科技馆", "纪念馆", "展馆")):
        return True
    return False


def _is_outdoor_attraction(name: str, category: Optional[str] = None, description: str = "") -> bool:
    """判断是否为户外景点：先查固定集合，再排除室内，再查 category，再查名称关键词。

    注意：不把 category="景点" 作为户外依据，因为"景点"是默认值不含语义。
    先检查 _is_indoor_attraction 以避免博物馆类（category=景点）被误判为户外。
    """
    if name in KNOWN_OUTDOOR_ATTRACTIONS:
        return True
    if name in KNOWN_INDOOR_ATTRACTIONS:
        return False
    if _is_indoor_attraction(name, category, description):
        return False
    if category and any(k in category for k in ("户外", "自然", "公园", "园林", "山水")):
        return True
    return any(k in name for k in OUTDOOR_KEYWORDS)


def _is_light_travel_request(preferences: List[str], free_text: str) -> bool:
    """判断是否为轻松型旅行需求"""
    combined = " ".join(preferences) + " " + (free_text or "")
    return any(k in combined for k in LIGHT_TRAVEL_KEYWORDS)


def _is_low_priority_attraction(name: str) -> bool:
    """判断是否为低优先级景点（过载移动时优先移除）"""
    return any(k in name for k in LOW_PRIORITY_KEYWORDS)


def _get_attraction_coord(a: Attraction) -> Optional[Tuple[float, float]]:
    """获取景点坐标。返回 (latitude, longitude) 顺序。

    注意：Location schema 中字段声明顺序是 longitude/latitude，
    但本函数统一返回 (latitude, longitude) 供 Haversine 使用。
    """
    if a.location and a.location.latitude and a.location.longitude:
        return (a.location.latitude, a.location.longitude)
    return None


def _get_hotel_coord(day: DayPlan) -> Optional[Tuple[float, float]]:
    """获取酒店坐标。返回 (latitude, longitude) 顺序。"""
    if day.hotel and day.hotel.location and day.hotel.location.latitude and day.hotel.location.longitude:
        return (day.hotel.location.latitude, day.hotel.location.longitude)
    return None


def _get_weather_for_day(day: DayPlan, weather_info: List[WeatherInfo]) -> Optional[WeatherInfo]:
    """根据日期匹配天气信息"""
    for w in weather_info:
        if w.date == day.date:
            return w
    return None


def _calculate_day_route_distance(day: DayPlan) -> float:
    """计算单日相邻景点路线总距离（千米）"""
    coords = []
    for a in day.attractions:
        c = _get_attraction_coord(a)
        if c:
            coords.append(c)

    if len(coords) < 2:
        return 0.0

    total = 0.0
    for i in range(len(coords) - 1):
        total += _haversine_distance_km(
            coords[i][0], coords[i][1],
            coords[i + 1][0], coords[i + 1][1],
        )
    return total


def _count_attractions_with_coords(day: DayPlan) -> int:
    """统计当天有坐标的景点数量"""
    return sum(1 for a in day.attractions if _get_attraction_coord(a))


def _has_adjacent_distance_violation(day: DayPlan, max_adjacent_km: float) -> bool:
    """检查当天是否存在相邻景点距离超过阈值的情况"""
    prev_coord = None
    for attraction in day.attractions:
        coord = _get_attraction_coord(attraction)
        if coord and prev_coord:
            dist = _haversine_distance_km(
                prev_coord[0], prev_coord[1], coord[0], coord[1]
            )
            if dist > max_adjacent_km:
                return True
        if coord:
            prev_coord = coord
    return False


def _make_risk_id(day_index: int, seq: int) -> str:
    """生成风险 ID: RISK-D{day_index+1}-{3位序号}"""
    return f"RISK-D{day_index + 1}-{seq:03d}"


# ========== 风险评分函数 ==========

def calculate_risk_score(plan: TripPlan, context: TripPlanningContext) -> Dict:
    """计算行程风险评分，各维度归一化到 0~1。

    Risk(P) = 0.30*V_weather + 0.25*V_load + 0.25*V_distance + 0.10*V_hotel + 0.10*V_missing
    """
    total_days = len(plan.days)
    if total_days == 0:
        return {"total_score": 0.0, "weather_score": 0.0, "load_score": 0.0,
                "distance_score": 0.0, "hotel_score": 0.0, "missing_score": 0.0}

    is_light = _is_light_travel_request(
        context.preferences, context.request.free_text_input or ""
    )
    max_attractions = LIGHT_MAX_ATTRACTIONS if is_light else NORMAL_MAX_ATTRACTIONS
    max_daily_km = LIGHT_MAX_DAILY_KM if is_light else NORMAL_MAX_DAILY_KM
    max_hotel_km = LIGHT_HOTEL_MAX_KM if is_light else NORMAL_HOTEL_MAX_KM

    # V_weather
    weather_bad_days = 0
    if plan.weather_info:
        for day in plan.days:
            w = _get_weather_for_day(day, plan.weather_info)
            if w and _is_bad_weather(w):
                outdoor = [a for a in day.attractions if _is_outdoor_attraction(a.name, a.category, a.description)]
                if outdoor:
                    weather_bad_days += 1
    v_weather = weather_bad_days / total_days

    # V_load
    overload_days = sum(1 for d in plan.days if len(d.attractions) > max_attractions)
    v_load = overload_days / total_days

    # V_distance（与 _detect_route_distance_risks 保持一致：总距离或相邻距离任一超限即计）
    max_adjacent_km = LIGHT_MAX_ADJACENT_KM if is_light else NORMAL_MAX_ADJACENT_KM
    distance_bad_days = 0
    for day in plan.days:
        daily_dist = _calculate_day_route_distance(day)
        has_adjacent_bad = _has_adjacent_distance_violation(day, max_adjacent_km)
        if daily_dist > max_daily_km or has_adjacent_bad:
            distance_bad_days += 1
    v_distance = distance_bad_days / total_days

    # V_hotel
    hotel_bad_days = 0
    for day in plan.days:
        hotel_coord = _get_hotel_coord(day)
        if hotel_coord and day.attractions:
            first_coord = _get_attraction_coord(day.attractions[0])
            last_coord = _get_attraction_coord(day.attractions[-1])
            max_dist = 0.0
            if first_coord:
                max_dist = max(max_dist, _haversine_distance_km(
                    hotel_coord[0], hotel_coord[1], first_coord[0], first_coord[1]))
            if last_coord:
                max_dist = max(max_dist, _haversine_distance_km(
                    hotel_coord[0], hotel_coord[1], last_coord[0], last_coord[1]))
            if max_dist > max_hotel_km:
                hotel_bad_days += 1
    v_hotel = hotel_bad_days / total_days

    # V_missing
    total_attractions = sum(len(d.attractions) for d in plan.days)
    missing_count = 0
    for day in plan.days:
        for a in day.attractions:
            if not _get_attraction_coord(a):
                missing_count += 1
    v_missing = missing_count / total_attractions if total_attractions > 0 else 0.0

    total = (0.30 * v_weather + 0.25 * v_load + 0.25 * v_distance
             + 0.10 * v_hotel + 0.10 * v_missing)

    return {
        "total_score": round(total, 4),
        "weather_score": round(v_weather, 4),
        "load_score": round(v_load, 4),
        "distance_score": round(v_distance, 4),
        "hotel_score": round(v_hotel, 4),
        "missing_score": round(v_missing, 4),
    }


# ========== 风险检测引擎 ==========

class TripRiskRepairEngine:
    """RC-LRA 行程风险识别与局部调整引擎"""

    def evaluate_and_repair(self, context: TripPlanningContext) -> TripPlanningContext:
        """执行完整的风险识别与局部调整流程"""
        plan = context.normalized_plan
        if plan is None:
            logger.warning("[RC-LRA] normalized_plan 为空，跳过风险识别")
            context.risk_evaluation_enabled = False
            return context

        # 1. 修复前评分
        pre_score = calculate_risk_score(plan, context)
        context.risk_score_before = pre_score
        logger.info(f"[阶段7] 修复前风险分数: {pre_score}")

        # 2. 风险检测
        risks = self.detect_risks(plan, context)
        logger.info(f"[阶段7] 识别风险数量: {len(risks)}")
        logger.info(f"[阶段7] 可修复风险数量: {sum(1 for r in risks if r.get('repairable'))}")

        # 3. 局部修复（基于 deep copy）
        repaired_plan, repair_log = self.repair_plan(plan, risks, context)
        repair_attempted = len(repair_log)
        repair_accepted = sum(1 for x in repair_log if x.get("accepted"))
        repaired_count = sum(1 for r in risks if r.get("repaired"))
        logger.info(f"[阶段7] 修复尝试数量: {repair_attempted}")
        logger.info(f"[阶段7] 成功接受修复数量: {repair_accepted}")

        # 4. 修复后评分
        post_score = calculate_risk_score(repaired_plan, context)
        context.risk_score_after = post_score
        logger.info(f"[阶段7] 修复后风险分数: {post_score}")

        # 5. 标记模块已启用
        context.risk_evaluation_enabled = True

        # 6. 写回 context
        context.normalized_plan = repaired_plan
        context.risks = risks
        context.repair_log = repair_log
        return context

    def detect_risks(self, plan: TripPlan, context: TripPlanningContext) -> List[dict]:
        """检测全部 5 类风险"""
        risks: List[dict] = []
        risks.extend(self._detect_weather_risks(plan, context))
        risks.extend(self._detect_daily_load_risks(plan, context))
        risks.extend(self._detect_route_distance_risks(plan, context))
        risks.extend(self._detect_hotel_location_risks(plan, context))
        risks.extend(self._detect_location_missing_risks(plan, context))

        # 统一分配 risk_id
        for i, risk in enumerate(risks):
            day_idx = risk.get("day_index", 0)
            risk["risk_id"] = _make_risk_id(day_idx, i + 1)

        return risks

    def repair_plan(
        self,
        plan: TripPlan,
        risks: List[dict],
        context: TripPlanningContext,
    ) -> Tuple[TripPlan, List[dict]]:
        """对可修复风险执行局部修复。

        必须基于 plan.model_copy(deep=True) 操作，不直接修改输入 plan。
        每个修复动作遵守风险单调不增原则：每次修复前计算当前 before_score，
        修复后 after_score <= before_score 才接受，否则回滚。
        """
        repaired_plan = plan.model_copy(deep=True)
        repair_log: List[dict] = []

        # 修复1: 路线最近邻重排
        route_risks = [r for r in risks if r["type"] == "route_distance_too_long" and r.get("repairable")]
        if route_risks:
            self._repair_route_order(repaired_plan, route_risks, context, repair_log)

        # 修复2: 过载景点移动
        load_risks = [r for r in risks if r["type"] == "daily_load_overflow" and r.get("repairable")]
        if load_risks:
            self._repair_daily_load(repaired_plan, load_risks, context, repair_log)

        # 修复3: 雨天户外/非雨天室内交换
        weather_risks = [r for r in risks if r["type"] == "weather_outdoor_conflict" and r.get("repairable")]
        if weather_risks:
            self._repair_weather_conflicts(repaired_plan, weather_risks, context, repair_log)

        # 标记修复后状态到 risks 列表
        repaired_risk_ids = {entry["risk_id"] for entry in repair_log if entry.get("accepted")}
        for risk in risks:
            risk["repaired"] = risk.get("risk_id") in repaired_risk_ids

        return repaired_plan, repair_log

    # ========== 风险检测实现 ==========

    def _detect_weather_risks(self, plan: TripPlan, context: TripPlanningContext) -> List[dict]:
        """检测天气冲突风险：恶劣天气 + 户外景点"""
        risks: List[dict] = []
        if not plan.weather_info:
            return risks

        for day in plan.days:
            weather = _get_weather_for_day(day, plan.weather_info)
            if not weather or not _is_bad_weather(weather):
                continue

            outdoor_attractions = [
                a.name for a in day.attractions
                if _is_outdoor_attraction(a.name, a.category, a.description)
            ]
            if not outdoor_attractions:
                continue

            weather_text = weather.day_weather or weather.night_weather or "恶劣天气"
            risks.append({
                "type": "weather_outdoor_conflict",
                "level": "medium",
                "day_index": day.day_index,
                "title": f"第{day.day_index + 1}天雨天户外景点较多",
                "description": (
                    f"第{day.day_index + 1}天天气为{weather_text}，"
                    f"但安排了{'、'.join(outdoor_attractions[:3])}"
                    f"{'等' if len(outdoor_attractions) > 3 else ''}户外景点。"
                ),
                "evidence": {
                    "weather": weather_text,
                    "affected_attractions": outdoor_attractions,
                },
                "suggestion": "建议减少户外游览，优先安排室内或半室内景点。",
                "repairable": True,
                "repaired": False,
            })

        return risks

    def _detect_daily_load_risks(self, plan: TripPlan, context: TripPlanningContext) -> List[dict]:
        """检测单日过载风险"""
        risks: List[dict] = []
        is_light = _is_light_travel_request(
            context.preferences, context.request.free_text_input or ""
        )
        max_attractions = LIGHT_MAX_ATTRACTIONS if is_light else NORMAL_MAX_ATTRACTIONS

        for day in plan.days:
            count = len(day.attractions)
            if count <= max_attractions:
                continue

            risks.append({
                "type": "daily_load_overflow",
                "level": "medium",
                "day_index": day.day_index,
                "title": f"第{day.day_index + 1}天景点安排过密",
                "description": (
                    f"第{day.day_index + 1}天安排了{count}个景点，"
                    f"超过{'轻松型' if is_light else '普通'}推荐上限{max_attractions}个。"
                ),
                "evidence": {
                    "attraction_count": count,
                    "max_recommended": max_attractions,
                    "travel_style": "light" if is_light else "normal",
                },
                "suggestion": f"建议减少至{max_attractions}个景点以内，保证游览质量。",
                "repairable": True,
                "repaired": False,
            })

        return risks

    def _detect_route_distance_risks(self, plan: TripPlan, context: TripPlanningContext) -> List[dict]:
        """检测路线跨度过大风险"""
        risks: List[dict] = []
        is_light = _is_light_travel_request(
            context.preferences, context.request.free_text_input or ""
        )
        max_adjacent_km = LIGHT_MAX_ADJACENT_KM if is_light else NORMAL_MAX_ADJACENT_KM
        max_daily_km = LIGHT_MAX_DAILY_KM if is_light else NORMAL_MAX_DAILY_KM

        for day in plan.days:
            daily_dist = _calculate_day_route_distance(day)

            # 检查相邻景点距离
            has_adjacent_long = False
            long_pairs: List[str] = []
            prev_coord = None
            prev_name = None
            for a in day.attractions:
                coord = _get_attraction_coord(a)
                if coord and prev_coord:
                    dist = _haversine_distance_km(
                        prev_coord[0], prev_coord[1], coord[0], coord[1]
                    )
                    if dist > max_adjacent_km:
                        has_adjacent_long = True
                        long_pairs.append(f"{prev_name}→{a.name}({dist:.1f}km)")
                prev_coord = coord
                prev_name = a.name

            if has_adjacent_long:
                risks.append({
                    "type": "route_distance_too_long",
                    "level": "medium",
                    "day_index": day.day_index,
                    "title": f"第{day.day_index + 1}天相邻景点距离过远",
                    "description": (
                        f"第{day.day_index + 1}天存在相邻景点距离超过{max_adjacent_km}km："
                        f"{'、'.join(long_pairs[:3])}。"
                    ),
                    "evidence": {
                        "long_pairs": long_pairs,
                        "max_adjacent_km": max_adjacent_km,
                    },
                    "suggestion": "建议优化游览顺序，减少跨区域移动。",
                    "repairable": True,
                    "repaired": False,
                })
            elif daily_dist > max_daily_km:
                risks.append({
                    "type": "route_distance_too_long",
                    "level": "low",
                    "day_index": day.day_index,
                    "title": f"第{day.day_index + 1}天路线总距离较长",
                    "description": (
                        f"第{day.day_index + 1}天路线总距离{daily_dist:.1f}km，"
                        f"超过{'轻松型' if is_light else '普通'}推荐上限{max_daily_km}km。"
                    ),
                    "evidence": {
                        "daily_distance_km": round(daily_dist, 1),
                        "max_daily_km": max_daily_km,
                    },
                    "suggestion": "建议优化游览顺序，减少当天移动距离。",
                    "repairable": True,
                    "repaired": False,
                })

        return risks

    def _detect_hotel_location_risks(self, plan: TripPlan, context: TripPlanningContext) -> List[dict]:
        """检测住宿位置不合理风险"""
        risks: List[dict] = []
        is_light = _is_light_travel_request(
            context.preferences, context.request.free_text_input or ""
        )
        max_hotel_km = LIGHT_HOTEL_MAX_KM if is_light else NORMAL_HOTEL_MAX_KM

        for day in plan.days:
            hotel_coord = _get_hotel_coord(day)
            if not hotel_coord or not day.attractions:
                continue

            first_coord = _get_attraction_coord(day.attractions[0])
            last_coord = _get_attraction_coord(day.attractions[-1])

            max_dist = 0.0
            farthest_attraction = ""
            for coord, name in [
                (first_coord, day.attractions[0].name if day.attractions else ""),
                (last_coord, day.attractions[-1].name if day.attractions else ""),
            ]:
                if coord:
                    d = _haversine_distance_km(
                        hotel_coord[0], hotel_coord[1], coord[0], coord[1]
                    )
                    if d > max_dist:
                        max_dist = d
                        farthest_attraction = name

            if max_dist > max_hotel_km:
                suggestion = f"建议选择距离游玩区域更近的住宿，当前酒店距{farthest_attraction}约{max_dist:.1f}km。"

                # 结合 candidate_areas 给建议
                if context.candidate_areas:
                    areas_text = "、".join(context.candidate_areas[:3])
                    suggestion += f"建议优先选择{areas_text}住宿。"

                risks.append({
                    "type": "hotel_location_mismatch",
                    "level": "low",
                    "day_index": day.day_index,
                    "title": f"第{day.day_index + 1}天住宿位置距游玩区域较远",
                    "description": (
                        f"第{day.day_index + 1}天酒店距主要景点最远{max_dist:.1f}km，"
                        f"超过{'轻松型' if is_light else '普通'}推荐上限{max_hotel_km}km。"
                    ),
                    "evidence": {
                        "hotel_name": day.hotel.name if day.hotel else "",
                        "max_distance_km": round(max_dist, 1),
                        "max_hotel_km": max_hotel_km,
                        "farthest_attraction": farthest_attraction,
                    },
                    "suggestion": suggestion,
                    "repairable": False,
                    "repaired": False,
                })

        return risks

    def _detect_location_missing_risks(self, plan: TripPlan, context: TripPlanningContext) -> List[dict]:
        """检测坐标缺失风险 — 按天聚合"""
        risks: List[dict] = []

        for day in plan.days:
            missing_attractions = [
                a.name for a in day.attractions if not _get_attraction_coord(a)
            ]
            hotel_missing = day.hotel is not None and not _get_hotel_coord(day)

            if not missing_attractions and not hotel_missing:
                continue

            risks.append({
                "type": "location_missing",
                "level": "low",
                "day_index": day.day_index,
                "title": f"第{day.day_index + 1}天部分地点缺少坐标信息",
                "description": (
                    f"第{day.day_index + 1}天"
                    f"{'景点' + '、'.join(missing_attractions[:3]) + '等' if missing_attractions else ''}"
                    f"{'和' if missing_attractions and hotel_missing else ''}"
                    f"{'酒店' if hotel_missing else ''}"
                    f"缺少坐标信息，无法进行路线距离分析。"
                ),
                "evidence": {
                    "missing_attractions": missing_attractions,
                    "hotel_missing": hotel_missing,
                },
                "suggestion": "建议补充坐标信息以获得更准确的风险分析。",
                "repairable": False,
                "repaired": False,
            })

        return risks

    # ========== 局部修复实现 ==========

    def _repair_route_order(
        self,
        plan: TripPlan,
        risks: List[dict],
        context: TripPlanningContext,
        repair_log: List[dict],
    ) -> None:
        """修复动作1: 最近邻路线重排

        每次修复前计算当前 before_score，修复后 after_score <= before_score 且距离下降才接受，
        否则严格回滚到 original_order。
        """
        risk_day_indices = {r["day_index"] for r in risks}

        for day in plan.days:
            if day.day_index not in risk_day_indices:
                continue
            if len(day.attractions) < 2:
                continue

            # 保存原始顺序用于回滚
            original_order = list(day.attractions)

            # 分离有/无坐标景点
            with_coord: List[Tuple[Attraction, Tuple[float, float]]] = []
            without_coord: List[Attraction] = []
            for a in day.attractions:
                c = _get_attraction_coord(a)
                if c:
                    with_coord.append((a, c))
                else:
                    without_coord.append(a)

            if len(with_coord) < 2:
                continue

            # 记录修复前指标
            old_dist = _calculate_day_route_distance(day)
            before_score = calculate_risk_score(plan, context)["total_score"]

            # 最近邻重排
            # 起点: 酒店坐标 或 第一个有坐标景点
            hotel_coord = _get_hotel_coord(day)
            if hotel_coord:
                start = hotel_coord
            else:
                start = with_coord[0][1]

            ordered: List[Attraction] = []
            remaining = list(with_coord)
            current = start

            while remaining:
                nearest_idx = 0
                nearest_dist = float("inf")
                for i, (_, coord) in enumerate(remaining):
                    d = _haversine_distance_km(
                        current[0], current[1], coord[0], coord[1]
                    )
                    if d < nearest_dist:
                        nearest_dist = d
                        nearest_idx = i

                attraction, coord = remaining.pop(nearest_idx)
                ordered.append(attraction)
                current = coord

            # 无坐标景点附在末尾
            ordered.extend(without_coord)

            # 应用重排
            day.attractions = ordered
            new_dist = _calculate_day_route_distance(day)
            after_score = calculate_risk_score(plan, context)["total_score"]

            risk_id = next(
                (r["risk_id"] for r in risks if r["day_index"] == day.day_index),
                "",
            )

            if new_dist < old_dist and after_score <= before_score:
                # 距离下降且风险分不升高，接受
                repair_log.append({
                    "risk_id": risk_id,
                    "action": "route_reorder",
                    "day_index": day.day_index,
                    "before_metric": round(old_dist, 1),
                    "after_metric": round(new_dist, 1),
                    "before_score": round(before_score, 4),
                    "after_score": round(after_score, 4),
                    "accepted": True,
                    "reason": "accepted: distance reduced and risk score not increased",
                })
            else:
                # 严格回滚到原始顺序
                day.attractions = original_order
                reason = (
                    "rejected: distance not reduced"
                    if new_dist >= old_dist
                    else "rejected: risk_score_increased"
                )
                repair_log.append({
                    "risk_id": risk_id,
                    "action": "route_reorder",
                    "day_index": day.day_index,
                    "before_metric": round(old_dist, 1),
                    "after_metric": round(new_dist, 1),
                    "before_score": round(before_score, 4),
                    "after_score": round(after_score, 4),
                    "accepted": False,
                    "reason": reason,
                })

    def _repair_daily_load(
        self,
        plan: TripPlan,
        risks: List[dict],
        context: TripPlanningContext,
        repair_log: List[dict],
    ) -> None:
        """修复动作3: 过载景点移动到其他日期

        每次修复前计算当前 before_score，修复后 after_score <= before_score 才接受。
        """
        is_light = _is_light_travel_request(
            context.preferences, context.request.free_text_input or ""
        )
        max_attractions = LIGHT_MAX_ATTRACTIONS if is_light else NORMAL_MAX_ATTRACTIONS

        risk_day_indices = sorted(r["day_index"] for r in risks)

        for day_idx in risk_day_indices:
            if day_idx >= len(plan.days):
                continue
            day = plan.days[day_idx]

            while len(day.attractions) > max_attractions:
                # 找低优先级景点（优先移最后一个低优先级）
                moved = False

                # 先尝试最后一个低优先级
                for i in range(len(day.attractions) - 1, -1, -1):
                    a = day.attractions[i]
                    if _is_low_priority_attraction(a.name) or i == len(day.attractions) - 1:
                        # 尝试移动到后续日期
                        target_day = self._find_underloaded_day(plan, day_idx, max_attractions, forward=True)
                        if target_day is None:
                            target_day = self._find_underloaded_day(plan, day_idx, max_attractions, forward=False)

                        if target_day is not None:
                            before_score = calculate_risk_score(plan, context)["total_score"]
                            attraction_to_move = day.attractions.pop(i)
                            target_day.attractions.append(attraction_to_move)
                            after_score = calculate_risk_score(plan, context)["total_score"]

                            if after_score <= before_score:
                                repair_log.append({
                                    "risk_id": next(
                                        (r["risk_id"] for r in risks if r["day_index"] == day_idx),
                                        "",
                                    ),
                                    "action": "daily_load_move_attraction",
                                    "day_index": day_idx,
                                    "moved_attraction": attraction_to_move.name,
                                    "target_day_index": target_day.day_index,
                                    "before_score": round(before_score, 4),
                                    "after_score": round(after_score, 4),
                                    "accepted": True,
                                    "reason": "accepted: risk score not increased",
                                })
                                moved = True
                                break
                            else:
                                # 回滚
                                target_day.attractions.pop()
                                day.attractions.insert(i, attraction_to_move)

                if not moved:
                    break  # 无法移动更多景点

    def _find_underloaded_day(
        self,
        plan: TripPlan,
        current_day_index: int,
        max_attractions: int,
        forward: bool = True,
    ) -> Optional[DayPlan]:
        """找到未过载的目标日期"""
        if forward:
            for day in plan.days:
                if day.day_index > current_day_index and len(day.attractions) < max_attractions:
                    return day
        else:
            for day in reversed(plan.days):
                if day.day_index < current_day_index and len(day.attractions) < max_attractions:
                    return day
        return None

    def _repair_weather_conflicts(
        self,
        plan: TripPlan,
        risks: List[dict],
        context: TripPlanningContext,
        repair_log: List[dict],
    ) -> None:
        """修复动作2: 雨天户外景点与非雨天室内景点交换

        每次修复前计算当前 before_score，修复后 after_score <= before_score 才接受。
        """
        if not plan.weather_info:
            return

        is_light = _is_light_travel_request(
            context.preferences, context.request.free_text_input or ""
        )
        max_attractions = LIGHT_MAX_ATTRACTIONS if is_light else NORMAL_MAX_ATTRACTIONS

        for risk in risks:
            day_idx = risk["day_index"]
            if day_idx >= len(plan.days):
                continue

            bad_day = plan.days[day_idx]
            weather = _get_weather_for_day(bad_day, plan.weather_info)
            if not weather or not _is_bad_weather(weather):
                continue

            # 找当天户外景点
            outdoor_indices = [
                i for i, a in enumerate(bad_day.attractions)
                if _is_outdoor_attraction(a.name, a.category, a.description)
            ]
            if not outdoor_indices:
                continue

            # 找非恶劣天气日的室内景点
            swap_done = False
            for other_day in plan.days:
                if other_day.day_index == day_idx:
                    continue
                other_weather = _get_weather_for_day(other_day, plan.weather_info)
                if other_weather and _is_bad_weather(other_weather):
                    continue

                indoor_indices = [
                    i for i, a in enumerate(other_day.attractions)
                    if _is_indoor_attraction(a.name, a.category, a.description)
                ]
                if not indoor_indices:
                    continue

                # 尝试交换第一个户外和第一个室内
                out_idx = outdoor_indices[0]
                in_idx = indoor_indices[0]

                outdoor_attraction = bad_day.attractions[out_idx]
                indoor_attraction = other_day.attractions[in_idx]

                # 检查两天都不超负载（交换不改变数量，但防御性检查）
                if (len(bad_day.attractions) > max_attractions
                        or len(other_day.attractions) > max_attractions):
                    continue

                # 记录修复前状态
                before_score = calculate_risk_score(plan, context)["total_score"]

                # 执行交换
                bad_day.attractions[out_idx] = indoor_attraction
                other_day.attractions[in_idx] = outdoor_attraction

                after_score = calculate_risk_score(plan, context)["total_score"]

                if after_score <= before_score:
                    repair_log.append({
                        "risk_id": risk["risk_id"],
                        "action": "weather_indoor_outdoor_swap",
                        "day_index": day_idx,
                        "outdoor_attraction": outdoor_attraction.name,
                        "indoor_attraction": indoor_attraction.name,
                        "swap_with_day_index": other_day.day_index,
                        "before_score": round(before_score, 4),
                        "after_score": round(after_score, 4),
                        "accepted": True,
                        "reason": "accepted: risk score not increased",
                    })
                    swap_done = True
                    break
                else:
                    # 回滚
                    bad_day.attractions[out_idx] = outdoor_attraction
                    other_day.attractions[in_idx] = indoor_attraction

            if not swap_done:
                repair_log.append({
                    "risk_id": risk["risk_id"],
                    "action": "weather_indoor_outdoor_swap",
                    "day_index": day_idx,
                    "accepted": False,
                    "reason": "no_suitable_swap_candidate",
                })
