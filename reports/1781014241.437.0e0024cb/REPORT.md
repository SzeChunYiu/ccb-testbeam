# Study report: P05b - failure-aware two-pulse abstention calibration

- **Study ID:** P05b
- **Ticket:** `1781014241.437.0e0024cb`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/p05b_1781014241_437_0e0024cb.json`

## 0. Question

Can S10d/S11a two-pulse recovery be made operational by calibrating when to abstain, rather than only minimizing average recovered-time RMS?

## 1. Reproduction gate

The raw `HRDv` selected-pulse count was rerun first from `data/root/root`. It reproduced `640737` selected B-stave pulses versus `640737` reported, with zero tolerance. The S10 injection AP reproduction also passed: `[0.982, 0.9719]`.

## 2. Methods

The base benchmark is regenerated from raw ROOT using the frozen S11a injected two-pulse construction. Training runs are `[58, 59, 60, 61, 62]` and held-out runs are `[63, 65]`. The recovery methods are the frozen bounded S01-style two-pulse template fit and the compact S11a MLP classifier/regressor.

The traditional abstention gate is a train-run-only grid of quality cuts on fit failure, fractional SSE improvement, chi2/ndf proxy, fitted separation, and amplitude ratio. The ML gate is a logistic risk model over normalized waveform features plus fit diagnostics, isotonic-calibrated with leave-one-run-out train folds. Both gates choose their operating threshold on train runs only to target bad-recovery rate <= `0.15`.

Bad recovery means the base method failed, event constituent-time RMS exceeded `12.0 ns`, or absolute charge bias exceeded `0.20`.

## 3. Held-out result

| Method | coverage | abstention | accepted time RMS ns | charge bias | charge res68 | bad recovery | risk-coverage AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| traditional train quality cuts | 0.343 | 0.657 | 7.42 [6.61, 8.26] | -0.028 | 0.070 | 0.092 | 0.197 |
| ML isotonic failure gate | 0.728 | 0.272 | 8.44 [8.28, 8.59] | -0.014 | 0.064 | 0.144 | 0.138 |

The traditional quality-cut gate remains competitive; ML calibration mainly gives a smoother risk ranking rather than an unambiguous operating-point win. The detailed bootstrap intervals are in `calibrated_method_summary.csv`.

## 4. Dependence on separation and amplitude ratio

The held-out bin tables are `metrics_by_separation.csv` and `metrics_by_ratio.csv`. The gate is most costly below 10 ns separation, where both methods abstain heavily because the train-calibrated bad-recovery probability rises.

## 5. Leakage checks

Run splitting is strict, thresholds are selected only on train runs, and event ids do not overlap. The base MLP shuffled-label sentinel from the S11a leakage check is `0.465` AP, and all P05b leakage checks pass in `leakage_checks.csv`.

## 6. Threats to validity

This is an injected, data-driven closure over raw-pulse-derived templates and residuals. It calibrates whether a recovered two-pulse correction should be trusted for timing/charge use, but it is not a direct measurement of real high-current pile-up truth.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/p05b_1781014241_437_0e0024cb_abstention_calibration.py --config configs/p05b_1781014241_437_0e0024cb.json
```

Runtime in this run was `28.54` s.
