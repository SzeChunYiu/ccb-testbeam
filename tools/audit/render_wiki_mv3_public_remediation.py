#!/usr/bin/env python3
"""Render deterministic SVG evidence for the MV3 public-WIKI remediation."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def label(
    x: int,
    y: int,
    value: str,
    size: int = 22,
    weight: str = "normal",
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="DejaVu Sans, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{html.escape(value)}</text>'
    )


def render(payload: dict[str, Any]) -> str:
    before = payload["before"]
    after = payload["after"]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="760" '
        'viewBox="0 0 1280 760">',
        '<rect width="1280" height="760" fill="white"/>',
        label(55, 58, "MV3 public-WIKI claim remediation", 34, "bold"),
        label(
            55,
            96,
            "Documentation/provenance evidence only — not detector data or physics closure",
            19,
        ),
        '<rect x="55" y="140" width="560" height="450" fill="#f2f2f2" '
        'stroke="#222" stroke-width="2"/>',
        '<rect x="665" y="140" width="560" height="450" fill="#f8f8f8" '
        'stroke="#222" stroke-width="2"/>',
        label(85, 185, "Before", 27, "bold"),
        label(695, 185, "After", 27, "bold"),
        label(85, 235, f"Section-binding status: {before['status']}", 22, "bold"),
        label(85, 275, f"Location-bound findings: {before['n_issues']}", 22),
        label(85, 325, "Rounded values and absence prose", 20),
        label(85, 365, "Exact tracked evidence not bound to use sites", 20),
        label(695, 235, f"Section-binding status: {after['status']}", 22, "bold"),
        label(695, 275, f"Location-bound findings: {after['n_issues']}", 22),
        label(695, 325, "Exact counts and Pearson arithmetic", 20),
        label(695, 365, "FLAWED boundary retained at six use sites", 20),
        label(695, 415, "B8 acceptance correction remains blocked", 20, "bold"),
        label(55, 630, f"Policy: {payload['policy']}", 18),
        label(55, 665, f"Committed WIKI blob: {after['wiki_blob_sha']}", 18),
        label(55, 700, f"Generation command: {payload['generation_command']}", 16),
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
