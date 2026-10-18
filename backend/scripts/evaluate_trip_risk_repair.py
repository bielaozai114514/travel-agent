"""RC-LRA 行程风险识别与局部调整评估脚本

对固定 initial_plans 分别计算 Baseline 指标和 RC-LRA 修复后指标，输出对比结果。

输入: data/eval/trip_initial_plans.jsonl（每条包含 request + candidate_attractions/areas + initial_plan）
输出: data/eval/trip_repair_results/summary_metrics.json + .csv + case_details.jsonl

使用方式:
    # 对已有 initial_plans 运行评估
    python scripts/evaluate_trip_risk_repair.py --input data/eval/trip_initial_plans.jsonl

    # 生成 initial_plans（需运行服务，会调用 TripPlannerAgent）
    TRIP_RISK_REPAIR_ENABLED=false python scripts/evaluate_trip_risk_repair.py --generate --requests data/eval/trip_eval_requests.jsonl

    # 指定输出目录
    python scripts/evaluate_trip_risk_repair.py --input data/eval/trip_initial_plans.jsonl --output-dir data/eval/trip_repair_results
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 确保可以导入 backend 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.trip_risk_repair import (
    TripRiskRepairEngine,
    calculate_risk_score,
    _is_light_travel_request,
    LIGHT_MAX_ATTRACTIONS,
    NORMAL_MAX_ATTRACTIONS,
)
from core.planning_context import TripPlanningContext
from schemas.trip import TripPlan, TripRequest


def load_jsonl(path: str) -> List[dict]:
    """加载 JSONL 文件"""
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def rebuild_context(item: dict) -> TripPlanningContext:
    """从评估数据重建 TripPlanningContext"""
    request = TripRequest(**item["request"])
    normalized_plan = TripPlan(**item["initial_plan"]) if "initial_plan" in item else None

    return TripPlanningContext(
        request=request,
        city=item["request"]["city"],
        travel_days=item["request"].get("travel_days", 1),
        preferences=item["request"].get("preferences", []),
        candidate_attractions=item.get("candidate_attractions", []),
        candidate_areas=item.get("candidate_areas", []),
        normalized_plan=normalized_plan,
    )


def compute_baseline_metrics(context: TripPlanningContext) -> Dict:
    """计算 Baseline 指标（不修复）"""
    plan = context.normalized_plan
    if plan is None:
        return {}

    is_light = _is_light_travel_request(
        context.preferences, context.request.free_text_input or ""
    )
    max_attractions = LIGHT_MAX_ATTRACTIONS if is_light else NORMAL_MAX_ATTRACTIONS
    total_days = len(plan.days)

    # WeatherConflictRate
    weather_conflict_days = 0
    if plan.weather_info:
        from core.trip_risk_repair import _get_weather_for_day, _is_bad_weather, _is_outdoor_attraction
        for day in plan.days:
            w = _get_weather_for_day(day, plan.weather_info)
            if w and _is_bad_weather(w):
                outdoor = [a for a in day.attractions if _is_outdoor_attraction(a.name, a.category, a.description)]
                if outdoor:
                    weather_conflict_days += 1

    # LoadViolationRate
    overload_days = sum(1 for d in plan.days if len(d.attractions) > max_attractions)

    # AvgDailyDistance
    from core.trip_risk_repair import _calculate_day_route_distance
    total_distance = sum(_calculate_day_route_distance(d) for d in plan.days)
    avg_distance = total_distance / total_days if total_days > 0 else 0.0

    risk_score = calculate_risk_score(plan, context)

    return {
        "weather_conflict_rate": weather_conflict_days / total_days if total_days > 0 else 0.0,
        "load_violation_rate": overload_days / total_days if total_days > 0 else 0.0,
        "avg_daily_distance_km": round(avg_distance, 2),
        "avg_risk_score": risk_score.get("total_score", 0.0),
        "total_days": total_days,
        "total_attractions": sum(len(d.attractions) for d in plan.days),
    }


def compute_repaired_metrics(context: TripPlanningContext) -> tuple:
    """运行 RC-LRA 并计算修复后指标，同时返回 context_copy 以获取 risks/repair_log"""
    plan = context.normalized_plan
    if plan is None:
        return {}, context

    start_time = time.time()
    engine = TripRiskRepairEngine()
    # 在副本上运行修复
    context_copy = TripPlanningContext(
        request=context.request,
        city=context.city,
        travel_days=context.travel_days,
        preferences=context.preferences,
        candidate_attractions=context.candidate_attractions,
        candidate_areas=context.candidate_areas,
        normalized_plan=plan.model_copy(deep=True),
    )
    context_copy.risk_score_before = context.risk_score_before
    context_copy = engine.evaluate_and_repair(context_copy)
    latency_ms = (time.time() - start_time) * 1000

    repaired_plan = context_copy.normalized_plan
    is_light = _is_light_travel_request(
        context.preferences, context.request.free_text_input or ""
    )
    max_attractions = LIGHT_MAX_ATTRACTIONS if is_light else NORMAL_MAX_ATTRACTIONS
    total_days = len(repaired_plan.days)

    from core.trip_risk_repair import (
        _get_weather_for_day, _is_bad_weather, _is_outdoor_attraction,
        _calculate_day_route_distance,
    )

    weather_conflict_days = 0
    if repaired_plan.weather_info:
        for day in repaired_plan.days:
            w = _get_weather_for_day(day, repaired_plan.weather_info)
            if w and _is_bad_weather(w):
                outdoor = [a for a in day.attractions if _is_outdoor_attraction(a.name, a.category, a.description)]
                if outdoor:
                    weather_conflict_days += 1

    overload_days = sum(1 for d in repaired_plan.days if len(d.attractions) > max_attractions)
    total_distance = sum(_calculate_day_route_distance(d) for d in repaired_plan.days)
    avg_distance = total_distance / total_days if total_days > 0 else 0.0

    risk_score = calculate_risk_score(repaired_plan, context)
    repairable_risks = sum(1 for r in context_copy.risks if r.get("repairable"))
    repaired_risks = sum(1 for r in context_copy.risks if r.get("repaired"))
    repair_rate = repaired_risks / repairable_risks if repairable_risks > 0 else 0.0

    baseline_score = context.risk_score_before.get("total_score", 0.0)
    repaired_score = risk_score.get("total_score", 0.0)
    risk_score_reduction = (
        (baseline_score - repaired_score) / baseline_score
        if baseline_score > 0 else 0.0
    )

    baseline_attractions = sum(len(d.attractions) for d in plan.days)
    repaired_attractions = sum(len(d.attractions) for d in repaired_plan.days)
    preservation_rate = repaired_attractions / baseline_attractions if baseline_attractions > 0 else 1.0

    return {
        "repaired_weather_conflict_rate": weather_conflict_days / total_days if total_days > 0 else 0.0,
        "repaired_load_violation_rate": overload_days / total_days if total_days > 0 else 0.0,
        "repaired_avg_daily_distance_km": round(avg_distance, 2),
        "repaired_avg_risk_score": risk_score.get("total_score", 0.0),
        "repair_rate": round(repair_rate, 4),
        "risk_score_reduction": round(risk_score_reduction, 4),
        "plan_structure_preservation_rate": round(preservation_rate, 4),
        "latency_ms": round(latency_ms, 1),
        "risk_count": len(context_copy.risks),
        "repairable_count": repairable_risks,
        "repaired_count": repaired_risks,
        "score_before": baseline_score,
        "score_after": repaired_score,
        "repair_log_count": len(context_copy.repair_log),
    }, context_copy


def model_to_dict(obj):
    """兼容 Pydantic v1/v2 的 model_dump"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj.dict()


def json_safe(obj):
    """递归转换为 JSON 安全结构"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, list):
        return [json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    return obj


def _is_risk_repair_disabled() -> bool:
    value = os.getenv("TRIP_RISK_REPAIR_ENABLED", "true").lower()
    return value in ("false", "0", "no", "off")


def _load_existing_ids(path: str) -> set:
    """读取已有 JSONL 中已成功的 ID 集合，用于断点续跑跳过"""
    ids = set()
    if not os.path.exists(path):
        return ids
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if item.get("id"):
                    ids.add(item["id"])
            except Exception:
                continue
    return ids


def _ensure_trailing_newline(path: str) -> None:
    """追加写入前确保文件末尾有换行，避免 JSONL 损坏"""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, "rb+") as f:
        f.seek(-1, os.SEEK_END)
        last = f.read(1)
        if last != b"\n":
            f.write(b"\n")


def _calculate_end_date(start_date: str, travel_days: int) -> str:
    """根据 start_date 和 travel_days 计算一致的 end_date。"""
    days = max(int(travel_days or 1), 1)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = start + timedelta(days=days - 1)
    return end.strftime("%Y-%m-%d")


def _build_trip_request_from_eval_item(item: dict, idx: int) -> TripRequest:
    """从评估请求构造 TripRequest，确保 start_date / end_date / travel_days 一致。"""
    item_id = item.get("id") or f"case_{idx:03d}"

    travel_days = int(item.get("travel_days", 1))
    start_date = item.get("start_date") or "2025-06-01"

    expected_end_date = _calculate_end_date(start_date, travel_days)
    raw_end_date = item.get("end_date")

    if raw_end_date and raw_end_date != expected_end_date:
        print(
            f"  警告: {item_id} 的 end_date 与 travel_days 不一致，"
            f"已从 {raw_end_date} 修正为 {expected_end_date}"
        )

    return TripRequest(
        city=item["city"],
        start_date=start_date,
        end_date=expected_end_date,
        travel_days=travel_days,
        transportation=item.get("transportation", "公共交通"),
        accommodation=item.get("accommodation", "经济型酒店"),
        preferences=item.get("preferences", []),
        free_text_input=item.get("free_text_input", ""),
    )


def _validate_baseline_date_consistency(path: str) -> list:
    """检查 baseline 文件中 request.start_date/end_date/travel_days 是否一致。"""
    problems = []
    if not os.path.exists(path):
        return problems

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                req = item.get("request", {})
                start_date = req.get("start_date")
                end_date = req.get("end_date")
                travel_days = int(req.get("travel_days", 1))
                if start_date and end_date:
                    expected = _calculate_end_date(start_date, travel_days)
                    if end_date != expected:
                        problems.append({
                            "line": line_no,
                            "id": item.get("id"),
                            "start_date": start_date,
                            "end_date": end_date,
                            "expected_end_date": expected,
                            "travel_days": travel_days,
                        })
            except Exception as e:
                problems.append({
                    "line": line_no,
                    "id": None,
                    "error": str(e),
                })

    return problems


def generate_initial_plans(requests_path: str, output_path: str, ids: str = "") -> None:
    """从评估请求生成初始行程并冻结。

    需要设置 TRIP_RISK_REPAIR_ENABLED=false 以确保生成的是 baseline。
    支持逐条保存、失败容错、断点续跑。
    """
    if not _is_risk_repair_disabled():
        raise RuntimeError(
            "生成 trip_initial_plans.jsonl 时必须设置 TRIP_RISK_REPAIR_ENABLED=false，"
            "否则 Baseline 会被 RC-LRA 提前修复，导致实验数据污染。"
        )
    print("[评估数据生成] 已确认 TRIP_RISK_REPAIR_ENABLED=false，生成阶段6 baseline initial_plans。")

    import asyncio
    import traceback
    from datetime import datetime
    from core.trip_planner_agent import TripPlannerAgent
    from services.amap_service import get_amap_mcp_tool

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    items = load_jsonl(requests_path)

    # --ids 过滤
    only_ids = {x.strip() for x in ids.split(",") if x.strip()}
    if only_ids:
        items = [item for item in items if (item.get("id") in only_ids)]
        print(f"仅生成指定样本: {sorted(only_ids)}")

    target_ids = {item.get("id") or f"case_{idx:03d}" for idx, item in enumerate(items, start=1)}
    existing_ids = _load_existing_ids(output_path)
    error_path = output_path.replace(".jsonl", "_errors.jsonl")
    total = len(items)

    # 确保追加写入前文件末尾有换行
    _ensure_trailing_newline(output_path)
    _ensure_trailing_newline(error_path)

    async def _generate():
        mcp_tool = get_amap_mcp_tool()
        for idx, item in enumerate(items, start=1):
            item_id = item.get("id")
            if not item_id:
                item_id = f"case_{idx:03d}"

            if item_id in existing_ids:
                print(f"[{idx}/{total}] 跳过已存在样本: {item_id}")
                continue

            print(f"[{idx}/{total}] 开始生成: {item_id}")

            try:
                req = _build_trip_request_from_eval_item(item, idx)
                print(
                    f"  请求参数: city={req.city}, start_date={req.start_date}, "
                    f"end_date={req.end_date}, travel_days={req.travel_days}"
                )

                agent = TripPlannerAgent(mcp_tool=mcp_tool)
                plan = await agent.aplan_trip(req)

                ctx = getattr(agent, "last_planning_context", None)
                candidate_attractions = ctx.candidate_attractions if ctx else []
                candidate_areas = ctx.candidate_areas if ctx else []

                if not ctx or not ctx.candidate_attractions:
                    print(f"  警告: {item_id} 候选景点为空")

                result = {
                    "id": item_id,
                    "request": model_to_dict(req),
                    "candidate_attractions": candidate_attractions,
                    "candidate_areas": candidate_areas,
                    "initial_plan": model_to_dict(plan),
                }

                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(json_safe(result), ensure_ascii=False) + "\n")
                    f.flush()

                existing_ids.add(item_id)

                current_success = len(target_ids & existing_ids)
                print(f"  生成并保存完成: {item_id} ({len(plan.days)}天, "
                      f"候选景点{len(candidate_attractions)}个, 候选区域{len(candidate_areas)}个) "
                      f"进度: {current_success}/{total}")

            except Exception as e:
                print(f"  生成失败: {item_id} - {type(e).__name__}: {e}")
                error_item = {
                    "id": item_id,
                    "city": item.get("city"),
                    "travel_days": item.get("travel_days"),
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "traceback": traceback.format_exc(),
                }
                with open(error_path, "a", encoding="utf-8") as ef:
                    ef.write(json.dumps(json_safe(error_item), ensure_ascii=False) + "\n")
                    ef.flush()
                continue

    asyncio.run(_generate())

    success_ids = _load_existing_ids(output_path)
    success_count = len(target_ids & success_ids)
    remaining = sorted(target_ids - success_ids)
    print(f"\nbaseline 生成结束: 成功 {success_count}/{len(target_ids)} 条")
    print(f"输出文件: {output_path}")
    if os.path.exists(error_path):
        print(f"错误文件: {error_path}")
    if remaining:
        print(f"剩余未成功样本数: {len(remaining)}")
        print("剩余样本ID:", remaining[:30])
        print("提示: 可重新运行脚本继续补齐，已成功样本会自动跳过。")

    # 检查 baseline 中是否存在日期不一致记录
    date_problems = _validate_baseline_date_consistency(output_path)
    if date_problems:
        print(f"\n警告: baseline 中发现 {len(date_problems)} 条日期不一致记录。")
        print("这些记录不影响脚本继续补齐缺失样本，但正式论文实验建议后续重新生成干净 baseline。")
        for p in date_problems[:5]:
            print("  ", p)


def run_evaluation(input_path: str, output_dir: str) -> None:
    """运行完整评估流程"""
    os.makedirs(output_dir, exist_ok=True)
    items = load_jsonl(input_path)

    all_metrics = []
    case_details = []

    for item in items:
        item_id = item.get("id", "unknown")
        print(f"评估: {item_id} ...")

        context = rebuild_context(item)
        if context.normalized_plan is None:
            print(f"  跳过 {item_id}: 无 initial_plan")
            continue

        # Baseline
        baseline = compute_baseline_metrics(context)
        context.risk_score_before = calculate_risk_score(context.normalized_plan, context)

        # RC-LRA
        repaired, context_copy = compute_repaired_metrics(context)

        # RouteDistanceReduction
        baseline_dist = baseline.get("avg_daily_distance_km", 0.0)
        repaired_dist = repaired.get("repaired_avg_daily_distance_km", 0.0)
        route_reduction = (
            (baseline_dist - repaired_dist) / baseline_dist
            if baseline_dist > 0 else 0.0
        )

        metrics = {
            "id": item_id,
            "city": item["request"]["city"],
            "travel_days": item["request"].get("travel_days", 1),
            **baseline,
            **repaired,
            "route_distance_reduction": round(route_reduction, 4),
        }
        all_metrics.append(metrics)

        case_detail = {
            "id": item_id,
            "city": item["request"]["city"],
            "request": item.get("request", {}),
            "before_metrics": baseline,
            "after_metrics": repaired,
            "baseline_score": context.risk_score_before,
            "repaired_score": context_copy.risk_score_after,
            "risk_count": repaired.get("risk_count", 0),
            "repairable_count": repaired.get("repairable_count", 0),
            "repaired_count": repaired.get("repaired_count", 0),
            "repair_log_count": repaired.get("repair_log_count", 0),
            "latency_ms": repaired.get("latency_ms", 0),
            "risks": context_copy.risks,
            "repair_log": context_copy.repair_log,
        }
        case_details.append(case_detail)

        print(f"  Baseline score={baseline.get('avg_risk_score', 0):.4f}, "
              f"Repaired score={repaired.get('repaired_avg_risk_score', 0):.4f}, "
              f"Reduction={repaired.get('risk_score_reduction', 0):.2%}")

    # 汇总指标
    if not all_metrics:
        print("无评估数据，跳过汇总")
        return

    n = len(all_metrics)
    summary = {
        "total_cases": n,
        "avg_weather_conflict_rate": round(sum(m.get("weather_conflict_rate", 0) for m in all_metrics) / n, 4),
        "avg_load_violation_rate": round(sum(m.get("load_violation_rate", 0) for m in all_metrics) / n, 4),
        "avg_daily_distance_km": round(sum(m.get("avg_daily_distance_km", 0) for m in all_metrics) / n, 2),
        "avg_risk_score_baseline": round(sum(m.get("avg_risk_score", 0) for m in all_metrics) / n, 4),
        "avg_repaired_weather_conflict_rate": round(sum(m.get("repaired_weather_conflict_rate", 0) for m in all_metrics) / n, 4),
        "avg_repaired_load_violation_rate": round(sum(m.get("repaired_load_violation_rate", 0) for m in all_metrics) / n, 4),
        "avg_repaired_daily_distance_km": round(sum(m.get("repaired_avg_daily_distance_km", 0) for m in all_metrics) / n, 2),
        "avg_repaired_risk_score": round(sum(m.get("repaired_avg_risk_score", 0) for m in all_metrics) / n, 4),
        "avg_route_distance_reduction": round(sum(m.get("route_distance_reduction", 0) for m in all_metrics) / n, 4),
        "avg_repair_rate": round(sum(m.get("repair_rate", 0) for m in all_metrics) / n, 4),
        "avg_risk_score_reduction": round(sum(m.get("risk_score_reduction", 0) for m in all_metrics) / n, 4),
        "avg_plan_structure_preservation_rate": round(sum(m.get("plan_structure_preservation_rate", 0) for m in all_metrics) / n, 4),
        "avg_latency_ms": round(sum(m.get("latency_ms", 0) for m in all_metrics) / n, 1),
    }

    # 论文友好别名字段
    summary.update({
        "WeatherConflictRate_before": summary["avg_weather_conflict_rate"],
        "WeatherConflictRate_after": summary["avg_repaired_weather_conflict_rate"],
        "LoadViolationRate_before": summary["avg_load_violation_rate"],
        "LoadViolationRate_after": summary["avg_repaired_load_violation_rate"],
        "AvgDailyDistance_before": summary["avg_daily_distance_km"],
        "AvgDailyDistance_after": summary["avg_repaired_daily_distance_km"],
        "RouteDistanceReduction": summary["avg_route_distance_reduction"],
        "RepairRate": summary["avg_repair_rate"],
        "AvgRiskScore_before": summary["avg_risk_score_baseline"],
        "AvgRiskScore_after": summary["avg_repaired_risk_score"],
        "RiskScoreReduction": summary["avg_risk_score_reduction"],
        "PlanStructurePreservationRate": summary["avg_plan_structure_preservation_rate"],
        "LatencyOverheadMs": summary["avg_latency_ms"],
    })

    # 保存 summary_metrics.json
    summary_path = os.path.join(output_dir, "summary_metrics.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n汇总指标已保存: {summary_path}")

    # 保存 summary_metrics.csv
    csv_path = os.path.join(output_dir, "summary_metrics.csv")
    if all_metrics:
        fieldnames = list(all_metrics[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_metrics)
        print(f"逐条指标已保存: {csv_path}")

    # 保存 case_details.jsonl
    details_path = os.path.join(output_dir, "case_details.jsonl")
    with open(details_path, "w", encoding="utf-8") as f:
        for d in case_details:
            f.write(json.dumps(json_safe(d), ensure_ascii=False) + "\n")
    print(f"案例详情已保存: {details_path}")

    # 打印汇总
    print("\n===== RC-LRA 评估汇总 =====")
    print(f"样本数: {n}")
    print(f"Baseline 平均风险分: {summary['avg_risk_score_baseline']}")
    print(f"Repaired 平均风险分: {summary['avg_repaired_risk_score']}")
    print(f"风险分下降比例: {summary['avg_risk_score_reduction']:.2%}")
    print(f"路线距离下降比例: {summary['avg_route_distance_reduction']:.2%}")
    print(f"平均修复率: {summary['avg_repair_rate']:.2%}")
    print(f"行程结构保持率: {summary['avg_plan_structure_preservation_rate']:.4f}")
    print(f"平均耗时: {summary['avg_latency_ms']:.1f}ms")


def main():
    parser = argparse.ArgumentParser(description="RC-LRA 行程风险修复评估")
    parser.add_argument("--input", type=str, default="data/eval/trip_initial_plans.jsonl",
                        help="评估数据输入路径 (JSONL)")
    parser.add_argument("--output-dir", type=str, default="data/eval/trip_repair_results",
                        help="结果输出目录")
    parser.add_argument("--generate", action="store_true",
                        help="生成 initial_plans（需配合 --requests）")
    parser.add_argument("--requests", type=str, default="data/eval/trip_eval_requests.jsonl",
                        help="评估请求输入路径（用于 --generate）")
    parser.add_argument("--ids", type=str, default="",
                        help="只生成指定样本 ID，多个 ID 用逗号分隔，例如 TRIP-BJ-002,TRIP-BJ-003")
    args = parser.parse_args()

    if args.generate:
        generate_initial_plans(args.requests, args.input, args.ids)
    else:
        run_evaluation(args.input, args.output_dir)


if __name__ == "__main__":
    main()
