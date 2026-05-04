"""Discrete time-step graph diffusion.

Diffusion starts with seeded retrieval confidence and lets that confidence move
across evidence edges in discrete time steps. A node keeps some energy and sends
the rest to related neighbors in proportion to edge weight. We use this because
supporting evidence often appears across multiple related chunks: diffusion lets
a cluster of mutually reinforcing candidates become visible before the final LLM
prompt is constructed.

Concretely, diffusion runs over discrete time steps. At time `t`, each node has
some current energy. One update computes time `t + 1`: the node keeps a retained
part of its energy, and the movable part is distributed to neighboring nodes
across evidence edges. If a node has two neighbors and one edge is much stronger
than the other, more of the movable energy follows the stronger edge. After
several time steps, energy tends to concentrate in parts of the graph where
retrieval confidence and graph support reinforce each other.

Diffusion and basin detection are related but distinct. The current pipeline
detects basins from graph structure using spectral partitioning, then uses
diffusion to measure how the seeded retrieval signal settles inside those
basins. In other words, diffusion does not create the basin labels by itself. It
helps decide which detected basin is strongest and which members of that basin
deserve to be returned.

This is a limited graph computation, not open-ended reasoning. It does not
generate claims or infer facts beyond the retrieved chunks. Its role is to
estimate which candidates are supported by the local evidence structure before
the LLM sees the final context.
"""

from __future__ import annotations


def diffuse(
    energy: dict[str, float],
    graph: dict[str, dict[str, float]],
    damping: float,
) -> dict[str, float]:
    """Diffuse seeded energy through graph edges.

    Args:
        energy: Current energy distribution by document id.
        graph: Weighted adjacency mapping.
        damping: Fraction of energy sent through edges.

    Returns:
        Normalized next-step energy distribution.
    """
    # Retained energy prevents every update from fully overwriting local evidence.
    next_energy = {
        doc_id: (1 - damping) * value
        for doc_id, value in energy.items()
    }
    for doc_id, neighbors in graph.items():
        if not neighbors:
            # Isolated nodes cannot send support elsewhere, so their movable energy
            # stays local instead of disappearing from the distribution.
            next_energy[doc_id] += damping * energy[doc_id]
            continue
        total_weight = sum(neighbors.values())
        for neighbor_id, weight in neighbors.items():
            # Edge weights define the transition proportions for this time step.
            next_energy[neighbor_id] += (
                damping * energy[doc_id] * (weight / total_weight)
            )
    total = sum(next_energy.values())
    if total > 0:
        # Renormalization keeps repeated time steps numerically comparable.
        next_energy = {
            doc_id: value / total
            for doc_id, value in next_energy.items()
        }
    return next_energy
