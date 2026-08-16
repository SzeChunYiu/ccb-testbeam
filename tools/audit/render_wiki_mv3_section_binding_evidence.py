#!/usr/bin/env python3
"""Render deterministic SVG evidence for MV3 WIKI section binding."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def text(x: int, y: int, value: str, size: int = 22, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="DejaVu Sans, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{html.escape(value)}</text>'
    )


def render(payload: dict[str, Any]) -> str:
    current = payload["current_wiki"]
    synthetic = payload["synthetic_regression"]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="760" '
        'viewBox="0 0 1280 760">',
        '<rect width="1280" height="760" fill="white"/>',
        text(55, 58, "MV3 WIKI section-binding validation", 34, "bold"),
        text(
            55,
            96,
            "Software/documentation evidence only — not detector data or physics closure",
            19,
        ),
        '<rect x="55" y="140" width="560" height="450" fill="#f2f2f2" '
        'stroke="#222" stroke-width="2"/>',
        '<rect x="665" y="140" width="560" height="450" fill="#f8f8f8" '
        'stroke="#222" stroke-width="2"/>',
        text(85, 185, "Current root WIKI", 27, "bold"),
        text(695, 185, "Synthetic token-dump regression", 27, "bold"),
        text(85, 235, f"Status: {current['status']}", 23, "bold"),
        text(85, 275, f"Section findings: {current['n_issues']}", 23),
        text(85, 320, "Rounded canonical row remains public", 20),
        text(85, 360, "Exact values are not bound to six use sites", 20),
        text(85, 415, "Required action: patch canonical sections", 20, "bold"),
        text(695, 235, "All exact tokens present globally", 21),
        text(695, 275, "Stale canonical row intentionally retained", 21),
        text(695, 315, "Global-token predicate: satisfied", 21),
        text(
            695,
            355,
            f"Section-binding validator: {synthetic['status']}",
            21,
            "bold",
        ),
        text(695, 395, f"Findings: {synthetic['n_issues']}", 21),
        text(695, 450, "Conclusion: token location is evidence", 21, "bold"),
        text(55, 635, f"Policy: {payload['policy']}", 18),
        text(55, 668, f"WIKI SHA-256: {current['sha256']}", 18),
        text(55, 701, f"Generation command: {payload['generation_command']}", 16),
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.json.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
