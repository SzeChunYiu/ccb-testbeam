#!/usr/bin/env python3
"""Render SVG evidence for the real-data CFD residual-visualization audit."""
from __future__ import annotations

import argparse
import html
import json
import os
import tempfile
from pathlib import Path

WIDTH = 1200
HEIGHT = 690
LEFT = 230
RIGHT = 70
X_MIN = -80.0
X_MAX = 80.0
PLOT_LOW = -10.0
PLOT_HIGH = 10.0


def _x(value: float) -> float:
    return LEFT + (value - X_MIN) / (X_MAX - X_MIN) * (WIDTH - LEFT - RIGHT)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        finally:
            raise


def render(payload: dict) -> str:
    rows = []
    coverage = payload["reported_distribution_coverage_bounds"]
    for tag in ("sample_II", "task_runs"):
        for method in ("t_cfd10", "t_cfd20"):
            rows.append((tag, method, coverage[tag][method]))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:DejaVu Sans,Arial,sans-serif;fill:#111}'
        '.title{font-size:27px;font-weight:700}.sub{font-size:16px}'
        '.label{font-size:17px;font-weight:600}.small{font-size:14px}'
        '.axis{stroke:#333;stroke-width:1.4}.tick{stroke:#777;stroke-width:1}'
        '.bound{stroke:#7b2cbf;stroke-width:7;stroke-linecap:round}'
        '.median{stroke:#c1121f;stroke-width:4}'
        '.window{fill:#d8f3dc;stroke:#2d6a4f;stroke-width:1.5}'
        '.warning{fill:#9b2226;font-size:15px;font-weight:700}</style>',
        '<text class="title" x="45" y="45">'
        'PR #939 residual plots omit the reported central distributions</text>',
        '<text class="sub" x="45" y="75">Fixed visible window: −10 to +10 ns. '
        'Purple bars are conservative q16–q84 bounds derived only from median and σ68.</text>',
        f'<rect class="window" x="{_x(PLOT_LOW):.2f}" y="105" '
        f'width="{_x(PLOT_HIGH)-_x(PLOT_LOW):.2f}" height="455"/>',
        '<text class="small" x="520" y="125">visible histogram window</text>',
    ]

    axis_y = 585
    parts.append(
        f'<line class="axis" x1="{LEFT}" y1="{axis_y}" '
        f'x2="{WIDTH-RIGHT}" y2="{axis_y}"/>'
    )
    for tick in range(-80, 81, 20):
        xpos = _x(float(tick))
        parts.append(
            f'<line class="tick" x1="{xpos:.2f}" y1="{axis_y}" '
            f'x2="{xpos:.2f}" y2="{axis_y+8}"/>'
        )
        parts.append(
            f'<text class="small" x="{xpos-13:.2f}" y="{axis_y+28}">{tick}</text>'
        )
    parts.append(
        f'<text class="label" x="{WIDTH/2-70:.2f}" y="650">'
        'raw pair residual (ns)</text>'
    )

    for index, (tag, method, item) in enumerate(rows):
        y = 170 + index * 100
        low = item["q16_lower_bound_ns"]
        high = item["q84_upper_bound_ns"]
        median = item["median_ns"]
        label = f"{tag} / {method} (n={item['n']})"
        parts.append(
            f'<text class="label" x="45" y="{y+5}">{html.escape(label)}</text>'
        )
        parts.append(
            f'<line class="bound" x1="{_x(low):.2f}" y1="{y}" '
            f'x2="{_x(high):.2f}" y2="{y}"/>'
        )
        parts.append(
            f'<line class="median" x1="{_x(median):.2f}" y1="{y-18}" '
            f'x2="{_x(median):.2f}" y2="{y+18}"/>'
        )
        parts.append(
            f'<text class="small" x="{_x(median)+8:.2f}" y="{y-12}">'
            f'median {median:.3f} ns</text>'
        )
        parts.append(
            f'<text class="warning" x="{LEFT}" y="{y+35}">'
            '≥84% guaranteed outside the displayed window</text>'
        )

    parts.extend(
        [
            '<text class="small" x="45" y="675">Software/visualization evidence only; '
            'no raw ROOT timing result is reprocessed or validated.</text>',
            '</svg>',
        ]
    )
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.validation_json.read_text(encoding="utf-8"))
    _atomic_write(args.output_svg, render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
