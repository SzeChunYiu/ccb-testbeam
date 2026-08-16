#!/usr/bin/env python3
"""Render figure-registry schema audit JSON as a compact SVG."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict, output: Path) -> None:
    summary = payload["summary"]
    issues = payload["issues"]
    rows = [
        ("Allowed statuses", len(summary["allowed_statuses"])),
        ("Used statuses", len(summary["used_statuses"])),
        (
            "Unsupported statuses",
            len(set(summary["used_statuses"]) - set(summary["allowed_statuses"])),
        ),
        (
            "Unsupported kinds",
            len(set(summary["used_kinds"]) - set(summary["allowed_kinds"])),
        ),
        (
            "Illustrative missing result",
            len(summary["missing_result_illustrative_entries"]),
        ),
    ]
    width, height = 940, 430
    max_value = max(value for _, value in rows) or 1
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        '<rect width="100%" height="100%" fill="white"/>',
        (
            '<text x="40" y="48" font-family="sans-serif" font-size="25" '
            'font-weight="bold">Figure registry schema alignment</text>'
        ),
        (
            '<text x="40" y="78" font-family="sans-serif" font-size="15">'
            f'status: {html.escape(payload["status"])} · findings: {len(issues)}</text>'
        ),
    ]
    y = 125
    for label, value in rows:
        bar = 540 * value / max_value
        parts.append(
            f'<text x="40" y="{y + 20}" font-family="sans-serif" '
            f'font-size="15">{html.escape(label)}</text>'
        )
        parts.append(
            f'<rect x="300" y="{y}" width="{bar:.1f}" height="25" '
            'fill="#777"/>'
        )
        parts.append(
            f'<text x="{310 + bar:.1f}" y="{y + 19}" font-family="sans-serif" '
            f'font-size="14">{value}</text>'
        )
        y += 48
    codes = ", ".join(sorted({item["code"] for item in issues}))
    parts.append(
        '<text x="40" y="385" font-family="sans-serif" font-size="13">'
        f'Finding families: {html.escape(codes)}</text>'
    )
    parts.append(
        '<text x="40" y="411" font-family="sans-serif" font-size="12">'
        'Software/schema evidence only; no scientific figure claim is validated by this '
        'graphic.</text>'
    )
    parts.append("</svg>\n")
    output.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    render(json.loads(args.input_json.read_text(encoding="utf-8")), args.output_svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
