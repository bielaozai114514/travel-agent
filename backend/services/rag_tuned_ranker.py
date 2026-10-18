"""TCR-RAG 优化排序器 — guide 级聚合 + 旅游特征增强排序

不调用 LLM，纯规则增强，用于 M2-Tuned 实验方法。
"""

from typing import Any, Dict, List, Optional, Set


# ========== 同义词扩展 ==========

SYNONYMS: Dict[str, List[str]] = {
    "父母": ["老人", "爸妈", "长辈"],
    "爸妈": ["父母", "老人", "长辈"],
    "老人": ["父母", "爸妈", "长辈"],
    "长辈": ["父母", "爸妈", "老人"],
    "孩子": ["亲子", "儿童", "小朋友"],
    "小孩": ["亲子", "儿童", "孩子"],
    "亲子": ["孩子", "儿童", "小朋友"],
    "省钱": ["低预算", "便宜", "预算低"],
    "低预算": ["省钱", "便宜", "预算低"],
    "预算不高": ["低预算", "省钱", "便宜"],
    "不累": ["轻松", "慢节奏"],
    "轻松": ["不累", "慢节奏"],
    "慢节奏": ["轻松", "不累"],
    "下雨": ["雨天", "室内"],
    "雨天": ["下雨", "室内"],
    "室内": ["雨天", "下雨"],
    "第一次": ["初次", "经典"],
    "初次": ["第一次", "经典"],
    "经典": ["第一次", "初次"],
    "情侣": ["浪漫", "约会"],
    "浪漫": ["情侣", "约会"],
    "火锅": ["美食", "餐饮"],
    "美食": ["火锅", "餐饮", "小吃"],
    "餐饮": ["美食", "吃饭"],
    "地铁": ["交通", "公交"],
    "公交": ["交通", "地铁"],
    "交通": ["地铁", "公交", "打车"],
    "避坑": ["注意事项", "提醒", "不要踩坑"],
    "预约": ["门票", "提前预约", "注意事项"],
    "门票": ["预约", "购票"],
    "便宜": ["省钱", "低预算"],
    "预算": ["省钱", "花费", "开销"],
    "花费": ["预算", "省钱", "开销"],
    "住宿": ["酒店", "宾馆", "民宿"],
    "酒店": ["住宿", "宾馆"],
}


# ========== 景点隐式城市映射 ==========

LANDMARK_CITY_MAP: Dict[str, str] = {
    "西湖": "杭州", "灵隐寺": "杭州", "断桥": "杭州", "雷峰塔": "杭州",
    "西溪湿地": "杭州", "苏堤": "杭州", "河坊街": "杭州", "梅家坞": "杭州",
    "大熊猫基地": "成都", "熊猫基地": "成都", "宽窄巷子": "成都", "锦里": "成都",
    "春熙路": "成都", "都江堰": "成都", "青城山": "成都",
    "故宫": "北京", "天安门": "北京", "颐和园": "北京", "长城": "北京",
    "天坛": "北京", "圆明园": "北京",
    "兵马俑": "西安", "大唐不夜城": "西安", "华清宫": "西安", "华清池": "西安",
    "大雁塔": "西安", "回民街": "西安",
    "鼓浪屿": "厦门", "曾厝垵": "厦门", "环岛路": "厦门",
}


# ========== 意图推断与 section 映射 ==========

INTENT_KEYWORDS: Dict[str, List[str]] = {
    "route": ["路线", "安排", "怎么玩", "几天", "一日游", "三日游", "五日游", "行程", "天游", "怎么走"],
    "food": ["吃", "美食", "火锅", "餐饮", "小吃", "好吃", "餐厅"],
    "transport": ["地铁", "公交", "交通", "怎么去", "打车", "出行"],
    "weather": ["下雨", "雨天", "室内", "天气", "季节", "冬天", "夏天"],
    "budget": ["预算", "省钱", "便宜", "低预算", "花费", "多少钱"],
    "tip": ["避坑", "注意", "预约", "门票", "提醒", "陷阱", "坑"],
    "attraction": ["景点", "故宫", "西湖", "灵隐寺", "兵马俑", "鼓浪屿", "熊猫", "长城", "颐和园"],
    "hotel": ["住宿", "酒店", "宾馆", "民宿", "住哪"],
}

INTENT_SECTION_MAP: Dict[str, List[str]] = {
    "route": ["route", "attraction", "transport"],
    "food": ["food", "tip", "budget"],
    "transport": ["transport", "tip"],
    "weather": ["weather", "attraction", "tip"],
    "budget": ["budget", "transport", "hotel"],
    "tip": ["tip", "attraction", "transport"],
    "attraction": ["attraction", "route", "tip"],
    "hotel": ["hotel", "transport", "budget"],
}


def infer_intent(query: str) -> str:
    """从查询文本推断意图类型"""
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            return intent
    return "route"


def expand_query_terms(query: str) -> Set[str]:
    """抽取查询词并按同义词扩展"""
    terms: Set[str] = set()
    # 1. 直接加入原始查询中的同义词键
    for key in SYNONYMS:
        if key in query:
            terms.add(key)
            terms.update(SYNONYMS[key])
    # 2. 加入城市名和景点名
    for landmark, city in LANDMARK_CITY_MAP.items():
        if landmark in query:
            terms.add(landmark)
            terms.add(city)
    # 3. 加入意图关键词
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in query:
                terms.add(kw)
                break
    # 4. 2-gram 滑动窗口补充（简单中文分词替代）
    for i in range(len(query) - 1):
        bigram = query[i:i+2]
        if bigram in SYNONYMS or bigram in LANDMARK_CITY_MAP:
            terms.add(bigram)
    return terms


# ========== 特征计算函数 ==========

def compute_title_match(query_terms: Set[str], title: str) -> float:
    """标题匹配度：query_terms 在 title 中的覆盖比例"""
    if not title or not query_terms:
        return 0.0
    matched = sum(1 for t in query_terms if t and t in title)
    return min(matched / max(len(query_terms), 1), 1.0)


def compute_tag_match(query_terms: Set[str], tags: Any) -> float:
    """标签匹配度：query_terms 在 tags 中的覆盖比例"""
    if not query_terms:
        return 0.0
    if tags is None:
        return 0.0
    if isinstance(tags, list):
        tag_text = " ".join(str(t) for t in tags)
    else:
        tag_text = str(tags)
    if not tag_text:
        return 0.0
    matched = sum(1 for t in query_terms if t and t in tag_text)
    return min(matched / max(len(query_terms), 1), 1.0)


def compute_section_match(section_type: str, intent_type: str) -> float:
    """section_type 与查询意图的匹配度"""
    if not section_type or not intent_type:
        return 0.0
    allowed = INTENT_SECTION_MAP.get(intent_type, [])
    return 1.0 if section_type in allowed else 0.0


def compute_keyword_match(query_terms: Set[str], title: str, tags_text: str,
                          heading_path: str, content_preview: str) -> float:
    """查询词在多字段中的覆盖度"""
    if not query_terms:
        return 0.0
    combined = f"{title} {tags_text} {heading_path} {content_preview}"
    matched = sum(1 for t in query_terms if t and t in combined)
    return min(matched / max(len(query_terms), 1), 1.0)


def detect_city_from_query(query: str) -> Optional[str]:
    """从查询中推断隐式城市（通过景点名）"""
    for landmark, city in LANDMARK_CITY_MAP.items():
        if landmark in query:
            return city
    return None


def compute_city_features(candidate_city: str, query_city: str,
                          query: str) -> Dict[str, float]:
    """计算城市匹配特征"""
    inferred = detect_city_from_query(query)
    target = query_city or inferred or ""

    if not target:
        return {"city_match": 0.0, "city_mismatch_penalty": 0.0}

    if candidate_city == target:
        return {"city_match": 1.0, "city_mismatch_penalty": 0.0}

    return {"city_match": 0.0, "city_mismatch_penalty": 1.0}


# ========== guide 级聚合与排序 ==========

def tuned_rank(
    candidates: List[Dict],
    query: str,
    city: str = "",
    intent_type: Optional[str] = None,
    limit: int = 5,
) -> List[Dict]:
    """
    guide 级聚合排序：按 title 分组，计算 tuned_score，返回 TopK。

    tuned_score = base_score
        + 0.05 * min(hit_count, 3)
        + 0.12 * title_match
        + 0.08 * tag_match
        + 0.06 * section_match
        + 0.04 * keyword_match
        + 0.04 * city_match
        - 0.10 * city_mismatch_penalty
    """
    if not candidates:
        return []

    query_terms = expand_query_terms(query)
    intent = intent_type or infer_intent(query)

    # 按 title 分组
    groups: Dict[str, List[Dict]] = {}
    for c in candidates:
        key = c.get("title", "") or c.get("metadata", {}).get("title", "")
        if key not in groups:
            groups[key] = []
        groups[key].append(c)

    # 计算每个 guide 的 tuned_score
    guide_results = []
    for title, chunks in groups.items():
        # base_score: 该 guide 下最高 chunk 的 M2 分数
        best_chunk = max(chunks, key=lambda c: c.get("score", 0))
        base_score = best_chunk.get("score", 0)

        # hit_count: 该 guide 下进入候选的 chunk 数
        hit_count = len(chunks)

        # 特征计算（用最佳 chunk 的字段）
        candidate_city = best_chunk.get("city", "") or best_chunk.get("metadata", {}).get("city", "")
        section_type = best_chunk.get("section_type", "") or best_chunk.get("metadata", {}).get("section_type", "")
        tags = best_chunk.get("tags") or best_chunk.get("metadata", {}).get("tags")
        heading_path = best_chunk.get("heading_path", "") or best_chunk.get("metadata", {}).get("heading_path", "")
        content_preview = (best_chunk.get("content", "") or "")[:200]
        tags_text = " ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags or "")

        title_match = compute_title_match(query_terms, title)
        tag_match = compute_tag_match(query_terms, tags)
        section_match = compute_section_match(section_type, intent)
        keyword_match = compute_keyword_match(query_terms, title, tags_text, heading_path, content_preview)
        city_features = compute_city_features(candidate_city, city, query)

        tuned_score = (
            base_score
            + 0.05 * min(hit_count, 3)
            + 0.12 * title_match
            + 0.08 * tag_match
            + 0.06 * section_match
            + 0.04 * keyword_match
            + 0.04 * city_features["city_match"]
            - 0.10 * city_features["city_mismatch_penalty"]
        )

        # 选择代表 chunk: 优先 section_match=1，再按 base_score
        represent = best_chunk
        if section_match < 1.0:
            section_matched = [c for c in chunks
                               if compute_section_match(
                                   c.get("section_type", "") or c.get("metadata", {}).get("section_type", ""),
                                   intent) >= 1.0]
            if section_matched:
                represent = max(section_matched, key=lambda c: c.get("score", 0))

        result = dict(represent)
        result["score"] = round(tuned_score, 4)
        result["base_score"] = round(base_score, 4)
        result["tuned_score"] = round(tuned_score, 4)
        result["rank_features"] = {
            "hit_count": hit_count,
            "title_match": round(title_match, 4),
            "tag_match": round(tag_match, 4),
            "section_match": section_match,
            "keyword_match": round(keyword_match, 4),
            "city_match": city_features["city_match"],
            "city_mismatch_penalty": city_features["city_mismatch_penalty"],
        }

        guide_results.append(result)

    # 按 tuned_score 降序排列
    guide_results.sort(key=lambda r: r.get("tuned_score", 0), reverse=True)
    return guide_results[:limit]
