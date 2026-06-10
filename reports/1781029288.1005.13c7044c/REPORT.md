# S10h: stress-test S10f overlay realism

- **Ticket:** `1781029288.1005.13c7044c`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT only; no Monte Carlo.
- **Config:** `configs/s10h_1781029288_1005_13c7044c_overlay_realism_stress.json`

## Question

Stress-test whether S10f's synthetic overlay benchmark is too template-like. The study reruns the S10d/S10f reproduction gates from raw ROOT first, then compares a strong traditional amplitude-binned/asymmetric two-pulse fit to a compact ML classifier/regressor on stricter overlays split by source run.

## Reproduction Gate

Raw selected-pulse count reproduction passed: `640737` selected B-stave pulses versus `640737` reported. S10 injection AP and S10b live-time reproduction also passed; details are in `s10_ml_reproduction.csv` and `s10b_reproduction.csv`.

The S10f anchor benchmark was recreated from raw pulses before the stress test. Its reproduced delay rows match the merged S10f report, including non-finite stable delays and finite bootstrap lower tails:

| Quantity | Report | Reproduced | Pass |
|---|---:|---:|---|
| S10f amp_binned_asymmetric_template_fit value | not stable | not stable | True |
| S10f amp_binned_asymmetric_template_fit ci_low | 50.0 | 50.0 | True |
| S10f amp_binned_asymmetric_template_fit ci_high | 60.0 | 60.0 | True |
| S10f compact_mlp_classifier_regressor value | not stable | not stable | True |
| S10f compact_mlp_classifier_regressor ci_low | 22.5 | 22.5 | True |
| S10f compact_mlp_classifier_regressor ci_high | 60.0 | 60.0 | True |

## Methods

Training source runs are `[58, 59, 60, 61, 62]` and held-out source runs are `[63, 65]`. Template fitting and ML training never see held-out source runs or held-out generation families.

The traditional method uses train-run-only amplitude-binned/asymmetric templates, with different primary and secondary candidates allowed in the bounded two-pulse least-squares fit. The stress overlays are generated from separate run-family templates, with run-family residual pools, baseline offset and slope jitter, late-tail jitter, time jitter, amplitude jitter, and cross-family second pulses. `stress_template_family_summary.csv` has 16 family/stave rows; `stress_template_summary.csv` has 36 train-only fit templates.

The ML method is the compact S10f MLP classifier/regressor trained on the same stricter training overlays. Identifiers, source run, and generation-family labels are excluded from features.

## Result

The stricter overlays make the S10f benchmark look more fragile: neither method reaches a finite stable delay under the S10d bias gate.

| Method | stress delay ns | bootstrap 95% CI ns | AP | time RMS ns | area bias | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| traditional stress fit | not stable | [50.0, 60.0] | 0.705 | 17.60 | -0.007 | 0.028 |
| compact ML stress fit | not stable | [10.0, 60.0] | 0.853 | 8.76 | -0.006 | 0.287 |

S10f anchor time RMS values on the original benchmark were 17.81 ns for the traditional fit and 9.28 ns for ML. Under the stricter overlays they are 17.60 ns and 8.76 ns.

## Held-Out Runs

| Run | Method | delay ns | positives |
|---:|---|---:|---:|
| 63 | stress_amp_binned_template_fit | not stable | 300 |
| 65 | stress_amp_binned_template_fit | not stable | 300 |
| 63 | stress_compact_mlp_classifier_regressor | 50.0 | 300 |
| 65 | stress_compact_mlp_classifier_regressor | not stable | 300 |

## Leakage Probes

`leakage_checks.csv` records strict source-run separation, no event-id overlap, held-out generation families absent from training, shuffled-label AP, and too-good sentinels. It found 0 flags. The shuffled-label held-out AP was `0.474`.

## Interpretation

The S10f overlay closure should be treated as template-family dependent. Adding held-out template families and realistic residual/baseline jitter does not rescue the traditional fit and does not produce a suspiciously good ML result. The result is evidence against using the original S10f synthetic overlay as a realism proof for beam pile-up; it remains a method-ranking closure on data-derived overlays.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s10h_1781029288_1005_13c7044c_overlay_realism_stress.py --config configs/s10h_1781029288_1005_13c7044c_overlay_realism_stress.json
```

Runtime in this run was `271.06` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, anchor tables, stress metrics, bootstrap CIs, leakage checks, and figures.
