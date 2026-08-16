#!/usr/bin/env python3
"""Render synthetic visual evidence for the WIKI tau-eff binding gate."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict[str, object]) -> str:
    result = payload.get("current_exact_excerpt_result", payload)
    status = html.escape(str(result["status"]))
    count = int(result["n_issues"])
    codes = sorted({str(issue["code"]) for issue in result.get("issues", [])})
    issue_text = html.escape(", ".join(codes) if codes else "none")
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675"',
        ' viewBox="0 0 1200 675">',
        '  <rect width="1200" height="675" fill="white"/>',
        '  <text x="60" y="80" font-family="sans-serif" font-size="34"',
        ' font-weight="bold">WIKI S10b live10 public-binding audit</text>',
        '  <text x="60" y="125" font-family="sans-serif" font-size="20">',
        'Synthetic software/provenance evidence — not detector data</text>',
        '  <rect x="60" y="170" width="1080" height="105" fill="#f3f4f6"',
        ' stroke="#111827"/>',
        f'  <text x="90" y="215" font-family="monospace" font-size="24">Status: {status}</text>',
        f'  <text x="90" y="252" font-family="monospace" font-size="24">Findings: {count}</text>',
        '  <text x="60" y="335" font-family="sans-serif" font-size="24"',
        ' font-weight="bold">Required location-bound contract</text>',
        '  <text x="85" y="380" font-family="sans-serif" font-size="20">',
        '1. Canonical table: exact value and exact run-bootstrap 95% interval</text>',
        '  <text x="85" y="420" font-family="sans-serif" font-size="20">',
        '2. data_measurement / DONE_DATA_ONLY; no invented stat/syst components</text>',
        '  <text x="85" y="460" font-family="sans-serif" font-size="20">',
        '3. Pile-up section: 14 runs, 252266 pulses, run-average caveat</text>',
        '  <text x="85" y="500" font-family="sans-serif" font-size="20">',
        '4. MV5 reuses the value and does not independently validate it</text>',
        '  <text x="60" y="560" font-family="sans-serif" font-size="22"',
        ' font-weight="bold">Finding codes</text>',
        f'  <text x="85" y="600" font-family="monospace" font-size="17">{issue_text}</text>',
        '  <text x="60" y="645" font-family="sans-serif" font-size="16">',
        'Policy: WIKI_TAU_EFF_MUST_BIND_EXACT_S10B_ESTIMAND_AND_INTERVAL</text>',
        '</svg>',
        '',
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
