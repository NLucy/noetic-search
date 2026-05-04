"""Post-retrieval graph reconciliation over hybrid candidates."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .database import Database
from .hybrid_search import HybridSearch
from .semantic_search import SearchResult


METADATA_GROUP_KEYS = (
    "document_id",
    "url",
    "domain",
    "source",
    "title",
    "section",
    "author",
)
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
SPECTRAL_MIN_SPLIT_SIZE = 4
SPECTRAL_MAX_DEPTH = 1
SPECTRAL_MIN_SPLIT_MODULARITY = 0.10

CommunityMethod = Literal["spectral", "greedy"]
ReturnRanker = Literal["specificity", "purifier"]


@dataclass(frozen=True)
class EvidenceEdge:
    """Relationship between two candidate documents."""

    source: str
    target: str
    type: str
    weight: float
    reason: str


@dataclass(frozen=True)
class Basin:
    """Candidate region where evidence settles after diffusion."""

    id: int
    label: str
    score: float
    energy: float
    documents: tuple[str, ...]
    cohesion: float
    support: int
    source_breadth: float
    document_breadth: float
    duplicate_penalty: float
    metadata_bonus: float


@dataclass(frozen=True)
class ReconciliationResult:
    """Computed reconciliation result."""

    query: str
    winner: Basin
    basins: tuple[Basin, ...]
    uncertainty: float
    dispersion: float
    modularity: float
    document_energy: dict[str, float]
    document_specificity: dict[str, float]
    document_query_score: dict[str, float]
    document_support: dict[str, float]
    document_echo: dict[str, float]
    edges: tuple[EvidenceEdge, ...]

    def document_ids(self, k: int = 5) -> list[str]:
        """Return top-k document IDs from the winning basin."""
        return list(self.winner.documents[:k])

    def top_k_documents(self, k: int = 5) -> list[str]:
        """Backward-compatible alias for callers that expect document IDs."""
        return self.document_ids(k)

    def chunks(self, database: Database, k: int = 5) -> list[dict[str, Any]]:
        """Return LLM-ready chunks from the winning basin."""
        return [
            chunk
            for doc_id in self.document_ids(k)
            if (chunk := self._chunk(database, doc_id, include_basin=True))
        ]

    def strongest_basin(
        self,
        database: Database,
        k: int | None = None,
    ) -> dict[str, Any]:
        """Return the strongest basin with its chunks as the primary surface."""
        doc_ids = self.winner.documents if k is None else tuple(self.document_ids(k))
        chunks = [
            chunk
            for doc_id in doc_ids
            if (chunk := self._chunk(database, doc_id, include_basin=False))
        ]

        return {
            "query": self.query,
            "basin": self._basin_dict(self.winner),
            "chunks": chunks,
            "uncertainty": {
                "score": self.uncertainty,
                "level": "high" if self.uncertainty > 0.5 else "low",
            },
            "metrics": {
                "modularity": self.modularity,
                "dispersion": self.dispersion,
            },
        }

    def _chunk(
        self,
        database: Database,
        doc_id: str,
        *,
        include_basin: bool,
    ) -> dict[str, Any] | None:
        doc = database.get_by_id(doc_id)
        if not doc:
            return None

        chunk = {
            "id": doc["id"],
            "text": doc["text"],
            "metadata": doc["metadata"],
            "energy": self.document_energy.get(doc_id, 0.0),
            "specificity": self.document_specificity.get(doc_id, 0.0),
            "query_score": self.document_query_score.get(doc_id, 0.0),
            "support": self.document_support.get(doc_id, 0.0),
            "query_echo": self.document_echo.get(doc_id, 0.0),
        }
        if include_basin:
            chunk["basin"] = self.winner.label
            chunk["basin_score"] = self.winner.score
        return chunk

    def evidence_field(self, max_basins: int = 3, max_edges: int = 12) -> dict[str, Any]:
        """Return the reconciled evidence field for an LLM or caller."""
        uncertainty_explanation = []
        if self.uncertainty > 0.5:
            if len(self.basins) > 1 and self.basins[0].score:
                competition = self.basins[1].score / self.basins[0].score
                if competition > 0.5:
                    uncertainty_explanation.append(
                        f"competing basin has {competition:.1%} as much field score"
                    )
            if self.dispersion > 0.4:
                uncertainty_explanation.append("candidates are scattered")
            if self.modularity < 0.3:
                uncertainty_explanation.append("weak graph structure")

        return {
            "query": self.query,
            "winning_basin": self._basin_dict(self.winner),
            "competing_basins": [
                self._basin_dict(basin)
                for basin in self.basins[1:max_basins]
            ],
            "support_edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.type,
                    "weight": edge.weight,
                    "reason": edge.reason,
                }
                for edge in self._top_edges_for(self.winner.documents, max_edges)
            ],
            "uncertainty": {
                "score": self.uncertainty,
                "level": "high" if self.uncertainty > 0.5 else "low",
                "reasons": uncertainty_explanation,
            },
            "metrics": {
                "modularity": self.modularity,
                "dispersion": self.dispersion,
            },
        }

    def evidence(self, max_basins: int = 3) -> dict[str, Any]:
        """Backward-compatible alias for the evidence field."""
        return self.evidence_field(max_basins=max_basins)

    def _basin_dict(self, basin: Basin) -> dict[str, Any]:
        return {
            "id": basin.id,
            "label": basin.label,
            "score": basin.score,
            "energy": basin.energy,
            "documents": list(basin.documents),
            "cohesion": basin.cohesion,
            "support": basin.support,
            "source_breadth": basin.source_breadth,
            "document_breadth": basin.document_breadth,
            "duplicate_penalty": basin.duplicate_penalty,
            "metadata_bonus": basin.metadata_bonus,
        }

    def _top_edges_for(
        self,
        documents: tuple[str, ...],
        max_edges: int,
    ) -> list[EvidenceEdge]:
        document_set = set(documents)
        edges = [
            edge
            for edge in self.edges
            if edge.source in document_set and edge.target in document_set
        ]
        return sorted(edges, key=lambda edge: edge.weight, reverse=True)[:max_edges]


class Reconciler:
    """Reconcile hybrid candidates into evidence basins."""

    def __init__(
        self,
        database: Database,
        hybrid_search: HybridSearch | None = None,
    ) -> None:
        """Initialize reconciliation engine."""
        self.database = database
        self.hybrid = hybrid_search or HybridSearch(database)

    def hybrid_baseline(
        self,
        query: str,
        limit: int = 10,
    ) -> list[str]:
        """Return top-k documents from hybrid search without reconciliation."""
        results = self.hybrid.search(query, limit=limit)
        return [r.id for r in results]

    def reconcile(
        self,
        query: str,
        *,
        candidate_limit: int = 50,
        result_limit: int = 30,
        diffusion_steps: int = 10,
        damping: float = 0.85,
        edge_threshold: float = EMBEDDING_EDGE_THRESHOLD,
        community_method: CommunityMethod = "spectral",
        return_ranker: ReturnRanker = "specificity",
    ) -> ReconciliationResult:
        """Run graph-based reconciliation."""
        candidates = self.hybrid.search(query, limit=candidate_limit)
        if not candidates:
            return self._empty_result(query)

        graph_candidates = self._select_graph_candidates(candidates, result_limit)
        doc_index = {result.id: result for result in graph_candidates}
        graph, edges = self._build_evidence_graph(doc_index, edge_threshold)
        communities = self._detect_communities(graph, method=community_method)
        if not communities:
            return self._empty_result(query)

        energy = self._seed_energy(graph_candidates)
        for _ in range(diffusion_steps):
            energy = self._diffuse(energy, graph, damping)

        specificity = self._document_specificity(graph_candidates)
        query_score = {result.id: result.score for result in graph_candidates}
        support = self._document_support(graph)
        echo = self._query_echo(query, graph_candidates)
        basins = self._build_basins(
            communities,
            energy,
            specificity,
            query_score,
            support,
            echo,
            return_ranker,
            graph,
            doc_index,
        )
        if not basins:
            return self._empty_result(query)

        basins = sorted(basins, key=lambda basin: basin.score, reverse=True)
        modularity = self._calculate_modularity(graph, communities)
        dispersion = self._calculate_dispersion(energy)
        uncertainty = self._calculate_uncertainty(basins, modularity, dispersion)

        return ReconciliationResult(
            query=query,
            winner=basins[0],
            basins=tuple(basins),
            uncertainty=uncertainty,
            dispersion=dispersion,
            modularity=modularity,
            document_energy={doc_id: float(value) for doc_id, value in energy.items()},
            document_specificity={
                doc_id: float(value)
                for doc_id, value in specificity.items()
            },
            document_query_score={
                doc_id: float(value)
                for doc_id, value in query_score.items()
            },
            document_support={doc_id: float(value) for doc_id, value in support.items()},
            document_echo={doc_id: float(value) for doc_id, value in echo.items()},
            edges=tuple(edges),
        )

    def _empty_result(self, query: str) -> ReconciliationResult:
        return ReconciliationResult(
            query=query,
            winner=Basin(0, "empty", 0.0, 0.0, (), 0.0, 0, 0.0, 0.0, 0.0, 0.0),
            basins=(),
            uncertainty=1.0,
            dispersion=1.0,
            modularity=0.0,
            document_energy={},
            document_specificity={},
            document_query_score={},
            document_support={},
            document_echo={},
            edges=(),
        )

    def _select_graph_candidates(
        self,
        candidates: list[SearchResult],
        result_limit: int,
    ) -> list[SearchResult]:
        """Select graph candidates with ordinary metadata diversity."""
        selected: list[SearchResult] = []
        selected_ids: set[str] = set()

        def add(result: SearchResult) -> None:
            if result.id in selected_ids or len(selected) >= result_limit:
                return
            selected.append(result)
            selected_ids.add(result.id)

        for result in candidates[: min(10, result_limit)]:
            add(result)

        grouped: dict[str, list[SearchResult]] = defaultdict(list)
        for result in candidates:
            grouped[self._candidate_group_key(result)].append(result)

        group_items = sorted(
            grouped.items(),
            key=lambda item: max(result.score for result in item[1]),
            reverse=True,
        )
        round_index = 0
        while len(selected) < result_limit:
            added = False
            for _, group in group_items:
                if round_index < len(group):
                    before = len(selected)
                    add(group[round_index])
                    added = added or len(selected) > before
                    if len(selected) >= result_limit:
                        break
            if not added:
                break
            round_index += 1

        for result in candidates:
            add(result)
            if len(selected) >= result_limit:
                break

        return selected

    def _candidate_group_key(self, result: SearchResult) -> str:
        """Group candidates by ordinary metadata only."""
        metadata = result.metadata
        for key in METADATA_GROUP_KEYS:
            value = metadata.get(key)
            if value:
                return f"{key}:{value}"
        return result.id

    def _build_evidence_graph(
        self,
        doc_index: dict[str, SearchResult],
        threshold: float,
    ) -> tuple[dict[str, dict[str, float]], list[EvidenceEdge]]:
        """Build an embedding and metadata evidence graph."""
        ids = list(doc_index.keys())
        result = self.database.collection.get(ids=ids, include=["embeddings"])
        embeddings_list = result.get("embeddings")
        if embeddings_list is None or len(embeddings_list) == 0:
            return {doc_id: {} for doc_id in ids}, []

        embeddings = dict(zip(result["ids"], embeddings_list))
        graph: dict[str, dict[str, float]] = {doc_id: {} for doc_id in ids}
        edges: list[EvidenceEdge] = []

        for i, id1 in enumerate(ids):
            for id2 in ids[i + 1:]:
                similarity = float(
                    self._cosine_similarity(embeddings[id1], embeddings[id2])
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

                metadata_weight = self._metadata_edge_weight(
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
            current = graph[edge.source].get(edge.target, 0.0)
            graph[edge.source][edge.target] = min(1.0, current + edge.weight)
            graph[edge.target][edge.source] = graph[edge.source][edge.target]

        return graph, edges

    def _metadata_edge_weight(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        similarity: float,
    ) -> float:
        """Weight shared ordinary metadata without requiring custom labels."""
        weight = 0.0
        for key, key_weight in STRONG_METADATA_WEIGHTS.items():
            if self._metadata_equal(left, right, key):
                weight += key_weight
        if similarity >= CONTEXT_METADATA_MIN_SIMILARITY:
            for key, key_weight in CONTEXT_METADATA_WEIGHTS.items():
                if self._metadata_equal(left, right, key):
                    weight += key_weight
        return min(MAX_METADATA_EDGE_WEIGHT, weight)

    def _metadata_equal(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        key: str,
    ) -> bool:
        return bool(left.get(key) and left.get(key) == right.get(key))

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def _detect_communities(
        self,
        graph: dict[str, dict[str, float]],
        method: CommunityMethod = "spectral",
    ) -> dict[str, int]:
        """Detect communities in the candidate graph."""
        if method == "spectral":
            communities = self._detect_spectral_communities(graph)
            if communities:
                return communities
        return self._detect_greedy_communities(graph)

    def _detect_greedy_communities(
        self,
        graph: dict[str, dict[str, float]],
    ) -> dict[str, int]:
        """Detect communities using greedy modularity optimization."""
        communities = {node: i for i, node in enumerate(graph.keys())}
        if len(graph) < 2:
            return communities

        improved = True
        iterations = 0
        while improved and iterations < 10:
            improved = False
            iterations += 1
            for node in graph.keys():
                current_comm = communities[node]
                best_comm = current_comm
                best_gain = 0.0
                neighbor_comms = {
                    communities[neighbor]
                    for neighbor in graph[node].keys()
                }
                for comm in neighbor_comms:
                    if comm == current_comm:
                        continue
                    gain = self._modularity_gain(
                        node,
                        current_comm,
                        comm,
                        communities,
                        graph,
                    )
                    if gain > best_gain:
                        best_gain = gain
                        best_comm = comm
                if best_comm != current_comm:
                    communities[node] = best_comm
                    improved = True

        return communities

    def _detect_spectral_communities(
        self,
        graph: dict[str, dict[str, float]],
    ) -> dict[str, int]:
        """Detect communities by recursively bisecting the normalized Laplacian."""
        nodes = list(graph)
        if len(nodes) < 2:
            return {node: index for index, node in enumerate(nodes)}

        partitions = self._spectral_partition(nodes, graph)
        communities: dict[str, int] = {}
        for comm_id, partition in enumerate(partitions):
            for node in partition:
                communities[node] = comm_id
        return communities

    def _spectral_partition(
        self,
        nodes: list[str],
        graph: dict[str, dict[str, float]],
        *,
        min_size: int = SPECTRAL_MIN_SPLIT_SIZE,
        max_depth: int = SPECTRAL_MAX_DEPTH,
        depth: int = 0,
    ) -> list[list[str]]:
        if len(nodes) <= min_size or depth >= max_depth:
            return [nodes]

        left, right = self._fiedler_split(nodes, graph)
        if not left or not right:
            return [nodes]
        if min(len(left), len(right)) < min_size:
            return [nodes]
        if self._split_modularity(left, right, graph) <= SPECTRAL_MIN_SPLIT_MODULARITY:
            return [nodes]

        return (
            self._spectral_partition(
                left,
                graph,
                min_size=min_size,
                max_depth=max_depth,
                depth=depth + 1,
            )
            + self._spectral_partition(
                right,
                graph,
                min_size=min_size,
                max_depth=max_depth,
                depth=depth + 1,
            )
        )

    def _fiedler_split(
        self,
        nodes: list[str],
        graph: dict[str, dict[str, float]],
    ) -> tuple[list[str], list[str]]:
        adjacency = self._adjacency_matrix(nodes, graph)
        degrees = adjacency.sum(axis=1)
        if float(degrees.sum()) == 0.0:
            return [], []

        inv_sqrt = np.zeros_like(degrees)
        nonzero = degrees > 0
        inv_sqrt[nonzero] = 1.0 / np.sqrt(degrees[nonzero])
        normalized = np.eye(len(nodes)) - (
            inv_sqrt[:, None] * adjacency * inv_sqrt[None, :]
        )
        eigenvalues, eigenvectors = np.linalg.eigh(normalized)
        if len(eigenvalues) < 2:
            return [], []

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

    def _adjacency_matrix(
        self,
        nodes: list[str],
        graph: dict[str, dict[str, float]],
    ) -> np.ndarray:
        index = {node: position for position, node in enumerate(nodes)}
        adjacency = np.zeros((len(nodes), len(nodes)), dtype=float)
        for source in nodes:
            source_index = index[source]
            for target, weight in graph.get(source, {}).items():
                target_index = index.get(target)
                if target_index is not None:
                    adjacency[source_index, target_index] = float(weight)
        return np.maximum(adjacency, adjacency.T)

    def _split_modularity(
        self,
        left: list[str],
        right: list[str],
        graph: dict[str, dict[str, float]],
    ) -> float:
        total_weight = sum(
            sum(neighbors.values())
            for neighbors in graph.values()
        ) / 2.0
        if total_weight == 0.0:
            return 0.0

        modularity = 0.0
        for group in (set(left), set(right)):
            for source in group:
                source_degree = sum(graph.get(source, {}).values())
                for target in group:
                    target_degree = sum(graph.get(target, {}).values())
                    weight = graph.get(source, {}).get(target, 0.0)
                    expected = (source_degree * target_degree) / (2.0 * total_weight)
                    modularity += weight - expected
        return float(modularity / (2.0 * total_weight))

    def _modularity_gain(
        self,
        node: str,
        from_comm: int,
        to_comm: int,
        communities: dict[str, int],
        graph: dict[str, dict[str, float]],
    ) -> float:
        edges_to_from = 0.0
        edges_to_to = 0.0
        for neighbor, weight in graph[node].items():
            if communities[neighbor] == from_comm:
                edges_to_from += weight
            elif communities[neighbor] == to_comm:
                edges_to_to += weight
        return edges_to_to - edges_to_from

    def _seed_energy(self, results: list[SearchResult]) -> dict[str, float]:
        energy = {}
        for rank, result in enumerate(results):
            energy[result.id] = result.score / (rank + 1)
        total = sum(energy.values())
        if total > 0:
            energy = {doc_id: e / total for doc_id, e in energy.items()}
        return energy

    def _diffuse(
        self,
        energy: dict[str, float],
        graph: dict[str, dict[str, float]],
        damping: float,
    ) -> dict[str, float]:
        next_energy = {
            doc_id: (1 - damping) * value
            for doc_id, value in energy.items()
        }
        for doc_id, neighbors in graph.items():
            if not neighbors:
                next_energy[doc_id] += damping * energy[doc_id]
                continue
            total_weight = sum(neighbors.values())
            for neighbor_id, weight in neighbors.items():
                next_energy[neighbor_id] += (
                    damping * energy[doc_id] * (weight / total_weight)
                )
        total = sum(next_energy.values())
        if total > 0:
            next_energy = {
                doc_id: value / total
                for doc_id, value in next_energy.items()
            }
        return next_energy

    def _build_basins(
        self,
        communities: dict[str, int],
        energy: dict[str, float],
        specificity: dict[str, float],
        query_score: dict[str, float],
        support: dict[str, float],
        echo: dict[str, float],
        return_ranker: ReturnRanker,
        graph: dict[str, dict[str, float]],
        doc_index: dict[str, SearchResult],
    ) -> list[Basin]:
        grouped: dict[int, list[tuple[str, float]]] = defaultdict(list)
        for doc_id, comm_id in communities.items():
            grouped[comm_id].append((doc_id, energy.get(doc_id, 0.0)))

        basins = []
        for comm_id, docs in grouped.items():
            energy_by_doc = dict(docs)
            doc_ids = self._rank_basin_documents(
                list(energy_by_doc),
                energy_by_doc,
                specificity,
                query_score,
                support,
                echo,
                return_ranker,
            )
            cohesion = self._calculate_cohesion(doc_ids, graph)
            source_breadth = self._source_breadth(doc_ids, doc_index)
            document_breadth = self._document_breadth(doc_ids, doc_index)
            duplicate_penalty = self._duplicate_penalty(doc_ids, graph)
            metadata_bonus = 0.15 * source_breadth + 0.15 * document_breadth
            basin_energy = float(sum(energy_by_doc.values()))
            support_score = min(1.0, len(doc_ids) / 6.0)
            score = (
                0.45 * basin_energy
                + 0.25 * support_score
                + 0.20 * cohesion
                + metadata_bonus
                - duplicate_penalty
            )

            basins.append(
                Basin(
                    id=comm_id,
                    label=f"basin-{comm_id}",
                    score=float(max(0.0, min(1.0, score))),
                    energy=basin_energy,
                    documents=tuple(doc_ids),
                    cohesion=float(cohesion),
                    support=len(doc_ids),
                    source_breadth=float(source_breadth),
                    document_breadth=float(document_breadth),
                    duplicate_penalty=float(duplicate_penalty),
                    metadata_bonus=float(metadata_bonus),
                )
            )
        return basins

    def _rank_basin_documents(
        self,
        doc_ids: list[str],
        energy: dict[str, float],
        specificity: dict[str, float],
        query_score: dict[str, float],
        support: dict[str, float],
        echo: dict[str, float],
        return_ranker: ReturnRanker,
    ) -> list[str]:
        """Rank basin members for return with a small purification pass."""
        max_energy = max((energy.get(doc_id, 0.0) for doc_id in doc_ids), default=0.0)
        max_specificity = max(
            (specificity.get(doc_id, 0.0) for doc_id in doc_ids),
            default=0.0,
        )
        max_query = max((query_score.get(doc_id, 0.0) for doc_id in doc_ids), default=0.0)
        max_support = max((support.get(doc_id, 0.0) for doc_id in doc_ids), default=0.0)

        def score(doc_id: str) -> tuple[float, float]:
            energy_score = (
                energy.get(doc_id, 0.0) / max_energy
                if max_energy > 0
                else 0.0
            )
            specificity_score = (
                specificity.get(doc_id, 0.0) / max_specificity
                if max_specificity > 0
                else 0.0
            )
            query_affinity = (
                query_score.get(doc_id, 0.0) / max_query
                if max_query > 0
                else 0.0
            )
            support_score = (
                support.get(doc_id, 0.0) / max_support
                if max_support > 0
                else 0.0
            )
            echo_penalty = echo.get(doc_id, 0.0)
            hub_penalty = max(0.0, support_score - 0.65)
            if return_ranker == "purifier":
                rank_score = (
                    0.38 * specificity_score
                    + 0.24 * query_affinity
                    + 0.18 * energy_score
                    + 0.12 * support_score
                    - 0.20 * echo_penalty
                    - 0.10 * hub_penalty
                )
            else:
                rank_score = 0.10 * energy_score + 0.90 * specificity_score
            return (
                rank_score,
                energy.get(doc_id, 0.0),
            )

        return sorted(doc_ids, key=score, reverse=True)

    def _document_support(self, graph: dict[str, dict[str, float]]) -> dict[str, float]:
        """Measure local graph support for each candidate."""
        return {
            doc_id: float(sum(neighbors.values()))
            for doc_id, neighbors in graph.items()
        }

    def _query_echo(
        self,
        query: str,
        results: list[SearchResult],
    ) -> dict[str, float]:
        """Penalize candidates that mostly echo the query wording."""
        query_tokens = set(self._tokens(query))
        if not query_tokens:
            return {result.id: 0.0 for result in results}

        echo: dict[str, float] = {}
        for result in results:
            tokens = set(self._tokens(result.text))
            if not tokens:
                echo[result.id] = 0.0
                continue
            query_overlap = len(tokens & query_tokens) / len(query_tokens)
            text_overlap = len(tokens & query_tokens) / len(tokens)
            echo[result.id] = float(0.65 * query_overlap + 0.35 * text_overlap)
        return echo

    def _document_specificity(self, results: list[SearchResult]) -> dict[str, float]:
        """Estimate candidate information density without labels."""
        token_sets = {
            result.id: set(self._tokens(result.text))
            for result in results
        }
        document_frequency: dict[str, int] = defaultdict(int)
        for tokens in token_sets.values():
            for token in tokens:
                document_frequency[token] += 1

        total = len(results)
        specificity: dict[str, float] = {}
        for result in results:
            tokens = token_sets[result.id]
            if not tokens:
                specificity[result.id] = 0.0
                continue
            specificity[result.id] = float(
                sum(
                    math.log((1 + total) / (1 + document_frequency[token]))
                    for token in tokens
                ) / len(tokens)
            )
        return specificity

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]{3,}", text.lower())

    def _source_breadth(
        self,
        doc_ids: list[str],
        doc_index: dict[str, SearchResult],
    ) -> float:
        sources = {
            str(doc_index[doc_id].metadata.get("source"))
            for doc_id in doc_ids
            if doc_index[doc_id].metadata.get("source")
        }
        return len(sources) / len(doc_ids) if doc_ids else 0.0

    def _document_breadth(
        self,
        doc_ids: list[str],
        doc_index: dict[str, SearchResult],
    ) -> float:
        parent_ids = {
            str(
                doc_index[doc_id].metadata.get("document_id")
                or doc_index[doc_id].metadata.get("url")
                or doc_id
            )
            for doc_id in doc_ids
        }
        return len(parent_ids) / len(doc_ids) if doc_ids else 0.0

    def _duplicate_penalty(
        self,
        doc_ids: list[str],
        graph: dict[str, dict[str, float]],
    ) -> float:
        if len(doc_ids) < 2:
            return 0.0
        near_duplicate_edges = 0
        possible_edges = 0
        for i, left in enumerate(doc_ids):
            for right in doc_ids[i + 1:]:
                possible_edges += 1
                if graph.get(left, {}).get(right, 0.0) >= 0.9:
                    near_duplicate_edges += 1
        if possible_edges == 0:
            return 0.0
        return min(0.35, 0.45 * (near_duplicate_edges / possible_edges))

    def _calculate_cohesion(
        self,
        doc_ids: list[str],
        graph: dict[str, dict[str, float]],
    ) -> float:
        if len(doc_ids) < 2:
            return 0.0
        total_weight = 0.0
        count = 0
        for i, left in enumerate(doc_ids):
            for right in doc_ids[i + 1:]:
                if right in graph.get(left, {}):
                    total_weight += graph[left][right]
                    count += 1
        return total_weight / count if count else 0.0

    def _calculate_modularity(
        self,
        graph: dict[str, dict[str, float]],
        communities: dict[str, int],
    ) -> float:
        if not graph or not communities:
            return 0.0
        total_weight = sum(
            sum(neighbors.values())
            for neighbors in graph.values()
        ) / 2.0
        if total_weight == 0:
            return 0.0

        modularity = 0.0
        for node1, comm1 in communities.items():
            for node2, comm2 in communities.items():
                if comm1 != comm2:
                    continue
                weight = graph.get(node1, {}).get(node2, 0.0)
                deg1 = sum(graph.get(node1, {}).values())
                deg2 = sum(graph.get(node2, {}).values())
                expected = (deg1 * deg2) / (2.0 * total_weight)
                modularity += weight - expected
        return float(modularity / (2.0 * total_weight))

    def _calculate_dispersion(self, energy: dict[str, float]) -> float:
        if not energy:
            return 1.0
        values = list(energy.values())
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return float(min(1.0, math.sqrt(variance)))

    def _calculate_uncertainty(
        self,
        basins: list[Basin],
        modularity: float,
        dispersion: float,
    ) -> float:
        if not basins:
            return 1.0
        competition = 0.0
        if len(basins) > 1 and basins[0].score > 0:
            competition = basins[1].score / basins[0].score
        modularity_uncertainty = max(0.0, 1.0 - modularity)
        uncertainty = (
            0.45 * competition
            + 0.30 * modularity_uncertainty
            + 0.25 * dispersion
        )
        return float(max(0.0, min(1.0, uncertainty)))
