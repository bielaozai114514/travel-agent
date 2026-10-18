"""旅游攻略分块 section_type 分类器

在同步到 RAG 时为每个 chunk 标注语义功能类型，用于检索和重排阶段的 section_type 约束。
"""

from typing import Dict, List, Optional

# section_type 关键词模式
SECTION_TYPE_PATTERNS: Dict[str, List[str]] = {
    "attraction": [
        "景点", "名胜", "公园", "古镇", "寺庙", "博物馆", "景区", "游玩", "打卡",
        "游览", "参观", "开放时间", "著名", "地标",
    ],
    "route": [
        "路线", "行程", "行程安排", "日程", "天游", "天行程", "规划",
        "第.*天", "安排", "上午", "下午", "先去", "再去",
    ],
    "food": [
        "美食", "小吃", "餐厅", "餐馆", "特色菜", "好吃", "火锅", "推荐吃",
        "当地菜", "什么好吃", "吃货", "必吃", "品尝", "味道", "美食推荐",
    ],
    "hotel": [
        "住宿", "酒店", "宾馆", "民宿", "住哪", "入住", "推荐住",
        "性价比",
    ],
    "transport": [
        "交通", "地铁", "公交", "高铁", "飞机", "怎么去", "出行", "机场",
        "火车站", "自驾", "打车", "租车",
    ],
    "tip": [
        "提示", "避坑", "不要", "切记", "务必", "小心", "千万别",
        "经验", "教训", "注意事项",
    ],
    "weather": [
        "天气", "雨天", "防晒", "下雨", "气温", "穿衣", "季节",
        "淡季", "旺季", "最佳时间", "什么时候去",
    ],
    "budget": [
        "预算", "花费", "费用", "多少钱", "省钱", "开销",
        "人均", "花销",
    ],
}

# 意图 → section 优先级映射（用于 S_section 计算）
INTENT_TO_SECTION_PRIORITY: Dict[str, List[str]] = {
    "attraction": ["attraction", "route", "tip", "budget"],
    "route": ["route", "attraction", "transport", "food"],
    "food": ["food", "tip", "budget"],
    "hotel": ["hotel", "tip", "transport"],
    "transport": ["transport", "tip"],
    "general": ["attraction", "route", "food", "tip", "hotel", "transport", "budget", "weather"],
}


def classify_section(heading_path: Optional[str], content: str) -> str:
    """
    分类 chunk 的 section_type

    规则:
    1. 如果 heading_path 包含明确关键词，直接分类
    2. 否则对 content 前 200 字做关键词频率统计，取最高频类型
    3. 无法判断时默认 "general"

    Args:
        heading_path: 标题路径（如 "攻略标题 > 美食推荐"）
        content: chunk 正文内容

    Returns:
        section_type 字符串
    """
    # 第一步：从 heading_path 匹配
    if heading_path:
        heading_scores = _score_by_keywords(heading_path)
        if heading_scores:
            best_type = max(heading_scores, key=heading_scores.get)
            if heading_scores[best_type] >= 1:
                return best_type

    # 第二步：从 content 前 200 字匹配
    content_preview = content[:200] if content else ""
    if content_preview:
        content_scores = _score_by_keywords(content_preview)
        if content_scores:
            sorted_scores = sorted(content_scores.items(), key=lambda x: x[1], reverse=True)
            best_type, best_score = sorted_scores[0]
            # 需要至少 1 次命中，且与第二名有区分度
            if best_score >= 1:
                if len(sorted_scores) == 1 or best_score > sorted_scores[1][1]:
                    return best_type
                # 分数相同时，按优先级：food > attraction > route > hotel > transport > tip > weather > budget
                tie_priority = ["food", "attraction", "route", "hotel", "transport", "tip", "weather", "budget"]
                tied = [t for t, s in sorted_scores if s == best_score]
                for t in tie_priority:
                    if t in tied:
                        return t

    return "general"


def _score_by_keywords(text: str) -> Dict[str, int]:
    """对文本做关键词频率统计"""
    import re

    scores: Dict[str, int] = {}
    for section_type, keywords in SECTION_TYPE_PATTERNS.items():
        count = 0
        for kw in keywords:
            # 支持正则模式（如 "第.*天"）
            try:
                count += len(re.findall(kw, text))
            except re.error:
                count += text.count(kw)
        if count > 0:
            scores[section_type] = count

    return scores


def get_section_boost(section_type: str, intent_type: str) -> float:
    """获取 section_type 与 intent 的匹配加分"""
    if section_type == intent_type:
        return 1.0

    priority_list = INTENT_TO_SECTION_PRIORITY.get(intent_type, [])
    if section_type in priority_list:
        return 0.6

    if section_type == "general":
        return 0.4

    return 0.2
