#!/usr/bin/env python
"""Summarize Noetic retrieval results across benchmark reports.

This script does not run retrieval. It reads machine-readable reports from the
external multi-hop suite and the clinical evidence benchmark, then emits one
compact cross-corpus summary. The goal is to separate formula discovery from
score interpretation: evaluators write raw metrics, this script shows what
those metrics imply across datasets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_K_VALUES = (5, 10)


def metric_at(
    metrics: dict[str, dict[str, dict[str, float]]],
    variant: str,
    k: int,
    metric: str,
) -> float:
    """Read one metric value from a benchmark table.

    Args:
        metrics: Metrics by variant and cutoff.
        variant: Variant name.
        k: Rank cutoff.
        metric: Metric name.

    Returns:
        Metric value, or `0.0` when absent.
    """
    return metrics.get(variant, {}).get(f"@{k}", {}).get(metric, 0.0)


def best_variant_for_metric(
    metrics: dict[str, dict[str, dict[str, float]]],
    *,
    k: int,
    metric: str,
    exclude: set[str] | None = None,
) -> tuple[str, float]:
    """Find the best variant for a metric at a cutoff.

    Args:
        metrics: Metrics by variant and cutoff.
        k: Rank cutoff.
        metric: Metric name.
        exclude: Variants to exclude from selection.

    Returns:
        Best variant name and value.
    """
    excluded = exclude or set()
    candidates = [
        (variant, metric_at(metrics, variant, k, metric))
        for variant in metrics
        if variant not in excluded
    ]
    if not candidates:
        return "", 0.0
    return max(candidates, key=lambda item: item[1])


def summarize_multihop_report(
    report: dict[str, Any],
    k_values: list[int],
) -> dict[str, Any]:
    """Summarize external multi-hop benchmark metrics.

    Args:
        report: Multi-hop report keyed by dataset name.
        k_values: Rank cutoffs to summarize.

    Returns:
        Cross-dataset summary.
    """
    datasets = {}
    aggregate = {
        f"recall_gain@{k}": []
        for k in k_values
    }
    aggregate.update(
        {
            f"auto_recall_gain@{k}": []
            for k in k_values
        }
    )

    for dataset, dataset_report in report.items():
        metrics = dataset_report["metrics"]
        rows = {}
        for k in k_values:
            hybrid = metric_at(metrics, "hybrid", k, "recall")
            best_variant, best_recall = best_variant_for_metric(
                metrics,
                k=k,
                metric="recall",
                exclude={"hybrid"},
            )
            auto_recall = metric_at(metrics, "auto", k, "recall")
            rows[f"@{k}"] = {
                "hybrid_recall": hybrid,
                "best_variant": best_variant,
                "best_recall": best_recall,
                "best_recall_gain": best_recall - hybrid,
                "auto_recall": auto_recall,
                "auto_recall_gain": auto_recall - hybrid,
            }
            aggregate[f"recall_gain@{k}"].append(best_recall - hybrid)
            aggregate[f"auto_recall_gain@{k}"].append(auto_recall - hybrid)
        datasets[dataset] = rows

    return {
        "datasets": datasets,
        "aggregate": average_lists(aggregate),
    }


def summarize_clinical_report(
    report: dict[str, Any],
    k_values: list[int],
) -> dict[str, Any]:
    """Summarize clinical evidence benchmark metrics.

    Args:
        report: Clinical benchmark report.
        k_values: Rank cutoffs to summarize.

    Returns:
        Clinical summary.
    """
    clinical = report["clinical"]
    utility = report.get("clinical_utility", {})
    rows = {}
    for k in k_values:
        hybrid_recall = metric_at(clinical, "hybrid", k, "critical_recall")
        best_variant, best_recall = best_variant_for_metric(
            clinical,
            k=k,
            metric="critical_recall",
            exclude={"hybrid"},
        )
        rows[f"@{k}"] = {
            "hybrid_critical_recall": hybrid_recall,
            "hybrid_decoy_rate": metric_at(clinical, "hybrid", k, "decoy_rate"),
            "best_variant": best_variant,
            "best_critical_recall": best_recall,
            "best_critical_recall_gain": best_recall - hybrid_recall,
            "best_decoy_rate": metric_at(clinical, best_variant, k, "decoy_rate"),
            "best_utility_by_lambda": best_utility_by_lambda(utility, k),
        }
    return {
        "dataset": report.get("dataset", "clinical"),
        "cases": report.get("cases", 0),
        "documents": report.get("documents", 0),
        "rows": rows,
    }


def best_utility_by_lambda(
    utility: dict[str, dict[str, dict[str, float]]],
    k: int,
) -> dict[str, dict[str, float | str]]:
    """Find the best utility variant for each lambda.

    Args:
        utility: Clinical utility table.
        k: Rank cutoff.

    Returns:
        Best utility rows keyed by lambda.
    """
    result = {}
    for penalty, variants in utility.items():
        best_variant = ""
        best_value = float("-inf")
        for variant, metrics_by_k in variants.items():
            value = metrics_by_k.get(f"@{k}", float("-inf"))
            if value > best_value:
                best_variant = variant
                best_value = value
        result[penalty] = {
            "variant": best_variant,
            "utility": best_value if best_value != float("-inf") else 0.0,
        }
    return result


def average_lists(values: dict[str, list[float]]) -> dict[str, float]:
    """Average numeric lists.

    Args:
        values: Numeric values by metric name.

    Returns:
        Mean values by metric name.
    """
    return {
        key: sum(items) / len(items) if items else 0.0
        for key, items in values.items()
    }


def print_summary(summary: dict[str, Any], k_values: list[int]) -> None:
    """Print a human-readable suite summary.

    Args:
        summary: Suite summary.
        k_values: Rank cutoffs included in the summary.

    Returns:
        None.
    """
    print("=== MULTI-HOP SUMMARY ===")
    for dataset, rows in summary["multihop"]["datasets"].items():
        for k in k_values:
            row = rows[f"@{k}"]
            print(
                f"{dataset:16} @{k:<2} "
                f"hybrid={row['hybrid_recall']:.3f} "
                f"best={row['best_variant']}:{row['best_recall']:.3f} "
                f"gain={row['best_recall_gain']:.3f} "
                f"auto={row['auto_recall']:.3f} "
                f"auto_gain={row['auto_recall_gain']:.3f}"
            )

    print()
    print("=== CLINICAL SUMMARY ===")
    clinical = summary["clinical"]
    for k in k_values:
        row = clinical["rows"][f"@{k}"]
        print(
            f"clinical         @{k:<2} "
            f"hybrid_critical={row['hybrid_critical_recall']:.3f} "
            f"best={row['best_variant']}:{row['best_critical_recall']:.3f} "
            f"gain={row['best_critical_recall_gain']:.3f} "
            f"decoy_rate={row['best_decoy_rate']:.3f}"
        )

    print()
    print("=== DERIVATION NOTES ===")
    for note in summary["derivation_notes"]:
        print(f"- {note}")


def derivation_notes(summary: dict[str, Any]) -> list[str]:
    """Build concise conclusions from cross-corpus metrics.

    Args:
        summary: Suite summary without notes.

    Returns:
        Methodology notes.
    """
    multihop = summary["multihop"]
    clinical = summary["clinical"]
    return [
        (
            "Across external multi-hop corpora, graph reconciliation should be "
            "judged first by support recall at compact k, not by downstream "
            "answer truth."
        ),
        (
            "Corpus-native calibration is valid only when weights are selected "
            "from graph health before question labels are evaluated."
        ),
        (
            "Useful graph formulas preserve enough semantic/lexical agreement "
            "for expansion, while controlling density, connected-component "
            "structure, Freeman degree centralization, duplicate pressure, and "
            "semantic-only bridge risk."
        ),
        (
            "Clinical decoy_rate is a domain risk annotation. It should be "
            "reported beside critical recall rather than replacing standard "
            "retrieval metrics."
        ),
        (
            "Current aggregate multi-hop best recall gains are "
            + ", ".join(
                f"{key}={value:.3f}"
                for key, value in multihop["aggregate"].items()
                if key.startswith("recall_gain@")
            )
            + "."
        ),
        (
            f"Clinical best critical recall gain at @5 is "
            f"{clinical['rows']['@5']['best_critical_recall_gain']:.3f} "
            f"with decoy_rate {clinical['rows']['@5']['best_decoy_rate']:.3f}."
        ),
    ]


def main() -> None:
    """Run the benchmark suite summarizer.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--multihop-report",
        type=Path,
        default=Path("reports/multihop_objectives_grounded_auto_300.json"),
    )
    parser.add_argument(
        "--clinical-report",
        type=Path,
        default=Path("reports/clinical_evidence_frontier.json"),
    )
    parser.add_argument("--ks", default="5,10")
    parser.add_argument("--json-report", type=Path, default=None)
    args = parser.parse_args()

    k_values = [
        int(part.strip())
        for part in args.ks.split(",")
        if part.strip()
    ]
    multihop_report = json.loads(args.multihop_report.read_text())
    clinical_report = json.loads(args.clinical_report.read_text())["metrics"]
    summary = {
        "multihop": summarize_multihop_report(multihop_report, k_values),
        "clinical": summarize_clinical_report(clinical_report, k_values),
    }
    summary["derivation_notes"] = derivation_notes(summary)

    print_summary(summary, k_values)
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
