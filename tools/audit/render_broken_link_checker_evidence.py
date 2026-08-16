#!/usr/bin/env python3
"""Render deterministic SVG evidence for the Markdown link-checker audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


def render(record: dict[str, object]) -> str:
    cases = record["validation"]["cases"]
    rows = [
        ("Missing local target", cases["old_missing_target"], cases["new_missing_target"]),
        ("Invalid UTF-8", cases["old_invalid_utf8"], cases["new_invalid_utf8"]),
        ("Repository escape", "not checked", cases["new_repository_escape"]),
        ("Valid local target", "pass", cases["new_valid_target"]),
    ]
    width = 1120
    height = 370
    row_height = 58
    top = 105
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="1120" height="370" fill="white"/>',
        '<text x="40" y="42" font-family="sans-serif" font-size="24" font-weight="bold">'
        'Markdown link-checker failure-mode evidence</text>',
        '<text x="40" y="70" font-family="sans-serif" font-size="14">'
        'Synthetic software/provenance validation — not detector data</text>',
        (
            '<text x="40" y="96" font-family="sans-serif" font-size="14" '
            'font-weight="bold">Case</text>'
        ),
        (
            '<text x="390" y="96" font-family="sans-serif" font-size="14" '
            'font-weight="bold">Former current-main behavior</text>'
        ),
        (
            '<text x="760" y="96" font-family="sans-serif" font-size="14" '
            'font-weight="bold">Validated behavior</text>'
        ),
    ]
    for index, (label, old, new) in enumerate(rows):
        y = top + index * row_height
        parts.append(f'<line x1="40" y1="{y}" x2="1080" y2="{y}" stroke="#999"/>')
        parts.append(
            f'<text x="40" y="{y + 34}" font-family="sans-serif" font-size="15">'
            f'{escape(str(label))}</text>'
        )
        parts.append(
            f'<text x="390" y="{y + 34}" font-family="monospace" font-size="14">'
            f'{escape(str(old))}</text>'
        )
        parts.append(
            f'<text x="760" y="{y + 34}" font-family="monospace" font-size="14">'
            f'{escape(str(new))}</text>'
        )
    parts.extend(
        [
            '<line x1="40" y1="337" x2="1080" y2="337" stroke="#999"/>',
            '<text x="40" y="362" font-family="sans-serif" font-size="12">'
            f'Policy: {escape(str(record["policy"]))}</text>',
            '</svg>',
        ]
    )
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    args.output.write_text(render(record), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
