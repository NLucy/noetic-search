#!/usr/bin/env python
"""Train, validate, and evaluate graph-health calibration settings.

This script turns the graph-health constants into an explicit experimental
object. It screens a readable grid of `GraphHealthConfig` settings on training
cases, selects the winner on validation cases, freezes that winner, and
evaluates it on held-out cases. The tuning target is retrieval quality, not
query-time graph inspection. No setting is changed per query.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
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
from noetic_systems.reconciliation.calibration import (
    GraphHealthConfig,
    calibrate_corpus_graph_weights,
)
from noetic_systems.reconciliation.engine import Reconciler

DEFAULT_BENCHMARKS = ("hotpotqa", "2wikimultihopqa", "musique")
DEFAULT_K_VALUES = (5, 10)


def candidate_health_configs() -> list[tuple[str, GraphHealthConfig]]:
    """Return named graph-health configurations for benchmark training.

    The grid is deliberately interpretable. Each candidate changes a coherent
    scoring priority, making the report readable after training.

    Args:
        None.

    Returns:
        Named graph-health configurations.
    """
    base = GraphHealthConfig()
    configs = [
        ("default", base),
        (
            "sparser_agreement",
            replace(
                base,
                density_target=0.12,
                agreement_target=0.04,
                bridge_start=0.12,
                bridge_stop=0.55,
                resonance_weight=0.24,
                bridge_weight=0.18,
                density_weight=0.18,
            ),
        ),
        (
            "denser_support",
            replace(
                base,
                density_target=0.22,
                lcc_target=0.90,
                agreement_target=0.08,
                connectivity_weight=0.18,
                density_weight=0.18,
                bridge_weight=0.11,
            ),
        ),
        (
            "anti_hub",
            replace(
                base,
                centralization_start=0.12,
                centralization_stop=0.42,
                centralization_weight=0.20,
                density_weight=0.17,
                duplicate_weight=0.14,
            ),
        ),
        (
            "agreement_heavy",
            replace(
                base,
                agreement_target=0.08,
                agreement_right_width=0.18,
                resonance_weight=0.28,
                lexical_weight=0.16,
                bridge_weight=0.18,
                density_weight=0.15,
                connectivity_weight=0.12,
            ),
        ),
        (
            "connectivity_heavy",
            replace(
                base,
                lcc_target=0.88,
                lcc_left_width=0.28,
                lcc_right_width=0.12,
                connectivity_weight=0.24,
                density_weight=0.18,
                centralization_weight=0.16,
                resonance_weight=0.16,
            ),
        ),
        (
            "duplicate_strict",
            replace(
                base,
                duplicate_start=0.02,
                duplicate_stop=0.10,
                duplicate_weight=0.20,
                density_weight=0.17,
                resonance_weight=0.18,
            ),
        ),
    ]
    density_targets = (0.12, 0.16, 0.22)
    agreement_targets = (0.04, 0.06, 0.08)
    bridge_profiles = (
        ("bridge_strict", 0.12, 0.50, 0.20),
        ("bridge_balanced", 0.20, 0.70, 0.15),
        ("bridge_tolerant", 0.28, 0.82, 0.10),
    )
    structural_profiles = (
        ("lcc_moderate", 0.78, 0.18),
        ("lcc_high", 0.90, 0.22),
    )

    for density_target in density_targets:
        for agreement_target in agreement_targets:
            configs.append(
                (
                    f"d{int(density_target * 100)}_a{int(agreement_target * 100)}",
                    replace(
                        base,
                        density_target=density_target,
                        agreement_target=agreement_target,
                    ),
                )
            )

    for name, bridge_start, bridge_stop, bridge_weight in bridge_profiles:
        configs.append(
            (
                name,
                replace(
                    base,
                    bridge_start=bridge_start,
                    bridge_stop=bridge_stop,
                    bridge_weight=bridge_weight,
                ),
            )
        )

    for name, lcc_target, connectivity_weight in structural_profiles:
        configs.append(
            (
                name,
                replace(
                    base,
                    lcc_target=lcc_target,
                    connectivity_weight=connectivity_weight,
                    density_weight=0.18,
                    centralization_weight=0.16,
                ),
            )
        )

    return dedupe_configs(configs)


def dedupe_configs(
    configs: list[tuple[str, GraphHealthConfig]],
) -> list[tuple[str, GraphHealthConfig]]:
    """Remove duplicate configurations while preserving first names.

    Args:
        configs: Named graph-health configurations.

    Returns:
        Deduplicated named configurations.
    """
    seen: set[tuple[tuple[str, float], ...]] = set()
    output: list[tuple[str, GraphHealthConfig]] = []
    for name, config in configs:
        key = tuple(sorted(asdict(config).items()))
        if key in seen:
            continue
        seen.add(key)
        output.append((name, config))
    return output


def build_benchmark_index(
    spec: BenchmarkSpec,
    *,
    limit_cases: int,
) -> tuple[Database, list[RetrievalCase]]:
    """Load a benchmark subset and index its paragraph corpus.

    Args:
        spec: Benchmark dataset specification.
        limit_cases: Number of benchmark records to load.

    Returns:
        Database plus converted retrieval cases.
    """
    records = load_records(spec, limit_cases)
    documents, cases = convert_records(spec, records)
    db = Database(collection_name=f"{spec.name}_health_tuning", reset=True)
    db.add_documents(documents)
    return db, cases


def evaluate_config(
    database: Database,
    cases: list[RetrievalCase],
    *,
    health_config: GraphHealthConfig,
    k_values: list[int],
    candidate_limit: int,
    edge_threshold: float,
    calibration_sample: int,
) -> dict[str, Any]:
    """Evaluate one graph-health configuration on retrieval cases.

    Args:
        database: Indexed benchmark corpus.
        cases: Retrieval cases to evaluate.
        health_config: Frozen graph-health scoring configuration.
        k_values: Rank cutoffs.
        candidate_limit: Hybrid candidates admitted to reconciliation.
        edge_threshold: Default semantic graph edge threshold.
        calibration_sample: Corpus documents sampled for graph calibration.

    Returns:
        Metrics, selected graph weights, and calibration profile.
    """
    weights, profile = calibrate_corpus_graph_weights(
        database,
        sample_limit=calibration_sample,
        objective="auto",
        health_config=health_config,
    )
    reconciler = Reconciler(database, graph_weights=weights)
    totals = empty_metric_totals(k_values)
    max_k = max(k_values)

    for case in cases:
        result = reconciler.reconcile(
            case.question,
            candidate_limit=candidate_limit,
            edge_threshold=edge_threshold,
        )
        add_metric_totals(totals, result.document_ids(max_k), set(case.target_ids))

    return {
        "metrics": average_metric_totals(totals, len(cases)),
        "weights": asdict(weights),
        "profile": asdict(profile),
    }


def evaluate_hybrid(
    database: Database,
    cases: list[RetrievalCase],
    *,
    k_values: list[int],
) -> dict[str, dict[str, float]]:
    """Evaluate raw hybrid retrieval for comparison.

    Args:
        database: Indexed benchmark corpus.
        cases: Retrieval cases to evaluate.
        k_values: Rank cutoffs.

    Returns:
        Average metrics by cutoff.
    """
    reconciler = Reconciler(database)
    totals = empty_metric_totals(k_values)
    max_k = max(k_values)
    for case in cases:
        ranked_ids = reconciler.hybrid_baseline(case.question, limit=max_k)
        add_metric_totals(totals, ranked_ids, set(case.target_ids))
    return average_metric_totals(totals, len(cases))


def objective_score(
    metrics_by_benchmark: dict[str, dict[str, Any]],
    *,
    k_values: list[int],
) -> float:
    """Score a trained configuration from benchmark retrieval metrics.

    Args:
        metrics_by_benchmark: Per-benchmark evaluation reports.
        k_values: Rank cutoffs included in the run.

    Returns:
        Mean recall across benchmarks and cutoffs.
    """
    values: list[float] = []
    for report in metrics_by_benchmark.values():
        metrics = report["metrics"]
        for cutoff in k_values:
            values.append(metrics[f"@{cutoff}"]["recall"])
    return sum(values) / len(values) if values else 0.0


def tune_health_config(
    *,
    benchmarks: list[str],
    train_cases: int,
    validation_cases: int,
    test_cases: int,
    validation_finalists: int,
    k_values: list[int],
    candidate_limit: int,
    edge_threshold: float,
    calibration_sample: int,
) -> dict[str, Any]:
    """Train, validate, and evaluate graph-health settings.

    Args:
        benchmarks: Benchmark names to include.
        train_cases: Number of cases used for initial candidate screening.
        validation_cases: Number of cases used for selecting the winner.
        test_cases: Number of held-out cases used for final evaluation.
        validation_finalists: Number of train-ranked configs evaluated on
            validation splits.
        k_values: Rank cutoffs.
        candidate_limit: Hybrid candidates admitted to reconciliation.
        edge_threshold: Default semantic graph edge threshold.
        calibration_sample: Corpus documents sampled for graph calibration.

    Returns:
        Training, validation, and held-out evaluation report.
    """
    indexed: dict[
        str,
        tuple[Database, list[RetrievalCase], list[RetrievalCase], list[RetrievalCase]],
    ] = {}
    limit_cases = train_cases + validation_cases + test_cases
    for benchmark in benchmarks:
        print(f"Indexing {benchmark} ({limit_cases} records)...", flush=True)
        db, cases = build_benchmark_index(
            BENCHMARK_SPECS[benchmark],
            limit_cases=limit_cases,
        )
        validation_start = train_cases
        test_start = train_cases + validation_cases
        indexed[benchmark] = (
            db,
            cases[:train_cases],
            cases[validation_start:test_start],
            cases[test_start:limit_cases],
        )

    trained: list[dict[str, Any]] = []
    for name, config in candidate_health_configs():
        print(f"Training config {name}...", flush=True)
        train_reports = {}
        for benchmark, (db, train_split, _, _) in indexed.items():
            print(f"  {benchmark} train split...", flush=True)
            train_reports[benchmark] = evaluate_config(
                db,
                train_split,
                health_config=config,
                k_values=k_values,
                candidate_limit=candidate_limit,
                edge_threshold=edge_threshold,
                calibration_sample=calibration_sample,
            )
        trained.append(
            {
                "name": name,
                "score": objective_score(train_reports, k_values=k_values),
                "config": asdict(config),
                "train": train_reports,
            }
        )

    trained.sort(key=lambda item: item["score"], reverse=True)
    finalists = trained[: max(1, validation_finalists)]
    validated: list[dict[str, Any]] = []
    for candidate in finalists:
        name = candidate["name"]
        config = GraphHealthConfig(**candidate["config"])
        print(f"Validating config {name}...", flush=True)
        validation_reports = {}
        for benchmark, (db, _, validation_split, _) in indexed.items():
            print(f"  {benchmark} validation split...", flush=True)
            validation_reports[benchmark] = evaluate_config(
                db,
                validation_split,
                health_config=config,
                k_values=k_values,
                candidate_limit=candidate_limit,
                edge_threshold=edge_threshold,
                calibration_sample=calibration_sample,
            )
        validated.append(
            {
                **candidate,
                "validation_score": objective_score(
                    validation_reports,
                    k_values=k_values,
                ),
                "validation": validation_reports,
            }
        )

    validated.sort(
        key=lambda item: (item["validation_score"], item["score"]),
        reverse=True,
    )
    winner = validated[0]
    winner_config = GraphHealthConfig(**winner["config"])
    heldout = {}
    hybrid = {}
    for benchmark, (db, _, _, test_split) in indexed.items():
        print(f"Evaluating held-out {benchmark}...", flush=True)
        heldout[benchmark] = evaluate_config(
            db,
            test_split,
            health_config=winner_config,
            k_values=k_values,
            candidate_limit=candidate_limit,
            edge_threshold=edge_threshold,
            calibration_sample=calibration_sample,
        )
        hybrid[benchmark] = evaluate_hybrid(db, test_split, k_values=k_values)
        db.reset()

    return {
        "protocol": {
            "train_cases": train_cases,
            "validation_cases": validation_cases,
            "test_cases": test_cases,
            "validation_finalists": validation_finalists,
            "benchmarks": benchmarks,
            "k_values": k_values,
            "candidate_limit": candidate_limit,
            "edge_threshold": edge_threshold,
            "calibration_sample": calibration_sample,
            "note": (
                "Graph-health settings are screened on train cases, selected "
                "on validation cases, frozen, and evaluated on held-out cases. "
                "No query-time labels are used."
            ),
        },
        "winner": winner,
        "candidates": trained,
        "validated": validated,
        "heldout": {
            "hybrid": hybrid,
            "noetic_auto": heldout,
        },
    }


def main() -> None:
    """Run the graph-health tuning CLI.

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
    parser.add_argument("--train-cases", type=int, default=100)
    parser.add_argument("--validation-cases", type=int, default=100)
    parser.add_argument("--test-cases", type=int, default=100)
    parser.add_argument("--validation-finalists", type=int, default=8)
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--calibration-sample", type=int, default=500)
    parser.add_argument("--ks", type=parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    report = tune_health_config(
        benchmarks=args.benchmarks,
        train_cases=args.train_cases,
        validation_cases=args.validation_cases,
        test_cases=args.test_cases,
        validation_finalists=args.validation_finalists,
        k_values=args.ks,
        candidate_limit=args.candidate_limit,
        edge_threshold=args.edge_threshold,
        calibration_sample=args.calibration_sample,
    )

    print("=== GRAPH-HEALTH CONFIG TRAINING ===")
    print(f"winner: {report['winner']['name']}")
    print(f"train score: {report['winner']['score']:.3f}")
    print(f"validation score: {report['winner']['validation_score']:.3f}")
    for variant, reports in report["heldout"].items():
        print(f"\n=== HELD-OUT {variant.upper()} ===")
        for benchmark, result in reports.items():
            metrics = result["metrics"] if variant == "noetic_auto" else result
            print(f"\n{benchmark}")
            print_ranking_table({variant: metrics}, args.ks)

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
