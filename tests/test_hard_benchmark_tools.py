"""Tests for hard benchmark generation utilities."""

import importlib.util
import unittest
from pathlib import Path


def load_generator():
    """Load the hard benchmark generator module from its file path.

    Returns:
        Imported generator module.
    """
    path = Path(__file__).parent / "data" / "generate_hard_rag_benchmark.py"
    spec = importlib.util.spec_from_file_location("generate_hard_rag_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HardBenchmarkToolTests(unittest.TestCase):
    """Validate hard benchmark generator behavior."""

    def test_generator_scales_cases_and_distractors(self) -> None:
        """Verify variants and distractor counts scale corpus size.

        Returns:
            None.
        """
        generator = load_generator()

        benchmark = generator.generate(total_distractors=25, variants=3, seed=123)

        self.assertEqual(benchmark["metadata"]["distractor_documents"], 25)
        self.assertEqual(benchmark["metadata"]["variant_count"], 3)
        self.assertEqual(benchmark["metadata"]["eval_case_count"], 30)
        self.assertEqual(len(benchmark["cases"]), 30)
        self.assertEqual(len(benchmark["corpus"]), 30 * 14 + 25)

    def test_variant_ids_do_not_collide(self) -> None:
        """Verify generated variant document ids remain unique.

        Returns:
            None.
        """
        generator = load_generator()

        benchmark = generator.generate(total_distractors=5, variants=4, seed=456)
        ids = [doc["id"] for doc in benchmark["corpus"]]

        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("payments_release", benchmark["cases"])
        self.assertIn("payments_release_v001", benchmark["cases"])


if __name__ == "__main__":
    unittest.main()
