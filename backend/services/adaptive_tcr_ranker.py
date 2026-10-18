"""M5 Adaptive TCR-RAG 排序器 — 向量分数主导的轻量旅游约束校正

以增强向量检索为候选基础，引入置信度判断与轻量特征校正机制，
整体以向量分数为主导，规则特征仅做小幅修正。
避免 M3/M4 那种全局规则重排破坏向量模型自身的排序能力。

不调用 LLM，不引入新模型。
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
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            return intent
    return "route"


def expand_query_terms(query: str) -> Set[str]:
    """抽取查询词并按同义词扩展"""
    terms: Set[str] = set()
    for key in SYNONYMS:
        if key in query:
            terms.add(key)
            terms.update(SYNONYMS[key])
    for landmark, city in LANDMARK_CITY_MAP.items():
        if landmark in query:
            terms.add(landmark)
            terms.add(city)
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in query:
                terms.add(kw)
                break
    for i in range(len(query) - 1):
        bigram = query[i:i+2]
        if bigram in SYNONYMS or bigram in LANDMARK_CITY_MAP:
            terms.add(bigram)
    return terms


def detect_query_city(query: str) -> Optional[str]:
    for landmark, city in LANDMARK_CITY_MAP.items():
        if landmark in query:
            return city
    return None


# ========== 特征计算函数 ==========

def compute_title_match(query_terms: Set[str], title: str) -> float:
    if not title or not query_terms:
        return 0.0
    matched = sum(1 for t in query_terms if t and t in title)
    return min(matched / max(len(query_terms), 1), 1.0)


def compute_tag_match(query_terms: Set[str], tags: Any) -> float:
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


def compute_keyword_match(query_terms: Set[str], title: str, tags_text: str,
                          heading_path: str, content_preview: str) -> float:
    if not query_terms:
        return 0.0
    combined = f"{title} {tags_text} {heading_path} {content_preview}"
    matched = sum(1 for t in query_terms if t and t in combined)
    return min(matched / max(len(query_terms), 1), 1.0)


def compute_section_match(section_type: str, intent_type: str) -> float:
    if not section_type or not intent_type:
        return 0.0
    allowed = INTENT_SECTION_MAP.get(intent_type, [])
    return 1.0 if section_type in allowed else 0.0


def compute_city_features(candidate_city: str, query_city: str,
                          query: str) -> Dict[str, float]:
    inferred = detect_query_city(query)
    target = query_city or inferred or ""

    if not target:
        return {"city_match": 0.0, "city_mismatch_penalty": 0.0}

    if candidate_city == target:
        return {"city_match": 1.0, "city_mismatch_penalty": 0.0}

    return {"city_match": 0.0, "city_mismatch_penalty": 1.0}


# ========== Top1 置信度判断 ==========

def is_top1_confident(
    candidates: List[Dict],
    query: str,
    city: str = "",
    intent_type: Optional[str] = None,
) -> bool:
    """判断 Top1 排序是否足够可信，可信则保留原排序，否则触发轻量特征校正

    规则:
    1. 候选数 < 2 → True
    2. top1 城市不匹配 → False
    3. score_gap >= 0.06 且 top1 有 title/keyword 命中 → True
    4. score_gap >= 0.09 → True
    5. top1 title_match=0 且 top2/top3 title_match 明显更高 → False
    6. 默认 → False (触发轻量特征校正)
    """
    if len(candidates) < 2:
        return True

    top1 = candidates[0]
    top2 = candidates[1]

    query_terms = expand_query_terms(query)
    top1_city = top1.get("city", "") or top1.get("metadata", {}).get("city", "")
    city_features = compute_city_features(top1_city, city, query)

    # 规则 2: top1 城市不匹配
    if city_features["city_mismatch_penalty"] > 0:
        return False

    top1_score = top1.get("score", 0)
    top2_score = top2.get("score", 0)
    score_gap = top1_score - top2_score

    top1_title = top1.get("title", "") or top1.get("metadata", {}).get("title", "")
    top1_title_match = compute_title_match(query_terms, top1_title)
    top1_tags = top1.get("tags") or top1.get("metadata", {}).get("tags")
    top1_tags_text = " ".join(str(t) for t in top1_tags) if isinstance(top1_tags, list) else str(top1_tags or "")
    top1_heading = top1.get("heading_path", "") or top1.get("metadata", {}).get("heading_path", "")
    top1_content = (top1.get("content", "") or "")[:200]
    top1_keyword_match = compute_keyword_match(query_terms, top1_title, top1_tags_text, top1_heading, top1_content)

    # 规则 4: score_gap >= 0.06 且有命中
    if score_gap >= 0.06 and (top1_title_match > 0 or top1_keyword_match > 0):
        return True

    # 规则 5: score_gap >= 0.09
    if score_gap >= 0.09:
        return True

    # 规则 6: top1 title_match=0 但 top2/top3 明显更高
    if top1_title_match == 0 and len(candidates) >= 2:
        for c in candidates[1:min(3, len(candidates))]:
            c_title = c.get("title", "") or c.get("metadata", {}).get("title", "")
            c_title_match = compute_title_match(query_terms, c_title)
            if c_title_match >= 0.3:
                return False

    # 默认: 低置信度，需重排
    return False


# ========== v2 Ablation (not used in production/business RAG) ==========

def is_top1_confident_v2(
    candidates: List[Dict],
    query: str,
    city: str = "",
    intent_type: Optional[str] = None,
) -> bool:
    """v2 放宽置信判断，目标让 20%-50% 样本保留 M1 排序

    规则:
    1. 候选数 < 2 → True
    2. top1 城市不匹配 → False
    3. score_gap >= 0.04 且 top1_title_match > 0 → True
    4. score_gap >= 0.04 且 top1_keyword_match >= 0.2 → True
    5. score_gap >= 0.07 → True
    6. top1_title_match == 0 且 top2/top3 title_match >= 0.3 → False
    7. top1_keyword_match >= 0.3 且 city_match=1 → True
    8. 默认 → False
    """
    if len(candidates) < 2:
        return True

    top1 = candidates[0]
    top2 = candidates[1]

    query_terms = expand_query_terms(query)
    top1_city = top1.get("city", "") or top1.get("metadata", {}).get("city", "")
    city_features = compute_city_features(top1_city, city, query)

    # 规则 2: top1 城市不匹配
    if city_features["city_mismatch_penalty"] > 0:
        return False

    top1_score = top1.get("score", 0)
    top2_score = top2.get("score", 0)
    score_gap = top1_score - top2_score

    top1_title = top1.get("title", "") or top1.get("metadata", {}).get("title", "")
    top1_title_match = compute_title_match(query_terms, top1_title)
    top1_tags = top1.get("tags") or top1.get("metadata", {}).get("tags")
    top1_tags_text = " ".join(str(t) for t in top1_tags) if isinstance(top1_tags, list) else str(top1_tags or "")
    top1_heading = top1.get("heading_path", "") or top1.get("metadata", {}).get("heading_path", "")
    top1_content = (top1.get("content", "") or "")[:200]
    top1_keyword_match = compute_keyword_match(query_terms, top1_title, top1_tags_text, top1_heading, top1_content)

    # 规则 3: score_gap >= 0.04 且 title 有命中
    if score_gap >= 0.04 and top1_title_match > 0:
        return True

    # 规则 4: score_gap >= 0.04 且 keyword 命中
    if score_gap >= 0.04 and top1_keyword_match >= 0.2:
        return True

    # 规则 5: score_gap >= 0.07
    if score_gap >= 0.07:
        return True

    # 规则 6: top1 title_match=0 但 top2/top3 明显更高
    if top1_title_match == 0 and len(candidates) >= 2:
        for c in candidates[1:min(3, len(candidates))]:
            c_title = c.get("title", "") or c.get("metadata", {}).get("title", "")
            c_title_match = compute_title_match(query_terms, c_title)
            if c_title_match >= 0.3:
                return False

    # 规则 7: keyword_match 高且城市匹配
    if top1_keyword_match >= 0.3 and city_features["city_match"] > 0:
        return True

    # 默认: 低置信度，需重排
    return False


# ========== 自适应重排 ==========

def adaptive_rank(
    candidates: List[Dict],
    query: str,
    city: str = "",
    intent_type: Optional[str] = None,
    limit: int = 5,
) -> List[Dict]:
    """向量分数主导的轻量旅游约束校正排序

    候选来自 M1 Enhanced，vector_score 为主导，规则特征小幅修正。

    adaptive_score = vector_score
        + 0.04 * title_match
        + 0.03 * tag_match
        + 0.02 * keyword_match
        + 0.015 * section_match
        + 0.02 * city_match
        - 0.20 * city_mismatch_penalty
        + 0.005 * min(hit_count, 3)
    """
    if not candidates:
        return []

    query_terms = expand_query_terms(query)
    intent = intent_type or infer_intent(query)

    # 按 title 分组做 guide 级聚合
    groups: Dict[str, List[Dict]] = {}
    for c in candidates:
        key = c.get("title", "") or c.get("metadata", {}).get("title", "")
        if key not in groups:
            groups[key] = []
        groups[key].append(c)

    guide_results = []
    for title, chunks in groups.items():
        # vector_score: 该 guide 下最高 chunk 的原始向量分
        best_chunk = max(chunks, key=lambda c: c.get("score", 0))
        vector_score = best_chunk.get("score", 0)

        hit_count = len(chunks)

        # 特征计算
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

        adaptive_score = (
            vector_score
            + 0.04 * title_match
            + 0.03 * tag_match
            + 0.02 * keyword_match
            + 0.015 * section_match
            + 0.02 * city_features["city_match"]
            - 0.20 * city_features["city_mismatch_penalty"]
            + 0.005 * min(hit_count, 3)
        )

        # 选择代表 chunk: 优先 section_match=1
        represent = best_chunk
        if section_match < 1.0:
            section_matched = [c for c in chunks
                               if compute_section_match(
                                   c.get("section_type", "") or c.get("metadata", {}).get("section_type", ""),
                                   intent) >= 1.0]
            if section_matched:
                represent = max(section_matched, key=lambda c: c.get("score", 0))

        score_gap = 0.0
        if len(candidates) >= 2:
            score_gap = round(candidates[0].get("score", 0) - candidates[1].get("score", 0), 4)

        result = dict(represent)
        result["score"] = round(adaptive_score, 4)
        result["adaptive_score"] = round(adaptive_score, 4)
        result["vector_score"] = round(vector_score, 4)
        result["adaptive_reranked"] = True
        result["method_stage"] = "adaptive_rerank"
        result["rank_features"] = {
            "score_gap": score_gap,
            "title_match": round(title_match, 4),
            "tag_match": round(tag_match, 4),
            "keyword_match": round(keyword_match, 4),
            "section_match": section_match,
            "city_match": city_features["city_match"],
            "city_mismatch_penalty": city_features["city_mismatch_penalty"],
        }

        guide_results.append(result)

    guide_results.sort(key=lambda r: r.get("adaptive_score", 0), reverse=True)

    # 去重后不足 limit 时，从原 candidates 补齐
    selected_titles = {r.get("title", "") for r in guide_results[:limit]}
    if len(guide_results) < limit:
        for c in candidates:
            c_title = c.get("title", "") or c.get("metadata", {}).get("title", "")
            if c_title not in selected_titles:
                entry = dict(c)
                entry["adaptive_score"] = round(c.get("score", 0), 4)
                entry["vector_score"] = round(c.get("score", 0), 4)
                entry["adaptive_reranked"] = True
                entry["method_stage"] = "adaptive_rerank"
                entry["rank_features"] = {
                    "score_gap": 0.0,
                    "title_match": 0.0,
                    "tag_match": 0.0,
                    "keyword_match": 0.0,
                    "section_match": 0.0,
                    "city_match": 0.0,
                    "city_mismatch_penalty": 0.0,
                }
                guide_results.append(entry)
                selected_titles.add(c_title)
                if len(guide_results) >= limit:
                    break

    return guide_results[:limit]


# ========== 自适应重排 v2（先排序再去重，代表按 vector_score 选） ==========

def adaptive_rank_v2(
    candidates: List[Dict],
    query: str,
    city: str = "",
    intent_type: Optional[str] = None,
    limit: int = 5,
) -> List[Dict]:
    """v2 ablation: score-first-then-dedup. v2 is for ablation only, not used in production/business RAG.

    与 v1 区别:
    1. 先给每个 chunk 计算 adaptive_score 并排序
    2. 排序后做 guide 级去重，保留每个 guide 最高 adaptive_score 的 chunk
    3. 代表 chunk 按 adaptive_score（即 vector_score 为主）选，不用 section_match 替换
    """
    if not candidates:
        return []

    query_terms = expand_query_terms(query)
    intent = intent_type or infer_intent(query)

    # 先给每个 chunk 计算 adaptive_score
    scored_chunks = []
    for c in candidates:
        vector_score = c.get("score", 0)
        candidate_city = c.get("city", "") or c.get("metadata", {}).get("city", "")
        section_type = c.get("section_type", "") or c.get("metadata", {}).get("section_type", "")
        title = c.get("title", "") or c.get("metadata", {}).get("title", "")
        tags = c.get("tags") or c.get("metadata", {}).get("tags")
        heading_path = c.get("heading_path", "") or c.get("metadata", {}).get("heading_path", "")
        content_preview = (c.get("content", "") or "")[:200]
        tags_text = " ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags or "")

        title_match = compute_title_match(query_terms, title)
        tag_match = compute_tag_match(query_terms, tags)
        section_match = compute_section_match(section_type, intent)
        keyword_match = compute_keyword_match(query_terms, title, tags_text, heading_path, content_preview)
        city_features = compute_city_features(candidate_city, city, query)

        adaptive_score = (
            vector_score
            + 0.04 * title_match
            + 0.03 * tag_match
            + 0.02 * keyword_match
            + 0.015 * section_match
            + 0.02 * city_features["city_match"]
            - 0.20 * city_features["city_mismatch_penalty"]
        )

        entry = dict(c)
        entry["adaptive_score"] = round(adaptive_score, 4)
        entry["vector_score"] = round(vector_score, 4)
        entry["_rank_features"] = {
            "title_match": round(title_match, 4),
            "tag_match": round(tag_match, 4),
            "keyword_match": round(keyword_match, 4),
            "section_match": section_match,
            "city_match": city_features["city_match"],
            "city_mismatch_penalty": city_features["city_mismatch_penalty"],
        }
        scored_chunks.append(entry)

    # 按 adaptive_score 降序
    scored_chunks.sort(key=lambda r: r.get("adaptive_score", 0), reverse=True)

    # guide 级去重：每个 title 保留最高 adaptive_score 的 chunk
    seen_titles: Set[str] = set()
    guide_results = []
    for entry in scored_chunks:
        title = entry.get("title", "") or entry.get("metadata", {}).get("title", "")
        if title in seen_titles:
            continue
        seen_titles.add(title)

        # 计算该 guide 的 hit_count
        hit_count = sum(1 for c in scored_chunks
                        if (c.get("title", "") or c.get("metadata", {}).get("title", "")) == title)

        # hit_count 加分（极弱特征）
        final_score = entry["adaptive_score"] + 0.005 * min(hit_count, 3)
        entry["score"] = round(final_score, 4)
        entry["adaptive_score"] = round(final_score, 4)
        entry["adaptive_reranked"] = True
        entry["method_stage"] = "adaptive_rerank"

        score_gap = 0.0
        if len(scored_chunks) >= 2:
            score_gap = round(scored_chunks[0]["vector_score"] - scored_chunks[1]["vector_score"], 4)

        rf = entry.pop("_rank_features")
        entry["rank_features"] = {
            "score_gap": score_gap,
            **rf,
        }

        guide_results.append(entry)
        if len(guide_results) >= limit:
            break

    # 不足 limit 时从原 candidates 补齐
    if len(guide_results) < limit:
        selected_titles = {r.get("title", "") for r in guide_results}
        for c in candidates:
            c_title = c.get("title", "") or c.get("metadata", {}).get("title", "")
            if c_title not in selected_titles:
                entry = dict(c)
                entry["adaptive_score"] = round(c.get("score", 0), 4)
                entry["vector_score"] = round(c.get("score", 0), 4)
                entry["adaptive_reranked"] = True
                entry["method_stage"] = "adaptive_rerank"
                entry["rank_features"] = {
                    "score_gap": 0.0,
                    "title_match": 0.0,
                    "tag_match": 0.0,
                    "keyword_match": 0.0,
                    "section_match": 0.0,
                    "city_match": 0.0,
                    "city_mismatch_penalty": 0.0,
                }
                guide_results.append(entry)
                selected_titles.add(c_title)
                if len(guide_results) >= limit:
                    break

    return guide_results[:limit]
