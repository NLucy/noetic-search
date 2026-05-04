"""Graph and basin metrics used by reconciliation.

Metrics translate graph structure into simple, inspectable signals: support,
specificity, query echo, cohesion, dispersion, and modularity. We use these
measures to prefer basins that are coherent and specific without being merely
repetitive.

The metrics are deliberately modest. They are not trying to decide truth; they
describe the shape of the retrieved evidence. Support measures how connected a
chunk is, specificity rewards terms that distinguish a chunk from the rest of
the candidate set, cohesion measures internal edge strength, and duplicate
penalty reduces regions dominated by repeated material.

Structural uncertainty is calculated in
`noetic_systems.reconciliation.uncertainty`. This module provides the component
measurements that uncertainty and basin scoring depend on.
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
    return {
        doc_id: float(sum(neighbors.values()))
        for doc_id, neighbors in graph.items()
    }


def query_echo(
    query: str,
    results: list[SearchResult],
) -> dict[str, float]:
    """Estimate how much candidates echo the query wording.

    Args:
        query: Query text.
        results: Candidate search results.

    Returns:
        Query-echo score by document id.
    """
    query_tokens = set(tokens(query))
    if not query_tokens:
        return {result.id: 0.0 for result in results}

    echo: dict[str, float] = {}
    for result in results:
        result_tokens = set(tokens(result.text))
        if not result_tokens:
            echo[result.id] = 0.0
            continue
        # Query echo is useful but risky: strong echo can be boilerplate, so later
        # ranking may penalize it rather than treat it as pure relevance.
        query_overlap = len(result_tokens & query_tokens) / len(query_tokens)
        text_overlap = len(result_tokens & query_tokens) / len(result_tokens)
        echo[result.id] = float(0.65 * query_overlap + 0.35 * text_overlap)
    return echo


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
    """Tokenize text for internal specificity and echo metrics.

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
    # weight under a degree-preserving null model.
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
