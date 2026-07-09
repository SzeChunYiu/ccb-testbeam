# S03l: Direct downstream substitution audit for the S03k winner

- **Ticket:** `1781147391.1146.677159b3`
- **Worker:** `testbeam-laptop-1`
- **Primary input:** raw B-stack ROOT under `data/root/root`
- **Frozen substitute:** `hgb_waveform_amp_shape_stave`, the S03k HGB waveform-amplitude-shape-stave winner
- **Comparator:** exact-fold `analytic_timewalk`
- **Fold unit:** untouched Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65

## Abstract

This audit freezes the S03k HGB timing correction and directly substitutes its event-level residuals for the exact-fold S03 analytic comparator on the same downstream B4/B6/B8 event-pair rows. The raw-ROOT reproduction gate passes exactly at **640,737** selected B-stave pulses. On the primary timing residual estimand, HGB reduces `sigma68` from **1.551 ns** to **1.107 ns**, with run-block CI **[1.075, 1.159]** and HGB-minus-analytic delta **-0.444 ns**.

The direct downstream join uses S06 charge/energy support covariates for every `(run,event_id,pair)` row and then recomputes charge, pile-up, PID-topology, and energy-support timing deltas under the HGB substitution. The result is favorable for timing width and tail risk, but it is not a license to replace all downstream calibrations: charge/PID/energy truth labels are imported references or support proxies unless their event-level labels are present in the joined table.

## Raw-ROOT Reproduction Gate

The gate reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude greater than 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimands

For event `e`, pair `(a,b)`, and method `m`, the residual is

`r_{eabm} = tau_{eam} - tau_{ebm}`.

The robust width and tail fraction are

`sigma68 = (Q84(r) - Q16(r))/2`,

`T5 = P(|r - median(r)| > 5 ns)`.

For each consumer stratum `c`, the substitution delta is

`Delta_c = metric_c(HGB) - metric_c(analytic_timewalk)`.

Confidence intervals resample held-out runs with replacement and keep all event-pair residuals inside a sampled run. Negative deltas are improvements for `sigma68`, full RMS, and tail fraction.

## Required Family Benchmark

| method                                 | model_family                      | family      |   n_pair_residuals |   sigma68_ns | ci             |   full_rms_ns |   tail_frac_vs_traditional_p95 |   delta_vs_traditional_ns | delta_ci         |
|:---------------------------------------|:----------------------------------|:------------|-------------------:|-------------:|:---------------|--------------:|-------------------------------:|--------------------------:|:-----------------|
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees            | ml          |              11460 |      1.10742 | [1.075, 1.159] |       2.13171 |                      0.0203316 |                 -0.443675 | [-0.842, -0.241] |
| mlp_waveform_amp_shape_stave           | mlp                               | ml          |              11460 |      1.1621  | [1.106, 1.235] |       2.45852 |                      0.0205061 |                 -0.388989 | [-0.818, -0.167] |
| ridge_waveform_stave_onehot            | ridge                             | ml          |              11460 |      1.24442 | [1.173, 1.322] |       2.40735 |                      0.0267888 |                 -0.306677 | [-0.739, -0.089] |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture    | ml          |              11460 |      1.25349 | [1.213, 1.308] |       2.43513 |                      0.0273997 |                 -0.297601 | [-0.671, -0.095] |
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                            | ml          |              11460 |      1.26387 | [1.212, 1.343] |       2.43601 |                      0.0280105 |                 -0.287227 | [-0.686, -0.086] |
| analytic_timewalk                      | traditional_s03_analytic_timewalk | traditional |              11460 |      1.55109 | [1.364, 1.936] |       2.66699 |                      0.05      |                  0        | [0.000, 0.000]   |

The required panel includes a strong traditional method, ridge, gradient-boosted trees, MLP, 1D-CNN, and a feature-gated architecture. The named winner is **hgb_waveform_amp_shape_stave**.

## Direct Substitution Results

| consumer   | stratum               |   n_pair_residuals |   analytic_sigma68_ns |   hgb_sigma68_ns |   hgb_minus_analytic_sigma68_ns | sigma68_delta_ci   |   hgb_minus_analytic_full_rms_ns |   hgb_minus_analytic_tail_frac_abs_gt5ns | tail_delta_ci      |
|:-----------|:----------------------|-------------------:|----------------------:|-----------------:|--------------------------------:|:-------------------|---------------------------------:|-----------------------------------------:|:-------------------|
| timing     | all                   |              11460 |               1.55109 |          1.10742 |                       -0.443675 | [-0.788, -0.250]   |                        -0.535279 |                              -0.00532286 | [-0.0087, -0.0022] |
| charge     | all_charge_matched    |              11460 |               1.55109 |          1.10742 |                       -0.443675 | [-0.775, -0.251]   |                        -0.535279 |                              -0.00532286 | [-0.0086, -0.0023] |
| energy     | all_energy_support    |              11460 |               1.55109 |          1.10742 |                       -0.443675 | [-0.837, -0.238]   |                        -0.535279 |                              -0.00532286 | [-0.0092, -0.0023] |
| pileup     | all_timing_tail_proxy |              11460 |               1.55109 |          1.10742 |                       -0.443675 | [-0.829, -0.252]   |                        -0.535279 |                              -0.00532286 | [-0.0091, -0.0022] |
| pid        | all_topology_proxy    |              11460 |               1.55109 |          1.10742 |                       -0.443675 | [-0.839, -0.252]   |                        -0.535279 |                              -0.00532286 | [-0.0091, -0.0022] |

All five top-level consumers are evaluated on identical joined rows. `timing` is the primary physical residual; `charge` and `energy` are the S06 support covariates; `pileup` is timing-tail sensitivity; `pid` is topology/anomaly-support sensitivity. The HGB substitution reduces the same residual distribution in each top-level view because the downstream strata are reweightings of the same event-pair population, not independent truth tasks.

## Stratum-Level Improvements

| consumer   | stratum                                   |   n_pair_residuals |   analytic_sigma68_ns |   hgb_sigma68_ns |   hgb_minus_analytic_sigma68_ns | sigma68_delta_ci   |   hgb_minus_analytic_tail_frac_abs_gt5ns |
|:-----------|:------------------------------------------|-------------------:|----------------------:|-----------------:|--------------------------------:|:-------------------|-----------------------------------------:|
| energy     | amplitude_bin=amp_adc[4000,7000)          |                492 |              2.55444  |         1.36516  |                       -1.18928  | [-1.848, -0.910]   |                              -0.0325203  |
| charge     | charge_bin=charge[24000,40000)            |               3624 |              1.77525  |         1.16119  |                       -0.61406  | [-0.928, -0.327]   |                              -0.0057947  |
| pileup     | run_family=sampleII_mid_61_63             |               6330 |              1.73368  |         1.12411  |                       -0.60957  | [-1.041, -0.218]   |                              -0.00868878 |
| pileup     | sample_window_mask=nominal_template_7_11  |               8056 |              1.86995  |         1.29504  |                       -0.574907 | [-0.951, -0.268]   |                              -0.00732373 |
| pid        | p09_anomaly_class=novel_early_pretrigger  |                298 |              1.31998  |         0.780244 |                       -0.539737 | [-0.621, -0.409]   |                               0.00671141 |
| pileup     | sample_window_mask=artifact_sensitive_3_6 |               2498 |              1.18037  |         0.64311  |                       -0.537264 | [-0.570, -0.491]   |                               0.00360288 |
| pid        | p09_anomaly_class=unassigned_common       |              10516 |              1.59707  |         1.10875  |                       -0.488315 | [-0.867, -0.270]   |                              -0.00589578 |
| energy     | amplitude_bin=amp_adc[2500,4000)          |               6811 |              1.56158  |         1.13278  |                       -0.428805 | [-0.844, -0.161]   |                              -0.00220232 |
| charge     | charge_bin=charge[14000,24000)            |               5990 |              1.54329  |         1.1282   |                       -0.415091 | [-0.813, -0.161]   |                              -0.00634391 |
| charge     | charge_bin=charge[8000,14000)             |               1471 |              1.23885  |         0.879768 |                       -0.359077 | [-0.479, -0.171]   |                              -0.00135962 |
| charge     | charge_bin=charge[4000,8000)              |                285 |              1.26605  |         0.925689 |                       -0.340356 | [-0.476, -0.275]   |                               0          |
| pileup     | run_family=sampleII_early_58_60           |               4932 |              1.38736  |         1.0818   |                       -0.305561 | [-0.392, -0.150]   |                              -0.00202758 |
| energy     | amplitude_bin=amp_adc[1500,2500)          |               3901 |              1.35234  |         1.05425  |                       -0.298087 | [-0.651, -0.126]   |                              -0.00615227 |
| pileup     | run_family=sampleII_late_65               |                198 |              1.49464  |         1.22328  |                       -0.271363 | [-0.271, -0.271]   |                              -0.00505051 |
| pileup     | sample_window_mask=late_tail_12_14        |                429 |              1.24758  |         1.0578   |                       -0.189781 | [-0.314, -0.004]   |                              -0.00932401 |
| energy     | amplitude_bin=amp_adc[1000,1500)          |                256 |              0.943987 |         0.817206 |                       -0.126781 | [-0.325, 0.254]    |                               0          |

The largest gains occur in high-support amplitude/charge and run-family bins, including the stress regions that made S03k useful. These rows are the most defensible substitution evidence because the analytic and HGB residuals are paired event-by-event.

## Imported Consumer Context

| source                              | consumer   | method                            | metric                 |     value |      ci_low |     ci_high | role                                      |
|:------------------------------------|:-----------|:----------------------------------|:-----------------------|----------:|------------:|------------:|:------------------------------------------|
| S06b charge-energy timing support   | charge     | traditional                       | calibration_loss       | 0.659059  |   0.549944  |   0.775257  | charge-matched pull calibration baseline  |
| S06b charge-energy timing support   | charge     | phase_conformal_gated_cnn         | calibration_loss       | 0.0534484 |   0.0414198 |   0.0704633 | best existing uncertainty consumer        |
| S06b charge-energy timing support   | energy     | traditional                       | sigma68_ns             | 1.55109   | nan         | nan         | energy-support timing width baseline      |
| S06b charge-energy timing support   | energy     | phase_conformal_gated_cnn         | sigma68_ns             | 1.50399   |   1.3773    |   1.68357   | best existing energy-support timing width |
| S06c action-band closure            | energy     | traditional_after_action_bands    | calibration_loss       | 0.203856  |   0.0919344 |   0.384142  | accepted support baseline                 |
| S06c action-band closure            | energy     | phase_conformal_gated_cnn         | calibration_loss       | 0.0748153 |   0.0542841 |   0.106241  | accepted support best existing consumer   |
| S10h phase-calibrated pileup window | pileup     | 1d_cnn                            | mean_average_precision | 1         | nan         | nan         | event-level pile-up classifier reference  |
| S00h calibrated PID-energy support  | pid        | traditional_fixed_secondary_score | roc_auc                | 0.48875   |   0.47      |   0.50875   | traditional PID-energy support reference  |
| S00h calibrated PID-energy support  | pid        | new_shape_residual_fusion         | roc_auc                | 0.988338  |   0.984335  |   0.993619  | best PID-energy support model             |
| S14h G4 energy calibration          | energy     | geant4_birks_lookup               | res68_frac             | 0.040244  |   0.0388569 |   0.0416063 | traditional energy calibration            |
| S14h G4 energy calibration          | energy     | gradient_boosted_trees            | res68_frac             | 0.0566846 |   0.048804  |   0.0671974 | tree energy calibration reference         |

These imported rows are not used to name the S03l timing-substitution winner. They document the downstream landscape: charge and energy support studies already prefer learned uncertainty or calibration models in some tasks; pile-up and PID references are strong but not event-label-joined to the S03k residual rows in this audit.

## Systematics and Caveats

- **Raw data:** the selected-pulse number is reproduced from raw ROOT before any substitution claims are made.
- **Split leakage:** all timing substitution rows are the frozen P03f/S03k leave-one-run-out Sample-II rows. No run id, event id, event order, other-stave time, or held-out residual target is added in this audit.
- **Consumer truth:** charge and energy support covariates are event-level and direct; PID and pile-up are timing/topology support proxies unless imported reference labels are explicitly cited.
- **Metric coupling:** top-level consumer deltas are correlated because they use the same residual rows with different support labels.
- **Adoption threshold:** the HGB substitution wins the timing residual audit, but downstream calibration adoption still requires consumer-native retraining or a locked correction API.

## Verdict

`result.json` names **hgb_waveform_amp_shape_stave** as the winner. The direct event-level substitution improves `sigma68`, full RMS, and the `|r-median|>5 ns` tail fraction against exact-fold S03 analytic timewalk on untouched run-family folds. The strongest defensible conclusion is timing-consumer substitution readiness; charge, pile-up, PID, and energy adoption should remain gated by consumer-native labels or the imported references above.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03l_1781147391_1146_677159b3_direct_downstream_substitution.py
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `required_family_benchmark.csv`, `substituted_residual_rows.csv.gz`, `substitution_summary.csv`, `downstream_metric_deltas.csv`, `imported_consumer_evidence.csv`, `input_sha256.csv`, and `manifest.json`.
