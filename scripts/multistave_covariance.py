#!/usr/bin/env python3
"""Multi-Stave Combination Covariance — corrected status (2026-07-03).

STATUS: WITHDRAWN as a closure; reissued as an honest bound calculation.

The 2026-07-01 version plugged S05c's raw pair-residual mean |covariance|
(16 ns^2) into a 3x3 matrix whose diagonals are 0.52-2.10 ns^2 — an indefinite
"covariance" matrix (implied correlation ~15) — and its conclusion string
("delta well within the reported range ... VALID") contradicted its own
computed delta of 2.702 ns. See EXTERNAL_REVIEW_2026-07-02.md.

What a valid closure needs (not yet available):
  - per-stave, timewalk-corrected event-level residuals for B4/B6/B8,
  - a robust covariance estimate projected to the nearest PSD matrix,
  - propagation through the inverse-variance combination.
S05c's published values are covariances of RAW, tail-heavy CFD20 *pair*
residuals — a different basis that cannot be reused here.

What we can say today: with per-stave sigmas (sigma4, sigma6, sigma8) and NO
covariance measurement, Cauchy-Schwarz (|c_ij| <= sigma_i * sigma_j) bounds the
equal-weight combined sigma between ~0 and the fully-correlated limit. The
independence value sits inside an interval too wide to validate the headline
sigma_comb ~ 0.54-0.56 ns. The covariance MUST be measured, not assumed.
"""
import json
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("CCB_OUTDIR", "/tmp/multistave_covariance"))
OUT.mkdir(parents=True, exist_ok=True)

# Per-stave sigmas from the note's downstream decomposition (docs/05, Table 19).
# NOTE: these carry no propagated uncertainty and are themselves under review.
sigma = np.array([1.45, 0.72, 0.93])  # B4, B6, B8 (ns)

var_sum = float(np.sum(sigma**2))
# Equal-weight average of three staves: var = (sum var_i + 2 sum_{i<j} c_ij) / 9
pair_bound = float(sigma[0] * sigma[1] + sigma[0] * sigma[2] + sigma[1] * sigma[2])

sigma_indep = float(np.sqrt(var_sum / 9.0))
sigma_max = float(np.sqrt((var_sum + 2.0 * pair_bound) / 9.0))  # fully correlated
sigma_min = float(np.sqrt(max(var_sum - 2.0 * pair_bound, 0.0) / 9.0))  # PSD floor

results = {
    "study": "Multi-Stave Combination Covariance (bound calculation)",
    "generated_utc": "2026-07-03",
    "status": "WITHDRAWN_AS_CLOSURE",
    "supersedes": (
        "2026-07-01 report (withdrawn: indefinite covariance matrix from a "
        "category-error reuse of S05c raw pair covariances; conclusion "
        "contradicted its own numbers; the '-0.127 ns^2 fitted covariance' "
        "cited in top-level docs exists in no artifact)"
    ),
    "per_stave_sigma_ns": {"B4": 1.45, "B6": 0.72, "B8": 0.93},
    "equal_weight_combined_sigma_ns": {
        "independence_assumed": round(sigma_indep, 3),
        "cauchy_schwarz_bounds_without_measurement": [
            round(sigma_min, 3),
            round(sigma_max, 3),
        ],
    },
    "conclusion": (
        "Without a measured B4/B6/B8 error covariance the combined sigma is "
        f"only bounded to [{sigma_min:.2f}, {sigma_max:.2f}] ns; the "
        f"independence value ({sigma_indep:.3f} ns) is a point inside that "
        "interval, not a validated result. The 0.54-0.56 ns headline requires "
        "a real covariance measurement on timewalk-corrected residuals."
    ),
    "gap_closure": "OPEN",
}

with open(OUT / "multistave_covariance_report.json", "w") as f:
    json.dump(results, f, indent=2)

print(json.dumps(results, indent=2))
print(f"report -> {OUT}/multistave_covariance_report.json")
