#!/usr/bin/env python3
"""Render DeltaE signal-value validation evidence as deterministic SVG."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict) -> str:
    controls = payload["synthetic_controls"]
    status = payload["status"]
    findings = payload["finding_count"]
    malformed_before = 1 if controls["former_malformed_cell_became_zero"] else 0
    infinity_before = 1 if controls["former_infinity_remained_infinite"] else 0
    malformed_after = 0 if not controls["corrected_malformed_finite_mask"][0] else 1
    infinity_after = 0 if not controls["corrected_infinity_finite_mask"][0] else 1
    source_hash = payload["source"]["sha256"]
    policy = html.escape(payload["policy"])
    status_text = html.escape(f"{status} — {findings} findings")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720"
viewBox="0 0 1200 720" role="img" aria-labelledby="title desc">
  <title id="title">DeltaE present-signal input integrity</title>
  <desc id="desc">Synthetic software validation showing former malformed-to-zero and
  infinity-retention behavior, and the corrected fail-closed contract.</desc>
  <rect width="1200" height="720" fill="#ffffff"/>
  <text x="60" y="70" font-family="sans-serif" font-size="34" font-weight="700">
    DeltaE present-signal integrity
  </text>
  <text x="60" y="108" font-family="monospace" font-size="18">{policy}</text>
  <rect x="60" y="140" width="1080" height="58" rx="8" fill="#eef6ee" stroke="#2f6f3e"/>
  <text x="84" y="177" font-family="sans-serif" font-size="24" font-weight="700">
    {status_text}
  </text>

  <text x="90" y="255" font-family="sans-serif" font-size="24" font-weight="700">
    Former algorithm
  </text>
  <text x="620" y="255" font-family="sans-serif" font-size="24" font-weight="700">
    Corrected contract
  </text>

  <text x="90" y="310" font-family="sans-serif" font-size="20">
    Malformed present cell accepted
  </text>
  <rect x="90" y="330" width="{380 * malformed_before}" height="42" fill="#b94a48"/>
  <text x="485" y="358" font-family="monospace" font-size="19">{malformed_before}</text>

  <text x="90" y="430" font-family="sans-serif" font-size="20">Infinite present cell retained</text>
  <rect x="90" y="450" width="{380 * infinity_before}" height="42" fill="#b94a48"/>
  <text x="485" y="478" font-family="monospace" font-size="19">{infinity_before}</text>

  <text x="620" y="310" font-family="sans-serif" font-size="20">
    Malformed present cell accepted
  </text>
  <rect x="620" y="330" width="{380 * malformed_after}" height="42" fill="#2f6f3e"/>
  <text x="1015" y="358" font-family="monospace" font-size="19">{malformed_after}</text>

  <text x="620" y="430" font-family="sans-serif" font-size="20">
    Infinite present cell retained
  </text>
  <rect x="620" y="450" width="{380 * infinity_after}" height="42" fill="#2f6f3e"/>
  <text x="1015" y="478" font-family="monospace" font-size="19">{infinity_after}</text>

  <line x1="560" y1="275" x2="560" y2="525" stroke="#777" stroke-width="2"/>
  <text x="60" y="570" font-family="sans-serif" font-size="20">
    Zero fill remains authorized only when an entire supported downstream column is absent.
  </text>
  <text x="60" y="610" font-family="sans-serif" font-size="17">
    Synthetic software/provenance evidence; not detector data and not a physics acceptance plot.
  </text>
  <text x="60" y="650" font-family="monospace" font-size="15">
    source sha256: {source_hash}
  </text>
</svg>
'''


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
