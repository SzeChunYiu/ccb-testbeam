#!/usr/bin/env python3
"""Render the DeltaE CSV provenance-reader validation record as SVG."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict[str, object]) -> str:
    observed = payload["observed_ci_failure"]
    validation = payload["validation"]
    files = payload["files"]
    lines = [
        "DeltaE-E CSV provenance identifier contract",
        f"Policy: {payload['policy']}",
        "",
        "Observed CI failure (Python 3.11 / pandas 3.0.5)",
        f"  all-digit 40-character commit inferred as: {observed['inferred_type']}",
        f"  expected semantic type: {observed['required_type']}",
        "",
        "Remediation",
        f"  explicit text columns: {validation['text_column_count']}",
        f"  authoritative typed metadata: {validation['authoritative_metadata']}",
        f"  all-digit identifier preserved: {validation['all_digit_preserved']}",
        f"  leading-zero identifier preserved: {validation['leading_zero_preserved']}",
        "",
        "Focused validation",
        f"  pytest: {validation['pytest_result']}",
        f"  Python: {validation['python']}; pandas: {validation['pandas']}",
        "",
        "Version-controlled inputs",
        f"  contract blob: {files['contract']['git_blob']}",
        f"  contract SHA-256: {files['contract']['sha256']}",
        f"  test blob: {files['contract_test']['git_blob']}",
        f"  test SHA-256: {files['contract_test']['sha256']}",
        "",
        "Boundary: software/provenance validation only; no A-002 physics result.",
    ]
    width = 1200
    line_height = 29
    height = 80 + line_height * len(lines)
    escaped = [html.escape(str(line)) for line in lines]
    text = "\n".join(
        f'<text x="55" y="{55 + i * line_height}" class="body">{line}</text>'
        for i, line in enumerate(escaped)
    )
    opening = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">'
    )
    return f'''{opening}
  <title>DeltaE CSV provenance identifier validation</title>
  <desc>Software and provenance validation evidence; not detector data.</desc>
  <style>
    .body {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 18px; fill: #111; }}
    .frame {{ fill: #fff; stroke: #222; stroke-width: 2; }}
  </style>
  <rect x="20" y="20" width="{width - 40}" height="{height - 40}" rx="12" class="frame"/>
  {text}
</svg>\n'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    args.output_svg.write_text(render(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
