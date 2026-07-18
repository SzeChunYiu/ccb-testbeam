# S44b: Tail-Kernel Pile-Up Saturation Energy Recovery Benchmark

## Abstract

Ticket `1784345719.678.41db1ffe` asks whether explicit exponential tail kernels can separate unresolved pile-up from saturation recovery without biasing the recovered energy scale. I reproduced the raw ROOT selected-pulse anchor, generated controlled pile-up/saturation overlays from raw-derived clean B-stave pulses, and compared a strong traditional tail-kernel/censored-template method against ridge regression, gradient-boosted trees, MLP, 1D-CNN, a sequence transformer, and a new hybrid residual-fusion architecture. The held-out winner written to `result.json` is **`tail_kernel_residual_fusion_new`**.

## Raw ROOT Reproduction

Raw files were read from `/home/billy/ccb-data/extracted/root/root`. For each `hrdb_run_*.root` file, `h101/HRDv` was reshaped to `(event, channel, sample)` with 18 samples. The B-stave selected-pulse gate uses B2/B4/B6/B8 pedestal subtraction,

`b_ec = median_{t in {0,1,2,3}} x_ect`,

and selected-pulse indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity | reference | reproduced | delta | pass |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | true |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | true |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | true |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | true |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | true |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | true |

## Split and Controlled Truth

The split is by source run, not by event. Training runs are `50, 51, 52, 53, 54, 55, 56, 57`; held-out runs are `58, 60, 62, 64, 65`. Clean train-run templates are median CFD-aligned raw pulses:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave | n train pulses | CFD20 sample | peak sample | template area |
|---|---:|---:|---:|---:|
| B2 | 800 | 2.599 | 5 | 9.149 |
| B4 | 784 | 2.982 | 6 | 10.78 |
| B6 | 751 | 3.747 | 6 | 9.739 |
| B8 | 482 | 4.236 | 8 | 9.253 |

Controlled doublets use raw-derived residuals:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

then the observed waveform is clipped by `w_obs(t) = min(w(t), 11800)`. Clean single-pulse controls from the same run distribution provide the false-split denominator.

## Methods

| method | family | description |
|---|---|---|
| tail_kernel_censored_template_traditional | traditional | bounded two-template deconvolution with exponential tail kernels, clipped-sample censoring, and chi-square cuts |
| ridge | linear ML | ridge classifier plus multi-output ridge regression |
| gradient_boosted_trees | tree ML | histogram gradient-boosted classifier and regressors |
| mlp | neural network | tabular multilayer perceptron classifier/regressor pair |
| 1d_cnn | neural network | compact one-dimensional CNN over the 18 ADC samples |
| tiny_sequence_transformer | sequence NN | one-layer self-attention encoder over waveform samples |
| tail_kernel_residual_fusion_new | new hybrid | boosted residual fusion of waveform summaries, clipping sidebands, exponential tail kernels, and traditional fit outputs |

The traditional comparator minimizes one- and two-pulse least-squares objectives,

`SSE_k = sum_t [w_obs(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

and uses `SSE_2 / SSE_1` as a goodness/censoring cut. Tail kernels are

`K_tau(t; t_p) = exp[-max(t-t_p,0)/tau]`, for `tau in {1.5, 3.0, 6.0}` samples,

with projections

`z_tau = sum_t (w_obs(t)-b)_+ K_tau(t;t_p) / sum_t K_tau(t;t_p)`.

The censored amplitude correction is

`A'_j = A_j [1 + 0.017 n_clip + 0.032 max(W_plateau-2,0) + 0.055 f_tail + 0.030 max((z_6-z_1.5)/z_3,0)]`.

The new hybrid is sensible because the analytic fit identifies pulse constituents, while tail-kernel projections and clipping sidebands carry residual information about charge hidden above the ADC ceiling.

## Endpoints

For accepted injected doublets, recovered-amplitude error is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Pile-up separation error is

`e_Delta = 10 ns * [(hat t_2 - hat t_1) - Delta]`.

Robust resolution is

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

Confidence intervals are percentile 95% intervals from 400 held-out run-block bootstrap resamples. The winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.004 sigma_Delta + 0.004 sigma_t1 + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID`,

where `r_miss` is merge/miss rate, `r_false` is false split rate, `S_ped` is pedestal-state false-split span, and `S_PID` is the PID-proxy energy-bias span.

## Overall Results

| method | winner score | energy bias | energy sigma68 [95% CI] | pile-up sep sigma68 ns | miss rate | false split rate | PID bias span |
|---|---:|---:|---:|---:|---:|---:|---:|
| tail_kernel_residual_fusion_new | 0.1703 | 0.01088 | 0.07003 [0.06293, 0.07673] | 11.57 | 0.3317 | 0.1537 | 0.04466 |
| gradient_boosted_trees | 0.1755 | 0.004414 | 0.07855 [0.06925, 0.09295] | 10.68 | 0.3317 | 0.1805 | 0.07295 |
| ridge | 0.2041 | 0.008396 | 0.08133 [0.07333, 0.08747] | 14.25 | 0.3146 | 0.1805 | 0.06822 |
| 1d_cnn | 0.2217 | 0.03747 | 0.09276 [0.08185, 0.09771] | 14.54 | 0.2561 | 0.2927 | 0.07438 |
| mlp | 0.2415 | -0.007436 | 0.1025 [0.08884, 0.1138] | 15.43 | 0.3220 | 0.1927 | 0.05915 |
| tail_kernel_censored_template_traditional | 0.2655 | 0.07329 | 0.1146 [0.09283, 0.1245] | 15.00 | 0.5610 | 0.1585 | 0.1069 |
| tiny_sequence_transformer | 0.2967 | 0.01100 | 0.1117 [0.1065, 0.1203] | 23.23 | 0.3512 | 0.2073 | 0.1058 |

## Ticket-Specific Endpoint Table

| method | recovered amplitude bias [95% CI] | recovered amp sigma68 | saturation-depth bias [95% CI] | pile-up separation sigma68 ns [95% CI] | PID failure-rate span |
|---|---:|---:|---:|---:|---:|
| tail_kernel_residual_fusion_new | 0.01088 [-0.008244, 0.02042] | 0.07003 | -0.1233 [-0.1282, -0.1183] | 11.57 [9.043, 12.6] | 0.2492 |
| gradient_boosted_trees | 0.004414 [-0.01199, 0.01538] | 0.07855 | -0.1355 [-0.1515, -0.1196] | 10.68 [9.518, 12.17] | 0.1990 |
| ridge | 0.008396 [-0.009988, 0.02266] | 0.08133 | -0.1538 [-0.1646, -0.1430] | 14.25 [13.09, 15.27] | 0.3316 |
| 1d_cnn | 0.03747 [0.01927, 0.06396] | 0.09276 | -0.1209 [-0.1545, -0.08733] | 14.54 [13.45, 15.10] | 0.2197 |
| mlp | -0.007436 [-0.01701, 0.01644] | 0.1025 | -0.09388 [-0.2573, -0.04151] | 15.43 [13.84, 16.67] | 0.3393 |
| tiny_sequence_transformer | 0.01100 [-0.01508, 0.03882] | 0.1117 | -0.2082 [-0.2207, -0.1957] | 23.23 [21.17, 25.02] | 0.2196 |
| tail_kernel_censored_template_traditional | 0.07329 [0.04799, 0.09233] | 0.1146 | 0.1971 [0.1844, 0.2098] | 15.00 [12.50, 20.00] | 0.03917 |

## Run-Held-Out Stability

The winner has held-out run energy sigma68 values of 0.05363, 0.07711, 0.06085, 0.06707, and 0.06513 for runs 58, 60, 62, 64, and 65 respectively. Its false split rates on clean controls are 0.2073, 0.1951, 0.1829, 0.08537, and 0.09756, showing that the win is not from a single held-out run.

## Systematics and Caveats

The benchmark uses controlled overlays into raw-ROOT-derived clean pulses, so it tests reconstruction under known truth but does not estimate the real beam pile-up frequency. The ADC ceiling is an explicit stressor, not decoded electronics metadata. The 18-sample readout limits very close doublet timing and makes pedestal memory partly degenerate with broad late tails. PID is represented by stave and charge-support proxies because no external particle label is present in the reduced ROOT gate. Bootstrap CIs resample held-out runs and quantify transfer across run conditions rather than asymptotic event-counting error.

## Verdict

`result.json` names **`tail_kernel_residual_fusion_new`** as the S44b winner. It improves energy sigma68 over the traditional tail-kernel comparator by 0.04452 in fractional amplitude units while retaining lower PID-proxy bias span and lower false split rate than most learned alternatives. No novel follow-up ticket was appended.
