#!/usr/bin/env python3
"""Render synthetic evidence for the strict MC weight-vector audit."""
from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path


def render(data: dict, output: Path) -> None:
    cases = data["synthetic_cases"]
    width = 1100
    row_height = 54
    height = 190 + row_height * len(cases)
    rows = []
    for index, case in enumerate(cases):
        y = 150 + index * row_height
        rows.append(
            f'<text x="45" y="{y}" font-size="18">{escape(case["case"])}</text>'
        )
        rows.append(
            f'<text x="590" y="{y}" font-size="18" font-family="monospace">'
            f'{escape(case["status"])}</text>'
        )
        rows.append(
            f'<text x="895" y="{y}" font-size="18" text-anchor="end">'
            f'{escape(case["interpretation"])}</text>'
        )
        rows.append(
            f'<line x1="35" y1="{y + 17}" x2="1065" y2="{y + 17}" '
            'stroke="currentColor" stroke-opacity="0.2"/>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<g fill="black" font-family="sans-serif">
<text x="35" y="42" font-size="28" font-weight="bold">Strict MC weight-vector validation</text>
<text x="35" y="76" font-size="17">Synthetic software/provenance evidence —
not detector data</text>
<text x="35" y="108" font-size="15">Policy: {escape(data["policy"])}</text>
<text x="45" y="132" font-size="16" font-weight="bold">Case</text>
<text x="590" y="132" font-size="16" font-weight="bold">Result</text>
<text x="895" y="132" font-size="16" font-weight="bold" text-anchor="end">Meaning</text>
{''.join(rows)}
</g>
</svg>
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("validation_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    data = json.loads(args.validation_json.read_text(encoding="utf-8"))
    render(data, args.output_svg)


if __name__ == "__main__":
    main()
