"""RAG 评测集审计脚本

检查评测集标注的完整性、一致性和覆盖率。

用法:
    python scripts/audit_rag_eval_queries.py \
      --eval-file data/eval/rag_eval_queries.jsonl \
      --guides-dir data/seed_guides
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_guide_titles(guides_dir: Path) -> dict:
    """加载所有攻略标题，返回 {title: {city, import_key}}"""
    titles = {}
    for f in sorted(guides_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            titles[data["title"]] = {
                "city": data.get("city", ""),
                "import_key": data.get("import_key", ""),
            }
        except Exception as e:
            print(f"[WARN] 无法解析 {f.name}: {e}")
    return titles


def load_queries(eval_file: Path) -> list:
    """加载评测集，返回 (query_dict, errors) 列表"""
    queries = []
    errors = []
    raw_lines = eval_file.read_text(encoding="utf-8").strip().split("\n")
    for i, line in enumerate(raw_lines, 1):
        if not line.strip():
            continue
        try:
            queries.append(json.loads(line))
        except json.JSONDecodeError as e:
            errors.append(f"行{i}: JSON 解析失败: {e}")
    return queries, errors


def audit(eval_file: Path, guides_dir: Path) -> dict:
    guide_titles = load_guide_titles(guides_dir)
    queries, parse_errors = load_queries(eval_file)

    results = {
        "total_queries": len(queries),
        "total_guides": len(guide_titles),
        "parse_errors": parse_errors,
        "id_duplicates": [],
        "missing_fields": [],
        "titles_not_found": [],
        "must_not_in_positive": [],
        "negative_overlap": [],
        "acceptable_negative_overlap": [],
        "stats": {},
    }

    # id 唯一性
    id_counts = Counter(q.get("id", "") for q in queries)
    results["id_duplicates"] = [id_ for id_, c in id_counts.items() if c > 1]

    positive_counts = []
    acceptable_counts = []
    must_ref_count = Counter()
    positive_ref_count = Counter()
    acceptable_ref_count = Counter()
    negative_ref_count = Counter()

    for q in queries:
        qid = q.get("id", "?")
        pos = q.get("positive_titles", [])
        acc = q.get("acceptable_titles", [])
        neg = q.get("negative_titles", [])
        must = q.get("must_title", "")

        # 必填字段
        for field in ["id", "query", "expected_city", "intent_type", "difficulty"]:
            if not q.get(field):
                results["missing_fields"].append(f"{qid}: {field} 为空")

        # 标题存在性
        for label, titles in [("must_title", [must] if must else []),
                               ("positive_titles", pos),
                               ("acceptable_titles", acc),
                               ("negative_titles", neg)]:
            for t in titles:
                if t and t not in guide_titles:
                    results["titles_not_found"].append(f"{qid}: {label} \"{t}\"")

        # must_title ∈ positive_titles
        if must and must not in pos:
            results["must_not_in_positive"].append(f"{qid}: must_title \"{must}\" 不在 positive_titles 中")

        # negative 不与 positive 重叠
        neg_set = set(neg)
        pos_set = set(pos)
        overlap = neg_set & pos_set
        if overlap:
            results["negative_overlap"].append(f"{qid}: negative ∩ positive = {overlap}")

        # negative 不与 acceptable 重叠
        acc_set = set(acc)
        acc_overlap = neg_set & acc_set
        if acc_overlap:
            results["acceptable_negative_overlap"].append(f"{qid}: negative ∩ acceptable = {acc_overlap}")

        # 引用计数
        positive_counts.append(len(pos))
        acceptable_counts.append(len(acc))
        if must:
            must_ref_count[must] += 1
        for t in pos:
            positive_ref_count[t] += 1
        for t in acc:
            acceptable_ref_count[t] += 1
        for t in neg:
            negative_ref_count[t] += 1

    # 统计
    avg_pos = sum(positive_counts) / len(positive_counts) if positive_counts else 0
    avg_acc = sum(acceptable_counts) / len(acceptable_counts) if acceptable_counts else 0
    avg_relaxed = avg_pos + avg_acc

    pos_dist = Counter(positive_counts)
    acc_dist = Counter(acceptable_counts)

    results["stats"] = {
        "avg_positive_titles": round(avg_pos, 2),
        "avg_acceptable_titles": round(avg_acc, 2),
        "avg_relevant_strict": round(avg_pos, 2),
        "avg_relevant_relaxed": round(avg_relaxed, 2),
        "positive_distribution": dict(sorted(pos_dist.items())),
        "acceptable_distribution": dict(sorted(acc_dist.items())),
        "positive_gt_3_count": sum(1 for c in positive_counts if c > 3),
        "queries_with_acceptable": sum(1 for c in acceptable_counts if c > 0),
    }

    # 未被引用的攻略
    all_refd = set(must_ref_count.keys()) | set(positive_ref_count.keys()) | set(acceptable_ref_count.keys())
    unused = [t for t in guide_titles if t not in all_refd]
    results["unused_guides"] = sorted(unused)

    # Top 引用
    results["top_must"] = must_ref_count.most_common(20)
    results["top_positive"] = positive_ref_count.most_common(20)

    return results


def print_report(results: dict):
    print("=" * 60)
    print(" RAG 评测集审计报告")
    print("=" * 60)
    print(f"  总查询数: {results['total_queries']}")
    print(f"  知识库攻略数: {results['total_guides']}")

    errors = (len(results["parse_errors"]) + len(results["id_duplicates"]) +
              len(results["missing_fields"]) + len(results["titles_not_found"]) +
              len(results["must_not_in_positive"]) + len(results["negative_overlap"]) +
              len(results["acceptable_negative_overlap"]))

    if results["parse_errors"]:
        print(f"\n  [ERR] JSON 解析错误 ({len(results['parse_errors'])}):")
        for e in results["parse_errors"]:
            print(f"    - {e}")

    if results["id_duplicates"]:
        print(f"\n  [ERR] ID 重复 ({len(results['id_duplicates'])}): {results['id_duplicates']}")

    if results["missing_fields"]:
        print(f"\n  [WARN] 缺少字段 ({len(results['missing_fields'])}):")
        for e in results["missing_fields"]:
            print(f"    - {e}")

    if results["titles_not_found"]:
        print(f"\n  [ERR] 标题不存在于知识库 ({len(results['titles_not_found'])}):")
        for e in results["titles_not_found"]:
            print(f"    - {e}")

    if results["must_not_in_positive"]:
        print(f"\n  [ERR] must_title 不在 positive_titles 中 ({len(results['must_not_in_positive'])}):")
        for e in results["must_not_in_positive"]:
            print(f"    - {e}")

    if results["negative_overlap"]:
        print(f"\n  [ERR] negative 与 positive 重叠 ({len(results['negative_overlap'])}):")
        for e in results["negative_overlap"]:
            print(f"    - {e}")

    if results["acceptable_negative_overlap"]:
        print(f"\n  [ERR] negative 与 acceptable 重叠 ({len(results['acceptable_negative_overlap'])}):")
        for e in results["acceptable_negative_overlap"]:
            print(f"    - {e}")

    s = results["stats"]
    print(f"\n--- 统计 ---")
    print(f"  avg positive_titles (strict):  {s['avg_positive_titles']}")
    print(f"  avg acceptable_titles:         {s['avg_acceptable_titles']}")
    print(f"  avg relevant (relaxed):        {s['avg_relevant_relaxed']}")
    print(f"  positive_titles 分布:          {s['positive_distribution']}")
    print(f"  acceptable_titles 分布:        {s['acceptable_distribution']}")
    print(f"  positive > 3 的样本:           {s['positive_gt_3_count']}")
    print(f"  含 acceptable 的查询:          {s['queries_with_acceptable']}")

    print(f"\n--- 未被引用的攻略 ({len(results['unused_guides'])} 篇) ---")
    for t in results["unused_guides"]:
        print(f"  - {t}")

    print(f"\n--- Top must_title 引用 ---")
    for t, c in results["top_must"]:
        print(f"  [{c}x] {t}")

    print(f"\n--- Top positive_titles 引用 ---")
    for t, c in results["top_positive"]:
        print(f"  [{c}x] {t}")

    exit_code = 0 if errors == 0 else 1
    status = "PASS" if exit_code == 0 else "FAIL"
    print(f"\n{'='*60}")
    print(f" 结果: {status} (错误数: {errors})")

    return exit_code


def main():
    parser = argparse.ArgumentParser(description="RAG 评测集审计")
    parser.add_argument("--eval-file", required=True, help="评测集 JSONL 文件路径")
    parser.add_argument("--guides-dir", required=True, help="seed_guides 目录路径")
    args = parser.parse_args()

    eval_file = Path(args.eval_file)
    guides_dir = Path(args.guides_dir)

    if not eval_file.exists():
        print(f"[ERROR] 评测集不存在: {eval_file}")
        sys.exit(1)
    if not guides_dir.is_dir():
        print(f"[ERROR] 攻略目录不存在: {guides_dir}")
        sys.exit(1)

    results = audit(eval_file, guides_dir)
    exit_code = print_report(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
