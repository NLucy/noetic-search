#!/usr/bin/env python
"""Evaluate top-k retrieval vs strongest-basin reconciliation on the hard benchmark."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from noetic_systems import Database, Reconciler


def target_doc_ids(data: dict[str, Any], case_id: str) -> set[str]:
    return {
        doc["id"]
        for doc in data["corpus"]
        if doc["metadata"].get("case") == case_id
        and doc["metadata"].get("gold") == "target"
    }


def strip_custom_metadata(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return corpus with benchmark-only metadata removed."""
    stripped = []
    for doc in data["corpus"]:
        metadata = {
            key: value
            for key, value in doc.get("metadata", {}).items()
            if key in {"source", "domain", "title", "url", "created_at", "document_id"}
        }
        stripped.append(
            {
                "id": doc["id"],
                "text": doc["text"],
                "metadata": metadata,
            }
        )
    return stripped


def docs_target_score(
    doc_ids: list[str] | tuple[str, ...],
    target_ids: set[str],
) -> float:
    if not doc_ids:
        return 0.0
    return sum(1 for doc_id in doc_ids if doc_id in target_ids) / len(doc_ids)


def basin_summary(basin) -> str:
    return (
        f"{basin.label} score={basin.score:.3f} energy={basin.energy:.3f} "
        f"support={basin.support} src={basin.source_breadth:.2f} "
        f"doc={basin.document_breadth:.2f} dup={basin.duplicate_penalty:.2f} "
        f"meta={basin.metadata_bonus:.2f}"
    )


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * pct))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("tests/data/hard_rag_benchmark.json"),
        help="benchmark JSON path",
    )
    parser.add_argument(
        "--collection-name",
        default="hard_rag_benchmark_eval",
        help="temporary Chroma collection name",
    )
    parser.add_argument(
        "--blind",
        action="store_true",
        help="strip custom benchmark labels before indexing",
    )
    parser.add_argument(
        "--community-method",
        choices=["spectral", "greedy"],
        default="spectral",
        help="community detector to use for basin construction",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=50,
        help="hybrid candidates to feed into reconciliation",
    )
    parser.add_argument(
        "--result-limit",
        type=int,
        default=30,
        help="documents kept in the reconciled result graph",
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=0.5,
        help="embedding similarity threshold for graph edges",
    )
    parser.add_argument(
        "--return-ranker",
        choices=["specificity", "purifier"],
        default="specificity",
        help="strategy for selecting final chunks from the winning basin",
    )
    parser.add_argument(
        "--limit-cases",
        type=int,
        default=None,
        help="evaluate only the first N cases",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=None,
        help="optional path to write a machine-readable report",
    )
    parser.add_argument(
        "--diagnose-docs",
        action="store_true",
        help="print ranked document IDs for cases where Noetic top-5 misses",
    )
    args = parser.parse_args()

    with open(args.data_path) as f:
        data = json.load(f)

    db = Database(collection_name=args.collection_name, reset=True)
    db.add_documents(strip_custom_metadata(data) if args.blind else data["corpus"])
    reconciler = Reconciler(db)

    case_items = list(data["cases"].items())
    baseline_hits = 0
    basin_majority_hits = 0
    basin_top5_hits = 0
    basin_target_present = 0
    expected_basin_rank1 = 0
    baseline_decoy_top = 0
    candidate_target_present = 0
    rows = []
    baseline_times = []
    reconcile_times = []

    if args.limit_cases is not None:
        case_items = case_items[: args.limit_cases]

    for case_id, case in case_items:
        query = case["query"]
        expected = case["expected_stance"]

        baseline_start = time.perf_counter()
        baseline_ids = reconciler.hybrid_baseline(query, limit=5)
        baseline_times.append((time.perf_counter() - baseline_start) * 1000)
        target_ids = target_doc_ids(data, case_id)
        baseline_target_score = docs_target_score(baseline_ids, target_ids)
        baseline_winner = "target" if baseline_target_score >= 0.5 else "other"

        reconcile_start = time.perf_counter()
        result = reconciler.reconcile(
            query,
            candidate_limit=args.candidate_limit,
            result_limit=args.result_limit,
            edge_threshold=args.edge_threshold,
            community_method=args.community_method,
            return_ranker=args.return_ranker,
        )
        reconcile_times.append((time.perf_counter() - reconcile_start) * 1000)
        candidates = reconciler.hybrid.search(query, limit=args.candidate_limit)
        candidate_ids = {candidate.id for candidate in candidates}
        found_targets = target_ids & candidate_ids
        result_ids = set(result.document_energy)
        reconciled_targets = target_ids & result_ids
        expected_basin = max(
            result.basins,
            key=lambda basin: docs_target_score(basin.documents, target_ids),
            default=None,
        )
        expected_rank = (
            next(
                index
                for index, basin in enumerate(result.basins, 1)
                if basin is expected_basin
            )
            if expected_basin
            else None
        )
        winner_target_score = docs_target_score(result.winner.documents, target_ids)
        basin_top5_ids = result.document_ids(5)
        basin_top5_target_score = docs_target_score(basin_top5_ids, target_ids)

        if baseline_target_score >= 0.5:
            baseline_hits += 1
        if baseline_ids and baseline_ids[0] not in target_ids:
            baseline_decoy_top += 1
        if winner_target_score >= 0.5:
            basin_majority_hits += 1
        if basin_top5_target_score >= 0.5:
            basin_top5_hits += 1
        if target_ids & set(result.winner.documents):
            basin_target_present += 1
        if found_targets:
            candidate_target_present += 1
        if expected_basin is result.winner:
            expected_basin_rank1 += 1

        rows.append(
            {
                "case": case_id,
                "baseline": baseline_winner,
                "basin": result.winner.label,
                "expected": expected,
                "field_score": result.winner.score,
                "energy": result.winner.energy,
                "uncertainty": result.uncertainty,
                "top5": baseline_ids,
                "basin_top5": basin_top5_ids,
                "candidate_top_ids": [candidate.id for candidate in candidates],
                "winner_ids": list(result.winner.documents),
                "baseline_target_score": baseline_target_score,
                "winner_target_score": winner_target_score,
                "basin_top5_target_score": basin_top5_target_score,
                "target_count": len(target_ids),
                "result_target_count": len(reconciled_targets),
                "basin_top5_target_count": sum(
                    1 for doc_id in basin_top5_ids if doc_id in target_ids
                ),
                "target_recall": len(found_targets) / len(target_ids),
                "result_target_recall": len(reconciled_targets) / len(target_ids),
                "found_targets": sorted(found_targets),
                "expected_rank": expected_rank,
                "expected_basin": expected_basin,
                "winner_basin": result.winner,
                "basins": result.basins[:4],
                "baseline_ms": baseline_times[-1],
                "reconcile_ms": reconcile_times[-1],
            }
        )

    total = len(case_items)
    metrics = {
        "mode": "blind" if args.blind else "labeled",
        "community_method": args.community_method,
        "documents": data["metadata"]["total_documents"],
        "cases": total,
        "candidate_limit": args.candidate_limit,
        "result_limit": args.result_limit,
        "edge_threshold": args.edge_threshold,
        "return_ranker": args.return_ranker,
        "baseline_majority_top5_accuracy": baseline_hits / total if total else 0.0,
        "baseline_top1_decoy_rate": baseline_decoy_top / total if total else 0.0,
        "strongest_basin_majority_accuracy": basin_majority_hits / total if total else 0.0,
        "strongest_basin_top5_accuracy": basin_top5_hits / total if total else 0.0,
        "strongest_basin_target_present_rate": basin_target_present / total if total else 0.0,
        "candidate_target_present_rate": candidate_target_present / total if total else 0.0,
        "target_heavy_basin_ranked_first_rate": expected_basin_rank1 / total if total else 0.0,
        "baseline_ms_p50": percentile(baseline_times, 0.50),
        "baseline_ms_p95": percentile(baseline_times, 0.95),
        "reconcile_ms_p50": percentile(reconcile_times, 0.50),
        "reconcile_ms_p95": percentile(reconcile_times, 0.95),
    }
    metrics["noetic_top5_uplift_cases"] = basin_top5_hits - baseline_hits

    print("=== HARD RAG BENCHMARK ===")
    print(f"mode: {metrics['mode']}")
    print(f"community method: {metrics['community_method']}")
    print(f"return ranker: {metrics['return_ranker']}")
    print(f"candidate/result limit: {args.candidate_limit}/{args.result_limit}")
    print(f"edge threshold: {args.edge_threshold:.2f}")
    print(f"documents: {metrics['documents']}")
    print(f"cases: {total}")
    print(f"standard hybrid top-5 majority accuracy: {baseline_hits}/{total}")
    print(f"standard hybrid top-1 decoy rate: {baseline_decoy_top}/{total}")
    print(f"strongest-basin majority accuracy: {basin_majority_hits}/{total}")
    print(
        f"noetic top-5 from hybrid top-{args.candidate_limit} accuracy: "
        f"{basin_top5_hits}/{total}"
    )
    print(f"noetic top-5 uplift over standard top-5: {metrics['noetic_top5_uplift_cases']:+d} cases")
    print(f"strongest-basin target-present rate: {basin_target_present}/{total}")
    print(f"candidate target-present rate: {candidate_target_present}/{total}")
    print(f"target-heavy basin ranked first: {expected_basin_rank1}/{total}")
    print(f"baseline latency p50/p95 ms: {metrics['baseline_ms_p50']:.1f}/{metrics['baseline_ms_p95']:.1f}")
    print(f"reconcile latency p50/p95 ms: {metrics['reconcile_ms_p50']:.1f}/{metrics['reconcile_ms_p95']:.1f}")
    print()

    for row in rows:
        print(
            f"{row['case']:20} expected={row['expected']:24} "
            f"baseline={row['baseline']:24} basin={row['basin']:24} "
            f"score={row['field_score']:.3f} uncertainty={row['uncertainty']:.3f} "
            f"basin_target={row['winner_target_score']:.2f} "
            f"basin_top5={row['basin_top5_target_score']:.2f} "
            f"target_recall@50={row['target_recall']:.2f} "
            f"target_in_graph={row['result_target_recall']:.2f}"
        )

    print()
    print("=== FAILURE DIAGNOSTICS ===")
    for row in rows:
        if row["basin_top5_target_score"] >= 0.5:
            continue

        print(f"\n{row['case']}")
        print(f"  expected: {row['expected']}")
        print(f"  winner:   {basin_summary(row['winner_basin'])}")
        if row["expected_basin"]:
            print(
                f"  expected basin rank {row['expected_rank']}: "
                f"{basin_summary(row['expected_basin'])}"
            )
        else:
            print("  expected basin: absent from reconciled graph")
        print(
            f"  target recall@50: {row['target_recall']:.2f} "
            f"({len(row['found_targets'])}/{row['target_count']})"
        )
        print(
            f"  target in graph: {row['result_target_recall']:.2f} "
            f"({row['result_target_count']}/{row['target_count']})"
        )
        print(
            f"  target in noetic top-5: {row['basin_top5_target_score']:.2f} "
            f"({row['basin_top5_target_count']}/5)"
        )
        print(f"  found target docs: {', '.join(row['found_targets']) or 'none'}")
        print("  top basins:")
        for basin in row["basins"]:
            print(f"    - {basin_summary(basin)}")
        if args.diagnose_docs:
            target_ids = target_doc_ids(data, row["case"])
            print("  standard top-5:")
            for index, doc_id in enumerate(row["top5"], 1):
                marker = "target" if doc_id in target_ids else "other"
                print(f"    {index:02d}. {marker:6} {doc_id}")
            print("  first 15 hybrid candidates:")
            for index, doc_id in enumerate(row["candidate_top_ids"][:15], 1):
                marker = "target" if doc_id in target_ids else "other"
                print(f"    {index:02d}. {marker:6} {doc_id}")
            print("  first 15 winning-basin docs:")
            for index, doc_id in enumerate(row["winner_ids"][:15], 1):
                marker = "target" if doc_id in target_ids else "other"
                print(f"    {index:02d}. {marker:6} {doc_id}")

    if args.json_report:
        report_rows = []
        for row in rows:
            report_rows.append(
                {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        "expected_basin",
                        "winner_basin",
                        "basins",
                    }
                }
            )
        args.json_report.write_text(
            json.dumps({"metrics": metrics, "rows": report_rows}, indent=2)
        )

    db.reset()


if __name__ == "__main__":
    main()
