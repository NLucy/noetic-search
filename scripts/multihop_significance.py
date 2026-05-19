#!/usr/bin/env python
"""Paired significance tests for multi-hop retrieval recall.

The script compares hybrid retrieval against one calibrated Noetic objective on
the same benchmark cases. It reports paired mean recall deltas, bootstrap
confidence intervals, and a sign-flip randomization p-value.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_multihop_objectives import (
    BENCHMARK_SPECS,
    convert_records,
    load_records,
    parse_names,
)
from noetic_systems.database import Database
from noetic_systems.evaluation.metrics import parse_k_values, ranking_metrics
from noetic_systems.reconciliation.calibration import (
    GRAPH_OBJECTIVES,
    calibrate_corpus_graph_weights,
)
from noetic_systems.reconciliation.engine import Reconciler

DEFAULT_K_VALUES = (5, 10)


def paired_bootstrap_ci(
    deltas: list[float],
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float]:
    """Calculate a paired bootstrap confidence interval for mean deltas.

    Args:
        deltas: Per-case metric deltas.
        iterations: Bootstrap resamples.
        seed: Random seed.

    Returns:
        Lower and upper bounds for a 95% interval.
    """
    if not deltas:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(deltas)
    means = []
    for _ in range(iterations):
        sample_sum = sum(deltas[rng.randrange(n)] for _index in range(n))
        means.append(sample_sum / n)
    means.sort()
    lower = means[int(0.025 * (iterations - 1))]
    upper = means[int(0.975 * (iterations - 1))]
    return lower, upper


def sign_flip_p_value(
    deltas: list[float],
    *,
    iterations: int,
    seed: int,
) -> float:
    """Estimate a two-sided paired randomization p-value.

    Args:
        deltas: Per-case metric deltas.
        iterations: Random sign-flip samples.
        seed: Random seed.

    Returns:
        Approximate p-value.
    """
    if not deltas:
        return 1.0
    observed = abs(sum(deltas) / len(deltas))
    rng = random.Random(seed)
    extreme = 0
    for _ in range(iterations):
        flipped = [
            delta if rng.random() < 0.5 else -delta
            for delta in deltas
        ]
        if abs(sum(flipped) / len(flipped)) >= observed:
            extreme += 1
    return (extreme + 1) / (iterations + 1)


def evaluate_significance(
    benchmark: str,
    *,
    objective: str,
    limit_cases: int,
    k_values: list[int],
    candidate_limit: int,
    result_limit: int,
    edge_threshold: float,
    calibration_sample: int,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    """Evaluate paired significance for one benchmark.

    Args:
        benchmark: Benchmark short name.
        objective: Calibrated Noetic objective to compare with hybrid.
        limit_cases: Number of examples to load.
        k_values: Rank cutoffs.
        candidate_limit: Hybrid candidates used by reconciliation.
        result_limit: Candidate graph size.
        edge_threshold: Semantic graph threshold.
        calibration_sample: Corpus documents used for calibration.
        iterations: Bootstrap and randomization iterations.
        seed: Random seed.

    Returns:
        Significance report for one benchmark.
    """
    spec = BENCHMARK_SPECS[benchmark]
    records = load_records(spec, limit_cases)
    documents, cases = convert_records(spec, records)

    db = Database(collection_name=f"{benchmark}_significance", reset=True)
    db.add_documents(documents)
    try:
        weights, profile = calibrate_corpus_graph_weights(
            db,
            sample_limit=calibration_sample,
            objective=objective,
        )
        hybrid_reconciler = Reconciler(db)
        noetic_reconciler = Reconciler(db, graph_weights=weights)
        max_k = max(k_values)
        per_k = {k: [] for k in k_values}

        for case in cases:
            target_ids = set(case.target_ids)
            hybrid_ids = hybrid_reconciler.hybrid_baseline(case.question, limit=max_k)
            noetic_result = noetic_reconciler.reconcile(
                case.question,
                candidate_limit=candidate_limit,
                result_limit=result_limit,
                edge_threshold=edge_threshold,
            )
            noetic_ids = noetic_result.document_ids(max_k)

            for k in k_values:
                hybrid_recall = ranking_metrics(hybrid_ids, target_ids, k)["recall"]
                noetic_recall = ranking_metrics(noetic_ids, target_ids, k)["recall"]
                per_k[k].append(noetic_recall - hybrid_recall)

        metrics = {}
        for k, deltas in per_k.items():
            mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
            lower, upper = paired_bootstrap_ci(
                deltas,
                iterations=iterations,
                seed=seed + k,
            )
            p_value = sign_flip_p_value(
                deltas,
                iterations=iterations,
                seed=seed + 1000 + k,
            )
            improved = sum(1 for delta in deltas if delta > 0)
            worsened = sum(1 for delta in deltas if delta < 0)
            tied = len(deltas) - improved - worsened
            metrics[f"@{k}"] = {
                "mean_delta": mean_delta,
                "bootstrap_ci_95": [lower, upper],
                "randomization_p_value": p_value,
                "improved_cases": improved,
                "worsened_cases": worsened,
                "tied_cases": tied,
            }

        return {
            "benchmark": benchmark,
            "dataset": spec.dataset,
            "objective": objective,
            "cases": len(cases),
            "documents": len(documents),
            "profile": profile.__dict__,
            "weights": weights.__dict__,
            "metrics": metrics,
        }
    finally:
        db.reset()


def main() -> None:
    """Run paired significance testing.

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
    )
    parser.add_argument("--objective", choices=GRAPH_OBJECTIVES, default="auto")
    parser.add_argument("--limit-cases", type=int, default=300)
    parser.add_argument("--candidate-limit", type=int, default=50)
    parser.add_argument("--result-limit", type=int, default=30)
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--calibration-sample", type=int, default=500)
    parser.add_argument("--ks", type=parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    reports = []
    for benchmark in args.benchmarks:
        print(f"Running paired significance for {benchmark}...", flush=True)
        report = evaluate_significance(
            benchmark,
            objective=args.objective,
            limit_cases=args.limit_cases,
            k_values=args.ks,
            candidate_limit=args.candidate_limit,
            result_limit=args.result_limit,
            edge_threshold=args.edge_threshold,
            calibration_sample=args.calibration_sample,
            iterations=args.iterations,
            seed=args.seed,
        )
        reports.append(report)
        for k, metrics in report["metrics"].items():
            lower, upper = metrics["bootstrap_ci_95"]
            print(
                f"{benchmark:16} {k:>3} "
                f"delta={metrics['mean_delta']:.4f} "
                f"95% CI=[{lower:.4f}, {upper:.4f}] "
                f"p={metrics['randomization_p_value']:.4f} "
                f"improved/worse/tied="
                f"{metrics['improved_cases']}/"
                f"{metrics['worsened_cases']}/"
                f"{metrics['tied_cases']}"
            )

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps({"reports": reports}, indent=2))


if __name__ == "__main__":
    main()
