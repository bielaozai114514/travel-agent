"""RAG 检索效果评估脚本

论文三方法对比:
  M1 (m1_enhanced): Enhanced RAG — 增强索引向量检索，无城市过滤
  M2 (m2_tcr): TCR-RAG — 强约束多路召回+重排序
  M3 (m3_adaptive): Adaptive TCR-RAG — 向量分主导+轻量旅游约束校正

用法:
    cd backend
    python scripts/evaluate_rag.py --dataset data/eval/rag_eval_queries.jsonl --output-dir data/eval/results --candidate-pool 30
    python scripts/evaluate_rag.py --dataset data/eval/rag_eval_queries.jsonl --methods m1_enhanced,m2_tcr,m3_adaptive --candidate-pool 30
"""

import argparse
import asyncio
import csv
import io
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Windows GBK 终端兼容
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 确保从 backend 根目录运行时 import 正确
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from services.guide_rag_service import (
    search_guides_basic_vector,            # M0: 朴素向量检索
    # search_guides_baseline_vector,         # M1-old: 增强索引+城市过滤 — 已注释
    search_guides_baseline_vector_no_city_filter,  # M1: 增强索引，无城市过滤
    # search_guides_current_rag,             # M2-old: LLM-RAG — 已注释
    search_guides_tcr_mode,                 # M2: TCR-RAG 强约束重排
    # search_guides_tcr_rerank_mode,         # TCR+Reranker — 已注释
    # search_guides_tcr_tuned_mode,          # TCR-Tuned — 已注释
    search_guides_adaptive_tcr_mode,        # M3: Adaptive TCR-RAG 轻量校正
    # search_guides_adaptive_tcr_v2_mode,    # M3-v2 消融变体 — 已注释
)

METHODS = {
    "m0_basic": search_guides_basic_vector,                       # M0: 朴素向量
    "m1_enhanced": search_guides_baseline_vector_no_city_filter,  # M1: 增强索引，无城市过滤
    # "m1_enhanced_no_city": search_guides_baseline_vector_no_city_filter,
    # "m2_llm_rag": search_guides_current_rag,
    "m2_tcr": search_guides_tcr_mode,                             # M2: TCR-RAG
    # "m4_tcr_tuned": search_guides_tcr_tuned_mode,
    # "m3_tcr_rerank": search_guides_tcr_rerank_mode,
    "m3_adaptive": search_guides_adaptive_tcr_mode,               # M3: Adaptive TCR-RAG
    # "m5_adaptive_v2": search_guides_adaptive_tcr_v2_mode,
}

# M3 Adaptive 支持 intent_type 参数
METHODS_WITH_INTENT = {"m3_adaptive"}

METRIC_KEYS = [
    "hit@3",
    "precision@returned",
    "precision@5_fixed",
    "recall@5",
    "ndcg@5",
    "mrr@5",
    "city_match@5",
    "section_match_raw@5",
    "section_match_guide@5",
    "must_hit@1",
    "top1_positive",
    "negative_hit@5",
    "unique@5",
    "returned@5",
    "n_relevant",
]

# 方法说明（用于审计报告）
METHOD_DESCRIPTIONS = {
    "m1_enhanced": (
        "M1 Enhanced RAG: 增强索引向量检索。向量文本注入标题、城市、标签和章节路径，"
        "检索时不使用城市过滤。作为消融基线，展示无城市约束时的检索效果。"
    ),
    "m2_tcr": (
        "M2 TCR-RAG: 使用规则查询理解、多路召回、强城市约束和旅游特征加权重排序，"
        "不调用 LLM。强规则约束提升了城市准确率，但破坏了语义排序质量。"
    ),
    "m3_adaptive": (
        "M3 Adaptive TCR-RAG (final method): 以增强向量检索（无城市过滤）为候选基础，"
        "使用向量分数主导的轻量旅游约束校正排序。city_mismatch_penalty(-0.20) 解决跨城干扰，"
        "正向轻量校正(≤0.14)保留语义排序优势。不调用 LLM。"
    ),
}


def load_dataset(path: Path) -> List[Dict]:
    """加载 JSONL 评估数据集"""
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))
    return samples


def dedupe_by_title(results: List[Dict]) -> List[Dict]:
    """按 title 去重，保留第一次出现的结果"""
    seen = set()
    deduped = []
    for r in results:
        title = r.get("title", "")
        if title and title not in seen:
            seen.add(title)
            deduped.append(r)
    return deduped


def compute_metrics(
    sample: Dict,
    raw_results: List[Dict],
    deduped_results: List[Dict],
    eval_mode: str = "strict",
) -> Dict[str, Any]:
    """计算单条样本的评估指标

    eval_mode:
      - strict: 仅使用 positive_titles 作为正例
      - relaxed: 使用 positive_titles + acceptable_titles 作为正例
    """
    positive_titles = set(sample.get("positive_titles", []))
    acceptable_titles = set(sample.get("acceptable_titles", []))
    negative_titles = set(sample.get("negative_titles", []))
    must_title = sample.get("must_title", "")
    expected_city = sample.get("expected_city", "")
    positive_sections = set(sample.get("positive_sections", []))

    # 正例集合：strict=仅positive, relaxed=positive+acceptable
    if eval_mode == "relaxed":
        relevant_titles = positive_titles | acceptable_titles
    else:
        relevant_titles = positive_titles

    top5_titles = [r.get("title", "") for r in deduped_results[:5]]
    n_correct = sum(1 for t in top5_titles if t in relevant_titles)
    n_negative = sum(1 for t in top5_titles if t in negative_titles)

    # --- Hit@3 ---
    top3_titles = [r.get("title", "") for r in deduped_results[:3]]
    hit_at_3 = 1 if any(t in relevant_titles for t in top3_titles) else 0

    # --- Precision@returned（分母为实际返回数） ---
    precision_at_returned = n_correct / len(top5_titles) if top5_titles else 0.0

    # --- Precision@5_fixed（分母始终为 5） ---
    precision_at_5_fixed = n_correct / 5

    # --- Recall@5 ---
    recall_at_5 = None
    if relevant_titles:
        recall_at_5 = n_correct / len(relevant_titles)

    # --- MRR@5 ---
    mrr_at_5 = 0.0
    for rank, t in enumerate(top5_titles, 1):
        if t in relevant_titles:
            mrr_at_5 = 1.0 / rank
            break

    # --- nDCG@5：分级相关性衡量排序质量 ---
    # must_title=3, positive(非must)=2, acceptable(非positive)=1
    def _relevance(title: str) -> int:
        if must_title and title == must_title:
            return 3
        if title in positive_titles:
            return 2
        if title in acceptable_titles:
            return 1
        return 0

    def _dcg(titles: list, k: int) -> float:
        dcg = 0.0
        for i, t in enumerate(titles[:k], 1):
            rel = _relevance(t)
            if rel > 0:
                dcg += rel / math.log2(i + 1)
        return dcg

    dcg_at_5 = _dcg(top5_titles, 5)
    # 理想排序：所有相关标题按相关性降序排列
    ideal_rels = sorted([_relevance(t) for t in positive_titles | acceptable_titles], reverse=True)
    ideal_titles = [f"__ideal_{i}" for i in range(len(ideal_rels))]  # 占位标题
    # 模拟理想排序的 DCG（只计算 k=5）
    idcg_at_5 = 0.0
    for i, rel in enumerate(ideal_rels[:5], 1):
        if rel > 0:
            idcg_at_5 += rel / math.log2(i + 1)

    ndcg_at_5 = round(dcg_at_5 / idcg_at_5, 4) if idcg_at_5 > 0 else 0.0

    # --- CityMatch@5 ---
    city_match_at_5 = None
    if expected_city:
        top5_cities = [r.get("city", "") for r in deduped_results[:5]]
        matched = sum(1 for c in top5_cities if c == expected_city)
        city_match_at_5 = matched / min(5, len(top5_cities)) if top5_cities else 0.0

    # --- SectionMatch_raw@5（chunk 级，基于 raw_results[:5]） ---
    section_match_raw_at_5 = None
    top5_raw = raw_results[:5]
    if top5_raw:
        sections = []
        for r in top5_raw:
            st = r.get("section_type") or r.get("metadata", {}).get("section_type", "")
            if st:
                sections.append(st)
        if sections and positive_sections:
            matched = sum(1 for s in sections if s in positive_sections)
            section_match_raw_at_5 = matched / len(sections)

    # --- SectionMatch_guide@5（guide 级，基于 deduped_results[:5]） ---
    section_match_guide_at_5 = None
    top5_deduped = deduped_results[:5]
    if top5_deduped:
        sections = []
        for r in top5_deduped:
            st = r.get("section_type") or r.get("metadata", {}).get("section_type", "")
            if st:
                sections.append(st)
        if sections and positive_sections:
            matched = sum(1 for s in sections if s in positive_sections)
            section_match_guide_at_5 = matched / len(sections)

    # --- MustHit@1：始终判断 top1 == must_title，不随 eval_mode 变化 ---
    first_title = deduped_results[0].get("title", "") if deduped_results else ""
    must_hit_at_1 = 1 if must_title and first_title == must_title else 0

    # --- Top1Positive：Top1 是否在正例集合中 ---
    top1_positive = 1 if top5_titles and top5_titles[0] in relevant_titles else 0

    # --- NegativeHit@5：始终判断 negative_titles ---
    negative_hit_at_5 = n_negative / 5

    # --- Unique@5 ---
    unique_at_5 = len(top5_titles)

    # --- Returned@5 ---
    returned_at_5 = len(top5_titles)

    return {
        "hit@3": hit_at_3,
        "precision@returned": round(precision_at_returned, 4),
        "precision@5_fixed": round(precision_at_5_fixed, 4),
        "recall@5": round(recall_at_5, 4) if recall_at_5 is not None else None,
        "ndcg@5": ndcg_at_5,
        "mrr@5": round(mrr_at_5, 4),
        "city_match@5": round(city_match_at_5, 4) if city_match_at_5 is not None else None,
        "section_match_raw@5": round(section_match_raw_at_5, 4) if section_match_raw_at_5 is not None else None,
        "section_match_guide@5": round(section_match_guide_at_5, 4) if section_match_guide_at_5 is not None else None,
        "must_hit@1": must_hit_at_1,
        "top1_positive": top1_positive,
        "negative_hit@5": round(negative_hit_at_5, 4),
        "unique@5": unique_at_5,
        "returned@5": returned_at_5,
        "n_correct@5": n_correct,
        "n_relevant": len(relevant_titles),
    }


def format_top5(deduped_results: List[Dict]) -> List[Dict]:
    """格式化 Top5 结果用于输出"""
    formatted = []
    for rank, r in enumerate(deduped_results[:5], 1):
        content = r.get("content", "") or r.get("metadata", {}).get("content", "")
        entry = {
            "rank": rank,
            "title": r.get("title", ""),
            "city": r.get("city", ""),
            "section_type": r.get("section_type") or r.get("metadata", {}).get("section_type", ""),
            "score": round(r.get("score", 0), 4),
            "heading_path": r.get("heading_path") or r.get("metadata", {}).get("heading_path", ""),
            "content_preview": (content or "")[:120],
        }
        if "rank_features" in r:
            entry["rank_features"] = r["rank_features"]
        formatted.append(entry)
    return formatted


def classify_failure(sample: Dict, top5: List[Dict], eval_mode: str = "strict") -> str:
    """推断失败原因

    优先级：
    1. no_results
    2. city_mismatch
    3. negative_top1
    4. missed_recall
    5. ranking_issue：Top1 不在 relevant_titles，但 Top5 中存在
    6. must_not_top1：Top1 在 relevant_titles，但不是 must_title
    7. section_mismatch：Top1 在 relevant_titles，但 section 不匹配
    8. low_title_match
    9. unknown
    """
    if not top5:
        return "no_results"
    top1 = top5[0]
    expected_city = sample.get("expected_city", "")
    positive_titles = set(sample.get("positive_titles", []))
    acceptable_titles = set(sample.get("acceptable_titles", []))
    relevant_titles = positive_titles | acceptable_titles if eval_mode == "relaxed" else positive_titles
    negative_titles = set(sample.get("negative_titles", []))
    top1_city = top1.get("city", "")
    top5_titles = [t.get("title", "") for t in top5]

    if expected_city and top1_city != expected_city:
        return "city_mismatch"

    if top5_titles and top5_titles[0] in negative_titles:
        return "negative_top1"

    if not any(t in relevant_titles for t in top5_titles):
        return "missed_recall"

    if top5_titles and top5_titles[0] not in relevant_titles and any(t in relevant_titles for t in top5_titles[1:]):
        return "ranking_issue"

    must_title = sample.get("must_title", "")
    if must_title and top5_titles and top5_titles[0] in relevant_titles and top5_titles[0] != must_title:
        return "must_not_top1"

    top1_section = top1.get("section_type", "")
    positive_sections = set(sample.get("positive_sections", []))
    if top1_section and positive_sections and top1_section not in positive_sections and top5_titles[0] in relevant_titles:
        return "section_mismatch"

    top1_features = top1.get("rank_features", {})
    if top1_features.get("title_match", 1) < 0.2:
        return "low_title_match"

    return "unknown"


async def evaluate_one_method(
    method_name: str,
    search_fn,
    samples: List[Dict],
    limit: int,
    candidate_pool: int = 0,
    eval_mode: str = "strict",
) -> List[Dict]:
    """评估单个方法，返回每条样本的明细"""
    details = []
    for sample in samples:
        query = sample["query"]
        city = sample.get("city", "") or None

        record = {
            "id": sample["id"],
            "query": query,
            "method": method_name,
            "intent_type": sample.get("intent_type", ""),
            "expected_city": sample.get("expected_city", ""),
            "difficulty": sample.get("difficulty", ""),
            "latency_ms": None,
            "metrics": {},
            "top5": [],
            "error": None,
        }

        try:
            t0 = time.perf_counter()
            if candidate_pool > 0 and method_name not in METHODS_WITH_INTENT:
                search_limit = candidate_pool
            else:
                search_limit = limit

            if method_name in METHODS_WITH_INTENT:
                raw_results = await search_fn(
                    query=query, city=city, limit=search_limit,
                    intent_type=sample.get("intent_type"),
                )
            else:
                raw_results = await search_fn(query=query, city=city, limit=search_limit)
            latency_ms = (time.perf_counter() - t0) * 1000

            deduped = dedupe_by_title(raw_results)
            metrics = compute_metrics(sample, raw_results, deduped, eval_mode=eval_mode)

            record["latency_ms"] = round(latency_ms, 1)
            record["metrics"] = metrics
            record["top5"] = format_top5(deduped)

        except Exception as e:
            record["error"] = str(e)

        details.append(record)
        status = "ERR" if record["error"] else "OK"
        print(f"  [{method_name}] {sample['id']} {status} ({record.get('latency_ms',0):.0f}ms)")

    return details


def compute_summary(details: List[Dict]) -> Dict[str, Any]:
    """汇总单个方法的指标"""
    valid = [d for d in details if not d.get("error")]
    n = len(valid)
    if n == 0:
        return {"count": 0}

    def avg(key: str) -> Optional[float]:
        vals = [d["metrics"][key] for d in valid if d["metrics"].get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    latencies = [d["latency_ms"] for d in valid if d.get("latency_ms") is not None]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

    summary = {"count": n}
    for mk in METRIC_KEYS:
        summary[mk] = avg(mk)
    summary["avg_latency_ms"] = avg_latency
    return summary


def compute_grouped_summary(details: List[Dict], group_key: str) -> Dict[str, Dict[str, Any]]:
    """按样本字段分组汇总指标"""
    groups: Dict[str, List[Dict]] = {}
    for d in details:
        if d.get("error"):
            continue
        gval = d.get(group_key, "unknown") or "unknown"
        groups.setdefault(gval, []).append(d)

    result = {}
    for gval, items in sorted(groups.items()):
        result[gval] = compute_summary(items)
    return result


def compute_method_audit(
    method_name: str,
    details: List[Dict],
    summary: Dict,
) -> Dict[str, Any]:
    """计算方法审计指标"""
    valid = [d for d in details if not d.get("error")]
    errors = [d for d in details if d.get("error")]

    under_returned_count = sum(
        1 for d in valid
        if d["metrics"].get("returned@5", 0) < 5
    )

    def sum_metric(key: str) -> Optional[float]:
        vals = [d["metrics"].get(key) for d in valid if d["metrics"].get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        "method": method_name,
        "description": METHOD_DESCRIPTIONS.get(method_name, ""),
        "total_samples": len(details),
        "valid_samples": len(valid),
        "error_count": len(errors),
        "avg_returned@5": summary.get("returned@5"),
        "avg_unique@5": summary.get("unique@5"),
        "avg_precision@5_fixed": summary.get("precision@5_fixed"),
        "avg_correct_count@5": sum_metric("n_correct@5"),
        "avg_negative@5": sum_metric("negative_hit@5"),
        "under_returned_count": under_returned_count,
    }


def write_grouped_csv(
    all_details: Dict[str, List[Dict]],
    group_key: str,
    output_path: Path,
) -> None:
    """写入分组分析 CSV"""
    columns = ["group", "method", "count"] + METRIC_KEYS + ["avg_latency_ms"]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for method_name in sorted(all_details):
            grouped = compute_grouped_summary(all_details[method_name], group_key)
            for gval in sorted(grouped):
                s = grouped[gval]
                row = {"group": gval, "method": method_name}
                row["count"] = s.get("count", 0)
                for mk in METRIC_KEYS:
                    row[mk] = s.get(mk, "")
                row["avg_latency_ms"] = s.get("avg_latency_ms", "")
                writer.writerow(row)
    print(f"[OUT] {output_path}")


def write_outputs(
    all_details: Dict[str, List[Dict]],
    all_summaries: Dict[str, Dict],
    output_dir: Path,
    samples: List[Dict],
    eval_mode: str = "strict",
) -> None:
    """写入所有输出文件"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 明细 JSONL
    details_path = output_dir / "rag_eval_details.jsonl"
    with open(details_path, "w", encoding="utf-8") as f:
        for method_name in sorted(all_details):
            for d in all_details[method_name]:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"[OUT] {details_path}")

    # 2. 汇总 JSON
    summary_path = output_dir / "rag_eval_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, ensure_ascii=False, indent=2)
    print(f"[OUT] {summary_path}")

    # 3. 论文 CSV
    csv_path = output_dir / "rag_eval_summary.csv"
    columns = ["method", "count"] + METRIC_KEYS + ["avg_latency_ms"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for method_name in sorted(all_summaries):
            row = {"method": method_name}
            s = all_summaries[method_name]
            row["count"] = s.get("count", 0)
            for mk in METRIC_KEYS:
                row[mk] = s.get(mk, "")
            row["avg_latency_ms"] = s.get("avg_latency_ms", "")
            writer.writerow(row)
    print(f"[OUT] {csv_path}")

    # 4. 错误样本 JSONL
    failures_path = output_dir / "rag_eval_failures.jsonl"
    failure_count = 0
    with open(failures_path, "w", encoding="utf-8") as f:
        for method_name in sorted(all_details):
            for d in all_details[method_name]:
                if d.get("error"):
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
                    failure_count += 1
                    continue
                m = d.get("metrics", {})
                if m.get("hit@3") == 0 or m.get("must_hit@1") == 0:
                    sample = next((s for s in samples if s["id"] == d["id"]), {})
                    top5 = d.get("top5", [])
                    top1_features = top5[0].get("rank_features", {}) if top5 else {}

                    failure_record = {
                        "id": d["id"],
                        "query": d["query"],
                        "method": d["method"],
                        "intent_type": d.get("intent_type", ""),
                        "expected_city": d.get("expected_city", ""),
                        "difficulty": d.get("difficulty", ""),
                        "metrics": m,
                        "expected": {
                            "must_title": sample.get("must_title", ""),
                            "positive_titles": sample.get("positive_titles", []),
                            "negative_titles": sample.get("negative_titles", []),
                            "positive_sections": sample.get("positive_sections", []),
                        },
                        "actual_top5_titles": [t.get("title", "") for t in top5],
                        "actual_top5_cities": [t.get("city", "") for t in top5],
                        "actual_top5_sections": [t.get("section_type", "") for t in top5],
                        "top1_rank_features": top1_features,
                        "possible_reason": classify_failure(sample, top5, eval_mode),
                    }
                    f.write(json.dumps(failure_record, ensure_ascii=False) + "\n")
                    failure_count += 1
    print(f"[OUT] {failures_path} ({failure_count} records)")

    # 5. 分组分析 CSV
    write_grouped_csv(all_details, "intent_type", output_dir / "rag_eval_by_intent.csv")
    write_grouped_csv(all_details, "expected_city", output_dir / "rag_eval_by_city.csv")
    write_grouped_csv(all_details, "difficulty", output_dir / "rag_eval_by_difficulty.csv")

    # 6. 方法审计报告
    audit_path = output_dir / "rag_eval_method_audit.json"
    audit_data = {}
    for method_name in sorted(all_details):
        audit_data[method_name] = compute_method_audit(
            method_name, all_details[method_name], all_summaries.get(method_name, {})
        )
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)
    print(f"[OUT] {audit_path}")


async def main_async(args: argparse.Namespace) -> None:
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)

    if not dataset_path.exists():
        print(f"[ERROR] 数据集文件不存在: {dataset_path}")
        sys.exit(1)

    samples = load_dataset(dataset_path)
    print(f"[INFO] 加载 {len(samples)} 条评估样本")

    method_names = [m.strip() for m in args.methods.split(",")]
    for m in method_names:
        if m not in METHODS:
            print(f"[ERROR] 未知方法: {m}，可选: {list(METHODS.keys())}")
            sys.exit(1)

    limit = args.limit
    candidate_pool = args.candidate_pool
    eval_mode = args.eval_mode
    print(f"[INFO] 方法: {method_names}, limit={limit}, candidate_pool={candidate_pool}, eval_mode={eval_mode}")
    print()

    all_details: Dict[str, List[Dict]] = {}
    all_summaries: Dict[str, Dict] = {}

    for method_name in method_names:
        search_fn = METHODS[method_name]
        print(f"=== 评估方法: {method_name} ===")

        try:
            details = await evaluate_one_method(
                method_name, search_fn, samples, limit,
                candidate_pool=candidate_pool,
                eval_mode=eval_mode,
            )
        except Exception as e:
            print(f"[ERROR] 方法 {method_name} 整体失败: {e}")
            all_details[method_name] = []
            all_summaries[method_name] = {"count": 0, "error": str(e)}
            continue

        summary = compute_summary(details)
        all_details[method_name] = details
        all_summaries[method_name] = summary

        n_errors = sum(1 for d in details if d.get("error"))
        print(f"  完成: {len(details)} 条, 错误: {n_errors}")
        print(f"  Hit@3={summary.get('hit@3','N/A')}, "
              f"MRR@5={summary.get('mrr@5','N/A')}, "
              f"MustHit@1={summary.get('must_hit@1','N/A')}, "
              f"CityMatch@5={summary.get('city_match@5','N/A')}, "
              f"AvgLatency={summary.get('avg_latency_ms','N/A')}ms")
        print()

    # 写入输出
    write_outputs(all_details, all_summaries, output_dir, samples, eval_mode)

    # 打印汇总表
    print()
    print("=" * 145)
    print(" 评估汇总")
    print("=" * 145)
    header = (
        f"{'Method':<14} {'Count':>5} "
        f"{'Hit@3':>8} {'P@5f':>8} {'R@5':>8} {'nDCG@5':>8} "
        f"{'MRR@5':>8} {'City@5':>8} {'SecG@5':>8} "
        f"{'Must@1':>8} {'Top1+':>8} {'Neg@5':>8} "
        f"{'NRel':>5} {'Latency':>10}"
    )
    print(header)
    print("-" * 130)

    def fmt(val):
        return str(val) if val is not None else "N/A"

    def fmt_nrel(val):
        return f"{val:.1f}" if isinstance(val, (int, float)) else str(val) if val is not None else "N/A"

    for m in sorted(all_summaries):
        s = all_summaries[m]
        print(
            f"{m:<14} {s.get('count',0):>5} "
            f"{fmt(s.get('hit@3')):>8} {fmt(s.get('precision@5_fixed')):>8} "
            f"{fmt(s.get('recall@5')):>8} {fmt(s.get('ndcg@5')):>8} "
            f"{fmt(s.get('mrr@5')):>8} {fmt(s.get('city_match@5')):>8} "
            f"{fmt(s.get('section_match_guide@5')):>8} "
            f"{fmt(s.get('must_hit@1')):>8} {fmt(s.get('top1_positive')):>8} "
            f"{fmt(s.get('negative_hit@5')):>8} "
            f"{fmt_nrel(s.get('n_relevant')):>5} "
            f"{fmt(s.get('avg_latency_ms'))+'ms':>10}"
        )
    print("=" * 145)


def main():
    parser = argparse.ArgumentParser(description="RAG 检索效果评估")
    parser.add_argument("--dataset", required=True, help="评估数据集路径 (JSONL)")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--methods", default="m0_basic,m1_enhanced,m2_tcr,m3_adaptive",
                        help="评估方法列表，逗号分隔")
    parser.add_argument("--limit", type=int, default=5, help="每个查询返回结果数 (默认: 5)")
    parser.add_argument("--candidate-pool", type=int, default=0,
                        help="候选池大小，>0 时对非 intent 方法使用此值作为检索 limit (默认: 0)")
    parser.add_argument("--eval-mode", default="strict", choices=["strict", "relaxed"],
                        help="评估口径: strict(仅positive_titles) / relaxed(positive+acceptable) (默认: strict)")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main_async(args))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
