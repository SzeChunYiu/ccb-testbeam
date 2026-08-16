#!/usr/bin/env python3
"""Render deterministic SVG evidence for the analyzer optical-count correction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def render(payload: dict) -> str:
    old_ratio = payload["synthetic_control"]["legacy_scintillation_ratio"]
    new_ratio = payload["synthetic_control"]["correct_total_ratio"]
    old_width = min(420, 320 * old_ratio)
    new_width = min(420, 320 * new_ratio)
    status = payload["validation"]["status"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"
  viewBox="0 0 960 540">
  <rect width="960" height="540" fill="white"/>
  <text x="48" y="55" font-family="sans-serif" font-size="28"
  font-weight="bold">Single-stave optical bookkeeping correction</text>
  <text x="48" y="88" font-family="sans-serif" font-size="16">
  Synthetic software/provenance evidence — not detector data</text>
  <text x="48" y="135" font-family="sans-serif" font-size="18">
  Example: scintillation=10, WLS=5, Cerenkov=0, readout arrivals=11</text>
  <text x="48" y="185" font-family="sans-serif" font-size="17">
  Former denominator: scintillation only</text>
  <rect x="360" y="163" width="{old_width:.1f}" height="30" fill="#d95f02"/>
  <text x="790" y="185" font-family="monospace" font-size="18">11/10 = {old_ratio:.3f}</text>
  <text x="48" y="250" font-family="sans-serif" font-size="17">
  Correct denominator: all optical tracks</text>
  <rect x="360" y="228" width="{new_width:.1f}" height="30" fill="#1b9e77"/>
  <text x="790" y="250" font-family="monospace" font-size="18">11/15 = {new_ratio:.3f}</text>
  <line x1="680" y1="145" x2="680" y2="285" stroke="black" stroke-dasharray="6 5"/>
  <text x="665" y="305" font-family="sans-serif" font-size="14">ratio = 1</text>
  <text x="48" y="360" font-family="sans-serif" font-size="18">Validated controls</text>
  <text x="70" y="395" font-family="sans-serif" font-size="16">• exact component sum enforced</text>
  <text x="70" y="425" font-family="sans-serif" font-size="16">
  • partial, nonfinite, fractional, and negative count contracts rejected</text>
  <text x="70" y="455" font-family="sans-serif" font-size="16">
  • result and G4S-03 source data record denominator and contract</text>
  <rect x="690" y="360" width="210" height="70" rx="10" fill="#e8f5e9" stroke="#1b9e77"/>
  <text x="795" y="403" text-anchor="middle" font-family="sans-serif"
  font-size="24" font-weight="bold">{status}</text>
  <text x="48" y="510" font-family="sans-serif" font-size="13">
  Policy: ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL</text>
</svg>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.write_text(render(payload) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
