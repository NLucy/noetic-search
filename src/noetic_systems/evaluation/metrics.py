"""Standard ranking metrics for retrieval evaluation.

This module contains the small information-retrieval metrics used by benchmark
CLIs. Precision answers "how clean are the returned results?" Recall answers
"how much of the known relevant evidence was recovered?" Hit rate answers
"did at least one relevant item appear?" MRR answers "how early did the first
relevant item appear?"

Key variables:
    `ranked_ids`: Document ids returned by a retrieval method in rank order.
    `target_ids`: Gold relevant document ids for the evaluated query.
    `k`: Rank cutoff. Metrics only inspect the first `k` returned ids.
    `precision`: Relevant documents in the first `k`, divided by `k`.
    `recall`: Relevant documents in the first `k`, divided by all known relevant
        documents for that query.
    `hit`: Binary indicator that at least one target appeared in the first `k`.
    `mrr`: Reciprocal rank of the first target in the first `k`.
"""

from __future__ import annotations

import argparse


def parse_k_values(value: str) -> list[int]:
    """Parse comma-separated rank cutoffs.

    Args:
        value: Comma-separated positive integers.

    Returns:
        Sorted unique rank cutoffs.
    """
    values = sorted({int(part.strip()) for part in value.split(",") if part.strip()})
    if not values or any(k <= 0 for k in values):
        raise argparse.ArgumentTypeError("--ks must contain positive integers")
    return values


def ranking_metrics(
    ranked_ids: list[str] | tuple[str, ...],
    target_ids: set[str],
    k: int,
) -> dict[str, float]:
    """Calculate precision, recall, hit rate, and MRR at one cutoff.

    Args:
        ranked_ids: Retrieved document ids in descending rank order.
        target_ids: Relevant document ids for the case.
        k: Rank cutoff.

    Returns:
        Metric mapping containing `precision`, `recall`, `hit`, and `mrr`.
    """
    top_ids = list(ranked_ids[:k])
    if not target_ids:
        return {"precision": 0.0, "recall": 0.0, "hit": 0.0, "mrr": 0.0}

    hits = sum(1 for doc_id in top_ids if doc_id in target_ids)
    reciprocal_rank = 0.0
    for rank, doc_id in enumerate(top_ids, 1):
        if doc_id in target_ids:
            reciprocal_rank = 1.0 / rank
            break

    return {
        "precision": hits / k,
        "recall": hits / len(target_ids),
        "hit": 1.0 if hits else 0.0,
        "mrr": reciprocal_rank,
    }


def empty_metric_totals(k_values: list[int]) -> dict[int, dict[str, float]]:
    """Create zeroed metric totals for each cutoff.

    Args:
        k_values: Rank cutoffs to track.

    Returns:
        Nested metric totals keyed by cutoff.
    """
    return {
        k: {"precision": 0.0, "recall": 0.0, "hit": 0.0, "mrr": 0.0}
        for k in k_values
    }


def add_metric_totals(
    totals: dict[int, dict[str, float]],
    ranked_ids: list[str] | tuple[str, ...],
    target_ids: set[str],
) -> None:
    """Accumulate ranking metrics for one case.

    Args:
        totals: Mutable metric totals keyed by cutoff.
        ranked_ids: Retrieved document ids in descending rank order.
        target_ids: Relevant document ids for the case.

    Returns:
        None.
    """
    for k in totals:
        metrics = ranking_metrics(ranked_ids, target_ids, k)
        for name, value in metrics.items():
            totals[k][name] += value


def average_metric_totals(
    totals: dict[int, dict[str, float]],
    count: int,
) -> dict[str, dict[str, float]]:
    """Average metric totals across cases.

    Args:
        totals: Metric totals keyed by cutoff.
        count: Number of evaluated cases.

    Returns:
        Metrics keyed as `@k`, then metric name.
    """
    denominator = count or 1
    return {
        f"@{k}": {
            name: value / denominator
            for name, value in metrics.items()
        }
        for k, metrics in totals.items()
    }
