"""Orchestration engine for Noetic reconciliation.

The engine owns stateful dependencies and runs the production reconciliation
path: retrieve broad hybrid candidates, build a local evidence graph, and rank a
compact linked-evidence return set. Spectral partitioning, diffusion, and basin
scoring remain available as explicit diagnostics and as the alternate
`return_policy="basin"` path, but they are no longer part of the default
production return.

The central method is `Reconciler.reconcile()`. In default linked mode, it
retrieves the graph-sized candidate field directly, builds the local evidence
graph, and ranks linked support chunks. When
diagnostics are requested, it also computes spectral basins plus diffusion
metrics for inspection. Each intermediate structure is ordinary Python data:
lists of search results, adjacency dictionaries, energy dictionaries, basin
records, and result payloads.

Keeping this file thin is important. If the engine starts accumulating scoring
rules or matrix logic, the method becomes hard to audit. The engine should answer
"what happens next?" while the specialized modules answer "how is this step
computed?"

Key variables:
    `candidate_limit`: Number of first-stage hybrid results admitted into the
        local graph. This bounds the query-time graph computation.
    `hybrid_pool_limit`: Fixed semantic and lexical channel depth used by
        hybrid search before final candidate truncation. This keeps hybrid
        normalization stable when the graph candidate limit changes.
    `edge_threshold`: Minimum embedding similarity used by graph construction.
    `include_diagnostics`: Whether to run spectral partitioning, diffusion, and
        basin scoring for inspection.
    `diffusion_steps`: Number of diagnostic diffusion time steps run after
        energy initialization.
    `damping`: Fraction of node energy allowed to move across graph edges during
        each diffusion step.
    `graph_candidates`: The actual working field used for graph construction
        and linked-evidence ranking. It is exactly the hybrid top-k field
        retrieved by `candidate_limit`, not a later truncation of a wider list.
    `communities`: Spectral basin assignment for each graph candidate.
    `basins`: Scored evidence regions sorted by descending basin score.
    `return_policy`: Compact return strategy. `linked` preserves early hybrid
        anchors and promotes graph-connected evidence from the candidate field.
        `basin` returns representatives from the strongest diffused basin and
        automatically enables diagnostics.
    `anchor_count`: Number of leading hybrid candidates used as anchors by the
        linked-evidence ranker.
    `protect_anchors`: Whether those anchors are locked at the front of the
        linked-evidence return.
"""

from __future__ import annotations

from dataclasses import replace

from noetic_systems.database import Database
from noetic_systems.reconciliation.basins import build_basins, calculate_uncertainty
from noetic_systems.reconciliation.diffusion import (
    constrain_graph_to_communities,
    diffuse,
    seed_energy,
)
from noetic_systems.reconciliation.graph import (
    EMBEDDING_EDGE_THRESHOLD,
    GraphWeights,
    build_evidence_graph,
)
from noetic_systems.reconciliation.metrics import (
    calculate_dispersion,
    calculate_modularity,
    document_specificity,
    document_support,
)
from noetic_systems.reconciliation.models import Basin, EvidenceEdge
from noetic_systems.reconciliation.ranking import (
    rank_basin_documents,
    rank_linked_evidence,
)
from noetic_systems.reconciliation.result import ReconciliationResult
from noetic_systems.reconciliation.spectral import detect_communities
from noetic_systems.search.hybrid import HybridSearch


class Reconciler:
    """Resolve hybrid candidates into compact linked evidence.

    The class owns database and hybrid-search state. The reconciliation steps
    themselves live in functional modules so the algorithm is easy to inspect and
    test independently.
    """

    def __init__(
        self,
        database: Database,
        hybrid_search: HybridSearch | None = None,
        graph_weights: GraphWeights | None = None,
    ) -> None:
        """Initialize the reconciliation engine.

        Args:
            database: Database containing candidate documents and embeddings.
            hybrid_search: Optional preconfigured hybrid search instance.
            graph_weights: Optional corpus-level graph calibration.

        Returns:
            None.
        """
        self.database = database
        self.hybrid = hybrid_search or HybridSearch(database)
        self.graph_weights = graph_weights

    def hybrid_baseline(
        self,
        query: str,
        limit: int = 10,
        hybrid_pool_limit: int = 100,
    ) -> list[str]:
        """Return top-k documents from hybrid search without reconciliation.

        Args:
            query: Query text.
            limit: Maximum number of document ids to return.
            hybrid_pool_limit: Fixed semantic and lexical channel depth used by
                hybrid search before final truncation.

        Returns:
            Ranked document ids from raw hybrid retrieval.
        """
        results = self.hybrid.search(
            query,
            limit=limit,
            pool_limit=hybrid_pool_limit,
        )
        return [result.id for result in results]

    def reconcile(
        self,
        query: str,
        *,
        candidate_limit: int = 30,
        hybrid_pool_limit: int = 100,
        diffusion_steps: int = 10,
        damping: float = 0.85,
        edge_threshold: float = EMBEDDING_EDGE_THRESHOLD,
        return_policy: str = "linked",
        include_diagnostics: bool = False,
        anchor_count: int = 3,
        protect_anchors: bool = True,
    ) -> ReconciliationResult:
        """Run graph-based reconciliation over hybrid candidates.

        Args:
            query: Query text.
            candidate_limit: Number of hybrid candidates to retrieve and admit
                into the local graph.
            hybrid_pool_limit: Fixed semantic and lexical channel depth used by
                hybrid search before final candidate truncation.
            diffusion_steps: Number of fixed diffusion iterations.
            damping: Fraction of energy allowed to move across graph edges.
            edge_threshold: Minimum embedding similarity for a semantic edge.
            return_policy: Compact return strategy: `linked` or `basin`.
            include_diagnostics: Whether to run spectral, diffusion, and basin
                scoring even when the linked return policy is used.
            anchor_count: Number of leading hybrid candidates used as anchors.
            protect_anchors: Whether anchors receive a fixed score boost that
                keeps them at the front of the linked ranking.

        Returns:
            Reconciliation result containing compact return ids and optional
            basin diagnostics.
        """
        if return_policy not in {"linked", "basin"}:
            raise ValueError("return_policy must be 'linked' or 'basin'")

        graph_candidates = self.hybrid.search(
            query,
            limit=candidate_limit,
            pool_limit=hybrid_pool_limit,
        )
        if not graph_candidates:
            return empty_result(query)

        # Candidate admission is intentionally direct: the returned hybrid
        # top-k field is the graph field. Hybrid scoring can still use a fixed
        # internal pool so score normalization does not shift with output size.
        doc_index = {result.id: result for result in graph_candidates}
        graph, edges = build_evidence_graph(
            self.database,
            doc_index,
            edge_threshold,
            weights=self.graph_weights,
        )
        return_documents = tuple(
            rank_linked_evidence(
                graph_candidates,
                graph,
                anchor_count=anchor_count,
                protect_anchors=protect_anchors,
            )
        )
        query_score = {result.id: result.score for result in graph_candidates}
        support = document_support(graph)

        if return_policy == "linked" and not include_diagnostics:
            return linked_result(
                query,
                return_documents,
                {},
                query_score,
                support,
                edges,
            )

        communities = detect_communities(graph)
        if not communities:
            if return_policy == "linked":
                return linked_result(
                    query,
                    return_documents,
                    {},
                    query_score,
                    support,
                    edges,
                )
            return empty_result(query)

        # Initialize from retrieval rank, then let confidence move inside the
        # fixed spectral basins. Cross-basin edges helped define the partition,
        # but diffusion should not let one competing region feed another.
        energy = seed_energy(graph_candidates)
        basin_graph = constrain_graph_to_communities(graph, communities)
        for _ in range(diffusion_steps):
            energy = diffuse(energy, basin_graph, damping)

        basins = build_basins(communities, energy, graph)
        if not basins:
            if return_policy == "linked":
                return linked_result(
                    query,
                    return_documents,
                    {},
                    query_score,
                    support,
                    edges,
                )
            return empty_result(query)

        # The winner is chosen after region-level scoring, not raw retrieval rank.
        # Under the default linked return policy, this remains an inspection and
        # alternate-return signal rather than the final chunk selector.
        basins = sorted(basins, key=lambda basin: basin.score, reverse=True)
        modularity = calculate_modularity(graph, communities)
        dispersion = calculate_dispersion(energy)
        uncertainty = calculate_uncertainty(basins, modularity, dispersion)
        specificity = document_specificity(graph_candidates)

        ranked_winner_documents = rank_basin_documents(
            list(basins[0].documents),
            energy,
            specificity,
        )
        winner = replace(basins[0], documents=tuple(ranked_winner_documents))
        basins = [winner, *basins[1:]]
        if return_policy == "basin":
            return_documents = winner.documents

        return ReconciliationResult(
            query=query,
            winner=winner,
            basins=tuple(basins),
            diagnostics_included=True,
            return_policy=return_policy,
            return_documents=return_documents,
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
            edges=tuple(edges),
    )


def linked_result(
    query: str,
    return_documents: tuple[str, ...],
    specificity: dict[str, float],
    query_score: dict[str, float],
    support: dict[str, float],
    edges: list[EvidenceEdge],
) -> ReconciliationResult:
    """Return a production linked-evidence result without diagnostics.

    Args:
        query: Query text.
        return_documents: Ranked compact return ids.
        specificity: Specificity score by document id.
        query_score: Hybrid query score by document id.
        support: Weighted graph support by document id.
        edges: Evidence edges from graph construction.

    Returns:
        Reconciliation result for the benchmarked production path.
    """
    winner = Basin(
        id=0,
        label="linked-evidence",
        score=0.0,
        energy=0.0,
        documents=return_documents,
        cohesion=0.0,
        support=len(return_documents),
        duplicate_penalty=0.0,
    )
    return ReconciliationResult(
        query=query,
        winner=winner,
        basins=(),
        diagnostics_included=False,
        return_policy="linked",
        return_documents=return_documents,
        uncertainty=0.0,
        dispersion=0.0,
        modularity=0.0,
        document_energy={},
        document_specificity={
            doc_id: float(value)
            for doc_id, value in specificity.items()
        },
        document_query_score={
            doc_id: float(value)
            for doc_id, value in query_score.items()
        },
        document_support={doc_id: float(value) for doc_id, value in support.items()},
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
        diagnostics_included=False,
        return_policy="linked",
        return_documents=(),
        uncertainty=1.0,
        dispersion=1.0,
        modularity=0.0,
        document_energy={},
        document_specificity={},
        document_query_score={},
        document_support={},
        edges=(),
    )
