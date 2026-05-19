"""Tests for HotpotQA evaluation conversion."""

from __future__ import annotations

import unittest

from noetic_systems.evaluation.hotpotqa import convert_records, document_id


class HotpotConversionTests(unittest.TestCase):
    """Validate paragraph conversion and support-target extraction."""

    def test_convert_records_builds_documents_and_targets(self) -> None:
        """Supporting fact titles become target document ids."""
        record = {
            "id": "case-1",
            "question": "Which city connects Alpha and Beta?",
            "answer": "Paris",
            "context": {
                "title": ["Alpha", "Beta", "Distractor"],
                "sentences": [
                    ["Alpha was founded in Paris."],
                    ["Beta later moved its office to Paris."],
                    ["This paragraph is unrelated."],
                ],
            },
            "supporting_facts": {
                "title": ["Alpha", "Beta"],
                "sent_id": [0, 0],
            },
        }

        documents, cases = convert_records([record])

        self.assertEqual(len(documents), 3)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].id, "case-1")
        self.assertEqual(
            cases[0].target_ids,
            frozenset(
                {
                    document_id("Alpha", ["Alpha was founded in Paris."]),
                    document_id("Beta", ["Beta later moved its office to Paris."]),
                }
            ),
        )

    def test_convert_records_skips_cases_without_targets(self) -> None:
        """Cases without matching support paragraphs are not evaluated."""
        record = {
            "id": "case-2",
            "question": "Question?",
            "answer": "Answer",
            "context": {
                "title": ["Only Distractor"],
                "sentences": [["No support here."]],
            },
            "supporting_facts": {
                "title": ["Missing"],
                "sent_id": [0],
            },
        }

        documents, cases = convert_records([record])

        self.assertEqual(len(documents), 1)
        self.assertEqual(cases, [])


if __name__ == "__main__":
    unittest.main()
