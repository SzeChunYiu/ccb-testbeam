# Ticket 2411: forced-random pedestal closure for learned baseline estimators

- **Ticket:** 2411
- **Author:** testbeam-laptop-3
- **Date:** 2026-08-16
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `3f71d0b1d84d9778aa0096cd3d24b9cd562e16a6`
- **Config:** `configs/p11_2411_forced_random_target_excluded_pedestal_bakeoff.json`

## 0. Question

The ticket asks whether learned baseline estimators should be adopted once an
independent forced/random or no-pulse B-stack pedestal mirror is available. The
first estimand is direct electronics pedestal truth,

```
epsilon_m = p_hat_m(x_i) - b_i^{forced/random}.
```

The accessible mirror does not contain such DAQ-provenanced non-beam B-stack
records, so the falsifiable fallback is a target-excluded pretrigger closure:

```
y_{i,k} = x_{i,k},  k in {0,1,2,3},
```

with `x_{i,k}` predicted after excluding target sample `k`. The adoption test
is also the counterfactual timing perturbation caused when the predicted value
is used as the pedestal for the selected pulse. This separates beam-triggered
pretrigger closure from true electronics pedestal truth.

## 1. Raw ROOT reproduction

The reproduction gate reruns the selected B-stave pulse count from raw ROOT
files in `/home/billy/ccb-data/data/extracted/sorted-b`. The mounted ROOT layout
stores the waveform as `tree/hrd.sample`; the adapter maps it to the legacy
`HRDv` shape of 8 channels by 18 samples. The seed pedestal is the median of
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

## 2. Forced/random source inventory

The direct forced/random requirement was audited before using the fallback
benchmark. `forced_random_source_inventory.csv` scans all accessible sorted
B-stack ROOT files for filename evidence and trigger-code evidence of non-beam
pedestal records.

| Quantity | Value |
| --- | ---: |
| B-stack ROOT files scanned | 53 |
| Total entries scanned | 1649802 |
| Filename forced/random/pedestal token hits | 0 |
| Files with `TRIGGER` branch | 0 |
| Entries with non-beam trigger code | 0 |

This makes the direct forced/random pedestal estimand unavailable in the current
mirror. The benchmark below is therefore not labelled as no-pulse truth; it is a
run-held-out target-excluded closure and downstream-risk stress test.

## 3. Estimators

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

## 4. Timing-risk propagation

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

## 5. Head-to-head results

| method | family | pedestal_rmse_adc | pedestal_rmse_adc_ci_low | pedestal_rmse_adc_ci_high | pedestal_bias_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_bias_delta_adc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_mean3 | traditional | 734.8356 | 617.4979 | 798.6610 | 0.0000 | 0.0922 | 0.1414 | 0.0007 | -37.9475 |
| traditional_median3 | traditional | 839.6783 | 714.4157 | 909.4735 | -37.9475 | 0.0703 | 0.1258 | 0.0013 | 0.0000 |
| ridge | ml | 476.0672 | 414.8750 | 527.3975 | 1.8951 | 0.5596 | 0.3917 | 0.0050 | -39.8426 |
| one_dimensional_cnn | ml | 425.8654 | 343.0132 | 472.3516 | -24.7838 | 0.3972 | 0.2685 | 0.0092 | -13.1638 |
| target_masked_residual_cnn | new_architecture | 268.1194 | 219.1260 | 311.1645 | 0.1040 | 0.5379 | 0.3444 | 0.0126 | -38.0516 |
| gradient_boosted_trees | ml | 262.7514 | 213.6750 | 307.2867 | -0.3972 | 0.1936 | 0.1851 | 0.0140 | -37.5503 |
| mlp | ml | 366.4136 | 313.8793 | 409.4913 | 0.4859 | 0.3970 | 0.2681 | 0.0198 | -38.4334 |
| traditional_line3 | traditional | 543.5508 | 457.8973 | 600.2091 | -33.8518 | 0.1984 | 0.1883 | 0.0245 | -4.0958 |
| traditional_run_stratified | traditional | 505.7932 | 427.1786 | 562.8500 | -0.5459 | 0.3195 | 0.2784 | 0.0569 | -37.4017 |

Paired run-block deltas in `Pr(|Delta r| > 5 ns)` relative to the best
traditional timing-risk method (`traditional_mean3`):

| method | reference_traditional_method | delta_tail_gt5_fraction | ci_low | ci_high |
| --- | --- | --- | --- | --- |
| traditional_median3 | traditional_mean3 | 0.00062 | 0.00039 | 0.00078 |
| ridge | traditional_mean3 | 0.00433 | 0.00377 | 0.00541 |
| one_dimensional_cnn | traditional_mean3 | 0.00848 | 0.00686 | 0.01011 |
| target_masked_residual_cnn | traditional_mean3 | 0.01190 | 0.01034 | 0.01382 |
| gradient_boosted_trees | traditional_mean3 | 0.01326 | 0.01193 | 0.01464 |
| mlp | traditional_mean3 | 0.01911 | 0.01736 | 0.02071 |
| traditional_line3 | traditional_mean3 | 0.02381 | 0.02226 | 0.02499 |
| traditional_run_stratified | traditional_mean3 | 0.05620 | 0.05373 | 0.05739 |

Winner by the preregistered timing-risk rule: **traditional_mean3**. Best traditional:
**traditional_mean3**.

The strongest ML method by pedestal RMSE is `gradient_boosted_trees`
(`262.75 ADC` RMSE), closely followed by the new `target_masked_residual_cnn`
(`268.12 ADC`). Both are worse on the adoption endpoint: their `Pr(|Delta r| >
5 ns)` values are `0.01396` and `0.01260`, compared with `0.00070` for
`traditional_mean3`. The MLP reached its configured optimization iteration cap
in each fold, so its poor timing-tail ranking should be read as a bounded
implementation result, not as a fully saturated hyperparameter claim.

## 6. Split-by-run diagnostics

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

## 7. Leakage and controls

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

## 8. Systematics and caveats

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

## 9. Finding

`result.json` names `traditional_mean3` as the winner under the timing-risk endpoint.
The core lesson is that pedestal RMSE and downstream timing safety are different
objectives. The report therefore treats methods that improve excluded-sample
RMSE but enlarge `|Delta r|` tails as diagnostic models rather than adopted
pedestal replacements.

## 10. Reproducibility

```bash
.venv/bin/python scripts/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.py --config configs/p11_2411_forced_random_target_excluded_pedestal_bakeoff.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `method_metrics.csv`, `per_run_metrics.csv`,
`method_delta_bootstrap.csv`, `stratified_audit.csv`, `leakage_checks.csv`,
`model_cv_scan.csv`, `forced_random_source_inventory.csv`, sampled held-out
predictions, and figures.
