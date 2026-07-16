# S39a Constant-Fraction Timing Versus Learned Waveform Alignment

## Abstract

Ticket `1784176161.696.69ab6710` asks whether a strong traditional
constant-fraction/template method can match or explain learned waveform timing
alignment under pedestal wander and pulse-shape changes.  This study rebuilds
the registered B-stack selected-pulse count directly from raw ROOT files,
constructs a run-held-out timing residual benchmark from the same waveforms,
and compares a CFD/template/time-walk baseline with ridge, gradient-boosted
trees, MLP, 1D-CNN, a compact transformer, and a new gated edge-attention CNN.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_timewalk`** as the
winner: `sigma_68 = 0.8699 ns`
`[0.6191, 1.118]`.  The
traditional CFD/template reference obtains `0.8699 ns`
`[0.6191, 1.118]`.

## Raw ROOT Reproduction

Input files are read from `data/root/root`.  For each run, `h101/HRDv`
is reshaped into eight channels and `18` samples.
For each B-stack channel `c`, the pedestal and amplitude are

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

The reproduced raw number is

`N = sum_e sum_{c in B2,B4,B6,B8} 1[A_{e,c} > 1000 ADC]`.

The benchmark proceeds only after this ROOT-derived count matches the
registered anchor.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced count is **640737**.
Input hashes are stored in `input_sha256.csv`; first rows:

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

## Estimand and Equations

Constant-fraction time at fraction `f` is the pre-peak linear interpolation

`t_f = k - 1 + (f A - y_{k-1}) / (y_k - y_{k-1})`,

where `y_t = x_t - b`, `y_{k-1} < fA <= y_k`, and the crossing index `k`
cannot exceed the waveform peak.  The prediction target is a run/stave-centered
CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

For method `m`, `epsilon_i^m = y_i - hat y_i^m`.  The resolution estimator is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

with signed bias `median(epsilon)`.  The traditional comparator is

`hat y_trad = r_50 + g(log(1 + A)) + alpha + beta (t_0.50 - t_0.20)`,

where `r_50` is the run/stave-centered CFD50 residual and `g` is a
non-increasing isotonic time-walk correction fitted on training runs.

## Split, Uncertainty, and Leakage Controls

The split unit is the run.  Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`; all
other configured B-stack runs train the models.  The sampled benchmark rows are:

| split | rows |
| --- | --- |
| heldout | 5466 |
| train | 15137 |

Confidence intervals use `500` percentile
bootstrap replicates that resample held-out runs with replacement:

`CI_95(theta) = [q_0.025(theta_b^*), q_0.975(theta_b^*)]`.

No model receives run number, event number, or split indicator.  Pedestal
wander and pulse-shape changes enter only through waveform-derived quantities:
baseline displacement, pretrigger slope, normalized samples, tail fraction, late
prominence, and flat-top occupancy.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_cfd_template_timewalk | traditional | CFD50 residual plus monotone log-amplitude time-walk and CFD20/50 template-shape correction |
| ridge | linear ML | standardized ridge regression on pedestal, amplitude, CFD, tail, pile-up, saturation, and waveform samples |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled engineered feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform and detector-state summaries |
| 1d_cnn | neural waveform | compact convolutional regressor over the normalized 18-sample waveform window |
| waveform_transformer | new learned alignment | one-layer sample-attention encoder with position input and amplitude-weighted pooling |
| edge_attention_cnn_new | new learned alignment | gated edge-attention CNN that reweights leading-edge and late-curvature convolutional channels |

The compact transformer is included because sample attention can express
sub-window alignment without hand-specifying an onset index.  The
`edge_attention_cnn_new` architecture is the ticket-specific new model: a
gated convolutional encoder in which a waveform-derived gate emphasizes
leading-edge samples and suppresses nuisance late-curvature channels when they
do not help timing.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_timewalk | 5466 | 0.2909 | -0.1932 | 0.5032 | 0.8699 | 0.6191 | 1.118 | 0.871 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.3338 | -1.329 | 0.493 | 3.692 | 3.219 | 4.162 | 4.715 | 0.1969 | 0.04629 |
| ridge | 5466 | -0.1183 | -0.8573 | 0.8939 | 4.102 | 3.634 | 4.785 | 5.08 | 0.2298 | 0.05177 |
| mlp | 5466 | -0.9488 | -1.89 | -0.01152 | 4.275 | 3.982 | 4.577 | 4.935 | 0.2415 | 0.05123 |
| edge_attention_cnn_new | 5466 | 0.9217 | 0.2759 | 1.624 | 5.258 | 4.62 | 6.077 | 6.576 | 0.3555 | 0.1116 |
| waveform_transformer | 5466 | 1.968 | 0.9464 | 2.73 | 6.343 | 5.925 | 7.106 | 7.192 | 0.4671 | 0.1405 |
| 1d_cnn | 5466 | -0.1329 | -1.232 | 0.8995 | 6.482 | 5.858 | 7.399 | 7.431 | 0.4254 | 0.1508 |

## Paired Deltas Against CFD/Template

Positive `delta_sigma68_ns` means the learned method is wider than the
traditional CFD/template reference under matched held-out run-block bootstrap.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_timewalk | 2.822 | 2.27 | 3.372 | -0.6247 | -1.67 | 0.2628 | 0.1969 |
| ridge | traditional_cfd_template_timewalk | 3.232 | 2.697 | 3.987 | -0.4092 | -1.181 | 0.6026 | 0.2298 |
| mlp | traditional_cfd_template_timewalk | 3.405 | 3.043 | 3.812 | -1.24 | -2.229 | -0.245 | 0.2415 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk | 4.388 | 3.74 | 5.281 | 0.6307 | -0.1114 | 1.476 | 0.3555 |
| waveform_transformer | traditional_cfd_template_timewalk | 5.474 | 4.943 | 6.331 | 1.677 | 0.5761 | 2.519 | 0.4671 |
| 1d_cnn | traditional_cfd_template_timewalk | 5.612 | 4.978 | 6.572 | -0.4238 | -1.504 | 0.8207 | 0.4254 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_timewalk | 1350 | -0.3036 | 0.7679 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.7306 | 3.584 | 0.2926 |
| sample_i_analysis | mlp | 1350 | -0.0004738 | 4.013 | 0.2919 |
| sample_i_analysis | ridge | 1350 | 1.044 | 5.129 | 0.3333 |
| sample_i_analysis | edge_attention_cnn_new | 1350 | 1.172 | 6.909 | 0.4526 |
| sample_i_analysis | waveform_transformer | 1350 | 1.497 | 7.285 | 0.477 |
| sample_i_analysis | 1d_cnn | 1350 | 0.7225 | 8.142 | 0.4993 |
| sample_i_calib | traditional_cfd_template_timewalk | 657 | 0.5385 | 1.368 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.785 | 3.153 | 0.1994 |
| sample_i_calib | mlp | 657 | 1.137 | 4.087 | 0.2755 |
| sample_i_calib | ridge | 657 | 2.162 | 4.643 | 0.3303 |
| sample_i_calib | edge_attention_cnn_new | 657 | 2.568 | 6.156 | 0.4673 |
| sample_i_calib | waveform_transformer | 657 | 2.905 | 6.243 | 0.4429 |
| sample_i_calib | 1d_cnn | 657 | 2.296 | 7.235 | 0.4947 |
| sample_ii_analysis | traditional_cfd_template_timewalk | 2739 | 0.4037 | 0.6477 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.38 | 3.478 | 0.1818 |
| sample_ii_analysis | ridge | 2739 | -0.8595 | 3.703 | 0.1756 |
| sample_ii_analysis | mlp | 2739 | -2.026 | 4.1 | 0.2326 |
| sample_ii_analysis | edge_attention_cnn_new | 2739 | 0.5452 | 4.635 | 0.2877 |
| sample_ii_analysis | 1d_cnn | 2739 | -0.8837 | 5.842 | 0.3826 |
| sample_ii_analysis | waveform_transformer | 2739 | 1.694 | 6.452 | 0.4702 |
| sample_ii_calib | traditional_cfd_template_timewalk | 720 | 0.5936 | 0.465 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -0.6029 | 2.99 | 0.07222 |
| sample_ii_calib | ridge | 720 | -0.3361 | 3.701 | 0.15 |
| sample_ii_calib | mlp | 720 | -1.294 | 4.081 | 0.15 |
| sample_ii_calib | edge_attention_cnn_new | 720 | 1.033 | 4.463 | 0.3292 |
| sample_ii_calib | 1d_cnn | 720 | -0.1028 | 5.679 | 0.3861 |
| sample_ii_calib | waveform_transformer | 720 | 2.687 | 5.99 | 0.4583 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 2.296 | 7.235 | 0.4947 |
| 1d_cnn | 50 | 680 | -1.933 | 9.762 | 0.5029 |
| 1d_cnn | 57 | 670 | 2.478 | 7.363 | 0.4955 |
| 1d_cnn | 58 | 654 | -2.308 | 6.148 | 0.4327 |
| 1d_cnn | 60 | 720 | 0.5219 | 5.965 | 0.4042 |
| 1d_cnn | 62 | 720 | -0.3921 | 5.384 | 0.3528 |
| 1d_cnn | 64 | 720 | -0.1028 | 5.679 | 0.3861 |
| 1d_cnn | 65 | 645 | -1.226 | 5.237 | 0.3411 |
| edge_attention_cnn_new | 42 | 657 | 2.568 | 6.156 | 0.4673 |
| edge_attention_cnn_new | 50 | 680 | -0.5499 | 9.737 | 0.4382 |
| edge_attention_cnn_new | 57 | 670 | 3.029 | 5.93 | 0.4672 |
| edge_attention_cnn_new | 58 | 654 | -1.313 | 5.253 | 0.3303 |
| edge_attention_cnn_new | 60 | 720 | 1.314 | 4.337 | 0.3194 |
| edge_attention_cnn_new | 62 | 720 | 0.8323 | 4.276 | 0.2694 |
| edge_attention_cnn_new | 64 | 720 | 1.033 | 4.463 | 0.3292 |
| edge_attention_cnn_new | 65 | 645 | 0.5412 | 4.152 | 0.2295 |
| gradient_boosted_trees | 42 | 657 | 1.785 | 3.153 | 0.1994 |
| gradient_boosted_trees | 50 | 680 | 0.7717 | 8.989 | 0.3118 |
| gradient_boosted_trees | 57 | 670 | 0.6476 | 4.204 | 0.2731 |
| gradient_boosted_trees | 58 | 654 | -2.944 | 2.925 | 0.2492 |
| gradient_boosted_trees | 60 | 720 | -0.6146 | 3.658 | 0.1389 |
| gradient_boosted_trees | 62 | 720 | -0.9433 | 3.028 | 0.1056 |
| gradient_boosted_trees | 64 | 720 | -0.6029 | 2.99 | 0.07222 |
| gradient_boosted_trees | 65 | 645 | -1.416 | 3.674 | 0.2465 |
| mlp | 42 | 657 | 1.137 | 4.087 | 0.2755 |
| mlp | 50 | 680 | -0.1015 | 8.486 | 0.3015 |
| mlp | 57 | 670 | 0.2943 | 5.3 | 0.2821 |
| mlp | 58 | 654 | -3.214 | 4.196 | 0.2905 |
| mlp | 60 | 720 | -1.467 | 4.417 | 0.2333 |
| mlp | 62 | 720 | -1.598 | 3.649 | 0.15 |
| mlp | 64 | 720 | -1.294 | 4.081 | 0.15 |
| mlp | 65 | 645 | -2.283 | 4.239 | 0.2651 |
| ridge | 42 | 657 | 2.162 | 4.643 | 0.3303 |
| ridge | 50 | 680 | -0.3321 | 9.371 | 0.3588 |
| ridge | 57 | 670 | 2.14 | 4.906 | 0.3075 |
| ridge | 58 | 654 | -1.882 | 4.444 | 0.292 |
| ridge | 60 | 720 | -0.6928 | 3.588 | 0.1444 |
| ridge | 62 | 720 | -0.7173 | 3.293 | 0.1347 |
| ridge | 64 | 720 | -0.3361 | 3.701 | 0.15 |
| ridge | 65 | 645 | -0.5341 | 3.217 | 0.138 |
| traditional_cfd_template_timewalk | 42 | 657 | 0.5385 | 1.368 | 0 |
| traditional_cfd_template_timewalk | 50 | 680 | -0.2775 | 0.6236 | 0 |
| traditional_cfd_template_timewalk | 57 | 670 | -0.7399 | 1.02 | 0 |
| traditional_cfd_template_timewalk | 58 | 654 | 0.7185 | 0.831 | 0 |
| traditional_cfd_template_timewalk | 60 | 720 | 0.3274 | 0.7469 | 0 |
| traditional_cfd_template_timewalk | 62 | 720 | 0.3343 | 0.5461 | 0 |
| traditional_cfd_template_timewalk | 64 | 720 | 0.5936 | 0.465 | 0 |
| traditional_cfd_template_timewalk | 65 | 645 | 0.391 | 0.6273 | 0 |
| waveform_transformer | 42 | 657 | 2.905 | 6.243 | 0.4429 |
| waveform_transformer | 50 | 680 | 0.2297 | 10.14 | 0.4618 |
| waveform_transformer | 57 | 670 | 3.467 | 6.14 | 0.4925 |
| waveform_transformer | 58 | 654 | -0.1204 | 7.016 | 0.448 |
| waveform_transformer | 60 | 720 | 2.141 | 6.521 | 0.4736 |
| waveform_transformer | 62 | 720 | 2.255 | 6.451 | 0.4931 |
| waveform_transformer | 64 | 720 | 2.687 | 5.99 | 0.4583 |
| waveform_transformer | 65 | 645 | 2.528 | 5.424 | 0.4636 |

## Pedestal and Pulse-Shape Stress Tables

Stress axes are raw-waveform proxies: pedestal drift is absolute baseline
displacement from the run/stave median; pulse-shape class is late-tail fraction;
pile-up proximity is late secondary prominence spacing; saturation onset is
high amplitude or flat-top occupancy; energy proxy is amplitude quartile; PID
sideband is duplicate-readout amplitude ratio.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| energy_bin | q1_low | 1d_cnn | 1398 | -2.55 | 6.617 | 0.48 |
| energy_bin | q1_low | edge_attention_cnn_new | 1398 | 0.3245 | 6.023 | 0.4041 |
| energy_bin | q1_low | gradient_boosted_trees | 1398 | -0.5496 | 3.617 | 0.186 |
| energy_bin | q1_low | mlp | 1398 | -0.8358 | 3.873 | 0.2046 |
| energy_bin | q1_low | ridge | 1398 | 1.034 | 3.935 | 0.2203 |
| energy_bin | q1_low | traditional_cfd_template_timewalk | 1398 | -0.1124 | 0.9557 | 0 |
| energy_bin | q1_low | waveform_transformer | 1398 | 2.859 | 5.991 | 0.4771 |
| energy_bin | q2 | 1d_cnn | 1510 | -0.6228 | 4.974 | 0.3179 |
| energy_bin | q2 | edge_attention_cnn_new | 1510 | 1.128 | 4.727 | 0.3205 |
| energy_bin | q2 | gradient_boosted_trees | 1510 | -0.3137 | 3.46 | 0.1815 |
| energy_bin | q2 | mlp | 1510 | -1.109 | 4.266 | 0.2338 |
| energy_bin | q2 | ridge | 1510 | 0.1854 | 4.023 | 0.2258 |
| energy_bin | q2 | traditional_cfd_template_timewalk | 1510 | 0.3824 | 0.6964 | 0 |
| energy_bin | q2 | waveform_transformer | 1510 | 3.915 | 5.772 | 0.5245 |
| energy_bin | q3 | 1d_cnn | 1458 | 3.099 | 4.636 | 0.4218 |
| energy_bin | q3 | edge_attention_cnn_new | 1458 | 2.01 | 4.589 | 0.345 |
| energy_bin | q3 | gradient_boosted_trees | 1458 | -0.1057 | 3.784 | 0.2119 |
| energy_bin | q3 | mlp | 1458 | -0.8852 | 4.558 | 0.2641 |
| energy_bin | q3 | ridge | 1458 | -0.5234 | 4.082 | 0.2202 |
| energy_bin | q3 | traditional_cfd_template_timewalk | 1458 | 0.4346 | 0.7125 | 0 |
| energy_bin | q3 | waveform_transformer | 1458 | 2.46 | 5.864 | 0.4547 |
| energy_bin | q4_high | 1d_cnn | 1100 | -2.259 | 7.072 | 0.5082 |
| energy_bin | q4_high | edge_attention_cnn_new | 1100 | -0.5832 | 5.433 | 0.3555 |
| energy_bin | q4_high | gradient_boosted_trees | 1100 | -0.4886 | 3.483 | 0.2118 |
| energy_bin | q4_high | mlp | 1100 | -1.017 | 4.043 | 0.2691 |
| energy_bin | q4_high | ridge | 1100 | -1.105 | 4.12 | 0.26 |
| energy_bin | q4_high | traditional_cfd_template_timewalk | 1100 | 0.226 | 0.9922 | 0 |
| energy_bin | q4_high | waveform_transformer | 1100 | -2.339 | 5.707 | 0.3918 |
| pedestal_drift_bin | high | 1d_cnn | 1763 | 0.02514 | 7.758 | 0.5003 |
| pedestal_drift_bin | high | edge_attention_cnn_new | 1763 | 1.423 | 6.806 | 0.468 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1763 | -0.1852 | 3.966 | 0.2189 |
| pedestal_drift_bin | high | mlp | 1763 | -0.1871 | 4.24 | 0.2484 |
| pedestal_drift_bin | high | ridge | 1763 | 0.1162 | 4.347 | 0.2564 |
| pedestal_drift_bin | high | traditional_cfd_template_timewalk | 1763 | 0.278 | 0.9027 | 0 |
| pedestal_drift_bin | high | waveform_transformer | 1763 | -0.164 | 7.007 | 0.4912 |
| pedestal_drift_bin | low | 1d_cnn | 1748 | -0.1951 | 6.145 | 0.405 |
| pedestal_drift_bin | low | edge_attention_cnn_new | 1748 | 0.7254 | 4.798 | 0.3238 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1748 | -0.4694 | 3.478 | 0.1808 |
| pedestal_drift_bin | low | mlp | 1748 | -1.242 | 4.103 | 0.2311 |
| pedestal_drift_bin | low | ridge | 1748 | -0.07267 | 4.267 | 0.238 |
| pedestal_drift_bin | low | traditional_cfd_template_timewalk | 1748 | 0.2708 | 0.9078 | 0 |
| pedestal_drift_bin | low | waveform_transformer | 1748 | 2.69 | 5.788 | 0.4737 |
| pedestal_drift_bin | mid | 1d_cnn | 1955 | -0.2763 | 5.795 | 0.376 |
| pedestal_drift_bin | mid | edge_attention_cnn_new | 1955 | 0.809 | 4.485 | 0.2824 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1955 | -0.3424 | 3.568 | 0.1913 |
| pedestal_drift_bin | mid | mlp | 1955 | -1.331 | 4.201 | 0.2445 |
| pedestal_drift_bin | mid | ridge | 1955 | -0.2424 | 3.813 | 0.1985 |
| pedestal_drift_bin | mid | traditional_cfd_template_timewalk | 1955 | 0.3279 | 0.8338 | 0 |
| pedestal_drift_bin | mid | waveform_transformer | 1955 | 2.626 | 5.593 | 0.4394 |
| pid_sideband | central | 1d_cnn | 3760 | -0.01353 | 5.849 | 0.3793 |
| pid_sideband | central | edge_attention_cnn_new | 3760 | 0.968 | 4.669 | 0.3101 |
| pid_sideband | central | gradient_boosted_trees | 3760 | -0.2649 | 3.6 | 0.1989 |
| pid_sideband | central | mlp | 3760 | -0.9874 | 4.184 | 0.237 |
| pid_sideband | central | ridge | 3760 | 0.1073 | 4.125 | 0.2324 |
| pid_sideband | central | traditional_cfd_template_timewalk | 3760 | 0.2766 | 0.892 | 0 |
| pid_sideband | central | waveform_transformer | 3760 | 2.964 | 5.67 | 0.4673 |
| pid_sideband | high_duplicate | 1d_cnn | 878 | -0.8892 | 9.211 | 0.6207 |
| pid_sideband | high_duplicate | edge_attention_cnn_new | 878 | 1.681 | 8.67 | 0.6185 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 878 | -0.8915 | 3.795 | 0.1982 |
| pid_sideband | high_duplicate | mlp | 878 | -0.4904 | 4.292 | 0.2346 |
| pid_sideband | high_duplicate | ridge | 878 | -0.746 | 4.434 | 0.2608 |
| pid_sideband | high_duplicate | traditional_cfd_template_timewalk | 878 | 0.2739 | 0.9337 | 0 |
| pid_sideband | high_duplicate | waveform_transformer | 878 | -3.244 | 6.218 | 0.4954 |
| pid_sideband | low_duplicate | 1d_cnn | 828 | -0.3143 | 6.341 | 0.4275 |
| pid_sideband | low_duplicate | edge_attention_cnn_new | 828 | 0.32 | 4.502 | 0.2826 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 828 | -0.2589 | 3.548 | 0.186 |
| pid_sideband | low_duplicate | mlp | 828 | -1.276 | 4.519 | 0.2693 |
| pid_sideband | low_duplicate | ridge | 828 | -0.4984 | 3.541 | 0.1848 |
| pid_sideband | low_duplicate | traditional_cfd_template_timewalk | 828 | 0.3812 | 0.8352 | 0 |
| pid_sideband | low_duplicate | waveform_transformer | 828 | 1.978 | 5.797 | 0.436 |
| pileup_separation_bin | close | 1d_cnn | 1681 | -1.315 | 6.598 | 0.4474 |
| pileup_separation_bin | close | edge_attention_cnn_new | 1681 | -0.6369 | 5.045 | 0.3195 |
| pileup_separation_bin | close | gradient_boosted_trees | 1681 | -0.6714 | 3.335 | 0.1701 |
| pileup_separation_bin | close | mlp | 1681 | -1.647 | 4.166 | 0.2385 |
| pileup_separation_bin | close | ridge | 1681 | -0.9662 | 3.885 | 0.2195 |
| pileup_separation_bin | close | traditional_cfd_template_timewalk | 1681 | 0.2996 | 0.8798 | 0 |
| pileup_separation_bin | close | waveform_transformer | 1681 | 1.188 | 5.962 | 0.4164 |
| pileup_separation_bin | late | 1d_cnn | 1 | -11.91 | 0 | 1 |
| pileup_separation_bin | late | edge_attention_cnn_new | 1 | -6.661 | 0 | 1 |
| pileup_separation_bin | late | gradient_boosted_trees | 1 | 1.006 | 0 | 0 |
| pileup_separation_bin | late | mlp | 1 | -4.918 | 0 | 0 |
| pileup_separation_bin | late | ridge | 1 | 3.367 | 0 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_timewalk | 1 | -0.8333 | 0 | 0 |
| pileup_separation_bin | late | waveform_transformer | 1 | -2.409 | 0 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1169 | 2.542 | 6.436 | 0.4987 |
| pileup_separation_bin | mid | edge_attention_cnn_new | 1169 | 2.438 | 5.772 | 0.4423 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1169 | -0.8661 | 3.564 | 0.1651 |
| pileup_separation_bin | mid | mlp | 1169 | -1.342 | 3.934 | 0.2216 |
| pileup_separation_bin | mid | ridge | 1169 | -0.7896 | 3.988 | 0.2113 |
| pileup_separation_bin | mid | traditional_cfd_template_timewalk | 1169 | 0.3874 | 0.8748 | 0 |
| pileup_separation_bin | mid | waveform_transformer | 1169 | -1.476 | 6.396 | 0.4542 |
| pileup_separation_bin | none | 1d_cnn | 2615 | -0.4821 | 5.861 | 0.3782 |
| pileup_separation_bin | none | edge_attention_cnn_new | 2615 | 1.273 | 4.789 | 0.3396 |
| pileup_separation_bin | none | gradient_boosted_trees | 2615 | 0.114 | 3.831 | 0.2283 |
| pileup_separation_bin | none | mlp | 2615 | -0.5328 | 4.211 | 0.2524 |
| pileup_separation_bin | none | ridge | 2615 | 0.6963 | 3.873 | 0.2447 |
| pileup_separation_bin | none | traditional_cfd_template_timewalk | 2615 | 0.2432 | 0.8326 | 0 |
| pileup_separation_bin | none | waveform_transformer | 2615 | 3.693 | 5.645 | 0.5055 |
| pulse_shape_class | compact | 1d_cnn | 1883 | -1.434 | 7.374 | 0.4981 |
| pulse_shape_class | compact | edge_attention_cnn_new | 1883 | 0.5555 | 6.584 | 0.4493 |
| pulse_shape_class | compact | gradient_boosted_trees | 1883 | -1.104 | 3.679 | 0.1896 |
| pulse_shape_class | compact | mlp | 1883 | -1.569 | 4.176 | 0.2284 |
| pulse_shape_class | compact | ridge | 1883 | -0.2499 | 4.352 | 0.2459 |
| pulse_shape_class | compact | traditional_cfd_template_timewalk | 1883 | 0.2721 | 0.9142 | 0 |
| pulse_shape_class | compact | waveform_transformer | 1883 | 0.9873 | 6.688 | 0.4833 |
| pulse_shape_class | late_tail | 1d_cnn | 1824 | 0.9927 | 6.188 | 0.3914 |
| pulse_shape_class | late_tail | edge_attention_cnn_new | 1824 | 1.156 | 5.111 | 0.3487 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1824 | 0.5877 | 4.125 | 0.2664 |
| pulse_shape_class | late_tail | mlp | 1824 | -0.3584 | 4.621 | 0.2922 |
| pulse_shape_class | late_tail | ridge | 1824 | 0.2979 | 4.322 | 0.2741 |
| pulse_shape_class | late_tail | traditional_cfd_template_timewalk | 1824 | 0.3194 | 0.7655 | 0 |
| pulse_shape_class | late_tail | waveform_transformer | 1824 | 1.588 | 6.188 | 0.443 |
| pulse_shape_class | nominal | 1d_cnn | 1759 | -0.07886 | 5.728 | 0.3826 |
| pulse_shape_class | nominal | edge_attention_cnn_new | 1759 | 0.8851 | 4.105 | 0.2621 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1759 | -0.4827 | 3.116 | 0.1325 |
| pulse_shape_class | nominal | mlp | 1759 | -1.24 | 3.784 | 0.203 |
| pulse_shape_class | nominal | ridge | 1759 | -0.4413 | 3.524 | 0.1666 |
| pulse_shape_class | nominal | traditional_cfd_template_timewalk | 1759 | 0.2839 | 0.8787 | 0 |
| pulse_shape_class | nominal | waveform_transformer | 1759 | 3.135 | 5.699 | 0.4747 |
| saturation_onset_bin | linear | 1d_cnn | 3978 | 0.09251 | 6.643 | 0.4324 |
| saturation_onset_bin | linear | edge_attention_cnn_new | 3978 | 1.127 | 5.56 | 0.3796 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3978 | -0.39 | 3.759 | 0.2006 |
| saturation_onset_bin | linear | mlp | 3978 | -0.986 | 4.344 | 0.2491 |
| saturation_onset_bin | linear | ridge | 3978 | -0.1748 | 4.204 | 0.2396 |
| saturation_onset_bin | linear | traditional_cfd_template_timewalk | 3978 | 0.311 | 0.8321 | 0 |
| saturation_onset_bin | linear | waveform_transformer | 3978 | 1.825 | 6.57 | 0.4683 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1488 | -0.6797 | 6.012 | 0.4066 |
| saturation_onset_bin | near_saturation | edge_attention_cnn_new | 1488 | 0.3918 | 4.638 | 0.291 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1488 | -0.197 | 3.462 | 0.1868 |
| saturation_onset_bin | near_saturation | mlp | 1488 | -0.8595 | 4.038 | 0.2211 |
| saturation_onset_bin | near_saturation | ridge | 1488 | 0.0628 | 3.901 | 0.2036 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_timewalk | 1488 | 0.2487 | 0.9123 | 0 |
| saturation_onset_bin | near_saturation | waveform_transformer | 1488 | 2.246 | 5.86 | 0.4637 |

Axis-compressed view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| energy_bin | 1d_cnn | 4 | q3 | 4.636 | q4_high | 7.072 | 2.437 |
| energy_bin | edge_attention_cnn_new | 4 | q3 | 4.589 | q1_low | 6.023 | 1.434 |
| energy_bin | mlp | 4 | q1_low | 3.873 | q3 | 4.558 | 0.6852 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.46 | q3 | 3.784 | 0.324 |
| energy_bin | traditional_cfd_template_timewalk | 4 | q2 | 0.6964 | q4_high | 0.9922 | 0.2958 |
| energy_bin | waveform_transformer | 4 | q4_high | 5.707 | q1_low | 5.991 | 0.2845 |
| energy_bin | ridge | 4 | q1_low | 3.935 | q4_high | 4.12 | 0.1846 |
| pedestal_drift_bin | edge_attention_cnn_new | 3 | mid | 4.485 | high | 6.806 | 2.321 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.795 | high | 7.758 | 1.963 |
| pedestal_drift_bin | waveform_transformer | 3 | mid | 5.593 | high | 7.007 | 1.414 |
| pedestal_drift_bin | ridge | 3 | mid | 3.813 | high | 4.347 | 0.5335 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.478 | high | 3.966 | 0.4881 |
| pedestal_drift_bin | mlp | 3 | low | 4.103 | high | 4.24 | 0.1363 |
| pedestal_drift_bin | traditional_cfd_template_timewalk | 3 | mid | 0.8338 | low | 0.9078 | 0.07403 |
| pid_sideband | edge_attention_cnn_new | 3 | low_duplicate | 4.502 | high_duplicate | 8.67 | 4.168 |
| pid_sideband | 1d_cnn | 3 | central | 5.849 | high_duplicate | 9.211 | 3.363 |
| pid_sideband | ridge | 3 | low_duplicate | 3.541 | high_duplicate | 4.434 | 0.893 |
| pid_sideband | waveform_transformer | 3 | central | 5.67 | high_duplicate | 6.218 | 0.5475 |
| pid_sideband | mlp | 3 | central | 4.184 | low_duplicate | 4.519 | 0.3356 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.548 | high_duplicate | 3.795 | 0.2468 |
| pid_sideband | traditional_cfd_template_timewalk | 3 | low_duplicate | 0.8352 | high_duplicate | 0.9337 | 0.09849 |
| pileup_separation_bin | 1d_cnn | 4 | late | 0 | close | 6.598 | 6.598 |
| pileup_separation_bin | waveform_transformer | 4 | late | 0 | mid | 6.396 | 6.396 |
| pileup_separation_bin | edge_attention_cnn_new | 4 | late | 0 | mid | 5.772 | 5.772 |
| pileup_separation_bin | mlp | 4 | late | 0 | none | 4.211 | 4.211 |
| pileup_separation_bin | ridge | 4 | late | 0 | mid | 3.988 | 3.988 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 0 | none | 3.831 | 3.831 |
| pileup_separation_bin | traditional_cfd_template_timewalk | 4 | late | 0 | close | 0.8798 | 0.8798 |
| pulse_shape_class | edge_attention_cnn_new | 3 | nominal | 4.105 | compact | 6.584 | 2.479 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 5.728 | compact | 7.374 | 1.646 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.116 | late_tail | 4.125 | 1.009 |
| pulse_shape_class | waveform_transformer | 3 | nominal | 5.699 | compact | 6.688 | 0.9885 |
| pulse_shape_class | mlp | 3 | nominal | 3.784 | late_tail | 4.621 | 0.8376 |
| pulse_shape_class | ridge | 3 | nominal | 3.524 | compact | 4.352 | 0.8282 |
| pulse_shape_class | traditional_cfd_template_timewalk | 3 | late_tail | 0.7655 | compact | 0.9142 | 0.1487 |
| saturation_onset_bin | edge_attention_cnn_new | 2 | near_saturation | 4.638 | linear | 5.56 | 0.9228 |
| saturation_onset_bin | waveform_transformer | 2 | near_saturation | 5.86 | linear | 6.57 | 0.7108 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 6.012 | linear | 6.643 | 0.6305 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.038 | linear | 4.344 | 0.3056 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.901 | linear | 4.204 | 0.3025 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.462 | linear | 3.759 | 0.2974 |
| saturation_onset_bin | traditional_cfd_template_timewalk | 2 | linear | 0.8321 | near_saturation | 0.9123 | 0.08019 |

## Systematic Ablations

The ablations use the gradient-boosted-tree learner and remove feature families
to test whether learned timing is mostly amplitude/CFD interpolation, pedestal
state, or late pulse-shape information.

| ablation | n_features | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| full_gradient_boosted_trees | 33 | 3.676 | 3.289 | 4.112 | 0 | 0.2033 |
| drop_tail_pulse_shape_features | 24 | 3.681 | 3.269 | 4.238 | 0.004731 | 0.2027 |
| drop_pretrigger_features | 27 | 3.913 | 3.469 | 4.647 | 0.2374 | 0.2133 |
| amplitude_cfd_only | 5 | 4.001 | 3.571 | 4.622 | 0.3254 | 0.2265 |

## Interpretation, Systematics, and Caveats

This is a comparative alignment benchmark, not an external timing-truth
measurement.  The ROOT tree provides digitized waveforms but not independent
particle truth, electronics-state labels, or picosecond reference timing.
Therefore, the analysis supports claims about relative method behavior on a
reproducible waveform-derived residual, not absolute beamline timing.

The run-block bootstrap targets transfer across data-taking periods and can be
wider than event-level uncertainty.  Small strata, especially close pile-up and
near-saturation levels, must be interpreted with their row counts.  Neural
models are compact and trained on a fixed small epoch budget; this tests whether
learned waveform alignment naturally beats a strong CFD/template construction,
not whether exhaustive neural architecture search can eventually overfit this
proxy target.

Runtime was `40.7 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.
