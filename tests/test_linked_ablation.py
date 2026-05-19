"""Tests for linked-production ablation helpers."""

from __future__ import annotations

import unittest

from scripts.evaluate_linked_ablation import DEFAULT_VARIANTS, weights_for_variant
from noetic_systems.reconciliation.graph import GraphWeights


class LinkedAblationTest(unittest.TestCase):
    """Validate focused production-ablation helper behavior."""

    def test_default_variants_cover_core_production_questions(self) -> None:
        """The default ablation set includes ranking and edge-channel controls."""
        self.assertIn("linked_static", DEFAULT_VARIANTS)
        self.assertIn("linked_auto", DEFAULT_VARIANTS)
        self.assertIn("anchors_only", DEFAULT_VARIANTS)
        self.assertIn("anchor_affinity_only", DEFAULT_VARIANTS)
        self.assertIn("support_only", DEFAULT_VARIANTS)
        self.assertIn("semantic_only", DEFAULT_VARIANTS)
        self.assertIn("lexical_only", DEFAULT_VARIANTS)

    def test_semantic_only_variant_disables_lexical_channels(self) -> None:
        """Semantic-only graph construction removes lexical and reference edges."""
        weights = weights_for_variant("semantic_only", GraphWeights())

        self.assertEqual(weights.lexical_weight, 0.0)
        self.assertGreater(weights.lexical_threshold, 1.0)
        self.assertEqual(weights.cross_reference_weight, 0.0)

    def test_lexical_only_variant_disables_semantic_channel(self) -> None:
        """Lexical-only graph construction removes semantic edges."""
        weights = weights_for_variant("lexical_only", GraphWeights())

        self.assertEqual(weights.semantic_weight, 0.0)
        self.assertGreater(weights.semantic_threshold, 1.0)

    def test_linked_auto_uses_calibrated_weights(self) -> None:
        """The auto variant receives the frozen corpus-calibrated weights."""
        auto_weights = GraphWeights(semantic_threshold=0.61, lexical_threshold=0.13)

        self.assertEqual(weights_for_variant("linked_auto", auto_weights), auto_weights)


if __name__ == "__main__":
    unittest.main()
