# S47c Pedestal-Memory Transfer Map for Energy Timing and PID

## Abstract

Ticket `2437` asked for an academic-grade map from pedestal drift
and baseline memory into pulse-shape descriptors, timing residuals, pile-up
tagging, saturation recovery, energy scale, and PID stability across run
conditions.  The registered B-stack count is first reproduced directly from raw
ROOT `h101/HRDv`; the same pulses are then used for a run-held-out benchmark.
The winner named in `result.json` is **`traditional_median_template_cfd_timewalk_shape`**, with held-out run-bootstrap
`sigma_68 = 0.902 ns [0.7622,
1]`.  The strong traditional comparator obtains
`0.902 ns [0.7622,
1]`.

## Raw ROOT Reproduction

The raw number is reproduced from `/home/billy/ccb-data/data/extracted/root/root`.  For each event,
`HRDv` is reshaped to `(8, 18)`.  For B-stack channel `c`, with
`b_c = median(x_c[0],...,x_c[3])`, the selected-pulse count is

`N = sum_e sum_c 1[max_t(x_e,c,t - b_e,c) > 1000]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced count is **640737**.
Input hashes are in `input_sha256.csv`; first rows:

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

## Estimands and Equations

Constant-fraction time is linearly interpolated before the peak:

`t_f = k - 1 + (f A - y_(k-1))/(y_k - y_(k-1))`, where `y_t=x_t-b`.

The timing target is run/stave-centered CFD20 residual
`Y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.
Resolution is `sigma_68 = 0.5 [Q_84(epsilon)-Q_16(epsilon)]` for
`epsilon_i=Y_i-hat(Y_i)`.  Pedestal memory is represented by event-ordered
baseline covariates within each run/stave:

`m_i = alpha b'_(i-1) + (1-alpha) m_(i-1)`,
`u_i=b'_i-m_i`, and `rho_i=b'_i / max(|b'_(i-1)|,1)`,

where `b'_i = b_i - median(b | run, stave)`.  The traditional method adds
ridge-regularized terms in `(b'_i, b'_(i-1), m_i, u_i, rho_i)` to the existing
CFD/template derivative time-walk fit.  This is the registered strong
traditional pedestal-memory comparator.

Energy scale is a raw charge proxy, `A=max_t(y_t)`.  PID stability is the
duplicate-readout sideband proxy, `A_dup/A`, with low/high duplicate sidebands
treated as operating-point shifts rather than external truth labels.

## Split and Uncertainty

The split unit is the run.  Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`; all
other configured runs train the models.  Benchmark rows:

| split | rows |
| --- | --- |
| heldout | 5196 |
| train | 14451 |

Confidence intervals use `400` paired percentile
bootstrap replicates resampling held-out runs with replacement.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_median_template_cfd_timewalk_shape | traditional | CFD/template derivative timing plus ridge-regularized AR(1), rolling-baseline, and innovation residual correction |
| ridge | linear ML | standardized ridge on waveform, derivative, curvature, pedestal-memory, energy-proxy, and PID-sideband features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted trees on the same leakage-controlled feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform and pedestal-state summaries |
| 1d_cnn | neural waveform | compact convolution over the 18 normalized waveform samples |
| compact_waveform_transformer | neural waveform | one-layer sample self-attention encoder |
| pedestal_memory_fusion_cnn_new | new architecture | CNN over waveform, derivative, and curvature channels gated by event-ordered pedestal-memory covariates |

The new architecture is sensible here because the ticket hypothesis is
pedestal-memory transfer, not generic waveform fitting.  The model gates
waveform/derivative/curvature convolution channels by baseline lag, rolling
memory, innovation, AR(1) proxy, and run-normalized pedestal displacement.

## Primary Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_median_template_cfd_timewalk_shape | 5196 | 0.3205 | 0.03551 | 0.5753 | 0.902 | 0.7622 | 1 | 0.8867 | 0.9944 | 0.172 | 0 | 0 |
| gradient_boosted_trees | 5196 | 0.1201 | -1.217 | 0.9483 | 3.751 | 3.264 | 4.22 | 4.365 | 1.01 | 0.172 | 0.1913 | 0.04215 |
| mlp | 5196 | -0.2837 | -1.152 | 0.6519 | 4.33 | 4.112 | 4.773 | 4.818 | 1.002 | 0.172 | 0.2552 | 0.05158 |
| ridge | 5196 | -0.8213 | -1.721 | 0.239 | 4.46 | 4.25 | 4.962 | 4.72 | 1.007 | 0.172 | 0.2577 | 0.0485 |
| pedestal_memory_fusion_cnn_new | 5196 | 0.02248 | -0.8264 | 0.9433 | 5.276 | 4.494 | 6.117 | 6.303 | 1.031 | 0.172 | 0.3399 | 0.09488 |
| compact_waveform_transformer | 5196 | -2.425 | -3.519 | -1.622 | 5.327 | 4.833 | 6.122 | 6.13 | 1.003 | 0.172 | 0.3691 | 0.1145 |
| 1d_cnn | 5196 | -2.021 | -2.808 | -1.149 | 5.454 | 4.722 | 6.443 | 6.645 | 1.025 | 0.172 | 0.389 | 0.1255 |

## Paired Deltas Versus Traditional

Positive `delta_sigma68_ns` means worse timing resolution than the traditional
pedestal-memory fit.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_median_template_cfd_timewalk_shape | 2.849 | 2.358 | 3.331 | -0.2004 | -1.514 | 0.7164 | 0.1913 |
| mlp | traditional_median_template_cfd_timewalk_shape | 3.428 | 3.197 | 3.883 | -0.6042 | -1.611 | 0.3775 | 0.2552 |
| ridge | traditional_median_template_cfd_timewalk_shape | 3.558 | 3.32 | 4.072 | -1.142 | -2.049 | -0.04667 | 0.2577 |
| pedestal_memory_fusion_cnn_new | traditional_median_template_cfd_timewalk_shape | 4.374 | 3.611 | 5.366 | -0.298 | -1.183 | 0.5884 | 0.3399 |
| compact_waveform_transformer | traditional_median_template_cfd_timewalk_shape | 4.425 | 3.948 | 5.261 | -2.745 | -3.841 | -1.89 | 0.3691 |
| 1d_cnn | traditional_median_template_cfd_timewalk_shape | 4.552 | 3.846 | 5.509 | -2.341 | -3.193 | -1.434 | 0.389 |

## Pedestal, Energy, and PID Transfer Systematics

| pedestal_memory_bin | method | n | bias_ns | sigma68_ns | median_energy_proxy_adc | pid_high_duplicate_fraction | near_saturation_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| moderate_memory | traditional_median_template_cfd_timewalk_shape | 1767 | 0.3269 | 0.881 | 3105 | 0.05207 | 0.2852 |
| moderate_memory | gradient_boosted_trees | 1767 | 0.2478 | 3.759 | 3105 | 0.05207 | 0.2852 |
| moderate_memory | mlp | 1767 | -0.1853 | 4.413 | 3105 | 0.05207 | 0.2852 |
| moderate_memory | ridge | 1767 | -0.817 | 4.437 | 3105 | 0.05207 | 0.2852 |
| moderate_memory | pedestal_memory_fusion_cnn_new | 1767 | 0.134 | 4.924 | 3105 | 0.05207 | 0.2852 |
| moderate_memory | 1d_cnn | 1767 | -1.965 | 4.935 | 3105 | 0.05207 | 0.2852 |
| moderate_memory | compact_waveform_transformer | 1767 | -2.34 | 4.974 | 3105 | 0.05207 | 0.2852 |
| quiet_memory | traditional_median_template_cfd_timewalk_shape | 1601 | 0.3357 | 0.9629 | 3266 | 0.01187 | 0.3079 |
| quiet_memory | gradient_boosted_trees | 1601 | -0.1987 | 3.768 | 3266 | 0.01187 | 0.3079 |
| quiet_memory | mlp | 1601 | -0.4676 | 4.136 | 3266 | 0.01187 | 0.3079 |
| quiet_memory | ridge | 1601 | -0.8646 | 4.183 | 3266 | 0.01187 | 0.3079 |
| quiet_memory | 1d_cnn | 1601 | -2.104 | 5.05 | 3266 | 0.01187 | 0.3079 |
| quiet_memory | compact_waveform_transformer | 1601 | -2.201 | 5.093 | 3266 | 0.01187 | 0.3079 |
| quiet_memory | pedestal_memory_fusion_cnn_new | 1601 | 0.431 | 5.393 | 3266 | 0.01187 | 0.3079 |
| strong_memory | traditional_median_template_cfd_timewalk_shape | 1828 | 0.2932 | 0.8674 | 2821 | 0.3993 | 0.2418 |
| strong_memory | gradient_boosted_trees | 1828 | 0.3164 | 3.644 | 2821 | 0.3993 | 0.2418 |
| strong_memory | mlp | 1828 | -0.22 | 4.243 | 2821 | 0.3993 | 0.2418 |
| strong_memory | ridge | 1828 | -0.7992 | 4.556 | 2821 | 0.3993 | 0.2418 |
| strong_memory | pedestal_memory_fusion_cnn_new | 1828 | -0.3274 | 5.656 | 2821 | 0.3993 | 0.2418 |
| strong_memory | compact_waveform_transformer | 1828 | -2.736 | 5.969 | 2821 | 0.3993 | 0.2418 |
| strong_memory | 1d_cnn | 1828 | -2.028 | 6.366 | 2821 | 0.3993 | 0.2418 |

## Run and Family Stability

| run_family | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_median_template_cfd_timewalk_shape | 1290 | 0.07574 | 0.8008 | 0.995 | 0.1972 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1290 | 1.071 | 3.259 | 1.005 | 0.1972 | 0.2775 |
| sample_i_analysis | mlp | 1290 | 0.606 | 4.25 | 0.9959 | 0.1972 | 0.3016 |
| sample_i_analysis | ridge | 1290 | 0.3247 | 4.27 | 1.005 | 0.1972 | 0.2876 |
| sample_i_analysis | compact_waveform_transformer | 1290 | -1.692 | 6.348 | 0.9942 | 0.1972 | 0.3853 |
| sample_i_analysis | pedestal_memory_fusion_cnn_new | 1290 | 1.373 | 6.468 | 1.028 | 0.1972 | 0.4566 |
| sample_i_analysis | 1d_cnn | 1290 | -1.302 | 7.008 | 1.02 | 0.1972 | 0.4488 |
| sample_i_calib | traditional_median_template_cfd_timewalk_shape | 627 | -0.02915 | 0.8213 | 0.9957 | 0.1949 | 0 |
| sample_i_calib | gradient_boosted_trees | 627 | 1.959 | 3.86 | 1.019 | 0.1949 | 0.2855 |
| sample_i_calib | mlp | 627 | 1.561 | 4.853 | 1.009 | 0.1949 | 0.311 |
| sample_i_calib | ridge | 627 | 1.189 | 4.999 | 1.01 | 0.1949 | 0.2935 |
| sample_i_calib | pedestal_memory_fusion_cnn_new | 627 | 1.992 | 5.365 | 1.034 | 0.1949 | 0.429 |
| sample_i_calib | compact_waveform_transformer | 627 | -0.8415 | 5.448 | 1.013 | 0.1949 | 0.3557 |
| sample_i_calib | 1d_cnn | 627 | 0.3407 | 6.209 | 1.041 | 0.1949 | 0.4322 |
| sample_ii_analysis | traditional_median_template_cfd_timewalk_shape | 2599 | 0.387 | 0.9285 | 0.9957 | 0.1596 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2599 | -1.245 | 3.535 | 1.005 | 0.1596 | 0.1524 |
| sample_ii_analysis | mlp | 2599 | -1.35 | 4.154 | 0.9973 | 0.1596 | 0.2366 |
| sample_ii_analysis | ridge | 2599 | -1.841 | 4.356 | 1.001 | 0.1596 | 0.2409 |
| sample_ii_analysis | pedestal_memory_fusion_cnn_new | 2599 | -0.9778 | 5.005 | 1.023 | 0.1596 | 0.304 |
| sample_ii_analysis | 1d_cnn | 2599 | -2.796 | 5.055 | 1.014 | 0.1596 | 0.3775 |
| sample_ii_analysis | compact_waveform_transformer | 2599 | -3.497 | 5.319 | 0.9997 | 0.1596 | 0.3963 |
| sample_ii_calib | traditional_median_template_cfd_timewalk_shape | 680 | 0.7565 | 0.5359 | 0.9946 | 0.1504 | 0 |
| sample_ii_calib | gradient_boosted_trees | 680 | 0.7394 | 3.476 | 1.007 | 0.1504 | 0.08971 |
| sample_ii_calib | pedestal_memory_fusion_cnn_new | 680 | 0.1406 | 3.714 | 1.046 | 0.1504 | 0.1735 |
| sample_ii_calib | mlp | 680 | -0.169 | 3.993 | 1.007 | 0.1504 | 0.1868 |
| sample_ii_calib | 1d_cnn | 680 | -1.652 | 4.081 | 1.039 | 0.1504 | 0.2794 |
| sample_ii_calib | compact_waveform_transformer | 680 | -1.478 | 4.336 | 1.015 | 0.1504 | 0.2471 |
| sample_ii_calib | ridge | 680 | -0.9868 | 4.377 | 1.005 | 0.1504 | 0.2324 |

| method | run | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 627 | 0.3407 | 6.209 | 1.041 | 0.1949 | 0.4322 |
| 1d_cnn | 50 | 650 | -2.336 | 8.258 | 1.007 | 0.1739 | 0.4215 |
| 1d_cnn | 57 | 640 | -0.04672 | 6.395 | 1.039 | 0.2208 | 0.4766 |
| 1d_cnn | 58 | 624 | -5.044 | 5.582 | 1.03 | 0.1818 | 0.5321 |
| 1d_cnn | 60 | 680 | -2.25 | 4.404 | 1 | 0.1624 | 0.2897 |
| 1d_cnn | 62 | 680 | -2.092 | 4.688 | 1.002 | 0.1452 | 0.3397 |
| 1d_cnn | 64 | 680 | -1.652 | 4.081 | 1.039 | 0.1504 | 0.2794 |
| 1d_cnn | 65 | 615 | -2.486 | 4.641 | 1.043 | 0.15 | 0.3593 |
| compact_waveform_transformer | 42 | 627 | -0.8415 | 5.448 | 1.013 | 0.1949 | 0.3557 |
| compact_waveform_transformer | 50 | 650 | -2.175 | 8.24 | 0.9824 | 0.1739 | 0.3877 |
| compact_waveform_transformer | 57 | 640 | -1.366 | 5.573 | 1.011 | 0.2208 | 0.3828 |
| compact_waveform_transformer | 58 | 624 | -5.786 | 5.306 | 1.003 | 0.1818 | 0.5817 |
| compact_waveform_transformer | 60 | 680 | -2.848 | 4.904 | 1.007 | 0.1624 | 0.3235 |
| compact_waveform_transformer | 62 | 680 | -3.255 | 5.32 | 1.007 | 0.1452 | 0.3529 |
| compact_waveform_transformer | 64 | 680 | -1.478 | 4.336 | 1.015 | 0.1504 | 0.2471 |
| compact_waveform_transformer | 65 | 615 | -2.524 | 4.883 | 1.01 | 0.15 | 0.3366 |
| gradient_boosted_trees | 42 | 627 | 1.959 | 3.86 | 1.019 | 0.1949 | 0.2855 |
| gradient_boosted_trees | 50 | 650 | 1.829 | 7.242 | 0.9934 | 0.1739 | 0.2985 |
| gradient_boosted_trees | 57 | 640 | 0.5347 | 4.252 | 1.021 | 0.2208 | 0.2562 |
| gradient_boosted_trees | 58 | 624 | -3.83 | 2.894 | 1.024 | 0.1818 | 0.2949 |
| gradient_boosted_trees | 60 | 680 | -0.1374 | 4.105 | 1.013 | 0.1624 | 0.1882 |
| gradient_boosted_trees | 62 | 680 | -0.2615 | 2.99 | 1.011 | 0.1452 | 0.05 |
| gradient_boosted_trees | 64 | 680 | 0.7394 | 3.476 | 1.007 | 0.1504 | 0.08971 |
| gradient_boosted_trees | 65 | 615 | -1.121 | 3.278 | 1.006 | 0.15 | 0.0813 |
| mlp | 42 | 627 | 1.561 | 4.853 | 1.009 | 0.1949 | 0.311 |
| mlp | 50 | 650 | 0.9655 | 6.982 | 0.9846 | 0.1739 | 0.3077 |
| mlp | 57 | 640 | 0.3719 | 5.325 | 1.012 | 0.2208 | 0.2953 |
| mlp | 58 | 624 | -3.59 | 3.887 | 1.011 | 0.1818 | 0.3285 |
| mlp | 60 | 680 | -0.7577 | 4.373 | 1.01 | 0.1624 | 0.25 |
| mlp | 62 | 680 | -0.6229 | 3.854 | 1.006 | 0.1452 | 0.175 |
| mlp | 64 | 680 | -0.169 | 3.993 | 1.007 | 0.1504 | 0.1868 |
| mlp | 65 | 615 | -0.953 | 4.103 | 1.001 | 0.15 | 0.1967 |
| pedestal_memory_fusion_cnn_new | 42 | 627 | 1.992 | 5.365 | 1.034 | 0.1949 | 0.429 |
| pedestal_memory_fusion_cnn_new | 50 | 650 | 0.7528 | 8.828 | 1.015 | 0.1739 | 0.4631 |
| pedestal_memory_fusion_cnn_new | 57 | 640 | 2.875 | 5.657 | 1.046 | 0.2208 | 0.45 |
| pedestal_memory_fusion_cnn_new | 58 | 624 | -2.867 | 6.108 | 1.032 | 0.1818 | 0.4311 |
| pedestal_memory_fusion_cnn_new | 60 | 680 | -0.8274 | 4.591 | 1.02 | 0.1624 | 0.2647 |
| pedestal_memory_fusion_cnn_new | 62 | 680 | -0.7226 | 4.467 | 1.019 | 0.1452 | 0.2647 |
| pedestal_memory_fusion_cnn_new | 64 | 680 | 0.1406 | 3.714 | 1.046 | 0.1504 | 0.1735 |
| pedestal_memory_fusion_cnn_new | 65 | 615 | -0.2187 | 4.441 | 1.04 | 0.15 | 0.2618 |
| ridge | 42 | 627 | 1.189 | 4.999 | 1.01 | 0.1949 | 0.2935 |
| ridge | 50 | 650 | 0.2735 | 6.395 | 0.9963 | 0.1739 | 0.3 |
| ridge | 57 | 640 | 0.3621 | 5.614 | 1.017 | 0.2208 | 0.275 |
| ridge | 58 | 624 | -3.332 | 4.422 | 1.013 | 0.1818 | 0.2788 |
| ridge | 60 | 680 | -1.829 | 4.628 | 1.004 | 0.1624 | 0.2368 |
| ridge | 62 | 680 | -1.191 | 4.107 | 1.01 | 0.1452 | 0.1882 |
| ridge | 64 | 680 | -0.9868 | 4.377 | 1.005 | 0.1504 | 0.2324 |
| ridge | 65 | 615 | -1.383 | 4.708 | 1.005 | 0.15 | 0.265 |
| traditional_median_template_cfd_timewalk_shape | 42 | 627 | -0.02915 | 0.8213 | 0.9957 | 0.1949 | 0 |
| traditional_median_template_cfd_timewalk_shape | 50 | 650 | 0.3257 | 0.5831 | 0.9942 | 0.1739 | 0 |
| traditional_median_template_cfd_timewalk_shape | 57 | 640 | -0.3765 | 0.828 | 0.9962 | 0.2208 | 0 |
| traditional_median_template_cfd_timewalk_shape | 58 | 624 | 0.7553 | 0.8528 | 0.993 | 0.1818 | 0 |
| traditional_median_template_cfd_timewalk_shape | 60 | 680 | -0.1819 | 0.7543 | 0.9962 | 0.1624 | 0 |
| traditional_median_template_cfd_timewalk_shape | 62 | 680 | 0.6979 | 1.289 | 0.9973 | 0.1452 | 0 |
| traditional_median_template_cfd_timewalk_shape | 64 | 680 | 0.7565 | 0.5359 | 0.9946 | 0.1504 | 0 |
| traditional_median_template_cfd_timewalk_shape | 65 | 615 | 0.3348 | 0.686 | 0.9946 | 0.15 | 0 |

## Stratified Systematics

| stratum | level | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_innovation_bin | high_innovation | 1d_cnn | 1806 | -1.696 | 6.453 | 1.014 | 0.3399 | 0.4319 |
| baseline_innovation_bin | high_innovation | compact_waveform_transformer | 1806 | -2.132 | 5.935 | 0.9967 | 0.3399 | 0.3992 |
| baseline_innovation_bin | high_innovation | gradient_boosted_trees | 1806 | 0.321 | 3.673 | 1.009 | 0.3399 | 0.1949 |
| baseline_innovation_bin | high_innovation | mlp | 1806 | -0.08038 | 4.342 | 1 | 0.3399 | 0.2564 |
| baseline_innovation_bin | high_innovation | pedestal_memory_fusion_cnn_new | 1806 | -0.1708 | 5.649 | 1.025 | 0.3399 | 0.3588 |
| baseline_innovation_bin | high_innovation | ridge | 1806 | -0.6634 | 4.501 | 1.005 | 0.3399 | 0.2702 |
| baseline_innovation_bin | high_innovation | traditional_median_template_cfd_timewalk_shape | 1806 | 0.2461 | 0.9368 | 0.996 | 0.3399 | 0 |
| baseline_innovation_bin | low_innovation | 1d_cnn | 1616 | -2.258 | 4.702 | 1.035 | 0.07917 | 0.3546 |
| baseline_innovation_bin | low_innovation | compact_waveform_transformer | 1616 | -2.595 | 4.865 | 1.004 | 0.07917 | 0.3472 |
| baseline_innovation_bin | low_innovation | gradient_boosted_trees | 1616 | -0.2661 | 3.767 | 1.016 | 0.07917 | 0.1974 |
| baseline_innovation_bin | low_innovation | mlp | 1616 | -0.6659 | 4.037 | 1.009 | 0.07917 | 0.2413 |
| baseline_innovation_bin | low_innovation | pedestal_memory_fusion_cnn_new | 1616 | 0.132 | 5.003 | 1.032 | 0.07917 | 0.3205 |
| baseline_innovation_bin | low_innovation | ridge | 1616 | -1.139 | 4.072 | 1.016 | 0.07917 | 0.2271 |
| baseline_innovation_bin | low_innovation | traditional_median_template_cfd_timewalk_shape | 1616 | 0.3552 | 0.8359 | 0.9929 | 0.07917 | 0 |
| baseline_innovation_bin | mid_innovation | 1d_cnn | 1774 | -2.163 | 5.222 | 1.031 | 0.08571 | 0.3766 |
| baseline_innovation_bin | mid_innovation | compact_waveform_transformer | 1774 | -2.572 | 5.295 | 1.013 | 0.08571 | 0.3585 |
| baseline_innovation_bin | mid_innovation | gradient_boosted_trees | 1774 | 0.2754 | 3.728 | 1.01 | 0.08571 | 0.1821 |
| baseline_innovation_bin | mid_innovation | mlp | 1774 | -0.07995 | 4.402 | 1.001 | 0.08571 | 0.2666 |
| baseline_innovation_bin | mid_innovation | pedestal_memory_fusion_cnn_new | 1774 | 0.06572 | 5.229 | 1.036 | 0.08571 | 0.3382 |
| baseline_innovation_bin | mid_innovation | ridge | 1774 | -0.6754 | 4.564 | 1.006 | 0.08571 | 0.2728 |
| baseline_innovation_bin | mid_innovation | traditional_median_template_cfd_timewalk_shape | 1774 | 0.341 | 0.8898 | 0.9927 | 0.08571 | 0 |
| curvature_energy_bin | curved | 1d_cnn | 1513 | -1.696 | 6.607 | 0.9811 | 0.3063 | 0.4508 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1513 | -3.868 | 6.105 | 1 | 0.3063 | 0.4957 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1513 | 0.2228 | 3.739 | 1.001 | 0.3063 | 0.1923 |
| curvature_energy_bin | curved | mlp | 1513 | -0.105 | 4.392 | 0.9938 | 0.3063 | 0.2657 |
| curvature_energy_bin | curved | pedestal_memory_fusion_cnn_new | 1513 | -0.8839 | 6.18 | 0.9952 | 0.3063 | 0.4078 |
| curvature_energy_bin | curved | ridge | 1513 | -0.6729 | 4.344 | 0.996 | 0.3063 | 0.2373 |
| curvature_energy_bin | curved | traditional_median_template_cfd_timewalk_shape | 1513 | 0.438 | 0.9545 | 0.997 | 0.3063 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1868 | -1.524 | 4.918 | 1.024 | 0.117 | 0.3362 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1868 | -1.901 | 5.289 | 1.015 | 0.117 | 0.3517 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1868 | 0.138 | 3.862 | 1.011 | 0.117 | 0.2077 |
| curvature_energy_bin | moderate | mlp | 1868 | -0.3994 | 4.562 | 1.002 | 0.117 | 0.2746 |
| curvature_energy_bin | moderate | pedestal_memory_fusion_cnn_new | 1868 | 0.554 | 4.82 | 1.022 | 0.117 | 0.3126 |
| curvature_energy_bin | moderate | ridge | 1868 | -1.029 | 4.708 | 1.009 | 0.117 | 0.2837 |
| curvature_energy_bin | moderate | traditional_median_template_cfd_timewalk_shape | 1868 | 0.3785 | 0.8747 | 0.9949 | 0.117 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1815 | -2.731 | 4.865 | 1.063 | 0.1167 | 0.3917 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1815 | -2.019 | 4.564 | 0.9811 | 0.1167 | 0.2815 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1815 | 0.01503 | 3.65 | 1.012 | 0.1167 | 0.1736 |
| curvature_energy_bin | smooth | mlp | 1815 | -0.2667 | 4.134 | 1.002 | 0.1167 | 0.2264 |
| curvature_energy_bin | smooth | pedestal_memory_fusion_cnn_new | 1815 | 0.1739 | 4.911 | 1.053 | 0.1167 | 0.3113 |
| curvature_energy_bin | smooth | ridge | 1815 | -0.759 | 4.22 | 1.007 | 0.1167 | 0.2479 |
| curvature_energy_bin | smooth | traditional_median_template_cfd_timewalk_shape | 1815 | 0.1792 | 0.9088 | 0.9939 | 0.1167 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1725 | -2.36 | 4.834 | 0.9506 | 0.04319 | 0.3501 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1725 | -2.637 | 5.021 | 1.11 | 0.04319 | 0.3536 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1725 | 0.03856 | 3.499 | 0.9521 | 0.04319 | 0.1565 |
| derivative_onset_bin | nominal | mlp | 1725 | -0.3454 | 4.278 | 0.9713 | 0.04319 | 0.2504 |
| derivative_onset_bin | nominal | pedestal_memory_fusion_cnn_new | 1725 | -0.516 | 4.59 | 0.9726 | 0.04319 | 0.28 |
| derivative_onset_bin | nominal | ridge | 1725 | -1.028 | 4.344 | 0.9615 | 0.04319 | 0.2359 |
| derivative_onset_bin | nominal | traditional_median_template_cfd_timewalk_shape | 1725 | 0.4318 | 0.89 | 0.9911 | 0.04319 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1886 | -2.146 | 4.72 | 0.836 | 0.04114 | 0.3499 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1886 | -2.431 | 5.258 | 1.03 | 0.04114 | 0.3568 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1886 | -0.3658 | 3.509 | 0.961 | 0.04114 | 0.1469 |
| derivative_onset_bin | sharp | mlp | 1886 | -0.8655 | 4.287 | 0.9802 | 0.04114 | 0.2349 |
| derivative_onset_bin | sharp | pedestal_memory_fusion_cnn_new | 1886 | -0.4672 | 4.739 | 0.8257 | 0.04114 | 0.29 |
| derivative_onset_bin | sharp | ridge | 1886 | -1.367 | 4.207 | 0.9677 | 0.04114 | 0.2243 |
| derivative_onset_bin | sharp | traditional_median_template_cfd_timewalk_shape | 1886 | 0.4471 | 0.8822 | 0.991 | 0.04114 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1585 | -1.363 | 7.552 | 1.041 | 0.4679 | 0.4776 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1585 | -2.21 | 5.851 | 1.001 | 0.4679 | 0.4006 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1585 | 1.031 | 4.304 | 1.008 | 0.4679 | 0.282 |
| derivative_onset_bin | slow | mlp | 1585 | 0.5744 | 4.4 | 1 | 0.4679 | 0.2845 |
| derivative_onset_bin | slow | pedestal_memory_fusion_cnn_new | 1585 | 1.43 | 6.586 | 1.039 | 0.4679 | 0.4644 |
| derivative_onset_bin | slow | ridge | 1585 | 0.09951 | 4.917 | 1.003 | 0.4679 | 0.3211 |
| derivative_onset_bin | slow | traditional_median_template_cfd_timewalk_shape | 1585 | 0.02161 | 0.8674 | 0.9966 | 0.4679 | 0 |
| energy_bin | q1_low | 1d_cnn | 1350 | -2.853 | 6.347 | 1.064 | 0.4235 | 0.4978 |
| energy_bin | q1_low | compact_waveform_transformer | 1350 | -1.643 | 4.896 | 0.9935 | 0.4235 | 0.3178 |
| energy_bin | q1_low | gradient_boosted_trees | 1350 | 0.2008 | 3.696 | 1.01 | 0.4235 | 0.1867 |
| energy_bin | q1_low | mlp | 1350 | -0.04655 | 3.879 | 0.999 | 0.4235 | 0.2178 |
| energy_bin | q1_low | pedestal_memory_fusion_cnn_new | 1350 | -0.3055 | 5.27 | 1.041 | 0.4235 | 0.343 |
| energy_bin | q1_low | ridge | 1350 | -0.5661 | 4.234 | 1.005 | 0.4235 | 0.2526 |
| energy_bin | q1_low | traditional_median_template_cfd_timewalk_shape | 1350 | -0.04656 | 0.959 | 0.9923 | 0.4235 | 0 |
| energy_bin | q2 | 1d_cnn | 1416 | -1.969 | 4.681 | 1.031 | 0.102 | 0.3298 |
| energy_bin | q2 | compact_waveform_transformer | 1416 | -1.675 | 4.742 | 1.006 | 0.102 | 0.3008 |
| energy_bin | q2 | gradient_boosted_trees | 1416 | 0.2585 | 3.705 | 1.013 | 0.102 | 0.1836 |
| energy_bin | q2 | mlp | 1416 | -0.2087 | 4.5 | 1.003 | 0.102 | 0.2691 |
| energy_bin | q2 | pedestal_memory_fusion_cnn_new | 1416 | 0.8067 | 4.673 | 1.032 | 0.102 | 0.3008 |
| energy_bin | q2 | ridge | 1416 | -0.83 | 4.595 | 1.01 | 0.102 | 0.2846 |
| energy_bin | q2 | traditional_median_template_cfd_timewalk_shape | 1416 | 0.3267 | 0.7619 | 0.9954 | 0.102 | 0 |
| energy_bin | q3 | 1d_cnn | 1337 | -0.3479 | 4.681 | 0.9816 | 0.0847 | 0.3007 |
| energy_bin | q3 | compact_waveform_transformer | 1337 | -2.596 | 5.486 | 1.023 | 0.0847 | 0.3889 |
| energy_bin | q3 | gradient_boosted_trees | 1337 | -0.08008 | 3.731 | 1.007 | 0.0847 | 0.1892 |
| energy_bin | q3 | mlp | 1337 | -0.7157 | 4.42 | 0.9982 | 0.0847 | 0.2588 |
| energy_bin | q3 | pedestal_memory_fusion_cnn_new | 1337 | 0.6265 | 4.699 | 1.006 | 0.0847 | 0.2939 |
| energy_bin | q3 | ridge | 1337 | -1.361 | 4.395 | 1.006 | 0.0847 | 0.264 |
| energy_bin | q3 | traditional_median_template_cfd_timewalk_shape | 1337 | 0.4631 | 0.9221 | 0.9952 | 0.0847 | 0 |
| energy_bin | q4_high | 1d_cnn | 1093 | -2.958 | 5.903 | 0.9832 | 0.05891 | 0.4392 |
| energy_bin | q4_high | compact_waveform_transformer | 1093 | -4.608 | 5.991 | 1.007 | 0.05891 | 0.4968 |
| energy_bin | q4_high | gradient_boosted_trees | 1093 | 0.08597 | 3.801 | 1.007 | 0.05891 | 0.2095 |
| energy_bin | q4_high | mlp | 1093 | -0.1246 | 4.413 | 1.016 | 0.05891 | 0.279 |
| energy_bin | q4_high | pedestal_memory_fusion_cnn_new | 1093 | -1.284 | 6.477 | 1.043 | 0.05891 | 0.4428 |
| energy_bin | q4_high | ridge | 1093 | -0.5141 | 4.1 | 1.005 | 0.05891 | 0.2214 |
| energy_bin | q4_high | traditional_median_template_cfd_timewalk_shape | 1093 | 0.5489 | 0.9241 | 0.9939 | 0.05891 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3139 | -1.856 | 5.2 | 0.9413 | 0.1476 | 0.3781 |
| late_tail_morphology | compact | compact_waveform_transformer | 3139 | -2.139 | 5.298 | 1.064 | 0.1476 | 0.3555 |
| late_tail_morphology | compact | gradient_boosted_trees | 3139 | -0.2447 | 3.598 | 0.9564 | 0.1476 | 0.1666 |
| late_tail_morphology | compact | mlp | 3139 | -0.5944 | 4.294 | 0.9693 | 0.1476 | 0.2424 |
| late_tail_morphology | compact | pedestal_memory_fusion_cnn_new | 3139 | -0.02799 | 4.609 | 1 | 0.1476 | 0.2803 |
| late_tail_morphology | compact | ridge | 3139 | -1.11 | 4.464 | 0.9636 | 0.1476 | 0.244 |
| late_tail_morphology | compact | traditional_median_template_cfd_timewalk_shape | 3139 | 0.3624 | 0.8754 | 0.9984 | 0.1476 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 578 | -3.476 | 4.491 | 0.8469 | 0.03699 | 0.4014 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 578 | -4.339 | 4.496 | 0.9241 | 0.03699 | 0.455 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 578 | 0.2919 | 3.477 | 0.9955 | 0.03699 | 0.1436 |
| late_tail_morphology | diffuse_tail | mlp | 578 | 0.0917 | 4.481 | 0.8746 | 0.03699 | 0.2561 |
| late_tail_morphology | diffuse_tail | pedestal_memory_fusion_cnn_new | 578 | -2.137 | 5.354 | 0.7344 | 0.03699 | 0.3633 |
| late_tail_morphology | diffuse_tail | ridge | 578 | -1.27 | 4.266 | 0.923 | 0.03699 | 0.2439 |
| late_tail_morphology | diffuse_tail | traditional_median_template_cfd_timewalk_shape | 578 | 0.5802 | 1.015 | 0.9609 | 0.03699 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 364 | -2.604 | 6.988 | 1.097 | 0.4998 | 0.4011 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 364 | -1.284 | 4.738 | 0.9818 | 0.4998 | 0.294 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 364 | -0.0522 | 3.536 | 1.041 | 0.4998 | 0.1648 |
| late_tail_morphology | late_derivative_bump | mlp | 364 | -0.5889 | 3.841 | 0.9899 | 0.4998 | 0.239 |
| late_tail_morphology | late_derivative_bump | pedestal_memory_fusion_cnn_new | 364 | -0.153 | 6.055 | 1.16 | 0.4998 | 0.3544 |
| late_tail_morphology | late_derivative_bump | ridge | 364 | -0.5355 | 3.596 | 0.9952 | 0.4998 | 0.2308 |
| late_tail_morphology | late_derivative_bump | traditional_median_template_cfd_timewalk_shape | 364 | 0.5573 | 0.8408 | 0.9975 | 0.4998 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1115 | -1.107 | 6.565 | 1.076 | 0.2038 | 0.409 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1115 | -2.355 | 5.704 | 1.027 | 0.2038 | 0.3874 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1115 | 1.092 | 4.64 | 1.009 | 0.2038 | 0.2942 |
| late_tail_morphology | late_rising_tail | mlp | 1115 | 0.438 | 4.663 | 1.002 | 0.2038 | 0.296 |
| late_tail_morphology | late_rising_tail | pedestal_memory_fusion_cnn_new | 1115 | 2.428 | 6.386 | 1.027 | 0.2038 | 0.4906 |
| late_tail_morphology | late_rising_tail | ridge | 1115 | 0.09611 | 4.869 | 1.01 | 0.2038 | 0.3121 |
| late_tail_morphology | late_rising_tail | traditional_median_template_cfd_timewalk_shape | 1115 | 0.003171 | 0.8898 | 0.9918 | 0.2038 | 0 |
| peak_phase_bin | early_phase | 1d_cnn | 2284 | -1.989 | 5.617 | 1.05 | 0.1508 | 0.3849 |
| peak_phase_bin | early_phase | compact_waveform_transformer | 2284 | -2.81 | 5.679 | 1.015 | 0.1508 | 0.3984 |
| peak_phase_bin | early_phase | gradient_boosted_trees | 2284 | 0.01452 | 3.845 | 1.012 | 0.1508 | 0.2115 |
| peak_phase_bin | early_phase | mlp | 2284 | -0.2669 | 4.485 | 1.005 | 0.1508 | 0.2706 |
| peak_phase_bin | early_phase | pedestal_memory_fusion_cnn_new | 2284 | 0.06132 | 5.406 | 1.042 | 0.1508 | 0.3485 |
| peak_phase_bin | early_phase | ridge | 2284 | -0.8426 | 4.615 | 1.008 | 0.1508 | 0.2754 |
| peak_phase_bin | early_phase | traditional_median_template_cfd_timewalk_shape | 2284 | 0.3756 | 0.8869 | 0.9926 | 0.1508 | 0 |
| peak_phase_bin | late_phase | 1d_cnn | 1213 | -2.144 | 5.468 | 1.008 | 0.1624 | 0.4064 |
| peak_phase_bin | late_phase | compact_waveform_transformer | 1213 | -2.199 | 5.123 | 0.9959 | 0.1624 | 0.3578 |
| peak_phase_bin | late_phase | gradient_boosted_trees | 1213 | 0.1769 | 3.869 | 1.004 | 0.1624 | 0.188 |
| peak_phase_bin | late_phase | mlp | 1213 | -0.1999 | 4.331 | 0.9986 | 0.1624 | 0.2589 |
| peak_phase_bin | late_phase | pedestal_memory_fusion_cnn_new | 1213 | -0.0167 | 5.36 | 1.022 | 0.1624 | 0.3495 |
| peak_phase_bin | late_phase | ridge | 1213 | -0.844 | 4.415 | 1 | 0.1624 | 0.2589 |
| peak_phase_bin | late_phase | traditional_median_template_cfd_timewalk_shape | 1213 | 0.2979 | 0.8698 | 0.9971 | 0.1624 | 0 |
| peak_phase_bin | mid_phase | 1d_cnn | 1699 | -1.962 | 5.238 | 1.003 | 0.2073 | 0.382 |
| peak_phase_bin | mid_phase | compact_waveform_transformer | 1699 | -2.199 | 5.022 | 0.9922 | 0.2073 | 0.3378 |
| peak_phase_bin | mid_phase | gradient_boosted_trees | 1699 | 0.2084 | 3.534 | 1.012 | 0.2073 | 0.1666 |
| peak_phase_bin | mid_phase | mlp | 1699 | -0.3799 | 4.142 | 1.001 | 0.2073 | 0.2319 |
| peak_phase_bin | mid_phase | pedestal_memory_fusion_cnn_new | 1699 | -0.006788 | 5.002 | 1.024 | 0.2073 | 0.3214 |
| peak_phase_bin | mid_phase | ridge | 1699 | -0.7409 | 4.139 | 1.01 | 0.2073 | 0.2331 |
| peak_phase_bin | mid_phase | traditional_median_template_cfd_timewalk_shape | 1699 | 0.2547 | 0.943 | 0.995 | 0.2073 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1665 | -1.729 | 7.289 | 1.015 | 0.3763 | 0.4631 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1665 | -2.754 | 6.301 | 1.003 | 0.3763 | 0.4517 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1665 | 0.3556 | 3.84 | 1.005 | 0.3763 | 0.221 |
| pedestal_drift_bin | high | mlp | 1665 | 0.1267 | 4.426 | 0.9967 | 0.3763 | 0.2643 |
| pedestal_drift_bin | high | pedestal_memory_fusion_cnn_new | 1665 | 0.0682 | 6.035 | 1.033 | 0.3763 | 0.3994 |
| pedestal_drift_bin | high | ridge | 1665 | -0.6066 | 4.62 | 1.002 | 0.3763 | 0.2919 |
| pedestal_drift_bin | high | traditional_median_template_cfd_timewalk_shape | 1665 | 0.3226 | 0.8716 | 0.9965 | 0.3763 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1692 | -2.267 | 4.885 | 1.029 | 0.07805 | 0.3593 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1692 | -2.385 | 5.027 | 0.9984 | 0.07805 | 0.3398 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1692 | -0.04927 | 3.588 | 1.017 | 0.07805 | 0.1743 |
| pedestal_drift_bin | low | mlp | 1692 | -0.5882 | 3.941 | 1.007 | 0.07805 | 0.2323 |
| pedestal_drift_bin | low | pedestal_memory_fusion_cnn_new | 1692 | 0.03516 | 5.089 | 1.03 | 0.07805 | 0.3268 |
| pedestal_drift_bin | low | ridge | 1692 | -1.029 | 4.066 | 1.014 | 0.07805 | 0.2252 |
| pedestal_drift_bin | low | traditional_median_template_cfd_timewalk_shape | 1692 | 0.3159 | 0.8998 | 0.9927 | 0.07805 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1839 | -2.058 | 4.695 | 1.033 | 0.07345 | 0.3491 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1839 | -2.239 | 4.673 | 1 | 0.07345 | 0.3214 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1839 | 0.1265 | 3.714 | 1.015 | 0.07345 | 0.18 |
| pedestal_drift_bin | mid | mlp | 1839 | -0.3087 | 4.537 | 1.006 | 0.07345 | 0.2681 |
| pedestal_drift_bin | mid | pedestal_memory_fusion_cnn_new | 1839 | -0.0574 | 4.84 | 1.034 | 0.07345 | 0.298 |
| pedestal_drift_bin | mid | ridge | 1839 | -0.8304 | 4.485 | 1.012 | 0.07345 | 0.2567 |
| pedestal_drift_bin | mid | traditional_median_template_cfd_timewalk_shape | 1839 | 0.3205 | 0.9351 | 0.9925 | 0.07345 | 0 |
| pedestal_memory_bin | moderate_memory | 1d_cnn | 1767 | -1.965 | 4.935 | 1.033 | 0.08108 | 0.3418 |
| pedestal_memory_bin | moderate_memory | compact_waveform_transformer | 1767 | -2.34 | 4.974 | 1.005 | 0.08108 | 0.3486 |
| pedestal_memory_bin | moderate_memory | gradient_boosted_trees | 1767 | 0.2478 | 3.759 | 1.011 | 0.08108 | 0.1868 |
| pedestal_memory_bin | moderate_memory | mlp | 1767 | -0.1853 | 4.413 | 1.004 | 0.08108 | 0.2666 |
| pedestal_memory_bin | moderate_memory | pedestal_memory_fusion_cnn_new | 1767 | 0.134 | 4.924 | 1.032 | 0.08108 | 0.3124 |
| pedestal_memory_bin | moderate_memory | ridge | 1767 | -0.817 | 4.437 | 1.009 | 0.08108 | 0.2518 |
| pedestal_memory_bin | moderate_memory | traditional_median_template_cfd_timewalk_shape | 1767 | 0.3269 | 0.881 | 0.9925 | 0.08108 | 0 |
| pedestal_memory_bin | quiet_memory | 1d_cnn | 1601 | -2.104 | 5.05 | 1.031 | 0.0732 | 0.3785 |
| pedestal_memory_bin | quiet_memory | compact_waveform_transformer | 1601 | -2.201 | 5.093 | 0.9982 | 0.0732 | 0.3335 |
| pedestal_memory_bin | quiet_memory | gradient_boosted_trees | 1601 | -0.1987 | 3.768 | 1.019 | 0.0732 | 0.1993 |
| pedestal_memory_bin | quiet_memory | mlp | 1601 | -0.4676 | 4.136 | 1.007 | 0.0732 | 0.2517 |
| pedestal_memory_bin | quiet_memory | pedestal_memory_fusion_cnn_new | 1601 | 0.431 | 5.393 | 1.027 | 0.0732 | 0.3498 |
| pedestal_memory_bin | quiet_memory | ridge | 1601 | -0.8646 | 4.183 | 1.016 | 0.0732 | 0.2442 |
| pedestal_memory_bin | quiet_memory | traditional_median_template_cfd_timewalk_shape | 1601 | 0.3357 | 0.9629 | 0.9924 | 0.0732 | 0 |
| pedestal_memory_bin | strong_memory | 1d_cnn | 1828 | -2.028 | 6.366 | 1.012 | 0.3464 | 0.4437 |
| pedestal_memory_bin | strong_memory | compact_waveform_transformer | 1828 | -2.736 | 5.969 | 1.002 | 0.3464 | 0.4201 |
| pedestal_memory_bin | strong_memory | gradient_boosted_trees | 1828 | 0.3164 | 3.644 | 1.007 | 0.3464 | 0.1887 |
| pedestal_memory_bin | strong_memory | mlp | 1828 | -0.22 | 4.243 | 0.998 | 0.3464 | 0.2473 |
| pedestal_memory_bin | strong_memory | pedestal_memory_fusion_cnn_new | 1828 | -0.3274 | 5.656 | 1.03 | 0.3464 | 0.3578 |
| pedestal_memory_bin | strong_memory | ridge | 1828 | -0.7992 | 4.556 | 1.001 | 0.3464 | 0.2752 |
| pedestal_memory_bin | strong_memory | traditional_median_template_cfd_timewalk_shape | 1828 | 0.2932 | 0.8674 | 0.9967 | 0.3464 | 0 |
| pid_sideband | central | 1d_cnn | 3525 | -1.835 | 4.964 | 1.032 | 0.08173 | 0.3529 |
| pid_sideband | central | compact_waveform_transformer | 3525 | -2.02 | 4.958 | 0.999 | 0.08173 | 0.3248 |
| pid_sideband | central | gradient_boosted_trees | 3525 | 0.1265 | 3.762 | 1.014 | 0.08173 | 0.1932 |
| pid_sideband | central | mlp | 3525 | -0.3137 | 4.37 | 1.005 | 0.08173 | 0.259 |
| pid_sideband | central | pedestal_memory_fusion_cnn_new | 3525 | 0.5481 | 5.071 | 1.027 | 0.08173 | 0.3206 |
| pid_sideband | central | ridge | 3525 | -0.7593 | 4.413 | 1.013 | 0.08173 | 0.2565 |
| pid_sideband | central | traditional_median_template_cfd_timewalk_shape | 3525 | 0.2935 | 0.8909 | 0.9926 | 0.08173 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 841 | -2.673 | 8.855 | 0.7171 | 0.6685 | 0.5898 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 841 | -4.882 | 6.552 | 0.7886 | 0.6685 | 0.5755 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 841 | 0.3344 | 3.564 | 1.073 | 0.6685 | 0.2069 |
| pid_sideband | high_duplicate | mlp | 841 | 0.07685 | 4.351 | 0.9341 | 0.6685 | 0.2533 |
| pid_sideband | high_duplicate | pedestal_memory_fusion_cnn_new | 841 | -1.64 | 6.032 | 0.8999 | 0.6685 | 0.4233 |
| pid_sideband | high_duplicate | ridge | 841 | -0.8246 | 4.779 | 0.9598 | 0.6685 | 0.3092 |
| pid_sideband | high_duplicate | traditional_median_template_cfd_timewalk_shape | 841 | 0.2818 | 0.8836 | 0.9965 | 0.6685 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 830 | -2.281 | 4.737 | 0.9981 | 0.05231 | 0.3386 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 830 | -2.645 | 4.813 | 0.9607 | 0.05231 | 0.3482 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 830 | -0.06065 | 3.648 | 1.012 | 0.05231 | 0.1675 |
| pid_sideband | low_duplicate | mlp | 830 | -0.4366 | 4.164 | 0.997 | 0.05231 | 0.241 |
| pid_sideband | low_duplicate | pedestal_memory_fusion_cnn_new | 830 | -0.6489 | 5.248 | 1.023 | 0.05231 | 0.3373 |
| pid_sideband | low_duplicate | ridge | 830 | -1.053 | 3.942 | 1.006 | 0.05231 | 0.2108 |
| pid_sideband | low_duplicate | traditional_median_template_cfd_timewalk_shape | 830 | 0.5125 | 0.9743 | 0.9898 | 0.05231 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1624 | -2.762 | 5.211 | 0.8817 | 0.04002 | 0.3904 |
| pileup_separation_bin | close | compact_waveform_transformer | 1624 | -2.628 | 5.022 | 0.9245 | 0.04002 | 0.3658 |
| pileup_separation_bin | close | gradient_boosted_trees | 1624 | -0.07182 | 3.635 | 0.9062 | 0.04002 | 0.1687 |
| pileup_separation_bin | close | mlp | 1624 | -0.645 | 4.266 | 0.9096 | 0.04002 | 0.2445 |
| pileup_separation_bin | close | pedestal_memory_fusion_cnn_new | 1624 | -0.8585 | 5.104 | 0.8065 | 0.04002 | 0.3288 |
| pileup_separation_bin | close | ridge | 1624 | -1.366 | 4.254 | 0.9134 | 0.04002 | 0.2174 |
| pileup_separation_bin | close | traditional_median_template_cfd_timewalk_shape | 1624 | 0.4836 | 0.8739 | 0.9916 | 0.04002 | 0 |
| pileup_separation_bin | late | 1d_cnn | 4 | -10.74 | 11.08 | 0.5792 | 0.1367 | 0.75 |
| pileup_separation_bin | late | compact_waveform_transformer | 4 | -8.024 | 5.254 | 1.546 | 0.1367 | 0.5 |
| pileup_separation_bin | late | gradient_boosted_trees | 4 | 1.235 | 2.335 | 1.077 | 0.1367 | 0 |
| pileup_separation_bin | late | mlp | 4 | 0.545 | 1.518 | 1.071 | 0.1367 | 0.25 |
| pileup_separation_bin | late | pedestal_memory_fusion_cnn_new | 4 | -6.749 | 3.005 | 1.265 | 0.1367 | 0.5 |
| pileup_separation_bin | late | ridge | 4 | 2.09 | 3.099 | 0.9477 | 0.1367 | 0.25 |
| pileup_separation_bin | late | traditional_median_template_cfd_timewalk_shape | 4 | -0.1792 | 0.5069 | 1.006 | 0.1367 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1140 | -0.7064 | 6.059 | 0.9385 | 0.1208 | 0.4009 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1140 | -4.426 | 5.631 | 1.11 | 0.1208 | 0.4912 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1140 | -0.3024 | 3.634 | 0.9468 | 0.1208 | 0.1754 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_innovation_bin | 1d_cnn | 3 | low_innovation | 4.702 | high_innovation | 6.453 | 1.751 |
| baseline_innovation_bin | compact_waveform_transformer | 3 | low_innovation | 4.865 | high_innovation | 5.935 | 1.069 |
| baseline_innovation_bin | pedestal_memory_fusion_cnn_new | 3 | low_innovation | 5.003 | high_innovation | 5.649 | 0.646 |
| baseline_innovation_bin | ridge | 3 | low_innovation | 4.072 | mid_innovation | 4.564 | 0.4914 |
| baseline_innovation_bin | mlp | 3 | low_innovation | 4.037 | mid_innovation | 4.402 | 0.3651 |
| baseline_innovation_bin | traditional_median_template_cfd_timewalk_shape | 3 | low_innovation | 0.8359 | high_innovation | 0.9368 | 0.101 |
| baseline_innovation_bin | gradient_boosted_trees | 3 | high_innovation | 3.673 | low_innovation | 3.767 | 0.09426 |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.865 | curved | 6.607 | 1.742 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.564 | curved | 6.105 | 1.541 |
| curvature_energy_bin | pedestal_memory_fusion_cnn_new | 3 | moderate | 4.82 | curved | 6.18 | 1.36 |
| curvature_energy_bin | ridge | 3 | smooth | 4.22 | moderate | 4.708 | 0.4881 |
| curvature_energy_bin | mlp | 3 | smooth | 4.134 | moderate | 4.562 | 0.4287 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.65 | moderate | 3.862 | 0.2126 |
| curvature_energy_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate | 0.8747 | curved | 0.9545 | 0.07977 |
| derivative_onset_bin | 1d_cnn | 3 | sharp | 4.72 | slow | 7.552 | 2.832 |
| derivative_onset_bin | pedestal_memory_fusion_cnn_new | 3 | nominal | 4.59 | slow | 6.586 | 1.997 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 5.021 | slow | 5.851 | 0.8302 |
| derivative_onset_bin | gradient_boosted_trees | 3 | nominal | 3.499 | slow | 4.304 | 0.8045 |
| derivative_onset_bin | ridge | 3 | sharp | 4.207 | slow | 4.917 | 0.7098 |
| derivative_onset_bin | mlp | 3 | nominal | 4.278 | slow | 4.4 | 0.1218 |
| derivative_onset_bin | traditional_median_template_cfd_timewalk_shape | 3 | slow | 0.8674 | nominal | 0.89 | 0.02266 |
| energy_bin | pedestal_memory_fusion_cnn_new | 4 | q2 | 4.673 | q4_high | 6.477 | 1.803 |
| energy_bin | 1d_cnn | 4 | q3 | 4.681 | q1_low | 6.347 | 1.666 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 4.742 | q4_high | 5.991 | 1.249 |
| energy_bin | mlp | 4 | q1_low | 3.879 | q2 | 4.5 | 0.6211 |
| energy_bin | ridge | 4 | q4_high | 4.1 | q2 | 4.595 | 0.4955 |
| energy_bin | traditional_median_template_cfd_timewalk_shape | 4 | q2 | 0.7619 | q1_low | 0.959 | 0.1971 |
| energy_bin | gradient_boosted_trees | 4 | q1_low | 3.696 | q4_high | 3.801 | 0.1053 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 4.491 | late_derivative_bump | 6.988 | 2.497 |
| late_tail_morphology | pedestal_memory_fusion_cnn_new | 4 | compact | 4.609 | late_rising_tail | 6.386 | 1.777 |
| late_tail_morphology | ridge | 4 | late_derivative_bump | 3.596 | late_rising_tail | 4.869 | 1.272 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 4.496 | late_rising_tail | 5.704 | 1.207 |
| late_tail_morphology | gradient_boosted_trees | 4 | diffuse_tail | 3.477 | late_rising_tail | 4.64 | 1.163 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.841 | late_rising_tail | 4.663 | 0.8218 |
| late_tail_morphology | traditional_median_template_cfd_timewalk_shape | 4 | late_derivative_bump | 0.8408 | diffuse_tail | 1.015 | 0.1742 |
| peak_phase_bin | compact_waveform_transformer | 3 | mid_phase | 5.022 | early_phase | 5.679 | 0.6566 |
| peak_phase_bin | ridge | 3 | mid_phase | 4.139 | early_phase | 4.615 | 0.4767 |
| peak_phase_bin | pedestal_memory_fusion_cnn_new | 3 | mid_phase | 5.002 | early_phase | 5.406 | 0.404 |
| peak_phase_bin | 1d_cnn | 3 | mid_phase | 5.238 | early_phase | 5.617 | 0.3786 |
| peak_phase_bin | mlp | 3 | mid_phase | 4.142 | early_phase | 4.485 | 0.3427 |
| peak_phase_bin | gradient_boosted_trees | 3 | mid_phase | 3.534 | late_phase | 3.869 | 0.3349 |
| peak_phase_bin | traditional_median_template_cfd_timewalk_shape | 3 | late_phase | 0.8698 | mid_phase | 0.943 | 0.07318 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 4.695 | high | 7.289 | 2.594 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 4.673 | high | 6.301 | 1.628 |
| pedestal_drift_bin | pedestal_memory_fusion_cnn_new | 3 | mid | 4.84 | high | 6.035 | 1.196 |
| pedestal_drift_bin | mlp | 3 | low | 3.941 | mid | 4.537 | 0.5959 |
| pedestal_drift_bin | ridge | 3 | low | 4.066 | high | 4.62 | 0.5536 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.588 | high | 3.84 | 0.2517 |
| pedestal_drift_bin | traditional_median_template_cfd_timewalk_shape | 3 | high | 0.8716 | mid | 0.9351 | 0.06357 |
| pedestal_memory_bin | 1d_cnn | 3 | moderate_memory | 4.935 | strong_memory | 6.366 | 1.431 |
| pedestal_memory_bin | compact_waveform_transformer | 3 | moderate_memory | 4.974 | strong_memory | 5.969 | 0.9953 |
| pedestal_memory_bin | pedestal_memory_fusion_cnn_new | 3 | moderate_memory | 4.924 | strong_memory | 5.656 | 0.7323 |
| pedestal_memory_bin | ridge | 3 | quiet_memory | 4.183 | strong_memory | 4.556 | 0.3733 |
| pedestal_memory_bin | mlp | 3 | quiet_memory | 4.136 | moderate_memory | 4.413 | 0.2771 |
| pedestal_memory_bin | gradient_boosted_trees | 3 | strong_memory | 3.644 | quiet_memory | 3.768 | 0.1236 |
| pedestal_memory_bin | traditional_median_template_cfd_timewalk_shape | 3 | strong_memory | 0.8674 | quiet_memory | 0.9629 | 0.09551 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 4.737 | high_duplicate | 8.855 | 4.118 |
| pid_sideband | compact_waveform_transformer | 3 | low_duplicate | 4.813 | high_duplicate | 6.552 | 1.739 |
| pid_sideband | pedestal_memory_fusion_cnn_new | 3 | central | 5.071 | high_duplicate | 6.032 | 0.9616 |
| pid_sideband | ridge | 3 | low_duplicate | 3.942 | high_duplicate | 4.779 | 0.837 |
| pid_sideband | mlp | 3 | low_duplicate | 4.164 | central | 4.37 | 0.2059 |
| pid_sideband | gradient_boosted_trees | 3 | high_duplicate | 3.564 | central | 3.762 | 0.198 |
| pid_sideband | traditional_median_template_cfd_timewalk_shape | 3 | high_duplicate | 0.8836 | low_duplicate | 0.9743 | 0.09068 |
| pileup_separation_bin | 1d_cnn | 4 | close | 5.211 | late | 11.08 | 5.868 |
| pileup_separation_bin | mlp | 4 | late | 1.518 | mid | 4.375 | 2.857 |
| pileup_separation_bin | pedestal_memory_fusion_cnn_new | 4 | late | 3.005 | none | 5.388 | 2.383 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 2.335 | none | 3.87 | 1.535 |
| pileup_separation_bin | ridge | 4 | late | 3.099 | mid | 4.59 | 1.491 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 4.904 | mid | 5.631 | 0.727 |
| pileup_separation_bin | traditional_median_template_cfd_timewalk_shape | 4 | late | 0.5069 | none | 0.9012 | 0.3943 |
| pulse_shape_class | pedestal_memory_fusion_cnn_new | 3 | nominal | 4.223 | late_tail | 6.714 | 2.491 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.18 | compact | 6.535 | 2.355 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 4.615 | compact | 5.776 | 1.161 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.458 | late_tail | 4.175 | 0.7168 |
| pulse_shape_class | mlp | 3 | nominal | 4.258 | late_tail | 4.568 | 0.3103 |
| pulse_shape_class | ridge | 3 | nominal | 4.231 | late_tail | 4.532 | 0.301 |
| pulse_shape_class | traditional_median_template_cfd_timewalk_shape | 3 | nominal | 0.8054 | compact | 0.9697 | 0.1643 |
| q_template_error_bin | 1d_cnn | 3 | template_like | 4.212 | shape_outlier | 7.989 | 3.777 |
| q_template_error_bin | pedestal_memory_fusion_cnn_new | 3 | template_like | 4.304 | shape_outlier | 6.979 | 2.676 |
| q_template_error_bin | compact_waveform_transformer | 3 | template_like | 4.028 | shape_outlier | 6.422 | 2.394 |
| q_template_error_bin | ridge | 3 | template_like | 4.081 | shape_outlier | 4.939 | 0.8575 |
| q_template_error_bin | gradient_boosted_trees | 3 | template_like | 3.359 | shape_outlier | 4.134 | 0.775 |
| q_template_error_bin | mlp | 3 | template_like | 4.049 | shape_outlier | 4.452 | 0.4029 |
| q_template_error_bin | traditional_median_template_cfd_timewalk_shape | 3 | shape_outlier | 0.8685 | template_like | 0.8947 | 0.02618 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.743 | linear | 5.803 | 1.06 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 4.849 | linear | 5.487 | 0.6381 |
| saturation_onset_bin | pedestal_memory_fusion_cnn_new | 2 | near_saturation | 4.844 | linear | 5.43 | 0.5858 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.504 | linear | 3.858 | 0.3543 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.223 | linear | 4.355 | 0.1315 |
| saturation_onset_bin | traditional_median_template_cfd_timewalk_shape | 2 | near_saturation | 0.807 | linear | 0.9349 | 0.1279 |
| saturation_onset_bin | ridge | 2 | linear | 4.456 | near_saturation | 4.489 | 0.03267 |

## Ablations

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 42 | 0.1589 | 3.746 | 3.311 | 4.323 | -0.02696 | 0.1932 |
| full_derivative_gradient_boosted_trees | 85 | 0.1543 | 3.773 | 3.33 | 4.365 | 0 | 0.1909 |
| derivative_only | 43 | 0.2909 | 4.033 | 3.446 | 4.942 | 0.2597 | 0.2317 |
| amplitude_cfd_no_derivative | 5 | 0.3748 | 4.083 | 3.553 | 5.029 | 0.3098 | 0.2365 |
| late_tail_curvature_window_only | 17 | 0.3589 | 4.586 | 4.1 | 5.199 | 0.8128 | 0.281 |
| onset_derivative_window_only | 14 | 0.2359 | 4.859 | 3.937 | 5.884 | 1.086 | 0.3097 |
| pretrigger_derivative_only | 7 | -2.919 | 18.59 | 16.35 | 19.14 | 14.82 | 0.5922 |

## Caveats

The raw files do not carry independent external particle-identification or
picosecond timing truth per pulse.  Timing, energy, saturation, and PID
statements are therefore transfer diagnostics on reproducible waveform-derived
proxies: CFD20 residual, raw amplitude, flat-top/late-pulse proxies, and
duplicate-readout sideband.  Run-block bootstrap protects against event-level
overconfidence but leaves model selection multiplicity as a caveat.  Neural
training used a fixed small CPU budget; the conclusion is about whether compact
learned models naturally beat a strong transparent pedestal-memory fit, not
about exhaustive architecture search.

Runtime was `117.1 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29` with Python
`3.8.10`.
