#!/usr/bin/env python3
"""Render a dependency-free SVG summary from Cluster E audit JSON."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict, output: Path) -> None:
    findings = payload.get("findings", [])
    canonical = payload.get("canonical_values", {})
    comparison = payload.get("mv3_source_comparison", {})
    rows = [
        ("CL-013 gain", "92 ADC/MeV", "Dashboard/summary/CSV use 110"),
        (
            "CL-021 chi2/ndf",
            str(canonical.get("CL-021", {}).get("chi2_per_ndf", "?")),
            str(comparison.get("clusterD_rerun_chi2_per_ndf", "?"))
            + " is a distinct rerun",
        ),
        ("CL-022 morphology", "283 / 87555", "Dashboard/summary/CSV use 25 / 38 toy subset"),
        (
            "Provenance",
            "full 40-hex commit + 64-hex input SHA-256",
            "current output truncates/omits bindings",
        ),
    ]
    width, height = 1200, 560
    y0, row_h = 170, 72
    status = payload.get("status", "UNKNOWN")
    fill = "#b2182b" if status == "FLAWED" else "#1b7837"
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            '<style>text{font-family:DejaVu Sans,Arial,sans-serif}'
            '.h{font-size:28px;font-weight:700}.s{font-size:17px}'
            '.b{font-size:16px;font-weight:700}.m{font-size:15px}</style>'
        ),
        '<text x="50" y="52" class="h">Cluster E canonical claim-binding audit</text>',
        f'<rect x="50" y="75" width="160" height="40" rx="8" fill="{fill}"/>',
        (
            f'<text x="130" y="102" text-anchor="middle" fill="white" '
            f'class="b">{html.escape(status)}</text>'
        ),
        (
            f'<text x="235" y="102" class="s">{len(findings)} fail-closed '
            'finding(s); software/documentation evidence only</text>'
        ),
        '<text x="50" y="145" class="b">Claim / provenance contract</text>',
        '<text x="390" y="145" class="b">Canonical binding</text>',
        '<text x="760" y="145" class="b">Observed conflict</text>',
    ]
    for index, (label, expected, observed) in enumerate(rows):
        y = y0 + index * row_h
        bg = "#f5f5f5" if index % 2 == 0 else "#ffffff"
        parts.append(
            f'<rect x="45" y="{y-26}" width="1110" height="58" '
            f'fill="{bg}" stroke="#dddddd"/>'
        )
        parts.append(f'<text x="60" y="{y+7}" class="m">{html.escape(label)}</text>')
        parts.append(f'<text x="390" y="{y+7}" class="m">{html.escape(expected)}</text>')
        parts.append(f'<text x="760" y="{y+7}" class="m">{html.escape(observed)}</text>')
    parts.extend(
        [
            (
                '<text x="50" y="500" class="s">Interpretation: Cluster D reruns/toy '
                'diagnostics may be shown, but must not silently replace canonical ledger rows.</text>'
            ),
            (
                '<text x="50" y="530" class="m">No detector-performance, calibration, '
                'data/MC-transfer, or accepted stopping-profile result is established by this '
                'audit.</text>'
            ),
            "</svg>",
        ]
    )
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    render(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
