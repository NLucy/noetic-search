"""Graph and basin metrics used by reconciliation.

Metrics translate graph structure into simple, inspectable signals: support,
specificity, cohesion, dispersion, and modularity. We use these measures to
prefer basins that are coherent and specific without being merely repetitive.

The metrics are deliberately modest. They are not trying to decide truth; they
describe the shape of the retrieved evidence. Support measures how connected a
chunk is, specificity rewards terms that distinguish a chunk from the rest of
the candidate set, cohesion measures internal edge strength, and duplicate
penalty reduces regions dominated by repeated material.

Structural uncertainty is calculated in `noetic_systems.reconciliation.basins`.
This module provides the component measurements that uncertainty and basin
scoring depend on.

Key variables:
    `support`: Sum of incident edge weights for a document. High support means a
        chunk is well connected inside the local graph.
    `specificity`: Local IDF-like score. It rewards words that distinguish a
        chunk from the rest of the retrieved candidate field.
    `document_frequency`: Count of candidate chunks containing each token.
    `duplicate_penalty`: Penalty derived from very high internal edge weights.
    `cohesion`: Mean internal edge weight inside a basin.
    `modularity`: Quality of the community assignment compared with a
        degree-preserving null model.
    `dispersion`: Spread of the final energy distribution. High dispersion means
        energy did not settle cleanly.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

from noetic_systems.search.semantic import SearchResult


def document_support(graph: dict[str, dict[str, float]]) -> dict[str, float]:
    """Measure local graph support for each candidate.

    Args:
        graph: Weighted adjacency mapping.

    Returns:
        Sum of incident edge weights by document id.
    """
    # Support is simply weighted degree. It is structural, not a metadata score.
    return {
        doc_id: float(sum(neighbors.values()))
        for doc_id, neighbors in graph.items()
    }


def document_specificity(results: list[SearchResult]) -> dict[str, float]:
    """Estimate candidate information density without labels.

    Args:
        results: Candidate search results.

    Returns:
        IDF-like specificity score by document id.
    """
    token_sets = {
        result.id: set(tokens(result.text))
        for result in results
    }
    document_frequency: dict[str, int] = defaultdict(int)
    for result_tokens in token_sets.values():
        for token in result_tokens:
            document_frequency[token] += 1

    # Specificity is local to the candidate field; it rewards distinguishing terms
    # among the retrieved candidates rather than global corpus rarity.
    total = len(results)
    specificity: dict[str, float] = {}
    for result in results:
        result_tokens = token_sets[result.id]
        if not result_tokens:
            specificity[result.id] = 0.0
            continue
        specificity[result.id] = float(
            sum(
                math.log((1 + total) / (1 + document_frequency[token]))
                for token in result_tokens
            ) / len(result_tokens)
        )
    return specificity


def tokens(text: str) -> list[str]:
    """Tokenize text for internal specificity metrics.

    Args:
        text: Text to tokenize.

    Returns:
        Lowercase alphanumeric tokens of at least three characters.
    """
    return re.findall(r"[a-z0-9]{3,}", text.lower())


def duplicate_penalty(
    doc_ids: list[str],
    graph: dict[str, dict[str, float]],
) -> float:
    """Calculate near-duplicate penalty for a basin.

    Args:
        doc_ids: Document ids in a basin.
        graph: Weighted adjacency mapping.

    Returns:
        Duplicate penalty capped at `0.35`.
    """
    if len(doc_ids) < 2:
        return 0.0
    near_duplicate_pairs = 0
    possible_edges = 0
    # Near-duplicate relationships are encoded as very high graph weights.
    for i, left in enumerate(doc_ids):
        for right in doc_ids[i + 1:]:
            possible_edges += 1
            if graph.get(left, {}).get(right, 0.0) >= 0.9:
                near_duplicate_pairs += 1
    if possible_edges == 0:
        return 0.0
    return min(0.35, 0.45 * (near_duplicate_pairs / possible_edges))


def calculate_cohesion(
    doc_ids: list[str],
    graph: dict[str, dict[str, float]],
) -> float:
    """Calculate mean internal edge strength for a basin.

    Args:
        doc_ids: Document ids in a basin.
        graph: Weighted adjacency mapping.

    Returns:
        Mean internal edge weight, or `0.0` when no internal edges exist.
    """
    if len(doc_ids) < 2:
        return 0.0
    total_weight = 0.0
    count = 0
    for i, left in enumerate(doc_ids):
        for right in doc_ids[i + 1:]:
            if right in graph.get(left, {}):
                total_weight += graph[left][right]
                count += 1
    return total_weight / count if count else 0.0


def calculate_modularity(
    graph: dict[str, dict[str, float]],
    communities: dict[str, int],
) -> float:
    """Calculate graph modularity for community assignments.

    Args:
        graph: Weighted adjacency mapping.
        communities: Community assignment by document id.

    Returns:
        Modularity score.
    """
    if not graph or not communities:
        return 0.0
    total_weight = sum(
        sum(neighbors.values())
        for neighbors in graph.values()
    ) / 2.0
    if total_weight == 0:
        return 0.0

    modularity = 0.0
    # Standard modularity: observed internal edge weight minus expected internal
    # weight under a degree-preserving null model. This says whether the detected
    # basins are better than what node degrees alone would imply.
    for node1, comm1 in communities.items():
        for node2, comm2 in communities.items():
            if comm1 != comm2:
                continue
            weight = graph.get(node1, {}).get(node2, 0.0)
            deg1 = sum(graph.get(node1, {}).values())
            deg2 = sum(graph.get(node2, {}).values())
            expected = (deg1 * deg2) / (2.0 * total_weight)
            modularity += weight - expected
    return float(modularity / (2.0 * total_weight))


def calculate_dispersion(energy: dict[str, float]) -> float:
    """Calculate dispersion of the final energy distribution.

    Args:
        energy: Energy distribution by document id.

    Returns:
        Dispersion score in the `[0, 1]` interval.
    """
    if not energy:
        return 1.0
    values = list(energy.values())
    mean = sum(values) / len(values)
    # Low variance means energy remained broadly spread across the field.
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return float(min(1.0, math.sqrt(variance)))
