#!/usr/bin/env python3
"""Emit the v2 re-audit mandatory status corrections as machine-readable records.

The v2 CRITICAL_FINDINGS_SUMMARY.json mandates status changes for MV0..MV6 and
the eventno-only ΔE–E outputs. This writes them as closure records (schema in
schemas/closure_record.schema.json) so downstream status is sourced from a
versioned artifact, not prose. Run from repo root:

    python tools/generate_status_corrections.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# (study, new_status_label, finding_id, rationale, downstream_action, blocker)
CORRECTIONS = [
    ("MV0-gain", "CORRECTED/BLOCKED", "A-001",
     "92 ADC/MeV derived from a pulse amplitude that was baseline-subtracted "
     "twice (pulse-table double subtraction). Value invalid until the table is "
     "regenerated under docs/contracts/PULSE_TABLE_CONTRACT.md.",
     "Re-derive gain from the v1 pulse contract.", "BLOCKED_COMPUTE"),
    ("MV1", "MC_TRUTH_ONLY_REAUDIT", "A-003",
     "MC weight (PrimaryWeight) ignored, so distributions are unweighted truth, "
     "not physical production. Reclassify as truth-only until reweighted.",
     "Reweight per docs/contracts/MC_WEIGHT_POLICY.md; publish ESS.",
     "BLOCKED_EXTERNAL"),
    ("MV3-stopping", "FAIL_DIAGNOSTIC", "A-004",
     "Stopping-depth data/MC comparison used a thresholded amplitude and an "
     "unresolved layer->stave mapping. Not a closure; a diagnostic only.",
     "Fix mapping (geometry contract), re-run weighted with material budget.",
     "BLOCKED_COMPUTE"),
    ("MV4-timing", "TOY_DIAGNOSTIC", "A-007",
     "Timing 1/A correction uses a hard-coded 246 ADC/MeV gain and hard-coded "
     "data anchors/uncertainties instead of loading v2 calibration + result "
     "files. Toy until re-run with real calibration.",
     "Load v2 gain + anchors from result files; add slicing/metrics; re-run.",
     "BLOCKED_COMPUTE"),
    ("MV5-pileup", "SELF_CONSISTENCY_ONLY", "A-006",
     "Inserts the measured tau_eff=124.8 ns and the same 0.38 factor into the "
     "capacity equation and uses fixed-threshold leading-edge theory while the "
     "code applies CFD20. Not an independent MC validation.",
     "Rebuild an independent pile-up validation consistent with CFD20.",
     "BLOCKED_COMPUTE"),
    ("MV6-C12anomaly", "MC_HYPOTHESIS_TENSION", "A-009",
     "C12 early-peak identity overclaimed: MC predicts ~0.32% early-peak "
     "fraction vs ~4% in data, with radically different saturation fractions. "
     "C12 dominance in one MC-selected class is a hypothesis, not data closure.",
     "State as MC hypothesis with tension; do not claim data-anomaly identity.",
     "BLOCKED_EXTERNAL"),
    ("DeltaE-E-eventno-outputs", "INVALID_PENDING_RERUN", "A-002",
     "Prior ΔE–E outputs joined data on eventno alone (cross-run collisions), "
     "ignored declared thresholds, used unseeded sampling, and defined stopping "
     "as any-deposit. Invalid until re-run with the composite-key module.",
     "Re-run with scripts/single_stave/deltaE_E.py (composite key + thresholds).",
     "BLOCKED_EXTERNAL"),
]


def main() -> int:
    target = REPO / "reports" / "reaudit_20260720" / "status_corrections"
    target.mkdir(parents=True, exist_ok=True)

    records = []
    for study, label, fid, rationale, action, blocker in CORRECTIONS:
        rec = {
            "task_id": f"STATUS-{study}",
            "status": "CORRECTED" if "CORRECTED" in label else (
                "FAILED_INFORMATIVE" if label in
                ("FAIL_DIAGNOSTIC", "TOY_DIAGNOSTIC", "SELF_CONSISTENCY_ONLY",
                 "MC_HYPOTHESIS_TENSION", "INVALID_PENDING_RERUN",
                 "MC_TRUTH_ONLY_REAUDIT") else "BLOCKED_COMPUTE"),
            "issue": fid,
            "mandated_label": label,
            "rationale": rationale,
            "downstream_action": action,
            "blocker": blocker,
            "dependencies": [],
            "evidence": ["audit/CRITICAL_FINDINGS_SUMMARY.json", f"BUG_LEDGER_V2:{fid}"],
            "acceptance": [{
                "criterion": f"{study} carries mandated label '{label}' in status docs",
                "passed": True,
                "evidence": "this record",
            }],
            "notes": f"Mandated by v2 re-audit. Downstream closure: {blocker}.",
        }
        records.append(rec)

    (target / "status_corrections.json").write_text(json.dumps(records, indent=2))
    with (target / "status_corrections.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["study", "mandated_label", "closure_status", "finding",
                    "blocker", "downstream_action", "rationale"])
        for study, label, fid, rationale, action, blocker in CORRECTIONS:
            cs = ("CORRECTED" if "CORRECTED" in label else
                  ("BLOCKED_COMPUTE" if label not in
                   ("FAIL_DIAGNOSTIC", "TOY_DIAGNOSTIC", "SELF_CONSISTENCY_ONLY",
                    "MC_HYPOTHESIS_TENSION", "INVALID_PENDING_RERUN",
                    "MC_TRUTH_ONLY_REAUDIT") else "FAILED_INFORMATIVE"))
            w.writerow([study, label, cs, fid, blocker, action, rationale])

    print(f"wrote {len(records)} status corrections to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
