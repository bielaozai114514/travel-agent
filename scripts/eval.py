"""离线评测脚本。

用法：
    python scripts/eval.py                 # 跑全量 30 条
    python scripts/eval.py --limit 5       # 只跑前 5 条
    python scripts/eval.py --json out.json # 结果落盘，便于改前改后对比

指标定义（面试可讲）：
1. 意图字段准确率：city / days / people / pace 四项逐条比对，任一错即该条记错
2. 行程结构完整率：天数正确 + 每天至少 1 个景点 + 每天含午晚餐
3. 约束满足率：无重复景点 + 时间轴递增 + 每天景点数不超过节奏上限
4. 片区聚类率：同一天所有景点落在同一片区的比例（衡量动线合理性）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents import intent as intent_agent  # noqa: E402
from app.agents import planner as planner_agent  # noqa: E402

CASES_PATH = ROOT / "data" / "eval_cases.jsonl"
PACE_LIMIT = planner_agent.PACE_SPOTS_PER_DAY


class _NoLLM:
    """桩对象：available=False 时 intent.parse 会走规则引擎。"""

    available = False


def load_cases(limit: int | None = None) -> list[dict]:
    cases = [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return cases[:limit] if limit else cases


def check_intent(pred: dict, expect: dict) -> tuple[bool, list[str]]:
    errors = []
    for field in ("city", "days", "people", "pace"):
        if pred.get(field) != expect.get(field):
            errors.append(f"{field}: 期望 {expect.get(field)!r} 实际 {pred.get(field)!r}")
    return (not errors), errors


def check_structure(plan: dict, days_expect: int) -> tuple[bool, list[str]]:
    errors = []
    if len(plan["days"]) != days_expect:
        errors.append(f"天数不符：期望 {days_expect} 实际 {len(plan['days'])}")
    for day in plan["days"]:
        spots = [i for i in day["items"] if i["type"] == "景点"]
        meals = {i["name"] for i in day["items"] if i["type"] == "餐饮"}
        if not spots:
            errors.append(f"第 {day['day']} 天没有景点")
        if not any("午餐" in m for m in meals):
            errors.append(f"第 {day['day']} 天缺午餐")
        if not any("晚餐" in m for m in meals):
            errors.append(f"第 {day['day']} 天缺晚餐")
    return (not errors), errors


def check_constraints(plan: dict, pace: str) -> tuple[bool, list[str]]:
    errors = []
    seen: set[str] = set()
    limit = PACE_LIMIT.get(pace, 3)
    for day in plan["days"]:
        spots = [i for i in day["items"] if i["type"] == "景点"]
        if len(spots) > limit:
            errors.append(f"第 {day['day']} 天景点数 {len(spots)} 超过节奏上限 {limit}")
        times = [i["time"] for i in day["items"]]
        if times != sorted(times):
            errors.append(f"第 {day['day']} 天时间轴未递增")
        for s in spots:
            if s["name"] in seen:
                errors.append(f"景点重复：{s['name']}")
            seen.add(s["name"])
    return (not errors), errors


def clustering_rate(plan: dict) -> float:
    """同一天景点落在同一片区的比例。"""
    total = same = 0
    for day in plan["days"]:
        areas = {i.get("area") for i in day["items"] if i["type"] == "景点" and i.get("area")}
        if len(areas) <= 1:
            same += 1
        total += 1
    return same / total if total else 0.0


def run(limit: int | None = None, engine: str = "auto") -> dict:
    cases = load_cases(limit)
    llm = _NoLLM() if engine == "rule" else None
    details = []
    for case in cases:
        parsed = intent_agent.parse(case["free_text_input"], llm=llm)
        pred = parsed.to_dict()
        ok_intent, intent_errs = check_intent(pred, case["expect"])

        plan_ok = True
        plan_errs: list[str] = []
        cluster = 0.0
        try:
            result = planner_agent.plan(parsed)
            plan = result.to_dict()
            struct_ok, struct_errs = check_structure(plan, case["travel_days"])
            cons_ok, cons_errs = check_constraints(plan, pred["pace"])
            plan_ok = struct_ok and cons_ok
            plan_errs = struct_errs + cons_errs
            cluster = clustering_rate(plan)
            per_person = plan["budget"]["per_person_estimate"]
        except Exception as exc:  # noqa: BLE001
            plan_ok = False
            plan_errs = [f"规划异常：{exc}"]
            per_person = None

        details.append({
            "id": case["id"],
            "input": case["free_text_input"],
            "source": pred.get("source"),
            "intent_ok": ok_intent,
            "intent_errors": intent_errs,
            "plan_ok": plan_ok,
            "plan_errors": plan_errs,
            "clustering": round(cluster, 3),
            "per_person": per_person,
        })

    n = len(details)
    summary = {
        "cases": n,
        "engine": details[0]["source"] if details else engine,
        "intent_accuracy": round(sum(d["intent_ok"] for d in details) / n, 4),
        "plan_pass_rate": round(sum(d["plan_ok"] for d in details) / n, 4),
        "clustering_rate": round(sum(d["clustering"] for d in details) / n, 4),
        "avg_per_person": round(
            sum(d["per_person"] for d in details if d["per_person"]) /
            max(1, sum(1 for d in details if d["per_person"])), 0
        ),
        "error_counter": dict(Counter(e.split("：")[0] for d in details for e in d["intent_errors"] + d["plan_errors"])),
    }
    return {"summary": summary, "details": details}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--json", type=str, default=None)
    ap.add_argument("--engine", choices=["auto", "rule", "llm"], default="auto",
                    help="auto=有Key走LLM；rule=强制规则引擎；llm=强制LLM")
    args = ap.parse_args()

    report = run(args.limit, args.engine)
    s = report["summary"]

    print(f"\n{'=' * 46}\n评测样本：{s['cases']} 条　引擎：{s['engine']}\n{'=' * 46}")
    print(f"意图字段准确率　{s['intent_accuracy']:.1%}")
    print(f"行程结构通过率　{s['plan_pass_rate']:.1%}")
    print(f"片区聚类率　　　{s['clustering_rate']:.1%}")
    print(f"人均预算均值　　¥{s['avg_per_person']:.0f}")
    if s["error_counter"]:
        print("\n错误分布：")
        for k, v in sorted(s["error_counter"].items(), key=lambda kv: -kv[1]):
            print(f"  {k}　{v} 次")

    failed = [d for d in report["details"] if not (d["intent_ok"] and d["plan_ok"])]
    if failed:
        print(f"\n未通过样例（{len(failed)} 条）：")
        for d in failed[:10]:
            print(f"  [{d['id']}] {d['input']}")
            for e in (d["intent_errors"] + d["plan_errors"])[:3]:
                print(f"      - {e}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已写入 {args.json}")


if __name__ == "__main__":
    main()
