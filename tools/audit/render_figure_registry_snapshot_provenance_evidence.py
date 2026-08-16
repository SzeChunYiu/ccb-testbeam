#!/usr/bin/env python3
"""Render before/after evidence for figure-registry snapshot provenance."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _short(value: str) -> str:
    return value[:12]


def render(payload: dict, output: Path) -> None:
    result = payload["controls"]["result_path_replacement"]
    source = payload["controls"]["source_artifact_replacement"]
    rows = [
        (
            "Result JSON",
            _short(result["snapshot_sha256"]),
            _short(result["replacement_sha256"]),
            _short(result["recorded_sha256"]),
            result["recorded_matches_snapshot"],
        ),
        (
            "Source artifact",
            _short(source["snapshot_sha256"]),
            _short(source["replacement_sha256"]),
            _short(source["published_target_sha256"]),
            source["published_matches_snapshot"],
        ),
    ]
    width = 1120
    height = 560
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="50" y="55" font-family="sans-serif" font-size="28" '
        'font-weight="bold">Figure provenance is bound to one exact byte snapshot</text>',
        '<text x="50" y="88" font-family="sans-serif" font-size="16">'
        f'{html.escape(payload["policy"])}</text>',
        '<text x="50" y="125" font-family="sans-serif" font-size="18" '
        f'font-weight="bold">Exact-current audit: {payload["current_audit"]["status"]} '
        f'({payload["current_audit"]["finding_count"]} findings)</text>',
        '<text x="50" y="175" font-family="monospace" font-size="15">Artifact</text>',
        '<text x="285" y="175" font-family="monospace" font-size="15">snapshot hash</text>',
        '<text x="500" y="175" font-family="monospace" font-size="15">later path hash</text>',
        '<text x="735" y="175" font-family="monospace" font-size="15">recorded/published</text>',
        '<text x="1000" y="175" font-family="monospace" font-size="15">match</text>',
    ]
    y = 235
    for label, snapshot, replacement, recorded, matches in rows:
        lines.extend(
            [
                f'<text x="50" y="{y}" font-family="sans-serif" font-size="20">'
                f'{html.escape(label)}</text>',
                f'<text x="285" y="{y}" font-family="monospace" font-size="19">'
                f'{snapshot}</text>',
                f'<text x="500" y="{y}" font-family="monospace" font-size="19">'
                f'{replacement}</text>',
                f'<text x="735" y="{y}" font-family="monospace" font-size="19">'
                f'{recorded}</text>',
                f'<text x="1010" y="{y}" font-family="sans-serif" font-size="20" '
                f'font-weight="bold">{"YES" if matches else "NO"}</text>',
            ]
        )
        y += 75
    lines.extend(
        [
            '<line x1="50" y1="390" x2="1070" y2="390" stroke="black" '
            'stroke-width="1"/>',
            '<text x="50" y="430" font-family="sans-serif" font-size="18" '
            'font-weight="bold">Remediated path:</text>',
            '<text x="225" y="430" font-family="sans-serif" font-size="18">read once; '
            'decode/parse or publish retained bytes; hash and size the same snapshot.</text>',
            '<text x="50" y="470" font-family="sans-serif" font-size="18">Source artifacts '
            'use same-directory temporary publication, flush, fsync, os.replace, and final-target '
            'verification.</text>',
            '<text x="50" y="520" font-family="sans-serif" font-size="14">Synthetic software '
            'evidence only; no underlying scientific value or uncertainty is validated.</text>',
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
