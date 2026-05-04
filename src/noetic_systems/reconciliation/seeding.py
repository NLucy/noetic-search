"""Retrieval-energy seeding for the candidate field.

Seeding turns the hybrid retrieval ranking into the initial energy distribution
used by diffusion. Higher-ranked candidates receive more starting energy, but
lower-ranked candidates still enter the process. This preserves the useful work
done by lexical and semantic retrieval without treating raw top-k rank as the
final answer.

The seed is normalized to sum to 1.0 so diffusion operates on comparable energy
distributions across queries and candidate counts. Later stages can then ask how
that initial retrieval confidence settles inside the evidence graph.
"""

from __future__ import annotations

from noetic_systems.search.semantic import SearchResult


def seed_energy(results: list[SearchResult]) -> dict[str, float]:
    """Initialize graph energy from hybrid scores and ranks.

    Args:
        results: Ranked candidate search results.

    Returns:
        Normalized energy distribution by document id.
    """
    energy = {}
    for rank, result in enumerate(results):
        # Rank decay keeps top retrieval hits influential without making them final.
        energy[result.id] = result.score / (rank + 1)
    total = sum(energy.values())
    if total > 0:
        # Diffusion expects a comparable distribution regardless of candidate count.
        energy = {doc_id: value / total for doc_id, value in energy.items()}
    return energy
