"""Tests for label-free diffusion-health diagnostics."""

from __future__ import annotations

import unittest

from noetic_systems.evaluation.diffusion_health import (
    band_score,
    diffusion_health,
    ranks,
    spearman_correlation,
)


class DiffusionHealthTests(unittest.TestCase):
    """Validate diffusion-health measurements."""

    def test_diffusion_health_rewards_connected_local_flow(self) -> None:
        """Connected graphs should transfer energy to neighbors."""
        graph = {
            "a": {"b": 1.0},
            "b": {"a": 1.0, "c": 1.0},
            "c": {"b": 1.0},
        }

        health = diffusion_health(graph, steps=2, damping=0.5)

        self.assertGreater(health.neighbor_transfer, 0.0)
        self.assertEqual(health.isolation_rate, 0.0)
        self.assertGreater(health.health_score, 0.0)

    def test_diffusion_health_detects_isolation(self) -> None:
        """Fully isolated graphs should have maximal isolation."""
        graph = {
            "a": {},
            "b": {},
        }

        health = diffusion_health(graph, steps=2, damping=0.85)

        self.assertEqual(health.isolation_rate, 1.0)
        self.assertEqual(health.neighbor_transfer, 0.0)

    def test_ranks_handle_ties(self) -> None:
        """Rank helper should average tied positions."""
        self.assertEqual(ranks([10.0, 20.0, 20.0]), [1.0, 2.5, 2.5])

    def test_band_score_prefers_middle_values(self) -> None:
        """Middle-band score should reject values that are too low or too high."""
        self.assertEqual(band_score(0.0, low=0.1, target=0.5, high=0.9), 0.0)
        self.assertEqual(band_score(1.0, low=0.1, target=0.5, high=0.9), 0.0)
        self.assertEqual(band_score(0.5, low=0.1, target=0.5, high=0.9), 1.0)

    def test_spearman_correlation_orders_match(self) -> None:
        """Perfectly aligned ranks produce correlation 1."""
        self.assertAlmostEqual(
            spearman_correlation([1.0, 2.0, 3.0], [10.0, 20.0, 30.0]),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
