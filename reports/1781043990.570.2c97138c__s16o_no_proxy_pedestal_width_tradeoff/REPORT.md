# S16o: no-proxy pedestal width tradeoff audit

- **Ticket:** `1781043990.570.2c97138c`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT under `data/root/root`; checksums in `input_sha256.csv`
- **Config:** `configs/s16o_1781043990_570_2c97138c_no_proxy_pedestal_width_tradeoff.json`
- **Git commit:** `45f3ad1bc342cee4f817324f8f908b0ea4f952c3`

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
intervals resample held-out runs as blocks.

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
| traditional_mean3 | traditional | 249.2353 | 734.8356 | 18.0000 | 13.3333 | 25.2583 | 0.0922 | 0.1414 | 0.0007 | 8.1667 | -37.9475 | 0.0004 |
| traditional_median3 | traditional | 271.1426 | 839.6783 | 16.0000 | 14.0000 | 20.0000 | 0.0703 | 0.1258 | 0.0013 | 5.5000 | 0.0000 | 0.0007 |
| ridge | ml | 175.2941 | 466.2359 | 85.9671 | 79.5649 | 93.1327 | 0.6163 | 0.6282 | 0.0046 | 82.3746 | -26.3000 | 0.1223 |
| target_masked_residual_cnn | new_architecture | 50.8670 | 241.5089 | 34.4948 | 32.7387 | 35.8626 | 0.4658 | 0.2983 | 0.0107 | 38.5993 | -37.5972 | 0.0793 |
| one_dimensional_cnn | ml | 88.4837 | 343.7406 | 30.8878 | 24.9958 | 35.8520 | 0.4499 | 0.2939 | 0.0194 | 31.9918 | -20.4265 | 0.0444 |
| gradient_boosted_trees | ml | 49.1575 | 216.2528 | 20.1287 | 16.9644 | 22.4410 | 0.2364 | 0.2062 | 0.0204 | 19.4726 | -37.4617 | 0.0114 |
| traditional_line3 | traditional | 168.5621 | 543.5508 | 15.5714 | 12.0000 | 20.5179 | 0.1984 | 0.1883 | 0.0245 | 15.3571 | -4.0958 | 0.0493 |
| mlp | ml | 90.1586 | 321.9763 | 31.3514 | 24.6118 | 41.4313 | 0.4534 | 0.2785 | 0.0372 | 32.6457 | -33.0826 | 0.0466 |
| traditional_run_stratified | traditional | 146.3407 | 511.8363 | 17.2381 | 13.8179 | 21.6190 | 0.2406 | 0.2353 | 0.0383 | 16.5000 | -28.3077 | 0.0385 |

Winner by the preregistered adoption rule: **traditional_mean3**. Best traditional:
**traditional_mean3**.

Paired run-block deltas versus the best traditional timing-risk method:

| method | reference_traditional_method | delta_tail_gt5_fraction | delta_tail_gt5_ci_low | delta_tail_gt5_ci_high | delta_pedestal_width68_adc | delta_pedestal_width68_ci_low | delta_pedestal_width68_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_median3 | traditional_mean3 | 0.00062 | 0.00040 | 0.00077 | -2.00000 | -5.59167 | 0.00000 |
| ridge | traditional_mean3 | 0.00391 | 0.00325 | 0.00492 | 67.96706 | 65.17024 | 69.70900 |
| target_masked_residual_cnn | traditional_mean3 | 0.01002 | 0.00895 | 0.01132 | 16.49480 | 11.43013 | 19.54969 |
| one_dimensional_cnn | traditional_mean3 | 0.01865 | 0.01636 | 0.02073 | 12.88777 | 9.88808 | 15.37594 |
| gradient_boosted_trees | traditional_mean3 | 0.01966 | 0.01815 | 0.02085 | 2.12872 | -1.80180 | 3.90221 |
| traditional_line3 | traditional_mean3 | 0.02381 | 0.02235 | 0.02498 | -2.42857 | -3.66667 | -1.66667 |
| mlp | traditional_mean3 | 0.03651 | 0.03002 | 0.04135 | 13.35144 | 3.73875 | 21.56586 |
| traditional_run_stratified | traditional_mean3 | 0.03757 | 0.03485 | 0.03964 | -0.76190 | -2.44940 | 0.08452 |

## 7. Split-by-Run Diagnostics

| run | method | pedestal_rmse_adc | pedestal_width68_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_bias_delta_adc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | traditional_mean3 | 275.3946 | 10.0000 | 0.0707 | 0.1211 | 0.0050 | -5.0843 |
| 58 | gradient_boosted_trees | 86.4014 | 13.9965 | 0.1938 | 0.1838 | 0.0228 | -9.3773 |
| 59 | traditional_mean3 | 818.4728 | 31.6667 | 0.0957 | 0.1415 | 0.0007 | -47.1848 |
| 59 | gradient_boosted_trees | 287.7924 | 23.7878 | 0.2508 | 0.2056 | 0.0221 | -42.3068 |
| 60 | traditional_mean3 | 812.5400 | 24.0000 | 0.1023 | 0.1489 | 0.0007 | -49.7751 |
| 60 | gradient_boosted_trees | 201.5600 | 23.2600 | 0.2503 | 0.2249 | 0.0209 | -51.1929 |
| 61 | traditional_mean3 | 753.1099 | 22.0000 | 0.0862 | 0.1360 | 0.0008 | -46.5205 |
| 61 | gradient_boosted_trees | 202.6630 | 21.4917 | 0.2232 | 0.1944 | 0.0183 | -46.3291 |
| 62 | traditional_mean3 | 761.7863 | 23.6667 | 0.0906 | 0.1447 | 0.0006 | -44.0506 |
| 62 | gradient_boosted_trees | 190.9849 | 22.2525 | 0.2322 | 0.2077 | 0.0218 | -41.5230 |
| 63 | traditional_mean3 | 790.2005 | 18.0000 | 0.0980 | 0.1441 | 0.0003 | -37.2820 |
| 63 | gradient_boosted_trees | 258.4733 | 20.2015 | 0.2430 | 0.2082 | 0.0193 | -36.1273 |
| 65 | traditional_mean3 | 739.4983 | 14.0000 | 0.0755 | 0.1018 | 0.0000 | -29.2067 |
| 65 | gradient_boosted_trees | 201.6504 | 17.2258 | 0.2036 | 0.1610 | 0.0107 | -30.8120 |

## 8. Ablations, Sentinels, and Support

The feature-group table records the full target-excluded ML/NN methods. The
sentinel rows check that the ranking is not reproduced by shuffled predictions
or run-target medians alone.

| method | feature_group | pedestal_rmse_adc | pedestal_width68_adc | timing_tail_gt5_fraction |
| --- | --- | --- | --- | --- |
| ridge | full_target_excluded | 466.2359 | 85.9671 | 0.0046 |
| gradient_boosted_trees | full_target_excluded | 216.2528 | 20.1287 | 0.0204 |
| mlp | full_target_excluded | 321.9763 | 31.3514 | 0.0372 |
| one_dimensional_cnn | full_target_excluded | 343.7406 | 30.8878 | 0.0194 |
| target_masked_residual_cnn | full_target_excluded | 241.5089 | 34.4948 | 0.0107 |

| sentinel | pedestal_mae_adc | pedestal_rmse_adc | pedestal_width68_adc | status |
| --- | --- | --- | --- | --- |
| shuffled_gradient_boosted_predictions | 553.1243 | 1262.8593 | 269.1624 | pass |
| run_target_median_sentinel | 322.8728 | 928.5475 | 154.0000 | pass |

Support drift is summarized in the head-to-head table as the fraction of
predictions outside the held-out target 0.1-99.9 percentile envelope.

## 9. Stratified Systematics

The full `stratified_tradeoff.csv` audits target sample, stave, amplitude bin,
peak-phase bin, pretrigger spectrum, adaptive-lowering state, anomaly taxon, and
run family. The first rows are:

| stratum | value | method | n | pedestal_mae_adc | pedestal_width68_adc | pedestal_rmse_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_sample | 0 | gradient_boosted_trees | 125096 | 43.5076 | 16.4905 | 206.6692 | nan | nan | nan |
| target_sample | 1 | gradient_boosted_trees | 125096 | 30.8398 | 9.6040 | 146.6781 | nan | nan | nan |
| target_sample | 2 | gradient_boosted_trees | 125096 | 40.7219 | 10.8924 | 196.7839 | nan | nan | nan |
| target_sample | 3 | gradient_boosted_trees | 125096 | 81.5605 | 21.1491 | 290.0182 | nan | nan | nan |
| target_sample | 0 | traditional_mean3 | 125096 | 287.8482 | 22.3333 | 818.9813 | nan | nan | nan |
| target_sample | 1 | traditional_mean3 | 125096 | 185.2503 | 13.3333 | 521.3154 | nan | nan | nan |
| target_sample | 2 | traditional_mean3 | 125096 | 140.7009 | 13.0000 | 480.7974 | nan | nan | nan |
| target_sample | 3 | traditional_mean3 | 125096 | 383.1415 | 23.6667 | 993.1099 | nan | nan | nan |
| stave | B2 | gradient_boosted_trees | 352852 | 49.6455 | 18.5071 | 242.1865 | nan | nan | nan |
| stave | B4 | gradient_boosted_trees | 84916 | 51.4429 | 25.9402 | 124.3810 | nan | nan | nan |
| stave | B6 | gradient_boosted_trees | 44592 | 40.9004 | 23.5492 | 91.6080 | nan | nan | nan |
| stave | B8 | gradient_boosted_trees | 18024 | 49.2648 | 22.8896 | 237.4676 | nan | nan | nan |
| stave | B2 | traditional_mean3 | 352852 | 236.3340 | 16.0000 | 747.3096 | nan | nan | nan |
| stave | B4 | traditional_mean3 | 84916 | 286.5774 | 30.6667 | 711.1571 | nan | nan | nan |
| stave | B6 | traditional_mean3 | 44592 | 254.3899 | 24.3333 | 646.8573 | nan | nan | nan |
| stave | B8 | traditional_mean3 | 18024 | 313.1187 | 23.6667 | 800.0583 | nan | nan | nan |
| amplitude_bin | 1000-1500 | gradient_boosted_trees | 46688 | 69.7521 | 32.1014 | 194.0796 | nan | nan | nan |
| amplitude_bin | 1500-2500 | gradient_boosted_trees | 99436 | 51.9592 | 23.1993 | 186.9333 | nan | nan | nan |
| amplitude_bin | 2500-4000 | gradient_boosted_trees | 209088 | 39.1382 | 18.3489 | 133.3714 | nan | nan | nan |
| amplitude_bin | 4000-7000 | gradient_boosted_trees | 123432 | 46.4331 | 18.4407 | 191.6353 | nan | nan | nan |
| amplitude_bin | >=7000 | gradient_boosted_trees | 21740 | 103.9443 | 21.0386 | 675.3353 | nan | nan | nan |
| amplitude_bin | 1000-1500 | traditional_mean3 | 46688 | 442.5223 | 129.3333 | 932.3832 | nan | nan | nan |
| amplitude_bin | 1500-2500 | traditional_mean3 | 99436 | 352.3690 | 28.0000 | 848.7260 | nan | nan | nan |
| amplitude_bin | 2500-4000 | traditional_mean3 | 209088 | 188.2706 | 16.0000 | 608.7026 | nan | nan | nan |
| amplitude_bin | 4000-7000 | traditional_mean3 | 123432 | 198.5072 | 14.6667 | 708.5105 | nan | nan | nan |
| amplitude_bin | >=7000 | traditional_mean3 | 21740 | 236.7723 | 16.3333 | 923.7674 | nan | nan | nan |
| peak_phase_bin | 5-7 | gradient_boosted_trees | 261320 | 44.7431 | 20.4058 | 155.0598 | nan | nan | nan |
| peak_phase_bin | 8-11 | gradient_boosted_trees | 170128 | 15.5801 | 13.0661 | 55.0814 | nan | nan | nan |

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
/home/billy/anaconda3/bin/python scripts/s16o_1781043990_570_2c97138c_no_proxy_pedestal_width_tradeoff.py --config configs/s16o_1781043990_570_2c97138c_no_proxy_pedestal_width_tradeoff.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`,
`reproduction_match_table.csv`, `s16e_reference_method_summary.csv`,
`method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`,
`stratified_tradeoff.csv`, `ablation_summary.csv`, `sentinel_summary.csv`,
`leakage_checks.csv`, `model_cv_scan.csv`, and figures. Large `.csv.gz`
prediction/timing/charge row dumps are regenerated by the command but omitted
from the PR because the repository ignores `*.gz`.
