"""Prompt builders for comparing retrieval surfaces."""

from __future__ import annotations

import json
from typing import Any

from .messages import DeveloperMessage, Message, UserMessage


RECONCILIATION_DEVELOPER_PROMPT = """You are evaluating retrieved evidence for an answer.
Use only the provided retrieval material. Distinguish direct evidence from inference.
If the evidence is conflicted or weak, say so plainly. Do not invent missing facts."""


def build_top_k_messages(
    query: str,
    chunks: list[dict[str, Any]],
) -> list[Message]:
    """Build a plain top-k chunk prompt."""
    payload = {
        "query": query,
        "chunks": chunks,
    }
    return [
        DeveloperMessage(RECONCILIATION_DEVELOPER_PROMPT),
        UserMessage(
            "Answer the query using these top-k retrieved chunks:\n"
            f"{json.dumps(payload, indent=2, sort_keys=True)}"
        ),
    ]


def build_evidence_field_messages(
    query: str,
    evidence_field: dict[str, Any],
    chunks: list[dict[str, Any]] | None = None,
) -> list[Message]:
    """Build a prompt that gives the model the reconciled evidence field."""
    payload = {
        "query": query,
        "evidence_field": evidence_field,
        "chunks": chunks or [],
    }
    return [
        DeveloperMessage(RECONCILIATION_DEVELOPER_PROMPT),
        UserMessage(
            "Answer the query using this reconciled evidence field. Explain how the "
            "winning basin, competing basins, support edges, and uncertainty affect "
            "the answer:\n"
            f"{json.dumps(payload, indent=2, sort_keys=True)}"
        ),
    ]


def build_basin_messages(
    query: str,
    basin: dict[str, Any],
) -> list[Message]:
    """Build a prompt that gives the model the strongest basin only."""
    payload = {
        "query": query,
        "strongest_basin": basin,
    }
    return [
        DeveloperMessage(RECONCILIATION_DEVELOPER_PROMPT),
        UserMessage(
            "Answer the query using this strongest reconciled basin. Treat the "
            "basin chunks as the primary evidence, and use uncertainty as a caveat:\n"
            f"{json.dumps(payload, indent=2, sort_keys=True)}"
        ),
    ]
