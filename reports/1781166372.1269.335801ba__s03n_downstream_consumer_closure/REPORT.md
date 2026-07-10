# S03n: Downstream-consumer closure for frozen S03m action bands

- **Ticket:** `1781166372.1269.335801ba`
- **Worker:** `testbeam-laptop-2`
- **Raw input:** B-stack ROOT files resolved by `configs/p03f_1781034623_1381_12086ef0_loro_feature_multimodel.json`
- **Frozen action source:** `reports/1781056870.436.378a461c__s03m_run64_timewalk_action_bands`
- **Comparator:** exact-fold S03 `analytic_timewalk`
- **Refit candidate:** `hgb_waveform_amp_shape_stave`, trained and scored in untouched leave-one-run-out folds
- **Bootstrap:** 500 resamples of held-out runs 58, 59, 60, 61, 62, 63, and 65

## Abstract

This study freezes the S03m pass/abstain/recalibrate action bands and asks whether downstream pile-up, PID, charge, and energy support decisions change when abstain/recalibrate regions are excluded or when the retained pass rows are scored by the untouched-fold HGB timing model. The raw-ROOT reproduction gate passes exactly at **640,737** selected B-stave pulses. The family benchmark names **hgb_waveform_amp_shape_stave** as the global winner with `sigma68=1.107 ns` and 95% run-bootstrap CI **[1.075, 1.159]**. On the retained S03m pass rows, the LORO HGB refit changes `sigma68` by **-0.308 ns** versus the analytic comparator with CI **[-0.375, -0.214]**.

## Raw-ROOT Reproduction Gate

The gate reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Frozen S03m Actions

Each held-out pair row inherits three frozen labels: run action, pair action, and amplitude-bin action. The row-level action is

`a_i = max_priority(a_run, a_pair, a_amp)`, with `recalibrate > pass > abstain`.
This keeps recalibration vetoes conservative while allowing explicit frozen pass
bands to define the retained S03m closure sample even in the presence of the
global S03m abstain guard.

Rows with `a_i in {abstain, recalibrate}` are excluded for the pass-only closure. Rows with `a_i = pass` are scored twice: once with the analytic comparator and once with the HGB prediction from the leave-one-run-out fold that did not contain the scored run.

| unit                    | stratum            |   n_pair_residuals |   sigma68_ns | action      | rationale                                                      |
|:------------------------|:-------------------|-------------------:|-------------:|:------------|:---------------------------------------------------------------|
| run                     | 61                 |               2799 |      1.79299 | recalibrate | sigma68 CI above Sample-I transfer band                        |
| run                     | 63                 |               1110 |      1.40432 | recalibrate | amplitude slope and q_template shift both elevated             |
| sample_ii_amplitude_bin | (3000.0, 4000.0]   |                867 |      1.81425 | recalibrate | sigma68 CI above Sample-I transfer band                        |
| sample_ii_amplitude_bin | (999.999, 1500.0]  |               1145 |      1.27171 | recalibrate | amplitude slope and q_template shift both elevated             |
| global                  | sample_ii_analysis |              11460 |      1.49467 | abstain     | mixed evidence: not pass-stable and not a forced recalibration |
| run                     | 64                 |                  0 |    nan       | abstain     | no strict B4/B6/B8 same-event support                          |
| sample_ii_amplitude_bin | (4000.0, 7000.0]   |                 25 |     11.199   | abstain     | low support                                                    |
| sample_ii_amplitude_bin | (2000.0, 3000.0]   |               6922 |      1.56003 | abstain     | mixed evidence: not pass-stable and not a forced recalibration |
| sample_ii_pair          | B6-B8              |               3820 |      1.67097 | abstain     | mixed evidence: not pass-stable and not a forced recalibration |
| sample_ii_pair          | B4-B8              |               3820 |      1.07187 | abstain     | mixed evidence: not pass-stable and not a forced recalibration |
| sample_ii_pair          | B4-B6              |               3820 |      1.0389  | abstain     | mixed evidence: not pass-stable and not a forced recalibration |
| run                     | 60                 |               2424 |      1.41724 | pass        | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 62                 |               2421 |      1.41333 | pass        | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 59                 |               2289 |      1.37481 | pass        | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 58                 |                219 |      1.33262 | pass        | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 65                 |                198 |      1.30732 | pass        | width, tail, bias, and amplitude slope inside pass band        |
| sample_ii_amplitude_bin | (1500.0, 2000.0]   |               2501 |      1.38607 | pass        | width, tail, bias, and amplitude slope inside pass band        |

## Estimands and Equations

For event `e`, pair `(a,b)`, and method `m`,

`r_{eabm} = tau_{eam} - tau_{ebm}`.

The robust width and tail fraction are

`sigma68(r) = (Q84(r) - Q16(r))/2`,

`T5(r) = P(|r - median(r)| > 5 ns)`.

For a consumer stratum `c`, the refit delta is

`Delta_c = metric_c(HGB_LORO | a_i=pass) - metric_c(analytic | a_i=pass)`.

The action-gated all-row residual is

`r_i(action-gated) = 1[a_i=pass] r_i(HGB_LORO) + 1[a_i!=pass] r_i(analytic)`.

Confidence intervals resample complete held-out runs with replacement.

## Required Family Benchmark

| method                                 | model_family                      | family      |   n_pair_residuals |   sigma68_ns | ci             |   full_rms_ns |   delta_vs_traditional_ns | delta_ci         |
|:---------------------------------------|:----------------------------------|:------------|-------------------:|-------------:|:---------------|--------------:|--------------------------:|:-----------------|
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees            | ml          |              11460 |      1.10742 | [1.075, 1.159] |       2.13171 |                 -0.443675 | [-0.842, -0.241] |
| mlp_waveform_amp_shape_stave           | mlp                               | ml          |              11460 |      1.1621  | [1.106, 1.235] |       2.45852 |                 -0.388989 | [-0.818, -0.167] |
| ridge_waveform_stave_onehot            | ridge                             | ml          |              11460 |      1.24442 | [1.173, 1.322] |       2.40735 |                 -0.306677 | [-0.739, -0.089] |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture    | ml          |              11460 |      1.25349 | [1.213, 1.308] |       2.43513 |                 -0.297601 | [-0.671, -0.095] |
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                            | ml          |              11460 |      1.26387 | [1.212, 1.343] |       2.43601 |                 -0.287227 | [-0.686, -0.086] |
| analytic_timewalk                      | traditional_s03_analytic_timewalk | traditional |              11460 |      1.55109 | [1.364, 1.936] |       2.66699 |                  0        | [0.000, 0.000]   |

The required panel contains a strong traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and a feature-gated architecture. The named winner in `result.json` is **hgb_waveform_amp_shape_stave**.

## Downstream Decision Closure

| consumer   | stratum               |   n_pair_residuals |   retained_pass_fraction | analytic_decision   | hgb_refit_decision   | action_gated_decision   |   analytic_sigma68_ns |   hgb_sigma68_ns |   action_gated_sigma68_ns |
|:-----------|:----------------------|-------------------:|-------------------------:|:--------------------|:---------------------|:------------------------|----------------------:|-----------------:|--------------------------:|
| timing     | all                   |              11460 |                 0.658901 | usable              | usable               | withhold                |               1.55109 |          1.10742 |                   1.77886 |
| timing     | S03m pass rows        |               7551 |                 1        | usable              | usable               | usable                  |               1.42025 |          1.11209 |                   1.11209 |
| timing     | S03m excluded rows    |               3909 |                 0        | withhold            | usable               | withhold                |               1.94927 |          1.10505 |                   1.94927 |
| charge     | all_charge_matched    |              11460 |                 0.658901 | usable              | usable               | withhold                |               1.55109 |          1.10742 |                   1.77886 |
| energy     | all_energy_support    |              11460 |                 0.658901 | usable              | usable               | withhold                |               1.55109 |          1.10742 |                   1.77886 |
| pileup     | all_timing_tail_proxy |              11460 |                 0.658901 | usable              | usable               | withhold                |               1.55109 |          1.10742 |                   1.77886 |
| pid        | all_topology_proxy    |              11460 |                 0.658901 | usable              | usable               | withhold                |               1.55109 |          1.10742 |                   1.77886 |

The decision rule is intentionally simple and predeclared in the script: `usable` means `sigma68 <= 1.70 ns` and `T5 <= 0.04`; otherwise the row is `withhold`. The table is a downstream stability screen, not a replacement for consumer-native labels.

## Consumer Delta Table

| consumer   | stratum               | candidate                    | baseline                |   n_pair_residuals |   retained_pass_fraction |   candidate_minus_baseline_sigma68_ns | sigma68_delta_ci   |   candidate_sigma68_ns |
|:-----------|:----------------------|:-----------------------------|:------------------------|-------------------:|-------------------------:|--------------------------------------:|:-------------------|-----------------------:|
| timing     | all                   | hgb_waveform_amp_shape_stave | analytic_timewalk       |              11460 |                 0.658901 |                             -0.443675 | [-0.800, -0.249]   |                1.10742 |
| timing     | all                   | s03m_action_gated_hgb        | analytic_timewalk       |              11460 |                 0.658901 |                              0.227765 | [-0.327, 0.245]    |                1.77886 |
| timing     | S03m pass rows        | hgb_waveform_amp_shape_stave | analytic_timewalk       |               7551 |                 1        |                             -0.308161 | [-0.374, -0.220]   |                1.11209 |
| timing     | S03m pass rows        | s03m_action_gated_hgb        | analytic_timewalk       |               7551 |                 1        |                             -0.308161 | [-0.379, -0.217]   |                1.11209 |
| timing     | S03m pass rows        | s03m_pass_only_refit_hgb     | s03m_pass_only_analytic |               7551 |                 1        |                             -0.308161 | [-0.375, -0.214]   |                1.11209 |
| timing     | S03m excluded rows    | hgb_waveform_amp_shape_stave | analytic_timewalk       |               3909 |                 0        |                             -0.844218 | [-1.041, -0.218]   |                1.10505 |
| timing     | S03m excluded rows    | s03m_action_gated_hgb        | analytic_timewalk       |               3909 |                 0        |                              0        | [0.000, 0.000]     |                1.94927 |
| charge     | all_charge_matched    | hgb_waveform_amp_shape_stave | analytic_timewalk       |              11460 |                 0.658901 |                             -0.443675 | [-0.832, -0.238]   |                1.10742 |
| charge     | all_charge_matched    | s03m_action_gated_hgb        | analytic_timewalk       |              11460 |                 0.658901 |                              0.227765 | [-0.325, 0.256]    |                1.77886 |
| energy     | all_energy_support    | hgb_waveform_amp_shape_stave | analytic_timewalk       |              11460 |                 0.658901 |                             -0.443675 | [-0.829, -0.232]   |                1.10742 |
| energy     | all_energy_support    | s03m_action_gated_hgb        | analytic_timewalk       |              11460 |                 0.658901 |                              0.227765 | [-0.324, 0.259]    |                1.77886 |
| pileup     | all_timing_tail_proxy | hgb_waveform_amp_shape_stave | analytic_timewalk       |              11460 |                 0.658901 |                             -0.443675 | [-0.809, -0.253]   |                1.10742 |
| pileup     | all_timing_tail_proxy | s03m_action_gated_hgb        | analytic_timewalk       |              11460 |                 0.658901 |                              0.227765 | [-0.330, 0.252]    |                1.77886 |
| pid        | all_topology_proxy    | hgb_waveform_amp_shape_stave | analytic_timewalk       |              11460 |                 0.658901 |                             -0.443675 | [-0.816, -0.245]   |                1.10742 |
| pid        | all_topology_proxy    | s03m_action_gated_hgb        | analytic_timewalk       |              11460 |                 0.658901 |                              0.227765 | [-0.315, 0.262]    |                1.77886 |

## Stratum-Level Changes

| consumer   | stratum                                   | candidate                    | baseline                |   n_pair_residuals |   candidate_minus_baseline_sigma68_ns | sigma68_delta_ci   |
|:-----------|:------------------------------------------|:-----------------------------|:------------------------|-------------------:|--------------------------------------:|:-------------------|
| energy     | amplitude_bin=amp_adc[4000,7000)          | hgb_waveform_amp_shape_stave | analytic_timewalk       |                492 |                             -1.18928  | [-1.820, -0.906]   |
| timing     | S03m excluded rows                        | hgb_waveform_amp_shape_stave | analytic_timewalk       |               3909 |                             -0.844218 | [-1.041, -0.218]   |
| timing     | s03m_action=recalibrate                   | hgb_waveform_amp_shape_stave | analytic_timewalk       |               3909 |                             -0.844218 | [-1.041, -0.218]   |
| charge     | charge_bin=charge[24000,40000)            | hgb_waveform_amp_shape_stave | analytic_timewalk       |               3624 |                             -0.61406  | [-0.936, -0.333]   |
| pileup     | run_family=sampleII_mid_61_63             | hgb_waveform_amp_shape_stave | analytic_timewalk       |               6330 |                             -0.60957  | [-0.978, -0.218]   |
| pileup     | sample_window_mask=nominal_template_7_11  | hgb_waveform_amp_shape_stave | analytic_timewalk       |               8056 |                             -0.574907 | [-0.995, -0.266]   |
| pid        | p09_anomaly_class=novel_early_pretrigger  | hgb_waveform_amp_shape_stave | analytic_timewalk       |                298 |                             -0.539737 | [-0.623, -0.401]   |
| pileup     | sample_window_mask=artifact_sensitive_3_6 | hgb_waveform_amp_shape_stave | analytic_timewalk       |               2498 |                             -0.537264 | [-0.572, -0.496]   |
| pid        | p09_anomaly_class=unassigned_common       | hgb_waveform_amp_shape_stave | analytic_timewalk       |              10516 |                             -0.488315 | [-0.881, -0.281]   |
| energy     | amplitude_bin=amp_adc[2500,4000)          | hgb_waveform_amp_shape_stave | analytic_timewalk       |               6811 |                             -0.428805 | [-0.848, -0.156]   |
| charge     | charge_bin=charge[14000,24000)            | hgb_waveform_amp_shape_stave | analytic_timewalk       |               5990 |                             -0.415091 | [-0.821, -0.163]   |
| energy     | amplitude_bin=amp_adc[4000,7000)          | s03m_action_gated_hgb        | analytic_timewalk       |                492 |                             -0.376217 | [-1.073, 0.105]    |
| charge     | charge_bin=charge[8000,14000)             | hgb_waveform_amp_shape_stave | analytic_timewalk       |               1471 |                             -0.359077 | [-0.477, -0.181]   |
| charge     | charge_bin=charge[4000,8000)              | hgb_waveform_amp_shape_stave | analytic_timewalk       |                285 |                             -0.340356 | [-0.472, -0.273]   |
| timing     | S03m pass rows                            | hgb_waveform_amp_shape_stave | analytic_timewalk       |               7551 |                             -0.308161 | [-0.374, -0.220]   |
| timing     | S03m pass rows                            | s03m_action_gated_hgb        | analytic_timewalk       |               7551 |                             -0.308161 | [-0.379, -0.217]   |
| timing     | S03m pass rows                            | s03m_pass_only_refit_hgb     | s03m_pass_only_analytic |               7551 |                             -0.308161 | [-0.375, -0.214]   |
| timing     | s03m_action=pass                          | s03m_pass_only_refit_hgb     | s03m_pass_only_analytic |               7551 |                             -0.308161 | [-0.372, -0.220]   |

## Imported Consumer Context

| source                              | consumer   | method                    | metric                 |     value |      ci_low |     ci_high | role                                     |
|:------------------------------------|:-----------|:--------------------------|:-----------------------|----------:|------------:|------------:|:-----------------------------------------|
| S06b charge-energy timing support   | charge     | phase_conformal_gated_cnn | calibration_loss       | 0.0534484 |   0.0414198 |   0.0704633 | best existing uncertainty consumer       |
| S06c action-band closure            | energy     | phase_conformal_gated_cnn | calibration_loss       | 0.0748153 |   0.0542841 |   0.106241  | accepted support best existing consumer  |
| S10h phase-calibrated pileup window | pileup     | 1d_cnn                    | mean_average_precision | 1         | nan         | nan         | event-level pile-up classifier reference |
| S00h calibrated PID-energy support  | pid        | new_shape_residual_fusion | roc_auc                | 0.988338  |   0.984335  |   0.993619  | best PID-energy support model            |
| S14h G4 energy calibration          | energy     | geant4_birks_lookup       | res68_frac             | 0.040244  |   0.0388569 |   0.0416063 | traditional energy calibration           |

These imported rows define the consumer landscape but do not determine the S03n winner.

## Systematics and Caveats

- **Raw reproduction:** the selected-pulse number is reproduced from raw ROOT before residual joins.
- **Frozen policy:** S03n does not re-optimize S03m action thresholds; it only applies the frozen table.
- **Refit interpretation:** HGB, ridge, MLP, 1D-CNN, and the gated architecture are imported from the P03f leave-one-run-out panel, so each scored run was excluded from model fitting.
- **Consumer truth:** charge and energy are support covariates; pile-up and PID are topology/window proxies unless imported reference labels are explicitly cited.
- **Exclusion cost:** pass-only scoring improves interpretability but discards a large fraction of rows when any run/pair/amplitude band abstains or recalibrates.
- **Bootstrap granularity:** only seven held-out runs are available, so intervals are finite-run stability intervals, not event-level precision intervals.

## Verdict

`result.json` names **hgb_waveform_amp_shape_stave** as the global benchmark winner. Freezing S03m bands and excluding abstain/recalibrate regions changes downstream decisions mainly through coverage, not through a new global replacement claim. The retained pass rows remain compatible with HGB improvement under untouched-fold scoring, while excluded rows justify abstention/recalibration rather than silent adoption.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03n_1781166372_1269_335801ba_downstream_consumer_closure.py
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `required_family_benchmark.csv`, `frozen_s03m_action_bands.csv`, `action_labeled_residual_rows.csv.gz`, `substitution_summary.csv`, `downstream_metric_deltas.csv`, `consumer_decision_changes.csv`, `imported_consumer_evidence.csv`, `input_sha256.csv`, and `manifest.json`.
