#!/usr/bin/env python
"""Ablate the production linked-evidence retrieval path.

This script asks where the current benchmark lift comes from. It keeps hybrid
retrieval as the candidate selector, then varies only the graph and linked
ranking pieces used after broad retrieval. The goal is to separate the effect of
anchors, anchor affinity, graph support, semantic edges, lexical edges, and
corpus-level graph calibration.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_hotpotqa import print_ranking_table
from scripts.evaluate_multihop_objectives import (
    BENCHMARK_SPECS,
    BenchmarkSpec,
    convert_records,
    load_records,
    parse_names,
)
from noetic_systems.database import Database
from noetic_systems.evaluation.metrics import (
    add_metric_totals,
    average_metric_totals,
    empty_metric_totals,
    parse_k_values,
)
from noetic_systems.evaluation.multihop import RetrievalCase
from noetic_systems.reconciliation.calibration import calibrate_corpus_graph_weights
from noetic_systems.reconciliation.graph import GraphWeights, build_evidence_graph
from noetic_systems.reconciliation.ranking import rank_linked_evidence
from noetic_systems.search.hybrid import HybridSearch
from noetic_systems.search.semantic import SearchResult

DEFAULT_BENCHMARKS = ("hotpotqa", "2wikimultihopqa", "musique")
DEFAULT_K_VALUES = (5, 10)
DEFAULT_VARIANTS = (
    "hybrid",
    "linked_static",
    "linked_auto",
    "anchors_only",
    "no_anchors",
    "no_anchor_affinity",
    "no_support",
    "anchor_affinity_only",
    "support_only",
    "semantic_only",
    "lexical_only",
)


def load_benchmark(
    spec: BenchmarkSpec,
    *,
    limit_cases: int,
) -> tuple[Database, list[RetrievalCase]]:
    """Load benchmark records and index the retrieval corpus.

    Args:
        spec: Benchmark dataset specification.
        limit_cases: Number of cases to load.

    Returns:
        Indexed database and converted retrieval cases.
    """
    records = load_records(spec, limit_cases)
    documents, cases = convert_records(spec, records)
    db = Database(collection_name=f"{spec.name}_linked_ablation", reset=True)
    db.add_documents(documents)
    return db, cases


def parse_variants(value: str) -> list[str]:
    """Parse comma-separated ablation variant names.

    Args:
        value: Comma-separated variant names.

    Returns:
        Validated variant names.
    """
    return parse_names(value, set(DEFAULT_VARIANTS))


def rank_variant(
    database: Database,
    candidates: list[SearchResult],
    variant: str,
    *,
    edge_threshold: float,
    auto_weights: GraphWeights,
) -> list[str]:
    """Rank one candidate field with a linked-production ablation variant.

    Args:
        database: Indexed benchmark corpus.
        candidates: Broad hybrid candidates in original order.
        variant: Ablation variant name.
        edge_threshold: Default semantic edge threshold.
        auto_weights: Corpus-calibrated graph weights for `linked_auto`.

    Returns:
        Ranked document ids.
    """
    if variant == "hybrid":
        return [candidate.id for candidate in candidates]

    weights = weights_for_variant(variant, auto_weights)
    graph_candidates = {candidate.id: candidate for candidate in candidates}
    graph, _edges = build_evidence_graph(
        database,
        graph_candidates,
        edge_threshold,
        weights=weights,
    )

    if variant == "anchors_only":
        return rank_linked_evidence(
            candidates,
            graph,
            query_weight=1.0,
            link_weight=0.0,
            support_weight=0.0,
        )
    if variant == "no_anchors":
        return rank_linked_evidence(candidates, graph, anchor_count=0)
    if variant == "no_anchor_affinity":
        return rank_linked_evidence(
            candidates,
            graph,
            query_weight=0.85,
            link_weight=0.0,
            support_weight=0.15,
        )
    if variant == "no_support":
        return rank_linked_evidence(
            candidates,
            graph,
            query_weight=0.59,
            link_weight=0.41,
            support_weight=0.0,
        )
    if variant == "anchor_affinity_only":
        return rank_linked_evidence(
            candidates,
            graph,
            query_weight=0.0,
            link_weight=1.0,
            support_weight=0.0,
        )
    if variant == "support_only":
        return rank_linked_evidence(
            candidates,
            graph,
            anchor_count=0,
            query_weight=0.0,
            link_weight=0.0,
            support_weight=1.0,
        )

    return rank_linked_evidence(candidates, graph)


def weights_for_variant(
    variant: str,
    auto_weights: GraphWeights,
) -> GraphWeights:
    """Return graph-construction weights for an ablation variant.

    Args:
        variant: Ablation variant name.
        auto_weights: Corpus-calibrated graph weights.

    Returns:
        Graph weights used by the variant.
    """
    if variant == "linked_auto":
        return auto_weights
    if variant == "semantic_only":
        return GraphWeights(
            lexical_threshold=2.0,
            lexical_weight=0.0,
            cross_reference_weight=0.0,
            near_duplicate_weight=0.0,
        )
    if variant == "lexical_only":
        return GraphWeights(
            semantic_threshold=2.0,
            semantic_weight=0.0,
            cross_reference_weight=0.0,
            near_duplicate_weight=0.0,
        )
    return GraphWeights()


def evaluate_benchmark(
    spec: BenchmarkSpec,
    *,
    limit_cases: int,
    variants: list[str],
    k_values: list[int],
    candidate_limit: int,
    result_limit: int,
    edge_threshold: float,
    calibration_sample: int,
) -> dict[str, Any]:
    """Evaluate linked-production ablations on one benchmark.

    Args:
        spec: Benchmark dataset specification.
        limit_cases: Number of cases to evaluate.
        variants: Ablation variants to run.
        k_values: Rank cutoffs.
        candidate_limit: Hybrid candidates retrieved for candidate recall.
        result_limit: Candidates admitted to graph reconciliation.
        edge_threshold: Default semantic graph edge threshold.
        calibration_sample: Corpus sample size for `linked_auto`.

    Returns:
        Benchmark report containing metrics and auto weights.
    """
    db, cases = load_benchmark(spec, limit_cases=limit_cases)
    hybrid = HybridSearch(db)
    auto_weights, auto_profile = calibrate_corpus_graph_weights(
        db,
        sample_limit=calibration_sample,
        objective="auto",
    )
    max_k = max(k_values)
    totals = {variant: empty_metric_totals(k_values) for variant in variants}

    for case in cases:
        candidates = hybrid.search(case.question, limit=candidate_limit)
        graph_candidates = candidates[:result_limit]
        targets = set(case.target_ids)
        for variant in variants:
            if variant == "hybrid":
                ranked_ids = [candidate.id for candidate in candidates[:max_k]]
            else:
                ranked_ids = rank_variant(
                    db,
                    graph_candidates,
                    variant,
                    edge_threshold=edge_threshold,
                    auto_weights=auto_weights,
                )
            add_metric_totals(totals[variant], ranked_ids, targets)

    metrics = {
        variant: average_metric_totals(total, len(cases))
        for variant, total in totals.items()
    }
    report = {
        "dataset": spec.dataset,
        "subset": spec.subset,
        "split": spec.split,
        "cases": len(cases),
        "metrics": metrics,
        "auto_weights": asdict(auto_weights),
        "auto_profile": asdict(auto_profile),
    }
    db.reset()
    return report


def main() -> None:
    """Run the linked-production ablation CLI.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmarks",
        type=lambda value: parse_names(value, set(BENCHMARK_SPECS)),
        default=list(DEFAULT_BENCHMARKS),
        help="comma-separated benchmark names",
    )
    parser.add_argument(
        "--variants",
        type=parse_variants,
        default=list(DEFAULT_VARIANTS),
        help="comma-separated linked ablation variant names",
    )
    parser.add_argument("--limit-cases", type=int, default=100)
    parser.add_argument("--candidate-limit", type=int, default=50)
    parser.add_argument("--result-limit", type=int, default=30)
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--calibration-sample", type=int, default=500)
    parser.add_argument("--ks", type=parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    reports = {}
    for benchmark in args.benchmarks:
        print(f"Running {benchmark} linked ablation...", flush=True)
        report = evaluate_benchmark(
            BENCHMARK_SPECS[benchmark],
            limit_cases=args.limit_cases,
            variants=args.variants,
            k_values=args.ks,
            candidate_limit=args.candidate_limit,
            result_limit=args.result_limit,
            edge_threshold=args.edge_threshold,
            calibration_sample=args.calibration_sample,
        )
        reports[benchmark] = report
        print(f"\n=== {benchmark.upper()} LINKED ABLATION ===")
        print_ranking_table(report["metrics"], args.ks)

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
