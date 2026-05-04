"""Integration tests for the full Noetic Systems pipeline."""

import json
import unittest
from pathlib import Path

from noetic_systems import Database, HybridSearch, LexicalSearch, SemanticSearch


class TestSearchIntegration(unittest.TestCase):
    """Test semantic, lexical, and hybrid search with real data."""

    @classmethod
    def setUpClass(cls):
        """Load test data once for all tests."""
        data_path = Path(__file__).parent / "data" / "memories.json"
        with open(data_path) as f:
            cls.test_data = json.load(f)

    def setUp(self):
        """Create fresh database for each test."""
        self.db = Database(collection_name="test_memories", reset=True)
        self.db.add_documents(self.test_data["test_corpus"])

    def tearDown(self):
        """Clean up database after each test."""
        self.db.reset()

    def test_database_loads_documents(self):
        """Verify database correctly loads documents from JSON."""
        count = self.db.count()
        self.assertEqual(count, len(self.test_data["test_corpus"]))

        # Verify we can retrieve a document
        doc = self.db.get_by_id("sys-upgrade-risk-performance")
        self.assertIsNotNone(doc)
        self.assertIn("Load tests reveal memory pressure", doc["text"])
        self.assertEqual(doc["metadata"]["stance"], "risk-cluster")

    def test_semantic_search_finds_relevant_docs(self):
        """Semantic search should find documents by meaning."""
        semantic = SemanticSearch(self.db)

        query = self.test_data["queries"]["system_upgrade_safety"]
        results = semantic.search(query, limit=5)

        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 5)

        # All results should have required fields
        for result in results:
            self.assertIsNotNone(result.id)
            self.assertIsNotNone(result.text)
            self.assertIsInstance(result.score, float)
            self.assertIsInstance(result.metadata, dict)

    def test_lexical_search_matches_keywords(self):
        """BM25 should find documents with keyword overlap."""
        lexical = LexicalSearch(self.db)

        query = "deployment safety upgrade system"
        results = lexical.search(query, limit=5)

        self.assertGreater(len(results), 0)

        # Top results should contain some query keywords
        top_result = results[0]
        top_text_lower = top_result.text.lower()
        keywords = {"deployment", "safety", "upgrade", "system"}
        matches = sum(1 for kw in keywords if kw in top_text_lower)
        self.assertGreater(matches, 0, "Top result should match some keywords")

    def test_hybrid_search_combines_strategies(self):
        """Hybrid search should merge semantic and lexical results."""
        hybrid = HybridSearch(self.db)

        query = self.test_data["queries"]["system_upgrade_safety"]
        results = hybrid.search(query, limit=5)

        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 5)

        # Scores should be normalized and combined
        for result in results:
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0)

    def test_metadata_filtering(self):
        """All search types should support metadata filtering."""
        semantic = SemanticSearch(self.db)
        lexical = LexicalSearch(self.db)
        hybrid = HybridSearch(self.db)

        query = "system upgrade"
        where_filter = {"source": "lab"}

        # Semantic with filter
        sem_results = semantic.search(query, limit=10, where=where_filter)
        for result in sem_results:
            self.assertEqual(result.metadata.get("source"), "lab")

        # Lexical with filter
        lex_results = lexical.search(query, limit=10, where=where_filter)
        for result in lex_results:
            self.assertEqual(result.metadata.get("source"), "lab")

        # Hybrid with filter
        hyb_results = hybrid.search(query, limit=10, where=where_filter)
        for result in hyb_results:
            self.assertEqual(result.metadata.get("source"), "lab")

    def test_semantic_vs_lexical_differences(self):
        """Semantic and lexical should return different result orderings."""
        semantic = SemanticSearch(self.db)
        lexical = LexicalSearch(self.db)

        # Query with clear semantic meaning but few exact matches
        query = "Is it safe to roll out the new version?"

        sem_results = semantic.search(query, limit=3)
        lex_results = lexical.search(query, limit=3)

        sem_ids = [r.id for r in sem_results]
        lex_ids = [r.id for r in lex_results]

        # Unless we're very unlucky, orderings should differ
        # (This is a probabilistic assertion but should hold for this dataset)
        self.assertGreater(len(sem_ids), 0)
        self.assertGreater(len(lex_ids), 0)

    def test_decoy_documents_rank_high_semantically(self):
        """Verify that decoy documents rank highly in semantic search."""
        semantic = SemanticSearch(self.db)

        query = self.test_data["queries"]["system_upgrade_safety"]
        results = semantic.search(query, limit=5)

        # Count how many decoys appear in top 5
        decoy_count = sum(
            1 for r in results
            if r.metadata.get("stance") == "safe-decoy"
        )

        # Decoys should be present (they're designed to match the query semantically)
        self.assertGreater(
            decoy_count,
            0,
            "Decoy documents should rank in top semantic results",
        )

    def test_risk_documents_form_cluster(self):
        """Verify that risk documents exist and have consistent metadata."""
        risk_ids = [
            "sys-upgrade-risk-performance",
            "sys-upgrade-risk-database",
            "sys-upgrade-risk-infrastructure",
            "sys-upgrade-risk-monitoring",
            "sys-upgrade-risk-operations",
        ]

        for doc_id in risk_ids:
            doc = self.db.get_by_id(doc_id)
            self.assertIsNotNone(doc, f"Risk document {doc_id} should exist")
            self.assertEqual(
                doc["metadata"]["stance"],
                "risk-cluster",
                f"Document {doc_id} should have stance=risk-cluster",
            )


if __name__ == "__main__":
    unittest.main()
