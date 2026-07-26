#!/usr/bin/env python3
"""Render SVG evidence for the PR #939 single-stave inference audit."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict, output: Path) -> None:
    controls = payload["toy_controls"]
    width, height = 920, 520
    left, top, chart_w, chart_h = 260, 90, 560, 300
    max_abs = max(abs(float(row["relative_error"])) for row in controls)
    scale = chart_w / (2.0 * max_abs * 1.15)
    zero_x = left + chart_w / 2.0
    rows = []
    for index, row in enumerate(controls):
        y = top + 35 + index * 52
        err = float(row["relative_error"])
        x = zero_x if err >= 0 else zero_x + err * scale
        bar_w = abs(err) * scale
        label = html.escape(str(row["case"]))
        rows.append(f'<text x="20" y="{y+6}" font-size="15">{label}</text>')
        rows.append(
            f'<rect x="{x:.2f}" y="{y-14}" width="{bar_w:.2f}" height="24" '
            'fill="#5b8ff9" stroke="#1f1f1f" />'
        )
        rows.append(
            f'<text x="{zero_x + err*scale + (8 if err >= 0 else -8):.2f}" '
            f'y="{y+5}" text-anchor="{("start" if err >= 0 else "end")}" '
            f'font-size="14">{err*100:+.1f}%</text>'
        )
    headline = payload["headline_pair"]
    ratio = headline["full_rms_ns"] / headline["sigma68_ns"]
    svg_parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        '<rect width="100%" height="100%" fill="white"/>',
        (
            '<text x="20" y="34" font-size="24" font-weight="bold">'
            'Pair sigma68 / sqrt(2) is not a general single-stave estimator</text>'
        ),
        (
            '<text x="20" y="62" font-size="15">Relative error versus stave A '
            'sigma68 in deterministic fixed-seed controls</text>'
        ),
        (
            f'<line x1="{zero_x}" y1="{top}" x2="{zero_x}" '
            f'y2="{top+chart_h}" stroke="black" stroke-width="2"/>'
        ),
        (
            f'<text x="{zero_x}" y="{top+chart_h+28}" text-anchor="middle" '
            'font-size="14">0% error</text>'
        ),
        "".join(rows),
        '<text x="20" y="438" font-size="16" font-weight="bold">Observed PR pair metric</text>',
        (
            '<text x="20" y="466" font-size="15">'
            f'sigma68 = {headline["sigma68_ns"]:.6f} ns; naive /sqrt(2) = '
            f'{payload["naive_single_stave_ns"]:.6f} ns</text>'
        ),
        (
            '<text x="20" y="492" font-size="15">'
            f'tail &gt;5 ns = {headline["tail_frac_gt5ns"]:.3f}; '
            f'RMS/sigma68 = {ratio:.2f}</text>'
        ),
        (
            '<text x="20" y="514" font-size="13">Interpretation: pair-only timing '
            'evidence; individual-stave inference remains unauthorized without '
            'deconvolution and covariance assumptions.</text>'
        ),
        '</svg>',
    ]
    svg = "\n".join(svg_parts)
    output.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    render(payload, Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
