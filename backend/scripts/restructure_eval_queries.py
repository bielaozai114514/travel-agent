"""RAG 评测集半自动重构 — positive_titles / acceptable_titles 分层

规则：
1. 专项攻略（住宿/防骗/Citywalk/具体景点名/交通/美食/亲子/情侣/老人/雨天/预算）→ 优先保留为 positive
2. 综合类攻略（"第一次来"/"XX日游"）→ 存在专项攻略时降为 acceptable
3. 多意图/模糊样本 → 标记 [REVIEW]
4. 目标：positive 1-3个, acceptable 1-4个

用法:
    python scripts/restructure_eval_queries.py \
      --eval-file data/eval/rag_eval_queries.jsonl \
      --guides-dir data/seed_guides \
      --output data/eval/rag_eval_queries_restructured.jsonl \
      --review-file data/eval/review_needed.jsonl
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# 专项关键词（按优先级排序——匹配到越靠前的越倾向于保留为 positive）
SPECIALIZED_KEYWORDS = [
    # 住宿专项
    "住宿", "酒店", "民宿",
    # 防骗专项
    "防骗", "防坑", "避坑指南",
    # Citywalk
    "Citywalk", "citywalk",
    # 具体景点（在标题中作为核心主题）
    "长城", "故宫", "颐和园", "圆明园", "天安门", "升旗",
    "兵马俑", "华清宫", "大雁塔", "大唐不夜城", "钟鼓楼", "城墙",
    "华山", "碑林", "陕历博", "陕西历史博物馆",
    "都江堰", "青城山", "熊猫", "宽窄巷子", "锦里", "武侯祠",
    "西湖", "灵隐寺", "河坊街", "龙井", "九溪", "千岛湖",
    "鼓浪屿", "曾厝垵", "沙坡尾", "环岛路", "厦门大学", "南普陀",
    "集美学村", "园博苑", "万石植物园",
    # 交通专项
    "交通", "地铁", "公交", "BRT",
    # 美食专项
    "美食", "海鲜", "火锅", "小吃", "餐饮",
    # 人群专项
    "亲子", "情侣", "老人", "带娃",
    # 天气专项
    "雨天", "室内",
    # 预算
    "预算", "省钱", "穷游", "低预算",
    # 历史文化
    "历史文化", "博物馆", "古迹",
    # 周末
    "周末",
]


def classify_specialization(title: str) -> tuple:
    """判断攻略标题的专项程度。

    Returns:
        (is_specialized: bool, keyword: str, priority: int)
        优先保留优先级低的（数字越小越专项）
    """
    for i, kw in enumerate(SPECIALIZED_KEYWORDS):
        if kw in title:
            return True, kw, i
    return False, "", 999


def is_general_guide(title: str) -> bool:
    """判断是否为综合类攻略（"第一次来"/"XX日游"等泛化标题）"""
    general_markers = ["第一次来", "首次", "日游攻略", "几日游"]
    return any(m in title for m in general_markers)


def restructure_query(q: dict, guide_titles: dict) -> dict:
    """对单条查询执行 positive → acceptable 分层重构"""
    qid = q.get("id", "?")
    old_pos = q.get("positive_titles", [])
    city = q.get("expected_city", "")

    if not old_pos:
        # 无 positive_titles → 标记 review
        q["_review"] = True
        q["_review_reason"] = "无 positive_titles"
        return q

    # 对每个 positive_title 分类
    specialized = []
    general = []
    for t in old_pos:
        is_spec, kw, pri = classify_specialization(t)
        if is_spec:
            specialized.append((pri, kw, t))
        else:
            general.append(t)

    # 排序：优先级低的（更专项的）排在前面
    specialized.sort(key=lambda x: x[0])

    # 决定新的 positive 和 acceptable
    must = q.get("must_title", "")
    new_pos = []
    new_acc = []

    # 确保 must_title 一定在 positive 中
    if must:
        new_pos.append(must)
        # 从 specialized 和 general 中移除 must
        specialized = [s for s in specialized if s[2] != must]
        general = [g for g in general if g != must]

    # 填充 positive 到 1-3 个：优先专项
    for _, _, t in specialized:
        if len(new_pos) >= 3:
            break
        if t not in new_pos:
            new_pos.append(t)

    # 如果专项不够，补一两个综合类
    if len(new_pos) < 2 and general:
        new_pos.append(general.pop(0))

    # 剩余的进入 acceptable
    for _, _, t in specialized:
        if t not in new_pos and t not in new_acc:
            new_acc.append(t)
    for t in general:
        if t not in new_pos and t not in new_acc:
            new_acc.append(t)

    # 标记需要 review 的情况
    needs_review = False
    review_reason = ""

    if len(old_pos) > 1:
        # 检查是否有容易混淆的多意图
        spec_keywords = [kw for _, kw, _ in specialized]
        if len(set(spec_keywords)) >= 2 and len(old_pos) <= 3:
            # 多种专项类型共存的短 positive 列表 → 多意图 query
            needs_review = True
            review_reason = f"多意图: {list(set(spec_keywords))}"

    if must and must not in new_pos:
        needs_review = True
        review_reason = f"must_title 未被归入 positive"

    q["positive_titles"] = new_pos
    q["acceptable_titles"] = new_acc
    q["_review"] = needs_review
    q["_review_reason"] = review_reason
    q["_old_positive_count"] = len(old_pos)

    return q


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-file", required=True)
    parser.add_argument("--guides-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-file", default=None)
    args = parser.parse_args()

    # 加载攻略标题
    guide_titles = set()
    guides_dir = Path(args.guides_dir)
    for f in sorted(guides_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        guide_titles.add(data["title"])

    # 加载查询
    eval_file = Path(args.eval_file)
    queries = []
    raw = eval_file.read_text(encoding="utf-8").strip().split("\n")
    for line in raw:
        if line.strip():
            queries.append(json.loads(line))

    # 重构每条查询
    restructured = []
    review_items = []
    for q in queries:
        rq = restructure_query(q, guide_titles)
        # 清理内部标记
        needs_review = rq.pop("_review", False)
        reason = rq.pop("_review_reason", "")
        old_count = rq.pop("_old_positive_count", 0)

        if needs_review:
            review_items.append({
                "id": rq["id"],
                "query": rq["query"],
                "reason": reason,
                "positive_titles": rq["positive_titles"],
                "acceptable_titles": rq["acceptable_titles"],
                "must_title": rq.get("must_title", ""),
            })

        restructured.append(rq)

    # 写输出
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        for q in restructured:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    # 统计
    pos_counts = [len(q["positive_titles"]) for q in restructured]
    acc_counts = [len(q["acceptable_titles"]) for q in restructured]
    avg_pos = sum(pos_counts) / len(pos_counts)
    avg_acc = sum(acc_counts) / len(acc_counts)

    print(f"重构完成: {len(restructured)} 条")
    print(f"  avg positive_titles: {avg_pos:.2f} (分布: {dict(sorted(Counter(pos_counts).items()))})")
    print(f"  avg acceptable_titles: {avg_acc:.2f} (分布: {dict(sorted(Counter(acc_counts).items()))})")
    print(f"  需人工审核: {len(review_items)} 条")
    print(f"  输出: {output_path}")

    # 写 review 文件
    if args.review_file and review_items:
        review_path = Path(args.review_file)
        with open(review_path, "w", encoding="utf-8") as f:
            for item in review_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  Review 清单: {review_path}")
        print(f"\n  请人工审核 review 清单中的样本，确认 positive/acceptable 分层合理后")
        print(f"  将 {output_path} 重命名为 rag_eval_queries.jsonl")


if __name__ == "__main__":
    main()
