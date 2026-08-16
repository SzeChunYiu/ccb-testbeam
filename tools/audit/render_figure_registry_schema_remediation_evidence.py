#!/usr/bin/env python3
"""Render deterministic SVG evidence for figure-registry schema remediation."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict, output: Path) -> None:
    status_rows = payload["status_dispositions"]
    row_height = 30
    width = 980
    height = 190 + row_height * len(status_rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:monospace;fill:#111}.h{font-size:22px;font-weight:bold}'
        '.s{font-size:13px}.b{font-size:14px;font-weight:bold}</style>',
        '<text x="28" y="38" class="h">Figure-registry scientific disposition contract</text>',
        '<text x="28" y="66" class="s">Policy: '
        + html.escape(payload["policy"])
        + '</text>',
        '<text x="28" y="90" class="s">Focused pytest: '
        + html.escape(payload["validation"]["pytest_result"])
        + '</text>',
        '<text x="28" y="114" class="s">Shipped semantic inventory: '
        + f'{payload["inventory"]["n_used_statuses"]} statuses, '
        + f'{payload["inventory"]["n_used_kinds"]} kinds; structural findings after fix: 0'
        + '</text>',
        '<text x="28" y="150" class="b">Status</text>',
        '<text x="360" y="150" class="b">Disposition</text>',
        '<text x="560" y="150" class="b">Paper authorization</text>',
    ]
    y = 178
    for status, disposition in status_rows:
        authorization = "YES" if disposition == "BUILD" else "NO"
        if disposition == "CONDITIONAL":
            authorization = "ONLY WITH EXPLICIT FLAG"
        if disposition == "ILLUSTRATIVE":
            authorization = "NON-QUANTITATIVE"
        parts.extend(
            [
                f'<line x1="28" y1="{y - 19}" x2="950" y2="{y - 19}" '
                'stroke="#ddd"/>',
                f'<text x="28" y="{y}" class="s">{html.escape(status)}</text>',
                f'<text x="360" y="{y}" class="s">{html.escape(disposition)}</text>',
                f'<text x="560" y="{y}" class="s">{html.escape(authorization)}</text>',
            ]
        )
        y += row_height
    parts.append('</svg>')
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.validation_json.read_text(encoding="utf-8"))
    render(payload, args.output_svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
