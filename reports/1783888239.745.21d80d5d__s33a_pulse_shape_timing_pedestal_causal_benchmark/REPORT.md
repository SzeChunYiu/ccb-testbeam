# S33a: Pulse-Shape Timing Pedestal Causal Benchmark

## Abstract

Ticket `1783888239.745.21d80d5d` requested an academic-grade comparison between a
strong traditional constant-fraction/template residual analysis and several
ML/NN methods for joint pulse-shape, time-pickoff, and pedestal-drift inference.
This study reads raw B-stack ROOT directly, reproduces the canonical selected
pulse count, splits complete runs into train and held-out blocks, and reports
paired run-bootstrap confidence intervals for timing residuals, shape residuals,
pedestal bias, and calibration stability.  The `result.json` winner is
**`traditional_cfd_template_timewalk`**, with registered score `1.223` and
timing sigma68 `0.9573 ns`
`[0.7624, 1.156]`.

## Raw ROOT Reproduction

Input files are `data/root/root/hrdb_run_*.root`.  For every event
the branch `h101/HRDv` is reshaped as `(8, 18)`.  For B-stack stave channel `c`,
the pedestal is

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

and the corrected amplitude is

`A_c = max_t [x_c(t)-b_c]`.

A selected pulse satisfies `A_c > 1000 ADC` for one
of B2, B4, B6, or B8.  The reproduction gate is evaluated before row sampling or
model fitting:

| group                 |   events_total |   selected_pulses |   expected_selected_pulses |   delta | pass   |
|:----------------------|---------------:|------------------:|---------------------------:|--------:|:-------|
| sample_i_calib        |         409815 |            248745 |                     248745 |       0 | True   |
| sample_i_analysis     |         388879 |            252266 |                     252266 |       0 | True   |
| sample_ii_calib       |          35943 |             14630 |                      14630 |       0 | True   |
| sample_ii_analysis    |         262091 |            125096 |                     125096 |       0 | True   |
| all_registered_groups |        1096728 |            640737 |                     640737 |       0 | True   |

## Estimands and Split

For CFD fraction `f`, the crossing time is the first pre-peak linear
interpolation satisfying

`x(t_f)-b = f A`.

The primary target is the run/stave-centered CFD20 onset residual,

`y_i = 10 ns * [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The split is by complete run.  Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`; all
other registered B-stack runs train the models.  The sampled benchmark contains:

| split   |   rows |
|:--------|-------:|
| heldout |   5466 |
| train   |  15137 |

Intervals are percentile 95% confidence intervals from
`400` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Methods

| method                            | family           | description                                                                                                        |
|:----------------------------------|:-----------------|:-------------------------------------------------------------------------------------------------------------------|
| traditional_cfd_template_timewalk | traditional      | CFD50 residual plus monotone log-amplitude time-walk and template-shape correction                                 |
| ridge                             | linear ML        | standardized ridge regression on waveform, amplitude, CFD, tail, saturation, duplicate-readout, and pedestal atoms |
| gradient_boosted_trees            | tree ML          | histogram gradient-boosted regressor on the same ticket-frozen feature matrix                                      |
| mlp                               | neural tabular   | two-layer MLP regressor on standardized engineered pulse-shape and detector-state atoms                            |
| 1d_cnn                            | neural waveform  | compact convolutional regressor over the 18 normalized waveform samples                                            |
| waveform_transformer              | neural waveform  | single-layer self-attention sequence model with sample-position embedding                                          |
| edge_attention_cnn_new            | new architecture | gated convolutional waveform model that can upweight leading-edge and late-curvature regions                       |

The traditional comparator is deliberately strong.  It starts from a CFD50
residual `r_50`, fits a non-increasing isotonic time-walk correction
`g(log(1+A))`, and adds a linear template-shape proxy:

`hat y = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`.

The new `edge_attention_cnn_new` is sensible for this ticket because the causal
timing information is expected on the leading edge, while pedestal memory is
encoded in samples 0--3 and pile-up/saturation nuisance information appears in
late curvature and flat-top regions.

## Primary Timing Results

| method                            |    n |   bias_ns |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   rms_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|-----:|----------:|-------------:|--------------------:|---------------------:|---------:|---------------------------:|
| traditional_cfd_template_timewalk | 5466 |    0.387  |       0.9573 |              0.7647 |                1.107 |   0.9364 |                  0.0001829 |
| gradient_boosted_trees            | 5466 |   -0.3978 |       3.791  |              3.027  |                4.144 |   3.667  |                  0.1561    |
| ridge                             | 5466 |   -0.3684 |       4.03   |              3.67   |                4.367 |   4.163  |                  0.2186    |
| mlp                               | 5466 |   -0.6728 |       4.058  |              3.501  |                4.597 |   4.131  |                  0.2214    |
| edge_attention_cnn_new            | 5466 |   -1.315  |       4.859  |              4.326  |                5.454 |   6.444  |                  0.3277    |
| waveform_transformer              | 5466 |    0.6127 |       5.43   |              4.896  |                6.03  |   5.889  |                  0.3708    |
| 1d_cnn                            | 5466 |    0.9526 |       5.809  |              5.186  |                6.435 |   6.807  |                  0.3932    |

## Registered S33a Endpoint Table

Shape residual is the width of `prediction - target`, evaluated against a
rise-time/tail proxy.  Pedestal bias is the high-minus-low pedestal-drift median
error.  Calibration stability is the standard deviation of per-run sigma68 and
the span of per-run median biases.

| method                            |   registered_score |   timing_residual_sigma68_ns |   timing_residual_sigma68_ns_ci_low |   timing_residual_sigma68_ns_ci_high |   shape_residual_sigma68 |   pedestal_high_minus_low_bias_ns |   pedestal_high_minus_low_bias_ns_ci_low |   pedestal_high_minus_low_bias_ns_ci_high |   calibration_stability_run_sigma68_sd_ns |   calibration_stability_run_bias_span_ns |
|:----------------------------------|-------------------:|-----------------------------:|------------------------------------:|-------------------------------------:|-------------------------:|----------------------------------:|-----------------------------------------:|------------------------------------------:|------------------------------------------:|-----------------------------------------:|
| traditional_cfd_template_timewalk |              1.223 |                       0.9573 |                              0.7624 |                                1.156 |                   0.9573 |                          -0.08767 |                                  -0.4965 |                                    0.1271 |                                    0.3319 |                                    1.571 |
| gradient_boosted_trees            |              4.519 |                       3.791  |                              3.12   |                                4.101 |                   3.791  |                           0.2897  |                                  -0.5013 |                                    0.9145 |                                    0.6409 |                                    6.4   |
| ridge                             |              4.757 |                       4.03   |                              3.615  |                                4.428 |                   4.03   |                           0.334   |                                  -0.1903 |                                    0.6344 |                                    0.5127 |                                    5.342 |
| mlp                               |              5.32  |                       4.058  |                              3.53   |                                4.568 |                   4.058  |                           1.088   |                                   0.3657 |                                    1.793  |                                    0.7446 |                                    6.082 |
| edge_attention_cnn_new            |              5.696 |                       4.859  |                              4.231  |                                5.474 |                   4.859  |                           0.1056  |                                  -0.5195 |                                    0.6452 |                                    0.6857 |                                    5.923 |
| waveform_transformer              |              6.723 |                       5.43   |                              4.903  |                                6.029 |                   5.43   |                          -0.9223  |                                  -1.813  |                                   -0.2808 |                                    0.6913 |                                    5.715 |
| 1d_cnn                            |              7.009 |                       5.809  |                              5.245  |                                6.431 |                   5.809  |                           0.4752  |                                  -0.2519 |                                    0.8931 |                                    0.8539 |                                    6.085 |

The traditional comparator has registered score `1.223`;
the selected winner `traditional_cfd_template_timewalk` has score `1.223`.

## Paired Deltas Against Traditional

Positive `delta_sigma68_ns` means the candidate is wider than the traditional
comparator under paired held-out run-block bootstrap resampling.

| method                 | reference_method                  |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |   delta_tail_fraction_abs_gt_5ns |   delta_tail_fraction_abs_gt_5ns_ci_low |   delta_tail_fraction_abs_gt_5ns_ci_high |
|:-----------------------|:----------------------------------|-------------------:|--------------------------:|---------------------------:|---------------------------------:|----------------------------------------:|-----------------------------------------:|
| gradient_boosted_trees | traditional_cfd_template_timewalk |              2.834 |                     2.128 |                      3.238 |                           0.1559 |                                  0.1116 |                                   0.2178 |
| ridge                  | traditional_cfd_template_timewalk |              3.073 |                     2.672 |                      3.481 |                           0.2184 |                                  0.1689 |                                   0.2692 |
| mlp                    | traditional_cfd_template_timewalk |              3.101 |                     2.55  |                      3.69  |                           0.2212 |                                  0.1613 |                                   0.2836 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk |              3.901 |                     3.354 |                      4.604 |                           0.3275 |                                  0.2866 |                                   0.3797 |
| waveform_transformer   | traditional_cfd_template_timewalk |              4.473 |                     3.936 |                      5.13  |                           0.3707 |                                  0.3219 |                                   0.4199 |
| 1d_cnn                 | traditional_cfd_template_timewalk |              4.852 |                     4.24  |                      5.531 |                           0.393  |                                  0.3328 |                                   0.4434 |

## Causal Region and Pedestal-Memory Audit

The causal-region audit uses the best non-traditional tree learner and removes
families of correlated waveform atoms.  A positive delta means the removed region
was carrying transferable timing information after complete-run blocking.

| region_test                                | ablation                       |   sigma68_ns |   delta_vs_full_gbt_ns | interpretation                             |
|:-------------------------------------------|:-------------------------------|-------------:|-----------------------:|:-------------------------------------------|
| pretrigger pedestal memory                 | drop_pretrigger_features       |        3.874 |                0.08225 | weak or redundant after run-block controls |
| late pulse-shape/tail region               | drop_tail_pulse_shape_features |        3.776 |               -0.01596 | weak or redundant after run-block controls |
| leading-edge amplitude and CFD region only | amplitude_cfd_only             |        3.931 |                0.14    | weak or redundant after run-block controls |

Full ablation table:

| ablation                       |   n_features |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   delta_sigma68_vs_full_ns |   tail_fraction_abs_gt_5ns |
|:-------------------------------|-------------:|-------------:|--------------------:|---------------------:|---------------------------:|---------------------------:|
| drop_tail_pulse_shape_features |           24 |        3.776 |               3.071 |                4.191 |                   -0.01596 |                     0.165  |
| full_gradient_boosted_trees    |           33 |        3.791 |               3.106 |                4.104 |                    0       |                     0.161  |
| drop_pretrigger_features       |           27 |        3.874 |               3.463 |                4.201 |                    0.08225 |                     0.1934 |
| amplitude_cfd_only             |            5 |        3.931 |               3.558 |                4.396 |                    0.14    |                     0.2124 |

## Falsification and Fleet Context

The pre-registered decision rule is the ticket request itself: compare the
traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new
architecture under run-block bootstrap CIs, then name the lowest registered
endpoint score in `result.json`.  The falsification test is direct: the
traditional-winner conclusion would fail if any ML/NN method had a paired
run-bootstrap `delta_sigma68_ns` confidence interval entirely below zero or a
lower registered endpoint score.  Six non-traditional candidates were compared;
none beat the traditional comparator, so no multiple-comparison adjusted ML win
is claimed.

The current `reports/SUMMARY.md` is a queue-hygiene scoreboard rather than a
physics synthesis, so S33a does not conflict with a listed fleet-level timing
verdict.  It does, however, reinforce the standing lesson that a strong
traditional baseline can dominate compact neural models when the target is an
internally defined CFD residual and complete runs are held out.

## Run Stability

| method                            |   run |   n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|------:|----:|----------:|-------------:|---------------------------:|
| 1d_cnn                            |    42 | 657 |   3.618   |       6.902  |                   0.4658   |
| 1d_cnn                            |    50 | 680 |   0.4593  |       5.069  |                   0.3088   |
| 1d_cnn                            |    57 | 670 |   2.93    |       6.337  |                   0.497    |
| 1d_cnn                            |    58 | 654 |  -2.466   |       6.023  |                   0.4526   |
| 1d_cnn                            |    60 | 720 |   1.882   |       4.979  |                   0.4083   |
| 1d_cnn                            |    62 | 720 |   0.6494  |       6.082  |                   0.4278   |
| 1d_cnn                            |    64 | 720 |  -0.3381  |       4.526  |                   0.2903   |
| 1d_cnn                            |    65 | 645 |   0.2786  |       4.803  |                   0.2992   |
| edge_attention_cnn_new            |    42 | 657 |   1.567   |       5.511  |                   0.344    |
| edge_attention_cnn_new            |    50 | 680 |  -1.544   |       4.345  |                   0.2735   |
| edge_attention_cnn_new            |    57 | 670 |   1.318   |       5.334  |                   0.3851   |
| edge_attention_cnn_new            |    58 | 654 |  -4.355   |       5.201  |                   0.4832   |
| edge_attention_cnn_new            |    60 | 720 |  -0.4007  |       4.212  |                   0.2444   |
| edge_attention_cnn_new            |    62 | 720 |  -1.999   |       4.993  |                   0.3333   |
| edge_attention_cnn_new            |    64 | 720 |  -2.748   |       3.781  |                   0.2903   |
| edge_attention_cnn_new            |    65 | 645 |  -1.704   |       3.863  |                   0.2791   |
| gradient_boosted_trees            |    42 | 657 |   2.16    |       2.321  |                   0.1857   |
| gradient_boosted_trees            |    50 | 680 |   1.233   |       3.087  |                   0.08676  |
| gradient_boosted_trees            |    57 | 670 |   0.843   |       3.163  |                   0.1746   |
| gradient_boosted_trees            |    58 | 654 |  -4.24    |       2.834  |                   0.3486   |
| gradient_boosted_trees            |    60 | 720 |  -0.02561 |       3.599  |                   0.09583  |
| gradient_boosted_trees            |    62 | 720 |  -2.228   |       4.194  |                   0.15     |
| gradient_boosted_trees            |    64 | 720 |  -1.946   |       2.229  |                   0.08472  |
| gradient_boosted_trees            |    65 | 645 |  -1.621   |       3.07   |                   0.138    |
| mlp                               |    42 | 657 |   2.217   |       3.41   |                   0.2359   |
| mlp                               |    50 | 680 |   0.5422  |       2.556  |                   0.07059  |
| mlp                               |    57 | 670 |   0.9456  |       4.088  |                   0.2537   |
| mlp                               |    58 | 654 |  -3.865   |       4.004  |                   0.3777   |
| mlp                               |    60 | 720 |  -0.4077  |       4.204  |                   0.2264   |
| mlp                               |    62 | 720 |  -2.48    |       4.989  |                   0.3028   |
| mlp                               |    64 | 720 |  -2.454   |       3.121  |                   0.1375   |
| mlp                               |    65 | 645 |  -2.093   |       3.943  |                   0.1705   |
| ridge                             |    42 | 657 |   2.203   |       4.119  |                   0.2968   |
| ridge                             |    50 | 680 |  -0.0181  |       3.855  |                   0.1868   |
| ridge                             |    57 | 670 |   1.838   |       4.347  |                   0.2657   |
| ridge                             |    58 | 654 |  -3.139   |       4.294  |                   0.344    |
| ridge                             |    60 | 720 |  -0.05387 |       3.487  |                   0.1264   |
| ridge                             |    62 | 720 |  -1.5     |       4.478  |                   0.2403   |
| ridge                             |    64 | 720 |  -2.038   |       2.993  |                   0.1375   |
| ridge                             |    65 | 645 |  -1.037   |       3.572  |                   0.1659   |
| traditional_cfd_template_timewalk |    42 | 657 |  -0.7082  |       1.027  |                   0        |
| traditional_cfd_template_timewalk |    50 | 680 |   0.1694  |       0.7097 |                   0        |
| traditional_cfd_template_timewalk |    57 | 670 |  -0.5498  |       1.361  |                   0        |
| traditional_cfd_template_timewalk |    58 | 654 |   0.5192  |       0.7946 |                   0        |
| traditional_cfd_template_timewalk |    60 | 720 |  -0.3777  |       0.6908 |                   0.001389 |
| traditional_cfd_template_timewalk |    62 | 720 |   0.8294  |       0.2009 |                   0        |
| traditional_cfd_template_timewalk |    64 | 720 |   0.863   |       0.7442 |                   0        |
| traditional_cfd_template_timewalk |    65 | 645 |   0.4151  |       0.9555 |                   0        |
| waveform_transformer              |    42 | 657 |   2.444   |       4.892  |                   0.3668   |
| waveform_transformer              |    50 | 680 |   0.558   |       3.98   |                   0.2294   |
| waveform_transformer              |    57 | 670 |   1.801   |       4.964  |                   0.3478   |
| waveform_transformer              |    58 | 654 |  -3.272   |       5.628  |                   0.4786   |
| waveform_transformer              |    60 | 720 |   1.448   |       5.498  |                   0.3833   |
| waveform_transformer              |    62 | 720 |   0.5565  |       6.396  |                   0.4542   |
| waveform_transformer              |    64 | 720 |  -0.2862  |       5.13   |                   0.3347   |
| waveform_transformer              |    65 | 645 |   0.5418  |       5.228  |                   0.3721   |

## Provenance and Reproducibility

The machine-readable provenance is `manifest.json`; raw input hashes are in
`input_sha256.csv`; output hashes are stored in the manifest.  The exact command
to regenerate the study is:

`/home/billy/anaconda3/bin/python scripts/s33a_1783888239_745_21d80d5d_pulse_shape_timing_pedestal_causal_benchmark.py --config configs/s33a_1783888239_745_21d80d5d_pulse_shape_timing_pedestal_causal_benchmark.json`

The script writes `reproduction.csv`, `benchmark_rows.parquet`,
`predictions.parquet`, `metrics.csv`, `endpoint_metrics.csv`,
`method_deltas.csv`, `by_run.csv`, `strata.csv`, `ablations.csv`,
`causal_region_audit.csv`, `result.json`, `REPORT.md`, and `manifest.json`.

## Systematics and Caveats

Pedestal drift, pile-up separation, saturation onset, energy, and PID confusion
are raw-waveform sideband proxies because the reduced ROOT tree provides `HRDv`
waveforms, not external particle truth or electronics state labels.  The target
is an internally reproducible CFD20 reference, not an absolute beamline timing
truth.  The run-block bootstrap covers observed run-to-run transfer scatter but
does not cover unobserved electronics modes.  The 18-sample, 10 ns waveform
window imposes a shared interpolation floor.  A neural win would therefore be
evidence for waveform-context transfer, not a deployment decision without a
larger systematic campaign.

Runtime was `68.4 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.
