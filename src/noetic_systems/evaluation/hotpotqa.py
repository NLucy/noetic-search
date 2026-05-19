"""HotpotQA conversion utilities for retrieval evaluation.

HotpotQA examples contain a question, a small context set of Wikipedia
paragraphs, and sentence-level supporting facts. For retrieval evaluation, this
module converts each paragraph into one candidate document and treats any
paragraph title listed in `supporting_facts` as relevant evidence for that
question.

This is intentionally paragraph-level, not answer-level. Noetic Search is being
tested as a retrieval and compression layer, so the metric target is whether the
right supporting paragraphs are returned near the top, not whether an LLM
generates the final answer.

Key variables:
    `record`: One HotpotQA example from Hugging Face.
    `context.title`: Paragraph titles included with the example.
    `context.sentences`: Sentence lists for each context paragraph.
    `supporting_facts.title`: Titles of paragraphs containing gold support.
    `document_id`: Stable hash of title and paragraph text.
    `target_ids`: Document ids for paragraphs needed to answer the question.
"""

from __future__ import annotations

from typing import Any

from noetic_systems.evaluation.multihop import (
    RetrievalCase,
    convert_hotpot_like_records,
    document_id as multihop_document_id,
    paragraph_text as multihop_paragraph_text,
)

HotpotCase = RetrievalCase


def document_id(title: str, sentences: list[str]) -> str:
    """Create a stable document id for a HotpotQA paragraph.

    Args:
        title: Paragraph title.
        sentences: Paragraph sentences.

    Returns:
        Stable document identifier.
    """
    return multihop_document_id("hotpot", title, " ".join(sentences))


def paragraph_text(title: str, sentences: list[str]) -> str:
    """Format a HotpotQA paragraph for indexing.

    Args:
        title: Paragraph title.
        sentences: Paragraph sentences.

    Returns:
        Text chunk suitable for retrieval.
    """
    return multihop_paragraph_text(title, " ".join(sentences))


def convert_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[HotpotCase]]:
    """Convert HotpotQA records into corpus documents and cases.

    Args:
        records: HotpotQA records from Hugging Face.

    Returns:
        Tuple of corpus documents and retrieval cases.
    """
    return convert_hotpot_like_records(records, source="hotpot")
