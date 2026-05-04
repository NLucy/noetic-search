"""Public result surfaces for reconciled evidence fields.

The result object is the handoff point between search and downstream callers. It
can return only the winning basin's chunks for compact LLM context, or expose the
full evidence field with competing basins, support edges, and uncertainty. We
keep this logic separate from reconciliation so the search computation and
external payload shapes do not become tangled.

There are three useful public surfaces. `document_ids()` returns the compact
ranked ids from the winning basin. `chunks()` materializes those ids into
LLM-ready text, metadata, and scores. `evidence_field()` exposes the inspection
view: winning basin, competing basins, support edges, metrics, and uncertainty
reasons. The same computed result can therefore serve a production prompt, a
debugging interface, or an evaluation harness.

The result also preserves per-document scores. Energy, specificity, query score,
support, and query echo remain available after reconciliation so final chunks can
be audited without rerunning the pipeline.
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
        winner: Highest-scoring basin.
        basins: All detected basins sorted by descending score.
        uncertainty: Structural uncertainty score in the `[0, 1]` interval.
        dispersion: Diffused-energy dispersion score.
        modularity: Graph modularity for the detected communities.
        document_energy: Settled energy by document id.
        document_specificity: Specificity score by document id.
        document_query_score: Hybrid query score by document id.
        document_support: Graph support by document id.
        document_echo: Query-echo score by document id.
        edges: Evidence edges used to build the candidate graph.
    """

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
        """Return top-k document ids from the winning basin.

        Args:
            k: Maximum number of document ids to return.

        Returns:
            Ranked document ids.
        """
        return list(self.winner.documents[:k])

    def top_k_documents(self, k: int = 5) -> list[str]:
        """Return top-k document ids from the winning basin.

        Args:
            k: Maximum number of document ids to return.

        Returns:
            Ranked document ids.
        """
        return self.document_ids(k)

    def chunks(self, database: Database, k: int = 5) -> list[dict[str, Any]]:
        """Return LLM-ready chunks from the winning basin.

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
        """Return the strongest basin with its chunks as the primary surface.

        Args:
            database: Database used to materialize chunk text and metadata.
            k: Optional maximum number of chunks. When omitted, all winning-basin
                documents are returned.

        Returns:
            Structured strongest-basin payload.
        """
        doc_ids = self.winner.documents if k is None else tuple(self.document_ids(k))
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
                "level": "high" if self.uncertainty > 0.5 else "low",
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

        # Preserve all major reconciliation signals on each materialized chunk.
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
            # Expose structural reasons so callers can decide how much caveat to add.
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
                "level": "high" if self.uncertainty > 0.5 else "low",
                "reasons": uncertainty_explanation,
            },
            "metrics": {
                "modularity": self.modularity,
                "dispersion": self.dispersion,
            },
        }

    def evidence(self, max_basins: int = 3) -> dict[str, Any]:
        """Return the reconciled evidence field.

        Args:
            max_basins: Maximum number of basins to expose.

        Returns:
            Structured inspection payload.
        """
        return self.evidence_field(max_basins=max_basins)

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
