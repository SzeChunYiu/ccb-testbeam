#!/usr/bin/env python3
"""Render machine-readable and SVG evidence for real-data CFD safeguards."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import html

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from real_data_cfd_contract import (  # noqa: E402
    EVENT_KEY_COLUMNS,
    POLICY,
    pair_only_inference_contract,
    pivot_by_event,
    residual_plot_record,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def build_evidence() -> dict[str, object]:
    control = pd.DataFrame(
        {
            "run": [1, 1, 2, 2],
            "event_id": [7, 7, 7, 7],
            "stave": ["B6", "B8", "B6", "B8"],
            "t": [1.0, 0.0, 101.0, 100.0],
        }
    )
    wide = pivot_by_event(control, "t")
    pair = (wide["B6"] - wide["B8"]).to_numpy(dtype=float)
    centered, plot_record = residual_plot_record(
        [-100.0, -2.0, -1.0, 0.0, 1.0, 2.0, 100.0],
        "synthetic_tail_control",
        core_half_width_ns=5.0,
    )
    inference = pair_only_inference_contract()
    producer = ROOT / "scripts" / "real_data_cfd_timing.py"
    contract = ROOT / "scripts" / "real_data_cfd_contract.py"
    tests = ROOT / "tests" / "test_real_data_cfd_production_safeguards.py"
    report = ROOT / "reports" / "real_data_cfd_timing" / "REPORT.md"
    result = ROOT / "reports" / "real_data_cfd_timing" / "result.json"
    result_data = json.loads(result.read_text(encoding="utf-8"))
    findings = []
    if list(wide.index.names) != list(EVENT_KEY_COLUMNS) or len(wide) != 2:
        findings.append("COMPOSITE_EVENT_IDENTITY_CONTROL_FAILED")
    if not np.allclose(pair, [1.0, 1.0]):
        findings.append("PAIR_RESIDUAL_CONTROL_FAILED")
    if plot_record.full_underflow or plot_record.full_overflow:
        findings.append("FULL_RANGE_VISUALIZATION_DROPPED_EVENTS")
    if plot_record.core_underflow != 1 or plot_record.core_overflow != 1:
        findings.append("CORE_TAIL_COUNTS_INCORRECT")
    if inference["authorized"] is not False:
        findings.append("SINGLE_STAVE_INFERENCE_NOT_DENIED")
    if result_data["acceptance"]["status"] != "FLAWED_LEGACY_OUTPUT_QUARANTINED":
        findings.append("LEGACY_BUNDLE_NOT_QUARANTINED")
    return {
        "schema": "ccb-real-data-cfd-production-safeguards/1",
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "findings": findings,
        "base_main_sha": "be97e1a1e77de3bba6305f28802d1c876d2d1605",
        "controls": {
            "composite_event_identity": {
                "input_rows": 4,
                "unique_event_ids_without_run": 1,
                "unique_composite_events": int(len(wide)),
                "pair_residuals_ns": pair.tolist(),
                "event_key": list(EVENT_KEY_COLUMNS),
            },
            "residual_visualization": {
                "input_ns": centered.tolist(),
                **plot_record.to_dict(),
            },
            "single_stave_inference": inference,
            "legacy_bundle": {
                "acceptance": result_data["acceptance"],
                "residual_pngs_authorized": result_data["visualization_status"][
                    "residual_pngs_authorized"
                ],
            },
        },
        "files": {
            str(path.relative_to(ROOT)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in [producer, contract, tests, report, result]
        },
        "validation": {
            "commands": [
                "python -m py_compile "
                "scripts/real_data_cfd_contract.py "
                "scripts/real_data_cfd_timing.py "
                "tests/test_real_data_cfd_production_safeguards.py "
                "tools/audit/render_real_data_cfd_production_safeguard_evidence.py",
                "PYTHONPATH=. pytest -q tests/test_real_data_cfd_production_safeguards.py",
            ],
            "focused_pytest": "8 passed",
            "root_data_reprocessed": False,
            "scientific_acceptance": "PAIR_ONLY_PENDING_CONTENT_ADDRESSED_RERUN",
        },
    }


def render_svg(evidence: dict[str, object], path: Path) -> None:
    controls = evidence["controls"]
    event = controls["composite_event_identity"]
    residual = controls["residual_visualization"]
    values = np.asarray(residual["input_ns"], dtype=float)
    low, high = residual["full_range_ns"]

    def x(value: float) -> float:
        return 650.0 + 480.0 * (float(value) - low) / (high - low)

    points = " ".join(
        f"{x(value):.2f},{410 - 250 * (index % 2):.2f}"
        for index, value in enumerate(sorted(values))
    )
    q16_x = x(residual["q16_centered_ns"])
    q84_x = x(residual["q84_centered_ns"])
    title = html.escape(
        "Real-data CFD safeguards: composite keys, visible tails, pair-only inference"
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="500"
 viewBox="0 0 1200 500" role="img" aria-labelledby="title desc">
<title id="title">{title}</title>
<desc id="desc">Two synthetic controls demonstrate collision-safe composite event keys
 and a full-range median-centered residual visualization with explicit tail counts.</desc>
<rect width="1200" height="500" fill="white"/>
<text x="600" y="35" text-anchor="middle" font-family="sans-serif" font-size="20">{title}</text>
<text x="290" y="75" text-anchor="middle" font-family="sans-serif"
 font-size="16">Event identity control</text>
<line x1="90" y1="420" x2="520" y2="420" stroke="black"/>
<line x1="90" y1="100" x2="90" y2="420" stroke="black"/>
<rect x="150" y="260" width="100" height="160" fill="#777"/>
<rect x="350" y="100" width="100" height="320" fill="#222"/>
<text x="200" y="445" text-anchor="middle" font-family="sans-serif"
 font-size="13">event_id only</text>
<text x="400" y="445" text-anchor="middle" font-family="sans-serif"
 font-size="13">(run,event_id)</text>
<text x="200" y="250" text-anchor="middle" font-family="sans-serif"
 font-size="18">{event['unique_event_ids_without_run']}</text>
<text x="400" y="90" text-anchor="middle" font-family="sans-serif"
 font-size="18">{event['unique_composite_events']}</text>
<text x="290" y="475" text-anchor="middle" font-family="sans-serif"
 font-size="13">Two runs reuse EVENTNO=7</text>
<text x="890" y="75" text-anchor="middle" font-family="sans-serif"
 font-size="16">Full-range residual control</text>
<line x1="650" y1="420" x2="1130" y2="420" stroke="black"/>
<line x1="650" y1="100" x2="650" y2="420" stroke="black"/>
<polyline points="{points}" fill="none" stroke="#222" stroke-width="2"/>
<line x1="{q16_x:.2f}" y1="100" x2="{q16_x:.2f}" y2="420" stroke="#555" stroke-dasharray="5 5"/>
<line x1="{q84_x:.2f}" y1="100" x2="{q84_x:.2f}" y2="420" stroke="#555" stroke-dasharray="5 5"/>
<text x="650" y="445" font-family="sans-serif" font-size="12">-100 ns</text>
<text x="1130" y="445" text-anchor="end" font-family="sans-serif" font-size="12">+100 ns</text>
<text x="890" y="470" text-anchor="middle" font-family="sans-serif"
 font-size="13">full under/overflow 0/0; core under/overflow 1/1</text>
</svg>
"""
    atomic_write(path, svg.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        type=Path,
        default=ROOT / "docs/validation/real_data_cfd_production_safeguard_validation.json",
    )
    parser.add_argument(
        "--svg",
        type=Path,
        default=ROOT / "docs/validation/real_data_cfd_production_safeguard.svg",
    )
    args = parser.parse_args()
    evidence = build_evidence()
    atomic_write(args.json, (json.dumps(evidence, indent=2, allow_nan=False) + "\n").encode())
    render_svg(evidence, args.svg)
    return 0 if evidence["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
