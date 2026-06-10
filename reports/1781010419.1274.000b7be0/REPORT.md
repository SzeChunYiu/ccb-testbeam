# S16d: forced-trigger validation of adaptive-lowering strata

- **Ticket:** `1781010419.1274.000b7be0`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `8dd38baebdff5b068a8c177c9e0d52bf97f778d0`
- **Config:** `s16d_config.json`

## Question

Locate true forced/random-trigger pedestal data if present, then test whether S16 adaptive-lowering strata correspond to true pedestal bias or mainly pre-trigger contamination in physics events.

## Raw ROOT reproduction first

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |
| forced/random-tagged ROOT entries | 0 | 0 | yes |

The mirror contains no true forced/random pedestal sample: ROOT trigger audit found `0` non-beam trigger entries and the filesystem scan found `0` forced/random/pedestal filename hits. Therefore the direct forced-trigger validation is blocked; the remaining tests use raw physics events and an explicitly labeled quiet no-pulse proxy.

## Traditional method

Traditional validation uses no fitted model. It recomputes the S16/S10c adaptive lowering from raw waveforms, assigns `s16_no_lowering`, `s16_mild_lowering`, and `s16_large_lowering`, then compares pedestal estimates to held-out pre-trigger samples by run. CIs bootstrap held-out runs and records within run.

| Method | stratum | n | mean bias [ADC] | MAE [ADC] |
|---|---|---:|---:|---:|
| adaptive_pc | s16_large_lowering | 10921 | -2186.39 [-2655.20, -1523.23] | 2362.64 [1722.26, 2808.05] |
| adaptive_pc | s16_mild_lowering | 3896 | -470.90 [-505.72, -420.07] | 521.63 [486.60, 560.85] |
| adaptive_pc | s16_no_lowering | 92667 | -55.56 [-65.13, -45.67] | 64.68 [53.47, 75.36] |
| median3 | not_applicable | 107484 | -35.32 [-45.39, -25.96] | 260.13 [233.36, 286.07] |

On selected physics pulses, adaptive large-lowering is a strong negative-bias stratum. The quiet no-pulse proxy does not show a comparable true-pedestal large-lowering population:

| Quiet-proxy stratum | n | mean bias [ADC] | MAE [ADC] |
|---|---:|---:|---:|
| s16_large_lowering | 359 | -992.32 [-1194.12, -284.90] | 992.80 [278.42, 1178.49] |
| s16_mild_lowering | 24086 | -1.86 [-2.11, -1.60] | 14.74 [14.56, 14.88] |
| s16_no_lowering | 47879 | -6.50 [-6.68, -6.22] | 13.31 [13.15, 13.42] |

## ML method

The ML method is a regularized logistic classifier for `s16_large_lowering`, trained on non-held-out runs and evaluated on runs `[57, 65]`. Features are pre-trigger summaries normalized by amplitude plus peak/stave; they exclude run, event id, trigger, filenames, adaptive-lowering value, stratum label, and any pedestal residual target. Best CV setting: `{'C': 10.0, 'cv_auc': 0.9947405875461848, 'cv_auc_std': 0.0017302922634878997, 'cv_average_precision': 0.9934189963226895}`.

Held-out result: AUC **0.997** [0.994, 0.999], average precision **0.997** [0.995, 0.999], positive fraction 0.456.

## Leakage checks

| Check | value | pass? | note |
|---|---:|---|---|
| shuffled_training_labels_auc | 0.348 | yes |  |
| intentional_lowering_oracle_auc | 1.000 | yes |  |
| row_split_minus_run_split_auc | -0.002 | yes |  |
| real_feature_exclusion |  | yes | features exclude run, event id, trigger, lowering value, stratum label, target residuals, and filenames |

## Conclusion

No true forced/random pedestal data is present in the mirror, so S16d cannot claim a direct forced-trigger validation. Within the raw data that does exist, the evidence points to adaptive-lowering strata being a pre-trigger contamination/pathology diagnostic rather than a true electronics pedestal-bias class: large lowering is predictable from pre-trigger shape on held-out runs and is associated with large selected-pulse LOPO bias, while quiet no-pulse proxy records are overwhelmingly not in the large-lowering stratum.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781010419.1274.000b7be0/s16d_forced_trigger_adaptive_strata.py --config reports/1781010419.1274.000b7be0/s16d_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `filesystem_runlog_scan.csv`, `selected_lopo_heldout_summary.csv`, `quiet_proxy_heldout_summary.csv`, `selected_strata_counts.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_heldout_scores.csv`, `leakage_checks.csv`, and PNG diagnostics.
