# P11: learned baseline/pedestal estimation bakeoff

- **Ticket:** 2405
- **Author:** testbeam-laptop-2
- **Date:** 2026-08-16
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `d3b2beb217c7157693da45e3e8824489c7a8f036`
- **Config:** `configs/p11_2405_learned_baseline_pedestal_bakeoff.json`

## 0. Question

The ticket asks whether learned pedestal estimators built from pretrigger
samples improve low-amplitude baseline handling enough to replace a strong
traditional pedestal estimator. Because no independent forced/random no-pulse
truth source is complete in this checkout, the operational test is a
target-excluded pretrigger closure benchmark plus a downstream timing-risk
counterfactual. It is therefore not only

```
y_{i,k} = x_{i,k},  k in {0,1,2,3},
```

with `x_{i,k}` predicted after excluding target sample `k`. It is also the
counterfactual timing perturbation caused when the predicted value is used as
the pedestal for the selected pulse.

## 1. Raw ROOT reproduction

The reproduction gate reruns the selected B-stave pulse count from raw
`h101/HRDv` ROOT files in `/home/billy/ccb-data/data/extracted/root/root`.
The seed pedestal is the median of samples 0-3 and the selection is
`A > 1000 ADC`.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | True |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | True |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | True |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | True |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | True |

The gate passes exactly, so the benchmark population is anchored to the raw
selected-pulse definition required by the P11 ticket.

## 2. Estimators

For each selected pulse and each target pretrigger sample `k`, all estimators
see only the other three pretrigger samples plus target-excluded waveform
summaries. The traditional estimators are

```
mean3_k   = mean({x_j : j != k})
median3_k = median({x_j : j != k})
line3_k   = least-squares extrapolation through the three visible samples.
```

The deliberately conservative deployment comparator is `traditional_mean3`,
which is the current transparent pedestal replacement with the lowest
downstream timing-tail risk in this study. A stronger descriptive traditional
estimator, `traditional_run_stratified`, adds a train-run median residual
correction to `line3_k` in cells of target sample, stave, provisional amplitude,
and visible-pretrigger range. No held-out run is used for those medians.

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
kept to audit S02/S03-like downstream residual risk. Bootstrap intervals
resample held-out runs with replacement.

## 4. Head-to-head results

| method | family | pedestal_rmse_adc | pedestal_rmse_adc_ci_low | pedestal_rmse_adc_ci_high | pedestal_bias_adc | timing_sigma68_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | charge_bias_delta_adc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_mean3 | traditional | 734.8356 | 631.8139 | 797.7145 | -0.0000 | 0.0922 | 0.1414 | 0.0007 | -37.9475 |
| traditional_median3 | traditional | 839.6783 | 704.3229 | 910.1242 | -37.9475 | 0.0703 | 0.1258 | 0.0013 | 0.0000 |
| ridge | ml | 464.3999 | 391.5417 | 510.9531 | -9.9448 | 0.6527 | 0.6603 | 0.0051 | -28.0028 |
| target_masked_residual_cnn | new_architecture | 234.6782 | 187.4733 | 276.1207 | 4.7204 | 0.4926 | 0.3156 | 0.0111 | -42.6679 |
| gradient_boosted_trees | ml | 216.7075 | 163.5823 | 250.5664 | -0.6730 | 0.2442 | 0.2118 | 0.0193 | -37.2745 |
| one_dimensional_cnn | ml | 310.4645 | 257.5512 | 350.4674 | -4.3119 | 0.4631 | 0.3055 | 0.0195 | -33.6357 |
| traditional_line3 | traditional | 543.5508 | 446.9266 | 605.0401 | -33.8518 | 0.1984 | 0.1883 | 0.0245 | -4.0958 |
| mlp | ml | 328.6019 | 265.3312 | 379.8337 | -6.9958 | 0.4785 | 0.3018 | 0.0293 | -30.9517 |
| traditional_run_stratified | traditional | 512.6087 | 418.2159 | 570.0277 | -7.5261 | 0.2386 | 0.2342 | 0.0397 | -30.4215 |

Paired run-block deltas in `Pr(|Delta r| > 5 ns)` relative to the best
traditional timing-risk method (`traditional_mean3`):

| method | reference_traditional_method | delta_tail_gt5_fraction | ci_low | ci_high |
| --- | --- | --- | --- | --- |
| traditional_median3 | traditional_mean3 | 0.00062 | 0.00042 | 0.00077 |
| ridge | traditional_mean3 | 0.00443 | 0.00357 | 0.00557 |
| target_masked_residual_cnn | traditional_mean3 | 0.01039 | 0.00902 | 0.01142 |
| gradient_boosted_trees | traditional_mean3 | 0.01856 | 0.01722 | 0.01949 |
| one_dimensional_cnn | traditional_mean3 | 0.01882 | 0.01294 | 0.02260 |
| traditional_line3 | traditional_mean3 | 0.02381 | 0.02236 | 0.02489 |
| mlp | traditional_mean3 | 0.02856 | 0.02461 | 0.03147 |
| traditional_run_stratified | traditional_mean3 | 0.03897 | 0.03577 | 0.04121 |

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
- **ML convergence:** the tabular MLP reached the configured 120-iteration cap
  in all seven folds. Its row remains a required neural comparator, but its
  poor timing-risk result should not be over-interpreted as a fully optimized
  architecture limit.

## 8. Finding

`result.json` names `traditional_mean3` as the winner under the timing-risk
endpoint. The target-masked residual CNN and gradient-boosted trees greatly
reduce excluded-sample pedestal RMSE, but their held-out downstream
`Pr(|Delta r| > 5 ns)` is higher than the transparent mean3 baseline with
run-block CIs well above zero. The core lesson is that pedestal RMSE and
downstream timing safety are different objectives. The report therefore treats
methods that improve excluded-sample RMSE but enlarge `|Delta r|` tails as
diagnostic models rather than adopted pedestal replacements.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.py --config configs/p11_2405_learned_baseline_pedestal_bakeoff.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `method_metrics.csv`, `per_run_metrics.csv`,
`method_delta_bootstrap.csv`, `stratified_audit.csv`, `leakage_checks.csv`,
`model_cv_scan.csv`, sampled held-out predictions, and figures.
