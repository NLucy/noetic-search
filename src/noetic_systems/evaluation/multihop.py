"""Multi-hop benchmark conversion utilities.

The external retrieval benchmarks used by Noetic Search share the same
evaluation shape: each record contains a question, a set of candidate
paragraphs, and labels identifying the paragraphs that support the answer. This
module converts those records into one common document/case format so benchmark
CLIs can compare HotpotQA, 2WikiMultiHopQA, and MuSiQue without changing the
retrieval code.

Key variables:
    `source`: Short benchmark name used in document ids and metadata.
    `record`: One dataset example from Hugging Face.
    `document_id`: Stable hash of benchmark name, paragraph title, and text.
    `target_ids`: Document ids for paragraphs labeled as supporting evidence.
    `paragraph_support_idx`: MuSiQue support paragraph index from a decomposed
        subquestion.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalCase:
    """Converted multi-hop retrieval case.

    Attributes:
        id: Dataset case id.
        source: Benchmark source name.
        question: Natural-language question.
        answer: Gold answer string from the dataset.
        target_ids: Paragraph document ids containing supporting evidence.
    """

    id: str
    source: str
    question: str
    answer: str
    target_ids: frozenset[str]


def document_id(source: str, title: str, text: str) -> str:
    """Create a stable paragraph document id.

    Args:
        source: Benchmark source name.
        title: Paragraph title.
        text: Paragraph text.

    Returns:
        Stable document identifier.
    """
    payload = f"{source}\n{title}\n{text}".encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()[:16]
    return f"{source}-{digest}"


def paragraph_text(title: str, text: str) -> str:
    """Format a titled paragraph for indexing.

    Args:
        title: Paragraph title.
        text: Paragraph body.

    Returns:
        Text chunk suitable for retrieval.
    """
    return f"Title: {title}\n{text}"


def convert_hotpot_like_records(
    records: list[dict[str, Any]],
    *,
    source: str,
) -> tuple[list[dict[str, Any]], list[RetrievalCase]]:
    """Convert HotpotQA-shaped records into retrieval documents and cases.

    HotpotQA and the selected 2WikiMultiHopQA packaging both expose
    `context.title`, `context.sentences`, and `supporting_facts.title`.

    Args:
        records: Dataset records.
        source: Benchmark source name.

    Returns:
        Tuple of corpus documents and retrieval cases.
    """
    documents_by_id: dict[str, dict[str, Any]] = {}
    cases: list[RetrievalCase] = []

    for index, record in enumerate(records):
        context = record["context"]
        titles = list(context["title"])
        sentence_groups = [list(sentences) for sentences in context["sentences"]]
        support_titles = set(record["supporting_facts"]["title"])
        targets: set[str] = set()

        for title, sentences in zip(titles, sentence_groups):
            body = " ".join(str(sentence) for sentence in sentences)
            doc_id = document_id(source, str(title), body)
            documents_by_id.setdefault(
                doc_id,
                {
                    "id": doc_id,
                    "text": paragraph_text(str(title), body),
                    "metadata": {
                        "source": source,
                        "title": str(title),
                    },
                },
            )
            if title in support_titles:
                targets.add(doc_id)

        if targets:
            cases.append(
                RetrievalCase(
                    id=str(record.get("id") or record.get("_id") or f"{source}-{index}"),
                    source=source,
                    question=str(record["question"]),
                    answer=str(record.get("answer", "")),
                    target_ids=frozenset(targets),
                )
            )

    return list(documents_by_id.values()), cases


def convert_musique_records(
    records: list[dict[str, Any]],
    *,
    source: str = "musique",
) -> tuple[list[dict[str, Any]], list[RetrievalCase]]:
    """Convert MuSiQue records into retrieval documents and cases.

    MuSiQue labels support paragraphs either directly with `is_supporting` or
    indirectly through `question_decomposition[*].paragraph_support_idx`. The
    converter uses both forms so different Hugging Face packagings remain
    compatible.

    Args:
        records: MuSiQue records.
        source: Benchmark source name.

    Returns:
        Tuple of corpus documents and retrieval cases.
    """
    documents_by_id: dict[str, dict[str, Any]] = {}
    cases: list[RetrievalCase] = []

    for index, record in enumerate(records):
        if record.get("answerable") is False:
            continue

        paragraphs = list(record["paragraphs"])
        support_indices = {
            int(step["paragraph_support_idx"])
            for step in record.get("question_decomposition", [])
            if step.get("paragraph_support_idx") is not None
        }
        targets: set[str] = set()

        for paragraph in paragraphs:
            paragraph_index = int(paragraph["idx"])
            title = str(paragraph.get("title") or f"paragraph-{paragraph_index}")
            body = str(paragraph["paragraph_text"])
            doc_id = document_id(source, title, body)
            documents_by_id.setdefault(
                doc_id,
                {
                    "id": doc_id,
                    "text": paragraph_text(title, body),
                    "metadata": {
                        "source": source,
                        "title": title,
                        "paragraph_index": paragraph_index,
                    },
                },
            )
            if paragraph.get("is_supporting") or paragraph_index in support_indices:
                targets.add(doc_id)

        if targets:
            cases.append(
                RetrievalCase(
                    id=str(record.get("id") or f"{source}-{index}"),
                    source=source,
                    question=str(record["question"]),
                    answer=str(record.get("answer", "")),
                    target_ids=frozenset(targets),
                )
            )

    return list(documents_by_id.values()), cases
