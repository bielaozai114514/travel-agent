"""TCR-RAG: 面向旅游场景的多路召回与约束重排序算法

Tourism-Constrained Retrieval-Augmented Generation

核心流程:
1. 查询理解 → 提取 city、偏好、意图类型
2. 多查询扩展 → 原始查询 + LLM重写 + 关键词组合 + 意图模板查询
3. 向量召回 → 每路查询从 Qdrant 召回 top-N
4. 候选融合 → 按 chunk_id 合并，统计 query_hit_count
5. 城市强约束门控 → 过滤不兼容城市
6. 旅游约束打分 → city、tag、keyword、query_hit、section、official 加权
7. [可选] 语义精排 → bge-reranker 对 top-20 候选重新打分
8. 同源多样性限制 → 同一攻略最多 MAX_CHUNKS_PER_GUIDE 个 chunk
9. Top-K 上下文构建
"""

import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from core.logger import logger
from settings import settings
from services.rag_query_utils import (
    rewrite_query_with_llm,
    extract_keywords_with_llm,
    _clean_expired_cache,
)


# ========== 省市映射 ==========

PROVINCE_CITY_MAP: Dict[str, List[str]] = {
    "北京": ["北京"],
    "上海": ["上海"],
    "天津": ["天津"],
    "重庆": ["重庆"],
    "四川": ["成都", "绵阳", "乐山", "峨眉山", "都江堰", "九寨沟", "黄龙", "稻城", "康定", "阆中"],
    "浙江": ["杭州", "宁波", "温州", "绍兴", "嘉兴", "湖州", "金华", "丽水", "舟山", "乌镇", "西塘"],
    "江苏": ["南京", "苏州", "无锡", "常州", "扬州", "镇江", "徐州", "连云港", "周庄", "同里"],
    "广东": ["广州", "深圳", "珠海", "佛山", "东莞", "中山", "惠州", "汕头", "潮州"],
    "云南": ["昆明", "大理", "丽江", "西双版纳", "香格里拉", "腾冲", "泸沽湖"],
    "陕西": ["西安", "咸阳", "延安", "华山", "宝鸡", "汉中"],
    "福建": ["福州", "厦门", "泉州", "漳州", "武夷山", "霞浦"],
    "湖南": ["长沙", "张家界", "凤凰", "岳阳", "衡阳", "韶山"],
    "湖北": ["武汉", "宜昌", "十堰", "恩施", "神农架"],
    "山东": ["济南", "青岛", "烟台", "威海", "泰安", "曲阜", "日照"],
    "河南": ["郑州", "洛阳", "开封", "安阳", "少林寺"],
    "河北": ["石家庄", "承德", "秦皇岛", "保定", "邯郸", "张家口"],
    "山西": ["太原", "大同", "平遥", "五台山", "壶口瀑布"],
    "辽宁": ["沈阳", "大连", "丹东", "鞍山"],
    "吉林": ["长春", "吉林", "延吉", "长白山"],
    "黑龙江": ["哈尔滨", "齐齐哈尔", "牡丹江", "漠河"],
    "安徽": ["合肥", "黄山", "安庆", "芜湖", "宏村", "西递"],
    "江西": ["南昌", "九江", "景德镇", "婺源", "庐山"],
    "广西": ["南宁", "桂林", "柳州", "北海", "阳朔", "龙胜"],
    "海南": ["海口", "三亚", "万宁", "博鳌"],
    "贵州": ["贵阳", "遵义", "安顺", "凯里", "黄果树", "荔波"],
    "甘肃": ["兰州", "敦煌", "嘉峪关", "张掖", "天水"],
    "青海": ["西宁", "格尔木", "青海湖", "茶卡盐湖"],
    "宁夏": ["银川", "中卫", "沙坡头"],
    "西藏": ["拉萨", "日喀则", "林芝", "纳木错"],
    "新疆": ["乌鲁木齐", "喀什", "伊犁", "吐鲁番", "阿勒泰"],
    "内蒙古": ["呼和浩特", "包头", "呼伦贝尔", "鄂尔多斯", "额济纳"],
    "香港": ["香港"],
    "澳门": ["澳门"],
    "台湾": ["台北", "高雄", "花莲", "台东", "垦丁"],
}

# 反向映射：城市 → 省份
CITY_TO_PROVINCE: Dict[str, str] = {}
for _prov, _cities in PROVINCE_CITY_MAP.items():
    for _city in _cities:
        CITY_TO_PROVINCE[_city] = _prov

# ========== 景点—城市映射（隐式城市识别） ==========

LANDMARK_CITY_MAP: Dict[str, str] = {
    # 杭州
    "西湖": "杭州", "灵隐寺": "杭州", "西溪湿地": "杭州", "宋城": "杭州",
    "雷峰塔": "杭州", "断桥": "杭州", "千岛湖": "杭州", "龙井村": "杭州",
    # 成都
    "宽窄巷子": "成都", "春熙路": "成都", "武侯祠": "成都", "锦里": "成都",
    "都江堰": "成都", "青城山": "成都", "大熊猫基地": "成都", "杜甫草堂": "成都",
    # 北京
    "故宫": "北京", "天坛": "北京", "颐和园": "北京", "长城": "北京",
    "天安门": "北京", "王府井": "北京", "南锣鼓巷": "北京", "圆明园": "北京",
    "鸟巢": "北京", "水立方": "北京", "什刹海": "北京",
    # 西安
    "兵马俑": "西安", "华清宫": "西安", "大雁塔": "西安", "回民街": "西安",
    "钟楼": "西安", "鼓楼": "西安", "大唐不夜城": "西安", "城墙": "西安",
    # 厦门
    "鼓浪屿": "厦门", "曾厝垵": "厦门", "南普陀寺": "厦门", "中山路": "厦门",
    # 上海
    "外滩": "上海", "东方明珠": "上海", "迪士尼": "上海", "南京路": "上海",
    "豫园": "上海", "城隍庙": "上海",
    # 南京
    "中山陵": "南京", "夫子庙": "南京", "秦淮河": "南京", "玄武湖": "南京",
    # 苏州
    "拙政园": "苏州", "虎丘": "苏州", "留园": "苏州", "周庄": "苏州",
    # 重庆
    "洪崖洞": "重庆", "解放碑": "重庆", "磁器口": "重庆", "朝天门": "重庆",
    # 丽江
    "古城": "丽江", "玉龙雪山": "丽江", "束河": "丽江",
    # 桂林
    "漓江": "桂林", "象鼻山": "桂林", "阳朔": "桂林",
    # 黄山
    "迎客松": "黄山", "黄山": "黄山",
    # 张家界
    "天门山": "张家界", "玻璃栈道": "张家界",
    # 三亚
    "天涯海角": "三亚", "亚龙湾": "三亚", "蜈支洲岛": "三亚",
    # 大理
    "洱海": "大理", "苍山": "大理", "双廊": "大理",
}


# ========== 查询理解 ==========

INTENT_KEYWORDS: Dict[str, List[str]] = {
    "attraction": ["景点", "名胜", "公园", "古镇", "寺庙", "博物馆", "景区", "游玩", "打卡",
                   "看看", "去哪玩", "好玩", "必去", "值得去", "迪士尼", "乐园"],
    "route": ["路线", "行程", "行程安排", "日程", "天游", "天行程", "规划", "怎么安排",
              "几天", "第一天", "攻略"],
    "food": ["美食", "小吃", "餐厅", "餐馆", "特色菜", "好吃", "火锅", "推荐吃",
             "当地菜", "什么好吃", "吃货"],
    "hotel": ["住宿", "酒店", "宾馆", "民宿", "住哪", "入住", "推荐住"],
    "transport": ["交通", "地铁", "公交", "高铁", "飞机", "怎么去", "出行", "机场",
                  "火车站", "自驾", "路线怎么走"],
}

PREFERENCE_KEYWORDS: List[str] = [
    "亲子", "自驾", "古镇", "网红", "情侣", "老人", "穷游", "豪华",
    "轻松", "深度", "文化", "自然", "海滩", "温泉", "滑雪", "徒步",
    "摄影", "周末", "避暑", "赏花", "看雪", "看海",
]


@dataclass
class QueryUnderstanding:
    """查询理解结果"""
    city: Optional[str]
    province: Optional[str]
    preferences: List[str]
    intent_type: str  # attraction / route / food / hotel / transport / general
    original_query: str


def understand_query(query: str, city: Optional[str] = None) -> QueryUnderstanding:
    """
    查询理解：提取城市、偏好、意图类型（纯规则，不调LLM）

    Args:
        query: 用户查询
        city: 可选的城市参数（调用方已知的城市）

    Returns:
        QueryUnderstanding
    """
    # 城市提取
    detected_city = city
    if not detected_city:
        # 从查询中扫描城市名
        for c in CITY_TO_PROVINCE:
            if c in query:
                detected_city = c
                break
        # 如果没找到城市，尝试景点→城市映射
        if not detected_city:
            for landmark, lc in LANDMARK_CITY_MAP.items():
                if landmark in query:
                    detected_city = lc
                    break

    # 省份推导
    province = None
    if detected_city:
        province = CITY_TO_PROVINCE.get(detected_city)
    if not province:
        # 检查查询中是否包含省份名
        for prov in PROVINCE_CITY_MAP:
            if prov in query:
                province = prov
                break

    # 偏好提取
    preferences = [kw for kw in PREFERENCE_KEYWORDS if kw in query]

    # 意图分类
    intent_type = "general"
    intent_scores: Dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query)
        if score > 0:
            intent_scores[intent] = score

    if intent_scores:
        intent_type = max(intent_scores, key=intent_scores.get)

    return QueryUnderstanding(
        city=detected_city,
        province=province,
        preferences=preferences,
        intent_type=intent_type,
        original_query=query,
    )


# ========== 多查询扩展 ==========

INTENT_TEMPLATES: Dict[str, str] = {
    "attraction": "{city}必去景点 推荐",
    "route": "{city}行程路线 规划",
    "food": "{city}美食推荐 特色小吃",
    "hotel": "{city}住宿推荐 酒店",
    "transport": "{city}交通攻略 出行",
    "general": "{city}旅游攻略",
}


async def expand_queries(
    understanding: QueryUnderstanding,
    use_llm_optimization: Optional[bool] = None,
) -> List[str]:
    """
    生成多路查询：原始查询 + LLM重写 + 关键词组合 + 意图模板查询

    Args:
        understanding: 查询理解结果
        use_llm_optimization: 是否启用LLM优化查询，None 时跟随 settings

    Returns:
        去重后的查询列表
    """
    queries = []
    city_label = understanding.city or understanding.province or ""

    # 1. 原始查询（始终包含）
    queries.append(understanding.original_query)

    # 2 & 3. LLM优化查询（复用已有函数，异步执行）
    if use_llm_optimization is None:
        use_llm = settings.RAG_USE_LLM_OPTIMIZATION
    else:
        use_llm = use_llm_optimization
    if use_llm:
        tasks = []
        if settings.RAG_QUERY_REWRITE_ENABLED:
            tasks.append(asyncio.to_thread(rewrite_query_with_llm, understanding.original_query, understanding.city))
        if settings.RAG_KEYWORD_EXTRACTION_ENABLED:
            tasks.append(asyncio.to_thread(extract_keywords_with_llm, understanding.original_query, understanding.city))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.debug(f"LLM查询扩展失败: {r}")
                    continue
                if isinstance(r, list):
                    # 关键词列表 → 组合查询
                    keyword_query = " ".join(r)
                    if keyword_query:
                        queries.append(keyword_query)
                elif isinstance(r, str) and r:
                    queries.append(r)

    # 4. 意图模板查询（纯规则，零延迟）
    template = INTENT_TEMPLATES.get(understanding.intent_type, INTENT_TEMPLATES["general"])
    template_query = template.format(city=city_label).strip()
    if template_query and city_label:
        queries.append(template_query)

    # 去重（保持顺序）
    seen = set()
    unique_queries = []
    for q in queries:
        q_stripped = q.strip()
        if q_stripped and q_stripped not in seen:
            seen.add(q_stripped)
            unique_queries.append(q_stripped)

    logger.debug(f"TCR多查询扩展: {understanding.original_query} → {unique_queries}")
    return unique_queries


# ========== 候选融合 ==========

@dataclass
class FusedCandidate:
    """融合后的候选 chunk"""
    chunk_id: str
    guide_id: str
    title: str
    city: str
    tags: List[str]
    is_official: bool
    section_type: str
    heading_path: Optional[str]
    content: str
    vector_score: float
    query_hit_count: int
    source_queries: List[str] = field(default_factory=list)


def fuse_candidates(
    all_results_per_query: List[List[Dict[str, Any]]],
    search_queries: List[str],
) -> Dict[str, FusedCandidate]:
    """
    按 chunk_id 合并多路召回结果，统计 query_hit_count

    Args:
        all_results_per_query: 每路查询的搜索结果列表
        search_queries: 对应的查询字符串列表

    Returns:
        {chunk_id: FusedCandidate} 字典
    """
    fused: Dict[str, FusedCandidate] = {}

    for query_idx, results in enumerate(all_results_per_query):
        query = search_queries[query_idx] if query_idx < len(search_queries) else ""

        for result in results:
            chunk_id = result.get("id", "")
            if not chunk_id:
                continue

            score = result.get("score", 0)
            metadata = result.get("metadata", {})

            if chunk_id in fused:
                # 已存在：累加命中计数，取最高向量分
                fused[chunk_id].query_hit_count += 1
                fused[chunk_id].source_queries.append(query)
                if score > fused[chunk_id].vector_score:
                    fused[chunk_id].vector_score = score
            else:
                fused[chunk_id] = FusedCandidate(
                    chunk_id=chunk_id,
                    guide_id=metadata.get("guide_id", ""),
                    title=metadata.get("title", ""),
                    city=metadata.get("city", ""),
                    tags=metadata.get("tags", []) or [],
                    is_official=bool(metadata.get("is_official", False)),
                    section_type=metadata.get("section_type", "general"),
                    heading_path=metadata.get("heading_path"),
                    content=metadata.get("content", ""),
                    vector_score=score,
                    query_hit_count=1,
                    source_queries=[query],
                )

    logger.debug(f"候选融合: {sum(len(r) for r in all_results_per_query)} 条原始结果 → {len(fused)} 条去重候选")
    return fused


# ========== 城市兼容性判断 ==========

def is_city_compatible(
    candidate_city: str,
    query_city: Optional[str],
    query_province: Optional[str],
) -> bool:
    """
    判断候选 chunk 的城市是否与查询兼容

    规则:
    - 明确城市查询：只允许精确城市匹配
    - 省份/区域查询：允许同省城市
    - 候选 city 为空或省份名：允许
    - 无城市查询：始终允许

    Args:
        candidate_city: 候选 chunk 的城市
        query_city: 查询中明确识别的城市
        query_province: 查询中识别的省份

    Returns:
        是否兼容
    """
    if not query_city and not query_province:
        # 无城市查询：不硬过滤
        return True

    if not candidate_city:
        # 候选无城市标注：允许通过，靠评分区分
        return True

    if query_city:
        # 明确城市查询：只允许精确匹配
        if candidate_city == query_city:
            return True
        # 候选城市是省份名本身且是查询城市所在省份
        if candidate_city in PROVINCE_CITY_MAP and candidate_city == CITY_TO_PROVINCE.get(query_city):
            return True
        return False

    if query_province:
        # 省份查询：允许同省城市
        candidate_province = CITY_TO_PROVINCE.get(candidate_city)
        if candidate_province == query_province:
            return True
        if candidate_city == query_province:
            return True
        return False

    return True


# ========== 旅游约束评分 ==========

def _score_city(
    candidate_city: str,
    query_city: Optional[str],
    query_province: Optional[str],
    all_queries: List[str],
) -> float:
    """城市匹配评分 [0, 1]"""
    if not candidate_city:
        return 0.3  # 无城市标注，给中等分

    if query_city and candidate_city == query_city:
        return 1.0

    if query_province:
        candidate_province = CITY_TO_PROVINCE.get(candidate_city)
        if candidate_province == query_province:
            return 0.7
        if candidate_city == query_province:
            return 0.7

    # 城市名出现在某个查询中
    for q in all_queries:
        if candidate_city in q:
            return 0.5

    return 0.0


def _score_tag_overlap(
    candidate_tags: List[str],
    preferences: List[str],
    all_queries: List[str],
) -> float:
    """标签重叠评分 [0, 1]，使用 Jaccard 相似度"""
    if not candidate_tags:
        return 0.5  # 无标签，给中等分

    # 构建查询关键词集合
    query_terms = set(preferences)
    for q in all_queries:
        # 简单分词：2-4字的中文词
        for length in range(2, 5):
            for i in range(len(q) - length + 1):
                word = q[i:i + length]
                if all('一' <= c <= '鿿' for c in word):
                    query_terms.add(word)

    if not query_terms:
        return 0.5

    candidate_set = set(candidate_tags)
    intersection = candidate_set & query_terms
    union = candidate_set | query_terms

    if not union:
        return 0.5

    return len(intersection) / len(union)


def _score_keyword_match(content: str, all_queries: List[str]) -> float:
    """关键词覆盖率评分 [0, 1]"""
    if not content or not all_queries:
        return 0.0

    # 从查询中提取中文关键词（2字以上）
    keywords = set()
    for q in all_queries:
        for length in range(2, 5):
            for i in range(len(q) - length + 1):
                word = q[i:i + length]
                if all('一' <= c <= '鿿' for c in word):
                    keywords.add(word)

    if not keywords:
        return 0.0

    matched = sum(1 for kw in keywords if kw in content)
    return min(matched / len(keywords), 1.0)


def _score_query_hit(hit_count: int, max_hits: int) -> float:
    """多查询命中评分 [0, 1]"""
    if max_hits <= 0:
        return 0.0
    return min(hit_count / max_hits, 1.0)


def _score_section_type(section_type: str, intent_type: str) -> float:
    """section_type 与 intent 匹配评分 [0, 1]"""
    from services.tcr_section_classifier import INTENT_TO_SECTION_PRIORITY

    if section_type == "general":
        return 0.4

    if section_type == intent_type:
        return 1.0

    priority_list = INTENT_TO_SECTION_PRIORITY.get(intent_type, [])
    if section_type in priority_list:
        return 0.6

    return 0.2


def _score_official(is_official: bool) -> float:
    """官方来源评分"""
    return 1.0 if is_official else 0.5


def compute_tourism_score(
    candidate: FusedCandidate,
    understanding: QueryUnderstanding,
    all_queries: List[str],
    max_hits: int,
    weights: List[float],
) -> Tuple[float, Dict[str, float]]:
    """
    计算旅游约束加权分

    Args:
        candidate: 候选 chunk
        understanding: 查询理解结果
        all_queries: 所有扩展查询
        max_hits: 最大命中次数（查询总数）
        weights: 权重列表 [vector, city, tag, keyword, hit, section, official]

    Returns:
        (最终分数, 各子分数字典)
    """
    s_vector = max(candidate.vector_score, 0.0)
    s_city = _score_city(candidate.city, understanding.city, understanding.province, all_queries)
    s_tag = _score_tag_overlap(candidate.tags, understanding.preferences, all_queries)
    s_keyword = _score_keyword_match(candidate.content, all_queries)
    s_hit = _score_query_hit(candidate.query_hit_count, max_hits)
    s_section = _score_section_type(candidate.section_type, understanding.intent_type)
    s_official = _score_official(candidate.is_official)

    sub_scores = {
        "vector_score": s_vector,
        "city_score": s_city,
        "tag_score": s_tag,
        "keyword_score": s_keyword,
        "query_hit_score": s_hit,
        "section_score": s_section,
        "official_score": s_official,
    }

    # 加权求和
    components = [s_vector, s_city, s_tag, s_keyword, s_hit, s_section, s_official]
    final = sum(w * s for w, s in zip(weights[:len(components)], components[:len(weights)]))

    return final, sub_scores


# ========== 权重解析 ==========

DEFAULT_WEIGHTS = [0.50, 0.15, 0.12, 0.10, 0.08, 0.03, 0.02]
DEFAULT_WEIGHTS_RERANK = [0.55, 0.20, 0.10, 0.06, 0.04, 0.03, 0.02]


def parse_weights(value: str, expected_len: int, default: List[float]) -> List[float]:
    """解析并校验权重字符串"""
    try:
        weights = [float(x.strip()) for x in value.split(",")]
        if len(weights) != expected_len or sum(weights) <= 0:
            return default
        total = sum(weights)
        return [w / total for w in weights]
    except Exception:
        return default


# ========== 可选 Reranker ==========

_reranker_model = None


def get_reranker():
    """
    延迟加载 bge-reranker，不可用则返回 None

    Returns:
        CrossEncoder 实例或 None
    """
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder
            model_path = settings.TCR_RERANKER_MODEL_PATH
            if os.path.isdir(model_path):
                _reranker_model = CrossEncoder(model_path)
            else:
                # 尝试从 HuggingFace 加载
                _reranker_model = CrossEncoder("BAAI/bge-reranker-base")
            logger.info(f"Reranker 模型加载成功: {model_path}")
        except Exception as e:
            logger.warning(f"Reranker 模型加载失败，将使用纯约束评分: {e}")
            _reranker_model = False  # sentinel: 已尝试但失败
    return _reranker_model if _reranker_model is not False else None


def rerank_candidates(
    candidates: List[Tuple[FusedCandidate, float, Dict[str, float]]],
    query: str,
    top_n: int = 20,
) -> List[Tuple[FusedCandidate, float, Dict[str, float]]]:
    """
    对 top 候选进行 rerank

    Args:
        candidates: [(candidate, current_score, sub_scores)] 列表（已按分数排序）
        query: 原始用户查询
        top_n: 参与重排的候选数量

    Returns:
        重排后的 [(candidate, new_score, sub_scores)] 列表
    """
    reranker = get_reranker()
    if reranker is None:
        return candidates

    top_candidates = candidates[:top_n]

    try:
        pairs = [(query, c.content[:512]) for c, _, _ in top_candidates]
        scores = reranker.predict(pairs)

        # 归一化到 [0, 1]
        min_s = min(scores)
        max_s = max(scores)
        range_s = max_s - min_s if max_s > min_s else 1.0
        normalized = [(s - min_s) / range_s for s in scores]

        # 更新 sub_scores 中的 rerank_score 和总分
        rerank_weights = parse_weights(
            settings.TCR_SCORE_WEIGHTS_RERANK, 7, DEFAULT_WEIGHTS_RERANK
        )

        result = []
        for (candidate, _, sub_scores), rerank_score in zip(top_candidates, normalized):
            sub_scores["rerank_score"] = rerank_score
            # 重新计算总分：rerank权重 = [rerank, vector, city, tag, keyword, hit, official]
            components = [
                rerank_score,
                sub_scores["vector_score"],
                sub_scores["city_score"],
                sub_scores["tag_score"],
                sub_scores["keyword_score"],
                sub_scores["query_hit_score"],
                sub_scores["official_score"],
            ]
            new_score = sum(w * s for w, s in zip(rerank_weights, components))
            result.append((candidate, new_score, sub_scores))

        # 追加未参与重排的候选
        result.extend(candidates[top_n:])

        logger.debug(f"Rerank 完成: top-{top_n} 候选已重排")
        return result

    except Exception as e:
        logger.warning(f"Rerank 执行失败，使用原始评分: {e}")
        return candidates


# ========== 主搜索函数 ==========

async def search_guides_tcr(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
    min_score: float = 0.3,
    use_llm_optimization: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    TCR-RAG 主搜索函数

    流程:
    1. understand_query → 查询理解
    2. expand_queries → 多路查询
    3. 向量召回（每路 top_k=TCR_CANDIDATE_K）
    4. fuse_candidates → 候选融合
    5. 城市强约束门控
    6. compute_tourism_score → 加权评分
    7. [可选] rerank_candidates → 语义精排
    8. 同源多样性限制 → 排序取 top-K

    Args:
        query: 用户查询
        city: 可选城市过滤
        limit: 返回结果数量
        min_score: 最小相似度
        use_llm_optimization: 是否使用LLM优化查询

    Returns:
        搜索结果列表（含调试分数）
    """
    try:
        _clean_expired_cache()

        # 1. 查询理解
        understanding = understand_query(query, city)
        # 如果调用方没传 city 但理解到了，使用理解到的城市
        effective_city = city or understanding.city

        logger.debug(f"TCR查询理解: city={understanding.city}, province={understanding.province}, "
                     f"intent={understanding.intent_type}, preferences={understanding.preferences}")

        # 2. 多查询扩展
        search_queries = await expand_queries(
            understanding,
            use_llm_optimization=use_llm_optimization,
        )
        logger.debug(f"TCR多查询扩展: {search_queries}")

        # 3. 向量召回
        from services.guide_rag_service import get_guide_rag_tool
        rag_tool = get_guide_rag_tool()
        candidate_k = settings.TCR_CANDIDATE_K

        # 构建过滤条件：不在这里做城市硬过滤，交给后面的门控
        filter_conditions = None

        all_results_per_query = []
        for search_query in search_queries:
            results = await asyncio.to_thread(
                rag_tool.search_structured,
                query=search_query,
                top_k=candidate_k,
                min_score=settings.TCR_MIN_VECTOR_SCORE,
                filter_conditions=filter_conditions,
            )
            all_results_per_query.append(results)
            logger.debug(f"查询 '{search_query[:30]}' 召回 {len(results)} 条结果")

        # 4. 候选融合
        fused = fuse_candidates(all_results_per_query, search_queries)
        if not fused:
            logger.debug("TCR搜索: 无候选结果")
            return []

        # 5. 城市强约束门控
        candidates_after_gate = []
        for chunk_id, candidate in fused.items():
            if is_city_compatible(candidate.city, understanding.city, understanding.province):
                candidates_after_gate.append(candidate)
            else:
                logger.debug(f"城市门控过滤: chunk={chunk_id}, city={candidate.city}")

        logger.debug(f"城市门控: {len(fused)} → {len(candidates_after_gate)} 条候选")

        if not candidates_after_gate:
            return []

        # 6. 旅游约束评分
        weights = parse_weights(settings.TCR_SCORE_WEIGHTS, 7, DEFAULT_WEIGHTS)
        max_hits = len(search_queries)

        scored_candidates = []
        for candidate in candidates_after_gate:
            if candidate.vector_score < min_score:
                continue
            final_score, sub_scores = compute_tourism_score(
                candidate, understanding, search_queries, max_hits, weights
            )
            scored_candidates.append((candidate, final_score, sub_scores))

        # 按总分排序
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # 7. [可选] Reranker 精排
        if settings.TCR_RERANKER_ENABLED:
            scored_candidates = await asyncio.to_thread(
                rerank_candidates, scored_candidates, query, 20
            )
            scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # 8. 同源多样性限制
        guide_count: Dict[str, int] = {}
        filtered_candidates = []
        max_per_guide = settings.TCR_MAX_CHUNKS_PER_GUIDE

        for candidate, score, sub_scores in scored_candidates:
            gid = candidate.guide_id
            if guide_count.get(gid, 0) < max_per_guide:
                filtered_candidates.append((candidate, score, sub_scores))
                guide_count[gid] = guide_count.get(gid, 0) + 1
            if len(filtered_candidates) >= limit:
                break

        logger.debug(f"TCR搜索: {len(candidates_after_gate)} 条评分候选 → {len(filtered_candidates)} 条最终结果")

        # 9. 格式化输出
        truncate_len = settings.TCR_CONTENT_TRUNCATE_LENGTH
        formatted = []
        for candidate, final_score, sub_scores in filtered_candidates:
            entry = {
                "id": candidate.guide_id,
                "title": candidate.title,
                "city": candidate.city,
                "content": candidate.content[:truncate_len] if candidate.content else "",
                "score": round(final_score, 4),
                "section_type": candidate.section_type,
                "heading_path": candidate.heading_path,
                "metadata": {
                    "vector_score": round(sub_scores.get("vector_score", 0), 4),
                    "city_score": round(sub_scores.get("city_score", 0), 4),
                    "tag_score": round(sub_scores.get("tag_score", 0), 4),
                    "keyword_score": round(sub_scores.get("keyword_score", 0), 4),
                    "query_hit_score": round(sub_scores.get("query_hit_score", 0), 4),
                    "section_score": round(sub_scores.get("section_score", 0), 4),
                    "official_score": round(sub_scores.get("official_score", 0), 4),
                    "rerank_score": round(sub_scores.get("rerank_score", 0), 4) if "rerank_score" in sub_scores else None,
                    "query_hit_count": candidate.query_hit_count,
                    "source_queries": candidate.source_queries,
                    "tags": candidate.tags,
                    "is_official": candidate.is_official,
                }
            }
            formatted.append(entry)

        return formatted

    except Exception as e:
        logger.error(f"TCR-RAG 搜索失败: {str(e)}", exc_info=True)
        return []
