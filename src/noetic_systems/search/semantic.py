"""Semantic search using ChromaDB vector similarity."""

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
            # ChromaDB returns distances (lower is better for cosine)
            # Convert to similarity score (higher is better)
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
