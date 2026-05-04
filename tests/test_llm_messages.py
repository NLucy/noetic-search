"""Tests for Responses API message and payload construction."""

import unittest

from noetic_systems.corpus import demo_corpus
from noetic_systems.database import Database
from noetic_systems.llm.experiment import build_llm_experiment
from noetic_systems.llm.messages import (
    AssistantMessage,
    DeveloperMessage,
    serialize_messages,
    ToolMessage,
    UserMessage,
)
from noetic_systems.llm.openai_client import load_env_file, OpenAIResponsesClient


class LLMMessageTests(unittest.TestCase):
    """Validate LLM message serialization and payload building."""

    def test_serializes_responses_api_messages(self) -> None:
        """Verify message classes serialize to Responses API input items.

        Returns:
            None.
        """
        messages = [
            DeveloperMessage("Use only provided evidence."),
            UserMessage("Answer the question."),
            AssistantMessage("Prior answer."),
            ToolMessage(call_id="call_123", output='{"ok": true}'),
        ]

        serialized = serialize_messages(messages)

        self.assertEqual(serialized[0]["type"], "message")
        self.assertEqual(serialized[0]["role"], "developer")
        self.assertEqual(serialized[0]["content"][0]["type"], "input_text")
        self.assertEqual(serialized[1]["role"], "user")
        self.assertEqual(serialized[2]["role"], "assistant")
        self.assertEqual(serialized[3]["type"], "function_call_output")
        self.assertEqual(serialized[3]["call_id"], "call_123")

    def test_builds_top_k_and_evidence_field_payloads(self) -> None:
        """Verify all LLM comparison surfaces build request payloads.

        Returns:
            None.
        """
        db = Database(collection_name="test_llm_payloads", reset=True)
        db.add_documents(demo_corpus())

        experiment = build_llm_experiment(
            db,
            "Should I trust the battery life claims?",
            candidate_limit=7,
            result_limit=7,
        )
        client = OpenAIResponsesClient(model="test-model")

        top_k_payload = client.request_payload(experiment.top_k_messages)
        basin_payload = client.request_payload(experiment.basin_messages)
        evidence_payload = client.request_payload(experiment.evidence_field_messages)

        self.assertEqual(top_k_payload["model"], "test-model")
        self.assertEqual(basin_payload["model"], "test-model")
        self.assertEqual(evidence_payload["model"], "test-model")
        top_k_text = top_k_payload["input"][1]["content"][0]["text"]
        basin_text = basin_payload["input"][1]["content"][0]["text"]
        evidence_text = evidence_payload["input"][1]["content"][0]["text"]
        self.assertIn("top-k retrieved chunks", top_k_text)
        self.assertIn("strongest_basin", basin_text)
        self.assertIn("evidence_field", evidence_text)
        self.assertIn("support_edges", evidence_text)

        db.reset()

    def test_loads_local_env_file_without_overriding_existing_values(self) -> None:
        """Verify `.env` loading preserves existing environment values.

        Returns:
            None.
        """
        from os import environ
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("NOETIC_TEST_ENV=from-file\n")
            environ.pop("NOETIC_TEST_ENV", None)
            load_env_file(env_path)
            self.assertEqual(environ["NOETIC_TEST_ENV"], "from-file")

            env_path.write_text("NOETIC_TEST_ENV=from-second-file\n")
            load_env_file(env_path)
            self.assertEqual(environ["NOETIC_TEST_ENV"], "from-file")
            environ.pop("NOETIC_TEST_ENV", None)


if __name__ == "__main__":
    unittest.main()
