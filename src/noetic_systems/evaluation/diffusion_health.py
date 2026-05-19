"""Label-free diffusion diagnostics for graph objective studies.

These measurements ask whether a graph behaves sensibly when any node is
activated. They do not inspect benchmark labels or answer correctness. The goal
is to compare graph-weight objectives by dynamic behavior: does energy stay
local enough to be useful, reach connected neighbors, and avoid collapsing into
generic high-degree hubs?

Key variables:
    `seed_id`: Document id receiving all starting energy for one pulse.
    `energy`: Diffused energy distribution after fixed time steps.
    `local_retention`: Energy retained by the seed and its direct neighbors.
    `neighbor_transfer`: Energy received by direct neighbors, excluding the
        seed.
    `field_flooding`: Fraction of nodes receiving nontrivial energy.
    `spread_balance`: Score for landing in a useful middle band of spread.
    `retention_balance`: Score for retaining useful locality without trapping
        energy at the seed.
    `hub_absorption`: Energy captured by the highest-degree graph nodes.
    `flow_coherence`: Edge-weighted concentration of final energy.
"""

from __future__ import annotations

from dataclasses import dataclass

from noetic_systems.reconciliation.diffusion import diffuse


@dataclass(frozen=True)
class DiffusionHealth:
    """Aggregate diffusion behavior for one graph.

    Attributes:
        local_retention: Mean energy retained by the seed and direct neighbors.
        neighbor_transfer: Mean energy transferred from the seed to direct
            neighbors.
        field_flooding: Mean fraction of graph nodes receiving nontrivial energy.
        spread_balance: Score for enough, but not excessive, nontrivial spread.
        retention_balance: Score for local retention that is neither trapped nor
            over-diffused.
        hub_absorption: Mean energy captured by the highest-degree nodes.
        flow_coherence: Mean edge-weighted concentration of final energy.
        isolation_rate: Fraction of seed nodes with no graph neighbors.
        health_score: Bounded summary score. Higher is healthier.
    """

    local_retention: float
    neighbor_transfer: float
    field_flooding: float
    spread_balance: float
    retention_balance: float
    hub_absorption: float
    flow_coherence: float
    isolation_rate: float
    health_score: float


def diffusion_health(
    graph: dict[str, dict[str, float]],
    *,
    steps: int = 4,
    damping: float = 0.85,
    flood_threshold: float = 0.001,
    hub_fraction: float = 0.10,
    max_seeds: int | None = None,
) -> DiffusionHealth:
    """Measure all-node seeded diffusion behavior for a graph.

    Args:
        graph: Weighted adjacency mapping.
        steps: Number of diffusion time steps per seed pulse.
        damping: Fraction of energy moved across edges each time step.
        flood_threshold: Minimum node energy counted as nontrivial spread.
        hub_fraction: Fraction of highest-degree nodes treated as hubs.
        max_seeds: Optional cap on seed nodes for large graphs.

    Returns:
        Aggregate diffusion health metrics.
    """
    node_ids = list(graph)
    if not node_ids:
        return DiffusionHealth(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)

    seed_ids = node_ids[:max_seeds] if max_seeds is not None else node_ids
    hubs = hub_nodes(graph, hub_fraction)
    totals = {
        "local_retention": 0.0,
        "neighbor_transfer": 0.0,
        "field_flooding": 0.0,
        "hub_absorption": 0.0,
        "flow_coherence": 0.0,
        "isolation": 0.0,
    }

    for seed_id in seed_ids:
        neighbors = set(graph.get(seed_id, {}))
        if not neighbors:
            totals["isolation"] += 1.0

        energy = {doc_id: 0.0 for doc_id in node_ids}
        energy[seed_id] = 1.0
        for _ in range(steps):
            energy = diffuse(energy, graph, damping)

        local_nodes = neighbors | {seed_id}
        totals["local_retention"] += sum(energy.get(doc_id, 0.0) for doc_id in local_nodes)
        totals["neighbor_transfer"] += sum(energy.get(doc_id, 0.0) for doc_id in neighbors)
        totals["field_flooding"] += (
            sum(1 for value in energy.values() if value >= flood_threshold) / len(node_ids)
        )
        totals["hub_absorption"] += sum(energy.get(doc_id, 0.0) for doc_id in hubs)
        totals["flow_coherence"] += edge_weighted_energy(energy, graph)

    count = len(seed_ids) or 1
    local_retention = totals["local_retention"] / count
    neighbor_transfer = totals["neighbor_transfer"] / count
    field_flooding = totals["field_flooding"] / count
    hub_absorption = totals["hub_absorption"] / count
    flow_coherence = totals["flow_coherence"] / count
    isolation_rate = totals["isolation"] / count
    spread_balance = band_score(field_flooding, low=0.04, target=0.14, high=0.26)
    retention_balance = band_score(local_retention, low=0.45, target=0.64, high=0.78)
    health_score = diffusion_health_score(
        local_retention=local_retention,
        neighbor_transfer=neighbor_transfer,
        field_flooding=field_flooding,
        spread_balance=spread_balance,
        retention_balance=retention_balance,
        hub_absorption=hub_absorption,
        flow_coherence=flow_coherence,
        isolation_rate=isolation_rate,
    )

    return DiffusionHealth(
        local_retention=local_retention,
        neighbor_transfer=neighbor_transfer,
        field_flooding=field_flooding,
        spread_balance=spread_balance,
        retention_balance=retention_balance,
        hub_absorption=hub_absorption,
        flow_coherence=flow_coherence,
        isolation_rate=isolation_rate,
        health_score=health_score,
    )


def diffusion_health_score(
    *,
    local_retention: float,
    neighbor_transfer: float,
    field_flooding: float,
    spread_balance: float,
    retention_balance: float,
    hub_absorption: float,
    flow_coherence: float,
    isolation_rate: float,
) -> float:
    """Combine diffusion diagnostics into a bounded summary score.

    Args:
        local_retention: Energy retained by seed neighborhoods.
        neighbor_transfer: Energy transferred to direct neighbors.
        field_flooding: Fraction of graph receiving nontrivial energy.
        spread_balance: Middle-band score for nontrivial spread.
        retention_balance: Middle-band score for local retention.
        hub_absorption: Energy captured by high-degree nodes.
        flow_coherence: Edge-weighted final energy concentration.
        isolation_rate: Fraction of seed nodes with no neighbors.

    Returns:
        Health score in the `[0, 1]` interval.
    """
    hub_overload = max(0.0, hub_absorption - 0.35)
    raw_score = (
        0.55 * neighbor_transfer
        + 0.20 * flow_coherence
        + 0.17 * (1.0 - isolation_rate)
        + 0.05 * retention_balance
        + 0.03 * spread_balance
        - 0.05 * hub_overload
    )
    return max(0.0, min(1.0, raw_score))


def band_score(value: float, *, low: float, target: float, high: float) -> float:
    """Score whether a value lies in a preferred middle band.

    Args:
        value: Value to score.
        low: Lower unacceptable boundary.
        target: Preferred value.
        high: Upper unacceptable boundary.

    Returns:
        Triangular score in the `[0, 1]` interval.
    """
    if value <= low or value >= high:
        return 0.0
    if value == target:
        return 1.0
    if value < target:
        return (value - low) / (target - low)
    return (high - value) / (high - target)


def hub_nodes(
    graph: dict[str, dict[str, float]],
    hub_fraction: float,
) -> set[str]:
    """Return highest-degree nodes in a graph.

    Args:
        graph: Weighted adjacency mapping.
        hub_fraction: Fraction of nodes to mark as hubs.

    Returns:
        Set of hub document ids.
    """
    if not graph:
        return set()
    hub_count = max(1, round(len(graph) * hub_fraction))
    weighted_degrees = {
        doc_id: sum(neighbors.values())
        for doc_id, neighbors in graph.items()
    }
    ranked = sorted(weighted_degrees, key=weighted_degrees.get, reverse=True)
    return set(ranked[:hub_count])


def edge_weighted_energy(
    energy: dict[str, float],
    graph: dict[str, dict[str, float]],
) -> float:
    """Measure whether final energy lies on well-connected nodes.

    Args:
        energy: Final energy distribution.
        graph: Weighted adjacency mapping.

    Returns:
        Energy-weighted normalized degree score.
    """
    degrees = {
        doc_id: sum(neighbors.values())
        for doc_id, neighbors in graph.items()
    }
    max_degree = max(degrees.values(), default=0.0)
    if max_degree == 0:
        return 0.0
    return sum(
        energy.get(doc_id, 0.0) * (degree / max_degree)
        for doc_id, degree in degrees.items()
    )


def spearman_correlation(
    left: list[float],
    right: list[float],
) -> float:
    """Calculate Spearman rank correlation for two numeric lists.

    Args:
        left: First numeric sequence.
        right: Second numeric sequence.

    Returns:
        Spearman correlation, or `0.0` when undefined.
    """
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_ranks = ranks(left)
    right_ranks = ranks(right)
    return pearson_correlation(left_ranks, right_ranks)


def ranks(values: list[float]) -> list[float]:
    """Return average ranks for values, handling ties.

    Args:
        values: Numeric values.

    Returns:
        Rank values starting at 1.0.
    """
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    output = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        next_index = index + 1
        while next_index < len(indexed) and indexed[next_index][1] == indexed[index][1]:
            next_index += 1
        average_rank = (index + 1 + next_index) / 2
        for original_index, _value in indexed[index:next_index]:
            output[original_index] = average_rank
        index = next_index
    return output


def pearson_correlation(
    left: list[float],
    right: list[float],
) -> float:
    """Calculate Pearson correlation for two numeric lists.

    Args:
        left: First numeric sequence.
        right: Second numeric sequence.

    Returns:
        Pearson correlation, or `0.0` when undefined.
    """
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numerator = sum(
        (left_value - mean_left) * (right_value - mean_right)
        for left_value, right_value in zip(left, right)
    )
    left_variance = sum((value - mean_left) ** 2 for value in left)
    right_variance = sum((value - mean_right) ** 2 for value in right)
    denominator = (left_variance * right_variance) ** 0.5
    if denominator == 0:
        return 0.0
    return numerator / denominator
