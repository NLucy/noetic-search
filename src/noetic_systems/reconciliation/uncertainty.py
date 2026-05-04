"""Structural uncertainty for reconciled evidence fields.

Uncertainty describes whether the local evidence field produced a clear winner.
It is not a probability that the answer is true. It is a compact signal about
graph structure: whether another basin competes strongly with the winner,
whether diffused energy stayed scattered, and whether the graph partition has
clear modular structure.

This matters because a retrieval result can be useful and still unsettled. When
uncertainty is high, callers can expose competing basins, ask the LLM to answer
with caveats, or trigger a broader retrieval pass.
"""

from __future__ import annotations

from noetic_systems.reconciliation.models import Basin


def calculate_uncertainty(
    basins: list[Basin],
    modularity: float,
    dispersion: float,
) -> float:
    """Calculate structural uncertainty for a reconciliation result.

    Args:
        basins: Scored basins sorted by descending score.
        modularity: Graph modularity score.
        dispersion: Energy dispersion score.

    Returns:
        Uncertainty score in the `[0, 1]` interval.
    """
    if not basins:
        return 1.0
    competition = 0.0
    if len(basins) > 1 and basins[0].score > 0:
        # A close runner-up means the field did not produce a decisive region.
        competition = basins[1].score / basins[0].score
    modularity_uncertainty = max(0.0, 1.0 - modularity)
    # The weights express a product judgment: basin competition matters most,
    # but weak graph structure and scattered energy should also raise caution.
    uncertainty = (
        0.45 * competition
        + 0.30 * modularity_uncertainty
        + 0.25 * dispersion
    )
    return float(max(0.0, min(1.0, uncertainty)))
