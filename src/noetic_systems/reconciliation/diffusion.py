"""Retrieval-energy initialization and graph diffusion.

Diffusion starts by converting hybrid retrieval scores and ranks into an initial
energy distribution. Higher-ranked candidates receive more starting energy, but
lower-ranked candidates still enter the process. This preserves the useful work
done by lexical and semantic retrieval without treating raw top-k rank as the
final answer.

After initialization, diffusion lets retrieval confidence move across selected
evidence edges in discrete time steps. The same update can be used in two ways.
Whole-graph diffusion keeps every edge open and acts as a diagnostic: it shows
whether a basin absorbs energy from the surrounding field or leaks energy into
neighbors. Basin-constrained diffusion removes cross-basin edges before scoring,
so competing explanations do not feed one another. We use this because
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
basins. In other words, diffusion does not create the basin labels by itself.

Diffusion is also not the primary driver of the current external benchmark win.
The default linked-evidence return policy uses graph edges directly to preserve
strong hybrid anchors and promote connected support chunks. Diffusion remains in
the system because it powers basin scoring, uncertainty, trace visualization,
and the alternate basin-only return policy. That distinction matters: graph
construction and linked ranking are the measured retrieval improvement; diffusion
is the diagnostic and basin-scoring layer.

This is a limited graph computation, not open-ended reasoning. It does not
generate claims or infer facts beyond the retrieved chunks. Its role is to
estimate which candidates are supported by the local evidence structure before
the LLM sees the final context.

Key variables:
    `energy`: Current retrieval confidence by document id. It is normalized so
        the values sum to 1.0 when possible.
    `rank`: Zero-based candidate position from hybrid retrieval. The initializer
        divides by `rank + 1`, so top-ranked chunks start stronger without
        becoming final truth.
    `graph`: Weighted adjacency mapping. Edge weights control how movable energy
        is distributed to neighbors.
    `communities`: Spectral basin assignment by document id.
    `basin_graph`: Graph with cross-basin edges removed. Scoring diffusion uses
        this after basin detection so energy can settle inside fixed regions
        without leaking between competing regions.
    `damping`: Fraction of each node's current energy allowed to move during one
        time step. A higher value trusts graph structure more; a lower value
        keeps more confidence local to the original candidate.
    `diffusion_steps`: The engine-level number of repeated updates. More steps
        let energy travel farther through the graph; fewer steps keep it closer
        to the retrieval seed.
    `next_energy`: The next time-step distribution after retained and moved
        energy are combined.
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
        # Retrieval rank is useful signal, but this is where it stops being law.
        energy[result.id] = result.score / (rank + 1)
    total = sum(energy.values())
    if total > 0:
        # Diffusion expects a comparable distribution regardless of candidate count.
        energy = {doc_id: value / total for doc_id, value in energy.items()}
    return energy


def constrain_graph_to_communities(
    graph: dict[str, dict[str, float]],
    communities: dict[str, int],
) -> dict[str, dict[str, float]]:
    """Remove graph edges that cross spectral basin boundaries.

    Args:
        graph: Weighted adjacency mapping.
        communities: Spectral community assignment by document id.

    Returns:
        Weighted adjacency mapping containing only same-community edges.
    """
    basin_graph: dict[str, dict[str, float]] = {}
    for doc_id, neighbors in graph.items():
        doc_community = communities.get(doc_id)
        basin_graph[doc_id] = {
            neighbor_id: weight
            for neighbor_id, weight in neighbors.items()
            if doc_community is not None
            and communities.get(neighbor_id) == doc_community
        }
    return basin_graph


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
    # Retained energy is the "stay put" part of the update. Without it, every step
    # would fully overwrite local retrieval confidence with graph-neighbor signal.
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
            # Weighted edges define the transition proportions for this time step:
            # stronger relationships receive more of the node's movable energy.
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
