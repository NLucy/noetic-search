"""Orchestration engine for Noetic reconciliation.

The engine owns stateful dependencies, retrieves a broad hybrid candidate set,
and then calls the functional graph, diffusion, spectral, basin, and result
modules in order. We keep orchestration separate from the math so the algorithm
can be inspected step by step and each methodology can be tested without a large
stateful class.

The central method is `Reconciler.reconcile()`. It retrieves more candidates
than it plans to return, selects a graph-sized working set, builds the local
evidence graph, detects communities, diffuses energy, scores basins, and returns
a `ReconciliationResult`. Each intermediate structure is ordinary Python data:
lists of search results, adjacency dictionaries, energy dictionaries, community
assignments, basin records, and result payloads.

Keeping this file thin is important. If the engine starts accumulating scoring
rules or matrix logic, the method becomes hard to audit. The engine should answer
"what happens next?" while the specialized modules answer "how is this step
computed?"
"""

from __future__ import annotations

from noetic_systems.database import Database
from noetic_systems.reconciliation.basins import build_basins
from noetic_systems.reconciliation.candidates import select_graph_candidates
from noetic_systems.reconciliation.diffusion import diffuse
from noetic_systems.reconciliation.graph import (
    EMBEDDING_EDGE_THRESHOLD,
    build_evidence_graph,
)
from noetic_systems.reconciliation.metrics import (
    calculate_dispersion,
    calculate_modularity,
    document_specificity,
    document_support,
    query_echo,
)
from noetic_systems.reconciliation.models import Basin, ReturnRanker
from noetic_systems.reconciliation.result import ReconciliationResult
from noetic_systems.reconciliation.seeding import seed_energy
from noetic_systems.reconciliation.spectral import detect_communities
from noetic_systems.reconciliation.uncertainty import calculate_uncertainty
from noetic_systems.search.hybrid import HybridSearch


class Reconciler:
    """Resolve hybrid candidates into evidence basins.

    The class owns database and hybrid-search state. The reconciliation steps
    themselves live in functional modules so the algorithm is easy to inspect and
    test independently.
    """

    def __init__(
        self,
        database: Database,
        hybrid_search: HybridSearch | None = None,
    ) -> None:
        """Initialize the reconciliation engine.

        Args:
            database: Database containing candidate documents and embeddings.
            hybrid_search: Optional preconfigured hybrid search instance.

        Returns:
            None.
        """
        self.database = database
        self.hybrid = hybrid_search or HybridSearch(database)

    def hybrid_baseline(
        self,
        query: str,
        limit: int = 10,
    ) -> list[str]:
        """Return top-k documents from hybrid search without reconciliation.

        Args:
            query: Query text.
            limit: Maximum number of document ids to return.

        Returns:
            Ranked document ids from raw hybrid retrieval.
        """
        results = self.hybrid.search(query, limit=limit)
        return [result.id for result in results]

    def reconcile(
        self,
        query: str,
        *,
        candidate_limit: int = 50,
        result_limit: int = 30,
        diffusion_steps: int = 10,
        damping: float = 0.85,
        edge_threshold: float = EMBEDDING_EDGE_THRESHOLD,
        return_ranker: ReturnRanker = "specificity",
    ) -> ReconciliationResult:
        """Run graph-based reconciliation over hybrid candidates.

        Args:
            query: Query text.
            candidate_limit: Number of hybrid candidates to retrieve.
            result_limit: Number of candidates retained for the local graph.
            diffusion_steps: Number of fixed diffusion iterations.
            damping: Fraction of energy allowed to move across graph edges.
            edge_threshold: Minimum embedding similarity for a semantic edge.
            return_ranker: Strategy for ranking documents inside the winning basin.

        Returns:
            Reconciliation result containing basins, chunk scores, and graph metrics.
        """
        candidates = self.hybrid.search(query, limit=candidate_limit)
        if not candidates:
            return empty_result(query)

        # The graph is built from a broad-but-bounded field, not from raw top-k.
        graph_candidates = select_graph_candidates(candidates, result_limit)
        doc_index = {result.id: result for result in graph_candidates}
        graph, edges = build_evidence_graph(self.database, doc_index, edge_threshold)
        communities = detect_communities(graph)
        if not communities:
            return empty_result(query)

        # Diffusion is a discrete-time propagation over the fixed evidence graph.
        energy = seed_energy(graph_candidates)
        for _ in range(diffusion_steps):
            energy = diffuse(energy, graph, damping)

        # These per-document signals feed both basin scoring and final chunk ranking.
        specificity = document_specificity(graph_candidates)
        query_score = {result.id: result.score for result in graph_candidates}
        support = document_support(graph)
        echo = query_echo(query, graph_candidates)
        basins = build_basins(
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
            return empty_result(query)

        # The winner is chosen after region-level scoring, not raw retrieval rank.
        basins = sorted(basins, key=lambda basin: basin.score, reverse=True)
        modularity = calculate_modularity(graph, communities)
        dispersion = calculate_dispersion(energy)
        uncertainty = calculate_uncertainty(basins, modularity, dispersion)

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


def empty_result(query: str) -> ReconciliationResult:
    """Return a structurally valid empty reconciliation result.

    Args:
        query: Query text associated with the failed reconciliation.

    Returns:
        Empty result with maximal uncertainty.
    """
    return ReconciliationResult(
        query=query,
        winner=Basin(0, "empty", 0.0, 0.0, (), 0.0, 0, 0.0),
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
