#!/usr/bin/env python3
"""Render synthetic documentation evidence for the MV3 WIKI synchronization gate."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _text(x: int, y: int, value: str, *, size: int = 18, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
        f'font-weight="{weight}">{html.escape(value)}</text>'
    )


def render(payload: dict, output: Path) -> None:
    values = payload["reconstructed"]
    width, height = 1200, 720
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="1200" height="720" fill="white"/>',
        _text(50, 55, "MV3 public-summary provenance remediation", size=28, weight="bold"),
        _text(50, 88, "Synthetic software/documentation validation — not detector data", size=17),
        '<rect x="50" y="125" width="500" height="230" fill="#f4f4f4" '
        'stroke="black" stroke-width="2"/>',
        _text(75, 165, "Former public wording", size=22, weight="bold"),
        _text(75, 205, "Rounded-only B8 fractions", size=19),
        _text(75, 240, "χ²/ndf label reported as 68,269.4", size=19),
        _text(75, 275, "Claimed exact counts/statistic were absent", size=19),
        _text(75, 325, "Status: provenance narrative FLAWED", size=19, weight="bold"),
        '<path d="M570 240 L635 240" stroke="black" stroke-width="5"/>',
        '<path d="M635 240 L615 225 M635 240 L615 255" stroke="black" '
        'stroke-width="5" fill="none"/>',
        '<rect x="660" y="125" width="490" height="430" fill="white" '
        'stroke="black" stroke-width="2"/>',
        _text(685, 165, "Exact tracked-summary wording", size=22, weight="bold"),
        _text(
            685,
            210,
            f"Data B8: {values['data_counts']['B8']}/{values['data_total']}",
            size=19,
        ),
        _text(685, 245, f"Fraction: {values['data_b8_fraction']!r}", size=18),
        _text(
            685,
            295,
            f"MC B8: {values['mc_counts']['B8']}/{values['mc_total']}",
            size=19,
        ),
        _text(685, 330, f"Fraction: {values['mc_b8_fraction']!r}", size=18),
        _text(685, 380, f"Pearson χ²: {values['chi2']!r}", size=18),
        _text(685, 415, f"ndf: {values['ndf']}", size=18),
        _text(685, 450, f"χ²/ndf: {values['chi2_ndf']!r}", size=18),
        _text(685, 505, "Boundary retained: FLAWED", size=20, weight="bold"),
        _text(685, 535, "BLK-MV3-LEGACY-001 remains open", size=17),
        '<rect x="50" y="590" width="1100" height="80" fill="#f4f4f4" '
        'stroke="black" stroke-width="2"/>',
        _text(
            75,
            625,
            "Interpretation: fixed-source arithmetic is reproducible; geometry, selection,",
            size=18,
        ),
        _text(
            75,
            654,
            "response, covariance, p-value interpretation, and systematics remain unresolved.",
            size=18,
        ),
        "</svg>",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(elements) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.validation_json.read_text(encoding="utf-8"))
    render(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
