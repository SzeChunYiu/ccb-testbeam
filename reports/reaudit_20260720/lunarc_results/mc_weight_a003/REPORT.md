# MC weight effective sample size (A-003, CCB-MCWEIGHT)

Quantifies P0 finding A-003 ("MC event weights mostly ignored") against the
deployed krakow MC (`geant4/data/output_krakow_1M.root`, `PrimaryWeight`, 2,000,000
primaries).

| quantity | value |
|---|--:|
| n (primaries) | 2,000,000 |
| Σw | 6,445,162 |
| **effective sample size (ESS = (Σw)²/Σw²)** | **694,524** |
| **ESS fraction** | **0.347** |
| weight min / max | 0.126 / 15.325 |
| weight p50 / p99 | 0.652 / 14.919 |
| max / mean | 4.76 |

## Interpretation
The weights are **not** trivially flat: they span 0.13–15.3 (≈120×) with a heavy
high-weight tail (p99 = 14.9 vs p50 = 0.65). The **effective sample size is only
35% of nominal**. Therefore any analysis that reads MC truth **unweighted** (which
`tools/audit/audit_repository.py` flagged as `MC_WEIGHT_NOT_DECLARED` in 36
scripts) is:

1. **biased** — it represents the uniform-θ_cm generation, not the physical
   lab-angle cross-section (the Jacobian/weight is exactly what converts one to
   the other); and
2. **statistically weaker** — ~65% of the effective statistics are lost, and the
   physically important high-weight events are under-represented.

This confirms A-003 is a genuine P0: per `docs/contracts/MC_WEIGHT_POLICY.md`, every
MC-truth analysis must consume `PrimaryWeight` (or explicitly justify unweighted).
Reweighting/regenerating the 36 flagged scripts remains BLOCKED_COMPUTE (each must
be re-run weighted and re-validated).
