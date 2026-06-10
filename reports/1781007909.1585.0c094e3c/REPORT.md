# Study report: S16d - forced/random-trigger HRD pedestal event search and closure

- **Ticket:** 1781007909.1585.0c094e3c
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `ceeea92ec3a0608cb2b9ece15211a16b46b2e10c`
- **Config:** `s16d_config.json`

## Question

Can the local DAQ metadata or raw mirrors identify true forced/random-trigger HRD pedestal events, and if not, what does a quiet no-pulse proxy say about S16b pedestal closure?

## Raw ROOT reproduction first

The S00 selected-pulse number was reproduced from raw B-stack `h101/HRDv` before the forced/random search or modeling:

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |

## Forced/random event search

DAQ metadata available in these raw ROOT mirrors is limited to `TRIGGER`, `EVENTNO`, and `EVT` plus the HRD waveform branches. The audit found `110` raw ROOT files, `102` populated files, `0` extracted mirror filenames with forced/random/pedestal-like tokens, and `0` forced/random-tagged ROOT entries (`TRIGGER != 1` or a token-matched ROOT filename).

The current mirror still contains no populated true forced/random pedestal sample: every populated A/B ROOT file has `TRIGGER == 1`; A-stack runs 0000-0003 are empty. The closure study below is therefore a clearly labeled **quiet no-pulse proxy**, not a true forced-trigger validation.

## Proxy dataset

Proxy no-pulse events are B-stack events where all configured B staves have baseline-subtracted max amplitude below `80 ADC` using samples 0-3 as the seed pedestal. This gives `386967` events and `1547868` stave records across configured runs; held-out runs `[57, 65]` contribute `1883784` sample-level targets from samples [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17].

## Methods

Traditional estimators:
- `median4_pre`: median of samples 0-3.
- `mean4_pre`: mean of samples 0-3.
- `median4_plus_train_offset`: median4 plus a train-run median offset by stave and target sample.
- `adaptive_pc_excluding_target`: S16 adaptive positivity correction, with the target sample excluded from the constraint.

ML estimator: `ml_pretrigger_hgbr_calibrated`, a histogram-gradient-boosted regressor using only pre-trigger summaries, stave, and target sample. Splits are by run: held-out runs [57, 65], calibration runs [56, 64], all remaining configured runs for model development. Best CV setting: `{'max_leaf_nodes': 15.0, 'learning_rate': 0.1, 'l2_regularization': 0.1, 'cv_mae_adc': 15.773845167519331, 'cv_mae_std_adc': 0.6421365313206161}`.

## Held-out benchmark

Intervals are run-heldout bootstraps over runs [57, 65]; residual is estimate minus held-out no-pulse sample.

| Method | n | MAE [ADC] | Mean bias [ADC] | RMSE [ADC] |
|---|---:|---:|---:|---:|
| ml_pretrigger_hgbr_calibrated | 1883784 | 15.60 [14.91, 16.76] | -1.69 [-3.43, -0.83] | 32.03 [20.69, 47.53] |
| adaptive_pc_excluding_target | 1883784 | 17.18 [15.49, 20.03] | -6.63 [-9.65, -4.82] | 66.45 [28.37, 95.75] |
| mean4_pre | 1883784 | 24.49 [19.38, 33.71] | 7.89 [2.44, 16.46] | 128.30 [45.17, 194.99] |
| median4_plus_train_offset | 1883784 | 24.87 [19.71, 33.46] | 6.44 [1.04, 15.63] | 130.71 [48.82, 203.24] |
| median4_pre | 1883784 | 24.92 [19.54, 33.95] | 8.06 [2.71, 17.69] | 130.83 [51.39, 202.68] |

Verdict: best proxy MAE is `ml_pretrigger_hgbr_calibrated` at 15.60 ADC. The adaptive method is not consistent with zero bias on this proxy, with mean bias -6.63 ADC and MAE 17.18 ADC. Compared with `median4_pre`, adaptive changes MAE by -7.74 ADC; ML changes MAE by -9.32 ADC.

## Leakage checks

| Check | MAE [ADC] | Interpretation |
|---|---:|---|
| shuffled_training_target | 80.88 | should be no better than simple pedestal baselines |
| intentional_target_feature_oracle | 2.98 | very low error confirms direct target leakage would be obvious and is excluded from the real model |
| real_feature_exclusion |  | real ML features exclude run, eventno, evt, target_adc, and any post-trigger target sample value |

The real ML feature list is recorded in `manifest.json` and excludes run ID, event ID, target ADC, and target-sample waveform value. Because no true forced/random triggers exist, the proxy can still inherit beam-trigger selection bias.

## Outputs

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `mirror_file_audit.csv`, `quiet_counts_by_run.csv`, `heldout_benchmark.csv`, `heldout_by_run.csv`, `ml_cv_scan.csv`, and `leakage_checks.csv`.

## Follow-up

The high-value next step is not another proxy: locate or acquire true random/forced B-stack pedestal ROOT with a non-beam trigger code or a separate run log. Once present, this script can rerun with the proxy flag removed and no amplitude-selected quiet cut.
