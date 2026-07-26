#!/usr/bin/env python3
"""Render synthetic visual evidence for figure-registry provenance drift."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _short(value: str) -> str:
    return value[:12]


def render(payload: dict, output: Path) -> None:
    result = payload["behavioral_controls"]["result_path_replacement"]
    source = payload["behavioral_controls"]["source_artifact_replacement"]
    rows = [
        (
            "Result JSON",
            _short(result["bytes_used_sha256"]),
            _short(result["later_reported_sha256"]),
            result["later_hash_matches_used_bytes"],
        ),
        (
            "Source artifact",
            _short(source["copied_target_sha256"]),
            _short(source["later_reported_source_sha256"]),
            source["later_metadata_matches_copied_target"],
        ),
    ]
    width = 1000
    height = 500
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="50" y="55" font-family="sans-serif" font-size="28" '
        'font-weight="bold">Figure artifact provenance must follow the bytes used</text>',
        '<text x="50" y="88" font-family="sans-serif" font-size="16">'
        f'{html.escape(payload["policy"])}</text>',
        '<text x="50" y="130" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Synthetic replacement controls</text>',
        '<text x="50" y="165" font-family="monospace" font-size="15">Artifact</text>',
        '<text x="310" y="165" font-family="monospace" font-size="15">bytes used/copied</text>',
        '<text x="560" y="165" font-family="monospace" font-size="15">later metadata hash</text>',
        '<text x="835" y="165" font-family="monospace" font-size="15">match?</text>',
    ]
    y = 220
    for label, used, reported, matches in rows:
        lines.extend(
            [
                f'<text x="50" y="{y}" font-family="sans-serif" font-size="20">'
                f'{html.escape(label)}</text>',
                f'<text x="310" y="{y}" font-family="monospace" font-size="20">{used}</text>',
                f'<text x="560" y="{y}" font-family="monospace" font-size="20">{reported}</text>',
                f'<text x="850" y="{y}" font-family="sans-serif" font-size="20" '
                f'font-weight="bold">{"YES" if matches else "NO"}</text>',
            ]
        )
        y += 70
    lines.extend(
        [
            '<line x1="50" y1="370" x2="950" y2="370" stroke="black" stroke-width="1"/>',
            '<text x="50" y="410" font-family="sans-serif" font-size="18" '
            'font-weight="bold">Correct method:</text>',
            '<text x="210" y="410" font-family="sans-serif" font-size="18">read exact bytes once; '
            'parse/copy, hash, and size the retained snapshot; publish atomically.</text>',
            '<text x="50" y="455" font-family="sans-serif" font-size="14">Synthetic software '
            'evidence only; no scientific figure value or uncertainty is validated.</text>',
            '</svg>',
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.validation.read_text(encoding="utf-8"))
    render(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
