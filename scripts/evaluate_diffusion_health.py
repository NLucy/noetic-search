#!/usr/bin/env python
"""Study whether diffusion-health diagnostics explain benchmark performance.

This script is intentionally diagnostic, not product calibration. For each
benchmark corpus and graph objective, it derives fixed corpus-level graph
weights without labels, builds a calibration graph, measures all-node seeded
diffusion behavior, and then evaluates the same objective on retrieval metrics.
It finally reports whether label-free diffusion-health metrics correlate with
benchmark recall across objectives.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_multihop_objectives import (
    BENCHMARK_SPECS,
    DEFAULT_K_VALUES,
    DEFAULT_OBJECTIVES,
    convert_records,
    load_records,
    parse_names,
)
from noetic_systems.database import Database
from noetic_systems.evaluation.diffusion_health import (
    DiffusionHealth,
    diffusion_health,
    spearman_correlation,
)
from noetic_systems.evaluation.metrics import (
    add_metric_totals,
    average_metric_totals,
    empty_metric_totals,
    parse_k_values,
)
from noetic_systems.reconciliation.calibration import (
    GRAPH_OBJECTIVES,
    calibrate_corpus_graph_weights,
)
from noetic_systems.reconciliation.engine import Reconciler
from noetic_systems.reconciliation.graph import build_evidence_graph
from noetic_systems.search.semantic import SearchResult


def sampled_corpus_candidates(
    database: Database,
    sample_limit: int,
) -> list[SearchResult]:
    """Load corpus documents as graph candidates for diagnostics.

    Args:
        database: Indexed benchmark database.
        sample_limit: Maximum number of stored documents to sample.

    Returns:
        Search-result records with neutral scores.
    """
    result = database.collection.get(
        limit=sample_limit,
        include=["documents", "metadatas"],
    )
    return [
        SearchResult(
            id=doc_id,
            text=text,
            score=0.0,
            metadata=metadata or {},
        )
        for doc_id, text, metadata in zip(
            result.get("ids", []),
            result.get("documents", []),
            result.get("metadatas", []),
        )
    ]


def evaluate_with_health(
    benchmark: str,
    *,
    limit_cases: int,
    objectives: list[str],
    k_values: list[int],
    candidate_limit: int,
    edge_threshold: float,
    calibration_sample: int,
    diffusion_steps: int,
    damping: float,
    max_seeds: int | None,
) -> dict[str, Any]:
    """Evaluate one benchmark and attach diffusion-health diagnostics.

    Args:
        benchmark: Benchmark name from `BENCHMARK_SPECS`.
        limit_cases: Number of records to load.
        objectives: Graph objectives to compare.
        k_values: Rank cutoffs.
        candidate_limit: Hybrid candidates admitted to graph reconciliation.
        edge_threshold: Default semantic graph edge threshold.
        calibration_sample: Corpus documents sampled for graph calibration.
        diffusion_steps: All-node diffusion diagnostic time steps.
        damping: Diffusion damping value.
        max_seeds: Optional cap on seed nodes in the diagnostic graph.

    Returns:
        Report with ranking metrics, health metrics, and correlations.
    """
    spec = BENCHMARK_SPECS[benchmark]
    records = load_records(spec, limit_cases)
    documents, cases = convert_records(spec, records)
    db = Database(collection_name=f"{benchmark}_diffusion_health", reset=True)
    db.add_documents(documents)

    calibration_candidates = sampled_corpus_candidates(db, calibration_sample)
    doc_index = {candidate.id: candidate for candidate in calibration_candidates}
    max_k = max(k_values)
    metric_totals = {
        "hybrid": empty_metric_totals(k_values),
        **{
            objective: empty_metric_totals(k_values)
            for objective in objectives
        },
    }
    health_by_objective: dict[str, DiffusionHealth] = {}
    reconcilers = {}
    weights_by_objective = {}
    profiles = {}
    baseline_reconciler = Reconciler(db)

    for objective in objectives:
        weights, profile = calibrate_corpus_graph_weights(
            db,
            sample_limit=calibration_sample,
            objective=objective,
        )
        graph, _edges = build_evidence_graph(
            db,
            doc_index,
            edge_threshold,
            weights=weights,
        )
        health_by_objective[objective] = diffusion_health(
            graph,
            steps=diffusion_steps,
            damping=damping,
            max_seeds=max_seeds,
        )
        reconcilers[objective] = Reconciler(db, graph_weights=weights)
        weights_by_objective[objective] = weights
        profiles[objective] = profile

    for case in cases:
        target_ids = set(case.target_ids)
        hybrid_ids = baseline_reconciler.hybrid_baseline(case.question, limit=max_k)
        add_metric_totals(metric_totals["hybrid"], hybrid_ids, target_ids)

        for objective, reconciler in reconcilers.items():
            result = reconciler.reconcile(
                case.question,
                candidate_limit=candidate_limit,
                edge_threshold=edge_threshold,
            )
            add_metric_totals(metric_totals[objective], result.document_ids(max_k), target_ids)

    metrics = {
        variant: average_metric_totals(totals, len(cases))
        for variant, totals in metric_totals.items()
    }
    correlations = correlations_for_objectives(objectives, metrics, health_by_objective)
    report = {
        "dataset": spec.dataset,
        "subset": spec.subset,
        "split": spec.split,
        "records_loaded": len(records),
        "cases": len(cases),
        "documents": len(documents),
        "metrics": metrics,
        "health": {
            objective: health.__dict__
            for objective, health in health_by_objective.items()
        },
        "correlations": correlations,
        "weights": {
            objective: weights.__dict__
            for objective, weights in weights_by_objective.items()
        },
        "profiles": {
            objective: profile.__dict__
            for objective, profile in profiles.items()
        },
    }
    db.reset()
    return report


def correlations_for_objectives(
    objectives: list[str],
    metrics: dict[str, dict[str, dict[str, float]]],
    health_by_objective: dict[str, DiffusionHealth],
) -> dict[str, dict[str, float]]:
    """Correlate diffusion-health metrics with objective recall.

    Args:
        objectives: Objective names to compare.
        metrics: Ranking metrics by variant.
        health_by_objective: Diffusion-health metrics by objective.

    Returns:
        Spearman correlations keyed by cutoff and health metric.
    """
    health_names = list(DiffusionHealth.__dataclass_fields__)
    output: dict[str, dict[str, float]] = {}
    for cutoff in ("@5", "@10"):
        recall_values = [
            metrics[objective][cutoff]["recall"]
            for objective in objectives
            if cutoff in metrics[objective]
        ]
        output[cutoff] = {}
        for health_name in health_names:
            health_values = [
                getattr(health_by_objective[objective], health_name)
                for objective in objectives
                if cutoff in metrics[objective]
            ]
            output[cutoff][health_name] = spearman_correlation(
                health_values,
                recall_values,
            )
    return output


def print_health_report(benchmark: str, report: dict[str, Any]) -> None:
    """Print compact health and recall report.

    Args:
        benchmark: Benchmark name.
        report: Benchmark report.

    Returns:
        None.
    """
    print(f"=== {benchmark.upper()} DIFFUSION HEALTH STUDY ===")
    print(f"records/cases/documents: {report['records_loaded']}/{report['cases']}/{report['documents']}")
    print(
        "objective                 R@5    R@10   health  transfer "
        "flood  spread retain coherent isolate"
    )
    for objective, health in report["health"].items():
        metrics = report["metrics"][objective]
        print(
            f"{objective:24} "
            f"{metrics['@5']['recall']:.3f}  "
            f"{metrics['@10']['recall']:.3f}  "
            f"{health['health_score']:.3f}   "
            f"{health['neighbor_transfer']:.3f}    "
            f"{health['field_flooding']:.3f}  "
            f"{health['spread_balance']:.3f}  "
            f"{health['retention_balance']:.3f}  "
            f"{health['flow_coherence']:.3f}    "
            f"{health['isolation_rate']:.3f}"
        )
    print("correlation with recall:")
    for cutoff, values in report["correlations"].items():
        best = sorted(values.items(), key=lambda item: abs(item[1]), reverse=True)
        rendered = ", ".join(f"{name}={value:.2f}" for name, value in best[:4])
        print(f"  {cutoff}: {rendered}")
    print()


def main() -> None:
    """Run the diffusion-health diagnostic CLI.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmarks",
        type=lambda value: parse_names(value, set(BENCHMARK_SPECS)),
        default=["hotpotqa", "2wikimultihopqa", "musique"],
        help="comma-separated benchmark names",
    )
    parser.add_argument(
        "--objectives",
        type=lambda value: parse_names(value, set(GRAPH_OBJECTIVES)),
        default=list(DEFAULT_OBJECTIVES),
        help="comma-separated graph objective names",
    )
    parser.add_argument("--limit-cases", type=int, default=100)
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--calibration-sample", type=int, default=500)
    parser.add_argument("--diffusion-steps", type=int, default=4)
    parser.add_argument("--damping", type=float, default=0.85)
    parser.add_argument("--max-seeds", type=int, default=200)
    parser.add_argument("--ks", type=parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    reports = {}
    for benchmark in args.benchmarks:
        print(f"Running {benchmark}...", flush=True)
        report = evaluate_with_health(
            benchmark,
            limit_cases=args.limit_cases,
            objectives=args.objectives,
            k_values=args.ks,
            candidate_limit=args.candidate_limit,
            edge_threshold=args.edge_threshold,
            calibration_sample=args.calibration_sample,
            diffusion_steps=args.diffusion_steps,
            damping=args.damping,
            max_seeds=args.max_seeds,
        )
        reports[benchmark] = report
        print_health_report(benchmark, report)

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
