"""Ablation variants for retrieval/reconciliation evaluation.

These helpers are intentionally evaluation-only. They reuse production graph,
spectral, diffusion, basin, and ranking functions, but combine them in altered
ways so benchmark runs can identify which layer is helping or hurting.

Key variables:
    `hybrid`: Raw first-stage retrieval order.
    `noetic`: Production pipeline output.
    `single_basin`: No spectral split; diffuse and rank the admitted graph field.
    `seed_only`: Spectral basins scored from initial retrieval seed energy.
    `energy_only`: Spectral basins selected by total energy alone.
    `unranked_winner`: Winning basin returned in raw hybrid order.
    `hybrid_graph_score`: Hybrid-preserving rank with graph features as a
        controlled rerank signal.
    `topk_basin_round_robin`: Interleave candidates from multiple basins in
        hybrid order.
    `anchored_bridge`: Preserve early hybrid anchors, then promote candidates
        connected to those anchors.
    `anchor_mention_bridge`: Preserve anchors, then promote candidates whose
        titles are mentioned by anchor text or whose text mentions anchor titles.
    `hybrid_weighted_noetic`: Production-style spectral/diffusion/ranking over a
        query-conditioned graph weighted by hybrid relevance and lexical overlap.
"""

from __future__ import annotations

from noetic_systems.database import Database
from noetic_systems.reconciliation.basins import build_basins
from noetic_systems.reconciliation.diffusion import (
    constrain_graph_to_communities,
    diffuse,
    seed_energy,
)
from noetic_systems.reconciliation.graph import build_evidence_graph
from noetic_systems.reconciliation.graph import cosine_similarity
from noetic_systems.reconciliation.metrics import document_specificity
from noetic_systems.reconciliation.metrics import tokens
from noetic_systems.reconciliation.ranking import rank_basin_documents
from noetic_systems.reconciliation.spectral import detect_communities
from noetic_systems.search.semantic import SearchResult

ABLATION_VARIANTS = (
    "hybrid",
    "noetic",
    "single_basin",
    "seed_only",
    "energy_only",
    "unranked_winner",
    "hybrid_graph_score",
    "topk_basin_round_robin",
    "anchored_bridge",
    "anchor_mention_bridge",
    "hybrid_weighted_noetic",
)

DEFAULT_HYBRID_GRAPH_WEIGHTS = {
    "query": 0.85,
    "energy": 0.10,
    "support": 0.05,
    "specificity": 0.00,
}


def ranked_ids_for_variant(
    database: Database,
    graph_candidates: list[SearchResult],
    variant: str,
    *,
    edge_threshold: float,
    diffusion_steps: int,
    damping: float,
) -> list[str]:
    """Return a ranked candidate list for one ablation variant.

    Args:
        database: Database containing candidate embeddings.
        graph_candidates: Candidates admitted to the local evidence graph.
        variant: Ablation variant name.
        edge_threshold: Minimum embedding similarity for graph edges.
        diffusion_steps: Number of diffusion time steps.
        damping: Fraction of energy moved during each diffusion step.

    Returns:
        Ranked document ids produced by the selected variant.
    """
    if variant == "hybrid":
        return [candidate.id for candidate in graph_candidates]

    if not graph_candidates:
        return []

    doc_index = {candidate.id: candidate for candidate in graph_candidates}
    graph, _edges = build_evidence_graph(database, doc_index, edge_threshold)
    if variant == "hybrid_weighted_noetic":
        graph = build_hybrid_weighted_graph(database, graph_candidates, edge_threshold)
    initial_energy = seed_energy(graph_candidates)
    specificity = document_specificity(graph_candidates)

    if variant == "single_basin":
        # Remove basin detection and ask whether field-wide diffusion/ranking is
        # enough to produce a better compact retrieval list.
        energy = dict(initial_energy)
        for _ in range(diffusion_steps):
            energy = diffuse(energy, graph, damping)
        return rank_basin_documents(list(graph), energy, specificity)

    if variant == "hybrid_graph_score":
        energy = dict(initial_energy)
        for _ in range(diffusion_steps):
            energy = diffuse(energy, graph, damping)
        return hybrid_graph_rank(graph_candidates, graph, energy, specificity)

    if variant == "anchored_bridge":
        return anchored_bridge_rank(graph_candidates, graph)

    if variant == "anchor_mention_bridge":
        return anchor_mention_bridge_rank(graph_candidates, graph)

    communities = detect_communities(graph)
    if not communities:
        return []

    if variant == "topk_basin_round_robin":
        return topk_basin_round_robin(graph_candidates, communities)

    basin_graph = constrain_graph_to_communities(graph, communities)
    energy = dict(initial_energy)
    if variant != "seed_only":
        for _ in range(diffusion_steps):
            energy = diffuse(energy, basin_graph, damping)

    basins = build_basins(communities, energy, graph)
    if not basins:
        return []

    if variant == "energy_only":
        winner = max(basins, key=lambda basin: basin.energy)
    else:
        winner = max(basins, key=lambda basin: basin.score)

    if variant == "unranked_winner":
        candidate_order = {
            candidate.id: index
            for index, candidate in enumerate(graph_candidates)
        }
        return sorted(
            winner.documents,
            key=lambda doc_id: candidate_order.get(doc_id, 10**9),
        )

    return rank_basin_documents(list(winner.documents), energy, specificity)


def hybrid_graph_rank(
    graph_candidates: list[SearchResult],
    graph: dict[str, dict[str, float]],
    energy: dict[str, float],
    specificity: dict[str, float],
    *,
    weights: dict[str, float] | None = None,
) -> list[str]:
    """Rank candidates with hybrid score preserved as the primary signal.

    Args:
        graph_candidates: Candidates admitted to the local evidence graph.
        graph: Weighted adjacency mapping.
        energy: Diffused energy by document id.
        specificity: Specificity score by document id.
        weights: Optional feature weights for query, energy, support, and
            specificity.

    Returns:
        Ranked document ids.
    """
    active_weights = weights or DEFAULT_HYBRID_GRAPH_WEIGHTS
    query_score = {candidate.id: candidate.score for candidate in graph_candidates}
    support = {
        doc_id: sum(neighbors.values())
        for doc_id, neighbors in graph.items()
    }
    normalized = {
        "query": normalize_feature(query_score),
        "energy": normalize_feature(energy),
        "support": normalize_feature(support),
        "specificity": normalize_feature(specificity),
    }
    original_rank = {
        candidate.id: index
        for index, candidate in enumerate(graph_candidates)
    }

    def score(doc_id: str) -> tuple[float, int]:
        """Score one candidate for hybrid-preserving reranking.

        Args:
            doc_id: Candidate document id.

        Returns:
            Descending score and ascending original rank.
        """
        value = sum(
            active_weights.get(name, 0.0) * normalized[name].get(doc_id, 0.0)
            for name in normalized
        )
        return value, -original_rank.get(doc_id, 10**9)

    return sorted(query_score, key=score, reverse=True)


def topk_basin_round_robin(
    graph_candidates: list[SearchResult],
    communities: dict[str, int],
) -> list[str]:
    """Interleave spectral basins while preserving hybrid order inside each basin.

    Args:
        graph_candidates: Candidates admitted to the local evidence graph.
        communities: Spectral community assignment by document id.

    Returns:
        Ranked document ids.
    """
    grouped: dict[int, list[str]] = {}
    basin_first_rank: dict[int, int] = {}
    for rank, candidate in enumerate(graph_candidates):
        basin = communities.get(candidate.id)
        if basin is None:
            continue
        grouped.setdefault(basin, []).append(candidate.id)
        basin_first_rank.setdefault(basin, rank)

    basin_order = sorted(grouped, key=lambda basin: basin_first_rank[basin])
    ranked: list[str] = []
    while any(grouped[basin] for basin in basin_order):
        for basin in basin_order:
            if grouped[basin]:
                ranked.append(grouped[basin].pop(0))
    return ranked


def normalize_feature(values: dict[str, float]) -> dict[str, float]:
    """Normalize a feature dictionary to the `[0, 1]` interval.

    Args:
        values: Raw feature values by document id.

    Returns:
        Min-max normalized feature values.
    """
    if not values:
        return {}
    minimum = min(values.values())
    maximum = max(values.values())
    if maximum == minimum:
        return {doc_id: 1.0 for doc_id in values}
    return {
        doc_id: (value - minimum) / (maximum - minimum)
        for doc_id, value in values.items()
    }


def anchored_bridge_rank(
    graph_candidates: list[SearchResult],
    graph: dict[str, dict[str, float]],
    *,
    anchor_count: int = 3,
    query_weight: float = 0.68,
    bridge_weight: float = 0.27,
    support_weight: float = 0.05,
    anchor_bonus: float = 2.0,
) -> list[str]:
    """Promote graph neighbors of the strongest hybrid anchors.

    Args:
        graph_candidates: Candidates admitted to the local evidence graph.
        graph: Weighted adjacency mapping.
        anchor_count: Number of top hybrid candidates treated as anchors.
        query_weight: Weight for original hybrid score after the anchors.
        bridge_weight: Weight for connection strength to the anchors.
        support_weight: Weight for weighted graph degree.
        anchor_bonus: Fixed score boost that keeps anchors at the top.

    Returns:
        Ranked document ids.
    """
    if not graph_candidates:
        return []

    candidate_ids = [candidate.id for candidate in graph_candidates]
    anchors = candidate_ids[:anchor_count]
    query_score = normalize_feature(
        {candidate.id: candidate.score for candidate in graph_candidates}
    )
    support = normalize_feature(
        {
            doc_id: sum(neighbors.values())
            for doc_id, neighbors in graph.items()
        }
    )
    original_rank = {
        candidate.id: index
        for index, candidate in enumerate(graph_candidates)
    }
    anchor_affinity = {}
    for doc_id in candidate_ids:
        anchor_affinity[doc_id] = max(
            (graph.get(doc_id, {}).get(anchor, 0.0) for anchor in anchors),
            default=0.0,
        )
    anchor_affinity = normalize_feature(anchor_affinity)

    def score(doc_id: str) -> tuple[float, int]:
        """Score one candidate for bridge-oriented reranking.

        Args:
            doc_id: Candidate document id.

        Returns:
            Descending score and ascending original rank.
        """
        if doc_id in anchors:
            return anchor_bonus - (original_rank[doc_id] * 0.001), -original_rank[doc_id]
        value = (
            query_weight * query_score.get(doc_id, 0.0)
            + bridge_weight * anchor_affinity.get(doc_id, 0.0)
            + support_weight * support.get(doc_id, 0.0)
        )
        return value, -original_rank.get(doc_id, 10**9)

    return sorted(candidate_ids, key=score, reverse=True)


def anchor_mention_bridge_rank(
    graph_candidates: list[SearchResult],
    graph: dict[str, dict[str, float]],
    *,
    anchor_count: int = 4,
    query_weight: float = 0.45,
    mention_weight: float = 0.35,
    bridge_weight: float = 0.15,
    support_weight: float = 0.05,
    anchor_bonus: float = 2.0,
) -> list[str]:
    """Promote candidates connected to anchors by title/text mentions.

    Args:
        graph_candidates: Candidates admitted to the local evidence graph.
        graph: Weighted adjacency mapping.
        anchor_count: Number of top hybrid candidates treated as anchors.
        query_weight: Weight for original hybrid score after the anchors.
        mention_weight: Weight for anchor/candidate title mention evidence.
        bridge_weight: Weight for graph connection strength to anchors.
        support_weight: Weight for weighted graph degree.
        anchor_bonus: Fixed score boost that keeps anchors at the top.

    Returns:
        Ranked document ids.
    """
    if not graph_candidates:
        return []

    candidate_ids = [candidate.id for candidate in graph_candidates]
    anchors = graph_candidates[:anchor_count]
    anchor_ids = {candidate.id for candidate in anchors}
    anchor_text = "\n".join(candidate.text.lower() for candidate in anchors)
    anchor_titles = [
        title
        for candidate in anchors
        if (title := title_from_result(candidate))
    ]
    query_score = normalize_feature(
        {candidate.id: candidate.score for candidate in graph_candidates}
    )
    support = normalize_feature(
        {
            doc_id: sum(neighbors.values())
            for doc_id, neighbors in graph.items()
        }
    )
    original_rank = {
        candidate.id: index
        for index, candidate in enumerate(graph_candidates)
    }
    anchor_affinity = normalize_feature(
        {
            doc_id: max(
                (graph.get(doc_id, {}).get(anchor.id, 0.0) for anchor in anchors),
                default=0.0,
            )
            for doc_id in candidate_ids
        }
    )
    mention = normalize_feature(
        {
            candidate.id: mention_score(candidate, anchor_text, anchor_titles)
            for candidate in graph_candidates
        }
    )

    def score(doc_id: str) -> tuple[float, int]:
        """Score one candidate for mention-aware bridge ranking.

        Args:
            doc_id: Candidate document id.

        Returns:
            Descending score and ascending original rank.
        """
        if doc_id in anchor_ids:
            return anchor_bonus - (original_rank[doc_id] * 0.001), -original_rank[doc_id]
        value = (
            query_weight * query_score.get(doc_id, 0.0)
            + mention_weight * mention.get(doc_id, 0.0)
            + bridge_weight * anchor_affinity.get(doc_id, 0.0)
            + support_weight * support.get(doc_id, 0.0)
        )
        return value, -original_rank.get(doc_id, 10**9)

    return sorted(candidate_ids, key=score, reverse=True)


def title_from_result(result: SearchResult) -> str:
    """Extract a title-like label from result metadata or text.

    Args:
        result: Search result to inspect.

    Returns:
        Lowercase title string, or an empty string when absent.
    """
    metadata_title = str(result.metadata.get("title", "")).strip()
    if metadata_title:
        return metadata_title.lower()
    first_line = result.text.splitlines()[0].strip() if result.text else ""
    if first_line.lower().startswith("title:"):
        return first_line.split(":", 1)[1].strip().lower()
    return ""


def mention_score(
    candidate: SearchResult,
    anchor_text: str,
    anchor_titles: list[str],
) -> float:
    """Score title/text mention evidence between anchors and a candidate.

    Args:
        candidate: Candidate to score.
        anchor_text: Lowercase combined anchor text.
        anchor_titles: Lowercase titles from anchor candidates.

    Returns:
        Mention score before normalization.
    """
    title = title_from_result(candidate)
    candidate_text = candidate.text.lower()
    score = 0.0
    if title and title in anchor_text:
        score += 1.0
    if any(anchor_title and anchor_title in candidate_text for anchor_title in anchor_titles):
        score += 0.8
    if title:
        title_tokens = {
            token
            for token in title.replace("_", " ").split()
            if len(token) >= 3
        }
        anchor_tokens = set(anchor_text.replace("_", " ").split())
        if title_tokens:
            score += 0.4 * (len(title_tokens & anchor_tokens) / len(title_tokens))
    return score


def build_hybrid_weighted_graph(
    database: Database,
    graph_candidates: list[SearchResult],
    edge_threshold: float,
    *,
    semantic_weight: float = 0.65,
    lexical_weight: float = 0.35,
    query_floor: float = 0.30,
) -> dict[str, dict[str, float]]:
    """Build a query-conditioned graph from semantic, lexical, and hybrid signals.

    Args:
        database: Database containing candidate embeddings.
        graph_candidates: Candidates admitted to the local evidence graph.
        edge_threshold: Minimum semantic similarity for a semantic edge.
        semantic_weight: Weight for pairwise embedding similarity.
        lexical_weight: Weight for pairwise lexical overlap.
        query_floor: Minimum query-relevance multiplier retained for an edge.

    Returns:
        Weighted adjacency mapping.
    """
    ids = [candidate.id for candidate in graph_candidates]
    result = database.collection.get(ids=ids, include=["embeddings"])
    embeddings_list = result.get("embeddings")
    if embeddings_list is None or len(embeddings_list) == 0:
        return {doc_id: {} for doc_id in ids}

    embeddings = dict(zip(result["ids"], embeddings_list))
    token_sets = {
        candidate.id: set(tokens(candidate.text))
        for candidate in graph_candidates
    }
    query_scores = normalize_feature(
        {candidate.id: candidate.score for candidate in graph_candidates}
    )
    graph: dict[str, dict[str, float]] = {doc_id: {} for doc_id in ids}

    for left_index, left in enumerate(graph_candidates):
        for right in graph_candidates[left_index + 1:]:
            semantic = float(cosine_similarity(embeddings[left.id], embeddings[right.id]))
            lexical = lexical_overlap(token_sets[left.id], token_sets[right.id])
            if semantic < edge_threshold and lexical <= 0:
                continue

            relation = 0.0
            if semantic >= edge_threshold:
                relation += semantic_weight * semantic
            relation += lexical_weight * lexical
            if relation <= 0:
                continue

            # Hybrid retrieval is query-to-document signal. Multiplying pairwise
            # relation by both endpoint priors makes the Laplacian query-aware
            # without inventing labels or metadata.
            query_prior = (
                query_floor
                + (1.0 - query_floor)
                * ((query_scores.get(left.id, 0.0) * query_scores.get(right.id, 0.0)) ** 0.5)
            )
            weight = min(1.0, relation * query_prior)
            graph[left.id][right.id] = weight
            graph[right.id][left.id] = weight

    return graph


def lexical_overlap(left: set[str], right: set[str]) -> float:
    """Calculate pairwise lexical overlap for graph weighting.

    Args:
        left: Tokens from the first candidate.
        right: Tokens from the second candidate.

    Returns:
        Jaccard overlap score.
    """
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
