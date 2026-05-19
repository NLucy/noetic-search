"""Tests for unsupervised graph calibration."""

from __future__ import annotations

import unittest

from noetic_systems.database import Database
from noetic_systems.reconciliation.calibration import (
    GRAPH_OBJECTIVES,
    MANUAL_GRAPH_OBJECTIVES,
    calibrate_corpus_graph_formula,
    calibrate_corpus_graph_weights,
    calibrate_graph_weights,
    degree_centralization,
    largest_component_ratio,
)
from noetic_systems.search.semantic import SearchResult


class GraphCalibrationTests(unittest.TestCase):
    """Validate candidate-field graph calibration."""

    def test_calibration_returns_profile_and_weights(self) -> None:
        """Calibration produces bounded graph settings without labels."""
        db = Database(collection_name="test_graph_calibration", reset=True)
        try:
            documents = [
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
                {
                    "id": "city",
                    "text": "Title: Greenwich Village\nA neighborhood in New York City.",
                    "metadata": {"title": "Greenwich Village"},
                },
            ]
            db.add_documents(documents)
            candidates = [
                SearchResult(doc["id"], doc["text"], 1.0 - index * 0.2, doc["metadata"])
                for index, doc in enumerate(documents)
            ]

            weights, profile = calibrate_graph_weights(db, candidates)

            self.assertGreater(profile.pair_count, 0)
            self.assertGreaterEqual(weights.semantic_threshold, 0.42)
            self.assertLessEqual(weights.semantic_threshold, 0.62)
            self.assertGreater(weights.cross_reference_weight, 0.0)
        finally:
            db.reset()

    def test_corpus_calibration_uses_index_documents(self) -> None:
        """Corpus calibration returns one reusable graph setting."""
        db = Database(collection_name="test_corpus_graph_calibration", reset=True)
        try:
            db.add_documents(
                [
                    {
                        "id": "alpha",
                        "text": "Title: Alpha\nAlpha mentions Beta.",
                        "metadata": {"title": "Alpha"},
                    },
                    {
                        "id": "beta",
                        "text": "Title: Beta\nBeta mentions Gamma.",
                        "metadata": {"title": "Beta"},
                    },
                    {
                        "id": "gamma",
                        "text": "Title: Gamma\nGamma contains the answer.",
                        "metadata": {"title": "Gamma"},
                    },
                ]
            )

            weights, profile = calibrate_corpus_graph_weights(db, sample_limit=3)

            self.assertGreater(profile.pair_count, 0)
            self.assertGreater(weights.cross_reference_weight, 0.0)
        finally:
            db.reset()

    def test_all_graph_objectives_return_weights(self) -> None:
        """Each graph-health objective derives bounded graph weights."""
        db = Database(collection_name="test_graph_objectives", reset=True)
        try:
            documents = [
                {
                    "id": "alpha",
                    "text": "Title: Alpha\nAlpha mentions Beta.",
                    "metadata": {"title": "Alpha"},
                },
                {
                    "id": "beta",
                    "text": "Title: Beta\nBeta mentions Gamma.",
                    "metadata": {"title": "Beta"},
                },
                {
                    "id": "gamma",
                    "text": "Title: Gamma\nGamma contains the answer.",
                    "metadata": {"title": "Gamma"},
                },
            ]
            db.add_documents(documents)
            for objective in GRAPH_OBJECTIVES:
                weights, profile = calibrate_corpus_graph_weights(
                    db,
                    sample_limit=3,
                    objective=objective,
                )
                self.assertGreater(profile.pair_count, 0)
                self.assertGreater(weights.semantic_weight, 0.0)
                self.assertGreater(weights.cross_reference_weight, 0.0)
        finally:
            db.reset()

    def test_auto_calibration_scores_candidate_formulas(self) -> None:
        """Auto calibration should select from unsupervised graph objectives."""
        db = Database(collection_name="test_auto_graph_calibration", reset=True)
        try:
            db.add_documents(
                [
                    {
                        "id": "alpha",
                        "text": "Title: Alpha\nAlpha references Beta and Gamma.",
                        "metadata": {"title": "Alpha"},
                    },
                    {
                        "id": "beta",
                        "text": "Title: Beta\nBeta references Alpha and Gamma.",
                        "metadata": {"title": "Beta"},
                    },
                    {
                        "id": "gamma",
                        "text": "Title: Gamma\nGamma references Alpha and Beta.",
                        "metadata": {"title": "Gamma"},
                    },
                    {
                        "id": "delta",
                        "text": "Title: Delta\nDelta is unrelated background material.",
                        "metadata": {"title": "Delta"},
                    },
                ]
            )

            result = calibrate_corpus_graph_formula(db, sample_limit=4)
            auto_weights, auto_profile = calibrate_corpus_graph_weights(
                db,
                sample_limit=4,
                objective="auto",
            )

            self.assertGreaterEqual(len(result.candidates), len(MANUAL_GRAPH_OBJECTIVES))
            self.assertGreaterEqual(result.selected.score, result.candidates[-1].score)
            self.assertEqual(auto_weights, result.selected.weights)
            self.assertEqual(auto_profile, result.selected.profile)
        finally:
            db.reset()

    def test_standard_graph_health_measures(self) -> None:
        """Component ratio and Freeman centralization follow graph definitions."""
        adjacency = {
            "a": {"b"},
            "b": {"a", "c"},
            "c": {"b"},
            "d": set(),
        }
        degrees = {
            node: len(neighbors)
            for node, neighbors in adjacency.items()
        }

        self.assertAlmostEqual(largest_component_ratio(adjacency), 0.75)
        self.assertAlmostEqual(degree_centralization(degrees), 4 / 6)


if __name__ == "__main__":
    unittest.main()
