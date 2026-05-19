"""Tests for graph-health configuration tuning helpers."""

from __future__ import annotations

import unittest

from scripts.tune_graph_health_config import (
    candidate_health_configs,
    objective_score,
)
from noetic_systems.reconciliation.calibration import GraphHealthConfig


class GraphHealthTuningTest(unittest.TestCase):
    """Validate benchmark-training helper behavior."""

    def test_candidate_health_configs_are_named_configs(self) -> None:
        """The tuning grid exposes inspectable named configurations."""
        candidates = candidate_health_configs()

        self.assertGreater(len(candidates), 10)
        self.assertTrue(all(name for name, _ in candidates))
        self.assertTrue(
            all(isinstance(config, GraphHealthConfig) for _, config in candidates)
        )
        self.assertEqual(
            len({tuple(sorted(config.__dict__.items())) for _, config in candidates}),
            len(candidates),
        )

    def test_objective_score_averages_recall_across_cutoffs(self) -> None:
        """The tuning objective uses recall from every benchmark and cutoff."""
        score = objective_score(
            {
                "a": {
                    "metrics": {
                        "@5": {"recall": 0.50},
                        "@10": {"recall": 0.75},
                    }
                },
                "b": {
                    "metrics": {
                        "@5": {"recall": 0.25},
                        "@10": {"recall": 1.00},
                    }
                },
            },
            k_values=[5, 10],
        )

        self.assertAlmostEqual(score, 0.625)


if __name__ == "__main__":
    unittest.main()
