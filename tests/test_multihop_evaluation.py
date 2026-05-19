"""Tests for shared multi-hop benchmark conversion."""

from __future__ import annotations

import unittest

from noetic_systems.evaluation.multihop import (
    convert_hotpot_like_records,
    convert_musique_records,
    document_id,
)


class MultiHopConversionTests(unittest.TestCase):
    """Validate common paragraph-level retrieval conversion."""

    def test_convert_hotpot_like_records_support_titles(self) -> None:
        """Support titles identify target paragraphs."""
        record = {
            "id": "wiki-case",
            "question": "Who connects Alpha and Beta?",
            "answer": "Gamma",
            "context": {
                "title": ["Alpha", "Beta", "Decoy"],
                "sentences": [
                    ["Alpha mentions Gamma."],
                    ["Beta was founded by Gamma."],
                    ["No useful evidence."],
                ],
            },
            "supporting_facts": {
                "title": ["Alpha", "Beta"],
                "sent_id": [0, 0],
            },
        }

        documents, cases = convert_hotpot_like_records([record], source="2wiki")

        self.assertEqual(len(documents), 3)
        self.assertEqual(len(cases), 1)
        self.assertEqual(
            cases[0].target_ids,
            frozenset(
                {
                    document_id("2wiki", "Alpha", "Alpha mentions Gamma."),
                    document_id("2wiki", "Beta", "Beta was founded by Gamma."),
                }
            ),
        )

    def test_convert_musique_records_uses_support_indices(self) -> None:
        """MuSiQue decomposition support indexes become target ids."""
        record = {
            "id": "musique-case",
            "question": "Who founded the company that distributed UHF?",
            "answer": "Mike Medavoy",
            "answerable": True,
            "paragraphs": [
                {
                    "idx": 0,
                    "title": "Distractor",
                    "paragraph_text": "Irrelevant text.",
                    "is_supporting": False,
                },
                {
                    "idx": 2,
                    "title": "UHF",
                    "paragraph_text": "UHF was distributed by Orion Pictures.",
                    "is_supporting": False,
                },
                {
                    "idx": 5,
                    "title": "Orion Pictures",
                    "paragraph_text": "Orion Pictures was founded by Mike Medavoy.",
                    "is_supporting": False,
                },
            ],
            "question_decomposition": [
                {"paragraph_support_idx": 2},
                {"paragraph_support_idx": 5},
            ],
        }

        documents, cases = convert_musique_records([record])

        self.assertEqual(len(documents), 3)
        self.assertEqual(len(cases), 1)
        self.assertEqual(
            cases[0].target_ids,
            frozenset(
                {
                    document_id(
                        "musique",
                        "UHF",
                        "UHF was distributed by Orion Pictures.",
                    ),
                    document_id(
                        "musique",
                        "Orion Pictures",
                        "Orion Pictures was founded by Mike Medavoy.",
                    ),
                }
            ),
        )

    def test_convert_musique_records_skips_unanswerable(self) -> None:
        """Unanswerable MuSiQue records are excluded."""
        record = {
            "id": "bad-case",
            "question": "Question?",
            "answerable": False,
            "paragraphs": [],
            "question_decomposition": [],
        }

        documents, cases = convert_musique_records([record])

        self.assertEqual(documents, [])
        self.assertEqual(cases, [])


if __name__ == "__main__":
    unittest.main()
