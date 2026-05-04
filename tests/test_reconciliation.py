"""Unit tests for reconciliation result surfaces."""

import unittest

from noetic_systems.corpus import demo_corpus
from noetic_systems.database import Database
from noetic_systems.reconciliation.engine import Reconciler


class ReconciliationTests(unittest.TestCase):
    """Validate basin, chunk, and evidence-field result surfaces."""

    def setUp(self) -> None:
        """Create a fresh demo database for each test.

        Returns:
            None.
        """
        self.db = Database(collection_name="test_reconciliation", reset=True)
        self.db.add_documents(demo_corpus())
        self.reconciler = Reconciler(self.db)

    def tearDown(self) -> None:
        """Remove the test collection.

        Returns:
            None.
        """
        self.db.reset()

    def test_returns_winning_basin(self) -> None:
        """Verify reconciliation returns a non-empty winning basin.

        Returns:
            None.
        """
        result = self.reconciler.reconcile(
            "Should I trust the battery life claims?",
            candidate_limit=7,
            result_limit=7,
        )

        self.assertIn("battery", " ".join(result.winner.documents))
        self.assertGreater(result.winner.energy, 0.0)
        self.assertGreater(len(result.basins), 0)

    def test_can_return_structured_evidence_or_chunks(self) -> None:
        """Verify evidence-field and chunk payloads are populated.

        Returns:
            None.
        """
        result = self.reconciler.reconcile(
            "Should I trust the battery life claims?",
            candidate_limit=7,
            result_limit=7,
        )

        evidence = result.evidence_field()
        chunks = result.chunks(self.db, k=2)

        self.assertIn("winning_basin", evidence)
        self.assertIn("competing_basins", evidence)
        self.assertIn("support_edges", evidence)
        self.assertEqual(evidence["winning_basin"]["label"], result.winner.label)
        self.assertGreater(len(chunks), 0)
        self.assertIn("text", chunks[0])
        self.assertIn("metadata", chunks[0])
        self.assertEqual(chunks[0]["basin"], result.winner.label)
        self.assertEqual(chunks[0]["basin_score"], result.winner.score)
        self.assertIn("specificity", chunks[0])

    def test_can_return_strongest_basin_as_primary_surface(self) -> None:
        """Verify the strongest-basin payload is the primary compact surface.

        Returns:
            None.
        """
        result = self.reconciler.reconcile(
            "Should I trust the battery life claims?",
            candidate_limit=7,
            result_limit=7,
        )

        basin = result.strongest_basin(self.db, k=3)

        self.assertEqual(basin["basin"]["label"], result.winner.label)
        self.assertIn("chunks", basin)
        self.assertGreater(len(basin["chunks"]), 0)
        self.assertIn("uncertainty", basin)
        self.assertIn("metrics", basin)
        self.assertIn("energy", basin["chunks"][0])
        self.assertIn("specificity", basin["chunks"][0])

if __name__ == "__main__":
    unittest.main()
