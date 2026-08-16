#!/usr/bin/env python3
"""Render a compact SVG for the Cluster D PSTAR-reference migration audit."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

TOOL_VERSION = "1.0.0"


def render(payload: dict[str, object]) -> str:
    comparisons = payload["former_vs_canonical_reference"]
    energies = sorted(comparisons, key=lambda item: float(item))
    rows = []
    for index, energy in enumerate(energies):
        item = comparisons[energy]
        y = 210 + index * 82
        bias = float(item["former_relative_bias_percent"])
        width = min(620.0, bias * 6.2)
        rows.append(
            f'<text x="65" y="{y}" font-size="18">{html.escape(energy)} MeV</text>'
        )
        rows.append(
            f'<rect x="175" y="{y - 20}" width="{width:.1f}" height="28" '
            'fill="#777"/>'
        )
        rows.append(
            f'<text x="{190 + width:.1f}" y="{y}" font-size="17">'
            f'{bias:.1f}% high</text>'
        )
        rows.append(
            f'<text x="880" y="{y}" font-size="16">'
            f'{item["former_embedded_total_MeV_cm2_g"]} → '
            f'{item["canonical_total_MeV_cm2_g"]} MeV cm²/g</text>'
        )
    status = html.escape(str(payload["status"]))
    findings = int(payload["finding_count"])
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" '
            'viewBox="0 0 1200 650">',
            '<rect width="1200" height="650" fill="white"/>',
            '<text x="55" y="55" font-size="28" font-weight="bold">'
            'Cluster D VIS-MC-002 canonical PSTAR migration</text>',
            f'<text x="55" y="90" font-size="17">status={status}; '
            f'findings={findings}; policy={html.escape(str(payload["policy"]))}</text>',
            '<text x="55" y="130" font-size="17">Former embedded table bias relative '
            'to the committed canonical PSTAR total column</text>',
            '<line x1="175" y1="160" x2="795" y2="160" stroke="black"/>',
            '<text x="175" y="185" font-size="14">0%</text>',
            '<text x="485" y="185" font-size="14">50%</text>',
            '<text x="755" y="185" font-size="14">100%</text>',
            *rows,
            '<text x="55" y="585" font-size="16" font-weight="bold">Interpretation: '
            'the historical plot reference increasingly overstated PSTAR above 10 MeV.</text>',
            '<text x="55" y="615" font-size="15">Software/reference provenance only; '
            'no campaign ROOT rerun or accepted stopping-power closure.</text>',
            '</svg>',
        ]
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(payload), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
