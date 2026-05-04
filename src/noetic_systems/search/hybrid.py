"""Hybrid search combining semantic and lexical retrieval."""

from __future__ import annotations

from typing import Any

from noetic_systems.database import Database
from noetic_systems.search.lexical import LexicalSearch
from noetic_systems.search.semantic import SearchResult, SemanticSearch


class HybridSearch:
    """Combine semantic search and BM25 lexical search."""

    def __init__(
        self,
        database: Database,
        semantic_weight: float = 0.5,
        lexical_weight: float = 0.5,
    ) -> None:
        """Initialize hybrid search.

        Args:
            database: Database instance with a populated collection.
            semantic_weight: Weight applied to normalized semantic scores.
            lexical_weight: Weight applied to normalized lexical scores.

        Returns:
            None.
        """
        self.database = database
        self.semantic = SemanticSearch(database)
        self.lexical = LexicalSearch(database)
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight

    def search(
        self,
        query: str,
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform hybrid search combining semantic and lexical strategies.

        Args:
            query: Query text to search for.
            limit: Maximum number of results to return.
            where: Optional metadata filter, such as `{"source": "lab"}`.

        Returns:
            Search results sorted by descending combined score.
        """
        semantic_results = self.semantic.search(query, limit=limit * 2, where=where)
        lexical_results = self.lexical.search(query, limit=limit * 2, where=where)

        semantic_scores = self.normalize_scores(semantic_results)
        lexical_scores = self.normalize_scores(lexical_results)

        combined: dict[str, tuple[SearchResult, float]] = {}

        for result, norm_score in zip(semantic_results, semantic_scores):
            combined[result.id] = (result, norm_score * self.semantic_weight)

        for result, norm_score in zip(lexical_results, lexical_scores):
            if result.id in combined:
                existing_result, existing_score = combined[result.id]
                combined[result.id] = (
                    existing_result,
                    existing_score + norm_score * self.lexical_weight,
                )
            else:
                combined[result.id] = (result, norm_score * self.lexical_weight)

        ranked = sorted(
            combined.items(),
            key=lambda x: x[1][1],
            reverse=True,
        )

        results = []
        for _, (result, combined_score) in ranked[:limit]:
            results.append(
                SearchResult(
                    id=result.id,
                    text=result.text,
                    score=combined_score,
                    metadata=result.metadata,
                )
            )

        return results

    def normalize_scores(self, results: list[SearchResult]) -> list[float]:
        """Normalize scores with min-max scaling.

        Args:
            results: Search results whose scores should be normalized.

        Returns:
            Scores scaled to the `[0, 1]` interval. Equal scores map to `1.0`.
        """
        if not results:
            return []

        scores = [r.score for r in results]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [1.0] * len(scores)

        return [(s - min_score) / (max_score - min_score) for s in scores]
