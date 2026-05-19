"""Build LLM comparison requests for top-k, basin, and field surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from noetic_systems.database import Database
from noetic_systems.llm.messages import Message
from noetic_systems.llm.prompts import (
    build_basin_messages,
    build_evidence_field_messages,
    build_top_k_messages,
)
from noetic_systems.reconciliation.engine import Reconciler


Mode = Literal["top-k", "basin", "evidence-field"]


@dataclass(frozen=True)
class LLMExperiment:
    """Prepared LLM inputs for comparing retrieval surfaces.

    Attributes:
        query: Query used to produce all comparison surfaces.
        top_k_messages: Messages for the raw top-k baseline.
        basin_messages: Messages for the strongest-basin surface.
        evidence_field_messages: Messages for the full evidence-field surface.
    """

    query: str
    top_k_messages: list[Message]
    basin_messages: list[Message]
    evidence_field_messages: list[Message]

    def messages_for(self, mode: Mode) -> list[Message]:
        """Return messages for a retrieval surface.

        Args:
            mode: Retrieval surface identifier.

        Returns:
            Messages for the requested surface.
        """
        if mode == "top-k":
            return self.top_k_messages
        if mode == "basin":
            return self.basin_messages
        return self.evidence_field_messages


def build_llm_experiment(
    database: Database,
    query: str,
    *,
    candidate_limit: int = 10,
    result_limit: int = 10,
    chunk_limit: int = 5,
) -> LLMExperiment:
    """Build comparable top-k, basin, and evidence-field LLM inputs.

    Args:
        database: Database containing the indexed corpus.
        query: Query to evaluate.
        candidate_limit: Hybrid candidates to retrieve before reconciliation.
        result_limit: Candidates retained in the reconciled graph.
        chunk_limit: Number of chunks to include in compact payloads.

    Returns:
        Experiment object containing all comparison message sets.
    """
    reconciler = Reconciler(database)
    baseline_ids = reconciler.hybrid_baseline(query, limit=chunk_limit)
    baseline_chunks = []
    for doc_id in baseline_ids:
        doc = database.get_by_id(doc_id)
        if not doc:
            continue
        baseline_chunks.append(
            {
                "id": doc["id"],
                "text": doc["text"],
                "metadata": doc["metadata"],
            }
        )

    result = reconciler.reconcile(
        query,
        candidate_limit=candidate_limit,
        result_limit=result_limit,
        include_diagnostics=True,
    )
    evidence_field = result.evidence_field(max_basins=4)
    strongest_basin = result.strongest_basin(database, k=chunk_limit)
    evidence_chunks = result.chunks(database, k=chunk_limit)

    return LLMExperiment(
        query=query,
        top_k_messages=build_top_k_messages(query, baseline_chunks),
        basin_messages=build_basin_messages(query, strongest_basin),
        evidence_field_messages=build_evidence_field_messages(
            query,
            evidence_field,
            evidence_chunks,
        ),
    )


def summarize_payload(payload: dict[str, Any]) -> str:
    """Return a compact payload summary for CLI output.

    Args:
        payload: Responses API request payload.

    Returns:
        Human-readable one-line summary.
    """
    input_items = payload.get("input", [])
    roles = [
        item.get("role", item.get("type", "unknown"))
        for item in input_items
    ]
    return (
        f"model={payload.get('model')} "
        f"items={len(input_items)} "
        f"roles={roles} "
        f"max_output_tokens={payload.get('max_output_tokens')}"
    )
