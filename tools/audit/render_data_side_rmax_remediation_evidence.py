#!/usr/bin/env python3
"""Render the validated data-side Rmax remediation summary as SVG."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict) -> str:
    calc = payload["independent_calculations"]
    status = html.escape(payload["status"])
    issue_count = payload["n_issues"]
    mean = calc["mean_selected_pulses_per_event"]
    model = calc["model_sensitivity_only_mhz"]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="540"',
        ' viewBox="0 0 1100 540" role="img" aria-labelledby="title desc">',
        '<title id="title">Rmax occupancy remediation</title>',
        '<desc id="desc">Measured selected-pulse occupancy is separated from model',
        ' conventions and absolute Rmax remains blocked.</desc>',
        '<rect width="1100" height="540" fill="white"/>',
        '<text x="50" y="52" font-family="sans-serif" font-size="30"',
        ' font-weight="700">Rmax occupancy semantics remediated</text>',
        '<text x="50" y="84" font-family="sans-serif" font-size="17">',
        'OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE</text>',
        '<rect x="50" y="120" width="300" height="180" rx="12" fill="#e8f1fb"',
        ' stroke="#1f5a92" stroke-width="2"/>',
        '<text x="75" y="158" font-family="sans-serif" font-size="22"',
        ' font-weight="700">Measured</text>',
        '<text x="75" y="198" font-family="sans-serif" font-size="18">',
        '640,737 selected pulses</text>',
        '<text x="75" y="230" font-family="sans-serif" font-size="18">',
        '584,602 composite events</text>',
        '<text x="75" y="262" font-family="sans-serif" font-size="18">',
        f'mean multiplicity = {mean:.6f}</text>',
        '<rect x="400" y="120" width="300" height="180" rx="12" fill="#fff4d6"',
        ' stroke="#a87000" stroke-width="2"/>',
        '<text x="425" y="158" font-family="sans-serif" font-size="22"',
        ' font-weight="700">Model-only inputs</text>',
        '<text x="425" y="198" font-family="sans-serif" font-size="18">',
        'legacy mu = 0.38</text>',
        '<text x="425" y="230" font-family="sans-serif" font-size="18">',
        'tau = 124.7901839 ns</text>',
        '<text x="425" y="262" font-family="sans-serif" font-size="18">',
        'rate exposure absent</text>',
        '<rect x="750" y="120" width="300" height="180" rx="12" fill="#e8f6ec"',
        ' stroke="#267a3e" stroke-width="2"/>',
        '<text x="775" y="158" font-family="sans-serif" font-size="22"',
        ' font-weight="700">Remediated contract</text>',
        '<text x="775" y="198" font-family="sans-serif" font-size="18">',
        'CL-010 = BLOCKED</text>',
        '<text x="775" y="230" font-family="sans-serif" font-size="18">',
        'accepted Rmax = none</text>',
        '<text x="775" y="262" font-family="sans-serif" font-size="18">',
        f'validation: {status} ({issue_count} findings)</text>',
        '<rect x="50" y="340" width="1000" height="120" rx="12" fill="#f5f5f5"',
        ' stroke="#777"/>',
        '<text x="75" y="380" font-family="monospace" font-size="18">',
        f'0.38 / 124.79018394263471 ns = {model:.15f} MHz</text>',
        '<text x="75" y="415" font-family="sans-serif" font-size="17">',
        'Explicitly labelled model sensitivity only; not a data-derived detector rate.</text>',
        '<text x="50" y="510" font-family="sans-serif" font-size="15">',
        'Software/documentation validation; no ROOT rerun or detector-performance claim.</text>',
        '</svg>',
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.validation_json.read_text(encoding="utf-8"))
    args.output_svg.write_text(render(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
