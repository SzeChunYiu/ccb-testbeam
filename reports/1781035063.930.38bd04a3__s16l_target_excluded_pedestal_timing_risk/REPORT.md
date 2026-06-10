# S16l: target-excluded pedestal estimator timing-risk audit

- **Ticket:** 1781035063.930.38bd04a3
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `3bba7954bcce54603fedc00615d93a5ea8084c41`
- **Config:** `configs/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.json`

## 0. Question

The ticket asks why a target-excluded ML pedestal estimator can reduce pedestal
RMSE while producing larger downstream timing-shift tails than a traditional
mean3 estimator. The operational test is therefore not only

```
y_{i,k} = x_{i,k},  k in {0,1,2,3},
```

with `x_{i,k}` predicted after excluding target sample `k`. It is also the
counterfactual timing perturbation caused when the predicted value is used as
the pedestal for the selected pulse.

## 1. Raw ROOT reproduction

The reproduction gate reruns the selected B-stave pulse count from raw
`h101/HRDv` ROOT files in `data/root/root`. The seed pedestal is the median of
samples 0-3 and the selection is `A > 1000 ADC`.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | True |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | True |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | True |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | True |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | True |

The gate passes exactly, so the benchmark population is anchored to the same
raw selected-pulse definition used by the S16 family.

## 2. Estimators

For each selected pulse and each target pretrigger sample `k`, all estimators
see only the other three pretrigger samples plus target-excluded waveform
summaries. The traditional estimators are

```
mean3_k   = mean({x_j : j != k})
median3_k = median({x_j : j != k})
line3_k   = least-squares extrapolation through the three visible samples.
```

The strong traditional comparator, `traditional_run_stratified`, adds a
train-run median residual correction to `line3_k` in cells of target sample,
stave, provisional amplitude, and visible-pretrigger range. No held-out run is
used for those medians.

Learned regressors predict the residual `y - line3_k`. The benchmark includes
ridge, histogram gradient-boosted trees, MLP, a one-dimensional CNN over the
target-masked waveform, and a new `target_masked_residual_cnn` with an explicit
mask channel for the excluded sample.

## 3. Timing-risk propagation

For each held-out run, method, and target sample, the predicted pedestal
`p_hat_{i,k}` is subtracted from the raw waveform and CFD20 time is recomputed.
The reference time uses the four-sample median pedestal. For downstream pair
`a,b`, the induced shift is

```
Delta r_i = (t_hat_{i,a} - t_ref_{i,a}) - (t_hat_{i,b} - t_ref_{i,b}).
```

The time-of-flight term cancels in this difference, but the pair identities are
kept to audit S02/S03-like downstream residual risk. Bootstrap intervals resample
held-out runs with replacement.

## 4. Head-to-head results

| method | family | pedestal_rmse_adc | pedestal_rmse_adc_ci_low | pedestal_rmse_adc_ci_high | pedestal_bias_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_bias_delta_adc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_mean3 | traditional | 734.8356 | 618.6427 | 798.9858 | -0.0000 | 0.0922 | 0.1414 | 0.0007 | -37.9475 |
| traditional_median3 | traditional | 839.6783 | 706.2851 | 908.3776 | -37.9475 | 0.0703 | 0.1258 | 0.0013 | 0.0000 |
| ridge | ml | 465.3697 | 382.2484 | 511.8805 | -9.7985 | 0.6521 | 0.6564 | 0.0053 | -28.1491 |
| target_masked_residual_cnn | new_architecture | 234.8554 | 181.4450 | 285.4470 | 3.7990 | 0.4925 | 0.3175 | 0.0115 | -41.7465 |
| gradient_boosted_trees | ml | 219.2408 | 182.2232 | 252.7612 | -0.9620 | 0.2453 | 0.2110 | 0.0205 | -36.9856 |
| one_dimensional_cnn | ml | 311.9920 | 249.3848 | 361.3381 | -6.5637 | 0.4538 | 0.2979 | 0.0213 | -31.3838 |
| traditional_line3 | traditional | 543.5508 | 454.0788 | 599.5257 | -33.8518 | 0.1984 | 0.1883 | 0.0245 | -4.0958 |
| mlp | ml | 307.7480 | 259.4720 | 345.3102 | -10.5436 | 0.4658 | 0.2884 | 0.0346 | -27.4040 |
| traditional_run_stratified | traditional | 511.5687 | 431.1550 | 575.6264 | -8.2113 | 0.2378 | 0.2358 | 0.0400 | -29.7363 |

Paired run-block deltas in `Pr(|Delta r| > 5 ns)` relative to the best
traditional timing-risk method (`traditional_mean3`):

| method | reference_traditional_method | delta_tail_gt5_fraction | ci_low | ci_high |
| --- | --- | --- | --- | --- |
| traditional_median3 | traditional_mean3 | 0.00062 | 0.00044 | 0.00077 |
| ridge | traditional_mean3 | 0.00455 | 0.00361 | 0.00551 |
| target_masked_residual_cnn | traditional_mean3 | 0.01083 | 0.00887 | 0.01306 |
| gradient_boosted_trees | traditional_mean3 | 0.01983 | 0.01857 | 0.02051 |
| one_dimensional_cnn | traditional_mean3 | 0.02059 | 0.01627 | 0.02387 |
| traditional_line3 | traditional_mean3 | 0.02381 | 0.02208 | 0.02512 |
| mlp | traditional_mean3 | 0.03388 | 0.02852 | 0.03942 |
| traditional_run_stratified | traditional_mean3 | 0.03934 | 0.03682 | 0.04083 |

Winner by the preregistered timing-risk rule: **traditional_mean3**. Best traditional:
**traditional_mean3**.

## 5. Split-by-run diagnostics

| run | method | pedestal_rmse_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_bias_delta_adc |
| --- | --- | --- | --- | --- | --- | --- |
| 58 | traditional_mean3 | 275.3946 | 0.0707 | 0.1211 | 0.0050 | -5.0843 |
| 59 | traditional_mean3 | 818.4728 | 0.0957 | 0.1415 | 0.0007 | -47.1848 |
| 60 | traditional_mean3 | 812.5400 | 0.1023 | 0.1489 | 0.0007 | -49.7751 |
| 61 | traditional_mean3 | 753.1099 | 0.0862 | 0.1360 | 0.0008 | -46.5205 |
| 62 | traditional_mean3 | 761.7863 | 0.0906 | 0.1447 | 0.0006 | -44.0506 |
| 63 | traditional_mean3 | 790.2005 | 0.0980 | 0.1441 | 0.0003 | -37.2820 |
| 65 | traditional_mean3 | 739.4983 | 0.0755 | 0.1018 | 0.0000 | -29.2067 |

The full stratum table is in `stratified_audit.csv`. It audits pedestal error by
target sample, stave, amplitude bin, pretrigger spectrum bin, adaptive-lowering
state, and anomaly taxon; timing shifts are additionally audited by target
sample and downstream pair.

## 6. Leakage and controls

| check | status | detail |
| --- | --- | --- |
| leave_one_run_out_declared | pass | heldout runs [58, 59, 60, 61, 62, 63, 65]; every fold trains with its held-out run removed |
| target_sample_excluded_from_features | pass | feature matrix contains only the other three pretrigger samples; target_adc is never in TAB_FEATURES or NN sequence |
| run_and_event_id_excluded_from_features | pass | run, event_id, eventno, evt, residuals, and target labels are not model inputs |
| train_test_run_sets_disjoint | pass | for each fold, model training uses analysis_runs minus the current held-out run; the scored rows are only that held-out run |
| finite_predictions | pass | 4503456 / 4503456 finite predictions |

The learned methods are closure predictors, not forced/random electronics
truth. Post-trigger waveform summaries can legitimately predict a contaminated
early sample, but low RMSE on that target can preserve the contamination rather
than remove it. That is why the timing-shift endpoint is the adoption gate.

## 7. Systematics and caveats

- **No no-pulse truth:** this is a leave-one-pretrigger-sample closure test on
  beam-triggered events, not a direct forced/random pedestal measurement.
- **Target semantics:** the target sample can include early pulse activity. A
  model that predicts it accurately may also encode the contamination that a
  pedestal correction should avoid.
- **Timing counterfactual:** substituting one predicted sample as a pedestal is
  deliberately harsh. It tests downstream risk from using target-excluded
  imputation as a baseline, not the best possible timing algorithm.
- **Run uncertainty:** CIs bootstrap held-out runs. Within-run event
  correlations and duplicated pair rows mean row-wise CIs would be too narrow.
- **Model selection:** several model families were tried, so the result is a
  benchmark ranking with bootstrap deltas, not a single-family discovery
  p-value.

## 8. Finding

`result.json` names `traditional_mean3` as the winner under the timing-risk endpoint.
The core lesson is that pedestal RMSE and downstream timing safety are different
objectives. The report therefore treats methods that improve excluded-sample
RMSE but enlarge `|Delta r|` tails as diagnostic models rather than adopted
pedestal replacements.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.py --config configs/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `method_metrics.csv`, `per_run_metrics.csv`,
`method_delta_bootstrap.csv`, `stratified_audit.csv`, `leakage_checks.csv`,
`model_cv_scan.csv`, sampled held-out predictions, and figures.
