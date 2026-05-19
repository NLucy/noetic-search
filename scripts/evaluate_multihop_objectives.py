#!/usr/bin/env python
"""Compare graph objectives across external multi-hop retrieval benchmarks.

The benchmark suite uses datasets with paragraph-level support labels:
HotpotQA, 2WikiMultiHopQA, and MuSiQue. Each corpus is indexed independently,
one corpus-level graph profile is derived without queries or labels, and the
same fixed objective is evaluated over that benchmark's questions.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_hotpotqa import print_ranking_table
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
from noetic_systems.reconciliation.calibration import (
    GRAPH_OBJECTIVES,
    calibrate_corpus_graph_weights,
)
from noetic_systems.reconciliation.engine import Reconciler

DEFAULT_BENCHMARKS = ("hotpotqa", "2wikimultihopqa", "musique")
DEFAULT_OBJECTIVES = (
    "balanced",
    "lexical_salience_heavy",
    "reference_forward",
    "anti_hub",
    "semantic_heavy",
)
DEFAULT_K_VALUES = (1, 3, 5, 10, 20, 30)


@dataclass(frozen=True)
class BenchmarkSpec:
    """Hugging Face dataset specification.

    Attributes:
        name: Short benchmark name used in reports.
        dataset: Hugging Face dataset id.
        subset: Optional dataset subset/config.
        split: Dataset split.
        converter: Conversion function name.
    """

    name: str
    dataset: str
    subset: str | None
    split: str
    converter: str


BENCHMARK_SPECS = {
    "hotpotqa": BenchmarkSpec(
        name="hotpotqa",
        dataset="hotpotqa/hotpot_qa",
        subset="distractor",
        split="validation",
        converter="hotpot_like",
    ),
    "2wikimultihopqa": BenchmarkSpec(
        name="2wikimultihopqa",
        dataset="framolfese/2WikiMultihopQA",
        subset=None,
        split="validation",
        converter="hotpot_like",
    ),
    "musique": BenchmarkSpec(
        name="musique",
        dataset="fladhak/musique",
        subset=None,
        split="validation",
        converter="musique",
    ),
}


def parse_names(value: str, allowed: tuple[str, ...] | set[str]) -> list[str]:
    """Parse comma-separated names and validate membership.

    Args:
        value: Comma-separated names.
        allowed: Valid names.

    Returns:
        Parsed names.
    """
    names = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [name for name in names if name not in allowed]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown values: {', '.join(unknown)}")
    return names


def load_records(spec: BenchmarkSpec, limit_cases: int) -> list[dict[str, Any]]:
    """Load benchmark records from Hugging Face.

    Args:
        spec: Benchmark dataset specification.
        limit_cases: Number of examples to load.

    Returns:
        Dataset records as dictionaries.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "Install evaluation dependencies with:\n"
            "  uv sync --extra eval"
        ) from exc

    split_expr = f"{spec.split}[:{limit_cases}]"
    if spec.subset is None:
        dataset = load_dataset(spec.dataset, split=split_expr)
    else:
        dataset = load_dataset(spec.dataset, spec.subset, split=split_expr)
    return [dict(record) for record in dataset]


def convert_records(
    spec: BenchmarkSpec,
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[RetrievalCase]]:
    """Convert benchmark records into documents and retrieval cases.

    Args:
        spec: Benchmark dataset specification.
        records: Raw dataset records.

    Returns:
        Tuple of corpus documents and retrieval cases.
    """
    if spec.converter == "hotpot_like":
        return convert_hotpot_like_records(records, source=spec.name)
    if spec.converter == "musique":
        return convert_musique_records(records, source=spec.name)
    raise ValueError(f"unknown converter: {spec.converter}")


def evaluate_benchmark(
    spec: BenchmarkSpec,
    *,
    limit_cases: int,
    objectives: list[str],
    k_values: list[int],
    candidate_limit: int,
    result_limit: int,
    edge_threshold: float,
    calibration_sample: int,
) -> dict[str, Any]:
    """Evaluate one benchmark across graph objectives.

    Args:
        spec: Benchmark dataset specification.
        limit_cases: Number of records to load.
        objectives: Graph objectives to compare.
        k_values: Rank cutoffs.
        candidate_limit: Hybrid candidates admitted to graph reconciliation.
        result_limit: Documents kept in the reconciled graph.
        edge_threshold: Default semantic graph edge threshold.
        calibration_sample: Corpus documents sampled for graph calibration.

    Returns:
        Benchmark report containing metrics, weights, and graph profiles.
    """
    records = load_records(spec, limit_cases)
    documents, cases = convert_records(spec, records)

    db = Database(collection_name=f"{spec.name}_objective_suite", reset=True)
    db.add_documents(documents)

    max_k = max(k_values)
    variants = ("hybrid", *objectives)
    metric_totals = {
        variant: empty_metric_totals(k_values)
        for variant in variants
    }
    profiles = {}
    weights_by_objective = {}
    reconcilers = {}
    baseline_reconciler = Reconciler(db)

    for objective in objectives:
        weights, profile = calibrate_corpus_graph_weights(
            db,
            sample_limit=calibration_sample,
            objective=objective,
        )
        profiles[objective] = profile
        weights_by_objective[objective] = weights
        reconcilers[objective] = Reconciler(db, graph_weights=weights)

    for case in cases:
        target_ids = set(case.target_ids)
        hybrid_ids = baseline_reconciler.hybrid_baseline(case.question, limit=max_k)
        add_metric_totals(metric_totals["hybrid"], hybrid_ids, target_ids)

        for objective, reconciler in reconcilers.items():
            result = reconciler.reconcile(
                case.question,
                candidate_limit=candidate_limit,
                result_limit=result_limit,
                edge_threshold=edge_threshold,
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
    report = {
        "dataset": spec.dataset,
        "subset": spec.subset,
        "split": spec.split,
        "records_loaded": len(records),
        "cases": len(cases),
        "documents": len(documents),
        "metrics": metrics_by_variant,
        "weights": {
            name: weights.__dict__
            for name, weights in weights_by_objective.items()
        },
        "profiles": {
            name: profile.__dict__
            for name, profile in profiles.items()
        },
    }
    db.reset()
    return report


def main() -> None:
    """Run the cross-benchmark graph objective CLI.

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
    parser.add_argument("--limit-cases", type=int, default=100)
    parser.add_argument("--candidate-limit", type=int, default=50)
    parser.add_argument("--result-limit", type=int, default=30)
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--calibration-sample", type=int, default=500)
    parser.add_argument(
        "--objectives",
        type=lambda value: parse_names(value, set(GRAPH_OBJECTIVES)),
        default=list(DEFAULT_OBJECTIVES),
        help="comma-separated graph objective names",
    )
    parser.add_argument("--ks", type=parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    reports = {}
    for benchmark in args.benchmarks:
        spec = BENCHMARK_SPECS[benchmark]
        print(f"Running {benchmark}...", flush=True)
        report = evaluate_benchmark(
            spec,
            limit_cases=args.limit_cases,
            objectives=args.objectives,
            k_values=args.ks,
            candidate_limit=args.candidate_limit,
            result_limit=args.result_limit,
            edge_threshold=args.edge_threshold,
            calibration_sample=args.calibration_sample,
        )
        reports[benchmark] = report

        print(f"=== {benchmark.upper()} GRAPH OBJECTIVE GRID ===")
        print(f"dataset: {report['dataset']}")
        print(f"subset/split: {report['subset']}/{report['split']}")
        print(
            "records/cases/documents: "
            f"{report['records_loaded']}/{report['cases']}/{report['documents']}"
        )
        print(f"calibration sample: {args.calibration_sample}")
        print()
        print_ranking_table(report["metrics"], args.ks)
        print()

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
