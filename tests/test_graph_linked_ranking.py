"""Tests for graph edge construction and linked evidence ranking."""

from __future__ import annotations

import unittest

from noetic_systems.database import Database
from noetic_systems.reconciliation.graph import build_evidence_graph
from noetic_systems.reconciliation.ranking import rank_linked_evidence
from noetic_systems.search.semantic import SearchResult


class GraphLinkedRankingTests(unittest.TestCase):
    """Validate cross-reference edges and anchor-linked promotion."""

    def test_graph_adds_cross_reference_edges(self) -> None:
        """A chunk that names another chunk's title creates a graph edge."""
        db = Database(collection_name="test_graph_cross_reference", reset=True)
        try:
            db.add_documents(
                [
                    {
                        "id": "film",
                        "text": "Title: Big Stone Gap\nDirected by Adriana Trigiani.",
                        "metadata": {"title": "Big Stone Gap"},
                    },
                    {
                        "id": "person",
                        "text": "Title: Adriana Trigiani\nBased in Greenwich Village.",
                        "metadata": {"title": "Adriana Trigiani"},
                    },
                ]
            )
            doc_index = {
                "film": SearchResult(
                    "film",
                    "Title: Big Stone Gap\nDirected by Adriana Trigiani.",
                    1.0,
                    {"title": "Big Stone Gap"},
                ),
                "person": SearchResult(
                    "person",
                    "Title: Adriana Trigiani\nBased in Greenwich Village.",
                    0.2,
                    {"title": "Adriana Trigiani"},
                ),
            }

            graph, edges = build_evidence_graph(db, doc_index, 0.99)

            self.assertIn("person", graph["film"])
            self.assertTrue(any(edge.type == "cross_reference" for edge in edges))
        finally:
            db.reset()

    def test_linked_ranking_promotes_anchor_neighbor(self) -> None:
        """Linked ranking keeps anchors and promotes graph-connected evidence."""
        candidates = [
            SearchResult(f"doc-{index}", f"document {index}", 1.0 - index * 0.1, {})
            for index in range(7)
        ]
        graph = {candidate.id: {} for candidate in candidates}
        graph["doc-0"]["doc-6"] = 0.9
        graph["doc-6"]["doc-0"] = 0.9

        ranked = rank_linked_evidence(candidates, graph, anchor_count=1)

        self.assertEqual(ranked[0], "doc-0")
        self.assertLess(ranked.index("doc-6"), 5)

    def test_graph_adds_lexical_salience_edges_for_repeated_phrases(self) -> None:
        """Shared salient phrases create lexical edges after stop-word removal."""
        db = Database(collection_name="test_graph_lexical_salience", reset=True)
        try:
            db.add_documents(
                [
                    {
                        "id": "left",
                        "text": "Title: Left\nAdriana Trigiani directed the film.",
                        "metadata": {"title": "Left"},
                    },
                    {
                        "id": "right",
                        "text": "Title: Right\nAdriana Trigiani lives in New York.",
                        "metadata": {"title": "Right"},
                    },
                    {
                        "id": "other",
                        "text": "Title: Other\nThe city has several buildings.",
                        "metadata": {"title": "Other"},
                    },
                ]
            )
            doc_index = {
                "left": SearchResult(
                    "left",
                    "Title: Left\nAdriana Trigiani directed the film.",
                    1.0,
                    {"title": "Left"},
                ),
                "right": SearchResult(
                    "right",
                    "Title: Right\nAdriana Trigiani lives in New York.",
                    0.8,
                    {"title": "Right"},
                ),
                "other": SearchResult(
                    "other",
                    "Title: Other\nThe city has several buildings.",
                    0.1,
                    {"title": "Other"},
                ),
            }

            graph, edges = build_evidence_graph(db, doc_index, 0.99)

            self.assertIn("right", graph["left"])
            self.assertTrue(any(edge.type == "lexical_salience" for edge in edges))
        finally:
            db.reset()


if __name__ == "__main__":
    unittest.main()
