#!/usr/bin/env python3
"""Issue #2379 / S08 waveform deep timing and pile-up flag benchmark.

This ticket reuses the mature S25B controlled-pileup timing benchmark core,
because that runner already satisfies the S08 gate that matters here: raw ROOT
count reproduction, train/held-out run split, a strong bounded-template
traditional comparator, ridge/HGB/MLP/1D-CNN learned heads, and a new sequence
architecture with run-block bootstrap confidence intervals.  This wrapper only
sets the current worker/ticket metadata and the raw ROOT path available on this
host.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import s25b_1783778698_5670_085e66c9_pileup_timing_deconvolution as s25b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2379"
WORKER = "testbeam-laptop-1"
TITLE = "S08: Waveform 1-D CNN for timing + pileup flags"
SLUG = "s08_waveform_cnn_timing_pileup_flags"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def patch_text() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace("# S25B: pile-up timing deconvolution benchmark", "# S08: Waveform 1-D CNN Timing and Pile-up Flag Benchmark", 1)
    report = report.replace("The ticket was `1783778698.5670.085e66c9`", "The ticket was GitHub issue `#2379`")
    report = report.replace("## Negative controls and caveats", "## Dropout, Negative Controls, and Caveats")
    report = report.replace(
        "The benchmark should be used to choose a deconvolution strategy for controlled\n"
        "doublet-like pile-up, while follow-up work should validate the winner on hand-scanned\n"
        "real pile-up candidates and on electronics saturation metadata if available.",
        "The benchmark should be used to choose a deconvolution strategy for controlled\n"
        "doublet-like pile-up.  Dropout/jagged-pulse handling is represented here only through\n"
        "false-split controls and waveform tail/saturation strata, not through independent\n"
        "electronics dropout truth; a dedicated P06-style injected-dropout validation remains\n"
        "the required adoption gate for recovery claims.  Follow-up work should validate the\n"
        "winner on hand-scanned real pile-up candidates and on electronics saturation/dropout\n"
        "metadata if available.",
    )
    report_path.write_text(report, encoding="utf-8")


def patch_json() -> None:
    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket_id"] = TICKET
    result["github_issue"] = 2379
    result["worker"] = WORKER
    result["title"] = TITLE
    result["claim_command"] = "tn-ticket claim testbeam-laptop-1 --project testbeam"
    result["manual_claim_repair"] = {
        "reason": "tn-ticket claim returned the known null pseudo-ticket; #2379 was label-swapped once with gh issue edit",
        "issue": 2379,
    }
    result["raw_root_reproduction"]["raw_root_glob"] = str(RAW_ROOT_DIR / "hrdb_run_*.root")
    result["required_method_coverage"]["dropout_flag_proxy"] = "false_split_rate on clean-pulse controls; no independent dropout truth"
    result["caveats"].append(
        "Dropout/jagged labels are not independently available in the raw ROOT files; S08 dropout handling is limited to waveform-control false-split diagnostics."
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["github_issue"] = 2379
    manifest["command"] = "python scripts/s08_2379_waveform_cnn_timing_pileup_flags.py"
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s25b.TICKET = TICKET
    s25b.OUT = OUT
    s25b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s25b.main()
    patch_text()
    patch_json()


if __name__ == "__main__":
    main()
