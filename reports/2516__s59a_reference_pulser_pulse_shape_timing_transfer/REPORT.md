# S59a Reference-Pulser Pulse-Shape Timing Transfer Benchmark

## Abstract

Ticket `#2516` asks whether pulse-shape and timing information transfers across run/current blocks for reference-pulser-like B-stack pulses.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction plus parametric CR-RC/log-normal template fit with derivative residual correction is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `shape_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_crrc_lognormal_template`** as the
winner with `sigma_68 = 1.008 ns`
`[0.8213, 1.155]`.  The
traditional CFD/template comparator obtains `1.008 ns`
`[0.8213, 1.155]`.


## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-1 --project testbeam` command was
run exactly once.  The local helper returned the malformed empty-existing-claim
payload

```text
null
# null

null
```

without moving an open issue.  Read-only GitHub inspection then showed issue
`#2516` still labeled `factory:open project:testbeam` and no valid
`worker:testbeam-laptop-1` claimed issue.  To bind exactly one ticket without
running the helper a second time, `#2516` was manually label-swapped to
`factory:claimed worker:testbeam-laptop-1` using:

```text
gh issue edit 2516 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open
```

No other testbeam ticket was claimed in this worker.

## Raw ROOT Reproduction

Input files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each event the raw
vector `HRDv` is reshaped to `(8, 18)`.  The B-stack channels are B2, B4, B6,
and B8.  With pretrigger baseline

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

the reproduced count is

`N = sum_e sum_{c in B2,B4,B6,B8} 1[max_t(x_{e,c,t} - b_{e,c}) > 1000]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced raw count is **640737**.
Input hashes are stored in `input_sha256.csv`; first rows:

| run | path | bytes | sha256 |
| --- | --- | --- | --- |
| 31 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0031.root | 11638901 | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| 32 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0032.root | 12157812 | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| 33 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0033.root | 16781109 | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| 34 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0034.root | 11697434 | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| 35 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0035.root | 7793651 | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| 36 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0036.root | 6167361 | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| 37 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0037.root | 14369738 | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| 39 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0039.root | 8625385 | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |

## Estimand and Equations

The sub-sample constant-fraction crossing at fraction `f` is computed by
linear interpolation before the waveform peak:

`t_f = k - 1 + (f A - y_{k-1}) / (y_k - y_{k-1})`,

where `y_t = x_t - b`, `A = max_t y_t`, and `k` is the first pre-peak sample
with `y_k >= f A`.  The supervised target is the run/stave-centered CFD20
residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The normalized waveform is `z_t = (x_t - b) / max(A, 1)`.  Derivative features
are the finite differences

`d_t = z_{t+1} - z_t`,

and curvature samples

`c_t = d_{t+1} - d_t`.

The traditional method starts from the audited CFD/template time-walk baseline
`hat y_0`, then fits a ridge-regularized derivative residual correction on
training runs only:

`hat y = hat y_0 + beta_0 + beta^T standardize(s_deriv)`,

where `s_deriv` contains onset slope, late slope, curvature peak, curvature
energy, derivative centroids, and pretrigger derivative RMS.  The ridge penalty
prevents derivative summaries from silently absorbing run identity.

For method `m`, residual error is `epsilon_i^m = y_i - hat y_i^m`.  Resolution
is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

and bias is `median(epsilon)`.

## Split and Uncertainty

The split unit is the run: held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]` and all
other configured B-stack runs are used for training.  Sampled benchmark rows:

| split | rows |
| --- | --- |
| heldout | 5466 |
| train | 15137 |

Confidence intervals use `500` paired percentile
bootstrap replicates that resample held-out runs with replacement.  Paired
deltas subtract each replicate of the traditional CFD/template comparator from
the corresponding replicate of the learned method.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_cfd_crrc_lognormal_template | traditional | CFD20/50 template time-walk baseline plus ridge-regularized derivative and curvature residual correction |
| ridge | linear ML | standardized ridge regression on pedestal, amplitude, CFD, waveform, derivative, and curvature features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled derivative feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform, detector-state, derivative, and curvature summaries |
| 1d_cnn | neural waveform | compact 1D convolutional regressor over normalized 18-sample waveforms |
| compact_waveform_transformer | neural waveform | one-layer waveform self-attention encoder inherited from the audited timing benchmark |
| shape_gate_transformer_new | new architecture | compact transformer over waveform, first derivative, second derivative, and pulse-shape gates with shape-residual pooling |

The new architecture is sensible for this ticket because the hypothesis is not generic waveform learning; it is that onset, late-tail, and curvature channels localize pulse-shape timing transfer failures across run/current blocks.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_crrc_lognormal_template | 5466 | 0.005831 | -0.4084 | 0.5269 | 1.008 | 0.8213 | 1.155 | 0.9867 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.3231 | -1.122 | 0.4347 | 3.799 | 3.268 | 4.366 | 6.477 | 0.2122 | 0.05891 |
| ridge | 5466 | 0.138 | -0.7376 | 1.19 | 4.065 | 3.643 | 4.785 | 6.688 | 0.2347 | 0.05671 |
| mlp | 5466 | -0.5612 | -1.474 | 0.6021 | 4.302 | 3.85 | 4.897 | 6.59 | 0.2517 | 0.06202 |
| shape_gate_transformer_new | 5466 | 0.9999 | 0.04263 | 2.227 | 4.916 | 4.297 | 5.932 | 7.627 | 0.3178 | 0.07611 |
| 1d_cnn | 5466 | -0.4766 | -1.481 | 0.7439 | 5.271 | 4.749 | 6.393 | 8.266 | 0.3372 | 0.1123 |
| compact_waveform_transformer | 5466 | 1.745 | 0.7103 | 2.574 | 6.789 | 6.45 | 7.683 | 9.306 | 0.4482 | 0.1815 |

## Paired Deltas Against Traditional CFD/Template Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional CFD/template comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_crrc_lognormal_template | 2.791 | 2.234 | 3.449 | -0.3289 | -1.324 | 0.5889 | 0.2122 |
| ridge | traditional_cfd_crrc_lognormal_template | 3.057 | 2.638 | 3.792 | 0.1322 | -0.9333 | 1.232 | 0.2347 |
| mlp | traditional_cfd_crrc_lognormal_template | 3.294 | 2.833 | 3.949 | -0.5671 | -1.641 | 0.607 | 0.2517 |
| shape_gate_transformer_new | traditional_cfd_crrc_lognormal_template | 3.908 | 3.269 | 4.912 | 0.9941 | -0.1677 | 2.308 | 0.3178 |
| 1d_cnn | traditional_cfd_crrc_lognormal_template | 4.264 | 3.7 | 5.449 | -0.4825 | -1.627 | 0.86 | 0.3372 |
| compact_waveform_transformer | traditional_cfd_crrc_lognormal_template | 5.781 | 5.44 | 6.714 | 1.739 | 0.5952 | 2.74 | 0.4482 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_crrc_lognormal_template | 1350 | -0.5595 | 0.7566 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.4117 | 3.379 | 0.2852 |
| sample_i_analysis | mlp | 1350 | 0.4174 | 4.58 | 0.3089 |
| sample_i_analysis | ridge | 1350 | 0.9397 | 5.55 | 0.3615 |
| sample_i_analysis | shape_gate_transformer_new | 1350 | 2.209 | 6.898 | 0.4948 |
| sample_i_analysis | 1d_cnn | 1350 | -0.6926 | 7.683 | 0.4304 |
| sample_i_analysis | compact_waveform_transformer | 1350 | 1.261 | 8.332 | 0.4593 |
| sample_i_calib | traditional_cfd_crrc_lognormal_template | 657 | -0.3543 | 1.408 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.355 | 3.838 | 0.2527 |
| sample_i_calib | ridge | 657 | 2.463 | 4.405 | 0.2892 |
| sample_i_calib | mlp | 657 | 1.758 | 4.425 | 0.2877 |
| sample_i_calib | shape_gate_transformer_new | 657 | 3.228 | 4.921 | 0.379 |
| sample_i_calib | 1d_cnn | 657 | 1.237 | 5.396 | 0.382 |
| sample_i_calib | compact_waveform_transformer | 657 | 2.722 | 6.868 | 0.4125 |
| sample_ii_analysis | traditional_cfd_crrc_lognormal_template | 2739 | 0.3482 | 0.9842 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.059 | 3.368 | 0.1566 |
| sample_ii_analysis | ridge | 2739 | -0.5197 | 3.562 | 0.1581 |
| sample_ii_analysis | mlp | 2739 | -1.137 | 3.834 | 0.2015 |
| sample_ii_analysis | shape_gate_transformer_new | 2739 | 0.4142 | 4.207 | 0.2304 |
| sample_ii_analysis | 1d_cnn | 2739 | -0.8436 | 4.839 | 0.2921 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | 1.386 | 6.625 | 0.4498 |
| sample_ii_calib | traditional_cfd_crrc_lognormal_template | 720 | 0.664 | 0.2684 | 0 |
| sample_ii_calib | ridge | 720 | -0.4123 | 4.236 | 0.2389 |
| sample_ii_calib | shape_gate_transformer_new | 720 | 0.8128 | 4.48 | 0.2625 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.077 | 4.698 | 0.25 |
| sample_ii_calib | 1d_cnn | 720 | -0.7672 | 4.727 | 0.2931 |
| sample_ii_calib | mlp | 720 | -1.575 | 5.181 | 0.3028 |
| sample_ii_calib | compact_waveform_transformer | 720 | 2.802 | 6.606 | 0.4542 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.237 | 5.396 | 0.382 |
| 1d_cnn | 50 | 680 | -2.258 | 15.16 | 0.4074 |
| 1d_cnn | 57 | 670 | 2.12 | 5.893 | 0.4537 |
| 1d_cnn | 58 | 654 | -2.014 | 5.444 | 0.3532 |
| 1d_cnn | 60 | 720 | 0.8404 | 4.28 | 0.2764 |
| 1d_cnn | 62 | 720 | -0.8585 | 4.431 | 0.2611 |
| 1d_cnn | 64 | 720 | -0.7672 | 4.727 | 0.2931 |
| 1d_cnn | 65 | 645 | -1.298 | 4.221 | 0.2822 |
| compact_waveform_transformer | 42 | 657 | 2.722 | 6.868 | 0.4125 |
| compact_waveform_transformer | 50 | 680 | -0.2267 | 16.82 | 0.4353 |
| compact_waveform_transformer | 57 | 670 | 3.566 | 7.327 | 0.4836 |
| compact_waveform_transformer | 58 | 654 | -0.1954 | 7.638 | 0.4817 |
| compact_waveform_transformer | 60 | 720 | 2.5 | 6.59 | 0.4653 |
| compact_waveform_transformer | 62 | 720 | 1.403 | 6.216 | 0.425 |
| compact_waveform_transformer | 64 | 720 | 2.802 | 6.606 | 0.4542 |
| compact_waveform_transformer | 65 | 645 | 1.386 | 6.326 | 0.4279 |
| shape_gate_transformer_new | 42 | 657 | 3.228 | 4.921 | 0.379 |
| shape_gate_transformer_new | 50 | 680 | -1.025 | 17.26 | 0.5471 |
| shape_gate_transformer_new | 57 | 670 | 3.898 | 5.139 | 0.4418 |
| shape_gate_transformer_new | 58 | 654 | -0.6082 | 4.744 | 0.2768 |
| shape_gate_transformer_new | 60 | 720 | 1.455 | 4.001 | 0.2333 |
| shape_gate_transformer_new | 62 | 720 | 0.4784 | 4.219 | 0.2222 |
| shape_gate_transformer_new | 64 | 720 | 0.8128 | 4.48 | 0.2625 |
| shape_gate_transformer_new | 65 | 645 | -0.5544 | 3.662 | 0.1891 |
| gradient_boosted_trees | 42 | 657 | 1.355 | 3.838 | 0.2527 |
| gradient_boosted_trees | 50 | 680 | -0.2055 | 14.11 | 0.2809 |
| gradient_boosted_trees | 57 | 670 | 1.337 | 4.356 | 0.2896 |
| gradient_boosted_trees | 58 | 654 | -2.102 | 3.436 | 0.2722 |
| gradient_boosted_trees | 60 | 720 | 0.09002 | 3.354 | 0.09861 |
| gradient_boosted_trees | 62 | 720 | -0.715 | 2.8 | 0.07917 |
| gradient_boosted_trees | 64 | 720 | -1.077 | 4.698 | 0.25 |
| gradient_boosted_trees | 65 | 645 | -1.882 | 3.034 | 0.1907 |
| mlp | 42 | 657 | 1.758 | 4.425 | 0.2877 |
| mlp | 50 | 680 | -0.8436 | 14.17 | 0.3015 |
| mlp | 57 | 670 | 2.01 | 5.279 | 0.3164 |
| mlp | 58 | 654 | -2.051 | 4.088 | 0.292 |
| mlp | 60 | 720 | -0.3046 | 3.956 | 0.2 |
| mlp | 62 | 720 | -0.9355 | 3.627 | 0.1375 |
| mlp | 64 | 720 | -1.575 | 5.181 | 0.3028 |
| mlp | 65 | 645 | -2.014 | 3.728 | 0.1829 |
| ridge | 42 | 657 | 2.463 | 4.405 | 0.2892 |
| ridge | 50 | 680 | -1.09 | 14.95 | 0.3662 |
| ridge | 57 | 670 | 3.118 | 5.005 | 0.3567 |
| ridge | 58 | 654 | -1.485 | 4.161 | 0.2385 |
| ridge | 60 | 720 | 0.606 | 3.38 | 0.1236 |
| ridge | 62 | 720 | -0.3821 | 3.144 | 0.1389 |
| ridge | 64 | 720 | -0.4123 | 4.236 | 0.2389 |
| ridge | 65 | 645 | -0.9965 | 3.141 | 0.1364 |
| traditional_cfd_crrc_lognormal_template | 42 | 657 | -0.3543 | 1.408 | 0 |
| traditional_cfd_crrc_lognormal_template | 50 | 680 | -0.4572 | 0.4968 | 0 |
| traditional_cfd_crrc_lognormal_template | 57 | 670 | -0.7666 | 1.145 | 0 |
| traditional_cfd_crrc_lognormal_template | 58 | 654 | 0.6316 | 0.9572 | 0 |
| traditional_cfd_crrc_lognormal_template | 60 | 720 | -0.6435 | 1.241 | 0 |
| traditional_cfd_crrc_lognormal_template | 62 | 720 | 0.1189 | 0.8099 | 0 |
| traditional_cfd_crrc_lognormal_template | 64 | 720 | 0.664 | 0.2684 | 0 |
| traditional_cfd_crrc_lognormal_template | 65 | 645 | 0.4397 | 0.8 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1579 | -1.184 | 6.323 | 0.4015 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1579 | -1.851 | 5.626 | 0.3813 |
| curvature_energy_bin | curved | shape_gate_transformer_new | 1579 | 1.032 | 5.818 | 0.3971 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1579 | -0.6184 | 3.776 | 0.2096 |
| curvature_energy_bin | curved | mlp | 1579 | -1.013 | 4.276 | 0.2799 |
| curvature_energy_bin | curved | ridge | 1579 | -0.6941 | 4.071 | 0.2489 |
| curvature_energy_bin | curved | traditional_cfd_crrc_lognormal_template | 1579 | -0.1441 | 1.086 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1998 | 0.2989 | 5.158 | 0.3418 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1998 | 2.749 | 6.636 | 0.4665 |
| curvature_energy_bin | moderate | shape_gate_transformer_new | 1998 | 1.282 | 4.856 | 0.3203 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1998 | -0.1249 | 4.008 | 0.2332 |
| curvature_energy_bin | moderate | mlp | 1998 | -0.1273 | 4.51 | 0.2603 |
| curvature_energy_bin | moderate | ridge | 1998 | 0.1411 | 4.139 | 0.2407 |
| curvature_energy_bin | moderate | traditional_cfd_crrc_lognormal_template | 1998 | 0.1525 | 0.9733 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1889 | -0.8785 | 4.607 | 0.2785 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1889 | 3.421 | 6.233 | 0.4849 |
| curvature_energy_bin | smooth | shape_gate_transformer_new | 1889 | 0.6852 | 4.396 | 0.2488 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1889 | -0.3672 | 3.484 | 0.1922 |
| curvature_energy_bin | smooth | mlp | 1889 | -0.6882 | 4.059 | 0.2192 |
| curvature_energy_bin | smooth | ridge | 1889 | 1.082 | 3.901 | 0.2165 |
| curvature_energy_bin | smooth | traditional_cfd_crrc_lognormal_template | 1889 | 0.005563 | 0.9767 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1859 | -0.9878 | 4.722 | 0.2867 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1859 | 2.286 | 6.311 | 0.4147 |
| derivative_onset_bin | nominal | shape_gate_transformer_new | 1859 | 0.8764 | 4.879 | 0.3141 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1859 | -0.6226 | 3.262 | 0.1737 |
| derivative_onset_bin | nominal | mlp | 1859 | -1.11 | 3.819 | 0.2259 |
| derivative_onset_bin | nominal | ridge | 1859 | -0.3939 | 3.91 | 0.2076 |
| derivative_onset_bin | nominal | traditional_cfd_crrc_lognormal_template | 1859 | 0.199 | 0.9843 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1943 | -0.4826 | 4.404 | 0.2573 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1943 | 2.657 | 6.384 | 0.4508 |
| derivative_onset_bin | sharp | shape_gate_transformer_new | 1943 | 0.973 | 4.392 | 0.245 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1943 | -0.7347 | 3.05 | 0.1544 |
| derivative_onset_bin | sharp | mlp | 1943 | -1.314 | 3.891 | 0.2126 |
| derivative_onset_bin | sharp | ridge | 1943 | -0.8522 | 3.854 | 0.1945 |
| derivative_onset_bin | sharp | traditional_cfd_crrc_lognormal_template | 1943 | 0.3096 | 0.9601 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1664 | 0.1754 | 8.913 | 0.4868 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1664 | -0.9252 | 8.2 | 0.4826 |
| derivative_onset_bin | slow | shape_gate_transformer_new | 1664 | 1.235 | 6.124 | 0.4069 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1664 | 0.9114 | 4.86 | 0.3227 |
| derivative_onset_bin | slow | mlp | 1664 | 1.197 | 4.78 | 0.3263 |
| derivative_onset_bin | slow | ridge | 1664 | 1.497 | 4.425 | 0.3119 |
| derivative_onset_bin | slow | traditional_cfd_crrc_lognormal_template | 1664 | -0.4064 | 1.02 | 0 |
| energy_bin | q1_low | 1d_cnn | 1463 | -0.8584 | 6.901 | 0.4183 |
| energy_bin | q1_low | compact_waveform_transformer | 1463 | 2.395 | 7.015 | 0.4757 |
| energy_bin | q1_low | shape_gate_transformer_new | 1463 | 0.1718 | 5.118 | 0.3274 |
| energy_bin | q1_low | gradient_boosted_trees | 1463 | -0.3094 | 3.76 | 0.2064 |
| energy_bin | q1_low | mlp | 1463 | -0.2979 | 4.085 | 0.2303 |
| energy_bin | q1_low | ridge | 1463 | 1.082 | 3.923 | 0.2358 |
| energy_bin | q1_low | traditional_cfd_crrc_lognormal_template | 1463 | -0.2723 | 1.109 | 0 |
| energy_bin | q2 | 1d_cnn | 1473 | -0.6066 | 4.451 | 0.2797 |
| energy_bin | q2 | compact_waveform_transformer | 1473 | 3.542 | 6.055 | 0.4582 |
| energy_bin | q2 | shape_gate_transformer_new | 1473 | 0.817 | 4.524 | 0.2654 |
| energy_bin | q2 | gradient_boosted_trees | 1473 | -0.01537 | 3.647 | 0.2186 |
| energy_bin | q2 | mlp | 1473 | -0.7907 | 4.432 | 0.2553 |
| energy_bin | q2 | ridge | 1473 | 0.2854 | 4.124 | 0.2254 |
| energy_bin | q2 | traditional_cfd_crrc_lognormal_template | 1473 | 0.2794 | 0.8937 | 0 |
| energy_bin | q3 | 1d_cnn | 1450 | 1.061 | 4.668 | 0.3069 |
| energy_bin | q3 | compact_waveform_transformer | 1450 | 2.093 | 6.771 | 0.4614 |
| energy_bin | q3 | shape_gate_transformer_new | 1450 | 1.441 | 4.804 | 0.3152 |
| energy_bin | q3 | gradient_boosted_trees | 1450 | -0.2713 | 3.812 | 0.211 |
| energy_bin | q3 | mlp | 1450 | -0.2816 | 4.517 | 0.2545 |
| energy_bin | q3 | ridge | 1450 | -0.09147 | 4.203 | 0.2455 |
| energy_bin | q3 | traditional_cfd_crrc_lognormal_template | 1450 | 0.339 | 0.992 | 0 |
| energy_bin | q4_high | 1d_cnn | 1080 | -2.031 | 4.738 | 0.3463 |
| energy_bin | q4_high | compact_waveform_transformer | 1080 | -2.353 | 5.448 | 0.3796 |
| energy_bin | q4_high | shape_gate_transformer_new | 1080 | 1.606 | 5.317 | 0.3796 |
| energy_bin | q4_high | gradient_boosted_trees | 1080 | -1.13 | 3.521 | 0.213 |
| energy_bin | q4_high | mlp | 1080 | -1.207 | 4.125 | 0.2722 |
| energy_bin | q4_high | ridge | 1080 | -0.7951 | 3.992 | 0.2315 |
| energy_bin | q4_high | traditional_cfd_crrc_lognormal_template | 1080 | -0.1128 | 1.094 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3297 | -0.6879 | 5.148 | 0.323 |
| late_tail_morphology | compact | compact_waveform_transformer | 3297 | 2.537 | 6.435 | 0.4471 |
| late_tail_morphology | compact | shape_gate_transformer_new | 3297 | 0.3136 | 4.846 | 0.3021 |
| late_tail_morphology | compact | gradient_boosted_trees | 3297 | -0.6968 | 3.493 | 0.1811 |
| late_tail_morphology | compact | mlp | 3297 | -1.206 | 4.017 | 0.2181 |
| late_tail_morphology | compact | ridge | 3297 | -0.3918 | 3.985 | 0.2181 |
| late_tail_morphology | compact | traditional_cfd_crrc_lognormal_template | 3297 | 0.1694 | 0.992 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 611 | -1.235 | 3.672 | 0.2553 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 611 | -0.616 | 5.051 | 0.3372 |
| late_tail_morphology | diffuse_tail | shape_gate_transformer_new | 611 | 1.21 | 3.483 | 0.2128 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 611 | 0.04975 | 3.09 | 0.1653 |
| late_tail_morphology | diffuse_tail | mlp | 611 | -0.08277 | 3.971 | 0.2308 |
| late_tail_morphology | diffuse_tail | ridge | 611 | -0.7175 | 3.536 | 0.18 |
| late_tail_morphology | diffuse_tail | traditional_cfd_crrc_lognormal_template | 611 | 0.3327 | 1.002 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 355 | -1.416 | 6.628 | 0.4056 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 355 | 0.8335 | 6.748 | 0.4366 |
| late_tail_morphology | late_derivative_bump | shape_gate_transformer_new | 355 | 3.474 | 5.148 | 0.4873 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 355 | -1.143 | 3.047 | 0.1831 |
| late_tail_morphology | late_derivative_bump | mlp | 355 | -1.617 | 3.746 | 0.2479 |
| late_tail_morphology | late_derivative_bump | ridge | 355 | -0.4421 | 3.585 | 0.2056 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_crrc_lognormal_template | 355 | -0.212 | 0.982 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1203 | 0.6084 | 6.1 | 0.3973 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1203 | 0.1014 | 9.661 | 0.5112 |
| late_tail_morphology | late_rising_tail | shape_gate_transformer_new | 1203 | 1.898 | 5.339 | 0.3641 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1203 | 0.8631 | 5.368 | 0.33 |
| late_tail_morphology | late_rising_tail | mlp | 1203 | 1.446 | 5.468 | 0.3558 |
| late_tail_morphology | late_rising_tail | ridge | 1203 | 1.756 | 4.388 | 0.3167 |
| late_tail_morphology | late_rising_tail | traditional_cfd_crrc_lognormal_template | 1203 | -0.4516 | 1.01 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1756 | -0.2192 | 7.447 | 0.4567 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1756 | -0.4643 | 6.964 | 0.4527 |
| pedestal_drift_bin | high | shape_gate_transformer_new | 1756 | 0.2867 | 5.992 | 0.4151 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1756 | -0.1305 | 4.206 | 0.254 |
| pedestal_drift_bin | high | mlp | 1756 | 0.002572 | 4.481 | 0.2733 |
| pedestal_drift_bin | high | ridge | 1756 | 0.296 | 4.319 | 0.2665 |
| pedestal_drift_bin | high | traditional_cfd_crrc_lognormal_template | 1756 | -0.1025 | 1.039 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1802 | -0.7086 | 4.603 | 0.2808 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1802 | 2.274 | 6.563 | 0.4434 |
| pedestal_drift_bin | low | shape_gate_transformer_new | 1802 | 1.156 | 4.63 | 0.2719 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1802 | -0.4869 | 3.261 | 0.1887 |
| pedestal_drift_bin | low | mlp | 1802 | -0.8431 | 3.973 | 0.237 |
| pedestal_drift_bin | low | ridge | 1802 | 0.05463 | 4.007 | 0.2264 |
| pedestal_drift_bin | low | traditional_cfd_crrc_lognormal_template | 1802 | 0.02326 | 0.9834 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1908 | -0.463 | 4.497 | 0.2804 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1908 | 2.576 | 6.44 | 0.4486 |
| pedestal_drift_bin | mid | shape_gate_transformer_new | 1908 | 1.332 | 4.434 | 0.2715 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1908 | -0.2962 | 3.682 | 0.196 |
| pedestal_drift_bin | mid | mlp | 1908 | -0.7554 | 4.202 | 0.2458 |
| pedestal_drift_bin | mid | ridge | 1908 | 0.07734 | 4.005 | 0.2133 |
| pedestal_drift_bin | mid | traditional_cfd_crrc_lognormal_template | 1908 | 0.1223 | 0.9808 | 0 |
| pid_sideband | central | 1d_cnn | 3786 | -0.2623 | 4.642 | 0.2882 |
| pid_sideband | central | compact_waveform_transformer | 3786 | 2.698 | 6.589 | 0.4654 |
| pid_sideband | central | shape_gate_transformer_new | 3786 | 1.312 | 4.61 | 0.2826 |
| pid_sideband | central | gradient_boosted_trees | 3786 | -0.3148 | 3.668 | 0.21 |
| pid_sideband | central | mlp | 3786 | -0.4462 | 4.303 | 0.2467 |
| pid_sideband | central | ridge | 3786 | 0.3553 | 4.137 | 0.2327 |
| pid_sideband | central | traditional_cfd_crrc_lognormal_template | 3786 | -0.03311 | 0.9849 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 868 | -1.27 | 10.05 | 0.6071 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 868 | -3.44 | 6.317 | 0.4044 |
| pid_sideband | high_duplicate | shape_gate_transformer_new | 868 | -2.582 | 5.904 | 0.5069 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 868 | -0.251 | 4.276 | 0.2523 |
| pid_sideband | high_duplicate | mlp | 868 | -0.4352 | 4.517 | 0.2742 |
| pid_sideband | high_duplicate | ridge | 868 | -0.3612 | 4.493 | 0.2903 |
| pid_sideband | high_duplicate | traditional_cfd_crrc_lognormal_template | 868 | -0.04711 | 1.046 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 812 | -0.8788 | 4.656 | 0.2771 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 812 | 1.65 | 6.349 | 0.415 |
| pid_sideband | low_duplicate | shape_gate_transformer_new | 812 | 1.628 | 4.145 | 0.2796 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 812 | -0.4372 | 3.536 | 0.1798 |
| pid_sideband | low_duplicate | mlp | 812 | -1.205 | 3.955 | 0.2512 |
| pid_sideband | low_duplicate | ridge | 812 | -0.4196 | 3.467 | 0.1847 |
| pid_sideband | low_duplicate | traditional_cfd_crrc_lognormal_template | 812 | 0.3067 | 1.023 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1713 | -1.512 | 4.861 | 0.3041 |
| pileup_separation_bin | close | compact_waveform_transformer | 1713 | 1.683 | 6.178 | 0.4174 |
| pileup_separation_bin | close | shape_gate_transformer_new | 1713 | 1.197 | 4.69 | 0.2668 |
| pileup_separation_bin | close | gradient_boosted_trees | 1713 | -0.8671 | 3.264 | 0.1699 |
| pileup_separation_bin | close | mlp | 1713 | -1.397 | 4.026 | 0.2411 |
| pileup_separation_bin | close | ridge | 1713 | -0.9237 | 3.959 | 0.2148 |
| pileup_separation_bin | close | traditional_cfd_crrc_lognormal_template | 1713 | 0.3527 | 0.9926 | 0 |
| pileup_separation_bin | late | 1d_cnn | 1 | 0.1001 | 0 | 0 |
| pileup_separation_bin | late | compact_waveform_transformer | 1 | -7.007 | 0 | 1 |
| pileup_separation_bin | late | shape_gate_transformer_new | 1 | 4.766 | 0 | 0 |
| pileup_separation_bin | late | gradient_boosted_trees | 1 | -1.031 | 0 | 0 |
| pileup_separation_bin | late | mlp | 1 | 6.648 | 0 | 1 |
| pileup_separation_bin | late | ridge | 1 | 1.448 | 0 | 0 |
| pileup_separation_bin | late | traditional_cfd_crrc_lognormal_template | 1 | -1.144 | 0 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1162 | 0.392 | 5.963 | 0.4002 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1162 | -1.229 | 5.608 | 0.3838 |
| pileup_separation_bin | mid | shape_gate_transformer_new | 1162 | -0.09671 | 5.705 | 0.4062 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1162 | -0.9327 | 3.622 | 0.1962 |
| pileup_separation_bin | mid | mlp | 1162 | -1.11 | 3.9 | 0.2238 |
| pileup_separation_bin | mid | ridge | 1162 | -0.6804 | 4.051 | 0.2367 |
| pileup_separation_bin | mid | traditional_cfd_crrc_lognormal_template | 1162 | 0.1706 | 1.015 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2590 | -0.03693 | 5.099 | 0.3309 |
| pileup_separation_bin | none | compact_waveform_transformer | 2590 | 2.992 | 7.19 | 0.4973 |
| pileup_separation_bin | none | shape_gate_transformer_new | 2590 | 1.265 | 4.588 | 0.312 |
| pileup_separation_bin | none | gradient_boosted_trees | 2590 | 0.3084 | 4.005 | 0.2475 |
| pileup_separation_bin | none | mlp | 2590 | 0.2693 | 4.395 | 0.271 |
| pileup_separation_bin | none | ridge | 2590 | 1.121 | 3.761 | 0.2471 |
| pileup_separation_bin | none | traditional_cfd_crrc_lognormal_template | 2590 | -0.2065 | 0.9695 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1884 | -0.2094 | 6.633 | 0.4214 |
| pulse_shape_class | compact | compact_waveform_transformer | 1884 | 1.64 | 6.772 | 0.4655 |
| pulse_shape_class | compact | shape_gate_transformer_new | 1884 | -1.151 | 5.093 | 0.336 |
| pulse_shape_class | compact | gradient_boosted_trees | 1884 | -0.881 | 3.943 | 0.2028 |
| pulse_shape_class | compact | mlp | 1884 | -1.318 | 4.326 | 0.2325 |
| pulse_shape_class | compact | ridge | 1884 | -0.2393 | 4.424 | 0.2495 |
| pulse_shape_class | compact | traditional_cfd_crrc_lognormal_template | 1884 | 0.07371 | 1.047 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1838 | -0.08874 | 5.57 | 0.3482 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1838 | -0.09681 | 7.269 | 0.4499 |
| pulse_shape_class | late_tail | shape_gate_transformer_new | 1838 | 1.583 | 4.562 | 0.3107 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1838 | 0.4541 | 4.342 | 0.2715 |
| pulse_shape_class | late_tail | mlp | 1838 | 0.7919 | 4.716 | 0.3118 |
| pulse_shape_class | late_tail | ridge | 1838 | 1.027 | 4.137 | 0.2704 |
| pulse_shape_class | late_tail | traditional_cfd_crrc_lognormal_template | 1838 | -0.189 | 1.003 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1744 | -0.9753 | 4.143 | 0.2345 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1744 | 2.997 | 5.81 | 0.4278 |
| pulse_shape_class | nominal | shape_gate_transformer_new | 1744 | 1.353 | 4.304 | 0.3056 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1744 | -0.5 | 2.926 | 0.16 |
| pulse_shape_class | nominal | mlp | 1744 | -1.202 | 3.554 | 0.2093 |
| pulse_shape_class | nominal | ridge | 1744 | -0.4451 | 3.603 | 0.1812 |
| pulse_shape_class | nominal | traditional_cfd_crrc_lognormal_template | 1744 | 0.2047 | 0.9241 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3986 | -0.168 | 5.547 | 0.3532 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3986 | 1.64 | 7.075 | 0.4686 |
| saturation_onset_bin | linear | shape_gate_transformer_new | 3986 | 0.7463 | 4.89 | 0.3108 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3986 | -0.3279 | 3.82 | 0.212 |
| saturation_onset_bin | linear | mlp | 3986 | -0.5099 | 4.295 | 0.2491 |
| saturation_onset_bin | linear | ridge | 3986 | 0.1736 | 4.096 | 0.2376 |
| saturation_onset_bin | linear | traditional_cfd_crrc_lognormal_template | 3986 | 0.06118 | 1.025 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1480 | -1.053 | 4.7 | 0.2939 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1480 | 1.999 | 5.975 | 0.3932 |
| saturation_onset_bin | near_saturation | shape_gate_transformer_new | 1480 | 1.785 | 4.983 | 0.3365 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1480 | -0.3043 | 3.687 | 0.2128 |
| saturation_onset_bin | near_saturation | mlp | 1480 | -0.7272 | 4.307 | 0.2588 |
| saturation_onset_bin | near_saturation | ridge | 1480 | 0.03693 | 3.995 | 0.227 |
| saturation_onset_bin | near_saturation | traditional_cfd_crrc_lognormal_template | 1480 | -0.1635 | 0.9511 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.607 | curved | 6.323 | 1.716 |
| curvature_energy_bin | shape_gate_transformer_new | 3 | smooth | 4.396 | curved | 5.818 | 1.422 |
| curvature_energy_bin | compact_waveform_transformer | 3 | curved | 5.626 | moderate | 6.636 | 1.01 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.484 | moderate | 4.008 | 0.5238 |
| curvature_energy_bin | mlp | 3 | smooth | 4.059 | moderate | 4.51 | 0.4506 |
| curvature_energy_bin | ridge | 3 | smooth | 3.901 | moderate | 4.139 | 0.2375 |
| curvature_energy_bin | traditional_cfd_crrc_lognormal_template | 3 | moderate | 0.9733 | curved | 1.086 | 0.1126 |
| derivative_onset_bin | 1d_cnn | 3 | sharp | 4.404 | slow | 8.913 | 4.509 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 6.311 | slow | 8.2 | 1.889 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.05 | slow | 4.86 | 1.81 |
| derivative_onset_bin | shape_gate_transformer_new | 3 | sharp | 4.392 | slow | 6.124 | 1.732 |
| derivative_onset_bin | mlp | 3 | nominal | 3.819 | slow | 4.78 | 0.9609 |
| derivative_onset_bin | ridge | 3 | sharp | 3.854 | slow | 4.425 | 0.5706 |
| derivative_onset_bin | traditional_cfd_crrc_lognormal_template | 3 | sharp | 0.9601 | slow | 1.02 | 0.05965 |
| energy_bin | 1d_cnn | 4 | q2 | 4.451 | q1_low | 6.901 | 2.45 |
| energy_bin | compact_waveform_transformer | 4 | q4_high | 5.448 | q1_low | 7.015 | 1.567 |
| energy_bin | shape_gate_transformer_new | 4 | q2 | 4.524 | q4_high | 5.317 | 0.7934 |
| energy_bin | mlp | 4 | q1_low | 4.085 | q3 | 4.517 | 0.4322 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.521 | q3 | 3.812 | 0.2916 |
| energy_bin | ridge | 4 | q1_low | 3.923 | q3 | 4.203 | 0.2796 |
| energy_bin | traditional_cfd_crrc_lognormal_template | 4 | q2 | 0.8937 | q1_low | 1.109 | 0.2152 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 5.051 | late_rising_tail | 9.661 | 4.61 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 3.672 | late_derivative_bump | 6.628 | 2.956 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 3.047 | late_rising_tail | 5.368 | 2.321 |
| late_tail_morphology | shape_gate_transformer_new | 4 | diffuse_tail | 3.483 | late_rising_tail | 5.339 | 1.856 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.746 | late_rising_tail | 5.468 | 1.722 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.536 | late_rising_tail | 4.388 | 0.8523 |
| late_tail_morphology | traditional_cfd_crrc_lognormal_template | 4 | late_derivative_bump | 0.982 | late_rising_tail | 1.01 | 0.02829 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 4.497 | high | 7.447 | 2.95 |
| pedestal_drift_bin | shape_gate_transformer_new | 3 | mid | 4.434 | high | 5.992 | 1.558 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.261 | high | 4.206 | 0.9455 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 6.44 | high | 6.964 | 0.524 |
| pedestal_drift_bin | mlp | 3 | low | 3.973 | high | 4.481 | 0.5075 |
| pedestal_drift_bin | ridge | 3 | mid | 4.005 | high | 4.319 | 0.3133 |
| pedestal_drift_bin | traditional_cfd_crrc_lognormal_template | 3 | mid | 0.9808 | high | 1.039 | 0.05849 |
| pid_sideband | 1d_cnn | 3 | central | 4.642 | high_duplicate | 10.05 | 5.412 |
| pid_sideband | shape_gate_transformer_new | 3 | low_duplicate | 4.145 | high_duplicate | 5.904 | 1.759 |
| pid_sideband | ridge | 3 | low_duplicate | 3.467 | high_duplicate | 4.493 | 1.027 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.536 | high_duplicate | 4.276 | 0.7408 |
| pid_sideband | mlp | 3 | low_duplicate | 3.955 | high_duplicate | 4.517 | 0.5623 |
| pid_sideband | compact_waveform_transformer | 3 | high_duplicate | 6.317 | central | 6.589 | 0.2727 |
| pid_sideband | traditional_cfd_crrc_lognormal_template | 3 | central | 0.9849 | high_duplicate | 1.046 | 0.06143 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 0 | none | 7.19 | 7.19 |
| pileup_separation_bin | 1d_cnn | 4 | late | 0 | mid | 5.963 | 5.963 |
| pileup_separation_bin | shape_gate_transformer_new | 4 | late | 0 | mid | 5.705 | 5.705 |
| pileup_separation_bin | mlp | 4 | late | 0 | none | 4.395 | 4.395 |
| pileup_separation_bin | ridge | 4 | late | 0 | mid | 4.051 | 4.051 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 0 | none | 4.005 | 4.005 |
| pileup_separation_bin | traditional_cfd_crrc_lognormal_template | 4 | late | 0 | mid | 1.015 | 1.015 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.143 | compact | 6.633 | 2.49 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.81 | late_tail | 7.269 | 1.459 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.926 | late_tail | 4.342 | 1.416 |
| pulse_shape_class | mlp | 3 | nominal | 3.554 | late_tail | 4.716 | 1.162 |
| pulse_shape_class | ridge | 3 | nominal | 3.603 | compact | 4.424 | 0.8209 |
| pulse_shape_class | shape_gate_transformer_new | 3 | nominal | 4.304 | compact | 5.093 | 0.7885 |
| pulse_shape_class | traditional_cfd_crrc_lognormal_template | 3 | nominal | 0.9241 | compact | 1.047 | 0.123 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.975 | linear | 7.075 | 1.1 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.7 | linear | 5.547 | 0.8463 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.687 | linear | 3.82 | 0.1327 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.995 | linear | 4.096 | 0.1016 |
| saturation_onset_bin | shape_gate_transformer_new | 2 | linear | 4.89 | near_saturation | 4.983 | 0.09287 |
| saturation_onset_bin | traditional_cfd_crrc_lognormal_template | 2 | near_saturation | 0.9511 | linear | 1.025 | 0.07374 |
| saturation_onset_bin | mlp | 2 | linear | 4.295 | near_saturation | 4.307 | 0.01251 |

## Pedestal, Censored-Sample, and Shape Ablations

The ablations use the gradient-boosted-tree learner to isolate whether transfer comes from onset derivatives, late-tail curvature, pretrigger pedestal subtraction, or non-derivative CFD/amplitude information.  The `drop_derivative_features` and localized tail/onset windows are treated as censored-sample stress tests because they remove the waveform regions most affected by saturation and pile-up censoring.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_derivative_gradient_boosted_trees | 76 | -0.3543 | 3.764 | 3.114 | 4.351 | 0 | 0.2162 |
| drop_derivative_features | 33 | -0.3198 | 3.784 | 3.282 | 4.402 | 0.01956 | 0.2161 |
| derivative_only | 43 | 0.09511 | 4.157 | 3.607 | 4.731 | 0.3925 | 0.2428 |
| amplitude_cfd_no_derivative | 5 | 0.1985 | 4.175 | 3.648 | 4.769 | 0.4111 | 0.2466 |
| late_tail_curvature_window_only | 17 | 0.3553 | 4.546 | 4.134 | 5.041 | 0.7819 | 0.2827 |
| onset_derivative_window_only | 14 | -0.0926 | 4.861 | 4.018 | 6.1 | 1.097 | 0.3086 |
| pretrigger_derivative_only | 7 | -3.403 | 18.97 | 17.45 | 20.15 | 15.21 | 0.5904 |


## Pulse-Shape Transfer Diagnostics

The raw ROOT stream provides 18 digitized samples per channel but not an
external truth waveform for each pulse.  Pulse-shape transfer is therefore
reported through run/stave-centered, leakage-controlled shape coordinates:
onset slope, late slope, tail fraction, and curvature energy.  These are not
used as independent truth labels; they quantify whether timing residuals align
with shape modes that should transfer under a stable reference pulser.

| method | n | median_abs_timing_residual_ns | median_abs_timing_residual_ns_ci_low | median_abs_timing_residual_ns_ci_high | onset_slope_sum_mad | onset_slope_sum_corr_with_timing_error | tail_fraction_corr_with_timing_error | curvature_energy_corr_with_timing_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_crrc_lognormal_template | 5466 | 0.7648 | 0.6203 | 0.893 | 0.02704 | 0.1322 | 0.1019 | -0.02384 |
| gradient_boosted_trees | 5466 | 2.202 | 1.921 | 2.552 | 0.02704 | -0.336 | 0.07368 | -0.007278 |
| ridge | 5466 | 2.73 | 2.313 | 3.168 | 0.02704 | -0.3364 | 0.08036 | 0.03082 |
| mlp | 5466 | 2.771 | 2.501 | 3.007 | 0.02704 | -0.3379 | 0.05905 | -0.03182 |
| 1d_cnn | 5466 | 3.393 | 3.114 | 3.71 | 0.02704 | -0.2372 | 0.08126 | 0.1222 |
| shape_gate_transformer_new | 5466 | 3.476 | 3.033 | 4.252 | 0.02704 | -0.1801 | 0.1373 | 0.06291 |
| compact_waveform_transformer | 5466 | 4.431 | 4.214 | 4.655 | 0.02704 | -0.1947 | 0.1633 | -0.008442 |

The ticket-local ablation table `pedestal_censored_ablation.csv` annotates
which feature removals correspond to pedestal-subtraction and censored
sample-region stress tests.

## Interpretation, Systematics, and Caveats

This S59a benchmark measures relative transfer on reproducible waveform-derived timing and pulse-shape residual proxies.  The raw ROOT files do not contain an independent external
picosecond timing truth for each pulse, so the numerical winner should not be
read as an absolute detector timing limit.  It answers the narrower ticket
question: whether derivative/curvature descriptions improve run-held-out
arrival-time residual prediction beyond a strong CFD/template derivative fit.

The run-block bootstrap is deliberately conservative for data-taking-period
transfer and can produce wider intervals than event bootstrap.  Neural models
are compact and trained under a fixed small epoch budget suitable for this
laptop worker; the study tests whether derivative-aware architectures naturally
outperform transparent timing fits, not whether exhaustive architecture search
can overfit the proxy.  Pedestal drift strata use raw pretrigger baseline
displacement from the run/stave median, so they are useful diagnostics but not
external electronics-state labels.

The result is consistent with the recent S41a/S40b timing family if the
traditional method remains competitive: transparent CFD/template corrections
capture most of the stable sub-sample timing signal, while derivative features
mainly expose where late tails and pedestal wander destabilize learned models.

Ticket-local wrapper runtime was `203.3 s`; benchmark runtime was `203.3 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.11.14`.
