#!/usr/bin/env python3
"""Render the single-stave event-contract validation record as an SVG."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def render(payload: dict) -> str:
    tests = payload["validation"]["focused_tests"]
    controls = payload["validation"]["controls"]
    passed = int(tests["passed"])
    control_passed = sum(item["status"] == "PASS" for item in controls)
    total_controls = len(controls)
    bar_width = 640
    test_width = (
        bar_width
        if passed == tests["total"]
        else bar_width * passed / tests["total"]
    )
    control_width = bar_width * control_passed / max(total_controls, 1)
    policy = html.escape(payload["policy"])
    run_action_blob = html.escape(
        payload["inputs"]["run_action_git_blob_sha"][:16]
    )
    adapter_sha = html.escape(payload["outputs"]["adapter_sha256"][:16])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600"
  viewBox="0 0 960 600">
  <rect width="960" height="600" fill="white"/>
  <text x="48" y="58" font-family="sans-serif" font-size="28"
    font-weight="bold">Single-stave event contract</text>
  <text x="48" y="88" font-family="sans-serif" font-size="16">
    Software/provenance validation — not detector data</text>
  <text x="48" y="126" font-family="monospace" font-size="13">
    Policy: {policy}</text>
  <text x="48" y="166" font-family="sans-serif" font-size="18"
    font-weight="bold">Current producer → normalized analysis fields</text>
  <text x="72" y="199" font-family="monospace" font-size="16">
    event → event_id</text>
  <text x="72" y="227" font-family="monospace" font-size="16">
    ke_MeV → kinetic_energy_MeV</text>
  <text x="72" y="255" font-family="monospace" font-size="16">
    arrival_readout → n_end_selected</text>
  <text x="72" y="283" font-family="monospace" font-size="16">
    detected_readout → n_detected_pe</text>
  <text x="72" y="311" font-family="monospace" font-size="16">
    track_len_scint_mm / 10 → track_length_scint_cm</text>
  <text x="48" y="356" font-family="sans-serif" font-size="18"
    font-weight="bold">Fail-closed validation</text>
  <rect x="72" y="382" width="{bar_width}" height="26" fill="#e5e7eb"/>
  <rect x="72" y="382" width="{test_width:.1f}" height="26"
    fill="#15803d"/>
  <text x="730" y="402" font-family="sans-serif" font-size="15">
    {passed}/{tests['total']} tests passed</text>
  <rect x="72" y="426" width="{bar_width}" height="26" fill="#e5e7eb"/>
  <rect x="72" y="426" width="{control_width:.1f}" height="26"
    fill="#0369a1"/>
  <text x="730" y="446" font-family="sans-serif" font-size="15">
    {control_passed}/{total_controls} controls passed</text>
  <text x="48" y="496" font-family="sans-serif" font-size="15">
    Arrival bound: scintillation + WLS + Cerenkov generated tracks</text>
  <text x="48" y="524" font-family="monospace" font-size="13">
    RunAction Git blob: {run_action_blob}…</text>
  <text x="48" y="550" font-family="monospace" font-size="13">
    Adapter SHA-256: {adapter_sha}…</text>
  <text x="48" y="580" font-family="sans-serif" font-size="14">
    Result: VALIDATED for contract conversion; no physics-performance claim.</text>
</svg>
'''


def main() -> int:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.write_text(render(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
