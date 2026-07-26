#!/usr/bin/env python3
"""Render compact SVG evidence for quantitative figure publication safety."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _flag(value: bool) -> str:
    return "YES" if value else "NO"


def render(source: Path, output: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    controls = payload["behavioral_controls"]
    former = controls["former_direct_target_failure"]
    corrected = controls["corrected_temporary_failure"]
    finding_text = " | ".join(item["code"] for item in payload["findings"])
    status_text = f"{payload['status']} ({payload['finding_count']} findings)"

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" '
        'viewBox="0 0 1200 700">',
        '  <rect width="1200" height="700" fill="white"/>',
        '  <text x="60" y="62" font-family="sans-serif" font-size="30" '
        'font-weight="bold">Quantitative figure publication integrity</text>',
        '  <text x="60" y="98" font-family="sans-serif" font-size="17">'
        f"Policy: {html.escape(payload['policy'])}</text>",
        '  <rect x="60" y="135" width="510" height="300" rx="14" '
        'fill="#f7e7e7" stroke="#7a2020" stroke-width="3"/>',
        '  <text x="90" y="180" font-family="sans-serif" font-size="25" '
        'font-weight="bold">Direct final-path render</text>',
        '  <text x="90" y="225" font-family="sans-serif" font-size="20">'
        'Injected render error</text>',
        '  <text x="90" y="268" font-family="sans-serif" font-size="20">'
        f"Prior target preserved: {_flag(former['previous_target_preserved'])}</text>",
        '  <text x="90" y="311" font-family="sans-serif" font-size="20">'
        f"Post-failure bytes: {former['post_failure_bytes']}</text>",
        '  <text x="90" y="365" font-family="sans-serif" font-size="17">'
        'Failure can truncate previously validated evidence.</text>',
        '  <rect x="630" y="135" width="510" height="300" rx="14" '
        'fill="#e6f4e8" stroke="#1b6b35" stroke-width="3"/>',
        '  <text x="660" y="180" font-family="sans-serif" font-size="25" '
        'font-weight="bold">Temporary render + atomic replace</text>',
        '  <text x="660" y="225" font-family="sans-serif" font-size="20">'
        'Injected render error</text>',
        '  <text x="660" y="268" font-family="sans-serif" font-size="20">'
        f"Prior target preserved: {_flag(corrected['previous_target_preserved'])}</text>",
        '  <text x="660" y="311" font-family="sans-serif" font-size="20">'
        f"Temporary files remaining: {corrected['temporary_files_remaining']}</text>",
        '  <text x="660" y="365" font-family="sans-serif" font-size="17">'
        'Only complete retained bytes replace the final target.</text>',
        '  <rect x="60" y="485" width="1080" height="135" rx="12" '
        'fill="#f2f2f2" stroke="#444"/>',
        '  <text x="85" y="525" font-family="sans-serif" font-size="20" '
        f'font-weight="bold">Current-source audit: {status_text}</text>',
        '  <text x="85" y="565" font-family="monospace" font-size="14">'
        f"{html.escape(finding_text)}</text>",
        '  <text x="85" y="602" font-family="sans-serif" font-size="15">'
        'This evidence concerns publication integrity, not scientific correctness '
        'of plotted values.</text>',
        "</svg>",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
