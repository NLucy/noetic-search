"""Spectral community detection for evidence graphs.

Spectral detection uses the normalized graph Laplacian to find a low-energy cut
through the local candidate graph. The Fiedler vector, associated with the
second-smallest eigenvalue, gives a principled split when the graph has a real
separation. We use this method to identify coherent basins before deciding which
chunks to return.

The normalized Laplacian represents how each node differs from its neighbors
after accounting for node degree. Its eigenvectors describe large-scale
directions of variation in the graph. The Fiedler vector is useful because its
sign and magnitude often reveal the strongest binary separation in a connected
graph. In this pipeline, that separation becomes a candidate basin split.

The split is accepted only when it is large enough and improves modularity. That
guard matters because eigendecomposition will always produce vectors, even when
the candidate graph does not contain a meaningful separation. If no useful split
exists, the graph remains one basin.
"""

from __future__ import annotations

import numpy as np

SPECTRAL_MIN_SPLIT_SIZE = 4
SPECTRAL_MAX_DEPTH = 1
SPECTRAL_MIN_SPLIT_MODULARITY = 0.10


def detect_communities(
    graph: dict[str, dict[str, float]],
) -> dict[str, int]:
    """Detect communities with normalized-Laplacian spectral partitioning.

    Args:
        graph: Weighted adjacency mapping.

    Returns:
        Mapping from document id to community id.
    """
    return detect_spectral_communities(graph)


def detect_spectral_communities(
    graph: dict[str, dict[str, float]],
) -> dict[str, int]:
    """Detect communities by bisecting the normalized Laplacian.

    Args:
        graph: Weighted adjacency mapping.

    Returns:
        Mapping from document id to spectral community id.
    """
    nodes = list(graph)
    if len(nodes) < 2:
        return {node: index for index, node in enumerate(nodes)}

    partitions = spectral_partition(nodes, graph)
    communities: dict[str, int] = {}
    for comm_id, partition in enumerate(partitions):
        for node in partition:
            communities[node] = comm_id
    return communities


def spectral_partition(
    nodes: list[str],
    graph: dict[str, dict[str, float]],
    *,
    min_size: int = SPECTRAL_MIN_SPLIT_SIZE,
    max_depth: int = SPECTRAL_MAX_DEPTH,
    depth: int = 0,
) -> list[list[str]]:
    """Recursively partition nodes with the Fiedler vector.

    Args:
        nodes: Document ids in the current subgraph.
        graph: Weighted adjacency mapping.
        min_size: Minimum allowed partition size.
        max_depth: Maximum recursive split depth.
        depth: Current recursive depth.

    Returns:
        List of accepted node partitions.
    """
    if len(nodes) <= min_size or depth >= max_depth:
        return [nodes]

    left, right = fiedler_split(nodes, graph)
    if not left or not right:
        return [nodes]
    # Spectral vectors always exist; these guards reject splits that are too small
    # or do not improve the graph's community structure enough to be useful.
    if min(len(left), len(right)) < min_size:
        return [nodes]
    if split_modularity(left, right, graph) <= SPECTRAL_MIN_SPLIT_MODULARITY:
        return [nodes]

    return (
        spectral_partition(
            left,
            graph,
            min_size=min_size,
            max_depth=max_depth,
            depth=depth + 1,
        )
        + spectral_partition(
            right,
            graph,
            min_size=min_size,
            max_depth=max_depth,
            depth=depth + 1,
        )
    )


def fiedler_split(
    nodes: list[str],
    graph: dict[str, dict[str, float]],
) -> tuple[list[str], list[str]]:
    """Split nodes using the normalized-Laplacian Fiedler vector.

    Args:
        nodes: Document ids to split.
        graph: Weighted adjacency mapping.

    Returns:
        Two node lists. Empty lists indicate that no valid split was found.
    """
    adjacency = adjacency_matrix(nodes, graph)
    degrees = adjacency.sum(axis=1)
    if float(degrees.sum()) == 0.0:
        return [], []

    # L_norm = I - D^-1/2 A D^-1/2 balances nodes by degree before eigenanalysis.
    inv_sqrt = np.zeros_like(degrees)
    nonzero = degrees > 0
    inv_sqrt[nonzero] = 1.0 / np.sqrt(degrees[nonzero])
    normalized = np.eye(len(nodes)) - (
        inv_sqrt[:, None] * adjacency * inv_sqrt[None, :]
    )
    eigenvalues, eigenvectors = np.linalg.eigh(normalized)
    if len(eigenvalues) < 2:
        return [], []

    # The Fiedler vector is the first nontrivial graph coordinate after the
    # constant eigenvector; splitting on it proposes a natural basin boundary.
    fiedler = eigenvectors[:, 1]
    threshold = float(np.median(fiedler))
    left = [
        node
        for node, value in zip(nodes, fiedler)
        if float(value) <= threshold
    ]
    right = [
        node
        for node, value in zip(nodes, fiedler)
        if float(value) > threshold
    ]

    if not left or not right:
        # Median is robust, but mean can recover a split when many values tie.
        mean = float(np.mean(fiedler))
        left = [
            node
            for node, value in zip(nodes, fiedler)
            if float(value) <= mean
        ]
        right = [
            node
            for node, value in zip(nodes, fiedler)
            if float(value) > mean
        ]
    return left, right


def adjacency_matrix(
    nodes: list[str],
    graph: dict[str, dict[str, float]],
) -> np.ndarray:
    """Convert a graph mapping into a symmetric adjacency matrix.

    Args:
        nodes: Ordered document ids defining matrix rows and columns.
        graph: Weighted adjacency mapping.

    Returns:
        Symmetric adjacency matrix.
    """
    index = {node: position for position, node in enumerate(nodes)}
    adjacency = np.zeros((len(nodes), len(nodes)), dtype=float)
    # Preserve the caller's node order so eigenvector entries map back to ids.
    for source in nodes:
        source_index = index[source]
        for target, weight in graph.get(source, {}).items():
            target_index = index.get(target)
            if target_index is not None:
                adjacency[source_index, target_index] = float(weight)
    return np.maximum(adjacency, adjacency.T)


def split_modularity(
    left: list[str],
    right: list[str],
    graph: dict[str, dict[str, float]],
) -> float:
    """Calculate modularity for a proposed two-way split.

    Args:
        left: Document ids in the first partition.
        right: Document ids in the second partition.
        graph: Weighted adjacency mapping.

    Returns:
        Modularity score for the proposed split.
    """
    total_weight = sum(
        sum(neighbors.values())
        for neighbors in graph.values()
    ) / 2.0
    if total_weight == 0.0:
        return 0.0

    modularity = 0.0
    # Score the proposed two-way partition against a degree-preserving baseline.
    for group in (set(left), set(right)):
        for source in group:
            source_degree = sum(graph.get(source, {}).values())
            for target in group:
                target_degree = sum(graph.get(target, {}).values())
                weight = graph.get(source, {}).get(target, 0.0)
                expected = (source_degree * target_degree) / (2.0 * total_weight)
                modularity += weight - expected
    return float(modularity / (2.0 * total_weight))

