#!/usr/bin/env python3
"""Render accessible SVG evidence for exact MV3 claim governance."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def render(payload: dict[str, Any], output: Path) -> None:
    contract = payload["source_contract"]
    mc_count = int(contract["mc_counts"]["B8"])
    mc_n = int(contract["mc_n"])
    data_count = int(contract["data_counts"]["B8"])
    data_n = int(contract["data_n"])
    mc_fraction = float(contract["mc_fractions"]["B8"])
    data_fraction = float(contract["data_fractions"]["B8"])
    ratio = float(contract["stated_chi2_per_ndf"])
    width = 1040
    height = 560
    left = 170
    scale = 720
    mc_w = mc_fraction * scale
    data_w = data_fraction * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Exact legacy MV3 source-governance validation</title>',
        '<desc id="desc">The tracked summary contains exact B8 counts and an exactly '
        'reconstructable Pearson chi-square diagnostic. The diagnostic remains scientifically '
        'non-accepting because geometry, selection transfer, covariance and systematics are '
        'unresolved.</desc>',
        '<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" '
        'stroke="#444" stroke-width="2"/></pattern></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="38" font-family="sans-serif" font-size="24" '
        'font-weight="bold">Legacy MV3: exact tracked arithmetic, flawed physics closure</text>',
        '<text x="30" y="66" font-family="sans-serif" font-size="14">'
        'Software/documentation validation — not a new detector-data result.</text>',
        '<text x="30" y="110" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Exact B8 fractions from tracked counts</text>',
        '<text x="30" y="160" font-family="sans-serif" font-size="15">Thresholded MC</text>',
        f'<rect x="{left}" y="140" width="{mc_w:.1f}" height="30" '
        'fill="url(#hatch)" stroke="black"/>',
        f'<text x="{left + mc_w + 10:.1f}" y="162" font-family="monospace" '
        f'font-size="14">{mc_count}/{mc_n} = {mc_fraction:.17g}</text>',
        '<text x="30" y="215" font-family="sans-serif" font-size="15">Selected data</text>',
        f'<rect x="{left}" y="195" width="{data_w:.1f}" height="30" '
        'fill="#d9d9d9" stroke="black"/>',
        f'<text x="{left + data_w + 10:.1f}" y="217" font-family="monospace" '
        f'font-size="14">{data_count}/{data_n} = {data_fraction:.17g}</text>',
        '<line x1="30" y1="260" x2="1010" y2="260" stroke="black"/>',
        '<text x="30" y="300" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Reconstructed fixed-source diagnostic</text>',
        f'<text x="30" y="334" font-family="monospace" font-size="16">Pearson χ² = '
        f'{contract["stated_chi2"]}; ndf = {contract["stated_ndf"]}; χ²/ndf = '
        f'{ratio:.14f}</text>',
        '<text x="30" y="370" font-family="sans-serif" font-size="14">'
        'Expected counts use selected-data total × exact thresholded-MC fractions.</text>',
        '<text x="30" y="410" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Acceptance boundary</text>',
        '<text x="30" y="440" font-family="sans-serif" font-size="14">'
        'Exact arithmetic does not repair geometry/material modelling, trigger and selection '
        'transfer, gain response, covariance, or detector/model systematics.</text>',
        '<text x="30" y="470" font-family="sans-serif" font-size="14">'
        'Strict current MV3 remains fail-closed without sample_label and per-layer hit '
        'masks.</text>',
        f'<text x="30" y="525" font-family="sans-serif" font-size="12">Status: '
        f'{html.escape(str(payload["status"]))}; policy: '
        f'{html.escape(str(payload["policy"]))}</text>',
        '</svg>',
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
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
