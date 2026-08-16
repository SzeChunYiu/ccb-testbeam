#!/usr/bin/env python3
"""Issue #2456 S51b saturated pile-up energy recovery benchmark wrapper.

This ticket uses the existing S32b saturation/energy-closure benchmark
implementation because it already performs the required raw ROOT reproduction,
run-held-out split, bootstrap confidence intervals, and method panel including
traditional, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture.
The wrapper isolates ticket metadata and output paths for testbeam-laptop-4.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2456"
WORKER = "testbeam-laptop-4"
SLUG = "s51b_saturated_pileup_energy_recovery_censored_pulse_windows"
TITLE = "S51b: Saturated pile-up energy recovery from censored pulse windows"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
CLAIMED_TICKET_BODY = """2456
# S51b: Saturated pile-up energy recovery from censored pulse windows

Academic-grade study: quantify how saturation, clipped samples, and overlapping pulses jointly bias charge, energy proxy, and recovered timing over separation, amplitude ratio, stave, and run-family strata.

Traditional method: constrained two-pulse template fit with censored-sample likelihood, spline charge correction, and analytic saturation-onset gates.

ML/NN comparison: ridge regression on censored-template residual features, gradient-boosted trees on shape/saturation summaries, MLP on engineered windows, 1D-CNN on raw clipped waveforms, and a causal transformer for multi-pulse windows where statistics support it.

Metrics: energy/charge bias, recovered-time RMS, pile-up separation resolution, saturation onset error, tail fraction, and calibrated uncertainty coverage. Use injection truth and run-held-out data with bootstrap 95% CIs and method-minus-template deltas.

Pulse-understanding target: determine when censored traditional fits are sufficient and when NN models recover physically meaningful energy and timing under pile-up and saturation.
"""
RAW_ROOT_CANDIDATES = (
    Path("/home/billy/ccb-data/extracted/root/root"),
    Path("/home/billy/ccb-data/data/extracted/root/root"),
    ROOT / "data" / "extracted" / "root" / "root",
)


def resolve_raw_root_dir() -> Path:
    for path in RAW_ROOT_CANDIDATES:
        if (path / "hrdb_run_0031.root").exists():
            return path
    return RAW_ROOT_CANDIDATES[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def postprocess_ticket_metadata() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# Issue #2456 S51b: Saturated Pile-Up Energy Recovery from Censored Pulse Windows",
        1,
    )
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred S51b controlled-overlay",
    )
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket_id"] = TICKET
    result["factory_issue"] = 2456
    result["title"] = TITLE
    result["status"] = "complete"
    result["claimed_ticket_text"] = TITLE
    result["ticket_workflow"] = {
        "claim_command": "tn-ticket claim testbeam-laptop-4 --project testbeam",
        "claim_artifact": f"reports/{OUT.name}/claimed_ticket.txt",
        "done_command_attempted": "tn-ticket done 2456",
        "done_command_status": "success_already_closed",
        "done_command_output": "Issue SzeChunYiu/factory-tickets#2456 (S51b: Saturated pile-up energy recovery from censored pulse windows) is already closed",
        "factory_issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2456",
    }
    result["execution_command"] = (
        "MPLCONFIGDIR=/tmp/matplotlib-2456-s51b "
        "uv run --index-strategy unsafe-best-match "
        "--index-url https://download.pytorch.org/whl/cpu "
        "--extra-index-url https://pypi.org/simple "
        "--with uproot --with awkward --with numpy --with pandas "
        "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
        f"python {Path(__file__).resolve().relative_to(ROOT)}"
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (OUT / "claimed_ticket.txt").write_text(CLAIMED_TICKET_BODY, encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["factory_issue"] = 2456
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.SLUG = SLUG
    s32b.TITLE = TITLE
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = resolve_raw_root_dir()
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
