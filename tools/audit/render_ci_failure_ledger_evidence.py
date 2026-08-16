#!/usr/bin/env python3
"""Render deterministic SVG evidence from a CI failure-ledger JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


def render(payload: dict[str, object]) -> str:
    candidate = payload["candidate"]
    assert isinstance(candidate, dict)
    counts = candidate["family_counts"]
    assert isinstance(counts, dict)
    items = sorted(
        ((str(key), int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], item[0]),
    )
    width = 1000
    row_height = 38
    height = 190 + row_height * len(items)
    max_count = max((count for _, count in items), default=1)
    bars = []
    for index, (label, count) in enumerate(items):
        y = 128 + index * row_height
        bar_width = int(620 * count / max_count)
        bars.append(
            f'<text x="20" y="{y + 20}" font-size="16">{escape(label)}</text>'
            f'<rect x="320" y="{y}" width="{bar_width}" height="24" fill="#4d4d4d"/>'
            f'<text x="{330 + bar_width}" y="{y + 19}" font-size="15">{count}</text>'
        )
    attribution = payload["causal_attribution"]
    assert isinstance(attribution, dict)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<text x="20" y="34" font-size="24" font-weight="bold">'
        'Repository CI failure ledger</text>'
        f'<text x="20" y="64" font-size="16">failed tests: {candidate["failure_count"]}</text>'
        f'<text x="20" y="88" font-size="16">attribution: '
        f'{escape(str(attribution["mode"]))}</text>'
        '<text x="20" y="112" font-size="14">'
        'Software/CI evidence only; no detector or physics result.</text>'
        + "".join(bars)
        + '</svg>\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.write_text(render(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
