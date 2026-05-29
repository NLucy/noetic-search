#!/usr/bin/env python
"""Compare corpus-level graph-health objectives on HotpotQA.

Each objective derives fixed graph weights from corpus structure only. The
benchmark then evaluates retrieval quality with those frozen weights. This is a
development tool for learning which unsupervised graph-health priorities tend to
help multi-hop retrieval.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_hotpotqa import load_hotpotqa_records, print_ranking_table
from noetic_systems.database import Database
from noetic_systems.evaluation.hotpotqa import convert_records
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

DEFAULT_K_VALUES = (1, 3, 5, 10, 20, 30)


def parse_objectives(value: str) -> list[str]:
    """Parse comma-separated graph objectives.

    Args:
        value: Comma-separated objective names.

    Returns:
        Objective names.
    """
    objectives = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [name for name in objectives if name not in GRAPH_OBJECTIVES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown objectives: {', '.join(unknown)}")
    return objectives


def main() -> None:
    """Run the graph objective comparison CLI.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", default="distractor", choices=("distractor", "fullwiki"))
    parser.add_argument("--split", default="validation")
    parser.add_argument("--limit-cases", type=int, default=100)
    parser.add_argument("--collection-name", default="hotpotqa_objective_eval")
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--calibration-sample", type=int, default=500)
    parser.add_argument(
        "--objectives",
        type=parse_objectives,
        default=list(GRAPH_OBJECTIVES),
        help="comma-separated graph objective names",
    )
    parser.add_argument("--ks", type=parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    records = load_hotpotqa_records(args.subset, args.split, args.limit_cases)
    documents, cases = convert_records(records)

    db = Database(collection_name=args.collection_name, reset=True)
    db.add_documents(documents)

    max_k = max(args.ks)
    variants = ("hybrid", *args.objectives)
    metric_totals = {
        variant: empty_metric_totals(args.ks)
        for variant in variants
    }
    profiles = {}
    weights_by_objective = {}
    reconcilers = {}
    baseline_reconciler = Reconciler(db)

    for objective in args.objectives:
        weights, profile = calibrate_corpus_graph_weights(
            db,
            sample_limit=args.calibration_sample,
            objective=objective,
        )
        profiles[objective] = profile
        weights_by_objective[objective] = weights
        reconcilers[objective] = Reconciler(db, graph_weights=weights)

    for case in cases:
        hybrid_ids = baseline_reconciler.hybrid_baseline(case.question, limit=max_k)
        target_ids = set(case.target_ids)
        add_metric_totals(metric_totals["hybrid"], hybrid_ids, target_ids)

        for objective, reconciler in reconcilers.items():
            result = reconciler.reconcile(
                case.question,
                candidate_limit=args.candidate_limit,
                edge_threshold=args.edge_threshold,
            )
            add_metric_totals(
                metric_totals[objective],
                result.document_ids(max_k),
                target_ids,
            )

    metrics_by_variant = {
        variant: average_metric_totals(totals, len(cases))
        for variant, totals in metric_totals.items()
    }

    print("=== HOTPOTQA GRAPH OBJECTIVE GRID ===")
    print(f"subset/split: {args.subset}/{args.split}")
    print(f"cases: {len(cases)}")
    print(f"documents: {len(documents)}")
    print(f"calibration sample: {args.calibration_sample}")
    print()
    print_ranking_table(metrics_by_variant, args.ks)
    print()
    print("=== OBJECTIVE SETTINGS ===")
    for objective in args.objectives:
        weights = weights_by_objective[objective]
        profile = profiles[objective]
        print(
            f"{objective:24} "
            f"sem_w={weights.semantic_weight:.2f} "
            f"sem_t={weights.semantic_threshold:.3f} "
            f"lex_w={weights.lexical_weight:.3f} "
            f"lex_t={weights.lexical_threshold:.3f} "
            f"ref_w={weights.cross_reference_weight:.2f} "
            f"dup_w={weights.near_duplicate_weight:.2f} "
            f"density={profile.graph_density:.3f} "
            f"lcc={profile.largest_component_ratio:.3f} "
            f"centralization={profile.degree_centralization:.3f}"
        )

    if args.json_report:
        args.json_report.write_text(
            json.dumps(
                {
                    "metrics": metrics_by_variant,
                    "weights": {
                        name: weights.__dict__
                        for name, weights in weights_by_objective.items()
                    },
                    "profiles": {
                        name: profile.__dict__
                        for name, profile in profiles.items()
                    },
                },
                indent=2,
            )
        )

    db.reset()


if __name__ == "__main__":
    main()
