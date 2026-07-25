#!/usr/bin/env python3
"""Render visual evidence for the Cluster A row/weight semantics correction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def text(x: int, y: int, size: int, value: str, *, bold: bool = False) -> str:
    weight = ' font-weight="bold"' if bold else ""
    return (
        f'<text x="{x}" y="{y}" font-family="sans-serif" '
        f'font-size="{size}"{weight}>{value}</text>'
    )


def render(payload: dict, output: Path) -> None:
    old = payload["negative_control"]["unweighted_bin_value"]
    new = payload["corrected_control"]["primary_weight_sum"]
    width = 960
    height = 520
    scale = 5.5
    old_w = old * scale
    new_w = new * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        text(40, 50, 26, "Cluster A data-side semantics validation", bold=True),
        text(40, 82, 15, "Software/provenance evidence — not detector-performance data"),
        text(40, 135, 18, "MC density for two events in one hexbin", bold=True),
        text(40, 180, 15, "Former plot: event count (PrimaryWeight ignored)"),
        f'<rect x="330" y="160" width="{old_w}" height="28" fill="#999"/>',
        f'<text x="{345 + old_w}" y="181" font-family="monospace" '
        f'font-size="16">{old}</text>',
        text(40, 235, 15, "Corrected plot: sum PrimaryWeight"),
        f'<rect x="330" y="215" width="{new_w}" height="28" fill="#4477aa"/>',
        f'<text x="{345 + new_w}" y="236" font-family="monospace" '
        f'font-size="16">{new}</text>',
        text(40, 310, 18, "Data-table interpretation", bold=True),
        '<rect x="40" y="335" width="880" height="115" rx="10" '
        'fill="#f5f5f5" stroke="#555"/>',
        text(
            60,
            370,
            16,
            "632,939 table rows and 385,984 composite keys are distinct denominators.",
        ),
        text(
            60,
            400,
            16,
            "Outputs now label row counts and preserve the composite-merge blocker.",
        ),
        text(
            60,
            430,
            16,
            "Invalid numeric cells fail closed instead of becoming zero or infinity.",
        ),
        f'<text x="40" y="490" font-family="monospace" font-size="13">'
        f'policy: {payload["policy"]}</text>',
        "</svg>",
    ]
    output.write_text("\n".join(parts) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(json.loads(args.input.read_text()), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
