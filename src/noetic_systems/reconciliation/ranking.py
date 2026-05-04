"""Representative chunk ranking inside the winning basin.

Basin selection chooses the strongest evidence region. Ranking chooses which
members of that region should be returned to the caller or LLM. Those are
different decisions: a basin can be correct while some of its members are
generic, repetitive, or less useful than others.

The default ranking favors specificity, an IDF-like signal computed within the
candidate field, with diffused energy as a smaller tie-in. The optional purifier
mode also considers query affinity, graph support, query echo, and hub pressure.
The purpose is to return compact, information-dense representatives of the
winning basin rather than echoing the original hybrid rank.
"""

from __future__ import annotations

from noetic_systems.reconciliation.models import ReturnRanker


def rank_basin_documents(
    doc_ids: list[str],
    energy: dict[str, float],
    specificity: dict[str, float],
    query_score: dict[str, float],
    support: dict[str, float],
    echo: dict[str, float],
    return_ranker: ReturnRanker,
) -> list[str]:
    """Rank basin members for return with a compact purification pass.

    Args:
        doc_ids: Basin document ids.
        energy: Basin-local energy by document id.
        specificity: Specificity score by document id.
        query_score: Hybrid query score by document id.
        support: Graph support by document id.
        echo: Query-echo score by document id.
        return_ranker: Ranking strategy.

    Returns:
        Document ids sorted for final return.
    """
    max_energy = max((energy.get(doc_id, 0.0) for doc_id in doc_ids), default=0.0)
    max_specificity = max(
        (specificity.get(doc_id, 0.0) for doc_id in doc_ids),
        default=0.0,
    )
    max_query = max((query_score.get(doc_id, 0.0) for doc_id in doc_ids), default=0.0)
    max_support = max((support.get(doc_id, 0.0) for doc_id in doc_ids), default=0.0)

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
        query_affinity = (
            query_score.get(doc_id, 0.0) / max_query
            if max_query > 0
            else 0.0
        )
        support_score = (
            support.get(doc_id, 0.0) / max_support
            if max_support > 0
            else 0.0
        )
        echo_penalty = echo.get(doc_id, 0.0)
        hub_penalty = max(0.0, support_score - 0.65)
        if return_ranker == "purifier":
            # Purifier mode is stricter about query echo and graph hubs.
            rank_score = (
                0.38 * specificity_score
                + 0.24 * query_affinity
                + 0.18 * energy_score
                + 0.12 * support_score
                - 0.20 * echo_penalty
                - 0.10 * hub_penalty
            )
        else:
            # Default mode favors information density after the basin is chosen.
            rank_score = 0.10 * energy_score + 0.90 * specificity_score
        return (
            rank_score,
            energy.get(doc_id, 0.0),
        )

    return sorted(doc_ids, key=score, reverse=True)
