"""OpenAI Responses API client wrapper."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from noetic_systems.llm.messages import Message, serialize_messages


DEFAULT_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class OpenAIResponsesClient:
    """Small wrapper around the OpenAI Responses API.

    Attributes:
        model: Default model identifier used when no environment override exists.
    """

    model: str = DEFAULT_MODEL

    def create(
        self,
        messages: list[Message],
        *,
        max_output_tokens: int = 800,
        temperature: float | None = None,
    ) -> str:
        """Call the Responses API and return output text.

        Args:
            messages: Messages to serialize into the Responses API `input` field.
            max_output_tokens: Maximum generated output tokens.
            temperature: Optional sampling temperature.

        Returns:
            Response output text.

        Raises:
            RuntimeError: If the OpenAI SDK is not installed.
        """
        load_env_file()
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The OpenAI SDK is not installed. Install the project with the "
                "openai dependency before calling the Responses API."
            ) from exc

        client = OpenAI()
        kwargs: dict[str, Any] = {
            "model": os.getenv("NOETIC_OPENAI_MODEL", self.model),
            "input": serialize_messages(messages),
            "max_output_tokens": max_output_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = client.responses.create(**kwargs)
        return response.output_text

    def request_payload(
        self,
        messages: list[Message],
        *,
        max_output_tokens: int = 800,
    ) -> dict[str, Any]:
        """Return the Responses API payload without making a network call.

        Args:
            messages: Messages to serialize into the Responses API `input` field.
            max_output_tokens: Maximum generated output tokens.

        Returns:
            Request payload dictionary.
        """
        load_env_file()
        return {
            "model": os.getenv("NOETIC_OPENAI_MODEL", self.model),
            "input": serialize_messages(messages),
            "max_output_tokens": max_output_tokens,
        }


def load_env_file(path: str | Path = ".env") -> None:
    """Load simple `KEY=VALUE` entries from a local environment file.

    Existing environment variables are left unchanged.

    Args:
        path: Path to the environment file.

    Returns:
        None.
    """
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
