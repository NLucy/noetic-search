"""Tests for the synthetic clinical evidence benchmark."""

from __future__ import annotations

import unittest

from scripts.evaluate_clinical_benchmark import (
    clinical_frontier,
    clinical_metrics,
    clinical_utility,
    critical_doc_ids,
    dangerous_decoy_ids,
    guarded_resonance_ids,
    risk_aware_resonance_ids,
    resonance_graph_from_edges,
    strip_custom_metadata,
    target_doc_ids,
)
from noetic_systems.reconciliation.models import EvidenceEdge
from tests.data.generate_clinical_evidence_benchmark import generate


class ClinicalBenchmarkTests(unittest.TestCase):
    """Validate benchmark structure and clinical retrieval metrics."""

    def test_generate_contains_targets_and_decoys(self) -> None:
        """Generated cases should expose target, critical, and decoy ids."""
        data = generate(total_distractors=5, seed=7)
        case_id = next(iter(data["cases"]))

        targets = target_doc_ids(data, case_id)
        critical = critical_doc_ids(data, case_id)
        decoys = dangerous_decoy_ids(data, case_id)

        self.assertGreaterEqual(len(targets), 5)
        self.assertGreaterEqual(len(critical), 3)
        self.assertGreaterEqual(len(decoys), 4)
        self.assertTrue(critical.issubset(targets))

    def test_strip_custom_metadata_removes_gold_labels(self) -> None:
        """Blind corpus should not index benchmark-only labels."""
        data = generate(total_distractors=1, seed=8)
        stripped = strip_custom_metadata(data)

        for doc in stripped:
            self.assertNotIn("gold", doc["metadata"])
            self.assertNotIn("case", doc["metadata"])
            self.assertNotIn("safety_critical", doc["metadata"])

    def test_clinical_metrics_capture_support_and_decoy_risk(self) -> None:
        """Clinical metrics should distinguish complete support and decoys."""
        ranked = ["a", "b", "decoy", "x", "y"]
        metrics = clinical_metrics(
            ranked,
            target_ids={"a", "b"},
            critical_ids={"a"},
            decoy_ids={"decoy"},
            k=5,
        )

        self.assertEqual(metrics["exact_support"], 1.0)
        self.assertEqual(metrics["critical_recall"], 1.0)
        self.assertEqual(metrics["critical_miss_rate"], 0.0)
        self.assertEqual(metrics["decoy_rate"], 1.0)

    def test_clinical_utility_penalizes_decoy_rate(self) -> None:
        """Utility should score critical recall against plain decoy rate."""
        clinical = {
            "safe": {
                "@5": {
                    "critical_recall": 0.3,
                    "decoy_rate": 0.0,
                    "exact_support": 0.0,
                }
            },
            "risky": {
                "@5": {
                    "critical_recall": 0.6,
                    "decoy_rate": 1.0,
                    "exact_support": 0.0,
                }
            },
        }

        utility = clinical_utility(clinical, [5])
        frontier = clinical_frontier(clinical, [5])

        self.assertEqual(utility["lambda_0.5"]["safe"]["@5"], 0.3)
        self.assertAlmostEqual(utility["lambda_0.5"]["risky"]["@5"], 0.1)
        self.assertEqual(frontier["@5"][0]["variant"], "safe")

    def test_resonance_graph_rewards_channel_agreement(self) -> None:
        """Semantic and lexical agreement should outweigh one-channel tension."""
        graph = resonance_graph_from_edges(
            ["a", "b", "c"],
            [
                EvidenceEdge("a", "b", "embedding_similarity", 1.0, "semantic"),
                EvidenceEdge("a", "b", "lexical_salience", 1.0, "lexical"),
                EvidenceEdge("a", "c", "embedding_similarity", 1.0, "semantic"),
            ],
            minimum_weight=0.0,
        )

        self.assertGreater(graph["a"]["b"], graph["a"]["c"])

    def test_resonance_graph_penalizes_duplicate_pressure(self) -> None:
        """Near-duplicate pressure should lower otherwise matched edges."""
        graph = resonance_graph_from_edges(
            ["a", "b", "c"],
            [
                EvidenceEdge("a", "b", "embedding_similarity", 1.0, "semantic"),
                EvidenceEdge("a", "b", "lexical_salience", 1.0, "lexical"),
                EvidenceEdge("a", "b", "near_duplicate", 1.0, "duplicate"),
                EvidenceEdge("a", "c", "embedding_similarity", 1.0, "semantic"),
                EvidenceEdge("a", "c", "lexical_salience", 1.0, "lexical"),
            ],
            minimum_weight=0.0,
        )

        self.assertLess(graph["a"]["b"], graph["a"]["c"])

    def test_guarded_resonance_removes_unsupported_promotions(self) -> None:
        """Unsupported resonance ids should fall back to conservative hybrid order."""
        ranked = guarded_resonance_ids(
            resonance_ids=["decoy", "supported"],
            hybrid_ids=["anchor", "fallback"],
            signatures_by_doc={
                "decoy": {"resonance_degree": 0.0, "hybrid_rank": 12},
                "supported": {"resonance_degree": 0.4, "hybrid_rank": 8},
                "anchor": {"resonance_degree": 0.0, "hybrid_rank": 1},
            },
            limit=3,
        )

        self.assertEqual(ranked, ["supported", "anchor", "fallback"])

    def test_risk_aware_resonance_penalizes_bridge_risk(self) -> None:
        """Bridge risk should lower otherwise energetic candidates."""
        ranked = risk_aware_resonance_ids(
            candidate_ids=["safe", "bridge"],
            signatures_by_doc={
                "safe": {
                    "hybrid_rank": 6,
                    "final_energy": 0.5,
                    "resonance_degree": 0.5,
                    "anchor_resonance": 0.5,
                    "bridge_risk": 0.0,
                    "anchor_bridge_risk": 0.0,
                },
                "bridge": {
                    "hybrid_rank": 5,
                    "final_energy": 1.0,
                    "resonance_degree": 1.0,
                    "anchor_resonance": 1.0,
                    "bridge_risk": 1.0,
                    "anchor_bridge_risk": 1.0,
                },
            },
            limit=2,
        )

        self.assertEqual(ranked[0], "safe")


if __name__ == "__main__":
    unittest.main()
