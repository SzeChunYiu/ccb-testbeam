#!/usr/bin/env python3
"""Render compact SVG evidence for the DeltaE CSV key-identity audit."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict, output: Path) -> None:
    controls = payload["controls"]
    findings = payload["findings"]
    rows = [
        ("Raw exact keys", "001 and 1"),
        ("Default distinct keys", str(controls["default_distinct_composite_keys"])),
        ("Lossless distinct keys", str(controls["lossless_distinct_composite_keys"])),
        ("Default false joins", str(controls["default_false_cross_file_matches"])),
        ("Lossless false joins", str(controls["lossless_cross_file_matches"])),
        ("Audit status", payload["status"]),
    ]
    width, height = 960, 470
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="40" y="48" font-family="sans-serif" font-size="26" font-weight="bold">'
        'DeltaE CSV composite-key integrity</text>',
        '<text x="40" y="78" font-family="sans-serif" font-size="15">'
        'Synthetic software/provenance control — not detector data</text>',
    ]
    y = 125
    for label, value in rows:
        parts.append(
            f'<text x="55" y="{y}" font-family="monospace" font-size="18">'
            f'{html.escape(label):28s} {html.escape(value)}</text>'
        )
        y += 40
    parts.append(
        f'<text x="55" y="{y + 5}" font-family="sans-serif" font-size="16">'
        f'Findings: {len(findings)} — exact text identifiers must be preserved before joins.</text>'
    )
    parts.append(
        '<text x="40" y="435" font-family="sans-serif" font-size="13">Policy: '
        f'{html.escape(payload["policy"])}</text>'
    )
    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    render(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
