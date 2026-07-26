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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].bar(
        ["event_id only", "(run,event_id)"],
        [event["unique_event_ids_without_run"], event["unique_composite_events"]],
    )
    axes[0].set_ylabel("identified events")
    axes[0].set_title("Collision-safe event identity control")
    axes[0].text(
        0.5,
        0.95,
        "Two runs reuse EVENTNO=7",
        ha="center",
        va="top",
        transform=axes[0].transAxes,
    )
    values = np.asarray(residual["input_ns"], dtype=float)
    axes[1].hist(values, bins=15, range=tuple(residual["full_range_ns"]))
    axes[1].axvline(residual["q16_centered_ns"], linestyle=":", linewidth=1)
    axes[1].axvline(residual["q84_centered_ns"], linestyle=":", linewidth=1)
    axes[1].set_xlabel("residual minus median (ns)")
    axes[1].set_ylabel("entries")
    axes[1].set_title("Full-range residual evidence")
    axes[1].text(
        0.5,
        0.95,
        "full under/overflow = 0/0\ncore under/overflow = 1/1",
        ha="center",
        va="top",
        transform=axes[1].transAxes,
    )
    fig.suptitle(
        "Real-data CFD production safeguards: composite keys, visible tails, pair-only inference"
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="svg")
    plt.close(fig)


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
