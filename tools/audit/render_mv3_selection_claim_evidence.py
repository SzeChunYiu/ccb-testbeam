#!/usr/bin/env python3
"""Render software/provenance evidence for the MV3 selection-claim audit."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict) -> str:
    calc = payload["independent_calculations"]
    findings = payload["findings"]
    lines = [
        ("Status", payload["status"]),
        ("Findings", str(payload["n_findings"])),
        ("Reported χ² improvement", f"{calc['reported_improvement_factor']:.3f}×"),
        (
            "Same-target improvement",
            f"{calc['same_target_unselected_vs_selected_improvement']:.3f}×",
        ),
        ("Matched χ²/ndf", f"{calc['chi2_per_ndf_selected_vs_sample_i']:.1f}"),
        ("B2 residual", f"{calc['sample_i_b2_residual_percentage_points']:.3f} pp"),
        ("Total-variation distance", f"{calc['sample_i_total_variation_distance']:.4f}"),
    ]
    height = 190 + 28 * (len(lines) + min(len(findings), 8))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="{height}" '
        f'viewBox="0 0 1100 {height}">',
        '<rect width="1100" height="100%" fill="white"/>',
        '<text x="40" y="48" font-family="sans-serif" font-size="26" font-weight="bold">'
        'MV3 selection-matched claim audit</text>',
        '<text x="40" y="78" font-family="sans-serif" font-size="15">'
        'Software and provenance evidence — not detector-performance data</text>',
    ]
    y = 118
    for label, value in lines:
        parts.append(
            f'<text x="55" y="{y}" font-family="monospace" font-size="16">'
            f'{html.escape(label):34s} {html.escape(value)}</text>'
        )
        y += 28
    parts.append(
        f'<text x="40" y="{y + 12}" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Fail-closed findings</text>'
    )
    y += 42
    for finding in findings[:8]:
        parts.append(
            f'<text x="55" y="{y}" font-family="monospace" font-size="14">'
            f'• {html.escape(finding["code"])}</text>'
        )
        y += 25
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("validation_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.validation_json.read_text(encoding="utf-8"))
    args.output_svg.write_text(render(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
