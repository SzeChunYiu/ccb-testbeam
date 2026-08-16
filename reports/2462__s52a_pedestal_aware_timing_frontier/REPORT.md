# S52a/#2462: Pedestal-Aware Pulse-Shape Timing Frontier

## Abstract

Ticket `2462` requested a raw-ROOT reproduction followed by a
run-split benchmark of a strong traditional timing method against ridge,
gradient-boosted trees, MLP, 1D-CNN, compact transformer encoders, and a new
architecture when sensible. For this ticket the traditional comparator is interpreted as the constant-fraction/cross-correlation template baseline requested in the issue body.  This study rebuilds the B-stack pulse table
directly from `h101/HRDv`, verifies the registered selected-pulse count, and
evaluates timing bias and resolution under pulse-shape, pedestal-memory,
pile-up-proximity, saturation-onset, energy-proxy, and PID-sideband strata.

The primary registered criterion is held-out run-block `sigma_68` of onset
residual error.  The winner written to `result.json` is **`traditional_cfd_template_timewalk`** with
`sigma_68 = 0.9882 ns`
`[0.7903, 1.159]`.  The
traditional reference obtains `0.9882 ns`
`[0.7903, 1.159]`.

## Raw ROOT Reproduction Gate

Input ROOT files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each run the
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
| 31 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0031.root | 11638901 | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| 32 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0032.root | 12157812 | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| 33 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0033.root | 16781109 | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| 34 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0034.root | 11697434 | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| 35 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0035.root | 7793651 | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| 36 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0036.root | 6167361 | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| 37 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0037.root | 14369738 | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| 39 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0039.root | 8625385 | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |

## Ticket Claim Provenance

The required command `tn-ticket claim testbeam-laptop-1 --project testbeam` was run once and returned the null pseudo-ticket output recorded in `claimed_ticket.txt`.  Read-only GitHub checks showed open testbeam analysis tickets and no worker claim for `testbeam-laptop-1`, so issue #2462 was manually label-swapped to `factory:claimed` and `worker:testbeam-laptop-1` without rerunning the helper.

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
| traditional_cfd_template_timewalk | 5466 | 0.118 | -0.5069 | 0.4616 | 0.9882 | 0.7903 | 1.159 | 0.939 | 0 |
| gradient_boosted_trees | 5466 | -0.724 | -1.667 | 0.1701 | 2.904 | 2.442 | 3.549 | 4.806 | 0.1401 |
| mlp | 5466 | -0.6789 | -1.585 | 0.06895 | 3.441 | 3.049 | 4.11 | 4.85 | 0.1711 |
| ridge | 5466 | -0.5105 | -1.24 | 0.06279 | 3.864 | 3.295 | 4.651 | 5.246 | 0.2067 |
| 1d_cnn | 5466 | -0.4328 | -1.498 | 0.3266 | 5.927 | 5.286 | 6.991 | 7.66 | 0.3891 |
| edge_attention_cnn_new | 5466 | -2.018 | -3.089 | -1.192 | 6.275 | 5.589 | 7.173 | 7.901 | 0.4378 |
| waveform_transformer | 5466 | 1.495 | 0.2415 | 2.573 | 7.123 | 6.471 | 7.944 | 7.91 | 0.4951 |

## Paired Deltas Against Traditional Reference

Positive `delta_sigma68_ns` means the method is wider than the traditional
reference under the same run-block bootstrap.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_timewalk | 1.916 | 1.46 | 2.596 | -0.842 | -1.804 | 0.4034 |
| mlp | traditional_cfd_template_timewalk | 2.453 | 2.024 | 3.202 | -0.7968 | -1.733 | 0.3282 |
| ridge | traditional_cfd_template_timewalk | 2.876 | 2.277 | 3.736 | -0.6285 | -1.438 | 0.2944 |
| 1d_cnn | traditional_cfd_template_timewalk | 4.939 | 4.287 | 6.002 | -0.5508 | -1.697 | 0.5326 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk | 5.287 | 4.573 | 6.214 | -2.136 | -3.247 | -0.9515 |
| waveform_transformer | traditional_cfd_template_timewalk | 6.135 | 5.475 | 6.989 | 1.377 | 0.08257 | 2.724 |

## Run and Run-Family Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_timewalk | 1350 | -0.4603 | 0.7616 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | -0.1983 | 2.629 | 0.1652 |
| sample_i_analysis | mlp | 1350 | -0.2126 | 3.459 | 0.1807 |
| sample_i_analysis | ridge | 1350 | -0.6055 | 4.591 | 0.2763 |
| sample_i_analysis | edge_attention_cnn_new | 1350 | -3.03 | 7.415 | 0.5104 |
| sample_i_analysis | 1d_cnn | 1350 | -1.083 | 7.585 | 0.4385 |
| sample_i_analysis | waveform_transformer | 1350 | 0.2321 | 7.747 | 0.4511 |
| sample_i_calib | traditional_cfd_template_timewalk | 657 | -0.5206 | 1.112 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.288 | 4.399 | 0.274 |
| sample_i_calib | ridge | 657 | 1.837 | 5.109 | 0.3653 |
| sample_i_calib | mlp | 657 | 1.392 | 5.252 | 0.3151 |
| sample_i_calib | 1d_cnn | 657 | 1.587 | 7.324 | 0.4886 |
| sample_i_calib | waveform_transformer | 657 | 2.479 | 7.673 | 0.4916 |
| sample_i_calib | edge_attention_cnn_new | 657 | -0.2475 | 7.941 | 0.5723 |
| sample_ii_analysis | traditional_cfd_template_timewalk | 2739 | 0.1689 | 1.035 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.164 | 2.909 | 0.1179 |
| sample_ii_analysis | mlp | 2739 | -0.942 | 3.318 | 0.1464 |
| sample_ii_analysis | ridge | 2739 | -0.6239 | 3.454 | 0.1541 |
| sample_ii_analysis | 1d_cnn | 2739 | -0.4899 | 5.479 | 0.3593 |
| sample_ii_analysis | edge_attention_cnn_new | 2739 | -1.909 | 5.754 | 0.3903 |
| sample_ii_analysis | waveform_transformer | 2739 | 2.03 | 7.184 | 0.5235 |
| sample_ii_calib | traditional_cfd_template_timewalk | 720 | 0.8183 | 0.7036 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.494 | 2.603 | 0.05556 |
| sample_ii_calib | ridge | 720 | -1.104 | 3.355 | 0.1319 |
| sample_ii_calib | mlp | 720 | -1.857 | 3.538 | 0.1153 |
| sample_ii_calib | 1d_cnn | 720 | -0.4638 | 5.083 | 0.3194 |
| sample_ii_calib | edge_attention_cnn_new | 720 | -1.853 | 5.256 | 0.3597 |
| sample_ii_calib | waveform_transformer | 720 | 1.998 | 6.313 | 0.4722 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.587 | 7.324 | 0.4886 |
| 1d_cnn | 50 | 680 | -1.878 | 11.07 | 0.4706 |
| 1d_cnn | 57 | 670 | -0.3196 | 6.248 | 0.406 |
| 1d_cnn | 58 | 654 | -3.014 | 6.023 | 0.4541 |
| 1d_cnn | 60 | 720 | 0.7311 | 4.691 | 0.3 |
| 1d_cnn | 62 | 720 | 0.7324 | 5.119 | 0.3528 |
| 1d_cnn | 64 | 720 | -0.4638 | 5.083 | 0.3194 |
| 1d_cnn | 65 | 645 | -1.82 | 4.855 | 0.3364 |
| edge_attention_cnn_new | 42 | 657 | -0.2475 | 7.941 | 0.5723 |
| edge_attention_cnn_new | 50 | 680 | -4.555 | 10.88 | 0.5691 |
| edge_attention_cnn_new | 57 | 670 | -1.933 | 6.682 | 0.4507 |
| edge_attention_cnn_new | 58 | 654 | -4.469 | 6.338 | 0.5153 |
| edge_attention_cnn_new | 60 | 720 | -0.4156 | 5.173 | 0.3125 |
| edge_attention_cnn_new | 62 | 720 | -0.6263 | 5.3 | 0.3472 |
| edge_attention_cnn_new | 64 | 720 | -1.853 | 5.256 | 0.3597 |
| edge_attention_cnn_new | 65 | 645 | -3.09 | 4.783 | 0.3984 |
| gradient_boosted_trees | 42 | 657 | 1.288 | 4.399 | 0.274 |
| gradient_boosted_trees | 50 | 680 | 0.6108 | 10.49 | 0.2779 |
| gradient_boosted_trees | 57 | 670 | -0.8058 | 1.974 | 0.05075 |
| gradient_boosted_trees | 58 | 654 | -3.176 | 2.839 | 0.2554 |
| gradient_boosted_trees | 60 | 720 | 0.344 | 2.104 | 0.05 |
| gradient_boosted_trees | 62 | 720 | -0.03502 | 2.89 | 0.06389 |
| gradient_boosted_trees | 64 | 720 | -1.494 | 2.603 | 0.05556 |
| gradient_boosted_trees | 65 | 645 | -2.194 | 2.389 | 0.1147 |
| mlp | 42 | 657 | 1.392 | 5.252 | 0.3151 |
| mlp | 50 | 680 | -0.1448 | 9.976 | 0.2926 |
| mlp | 57 | 670 | -0.2946 | 2.615 | 0.06716 |
| mlp | 58 | 654 | -3.042 | 4.119 | 0.2859 |
| mlp | 60 | 720 | 0.3442 | 2.393 | 0.04306 |
| mlp | 62 | 720 | -0.2034 | 3.646 | 0.1319 |
| mlp | 64 | 720 | -1.857 | 3.538 | 0.1153 |
| mlp | 65 | 645 | -1.884 | 3.075 | 0.1364 |
| ridge | 42 | 657 | 1.837 | 5.109 | 0.3653 |
| ridge | 50 | 680 | -0.7668 | 10.72 | 0.3471 |
| ridge | 57 | 670 | -0.5665 | 3.616 | 0.2045 |
| ridge | 58 | 654 | -2.371 | 4.287 | 0.3104 |
| ridge | 60 | 720 | 0.08756 | 2.703 | 0.06667 |
| ridge | 62 | 720 | 0.3018 | 3.25 | 0.1111 |
| ridge | 64 | 720 | -1.104 | 3.355 | 0.1319 |
| ridge | 65 | 645 | -1.274 | 3.157 | 0.1411 |
| traditional_cfd_template_timewalk | 42 | 657 | -0.5206 | 1.112 | 0 |
| traditional_cfd_template_timewalk | 50 | 680 | -0.4766 | 0.596 | 0 |
| traditional_cfd_template_timewalk | 57 | 670 | -0.1854 | 1.014 | 0 |
| traditional_cfd_template_timewalk | 58 | 654 | 0.5842 | 0.7505 | 0 |
| traditional_cfd_template_timewalk | 60 | 720 | -0.649 | 1.598 | 0 |
| traditional_cfd_template_timewalk | 62 | 720 | -0.1285 | 1.147 | 0 |
| traditional_cfd_template_timewalk | 64 | 720 | 0.8183 | 0.7036 | 0 |
| traditional_cfd_template_timewalk | 65 | 645 | 0.4184 | 0.4258 | 0 |
| waveform_transformer | 42 | 657 | 2.479 | 7.673 | 0.4916 |
| waveform_transformer | 50 | 680 | -0.597 | 11.67 | 0.4956 |
| waveform_transformer | 57 | 670 | 1.245 | 6.294 | 0.406 |
| waveform_transformer | 58 | 654 | -2.025 | 7.993 | 0.5245 |
| waveform_transformer | 60 | 720 | 3.698 | 6.799 | 0.5639 |
| waveform_transformer | 62 | 720 | 3.529 | 6.272 | 0.525 |
| waveform_transformer | 64 | 720 | 1.998 | 6.313 | 0.4722 |
| waveform_transformer | 65 | 645 | 1.773 | 6.437 | 0.476 |

## Frontier Strata

The requested axes are represented by raw waveform proxies: tail fraction for
pulse shape, baseline displacement for pedestal memory, late secondary
prominence spacing for pile-up proximity, high-amplitude/flat-top occupancy for
saturation onset, amplitude quartile for energy proxy, and duplicate-readout
ratio sidebands for PID stratum.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| energy_bin | q1_low | 1d_cnn | 1416 | -2.09 | 7.057 | 0.4951 |
| energy_bin | q1_low | edge_attention_cnn_new | 1416 | -3.476 | 7.082 | 0.548 |
| energy_bin | q1_low | gradient_boosted_trees | 1416 | -1.008 | 2.844 | 0.1349 |
| energy_bin | q1_low | mlp | 1416 | -0.7501 | 3.212 | 0.1532 |
| energy_bin | q1_low | ridge | 1416 | 0.161 | 3.676 | 0.1836 |
| energy_bin | q1_low | traditional_cfd_template_timewalk | 1416 | -0.1908 | 1.074 | 0 |
| energy_bin | q1_low | waveform_transformer | 1416 | 2.021 | 6.779 | 0.4696 |
| energy_bin | q2 | 1d_cnn | 1523 | -0.821 | 4.745 | 0.3086 |
| energy_bin | q2 | edge_attention_cnn_new | 1523 | -1.997 | 4.868 | 0.3414 |
| energy_bin | q2 | gradient_boosted_trees | 1523 | -0.7549 | 2.74 | 0.1326 |
| energy_bin | q2 | mlp | 1523 | -0.7123 | 3.489 | 0.1635 |
| energy_bin | q2 | ridge | 1523 | -0.5438 | 3.466 | 0.1944 |
| energy_bin | q2 | traditional_cfd_template_timewalk | 1523 | 0.2195 | 0.8442 | 0 |
| energy_bin | q2 | waveform_transformer | 1523 | 3.538 | 5.758 | 0.5056 |
| energy_bin | q3 | 1d_cnn | 1427 | 1.831 | 4.639 | 0.3392 |
| energy_bin | q3 | edge_attention_cnn_new | 1427 | 0.923 | 4.894 | 0.3167 |
| energy_bin | q3 | gradient_boosted_trees | 1427 | -0.5517 | 3.013 | 0.1338 |
| energy_bin | q3 | mlp | 1427 | -0.5693 | 3.561 | 0.1745 |
| energy_bin | q3 | ridge | 1427 | -0.8041 | 3.88 | 0.2334 |
| energy_bin | q3 | traditional_cfd_template_timewalk | 1427 | 0.2801 | 0.9415 | 0 |
| energy_bin | q3 | waveform_transformer | 1427 | 3.342 | 6.974 | 0.5193 |
| energy_bin | q4_high | 1d_cnn | 1100 | -2.186 | 6.224 | 0.4291 |
| energy_bin | q4_high | edge_attention_cnn_new | 1100 | -4.98 | 6.576 | 0.5864 |
| energy_bin | q4_high | gradient_boosted_trees | 1100 | -0.546 | 3.208 | 0.1655 |
| energy_bin | q4_high | mlp | 1100 | -0.6163 | 3.519 | 0.2 |
| energy_bin | q4_high | ridge | 1100 | -0.9846 | 3.981 | 0.2191 |
| energy_bin | q4_high | traditional_cfd_template_timewalk | 1100 | -0.3876 | 1.022 | 0 |
| energy_bin | q4_high | waveform_transformer | 1100 | -3.783 | 5.821 | 0.4818 |
| pedestal_drift_bin | high | 1d_cnn | 1764 | -0.5162 | 7.646 | 0.4904 |
| pedestal_drift_bin | high | edge_attention_cnn_new | 1764 | -2.259 | 7.894 | 0.5164 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1764 | -0.5817 | 3.182 | 0.1695 |
| pedestal_drift_bin | high | mlp | 1764 | -0.4119 | 3.5 | 0.1797 |
| pedestal_drift_bin | high | ridge | 1764 | -0.616 | 3.833 | 0.2098 |
| pedestal_drift_bin | high | traditional_cfd_template_timewalk | 1764 | -0.1598 | 1.017 | 0 |
| pedestal_drift_bin | high | waveform_transformer | 1764 | 0.2348 | 7.037 | 0.4586 |
| pedestal_drift_bin | low | 1d_cnn | 1831 | -0.368 | 5.313 | 0.3468 |
| pedestal_drift_bin | low | edge_attention_cnn_new | 1831 | -1.944 | 5.714 | 0.4042 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1831 | -0.9052 | 2.814 | 0.1267 |
| pedestal_drift_bin | low | mlp | 1831 | -0.7853 | 3.339 | 0.1584 |
| pedestal_drift_bin | low | ridge | 1831 | -0.535 | 3.922 | 0.213 |
| pedestal_drift_bin | low | traditional_cfd_template_timewalk | 1831 | 0.2118 | 0.9607 | 0 |
| pedestal_drift_bin | low | waveform_transformer | 1831 | 2.044 | 7.271 | 0.5183 |
| pedestal_drift_bin | mid | 1d_cnn | 1871 | -0.4502 | 5.138 | 0.3351 |
| pedestal_drift_bin | mid | edge_attention_cnn_new | 1871 | -1.923 | 5.569 | 0.3966 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1871 | -0.6188 | 2.806 | 0.1256 |
| pedestal_drift_bin | mid | mlp | 1871 | -0.8004 | 3.483 | 0.1753 |
| pedestal_drift_bin | mid | ridge | 1871 | -0.4201 | 3.852 | 0.1978 |
| pedestal_drift_bin | mid | traditional_cfd_template_timewalk | 1871 | 0.1461 | 0.9632 | 0 |
| pedestal_drift_bin | mid | waveform_transformer | 1871 | 2.147 | 6.997 | 0.5067 |
| pid_sideband | central | 1d_cnn | 3727 | -0.3715 | 5.173 | 0.3394 |
| pid_sideband | central | edge_attention_cnn_new | 3727 | -1.897 | 5.545 | 0.3982 |
| pid_sideband | central | gradient_boosted_trees | 3727 | -0.7147 | 2.807 | 0.1315 |
| pid_sideband | central | mlp | 3727 | -0.6874 | 3.426 | 0.168 |
| pid_sideband | central | ridge | 3727 | -0.3574 | 3.955 | 0.216 |
| pid_sideband | central | traditional_cfd_template_timewalk | 3727 | 0.1472 | 0.9622 | 0 |
| pid_sideband | central | waveform_transformer | 3727 | 2.288 | 6.983 | 0.5109 |
| pid_sideband | high_duplicate | 1d_cnn | 881 | -0.8158 | 10.01 | 0.6436 |
| pid_sideband | high_duplicate | edge_attention_cnn_new | 881 | -3.293 | 10.17 | 0.6311 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 881 | -0.9924 | 3.272 | 0.1816 |
| pid_sideband | high_duplicate | mlp | 881 | -0.7099 | 3.476 | 0.1827 |
| pid_sideband | high_duplicate | ridge | 881 | -1.118 | 3.711 | 0.2157 |
| pid_sideband | high_duplicate | traditional_cfd_template_timewalk | 881 | -0.193 | 1.079 | 0 |
| pid_sideband | high_duplicate | waveform_transformer | 881 | -1.464 | 6.302 | 0.3961 |
| pid_sideband | low_duplicate | 1d_cnn | 858 | -0.4924 | 5.493 | 0.3438 |
| pid_sideband | low_duplicate | edge_attention_cnn_new | 858 | -1.965 | 6.012 | 0.4114 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 858 | -0.4727 | 3.077 | 0.1352 |
| pid_sideband | low_duplicate | mlp | 858 | -0.5819 | 3.502 | 0.1725 |
| pid_sideband | low_duplicate | ridge | 858 | -0.5362 | 3.426 | 0.1573 |
| pid_sideband | low_duplicate | traditional_cfd_template_timewalk | 858 | 0.2218 | 0.9589 | 0 |
| pid_sideband | low_duplicate | waveform_transformer | 858 | 1.451 | 7.403 | 0.528 |
| pileup_separation_bin | close | 1d_cnn | 1654 | -1.659 | 5.932 | 0.39 |
| pileup_separation_bin | close | edge_attention_cnn_new | 1654 | -3.278 | 6.309 | 0.4686 |
| pileup_separation_bin | close | gradient_boosted_trees | 1654 | -0.9495 | 2.78 | 0.1106 |
| pileup_separation_bin | close | mlp | 1654 | -1.19 | 3.434 | 0.1765 |
| pileup_separation_bin | close | ridge | 1654 | -1.307 | 3.888 | 0.237 |
| pileup_separation_bin | close | traditional_cfd_template_timewalk | 1654 | -0.07868 | 0.9947 | 0 |
| pileup_separation_bin | close | waveform_transformer | 1654 | 2.4 | 7.009 | 0.5115 |
| pileup_separation_bin | late | 1d_cnn | 1 | -10.28 | 0 | 1 |
| pileup_separation_bin | late | edge_attention_cnn_new | 1 | -17.2 | 0 | 1 |
| pileup_separation_bin | late | gradient_boosted_trees | 1 | -5.099 | 0 | 1 |
| pileup_separation_bin | late | mlp | 1 | -6.725 | 0 | 1 |
| pileup_separation_bin | late | ridge | 1 | -1.154 | 0 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_timewalk | 1 | 0.747 | 0 | 0 |
| pileup_separation_bin | late | waveform_transformer | 1 | -11.62 | 0 | 1 |
| pileup_separation_bin | mid | 1d_cnn | 1209 | 1.41 | 6.653 | 0.4574 |
| pileup_separation_bin | mid | edge_attention_cnn_new | 1209 | -0.8164 | 6.766 | 0.4467 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1209 | -1.086 | 2.773 | 0.1348 |
| pileup_separation_bin | mid | mlp | 1209 | -0.906 | 3.281 | 0.1522 |
| pileup_separation_bin | mid | ridge | 1209 | -1.06 | 3.925 | 0.2184 |
| pileup_separation_bin | mid | traditional_cfd_template_timewalk | 1209 | -0.1017 | 1.026 | 0 |
| pileup_separation_bin | mid | waveform_transformer | 1209 | -0.1172 | 6.805 | 0.4376 |
| pileup_separation_bin | none | 1d_cnn | 2602 | -0.4586 | 5.468 | 0.3566 |
| pileup_separation_bin | none | edge_attention_cnn_new | 2602 | -1.878 | 5.816 | 0.4139 |
| pileup_separation_bin | none | gradient_boosted_trees | 2602 | -0.4195 | 3.065 | 0.161 |
| pileup_separation_bin | none | mlp | 2602 | -0.2164 | 3.301 | 0.176 |
| pileup_separation_bin | none | ridge | 2602 | 0.07136 | 3.414 | 0.1822 |
| pileup_separation_bin | none | traditional_cfd_template_timewalk | 2602 | 0.1689 | 0.9737 | 0 |
| pileup_separation_bin | none | waveform_transformer | 2602 | 1.775 | 7.312 | 0.5111 |
| pulse_shape_class | compact | 1d_cnn | 1842 | -1.395 | 7.314 | 0.5125 |
| pulse_shape_class | compact | edge_attention_cnn_new | 1842 | -3.374 | 7.275 | 0.5326 |
| pulse_shape_class | compact | gradient_boosted_trees | 1842 | -1.621 | 2.753 | 0.139 |
| pulse_shape_class | compact | mlp | 1842 | -1.325 | 3.366 | 0.171 |
| pulse_shape_class | compact | ridge | 1842 | -1.058 | 4.182 | 0.2448 |
| pulse_shape_class | compact | traditional_cfd_template_timewalk | 1842 | 0.07327 | 1.008 | 0 |
| pulse_shape_class | compact | waveform_transformer | 1842 | 2.506 | 6.452 | 0.4821 |
| pulse_shape_class | late_tail | 1d_cnn | 1880 | -0.007433 | 5.397 | 0.3511 |
| pulse_shape_class | late_tail | edge_attention_cnn_new | 1880 | -1.136 | 6.021 | 0.3989 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1880 | 0.255 | 3.375 | 0.1856 |
| pulse_shape_class | late_tail | mlp | 1880 | 0.2325 | 3.492 | 0.2048 |
| pulse_shape_class | late_tail | ridge | 1880 | -0.2168 | 3.459 | 0.1963 |
| pulse_shape_class | late_tail | traditional_cfd_template_timewalk | 1880 | 0.2309 | 0.9493 | 0 |
| pulse_shape_class | late_tail | waveform_transformer | 1880 | -1.458 | 6.772 | 0.4676 |
| pulse_shape_class | nominal | 1d_cnn | 1744 | -0.1973 | 4.834 | 0.2999 |
| pulse_shape_class | nominal | edge_attention_cnn_new | 1744 | -1.908 | 5.292 | 0.3796 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1744 | -0.7844 | 2.508 | 0.09232 |
| pulse_shape_class | nominal | mlp | 1744 | -0.905 | 3.139 | 0.1347 |
| pulse_shape_class | nominal | ridge | 1744 | -0.486 | 3.806 | 0.1778 |
| pulse_shape_class | nominal | traditional_cfd_template_timewalk | 1744 | -0.1703 | 0.9885 | 0 |
| pulse_shape_class | nominal | waveform_transformer | 1744 | 3.488 | 6.482 | 0.5384 |
| saturation_onset_bin | linear | 1d_cnn | 3955 | -0.1707 | 6.156 | 0.4043 |
| saturation_onset_bin | linear | edge_attention_cnn_new | 3955 | -1.722 | 6.492 | 0.4397 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3955 | -0.797 | 2.925 | 0.1391 |
| saturation_onset_bin | linear | mlp | 3955 | -0.7569 | 3.496 | 0.1697 |
| saturation_onset_bin | linear | ridge | 3955 | -0.6544 | 3.958 | 0.2149 |
| saturation_onset_bin | linear | traditional_cfd_template_timewalk | 3955 | 0.1704 | 1.002 | 0 |
| saturation_onset_bin | linear | waveform_transformer | 3955 | 1.275 | 7.13 | 0.4829 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1511 | -1.142 | 5.333 | 0.3494 |
| saturation_onset_bin | near_saturation | edge_attention_cnn_new | 1511 | -2.806 | 5.801 | 0.4328 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1511 | -0.5892 | 2.816 | 0.143 |
| saturation_onset_bin | near_saturation | mlp | 1511 | -0.3961 | 3.319 | 0.1747 |
| saturation_onset_bin | near_saturation | ridge | 1511 | -0.2396 | 3.644 | 0.1853 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_timewalk | 1511 | -0.2115 | 0.9546 | 0 |
| saturation_onset_bin | near_saturation | waveform_transformer | 1511 | 2.185 | 6.992 | 0.5268 |

The table below compresses each method/axis to its best and worst stratum.

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| energy_bin | 1d_cnn | 4 | q3 | 4.639 | q1_low | 7.057 | 2.418 |
| energy_bin | edge_attention_cnn_new | 4 | q2 | 4.868 | q1_low | 7.082 | 2.214 |
| energy_bin | waveform_transformer | 4 | q2 | 5.758 | q3 | 6.974 | 1.216 |
| energy_bin | ridge | 4 | q2 | 3.466 | q4_high | 3.981 | 0.5148 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 2.74 | q4_high | 3.208 | 0.4681 |
| energy_bin | mlp | 4 | q1_low | 3.212 | q3 | 3.561 | 0.3483 |
| energy_bin | traditional_cfd_template_timewalk | 4 | q2 | 0.8442 | q1_low | 1.074 | 0.2299 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.138 | high | 7.646 | 2.507 |
| pedestal_drift_bin | edge_attention_cnn_new | 3 | mid | 5.569 | high | 7.894 | 2.325 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | mid | 2.806 | high | 3.182 | 0.3757 |
| pedestal_drift_bin | waveform_transformer | 3 | mid | 6.997 | low | 7.271 | 0.2737 |
| pedestal_drift_bin | mlp | 3 | low | 3.339 | high | 3.5 | 0.1605 |
| pedestal_drift_bin | ridge | 3 | high | 3.833 | low | 3.922 | 0.08853 |
| pedestal_drift_bin | traditional_cfd_template_timewalk | 3 | low | 0.9607 | high | 1.017 | 0.05585 |
| pid_sideband | 1d_cnn | 3 | central | 5.173 | high_duplicate | 10.01 | 4.833 |
| pid_sideband | edge_attention_cnn_new | 3 | central | 5.545 | high_duplicate | 10.17 | 4.626 |
| pid_sideband | waveform_transformer | 3 | high_duplicate | 6.302 | low_duplicate | 7.403 | 1.1 |
| pid_sideband | ridge | 3 | low_duplicate | 3.426 | central | 3.955 | 0.529 |
| pid_sideband | gradient_boosted_trees | 3 | central | 2.807 | high_duplicate | 3.272 | 0.4653 |
| pid_sideband | traditional_cfd_template_timewalk | 3 | low_duplicate | 0.9589 | high_duplicate | 1.079 | 0.1202 |
| pid_sideband | mlp | 3 | central | 3.426 | low_duplicate | 3.502 | 0.07612 |
| pileup_separation_bin | waveform_transformer | 4 | late | 0 | none | 7.312 | 7.312 |
| pileup_separation_bin | edge_attention_cnn_new | 4 | late | 0 | mid | 6.766 | 6.766 |
| pileup_separation_bin | 1d_cnn | 4 | late | 0 | mid | 6.653 | 6.653 |
| pileup_separation_bin | ridge | 4 | late | 0 | mid | 3.925 | 3.925 |
| pileup_separation_bin | mlp | 4 | late | 0 | close | 3.434 | 3.434 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 0 | none | 3.065 | 3.065 |
| pileup_separation_bin | traditional_cfd_template_timewalk | 4 | late | 0 | mid | 1.026 | 1.026 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.834 | compact | 7.314 | 2.48 |
| pulse_shape_class | edge_attention_cnn_new | 3 | nominal | 5.292 | compact | 7.275 | 1.982 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.508 | late_tail | 3.375 | 0.867 |
| pulse_shape_class | ridge | 3 | late_tail | 3.459 | compact | 4.182 | 0.7229 |
| pulse_shape_class | mlp | 3 | nominal | 3.139 | late_tail | 3.492 | 0.3531 |
| pulse_shape_class | waveform_transformer | 3 | compact | 6.452 | late_tail | 6.772 | 0.3193 |
| pulse_shape_class | traditional_cfd_template_timewalk | 3 | late_tail | 0.9493 | compact | 1.008 | 0.05836 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.333 | linear | 6.156 | 0.8225 |
| saturation_onset_bin | edge_attention_cnn_new | 2 | near_saturation | 5.801 | linear | 6.492 | 0.6905 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.644 | linear | 3.958 | 0.3136 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.319 | linear | 3.496 | 0.1767 |
| saturation_onset_bin | waveform_transformer | 2 | near_saturation | 6.992 | linear | 7.13 | 0.1385 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 2.816 | linear | 2.925 | 0.1088 |
| saturation_onset_bin | traditional_cfd_template_timewalk | 2 | near_saturation | 0.9546 | linear | 1.002 | 0.04741 |

## Systematic Ablations

The ablations remove correlated feature families from the gradient-boosted-tree
learner.  They test whether the frontier is driven by pretrigger pedestal
memory, late pulse-shape information, or only amplitude and CFD features.

| ablation | n_features | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| full_gradient_boosted_trees | 33 | 2.95 | 2.559 | 3.558 | 0 | 0.1434 |
| drop_tail_pulse_shape_features | 24 | 2.965 | 2.494 | 3.51 | 0.01505 | 0.1462 |
| drop_pretrigger_features | 27 | 3.515 | 3.014 | 4.216 | 0.5654 | 0.193 |
| amplitude_cfd_only | 5 | 3.751 | 3.329 | 4.658 | 0.8019 | 0.208 |

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

Runtime was `40.0 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.
