#!/usr/bin/env python3
"""S48b ticket wrapper for saturation and pile-up energy-recovery bakeoff."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2444"
TITLE = "S48b saturation and pile-up energy-recovery method bakeoff"
SLUG = "s48b_saturation_pileup_energy_recovery_bakeoff"
WORKER = "testbeam-laptop-1"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def postprocess_ticket_metadata() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    replacements = {
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff": "# S48b: Saturation and Pile-up Energy-Recovery Method Bakeoff",
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay": "Use `saturation_residual_fusion_new` as the preferred S48b controlled-overlay",
    }
    for old, new in replacements.items():
        report = report.replace(old, new)
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "github_issue": 2444,
            "title": TITLE,
            "worker": WORKER,
            "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
            "claimed_ticket_text": "S48b: Saturation and pile-up energy-recovery method bakeoff",
            "claim_recovery_note": (
                "The required tn-ticket claim command was run once; it returned null due to the "
                "known null existing-ticket edge case, so issue #2444 was label-claimed via gh."
            ),
            "raw_root_reproduction": {
                **result["raw_root_reproduction"],
                "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            },
        }
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(result_path, ROOT / "result.json")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["github_issue"] = 2444
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"] = {
        p.name: s32b.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.TITLE = TITLE
    s32b.SLUG = SLUG
    s32b.WORKER = WORKER
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
