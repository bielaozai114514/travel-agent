"""对比两个引擎的评测结果，定位分歧点。

用法：python scripts/compare.py out/eval_rule.json out/eval_llm.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python scripts/compare.py <rule.json> <llm.json>")
        raise SystemExit(1)

    a, b = load(sys.argv[1]), load(sys.argv[2])
    sa, sb = a["summary"], b["summary"]

    print(f"\n{'指标':<16}{'规则引擎':>12}{'LLM':>12}{'差值':>10}")
    print("-" * 52)
    for key, label in [
        ("intent_accuracy", "意图字段准确率"),
        ("plan_pass_rate", "行程结构通过率"),
        ("clustering_rate", "片区聚类率"),
    ]:
        va, vb = sa[key], sb[key]
        print(f"{label:<14}{va:>12.1%}{vb:>12.1%}{(vb - va):>+10.1%}")
    print(f"{'人均预算':<14}{sa['avg_per_person']:>12.0f}{sb['avg_per_person']:>12.0f}"
          f"{sb['avg_per_person'] - sa['avg_per_person']:>+10.0f}")

    da = {d["id"]: d for d in a["details"]}
    db = {d["id"]: d for d in b["details"]}

    diffs = [i for i in da if i in db and da[i]["intent_ok"] != db[i]["intent_ok"]]
    print(f"\n判断分歧：{len(diffs)} 条")
    for i in diffs:
        print(f"\n[{i}] {da[i]['input']}")
        print(f"  规则引擎：{'通过' if da[i]['intent_ok'] else '未通过'}　{da[i]['intent_errors']}")
        print(f"  LLM：　　{'通过' if db[i]['intent_ok'] else '未通过'}　{db[i]['intent_errors']}")

    if not diffs:
        print("两个引擎在所有样本上判断一致。")


if __name__ == "__main__":
    main()
