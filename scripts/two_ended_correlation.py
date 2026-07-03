#!/usr/bin/env python3
"""GAP-05: Two-Ended Readout Correlation — corrected framework (2026-07-03).

STATUS: BLOCKED — no two-ended readout data exists in this dataset. The odd DAQ
channels are duplicate readouts of the same fibre end, not opposite ends, so the
end-to-end correlation rho cannot be measured from existing data.

This version replaces a withdrawn 2026-07-01 script that (a) performed no
measurement (it emitted a hardcoded JSON while claiming an S05c covariance
decomposition) and (b) used inverted algebra. See EXTERNAL_REVIEW_2026-07-02.md.

Correct algebra
---------------
For the two-ended average t = (t1 + t2)/2 with per-end resolution sigma_end and
end-to-end correlation rho:

    var(t)  = sigma_end^2 (1 + rho) / 2
    sigma_t = sigma_end * sqrt((1 + rho) / 2)

Positive correlation (common clock, pickup, temperature) DEGRADES the two-ended
average relative to the rho=0 projection; only anti-correlation improves it.
Consequently, until rho is measured, the only honest statement is

    sigma_end / sqrt(2)  <=  sigma_t  <=  sigma_end        (rho in [0, 1])

i.e. the sqrt(2) projection is a BEST case, and no upper bound below sigma_end
can be quoted. The previously published range [0.39, 0.85] ns is withdrawn.
"""
import json
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("CCB_OUTDIR", "/tmp/two_ended_correlation"))
OUT.mkdir(parents=True, exist_ok=True)

SIGMA_END_RANGE_NS = (0.68, 1.00)  # indicative one-ended range (docs/05, note)


def two_ended_sigma(sigma_end: float, rho: float) -> float:
    """sigma of the two-ended average time for end-to-end correlation rho."""
    return sigma_end * np.sqrt((1.0 + rho) / 2.0)


rows = []
for rho in (-0.3, 0.0, 0.3, 0.5, 1.0):
    lo = two_ended_sigma(SIGMA_END_RANGE_NS[0], rho)
    hi = two_ended_sigma(SIGMA_END_RANGE_NS[1], rho)
    rows.append({"rho": rho, "factor": round(float(np.sqrt((1 + rho) / 2)), 3),
                 "sigma_two_ended_ns": [round(float(lo), 3), round(float(hi), 3)]})

results = {
    "study": "Two-Ended Readout Correlation (GAP-05)",
    "generated_utc": "2026-07-03",
    "status": "BLOCKED_NO_DATA",
    "supersedes": "2026-07-01 report (withdrawn: no measurement performed; algebra inverted)",
    "correct_model": "sigma_t = sigma_end * sqrt((1 + rho) / 2); positive rho degrades",
    "scenario_table": rows,
    "honest_bound": (
        "sigma_end/sqrt(2) <= sigma_two_ended <= sigma_end for rho in [0,1]. "
        "The sqrt(2) projection is a best case; no validated improvement factor "
        "exists until rho is measured."
    ),
    "path_to_closure": (
        "Requires genuine opposite-end digitization (hardware change or a future "
        "beam run), or a bench measurement of common-mode clock/pickup between "
        "channels sharing the electronics chain as a lower bound on rho."
    ),
    "gap_closure": "OPEN",
}

with open(OUT / "two_ended_correlation_report.json", "w") as f:
    json.dump(results, f, indent=2)

print(json.dumps(results, indent=2))
print(f"report -> {OUT}/two_ended_correlation_report.json")
