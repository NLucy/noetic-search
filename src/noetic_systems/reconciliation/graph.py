"""Evidence graph construction.

The graph is the local evidence structure for one query after candidate
admission. Each admitted chunk is a node. Each pair of chunks can receive one
weighted evidence connection built from out-of-the-box signal contributions:
embedding similarity and near-duplicate similarity. We use a graph because
top-k ranking treats chunks as isolated items, while evidence quality often
depends on relationships among chunks.

The graph is query-conditioned because it is built only over the candidates
retrieved for the current query. It is not a permanent whole-corpus manifold.
That choice keeps the computation small, keeps the structure aligned with the
user's intent, and avoids requiring special corpus annotations. The available
inputs are the same ones a normal RAG system already has: chunk text, embeddings,
retrieval scores, and ordinary metadata.

Signal contributions have practical meanings. Embedding similarity indicates
semantic closeness. Near-duplicate similarity identifies very similar chunks so
later scoring can avoid overvaluing repetition. Metadata stays available on the
returned chunks, but it does not shape graph edges. These contributions are
collapsed into one final adjacency weight per chunk pair; that adjacency map is
the structure that spectral partitioning and diffusion operate on.

Key variables:
    `threshold`: Minimum cosine similarity required to create a semantic edge.
        Raising it makes the graph stricter and sparser. Lowering it admits
        weaker semantic relationships.
    `EMBEDDING_EDGE_THRESHOLD`: Default value for `threshold`.
    `NEAR_DUPLICATE_THRESHOLD`: Similarity level treated as likely repetition.
        This does not remove the chunk; it marks the relationship so scoring can
        penalize basins that are mostly repeated material.
    `NEAR_DUPLICATE_WEIGHT`: Small extra edge weight attached to near-duplicate
        pairs. The value is intentionally small because duplication is useful to
        detect but should not dominate semantic similarity.
    `graph`: Weighted adjacency mapping. `graph[a][b]` is the final relationship
        strength between two candidate chunks.
    `edges`: Inspection records explaining which signal created each
        relationship before signals are collapsed into `graph`.
"""

from __future__ import annotations

import math

from noetic_systems.database import Database
from noetic_systems.reconciliation.models import EvidenceEdge
from noetic_systems.search.semantic import SearchResult

EMBEDDING_EDGE_THRESHOLD = 0.50
NEAR_DUPLICATE_THRESHOLD = 0.86
NEAR_DUPLICATE_WEIGHT = 0.05


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
    # weighted adjacency map. This keeps the math input compact while preserving
    # enough detail for `evidence_field()` to explain why chunks were connected.
    for i, id1 in enumerate(ids):
        for id2 in ids[i + 1:]:
            similarity = float(
                cosine_similarity(embeddings[id1], embeddings[id2])
            )
            # The primary graph force is raw embedding similarity. No metadata
            # assumptions are used here.
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

            # Near-duplicates are recorded separately so downstream scoring can
            # distinguish "many supporting chunks" from "the same chunk repeated."
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
        # so repeated signals do not create an effectively absolute edge. The cap
        # keeps the graph numeric and prevents duplicates from swamping diffusion.
        current = graph[edge.source].get(edge.target, 0.0)
        graph[edge.source][edge.target] = min(1.0, current + edge.weight)
        graph[edge.target][edge.source] = graph[edge.source][edge.target]

    return graph, edges


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
