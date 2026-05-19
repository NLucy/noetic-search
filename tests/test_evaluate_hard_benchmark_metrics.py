"""Tests for hard-benchmark ranking metrics."""

from __future__ import annotations

import argparse
import unittest

from noetic_systems.evaluation.metrics import (
    add_metric_totals,
    average_metric_totals,
    empty_metric_totals,
    parse_k_values,
    ranking_metrics,
)


class RankingMetricTests(unittest.TestCase):
    """Validate precision, recall, hit rate, and MRR calculations."""

    def test_ranking_metrics_at_k(self) -> None:
        """Metric values use the cutoff as the precision denominator."""
        metrics = ranking_metrics(
            ["decoy-a", "target-a", "target-b", "decoy-b"],
            {"target-a", "target-b", "target-c"},
            3,
        )

        self.assertAlmostEqual(metrics["precision"], 2 / 3)
        self.assertAlmostEqual(metrics["recall"], 2 / 3)
        self.assertAlmostEqual(metrics["hit"], 1.0)
        self.assertAlmostEqual(metrics["mrr"], 1 / 2)

    def test_ranking_metrics_miss(self) -> None:
        """Misses return zero for all ranking metrics."""
        metrics = ranking_metrics(["decoy-a", "decoy-b"], {"target-a"}, 2)

        self.assertEqual(
            metrics,
            {"precision": 0.0, "recall": 0.0, "hit": 0.0, "mrr": 0.0},
        )

    def test_average_metric_totals(self) -> None:
        """Metric accumulators average cleanly across cases."""
        totals = empty_metric_totals([1, 3])
        add_metric_totals(totals, ["target-a", "decoy-a"], {"target-a"})
        add_metric_totals(totals, ["decoy-a", "target-a"], {"target-a"})

        averaged = average_metric_totals(totals, 2)

        self.assertAlmostEqual(averaged["@1"]["precision"], 0.5)
        self.assertAlmostEqual(averaged["@1"]["recall"], 0.5)
        self.assertAlmostEqual(averaged["@1"]["mrr"], 0.5)
        self.assertAlmostEqual(averaged["@3"]["hit"], 1.0)

    def test_parse_k_values(self) -> None:
        """Cutoff parsing sorts and deduplicates values."""
        self.assertEqual(parse_k_values("10, 1, 5, 5"), [1, 5, 10])

    def test_parse_k_values_rejects_nonpositive(self) -> None:
        """Cutoff parsing rejects invalid rank positions."""
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_k_values("1,0,5")


if __name__ == "__main__":
    unittest.main()
