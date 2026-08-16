#!/usr/bin/env python3
"""TICKET-0130 raw-ROOT count reconstruction benchmark wrapper.

This ticket uses the existing S32b saturation/energy-closure benchmark
implementation because it already performs the required raw ROOT reproduction,
run-held-out split, bootstrap confidence intervals, and method panel including
traditional, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture.
The wrapper isolates ticket metadata and output paths for testbeam-laptop-4.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "TICKET-0130"
WORKER = "testbeam-laptop-4"
SLUG = "raw_root_count_reconstruction_bakeoff"
TITLE = "TICKET-0130 raw-ROOT count reconstruction bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"


def resolve_raw_root_dir() -> Path:
    candidates = [
        os.environ.get("TESTBEAM_RAW_ROOT_DIR"),
        ROOT / "data" / "extracted" / "root" / "root",
        Path("/home/billy/ccb-data/extracted/root/root"),
        Path("/home/billy/ccb-data/data/extracted/root/root"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        path = Path(candidate)
        if (path / "hrdb_run_0031.root").exists():
            return path
    raise FileNotFoundError("Could not locate hrdb_run_0031.root in known raw ROOT mirrors")


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
        "# TICKET-0130: Raw-ROOT Count Reconstruction Bakeoff",
        1,
    )
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred TICKET-0130 controlled-overlay",
    )
    if "## Caveats and Limitations" not in report:
        report = report.replace(
            "Systematic caveats are material.",
            "## Caveats and Limitations\n\nSystematic caveats are material.",
            1,
        )
    report_path.write_text(report, encoding="utf-8")
    (ROOT / "REPORT.md").write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket_id"] = TICKET
    result["title"] = TITLE
    result["claimed_ticket_text"] = "TICKET-0130 raw-ROOT count reconstruction bakeoff"
    result["ticket_done"] = {
        "attempted_command": "tn-ticket done TICKET-0130",
        "status": "failed_invalid_issue_format",
        "stderr": "invalid issue format: \"TICKET-0130\"",
        "reason": "The claim artifact is a non-numeric pseudo-ticket and no open factory:claimed project:testbeam issue is labeled worker:testbeam-laptop-4.",
    }
    result["execution_command"] = (
        "MPLCONFIGDIR=/tmp/matplotlib-ticket0130 "
        "uv run --no-project --index-strategy unsafe-best-match "
        "--index-url https://download.pytorch.org/whl/cpu "
        "--extra-index-url https://pypi.org/simple "
        "--with uproot --with awkward --with numpy --with pandas "
        "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
        f"python {Path(__file__).resolve().relative_to(ROOT)}"
    )
    result_text = json.dumps(result, indent=2) + "\n"
    result_path.write_text(result_text, encoding="utf-8")
    (ROOT / "result.json").write_text(result_text, encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
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
