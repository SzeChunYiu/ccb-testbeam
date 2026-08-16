# Issue #2378: S06 resolution vs amplitude/energy and absolute time scale

## Abstract

This ticket evaluates whether the B-stack timing resolution can be parameterized as a one-dimensional function of pulse amplitude or charge-energy proxy, and whether a learned uncertainty model improves on a strong traditional timing-resolution baseline. The analysis starts with a fresh raw ROOT reproduction gate in the current workspace, then uses the reviewed S06b leave-one-run-out pair-residual benchmark tables as the method comparison layer. The pre-registered metric is pooled pairwise pull-calibration loss on held-out runs.

The winner is **phase_conformal_gated_cnn** with calibration loss **0.0534** and run-block bootstrap 95% CI **[0.0414, 0.0705]**. The strong traditional S02/S03/S04 atom robust-width baseline has loss **0.6591**, so the winner improves the calibration objective by **0.6056**. The raw ROOT count reproduces **640,737** configured selected B-stave pulses, matching the S00 anchor exactly.

## Ticket And Data Contract

- Ticket: `#2378`, `S06: Resolution vs amplitude/energy + absolute time scale`.
- Worker: `testbeam-laptop-4`.
- Raw data read-only input: `/home/billy/ccb-data/data/extracted/sorted-b`.
- Report directory: `reports/issue_2378_s06_resolution_amplitude_energy_timescale`.
- Configured report runs: `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]`.
- Held-out benchmark runs: `[58, 59, 60, 61, 62, 63, 65]`.
- Amplitude cut: `1000.0` ADC after per-channel median baseline over samples 0--3.

## Raw ROOT Reproduction

For event `e`, channel `c`, and sample `j`, the waveform value is `x_e,c,j`. The pedestal is

`b_e,c = median(x_e,c,0, x_e,c,1, x_e,c,2, x_e,c,3)`,

and the selected-pulse amplitude is

`A_e,c = max_j x_e,c,j - b_e,c`.

The S00/S06 B-stave gate counts channels B2/B4/B6/B8, mapped to sorted-B channels 0/2/4/6, with `A_e,c > 1000 ADC`. The reproduction table is:

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses on configured S00/S06 runs | 640737 | 640737 | 0 | 0 | true |
| sample-II analysis selected pulses | 125096 | 125096 | 0 | 0 | true |
| sample-II analysis B2 | 88213 | 88213 | 0 | 0 | true |
| sample-II analysis B4 | 21229 | 21229 | 0 | 0 | true |
| sample-II analysis B6 | 11148 | 11148 | 0 | 0 | true |
| sample-II analysis B8 | 4506 | 4506 | 0 | 0 | true |

The all-file sorted-B mirror contains additional early runs; this ticket intentionally counts only the S06 configured S00 run groups from the committed config.

## Estimands

The benchmark uses downstream B-stack pairs B4-B6, B4-B8, and B6-B8. For event `e`, stave `s`, and method `m`, the geometry-corrected timestamp is

`tau_e,s,m = t_e,s,m - x_s v_TOF`,

where `v_TOF = 0.078 ns/cm` and the downstream spacing is 2 cm. Pair residuals are

`r_e,a,b,m = tau_e,a,m - tau_e,b,m`.

Central timing width is reported as

`sigma68(r) = (Q_0.84(r) - Q_0.16(r)) / 2`,

with full RMS and tail fractions retained to expose non-Gaussian structure. Each uncertainty model predicts an interval scale `sigma_hat`; pulls are `z = r / sigma_hat`. The calibration loss is

`L = mean(|sigma68(z)-1|, |P(|z|<=1)-0.682689|, |P(|z|<=1.96)-0.95|, ECE)`.

Lower `L` is better. The bootstrap intervals in the benchmark tables are run-block/event-paired bootstrap intervals with 300 replicates.

## Methods

The traditional comparator is not a strawman. It combines S02 template-phase timing, the S03 amplitude-only analytic timewalk correction, and an S04 atom robust-width lookup over pair, peak sample, leading-edge phase, sample-window mask, and coarser fallbacks. It is run-external to the evaluated run.

The ML/NN comparators are ridge regression, HistGradientBoosting, MLP, 1D-CNN, and the new phase-conformal atom-gated CNN. The learned models use waveform shape, amplitude, charge proxy, q-template, baseline, phase, topology, anomaly/action, and run-family covariates, while leakage checks exclude event id, raw residual, pull, sigma target, and held-out labels. The new architecture uses 1D convolutional waveform encoders plus atom/tabular support gates and a run-external conformal phase-bin scale adjustment.

## Head-To-Head Results

| method | n | calibration_loss | calibration_loss_ci_low | calibration_loss_ci_high | pull_width68 | coverage68 | coverage95 | sigma68_ns | full_rms_ns | tail_frac_abs_gt5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase_conformal_gated_cnn | 11460 | 0.0534484 | 0.0414198 | 0.0704633 | 0.901022 | 0.631937 | 0.960995 | 1.50399 | 2.41532 | 0.0114311 |
| cnn1d | 11460 | 0.0973354 | 0.079418 | 0.159563 | 1.00983 | 0.454538 | 0.936126 | 1.5101 | 2.42042 | 0.0129145 |
| mlp | 11460 | 0.103472 | 0.0667066 | 0.170197 | 1.05182 | 0.516928 | 0.876003 | 1.64477 | 2.42453 | 0.0138743 |
| gradient_boosted_trees | 11460 | 0.109007 | 0.0740727 | 0.218837 | 1.0451 | 0.502792 | 0.869721 | 1.5543 | 2.31556 | 0.0153578 |
| ridge | 11460 | 0.110021 | 0.0776086 | 0.216983 | 1.02024 | 0.481065 | 0.871728 | 1.57318 | 2.54659 | 0.0161431 |
| traditional | 11460 | 0.659059 | 0.549944 | 0.775257 | 2.71207 | 0.384991 | 0.631588 | 1.55109 | 2.66699 | 0.0191099 |

## Held-Out Run Split

The split is leave-one-run-out over Sample-II analysis runs. The best row per held-out run is:

| run | method | n | calibration_loss | calibration_loss_ci_low | calibration_loss_ci_high | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | coverage68 | coverage95 | any_action_band_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | phase_conformal_gated_cnn | 219 | 0.0807315 | 0.0602546 | 0.107904 | 1.44496 | 1.35789 | 1.58067 | 0.552511 | 0.977169 | 0.826484 |
| 59 | phase_conformal_gated_cnn | 2289 | 0.036222 | 0.0300818 | 0.0439326 | 1.45517 | 1.41566 | 1.50307 | 0.638707 | 0.954128 | 0.706859 |
| 60 | phase_conformal_gated_cnn | 2424 | 0.0705094 | 0.0651583 | 0.0800182 | 1.31669 | 1.28861 | 1.35147 | 0.651815 | 0.963696 | 0.681931 |
| 61 | phase_conformal_gated_cnn | 2799 | 0.0816349 | 0.074942 | 0.091108 | 1.77103 | 1.72897 | 1.82807 | 0.536977 | 0.967846 | 0.733119 |
| 62 | mlp | 2421 | 0.0611271 | 0.0524967 | 0.0731523 | 1.60852 | 1.53992 | 1.65947 | 0.594796 | 0.914911 | 0.716233 |
| 63 | phase_conformal_gated_cnn | 1110 | 0.0578199 | 0.0483615 | 0.0703267 | 1.47808 | 1.43504 | 1.53173 | 0.596396 | 0.965766 | 0.725225 |
| 65 | phase_conformal_gated_cnn | 198 | 0.0838919 | 0.0552714 | 0.12015 | 1.52228 | 1.37735 | 1.65945 | 0.737374 | 0.989899 | 0.737374 |

The full per-method, per-run table is stored in `per_run_bootstrap_summary.csv`.

## Amplitude And Charge-Energy Proxy

The S06 question is not answered by a monotonic sigma(A) curve alone. The amplitude and charge proxy strata change support composition, especially q-template, baseline, dropout/anomaly, and saturation action bands. Representative pooled support rows are:

| dimension | stratum | method | n | n_runs | support_fraction | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | full_rms_ns | calibration_loss | any_action_band_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| amplitude_bin | amp_adc[1000,1500) | ridge | 256 | 7 | 0.0223386 | 1.04003 | 0.700025 | 1.36438 | 2.8117 | 0.184117 | 0.976562 |
| amplitude_bin | amp_adc[1000,1500) | mlp | 256 | 7 | 0.0223386 | 1.07925 | 0.851703 | 1.39175 | 2.82192 | 0.190266 | 0.976562 |
| amplitude_bin | amp_adc[1000,1500) | phase_conformal_gated_cnn | 256 | 7 | 0.0223386 | 0.713217 | 0.417429 | 1.11398 | 3.03328 | 0.202035 | 0.976562 |
| amplitude_bin | amp_adc[1000,1500) | gradient_boosted_trees | 256 | 7 | 0.0223386 | 0.851605 | 0.737313 | 1.27075 | 2.93945 | 0.215234 | 0.976562 |
| amplitude_bin | amp_adc[1000,1500) | cnn1d | 256 | 7 | 0.0223386 | 0.6722 | 0.494148 | 1.1443 | 2.95533 | 0.258354 | 0.976562 |
| amplitude_bin | amp_adc[1000,1500) | traditional | 256 | 7 | 0.0223386 | 0.943987 | 0.447368 | 1.33365 | 2.95576 | 2.02015 | 0.976562 |
| amplitude_bin | amp_adc[1500,2500) | phase_conformal_gated_cnn | 3901 | 7 | 0.340401 | 1.45683 | 1.32235 | 1.58486 | 2.11929 | 0.100333 | 0.758267 |
| amplitude_bin | amp_adc[1500,2500) | mlp | 3901 | 7 | 0.340401 | 1.49364 | 1.37795 | 1.61099 | 2.12202 | 0.125974 | 0.758267 |
| amplitude_bin | amp_adc[1500,2500) | gradient_boosted_trees | 3901 | 7 | 0.340401 | 1.45851 | 1.3207 | 1.63233 | 2.02969 | 0.129053 | 0.758267 |
| amplitude_bin | amp_adc[1500,2500) | cnn1d | 3901 | 7 | 0.340401 | 1.46823 | 1.33738 | 1.63103 | 2.0417 | 0.141732 | 0.758267 |
| amplitude_bin | amp_adc[1500,2500) | ridge | 3901 | 7 | 0.340401 | 1.46501 | 1.321 | 1.75808 | 2.11855 | 0.142435 | 0.758267 |
| amplitude_bin | amp_adc[1500,2500) | traditional | 3901 | 7 | 0.340401 | 1.35234 | 1.17755 | 1.69792 | 2.19758 | 1.1376 | 0.758267 |
| amplitude_bin | amp_adc[2500,4000) | phase_conformal_gated_cnn | 6811 | 7 | 0.594328 | 1.52437 | 1.37388 | 1.72082 | 2.36099 | 0.0376286 | 0.679636 |
| amplitude_bin | amp_adc[2500,4000) | cnn1d | 6811 | 7 | 0.594328 | 1.52271 | 1.38164 | 1.71096 | 2.41712 | 0.111934 | 0.679636 |
| amplitude_bin | amp_adc[2500,4000) | mlp | 6811 | 7 | 0.594328 | 1.68391 | 1.5514 | 1.83178 | 2.39921 | 0.131894 | 0.679636 |
| amplitude_bin | amp_adc[2500,4000) | ridge | 6811 | 7 | 0.594328 | 1.60364 | 1.44948 | 1.87092 | 2.51294 | 0.133362 | 0.679636 |
| amplitude_bin | amp_adc[2500,4000) | gradient_boosted_trees | 6811 | 7 | 0.594328 | 1.60385 | 1.4333 | 1.8447 | 2.32266 | 0.14793 | 0.679636 |
| amplitude_bin | amp_adc[2500,4000) | traditional | 6811 | 7 | 0.594328 | 1.56158 | 1.3175 | 1.94838 | 2.63796 | 0.460248 | 0.679636 |

The monotonicity audit counts adjacent-bin increases in `sigma68`; a significant violation additionally requires non-overlapping bootstrap CIs:

| dimension | method | n_bins | n_adjacent_transitions | monotonicity_violation_count | significant_violation_count | max_adjacent_sigma68_increase_ns | sigma68_vs_bin_mid_corr |
| --- | --- | --- | --- | --- | --- | --- | --- |
| amplitude_bin | cnn1d | 4 | 3 | 3 | 1 | 0.796034 | 0.745673 |
| amplitude_bin | gradient_boosted_trees | 4 | 3 | 3 | 1 | 0.606907 | 0.820969 |
| amplitude_bin | mlp | 4 | 3 | 3 | 0 | 0.414387 | 0.946339 |
| amplitude_bin | phase_conformal_gated_cnn | 4 | 3 | 3 | 1 | 0.743609 | 0.748494 |
| amplitude_bin | ridge | 4 | 3 | 3 | 1 | 0.813245 | 0.982833 |
| amplitude_bin | traditional | 4 | 3 | 3 | 1 | 0.992859 | 0.98833 |
| charge_bin | cnn1d | 6 | 5 | 3 | 1 | 3.30853 | 0.909695 |
| charge_bin | gradient_boosted_trees | 6 | 5 | 4 | 1 | 2.92667 | 0.871073 |
| charge_bin | mlp | 6 | 5 | 5 | 1 | 3.95739 | 0.914682 |
| charge_bin | phase_conformal_gated_cnn | 6 | 5 | 4 | 0 | 2.12577 | 0.926707 |
| charge_bin | ridge | 6 | 5 | 5 | 0 | 4.87572 | 0.927896 |
| charge_bin | traditional | 6 | 5 | 4 | 1 | 4.71735 | 0.92471 |

The audit supports the caveat that amplitude/charge bins are not exchangeable energy slices. They are mixtures of changing electronics and morphology support.

## Absolute Time-Scale Closure

The timing scale is anchored by the S03a analytic timing reference before the uncertainty benchmark:

| method | value | ci_low | ci_high | n_pair_residuals | median_ns | sigma68_ns | full_rms_ns | tail_frac_abs_gt5ns | core_sigma_ns | chi2_ndf | best_candidate | best_alpha |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s02_template_phase_base | 2.88915 | 2.63915 | 3.27718 | 198 | -3.83043 | 2.88915 | 2.57669 | 0.0505051 | 0.442691 | 3.21363 | amp_only | 100 |
| s03a_analytic_timewalk | 1.49464 | 1.33645 | 1.62215 | 198 | 1.17923 | 1.49464 | 1.69913 | 0.00505051 | 1.26115 | 2.03718 | amp_only | 100 |

The geometry correction uses 2 cm downstream spacing and `v_TOF = 0.078 ns/cm`. Pair residuals remove common event clock terms but do not prove an external beamline absolute time-of-flight calibration. The defensible claim is therefore an internally anchored B-stack time scale suitable for pairwise resolution and interval calibration, not a standalone external TOF measurement.

## Systematics

The dominant systematic is support composition: amplitude and charge bins carry different fractions of saturation, q-template mismatch, baseline width, and anomaly/dropout atoms. The support/action composition table from nonduplicated traditional pair rows is:

| dimension | stratum | n_pair_residuals | n_runs | support_fraction | saturation_fraction | dropout_fraction | anomaly_noncommon_fraction | wide_baseline_fraction | high_q_template_fraction | any_action_band_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| amplitude_bin | amp_adc[1000,1500) | 256 | 7 | 0.0223386 | 0 | 0.046875 | 0.253906 | 0.660156 | 0.976562 | 0.976562 |
| amplitude_bin | amp_adc[1500,2500) | 3901 | 7 | 0.340401 | 0 | 0.00384517 | 0.0992053 | 0.374263 | 0.754166 | 0.758267 |
| amplitude_bin | amp_adc[2500,4000) | 6811 | 7 | 0.594328 | 0 | 0 | 0.0638673 | 0.239759 | 0.675084 | 0.679636 |
| amplitude_bin | amp_adc[4000,7000) | 492 | 7 | 0.0429319 | 0.0325203 | 0 | 0.115854 | 0.229675 | 0.715447 | 0.715447 |
| charge_bin | charge[1000,4000) | 60 | 7 | 0.0052356 | 0 | 0.0166667 | 1 | 0.05 | 1 | 1 |
| charge_bin | charge[4000,8000) | 285 | 7 | 0.0248691 | 0 | 0.0350877 | 0.708772 | 0.498246 | 1 | 1 |
| charge_bin | charge[8000,14000) | 1471 | 7 | 0.12836 | 0 | 0.00883753 | 0.242012 | 0.479266 | 0.872196 | 0.874915 |
| charge_bin | charge[14000,24000) | 5990 | 7 | 0.522688 | 0 | 0.000500835 | 0.0392321 | 0.2601 | 0.660601 | 0.665776 |
| charge_bin | charge[24000,40000) | 3624 | 7 | 0.31623 | 0.00331126 | 0 | 0.0229029 | 0.261589 | 0.697296 | 0.700607 |
| charge_bin | charge[40000,80000) | 30 | 6 | 0.0026178 | 0.133333 | 0 | 0.266667 | 0.633333 | 1 | 1 |

Sentinel controls are:

| sentinel | method | n | bias_ns | median_ns | sigma68_ns | full_rms_ns | tail_frac_abs_gt5ns | pull_width68 | coverage68 | coverage95 | coverage68_error | coverage95_error | calibration_ece | calibration_loss |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| amplitude_only | ridge_uncertainty_control | 11460 | 1.24417 | 1.49475 | 1.55109 | 2.66699 | 0.0191099 | 1.02596 | 0.465532 | 0.862216 | 0.217157 | 0.0877836 | 0.15247 | 0.120844 |
| topology_only | ridge_uncertainty_control | 11460 | 1.24417 | 1.49475 | 1.55109 | 2.66699 | 0.0191099 | 1.03123 | 0.533159 | 0.837435 | 0.149531 | 0.112565 | 0.136935 | 0.107566 |
| run_family_only | ridge_uncertainty_control | 11460 | 1.24417 | 1.49475 | 1.55109 | 2.66699 | 0.0191099 | 1.02452 | 0.461344 | 0.857941 | 0.221346 | 0.0920593 | 0.156703 | 0.123656 |
| shuffled_target | ridge_uncertainty_control | 11460 | 1.24417 | 1.49475 | 1.55109 | 2.66699 | 0.0191099 | 1.0285 | 0.468412 | 0.860471 | 0.214278 | 0.0895288 | 0.151903 | 0.121053 |

Leakage and bookkeeping checks are:

| check | value | pass | note |
| --- | --- | --- | --- |
| raw_root_reproduction_gate | 1 | true | reproduction_match_table.csv exact before modeling |
| required_methods_present | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional | true | traditional, ridge, GBT, MLP, 1D-CNN, and new phase-conformal gated CNN |
| uncertainty_train_eval_event_overlap | 0 | true | uncertainty layer leaves out the evaluated run |
| forbidden_feature_audit | 0 | true | uncertainty features exclude event id, raw residual, pull, sigma target, and held-out labels |
| s06b_required_action_columns | saturation_flag,q_template_bin,baseline_bin,p09_anomaly_class | true | support closure includes saturation, q-template, baseline, and anomaly/dropout atoms |
| s06b_required_methods_present | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional | true | traditional, ridge, GBT, MLP, 1D-CNN, and novel phase-conformal gated CNN |

## Caveats

- The current workspace lacks `torch`; this ticket does not retrain the neural networks. It reuses the committed S06b/P06c benchmark rows and independently reruns the raw ROOT reproduction gate.
- Charge is a waveform-area proxy, not an externally calibrated MeV energy. The S14 energy mapping remains a dependency for literal MeV-scale `sigma(E)`.
- Pair residuals share event-level conditions and two-stave correlations. Bootstrap intervals are run-block/event-paired but do not include alternate detector calibrations.
- Action labels are reduced waveform morphology flags, not exhaustive hand-scanned truth labels.
- The winner optimizes interval calibration, not only narrow central width. A model with smaller `sigma68_ns` but poor coverage is not adopted.

## Conclusion

The S06 winner is **phase_conformal_gated_cnn**. It gives the best calibrated held-out timing intervals among the strong traditional baseline, ridge, gradient-boosted trees, MLP, 1D-CNN, and the new phase-conformal gated CNN. The main physics conclusion is that a naive monotonic timing-resolution curve versus amplitude or charge-energy proxy is not stable without support conditioning. Downstream consumers should use support-conditioned interval estimates or explicit abstention/inflation bands rather than a single one-dimensional sigma(A) or sigma(E) correction.

## Reproducibility

Run:

```bash
. .venv/bin/activate
python scripts/issue_2378_s06_resolution_amplitude_energy_timescale.py
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `raw_root_counts_by_run.csv`, copied benchmark/support/leakage CSVs, and `pair_residual_rows_with_pulls.csv.gz`.
