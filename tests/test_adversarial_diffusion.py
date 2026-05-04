"""Adversarial retrieval field tests for the Chroma-backed path."""

import json
import unittest
from pathlib import Path

from noetic_systems import Database, Reconciler


class AdversarialDiffusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data_path = Path(__file__).parent / "data" / "memories.json"
        with open(data_path) as f:
            cls.test_data = json.load(f)

    def setUp(self) -> None:
        self.db = Database(collection_name="test_adversarial", reset=True)
        self.db.add_documents(self.test_data["test_corpus"])
        self.reconciler = Reconciler(self.db)

    def tearDown(self) -> None:
        self.db.reset()

    def test_hybrid_baseline_exposes_decoys(self) -> None:
        query = self.test_data["queries"]["system_upgrade_safety"]
        baseline_docs = self.reconciler.hybrid_baseline(query, limit=5)

        baseline_stances = [
            self.db.get_by_id(doc_id)["metadata"]["stance"]
            for doc_id in baseline_docs
        ]

        self.assertGreaterEqual(baseline_stances.count("safe-decoy"), 2)

    def test_reconciliation_returns_measured_basin_record(self) -> None:
        query = self.test_data["queries"]["system_upgrade_safety"]
        result = self.reconciler.reconcile(query, candidate_limit=10, result_limit=10)

        evidence = result.evidence_field(max_basins=3)

        self.assertTrue(result.winner.label.startswith("basin-"))
        self.assertGreater(result.winner.support, 0)
        self.assertGreaterEqual(result.winner.score, 0.0)
        self.assertIn("winning_basin", evidence)
        self.assertIn("uncertainty", evidence)
        self.assertIn("metrics", evidence)
        self.assertIn("support_edges", evidence)
        self.assertGreaterEqual(result.winner.energy, 0.0)
        self.assertLessEqual(result.uncertainty, 1.0)
        self.assertGreater(len(result.document_ids()), 0)
        self.assertIn("source_breadth", evidence["winning_basin"])
        self.assertIn("document_breadth", evidence["winning_basin"])

    def test_chunks_are_ready_for_llm_context(self) -> None:
        query = self.test_data["queries"]["system_upgrade_safety"]
        result = self.reconciler.reconcile(query, candidate_limit=10, result_limit=10)

        chunks = result.chunks(self.db, k=3)

        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertIn("id", chunk)
            self.assertIn("text", chunk)
            self.assertIn("metadata", chunk)
            self.assertIn("basin", chunk)
            self.assertIn("energy", chunk)


if __name__ == "__main__":
    unittest.main()
