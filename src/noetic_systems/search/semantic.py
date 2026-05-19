"""ChromaDB semantic first-stage retrieval.

Semantic search supplies the vector half of hybrid retrieval. ChromaDB embeds
the query, compares it against stored document embeddings, and returns nearest
neighbors. This module converts ChromaDB cosine distances into larger-is-better
similarity scores so downstream retrieval code can combine them with BM25.

Key variables:
    `query`: Natural-language search request.
    `limit`: Number of semantic neighbors requested.
    `where`: Optional metadata equality filter.
    `score`: Converted similarity value, `1 - distance`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noetic_systems.database import Database


@dataclass(frozen=True)
class SearchResult:
    """Single search result with score and metadata.

    Attributes:
        id: Document identifier.
        text: Retrieved chunk text.
        score: Search score where larger values are better.
        metadata: Document metadata copied from storage.
    """

    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class SemanticSearch:
    """Vector-based semantic search using ChromaDB embeddings."""

    def __init__(self, database: Database) -> None:
        """Initialize semantic search with a database.

        Args:
            database: Database instance with a populated collection.

        Returns:
            None.
        """
        self.database = database

    def search(
        self,
        query: str,
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform semantic search using vector similarity.

        Args:
            query: Query text to search for.
            limit: Maximum number of results to return.
            where: Optional metadata filter, such as `{"source": "lab"}`.

        Returns:
            Search results sorted by descending semantic relevance.
        """
        results = self.database.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where,
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        search_results = []
        for i in range(len(results["ids"][0])):
            # ChromaDB returns cosine distances. Downstream ranking expects
            # larger-is-better scores, so convert distance to similarity.
            distance = results["distances"][0][i]
            score = 1.0 - distance

            search_results.append(
                SearchResult(
                    id=results["ids"][0][i],
                    text=results["documents"][0][i],
                    score=score,
                    metadata=results["metadatas"][0][i] or {},
                )
            )

        return search_results
