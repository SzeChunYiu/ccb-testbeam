# S55a/#2497: residual-shape atlas: matched-template fits vs neural embeddings

## Abstract

Ticket `2497` asks for a pulse shape and timing
identifiability atlas across stave, run family, amplitude, peak phase,
pedestal state, and mild pile-up strata.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
median-template time-walk, and shape-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `shape_time_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_median_template_cfd_timewalk_shape`** as the
winner with `sigma_68 = 0.9258 ns`
`[0.6779, 1.074]`.  The
traditional shape-time comparator obtains `0.9258 ns`
`[0.6779, 1.074]`.

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
| heldout | 4926 |
| train | 13747 |

Confidence intervals use `300` paired percentile
bootstrap replicates that resample held-out runs with replacement.  Paired
deltas subtract each replicate of the traditional shape-time comparator from
the corresponding replicate of the learned method.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_median_template_cfd_timewalk_shape | traditional | aligned median-template CFD/optimal-filter timing, explicit time-walk terms, and ridge-regularized shape/curvature residual correction |
| ridge | linear ML | standardized ridge regression on pedestal, amplitude, CFD, waveform, derivative, curvature, and hand pulse-shape features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled waveform-summary feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform, detector-state, derivative, curvature, and q-template summaries |
| 1d_cnn | neural waveform | compact 1D convolutional regressor over normalized 18-sample waveforms |
| compact_waveform_transformer | neural waveform | one-layer waveform self-attention encoder inherited from the audited timing benchmark |
| shape_time_gate_transformer_new | new architecture | compact transformer over waveform, first derivative, and second derivative channels with shape/time derivative-magnitude pooling |

The new architecture is sensible for this ticket because the hypothesis is not
generic waveform learning; it is that edge, curvature, and normalized
shape-template channels localize pulse-shape timing changes under pedestal
drift.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_median_template_cfd_timewalk_shape | 4926 | 0.3905 | -0.1845 | 0.6028 | 0.9258 | 0.6779 | 1.074 | 0.9458 | 0.9938 | 0.1816 | 0 | 0 |
| gradient_boosted_trees | 4926 | -0.4873 | -1.433 | 0.4438 | 3.331 | 2.716 | 3.775 | 3.984 | 1.014 | 0.1816 | 0.1445 | 0.02862 |
| mlp | 4926 | -0.5415 | -1.521 | 0.348 | 3.802 | 3.36 | 4.287 | 4.278 | 1.005 | 0.1816 | 0.1929 | 0.02984 |
| ridge | 4926 | -0.02735 | -0.6761 | 0.4589 | 3.92 | 3.403 | 4.479 | 4.467 | 1.016 | 0.1816 | 0.2024 | 0.03532 |
| shape_time_gate_transformer_new | 4926 | 0.2285 | -0.7169 | 0.8334 | 5.309 | 4.958 | 5.794 | 7.017 | 0.9735 | 0.1816 | 0.3494 | 0.08993 |
| 1d_cnn | 4926 | 0.516 | -0.4295 | 1.158 | 5.541 | 5.01 | 6.275 | 7.078 | 1.02 | 0.1816 | 0.3693 | 0.1027 |
| compact_waveform_transformer | 4926 | 1.252 | 0.3797 | 2.018 | 6.146 | 5.856 | 6.586 | 7.026 | 1.038 | 0.1816 | 0.4359 | 0.1133 |

## Paired Deltas Against Traditional Shape-Time Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional shape-time comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_median_template_cfd_timewalk_shape | 2.405 | 1.741 | 2.963 | -0.8777 | -1.793 | 0.2282 | 0.1445 |
| mlp | traditional_median_template_cfd_timewalk_shape | 2.876 | 2.407 | 3.405 | -0.932 | -1.878 | 0.1497 | 0.1929 |
| ridge | traditional_median_template_cfd_timewalk_shape | 2.995 | 2.48 | 3.602 | -0.4178 | -1.097 | 0.3447 | 0.2024 |
| shape_time_gate_transformer_new | traditional_median_template_cfd_timewalk_shape | 4.383 | 4.001 | 4.931 | -0.1619 | -1.144 | 0.6915 | 0.3494 |
| 1d_cnn | traditional_median_template_cfd_timewalk_shape | 4.616 | 4.052 | 5.362 | 0.1256 | -0.7712 | 1.046 | 0.3693 |
| compact_waveform_transformer | traditional_median_template_cfd_timewalk_shape | 5.22 | 4.912 | 5.767 | 0.8618 | -0.1109 | 1.787 | 0.4359 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_median_template_cfd_timewalk_shape | 1230 | -0.3463 | 0.9114 | 0.9952 | 0.2063 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1230 | 0.6097 | 2.522 | 1.015 | 0.2063 | 0.2008 |
| sample_i_analysis | mlp | 1230 | 0.5503 | 3.406 | 1.006 | 0.2063 | 0.226 |
| sample_i_analysis | ridge | 1230 | 0.5757 | 4.696 | 1.01 | 0.2063 | 0.2764 |
| sample_i_analysis | shape_time_gate_transformer_new | 1230 | 0.2535 | 6.154 | 0.9777 | 0.2063 | 0.4106 |
| sample_i_analysis | 1d_cnn | 1230 | 0.6882 | 6.787 | 1.021 | 0.2063 | 0.4732 |
| sample_i_analysis | compact_waveform_transformer | 1230 | 1.121 | 6.878 | 1.035 | 0.2063 | 0.4528 |
| sample_i_calib | traditional_median_template_cfd_timewalk_shape | 597 | -0.1423 | 1.125 | 0.997 | 0.1983 | 0 |
| sample_i_calib | gradient_boosted_trees | 597 | 1.2 | 2.716 | 1.017 | 0.1983 | 0.1106 |
| sample_i_calib | mlp | 597 | 1.15 | 3.096 | 1.012 | 0.1983 | 0.1441 |
| sample_i_calib | ridge | 597 | 0.8404 | 3.912 | 1.026 | 0.1983 | 0.2529 |
| sample_i_calib | shape_time_gate_transformer_new | 597 | 0.4608 | 5.363 | 0.9832 | 0.1983 | 0.3518 |
| sample_i_calib | 1d_cnn | 597 | 1.911 | 5.79 | 1.027 | 0.1983 | 0.3903 |
| sample_i_calib | compact_waveform_transformer | 597 | 2.173 | 5.807 | 1.048 | 0.1983 | 0.4322 |
| sample_ii_analysis | traditional_median_template_cfd_timewalk_shape | 2459 | 0.5373 | 0.7521 | 0.9953 | 0.1717 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2459 | -1.336 | 3.417 | 1.006 | 0.1717 | 0.1403 |
| sample_ii_analysis | ridge | 2459 | -0.4415 | 3.684 | 1.012 | 0.1717 | 0.1765 |
| sample_ii_analysis | mlp | 2459 | -1.27 | 3.934 | 0.9977 | 0.1717 | 0.2041 |
| sample_ii_analysis | shape_time_gate_transformer_new | 2459 | 0.1291 | 5.096 | 0.962 | 0.1717 | 0.3335 |
| sample_ii_analysis | 1d_cnn | 2459 | 0.2501 | 5.235 | 1.009 | 0.1717 | 0.3347 |
| sample_ii_analysis | compact_waveform_transformer | 2459 | 1.115 | 6.218 | 1.029 | 0.1717 | 0.44 |
| sample_ii_calib | traditional_median_template_cfd_timewalk_shape | 640 | 0.6799 | 0.4365 | 0.9933 | 0.1565 | 0 |
| sample_ii_calib | gradient_boosted_trees | 640 | -1.292 | 3.083 | 1.022 | 0.1565 | 0.08438 |
| sample_ii_calib | ridge | 640 | -0.7394 | 3.196 | 1.026 | 0.1565 | 0.1125 |
| sample_ii_calib | mlp | 640 | -1.525 | 3.654 | 1.01 | 0.1565 | 0.1313 |
| sample_ii_calib | 1d_cnn | 640 | -0.1964 | 4.678 | 1.028 | 0.1565 | 0.2828 |
| sample_ii_calib | shape_time_gate_transformer_new | 640 | 0.2412 | 4.709 | 0.9868 | 0.1565 | 0.2906 |
| sample_ii_calib | compact_waveform_transformer | 640 | 1.287 | 5.709 | 1.062 | 0.1565 | 0.3906 |

| method | run | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 597 | 1.911 | 5.79 | 1.027 | 0.1983 | 0.3903 |
| 1d_cnn | 50 | 620 | -0.3517 | 8.323 | 1.015 | 0.188 | 0.4887 |
| 1d_cnn | 57 | 610 | 1.809 | 5.743 | 1.031 | 0.225 | 0.4574 |
| 1d_cnn | 58 | 594 | -2.445 | 5.807 | 1.022 | 0.1957 | 0.3704 |
| 1d_cnn | 60 | 640 | 1.398 | 4.928 | 0.9795 | 0.1742 | 0.3484 |
| 1d_cnn | 62 | 640 | 0.7839 | 5.012 | 0.9968 | 0.1698 | 0.3234 |
| 1d_cnn | 64 | 640 | -0.1964 | 4.678 | 1.028 | 0.1565 | 0.2828 |
| 1d_cnn | 65 | 585 | 0.5422 | 4.729 | 1.05 | 0.1466 | 0.2957 |
| compact_waveform_transformer | 42 | 597 | 2.173 | 5.807 | 1.048 | 0.1983 | 0.4322 |
| compact_waveform_transformer | 50 | 620 | 0.0237 | 7.84 | 1.028 | 0.188 | 0.4758 |
| compact_waveform_transformer | 57 | 610 | 2.419 | 5.948 | 1.046 | 0.225 | 0.4295 |
| compact_waveform_transformer | 58 | 594 | -1.05 | 5.911 | 1.03 | 0.1957 | 0.4108 |
| compact_waveform_transformer | 60 | 640 | 2.588 | 6.479 | 1.03 | 0.1742 | 0.4828 |
| compact_waveform_transformer | 62 | 640 | 1.416 | 6.042 | 1.04 | 0.1698 | 0.4375 |
| compact_waveform_transformer | 64 | 640 | 1.287 | 5.709 | 1.062 | 0.1565 | 0.3906 |
| compact_waveform_transformer | 65 | 585 | 1.315 | 5.594 | 1.049 | 0.1466 | 0.4256 |
| gradient_boosted_trees | 42 | 597 | 1.2 | 2.716 | 1.017 | 0.1983 | 0.1106 |
| gradient_boosted_trees | 50 | 620 | 0.7259 | 6.924 | 1.002 | 0.188 | 0.3113 |
| gradient_boosted_trees | 57 | 610 | 0.4504 | 1.998 | 1.03 | 0.225 | 0.08852 |
| gradient_boosted_trees | 58 | 594 | -2.931 | 2.462 | 1.028 | 0.1957 | 0.229 |
| gradient_boosted_trees | 60 | 640 | -0.2807 | 3.578 | 1.006 | 0.1742 | 0.1203 |
| gradient_boosted_trees | 62 | 640 | -0.574 | 2.734 | 0.9995 | 0.1698 | 0.07031 |
| gradient_boosted_trees | 64 | 640 | -1.292 | 3.083 | 1.022 | 0.1565 | 0.08438 |
| gradient_boosted_trees | 65 | 585 | -1.684 | 3.672 | 1.017 | 0.1466 | 0.1487 |
| mlp | 42 | 597 | 1.15 | 3.096 | 1.012 | 0.1983 | 0.1441 |
| mlp | 50 | 620 | 0.395 | 6.85 | 0.9978 | 0.188 | 0.3548 |
| mlp | 57 | 610 | 0.6557 | 2.809 | 1.016 | 0.225 | 0.09508 |
| mlp | 58 | 594 | -2.413 | 3.407 | 1.018 | 0.1957 | 0.2643 |
| mlp | 60 | 640 | -0.3467 | 4.123 | 0.9953 | 0.1742 | 0.2078 |
| mlp | 62 | 640 | -0.5565 | 3.495 | 1.009 | 0.1698 | 0.1281 |
| mlp | 64 | 640 | -1.525 | 3.654 | 1.01 | 0.1565 | 0.1313 |
| mlp | 65 | 585 | -1.781 | 4.379 | 1.001 | 0.1466 | 0.2222 |
| ridge | 42 | 597 | 0.8404 | 3.912 | 1.026 | 0.1983 | 0.2529 |
| ridge | 50 | 620 | 0.09624 | 7.604 | 1.002 | 0.188 | 0.3952 |
| ridge | 57 | 610 | 1.199 | 3.748 | 1.021 | 0.225 | 0.1557 |
| ridge | 58 | 594 | -2.213 | 3.848 | 1.018 | 0.1957 | 0.2811 |
| ridge | 60 | 640 | 0.5199 | 3.46 | 1.023 | 0.1742 | 0.1406 |
| ridge | 62 | 640 | -0.03582 | 3.183 | 1.028 | 0.1698 | 0.1109 |
| ridge | 64 | 640 | -0.7394 | 3.196 | 1.026 | 0.1565 | 0.1125 |
| ridge | 65 | 585 | -0.348 | 3.79 | 1.019 | 0.1466 | 0.1812 |
| shape_time_gate_transformer_new | 42 | 597 | 0.4608 | 5.363 | 0.9832 | 0.1983 | 0.3518 |
| shape_time_gate_transformer_new | 50 | 620 | 0.05547 | 8.244 | 0.9671 | 0.188 | 0.4274 |
| shape_time_gate_transformer_new | 57 | 610 | 0.6184 | 5.585 | 0.9903 | 0.225 | 0.3934 |
| shape_time_gate_transformer_new | 58 | 594 | -2.489 | 5.299 | 0.9685 | 0.1957 | 0.4007 |
| shape_time_gate_transformer_new | 60 | 640 | 1.381 | 4.841 | 0.9534 | 0.1742 | 0.3125 |
| shape_time_gate_transformer_new | 62 | 640 | 1.167 | 5.11 | 0.9669 | 0.1698 | 0.3312 |
| shape_time_gate_transformer_new | 64 | 640 | 0.2412 | 4.709 | 0.9868 | 0.1565 | 0.2906 |
| shape_time_gate_transformer_new | 65 | 585 | 0.001079 | 4.694 | 0.9804 | 0.1466 | 0.2906 |
| traditional_median_template_cfd_timewalk_shape | 42 | 597 | -0.1423 | 1.125 | 0.997 | 0.1983 | 0 |
| traditional_median_template_cfd_timewalk_shape | 50 | 620 | 0.2429 | 0.7341 | 0.9962 | 0.188 | 0 |
| traditional_median_template_cfd_timewalk_shape | 57 | 610 | -0.889 | 0.5849 | 0.9948 | 0.225 | 0 |
| traditional_median_template_cfd_timewalk_shape | 58 | 594 | 0.8603 | 0.5433 | 0.9927 | 0.1957 | 0 |
| traditional_median_template_cfd_timewalk_shape | 60 | 640 | 0.3682 | 0.6384 | 0.9936 | 0.1742 | 0 |
| traditional_median_template_cfd_timewalk_shape | 62 | 640 | 0.4559 | 1.12 | 0.9978 | 0.1698 | 0 |
| traditional_median_template_cfd_timewalk_shape | 64 | 640 | 0.6799 | 0.4365 | 0.9933 | 0.1565 | 0 |
| traditional_median_template_cfd_timewalk_shape | 65 | 585 | 0.6651 | 0.6136 | 0.9924 | 0.1466 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1409 | 0.1947 | 6.578 | 0.9484 | 0.3492 | 0.4422 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1409 | -2.486 | 5.956 | 1.036 | 0.3492 | 0.4322 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1409 | -0.7564 | 3.371 | 1.008 | 0.3492 | 0.1561 |
| curvature_energy_bin | curved | mlp | 1409 | -0.8986 | 3.958 | 0.9967 | 0.3492 | 0.2193 |
| curvature_energy_bin | curved | ridge | 1409 | -0.5914 | 3.864 | 1.001 | 0.3492 | 0.2271 |
| curvature_energy_bin | curved | shape_time_gate_transformer_new | 1409 | -0.07217 | 5.786 | 0.9237 | 0.3492 | 0.3903 |
| curvature_energy_bin | curved | traditional_median_template_cfd_timewalk_shape | 1409 | 0.5047 | 1.035 | 0.9955 | 0.3492 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1820 | 1.199 | 4.759 | 1.029 | 0.1165 | 0.3286 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1820 | 3.168 | 6.179 | 1.04 | 0.1165 | 0.4775 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1820 | -0.3483 | 3.18 | 1.01 | 0.1165 | 0.1456 |
| curvature_energy_bin | moderate | mlp | 1820 | -0.4384 | 3.708 | 1.002 | 0.1165 | 0.1736 |
| curvature_energy_bin | moderate | ridge | 1820 | -0.1018 | 4.001 | 1.015 | 0.1165 | 0.1956 |
| curvature_energy_bin | moderate | shape_time_gate_transformer_new | 1820 | 0.2894 | 5.473 | 0.96 | 0.1165 | 0.3681 |
| curvature_energy_bin | moderate | traditional_median_template_cfd_timewalk_shape | 1820 | 0.4568 | 0.8544 | 0.9943 | 0.1165 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1697 | -0.1542 | 5.346 | 1.059 | 0.1122 | 0.3524 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1697 | 2.074 | 4.749 | 1.012 | 0.1122 | 0.3942 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1697 | -0.4445 | 3.209 | 1.018 | 0.1122 | 0.1338 |
| curvature_energy_bin | smooth | mlp | 1697 | -0.4167 | 3.655 | 1.008 | 0.1122 | 0.1915 |
| curvature_energy_bin | smooth | ridge | 1697 | 0.5499 | 3.716 | 1.019 | 0.1122 | 0.1892 |
| curvature_energy_bin | smooth | shape_time_gate_transformer_new | 1697 | 0.4036 | 4.754 | 1.008 | 0.1122 | 0.2952 |
| curvature_energy_bin | smooth | traditional_median_template_cfd_timewalk_shape | 1697 | 0.2408 | 0.9069 | 0.9938 | 0.1122 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1636 | -0.2983 | 4.921 | 0.9249 | 0.04186 | 0.3081 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1636 | 0.5535 | 6.226 | 1.084 | 0.04186 | 0.4352 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1636 | -0.6918 | 3.131 | 0.963 | 0.04186 | 0.1039 |
| derivative_onset_bin | nominal | mlp | 1636 | -0.8357 | 3.478 | 0.9651 | 0.04186 | 0.1626 |
| derivative_onset_bin | nominal | ridge | 1636 | -0.5868 | 3.56 | 1.013 | 0.04186 | 0.1565 |
| derivative_onset_bin | nominal | shape_time_gate_transformer_new | 1636 | 0.02014 | 4.784 | 1.148 | 0.04186 | 0.3056 |
| derivative_onset_bin | nominal | traditional_median_template_cfd_timewalk_shape | 1636 | 0.4503 | 0.9146 | 0.9864 | 0.04186 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1801 | 0.1316 | 4.923 | 0.8137 | 0.04604 | 0.3154 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1801 | 1.487 | 6.036 | 0.9591 | 0.04604 | 0.4181 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1801 | -0.986 | 2.917 | 0.9708 | 0.04604 | 0.07718 |
| derivative_onset_bin | sharp | mlp | 1801 | -1.206 | 3.398 | 0.9847 | 0.04604 | 0.1516 |
| derivative_onset_bin | sharp | ridge | 1801 | -0.6166 | 3.706 | 0.9885 | 0.04604 | 0.1816 |
| derivative_onset_bin | sharp | shape_time_gate_transformer_new | 1801 | 0.0086 | 4.853 | 0.9943 | 0.04604 | 0.3104 |
| derivative_onset_bin | sharp | traditional_median_template_cfd_timewalk_shape | 1801 | 0.5375 | 0.8928 | 0.9871 | 0.04604 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1489 | 2.194 | 6.95 | 1.02 | 0.4991 | 0.5017 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1489 | 1.768 | 6.359 | 1.053 | 0.4991 | 0.458 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1489 | 0.8184 | 4.177 | 1.011 | 0.4991 | 0.2707 |
| derivative_onset_bin | slow | mlp | 1489 | 0.6313 | 4.093 | 1 | 0.4991 | 0.276 |
| derivative_onset_bin | slow | ridge | 1489 | 1.042 | 4.146 | 1.011 | 0.4991 | 0.278 |
| derivative_onset_bin | slow | shape_time_gate_transformer_new | 1489 | 0.8659 | 6.604 | 0.9528 | 0.4991 | 0.4446 |
| derivative_onset_bin | slow | traditional_median_template_cfd_timewalk_shape | 1489 | 0.106 | 0.8608 | 0.996 | 0.4991 | 0 |
| energy_bin | q1_low | 1d_cnn | 1228 | -0.1362 | 6.623 | 1.027 | 0.4663 | 0.4536 |
| energy_bin | q1_low | compact_waveform_transformer | 1228 | 0.9365 | 5.582 | 1.032 | 0.4663 | 0.3925 |
| energy_bin | q1_low | gradient_boosted_trees | 1228 | -0.4021 | 3.415 | 1.011 | 0.4663 | 0.1572 |
| energy_bin | q1_low | mlp | 1228 | -0.196 | 3.622 | 0.996 | 0.4663 | 0.1954 |
| energy_bin | q1_low | ridge | 1228 | 0.7971 | 3.781 | 1.021 | 0.4663 | 0.2052 |
| energy_bin | q1_low | shape_time_gate_transformer_new | 1228 | 1.226 | 6.023 | 0.9582 | 0.4663 | 0.4112 |
| energy_bin | q1_low | traditional_median_template_cfd_timewalk_shape | 1228 | 0.04751 | 1.022 | 0.9928 | 0.4663 | 0 |
| energy_bin | q2 | 1d_cnn | 1382 | 0.0521 | 4.48 | 1.051 | 0.1066 | 0.2735 |
| energy_bin | q2 | compact_waveform_transformer | 1382 | 2.772 | 5.147 | 1.048 | 0.1066 | 0.4161 |
| energy_bin | q2 | gradient_boosted_trees | 1382 | -0.1885 | 3.142 | 1.017 | 0.1066 | 0.1317 |
| energy_bin | q2 | mlp | 1382 | -0.4941 | 3.753 | 1.011 | 0.1066 | 0.1925 |
| energy_bin | q2 | ridge | 1382 | 0.05866 | 3.701 | 1.021 | 0.1066 | 0.1961 |
| energy_bin | q2 | shape_time_gate_transformer_new | 1382 | 0.3767 | 4.563 | 1.002 | 0.1066 | 0.2764 |
| energy_bin | q2 | traditional_median_template_cfd_timewalk_shape | 1382 | 0.4114 | 0.7343 | 0.9945 | 0.1066 | 0 |
| energy_bin | q3 | 1d_cnn | 1328 | 2.08 | 4.299 | 0.9908 | 0.08913 | 0.3276 |
| energy_bin | q3 | compact_waveform_transformer | 1328 | 3.186 | 6.215 | 1.032 | 0.08913 | 0.4947 |
| energy_bin | q3 | gradient_boosted_trees | 1328 | -0.6815 | 3.281 | 1.012 | 0.08913 | 0.1423 |
| energy_bin | q3 | mlp | 1328 | -0.7636 | 3.762 | 1.004 | 0.08913 | 0.1777 |
| energy_bin | q3 | ridge | 1328 | -0.1875 | 4.229 | 1.007 | 0.08913 | 0.2108 |
| energy_bin | q3 | shape_time_gate_transformer_new | 1328 | 0.2036 | 5.649 | 0.9863 | 0.08913 | 0.3901 |
| energy_bin | q3 | traditional_median_template_cfd_timewalk_shape | 1328 | 0.5402 | 0.8051 | 0.9944 | 0.08913 | 0 |
| energy_bin | q4_high | 1d_cnn | 988 | -0.875 | 6.766 | 0.9836 | 0.05689 | 0.4545 |
| energy_bin | q4_high | compact_waveform_transformer | 988 | -3.246 | 5.524 | 1.066 | 0.05689 | 0.4383 |
| energy_bin | q4_high | gradient_boosted_trees | 988 | -0.8326 | 3.184 | 1.019 | 0.05689 | 0.1498 |
| energy_bin | q4_high | mlp | 988 | -0.8211 | 3.672 | 1.028 | 0.05689 | 0.2105 |
| energy_bin | q4_high | ridge | 988 | -0.6779 | 3.663 | 1.008 | 0.05689 | 0.1964 |
| energy_bin | q4_high | shape_time_gate_transformer_new | 988 | -0.8429 | 5.117 | 0.9361 | 0.05689 | 0.3198 |
| energy_bin | q4_high | traditional_median_template_cfd_timewalk_shape | 988 | 0.5466 | 1.103 | 0.9922 | 0.05689 | 0 |
| late_tail_morphology | compact | 1d_cnn | 2956 | 0.07958 | 4.948 | 0.933 | 0.1508 | 0.3153 |
| late_tail_morphology | compact | compact_waveform_transformer | 2956 | 0.902 | 6.083 | 1.142 | 0.1508 | 0.4249 |
| late_tail_morphology | compact | gradient_boosted_trees | 2956 | -0.7687 | 3.108 | 0.9678 | 0.1508 | 0.09472 |
| late_tail_morphology | compact | mlp | 2956 | -0.8372 | 3.511 | 0.9725 | 0.1508 | 0.1502 |
| late_tail_morphology | compact | ridge | 2956 | -0.467 | 3.739 | 1.001 | 0.1508 | 0.1786 |
| late_tail_morphology | compact | shape_time_gate_transformer_new | 2956 | 0.006793 | 5.369 | 0.9083 | 0.1508 | 0.3606 |
| late_tail_morphology | compact | traditional_median_template_cfd_timewalk_shape | 2956 | 0.4603 | 0.9149 | 0.9916 | 0.1508 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 538 | -0.5978 | 5.372 | 0.6816 | 0.03603 | 0.3494 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 538 | 0.3575 | 5.707 | 0.6515 | 0.03603 | 0.3903 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 538 | -0.4151 | 2.724 | 1.002 | 0.03603 | 0.1245 |
| late_tail_morphology | diffuse_tail | mlp | 538 | -0.4521 | 3.375 | 0.939 | 0.03603 | 0.1859 |
| late_tail_morphology | diffuse_tail | ridge | 538 | -0.5705 | 3.46 | 1.085 | 0.03603 | 0.1617 |
| late_tail_morphology | diffuse_tail | shape_time_gate_transformer_new | 538 | 1.269 | 4.344 | 0.9827 | 0.03603 | 0.2639 |
| late_tail_morphology | diffuse_tail | traditional_median_template_cfd_timewalk_shape | 538 | 0.6334 | 0.8431 | 0.952 | 0.03603 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 342 | -0.7279 | 7.324 | 0.6174 | 0.608 | 0.4737 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 342 | -0.7447 | 7.241 | 0.9015 | 0.608 | 0.4795 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 342 | -1.287 | 3.227 | 1.017 | 0.608 | 0.1754 |
| late_tail_morphology | late_derivative_bump | mlp | 342 | -1.325 | 4.008 | 0.94 | 0.608 | 0.269 |
| late_tail_morphology | late_derivative_bump | ridge | 342 | -0.5365 | 3.607 | 0.9506 | 0.608 | 0.2251 |
| late_tail_morphology | late_derivative_bump | shape_time_gate_transformer_new | 342 | 0.2483 | 5.509 | 0.8744 | 0.608 | 0.3538 |
| late_tail_morphology | late_derivative_bump | traditional_median_template_cfd_timewalk_shape | 342 | 0.3256 | 1.027 | 1.002 | 0.608 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1090 | 2.948 | 6.223 | 1.059 | 0.203 | 0.4927 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1090 | 3.201 | 5.784 | 1.065 | 0.203 | 0.4743 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1090 | 0.9072 | 4.292 | 1.01 | 0.203 | 0.2798 |
| late_tail_morphology | late_rising_tail | mlp | 1090 | 0.5007 | 4.432 | 1.009 | 0.203 | 0.2881 |
| late_tail_morphology | late_rising_tail | ridge | 1090 | 1.128 | 3.706 | 1.01 | 0.203 | 0.2798 |
| late_tail_morphology | late_rising_tail | shape_time_gate_transformer_new | 1090 | 0.1272 | 5.6 | 0.9648 | 0.203 | 0.3596 |
| late_tail_morphology | late_rising_tail | traditional_median_template_cfd_timewalk_shape | 1090 | 0.1016 | 0.8293 | 0.9907 | 0.203 | 0 |
| peak_phase_bin | early_phase | 1d_cnn | 2211 | 0.865 | 5.531 | 1.03 | 0.1747 | 0.3772 |
| peak_phase_bin | early_phase | compact_waveform_transformer | 2211 | 0.7568 | 6.583 | 1.05 | 0.1747 | 0.4541 |
| peak_phase_bin | early_phase | gradient_boosted_trees | 2211 | -0.5423 | 3.379 | 1.019 | 0.1747 | 0.1569 |
| peak_phase_bin | early_phase | mlp | 2211 | -0.3824 | 3.965 | 1.008 | 0.1747 | 0.2153 |
| peak_phase_bin | early_phase | ridge | 2211 | -0.1421 | 4.12 | 1.017 | 0.1747 | 0.2157 |
| peak_phase_bin | early_phase | shape_time_gate_transformer_new | 2211 | -0.4535 | 5.297 | 1 | 0.1747 | 0.3501 |
| peak_phase_bin | early_phase | traditional_median_template_cfd_timewalk_shape | 2211 | 0.4201 | 0.9413 | 0.993 | 0.1747 | 0 |
| peak_phase_bin | late_phase | 1d_cnn | 1098 | 0.2527 | 5.503 | 1.004 | 0.1749 | 0.3698 |
| peak_phase_bin | late_phase | compact_waveform_transformer | 1098 | 0.9426 | 5.935 | 1.028 | 0.1749 | 0.4016 |
| peak_phase_bin | late_phase | gradient_boosted_trees | 1098 | -0.4801 | 3.237 | 1.003 | 0.1749 | 0.1357 |
| peak_phase_bin | late_phase | mlp | 1098 | -0.6894 | 3.673 | 0.9914 | 0.1749 | 0.1821 |
| peak_phase_bin | late_phase | ridge | 1098 | -0.06244 | 3.68 | 1.003 | 0.1749 | 0.1922 |
| peak_phase_bin | late_phase | shape_time_gate_transformer_new | 1098 | 1.487 | 5.561 | 0.9088 | 0.1749 | 0.3843 |
| peak_phase_bin | late_phase | traditional_median_template_cfd_timewalk_shape | 1098 | 0.4249 | 0.9214 | 0.9944 | 0.1749 | 0 |
| peak_phase_bin | mid_phase | 1d_cnn | 1617 | 0.2366 | 5.499 | 1.016 | 0.1955 | 0.3581 |
| peak_phase_bin | mid_phase | compact_waveform_transformer | 1617 | 2.038 | 5.592 | 1.027 | 0.1955 | 0.4341 |
| peak_phase_bin | mid_phase | gradient_boosted_trees | 1617 | -0.4131 | 3.333 | 1.015 | 0.1955 | 0.1336 |
| peak_phase_bin | mid_phase | mlp | 1617 | -0.5855 | 3.624 | 1.011 | 0.1955 | 0.1694 |
| peak_phase_bin | mid_phase | ridge | 1617 | 0.1533 | 3.775 | 1.024 | 0.1955 | 0.1911 |
| peak_phase_bin | mid_phase | shape_time_gate_transformer_new | 1617 | 0.1766 | 4.989 | 0.9864 | 0.1955 | 0.3247 |
| peak_phase_bin | mid_phase | traditional_median_template_cfd_timewalk_shape | 1617 | 0.3324 | 0.9034 | 0.9945 | 0.1955 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1564 | 0.6343 | 6.624 | 0.9826 | 0.4076 | 0.4322 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1564 | -0.7804 | 6.715 | 1.048 | 0.4076 | 0.4808 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1564 | -0.09019 | 3.485 | 1.016 | 0.4076 | 0.1656 |
| pedestal_drift_bin | high | mlp | 1564 | 0.1041 | 3.734 | 1.004 | 0.4076 | 0.2027 |
| pedestal_drift_bin | high | ridge | 1564 | 0.1336 | 3.881 | 1.008 | 0.4076 | 0.2136 |
| pedestal_drift_bin | high | shape_time_gate_transformer_new | 1564 | 0.3397 | 6.503 | 0.9469 | 0.4076 | 0.4405 |
| pedestal_drift_bin | high | traditional_median_template_cfd_timewalk_shape | 1564 | 0.3934 | 0.9636 | 0.995 | 0.4076 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1599 | 0.1569 | 5.29 | 1.04 | 0.07868 | 0.3496 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1599 | 1.803 | 5.611 | 1.021 | 0.07868 | 0.409 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1599 | -0.6228 | 3.292 | 1.016 | 0.07868 | 0.1438 |
| pedestal_drift_bin | low | mlp | 1599 | -0.7756 | 3.726 | 1.012 | 0.07868 | 0.1945 |
| pedestal_drift_bin | low | ridge | 1599 | -0.2643 | 3.97 | 1.023 | 0.07868 | 0.2101 |
| pedestal_drift_bin | low | shape_time_gate_transformer_new | 1599 | -0.1512 | 4.98 | 0.9821 | 0.07868 | 0.3183 |
| pedestal_drift_bin | low | traditional_median_template_cfd_timewalk_shape | 1599 | 0.3828 | 0.9011 | 0.9922 | 0.07868 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1763 | 0.7124 | 5.07 | 1.043 | 0.0744 | 0.3313 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1763 | 2.197 | 5.547 | 1.021 | 0.0744 | 0.4203 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1763 | -0.6656 | 3.264 | 1.02 | 0.0744 | 0.1265 |
| pedestal_drift_bin | mid | mlp | 1763 | -0.8398 | 3.738 | 1.013 | 0.0744 | 0.1826 |
| pedestal_drift_bin | mid | ridge | 1763 | -0.07305 | 3.741 | 1.026 | 0.0744 | 0.1855 |
| pedestal_drift_bin | mid | shape_time_gate_transformer_new | 1763 | 0.4735 | 4.725 | 0.9909 | 0.0744 | 0.2967 |
| pedestal_drift_bin | mid | traditional_median_template_cfd_timewalk_shape | 1763 | 0.401 | 0.9046 | 0.9924 | 0.0744 | 0 |
| pid_sideband | central | 1d_cnn | 3374 | 0.7465 | 5.13 | 1.044 | 0.08186 | 0.3373 |
| pid_sideband | central | compact_waveform_transformer | 3374 | 2.243 | 5.464 | 1.023 | 0.08186 | 0.4185 |
| pid_sideband | central | gradient_boosted_trees | 3374 | -0.5066 | 3.301 | 1.021 | 0.08186 | 0.1452 |
| pid_sideband | central | mlp | 3374 | -0.558 | 3.771 | 1.012 | 0.08186 | 0.1915 |
| pid_sideband | central | ridge | 3374 | 0.02978 | 4.048 | 1.025 | 0.08186 | 0.2101 |
| pid_sideband | central | shape_time_gate_transformer_new | 3374 | 0.3329 | 4.933 | 0.9881 | 0.08186 | 0.3162 |
| pid_sideband | central | traditional_median_template_cfd_timewalk_shape | 3374 | 0.3282 | 0.9075 | 0.9927 | 0.08186 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 787 | -0.06618 | 7.572 | 0.3935 | 0.7349 | 0.5019 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 787 | -4.059 | 5.503 | 0.5688 | 0.7349 | 0.4956 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 787 | -0.1493 | 3.523 | 1.002 | 0.7349 | 0.1652 |
| pid_sideband | high_duplicate | mlp | 787 | 0.004623 | 3.831 | 0.9462 | 0.7349 | 0.2008 |
| pid_sideband | high_duplicate | ridge | 787 | -0.04691 | 3.753 | 0.8661 | 0.7349 | 0.2109 |
| pid_sideband | high_duplicate | shape_time_gate_transformer_new | 787 | -1.035 | 8.608 | 0.3846 | 0.7349 | 0.5629 |
| pid_sideband | high_duplicate | traditional_median_template_cfd_timewalk_shape | 787 | 0.4672 | 0.9684 | 0.9904 | 0.7349 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 765 | -0.1025 | 5.92 | 1.01 | 0.05224 | 0.3739 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 765 | 1.309 | 6.405 | 0.9822 | 0.05224 | 0.451 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 765 | -0.7026 | 3.251 | 1.017 | 0.05224 | 0.1203 |
| pid_sideband | low_duplicate | mlp | 765 | -1.106 | 3.664 | 1.008 | 0.05224 | 0.1908 |
| pid_sideband | low_duplicate | ridge | 765 | -0.314 | 3.389 | 1.015 | 0.05224 | 0.1595 |
| pid_sideband | low_duplicate | shape_time_gate_transformer_new | 765 | 0.4587 | 4.654 | 0.9443 | 0.05224 | 0.2758 |
| pid_sideband | low_duplicate | traditional_median_template_cfd_timewalk_shape | 765 | 0.5745 | 0.946 | 0.9896 | 0.05224 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1481 | -1.23 | 5.477 | 0.8642 | 0.03832 | 0.3579 |
| pileup_separation_bin | close | compact_waveform_transformer | 1481 | 0.3781 | 6.066 | 0.833 | 0.03832 | 0.4051 |
| pileup_separation_bin | close | gradient_boosted_trees | 1481 | -0.8213 | 3.02 | 0.9518 | 0.03832 | 0.09183 |
| pileup_separation_bin | close | mlp | 1481 | -1.045 | 3.371 | 0.9569 | 0.03832 | 0.1533 |
| pileup_separation_bin | close | ridge | 1481 | -0.8637 | 3.57 | 1.025 | 0.03832 | 0.1992 |
| pileup_separation_bin | close | shape_time_gate_transformer_new | 1481 | -0.5585 | 4.833 | 0.9568 | 0.03832 | 0.3363 |
| pileup_separation_bin | close | traditional_median_template_cfd_timewalk_shape | 1481 | 0.5187 | 0.9541 | 0.9838 | 0.03832 | 0 |
| pileup_separation_bin | late | 1d_cnn | 1 | -13.15 | 0 | nan | 0.03481 | 1 |
| pileup_separation_bin | late | compact_waveform_transformer | 1 | -8.09 | 0 | nan | 0.03481 | 1 |
| pileup_separation_bin | late | gradient_boosted_trees | 1 | -3.919 | 0 | nan | 0.03481 | 0 |
| pileup_separation_bin | late | mlp | 1 | -5.901 | 0 | nan | 0.03481 | 1 |
| pileup_separation_bin | late | ridge | 1 | -1.512 | 0 | nan | 0.03481 | 0 |
| pileup_separation_bin | late | shape_time_gate_transformer_new | 1 | -5.329 | 0 | nan | 0.03481 | 1 |
| pileup_separation_bin | late | traditional_median_template_cfd_timewalk_shape | 1 | 1.673 | 0 | nan | 0.03481 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1090 | 1.746 | 4.808 | 1.005 | 0.1175 | 0.3651 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1090 | -2.045 | 6.207 | 1.185 | 0.1175 | 0.4697 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1090 | -0.9785 | 3.115 | 0.9487 | 0.1175 | 0.09908 |
| pileup_separation_bin | mid | mlp | 1090 | -0.8447 | 3.654 | 0.9471 | 0.1175 | 0.144 |
| pileup_separation_bin | mid | ridge | 1090 | -0.3559 | 3.628 | 0.9716 | 0.1175 | 0.1706 |
| pileup_separation_bin | mid | shape_time_gate_transformer_new | 1090 | -0.8348 | 5.341 | 0.949 | 0.1175 | 0.3725 |
| pileup_separation_bin | mid | traditional_median_template_cfd_timewalk_shape | 1090 | 0.6445 | 0.8985 | 0.995 | 0.1175 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2354 | 1.065 | 5.631 | 1.027 | 0.3015 | 0.3781 |
| pileup_separation_bin | none | compact_waveform_transformer | 2354 | 2.802 | 5.082 | 1.019 | 0.3015 | 0.4393 |
| pileup_separation_bin | none | gradient_boosted_trees | 2354 | 0.03669 | 3.571 | 1.015 | 0.3015 | 0.1988 |
| pileup_separation_bin | none | mlp | 2354 | -0.08722 | 3.839 | 1.003 | 0.3015 | 0.24 |
| pileup_separation_bin | none | ridge | 2354 | 0.6272 | 3.733 | 1.014 | 0.3015 | 0.2192 |
| pileup_separation_bin | none | shape_time_gate_transformer_new | 2354 | 1.078 | 5.157 | 0.9536 | 0.3015 | 0.3466 |
| pileup_separation_bin | none | traditional_median_template_cfd_timewalk_shape | 2354 | 0.226 | 0.8496 | 0.9956 | 0.3015 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1659 | -0.2277 | 5.98 | 0.7943 | 0.3671 | 0.4117 |
| pulse_shape_class | compact | compact_waveform_transformer | 1659 | -0.1586 | 6.439 | 1.141 | 0.3671 | 0.4593 |
| pulse_shape_class | compact | gradient_boosted_trees | 1659 | -0.7815 | 3.224 | 0.955 | 0.3671 | 0.1151 |
| pulse_shape_class | compact | mlp | 1659 | -0.7278 | 3.573 | 0.9527 | 0.3671 | 0.1513 |
| pulse_shape_class | compact | ridge | 1659 | -0.07337 | 4.001 | 0.9775 | 0.3671 | 0.2122 |
| pulse_shape_class | compact | shape_time_gate_transformer_new | 1659 | -0.9536 | 6.174 | 0.816 | 0.3671 | 0.4412 |
| pulse_shape_class | compact | traditional_median_template_cfd_timewalk_shape | 1659 | 0.4493 | 1.006 | 0.9896 | 0.3671 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1650 | 1.44 | 6.186 | 1.065 | 0.1462 | 0.4442 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1650 | 2.195 | 6.027 | 1.054 | 0.1462 | 0.4442 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1650 | 0.2908 | 3.802 | 1.015 | 0.1462 | 0.2261 |
| pulse_shape_class | late_tail | mlp | 1650 | 0.1575 | 4.199 | 1.008 | 0.1462 | 0.2521 |
| pulse_shape_class | late_tail | ridge | 1650 | 0.5365 | 3.895 | 1.018 | 0.1462 | 0.24 |
| pulse_shape_class | late_tail | shape_time_gate_transformer_new | 1650 | 0.6036 | 5.079 | 0.9656 | 0.1462 | 0.3273 |
| pulse_shape_class | late_tail | traditional_median_template_cfd_timewalk_shape | 1650 | 0.2377 | 0.9019 | 0.9901 | 0.1462 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1617 | 0.1988 | 4.285 | 0.7758 | 0.02731 | 0.2492 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1617 | 1.65 | 5.745 | 0.8773 | 0.02731 | 0.4032 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1617 | -0.8172 | 3.055 | 0.9741 | 0.02731 | 0.09153 |
| pulse_shape_class | nominal | mlp | 1617 | -0.9669 | 3.493 | 0.9661 | 0.02731 | 0.175 |
| pulse_shape_class | nominal | ridge | 1617 | -0.7943 | 3.532 | 1.136 | 0.02731 | 0.154 |
| pulse_shape_class | nominal | shape_time_gate_transformer_new | 1617 | 0.5802 | 4.483 | 1.079 | 0.02731 | 0.2777 |
| pulse_shape_class | nominal | traditional_median_template_cfd_timewalk_shape | 1617 | 0.45 | 0.9022 | 0.9676 | 0.02731 | 0 |
| q_template_error_bin | moderate_shape | 1d_cnn | 1782 | 1.522 | 5.23 | 0.9376 | 0.05162 | 0.3502 |
| q_template_error_bin | moderate_shape | compact_waveform_transformer | 1782 | 1.603 | 6.938 | 0.9506 | 0.05162 | 0.5213 |
| q_template_error_bin | moderate_shape | gradient_boosted_trees | 1782 | -1.017 | 3.035 | 1 | 0.05162 | 0.09203 |
| q_template_error_bin | moderate_shape | mlp | 1782 | -0.8179 | 3.525 | 1.005 | 0.05162 | 0.1639 |
| q_template_error_bin | moderate_shape | ridge | 1782 | 0.2107 | 4.254 | 1.09 | 0.05162 | 0.2402 |
| q_template_error_bin | moderate_shape | shape_time_gate_transformer_new | 1782 | 0.6359 | 5.991 | 1.102 | 0.05162 | 0.4422 |
| q_template_error_bin | moderate_shape | traditional_median_template_cfd_timewalk_shape | 1782 | 0.595 | 0.8894 | 0.9875 | 0.05162 | 0 |
| q_template_error_bin | shape_outlier | 1d_cnn | 1530 | 1.733 | 7.244 | 1.024 | 0.508 | 0.5007 |
| q_template_error_bin | shape_outlier | compact_waveform_transformer | 1530 | 0.7387 | 6.947 | 1.065 | 0.508 | 0.4948 |
| q_template_error_bin | shape_outlier | gradient_boosted_trees | 1530 | 0.633 | 4.031 | 1.01 | 0.508 | 0.2562 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | moderate | 4.759 | curved | 6.578 | 1.819 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.749 | moderate | 6.179 | 1.431 |
| curvature_energy_bin | shape_time_gate_transformer_new | 3 | smooth | 4.754 | curved | 5.786 | 1.031 |
| curvature_energy_bin | mlp | 3 | smooth | 3.655 | curved | 3.958 | 0.3025 |
| curvature_energy_bin | ridge | 3 | smooth | 3.716 | moderate | 4.001 | 0.2855 |
| curvature_energy_bin | gradient_boosted_trees | 3 | moderate | 3.18 | curved | 3.371 | 0.1911 |
| curvature_energy_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate | 0.8544 | curved | 1.035 | 0.1802 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 4.921 | slow | 6.95 | 2.029 |
| derivative_onset_bin | shape_time_gate_transformer_new | 3 | nominal | 4.784 | slow | 6.604 | 1.82 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 2.917 | slow | 4.177 | 1.259 |
| derivative_onset_bin | mlp | 3 | sharp | 3.398 | slow | 4.093 | 0.6952 |
| derivative_onset_bin | ridge | 3 | nominal | 3.56 | slow | 4.146 | 0.5853 |
| derivative_onset_bin | compact_waveform_transformer | 3 | sharp | 6.036 | slow | 6.359 | 0.3233 |
| derivative_onset_bin | traditional_median_template_cfd_timewalk_shape | 3 | slow | 0.8608 | nominal | 0.9146 | 0.0538 |
| energy_bin | 1d_cnn | 4 | q3 | 4.299 | q4_high | 6.766 | 2.466 |
| energy_bin | shape_time_gate_transformer_new | 4 | q2 | 4.563 | q1_low | 6.023 | 1.46 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 5.147 | q3 | 6.215 | 1.068 |
| energy_bin | ridge | 4 | q4_high | 3.663 | q3 | 4.229 | 0.5656 |
| energy_bin | traditional_median_template_cfd_timewalk_shape | 4 | q2 | 0.7343 | q4_high | 1.103 | 0.3687 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.142 | q1_low | 3.415 | 0.2731 |
| energy_bin | mlp | 4 | q1_low | 3.622 | q3 | 3.762 | 0.1404 |
| late_tail_morphology | 1d_cnn | 4 | compact | 4.948 | late_derivative_bump | 7.324 | 2.376 |
| late_tail_morphology | gradient_boosted_trees | 4 | diffuse_tail | 2.724 | late_rising_tail | 4.292 | 1.568 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 5.707 | late_derivative_bump | 7.241 | 1.533 |
| late_tail_morphology | shape_time_gate_transformer_new | 4 | diffuse_tail | 4.344 | late_rising_tail | 5.6 | 1.256 |
| late_tail_morphology | mlp | 4 | diffuse_tail | 3.375 | late_rising_tail | 4.432 | 1.056 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.46 | compact | 3.739 | 0.2791 |
| late_tail_morphology | traditional_median_template_cfd_timewalk_shape | 4 | late_rising_tail | 0.8293 | late_derivative_bump | 1.027 | 0.1977 |
| peak_phase_bin | compact_waveform_transformer | 3 | mid_phase | 5.592 | early_phase | 6.583 | 0.9916 |
| peak_phase_bin | shape_time_gate_transformer_new | 3 | mid_phase | 4.989 | late_phase | 5.561 | 0.5722 |
| peak_phase_bin | ridge | 3 | late_phase | 3.68 | early_phase | 4.12 | 0.4403 |
| peak_phase_bin | mlp | 3 | mid_phase | 3.624 | early_phase | 3.965 | 0.341 |
| peak_phase_bin | gradient_boosted_trees | 3 | late_phase | 3.237 | early_phase | 3.379 | 0.1425 |
| peak_phase_bin | traditional_median_template_cfd_timewalk_shape | 3 | mid_phase | 0.9034 | early_phase | 0.9413 | 0.03789 |
| peak_phase_bin | 1d_cnn | 3 | mid_phase | 5.499 | early_phase | 5.531 | 0.03207 |
| pedestal_drift_bin | shape_time_gate_transformer_new | 3 | mid | 4.725 | high | 6.503 | 1.778 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.07 | high | 6.624 | 1.554 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.547 | high | 6.715 | 1.169 |
| pedestal_drift_bin | ridge | 3 | mid | 3.741 | low | 3.97 | 0.2292 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | mid | 3.264 | high | 3.485 | 0.2213 |
| pedestal_drift_bin | traditional_median_template_cfd_timewalk_shape | 3 | low | 0.9011 | high | 0.9636 | 0.06258 |
| pedestal_drift_bin | mlp | 3 | low | 3.726 | mid | 3.738 | 0.0116 |
| pid_sideband | shape_time_gate_transformer_new | 3 | low_duplicate | 4.654 | high_duplicate | 8.608 | 3.954 |
| pid_sideband | 1d_cnn | 3 | central | 5.13 | high_duplicate | 7.572 | 2.442 |
| pid_sideband | compact_waveform_transformer | 3 | central | 5.464 | low_duplicate | 6.405 | 0.941 |
| pid_sideband | ridge | 3 | low_duplicate | 3.389 | central | 4.048 | 0.659 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.251 | high_duplicate | 3.523 | 0.2725 |
| pid_sideband | mlp | 3 | low_duplicate | 3.664 | high_duplicate | 3.831 | 0.1679 |
| pid_sideband | traditional_median_template_cfd_timewalk_shape | 3 | central | 0.9075 | high_duplicate | 0.9684 | 0.06089 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 0 | mid | 6.207 | 6.207 |
| pileup_separation_bin | 1d_cnn | 4 | late | 0 | none | 5.631 | 5.631 |
| pileup_separation_bin | shape_time_gate_transformer_new | 4 | late | 0 | mid | 5.341 | 5.341 |
| pileup_separation_bin | mlp | 4 | late | 0 | none | 3.839 | 3.839 |
| pileup_separation_bin | ridge | 4 | late | 0 | none | 3.733 | 3.733 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 0 | none | 3.571 | 3.571 |
| pileup_separation_bin | traditional_median_template_cfd_timewalk_shape | 4 | late | 0 | close | 0.9541 | 0.9541 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.285 | late_tail | 6.186 | 1.901 |
| pulse_shape_class | shape_time_gate_transformer_new | 3 | nominal | 4.483 | compact | 6.174 | 1.691 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.055 | late_tail | 3.802 | 0.7474 |
| pulse_shape_class | mlp | 3 | nominal | 3.493 | late_tail | 4.199 | 0.7062 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.745 | compact | 6.439 | 0.6941 |
| pulse_shape_class | ridge | 3 | nominal | 3.532 | compact | 4.001 | 0.4689 |
| pulse_shape_class | traditional_median_template_cfd_timewalk_shape | 3 | late_tail | 0.9019 | compact | 1.006 | 0.1039 |
| q_template_error_bin | shape_time_gate_transformer_new | 3 | template_like | 3.243 | shape_outlier | 6.906 | 3.663 |
| q_template_error_bin | 1d_cnn | 3 | template_like | 4.28 | shape_outlier | 7.244 | 2.964 |
| q_template_error_bin | compact_waveform_transformer | 3 | template_like | 4.326 | shape_outlier | 6.947 | 2.621 |
| q_template_error_bin | ridge | 3 | template_like | 2.99 | moderate_shape | 4.254 | 1.264 |
| q_template_error_bin | gradient_boosted_trees | 3 | template_like | 3.011 | shape_outlier | 4.031 | 1.021 |
| q_template_error_bin | mlp | 3 | template_like | 3.382 | shape_outlier | 4.121 | 0.7386 |
| q_template_error_bin | traditional_median_template_cfd_timewalk_shape | 3 | shape_outlier | 0.8605 | template_like | 0.9112 | 0.05079 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.881 | linear | 5.782 | 0.9008 |
| saturation_onset_bin | shape_time_gate_transformer_new | 2 | near_saturation | 4.718 | linear | 5.539 | 0.8212 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.709 | linear | 3.999 | 0.2908 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 6.043 | linear | 6.282 | 0.2389 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.669 | linear | 3.802 | 0.1329 |
| saturation_onset_bin | traditional_median_template_cfd_timewalk_shape | 2 | near_saturation | 0.8709 | linear | 0.9545 | 0.08367 |
| saturation_onset_bin | gradient_boosted_trees | 2 | linear | 3.321 | near_saturation | 3.397 | 0.0761 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 34 | -0.5561 | 3.31 | 2.735 | 3.747 | -0.04319 | 0.1454 |
| full_derivative_gradient_boosted_trees | 77 | -0.5148 | 3.353 | 2.877 | 3.773 | 0 | 0.1476 |
| amplitude_cfd_no_derivative | 5 | -0.04866 | 3.937 | 3.624 | 4.346 | 0.5839 | 0.217 |
| derivative_only | 43 | -0.1503 | 3.953 | 3.6 | 4.702 | 0.5997 | 0.2162 |
| late_tail_curvature_window_only | 17 | 0.1094 | 4.375 | 3.979 | 5.096 | 1.022 | 0.2621 |
| onset_derivative_window_only | 14 | -0.2917 | 4.673 | 4.045 | 5.981 | 1.32 | 0.2986 |
| pretrigger_derivative_only | 7 | -3.121 | 17.75 | 16.69 | 19.62 | 14.4 | 0.5465 |

## Interpretation, Systematics, and Caveats

This benchmark measures relative transfer on a reproducible waveform-derived
timing residual.  The raw ROOT files do not contain an independent external
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

Runtime was `94.6 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.
