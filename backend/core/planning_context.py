"""行程规划上下文 — 阶段式编排的内部数据流与候选抽取"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set
from collections import Counter

from core.logger import logger
from schemas.trip import TripRequest, TripPlan


# ========== 扩展地标词典 ==========

EXTENDED_LANDMARKS: Dict[str, List[str]] = {
    "杭州": [
        "西湖", "灵隐寺", "雷峰塔", "断桥", "河坊街", "西溪湿地",
        "苏堤", "梅家坞", "湖滨", "武林广场", "钱江新城", "龙井村",
        "九溪", "六和塔", "宋城", "千岛湖", "湘湖", "良渚",
        "飞来峰", "白堤", "满觉陇", "南宋御街", "小河直街", "大运河",
        "中国丝绸博物馆", "浙江省博物馆", "杭州博物馆", "中国茶叶博物馆",
        "九溪十八涧", "龙井", "黄龙", "拱宸桥", "凤起路",
    ],
    "成都": [
        "大熊猫基地", "宽窄巷子", "锦里", "春熙路", "都江堰", "青城山",
        "武侯祠", "杜甫草堂", "太古里", "人民公园", "文殊院", "金沙遗址",
        "九眼桥", "玉林路", "望江楼", "天府广场",
        "青羊宫", "浣花溪公园", "东郊记忆", "琴台路", "四川博物院",
        "望平街", "芳草街", "成都博物馆", "双流机场", "天府机场",
        "灌县古城", "青城前山", "青城后山",
    ],
    "北京": [
        "故宫", "天安门", "颐和园", "长城", "天坛", "圆明园",
        "王府井", "南锣鼓巷", "什刹海", "鸟巢", "水立方",
        "景山公园", "北海公园", "雍和宫", "国子监", "恭王府", "前门",
        "八达岭长城", "慕田峪长城", "天安门广场", "中国国家博物馆",
        "798艺术区", "三里屯", "牛街", "簋街",
        "五道营", "杨梅竹斜街", "首都博物馆", "钟楼", "鼓楼",
        "北京动物园", "朝阳公园", "亮马河",
    ],
    "西安": [
        "兵马俑", "大唐不夜城", "华清宫", "大雁塔", "回民街", "钟楼",
        "鼓楼", "城墙", "陕西历史博物馆", "碑林", "小雁塔", "大唐芙蓉园",
        "永兴坊", "洒金桥", "曲江池",
        "华山", "大唐西市", "西安博物院", "书院门", "永宁门",
        "秦始皇陵", "临潼", "大慈恩寺", "西安城墙",
    ],
    "厦门": [
        "鼓浪屿", "曾厝垵", "环岛路", "厦门大学", "中山路",
        "南普陀寺", "胡里山炮台", "集美学村", "白城沙滩", "沙坡尾",
        "万石植物园",
        "八市", "黄厝", "园博苑", "菽庄花园", "日光岩",
        "演武大桥", "顶澳仔猫街", "椰风寨", "龙舟池",
    ],
}

AREA_KEYWORDS: Dict[str, List[str]] = {
    "杭州": ["西湖周边", "湖滨", "武林", "灵隐寺周边", "钱江新城", "西溪周边",
             "大运河周边", "龙井", "满觉陇"],
    "成都": ["春熙路周边", "宽窄巷子周边", "太古里周边", "武侯祠周边", "大熊猫基地周边",
             "浣花溪周边", "九眼桥周边", "玉林周边", "东郊记忆"],
    "北京": ["王府井", "什刹海", "前门", "三里屯", "颐和园周边", "奥体中心周边",
             "798艺术区", "牛街", "五道营", "亮马河"],
    "西安": ["大雁塔周边", "钟楼周边", "回民街周边", "曲江",
             "书院门", "小寨", "临潼"],
    "厦门": ["鼓浪屿", "中山路周边", "曾厝垵周边", "厦大周边",
             "八市周边", "黄厝", "集美", "园博苑"],
}

# 景点 → 区域反推映射
ATTRACTION_AREA_MAP: Dict[str, str] = {
    # 杭州
    "西湖": "西湖周边", "断桥": "西湖周边", "雷峰塔": "西湖周边",
    "苏堤": "西湖周边", "花港观鱼": "西湖周边", "三潭印月": "西湖周边",
    "灵隐寺": "灵隐寺周边", "六和塔": "灵隐寺周边", "九溪": "灵隐寺周边",
    "西溪湿地": "西溪周边", "河坊街": "湖滨", "湖滨": "湖滨",
    "武林广场": "武林", "龙井村": "西湖周边", "梅家坞": "西湖周边",
    "宋城": "西湖周边", "钱江新城": "钱江新城", "湘湖": "西湖周边",
    "良渚": "西溪周边",
    "飞来峰": "灵隐寺周边", "白堤": "西湖周边", "满觉陇": "西湖周边",
    "南宋御街": "湖滨", "小河直街": "大运河周边", "大运河": "大运河周边",
    "中国丝绸博物馆": "西湖周边", "浙江省博物馆": "西湖周边",
    "杭州博物馆": "湖滨", "中国茶叶博物馆": "西湖周边",
    "九溪十八涧": "灵隐寺周边", "龙井": "龙井", "黄龙": "西湖周边",
    "拱宸桥": "大运河周边", "凤起路": "湖滨",
    # 成都
    "宽窄巷子": "宽窄巷子周边", "人民公园": "宽窄巷子周边",
    "锦里": "武侯祠周边", "武侯祠": "武侯祠周边",
    "春熙路": "春熙路周边", "太古里": "太古里周边",
    "大熊猫基地": "大熊猫基地周边", "文殊院": "春熙路周边",
    "杜甫草堂": "武侯祠周边", "金沙遗址": "春熙路周边",
    "九眼桥": "九眼桥周边", "玉林路": "玉林周边",
    "天府广场": "春熙路周边", "望江楼": "太古里周边",
    "青羊宫": "浣花溪周边", "浣花溪公园": "浣花溪周边",
    "东郊记忆": "东郊记忆", "琴台路": "宽窄巷子周边",
    "四川博物院": "浣花溪周边", "成都博物馆": "春熙路周边",
    "望平街": "太古里周边", "芳草街": "玉林周边",
    "灌县古城": "都江堰", "青城前山": "都江堰", "青城后山": "都江堰",
    # 北京
    "故宫": "王府井", "天安门": "前门", "景山公园": "王府井",
    "王府井": "王府井", "前门": "前门", "天坛": "前门",
    "南锣鼓巷": "什刹海", "什刹海": "什刹海", "北海公园": "什刹海",
    "雍和宫": "什刹海", "恭王府": "什刹海", "国子监": "什刹海",
    "颐和园": "颐和园周边", "圆明园": "颐和园周边", "长城": "前门",
    "鸟巢": "奥体中心周边", "水立方": "奥体中心周边",
    "八达岭长城": "前门", "慕田峪长城": "前门", "天安门广场": "前门",
    "中国国家博物馆": "前门", "798艺术区": "798艺术区",
    "三里屯": "三里屯", "牛街": "牛街", "簋街": "什刹海",
    "五道营": "五道营", "杨梅竹斜街": "前门", "首都博物馆": "前门",
    "钟楼": "什刹海", "鼓楼": "什刹海",
    "北京动物园": "三里屯", "朝阳公园": "三里屯", "亮马河": "亮马河",
    # 西安
    "大雁塔": "大雁塔周边", "大唐不夜城": "大雁塔周边",
    "大唐芙蓉园": "大雁塔周边", "曲江池": "曲江",
    "钟楼": "钟楼周边", "鼓楼": "钟楼周边",
    "回民街": "回民街周边", "洒金桥": "回民街周边",
    "永兴坊": "钟楼周边", "碑林": "钟楼周边",
    "兵马俑": "大雁塔周边", "华清宫": "大雁塔周边",
    "陕西历史博物馆": "大雁塔周边", "小雁塔": "钟楼周边",
    "华山": "临潼", "大唐西市": "钟楼周边", "西安博物院": "小寨",
    "书院门": "书院门", "永宁门": "钟楼周边", "秦始皇陵": "临潼",
    "大慈恩寺": "大雁塔周边", "西安城墙": "钟楼周边",
    # 厦门
    "鼓浪屿": "鼓浪屿", "中山路": "中山路周边",
    "曾厝垵": "曾厝垵周边", "厦门大学": "厦大周边",
    "南普陀寺": "厦大周边", "白城沙滩": "厦大周边",
    "环岛路": "曾厝垵周边", "胡里山炮台": "厦大周边",
    "沙坡尾": "厦大周边", "集美学村": "集美",
    "万石植物园": "厦大周边",
    "八市": "八市周边", "黄厝": "黄厝", "园博苑": "园博苑",
    "菽庄花园": "鼓浪屿", "日光岩": "鼓浪屿",
    "演武大桥": "厦大周边", "顶澳仔猫街": "厦大周边",
    "椰风寨": "黄厝", "龙舟池": "集美",
}

MAX_CANDIDATE_ATTRACTIONS = 8
MAX_CANDIDATE_AREAS = 5


# ========== 规划上下文 ==========

@dataclass
class TripPlanningContext:
    """阶段式编排的内部上下文，不暴露给前端"""

    request: TripRequest
    city: str = ""
    travel_days: int = 1
    preferences: List[str] = field(default_factory=list)

    # 阶段2: RAG
    rag_query: str = ""
    rag_results: List[dict] = field(default_factory=list)
    rag_context: str = ""

    # 阶段3: 候选抽取
    candidate_attractions: List[str] = field(default_factory=list)
    candidate_areas: List[str] = field(default_factory=list)
    guide_preferences: List[str] = field(default_factory=list)
    guide_notes: List[str] = field(default_factory=list)
    key_facts: List[str] = field(default_factory=list)  # 关键事实（票价/免费/避坑，紧凑格式）

    # 阶段4: 外部信息
    attraction_info: str = ""
    weather_info: str = ""
    hotel_info: str = ""
    used_candidate_attractions: bool = False
    used_candidate_areas: bool = False

    # 阶段5: 初始规划
    raw_planner_response: str = ""
    initial_plan: Optional[TripPlan] = None

    # 阶段6: 标准化
    normalized_plan: Optional[TripPlan] = None
    location_fix_applied: bool = False

    # 阶段7: 风险识别与局部调整
    risk_evaluation_enabled: bool = False
    risk_score_before: Dict = field(default_factory=dict)
    risk_score_after: Dict = field(default_factory=dict)
    risks: List[dict] = field(default_factory=list)
    repair_log: List[dict] = field(default_factory=list)

    # 阶段8: 最终
    final_plan: Optional[TripPlan] = None


# ========== 工具函数 ==========

def get_result_text(result: dict) -> str:
    """从 RAG 结果中提取所有可用文本，兼容不同字段结构。

    search_guides_rag() 返回的每条结果可能包含以下字段（位置不固定）：
    - 顶层: title, content, heading_path, section_type, city, text, snippet, tags
    - metadata 内: 同上
    - payload 内: 同上
    - 兼容 metadata=None / payload=None / 非dict 值
    """
    parts: List[str] = []

    if not isinstance(result, dict):
        return ""

    # 顶层字段
    for key in ("title", "heading_path", "content", "text", "snippet", "section_type", "city"):
        value = result.get(key)
        if value:
            parts.append(str(value))

    # tags 顶层字段
    tags = result.get("tags")
    if isinstance(tags, list):
        parts.append(" ".join(str(t) for t in tags if t))
    elif tags:
        parts.append(str(tags))

    # metadata / payload 兼容
    for container_key in ("metadata", "payload"):
        container = result.get(container_key) or {}
        if not isinstance(container, dict):
            continue
        for key in ("title", "heading_path", "content", "text", "snippet", "section_type", "city"):
            value = container.get(key)
            if value:
                parts.append(str(value))
        nested_tags = container.get("tags")
        if isinstance(nested_tags, list):
            parts.append(" ".join(str(t) for t in nested_tags if t))
        elif nested_tags:
            parts.append(str(nested_tags))

    return " ".join(p for p in parts if p)


# ========== 候选抽取 ==========

def _get_tags_from_result(result: dict) -> List[str]:
    """从 RAG 结果中提取 tags，兼容不同字段结构。"""
    if not isinstance(result, dict):
        return []
    for container in (result, result.get("metadata") or {}, result.get("payload") or {}):
        if not isinstance(container, dict):
            continue
        tags = container.get("tags")
        if isinstance(tags, list):
            return [str(t).strip() for t in tags if t]
        elif tags:
            return [str(tags)]
    return []


def _get_section_type_from_result(result: dict) -> str:
    """从 RAG 结果中提取 section_type，兼容不同字段结构。"""
    if not isinstance(result, dict):
        return ""
    for container in (result, result.get("metadata") or {}, result.get("payload") or {}):
        if not isinstance(container, dict):
            continue
        value = container.get("section_type")
        if value:
            return str(value)
    return ""


def extract_candidates_from_guides(context: TripPlanningContext) -> None:
    """从 RAG 结果中抽取候选景点、候选区域、偏好标签和避坑提示。

    纯规则实现，不调用 LLM。直接修改 context 的候选字段。
    """
    from collections import Counter

    city = context.city
    attraction_counter: Counter = Counter()
    area_counter: Counter = Counter()
    preferences_set: Set[str] = set()
    notes_list: List[str] = []

    # 构建当前城市的地标集合
    city_landmarks = set(EXTENDED_LANDMARKS.get(city, []))
    # 兼容其他城市：从 adaptive_tcr_ranker 的 LANDMARK_CITY_MAP 中补充
    try:
        from services.adaptive_tcr_ranker import LANDMARK_CITY_MAP
        for landmark, landmark_city in LANDMARK_CITY_MAP.items():
            if landmark_city == city:
                city_landmarks.add(landmark)
    except ImportError:
        pass

    city_area_keywords = set(AREA_KEYWORDS.get(city, []))

    for result in context.rag_results:
        text = get_result_text(result)
        if not text:
            continue

        # 1. 匹配已知地标
        for landmark in city_landmarks:
            if landmark in text:
                attraction_counter[landmark] += 1

        # 2. 匹配区域关键词
        for area in city_area_keywords:
            if area in text:
                area_counter[area] += 1

        # 3. 从 tags 提取偏好（统一走 _get_tags_from_result）
        tags = _get_tags_from_result(result)
        for tag_str in tags:
            if tag_str and tag_str != city and tag_str not in city_landmarks:
                preferences_set.add(tag_str)

        # 4. 从 section_type 提取避坑提示（统一走 _get_section_type_from_result）
        section_type = _get_section_type_from_result(result)
        if section_type == "tip" and text:
            note = text[:60].strip()
            if note and note not in notes_list:
                notes_list.append(note)

    # 5. 从候选景点反推区域
    for attraction in attraction_counter:
        mapped_area = ATTRACTION_AREA_MAP.get(attraction)
        if mapped_area:
            area_counter[mapped_area] += attraction_counter[attraction]

    # 候选景点排序（按出现次数降序）
    sorted_attractions = sorted(
        attraction_counter.keys(),
        key=lambda a: attraction_counter[a],
        reverse=True,
    )
    context.candidate_attractions = sorted_attractions[:MAX_CANDIDATE_ATTRACTIONS]

    # 候选区域排序（稳定排序：出现次数降序 → 预定义顺序 → 字典序）
    city_area_order = AREA_KEYWORDS.get(city, [])
    order_map = {area: idx for idx, area in enumerate(city_area_order)}
    ranked_areas = sorted(
        area_counter.items(),
        key=lambda item: (-item[1], order_map.get(item[0], 999), item[0]),
    )
    context.candidate_areas = [area for area, _ in ranked_areas[:MAX_CANDIDATE_AREAS]]

    context.guide_preferences = sorted(preferences_set)[:10]
    context.guide_notes = notes_list[:5]

    # 6. 提取关键事实（票价/免费/注意事项等）
    context.key_facts = _extract_key_facts(
        context.rag_results, set(context.candidate_attractions), city
    )
    if context.key_facts:
        logger.info(f"[阶段3] 提取到 {len(context.key_facts)} 条关键事实:")
        for i, fact in enumerate(context.key_facts):
            logger.info(f"[阶段3]   关键事实#{i+1}: {fact}")

    logger.info(
        f"[阶段3] 候选抽取完成: "
        f"attractions={context.candidate_attractions}, "
        f"areas={context.candidate_areas}, "
        f"preferences={context.guide_preferences[:5]}, "
        f"notes={len(context.guide_notes)}, "
        f"key_facts={len(context.key_facts)}"
    )


# ========== 关键事实提取 ==========

_PRICE_KEYWORDS = {"免费", "不收费", "无需购票", "无需门票", "免门票", "门票", "票价", "收费"}


def _extract_key_facts(
    rag_results: List[dict],
    candidate_attractions: set,
    city: str,
) -> List[str]:
    """从 RAG 结果中提取关键事实（票价/免费/避坑），返回紧凑文本列表。

    仅提取与候选景点相关的事实，避免噪声。
    """
    import re

    facts: List[str] = []
    seen: set = set()

    for result in rag_results:
        text = get_result_text(result)
        if not text:
            continue

        # 按句号/换行切句
        sentences = re.split(r"[。\n；;！!]", text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 6 or len(sent) > 120:
                continue

            # 必须包含价格关键词
            has_price = any(kw in sent for kw in _PRICE_KEYWORDS)
            if not has_price:
                continue

            # 去重（相似度 > 80% 视为重复）
            dedup_key = sent[:20]
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # 尝试关联到候选景点
            tagged = False
            for attr in sorted(candidate_attractions, key=len, reverse=True):
                if attr in sent:
                    facts.append(f"{attr}: {sent}")
                    tagged = True
                    break
            if not tagged:
                facts.append(sent)

    # 合并 guide_notes 中的避坑提示
    return facts[:20]  # 最多 20 条


def build_key_facts_text(context: TripPlanningContext) -> str:
    """将关键事实列表格式化为 Planner prompt 用的紧凑文本。"""
    if not context.key_facts:
        return "（暂无提取到的关键事实）"

    lines = []
    for i, fact in enumerate(context.key_facts, 1):
        lines.append(f"  {i}. {fact}")
    return "\n".join(lines)


# ========== RAG 查询构造 ==========

def build_rag_query(context: TripPlanningContext) -> str:
    """基于 TripRequest 构造更完整的 RAG 查询。"""
    req = context.request
    parts = [
        req.city,
        f"{req.travel_days}天" if req.travel_days else "",
    ]

    # 同义词展开
    try:
        from services.adaptive_tcr_ranker import SYNONYMS
        free_text = req.free_text_input or ""
        pref_text = " ".join(req.preferences or [])
        combined = f"{free_text} {pref_text}"
        for short, synonyms in SYNONYMS.items():
            if short in combined:
                parts.extend(synonyms)
    except ImportError:
        pass

    if req.preferences:
        parts.extend(req.preferences)
    if req.transportation and req.transportation != "公共交通":
        parts.append(req.transportation)
    if req.accommodation and req.accommodation != "经济型酒店":
        parts.append(req.accommodation)
    if req.free_text_input:
        parts.append(req.free_text_input)

    parts.append("行程 安排 攻略 避坑 交通")

    rag_query = " ".join(p for p in parts if p)
    context.rag_query = rag_query
    return rag_query
