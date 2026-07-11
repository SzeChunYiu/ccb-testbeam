# S19c: pile-up saturation timing recovery head-to-head

- **Ticket:** 1783759304.10079.0a892fb8
- **Worker:** testbeam-laptop-3
- **Config:** `configs/s19c_1783759304_10079_0a892fb8_pileup_saturation_timing_recovery.yaml`
- **Raw input:** `data/root/root`
- **Primary output:** `reports/1783759304.10079.0a892fb8__s19c_pileup_saturation_timing_recovery/result.json`

## Abstract

S19c asks whether timing can be recovered under overlapping or saturated B-stack
pulses with baseline drift, and whether waveform-based ML/NN corrections beat a
strong traditional timing baseline when validation is split by source run.  The
raw ROOT reproduction gate exactly recovers the selected B-pulse counts, then a
leave-one-run-out benchmark evaluates CFD20 pair-template timing, Ridge,
gradient-boosted trees, MLP, 1D-CNN, and a hybrid CNN-tabular architecture with
run-block bootstrap 95% confidence intervals.  The primary all-pair winner is
`raw_pair_median` with sigma68 = 1.779 ns and 95% CI
[1.612, 2.130]
ns.

## Raw ROOT Reproduction

The analysis reads `h101/HRDv` from the raw ROOT files under `data/root/root`,
uses the physical B-stack channels `B2/B4/B6/B8 = 0/2/4/6`, subtracts the
median of samples 0--3 as a pedestal, requires amplitude above 1000 ADC, and
computes CFD20 timing.  The reproduced count gate is exact:

| quantity | reported | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| total_selected_b_pulses | 640737 | 640737 | 0 | True |
| sample_i_analysis_b_selected_pulses | 252266 | 252266 | 0 | True |
| sample_ii_analysis_b_selected_pulses | 125096 | 125096 | 0 | True |

Pair rows used in the run-split timing benchmark:

| pair | n_pair_rows |
| --- | --- |
| B2-B4 | 26387 |
| B2-B6 | 12626 |
| B2-B8 | 4943 |
| B4-B6 | 12196 |
| B4-B8 | 4542 |
| B6-B8 | 4790 |

## Methods

For event `e`, run `r`, and stave pair `p=(i,j)`, the benchmark target is

```text
y_erp = t_j(e) - t_i(e) - (z_j - z_i) * 0.078 ns/cm
```

with 2 cm stave spacing.  The CFD20 time is estimated after pedestal refit from
the median baseline samples.  The uncorrected traditional comparator centers
each pair by a train-fold median:

```text
residual_raw = y_erp - median_train(y_p)
```

The Ridge comparators fit

```text
argmin_beta ||y - X beta||_2^2 + alpha ||beta||_2^2
```

where the no-saturation model uses amplitude, area, tail, peak, and pair
identity summaries, while the duplicate-safe traditional model additionally
uses direct waveform saturation observables: high-ADC sample count, near-peak
width, saturation excess, post-peak fall, and recovery tail.  Tree, MLP, CNN,
and hybrid models are trained only on the six non-held-out runs in each fold.
The hybrid CNN-tabular method is the new architecture: a waveform branch over
the two endpoint samples is concatenated with duplicate-safe tabular features.

The robust timing width is

```text
sigma68(x) = (Q84(x - median(x)) - Q16(x - median(x))) / 2
```

Confidence intervals resample held-out runs with replacement, preserving the
source-run split, and then evaluate the same held-out residual distribution.

## Primary Run-Split Benchmark

All folds hold out one Sample-II source run from `[58, 59, 60, 61, 62, 63, 65]`;
all metrics below are computed on every held-out pair row.

| method | role | sigma68 ns | 95% CI ns | full RMS ns | tail \|r\|>5 ns |
| --- | --- | --- | --- | --- | --- |
| raw_pair_median | CFD20 pair-median template baseline | 1.779 | [1.612, 2.130] | 12.779 | 0.0886 |
| extra_trees_duplicate_safe | ExtraTrees architecture added as the new non-linear comparator | 2.994 | [2.775, 3.541] | 11.238 | 0.1784 |
| mlp_duplicate_safe | Tabular MLP | 3.610 | [3.348, 4.006] | 11.952 | 0.1761 |
| gbt_duplicate_safe | Gradient-boosted trees | 3.884 | [3.746, 4.139] | 9.951 | 0.2199 |
| hybrid_cnn_tabular_duplicate_safe | New hybrid 1D-CNN plus tabular architecture | 4.084 | [3.119, 5.199] | 13.145 | 0.2063 |
| ridge_duplicate_safe | Strong traditional ridge recovery with waveform saturation diagnostics | 4.602 | [4.345, 5.174] | 9.735 | 0.2902 |
| cnn_waveform_only | 1D-CNN on endpoint waveforms | 4.688 | [3.314, 5.455] | 13.128 | 0.2890 |
| ridge_no_saturation | Ridge, no explicit saturation features | 4.857 | [4.492, 5.377] | 10.276 | 0.3101 |

The requested ML/NN family coverage is explicit: Ridge, gradient-boosted trees,
MLP, 1D-CNN, and a new hybrid CNN-tabular architecture are all included.  The
new architecture did not win this run-split validation; the CFD20 pair-template
median baseline retained the narrowest central timing residual.

## Saturated and Pile-Up Candidate Diagnostics

The raw B-stack does not contain truth labels for simulated pile-up onset,
charge-energy residuals, or downstream PID decisions.  Therefore the following
diagnostics are proxy validations, not production estimates of those quantities.
The pile-up/saturation candidate label is `b2_sat_count > 0`, and AP uses
`abs(residual)` as a failure-score proxy.  The saturation failure rate is the
fraction of those candidate rows with `abs(residual) > 5 ns`.

| method | AP proxy | bias ns | sat sigma68 ns | sat 95% CI ns | sat fail rate |
| --- | --- | --- | --- | --- | --- |
| ridge_duplicate_safe | 0.2701 | -0.715 | 9.964 | [7.870, 11.615] | 0.6163 |
| ridge_no_saturation | 0.2297 | -0.956 | 10.232 | [7.132, 12.477] | 0.5216 |
| gbt_duplicate_safe | 0.2522 | -1.567 | 10.250 | [4.860, 12.886] | 0.4547 |
| extra_trees_duplicate_safe | 0.3852 | -1.283 | 12.025 | [5.643, 15.130] | 0.7046 |
| mlp_duplicate_safe | 0.4044 | -0.641 | 12.868 | [5.177, 16.797] | 0.6287 |
| raw_pair_median | 0.3321 | 0.000 | 13.292 | [5.930, 17.045] | 0.3908 |
| hybrid_cnn_tabular_duplicate_safe | 0.3166 | -3.392 | 13.781 | [6.467, 17.397] | 0.7497 |
| cnn_waveform_only | 0.3045 | -3.644 | 14.591 | [8.232, 17.224] | 0.6962 |

Delay and amplitude-ratio requests are approximated with observable proxies:
`abs(target_residual_ns)` for apparent delay and the top decile of B2 amplitude
for high amplitude-ratio stress.

| method | delay proxy stratum | n | sigma68 ns | 95% CI ns |
| --- | --- | --- | --- | --- |
| hybrid_cnn_tabular_duplicate_safe | abs_raw_delay_1to3ns | 17993 | 2.763 | [2.306, 3.412] |
| hybrid_cnn_tabular_duplicate_safe | abs_raw_delay_3to6ns | 16052 | 2.550 | [1.246, 3.497] |
| hybrid_cnn_tabular_duplicate_safe | abs_raw_delay_ge6ns | 6669 | 19.158 | [17.185, 25.808] |
| hybrid_cnn_tabular_duplicate_safe | abs_raw_delay_lt1ns | 12325 | 2.185 | [1.024, 2.753] |
| raw_pair_median | abs_raw_delay_1to3ns | 17993 | 0.789 | [0.761, 0.825] |
| raw_pair_median | abs_raw_delay_3to6ns | 16052 | 1.190 | [1.086, 1.366] |
| raw_pair_median | abs_raw_delay_ge6ns | 6669 | 18.597 | [17.328, 26.502] |
| raw_pair_median | abs_raw_delay_lt1ns | 12325 | 1.778 | [1.657, 1.804] |
| ridge_duplicate_safe | abs_raw_delay_1to3ns | 17993 | 4.116 | [3.894, 4.490] |
| ridge_duplicate_safe | abs_raw_delay_3to6ns | 16052 | 3.793 | [3.554, 4.129] |
| ridge_duplicate_safe | abs_raw_delay_ge6ns | 6669 | 15.861 | [14.690, 18.210] |
| ridge_duplicate_safe | abs_raw_delay_lt1ns | 12325 | 5.017 | [4.633, 5.408] |

| method | amplitude proxy stratum | n | sigma68 ns | 95% CI ns |
| --- | --- | --- | --- | --- |
| hybrid_cnn_tabular_duplicate_safe | B2_amp_lower_90pct | 47731 | 3.795 | [3.052, 4.531] |
| hybrid_cnn_tabular_duplicate_safe | B2_amp_top_decile | 5308 | 12.556 | [10.173, 15.495] |
| raw_pair_median | B2_amp_lower_90pct | 47731 | 1.622 | [1.537, 1.794] |
| raw_pair_median | B2_amp_top_decile | 5308 | 12.157 | [9.796, 15.060] |
| ridge_duplicate_safe | B2_amp_lower_90pct | 47731 | 4.195 | [3.924, 4.559] |
| ridge_duplicate_safe | B2_amp_top_decile | 5308 | 9.201 | [8.545, 10.907] |

The independently generated B2 saturation strata are retained in
`saturation_strata.csv`; they show that the all-B2-containing raw baseline has
sigma68 1.838
ns, but B2 saturated rows broaden to
13.292
ns.

## Negative Controls and Leakage Checks

| check | value | pass |
| --- | --- | --- |
| run_split_event_overlap | 0.000 | True |
| ml_features_exclude_forbidden_columns | 1.000 | True |
| actual_ml_sigma68_ns | 2.994 | True |
| shuffled_train_target_ml_sigma68_ns | 3.675 | True |
| intentional_target_echo_sigma68_ns | 0.000 | True |

The shuffled-target sentinel stays worse than the nominal ExtraTrees model and
far worse than an intentionally leaked target echo.  Features exclude run,
event, direct timing labels, and raw target residuals.

## Systematics

The leading systematic is label limitation: there is no independent truth for
two-pulse overlay time, charge energy, or PID classification in the real B-stack
candidate table, so pile-up detection AP, charge residuals, and PID stability
are reported only as waveform-derived proxies.  The second systematic is model
capacity: NN fits are deliberately capped (`nn_epochs = 1`, 1200 fit rows per
fold) to make the ticket benchmark reproducible on CPU, which likely underfits
the CNN and MLP.  The third systematic is selection: the benchmark uses
Sample-II runs 58, 59, 60, 61, 62, 63, and 65 because the duplicate-readout
saturation validity gate is defined there; the reproduction gate covers the
larger configured B-stack count set.

Baseline drift is handled by per-pulse pedestal refits from samples 0--3, but no
separate slow-control or spill-level baseline model is fitted.  Saturation
features are duplicate-safe waveform measurements and do not use any adopted
P07 ratio-transfer amplitude correction.

## Caveats

This is a real-candidate run-split study, not a full synthetic overlay campaign.
The ticket's synthetic-overlay, charge-energy, and PID-consumer requirements are
addressed only through available real-candidate timing and saturation proxies in
this repository state.  A future dedicated overlay truth table would be needed
to convert the proxy AP, proxy amplitude strata, and proxy stability quantities
into detector-performance claims.

## Conclusion

The raw ROOT count gate passes exactly.  In leave-one-run-out validation with
run bootstrap confidence intervals, `raw_pair_median` wins the primary timing
metric.  The best non-traditional ML comparator is
`extra_trees_duplicate_safe`,
but its all-pair sigma68 remains wider than the raw CFD20 pair-template
baseline.  The result is recorded in `result.json`, with auxiliary S19c proxy
tables in `s19c_proxy_diagnostics.csv` and `s19c_delay_amplitude_strata.csv`.
