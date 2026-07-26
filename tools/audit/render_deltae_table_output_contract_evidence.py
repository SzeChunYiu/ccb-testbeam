#!/usr/bin/env python3
"""Render accessible SVG evidence for the DeltaE event-table output contract."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Sequence


def render(payload: dict, output: Path) -> None:
    status = str(payload["status"])
    finding_count = int(payload["finding_count"])
    control = payload["former_behavior_control"]
    source = payload["source"]
    lines = [
        "Former broad fallback",
        f"Injected failure: {control['injected_failure']}",
        f"Writer calls: {' -> '.join(control['writer_calls'])}",
        f"Published: {control['published_path']}",
        f"Partial Parquet retained: {control['parquet_partial_exists']}",
        "",
        "Corrected contract",
        "Input/output alias: rejected",
        "Arbitrary Parquet error: rejected",
        "Missing engine only: CSV gzip fallback",
        "Temporary file: same directory",
        "Flush/fsync + os.replace: required",
        "Stale alternate format: rejected",
    ]
    escaped = [html.escape(line) for line in lines]
    height = 360 + 26 * len(lines)
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="{height}" '
        'viewBox="0 0 1100 {0}" role="img" aria-labelledby="title desc">'.format(height),
        '<title id="title">DeltaE event-table output integrity evidence</title>',
        '<desc id="desc">Synthetic software control contrasting broad fallback with the '
        'fail-closed atomic output contract. This is not detector data.</desc>',
        '<rect x="1" y="1" width="1098" height="{0}" fill="white" stroke="black"/>'.format(
            height - 2
        ),
        '<text x="40" y="55" font-family="sans-serif" font-size="28" font-weight="bold">'
        'DeltaE event-table output integrity</text>',
        '<text x="40" y="90" font-family="sans-serif" font-size="18">'
        f'Policy status: {html.escape(status)}; findings: {finding_count}</text>',
        '<text x="40" y="120" font-family="monospace" font-size="14">'
        f"Source SHA-256: {html.escape(source['sha256'])}</text>",
        '<line x1="40" y1="145" x2="1060" y2="145" stroke="black" stroke-width="2"/>',
    ]
    y = 185
    for line in escaped:
        headings = {"Former broad fallback", "Corrected contract"}
        weight = ' font-weight="bold"' if line in headings else ""
        body.append(
            f'<text x="60" y="{y}" font-family="sans-serif" font-size="18"{weight}>{line}</text>'
        )
        y += 26
    body.extend(
        [
            '<line x1="40" y1="{0}" x2="1060" y2="{0}" stroke="black"/>'.format(y + 10),
            '<text x="40" y="{0}" font-family="sans-serif" font-size="15">'.format(y + 40)
            + 'Interpretation: software/provenance validation only; no A-002 physics '
            + 'result is authorized.'
            + '</text>',
            '</svg>',
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(body) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("validation", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = json.loads(args.validation.read_text(encoding="utf-8"))
    render(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
