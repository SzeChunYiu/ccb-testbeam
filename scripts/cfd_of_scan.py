#!/usr/bin/env python3
"""GAP-06: CFD/OF Parameter Scan

Systematically scan CFD fraction (10-50%) and optimal filter window (3-18 samples)
to verify CFD20 is near-optimal and quantify sensitivity.
"""
import json, os, sys
import numpy as np
from pathlib import Path

OUT = Path(os.environ.get("CCB_OUTDIR", "/tmp/cfd_of_scan"))
OUT.mkdir(parents=True, exist_ok=True)

results = {
    "study": "CFD/OF Parameter Scan (GAP-06)",
    "description": "Systematic scan of CFD fraction and optimal filter window parameters",
    "status": "framework_ready",
    "dependency": "Requires S02 timing data with per-CFD-fraction times",
    "cfd_fractions": list(range(10, 55, 5)),
    "of_windows": [3, 6, 9, 12, 15, 18],
    "recommended_default": {"cfd_fraction": 20, "of_window": 9},
    "gap_closure_criterion": "If default is within 5% of optimum sigma68, GAP-06 is closed",
    "next_step": "Run with actual S02 data to compute sigma68 per parameter set"
}

with open(OUT / "cfd_of_scan_report.json", "w") as f:
    json.dump(results, f, indent=2)

print(json.dumps(results, indent=2))
print(f"report -> {OUT}/cfd_of_scan_report.json")
