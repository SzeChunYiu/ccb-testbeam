# S05j: Anomaly-tail covariance coverage stress

- **Ticket:** `1781044006.709.301620de`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** `/home/billy/ccb-data/extracted/root/root`
- **Frozen residual panel:** `reports/1781040960.767.247d3910__s05h_saturation_covariance_support_frontier`
- **No Monte Carlo:** raw HRD ROOT plus frozen leave-one-run-held-out data residuals

## Question

Do S05f covariance intervals remain calibrated when B2-local covariance corrections are stressed by anomaly taxa, timing-tail atoms, baseline contamination, saturation boundary, and two-pulse scores rather than only B2 topology?

## Abstract

This study rebuilds the raw `HRDv` reproduction anchors and the S05h support-coordinate table, then freezes the S05h leave-one-run-held-out residual panel.  The stress test asks whether conformal intervals and covariance contrasts remain calibrated when the data are sliced one pathology axis at a time: anomaly taxon, timing-tail/q-template atom, low-baseline contamination, B2 saturation boundary, and two-pulse/pile-up score.  The benchmark includes the required strong traditional comparators (`pair_median`, `traditional_s05d_static_priors`) and learned methods (`ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, and the new `support_gated_cnn_new`; `extra_trees_s05e_dynamic` is kept as the S05e dynamic-tree reference).  Splits are by run throughout, and confidence intervals use run-block bootstrap resampling.

The winner named in `result.json` is **extra_trees_s05e_dynamic**, selected by the smallest mean 95% stress-axis score `mean(abs coverage error) + 0.01 * mean interval width` among non-control methods.  Its mean absolute 95% coverage error is **0.0009**, worst stress-bin error **0.0041**, and mean interval width **35.072 ns**.

## Reproduction first

The raw ROOT gate was rebuilt before any stress scoring:

| quantity                             |     expected |   reproduced |       delta |   tolerance | pass   |
|:-------------------------------------|-------------:|-------------:|------------:|------------:|:-------|
| total_selected_b_pulses              | 640737       | 640737       | 0           |       0     | True   |
| sample_i_analysis_b_selected_pulses  | 252266       | 252266       | 0           |       0     | True   |
| sample_ii_analysis_b_selected_pulses | 125096       | 125096       | 0           |       0     | True   |
| sample_iv_a1_a3_pairs                |    127       |    127       | 0           |       0     | True   |
| sample_iv_a1_a3_robust_width_ns      |      1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |

## Stress axes

S05h support atoms are rederived from raw waveform features.  The axes are deliberately frozen before scoring: `timing_tail_atom` is the q-template-shift proxy tertile, `baseline_contamination` is the low pre-trigger baseline flag, `saturation_boundary` is the B2 saturation-depth bin, and `two_pulse_score` is the S05h pile-up-like proxy.  `anomaly_taxon` is a mutually exclusive summary that gives precedence to saturation, then timing-tail, baseline, and two-pulse-like atoms.

| axis                   | stratum                  |   n_pair_rows |   n_runs |   b2_fraction |
|:-----------------------|:-------------------------|--------------:|---------:|--------------:|
| anomaly_taxon          | baseline_contamination   |          3181 |       20 |      1        |
| anomaly_taxon          | common_support           |         33269 |       21 |      0.599567 |
| anomaly_taxon          | saturation_boundary      |         11976 |       21 |      1        |
| anomaly_taxon          | timing_tail_high_q_shift |         17051 |       21 |      0.518797 |
| anomaly_taxon          | two_pulse_like           |             7 |        5 |      0.857143 |
| timing_tail_atom       | high                     |         21828 |       21 |      0.624107 |
| timing_tail_atom       | low                      |         21828 |       21 |      0.682472 |
| timing_tail_atom       | mid                      |         21828 |       21 |      0.707165 |
| baseline_contamination | low_baseline             |          6608 |       21 |      1        |
| baseline_contamination | nominal_baseline         |         58876 |       21 |      0.63435  |
| saturation_boundary    | deep                     |          3417 |       21 |      1        |
| saturation_boundary    | mild                     |          5545 |       21 |      1        |
| saturation_boundary    | moderate                 |          3014 |       20 |      1        |
| saturation_boundary    | none                     |         53508 |       21 |      0.597668 |
| two_pulse_score        | not_pileup_like          |         54087 |       21 |      0.666075 |
| two_pulse_score        | pileup_like              |         11397 |       21 |      0.695797 |
| topology               | B2_containing            |         43956 |       21 |      1        |
| topology               | downstream_only          |         21528 |       21 |      0        |

## Methods and equations

For pair residual `r_i = (t_right - t_left) - TOF`, method `m` supplies frozen out-of-fold residual `e_i(m)=r_i-hat r_m(x_i)`.  For held-out run `k`, stress axis `a`, stratum `s`, and nominal coverage `q`, the calibration set is all rows from runs other than `k` in the same stratum when support is sufficient.  The interval center and half-width are

`c_maks = median(e_train)`,  
`h_maks(q) = Quantile_q(|e_train - c_maks|)`.

The held-out interval is `[c_maks - h_maks, c_maks + h_maks]`.  If a stress bin has fewer than `100` train rows or `3` train runs, the interval falls back to all non-held-out stress strata and that fallback fraction is reported.

The robust width is `W_68 = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.  For covariance, residuals are pivoted by `(run,event,pair)`.  The signed stress contrast is

`Delta C_m(a,s) = mean Cov_B2(e_p,e_q | a=s) - mean Cov_downstream(e_p,e_q | a=s)`.

When a downstream stratum is absent, the covariance table explicitly marks the same-run downstream fallback.

## Head-to-head residual stress metrics

Topology-split B2-containing overview:

| method                         | method_class   | axis     | stratum       |   n_pair_rows |   n_runs |   support_loss_fraction |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |
|:-------------------------------|:---------------|:---------|:--------------|--------------:|---------:|------------------------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|
| pair_median                    | traditional    | topology | B2_containing |         43956 |       21 |                0.328752 |      3.52628 |            18.7858  |              30.1252 |       24.8251 |              30.6636 |               39.8925 |                   0.202748 |
| traditional_s05d_static_priors | traditional    | topology | B2_containing |         43956 |       21 |                0.328752 |      7.91002 |             8.9197  |              11.0422 |       11.8129 |              13.3981 |               16.0027 |                   0.487078 |
| ridge                          | ml             | topology | B2_containing |         43956 |       21 |                0.328752 |      7.36964 |             8.37749 |              10.171  |       11.4123 |              12.6935 |               14.9712 |                   0.467718 |
| gradient_boosted_trees         | ml             | topology | B2_containing |         43956 |       21 |                0.328752 |      4.36747 |            10.0673  |              15.0401 |       14.8581 |              17.0355 |               21.713  |                   0.247111 |
| extra_trees_s05e_dynamic       | ml             | topology | B2_containing |         43956 |       21 |                0.328752 |      2.61107 |             4.97066 |               7.4093 |       10.3148 |              11.2041 |               14.5234 |                   0.209368 |
| mlp                            | ml             | topology | B2_containing |         43956 |       21 |                0.328752 |      4.94963 |            17.6851  |              28.4802 |       23.1877 |              27.792  |               37.9352 |                   0.284148 |
| cnn_1d                         | ml             | topology | B2_containing |         43956 |       21 |                0.328752 |      6.88546 |            18.9002  |              33.1267 |       24.6697 |              26.5945 |               38.9375 |                   0.399081 |
| support_gated_cnn_new          | ml             | topology | B2_containing |         43956 |       21 |                0.328752 |      5.72668 |            19.8047  |              31.4884 |       24.4825 |              30.1559 |               39.7966 |                   0.342866 |

Full per-axis residual metrics with sigma68, full RMS, tail fraction, and support loss are in `stress_residual_metrics.csv`.

## Interval coverage under pathology stress

Winner 95% interval stress summary:

| method                   | axis                   | stratum                  |   nominal_coverage |   n_runs |   n_pair_rows |   coverage |   coverage_ci_low |   coverage_ci_high |   coverage_error |   abs_coverage_error |   mean_interval_width_ns |   interval_width_ci_low_ns |   interval_width_ci_high_ns |   fallback_fraction |
|:-------------------------|:-----------------------|:-------------------------|-------------------:|---------:|--------------:|-----------:|------------------:|-------------------:|-----------------:|---------------------:|-------------------------:|---------------------------:|----------------------------:|--------------------:|
| extra_trees_s05e_dynamic | anomaly_taxon          | baseline_contamination   |               0.95 |       11 |          3119 |   0.953511 |          0.945736 |           0.962063 |      0.00351074  |          0.00351074  |                  5.28869 |                    5.22754 |                     5.35206 |                   0 |
| extra_trees_s05e_dynamic | anomaly_taxon          | common_support           |               0.95 |       20 |         33264 |   0.951269 |          0.92846  |           0.969325 |      0.00126864  |          0.00126864  |                  9.69634 |                    8.9364  |                    10.3196  |                   0 |
| extra_trees_s05e_dynamic | anomaly_taxon          | saturation_boundary      |               0.95 |       20 |         11970 |   0.949541 |          0.938866 |           0.958097 |     -0.000459482 |          0.000459482 |                 50.5416  |                   50.3253  |                    50.7426  |                   0 |
| extra_trees_s05e_dynamic | anomaly_taxon          | timing_tail_high_q_shift |               0.95 |       20 |         17049 |   0.95073  |          0.928433 |           0.963614 |      0.000730248 |          0.000730248 |                 47.9734  |                   45.3283  |                    49.5479  |                   0 |
| extra_trees_s05e_dynamic | baseline_contamination | low_baseline             |               0.95 |       18 |          6590 |   0.950986 |          0.921692 |           0.966022 |      0.000986343 |          0.000986343 |                 28.3418  |                   27.1653  |                    28.8634  |                   0 |
| extra_trees_s05e_dynamic | baseline_contamination | nominal_baseline         |               0.95 |       20 |         58865 |   0.949885 |          0.915606 |           0.966488 |     -0.000114669 |          0.000114669 |                 34.9541  |                   33.2567  |                    36.2761  |                   0 |
| extra_trees_s05e_dynamic | saturation_boundary    | deep                     |               0.95 |       20 |          3412 |   0.949297 |          0.937461 |           0.960271 |     -0.0007034   |          0.0007034   |                 44.2847  |                   43.8267  |                    44.6428  |                   0 |
| extra_trees_s05e_dynamic | saturation_boundary    | mild                     |               0.95 |       19 |          5527 |   0.949882 |          0.930251 |           0.967072 |     -0.000117604 |          0.000117604 |                 54.3118  |                   53.0461  |                    55.3692  |                   0 |
| extra_trees_s05e_dynamic | saturation_boundary    | moderate                 |               0.95 |       19 |          3001 |   0.950017 |          0.932295 |           0.961122 |      1.66611e-05 |          1.66611e-05 |                 50.6413  |                   50.376   |                    50.9027  |                   0 |
| extra_trees_s05e_dynamic | saturation_boundary    | none                     |               0.95 |       20 |         53501 |   0.950898 |          0.933924 |           0.963202 |      0.000898114 |          0.000898114 |                 21.1341  |                   20.1936  |                    21.9949  |                   0 |
| extra_trees_s05e_dynamic | timing_tail_atom       | high                     |               0.95 |       20 |         21825 |   0.950561 |          0.93888  |           0.963599 |      0.000561283 |          0.000561283 |                 54.7186  |                   53.8196  |                    55.8198  |                   0 |
| extra_trees_s05e_dynamic | timing_tail_atom       | low                      |               0.95 |       20 |         21822 |   0.950005 |          0.933819 |           0.963476 |      4.58253e-06 |          4.58253e-06 |                 14.1059  |                   13.718   |                    14.4805  |                   0 |
| extra_trees_s05e_dynamic | timing_tail_atom       | mid                      |               0.95 |       20 |         21824 |   0.945931 |          0.90506  |           0.981959 |     -0.00406891  |          0.00406891  |                 26.9579  |                   22.3703  |                    30.7554  |                   0 |
| extra_trees_s05e_dynamic | two_pulse_score        | not_pileup_like          |               0.95 |       20 |         54077 |   0.948832 |          0.921612 |           0.968737 |     -0.00116778  |          0.00116778  |                 20.1543  |                   18.2491  |                    21.6234  |                   0 |
| extra_trees_s05e_dynamic | two_pulse_score        | pileup_like              |               0.95 |       20 |         11394 |   0.949798 |          0.939517 |           0.958536 |     -0.000201861 |          0.000201861 |                 78.078   |                   77.3788  |                    78.5918  |                   0 |

All per-run interval rows are in `interval_coverage_by_run.csv`; all summaries are in `interval_coverage_summary.csv`.

## Covariance stress

Winner covariance stress rows:

|   b2_signed_cov_ns2 |   downstream_signed_cov_ns2 |   b2_minus_downstream_cov_ns2 |   b2_mean_abs_cov_ns2 |   downstream_mean_abs_cov_ns2 |   b2_minus_downstream_abs_cov_ns2 |   inferred_correlated_fraction | method                   | axis                   | stratum                  |   n_b2_pair_rows |   n_downstream_pair_rows |   n_b2_runs |   n_downstream_runs | control_mode                  |   delta_ci_low_ns2 |   delta_ci_high_ns2 | interval_excludes_zero   |
|--------------------:|----------------------------:|------------------------------:|----------------------:|------------------------------:|----------------------------------:|-------------------------------:|:-------------------------|:-----------------------|:-------------------------|-----------------:|-------------------------:|------------:|--------------------:|:------------------------------|-------------------:|--------------------:|:-------------------------|
|             12.6675 |                    15.9522  |                      -3.28472 |               12.7297 |                      16.1774  |                          -3.44777 |                      -0.259304 | extra_trees_s05e_dynamic | anomaly_taxon          | baseline_contamination   |             3181 |                    21525 |          20 |                  20 | fallback_same_runs_downstream |          -10.1795  |             24.6584 | False                    |
|             15.073  |                     1.38755 |                      13.6855  |               15.2352 |                       1.67742 |                          13.5577  |                       0.907945 | extra_trees_s05e_dynamic | anomaly_taxon          | common_support           |            19947 |                    13322 |          21 |                  21 | same_axis_stratum_downstream  |            8.44267 |             18.7382 | True                     |
|             85.0987 |                    15.9522  |                      69.1465  |               86.3215 |                      16.1774  |                          70.144   |                       0.812545 | extra_trees_s05e_dynamic | anomaly_taxon          | saturation_boundary      |            11976 |                    21528 |          21 |                  21 | fallback_same_runs_downstream |           49.9623  |             82.3517 | True                     |
|            331.366  |                    25.0606  |                     306.305   |              331.381  |                      25.8524  |                         305.528   |                       0.924372 | extra_trees_s05e_dynamic | anomaly_taxon          | timing_tail_high_q_shift |             8846 |                     8205 |          21 |                  20 | same_axis_stratum_downstream  |          229.795   |            459.689  | True                     |
|            214.515  |                    25.0606  |                     189.454   |              215.788  |                      25.8524  |                         189.936   |                       0.883175 | extra_trees_s05e_dynamic | timing_tail_atom       | high                     |            13623 |                     8205 |          21 |                  20 | same_axis_stratum_downstream  |          103.361   |            256.621  | True                     |
|             13.3336 |                     1.20141 |                      12.1322  |               13.3336 |                       1.41201 |                          11.9216  |                       0.909896 | extra_trees_s05e_dynamic | timing_tail_atom       | low                      |            14897 |                     6931 |          21 |                  21 | same_axis_stratum_downstream  |            8.39162 |             17.5777 | True                     |
|             34.1529 |                     2.51888 |                      31.634   |               34.1529 |                       2.79088 |                          31.362   |                       0.926247 | extra_trees_s05e_dynamic | timing_tail_atom       | mid                      |            15436 |                     6392 |          21 |                  20 | same_axis_stratum_downstream  |           20.9854  |             47.7881 | True                     |
|             60.6828 |                    15.9522  |                      44.7306  |               60.9475 |                      16.1774  |                          44.77    |                       0.737122 | extra_trees_s05e_dynamic | baseline_contamination | low_baseline             |             6608 |                    21528 |          21 |                  21 | fallback_same_runs_downstream |            7.99551 |             75.9832 | True                     |
|            123.105  |                    15.9522  |                     107.153   |              124.163  |                      16.1774  |                         107.986   |                       0.870418 | extra_trees_s05e_dynamic | baseline_contamination | nominal_baseline         |            37348 |                    21528 |          21 |                  21 | same_axis_stratum_downstream  |           77.9564  |            145.522  | True                     |
|             83.6834 |                    15.9522  |                      67.7312  |               85.4247 |                      16.1774  |                          69.2473  |                       0.809374 | extra_trees_s05e_dynamic | saturation_boundary    | deep                     |             3417 |                    21528 |          21 |                  21 | fallback_same_runs_downstream |           42.6721  |             88.9316 | True                     |
|            117.75   |                    15.9522  |                     101.797   |              118.35   |                      16.1774  |                         102.173   |                       0.864525 | extra_trees_s05e_dynamic | saturation_boundary    | mild                     |             5545 |                    21528 |          21 |                  21 | fallback_same_runs_downstream |           54.7364  |            159.066  | True                     |
|             67.7543 |                    15.9522  |                      51.8021  |               86.0335 |                      16.1774  |                          69.8561  |                       0.764558 | extra_trees_s05e_dynamic | saturation_boundary    | moderate                 |             3014 |                    21525 |          20 |                  20 | fallback_same_runs_downstream |           16.6287  |             93.9269 | True                     |
|            163.306  |                    15.9522  |                     147.354   |              163.306  |                      16.1774  |                         147.128   |                       0.902317 | extra_trees_s05e_dynamic | saturation_boundary    | none                     |            31980 |                    21528 |          21 |                  21 | same_axis_stratum_downstream  |          118.677   |            242.165  | True                     |
|             35.5146 |                     2.12318 |                      33.3914  |               35.5146 |                       2.393   |                          33.1216  |                       0.940217 | extra_trees_s05e_dynamic | two_pulse_score        | not_pileup_like          |            36026 |                    18061 |          21 |                  21 | same_axis_stratum_downstream  |           24.5381  |             44.5149 | True                     |
|            254.994  |                    32.6201  |                     222.374   |              256.925  |                      35.0261  |                         221.898   |                       0.872075 | extra_trees_s05e_dynamic | two_pulse_score        | pileup_like              |             7930 |                     3467 |          21 |                  20 | same_axis_stratum_downstream  |          152.751   |            288.68   | True                     |
|            118.093  |                    15.9522  |                     102.141   |              118.798  |                      16.1774  |                         102.621   |                       0.864918 | extra_trees_s05e_dynamic | topology               | all                      |            43956 |                    21528 |          21 |                  21 | same_axis_stratum_downstream  |           70.6059  |            130.613  | True                     |

The table records signed B2-containing minus downstream covariance, mean absolute covariance, inferred correlated fraction, support counts, and bootstrap CIs.  Fallback rows are not interpreted as matched downstream controls; they are systematic sentinels for axes where downstream-only events cannot occupy the B2-local category.

## Winner scoring

| method                         |   mean_abs_coverage_error_95 |   worst_abs_coverage_error_95 |   mean_interval_width_ns |   mean_abs_cov_delta_ns2 |   winner_score |
|:-------------------------------|-----------------------------:|------------------------------:|-------------------------:|-------------------------:|---------------:|
| extra_trees_s05e_dynamic       |                  0.00094214  |                    0.00406891 |                  35.0721 |                  93.4651 |       0.351663 |
| ridge                          |                  0.000935144 |                    0.00231589 |                  43.4787 |                  93.5077 |       0.435722 |
| traditional_s05d_static_priors |                  0.00113163  |                    0.00568581 |                  46.1819 |                 108.812  |       0.46295  |
| gradient_boosted_trees         |                  0.00105438  |                    0.00364878 |                  54.8837 |                 205.824  |       0.549892 |
| mlp                            |                  0.00415935  |                    0.0198942  |                  98.645  |                 651.106  |       0.99061  |
| pair_median                    |                  0.00149994  |                    0.00429802 |                 104.446  |                 735.034  |       1.04596  |
| support_gated_cnn_new          |                  0.0049499   |                    0.0429785  |                 104.13   |                 724.172  |       1.04625  |
| cnn_1d                         |                  0.0101891   |                    0.0491405  |                 104.868  |                 731.303  |       1.05887  |

Controls (`waveform_only_mlp`, `pool_label_control`, `ml_shuffled_target_control`) are scored in the artifact tables but excluded from winner selection.

## Systematics and caveats

The anomaly taxa are support-coordinate taxa, not hand-scanned P09 gallery labels.  The timing-tail axis is a q-template-shift proxy from late charge and peak displacement; it should be read as a stress coordinate for waveform shape, not an absolute template-quality measurement.  The two-pulse score is the S05h pile-up-like proxy, so it cannot by itself prove two physical pulses.  Saturation strata above `none` have weak or absent exact downstream-only analogues; fallback covariance rows are therefore conservative diagnostics rather than matched estimates.

The neural models are inherited from the frozen S05h laptop budget.  Their poor stress performance is a reproducible benchmark result under that budget, not a proof that larger neural architectures cannot improve.  Because calibration uses observed held-out residuals, good interval coverage can coexist with wide intervals and poor covariance reduction; this is why the result reports width, sigma68, full RMS, covariance, support loss, and control behavior together.

## Conclusion

S05j confirms the S05h/S05i pattern under pathology stress: interval calibration can remain near nominal, but the price is large B2-local interval width and residual covariance in timing-tail, saturation, and two-pulse-like atoms.  The named winner is the best calibrated stress benchmark method under the declared score, while the caveated covariance rows identify the remaining systematics that downstream timing and PID consumers should either veto or propagate.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `stress_axis_counts.csv`, `stress_residual_metrics.csv`, `interval_coverage_by_run.csv`, `interval_coverage_summary.csv`, `covariance_stress_summary.csv`, `winner_score_table.csv`, `bstack_pair_features.csv.gz`, and PNG diagnostics are in this folder.
