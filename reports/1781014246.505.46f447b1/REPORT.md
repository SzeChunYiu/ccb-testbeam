# S16g: quiet-run pseudo-pedestal calibration

- **Ticket:** `1781014246.505.46f447b1`
- **Worker:** `testbeam-laptop-4`
- **Input manifest:** `input_sha256.csv`
- **Config:** `s16g_config.json`
- **Git commit:** `904ea43c32e46a8f9f838566a68ab4e43fd37e68`

## Question

Can the quietest beam-event strata serve as a calibrated pseudo-pedestal without biasing low-amplitude pulse baselines, given that S16d found no true forced/random pedestal runs?

## Raw ROOT reproduction first

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |
| forced/random-tagged ROOT entries | 0 | 0 | yes |

## Frozen strata

Traditional quiet strata were fixed before held-out scoring. `quietest` requires event max < 80 ADC, pre-trigger std <= 8 ADC, pre-trigger range <= 25 ADC, adaptive lowering <= 0.1 ADC, and run quietest fraction >= 0.0050. `quietish` relaxes those cuts to event max < 200 ADC, pre-trigger std <= 16 ADC, pre-trigger range <= 55 ADC, and adaptive lowering <= 200 ADC.

## Run-held-out benchmark

Each row predicts the S16 adaptive baseline for a fixed run-balanced scoring sample of low-amplitude pulses (1000-3000 ADC, max 2500 records per run) in one held-out run. Traditional methods use the held-out run's frozen quiet stratum to form a run/stave pseudo-pedestal and subtract a train-run stave calibration offset. ML trains a pre-trigger-only quiet-probability model with no run id or post-trigger amplitude features, then forms an inverse-probability weighted quiet pedestal.

| Method | n | pedestal bias [ADC] | pedestal MAE [ADC] | charge bias [ADC sample] | timing-tail delta |
|---|---:|---:|---:|---:|---:|
| traditional_quietish_calibrated_median | 70887 | -89.84 [-102.86, -71.78] | 123.91 [103.40, 140.27] | 808.6 [646.0, 925.8] | 0.0036 [0.0031, 0.0042] |
| traditional_quietest_calibrated_median | 70887 | -89.82 [-103.97, -73.28] | 123.93 [103.77, 140.57] | 808.4 [659.5, 935.8] | 0.0036 [0.0029, 0.0042] |
| ml_ipw_quiet_probability | 70887 | -89.81 [-104.32, -73.88] | 123.95 [104.94, 139.60] | 808.3 [665.0, 938.9] | 0.0036 [0.0030, 0.0043] |

## ML calibration

The ML quiet-probability model was Gaussian Naive Bayes on pre-trigger-only features. It had mean held-out AUC **0.721** [0.714, 0.729], AP **0.316** [0.277, 0.355], and calibration ECE **0.580** [0.557, 0.602] across leave-one-run-out folds. The model family was fixed in config before held-out scoring.

## Leakage checks

| Check | value | pass? | note |
|---|---:|---|---|
| ml_feature_forbidden_column_overlap | 0.000 | yes | ML features are pre-trigger only plus stave index; no run id or post-trigger pulse amplitude. |
| loro_train_heldout_run_overlap | 0.000 | yes | Each fold trains on all runs except the held-out run. |
| ml_probability_too_good_auc | 0.721 | yes | If this failed, probability labels would need a stronger leakage audit. |
| quietest_stratum_not_empty | 882366.000 | yes |  |
| pedestal_residual_exact_zero_fraction | 0.003 | yes | Guards against accidentally scoring the S16 adaptive baseline against itself. |

## Conclusion

The quietest and quietish traditional pseudo-pedestals are nearly indistinguishable, with quietish slightly lower in MAE in this run-balanced score. They keep the mean pedestal bias bounded relative to the S16 adaptive baseline but still have non-negligible MAE and a measurable charge shift on low-amplitude pulses, so quiet beam-event strata are usable as emergency references but not zero-bias replacements for real random/forced pedestal data. The ML IPW estimator is useful as a calibration diagnostic, but it does not dominate the frozen traditional medians.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781014246.505.46f447b1/s16g_1781014246_quiet_pseudopedestal.py --config reports/1781014246.505.46f447b1/s16g_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_by_run.csv`, `ml_fold_summary.csv`, `ml_calibration_bins.csv`, `leakage_checks.csv`, and PNG diagnostics.
