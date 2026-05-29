"""Unit tests for hybrid retrieval invariants."""

import unittest

from noetic_systems.database import Database
from noetic_systems.search.hybrid import HybridSearch


class HybridSearchTests(unittest.TestCase):
    """Validate hybrid retrieval score-pool behavior."""

    def setUp(self) -> None:
        """Create a corpus large enough to expose limit-sensitive ranking.

        Returns:
            None.
        """
        self.db = Database(collection_name="test_hybrid_search", reset=True)
        documents = [
            {
                "id": f"battery-{index:03d}",
                "text": (
                    f"Battery update drain report {index}. "
                    "Firmware indexing sync power telemetry."
                ),
                "metadata": {"topic": "battery"},
            }
            for index in range(70)
        ]
        documents.extend(
            {
                "id": f"camera-{index:03d}",
                "text": f"Camera autofocus lens exposure report {index}.",
                "metadata": {"topic": "camera"},
            }
            for index in range(70)
        )
        self.db.add_documents(documents)
        self.search = HybridSearch(self.db)

    def tearDown(self) -> None:
        """Remove the test collection.

        Returns:
            None.
        """
        self.db.reset()

    def test_fixed_pool_makes_output_limit_truncation_equivalent(self) -> None:
        """Verify `top 30` equals `top 50[:30]` with the same scoring pool.

        Returns:
            None.
        """
        query = "battery update drain telemetry"

        top_30 = self.search.search(query, limit=30, pool_limit=100)
        top_50_slice = self.search.search(query, limit=50, pool_limit=100)[:30]

        self.assertEqual(
            [(result.id, result.score) for result in top_30],
            [(result.id, result.score) for result in top_50_slice],
        )


if __name__ == "__main__":
    unittest.main()
