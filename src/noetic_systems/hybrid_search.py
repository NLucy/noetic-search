"""Hybrid search combining semantic and lexical retrieval."""

from __future__ import annotations

from typing import Any

from .database import Database
from .lexical_search import LexicalSearch
from .semantic_search import SearchResult, SemanticSearch


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
            database: Database instance with populated collection
            semantic_weight: Weight for semantic search scores (default: 0.5)
            lexical_weight: Weight for lexical search scores (default: 0.5)
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
            query: Query text to search for
            limit: Maximum number of results to return
            where: Optional metadata filter (e.g., {"source": "lab"})

        Returns:
            List of SearchResult objects, sorted by combined score (highest first)
        """
        semantic_results = self.semantic.search(query, limit=limit * 2, where=where)
        lexical_results = self.lexical.search(query, limit=limit * 2, where=where)

        semantic_scores = self._normalize_scores(semantic_results)
        lexical_scores = self._normalize_scores(lexical_results)

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

    def _normalize_scores(self, results: list[SearchResult]) -> list[float]:
        """Normalize scores to [0, 1] range using min-max normalization."""
        if not results:
            return []

        scores = [r.score for r in results]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [1.0] * len(scores)

        return [(s - min_score) / (max_score - min_score) for s in scores]
