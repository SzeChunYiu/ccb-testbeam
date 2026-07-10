#!/usr/bin/env python3
"""S01j calibrated charge-depth transfer benchmark.

This ticket repeats the S01i charge-depth transfer panel under the S01j claim,
preserving the raw ROOT reproduction, run-heldout split, bootstrap CIs, and the
q-token/atom-gated architecture family.
"""

from __future__ import annotations

import importlib.machinery
import sys
from pathlib import Path


S01I = importlib.machinery.SourceFileLoader(
    "s01i_charge_depth",
    "scripts/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.py",
).load_module()

ORIGINAL_WRITE_REPORT = S01I.write_report

DEFAULT_CONFIG = "configs/s01j_1783603932_26998_27ca583b_charge_depth_truth_transfer.yaml"
SCRIPT_PATH = "scripts/s01j_1783603932_26998_27ca583b_charge_depth_truth_transfer.py"


def write_report(out_dir, result, summary, per_run, repro, transfer_rows, qdiag, target_diag):
    ORIGINAL_WRITE_REPORT(out_dir, result, summary, per_run, repro, transfer_rows, qdiag, target_diag)
    report = Path(out_dir) / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S01i Charge-Depth Truth Transfer for q-Template Support Atom",
        "# S01j Charge-Depth Truth Transfer for q-Template Support Atom",
        1,
    )
    text = text.replace("**Date:** 2026-07-10", "**Date:** 2026-07-11", 1)
    text = text.replace("This study repeats the S01h transfer panel", "This S01j study repeats the S01h/S01i transfer panel", 1)
    text = text.replace(
        "/home/billy/anaconda3/bin/python scripts/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.py --config configs/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.yaml",
        f"/home/billy/anaconda3/bin/python {SCRIPT_PATH} --config {DEFAULT_CONFIG}",
        1,
    )
    report.write_text(text, encoding="utf-8")


def main() -> int:
    S01I.write_report = write_report
    if "--config" not in sys.argv:
        sys.argv.extend(["--config", DEFAULT_CONFIG])
    return int(S01I.main())


if __name__ == "__main__":
    raise SystemExit(main())
