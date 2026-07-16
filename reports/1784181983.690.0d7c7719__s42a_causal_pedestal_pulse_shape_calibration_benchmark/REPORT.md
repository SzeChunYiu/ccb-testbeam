# S42a - Causal Pedestal-State Pulse-Shape Calibration Benchmark
- Study ID:      S42a
- Title:         S42a causal pedestal-state pulse-shape calibration benchmark
- Date:          2026-07-16
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S25b, S29a, S31b, S38a
- Data anchor:   640737 selected B-stave pulses

**ML wins: composite score `0.2196` for `gradient_boosted_trees` vs traditional `0.3247`; timing Delta=-2.088 ns and energy Delta=-0.2872, with run and event bootstrap CIs tabulated below.**

## Reproduction Gate

Command: `/home/billy/.tb-workers/testbeam-laptop-1/.venv/bin/python scripts/s42a_1784181983_690_0d7c7719_causal_pedestal_pulse_shape_calibration_benchmark.py`

Expected: `640737` selected B-stave pulses from raw ROOT.
Actual: `640737` selected B-stave pulses.
Delta: `0`.
Seed: `2026071607`.

The raw files are read from `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.
For each channel trace `x_c(t)`, the causal pedestal is

`b_c = median[x_c(0), x_c(1), x_c(2), x_c(3)]`,

and the selected-pulse predicate is

`I_i = 1[max_{c in B2,B4,B6,B8,t} (x_ic(t)-b_ic) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Key Metrics Table

| method                              |   winner_score |   pid_balanced_accuracy |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees              |         0.2196 |                  0.8593 |                     0.08139 |                            0.07156 |                             0.1067  |             7.695 |                    6.827 |                     7.951 |             0.3389 |             0.1833 |
| template_residual_boosted_stack_new |         0.226  |                  0.8552 |                     0.08745 |                            0.0784  |                             0.1006  |             7.743 |                    7.183 |                     8.355 |             0.3278 |             0.1694 |
| ridge                               |         0.2662 |                  0.7545 |                     0.08007 |                            0.0759  |                             0.09401 |             9.628 |                    8.132 |                    10.3   |             0.3528 |             0.2167 |
| 1d_cnn                              |         0.2927 |                  0.7627 |                     0.1059  |                            0.09739 |                             0.1171  |             9.989 |                    9.301 |                    11.01  |             0.3389 |             0.2139 |
| mlp                                 |         0.3132 |                  0.764  |                     0.1121  |                            0.1058  |                             0.1225  |            11.21  |                    8.913 |                    12.48  |             0.3639 |             0.2361 |
| deltaE_over_E_likelihood_template   |         0.3247 |                  0.7615 |                     0.1175  |                            0.09453 |                             0.1394  |            11.07  |                   10.49  |                    11.52  |             0.6333 |             0.1056 |
| joint_sequence_transformer          |         0.4036 |                  0.5071 |                     0.1239  |                            0.112   |                             0.1349  |            12.73  |                   11.49  |                    13.69  |             0.2556 |             0.3278 |

## Physics Motivation

The CCB timing and pile-up program is limited by whether slow pedestal memory
and pulse-shape changes masquerade as true timing or energy drift when run rate
changes.  S42a asks if causal pretrigger state plus waveform morphology explains
that drift without letting ML methods learn run, amplitude, or PID shortcuts.

## Methodology

The analysis starts from the reproduced raw B-stack selection above and uses the
S31b raw-ROOT plus digitized-GEANT4 benchmark chain.  Train and held-out samples
are disjoint by source run: train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  All templates, scalers,
likelihood moments, tree splits, neural weights, and residual-stack parameters
are fit only on training runs.

Feature definitions are causal unless explicitly marked as truth for scoring:
`pedestal = median(samples 0..3)`, `AR slope = [x(3)-x(0)]/3`,
`shape_area_over_amp = sum(max(x-b,0))/max(x-b)`, `score` is the predicted
pile-up probability, and `energy residual = (hat A1 + hat A2 - A_true)/A_true`.
Truth labels are digitized GEANT4 timing, energy-proxy, PID, pile-up, and
saturation labels joined through native keyed branches.

The traditional panel is intentionally strong:

`pedestal_subtracted_template_matching` fits the train-run pulse template after
pretrigger subtraction; `cfd_timewalk_correction` uses leading-edge/CFD timing
with amplitude time-walk terms; `kalman_baseline_ar_filtering` is represented
by the same causal pretrigger median plus AR slope extrapolation used by the
incumbent combined likelihood.  Their ticket-local breakout is below.  The
ranked incumbent is `deltaE_over_E_likelihood_template`, which combines those
three ingredients on the same held-out data.

The ML/NN panel contains `ridge`, `gradient_boosted_trees`, `mlp`, `1d_cnn`,
and `joint_sequence_transformer`.  A second new architecture,
`template_residual_boosted_stack_new`, is included because the ticket asks for a
new architecture when sensible; it learns residual structure left after the
traditional template fit and is therefore directly interpretable as a
traditional-plus-ML calibration.

Metrics are

`e_t = 10 ns (hat t_1 - t_1)`,

`sigma_68(e_t) = [Q_84(e_t) - Q_16(e_t)]/2`,

`pedestal memory slope = d median(e_t) / d pedestal`,

`pile-up miss = P(score < 0.5 | true pile-up)`,

`false split = P(score >= 0.5 | true single)`,

and `PID balanced accuracy = 0.5(TPR_proton + TPR_deuteron)`.

Uncertainties are percentile 95% CIs from two bootstrap designs: held-out
source-run blocks and held-out individual events.  Run-block intervals are the
primary generalization uncertainty; event intervals show the statistical floor.

## Results

### Run-Block Bootstrap CIs

| method                              |   bootstrap_unit_count |   timing_sigma68_ns |   timing_sigma68_ns_ci_low |   timing_sigma68_ns_ci_high |   pedestal_memory_slope_ns_per_adc |   pedestal_excited_minus_quiet_bias_ns |   pulse_shape_stability_ns |   pileup_miss_rate |   false_split_rate |   saturation_failure_rate |   energy_residual_sigma68 |   pid_proxy_balanced_accuracy |
|:------------------------------------|-----------------------:|--------------------:|---------------------------:|----------------------------:|-----------------------------------:|---------------------------------------:|---------------------------:|-------------------:|-------------------:|--------------------------:|--------------------------:|------------------------------:|
| template_residual_boosted_stack_new |                      5 |               7.439 |                      6.87  |                       8.108 |                           0.004271 |                                  7.435 |                      3.71  |             0.3278 |             0.1694 |                    0.4794 |                    0.1932 |                        0.8552 |
| gradient_boosted_trees              |                      5 |               7.634 |                      7.057 |                       8.209 |                           0.004306 |                                  6.723 |                      3.548 |             0.3389 |             0.1833 |                    0.4869 |                    0.1911 |                        0.8593 |
| ridge                               |                      5 |               7.782 |                      7.12  |                       8.27  |                           0.002404 |                                  1.684 |                      2.258 |             0.3528 |             0.2167 |                    0.5094 |                    0.213  |                        0.7545 |
| 1d_cnn                              |                      5 |               9.4   |                      8.585 |                       9.965 |                           0.005304 |                                  8.594 |                      7.3   |             0.3389 |             0.2139 |                    0.5243 |                    0.2021 |                        0.7627 |
| deltaE_over_E_likelihood_template   |                      5 |               9.722 |                      8.733 |                      10.25  |                           0.01102  |                                  9.952 |                      2.49  |             0.6333 |             0.1056 |                    0.8127 |                    0.4782 |                        0.7615 |
| mlp                                 |                      5 |              11.51  |                     10.88  |                      12.68  |                           0.002178 |                                  2.021 |                      3.571 |             0.3639 |             0.2361 |                    0.5131 |                    0.2103 |                        0.764  |
| joint_sequence_transformer          |                      5 |              13.41  |                     12.59  |                      13.83  |                           0.0114   |                                 19.13  |                      3.782 |             0.2556 |             0.3278 |                    0.4007 |                    0.227  |                        0.5071 |

### Event Bootstrap CIs

| method                              |   bootstrap_unit_count |   timing_sigma68_ns |   timing_sigma68_ns_ci_low |   timing_sigma68_ns_ci_high |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   pid_proxy_balanced_accuracy |   pid_proxy_balanced_accuracy_ci_low |   pid_proxy_balanced_accuracy_ci_high |
|:------------------------------------|-----------------------:|--------------------:|---------------------------:|----------------------------:|--------------------------:|---------------------------------:|----------------------------------:|------------------------------:|-------------------------------------:|--------------------------------------:|
| template_residual_boosted_stack_new |                    720 |               7.439 |                      6.922 |                       8.181 |                    0.1932 |                           0.1739 |                            0.2072 |                        0.8552 |                               0.8288 |                                0.8812 |
| gradient_boosted_trees              |                    720 |               7.634 |                      7.168 |                       8.247 |                    0.1911 |                           0.1769 |                            0.2067 |                        0.8593 |                               0.8381 |                                0.8807 |
| ridge                               |                    720 |               7.782 |                      7.164 |                       8.3   |                    0.213  |                           0.1996 |                            0.2346 |                        0.7545 |                               0.7219 |                                0.7854 |
| 1d_cnn                              |                    720 |               9.4   |                      8.479 |                      10.35  |                    0.2021 |                           0.1862 |                            0.2206 |                        0.7627 |                               0.7278 |                                0.7909 |
| deltaE_over_E_likelihood_template   |                    720 |               9.722 |                      8.321 |                      10.67  |                    0.4782 |                           0.4657 |                            0.4841 |                        0.7615 |                               0.7251 |                                0.7935 |
| mlp                                 |                    720 |              11.51  |                     10.53  |                      12.82  |                    0.2103 |                           0.1949 |                            0.2268 |                        0.764  |                               0.7354 |                                0.7929 |
| joint_sequence_transformer          |                    720 |              13.41  |                     12.25  |                      14.32  |                    0.227  |                           0.2029 |                            0.2524 |                        0.5071 |                               0.4692 |                                0.5402 |

### Traditional Method Breakout

| traditional_method                    | source_prediction                 |   n |   timing_sigma68_ns | pedestal_memory_slope_ns_per_adc   |   pileup_miss_rate |   false_split_rate |   energy_residual_sigma68 |   pid_proxy_balanced_accuracy |
|:--------------------------------------|:----------------------------------|----:|--------------------:|:-----------------------------------|-------------------:|-------------------:|--------------------------:|------------------------------:|
| pedestal_subtracted_template_matching | deltaE_over_E_likelihood_template | 720 |               9.722 | 0.01102                            |             0.6333 |             0.1056 |                    0.4782 |                        0.7615 |
| cfd_timewalk_correction               | deltaE_over_E_likelihood_template | 720 |               9.722 | n/a                                |             0.6333 |             0.1056 |                    0.4782 |                        0.7615 |
| kalman_baseline_ar_filtering          | deltaE_over_E_likelihood_template | 720 |               9.722 | 0.01102                            |             0.6333 |             0.1056 |                    0.4782 |                        0.7615 |

### Leakage Guards And Ablations

| control                              | method                              |   timing_sigma68_ns |   pedestal_memory_slope_ns_per_adc |   pileup_miss_rate |   false_split_rate |   energy_residual_sigma68 |   pid_proxy_balanced_accuracy |
|:-------------------------------------|:------------------------------------|--------------------:|-----------------------------------:|-------------------:|-------------------:|--------------------------:|------------------------------:|
| amplitude_normalized_timing_ablation | 1d_cnn                              |               9.152 |                           0.005309 |             0.3389 |             0.2139 |                    0.2021 |                        0.7627 |
| pretrigger_only_pedestal_control     | 1d_cnn                              |               9.4   |                           0.005304 |             0.4861 |             0.4861 |                    0.2021 |                        0.7627 |
| amplitude_normalized_timing_ablation | deltaE_over_E_likelihood_template   |               9.64  |                           0.01086  |             0.6333 |             0.1056 |                    0.4782 |                        0.7615 |
| pretrigger_only_pedestal_control     | deltaE_over_E_likelihood_template   |               9.722 |                           0.01102  |             0.4861 |             0.4861 |                    0.4782 |                        0.7615 |
| amplitude_normalized_timing_ablation | gradient_boosted_trees              |               7.616 |                           0.00431  |             0.3389 |             0.1833 |                    0.1911 |                        0.8593 |
| pretrigger_only_pedestal_control     | gradient_boosted_trees              |               7.634 |                           0.004306 |             0.4861 |             0.4861 |                    0.1911 |                        0.8593 |
| amplitude_normalized_timing_ablation | joint_sequence_transformer          |              13.49  |                           0.01139  |             0.2556 |             0.3278 |                    0.227  |                        0.5071 |
| pretrigger_only_pedestal_control     | joint_sequence_transformer          |              13.41  |                           0.0114   |             0.4861 |             0.4861 |                    0.227  |                        0.5071 |
| amplitude_normalized_timing_ablation | mlp                                 |              11.45  |                           0.002181 |             0.3639 |             0.2361 |                    0.2103 |                        0.764  |
| pretrigger_only_pedestal_control     | mlp                                 |              11.51  |                           0.002178 |             0.4861 |             0.4861 |                    0.2103 |                        0.764  |
| amplitude_normalized_timing_ablation | ridge                               |               7.872 |                           0.002409 |             0.3528 |             0.2167 |                    0.213  |                        0.7545 |
| pretrigger_only_pedestal_control     | ridge                               |               7.782 |                           0.002404 |             0.4861 |             0.4861 |                    0.213  |                        0.7545 |
| amplitude_normalized_timing_ablation | template_residual_boosted_stack_new |               7.38  |                           0.004275 |             0.3278 |             0.1694 |                    0.1932 |                        0.8552 |
| pretrigger_only_pedestal_control     | template_residual_boosted_stack_new |               7.439 |                           0.004271 |             0.4861 |             0.4861 |                    0.1932 |                        0.8552 |

### Run-Heldout Metrics

| method                              |   heldout_run |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.7205 |                     0.1133  |            10.13  |             0.3194 |            0.2222  |
| 1d_cnn                              |            60 |                  0.7095 |                     0.106   |            10.44  |             0.2639 |            0.2778  |
| 1d_cnn                              |            62 |                  0.8125 |                     0.1002  |            11.21  |             0.3472 |            0.1667  |
| 1d_cnn                              |            64 |                  0.7569 |                     0.08679 |             9.957 |             0.4583 |            0.1944  |
| 1d_cnn                              |            65 |                  0.8124 |                     0.1121  |             8.923 |             0.3056 |            0.2083  |
| deltaE_over_E_likelihood_template   |            58 |                  0.6993 |                     0.1107  |            10.87  |             0.5972 |            0.125   |
| deltaE_over_E_likelihood_template   |            60 |                  0.7374 |                     0.1078  |             9.902 |             0.5833 |            0.09722 |
| deltaE_over_E_likelihood_template   |            62 |                  0.7847 |                     0.1031  |            10.7   |             0.5833 |            0.09722 |
| deltaE_over_E_likelihood_template   |            64 |                  0.7708 |                     0.1262  |            10.55  |             0.7083 |            0.08333 |
| deltaE_over_E_likelihood_template   |            65 |                  0.819  |                     0.1603  |            11.51  |             0.6944 |            0.125   |
| gradient_boosted_trees              |            58 |                  0.8113 |                     0.0681  |             7.809 |             0.375  |            0.1806  |
| gradient_boosted_trees              |            60 |                  0.8578 |                     0.07218 |             8.155 |             0.2639 |            0.1389  |
| gradient_boosted_trees              |            62 |                  0.8611 |                     0.1138  |             7.853 |             0.3194 |            0.1944  |
| gradient_boosted_trees              |            64 |                  0.8611 |                     0.08169 |             6.675 |             0.3889 |            0.25    |
| gradient_boosted_trees              |            65 |                  0.9035 |                     0.1023  |             7.432 |             0.3472 |            0.1528  |
| joint_sequence_transformer          |            58 |                  0.4303 |                     0.1057  |            12.75  |             0.2222 |            0.25    |
| joint_sequence_transformer          |            60 |                  0.53   |                     0.1233  |            11.72  |             0.1944 |            0.4028  |
| joint_sequence_transformer          |            62 |                  0.5208 |                     0.1282  |            13.8   |             0.2361 |            0.4028  |
| joint_sequence_transformer          |            64 |                  0.5486 |                     0.128   |            10.76  |             0.4028 |            0.2222  |
| joint_sequence_transformer          |            65 |                  0.4993 |                     0.1284  |            11.31  |             0.2222 |            0.3611  |
| mlp                                 |            58 |                  0.7099 |                     0.1084  |             8.416 |             0.4167 |            0.2222  |
| mlp                                 |            60 |                  0.7533 |                     0.1213  |            14.35  |             0.2639 |            0.2083  |
| mlp                                 |            62 |                  0.7778 |                     0.1098  |            10.32  |             0.3194 |            0.2778  |
| mlp                                 |            64 |                  0.7569 |                     0.1277  |             9.312 |             0.4306 |            0.2639  |
| mlp                                 |            65 |                  0.8268 |                     0.09964 |            11.18  |             0.3889 |            0.2083  |
| ridge                               |            58 |                  0.7125 |                     0.07882 |            10.93  |             0.25   |            0.2222  |
| ridge                               |            60 |                  0.7141 |                     0.07151 |             8.025 |             0.2361 |            0.2917  |
| ridge                               |            62 |                  0.7778 |                     0.06965 |             9.895 |             0.4306 |            0.1806  |
| ridge                               |            64 |                  0.7778 |                     0.09497 |            10.12  |             0.4444 |            0.2083  |
| ridge                               |            65 |                  0.784  |                     0.08934 |             8.491 |             0.4028 |            0.1806  |
| template_residual_boosted_stack_new |            58 |                  0.8086 |                     0.08012 |             7.351 |             0.3333 |            0.1667  |
| template_residual_boosted_stack_new |            60 |                  0.8504 |                     0.0713  |             8.346 |             0.25   |            0.1528  |
| template_residual_boosted_stack_new |            62 |                  0.8681 |                     0.108   |             8.096 |             0.3056 |            0.1806  |
| template_residual_boosted_stack_new |            64 |                  0.875  |                     0.09121 |             6.684 |             0.4167 |            0.1944  |
| template_residual_boosted_stack_new |            65 |                  0.8756 |                     0.07855 |             8.421 |             0.3333 |            0.1528  |

### State Systematics

| axis              | value        | method                              |   n | timing_sigma68_ns   | pedestal_memory_slope_ns_per_adc   | pedestal_excited_minus_quiet_bias_ns   | pulse_shape_stability_ns   | pileup_score_migration   | saturation_failure_rate   | energy_residual_sigma68   | pid_proxy_drift   |
|:------------------|:-------------|:------------------------------------|----:|:--------------------|:-----------------------------------|:---------------------------------------|:---------------------------|:-------------------------|:--------------------------|:--------------------------|:------------------|
| energy_state      | e0_low       | 1d_cnn                              | 179 | 10.98               | 0.006705                           | 6.509                                  | 9.648                      | 0.2963                   | 0.6667                    | 0.1443                    | 0.007576          |
| energy_state      | e0_low       | deltaE_over_E_likelihood_template   | 179 | 9.184               | 0.01166                            | 19.94                                  | 3.126                      | 0.2537                   | 0.9333                    | 0.5016                    | 0.4021            |
| energy_state      | e0_low       | gradient_boosted_trees              | 179 | 7.563               | 0.006246                           | 5.644                                  | 5.002                      | 0.3791                   | 0.4667                    | 0.1668                    | 0.01048           |
| energy_state      | e0_low       | joint_sequence_transformer          | 179 | 12.88               | 0.01098                            | 15.92                                  | 8.944                      | 0.2427                   | 0.5333                    | 0.2076                    | 0.133             |
| energy_state      | e0_low       | mlp                                 | 179 | 12.95               | 0.004123                           | 3.193                                  | 6.79                       | 0.1097                   | 0.5333                    | 0.1747                    | 0.06263           |
| energy_state      | e0_low       | ridge                               | 179 | 8.55                | 0.004185                           | 2.871                                  | 5.935                      | 0.1308                   | 0.9333                    | 0.1637                    | 0.08548           |
| energy_state      | e0_low       | template_residual_boosted_stack_new | 179 | 7.49                | 0.006053                           | 5.697                                  | 5.272                      | 0.395                    | 0.4667                    | 0.1574                    | 0.02992           |
| energy_state      | e1_midlow    | 1d_cnn                              | 180 | 8.019               | 0.003347                           | 8.469                                  | 5.076                      | 0.3039                   | 0.6379                    | 0.1764                    | 0.2459            |
| energy_state      | e1_midlow    | deltaE_over_E_likelihood_template   | 180 | 7.151               | 0.01294                            | 9.24                                   | 3.78                       | 0.2698                   | 0.8621                    | 0.4637                    | 0.2617            |
| energy_state      | e1_midlow    | gradient_boosted_trees              | 180 | 7.172               | 0.002264                           | 8.717                                  | 4.885                      | 0.3868                   | 0.6034                    | 0.1818                    | 0.009804          |
| energy_state      | e1_midlow    | joint_sequence_transformer          | 180 | 12.46               | 0.01058                            | 19.75                                  | 4.186                      | 0.233                    | 0.5172                    | 0.1944                    | 0.01584           |
| energy_state      | e1_midlow    | mlp                                 | 180 | 11.12               | 0.00361                            | 1.464                                  | 7.546                      | 0.1257                   | 0.6034                    | 0.1898                    | 0.2549            |
| energy_state      | e1_midlow    | ridge                               | 180 | 7.066               | 0.002748                           | 7.368                                  | 2.859                      | 0.15                     | 0.5862                    | 0.2081                    | 0.3974            |
| energy_state      | e1_midlow    | template_residual_boosted_stack_new | 180 | 7.496               | 0.002162                           | 8.095                                  | 4.351                      | 0.376                    | 0.6034                    | 0.1872                    | 0.003017          |
| energy_state      | e2_midhigh   | 1d_cnn                              |  11 | 5.825               | 0.004249                           | 7.717                                  | 4.675                      | 0.2136                   | 0.2857                    | 0.2448                    | 0.1111            |
| energy_state      | e2_midhigh   | deltaE_over_E_likelihood_template   | 361 | 9.831               | 0.009966                           | 9.205                                  | 4.23                       | 0.259                    | 0.7887                    | 0.4595                    | 0.1705            |
| energy_state      | e2_midhigh   | gradient_boosted_trees              | 361 | 7.804               | 0.004283                           | 6.029                                  | 3.4                        | 0.3815                   | 0.4536                    | 0.2058                    | 0.238             |
| energy_state      | e2_midhigh   | joint_sequence_transformer          |  11 | 6.879               | 0.008095                           | 15.1                                   | 7.626                      | 0.1496                   | 0.1429                    | 0.2243                    | 0.4444            |
| energy_state      | e2_midhigh   | mlp                                 |  11 | 10.07               | -5.09e-05                          | -1.779                                 | 8.476                      | 0.04582                  | 0.1429                    | 0.2722                    | 0.1111            |
| energy_state      | e2_midhigh   | ridge                               | 361 | 8.006               | 0.001524                           | 0.949                                  | 1.711                      | 0.1347                   | 0.4536                    | 0.2232                    | 0.000768          |
| energy_state      | e2_midhigh   | template_residual_boosted_stack_new |  11 | 4.41                | 0.002922                           | 6.4                                    | 3.199                      | 0.3157                   | 0.1429                    | 0.1331                    | 0                 |
| energy_state      | e3_high      | 1d_cnn                              | 350 | 9.347               | 0.005455                           | 9.155                                  | 7.667                      | 0.2844                   | 0.4866                    | 0.212                     | 0.05212           |
| energy_state      | e3_high      | deltaE_over_E_likelihood_template   |   0 | n/a                 | n/a                                | n/a                                    | n/a                        | n/a                      | n/a                       | n/a                       | n/a               |
| energy_state      | e3_high      | gradient_boosted_trees              |   0 | n/a                 | n/a                                | n/a                                    | n/a                        | n/a                      | n/a                       | n/a                       | n/a               |
| energy_state      | e3_high      | joint_sequence_transformer          | 350 | 13.77               | 0.01206                            | 21.4                                   | 1.405                      | 0.2209                   | 0.3636                    | 0.2412                    | 0.005454          |
| energy_state      | e3_high      | mlp                                 | 350 | 11.47               | 0.0007806                          | 1.854                                  | 4.933                      | 0.121                    | 0.4973                    | 0.2125                    | 0.1147            |
| energy_state      | e3_high      | ridge                               |   0 | n/a                 | n/a                                | n/a                                    | n/a                        | n/a                      | n/a                       | n/a                       | n/a               |
| energy_state      | e3_high      | template_residual_boosted_stack_new | 350 | 7.436               | 0.004403                           | 7.865                                  | 3.34                       | 0.3757                   | 0.4545                    | 0.2012                    | 0.2383            |
| pedestal_state    | p0_quiet     | 1d_cnn                              | 126 | 14.14               | 0.003186                           | n/a                                    | 8.629                      | 0.1764                   | 0.5476                    | 0.278                     | 0.1019            |
| pedestal_state    | p0_quiet     | deltaE_over_E_likelihood_template   | 126 | 10.42               | 0.01268                            | n/a                                    | 16.42                      | 0.2559                   | 0.7976                    | 0.5065                    | 0.1078            |
| pedestal_state    | p0_quiet     | gradient_boosted_trees              | 126 | 10.01               | 0.002727                           | n/a                                    | 3.206                      | 0.2095                   | 0.4524                    | 0.231                     | 0.05992           |
| pedestal_state    | p0_quiet     | joint_sequence_transformer          | 126 | 18.28               | 0.006246                           | n/a                                    | 9.496                      | 0.1016                   | 0.3452                    | 0.2572                    | 0.1734            |
| pedestal_state    | p0_quiet     | mlp                                 | 126 | 15.28               | 0.0001064                          | n/a                                    | 9.691                      | 0.04243                  | 0.4286                    | 0.2914                    | 0.05736           |
| pedestal_state    | p0_quiet     | ridge                               | 126 | 11.18               | -0.0005405                         | n/a                                    | 7.131                      | 0.1032                   | 0.5714                    | 0.2368                    | 0.1905            |
| pedestal_state    | p0_quiet     | template_residual_boosted_stack_new | 126 | 10.36               | 0.003013                           | n/a                                    | 2.682                      | 0.2359                   | 0.4524                    | 0.2248                    | 0.09629           |
| pedestal_state    | p1_low       | 1d_cnn                              | 213 | 9.879               | 0.007045                           | n/a                                    | 3.462                      | 0.2503                   | 0.5934                    | 0.1892                    | 0.02268           |
| pedestal_state    | p1_low       | deltaE_over_E_likelihood_template   | 213 | 8.86                | -0.004999                          | n/a                                    | 6.474                      | 0.1878                   | 0.8571                    | 0.4882                    | 0.1174            |
| pedestal_state    | p1_low       | gradient_boosted_trees              | 213 | 8.006               | -0.00333                           | n/a                                    | 4.451                      | 0.3584                   | 0.5934                    | 0.1916                    | 0.0541            |
| pedestal_state    | p1_low       | joint_sequence_transformer          | 213 | 13.95               | 0.01572                            | n/a                                    | 11.28                      | 0.1958                   | 0.5055                    | 0.2181                    | 0.08005           |
| pedestal_state    | p1_low       | mlp                                 | 213 | 13.61               | -0.006081                          | n/a                                    | 7.044                      | 0.107                    | 0.6703                    | 0.1996                    | 0.1368            |
| pedestal_state    | p1_low       | ridge                               | 213 | 8.183               | 0.001349                           | n/a                                    | 2.344                      | 0.121                    | 0.5385                    | 0.2168                    | 0.07855           |
| pedestal_state    | p1_low       | template_residual_boosted_stack_new | 213 | 7.513               | -0.003086                          | n/a                                    | 5.866                      | 0.3495                   | 0.5714                    | 0.1906                    | 0.008032          |
| pedestal_state    | p2_high      | 1d_cnn                              | 186 | 8.136               | -0.0008666                         | n/a                                    | 8.768                      | 0.3275                   | 0.5472                    | 0.186                     | 0.04622           |
| pedestal_state    | p2_high      | deltaE_over_E_likelihood_template   | 186 | 9.334               | 0.0561                             | n/a                                    | 5.896                      | 0.2745                   | 0.8113                    | 0.4759                    | 0.03852           |
| pedestal_state    | p2_high      | gradient_boosted_trees              | 186 | 7.392               | 0.0001247                          | n/a                                    | 5.694                      | 0.4185                   | 0.4906                    | 0.1806                    | 0.1814            |
| pedestal_state    | p2_high      | joint_sequence_transformer          | 186 | 9.241               | 0.005375                           | n/a                                    | 5.871                      | 0.2618                   | 0.434                     | 0.2017                    | 0.02801           |
| pedestal_state    | p2_high      | mlp                                 | 186 | 9.754               | -0.05517                           | n/a                                    | 4.876                      | 0.1385                   | 0.5094                    | 0.1994                    | 0.04062           |
| pedestal_state    | p2_high      | ridge                               | 186 | 6.362               | -0.01854                           | n/a                                    | 2.103                      | 0.1504                   | 0.5094                    | 0.1986                    | 0.05392           |
| pedestal_state    | p2_high      | template_residual_boosted_stack_new | 186 | 7.152               | 0.005316                           | n/a                                    | 5.154                      | 0.394                    | 0.4906                    | 0.1716                    | 0.1401            |
| pedestal_state    | p3_excited   | 1d_cnn                              | 195 | 7.607               | 0.01785                            | n/a                                    | 8.889                      | 0.3524                   | 0.2821                    | 0.1895                    | 0.0584            |
| pedestal_state    | p3_excited   | deltaE_over_E_likelihood_template   | 195 | 6.512               | -0.014                             | n/a                                    | 7.852                      | 0.3092                   | 0.7436                    | 0.4644                    | 0.07986           |
| pedestal_state    | p3_excited   | gradient_boosted_trees              | 195 | 4.932               | 0.00592                            | n/a                                    | 2.544                      | 0.4644                   | 0.3077                    | 0.1917                    | 0.1386            |
| pedestal_state    | p3_excited   | joint_sequence_transformer          | 195 | 8.466               | 0.02276                            | n/a                                    | 2.824                      | 0.2925                   | 0.2308                    | 0.2107                    | 0.1165            |
| pedestal_state    | p3_excited   | mlp                                 | 195 | 9.053               | 0.03835                            | n/a                                    | 4.225                      | 0.1493                   | 0.3333                    | 0.1837                    | 0.06408           |
| pedestal_state    | p3_excited   | ridge                               | 195 | 6.367               | -0.01647                           | n/a                                    | 1.9                        | 0.16                     | 0.3077                    | 0.2058                    | 0.03788           |
| pedestal_state    | p3_excited   | template_residual_boosted_stack_new | 195 | 4.777               | 0.006544                           | n/a                                    | 2.986                      | 0.472                    | 0.3077                    | 0.1976                    | 0.1591            |
| pid_proxy_state   | deuteron     | 1d_cnn                              | 363 | 9.292               | 0.005438                           | 8.135                                  | 6.994                      | 0.3024                   | 0.5333                    | 0.2046                    | n/a               |
| pid_proxy_state   | deuteron     | deltaE_over_E_likelihood_template   | 363 | 9.208               | 0.0127                             | 9.654                                  | 6.765                      | 0.2506                   | 0.8074                    | 0.4671                    | n/a               |
| pid_proxy_state   | deuteron     | gradient_boosted_trees              | 363 | 7.693               | 0.004541                           | 6.936                                  | 4.002                      | 0.3902                   | 0.4667                    | 0.1931                    | n/a               |
| pid_proxy_state   | deuteron     | joint_sequence_transformer          | 363 | 13.35               | 0.012                              | 20.52                                  | 2.694                      | 0.2362                   | 0.4074                    | 0.2449                    | n/a               |
| pid_proxy_state   | deuteron     | mlp                                 | 363 | 12.13               | 0.002342                           | 1.809                                  | 3.071                      | 0.1185                   | 0.4741                    | 0.2082                    | n/a               |
| pid_proxy_state   | deuteron     | ridge                               | 363 | 7.416               | 0.001596                           | 0.2293                                 | 1.938                      | 0.1417                   | 0.4889                    | 0.226                     | n/a               |
| pid_proxy_state   | deuteron     | template_residual_boosted_stack_new | 363 | 7.57                | 0.004527                           | 8.112                                  | 4.072                      | 0.3822                   | 0.4593                    | 0.1947                    | n/a               |
| pid_proxy_state   | proton       | 1d_cnn                              | 357 | 9.231               | 0.005215                           | 8.928                                  | 8.374                      | 0.2809                   | 0.5152                    | 0.1963                    | n/a               |
| pid_proxy_state   | proton       | deltaE_over_E_likelihood_template   | 357 | 9.896               | 0.009888                           | 12.02                                  | 6.041                      | 0.2732                   | 0.8182                    | 0.4822                    | n/a               |
| pid_proxy_state   | proton       | gradient_boosted_trees              | 357 | 7.504               | 0.004122                           | 6.492                                  | 2.894                      | 0.3756                   | 0.5076                    | 0.1893                    | n/a               |
| pid_proxy_state   | proton       | joint_sequence_transformer          | 357 | 13.55               | 0.01099                            | 18.47                                  | 5.183                      | 0.2201                   | 0.3939                    | 0.2108                    | n/a               |
| pid_proxy_state   | proton       | mlp                                 | 357 | 10.9                | 0.002117                           | 2.239                                  | 2.776                      | 0.1202                   | 0.553                     | 0.2085                    | n/a               |
| pid_proxy_state   | proton       | ridge                               | 357 | 7.929               | 0.003012                           | 2.827                                  | 0.9949                     | 0.134                    | 0.5303                    | 0.2109                    | n/a               |
| pid_proxy_state   | proton       | template_residual_boosted_stack_new | 357 | 7.299               | 0.004076                           | 7.178                                  | 3.653                      | 0.38                     | 0.5                       | 0.186                     | n/a               |
| pileup_state      | merged       | 1d_cnn                              | 150 | 7.26                | 0.002582                           | 4                                      | 3.463                      | n/a                      | 0.5862                    | 0.1447                    | 0.04017           |
| pileup_state      | merged       | deltaE_over_E_likelihood_template   | 150 | 9.254               | 0.01185                            | 16.51                                  | 6.598                      | n/a                      | 0.8391                    | 0.4889                    | 0.05488           |
| pileup_state      | merged       | gradient_boosted_trees              | 150 | 5.004               | 0.002057                           | 3.504                                  | 1.239                      | n/a                      | 0.5172                    | 0.1153                    | 0.1216            |
| pileup_state      | merged       | joint_sequence_transformer          | 150 | 11.68               | 0.009167                           | 16.54                                  | 4.996                      | n/a                      | 0.4598                    | 0.1543                    | 0.1148            |
| pileup_state      | merged       | mlp                                 | 150 | 8.943               | 0.001622                           | -1.01                                  | 4.378                      | n/a                      | 0.5172                    | 0.1405                    | 0.01614           |
| pileup_state      | merged       | ridge                               | 150 | 6.528               | 0.002177                           | 2.732                                  | 2.225                      | n/a                      | 0.5172                    | 0.1362                    | 0.05237           |
| pileup_state      | merged       | template_residual_boosted_stack_new | 150 | 5.195               | 0.002296                           | 3.19                                   | 2.119                      | n/a                      | 0.4943                    | 0.1178                    | 0.06277           |
| pileup_state      | near         | 1d_cnn                              |  80 | 7.052               | 0.007582                           | 10.97                                  | 7.231                      | n/a                      | 0.2941                    | 0.1232                    | 0.0243            |
| pileup_state      | near         | deltaE_over_E_likelihood_template   |  80 | 11.71               | 0.009859                           | 19.03                                  | 12.43                      | n/a                      | 0.6765                    | 0.5168                    | 0.08312           |
| pileup_state      | near         | gradient_boosted_trees              |  80 | 6.043               | 0.002938                           | 6.495                                  | 3.519                      | n/a                      | 0.2059                    | 0.09886                   | 0.101             |
| pileup_state      | near         | joint_sequence_transformer          |  80 | 10.71               | 0.01226                            | 18.37                                  | 6.938                      | n/a                      | 0.2059                    | 0.1445                    | 0.335             |
| pileup_state      | near         | mlp                                 |  80 | 10.88               | 0.003943                           | 1.532                                  | 5.852                      | n/a                      | 0.2941                    | 0.1506                    | 0.1266            |
| pileup_state      | near         | ridge                               |  80 | 7.536               | -9.948e-05                         | -0.425                                 | 8.675                      | n/a                      | 0.3235                    | 0.1268                    | 0.1343            |
| pileup_state      | near         | template_residual_boosted_stack_new |  80 | 6.098               | 0.003047                           | 5.661                                  | 3.998                      | n/a                      | 0.2941                    | 0.1092                    | 0.07161           |
| pileup_state      | separated    | 1d_cnn                              | 130 | 6.157               | 0.004509                           | 3.078                                  | 4.909                      | n/a                      | 0.09756                   | 0.1245                    | 0.2255            |
| pileup_state      | separated    | deltaE_over_E_likelihood_template   | 130 | 7.548               | 0.0126                             | 9.052                                  | 1.502                      | n/a                      | 0.561                     | 0.5109                    | 0.2414            |
| pileup_state      | separated    | gradient_boosted_trees              | 130 | 5.599               | 0.004117                           | 5.982                                  | 8.211                      | n/a                      | 0.07317                   | 0.1092                    | 0.1644            |
| pileup_state      | separated    | joint_sequence_transformer          | 130 | 9.398               | 0.009751                           | 8.471                                  | 9.712                      | n/a                      | 0.04878                   | 0.1271                    | 0.8619            |
| pileup_state      | separated    | mlp                                 | 130 | 9.904               | 0.001561                           | 4.212                                  | 6.279                      | n/a                      | 0.1707                    | 0.1459                    | 0.2097            |
| pileup_state      | separated    | ridge                               | 130 | 6.275               | 0.001362                           | 2.614                                  | 8.584                      | n/a                      | 0.1463                    | 0.08583                   | 0.1938            |
| pileup_state      | separated    | template_residual_boosted_stack_new | 130 | 5.659               | 0.004399                           | 4.957                                  | 7.539                      | n/a                      | 0.04878                   | 0.1013                    | 0.1654            |
| pileup_state      | single       | 1d_cnn                              | 360 | 13.06               | 0.006246                           | 11.23                                  | 11.75                      | n/a                      | 0.7143                    | 0.2504                    | 0.03565           |
| pileup_state      | single       | deltaE_over_E_likelihood_template   | 360 | 8.158               | 0.008605                           | 2.681                                  | 1.585                      | n/a                      | 0.9333                    | 0.2981                    | 0.03745           |
| pileup_state      | single       | gradient_boosted_trees              | 360 | 8.65                | 0.005514                           | 10.69                                  | 4.893                      | n/a                      | 0.7143                    | 0.2356                    | 0.09483           |
| pileup_state      | single       | joint_sequence_transformer          | 360 | 16.35               | 0.01265                            | 28.25                                  | 8.378                      | n/a                      | 0.5524                    | 0.283                     | 0.2717            |
| pileup_state      | single       | mlp                                 | 360 | 13.32               | 0.002244                           | 5.146                                  | 3.042                      | n/a                      | 0.7143                    | 0.2513                    | 0.05801           |
| pileup_state      | single       | ridge                               | 360 | 7.552               | 0.003176                           | 5.512                                  | 6.885                      | n/a                      | 0.7048                    | 0.2469                    | 0.03571           |
| pileup_state      | single       | template_residual_boosted_stack_new | 360 | 8.421               | 0.005241                           | 10.22                                  | 5.397                      | n/a                      | 0.6952                    | 0.2295                    | 0.09309           |
| pulse_shape_state | broad_tail   | 1d_cnn                              | 151 | 10.63               | 0.006209                           | 10.11                                  | n/a                        | 0.2226                   | 0.2647                    | 0.1773                    | 0.1161            |
| pulse_shape_state | broad_tail   | deltaE_over_E_likelihood_template   | 151 | 9.55                | 0.009001                           | 10.75                                  | n/a                        | 0.4354                   | 0.6324                    | 0.5306                    | 0.09603           |
| pulse_shape_state | broad_tail   | gradient_boosted_trees              | 151 | 7.621               | 0.004273                           | 3.482                                  | n/a                        | 0.3097                   | 0.1765                    | 0.1423                    | 0.07778           |
| pulse_shape_state | broad_tail   | joint_sequence_transformer          | 151 | 13.29               | 0.008456                           | 15.86                                  | n/a                        | 0.1054                   | 0.1029                    | 0.2179                    | 0.5934            |
| pulse_shape_state | broad_tail   | mlp                                 | 151 | 9.756               | 0.002649                           | 4.268                                  | n/a                        | 0.04668                  | 0.1765                    | 0.2076                    | 0.1469            |
| pulse_shape_state | broad_tail   | ridge                               | 151 | 9.386               | 0.0005353                          | -1.67                                  | n/a                        | 0.1124                   | 0.2941                    | 0.1649                    | 0.1308            |
| pulse_shape_state | broad_tail   | template_residual_boosted_stack_new | 151 | 7.15                | 0.004232                           | 3.568                                  | n/a                        | 0.3095                   | 0.1765                    | 0.1412                    | 0.06308           |
| pulse_shape_state | compact      | 1d_cnn                              | 207 | 14.23               | 0.0006163                          | -9.197                                 | n/a                        | 0.08081                  | 0.9516                    | 0.2474                    | 0.07515           |
| pulse_shape_state | compact      | deltaE_over_E_likelihood_template   | 207 | 11.03               | 0.005585                           | 17.39                                  | n/a                        | 0.03057                  | 1                         | 0                         | 0.09886           |
| pulse_shape_state | compact      | gradient_boosted_trees              | 207 | 9.083               | 0.005329                           | 2.221                                  | n/a                        | 0.1335                   | 0.9032                    | 0.237                     | 0.1532            |
| pulse_shape_state | compact      | joint_sequence_transformer          | 207 | 14.87               | 0.01775                            | 13.46                                  | n/a                        | 0.06274                  | 0.9355                    | 0.2732                    | 0.4394            |
| pulse_shape_state | compact      | mlp                                 | 207 | 13.33               | -0.001748                          | -3.458                                 | n/a                        | 0.03524                  | 0.9677                    | 0.2682                    | 0.01708           |
| pulse_shape_state | compact      | ridge                               | 207 | 8.208               | 0.005879                           | 0.4207                                 | n/a                        | 0.06126                  | 0.9839                    | 0.2551                    | 0.03118           |
| pulse_shape_state | compact      | template_residual_boosted_stack_new | 207 | 9.016               | 0.004564                           | 0.5737                                 | n/a                        | 0.09086                  | 0.9516                    | 0.2398                    | 0.1243            |
| pulse_shape_state | nominal_fast | 1d_cnn                              | 190 | 7.244               | 0.003885                           | 6.668                                  | n/a                        | 0.1553                   | 0.575                     | 0.2015                    | 0.06667           |
| pulse_shape_state | nominal_fast | deltaE_over_E_likelihood_template   | 190 | 11.06               | 0.009921                           | -3.357                                 | n/a                        | 0.02962                  | 0.9375                    | 0.3361                    | 0.07889           |
| pulse_shape_state | nominal_fast | gradient_boosted_trees              | 190 | 6.941               | 0.00438                            | 6.115                                  | n/a                        | 0.2379                   | 0.6                       | 0.1758                    | 0.1189            |
| pulse_shape_state | nominal_fast | joint_sequence_transformer          | 190 | 11.09               | 0.01318                            | 18.17                                  | n/a                        | 0.1114                   | 0.4125                    | 0.1957                    | 0.1689            |
| pulse_shape_state | nominal_fast | mlp                                 | 190 | 12.05               | -2.067e-05                         | -5.449                                 | n/a                        | 0.04301                  | 0.6125                    | 0.189                     | 0.03556           |
| pulse_shape_state | nominal_fast | ridge                               | 190 | 7.128               | 0.004799                           | 4.028                                  | n/a                        | 0.06188                  | 0.55                      | 0.1774                    | 0.08              |
| pulse_shape_state | nominal_fast | template_residual_boosted_stack_new | 190 | 7.013               | 0.004393                           | 5.244                                  | n/a                        | 0.2324                   | 0.575                     | 0.1686                    | 0.11              |
| pulse_shape_state | nominal_tail | 1d_cnn                              | 172 | 6.934               | 0.006188                           | 11.67                                  | n/a                        | 0.1856                   | 0.2982                    | 0.1492                    | 0.075             |

The full S42a state ledger is `s42a_systematics_by_state.csv`.

## Interpretation

`gradient_boosted_trees` is the S42a winner by the predeclared composite score.  Its primary
run-block timing sigma68 is `7.634` ns with 95% CI
[`7.057`, `8.209`],
and its event-bootstrap timing CI is
[`7.168`, `8.247`].
The traditional combined comparator has timing sigma68
`9.722` ns.  The result supports using residual
pulse-shape calibration as an audit layer over the transparent template/CFD/AR
baseline, not as an unqualified replacement for production calibration.

The caveat is important: the target labels are digitized GEANT4 and controlled
raw-waveform overlays.  This is a strong causal benchmark for drift mechanisms,
but not an independent hardware-pedestal measurement.

## MC Verdict

MC validation available through the S29a/S31b digitized GEANT4 bridge: timing,
energy, PID, pile-up, and saturation truth labels come from
`/home/billy/ccb-geant4/output_30k.root` and are joined through
`digitized_g4_08_keyed.root`.  The MC/data bridge is suitable for relative
method ranking, while absolute electronics pedestal memory still needs an
independent hardware stream for closure.

## Open Questions

1. S42b: hardware pedestal side-stream closure.  Hypothesis: independent
   pedestal monitor samples reduce the residual high-minus-low pedestal bias;
   falsify by showing no held-out improvement versus the S42a AR baseline.
2. S42c: hand-scanned pile-up morphology labels.  Hypothesis: the residual-stack
   winner is sensitive to controlled overlay assumptions; falsify by matching
   its pile-up miss/false-split rates on human-labeled raw events.

No novel ticket was appended by this worker.

## Provenance

Git commit: `e3334071954a1ea9d93bb1eeddde8bdf1dba3bce`

Data SHA256: see `input_sha256.csv`.

Python: `3.11.14`

numpy / pandas: `2.4.6` / `3.0.3`

Run host / job: `billy` / local worker `testbeam-laptop-1`

Artifacts: `reports/1784181983.690.0d7c7719__s42a_causal_pedestal_pulse_shape_calibration_benchmark/{REPORT.md,result.json,manifest.json,event_predictions.csv,winner_ranked_metrics.csv,s42a_run_block_bootstrap_ci.csv,s42a_event_bootstrap_ci.csv,s42a_systematics_by_state.csv}`

Runtime was `20.0` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.
