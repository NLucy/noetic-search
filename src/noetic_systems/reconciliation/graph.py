"""Evidence graph construction.

The graph is the local evidence structure for one query after candidate
admission. Each admitted chunk is a node. Each pair of chunks can receive one
weighted evidence connection built from out-of-the-box signal contributions:
embedding similarity, lexical salience, explicit cross-reference, and
near-duplicate similarity. We use a graph because top-k ranking treats chunks as
isolated items, while evidence quality often depends on relationships among
chunks.

The graph is query-conditioned because it is built only over the candidates
retrieved for the current query. It is not a permanent whole-corpus manifold.
That choice keeps the computation small, keeps the structure aligned with the
user's intent, and avoids requiring special corpus annotations. The available
inputs are the same ones a normal RAG system already has: chunk text,
embeddings, and retrieval scores.

Signal contributions have practical meanings. Embedding similarity indicates
semantic closeness. Lexical salience captures shared identifying words and
phrases after stop-word removal and local IDF weighting. Explicit
cross-reference captures the multi-hop case where one chunk names the title-like
label of another chunk. Near-duplicate similarity identifies very similar chunks
so later scoring can avoid overvaluing repetition. These contributions are
collapsed into one final adjacency weight per chunk pair; that adjacency map is
the structure that linked-evidence ranking uses. The same adjacency map also
feeds spectral partitioning and diffusion when diagnostics are requested.

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
    `LEXICAL_EDGE_THRESHOLD`: Minimum salience overlap required for a lexical
        edge.
    `LEXICAL_EDGE_WEIGHT`: Weight applied to lexical salience edges.
    `CROSS_REFERENCE_WEIGHT`: Weight applied when one chunk names another
        chunk's title-like label.
    `graph`: Weighted adjacency mapping. `graph[a][b]` is the final relationship
        strength between two candidate chunks.
    `edges`: Inspection records explaining which signal created each
        relationship before signals are collapsed into `graph`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from noetic_systems.database import Database
from noetic_systems.reconciliation.models import EvidenceEdge
from noetic_systems.search.semantic import SearchResult

EMBEDDING_EDGE_THRESHOLD = 0.50
NEAR_DUPLICATE_THRESHOLD = 0.86
NEAR_DUPLICATE_WEIGHT = 0.05
LEXICAL_EDGE_THRESHOLD = 0.08
LEXICAL_EDGE_WEIGHT = 0.20
CROSS_REFERENCE_WEIGHT = 0.55
STOPWORDS = frozenset(
    {
        "about",
        "after",
        "also",
        "and",
        "are",
        "because",
        "been",
        "but",
        "can",
        "for",
        "from",
        "had",
        "has",
        "have",
        "her",
        "his",
        "into",
        "its",
        "more",
        "not",
        "one",
        "only",
        "other",
        "over",
        "she",
        "that",
        "the",
        "their",
        "then",
        "there",
        "this",
        "through",
        "title",
        "was",
        "were",
        "when",
        "where",
        "which",
        "who",
        "with",
    }
)


@dataclass(frozen=True)
class GraphWeights:
    """Weights and thresholds used during evidence graph construction.

    Attributes:
        semantic_weight: Weight applied to semantic similarity values.
        semantic_threshold: Minimum cosine similarity required for a semantic edge.
        lexical_threshold: Minimum salience overlap required for a lexical edge.
        lexical_weight: Weight applied to lexical salience values.
        cross_reference_weight: Weight applied to explicit cross-reference edges.
        near_duplicate_threshold: Similarity treated as likely repetition.
        near_duplicate_weight: Weight applied to near-duplicate edges.
    """

    semantic_weight: float = 1.0
    semantic_threshold: float = EMBEDDING_EDGE_THRESHOLD
    lexical_threshold: float = LEXICAL_EDGE_THRESHOLD
    lexical_weight: float = LEXICAL_EDGE_WEIGHT
    cross_reference_weight: float = CROSS_REFERENCE_WEIGHT
    near_duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD
    near_duplicate_weight: float = NEAR_DUPLICATE_WEIGHT


def build_evidence_graph(
    database: Database,
    doc_index: dict[str, SearchResult],
    threshold: float,
    weights: GraphWeights | None = None,
) -> tuple[dict[str, dict[str, float]], list[EvidenceEdge]]:
    """Build a weighted evidence graph from pairwise signal contributions.

    Args:
        database: Database used to fetch candidate embeddings.
        doc_index: Candidate lookup by document id.
        threshold: Minimum embedding similarity for semantic edges.
        weights: Optional calibrated graph weights. When omitted, defaults are
            used and `threshold` supplies the semantic threshold.

    Returns:
        Weighted adjacency mapping and signal-contribution inspection records.
    """
    active_weights = weights or GraphWeights(semantic_threshold=threshold)
    ids = list(doc_index.keys())
    result = database.collection.get(ids=ids, include=["embeddings"])
    embeddings_list = result.get("embeddings")
    if embeddings_list is None or len(embeddings_list) == 0:
        return {doc_id: {} for doc_id in ids}, []

    embeddings = dict(zip(result["ids"], embeddings_list))
    similarities = pairwise_cosine_similarities(ids, embeddings)
    graph: dict[str, dict[str, float]] = {doc_id: {} for doc_id in ids}
    edges: list[EvidenceEdge] = []
    salience_maps = candidate_salience_maps(
        [doc_index[doc_id] for doc_id in ids]
    )
    labels = {
        doc_id: title_like_label(doc_index[doc_id])
        for doc_id in ids
    }

    # Build inspection-friendly edge records first, then collapse them into one
    # weighted adjacency map. This keeps the math input compact while preserving
    # enough detail for `evidence_field()` to explain why chunks were connected.
    for i, id1 in enumerate(ids):
        for id2 in ids[i + 1:]:
            similarity = similarities.get((id1, id2), 0.0)
            # The primary graph force is raw embedding similarity. No metadata
            # assumptions are used here.
            if similarity >= active_weights.semantic_threshold:
                edges.append(
                    EvidenceEdge(
                        id1,
                        id2,
                        "embedding_similarity",
                        active_weights.semantic_weight * similarity,
                        "embedding similarity above threshold",
                    )
                )

            # Near-duplicates are recorded separately so downstream scoring can
            # distinguish "many supporting chunks" from "the same chunk repeated."
            if similarity >= active_weights.near_duplicate_threshold:
                edges.append(
                    EvidenceEdge(
                        id1,
                        id2,
                        "near_duplicate",
                        active_weights.near_duplicate_weight,
                        "very high embedding similarity",
                    )
                )

            lexical = salience_overlap(salience_maps[id1], salience_maps[id2])
            if lexical >= active_weights.lexical_threshold:
                edges.append(
                    EvidenceEdge(
                        id1,
                        id2,
                        "lexical_salience",
                        active_weights.lexical_weight * lexical,
                        "shared salient terms or phrases above threshold",
                    )
                )

            if cross_reference(doc_index[id1].text, labels[id2]) or cross_reference(
                doc_index[id2].text,
                labels[id1],
            ):
                edges.append(
                    EvidenceEdge(
                        id1,
                        id2,
                        "cross_reference",
                        active_weights.cross_reference_weight,
                        "one chunk names the title-like label of the other",
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


def title_like_label(result: SearchResult) -> str:
    """Extract the best available title-like label for a chunk.

    Args:
        result: Candidate search result.

    Returns:
        Lowercase label, or an empty string when no label is available.
    """
    title = str(result.metadata.get("title", "")).strip()
    if title:
        return title.lower()
    first_line = result.text.splitlines()[0].strip() if result.text else ""
    if first_line.lower().startswith("title:"):
        return first_line.split(":", 1)[1].strip().lower()
    return ""


def pairwise_cosine_similarities(
    ids: list[str],
    embeddings: dict[str, list[float]],
) -> dict[tuple[str, str], float]:
    """Calculate pairwise cosine similarities with one matrix operation.

    Args:
        ids: Ordered document ids.
        embeddings: Embedding vectors by document id.

    Returns:
        Similarity values keyed by ordered document-id pair.
    """
    if len(ids) < 2:
        return {}
    matrix = np.array([embeddings[doc_id] for doc_id in ids], dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    normalized = np.divide(
        matrix,
        norms,
        out=np.zeros_like(matrix),
        where=norms != 0,
    )
    similarity_matrix = normalized @ normalized.T
    similarities: dict[tuple[str, str], float] = {}
    for i, left_id in enumerate(ids):
        for j in range(i + 1, len(ids)):
            similarities[(left_id, ids[j])] = float(similarity_matrix[i, j])
    return similarities


def cross_reference(text: str, label: str) -> bool:
    """Return whether text explicitly names a title-like label.

    Args:
        text: Chunk text to inspect.
        label: Candidate title-like label.

    Returns:
        Whether the label appears as a phrase in the text.
    """
    if not label or len(label) < 3:
        return False
    return bool(re.search(rf"\b{re.escape(label)}\b", text.lower()))


def tokens(text: str) -> list[str]:
    """Tokenize text for lexical graph edges.

    Args:
        text: Text to tokenize.

    Returns:
        Lowercase alphanumeric tokens of at least three characters.
    """
    return [
        token
        for token in re.findall(r"[a-z0-9]{3,}", text.lower())
        if token not in STOPWORDS
    ]


def candidate_salience_maps(
    candidates: list[SearchResult],
) -> dict[str, dict[str, float]]:
    """Build salience-weighted term and phrase maps for candidates.

    Args:
        candidates: Candidate search results.

    Returns:
        Mapping from document id to salience weights by token or phrase.
    """
    candidate_terms = {
        candidate.id: set(terms_and_phrases(candidate.text))
        for candidate in candidates
    }
    document_frequency: dict[str, int] = {}
    for terms in candidate_terms.values():
        for term in terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1

    total = len(candidates)
    salience: dict[str, dict[str, float]] = {}
    for candidate_id, terms in candidate_terms.items():
        term_weights: dict[str, float] = {}
        for term in terms:
            idf = math.log((1 + total) / (1 + document_frequency[term]))
            term_weights[term] = idf * phrase_boost(term)
        salience[candidate_id] = term_weights
    return salience


def terms_and_phrases(text: str) -> list[str]:
    """Extract stop-word-filtered unigrams, bigrams, and trigrams.

    Args:
        text: Text to inspect.

    Returns:
        Salience candidates.
    """
    base_tokens = tokens(text)
    terms = list(base_tokens)
    for size in (2, 3):
        for index in range(0, len(base_tokens) - size + 1):
            phrase = " ".join(base_tokens[index : index + size])
            terms.append(phrase)
    return terms


def phrase_boost(term: str) -> float:
    """Return a weight multiplier for longer terms.

    Args:
        term: Token or phrase.

    Returns:
        Salience multiplier.
    """
    length = len(term.split())
    if length >= 3:
        return 2.0
    if length == 2:
        return 1.5
    return 1.0


def salience_overlap(left: dict[str, float], right: dict[str, float]) -> float:
    """Calculate weighted lexical salience overlap.

    Args:
        left: Salience map for the first candidate.
        right: Salience map for the second candidate.

    Returns:
        Cosine-like overlap over shared salient terms and phrases.
    """
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    numerator = sum(min(left[term], right[term]) for term in shared)
    left_total = sum(left.values())
    right_total = sum(right.values())
    denominator = min(left_total, right_total)
    if denominator == 0:
        return 0.0
    return numerator / denominator


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
