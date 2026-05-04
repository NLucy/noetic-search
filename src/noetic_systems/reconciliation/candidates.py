"""Candidate field admission for the local evidence graph.

The candidate field is the bridge between broad hybrid retrieval and graph
reconciliation. Hybrid search may retrieve more chunks than the graph should
use directly, so this module selects a smaller working set by preserving hybrid
rank order. The goal is still recall: the graph should contain enough plausible
evidence to let later stages separate support, decoys, duplicates, and noise.

This step is separate from graph construction because it answers a different
question. Candidate admission asks which retrieved chunks are allowed into the
local field. Graph construction asks how admitted chunks relate to each other.
Candidate admission should stay neutral: sometimes the relevant evidence really
is distributed across one source.
"""

from __future__ import annotations

from noetic_systems.search.semantic import SearchResult


def select_graph_candidates(
    candidates: list[SearchResult],
    result_limit: int,
) -> list[SearchResult]:
    """Select the top ranked graph candidates without metadata downsampling.

    Args:
        candidates: Ranked hybrid candidates.
        result_limit: Maximum candidates retained for the graph.

    Returns:
        Candidate subset for graph construction.
    """
    # Keep admission neutral. The graph can use metadata as relationship evidence,
    # but admission should not downsample one source before structure is measured.
    return candidates[:result_limit]
