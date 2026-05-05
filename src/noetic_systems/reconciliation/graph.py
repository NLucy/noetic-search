"""Evidence graph construction.

The graph is the local evidence structure for one query after candidate
admission. Each admitted chunk is a node. Each pair of chunks can receive one
weighted evidence connection built from out-of-the-box signal contributions:
embedding similarity, ordinary shared metadata, and near-duplicate similarity.
We use a graph because top-k ranking treats chunks as isolated items, while
evidence quality often depends on relationships among chunks.

The graph is query-conditioned because it is built only over the candidates
retrieved for the current query. It is not a permanent whole-corpus manifold.
That choice keeps the computation small, keeps the structure aligned with the
user's intent, and avoids requiring special corpus annotations. The available
inputs are the same ones a normal RAG system already has: chunk text, embeddings,
retrieval scores, and ordinary metadata.

Signal contributions have practical meanings. Embedding similarity indicates
semantic closeness, metadata agreement indicates shared source context such as
document, URL, title, or domain, and near-duplicate similarity identifies very
similar chunks so later scoring can avoid overvaluing repetition. These
contributions are collapsed into one final adjacency weight per chunk pair; that
adjacency map is the structure that spectral partitioning and diffusion operate
on.
"""

from __future__ import annotations

import math
from typing import Any

from noetic_systems.database import Database
from noetic_systems.reconciliation.models import EvidenceEdge
from noetic_systems.search.semantic import SearchResult

STRONG_METADATA_WEIGHTS = {
    "document_id": 0.32,
    "url": 0.24,
    "title": 0.14,
}
CONTEXT_METADATA_WEIGHTS = {
    "domain": 0.10,
    "section": 0.06,
    "author": 0.06,
    "source": 0.08,
}
CONTEXT_METADATA_MIN_SIMILARITY = 0.35
EMBEDDING_EDGE_THRESHOLD = 0.50
NEAR_DUPLICATE_THRESHOLD = 0.86
NEAR_DUPLICATE_WEIGHT = 0.05
MAX_METADATA_EDGE_WEIGHT = 0.40


def build_evidence_graph(
    database: Database,
    doc_index: dict[str, SearchResult],
    threshold: float,
) -> tuple[dict[str, dict[str, float]], list[EvidenceEdge]]:
    """Build a weighted evidence graph from pairwise signal contributions.

    Args:
        database: Database used to fetch candidate embeddings.
        doc_index: Candidate lookup by document id.
        threshold: Minimum embedding similarity for semantic edges.

    Returns:
        Weighted adjacency mapping and signal-contribution inspection records.
    """
    ids = list(doc_index.keys())
    result = database.collection.get(ids=ids, include=["embeddings"])
    embeddings_list = result.get("embeddings")
    if embeddings_list is None or len(embeddings_list) == 0:
        return {doc_id: {} for doc_id in ids}, []

    embeddings = dict(zip(result["ids"], embeddings_list))
    graph: dict[str, dict[str, float]] = {doc_id: {} for doc_id in ids}
    edges: list[EvidenceEdge] = []

    # Build inspection-friendly edge records first, then collapse them into one
    # weighted adjacency map for spectral partitioning and diffusion.
    for i, id1 in enumerate(ids):
        for id2 in ids[i + 1:]:
            similarity = float(
                cosine_similarity(embeddings[id1], embeddings[id2])
            )
            if similarity >= threshold:
                edges.append(
                    EvidenceEdge(
                        id1,
                        id2,
                        "embedding_similarity",
                        similarity,
                        "embedding similarity above threshold",
                    )
                )

            metadata_weight = metadata_signal_weight(
                doc_index[id1].metadata,
                doc_index[id2].metadata,
                similarity,
            )
            if metadata_weight > 0:
                edges.append(
                    EvidenceEdge(
                        id1,
                        id2,
                        "metadata_relation",
                        metadata_weight,
                        "shared ordinary metadata",
                    )
                )

            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                edges.append(
                    EvidenceEdge(
                        id1,
                        id2,
                        "near_duplicate",
                        NEAR_DUPLICATE_WEIGHT,
                        "very high embedding similarity",
                    )
                )

    for edge in edges:
        # Multiple evidence signals can connect the same pair; cap combined weight
        # so repeated signals do not create an effectively absolute edge.
        current = graph[edge.source].get(edge.target, 0.0)
        graph[edge.source][edge.target] = min(1.0, current + edge.weight)
        graph[edge.target][edge.source] = graph[edge.source][edge.target]

    return graph, edges


def metadata_signal_weight(
    left: dict[str, Any],
    right: dict[str, Any],
    similarity: float,
) -> float:
    """Calculate the metadata contribution to a pairwise connection.

    Args:
        left: Metadata for the first candidate.
        right: Metadata for the second candidate.
        similarity: Embedding similarity between the candidates.

    Returns:
        Metadata edge weight capped by `MAX_METADATA_EDGE_WEIGHT`.
    """
    weight = 0.0
    # Strong metadata can connect chunks even when wording differs substantially.
    for key, key_weight in STRONG_METADATA_WEIGHTS.items():
        if metadata_equal(left, right, key):
            weight += key_weight
    if similarity >= CONTEXT_METADATA_MIN_SIMILARITY:
        # Context metadata is only used when embeddings already show some relation.
        for key, key_weight in CONTEXT_METADATA_WEIGHTS.items():
            if metadata_equal(left, right, key):
                weight += key_weight
    return min(MAX_METADATA_EDGE_WEIGHT, weight)


def metadata_equal(
    left: dict[str, Any],
    right: dict[str, Any],
    key: str,
) -> bool:
    """Check whether a metadata key is present and equal on both sides.

    Args:
        left: Metadata for the first candidate.
        right: Metadata for the second candidate.
        key: Metadata key to compare.

    Returns:
        `True` when both candidates share the same non-empty value.
    """
    return bool(left.get(key) and left.get(key) == right.get(key))


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity, or `0.0` when either vector has zero norm.
    """
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)
