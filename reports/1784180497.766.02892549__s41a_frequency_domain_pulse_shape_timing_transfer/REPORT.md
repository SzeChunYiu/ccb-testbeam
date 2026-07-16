# S41a Frequency-Domain Pulse-Shape Timing Transfer Benchmark

## Abstract

Ticket `1784180497.766.02892549` asks whether frequency-domain pulse-shape
descriptors improve timing transfer across run, rate, and sensor conditions
without leaking pedestal or amplitude state.  This study rebuilds the registered
B-stack selected-pulse count directly from raw ROOT files, constructs a
run-held-out timing residual benchmark from the same waveforms, and compares a
strong FFT/template/CFD baseline with ridge, gradient-boosted trees, MLP,
1D-CNN, a lightweight transformer, and a new spectrogram/patch transformer proxy.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_fft_template_cfd_timewalk`** as the
winner: `sigma_68 = 0.9946 ns`
`[0.7667, 1.166]`.  The
traditional FFT/CFD/template reference obtains `0.9946 ns`
`[0.7667, 1.166]`.

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

## Estimand, Spectral Features, and Equations

Constant-fraction time at fraction `f` is the pre-peak linear interpolation

`t_f = k - 1 + (f A - y_{k-1}) / (y_k - y_{k-1})`,

where `y_t = x_t - b`, `y_{k-1} < fA <= y_k`, and the crossing index `k`
cannot exceed the waveform peak.  The prediction target is a run/stave-centered
CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

For method `m`, `epsilon_i^m = y_i - hat y_i^m`.  The resolution estimator is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

with signed bias `median(epsilon)`.  The normalized waveform
`z_t = (x_t - b) / max(A, 1)` is Hann tapered before the real FFT

`Z_k = sum_t h_t z_t exp(-2 pi i k t / 18)`.

The spectral feature set contains `log(1 + |Z_k|)`, unwrapped phase
`arg(Z_k)`, band powers, spectral entropy

`H = - sum_k p_k log(p_k) / log(K)`,

and centroid

`C = sum_k k |Z_k| / sum_k |Z_k|`.

The traditional comparator is

`hat y_trad = r_50 + g(log(1 + A)) + alpha + beta (t_0.50 - t_0.20) + gamma^T s`,

where `r_50` is the run/stave-centered CFD50 residual, `g` is a non-increasing
isotonic time-walk correction fitted on training runs, and `s` is the
standardized FFT band/phase summary vector.  The ridge penalty on `gamma`
prevents the frequency correction from silently absorbing run identifiers.

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
wander, amplitude state, and pulse-shape changes enter only through waveform
quantities: baseline displacement, pretrigger slope, normalized samples, tail
fraction, late prominence, flat-top occupancy, and FFT descriptors computed
after amplitude normalization.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_fft_template_cfd_timewalk | traditional | CFD50 residual plus monotone log-amplitude time-walk, CFD20/50 template-shape correction, and linear FFT band/phase residual correction |
| ridge | linear ML | standardized ridge regression on pedestal, amplitude, CFD, tail, pile-up, saturation, waveform samples, and FFT descriptors |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled time/frequency feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform, detector-state, and spectral summaries |
| 1d_cnn | neural waveform | compact convolutional regressor over the normalized 18-sample waveform window |
| lightweight_transformer | neural waveform | one-layer sample-attention encoder with position input and amplitude-weighted pooling |
| spectrogram_patch_transformer_new | new architecture | ticket-local spectrogram/patch proxy: gated convolutional encoder trained on waveform patches while FFT descriptors enter the tabular heads |

The lightweight transformer is included because sample attention can express
sub-window alignment without hand-specifying an onset index.  The
`spectrogram_patch_transformer_new` architecture is the ticket-specific new
model: a spectrogram/patch proxy using a gated convolutional waveform encoder
while frequency-domain patch descriptors enter the tabular heads.  This is
sensible for S41a because the ticket is explicitly about whether spectral shape
axes add transfer information beyond CFD timing and amplitude.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_fft_template_cfd_timewalk | 5466 | 0.3945 | 0.03702 | 0.7265 | 0.9946 | 0.7667 | 1.166 | 0.9863 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.2883 | -1.486 | 0.8039 | 4.024 | 3.32 | 4.668 | 5.578 | 0.2236 | 0.05379 |
| ridge | 5466 | -0.03033 | -0.9881 | 1.011 | 4.321 | 3.706 | 5.134 | 5.778 | 0.2558 | 0.06275 |
| mlp | 5466 | -0.3712 | -1.498 | 0.8025 | 4.428 | 3.843 | 5.126 | 5.735 | 0.258 | 0.06659 |
| 1d_cnn | 5466 | -0.3841 | -1.419 | 1.065 | 5.812 | 5.115 | 6.886 | 8.603 | 0.3851 | 0.1299 |
| spectrogram_patch_transformer_new | 5466 | -0.6788 | -1.562 | 0.5972 | 6.095 | 5.429 | 7.061 | 8.198 | 0.408 | 0.1411 |
| lightweight_transformer | 5466 | 1.423 | 0.6177 | 2.304 | 6.67 | 6.231 | 7.355 | 7.874 | 0.4718 | 0.1528 |

## Paired Deltas Against FFT/CFD Template

Positive `delta_sigma68_ns` means the learned method is wider than the
traditional FFT/CFD template reference under matched held-out run-block
bootstrap.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_fft_template_cfd_timewalk | 3.03 | 2.343 | 3.749 | -0.6828 | -1.853 | 0.5048 | 0.2236 |
| ridge | traditional_fft_template_cfd_timewalk | 3.326 | 2.712 | 4.184 | -0.4248 | -1.461 | 0.6442 | 0.2558 |
| mlp | traditional_fft_template_cfd_timewalk | 3.434 | 2.828 | 4.207 | -0.7657 | -1.965 | 0.4115 | 0.258 |
| 1d_cnn | traditional_fft_template_cfd_timewalk | 4.817 | 4.151 | 5.984 | -0.7786 | -1.88 | 0.6951 | 0.3851 |
| spectrogram_patch_transformer_new | traditional_fft_template_cfd_timewalk | 5.1 | 4.436 | 6.097 | -1.073 | -1.992 | 0.2133 | 0.408 |
| lightweight_transformer | traditional_fft_template_cfd_timewalk | 5.676 | 5.196 | 6.399 | 1.028 | 0.2208 | 1.96 | 0.4718 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_fft_template_cfd_timewalk | 1350 | -0.2339 | 0.8725 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 1.143 | 3.453 | 0.3022 |
| sample_i_analysis | mlp | 1350 | 1.221 | 4.306 | 0.3104 |
| sample_i_analysis | ridge | 1350 | 1.313 | 5.385 | 0.3556 |
| sample_i_analysis | 1d_cnn | 1350 | 0.1941 | 7.126 | 0.457 |
| sample_i_analysis | spectrogram_patch_transformer_new | 1350 | 0.1638 | 7.775 | 0.483 |
| sample_i_analysis | lightweight_transformer | 1350 | 1.633 | 7.968 | 0.4933 |
| sample_i_calib | traditional_fft_template_cfd_timewalk | 657 | 0.1357 | 1.379 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.499 | 4.758 | 0.3181 |
| sample_i_calib | ridge | 657 | 2.492 | 5.227 | 0.4155 |
| sample_i_calib | mlp | 657 | 1.808 | 5.535 | 0.3151 |
| sample_i_calib | lightweight_transformer | 657 | 2.698 | 7.064 | 0.4612 |
| sample_i_calib | 1d_cnn | 657 | 1.931 | 7.23 | 0.5175 |
| sample_i_calib | spectrogram_patch_transformer_new | 657 | 1.805 | 7.288 | 0.5114 |
| sample_ii_analysis | traditional_fft_template_cfd_timewalk | 2739 | 0.6181 | 0.8638 | 0 |
| sample_ii_analysis | ridge | 2739 | -0.4984 | 3.967 | 0.207 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.154 | 4.1 | 0.2037 |
| sample_ii_analysis | mlp | 2739 | -1.298 | 4.542 | 0.2618 |
| sample_ii_analysis | 1d_cnn | 2739 | -0.7375 | 5.294 | 0.341 |
| sample_ii_analysis | spectrogram_patch_transformer_new | 2739 | -1.089 | 5.596 | 0.3655 |
| sample_ii_analysis | lightweight_transformer | 2739 | 1.178 | 6.594 | 0.4845 |
| sample_ii_calib | traditional_fft_template_cfd_timewalk | 720 | 0.8248 | 0.781 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.482 | 2.712 | 0.06528 |
| sample_ii_calib | ridge | 720 | -1.176 | 2.988 | 0.1083 |
| sample_ii_calib | mlp | 720 | -1.544 | 3.448 | 0.09306 |
| sample_ii_calib | 1d_cnn | 720 | -1.533 | 4.255 | 0.2972 |
| sample_ii_calib | spectrogram_patch_transformer_new | 720 | -1.775 | 4.6 | 0.3347 |
| sample_ii_calib | lightweight_transformer | 720 | 1.028 | 5.907 | 0.3931 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.931 | 7.23 | 0.5175 |
| 1d_cnn | 50 | 680 | -1.729 | 11.93 | 0.4294 |
| 1d_cnn | 57 | 670 | 2.978 | 6.199 | 0.4851 |
| 1d_cnn | 58 | 654 | -2.923 | 5.813 | 0.4281 |
| 1d_cnn | 60 | 720 | 0.1548 | 5.017 | 0.3278 |
| 1d_cnn | 62 | 720 | -0.0838 | 4.68 | 0.3014 |
| 1d_cnn | 64 | 720 | -1.533 | 4.255 | 0.2972 |
| 1d_cnn | 65 | 645 | -0.2973 | 5.102 | 0.3116 |
| gradient_boosted_trees | 42 | 657 | 1.499 | 4.758 | 0.3181 |
| gradient_boosted_trees | 50 | 680 | 0.7131 | 11.37 | 0.3044 |
| gradient_boosted_trees | 57 | 670 | 1.51 | 4.276 | 0.3 |
| gradient_boosted_trees | 58 | 654 | -3.356 | 2.974 | 0.2538 |
| gradient_boosted_trees | 60 | 720 | -0.3088 | 4.467 | 0.2569 |
| gradient_boosted_trees | 62 | 720 | -0.2841 | 3.109 | 0.08889 |
| gradient_boosted_trees | 64 | 720 | -1.482 | 2.712 | 0.06528 |
| gradient_boosted_trees | 65 | 645 | -1.463 | 4.538 | 0.2217 |
| lightweight_transformer | 42 | 657 | 2.698 | 7.064 | 0.4612 |
| lightweight_transformer | 50 | 680 | 0.649 | 11.71 | 0.4603 |
| lightweight_transformer | 57 | 670 | 3.659 | 6.935 | 0.5269 |
| lightweight_transformer | 58 | 654 | -0.8167 | 6.661 | 0.4618 |
| lightweight_transformer | 60 | 720 | 1.397 | 6.722 | 0.5042 |
| lightweight_transformer | 62 | 720 | 1.815 | 6.257 | 0.4861 |
| lightweight_transformer | 64 | 720 | 1.028 | 5.907 | 0.3931 |
| lightweight_transformer | 65 | 645 | 2.177 | 6.169 | 0.4837 |
| mlp | 42 | 657 | 1.808 | 5.535 | 0.3151 |
| mlp | 50 | 680 | 0.1956 | 11.32 | 0.3206 |
| mlp | 57 | 670 | 1.819 | 5.031 | 0.3 |
| mlp | 58 | 654 | -2.736 | 3.861 | 0.2722 |
| mlp | 60 | 720 | -0.6869 | 4.879 | 0.2681 |
| mlp | 62 | 720 | -0.3996 | 3.98 | 0.1889 |
| mlp | 64 | 720 | -1.544 | 3.448 | 0.09306 |
| mlp | 65 | 645 | -1.595 | 5.065 | 0.3256 |
| ridge | 42 | 657 | 2.492 | 5.227 | 0.4155 |
| ridge | 50 | 680 | -0.6098 | 11.83 | 0.3574 |
| ridge | 57 | 670 | 2.76 | 4.799 | 0.3537 |
| ridge | 58 | 654 | -2.308 | 4.225 | 0.3012 |
| ridge | 60 | 720 | -0.1942 | 3.765 | 0.1917 |
| ridge | 62 | 720 | -0.05444 | 3.511 | 0.1306 |
| ridge | 64 | 720 | -1.176 | 2.988 | 0.1083 |
| ridge | 65 | 645 | -0.1081 | 3.951 | 0.214 |
| spectrogram_patch_transformer_new | 42 | 657 | 1.805 | 7.288 | 0.5114 |
| spectrogram_patch_transformer_new | 50 | 680 | -1.513 | 12.23 | 0.4647 |
| spectrogram_patch_transformer_new | 57 | 670 | 2.666 | 6.587 | 0.5015 |
| spectrogram_patch_transformer_new | 58 | 654 | -3.206 | 5.902 | 0.4526 |
| spectrogram_patch_transformer_new | 60 | 720 | -0.2562 | 5.362 | 0.35 |
| spectrogram_patch_transformer_new | 62 | 720 | -0.3103 | 5.188 | 0.3264 |
| spectrogram_patch_transformer_new | 64 | 720 | -1.775 | 4.6 | 0.3347 |
| spectrogram_patch_transformer_new | 65 | 645 | -1.004 | 5.243 | 0.338 |
| traditional_fft_template_cfd_timewalk | 42 | 657 | 0.1357 | 1.379 | 0 |
| traditional_fft_template_cfd_timewalk | 50 | 680 | 0.1808 | 0.5488 | 0 |
| traditional_fft_template_cfd_timewalk | 57 | 670 | -0.9184 | 1.04 | 0 |
| traditional_fft_template_cfd_timewalk | 58 | 654 | 0.9064 | 0.8978 | 0 |
| traditional_fft_template_cfd_timewalk | 60 | 720 | 0.3893 | 1.061 | 0 |
| traditional_fft_template_cfd_timewalk | 62 | 720 | 0.3497 | 0.8324 | 0 |
| traditional_fft_template_cfd_timewalk | 64 | 720 | 0.8248 | 0.781 | 0 |
| traditional_fft_template_cfd_timewalk | 65 | 645 | 0.8659 | 0.4365 | 0 |

## Pedestal and Pulse-Shape Stress Tables

Stress axes are raw-waveform proxies: pedestal drift is absolute baseline
displacement from the run/stave median; pulse-shape class is late-tail fraction;
pile-up proximity is late secondary prominence spacing; saturation onset is
high amplitude or flat-top occupancy; energy proxy is amplitude quartile; PID
sideband is duplicate-readout amplitude ratio; spectral centroid and phase
slope are frequency-domain stability axes.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| energy_bin | q1_low | 1d_cnn | 1416 | -0.7232 | 7.259 | 0.4619 |
| energy_bin | q1_low | gradient_boosted_trees | 1416 | -0.382 | 4.171 | 0.2288 |
| energy_bin | q1_low | lightweight_transformer | 1416 | 1.144 | 6.278 | 0.4449 |
| energy_bin | q1_low | mlp | 1416 | -0.4199 | 4.406 | 0.2549 |
| energy_bin | q1_low | ridge | 1416 | 0.5358 | 4.322 | 0.2705 |
| energy_bin | q1_low | spectrogram_patch_transformer_new | 1416 | -1.988 | 6.82 | 0.5106 |
| energy_bin | q1_low | traditional_fft_template_cfd_timewalk | 1416 | 0.04803 | 1.056 | 0 |
| energy_bin | q2 | 1d_cnn | 1507 | -0.5246 | 5.178 | 0.3358 |
| energy_bin | q2 | gradient_boosted_trees | 1507 | -0.1785 | 4.043 | 0.219 |
| energy_bin | q2 | lightweight_transformer | 1507 | 3.257 | 5.559 | 0.495 |
| energy_bin | q2 | mlp | 1507 | -0.5921 | 4.67 | 0.2774 |
| energy_bin | q2 | ridge | 1507 | 0.2275 | 4.254 | 0.2522 |
| energy_bin | q2 | spectrogram_patch_transformer_new | 1507 | -1.011 | 5.146 | 0.3444 |
| energy_bin | q2 | traditional_fft_template_cfd_timewalk | 1507 | 0.4903 | 0.879 | 0 |
| energy_bin | q3 | 1d_cnn | 1441 | 1.578 | 4.92 | 0.3081 |
| energy_bin | q3 | gradient_boosted_trees | 1441 | -0.2143 | 3.911 | 0.211 |
| energy_bin | q3 | lightweight_transformer | 1441 | 3.004 | 6.408 | 0.5094 |
| energy_bin | q3 | mlp | 1441 | 0.003671 | 4.468 | 0.2519 |
| energy_bin | q3 | ridge | 1441 | -0.1566 | 4.487 | 0.2609 |
| energy_bin | q3 | spectrogram_patch_transformer_new | 1441 | 1.56 | 4.98 | 0.3269 |
| energy_bin | q3 | traditional_fft_template_cfd_timewalk | 1441 | 0.6008 | 0.9852 | 0 |
| energy_bin | q4_high | 1d_cnn | 1102 | -2.502 | 6.248 | 0.4546 |
| energy_bin | q4_high | gradient_boosted_trees | 1102 | -0.4603 | 3.879 | 0.2396 |
| energy_bin | q4_high | lightweight_transformer | 1102 | -2.888 | 5.798 | 0.4256 |
| energy_bin | q4_high | mlp | 1102 | -0.5821 | 4.095 | 0.2432 |
| energy_bin | q4_high | ridge | 1102 | -1.008 | 4.281 | 0.235 |
| energy_bin | q4_high | spectrogram_patch_transformer_new | 1102 | -1.764 | 6.699 | 0.4691 |
| energy_bin | q4_high | traditional_fft_template_cfd_timewalk | 1102 | 0.3878 | 1.031 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1704 | 0.7424 | 7.163 | 0.4701 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1704 | -0.04336 | 4.456 | 0.257 |
| pedestal_drift_bin | high | lightweight_transformer | 1704 | -0.6925 | 7.514 | 0.5346 |
| pedestal_drift_bin | high | mlp | 1704 | -0.03459 | 4.67 | 0.277 |
| pedestal_drift_bin | high | ridge | 1704 | 0.2481 | 4.539 | 0.2823 |
| pedestal_drift_bin | high | spectrogram_patch_transformer_new | 1704 | 0.08235 | 7.851 | 0.4982 |
| pedestal_drift_bin | high | traditional_fft_template_cfd_timewalk | 1704 | 0.367 | 1.045 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1770 | -0.8471 | 5.186 | 0.3446 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1770 | -0.5996 | 3.817 | 0.2073 |
| pedestal_drift_bin | low | lightweight_transformer | 1770 | 1.872 | 5.679 | 0.4243 |
| pedestal_drift_bin | low | mlp | 1770 | -0.6337 | 4.059 | 0.2367 |
| pedestal_drift_bin | low | ridge | 1770 | -0.1754 | 4.191 | 0.2458 |
| pedestal_drift_bin | low | spectrogram_patch_transformer_new | 1770 | -1.004 | 5.509 | 0.3757 |
| pedestal_drift_bin | low | traditional_fft_template_cfd_timewalk | 1770 | 0.3878 | 0.9906 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1992 | -0.8134 | 5.268 | 0.3484 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1992 | -0.218 | 3.844 | 0.2093 |
| pedestal_drift_bin | mid | lightweight_transformer | 1992 | 2.329 | 5.914 | 0.4603 |
| pedestal_drift_bin | mid | mlp | 1992 | -0.5461 | 4.534 | 0.2605 |
| pedestal_drift_bin | mid | ridge | 1992 | -0.1044 | 4.199 | 0.242 |
| pedestal_drift_bin | mid | spectrogram_patch_transformer_new | 1992 | -0.8402 | 5.432 | 0.3594 |
| pedestal_drift_bin | mid | traditional_fft_template_cfd_timewalk | 1992 | 0.4493 | 0.9518 | 0 |
| phase_slope_bin | central | 1d_cnn | 1557 | -0.265 | 5.99 | 0.3976 |
| phase_slope_bin | central | gradient_boosted_trees | 1557 | -0.5485 | 3.893 | 0.2312 |
| phase_slope_bin | central | lightweight_transformer | 1557 | -0.3214 | 6.279 | 0.4464 |
| phase_slope_bin | central | mlp | 1557 | -0.8222 | 4.486 | 0.264 |
| phase_slope_bin | central | ridge | 1557 | -0.2034 | 4.627 | 0.282 |
| phase_slope_bin | central | spectrogram_patch_transformer_new | 1557 | -0.4978 | 6.045 | 0.4066 |
| phase_slope_bin | central | traditional_fft_template_cfd_timewalk | 1557 | 0.4107 | 1.047 | 0 |
| phase_slope_bin | negative | 1d_cnn | 2262 | -1.358 | 5.011 | 0.3232 |
| phase_slope_bin | negative | gradient_boosted_trees | 2262 | -0.6282 | 3.476 | 0.1477 |
| phase_slope_bin | negative | lightweight_transformer | 2262 | 2.576 | 5.366 | 0.4293 |
| phase_slope_bin | negative | mlp | 2262 | -0.8187 | 4.016 | 0.2091 |
| phase_slope_bin | negative | ridge | 2262 | -0.5146 | 3.822 | 0.1958 |
| phase_slope_bin | negative | spectrogram_patch_transformer_new | 2262 | -1.518 | 5.121 | 0.3448 |
| phase_slope_bin | negative | traditional_fft_template_cfd_timewalk | 2262 | 0.5931 | 0.9452 | 0 |
| phase_slope_bin | positive | 1d_cnn | 1647 | 1.127 | 7.152 | 0.4584 |
| phase_slope_bin | positive | gradient_boosted_trees | 1647 | 0.6843 | 4.878 | 0.3206 |
| phase_slope_bin | positive | lightweight_transformer | 1647 | 1.237 | 8.313 | 0.5543 |
| phase_slope_bin | positive | mlp | 1647 | 0.6946 | 4.952 | 0.3194 |
| phase_slope_bin | positive | ridge | 1647 | 0.9251 | 4.807 | 0.3133 |
| phase_slope_bin | positive | spectrogram_patch_transformer_new | 1647 | 0.9431 | 7.906 | 0.4961 |
| phase_slope_bin | positive | traditional_fft_template_cfd_timewalk | 1647 | 0.202 | 0.9947 | 0 |
| pid_sideband | central | 1d_cnn | 3718 | -0.558 | 5.336 | 0.3526 |
| pid_sideband | central | gradient_boosted_trees | 3718 | -0.2975 | 3.843 | 0.209 |
| pid_sideband | central | lightweight_transformer | 3718 | 2.42 | 5.618 | 0.4449 |
| pid_sideband | central | mlp | 3718 | -0.3422 | 4.292 | 0.2445 |
| pid_sideband | central | ridge | 3718 | 0.05269 | 4.27 | 0.2504 |
| pid_sideband | central | spectrogram_patch_transformer_new | 3718 | -0.6882 | 5.522 | 0.3679 |
| pid_sideband | central | traditional_fft_template_cfd_timewalk | 3718 | 0.3711 | 0.9683 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 891 | 1.915 | 8.652 | 0.5791 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 891 | -0.03466 | 4.457 | 0.2907 |
| pid_sideband | high_duplicate | lightweight_transformer | 891 | -5.199 | 6.254 | 0.587 |
| pid_sideband | high_duplicate | mlp | 891 | -0.2466 | 4.861 | 0.3086 |
| pid_sideband | high_duplicate | ridge | 891 | -0.1127 | 5.06 | 0.3199 |
| pid_sideband | high_duplicate | spectrogram_patch_transformer_new | 891 | 0.2292 | 10.16 | 0.6341 |
| pid_sideband | high_duplicate | traditional_fft_template_cfd_timewalk | 891 | 0.308 | 1.08 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 857 | -1.165 | 5.432 | 0.3244 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 857 | -0.4333 | 3.902 | 0.217 |
| pid_sideband | low_duplicate | lightweight_transformer | 857 | 1.94 | 6.255 | 0.4691 |
| pid_sideband | low_duplicate | mlp | 857 | -0.6976 | 4.461 | 0.2637 |
| pid_sideband | low_duplicate | ridge | 857 | -0.2166 | 4.044 | 0.2124 |
| pid_sideband | low_duplicate | spectrogram_patch_transformer_new | 857 | -1.082 | 5.591 | 0.3466 |
| pid_sideband | low_duplicate | traditional_fft_template_cfd_timewalk | 857 | 0.5836 | 0.9911 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1690 | -1.717 | 5.678 | 0.3828 |
| pileup_separation_bin | close | gradient_boosted_trees | 1690 | -0.5265 | 3.766 | 0.2041 |
| pileup_separation_bin | close | lightweight_transformer | 1690 | 1.027 | 6.136 | 0.4284 |
| pileup_separation_bin | close | mlp | 1690 | -0.8639 | 4.454 | 0.2408 |
| pileup_separation_bin | close | ridge | 1690 | -0.6314 | 4.373 | 0.245 |
| pileup_separation_bin | close | spectrogram_patch_transformer_new | 1690 | -1.724 | 5.681 | 0.3846 |
| pileup_separation_bin | close | traditional_fft_template_cfd_timewalk | 1690 | 0.5474 | 1.003 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1165 | 1.333 | 5.681 | 0.3691 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1165 | -0.8493 | 3.852 | 0.2172 |
| pileup_separation_bin | mid | lightweight_transformer | 1165 | -2.595 | 6.871 | 0.5236 |
| pileup_separation_bin | mid | mlp | 1165 | -0.9363 | 4.342 | 0.2446 |
| pileup_separation_bin | mid | ridge | 1165 | -0.7001 | 4.398 | 0.2584 |
| pileup_separation_bin | mid | spectrogram_patch_transformer_new | 1165 | 1.565 | 5.936 | 0.4103 |
| pileup_separation_bin | mid | traditional_fft_template_cfd_timewalk | 1165 | 0.7 | 1.001 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2611 | -0.2456 | 6.098 | 0.3937 |
| pileup_separation_bin | none | gradient_boosted_trees | 2611 | 0.1415 | 4.121 | 0.239 |
| pileup_separation_bin | none | lightweight_transformer | 2611 | 2.982 | 5.464 | 0.4768 |
| pileup_separation_bin | none | mlp | 2611 | 0.165 | 4.327 | 0.275 |
| pileup_separation_bin | none | ridge | 2611 | 0.685 | 4.012 | 0.2616 |
| pileup_separation_bin | none | spectrogram_patch_transformer_new | 2611 | -0.8257 | 6.217 | 0.4221 |
| pileup_separation_bin | none | traditional_fft_template_cfd_timewalk | 2611 | 0.2787 | 0.9754 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1857 | 0.03342 | 7.109 | 0.4626 |
| pulse_shape_class | compact | gradient_boosted_trees | 1857 | -0.7442 | 4.286 | 0.2396 |
| pulse_shape_class | compact | lightweight_transformer | 1857 | -0.3859 | 7.041 | 0.5094 |
| pulse_shape_class | compact | mlp | 1857 | -0.9702 | 4.723 | 0.2709 |
| pulse_shape_class | compact | ridge | 1857 | -0.09665 | 4.897 | 0.3091 |
| pulse_shape_class | compact | spectrogram_patch_transformer_new | 1857 | -1.053 | 7.333 | 0.4943 |
| pulse_shape_class | compact | traditional_fft_template_cfd_timewalk | 1857 | 0.403 | 1.036 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1789 | -0.1904 | 6.49 | 0.3974 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1789 | 0.4597 | 4.362 | 0.2633 |
| pulse_shape_class | late_tail | lightweight_transformer | 1789 | 2.329 | 6.427 | 0.4695 |
| pulse_shape_class | late_tail | mlp | 1789 | 0.7408 | 4.341 | 0.2767 |
| pulse_shape_class | late_tail | ridge | 1789 | 0.3164 | 4.078 | 0.2683 |
| pulse_shape_class | late_tail | spectrogram_patch_transformer_new | 1789 | -0.1846 | 6.395 | 0.4136 |
| pulse_shape_class | late_tail | traditional_fft_template_cfd_timewalk | 1789 | 0.3262 | 0.9968 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1820 | -1.086 | 4.609 | 0.294 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1820 | -0.6434 | 3.418 | 0.1681 |
| pulse_shape_class | nominal | lightweight_transformer | 1820 | 1.896 | 5.831 | 0.4357 |
| pulse_shape_class | nominal | mlp | 1820 | -0.9691 | 3.988 | 0.2264 |
| pulse_shape_class | nominal | ridge | 1820 | -0.4014 | 3.997 | 0.189 |
| pulse_shape_class | nominal | spectrogram_patch_transformer_new | 1820 | -0.8258 | 4.882 | 0.3143 |
| pulse_shape_class | nominal | traditional_fft_template_cfd_timewalk | 1820 | 0.524 | 0.9232 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3964 | -0.1229 | 6.179 | 0.4001 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3964 | -0.3557 | 4.123 | 0.2311 |
| saturation_onset_bin | linear | lightweight_transformer | 3964 | 1.273 | 6.86 | 0.4768 |
| saturation_onset_bin | linear | mlp | 3964 | -0.443 | 4.469 | 0.2593 |
| saturation_onset_bin | linear | ridge | 3964 | -0.09983 | 4.377 | 0.2649 |
| saturation_onset_bin | linear | spectrogram_patch_transformer_new | 3964 | -0.5382 | 6.36 | 0.4296 |
| saturation_onset_bin | linear | traditional_fft_template_cfd_timewalk | 3964 | 0.4269 | 1.001 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1502 | -1.047 | 5.273 | 0.3455 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1502 | -0.1783 | 3.807 | 0.2037 |
| saturation_onset_bin | near_saturation | lightweight_transformer | 1502 | 1.819 | 6.153 | 0.4587 |
| saturation_onset_bin | near_saturation | mlp | 1502 | -0.2406 | 4.246 | 0.2543 |
| saturation_onset_bin | near_saturation | ridge | 1502 | 0.1874 | 4.205 | 0.2317 |
| saturation_onset_bin | near_saturation | spectrogram_patch_transformer_new | 1502 | -1.096 | 5.445 | 0.3509 |
| saturation_onset_bin | near_saturation | traditional_fft_template_cfd_timewalk | 1502 | 0.3654 | 0.9767 | 0 |
| spectral_centroid_bin | high | 1d_cnn | 1593 | -0.8905 | 7.553 | 0.452 |
| spectral_centroid_bin | high | gradient_boosted_trees | 1593 | 0.4752 | 4.433 | 0.2668 |
| spectral_centroid_bin | high | lightweight_transformer | 1593 | 1.1 | 6.985 | 0.4601 |
| spectral_centroid_bin | high | mlp | 1593 | 0.7961 | 4.272 | 0.2712 |
| spectral_centroid_bin | high | ridge | 1593 | 0.5909 | 4.325 | 0.2768 |
| spectral_centroid_bin | high | spectrogram_patch_transformer_new | 1593 | -0.9758 | 7.492 | 0.4614 |
| spectral_centroid_bin | high | traditional_fft_template_cfd_timewalk | 1593 | 0.2894 | 1.027 | 0 |
| spectral_centroid_bin | low | 1d_cnn | 2049 | -0.9519 | 5.407 | 0.3826 |
| spectral_centroid_bin | low | gradient_boosted_trees | 2049 | -0.8166 | 3.946 | 0.2016 |
| spectral_centroid_bin | low | lightweight_transformer | 2049 | 1.393 | 6.356 | 0.4705 |
| spectral_centroid_bin | low | mlp | 2049 | -1.006 | 4.662 | 0.2567 |
| spectral_centroid_bin | low | ridge | 2049 | 0.09036 | 4.342 | 0.2533 |
| spectral_centroid_bin | low | spectrogram_patch_transformer_new | 2049 | -1.834 | 5.508 | 0.4275 |
| spectral_centroid_bin | low | traditional_fft_template_cfd_timewalk | 2049 | 0.4644 | 0.9882 | 0 |
| spectral_centroid_bin | mid | 1d_cnn | 1824 | 0.4715 | 5.233 | 0.3295 |
| spectral_centroid_bin | mid | gradient_boosted_trees | 1824 | -0.3807 | 3.836 | 0.2105 |
| spectral_centroid_bin | mid | lightweight_transformer | 1824 | 1.866 | 6.796 | 0.4836 |
| spectral_centroid_bin | mid | mlp | 1824 | -0.6792 | 4.28 | 0.2478 |
| spectral_centroid_bin | mid | ridge | 1824 | -0.6482 | 4.274 | 0.2401 |
| spectral_centroid_bin | mid | spectrogram_patch_transformer_new | 1824 | 0.6564 | 5.188 | 0.3394 |
| spectral_centroid_bin | mid | traditional_fft_template_cfd_timewalk | 1824 | 0.5261 | 1.003 | 0 |

Axis-compressed view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| energy_bin | 1d_cnn | 4 | q3 | 4.92 | q1_low | 7.259 | 2.339 |
| energy_bin | spectrogram_patch_transformer_new | 4 | q3 | 4.98 | q1_low | 6.82 | 1.84 |
| energy_bin | lightweight_transformer | 4 | q2 | 5.559 | q3 | 6.408 | 0.8488 |
| energy_bin | mlp | 4 | q4_high | 4.095 | q2 | 4.67 | 0.5753 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.879 | q1_low | 4.171 | 0.2917 |
| energy_bin | ridge | 4 | q2 | 4.254 | q3 | 4.487 | 0.2327 |
| energy_bin | traditional_fft_template_cfd_timewalk | 4 | q2 | 0.879 | q1_low | 1.056 | 0.1768 |
| pedestal_drift_bin | spectrogram_patch_transformer_new | 3 | mid | 5.432 | high | 7.851 | 2.418 |
| pedestal_drift_bin | 1d_cnn | 3 | low | 5.186 | high | 7.163 | 1.977 |
| pedestal_drift_bin | lightweight_transformer | 3 | low | 5.679 | high | 7.514 | 1.836 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.817 | high | 4.456 | 0.639 |
| pedestal_drift_bin | mlp | 3 | low | 4.059 | high | 4.67 | 0.611 |
| pedestal_drift_bin | ridge | 3 | low | 4.191 | high | 4.539 | 0.348 |
| pedestal_drift_bin | traditional_fft_template_cfd_timewalk | 3 | mid | 0.9518 | high | 1.045 | 0.09342 |
| phase_slope_bin | lightweight_transformer | 3 | negative | 5.366 | positive | 8.313 | 2.946 |
| phase_slope_bin | spectrogram_patch_transformer_new | 3 | negative | 5.121 | positive | 7.906 | 2.785 |
| phase_slope_bin | 1d_cnn | 3 | negative | 5.011 | positive | 7.152 | 2.141 |
| phase_slope_bin | gradient_boosted_trees | 3 | negative | 3.476 | positive | 4.878 | 1.402 |
| phase_slope_bin | ridge | 3 | negative | 3.822 | positive | 4.807 | 0.9851 |
| phase_slope_bin | mlp | 3 | negative | 4.016 | positive | 4.952 | 0.9368 |
| phase_slope_bin | traditional_fft_template_cfd_timewalk | 3 | negative | 0.9452 | central | 1.047 | 0.1015 |
| pid_sideband | spectrogram_patch_transformer_new | 3 | central | 5.522 | high_duplicate | 10.16 | 4.641 |
| pid_sideband | 1d_cnn | 3 | central | 5.336 | high_duplicate | 8.652 | 3.316 |
| pid_sideband | ridge | 3 | low_duplicate | 4.044 | high_duplicate | 5.06 | 1.017 |
| pid_sideband | lightweight_transformer | 3 | central | 5.618 | low_duplicate | 6.255 | 0.6368 |
| pid_sideband | gradient_boosted_trees | 3 | central | 3.843 | high_duplicate | 4.457 | 0.6141 |
| pid_sideband | mlp | 3 | central | 4.292 | high_duplicate | 4.861 | 0.5693 |
| pid_sideband | traditional_fft_template_cfd_timewalk | 3 | central | 0.9683 | high_duplicate | 1.08 | 0.1122 |
| pileup_separation_bin | lightweight_transformer | 3 | none | 5.464 | mid | 6.871 | 1.407 |
| pileup_separation_bin | spectrogram_patch_transformer_new | 3 | close | 5.681 | none | 6.217 | 0.5359 |
| pileup_separation_bin | 1d_cnn | 3 | close | 5.678 | none | 6.098 | 0.4203 |
| pileup_separation_bin | ridge | 3 | none | 4.012 | mid | 4.398 | 0.3861 |
| pileup_separation_bin | gradient_boosted_trees | 3 | close | 3.766 | none | 4.121 | 0.3554 |
| pileup_separation_bin | mlp | 3 | none | 4.327 | close | 4.454 | 0.1267 |
| pileup_separation_bin | traditional_fft_template_cfd_timewalk | 3 | none | 0.9754 | close | 1.003 | 0.02745 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.609 | compact | 7.109 | 2.5 |
| pulse_shape_class | spectrogram_patch_transformer_new | 3 | nominal | 4.882 | compact | 7.333 | 2.451 |
| pulse_shape_class | lightweight_transformer | 3 | nominal | 5.831 | compact | 7.041 | 1.21 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.418 | late_tail | 4.362 | 0.9443 |
| pulse_shape_class | ridge | 3 | nominal | 3.997 | compact | 4.897 | 0.8999 |
| pulse_shape_class | mlp | 3 | nominal | 3.988 | compact | 4.723 | 0.7344 |
| pulse_shape_class | traditional_fft_template_cfd_timewalk | 3 | nominal | 0.9232 | compact | 1.036 | 0.1125 |
| saturation_onset_bin | spectrogram_patch_transformer_new | 2 | near_saturation | 5.445 | linear | 6.36 | 0.9143 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.273 | linear | 6.179 | 0.9067 |
| saturation_onset_bin | lightweight_transformer | 2 | near_saturation | 6.153 | linear | 6.86 | 0.7072 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.807 | linear | 4.123 | 0.3159 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.246 | linear | 4.469 | 0.223 |
| saturation_onset_bin | ridge | 2 | near_saturation | 4.205 | linear | 4.377 | 0.1713 |
| saturation_onset_bin | traditional_fft_template_cfd_timewalk | 2 | near_saturation | 0.9767 | linear | 1.001 | 0.02401 |
| spectral_centroid_bin | 1d_cnn | 3 | mid | 5.233 | high | 7.553 | 2.32 |
| spectral_centroid_bin | spectrogram_patch_transformer_new | 3 | mid | 5.188 | high | 7.492 | 2.304 |
| spectral_centroid_bin | lightweight_transformer | 3 | low | 6.356 | high | 6.985 | 0.6289 |
| spectral_centroid_bin | gradient_boosted_trees | 3 | mid | 3.836 | high | 4.433 | 0.5975 |
| spectral_centroid_bin | mlp | 3 | high | 4.272 | low | 4.662 | 0.3897 |
| spectral_centroid_bin | ridge | 3 | mid | 4.274 | low | 4.342 | 0.06797 |
| spectral_centroid_bin | traditional_fft_template_cfd_timewalk | 3 | low | 0.9882 | high | 1.027 | 0.03854 |

## Systematic Ablations

The ablations use the gradient-boosted-tree learner and remove or isolate
feature families to test whether learned timing is mostly pretrigger leakage,
amplitude-normalized spectra, phase information, or ordinary time-domain
interpolation.

| ablation | n_features | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| phase_randomized_spectra | 49 | 3.954 | 3.298 | 4.564 | -0.01359 | 0.2168 |
| full_spectral_gradient_boosted_trees | 59 | 3.967 | 3.266 | 4.654 | 0 | 0.2144 |
| time_domain_no_fft | 33 | 3.969 | 3.305 | 4.597 | 0.001508 | 0.212 |
| amplitude_normalized_spectra_only | 17 | 4.87 | 4.339 | 5.564 | 0.9025 | 0.3079 |
| pretrigger_only | 6 | 17.73 | 15.05 | 25.8 | 13.77 | 0.6787 |

## Interpretation, Systematics, and Caveats

This is a comparative frequency-domain alignment benchmark, not an external timing-truth
measurement.  The ROOT tree provides digitized waveforms but not independent
particle truth, electronics-state labels, or picosecond reference timing.
Therefore, the analysis supports claims about relative method behavior on a
reproducible waveform-derived residual, not absolute beamline timing.

The run-block bootstrap targets transfer across data-taking periods and can be
wider than event-level uncertainty.  Small strata, especially close pile-up and
near-saturation levels, must be interpreted with their row counts.  Neural
models are compact and trained on a fixed small epoch budget; this tests whether
frequency-domain descriptors naturally beat a strong FFT/CFD/template
construction under run transfer, not whether exhaustive neural architecture
search can eventually overfit this proxy target.

Runtime was `47.2 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.11.14`.
