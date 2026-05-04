"""Small built-in corpus used by demos and smoke tests."""

from __future__ import annotations

from typing import Any


def demo_corpus() -> list[dict[str, Any]]:
    """Return the built-in demonstration corpus.

    Returns:
        Documents with `id`, `text`, and `metadata` fields suitable for loading into
        the local database wrapper.
    """
    return [
        {
            "id": "battery.lab",
            "text": "Lab test shows the phone battery lasts 14 hours under mixed use.",
            "metadata": {"source": "lab", "stance": "battery-strong"},
        },
        {
            "id": "battery.review",
            "text": "Long-term reviewers report excellent battery life after two weeks.",
            "metadata": {"source": "review", "stance": "battery-strong"},
        },
        {
            "id": "battery.forum",
            "text": "Forum complaints say battery drains quickly while gaming.",
            "metadata": {"source": "forum", "stance": "battery-weak"},
        },
        {
            "id": "camera.lab",
            "text": "Camera samples are sharp in daylight but noisy in low light.",
            "metadata": {"source": "lab", "stance": "camera-mixed"},
        },
        {
            "id": "camera.review",
            "text": "Reviewers praise natural colors and fast autofocus.",
            "metadata": {"source": "review", "stance": "camera-strong"},
        },
        {
            "id": "price.note",
            "text": "The device is cheaper than competing flagship phones.",
            "metadata": {"source": "market", "stance": "price-strong"},
        },
        {
            "id": "price.warning",
            "text": "Repair costs are high despite the lower purchase price.",
            "metadata": {"source": "market", "stance": "price-mixed"},
        },
    ]
