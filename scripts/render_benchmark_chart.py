#!/usr/bin/env python
"""Render the external benchmark summary chart.

The chart is intentionally generated from an anchor-policy benchmark report so
the visual can be reproduced after benchmark runs instead of hand-edited.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

WIDTH = 1080
HEIGHT = 620
PLOT_LEFT = 118
PLOT_TOP = 146
PLOT_WIDTH = 864
PLOT_HEIGHT = 320
BAR_WIDTH = 26
HYBRID_COLOR = "#2563eb"
NOETIC_COLOR = "#0f766e"
PAPER = "#f7f4ee"
WHITE = "#fffdf8"
INK = "#111827"
MUTED = "#526173"
LINE = "#d7d0c5"
FONT = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif"


def y_position(value: float) -> float:
    """Map a recall value to the chart y coordinate.

    Args:
        value: Recall value in the `[0, 1]` interval.

    Returns:
        Y coordinate.
    """
    return PLOT_TOP + PLOT_HEIGHT - (value * PLOT_HEIGHT)


def bar(
    x: float,
    value: float,
    color: str,
    *,
    opacity: float = 1.0,
) -> str:
    """Render one vertical bar.

    Args:
        x: Left coordinate.
        value: Recall value.
        color: Bar fill color.
        opacity: Fill opacity.

    Returns:
        SVG markup.
    """
    y = y_position(value)
    height = PLOT_TOP + PLOT_HEIGHT - y
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{BAR_WIDTH}" '
        f'height="{height:.1f}" rx="4" fill="{color}" opacity="{opacity}"/>'
    )


def label(
    x: float,
    y: float,
    text: str,
    *,
    size: int = 14,
    color: str = INK,
    anchor: str = "middle",
    weight: int = 500,
) -> str:
    """Render an SVG text label.

    Args:
        x: X coordinate.
        y: Y coordinate.
        text: Text content.
        size: Font size.
        color: Text color.
        anchor: SVG text anchor.
        weight: Font weight.

    Returns:
        SVG markup.
    """
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'fill="{color}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}">{text}</text>'
    )


def render(summary: dict[str, Any]) -> str:
    """Render the benchmark chart SVG.

    Args:
        summary: Benchmark suite summary.

    Returns:
        SVG document.
    """
    datasets = [
        ("hotpotqa", "HotpotQA"),
        ("2wikimultihopqa", "2WikiMultiHopQA"),
        ("musique", "MuSiQue"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        '<title id="title">Hybrid versus Noetic protected-anchor support recall</title>',
        '<desc id="desc">Grouped bar chart comparing Hybrid and Noetic protected three-anchor support recall at 5 and 10 across HotpotQA, 2WikiMultiHopQA, and MuSiQue.</desc>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}"/>',
        f'<rect x="28" y="28" width="{WIDTH - 56}" height="{HEIGHT - 56}" rx="10" fill="{WHITE}" stroke="{LINE}"/>',
        label(64, 76, "External multi-hop support recall", size=30, anchor="start", weight=800),
        label(64, 106, "Hybrid baseline versus Noetic with 3 protected anchors. 300 cases per dataset.", size=15, color=MUTED, anchor="start"),
    ]

    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y_position(tick)
        parts.append(f'<line x1="{PLOT_LEFT}" y1="{y:.1f}" x2="{PLOT_LEFT + PLOT_WIDTH}" y2="{y:.1f}" stroke="{LINE}"/>')
        parts.append(label(92, y + 5, f"{tick:.2f}", size=12, color=MUTED))

    parts.extend(
        [
            f'<line x1="{PLOT_LEFT}" y1="{PLOT_TOP + PLOT_HEIGHT}" x2="{PLOT_LEFT + PLOT_WIDTH}" y2="{PLOT_TOP + PLOT_HEIGHT}" stroke="{INK}" stroke-width="1.5"/>',
            f'<rect x="716" y="68" width="16" height="16" rx="3" fill="{HYBRID_COLOR}"/>',
            label(740, 81, "Hybrid", size=14, anchor="start"),
            f'<rect x="812" y="68" width="16" height="16" rx="3" fill="{NOETIC_COLOR}"/>',
            label(836, 81, "Noetic 3-anchor", size=14, anchor="start"),
        ]
    )

    group_centers = [244, 550, 856]
    for (dataset_key, dataset_label), center in zip(datasets, group_centers):
        rows = summary[dataset_key]["metrics"]
        values = [
            (
                "R@5",
                rows["hybrid"]["@5"]["recall"],
                rows["anchors_3_protected"]["@5"]["recall"],
            ),
            (
                "R@10",
                rows["hybrid"]["@10"]["recall"],
                rows["anchors_3_protected"]["@10"]["recall"],
            ),
        ]
        x_positions = [center - 72, center + 24]
        for (cutoff, hybrid, auto), x in zip(values, x_positions):
            parts.append(bar(x, hybrid, HYBRID_COLOR))
            parts.append(bar(x + BAR_WIDTH + 8, auto, NOETIC_COLOR))
            parts.append(label(x + 13, y_position(hybrid) - 8, f"{hybrid:.3f}", size=12))
            parts.append(label(x + BAR_WIDTH + 21, y_position(auto) - 8, f"{auto:.3f}", size=12))
            parts.append(label(x + BAR_WIDTH + 4, PLOT_TOP + PLOT_HEIGHT + 28, cutoff, size=13, color=MUTED))
        parts.append(label(center, PLOT_TOP + PLOT_HEIGHT + 70, dataset_label, size=17, weight=800))

    parts.append(label(64, 586, "Metric: support recall. Source: reports/anchor_policy_300.json.", size=13, color=MUTED, anchor="start"))
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    """Run the chart renderer.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, default=Path("reports/anchor_policy_300.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/assets/benchmark_summary.svg"))
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(summary))


if __name__ == "__main__":
    main()
