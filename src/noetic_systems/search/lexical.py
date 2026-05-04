"""BM25 lexical search implementation."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from noetic_systems.database import Database
from noetic_systems.search.semantic import SearchResult


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric terms.

    Args:
        text: Text to tokenize.

    Returns:
        Lowercase alphanumeric tokens.
    """
    return TOKEN_PATTERN.findall(text.lower())


@dataclass
class BM25Index:
    """BM25 index for a document corpus.

    Attributes:
        doc_ids: Document identifiers aligned with token and length arrays.
        doc_tokens: Tokenized documents.
        doc_lengths: Token counts for each document.
        avg_doc_length: Mean token count across indexed documents.
        term_doc_freqs: Number of documents containing each term.
    """

    doc_ids: list[str]
    doc_tokens: list[list[str]]
    doc_lengths: list[int]
    avg_doc_length: float
    term_doc_freqs: dict[str, int]


class LexicalSearch:
    """BM25-based lexical search."""

    def __init__(
        self,
        database: Database,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        """Initialize BM25 search.

        Args:
            database: Database instance with a populated collection.
            k1: BM25 term-frequency saturation parameter.
            b: BM25 length-normalization parameter.

        Returns:
            None.
        """
        self.database = database
        self.k1 = k1
        self.b = b
        self.index = self.build_index()

    def build_index(self) -> BM25Index:
        """Build a BM25 index from database documents.

        Returns:
            Index containing tokenized documents and corpus statistics.
        """
        result = self.database.collection.get()

        doc_ids = result["ids"]
        doc_texts = result["documents"]

        doc_tokens = [tokenize(text) for text in doc_texts]
        doc_lengths = [len(tokens) for tokens in doc_tokens]
        avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0

        term_doc_freqs: dict[str, int] = {}
        for tokens in doc_tokens:
            unique_terms = set(tokens)
            for term in unique_terms:
                term_doc_freqs[term] = term_doc_freqs.get(term, 0) + 1

        return BM25Index(
            doc_ids=doc_ids,
            doc_tokens=doc_tokens,
            doc_lengths=doc_lengths,
            avg_doc_length=avg_doc_length,
            term_doc_freqs=term_doc_freqs,
        )

    def bm25_score(self, query_tokens: list[str], doc_idx: int) -> float:
        """Calculate a BM25 score for one indexed document.

        Args:
            query_tokens: Tokenized query terms.
            doc_idx: Position of the target document in the BM25 index.

        Returns:
            BM25 relevance score.
        """
        score = 0.0
        doc_tokens = self.index.doc_tokens[doc_idx]
        doc_length = self.index.doc_lengths[doc_idx]
        N = len(self.index.doc_ids)

        query_term_counts = Counter(query_tokens)
        doc_term_counts = Counter(doc_tokens)

        for term in query_term_counts:
            if term not in doc_term_counts:
                continue

            df = self.index.term_doc_freqs.get(term, 0)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
            tf = doc_term_counts[term]
            norm = 1 - self.b + self.b * (doc_length / self.index.avg_doc_length)
            score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)

        return score

    def search(
        self,
        query: str,
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform BM25 lexical search.

        Args:
            query: Query text to search for.
            limit: Maximum number of results to return.
            where: Optional metadata filter, such as `{"source": "lab"}`.

        Returns:
            Search results sorted by descending BM25 score.
        """
        query_tokens = tokenize(query)

        if not query_tokens:
            return []

        scores = []
        for doc_idx in range(len(self.index.doc_ids)):
            doc_id = self.index.doc_ids[doc_idx]

            if where:
                doc_metadata = self.database.get_by_id(doc_id)
                if doc_metadata and not self.matches_filter(
                    doc_metadata["metadata"],
                    where,
                ):
                    continue

            score = self.bm25_score(query_tokens, doc_idx)
            scores.append((doc_idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc_idx, score in scores[:limit]:
            doc_id = self.index.doc_ids[doc_idx]
            doc_data = self.database.get_by_id(doc_id)

            if doc_data:
                results.append(
                    SearchResult(
                        id=doc_data["id"],
                        text=doc_data["text"],
                        score=score,
                        metadata=doc_data["metadata"],
                    )
                )

        return results

    def matches_filter(self, metadata: dict[str, Any], where: dict[str, Any]) -> bool:
        """Check whether metadata satisfies an equality filter.

        Args:
            metadata: Metadata attached to a candidate document.
            where: Required key-value pairs.

        Returns:
            `True` when every requested key equals the requested value.
        """
        for key, value in where.items():
            if metadata.get(key) != value:
                return False
        return True
