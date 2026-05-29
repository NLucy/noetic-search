#!/usr/bin/env python
"""Evaluate linked-evidence anchor policies on multi-hop benchmarks.

This script isolates the final ranking question: how many hybrid anchors should
be used, and should those anchors be protected at the front of the return list?
It holds the graph objective fixed and compares anchor policies against a raw
hybrid baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noetic_systems.database import Database
from noetic_systems.evaluation.metrics import (
    add_metric_totals,
    average_metric_totals,
    empty_metric_totals,
    parse_k_values,
)
from noetic_systems.evaluation.multihop import (
    RetrievalCase,
    convert_hotpot_like_records,
    convert_musique_records,
)
from noetic_systems.reconciliation.calibration import calibrate_corpus_graph_weights
from noetic_systems.reconciliation.engine import Reconciler
from scripts.evaluate_multihop_objectives import (
    BENCHMARK_SPECS,
    DEFAULT_BENCHMARKS,
    BenchmarkSpec,
    load_records,
    parse_names,
)
from scripts.evaluate_hotpotqa import print_ranking_table


def convert_records(
    spec: BenchmarkSpec,
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[RetrievalCase]]:
    """Convert benchmark records into corpus documents and retrieval cases.

    Args:
        spec: Benchmark dataset specification.
        records: Raw Hugging Face records.

    Returns:
        Tuple of corpus documents and retrieval cases.
    """
    if spec.converter == "hotpot_like":
        return convert_hotpot_like_records(records, source=spec.name)
    if spec.converter == "musique":
        return convert_musique_records(records)
    raise ValueError(f"unknown converter: {spec.converter}")


def policy_name(anchor_count: int, protect_anchors: bool) -> str:
    """Return a compact policy label.

    Args:
        anchor_count: Number of leading hybrid candidates used as anchors.
        protect_anchors: Whether anchors are locked at the front.

    Returns:
        Stable policy label.
    """
    mode = "protected" if protect_anchors else "open"
    return f"anchors_{anchor_count}_{mode}"


def evaluate_benchmark(
    spec: BenchmarkSpec,
    *,
    limit_cases: int,
    anchor_counts: list[int],
    protect_modes: list[bool],
    k_values: list[int],
    candidate_limit: int,
    edge_threshold: float,
    calibration_sample: int,
    graph_objective: str,
) -> dict[str, Any]:
    """Evaluate anchor policies on one benchmark.

    Args:
        spec: Benchmark dataset specification.
        limit_cases: Number of records to load.
        anchor_counts: Anchor counts to test.
        protect_modes: Protection modes to test.
        k_values: Rank cutoffs.
        candidate_limit: Hybrid candidates admitted to graph reconciliation.
        edge_threshold: Default semantic graph edge threshold.
        calibration_sample: Corpus documents sampled for graph calibration.
        graph_objective: Corpus-level graph calibration objective.

    Returns:
        Benchmark report with metrics by policy.
    """
    records = load_records(spec, limit_cases)
    documents, cases = convert_records(spec, records)
    database = Database(collection_name=f"{spec.name}_anchor_policy", reset=True)
    database.add_documents(documents)
    weights, profile = calibrate_corpus_graph_weights(
        database,
        sample_limit=calibration_sample,
        objective=graph_objective,
    )
    reconciler = Reconciler(database, graph_weights=weights)
    max_k = max(k_values)
    policies = [
        (anchor_count, protect)
        for anchor_count in anchor_counts
        for protect in protect_modes
    ]
    totals = {"hybrid": empty_metric_totals(k_values)}
    for anchor_count, protect in policies:
        totals[policy_name(anchor_count, protect)] = empty_metric_totals(k_values)

    for case in cases:
        target_ids = set(case.target_ids)
        hybrid_ids = reconciler.hybrid_baseline(case.question, limit=max_k)
        add_metric_totals(totals["hybrid"], hybrid_ids, target_ids)
        for anchor_count, protect in policies:
            result = reconciler.reconcile(
                case.question,
                candidate_limit=candidate_limit,
                edge_threshold=edge_threshold,
                anchor_count=anchor_count,
                protect_anchors=protect,
            )
            add_metric_totals(
                totals[policy_name(anchor_count, protect)],
                result.document_ids(max_k),
                target_ids,
            )

    metrics = {
        variant: average_metric_totals(metric_totals, len(cases))
        for variant, metric_totals in totals.items()
    }
    database.reset()
    return {
        "dataset": spec.dataset,
        "subset": spec.subset,
        "split": spec.split,
        "records_loaded": len(records),
        "cases": len(cases),
        "documents": len(documents),
        "candidate_limit": candidate_limit,
        "graph_objective": graph_objective,
        "calibration_sample": calibration_sample,
        "weights": weights.__dict__,
        "profile": profile.__dict__,
        "metrics": metrics,
    }


def parse_anchor_counts(value: str) -> list[int]:
    """Parse comma-separated anchor counts.

    Args:
        value: Comma-separated integer counts.

    Returns:
        Anchor counts.
    """
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def main() -> None:
    """Run the anchor-policy benchmark.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmarks",
        type=lambda value: parse_names(value, set(DEFAULT_BENCHMARKS)),
        default=list(DEFAULT_BENCHMARKS),
    )
    parser.add_argument("--limit-cases", type=int, default=300)
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--anchor-counts", type=parse_anchor_counts, default=[1, 2, 3, 4, 5])
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--calibration-sample", type=int, default=500)
    parser.add_argument("--graph-objective", default="auto")
    parser.add_argument("--ks", type=parse_k_values, default=[5, 10, 20, 30])
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    reports = {}
    for benchmark in args.benchmarks:
        print(f"Running {benchmark} anchor policy grid...", flush=True)
        report = evaluate_benchmark(
            BENCHMARK_SPECS[benchmark],
            limit_cases=args.limit_cases,
            anchor_counts=args.anchor_counts,
            protect_modes=[True, False],
            k_values=args.ks,
            candidate_limit=args.candidate_limit,
            edge_threshold=args.edge_threshold,
            calibration_sample=args.calibration_sample,
            graph_objective=args.graph_objective,
        )
        reports[benchmark] = report
        print(f"\n=== {benchmark.upper()} ANCHOR POLICY GRID ===")
        print_ranking_table(report["metrics"], args.ks)
        print()

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
