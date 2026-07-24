#!/usr/bin/env python3
"""Render an accessible SVG for the legacy MV3 claim-governance audit."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def render(payload: dict[str, Any], output: Path) -> None:
    contract = payload["source_contract"]
    rounding = payload["rounding_identifiability"]
    mc = float(contract["b8_mc_fraction"])
    data = float(contract["b8_data_fraction"])
    width = 980
    height = 500
    left = 120
    scale = 700
    mc_w = mc * scale
    data_w = data * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Legacy MV3 stopping-profile claim audit</title>',
        '<desc id="desc">The fixed report shows rounded B8 fractions of 0.223 in MC and '
        '0.023 in data, while exact counts and a decomposed chi-square statistic are absent. '
        'The current implementation uses fail-closed sample and per-layer inputs.</desc>',
        '<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" '
        'stroke="#444" stroke-width="2"/></pattern></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="38" font-family="sans-serif" font-size="24" '
        'font-weight="bold">Legacy MV3 v3: fixed rounded outputs, not an accepted closure</text>',
        '<text x="30" y="66" font-family="sans-serif" font-size="14">'
        'Synthetic documentation/provenance visualization — not detector data.</text>',
        '<text x="30" y="108" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Reported B8 fractions</text>',
        '<text x="30" y="156" font-family="sans-serif" font-size="15">MC</text>',
        f'<rect x="{left}" y="136" width="{mc_w:.1f}" height="28" '
        'fill="url(#hatch)" stroke="black"/>',
        f'<text x="{left + mc_w + 10:.1f}" y="157" font-family="monospace" '
        f'font-size="15">{mc:.3f}</text>',
        '<text x="30" y="206" font-family="sans-serif" font-size="15">Data</text>',
        f'<rect x="{left}" y="186" width="{data_w:.1f}" height="28" '
        'fill="#d9d9d9" stroke="black"/>',
        f'<text x="{left + data_w + 10:.1f}" y="207" font-family="monospace" '
        f'font-size="15">{data:.3f}</text>',
        f'<text x="30" y="250" font-family="sans-serif" font-size="13">'
        f'MC exact numerator is unidentified: {rounding["mc_b8"]["possible_numerator_min"]}–'
        f'{rounding["mc_b8"]["possible_numerator_max"]} are all compatible with '
        '0.223 at 3 d.p.</text>',
        f'<text x="30" y="274" font-family="sans-serif" font-size="13">'
        f'Data exact numerator is unidentified: {rounding["data_b8"]["possible_numerator_min"]}–'
        f'{rounding["data_b8"]["possible_numerator_max"]} are all compatible with '
        '0.023 at 3 d.p.</text>',
        '<line x1="30" y1="304" x2="950" y2="304" stroke="black"/>',
        '<text x="30" y="338" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Goodness-of-fit label</text>',
        f'<text x="30" y="370" font-family="monospace" font-size="17">χ²/ndf = '
        f'{contract["chi2_ndf_label"]}</text>',
        '<text x="300" y="370" font-family="sans-serif" font-size="14">'
        'χ², ndf, p-value, bin errors and covariance are not reported.</text>',
        '<text x="30" y="410" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Accepted software policy</text>',
        '<text x="30" y="438" font-family="sans-serif" font-size="14">'
        'Require explicit sample_label + per-layer hit/energy masks; block instead of '
        'event-parity or stop_layer occupancy proxies.</text>',
        f'<text x="30" y="472" font-family="sans-serif" font-size="12">Status: '
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
