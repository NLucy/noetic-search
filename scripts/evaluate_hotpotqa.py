#!/usr/bin/env python
"""Evaluate hybrid retrieval and Noetic reconciliation on HotpotQA.

This CLI downloads a HotpotQA split through Hugging Face `datasets`, converts
each context paragraph into a retrieval document, and scores whether the known
supporting paragraphs appear in the returned rankings. It reports the same
precision, recall, hit rate, and MRR metrics used by the benchmark suite so
the runs are comparable.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from noetic_systems.database import Database
from noetic_systems.reconciliation.calibration import (
    GRAPH_OBJECTIVES,
    calibrate_corpus_graph_weights,
)
from noetic_systems.evaluation.ablations import (
    ABLATION_VARIANTS,
    ranked_ids_for_variant,
)
from noetic_systems.evaluation.hotpotqa import convert_records
from noetic_systems.evaluation.metrics import (
    add_metric_totals,
    average_metric_totals,
    empty_metric_totals,
    parse_k_values,
)
from noetic_systems.reconciliation.engine import Reconciler

DEFAULT_K_VALUES = (1, 3, 5, 10, 20, 30)


def load_hotpotqa_records(
    subset: str,
    split: str,
    limit_cases: int | None,
) -> list[dict]:
    """Load HotpotQA records from Hugging Face.

    Args:
        subset: HotpotQA subset, usually `distractor` or `fullwiki`.
        split: Dataset split, such as `validation`.
        limit_cases: Optional number of examples to load.

    Returns:
        List of dataset records.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "Install evaluation dependencies with:\n"
            "  uv sync --extra eval\n\n"
            "Then run:\n"
            "  uv run --extra eval python scripts/evaluate_hotpotqa.py --limit-cases 100"
        ) from exc

    split_expr = split if limit_cases is None else f"{split}[:{limit_cases}]"
    dataset = load_dataset("hotpotqa/hotpot_qa", subset, split=split_expr)
    return [dict(record) for record in dataset]


def print_ranking_table(
    metrics_by_variant: dict[str, dict[str, dict[str, float]]],
    k_values: list[int],
) -> None:
    """Print ranking metrics as a compact table.

    Args:
        metrics_by_variant: Averaged metrics by variant and cutoff.
        k_values: Rank cutoffs included in the report.

    Returns:
        None.
    """
    print("=== RANKING METRICS ===")
    print("variant   k   P@k    R@k    Hit@k  MRR@k")
    for variant, metrics_by_k in metrics_by_variant.items():
        for k in k_values:
            values = metrics_by_k[f"@{k}"]
            print(
                f"{variant:8} {k:2d}  "
                f"{values['precision']:.3f}  "
                f"{values['recall']:.3f}  "
                f"{values['hit']:.3f}  "
                f"{values['mrr']:.3f}"
            )


def main() -> None:
    """Run the HotpotQA retrieval evaluation CLI.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--subset",
        default="distractor",
        choices=("distractor", "fullwiki"),
        help="HotpotQA subset to load",
    )
    parser.add_argument(
        "--split",
        default="validation",
        help="HotpotQA split to load",
    )
    parser.add_argument(
        "--limit-cases",
        type=int,
        default=100,
        help="number of HotpotQA examples to evaluate",
    )
    parser.add_argument(
        "--collection-name",
        default="hotpotqa_eval",
        help="temporary Chroma collection name",
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
        "--diffusion-steps",
        type=int,
        default=10,
        help="diffusion time steps for Noetic reconciliation",
    )
    parser.add_argument(
        "--damping",
        type=float,
        default=0.85,
        help="fraction of energy moved across graph edges each diffusion step",
    )
    parser.add_argument(
        "--ks",
        type=parse_k_values,
        default=list(DEFAULT_K_VALUES),
        help="comma-separated rank cutoffs for precision, recall, hit, and MRR",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=None,
        help="optional path to write a machine-readable report",
    )
    parser.add_argument(
        "--ablations",
        action="store_true",
        help="run layer ablations in addition to hybrid and production Noetic",
    )
    parser.add_argument(
        "--calibrate-graph",
        action="store_true",
        help="derive one corpus-level graph calibration before evaluation",
    )
    parser.add_argument(
        "--graph-objective",
        choices=GRAPH_OBJECTIVES,
        default="reference_forward",
        help="corpus-level graph objective used with --calibrate-graph",
    )
    parser.add_argument(
        "--calibration-sample",
        type=int,
        default=500,
        help="documents sampled for corpus-level graph calibration",
    )
    args = parser.parse_args()

    records = load_hotpotqa_records(args.subset, args.split, args.limit_cases)
    documents, cases = convert_records(records)

    db = Database(collection_name=args.collection_name, reset=True)
    db.add_documents(documents)
    graph_weights = None
    if args.calibrate_graph:
        graph_weights, _profile = calibrate_corpus_graph_weights(
            db,
            sample_limit=args.calibration_sample,
            objective=args.graph_objective,
        )
    reconciler = Reconciler(db, graph_weights=graph_weights)

    max_k = max(args.ks)
    variants = ABLATION_VARIANTS if args.ablations else ("hybrid", "noetic")
    metric_totals = {
        variant: empty_metric_totals(args.ks)
        for variant in variants
    }
    rows = []
    baseline_times = []
    candidate_baseline_times = []
    reconcile_times = []

    for case in cases:
        baseline_start = time.perf_counter()
        hybrid_ids = reconciler.hybrid_baseline(case.question, limit=max_k)
        baseline_times.append((time.perf_counter() - baseline_start) * 1000)
        candidate_baseline_start = time.perf_counter()
        reconciler.hybrid_baseline(case.question, limit=args.candidate_limit)
        candidate_baseline_times.append(
            (time.perf_counter() - candidate_baseline_start) * 1000
        )

        reconcile_start = time.perf_counter()
        result = reconciler.reconcile(
            case.question,
            candidate_limit=args.candidate_limit,
            result_limit=args.result_limit,
            diffusion_steps=args.diffusion_steps,
            damping=args.damping,
            edge_threshold=args.edge_threshold,
        )
        reconcile_times.append((time.perf_counter() - reconcile_start) * 1000)
        graph_candidates = reconciler.hybrid.search(
            case.question,
            limit=max(args.candidate_limit, max_k),
        )
        noetic_ids = result.document_ids(max_k)
        graph_candidates_for_ablations = graph_candidates[: args.result_limit]

        target_ids = set(case.target_ids)
        add_metric_totals(metric_totals["hybrid"], hybrid_ids, target_ids)
        add_metric_totals(metric_totals["noetic"], noetic_ids, target_ids)
        if args.ablations:
            for variant in variants:
                if variant in {"hybrid", "noetic"}:
                    continue
                variant_ids = ranked_ids_for_variant(
                    db,
                    graph_candidates_for_ablations,
                    variant,
                    edge_threshold=args.edge_threshold,
                    diffusion_steps=args.diffusion_steps,
                    damping=args.damping,
                )
                add_metric_totals(metric_totals[variant], variant_ids, target_ids)

        rows.append(
            {
                "case": case.id,
                "question": case.question,
                "answer": case.answer,
                "target_ids": sorted(target_ids),
                "hybrid_ids": hybrid_ids,
                "noetic_ids": noetic_ids,
                "winner": result.winner.label,
                "uncertainty": result.uncertainty,
            }
        )

    total = len(cases)
    metrics_by_variant = {
        variant: average_metric_totals(totals, total)
        for variant, totals in metric_totals.items()
    }
    report = {
        "dataset": "hotpotqa/hotpot_qa",
        "subset": args.subset,
        "split": args.split,
        "cases": total,
        "documents": len(documents),
        "candidate_limit": args.candidate_limit,
        "result_limit": args.result_limit,
        "edge_threshold": args.edge_threshold,
        "calibrate_graph": args.calibrate_graph,
        "graph_objective": args.graph_objective,
        "calibration_sample": args.calibration_sample,
        "diffusion_steps": args.diffusion_steps,
        "damping": args.damping,
        "ks": args.ks,
        "ranking": metrics_by_variant,
        "latency_ms": {
            "hybrid_mean": sum(baseline_times) / len(baseline_times)
            if baseline_times
            else 0.0,
            "hybrid_candidate_mean": sum(candidate_baseline_times)
            / len(candidate_baseline_times)
            if candidate_baseline_times
            else 0.0,
            "noetic_mean": sum(reconcile_times) / len(reconcile_times)
            if reconcile_times
            else 0.0,
        },
    }

    print("=== HOTPOTQA RETRIEVAL BENCHMARK ===")
    print(f"subset/split: {args.subset}/{args.split}")
    print(f"cases: {total}")
    print(f"documents: {len(documents)}")
    print(f"candidate/result limit: {args.candidate_limit}/{args.result_limit}")
    print(f"edge threshold: {args.edge_threshold:.2f}")
    print(f"calibrate graph: {args.calibrate_graph}")
    if args.calibrate_graph:
        print(f"graph objective: {args.graph_objective}")
        print(f"calibration sample: {args.calibration_sample}")
    print(f"diffusion steps/damping: {args.diffusion_steps}/{args.damping:.2f}")
    print()
    print_ranking_table(metrics_by_variant, args.ks)

    if args.json_report:
        args.json_report.write_text(
            json.dumps({"metrics": report, "rows": rows}, indent=2)
        )

    db.reset()


if __name__ == "__main__":
    main()
