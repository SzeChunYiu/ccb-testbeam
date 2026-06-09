# Study report: S16b - forced-trigger pedestal validation

- **Ticket:** 1781001221.625922.5a564a7e
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `e1006f46a1f4c96682778a602dbb8d9a9deeb3df`
- **Config:** `s16b_config.json`

## Question

Is the adaptive pedestal unbiased when validated on true no-pulse forced/random-trigger events rather than physics-event pre-trigger samples?

## Raw ROOT reproduction first

Two raw-ROOT checks were run before modeling:

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |
| forced/random-tagged ROOT entries (`TRIGGER != 1` or forced/random filename token) | 0 | 0 | yes |

The current mirror still contains no populated true forced/random pedestal sample: every populated A/B ROOT file has `TRIGGER == 1`; A-stack runs 0000-0003 are empty. The rest of this report is therefore a clearly labeled **quiet no-pulse proxy**, not a true forced-trigger validation.

## Proxy dataset

Proxy no-pulse events are B-stack events where all configured B staves have baseline-subtracted max amplitude below `80 ADC` using samples 0-3 as the seed pedestal. This gives `386967` events and `1547868` stave records across configured runs; held-out runs `[57, 65]` contribute `1883784` sample-level targets from samples [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17].

## Methods

Traditional estimators:
- `median4_pre`: median of samples 0-3.
- `mean4_pre`: mean of samples 0-3.
- `median4_plus_train_offset`: median4 plus a train-run median offset by stave and target sample.
- `adaptive_pc_excluding_target`: S16 adaptive positivity correction, with the target sample excluded from the constraint.

ML estimator: `ml_pretrigger_hgbr_calibrated`, a histogram-gradient-boosted regressor using only pre-trigger summaries, stave, and target sample. Splits are by run: held-out runs [57, 65], calibration runs [56, 64], all remaining configured runs for model development. Best CV setting: `{'max_leaf_nodes': 15.0, 'learning_rate': 0.1, 'l2_regularization': 0.1, 'cv_mae_adc': 15.903433510793912, 'cv_mae_std_adc': 1.244156582803603}`.

## Held-out benchmark

Intervals are run-heldout bootstraps over runs [57, 65]; residual is estimate minus held-out no-pulse sample.

| Method | n | MAE [ADC] | Mean bias [ADC] | RMSE [ADC] |
|---|---:|---:|---:|---:|
| ml_pretrigger_hgbr_calibrated | 1883784 | 15.64 [14.78, 16.74] | -1.89 [-3.37, -0.91] | 36.08 [21.24, 55.48] |
| adaptive_pc_excluding_target | 1883784 | 17.18 [15.41, 20.17] | -6.63 [-9.72, -4.96] | 66.45 [32.68, 97.23] |
| mean4_pre | 1883784 | 24.49 [19.72, 32.31] | 7.89 [2.51, 16.59] | 128.30 [49.90, 197.51] |
| median4_plus_train_offset | 1883784 | 24.85 [19.55, 33.33] | 6.43 [0.86, 15.29] | 130.71 [48.40, 198.32] |
| median4_pre | 1883784 | 24.92 [19.70, 33.82] | 8.06 [2.41, 16.98] | 130.83 [48.24, 196.95] |

Verdict: best proxy MAE is `ml_pretrigger_hgbr_calibrated` at 15.64 ADC. The adaptive method is not consistent with zero bias on this proxy, with mean bias -6.63 ADC and MAE 17.18 ADC. Compared with `median4_pre`, adaptive changes MAE by -7.74 ADC; ML changes MAE by -9.28 ADC.

## Leakage checks

| Check | MAE [ADC] | Interpretation |
|---|---:|---|
| shuffled_training_target | 80.87 | should be no better than simple pedestal baselines |
| intentional_target_feature_oracle | 3.11 | very low error confirms direct target leakage would be obvious and is excluded from the real model |
| real_feature_exclusion |  | real ML features exclude run, eventno, evt, target_adc, and any post-trigger target sample value |

The real ML feature list is recorded in `manifest.json` and excludes run ID, event ID, target ADC, and target-sample waveform value. Because no true forced/random triggers exist, the proxy can still inherit beam-trigger selection bias.

## Outputs

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `quiet_counts_by_run.csv`, `heldout_benchmark.csv`, `heldout_by_run.csv`, `ml_cv_scan.csv`, and `leakage_checks.csv`.

## Follow-up

The high-value next step is not another proxy: locate or acquire true random/forced B-stack pedestal ROOT with a non-beam trigger code or a separate run log. Once present, this same script can rerun with the proxy flag removed and no amplitude-selected quiet cut.
