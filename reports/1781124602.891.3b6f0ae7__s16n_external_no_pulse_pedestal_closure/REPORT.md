# S16n: external no-pulse pedestal closure for pseudo-pedestal risk atoms

- **Ticket:** 1781124602.891.3b6f0ae7
- **Author:** testbeam-laptop-3
- **Date:** 2026-07-09
- **Input checksums:** `input_sha256.csv`
- **Git commit at benchmark start:** `085a8f6b4da3e43013c86e5f0b7cfe203fe41ab5`
- **Config:** `configs/s16n_1781124602_891_3b6f0ae7_external_no_pulse_pedestal_closure.json`

## 0. Question

S16n asks whether external no-pulse, forced, or random acquisition records can
validate the high-risk pseudo-pedestal atoms seen in the S16m/S16l family with
true electronics-pedestal labels. The local mirror contains the selected raw
beam-triggered B-stack ROOT files, but no path advertises a forced/random/no-
pulse/pedestal acquisition file. The operational test is therefore a two-stage
closure:

1. audit the visible mirror for a direct external pedestal source; and
2. when none is visible, run the target-excluded pretrigger benchmark as a
   diagnostic of pseudo-pedestal risk, not as an adopted correction.

For the diagnostic stage, the target equation for each selected pulse is

```
y_{i,k} = x_{i,k},  k in {0,1,2,3},
```

with `x_{i,k}` predicted after excluding target sample `k`. The adoption gate is
not only excluded-sample RMSE; it is also the counterfactual timing perturbation
caused when the predicted value is used as the pedestal for the selected pulse.

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

## 1.1. External no-pulse source audit

The current mirrored data tree contains 110 ROOT files under `data/root/root`.
A filename audit over the full `data` tree for `forced`, `random`, `nopulse`,
`no_pulse`, `pedestal`, and `ped` returns zero matches; the audit is recorded in
`external_source_audit.csv`. Consequently, no direct electronics-pedestal labels
are available in this checkout. S16n cannot validate pseudo-pedestal atoms
against a true forced/random/no-pulse target yet. The rest of this report is a
run-held-out closure benchmark that quantifies whether target-excluded
estimators are safe enough to promote; under the preregistered S16n rule, absent
external labels keep these corrections diagnostic only.

## 2. Estimators and equations

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
`a,b`, the induced timing-shift equation is

```
Delta r_i = (t_hat_{i,a} - t_ref_{i,a}) - (t_hat_{i,b} - t_ref_{i,b}).
```

The time-of-flight term cancels in this difference, but the pair identities are
kept to audit S02/S03-like downstream residual risk. Bootstrap intervals resample
held-out runs with replacement.

## 4. Head-to-head results

| method | family | pedestal_rmse_adc | pedestal_rmse_adc_ci_low | pedestal_rmse_adc_ci_high | pedestal_bias_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_bias_delta_adc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_mean3 | traditional | 734.8356 | 590.6060 | 797.6723 | -0.0000 | 0.0922 | 0.1414 | 0.0007 | -37.9475 |
| traditional_median3 | traditional | 839.6783 | 697.8806 | 908.7517 | -37.9475 | 0.0703 | 0.1258 | 0.0013 | 0.0000 |
| ridge | ml | 467.1736 | 397.7601 | 508.6284 | -8.1031 | 0.6691 | 0.6565 | 0.0061 | -29.8445 |
| one_dimensional_cnn | ml | 446.0271 | 370.6120 | 493.9094 | -32.3984 | 0.4702 | 0.3113 | 0.0089 | -5.5491 |
| target_masked_residual_cnn | new_architecture | 315.4943 | 252.7694 | 360.4945 | 0.1301 | 0.6576 | 0.4186 | 0.0160 | -38.0776 |
| gradient_boosted_trees | ml | 238.5427 | 191.5573 | 275.9434 | 0.2884 | 0.2403 | 0.2058 | 0.0199 | -38.2359 |
| traditional_line3 | traditional | 543.5508 | 444.8158 | 600.4273 | -33.8518 | 0.1984 | 0.1883 | 0.0245 | -4.0958 |
| mlp | ml | 374.7510 | 311.8020 | 419.1884 | -10.3797 | 0.5671 | 0.3069 | 0.0407 | -27.5679 |
| traditional_run_stratified | traditional | 512.2466 | 432.4540 | 568.3994 | -7.2710 | 0.2458 | 0.2376 | 0.0412 | -30.6766 |

Paired run-block deltas in `Pr(|Delta r| > 5 ns)` relative to the best
traditional timing-risk method (`traditional_mean3`):

| method | reference_traditional_method | delta_tail_gt5_fraction | ci_low | ci_high |
| --- | --- | --- | --- | --- |
| traditional_median3 | traditional_mean3 | 0.00062 | 0.00040 | 0.00078 |
| ridge | traditional_mean3 | 0.00537 | 0.00442 | 0.00688 |
| one_dimensional_cnn | traditional_mean3 | 0.00815 | 0.00670 | 0.01067 |
| target_masked_residual_cnn | traditional_mean3 | 0.01526 | 0.01253 | 0.01722 |
| gradient_boosted_trees | traditional_mean3 | 0.01923 | 0.01703 | 0.02057 |
| traditional_line3 | traditional_mean3 | 0.02381 | 0.02241 | 0.02498 |
| mlp | traditional_mean3 | 0.04002 | 0.03550 | 0.04355 |
| traditional_run_stratified | traditional_mean3 | 0.04047 | 0.03525 | 0.04409 |

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

- **No external no-pulse truth in the mirror:** this is a leave-one-pretrigger-
  sample closure test on beam-triggered events, not a direct forced/random
  pedestal measurement. The filename audit found no forced/random/no-pulse/
  pedestal ROOT source in the mounted data tree.
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

`result.json` names `traditional_mean3` as the winner under the timing-risk
endpoint. The strongest learned model by excluded-sample RMSE is not the safest
model by downstream `|Delta r| > 5 ns` tail risk. The core lesson is that
pedestal RMSE and downstream timing safety are different objectives. Because
direct external no-pulse labels are absent from the current mirror, methods that
improve excluded-sample RMSE but enlarge timing tails remain diagnostic models
rather than charge/live-time pedestal replacements.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.py --config configs/s16n_1781124602_891_3b6f0ae7_external_no_pulse_pedestal_closure.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `method_metrics.csv`, `per_run_metrics.csv`,
`method_delta_bootstrap.csv`, `stratified_audit.csv`, `leakage_checks.csv`,
`model_cv_scan.csv`, `external_source_audit.csv`, sampled held-out predictions,
and figures.
