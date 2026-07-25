#!/usr/bin/env python3
"""Render compact SVG evidence for the adapter/analyzer metadata audit."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", required=True, type=Path)
    parser.add_argument("--output-svg", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    findings = payload.get("findings", [])
    codes = [finding.get("code", "UNKNOWN") for finding in findings]
    rows = "".join(
        f'<text x="55" y="{250 + index * 28}" font-size="17">'
        f'{html.escape(code)}</text>'
        for index, code in enumerate(codes[:8])
    )
    height = max(520, 300 + 28 * min(len(codes), 8))
    status = html.escape(str(payload.get("status", "UNKNOWN")))
    compatibility = html.escape(
        str(payload.get("observed", {}).get("adapter_analysis_compatibility", "missing"))
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200"
  height="{height}" viewBox="0 0 1200 {height}">
<rect width="1200" height="{height}" fill="white"/>
<text x="50" y="55" font-size="30" font-weight="bold">
  Single-stave adapter/analyzer metadata audit
</text>
<text x="50" y="92" font-size="18">Software/provenance evidence — not detector data</text>
<rect x="50" y="125" width="310" height="80" rx="10" fill="#eeeeee" stroke="#333333"/>
<text x="75" y="158" font-size="20">Adapter metadata</text>
<text x="75" y="188" font-size="17">{compatibility}</text>
<line x1="360" y1="165" x2="505" y2="165" stroke="#333333" stroke-width="3"/>
<polygon points="505,165 486,155 486,175" fill="#333333"/>
<rect x="505" y="125" width="310" height="80" rx="10" fill="#eeeeee" stroke="#333333"/>
<text x="530" y="158" font-size="20">Analyzer v2.0.0</text>
<text x="530" y="188" font-size="17">CURRENT_COMPONENT_SUM / total denominator</text>
<rect x="850" y="125" width="280" height="80" rx="10" fill="#eeeeee" stroke="#333333"/>
<text x="875" y="160" font-size="22" font-weight="bold">Audit status: {status}</text>
<text x="50" y="235" font-size="21" font-weight="bold">Fail-closed findings ({len(findings)})</text>
{rows}
<text x="50" y="{height - 52}" font-size="16">
  Policy: ADAPTER_METADATA_MUST_MATCH_CURRENT_ANALYZER_OPTICAL_CONTRACT
</text>
<text x="50" y="{height - 24}" font-size="16">
  Real ROOT execution and physics closure remain pending.
</text>
</svg>\n'''
    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.write_text(svg, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
