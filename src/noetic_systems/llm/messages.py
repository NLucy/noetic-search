"""Responses API message primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


Role = Literal["assistant", "developer", "system", "user"]


class Message(Protocol):
    """Serializable input item for the Responses API."""

    def to_response_input(self) -> dict[str, Any]:
        """Return this message as a Responses API input item."""
        ...


@dataclass(frozen=True)
class TextMessage:
    """Text message with a Responses API role."""

    content: str
    role: Role

    def to_response_input(self) -> dict[str, Any]:
        return {
            "type": "message",
            "role": self.role,
            "content": [
                {
                    "type": "input_text",
                    "text": self.content,
                }
            ],
        }


@dataclass(frozen=True)
class AssistantMessage(TextMessage):
    """Previous assistant message."""

    content: str
    role: Role = "assistant"


@dataclass(frozen=True)
class DeveloperMessage(TextMessage):
    """Application-level instruction message."""

    content: str
    role: Role = "developer"


@dataclass(frozen=True)
class SystemMessage(TextMessage):
    """System-level instruction message."""

    content: str
    role: Role = "system"


@dataclass(frozen=True)
class UserMessage(TextMessage):
    """End-user message."""

    content: str
    role: Role = "user"


@dataclass(frozen=True)
class ToolMessage:
    """Function tool output item for the Responses API."""

    call_id: str
    output: str

    def to_response_input(self) -> dict[str, Any]:
        return {
            "type": "function_call_output",
            "call_id": self.call_id,
            "output": self.output,
        }


def serialize_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Serialize messages to Responses API input items."""
    return [message.to_response_input() for message in messages]
