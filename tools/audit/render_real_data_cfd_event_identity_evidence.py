#!/usr/bin/env python3
"""Render deterministic SVG evidence for the CFD event-identity audit."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _bar(x: int, y: int, width: int, value: int, maximum: int, label: str) -> str:
    scaled = 0 if maximum == 0 else int(width * value / maximum)
    return (
        f'<text x="{x}" y="{y - 8}" font-size="14">'
        f'{html.escape(label)}: {value}</text>'
        f'<rect x="{x}" y="{y}" width="{width}" height="24" '
        f'fill="#e5e7eb"/>'
        f'<rect x="{x}" y="{y}" width="{scaled}" height="24" '
        f'fill="#4b5563"/>'
    )


def render(record: dict, output: Path) -> None:
    false_pair = record["behavioral_controls"]["false_cross_run_pair"]
    duplicate = record["behavioral_controls"]["duplicate_event_id"]
    values = [
        false_pair["current_event_id_only_pair_count"],
        false_pair["composite_key_pair_count"],
        duplicate["composite_key_pair_count"],
    ]
    maximum = max(values + [1])
    findings = record["finding_count"]
    status = record["status"]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="560" '
        'viewBox="0 0 960 560">',
        '<rect width="960" height="560" fill="white"/>',
        '<text x="48" y="52" font-size="26" font-weight="bold">'
        'Real-data CFD event identity audit</text>',
        '<text x="48" y="82" font-size="15">Policy: '
        f'{html.escape(record["policy"])}</text>',
        '<text x="48" y="112" font-size="18" font-weight="bold">'
        f'Status: {status} · findings: {findings}</text>',
        '<text x="48" y="158" font-size="18" font-weight="bold">'
        'Synthetic cross-run collision</text>',
        _bar(48, 190, 700, values[0], maximum, "event_id-only false pair count"),
        _bar(48, 248, 700, values[1], maximum, "(run,event_id) false pair count"),
        '<text x="48" y="318" font-size="18" font-weight="bold">'
        'Duplicate run-local EVENTNO control</text>',
        '<text x="48" y="350" font-size="14">event_id-only pivot outcome: '
        f'{html.escape(duplicate["current_event_id_only_outcome"])}</text>',
        _bar(48, 382, 700, values[2], maximum, "composite-key valid pair count"),
        '<text x="48" y="456" font-size="15">Interpretation: event identity is '
        'run-local unless proven otherwise.</text>',
        '<text x="48" y="486" font-size="15">A timing residual must never pair '
        'staves from different runs.</text>',
        '<text x="48" y="526" font-size="12">Synthetic software/provenance '
        'evidence; not detector timing data.</text>',
        '</svg>',
    ]
    svg = "\n".join(lines)
    output.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(json.loads(args.record.read_text(encoding="utf-8")), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
