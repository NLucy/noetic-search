"""Public result surfaces for reconciled evidence fields.

The result object is the handoff point between search and downstream callers. It
can return linked evidence chunks for compact LLM context, or expose the full
evidence field with competing basins, support edges, and uncertainty. We
keep this logic separate from reconciliation so the search computation and
external payload shapes do not become tangled.

There are three useful public surfaces. `document_ids()` returns the compact
ranked ids selected by the return policy. `chunks()` materializes those ids into
LLM-ready text, metadata, and scores. `evidence_field()` exposes the inspection
view: linked return ids, optional basin diagnostics, support edges, metrics, and
uncertainty reasons. The same computed result can therefore serve a production
prompt, a debugging interface, or an evaluation harness.

The result also preserves per-document scores. Energy, specificity, query score,
and graph support remain available after reconciliation so final chunks can be
audited without rerunning the pipeline.

Key variables:
    `winner`: The selected basin after scoring, or the linked-evidence return
        surface when diagnostics are not included.
    `basins`: Diagnostic basins ordered by score. Empty in the default linked
        production path.
    `diagnostics_included`: Whether basin diagnostics were computed.
    `return_policy`: Compact return policy used by `document_ids()`.
    `return_documents`: Ranked document ids selected for compact return.
    `uncertainty`: Structural caution score. It is not a correctness
        probability.
    `document_energy`: Final diffused energy by document id.
    `document_specificity`: Local information-density score by document id.
    `document_query_score`: Original hybrid retrieval score by document id.
    `document_support`: Weighted graph degree by document id.
    `edges`: Edge inspection records from graph construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noetic_systems.database import Database
from noetic_systems.reconciliation.models import Basin, EvidenceEdge


@dataclass(frozen=True)
class ReconciliationResult:
    """Computed reconciliation result.

    Attributes:
        query: Query used to produce the result.
        winner: Highest-scoring basin, or linked-evidence surface.
        basins: Detected diagnostic basins sorted by descending score.
        diagnostics_included: Whether basin diagnostics were computed.
        return_policy: Compact return policy used by `document_ids()`.
        return_documents: Ranked document ids selected for compact return.
        uncertainty: Structural uncertainty score in the `[0, 1]` interval.
        dispersion: Diffused-energy dispersion score.
        modularity: Graph modularity for the detected communities.
        document_energy: Settled energy by document id.
        document_specificity: Specificity score by document id.
        document_query_score: Hybrid query score by document id.
        document_support: Graph support by document id.
        edges: Evidence edges used to build the candidate graph.
    """

    query: str
    winner: Basin
    basins: tuple[Basin, ...]
    diagnostics_included: bool
    return_policy: str
    return_documents: tuple[str, ...]
    uncertainty: float
    dispersion: float
    modularity: float
    document_energy: dict[str, float]
    document_specificity: dict[str, float]
    document_query_score: dict[str, float]
    document_support: dict[str, float]
    edges: tuple[EvidenceEdge, ...]

    def document_ids(self, k: int = 5) -> list[str]:
        """Return top-k document ids from the compact return policy.

        Args:
            k: Maximum number of document ids to return.

        Returns:
            Ranked document ids.
        """
        return list(self.return_documents[:k])

    def chunks(self, database: Database, k: int = 5) -> list[dict[str, Any]]:
        """Return LLM-ready chunks from the compact return policy.

        Args:
            database: Database used to materialize chunk text and metadata.
            k: Maximum number of chunks to return.

        Returns:
            Chunk dictionaries enriched with reconciliation scores.
        """
        return [
            chunk
            for doc_id in self.document_ids(k)
            if (chunk := self.chunk(database, doc_id, include_basin=True))
        ]

    def strongest_basin(
        self,
        database: Database,
        k: int | None = None,
    ) -> dict[str, Any]:
        """Return the strongest diagnostic basin or linked evidence surface.

        Args:
            database: Database used to materialize chunk text and metadata.
            k: Optional maximum number of chunks. When omitted, all selected
                documents are returned.

        Returns:
            Structured basin-compatible payload.
        """
        doc_ids = self.winner.documents if k is None else self.winner.documents[:k]
        chunks = [
            chunk
            for doc_id in doc_ids
            if (chunk := self.chunk(database, doc_id, include_basin=False))
        ]

        return {
            "query": self.query,
            "basin": self.basin_dict(self.winner),
            "chunks": chunks,
            "uncertainty": {
                "score": self.uncertainty,
                "level": self.uncertainty_level(),
            },
            "metrics": {
                "modularity": self.modularity,
                "dispersion": self.dispersion,
            },
        }

    def chunk(
        self,
        database: Database,
        doc_id: str,
        *,
        include_basin: bool,
    ) -> dict[str, Any] | None:
        """Materialize one document as a scored chunk.

        Args:
            database: Database used to fetch the document.
            doc_id: Document identifier.
            include_basin: Whether to add winning-basin label and score.

        Returns:
            Scored chunk dictionary, or `None` when the document is absent.
        """
        doc = database.get_by_id(doc_id)
        if not doc:
            return None

        # Keep the chunk payload plain. These fields are enough for an LLM prompt
        # or a human inspection view to see why the chunk was returned.
        chunk = {
            "id": doc["id"],
            "text": doc["text"],
            "metadata": doc["metadata"],
            "energy": self.document_energy.get(doc_id, 0.0),
            "specificity": self.document_specificity.get(doc_id, 0.0),
            "query_score": self.document_query_score.get(doc_id, 0.0),
            "support": self.document_support.get(doc_id, 0.0),
        }
        if include_basin:
            chunk["return_policy"] = self.return_policy
            chunk["basin"] = self.basin_label_for(doc_id)
            chunk["basin_score"] = self.basin_score_for(doc_id)
        return chunk

    def basin_label_for(self, doc_id: str) -> str:
        """Return the basin label containing a document.

        Args:
            doc_id: Document identifier.

        Returns:
            Basin label, or `unassigned` when no basin contains the document.
        """
        for basin in self.basins:
            if doc_id in basin.documents:
                return basin.label
        if self.return_policy == "linked" and doc_id in self.return_documents:
            return "linked-evidence"
        return "unassigned"

    def basin_score_for(self, doc_id: str) -> float:
        """Return the basin score containing a document.

        Args:
            doc_id: Document identifier.

        Returns:
            Basin score, or `0.0` when no basin contains the document.
        """
        for basin in self.basins:
            if doc_id in basin.documents:
                return basin.score
        if self.return_policy == "linked" and doc_id in self.return_documents:
            return self.winner.score
        return 0.0

    def evidence_field(self, max_basins: int = 3, max_edges: int = 12) -> dict[str, Any]:
        """Return the inspection field with winner and competing basins.

        Args:
            max_basins: Maximum number of basins to expose, including the winner.
            max_edges: Maximum number of support edges to expose.

        Returns:
            Structured inspection payload with winning basin, competing basins,
            support edges, and uncertainty.
        """
        uncertainty_explanation = []
        if self.uncertainty > 0.5:
            # Keep uncertainty explainable: show competition, scatter, or weak
            # structure instead of a naked score.
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
            "winning_basin": self.basin_dict(self.winner),
            "diagnostics_included": self.diagnostics_included,
            "return_policy": self.return_policy,
            "return_documents": list(self.return_documents),
            "competing_basins": [
                self.basin_dict(basin)
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
                for edge in self.top_edges_for(self.winner.documents, max_edges)
            ],
            "uncertainty": {
                "score": self.uncertainty,
                "level": self.uncertainty_level(),
                "reasons": uncertainty_explanation,
            },
            "metrics": {
                "modularity": self.modularity,
                "dispersion": self.dispersion,
            },
        }

    def uncertainty_level(self) -> str:
        """Return a human-readable uncertainty level.

        Args:
            None.

        Returns:
            `not_computed`, `high`, or `low`.
        """
        if not self.diagnostics_included:
            return "not_computed"
        return "high" if self.uncertainty > 0.5 else "low"

    def basin_dict(self, basin: Basin) -> dict[str, Any]:
        """Serialize a basin for public result payloads.

        Args:
            basin: Basin to serialize.

        Returns:
            JSON-compatible basin dictionary.
        """
        return {
            "id": basin.id,
            "label": basin.label,
            "score": basin.score,
            "energy": basin.energy,
            "documents": list(basin.documents),
            "cohesion": basin.cohesion,
            "support": basin.support,
            "duplicate_penalty": basin.duplicate_penalty,
        }

    def top_edges_for(
        self,
        documents: tuple[str, ...],
        max_edges: int,
    ) -> list[EvidenceEdge]:
        """Return strongest internal edges for a document set.

        Args:
            documents: Document ids defining the subgraph of interest.
            max_edges: Maximum number of edges to return.

        Returns:
            Internal evidence edges sorted by descending weight.
        """
        document_set = set(documents)
        edges = [
            edge
            for edge in self.edges
            if edge.source in document_set and edge.target in document_set
        ]
        return sorted(edges, key=lambda edge: edge.weight, reverse=True)[:max_edges]
