# S35a Raw Pulse-Onset Pedestal Timing Frontier

## Abstract

Ticket `1784063447.849.4ac02d58` requested a raw-ROOT reproduction followed by a
run-split benchmark of a strong traditional timing method against ridge,
gradient-boosted trees, MLP, 1D-CNN, compact transformer encoders, and a new
architecture when sensible.  This study rebuilds the B-stack pulse table
directly from `h101/HRDv`, verifies the registered selected-pulse count, and
evaluates timing bias and resolution under pulse-shape, pedestal-memory,
pile-up-proximity, saturation-onset, energy-proxy, and PID-sideband strata.

The primary registered criterion is held-out run-block `sigma_68` of onset
residual error.  The winner written to `result.json` is **`traditional_cfd_template_timewalk`** with
`sigma_68 = 0.817 ns`
`[0.5772, 1.042]`.  The
traditional reference obtains `0.817 ns`
`[0.5772, 1.042]`.

## Raw ROOT Reproduction Gate

Input ROOT files are read from `data/root/root`.  For each run the
branch `h101/HRDv` is reshaped into eight channels and eighteen ADC samples.  A
per-channel pedestal is estimated from pretrigger samples

`b_{e,c} = median(x_{e,c,0}, x_{e,c,1}, x_{e,c,2}, x_{e,c,3})`,

and the pulse amplitude is

`A_{e,c} = max_t [x_{e,c,t} - b_{e,c}]`.

The raw reproduction number is

`N = sum_e sum_{c in B2,B4,B6,B8} 1[A_{e,c} > 1000 ADC]`.

The analysis proceeds only if every count below matches the registered ROOT
anchor exactly.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The reproduced all-group number is **640737**.
Raw input hashes are stored in `input_sha256.csv`; the first rows are:

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

For a selected waveform, a constant-fraction crossing at fraction `f` is found
by linear interpolation before the peak:

`t_f = k - 1 + (f A - y_{k-1}) / (y_k - y_{k-1})`,

where `y_t = x_t - b`, `y_{k-1} < fA <= y_k`, and `k` is constrained not to
exceed the peak sample.  The target is a run/stave-centered CFD20 residual

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

Models predict `hat y_i`; the residual error is `epsilon_i = y_i - hat y_i`.
The main resolution estimator is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

and the signed bias is `median(epsilon)`.

## Split and Uncertainty

The split is by run, never by shuffled event.  Held-out runs are
`[42, 50, 57, 58, 60, 62, 64, 65]`; all other configured B-stack runs are training
runs.  The sampled benchmark contains:

| split | rows |
| --- | --- |
| heldout | 5466 |
| train | 15137 |

Confidence intervals use `500` percentile
bootstrap replicates that resample held-out runs with replacement.  For a
metric `theta`,

`CI_95(theta) = [q_0.025(theta^*_b), q_0.975(theta^*_b)]`.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_cfd_template_timewalk | traditional | CFD50 residual with constrained monotone log-amplitude time-walk and template-shape correction |
| ridge | linear ML | standardized ridge regression on scalar pulse atoms plus normalized waveform samples |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled feature matrix |
| mlp | neural tabular | two-layer MLP over engineered onset, pedestal, shape, saturation, energy, and duplicate-readout features |
| 1d_cnn | neural waveform | compact 1D convolutional encoder over the 18-sample normalized waveform |
| waveform_transformer | compact transformer encoder | one-layer self-attention waveform encoder with sample-position embedding and amplitude-weighted pooling |
| edge_attention_cnn_new | new architecture | gated edge-attention CNN that learns leading-edge and late-curvature channel weights |

The traditional comparator is deliberately strong: it starts with the CFD50
residual, fits a non-increasing isotonic correction in `log(1+A)` on training
runs, and adds a linear template proxy from `(t_0.50 - t_0.20)`.

`hat y_trad = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`.

The new `edge_attention_cnn_new` is sensible here because onset timing is a
localized leading-edge problem, while late curvature and flat-top samples are
nuisance indicators for pile-up and saturation.  The architecture learns a gate
from the raw normalized waveform and multiplies the convolutional feature maps
before the timing head.  No model receives run number or event number.

## Primary Method Table

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_timewalk | 5466 | 0.5923 | 0.3005 | 0.7917 | 0.817 | 0.5772 | 1.042 | 0.8587 | 0 |
| gradient_boosted_trees | 5466 | -0.2546 | -1.195 | 0.613 | 3.727 | 3.291 | 4.408 | 5.287 | 0.2076 |
| ridge | 5466 | 0.4374 | -0.2193 | 1.251 | 4.272 | 3.725 | 5.033 | 5.488 | 0.249 |
| mlp | 5466 | -0.3392 | -1.135 | 0.6008 | 4.334 | 3.88 | 4.894 | 5.423 | 0.2499 |
| 1d_cnn | 5466 | 0.0894 | -0.8157 | 1.286 | 5.681 | 4.958 | 6.602 | 7.046 | 0.3754 |
| edge_attention_cnn_new | 5466 | -0.3123 | -1.241 | 0.747 | 6.409 | 5.698 | 7.352 | 7.783 | 0.4286 |
| waveform_transformer | 5466 | 1.609 | 0.7796 | 2.383 | 6.702 | 6.068 | 7.453 | 8.302 | 0.4704 |

## Paired Deltas Against Traditional Reference

Positive `delta_sigma68_ns` means the method is wider than the traditional
reference under the same run-block bootstrap.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_timewalk | 2.91 | 2.462 | 3.64 | -0.8469 | -1.824 | 0.08543 |
| ridge | traditional_cfd_template_timewalk | 3.455 | 2.864 | 4.229 | -0.155 | -0.7992 | 0.7116 |
| mlp | traditional_cfd_template_timewalk | 3.517 | 3.021 | 4.14 | -0.9316 | -1.725 | 0.0204 |
| 1d_cnn | traditional_cfd_template_timewalk | 4.863 | 4.072 | 5.846 | -0.5029 | -1.424 | 0.6996 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk | 5.592 | 4.862 | 6.523 | -0.9046 | -1.834 | 0.2059 |
| waveform_transformer | traditional_cfd_template_timewalk | 5.885 | 5.228 | 6.661 | 1.017 | 0.1931 | 1.844 |

## Run and Run-Family Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_timewalk | 1350 | 0.2163 | 0.8975 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.3875 | 3.967 | 0.2837 |
| sample_i_analysis | mlp | 1350 | 0.1982 | 4.529 | 0.303 |
| sample_i_analysis | ridge | 1350 | 0.7328 | 5.959 | 0.3748 |
| sample_i_analysis | 1d_cnn | 1350 | 0.08422 | 7.653 | 0.4985 |
| sample_i_analysis | edge_attention_cnn_new | 1350 | -0.6772 | 8.253 | 0.5326 |
| sample_i_analysis | waveform_transformer | 1350 | 0.6934 | 8.455 | 0.4941 |
| sample_i_calib | traditional_cfd_template_timewalk | 657 | 0.3186 | 1.565 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.774 | 3.944 | 0.2801 |
| sample_i_calib | mlp | 657 | 1.899 | 4.493 | 0.2892 |
| sample_i_calib | ridge | 657 | 3.091 | 4.494 | 0.3227 |
| sample_i_calib | 1d_cnn | 657 | 3.035 | 6.418 | 0.4642 |
| sample_i_calib | waveform_transformer | 657 | 3.604 | 6.967 | 0.4764 |
| sample_i_calib | edge_attention_cnn_new | 657 | 2.085 | 7.424 | 0.4901 |
| sample_ii_analysis | traditional_cfd_template_timewalk | 2739 | 0.6987 | 0.6458 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.09 | 3.856 | 0.1913 |
| sample_ii_analysis | ridge | 2739 | -0.003273 | 3.951 | 0.1986 |
| sample_ii_analysis | mlp | 2739 | -1.102 | 4.47 | 0.2526 |
| sample_ii_analysis | 1d_cnn | 2739 | -0.3234 | 5.139 | 0.3209 |
| sample_ii_analysis | edge_attention_cnn_new | 2739 | -0.6402 | 5.82 | 0.3855 |
| sample_ii_analysis | waveform_transformer | 2739 | 1.449 | 6.551 | 0.4786 |
| sample_ii_calib | traditional_cfd_template_timewalk | 720 | 0.6089 | 0.3177 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -0.6416 | 2.828 | 0.06111 |
| sample_ii_calib | ridge | 720 | -0.1176 | 3.26 | 0.1375 |
| sample_ii_calib | mlp | 720 | -0.9042 | 3.486 | 0.1042 |
| sample_ii_calib | 1d_cnn | 720 | -0.4198 | 4.417 | 0.2708 |
| sample_ii_calib | edge_attention_cnn_new | 720 | -0.6556 | 5.22 | 0.3417 |
| sample_ii_calib | waveform_transformer | 720 | 1.793 | 5.659 | 0.3889 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 3.035 | 6.418 | 0.4642 |
| 1d_cnn | 50 | 680 | -1.312 | 11 | 0.4603 |
| 1d_cnn | 57 | 670 | 2.88 | 7.03 | 0.5373 |
| 1d_cnn | 58 | 654 | -1.797 | 5.948 | 0.3823 |
| 1d_cnn | 60 | 720 | 1.137 | 4.714 | 0.3222 |
| 1d_cnn | 62 | 720 | -0.8683 | 4.335 | 0.2319 |
| 1d_cnn | 64 | 720 | -0.4198 | 4.417 | 0.2708 |
| 1d_cnn | 65 | 645 | -0.1851 | 5.491 | 0.3566 |
| edge_attention_cnn_new | 42 | 657 | 2.085 | 7.424 | 0.4901 |
| edge_attention_cnn_new | 50 | 680 | -2.955 | 10.71 | 0.5176 |
| edge_attention_cnn_new | 57 | 670 | 1.621 | 7.574 | 0.5478 |
| edge_attention_cnn_new | 58 | 654 | -1.809 | 6.279 | 0.4434 |
| edge_attention_cnn_new | 60 | 720 | 1.107 | 5.261 | 0.3778 |
| edge_attention_cnn_new | 62 | 720 | -1.158 | 5.089 | 0.3306 |
| edge_attention_cnn_new | 64 | 720 | -0.6556 | 5.22 | 0.3417 |
| edge_attention_cnn_new | 65 | 645 | -1.012 | 5.847 | 0.3969 |
| gradient_boosted_trees | 42 | 657 | 1.774 | 3.944 | 0.2801 |
| gradient_boosted_trees | 50 | 680 | 0.7916 | 9.383 | 0.2882 |
| gradient_boosted_trees | 57 | 670 | -0.2363 | 5.375 | 0.2791 |
| gradient_boosted_trees | 58 | 654 | -2.826 | 3.55 | 0.2569 |
| gradient_boosted_trees | 60 | 720 | 0.263 | 3.86 | 0.1917 |
| gradient_boosted_trees | 62 | 720 | -1.131 | 3.78 | 0.1403 |
| gradient_boosted_trees | 64 | 720 | -0.6416 | 2.828 | 0.06111 |
| gradient_boosted_trees | 65 | 645 | -1.309 | 3.98 | 0.1814 |
| mlp | 42 | 657 | 1.899 | 4.493 | 0.2892 |
| mlp | 50 | 680 | 0.2268 | 9.222 | 0.3074 |
| mlp | 57 | 670 | 0.1481 | 5.882 | 0.2985 |
| mlp | 58 | 654 | -2.438 | 4.369 | 0.2936 |
| mlp | 60 | 720 | 0.03294 | 4.437 | 0.2417 |
| mlp | 62 | 720 | -1.148 | 4.001 | 0.2 |
| mlp | 64 | 720 | -0.9042 | 3.486 | 0.1042 |
| mlp | 65 | 645 | -1.5 | 4.811 | 0.2822 |
| ridge | 42 | 657 | 3.091 | 4.494 | 0.3227 |
| ridge | 50 | 680 | -0.03845 | 10.47 | 0.3559 |
| ridge | 57 | 670 | 1.838 | 5.802 | 0.394 |
| ridge | 58 | 654 | -0.8476 | 4.441 | 0.2569 |
| ridge | 60 | 720 | 0.7058 | 3.506 | 0.1597 |
| ridge | 62 | 720 | -0.4762 | 3.348 | 0.1542 |
| ridge | 64 | 720 | -0.1176 | 3.26 | 0.1375 |
| ridge | 65 | 645 | 0.5036 | 4.261 | 0.2326 |
| traditional_cfd_template_timewalk | 42 | 657 | 0.3186 | 1.565 | 0 |
| traditional_cfd_template_timewalk | 50 | 680 | 0.2163 | 0.8892 | 0 |
| traditional_cfd_template_timewalk | 57 | 670 | 0.2103 | 0.982 | 0 |
| traditional_cfd_template_timewalk | 58 | 654 | 0.8598 | 0.6311 | 0 |
| traditional_cfd_template_timewalk | 60 | 720 | 0.06149 | 0.9169 | 0 |
| traditional_cfd_template_timewalk | 62 | 720 | 0.7291 | 0.5572 | 0 |
| traditional_cfd_template_timewalk | 64 | 720 | 0.6089 | 0.3177 | 0 |
| traditional_cfd_template_timewalk | 65 | 645 | 0.8647 | 0.3563 | 0 |
| waveform_transformer | 42 | 657 | 3.604 | 6.967 | 0.4764 |
| waveform_transformer | 50 | 680 | -0.5407 | 11.11 | 0.4412 |
| waveform_transformer | 57 | 670 | 2.594 | 7.459 | 0.5478 |
| waveform_transformer | 58 | 654 | 0.09544 | 7.866 | 0.5229 |
| waveform_transformer | 60 | 720 | 2.378 | 6.533 | 0.4806 |
| waveform_transformer | 62 | 720 | 1.113 | 5.607 | 0.4236 |
| waveform_transformer | 64 | 720 | 1.793 | 5.659 | 0.3889 |
| waveform_transformer | 65 | 645 | 1.998 | 6.298 | 0.493 |

## Frontier Strata

The requested axes are represented by raw waveform proxies: tail fraction for
pulse shape, baseline displacement for pedestal memory, late secondary
prominence spacing for pile-up proximity, high-amplitude/flat-top occupancy for
saturation onset, amplitude quartile for energy proxy, and duplicate-readout
ratio sidebands for PID stratum.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| energy_bin | q1_low | 1d_cnn | 1390 | -1.187 | 6.031 | 0.4101 |
| energy_bin | q1_low | edge_attention_cnn_new | 1390 | -2.271 | 6.872 | 0.4863 |
| energy_bin | q1_low | gradient_boosted_trees | 1390 | -0.3298 | 3.587 | 0.195 |
| energy_bin | q1_low | mlp | 1390 | -0.2323 | 3.938 | 0.2173 |
| energy_bin | q1_low | ridge | 1390 | 1.391 | 4.212 | 0.2683 |
| energy_bin | q1_low | traditional_cfd_template_timewalk | 1390 | 0.2734 | 0.8953 | 0 |
| energy_bin | q1_low | waveform_transformer | 1390 | 2.044 | 6.074 | 0.4446 |
| energy_bin | q2 | 1d_cnn | 1507 | -0.2534 | 5.392 | 0.3517 |
| energy_bin | q2 | edge_attention_cnn_new | 1507 | -0.832 | 5.303 | 0.3484 |
| energy_bin | q2 | gradient_boosted_trees | 1507 | -0.108 | 4.002 | 0.2269 |
| energy_bin | q2 | mlp | 1507 | -0.2852 | 4.773 | 0.2906 |
| energy_bin | q2 | ridge | 1507 | 0.6316 | 4.538 | 0.2727 |
| energy_bin | q2 | traditional_cfd_template_timewalk | 1507 | 0.6906 | 0.5768 | 0 |
| energy_bin | q2 | waveform_transformer | 1507 | 3.265 | 5.438 | 0.4844 |
| energy_bin | q3 | 1d_cnn | 1474 | 2.154 | 4.745 | 0.3372 |
| energy_bin | q3 | edge_attention_cnn_new | 1474 | 2.654 | 4.459 | 0.3833 |
| energy_bin | q3 | gradient_boosted_trees | 1474 | -0.07097 | 3.731 | 0.2069 |
| energy_bin | q3 | mlp | 1474 | -0.1989 | 4.439 | 0.2442 |
| energy_bin | q3 | ridge | 1474 | -0.1091 | 4.162 | 0.232 |
| energy_bin | q3 | traditional_cfd_template_timewalk | 1474 | 0.7315 | 0.618 | 0 |
| energy_bin | q3 | waveform_transformer | 1474 | 2.787 | 6.602 | 0.4844 |
| energy_bin | q4_high | 1d_cnn | 1095 | -1.109 | 6.101 | 0.4155 |
| energy_bin | q4_high | edge_attention_cnn_new | 1095 | -2.857 | 6.948 | 0.5269 |
| energy_bin | q4_high | gradient_boosted_trees | 1095 | -0.6097 | 3.332 | 0.1982 |
| energy_bin | q4_high | mlp | 1095 | -0.6866 | 3.881 | 0.2429 |
| energy_bin | q4_high | ridge | 1095 | -0.1686 | 3.923 | 0.2146 |
| energy_bin | q4_high | traditional_cfd_template_timewalk | 1095 | 0.5905 | 0.9942 | 0 |
| energy_bin | q4_high | waveform_transformer | 1095 | -3.348 | 5.835 | 0.4648 |
| pedestal_drift_bin | high | 1d_cnn | 1688 | 0.3851 | 6.669 | 0.4289 |
| pedestal_drift_bin | high | edge_attention_cnn_new | 1688 | 0.02046 | 7.914 | 0.5083 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1688 | 0.1175 | 3.965 | 0.2287 |
| pedestal_drift_bin | high | mlp | 1688 | 0.2455 | 4.246 | 0.2524 |
| pedestal_drift_bin | high | ridge | 1688 | 0.571 | 4.403 | 0.2737 |
| pedestal_drift_bin | high | traditional_cfd_template_timewalk | 1688 | 0.5397 | 0.8279 | 0 |
| pedestal_drift_bin | high | waveform_transformer | 1688 | 0.7094 | 7.136 | 0.4799 |
| pedestal_drift_bin | low | 1d_cnn | 1796 | -0.1625 | 5.429 | 0.3569 |
| pedestal_drift_bin | low | edge_attention_cnn_new | 1796 | -0.5133 | 5.918 | 0.4014 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1796 | -0.4116 | 3.496 | 0.1965 |
| pedestal_drift_bin | low | mlp | 1796 | -0.7081 | 4.147 | 0.24 |
| pedestal_drift_bin | low | ridge | 1796 | 0.3372 | 4.25 | 0.2433 |
| pedestal_drift_bin | low | traditional_cfd_template_timewalk | 1796 | 0.6195 | 0.8283 | 0 |
| pedestal_drift_bin | low | waveform_transformer | 1796 | 1.771 | 6.513 | 0.4633 |
| pedestal_drift_bin | mid | 1d_cnn | 1982 | 0.1441 | 5.284 | 0.3466 |
| pedestal_drift_bin | mid | edge_attention_cnn_new | 1982 | -0.4216 | 5.781 | 0.3855 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1982 | -0.3323 | 3.627 | 0.1998 |
| pedestal_drift_bin | mid | mlp | 1982 | -0.4379 | 4.445 | 0.2568 |
| pedestal_drift_bin | mid | ridge | 1982 | 0.4378 | 4.151 | 0.2331 |
| pedestal_drift_bin | mid | traditional_cfd_template_timewalk | 1982 | 0.6026 | 0.7983 | 0 |
| pedestal_drift_bin | mid | waveform_transformer | 1982 | 2.104 | 6.508 | 0.4687 |
| pid_sideband | central | 1d_cnn | 3728 | 0.1233 | 5.404 | 0.3608 |
| pid_sideband | central | edge_attention_cnn_new | 3728 | -0.3692 | 5.875 | 0.3887 |
| pid_sideband | central | gradient_boosted_trees | 3728 | -0.2414 | 3.674 | 0.2039 |
| pid_sideband | central | mlp | 3728 | -0.2771 | 4.357 | 0.2508 |
| pid_sideband | central | ridge | 3728 | 0.5447 | 4.305 | 0.2505 |
| pid_sideband | central | traditional_cfd_template_timewalk | 3728 | 0.6017 | 0.8088 | 0 |
| pid_sideband | central | waveform_transformer | 3728 | 2.314 | 6.478 | 0.4761 |
| pid_sideband | high_duplicate | 1d_cnn | 875 | 0.0449 | 7.897 | 0.4903 |
| pid_sideband | high_duplicate | edge_attention_cnn_new | 875 | 0.02304 | 10.57 | 0.6217 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 875 | -0.03044 | 4.072 | 0.2446 |
| pid_sideband | high_duplicate | mlp | 875 | -0.471 | 4.357 | 0.2491 |
| pid_sideband | high_duplicate | ridge | 875 | 0.3309 | 4.605 | 0.2914 |
| pid_sideband | high_duplicate | traditional_cfd_template_timewalk | 875 | 0.4954 | 0.8337 | 0 |
| pid_sideband | high_duplicate | waveform_transformer | 875 | -1.369 | 6.891 | 0.44 |
| pid_sideband | low_duplicate | 1d_cnn | 863 | -0.01498 | 5.084 | 0.3221 |
| pid_sideband | low_duplicate | edge_attention_cnn_new | 863 | -0.4705 | 5.872 | 0.4056 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 863 | -0.3808 | 3.494 | 0.1866 |
| pid_sideband | low_duplicate | mlp | 863 | -0.6012 | 4.31 | 0.2468 |
| pid_sideband | low_duplicate | ridge | 863 | 0.1568 | 3.872 | 0.1993 |
| pid_sideband | low_duplicate | traditional_cfd_template_timewalk | 863 | 0.6443 | 0.8445 | 0 |
| pid_sideband | low_duplicate | waveform_transformer | 863 | 1.253 | 7.011 | 0.4762 |
| pileup_separation_bin | close | 1d_cnn | 1696 | -1.179 | 5.526 | 0.3579 |
| pileup_separation_bin | close | edge_attention_cnn_new | 1696 | -1.815 | 6.517 | 0.4463 |
| pileup_separation_bin | close | gradient_boosted_trees | 1696 | -0.6457 | 3.234 | 0.1657 |
| pileup_separation_bin | close | mlp | 1696 | -1.114 | 4.043 | 0.2205 |
| pileup_separation_bin | close | ridge | 1696 | -0.4475 | 4.088 | 0.227 |
| pileup_separation_bin | close | traditional_cfd_template_timewalk | 1696 | 0.5885 | 0.8796 | 0 |
| pileup_separation_bin | close | waveform_transformer | 1696 | 1.339 | 6.563 | 0.4528 |
| pileup_separation_bin | late | 1d_cnn | 3 | -4.475 | 25.95 | 0.3333 |
| pileup_separation_bin | late | edge_attention_cnn_new | 3 | -2.133 | 18.53 | 0.3333 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | 0.416 | 3.347 | 0.3333 |
| pileup_separation_bin | late | mlp | 3 | -26.86 | 24.12 | 1 |
| pileup_separation_bin | late | ridge | 3 | 11.87 | 4.15 | 0.6667 |
| pileup_separation_bin | late | traditional_cfd_template_timewalk | 3 | 0.7065 | 0.5207 | 0 |
| pileup_separation_bin | late | waveform_transformer | 3 | -52.58 | 29.91 | 1 |
| pileup_separation_bin | mid | 1d_cnn | 1182 | 1.99 | 5.361 | 0.4019 |
| pileup_separation_bin | mid | edge_attention_cnn_new | 1182 | 1.869 | 6.386 | 0.4729 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1182 | -0.5545 | 3.664 | 0.1861 |
| pileup_separation_bin | mid | mlp | 1182 | -0.8753 | 3.986 | 0.2157 |
| pileup_separation_bin | mid | ridge | 1182 | -0.01346 | 4.156 | 0.22 |
| pileup_separation_bin | mid | traditional_cfd_template_timewalk | 1182 | 0.6591 | 0.7935 | 0 |
| pileup_separation_bin | mid | waveform_transformer | 1182 | -0.3372 | 6.097 | 0.4069 |
| pileup_separation_bin | none | 1d_cnn | 2585 | 0.2444 | 5.679 | 0.3749 |
| pileup_separation_bin | none | edge_attention_cnn_new | 2585 | -0.4211 | 6.113 | 0.3969 |
| pileup_separation_bin | none | gradient_boosted_trees | 2585 | 0.1234 | 4.05 | 0.2449 |
| pileup_separation_bin | none | mlp | 2585 | 0.3982 | 4.339 | 0.2839 |
| pileup_separation_bin | none | ridge | 2585 | 1.215 | 4.169 | 0.2762 |
| pileup_separation_bin | none | traditional_cfd_template_timewalk | 2585 | 0.5624 | 0.7799 | 0 |
| pileup_separation_bin | none | waveform_transformer | 2585 | 2.635 | 6.858 | 0.5103 |
| pulse_shape_class | compact | 1d_cnn | 1887 | -0.5565 | 6.374 | 0.4176 |
| pulse_shape_class | compact | edge_attention_cnn_new | 1887 | -1.199 | 7.632 | 0.4992 |
| pulse_shape_class | compact | gradient_boosted_trees | 1887 | -0.6527 | 3.772 | 0.2008 |
| pulse_shape_class | compact | mlp | 1887 | -1.078 | 4.162 | 0.2189 |
| pulse_shape_class | compact | ridge | 1887 | 0.4629 | 4.66 | 0.2814 |
| pulse_shape_class | compact | traditional_cfd_template_timewalk | 1887 | 0.5157 | 0.8073 | 0 |
| pulse_shape_class | compact | waveform_transformer | 1887 | 2.094 | 6.287 | 0.486 |
| pulse_shape_class | late_tail | 1d_cnn | 1831 | 1.032 | 6.178 | 0.4189 |
| pulse_shape_class | late_tail | edge_attention_cnn_new | 1831 | 0.686 | 6.099 | 0.396 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1831 | 0.3803 | 4.635 | 0.2818 |
| pulse_shape_class | late_tail | mlp | 1831 | 0.6951 | 4.739 | 0.3233 |
| pulse_shape_class | late_tail | ridge | 1831 | 0.8678 | 4.579 | 0.2977 |
| pulse_shape_class | late_tail | traditional_cfd_template_timewalk | 1831 | 0.6892 | 0.7081 | 0 |
| pulse_shape_class | late_tail | waveform_transformer | 1831 | 0.886 | 8.353 | 0.4921 |
| pulse_shape_class | nominal | 1d_cnn | 1748 | -0.3197 | 4.657 | 0.2843 |
| pulse_shape_class | nominal | edge_attention_cnn_new | 1748 | -0.8015 | 5.549 | 0.3867 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1748 | -0.4871 | 3.156 | 0.1373 |
| pulse_shape_class | nominal | mlp | 1748 | -0.7176 | 3.799 | 0.2065 |
| pulse_shape_class | nominal | ridge | 1748 | 0.004379 | 3.597 | 0.163 |
| pulse_shape_class | nominal | traditional_cfd_template_timewalk | 1748 | 0.5379 | 0.8857 | 0 |
| pulse_shape_class | nominal | waveform_transformer | 1748 | 1.786 | 5.846 | 0.4308 |
| saturation_onset_bin | linear | 1d_cnn | 3950 | 0.4137 | 5.811 | 0.3906 |
| saturation_onset_bin | linear | edge_attention_cnn_new | 3950 | -0.005825 | 6.456 | 0.4316 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3950 | -0.3137 | 3.751 | 0.2073 |
| saturation_onset_bin | linear | mlp | 3950 | -0.3926 | 4.284 | 0.2461 |
| saturation_onset_bin | linear | ridge | 3950 | 0.3521 | 4.28 | 0.2484 |
| saturation_onset_bin | linear | traditional_cfd_template_timewalk | 3950 | 0.6232 | 0.7579 | 0 |
| saturation_onset_bin | linear | waveform_transformer | 3950 | 1.402 | 6.865 | 0.4772 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1516 | -0.5293 | 5.255 | 0.3358 |
| saturation_onset_bin | near_saturation | edge_attention_cnn_new | 1516 | -1.308 | 6.047 | 0.4208 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1516 | -0.05768 | 3.695 | 0.2084 |
| saturation_onset_bin | near_saturation | mlp | 1516 | -0.1791 | 4.45 | 0.2599 |
| saturation_onset_bin | near_saturation | ridge | 1516 | 0.5828 | 4.288 | 0.2507 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_timewalk | 1516 | 0.4953 | 0.8773 | 0 |
| saturation_onset_bin | near_saturation | waveform_transformer | 1516 | 2.011 | 6.305 | 0.4525 |

The table below compresses each method/axis to its best and worst stratum.

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| energy_bin | edge_attention_cnn_new | 4 | q3 | 4.459 | q4_high | 6.948 | 2.489 |
| energy_bin | 1d_cnn | 4 | q3 | 4.745 | q4_high | 6.101 | 1.355 |
| energy_bin | waveform_transformer | 4 | q2 | 5.438 | q3 | 6.602 | 1.164 |
| energy_bin | mlp | 4 | q4_high | 3.881 | q2 | 4.773 | 0.8922 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.332 | q2 | 4.002 | 0.67 |
| energy_bin | ridge | 4 | q4_high | 3.923 | q2 | 4.538 | 0.6157 |
| energy_bin | traditional_cfd_template_timewalk | 4 | q2 | 0.5768 | q4_high | 0.9942 | 0.4175 |
| pedestal_drift_bin | edge_attention_cnn_new | 3 | mid | 5.781 | high | 7.914 | 2.134 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.284 | high | 6.669 | 1.385 |
| pedestal_drift_bin | waveform_transformer | 3 | mid | 6.508 | high | 7.136 | 0.6286 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.496 | high | 3.965 | 0.4688 |
| pedestal_drift_bin | mlp | 3 | low | 4.147 | mid | 4.445 | 0.298 |
| pedestal_drift_bin | ridge | 3 | mid | 4.151 | high | 4.403 | 0.2521 |
| pedestal_drift_bin | traditional_cfd_template_timewalk | 3 | mid | 0.7983 | low | 0.8283 | 0.03008 |
| pid_sideband | edge_attention_cnn_new | 3 | low_duplicate | 5.872 | high_duplicate | 10.57 | 4.703 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 5.084 | high_duplicate | 7.897 | 2.814 |
| pid_sideband | ridge | 3 | low_duplicate | 3.872 | high_duplicate | 4.605 | 0.7324 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.494 | high_duplicate | 4.072 | 0.578 |
| pid_sideband | waveform_transformer | 3 | central | 6.478 | low_duplicate | 7.011 | 0.5333 |
| pid_sideband | mlp | 3 | low_duplicate | 4.31 | high_duplicate | 4.357 | 0.04736 |
| pid_sideband | traditional_cfd_template_timewalk | 3 | central | 0.8088 | low_duplicate | 0.8445 | 0.03561 |
| pileup_separation_bin | waveform_transformer | 4 | mid | 6.097 | late | 29.91 | 23.81 |
| pileup_separation_bin | 1d_cnn | 4 | mid | 5.361 | late | 25.95 | 20.59 |
| pileup_separation_bin | mlp | 4 | mid | 3.986 | late | 24.12 | 20.13 |
| pileup_separation_bin | edge_attention_cnn_new | 4 | none | 6.113 | late | 18.53 | 12.42 |
| pileup_separation_bin | gradient_boosted_trees | 4 | close | 3.234 | none | 4.05 | 0.8157 |
| pileup_separation_bin | traditional_cfd_template_timewalk | 4 | late | 0.5207 | close | 0.8796 | 0.3589 |
| pileup_separation_bin | ridge | 4 | close | 4.088 | none | 4.169 | 0.0812 |
| pulse_shape_class | waveform_transformer | 3 | nominal | 5.846 | late_tail | 8.353 | 2.508 |
| pulse_shape_class | edge_attention_cnn_new | 3 | nominal | 5.549 | compact | 7.632 | 2.083 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.657 | compact | 6.374 | 1.718 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.156 | late_tail | 4.635 | 1.478 |
| pulse_shape_class | ridge | 3 | nominal | 3.597 | compact | 4.66 | 1.063 |
| pulse_shape_class | mlp | 3 | nominal | 3.799 | late_tail | 4.739 | 0.9398 |
| pulse_shape_class | traditional_cfd_template_timewalk | 3 | late_tail | 0.7081 | nominal | 0.8857 | 0.1775 |
| saturation_onset_bin | waveform_transformer | 2 | near_saturation | 6.305 | linear | 6.865 | 0.5605 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.255 | linear | 5.811 | 0.556 |
| saturation_onset_bin | edge_attention_cnn_new | 2 | near_saturation | 6.047 | linear | 6.456 | 0.4086 |
| saturation_onset_bin | mlp | 2 | linear | 4.284 | near_saturation | 4.45 | 0.1653 |
| saturation_onset_bin | traditional_cfd_template_timewalk | 2 | linear | 0.7579 | near_saturation | 0.8773 | 0.1193 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.695 | linear | 3.751 | 0.05528 |
| saturation_onset_bin | ridge | 2 | linear | 4.28 | near_saturation | 4.288 | 0.007513 |

## Systematic Ablations

The ablations remove correlated feature families from the gradient-boosted-tree
learner.  They test whether the frontier is driven by pretrigger pedestal
memory, late pulse-shape information, or only amplitude and CFD features.

| ablation | n_features | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| full_gradient_boosted_trees | 33 | 3.683 | 3.292 | 4.363 | 0 | 0.2051 |
| drop_tail_pulse_shape_features | 24 | 3.743 | 3.292 | 4.386 | 0.06009 | 0.2076 |
| drop_pretrigger_features | 27 | 4.043 | 3.495 | 4.738 | 0.3606 | 0.2384 |
| amplitude_cfd_only | 5 | 4.2 | 3.627 | 4.81 | 0.5174 | 0.255 |

## Systematics, Limitations, and Caveats

The raw ROOT tree provides waveforms but not independent particle truth,
external timing truth, or electronics-state labels.  PID, energy, pile-up
proximity, and saturation are therefore stress strata, not truth labels.
Because all targets are constructed from the same digitized waveform, absolute
physics timing should not be inferred from the sub-ns residuals alone.  The
claim supported here is comparative: given an identical raw-ROOT reconstruction,
run-held-out split, and bootstrap, the listed methods have the reported
relative bias and resolution on the registered onset residual.

The run-block bootstrap emphasizes transfer across data-taking periods; it is
not an event-level counting interval.  Small strata, especially high pile-up
prominence and near-saturation subsets, should be read through their tabled
sample counts.  Neural methods are intentionally compact and trained for a
fixed small epoch budget to avoid turning the ticket into architecture search.

Runtime was `35.2 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.
