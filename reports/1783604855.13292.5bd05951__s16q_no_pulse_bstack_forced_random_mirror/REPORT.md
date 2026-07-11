# S16q: dedicated no-pulse B-stack forced/random ROOT mirror and S16p adoption-rule rerun

- **Ticket:** `1783604855.13292.5bd05951`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-07-11
- **Input:** raw B-stack ROOT under `data/root/root`; checksums in `input_sha256.csv`
- **Config:** `configs/s16q_1783604855_13292_5bd05951_no_pulse_bstack_forced_random_mirror.json`
- **Git commit:** `654a7d167f5b113a0afaf5301fea7a0daf601419`

## 1. Preregistered Question

S16e showed a no-proxy result in which histogram gradient boosting lowered
held-out pedestal MAE relative to `traditional_mean3`, but widened the
per-sample core residual distribution. This ticket asks whether that MAE gain is
operationally usable once width68, timing tails, charge shifts, and support drift
are audited under run-held-out splits.

The adoption rule is lexicographic:

```
arg min_m [ Pr(|Delta r_m| > 5 ns),
            Pr(|Delta r_m| > 0.5 ns),
            width68(p_hat_m - y),
            RMSE(p_hat_m - y) ].
```

Pedestal MAE is retained as a diagnostic, not the deciding endpoint.

## 2. Raw-ROOT Reproduction of the S16e Number

The S16e reference gate was rerun from raw `h101/HRDv` ROOT files before any
new model fitting. The forced/random check also scans trigger codes, filenames,
local archives, and zip-member names.

| quantity | expected | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| S00 selected B-stave pulses | 640737 | 640737 | 0 | True |
| forced/random/non-beam ROOT entries | 0 | 0 | 0 | True |
| forced/random/pedestal archive or filename hits | 0 | 0 | 0 | True |

The reproduced no-proxy reference is:

| method | n | mean_bias_adc | mae_adc | mae_ci_low_adc | mae_ci_high_adc | width68_adc | width68_ci_low_adc | width68_ci_high_adc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ml_hist_gradient_boosting | 5000 | 3.967 | 32.143 | 24.262 | 40.772 | 13.262 | 12.954 | 13.786 |
| traditional_mean3 | 5000 | 0.388 | 35.891 | 22.834 | 48.206 | 10.333 | 9.992 | 11.000 |
| traditional_stave_sample_offset_median3 | 5000 | -1.783 | 37.374 | 27.612 | 50.360 | 11.000 | 10.000 | 11.000 |
| traditional_median3 | 5000 | -1.909 | 37.385 | 25.699 | 48.963 | 11.000 | 10.000 | 11.000 |

Thus the ticket premise is reproduced from raw ROOT: HGB changes MAE by
`-3.748` ADC versus mean3, while changing
width68 by `2.929` ADC. No true
forced/random pedestal ROOT source is present (`0`
non-beam ROOT entries and `0` archive hits).

S16e leakage controls:

| check | value | pass | note |
| --- | --- | --- | --- |
| shuffled_training_targets_mae_minus_real_mae | 138.5627 | True | Shuffled targets must perform materially worse than real training. |
| run_split_mae_minus_row_split_mae | -2.2917 | True | A large row-split advantage would suggest run leakage or duplicate memorization. |
| heldout_feature_duplicate_fraction | 0.0108 | True | Exact feature duplicates across train and held-out runs are rare enough to reject memorization. |
| feature_exclusion | nan | True | ML features exclude run, event number, trigger, filenames, selected-pulse amplitude, and target ADC. |

## 3. Data and Split

The new S16o benchmark uses selected B-stave pulses with

```
A = max_s (x_s - median(x_0,x_1,x_2,x_3)) > 1000 ADC,
```

where the four early samples define the seed pedestal. The exact selected-pulse
gate is:

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | True |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | True |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | True |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | True |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | True |

Runs `[58, 59, 60, 61, 62, 63, 65]` are held out one at a time. Every traditional
cell correction and learned model is fit without the held-out run; bootstrap
intervals use 250 run-block replicates that resample held-out runs as blocks.

## 4. Estimators

For a target pretrigger sample `k`, every method observes the other three
pretrigger samples only. Traditional comparators are

```
mean3_k   = (1/3) sum_{j != k} x_j
median3_k = median{x_j : j != k}
line3_k   = beta0 + beta1 k, fit through {(j, x_j): j != k}.
```

The strong traditional method adds a train-run median residual correction in
target-sample, stave, amplitude, and visible-range cells. Learned regressors
predict `y - line3_k` and add it back to `line3_k`. The ML/NN set is ridge,
gradient-boosted trees, MLP, 1D-CNN, and the new masked residual CNN with an
explicit channel marking the excluded sample.

## 5. Timing and Charge Propagation

For each prediction `p_hat`, the raw waveform is rebaselined by subtracting
`p_hat`, and CFD20 time is recomputed. Relative downstream-pair risk is

```
Delta r_i = (t_hat_{i,a} - t_ref_{i,a}) -
            (t_hat_{i,b} - t_ref_{i,b}),
```

for downstream pairs B4-B6, B4-B8, and B6-B8. Charge shift is the induced
amplitude difference relative to the four-sample median reference.

## 6. Head-to-Head Results

| method | family | pedestal_mae_adc | pedestal_rmse_adc | pedestal_width68_adc | pedestal_width68_adc_ci_low | pedestal_width68_adc_ci_high | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_res68_delta_adc | charge_bias_delta_adc | prediction_outside_target_0p1_99p9_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_mean3 | traditional | 249.2353 | 734.8356 | 18.0000 | 13.4083 | 23.3333 | 0.0922 | 0.1414 | 0.0007 | 8.1667 | -37.9475 | 0.0004 |
| traditional_median3 | traditional | 271.1426 | 839.6783 | 16.0000 | 13.0000 | 20.0000 | 0.0703 | 0.1258 | 0.0013 | 5.5000 | 0.0000 | 0.0007 |
| ridge | ml | 174.0255 | 463.0972 | 85.9132 | 79.7266 | 92.9389 | 0.6184 | 0.6008 | 0.0049 | 83.0764 | -27.8358 | 0.1215 |
| target_masked_residual_cnn | new_architecture | 53.8546 | 244.3380 | 37.4711 | 32.0537 | 43.0908 | 0.4751 | 0.3078 | 0.0132 | 41.8433 | -44.9821 | 0.0786 |
| one_dimensional_cnn | ml | 87.7278 | 338.4127 | 30.9160 | 25.8626 | 35.2107 | 0.4200 | 0.2805 | 0.0180 | 32.0933 | -16.6277 | 0.0503 |
| gradient_boosted_trees | ml | 51.1376 | 229.3215 | 21.9449 | 19.1791 | 25.0135 | 0.2440 | 0.2110 | 0.0211 | 20.8814 | -37.5808 | 0.0121 |
| traditional_line3 | traditional | 168.5621 | 543.5508 | 15.5714 | 12.0000 | 20.1107 | 0.1984 | 0.1883 | 0.0245 | 15.3571 | -4.0958 | 0.0493 |
| mlp | ml | 94.5690 | 323.1197 | 37.5081 | 30.7594 | 43.1495 | 0.5189 | 0.3215 | 0.0294 | 39.7356 | -40.8466 | 0.0494 |
| traditional_run_stratified | traditional | 145.8075 | 510.7481 | 17.0476 | 13.9446 | 21.8435 | 0.2390 | 0.2345 | 0.0372 | 16.3690 | -31.2731 | 0.0376 |

Winner by the preregistered adoption rule: **traditional_mean3**. Best traditional:
**traditional_mean3**.

Paired run-block deltas versus the best traditional timing-risk method:

| method | reference_traditional_method | delta_tail_gt5_fraction | delta_tail_gt5_ci_low | delta_tail_gt5_ci_high | delta_pedestal_width68_adc | delta_pedestal_width68_ci_low | delta_pedestal_width68_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_median3 | traditional_mean3 | 0.00062 | 0.00039 | 0.00078 | -2.00000 | -4.59167 | 0.00000 |
| ridge | traditional_mean3 | 0.00415 | 0.00332 | 0.00532 | 67.91316 | 64.64001 | 71.75507 |
| target_masked_residual_cnn | traditional_mean3 | 0.01251 | 0.00964 | 0.01513 | 19.47112 | 14.65331 | 22.53682 |
| one_dimensional_cnn | traditional_mean3 | 0.01732 | 0.01453 | 0.01996 | 12.91599 | 8.47301 | 14.52925 |
| gradient_boosted_trees | traditional_mean3 | 0.02039 | 0.01812 | 0.02253 | 3.94488 | 0.48566 | 5.88501 |
| traditional_line3 | traditional_mean3 | 0.02381 | 0.02208 | 0.02480 | -2.42857 | -3.64524 | -1.66667 |
| mlp | traditional_mean3 | 0.02867 | 0.02141 | 0.03604 | 19.50811 | 15.46117 | 22.38342 |
| traditional_run_stratified | traditional_mean3 | 0.03645 | 0.03429 | 0.03896 | -0.95238 | -2.45238 | -0.00000 |

## 7. Split-by-Run Diagnostics

| run | method | pedestal_rmse_adc | pedestal_width68_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_bias_delta_adc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | traditional_mean3 | 275.3946 | 10.0000 | 0.0707 | 0.1211 | 0.0050 | -5.0843 |
| 58 | gradient_boosted_trees | 86.5217 | 15.1785 | 0.2099 | 0.1790 | 0.0199 | -10.1094 |
| 59 | traditional_mean3 | 818.4728 | 31.6667 | 0.0957 | 0.1415 | 0.0007 | -47.1848 |
| 59 | gradient_boosted_trees | 307.2719 | 26.0143 | 0.2620 | 0.2148 | 0.0249 | -41.0852 |
| 60 | traditional_mean3 | 812.5400 | 24.0000 | 0.1023 | 0.1489 | 0.0007 | -49.7751 |
| 60 | gradient_boosted_trees | 226.8561 | 23.4526 | 0.2516 | 0.2243 | 0.0212 | -51.9985 |
| 61 | traditional_mean3 | 753.1099 | 22.0000 | 0.0862 | 0.1360 | 0.0008 | -46.5205 |
| 61 | gradient_boosted_trees | 184.7001 | 21.8209 | 0.2310 | 0.2049 | 0.0187 | -43.2097 |
| 62 | traditional_mean3 | 761.7863 | 23.6667 | 0.0906 | 0.1447 | 0.0006 | -44.0506 |
| 62 | gradient_boosted_trees | 207.0071 | 26.6347 | 0.2412 | 0.2085 | 0.0216 | -41.8367 |
| 63 | traditional_mean3 | 790.2005 | 18.0000 | 0.0980 | 0.1441 | 0.0003 | -37.2820 |
| 63 | gradient_boosted_trees | 269.4470 | 21.1038 | 0.2552 | 0.2147 | 0.0210 | -38.5158 |
| 65 | traditional_mean3 | 739.4983 | 14.0000 | 0.0755 | 0.1018 | 0.0000 | -29.2067 |
| 65 | gradient_boosted_trees | 236.1585 | 20.7452 | 0.2023 | 0.1526 | 0.0063 | -32.5933 |

## 8. Ablations, Sentinels, and Support

The feature-group table records the full target-excluded ML/NN methods. The
sentinel rows check that the ranking is not reproduced by shuffled predictions
or run-target medians alone.

| method | feature_group | pedestal_rmse_adc | pedestal_width68_adc | timing_tail_gt5_fraction |
| --- | --- | --- | --- | --- |
| ridge | full_target_excluded | 463.0972 | 85.9132 | 0.0049 |
| gradient_boosted_trees | full_target_excluded | 229.3215 | 21.9449 | 0.0211 |
| mlp | full_target_excluded | 323.1197 | 37.5081 | 0.0294 |
| one_dimensional_cnn | full_target_excluded | 338.4127 | 30.9160 | 0.0180 |
| target_masked_residual_cnn | full_target_excluded | 244.3380 | 37.4711 | 0.0132 |

| sentinel | pedestal_mae_adc | pedestal_rmse_adc | pedestal_width68_adc | status |
| --- | --- | --- | --- | --- |
| shuffled_gradient_boosted_predictions | 553.1888 | 1262.3089 | 269.8005 | pass |
| run_target_median_sentinel | 322.8728 | 928.5475 | 154.0000 | pass |

Support drift is summarized in the head-to-head table as the fraction of
predictions outside the held-out target 0.1-99.9 percentile envelope.

## 9. Stratified Systematics

The full `stratified_tradeoff.csv` audits target sample, stave, amplitude bin,
peak-phase bin, pretrigger spectrum, adaptive-lowering state, anomaly taxon, and
run family. The first rows are:

| stratum | value | method | n | pedestal_mae_adc | pedestal_width68_adc | pedestal_rmse_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_sample | 0 | gradient_boosted_trees | 125096 | 44.8039 | 16.4875 | 212.6229 | nan | nan | nan |
| target_sample | 1 | gradient_boosted_trees | 125096 | 32.7109 | 9.7564 | 149.7624 | nan | nan | nan |
| target_sample | 2 | gradient_boosted_trees | 125096 | 42.2217 | 11.1439 | 208.6381 | nan | nan | nan |
| target_sample | 3 | gradient_boosted_trees | 125096 | 84.8138 | 21.2103 | 314.9384 | nan | nan | nan |
| target_sample | 0 | traditional_mean3 | 125096 | 287.8482 | 22.3333 | 818.9813 | nan | nan | nan |
| target_sample | 1 | traditional_mean3 | 125096 | 185.2503 | 13.3333 | 521.3154 | nan | nan | nan |
| target_sample | 2 | traditional_mean3 | 125096 | 140.7009 | 13.0000 | 480.7974 | nan | nan | nan |
| target_sample | 3 | traditional_mean3 | 125096 | 383.1415 | 23.6667 | 993.1099 | nan | nan | nan |
| stave | B2 | gradient_boosted_trees | 352852 | 51.2352 | 20.0091 | 257.7883 | nan | nan | nan |
| stave | B4 | gradient_boosted_trees | 84916 | 55.3029 | 29.5555 | 132.4219 | nan | nan | nan |
| stave | B6 | gradient_boosted_trees | 44592 | 42.6101 | 25.6137 | 93.3784 | nan | nan | nan |
| stave | B8 | gradient_boosted_trees | 18024 | 50.6989 | 25.0583 | 234.1024 | nan | nan | nan |
| stave | B2 | traditional_mean3 | 352852 | 236.3340 | 16.0000 | 747.3096 | nan | nan | nan |
| stave | B4 | traditional_mean3 | 84916 | 286.5774 | 30.6667 | 711.1571 | nan | nan | nan |
| stave | B6 | traditional_mean3 | 44592 | 254.3899 | 24.3333 | 646.8573 | nan | nan | nan |
| stave | B8 | traditional_mean3 | 18024 | 313.1187 | 23.6667 | 800.0583 | nan | nan | nan |
| amplitude_bin | 1000-1500 | gradient_boosted_trees | 46688 | 74.3944 | 35.1138 | 211.2402 | nan | nan | nan |
| amplitude_bin | 1500-2500 | gradient_boosted_trees | 99436 | 54.2801 | 25.7436 | 196.3403 | nan | nan | nan |
| amplitude_bin | 2500-4000 | gradient_boosted_trees | 209088 | 40.4291 | 19.9693 | 139.6875 | nan | nan | nan |
| amplitude_bin | 4000-7000 | gradient_boosted_trees | 123432 | 48.1394 | 19.8258 | 208.8114 | nan | nan | nan |
| amplitude_bin | >=7000 | gradient_boosted_trees | 21740 | 106.8319 | 22.4786 | 709.2523 | nan | nan | nan |
| amplitude_bin | 1000-1500 | traditional_mean3 | 46688 | 442.5223 | 129.3333 | 932.3832 | nan | nan | nan |
| amplitude_bin | 1500-2500 | traditional_mean3 | 99436 | 352.3690 | 28.0000 | 848.7260 | nan | nan | nan |
| amplitude_bin | 2500-4000 | traditional_mean3 | 209088 | 188.2706 | 16.0000 | 608.7026 | nan | nan | nan |
| amplitude_bin | 4000-7000 | traditional_mean3 | 123432 | 198.5072 | 14.6667 | 708.5105 | nan | nan | nan |
| amplitude_bin | >=7000 | traditional_mean3 | 21740 | 236.7723 | 16.3333 | 923.7674 | nan | nan | nan |
| peak_phase_bin | 5-7 | gradient_boosted_trees | 261320 | 46.8257 | 22.0410 | 164.4172 | nan | nan | nan |
| peak_phase_bin | 8-11 | gradient_boosted_trees | 170128 | 16.5685 | 13.8745 | 62.1007 | nan | nan | nan |

The raw HRDv table does not contain a stable `q_template` label, so q-template
systematics are represented here by pretrigger-spectrum and anomaly-taxonomy
bins rather than by an unavailable external label.

## 10. Leakage and Caveats

| check | status | detail |
| --- | --- | --- |
| leave_one_run_out_declared | pass | heldout runs [58, 59, 60, 61, 62, 63, 65]; every fold trains with its held-out run removed |
| target_sample_excluded_from_features | pass | feature matrix contains only the other three pretrigger samples; target_adc is never in TAB_FEATURES or NN sequence |
| run_and_event_id_excluded_from_features | pass | run, event_id, eventno, evt, residuals, and target labels are not model inputs |
| train_test_run_sets_disjoint | pass | for each fold, model training uses analysis_runs minus the current held-out run; the scored rows are only that held-out run |
| finite_predictions | pass | 4503456 / 4503456 finite predictions |

- **No forced/random truth:** all learned methods remain beam-event
  target-excluded closure predictors; they are not direct no-pulse pedestal
  measurements.
- **MAE-width conflict:** a model can lower average absolute error by tracking
  contaminated early samples while widening the core residual or downstream
  timing-shift tails.
- **Run uncertainty:** run-block CIs are the correct uncertainty scale for this
  ticket; row-wise intervals would overstate precision.
- **Model convergence:** the MLP reached the configured scikit-learn iteration
  cap in verification. It remains a required benchmark family, but the safety
  conclusion does not rely on the MLP row.
- **Consumer risk:** timing, charge, pile-up, PID, and energy consumers should
  use the adoption winner or treat lower-MAE ML predictions as diagnostics until
  true random-trigger pedestal data exist.

## 11. Finding

`result.json` names `traditional_mean3` as the winner. The S16e MAE advantage of HGB is
real under the reproduced no-proxy benchmark, but the broader width/timing
audit does not justify adopting MAE alone as the pedestal replacement criterion.

## 12. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16o_1781043990_570_2c97138c_no_proxy_pedestal_width_tradeoff.py --config configs/s16q_1783604855_13292_5bd05951_no_pulse_bstack_forced_random_mirror.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`,
`reproduction_match_table.csv`, `s16e_reference_method_summary.csv`,
`method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`,
`stratified_tradeoff.csv`, `ablation_summary.csv`, `sentinel_summary.csv`,
`leakage_checks.csv`, `model_cv_scan.csv`, and figures. Large `.csv.gz`
prediction/timing/charge row dumps are regenerated by the command but omitted
from the PR because the repository ignores `*.gz`.
