"""Compact evidence ranking.

The benchmarked production ranker is linked-evidence ranking. It preserves the
strongest first-stage hybrid anchors, then promotes graph candidates connected
to those anchors. This is the deterministic step that turns broad retrieval into
a compact multi-hop evidence set.

Basin-local ranking remains available for `return_policy="basin"` and research
diagnostics. That alternate ranking favors specificity, an IDF-like signal
computed within the candidate field, with diffused energy as a smaller tie-in.

Key variables:
    `graph_candidates`: Candidates admitted to the local graph.
    `anchors`: Strongest early hybrid candidates preserved by linked ranking.
    `anchor_affinity`: Strongest graph edge from a candidate to an anchor.
    `support`: Weighted graph degree used by linked ranking.
    `doc_ids`: Members of the already-selected winning basin.
    `energy`: Settled diffusion energy by document id. It is a supporting signal,
        not the main ranking signal.
    `specificity`: Local information-density score by document id.
    `max_energy` and `max_specificity`: Basin-local normalizers. These keep raw
        scales from dominating the final rank score.
    `rank_score`: Weighted ranking score. Specificity dominates; energy breaks
        ties toward better-supported chunks.
    `linked_evidence`: Return policy that preserves early hybrid anchors and
        promotes candidates connected to those anchors in the graph.
"""

from __future__ import annotations

from noetic_systems.search.semantic import SearchResult


def rank_basin_documents(
    doc_ids: list[str],
    energy: dict[str, float],
    specificity: dict[str, float],
) -> list[str]:
    """Rank basin members for return.

    Args:
        doc_ids: Basin document ids.
        energy: Basin-local energy by document id.
        specificity: Specificity score by document id.

    Returns:
        Document ids sorted for final return.
    """
    max_energy = max((energy.get(doc_id, 0.0) for doc_id in doc_ids), default=0.0)
    max_specificity = max(
        (specificity.get(doc_id, 0.0) for doc_id in doc_ids),
        default=0.0,
    )

    # Ranking is intentionally basin-local. Once the basin is chosen, the job is
    # to pick representatives of that basin, not to rerun global retrieval.
    def score(doc_id: str) -> tuple[float, float]:
        """Score one basin document for intra-basin ranking.

        Args:
            doc_id: Document id to score.

        Returns:
            Tuple used for descending sort: rank score and raw energy.
        """
        # Normalize local features so no single raw scale dominates ranking.
        energy_score = (
            energy.get(doc_id, 0.0) / max_energy
            if max_energy > 0
            else 0.0
        )
        specificity_score = (
            specificity.get(doc_id, 0.0) / max_specificity
            if max_specificity > 0
            else 0.0
        )
        # Favor information density after the basin is chosen; energy breaks ties.
        rank_score = 0.10 * energy_score + 0.90 * specificity_score
        return (
            rank_score,
            energy.get(doc_id, 0.0),
        )

    return sorted(doc_ids, key=score, reverse=True)


def rank_linked_evidence(
    graph_candidates: list[SearchResult],
    graph: dict[str, dict[str, float]],
    *,
    anchor_count: int = 4,
    query_weight: float = 0.50,
    link_weight: float = 0.35,
    support_weight: float = 0.15,
    anchor_bonus: float = 2.0,
) -> list[str]:
    """Rank candidates by preserving hybrid anchors and promoting linked evidence.

    Args:
        graph_candidates: Candidates admitted to the local evidence graph.
        graph: Weighted adjacency mapping over graph candidates.
        anchor_count: Number of top hybrid candidates kept as anchors.
        query_weight: Weight for original hybrid score after the anchors.
        link_weight: Weight for edge strength to the anchors.
        support_weight: Weight for weighted graph degree.
        anchor_bonus: Fixed score boost that keeps anchors at the top.

    Returns:
        Ranked document ids for compact linked-evidence return.
    """
    if not graph_candidates:
        return []

    candidate_ids = [candidate.id for candidate in graph_candidates]
    anchors = candidate_ids[:anchor_count]
    query_score = normalize_feature(
        {candidate.id: candidate.score for candidate in graph_candidates}
    )
    support = normalize_feature(
        {
            doc_id: sum(neighbors.values())
            for doc_id, neighbors in graph.items()
        }
    )
    anchor_affinity = normalize_feature(
        {
            doc_id: max(
                (graph.get(doc_id, {}).get(anchor, 0.0) for anchor in anchors),
                default=0.0,
            )
            for doc_id in candidate_ids
        }
    )
    original_rank = {
        candidate.id: index
        for index, candidate in enumerate(graph_candidates)
    }

    def score(doc_id: str) -> tuple[float, int]:
        """Score one candidate for linked-evidence ranking.

        Args:
            doc_id: Candidate document id.

        Returns:
            Descending score and ascending original rank.
        """
        if doc_id in anchors:
            return anchor_bonus - (original_rank[doc_id] * 0.001), -original_rank[doc_id]
        value = (
            query_weight * query_score.get(doc_id, 0.0)
            + link_weight * anchor_affinity.get(doc_id, 0.0)
            + support_weight * support.get(doc_id, 0.0)
        )
        return value, -original_rank.get(doc_id, 10**9)

    return sorted(candidate_ids, key=score, reverse=True)


def normalize_feature(values: dict[str, float]) -> dict[str, float]:
    """Normalize feature values to the `[0, 1]` interval.

    Args:
        values: Raw feature values by document id.

    Returns:
        Min-max normalized values.
    """
    if not values:
        return {}
    minimum = min(values.values())
    maximum = max(values.values())
    if maximum == minimum:
        return {doc_id: 1.0 for doc_id in values}
    return {
        doc_id: (value - minimum) / (maximum - minimum)
        for doc_id, value in values.items()
    }
