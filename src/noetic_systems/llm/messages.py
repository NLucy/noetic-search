"""Responses API message primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


Role = Literal["assistant", "developer", "system", "user"]


class Message(Protocol):
    """Serializable input item for the Responses API."""

    def to_response_input(self) -> dict[str, Any]:
        """Return this message as a Responses API input item.

        Returns:
            Dictionary accepted in a Responses API `input` list.
        """
        ...


@dataclass(frozen=True)
class TextMessage:
    """Text message with a Responses API role.

    Attributes:
        content: Message text.
        role: Responses API role.
    """

    content: str
    role: Role

    def to_response_input(self) -> dict[str, Any]:
        """Return this text message as a Responses API input item.

        Returns:
            Dictionary with `type`, `role`, and text `content` fields.
        """
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
    """Function tool output item for the Responses API.

    Attributes:
        call_id: Identifier of the tool call being answered.
        output: Tool output text.
    """

    call_id: str
    output: str

    def to_response_input(self) -> dict[str, Any]:
        """Return this tool output as a Responses API input item.

        Returns:
            Function-call output dictionary.
        """
        return {
            "type": "function_call_output",
            "call_id": self.call_id,
            "output": self.output,
        }


def serialize_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Serialize messages to Responses API input items.

    Args:
        messages: Message objects implementing `to_response_input`.

    Returns:
        Responses API input dictionaries.
    """
    return [message.to_response_input() for message in messages]
