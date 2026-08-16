# S44a: S03 Guardrail-Orthogonal Cross-Sample CNN Timewalk Adoption Audit

## Abstract

Issue `#2414` asks whether the apparent Sample-II-trained CNN lift from ticket
`#2412` survives detector-identity guardrails.  I first reproduced the raw
B-stack selected-pulse count from ROOT, then trained on Sample-II analysis runs
`[58, 59, 60, 61, 62, 63, 65]` and evaluated transfer to Sample-I analysis plus run 64
`[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 64]`.  The benchmark compares analytic S03 time-walk,
ridge, gradient-boosted trees, MLP, 1D-CNN, and a new guardrail-orthogonal edge
transformer.  The primary decision uses support-matched held-out pulses; the
winner named in `result.json` is **`analytic_s03_timewalk`** with sigma68
`1.037 ns [0.726, 1.287]`.

## Raw ROOT Reproduction

Input files are `data/root/root/hrdb_run_*.root`.  For each event, `HRDv` is
reshaped as `(8,18)`.  For B-stack stave channel `c`, baseline and amplitude are

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

The reproduced registered count is

`N = sum_e sum_c 1[A_c > 1000]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group count is **640737**, matching
the registered value exactly.  Hashes are written to `input_sha256.csv`; first rows:

| run | path | bytes | sha256 |
| --- | --- | --- | --- |
| 31 | data/root/root/hrdb_run_0031.root | 11638901 | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| 32 | data/root/root/hrdb_run_0032.root | 12157812 | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| 33 | data/root/root/hrdb_run_0033.root | 16781109 | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| 34 | data/root/root/hrdb_run_0034.root | 11697434 | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| 35 | data/root/root/hrdb_run_0035.root | 7793651 | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| 36 | data/root/root/hrdb_run_0036.root | 6167361 | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| 37 | data/root/root/hrdb_run_0037.root | 14369738 | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| 39 | data/root/root/hrdb_run_0039.root | 8625385 | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |

## Estimand

For fraction `f`, the CFD crossing is linearly interpolated before the pulse
maximum:

`t_f = k - 1 + (f A - y_(k-1)) / (y_k - y_(k-1))`,

where `y_t = x_t - b` and `k` is the first pre-peak sample with `y_k >= f A`.
The supervised target is the run/stave-centered onset residual

`Y_i = 10 ns * [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

This target implements the stave-offset residualization guardrail: stable
per-run and per-stave offsets are removed before any learner sees labels.

## Split, Support, and Uncertainty

The split unit is the run.  Sample-II analysis runs train the models; Sample-I
analysis runs and run 64 are never used for fitting.  Sampled rows:

| split | rows |
| --- | --- |
| heldout | 6628 |
| train | 3599 |

Support matching removes held-out pulses outside the central training support in
amplitude and late-tail fraction, using quantiles `[0.05, 0.95]`.

| split | support_matched | rows |
| --- | --- | --- |
| heldout | False | 2480 |
| heldout | True | 4148 |
| train | False | 637 |
| train | True | 2962 |

Confidence intervals are 95% percentile intervals from
`400` held-out run-block bootstrap resamples.  The
resolution metric is

`sigma_68(epsilon) = 0.5 * [Q_84(epsilon - median(epsilon)) - Q_16(epsilon - median(epsilon))]`.

## Methods

| method | family | description |
| --- | --- | --- |
| analytic_s03_timewalk | traditional | CFD20/50 S03-style time-walk fit with derivative residual correction; no event/run ids. |
| ridge | linear ML | Standardized ridge on waveform, CFD, pedestal, onset derivative, and curvature summaries; no stave one-hot or run id. |
| gradient_boosted_trees | tree ML | Histogram gradient-boosted trees on the same guardrailed features. |
| mlp | neural tabular | Two-layer MLP on the same guardrailed feature matrix. |
| 1d_cnn_waveform_only | neural waveform | Compact 1D-CNN over only the normalized 18-sample waveform. |
| guardrail_orthogonal_edge_transformer_new | new architecture | Transformer over waveform, first derivative, and curvature channels with derivative-magnitude pooling; no amplitude, stave one-hot, duplicate readout, event id, or run id. |

The new architecture is sensible here because the risk is detector identity
leakage from stave labels and amplitude-support tails.  The model is therefore
orthogonal to those channels by construction: it consumes only waveform shape,
first derivative, second derivative, and sample position, then gates the
transformer states by derivative magnitude before regression.

## Primary Support-Matched Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| analytic_s03_timewalk | 4148 | 0.1778 | -0.06778 | 0.3355 | 1.037 | 0.726 | 1.287 | 1.015 | 0 |
| gradient_boosted_trees | 4148 | 2.785 | 1.694 | 4.816 | 7.413 | 3.313 | 10.23 | 9.236 | 0.5075 |
| ridge | 4148 | 1.774 | -0.6965 | 3.719 | 7.633 | 5.242 | 10.2 | 8.9 | 0.5039 |
| mlp | 4148 | 1.471 | -0.3753 | 3.614 | 7.881 | 5.349 | 10.19 | 9.049 | 0.4993 |
| 1d_cnn_waveform_only | 4148 | 2.742 | 1.114 | 4.945 | 9.7 | 7.512 | 11.54 | 17.15 | 0.6046 |
| guardrail_orthogonal_edge_transformer_new | 4148 | -1.342 | -2.355 | -0.6396 | 20.98 | 15.83 | 24.72 | 26.25 | 0.7124 |

## Full-Transfer Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| analytic_s03_timewalk | 6628 | -0.01751 | -0.3729 | 0.2028 | 1.111 | 0.9694 | 1.377 | 1.148 | 0 |
| gradient_boosted_trees | 6628 | 3.573 | 2.174 | 5.162 | 7.421 | 3.626 | 10.14 | 9.464 | 0.5748 |
| ridge | 6628 | 2.63 | 1.002 | 5.475 | 7.705 | 5.445 | 9.942 | 9.231 | 0.5768 |
| mlp | 6628 | 2.498 | 0.5626 | 5.179 | 8.134 | 5.527 | 10.45 | 9.878 | 0.5705 |
| 1d_cnn_waveform_only | 6628 | 5.306 | 3.985 | 6.374 | 11.6 | 9.269 | 15.36 | 24.96 | 0.6749 |
| guardrail_orthogonal_edge_transformer_new | 6628 | 0.1803 | -0.04834 | 0.4258 | 32.84 | 28.01 | 35.66 | 36.08 | 0.6927 |

## Paired Deltas Against Analytic S03

Positive `delta_sigma68_ns` means worse resolution than the analytic comparator.

Support-matched domain:

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | analytic_s03_timewalk | 6.376 | 2.32 | 9.213 | 2.607 | 1.529 | 4.671 |
| ridge | analytic_s03_timewalk | 6.596 | 4.201 | 9.172 | 1.596 | -0.8828 | 3.521 |
| mlp | analytic_s03_timewalk | 6.844 | 4.253 | 9.112 | 1.294 | -0.6067 | 3.499 |
| 1d_cnn_waveform_only | analytic_s03_timewalk | 8.662 | 6.432 | 10.57 | 2.564 | 0.9168 | 4.711 |
| guardrail_orthogonal_edge_transformer_new | analytic_s03_timewalk | 19.94 | 14.65 | 23.67 | -1.52 | -2.512 | -0.7427 |

Full-transfer domain:

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | analytic_s03_timewalk | 6.31 | 2.483 | 8.941 | 3.59 | 2.156 | 5.297 |
| ridge | analytic_s03_timewalk | 6.594 | 4.261 | 8.819 | 2.647 | 1.119 | 5.353 |
| mlp | analytic_s03_timewalk | 7.023 | 4.395 | 9.264 | 2.516 | 0.6121 | 5.161 |
| 1d_cnn_waveform_only | analytic_s03_timewalk | 10.49 | 8.12 | 14.22 | 5.324 | 4.118 | 6.392 |
| guardrail_orthogonal_edge_transformer_new | analytic_s03_timewalk | 31.73 | 26.94 | 34.53 | 0.1978 | -0.1514 | 0.6403 |

## Run Stability

| domain | method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| full_transfer | 1d_cnn_waveform_only | 44 | 284 | 8.873 | 6.172 | 0.7641 |
| full_transfer | 1d_cnn_waveform_only | 45 | 520 | 3.524 | 17.29 | 0.6635 |
| full_transfer | 1d_cnn_waveform_only | 46 | 142 | 11.04 | 4.796 | 0.9366 |
| full_transfer | 1d_cnn_waveform_only | 47 | 290 | 9.887 | 5.381 | 0.8414 |
| full_transfer | 1d_cnn_waveform_only | 48 | 502 | 5.576 | 11.21 | 0.5876 |
| full_transfer | 1d_cnn_waveform_only | 49 | 505 | 6.147 | 8.76 | 0.6792 |
| full_transfer | 1d_cnn_waveform_only | 50 | 520 | 5.477 | 15.37 | 0.7404 |
| full_transfer | 1d_cnn_waveform_only | 51 | 450 | 4.632 | 15.57 | 0.78 |
| full_transfer | 1d_cnn_waveform_only | 52 | 371 | 5.369 | 12.71 | 0.8059 |
| full_transfer | 1d_cnn_waveform_only | 53 | 510 | 3.57 | 21.81 | 0.6843 |
| full_transfer | 1d_cnn_waveform_only | 54 | 503 | 3.172 | 20.88 | 0.6183 |
| full_transfer | 1d_cnn_waveform_only | 55 | 471 | 4.282 | 17.51 | 0.7304 |
| full_transfer | 1d_cnn_waveform_only | 56 | 520 | 6.831 | 17.66 | 0.7519 |
| full_transfer | 1d_cnn_waveform_only | 57 | 520 | 4.372 | 9.725 | 0.5423 |
| full_transfer | 1d_cnn_waveform_only | 64 | 520 | 0.9464 | 5.397 | 0.3538 |
| full_transfer | analytic_s03_timewalk | 44 | 284 | 0.3666 | 1.692 | 0 |
| full_transfer | analytic_s03_timewalk | 45 | 520 | -0.1706 | 1.111 | 0 |
| full_transfer | analytic_s03_timewalk | 46 | 142 | 0.1877 | 0.1245 | 0 |
| full_transfer | analytic_s03_timewalk | 47 | 290 | 0.452 | 1.304 | 0 |
| full_transfer | analytic_s03_timewalk | 48 | 502 | -0.2578 | 1.012 | 0 |
| full_transfer | analytic_s03_timewalk | 49 | 505 | 0.4047 | 1.191 | 0 |
| full_transfer | analytic_s03_timewalk | 50 | 520 | -0.05201 | 0.9159 | 0 |
| full_transfer | analytic_s03_timewalk | 51 | 450 | -0.8081 | 1.2 | 0 |
| full_transfer | analytic_s03_timewalk | 52 | 371 | -1.011 | 1.156 | 0 |
| full_transfer | analytic_s03_timewalk | 53 | 510 | -0.2563 | 2.017 | 0 |
| full_transfer | analytic_s03_timewalk | 54 | 503 | -1.714 | 1.24 | 0 |
| full_transfer | analytic_s03_timewalk | 55 | 471 | 0.357 | 1.357 | 0 |
| full_transfer | analytic_s03_timewalk | 56 | 520 | 0.01085 | 0.3244 | 0 |
| full_transfer | analytic_s03_timewalk | 57 | 520 | -1.082 | 0.9284 | 0 |
| full_transfer | analytic_s03_timewalk | 64 | 520 | 0.4649 | 0.3443 | 0 |
| full_transfer | gradient_boosted_trees | 44 | 284 | 6.409 | 2.167 | 0.7782 |
| full_transfer | gradient_boosted_trees | 45 | 520 | 2.55 | 14.41 | 0.5096 |
| full_transfer | gradient_boosted_trees | 46 | 142 | 9.042 | 1.071 | 0.993 |
| full_transfer | gradient_boosted_trees | 47 | 290 | 7.621 | 3.101 | 0.9586 |
| full_transfer | gradient_boosted_trees | 48 | 502 | 4.697 | 3.821 | 0.4422 |
| full_transfer | gradient_boosted_trees | 49 | 505 | 5.967 | 1.624 | 0.6812 |
| full_transfer | gradient_boosted_trees | 50 | 520 | 4.312 | 19.72 | 0.7327 |
| full_transfer | gradient_boosted_trees | 51 | 450 | 1.807 | 9.437 | 0.7222 |
| full_transfer | gradient_boosted_trees | 52 | 371 | 5.407 | 8.858 | 0.9704 |
| full_transfer | gradient_boosted_trees | 53 | 510 | 1.947 | 10.75 | 0.5176 |
| full_transfer | gradient_boosted_trees | 54 | 503 | 2.531 | 12.42 | 0.4891 |
| full_transfer | gradient_boosted_trees | 55 | 471 | -2.575 | 6.56 | 0.5393 |
| full_transfer | gradient_boosted_trees | 56 | 520 | 4.795 | 10.58 | 0.7442 |
| full_transfer | gradient_boosted_trees | 57 | 520 | 3.832 | 1.68 | 0.1962 |
| full_transfer | gradient_boosted_trees | 64 | 520 | 1.348 | 1.191 | 0.03846 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 44 | 284 | 0.2116 | 21.93 | 0.6585 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 45 | 520 | -0.1446 | 40.69 | 0.8 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 46 | 142 | 0.6681 | 5.14 | 0.338 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 47 | 290 | 0.05439 | 9.271 | 0.5069 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 48 | 502 | 0.07283 | 34.48 | 0.745 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 49 | 505 | -0.1266 | 31.52 | 0.7228 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 50 | 520 | 0.228 | 32.18 | 0.6481 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 51 | 450 | 0.3566 | 35.07 | 0.6756 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 52 | 371 | 0.6546 | 33.5 | 0.6712 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 53 | 510 | 0.5006 | 41.58 | 0.6882 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 54 | 503 | 0.3508 | 36.98 | 0.7316 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 55 | 471 | 0.2719 | 36.76 | 0.7622 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 56 | 520 | 0.8339 | 38.42 | 0.7269 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 57 | 520 | 0.7218 | 31.83 | 0.7538 |
| full_transfer | guardrail_orthogonal_edge_transformer_new | 64 | 520 | -0.2579 | 15.04 | 0.6077 |
| full_transfer | mlp | 44 | 284 | 7.596 | 1.951 | 0.9507 |
| full_transfer | mlp | 45 | 520 | 0.2784 | 14.88 | 0.4981 |
| full_transfer | mlp | 46 | 142 | 11.79 | 1.81 | 0.993 |
| full_transfer | mlp | 47 | 290 | 9.142 | 3.331 | 0.9138 |
| full_transfer | mlp | 48 | 502 | 5.976 | 5.6 | 0.5339 |
| full_transfer | mlp | 49 | 505 | 4.904 | 3.174 | 0.4832 |
| full_transfer | mlp | 50 | 520 | 1.609 | 19.89 | 0.5865 |
| full_transfer | mlp | 51 | 450 | -1.679 | 10.61 | 0.7044 |
| full_transfer | mlp | 52 | 371 | 3.1 | 9.373 | 0.8625 |
| full_transfer | mlp | 53 | 510 | -0.9699 | 11.02 | 0.5176 |
| full_transfer | mlp | 54 | 503 | -0.1593 | 12.69 | 0.5209 |
| full_transfer | mlp | 55 | 471 | -3.327 | 8.527 | 0.6008 |
| full_transfer | mlp | 56 | 520 | 1.969 | 10.83 | 0.6038 |
| full_transfer | mlp | 57 | 520 | 3.582 | 4.12 | 0.4192 |
| full_transfer | mlp | 64 | 520 | 1.128 | 3.075 | 0.09808 |
| full_transfer | ridge | 44 | 284 | 7.503 | 1.788 | 0.9296 |
| full_transfer | ridge | 45 | 520 | 0.5328 | 14.3 | 0.5019 |
| full_transfer | ridge | 46 | 142 | 11.47 | 1.266 | 1 |
| full_transfer | ridge | 47 | 290 | 8.768 | 3.553 | 0.9172 |
| full_transfer | ridge | 48 | 502 | 5.303 | 5.142 | 0.5279 |
| full_transfer | ridge | 49 | 505 | 5.406 | 3.136 | 0.5446 |
| full_transfer | ridge | 50 | 520 | 1.901 | 19.22 | 0.6115 |
| full_transfer | ridge | 51 | 450 | -1.415 | 10.2 | 0.7111 |
| full_transfer | ridge | 52 | 371 | 3.197 | 8.977 | 0.8976 |
| full_transfer | ridge | 53 | 510 | -0.3024 | 10.23 | 0.5098 |
| full_transfer | ridge | 54 | 503 | 0.1521 | 12.18 | 0.5089 |
| full_transfer | ridge | 55 | 471 | -2.624 | 7.582 | 0.5817 |
| full_transfer | ridge | 56 | 520 | 2.622 | 10.09 | 0.6077 |
| full_transfer | ridge | 57 | 520 | 3.832 | 4.135 | 0.4269 |
| full_transfer | ridge | 64 | 520 | 1.241 | 3.126 | 0.09808 |
| support_matched | 1d_cnn_waveform_only | 44 | 197 | 8.934 | 5.114 | 0.7563 |
| support_matched | 1d_cnn_waveform_only | 45 | 322 | 1.669 | 11.19 | 0.5466 |
| support_matched | 1d_cnn_waveform_only | 46 | 91 | 13.23 | 4.104 | 0.978 |
| support_matched | 1d_cnn_waveform_only | 47 | 184 | 10.57 | 4.56 | 0.8696 |
| support_matched | 1d_cnn_waveform_only | 48 | 345 | 4.107 | 7.022 | 0.5275 |
| support_matched | 1d_cnn_waveform_only | 49 | 352 | 5.769 | 6.425 | 0.6278 |
| support_matched | 1d_cnn_waveform_only | 50 | 286 | 0.1861 | 18.65 | 0.6399 |
| support_matched | 1d_cnn_waveform_only | 51 | 258 | -2.633 | 12.37 | 0.686 |
| support_matched | 1d_cnn_waveform_only | 52 | 203 | 1.357 | 11.61 | 0.8227 |
| support_matched | 1d_cnn_waveform_only | 53 | 279 | -1.148 | 10.21 | 0.5663 |
| support_matched | 1d_cnn_waveform_only | 54 | 277 | -0.01153 | 12.63 | 0.5487 |
| support_matched | 1d_cnn_waveform_only | 55 | 248 | -2.769 | 11.1 | 0.6774 |
| support_matched | 1d_cnn_waveform_only | 56 | 296 | 2.27 | 11.11 | 0.6419 |
| support_matched | 1d_cnn_waveform_only | 57 | 378 | 3.554 | 6.126 | 0.4921 |
| support_matched | 1d_cnn_waveform_only | 64 | 432 | 0.9339 | 5.179 | 0.3472 |
| support_matched | analytic_s03_timewalk | 44 | 197 | 1.312 | 1.692 | 0 |
| support_matched | analytic_s03_timewalk | 45 | 322 | 0.08055 | 1.068 | 0 |
| support_matched | analytic_s03_timewalk | 46 | 91 | 0.1751 | 0.08894 | 0 |
| support_matched | analytic_s03_timewalk | 47 | 184 | 0.8734 | 1.318 | 0 |
| support_matched | analytic_s03_timewalk | 48 | 345 | -0.2015 | 1.019 | 0 |
| support_matched | analytic_s03_timewalk | 49 | 352 | 0.4515 | 1.201 | 0 |
| support_matched | analytic_s03_timewalk | 50 | 286 | -0.005652 | 0.4176 | 0 |
| support_matched | analytic_s03_timewalk | 51 | 258 | 0.3464 | 1.094 | 0 |
| support_matched | analytic_s03_timewalk | 52 | 203 | -0.9095 | 1.16 | 0 |
| support_matched | analytic_s03_timewalk | 53 | 279 | 0.6111 | 1.391 | 0 |
| support_matched | analytic_s03_timewalk | 54 | 277 | 0.0782 | 1.131 | 0 |
| support_matched | analytic_s03_timewalk | 55 | 248 | 0.5162 | 0.2915 | 0 |
| support_matched | analytic_s03_timewalk | 56 | 296 | 0.09046 | 0.2617 | 0 |
| support_matched | analytic_s03_timewalk | 57 | 378 | -0.6606 | 0.9188 | 0 |
| support_matched | analytic_s03_timewalk | 64 | 432 | 0.4517 | 0.3146 | 0 |
| support_matched | gradient_boosted_trees | 44 | 197 | 6.305 | 2.151 | 0.7868 |
| support_matched | gradient_boosted_trees | 45 | 322 | 2.509 | 14.37 | 0.4503 |
| support_matched | gradient_boosted_trees | 46 | 91 | 9.101 | 0.9732 | 0.989 |
| support_matched | gradient_boosted_trees | 47 | 184 | 8.984 | 3.126 | 0.962 |
| support_matched | gradient_boosted_trees | 48 | 345 | 4.463 | 3.86 | 0.4232 |
| support_matched | gradient_boosted_trees | 49 | 352 | 5.846 | 1.613 | 0.679 |
| support_matched | gradient_boosted_trees | 50 | 286 | 1.954 | 19.56 | 0.6643 |
| support_matched | gradient_boosted_trees | 51 | 258 | -7.708 | 7.46 | 0.6395 |
| support_matched | gradient_boosted_trees | 52 | 203 | -7.987 | 9.194 | 0.9754 |
| support_matched | gradient_boosted_trees | 53 | 279 | 1.164 | 9.156 | 0.4014 |
| support_matched | gradient_boosted_trees | 54 | 277 | 1.897 | 12.03 | 0.3935 |
| support_matched | gradient_boosted_trees | 55 | 248 | -3.464 | 2.915 | 0.3871 |
| support_matched | gradient_boosted_trees | 56 | 296 | 3.133 | 10.04 | 0.6723 |
| support_matched | gradient_boosted_trees | 57 | 378 | 3.675 | 1.675 | 0.1852 |
| support_matched | gradient_boosted_trees | 64 | 432 | 1.315 | 1.037 | 0.03241 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 44 | 197 | 0.0765 | 10.05 | 0.6294 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 45 | 322 | -2.421 | 25.7 | 0.8106 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 46 | 91 | 1.064 | 4.624 | 0.3077 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 47 | 184 | -0.2377 | 8.8 | 0.5 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 48 | 345 | -1.732 | 18.31 | 0.7101 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 49 | 352 | -0.8329 | 19.87 | 0.696 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 50 | 286 | -3.533 | 24.33 | 0.7203 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 51 | 258 | -1.985 | 28.67 | 0.8101 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 52 | 203 | -1.092 | 24.96 | 0.7291 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 53 | 279 | -2.67 | 24.83 | 0.7384 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 54 | 277 | -5.476 | 24.72 | 0.7942 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 55 | 248 | -3.663 | 28.36 | 0.8629 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 56 | 296 | -2.468 | 29.01 | 0.7736 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 57 | 378 | -0.1461 | 22.21 | 0.7434 |
| support_matched | guardrail_orthogonal_edge_transformer_new | 64 | 432 | -0.1666 | 13.35 | 0.5718 |
| support_matched | mlp | 44 | 197 | 7.663 | 1.779 | 0.9645 |
| support_matched | mlp | 45 | 322 | -0.002832 | 14.62 | 0.441 |
| support_matched | mlp | 46 | 91 | 11.9 | 1.572 | 1 |
| support_matched | mlp | 47 | 184 | 9.553 | 3.426 | 0.8967 |
| support_matched | mlp | 48 | 345 | 5.994 | 5.596 | 0.5304 |
| support_matched | mlp | 49 | 352 | 4.743 | 3.24 | 0.4489 |
| support_matched | mlp | 50 | 286 | 0.06639 | 18.27 | 0.4371 |
| support_matched | mlp | 51 | 258 | -6.228 | 7.511 | 0.624 |
| support_matched | mlp | 52 | 203 | -6.213 | 9.455 | 0.8325 |
| support_matched | mlp | 53 | 279 | -2.186 | 8.057 | 0.405 |

## Guardrail and Systematic Strata

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| energy_bin | q1_low | analytic_s03_timewalk | 1658 | -0.1853 | 1.122 | 0 |
| energy_bin | q1_low | ridge | 1658 | 1.506 | 8.131 | 0.4916 |
| energy_bin | q1_low | mlp | 1658 | 0.9735 | 8.301 | 0.4777 |
| energy_bin | q1_low | gradient_boosted_trees | 1658 | 2.606 | 8.622 | 0.5012 |
| energy_bin | q1_low | 1d_cnn_waveform_only | 1658 | 5.586 | 22.55 | 0.6743 |
| energy_bin | q1_low | guardrail_orthogonal_edge_transformer_new | 1658 | -2.179 | 47.85 | 0.8311 |
| energy_bin | q2 | analytic_s03_timewalk | 1519 | 0.2982 | 0.82 | 0 |
| energy_bin | q2 | ridge | 1519 | 0.8553 | 8.037 | 0.4687 |
| energy_bin | q2 | mlp | 1519 | 0.4587 | 8.296 | 0.4556 |
| energy_bin | q2 | gradient_boosted_trees | 1519 | 2.461 | 8.535 | 0.4852 |
| energy_bin | q2 | 1d_cnn_waveform_only | 1519 | 5.537 | 15.77 | 0.6544 |
| energy_bin | q2 | guardrail_orthogonal_edge_transformer_new | 1519 | 1.045 | 38.5 | 0.7926 |
| energy_bin | q3 | analytic_s03_timewalk | 1548 | 0.2234 | 0.9921 | 0 |
| energy_bin | q3 | ridge | 1548 | 1.099 | 7.962 | 0.4922 |
| energy_bin | q3 | gradient_boosted_trees | 1548 | 2.503 | 8.319 | 0.5 |
| energy_bin | q3 | mlp | 1548 | 0.4433 | 8.829 | 0.4858 |
| energy_bin | q3 | 1d_cnn_waveform_only | 1548 | 3.149 | 17.5 | 0.657 |
| energy_bin | q3 | guardrail_orthogonal_edge_transformer_new | 1548 | 1.105 | 35.2 | 0.7481 |
| energy_bin | q4_high | analytic_s03_timewalk | 1903 | -1.196 | 1.188 | 0 |
| energy_bin | q4_high | gradient_boosted_trees | 1903 | 6.222 | 3.307 | 0.7714 |
| energy_bin | q4_high | ridge | 1903 | 7.442 | 5.278 | 0.8061 |
| energy_bin | q4_high | mlp | 1903 | 7.692 | 5.659 | 0.8119 |
| energy_bin | q4_high | 1d_cnn_waveform_only | 1903 | 5.67 | 6.499 | 0.7063 |
| energy_bin | q4_high | guardrail_orthogonal_edge_transformer_new | 1903 | 0.3661 | 6.753 | 0.4472 |
| late_tail_morphology | compact | analytic_s03_timewalk | 3786 | -0.1715 | 1.112 | 0 |
| late_tail_morphology | compact | gradient_boosted_trees | 3786 | 4.244 | 4.564 | 0.566 |
| late_tail_morphology | compact | ridge | 3786 | 3.312 | 6.254 | 0.5655 |
| late_tail_morphology | compact | mlp | 3786 | 3.364 | 6.402 | 0.5695 |
| late_tail_morphology | compact | 1d_cnn_waveform_only | 3786 | 3.676 | 7.52 | 0.594 |
| late_tail_morphology | compact | guardrail_orthogonal_edge_transformer_new | 3786 | -5.983 | 14.79 | 0.6054 |
| late_tail_morphology | diffuse_tail | analytic_s03_timewalk | 424 | 0.2853 | 0.9629 | 0 |
| late_tail_morphology | diffuse_tail | ridge | 424 | 1.002 | 7.869 | 0.4717 |
| late_tail_morphology | diffuse_tail | 1d_cnn_waveform_only | 424 | -3.898 | 8.3 | 0.5495 |
| late_tail_morphology | diffuse_tail | mlp | 424 | 0.285 | 8.394 | 0.4623 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 424 | 1.906 | 8.549 | 0.4434 |
| late_tail_morphology | diffuse_tail | guardrail_orthogonal_edge_transformer_new | 424 | 6.901 | 9.103 | 0.7075 |
| late_tail_morphology | late_derivative_bump | analytic_s03_timewalk | 639 | -1.216 | 1.101 | 0 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 639 | 6.501 | 3.162 | 0.7887 |
| late_tail_morphology | late_derivative_bump | ridge | 639 | 7.4 | 4.779 | 0.8044 |
| late_tail_morphology | late_derivative_bump | mlp | 639 | 8.02 | 5.191 | 0.7997 |
| late_tail_morphology | late_derivative_bump | 1d_cnn_waveform_only | 639 | 5.404 | 6.569 | 0.6839 |
| late_tail_morphology | late_derivative_bump | guardrail_orthogonal_edge_transformer_new | 639 | -3.14 | 10.19 | 0.4335 |
| late_tail_morphology | late_rising_tail | analytic_s03_timewalk | 1779 | 0.3143 | 0.9948 | 0 |
| late_tail_morphology | late_rising_tail | ridge | 1779 | 1.207 | 9.432 | 0.5441 |
| late_tail_morphology | late_rising_tail | mlp | 1779 | -0.004672 | 9.635 | 0.516 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1779 | 2.223 | 9.914 | 0.5481 |
| late_tail_morphology | late_rising_tail | guardrail_orthogonal_edge_transformer_new | 1779 | 54.64 | 33.35 | 0.968 |
| late_tail_morphology | late_rising_tail | 1d_cnn_waveform_only | 1779 | 27.46 | 37.25 | 0.8735 |
| pedestal_drift_bin | high | analytic_s03_timewalk | 2195 | 0.03002 | 1.151 | 0 |
| pedestal_drift_bin | high | gradient_boosted_trees | 2195 | 3.074 | 8.664 | 0.5727 |
| pedestal_drift_bin | high | ridge | 2195 | 2.355 | 8.746 | 0.585 |
| pedestal_drift_bin | high | mlp | 2195 | 2.091 | 9.096 | 0.5809 |
| pedestal_drift_bin | high | 1d_cnn_waveform_only | 2195 | 3.919 | 11.51 | 0.6569 |
| pedestal_drift_bin | high | guardrail_orthogonal_edge_transformer_new | 2195 | -6.617 | 33.2 | 0.7954 |
| pedestal_drift_bin | low | analytic_s03_timewalk | 2259 | -0.07935 | 1.105 | 0 |
| pedestal_drift_bin | low | gradient_boosted_trees | 2259 | 3.798 | 5.736 | 0.5719 |
| pedestal_drift_bin | low | ridge | 2259 | 2.839 | 6.662 | 0.5706 |
| pedestal_drift_bin | low | mlp | 2259 | 2.675 | 6.798 | 0.564 |
| pedestal_drift_bin | low | 1d_cnn_waveform_only | 2259 | 5.842 | 12.04 | 0.672 |
| pedestal_drift_bin | low | guardrail_orthogonal_edge_transformer_new | 2259 | 1.592 | 28.6 | 0.6348 |
| pedestal_drift_bin | mid | analytic_s03_timewalk | 2174 | -0.01561 | 1.1 | 0 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 2174 | 3.878 | 6.718 | 0.58 |
| pedestal_drift_bin | mid | ridge | 2174 | 2.785 | 7.38 | 0.575 |
| pedestal_drift_bin | mid | mlp | 2174 | 2.561 | 7.788 | 0.5667 |
| pedestal_drift_bin | mid | 1d_cnn_waveform_only | 2174 | 5.941 | 14.32 | 0.696 |
| pedestal_drift_bin | mid | guardrail_orthogonal_edge_transformer_new | 2174 | 2.409 | 29.88 | 0.649 |
| pulse_shape_class | compact | analytic_s03_timewalk | 2085 | 0.07809 | 1.091 | 0 |
| pulse_shape_class | compact | gradient_boosted_trees | 2085 | 3.268 | 6.254 | 0.529 |
| pulse_shape_class | compact | ridge | 2085 | 2.056 | 7.322 | 0.5189 |
| pulse_shape_class | compact | mlp | 2085 | 1.961 | 7.435 | 0.5199 |
| pulse_shape_class | compact | 1d_cnn_waveform_only | 2085 | 3.141 | 10.08 | 0.6173 |
| pulse_shape_class | compact | guardrail_orthogonal_edge_transformer_new | 2085 | -16.9 | 15.62 | 0.7894 |
| pulse_shape_class | late_tail | analytic_s03_timewalk | 2226 | 0.3026 | 0.9827 | 0 |
| pulse_shape_class | late_tail | ridge | 2226 | 1.182 | 9.203 | 0.5305 |
| pulse_shape_class | late_tail | mlp | 2226 | 0.1049 | 9.416 | 0.5063 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 2226 | 2.126 | 9.619 | 0.5265 |
| pulse_shape_class | late_tail | 1d_cnn_waveform_only | 2226 | 15.13 | 37.4 | 0.8077 |
| pulse_shape_class | late_tail | guardrail_orthogonal_edge_transformer_new | 2226 | 43.05 | 39.18 | 0.9151 |
| pulse_shape_class | nominal | analytic_s03_timewalk | 2317 | -1.025 | 1.177 | 0 |
| pulse_shape_class | nominal | gradient_boosted_trees | 2317 | 5.787 | 3.297 | 0.6625 |
| pulse_shape_class | nominal | ridge | 2317 | 6.676 | 5.701 | 0.6733 |
| pulse_shape_class | nominal | mlp | 2317 | 6.8 | 5.998 | 0.6776 |
| pulse_shape_class | nominal | guardrail_orthogonal_edge_transformer_new | 2317 | -1.017 | 6.02 | 0.3919 |
| pulse_shape_class | nominal | 1d_cnn_waveform_only | 2317 | 4.675 | 6.035 | 0.5991 |
| support_matched | False | analytic_s03_timewalk | 2480 | -0.9103 | 1.314 | 0 |
| support_matched | False | gradient_boosted_trees | 2480 | 5.159 | 7.487 | 0.6875 |
| support_matched | False | ridge | 2480 | 5.636 | 7.663 | 0.6988 |
| support_matched | False | mlp | 2480 | 5.369 | 8.356 | 0.6895 |
| support_matched | False | 1d_cnn_waveform_only | 2480 | 8.259 | 28.05 | 0.7923 |
| support_matched | False | guardrail_orthogonal_edge_transformer_new | 2480 | 2.518 | 47.24 | 0.6597 |
| support_matched | True | analytic_s03_timewalk | 4148 | 0.1778 | 1.037 | 0 |
| support_matched | True | gradient_boosted_trees | 4148 | 2.785 | 7.413 | 0.5075 |
| support_matched | True | ridge | 4148 | 1.774 | 7.633 | 0.5039 |
| support_matched | True | mlp | 4148 | 1.471 | 7.881 | 0.4993 |
| support_matched | True | 1d_cnn_waveform_only | 4148 | 2.742 | 9.7 | 0.6046 |
| support_matched | True | guardrail_orthogonal_edge_transformer_new | 4148 | -1.342 | 20.98 | 0.7124 |

## Amplitude/Tail Exclusion Check

The table below refits tabular learners after removing explicit amplitude,
late-tail, late-window waveform, and late-derivative features.  It tests whether
tree/MLP gains are driven by the exact support tails flagged in ticket `#2412`.

| variant | domain | method | n | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| primary_features | full_transfer | gradient_boosted_trees | 6628 | 7.421 | 3.69 | 9.978 | 0.5748 |
| amplitude_tail_excluded | full_transfer | gradient_boosted_trees_amplitude_tail_excluded | 6628 | 7.479 | 3.617 | 10.01 | 0.5771 |
| primary_features | full_transfer | mlp | 6628 | 8.134 | 5.65 | 10.51 | 0.5705 |
| amplitude_tail_excluded | full_transfer | mlp_amplitude_tail_excluded | 6628 | 7.919 | 5.731 | 10.54 | 0.5714 |
| primary_features | full_transfer | ridge | 6628 | 7.705 | 5.324 | 9.937 | 0.5768 |
| amplitude_tail_excluded | full_transfer | ridge_amplitude_tail_excluded | 6628 | 7.994 | 5.531 | 10.6 | 0.5813 |
| primary_features | support_matched | gradient_boosted_trees | 4148 | 7.413 | 3.439 | 9.94 | 0.5075 |
| amplitude_tail_excluded | support_matched | gradient_boosted_trees_amplitude_tail_excluded | 4148 | 7.41 | 3.473 | 9.775 | 0.513 |
| primary_features | support_matched | mlp | 4148 | 7.881 | 5.416 | 10.24 | 0.4993 |
| amplitude_tail_excluded | support_matched | mlp_amplitude_tail_excluded | 4148 | 7.73 | 5.51 | 10.17 | 0.4973 |
| primary_features | support_matched | ridge | 4148 | 7.633 | 5.315 | 10.25 | 0.5039 |
| amplitude_tail_excluded | support_matched | ridge_amplitude_tail_excluded | 4148 | 7.593 | 5.436 | 10.25 | 0.5019 |

## Interpretation and Caveats

The analysis supports adoption only if a learned model beats analytic S03 in the
support-matched domain and remains stable when amplitude/tail channels are
excluded.  It does not use run id, event id, duplicate readout, or stave one-hot
features.  The labels are waveform-derived CFD residuals, not external
picosecond truth.  The run-block bootstrap is intentionally conservative for
cross-sample transfer and can be wider than an event bootstrap.  The neural
models use a fixed small epoch budget; a larger architecture search could change
absolute rankings but would also increase leakage risk.

Runtime was `87.8 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.
