"""Representative chunk ranking inside the winning basin.

Basin selection chooses the strongest evidence region. Ranking chooses which
members of that region should be returned to the caller or LLM. Those are
different decisions: a basin can be correct while some of its members are
generic, repetitive, or less useful than others.

The default ranking favors specificity, an IDF-like signal computed within the
candidate field, with diffused energy as a smaller tie-in. The purpose is to
return compact, information-dense representatives of the winning basin rather
than echoing the original hybrid rank.

Key variables:
    `doc_ids`: Members of the already-selected winning basin.
    `energy`: Settled diffusion energy by document id. It is a supporting signal,
        not the main ranking signal.
    `specificity`: Local information-density score by document id.
    `max_energy` and `max_specificity`: Basin-local normalizers. These keep raw
        scales from dominating the final rank score.
    `rank_score`: Weighted ranking score. Specificity dominates; energy breaks
        ties toward better-supported chunks.
"""

from __future__ import annotations


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
