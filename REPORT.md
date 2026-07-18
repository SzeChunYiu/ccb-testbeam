# S43c: Pileup Saturation Energy Recovery Frontier

## Abstract

Ticket `1784349956.673.79636a15` was claimed by `testbeam-laptop-4` and asks for a raw-ROOT reproduction plus a benchmark of a strong traditional two-pulse template deconvolution against ridge, gradient-boosted trees, MLP, 1D-CNN, transformer/attention waveform regression, and a new architecture for pile-up plus saturation recovery.  The held-out winner is **`saturation_residual_fusion_new`** by the registered composite score.  Its held-out energy residual sigma68 is `0.07110` with 95% run-block bootstrap CI `[0.05945, 0.07903]`; pile-up separation sigma68 is `10.56 ns` with CI `[9.613, 11.21]`.

## Raw ROOT Reproduction

Raw B-stack files were read from `data/root/root/hrdb_run_*.root`.  For every ROOT file, `h101/HRDv` was reshaped to `(event, channel, sample)` with 18 samples per channel.  The selected-pulse anchor used B2/B4/B6/B8 channels, pedestal

`b_ec = median_{t in {0,1,2,3}} x_ect`,

and indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

The raw ROOT gate reproduced the reference exactly:

| quantity | report_value | reproduced | delta | pass |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | True |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | True |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | True |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | True |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | True |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | True |

## Split and Controlled Truth

The split is by source run, not by random event.  Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]`; held-out runs are `[58, 60, 62, 64, 65]`.  Clean train-only templates were estimated as

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

Template support:

| stave | n_train_pulses | cfd20_sample | peak_sample | area |
|---|---:|---:|---:|---:|
| B2 | 800 | 2.599 | 5 | 9.149 |
| B4 | 784 | 2.982 | 6 | 10.78 |
| B6 | 751 | 3.747 | 6 | 9.739 |
| B8 | 482 | 4.236 | 8 | 9.253 |

Controlled doublets were generated from raw-ROOT-derived clean pulses:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

where `epsilon_rs(t)` is a run-local residual and `p` is a pedestal offset.  The observed waveform supplied to every method was clipped as `w_obs(t) = min(w(t), 11800)`.  Clean single-pulse controls were drawn from the same held-out run distribution and clipped with the same rule, so false split rate is a negative-control endpoint.

## Methods

| method | family | description |
|---|---|---|
| `analytic_clipped_template_sideband_traditional` | traditional | bounded two-template deconvolution with deterministic clipped sideband correction |
| `ridge` | linear ML | ridge classifier plus multi-output ridge regression |
| `gradient_boosted_trees` | tree ML | histogram gradient-boosted classifier/regressor panel |
| `mlp` | neural network | tabular multilayer perceptron classifier/regressor pair |
| `1d_cnn` | neural network | compact one-dimensional CNN over the 18 ADC samples |
| `tiny_sequence_transformer` | attention NN | one-layer self-attention encoder over waveform samples |
| `saturation_residual_fusion_new` | new hybrid | boosted residual fusion of waveform summaries, clipping sidebands, and traditional fit outputs |

The traditional comparator minimizes

`SSE_k = sum_t [w_obs(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

then applies

`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`.

The new architecture is sensible here because pile-up under ADC clipping is a hybrid failure mode: the analytic fit supplies identifiable pulse constituents, while clipped sidebands and waveform summaries carry residual information about charge hidden above the ADC ceiling.

## Metrics

For accepted injected doublets, the primary energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Pile-up separation error is

`e_Delta = 10 ns * [(hat t_2 - hat t_1) - Delta]`,

and constituent timing shifts use

`e_tj = 10 ns * (hat t_j - t_j)`.

Robust resolution is

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

Confidence intervals are percentile 95% intervals from 400 held-out run-block bootstrap resamples.  The winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.004 sigma_Delta + 0.004 sigma_t1 + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID`.

## Overall Results

| method | score | bias_E | sigma68_E | sigma68_E CI | sigma68_Delta ns | sigma68_t1 ns | miss | false |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| saturation_residual_fusion_new | 0.1771 | -0.00304 | 0.07110 | [0.05945, 0.07903] | 10.56 | 5.423 | 0.300 | 0.195 |
| gradient_boosted_trees | 0.1795 | -0.00984 | 0.07109 | [0.05751, 0.07866] | 11.40 | 4.960 | 0.278 | 0.195 |
| ridge | 0.1803 | -0.00151 | 0.06797 | [0.06179, 0.07188] | 13.15 | 6.594 | 0.263 | 0.198 |
| 1d_cnn | 0.2366 | 0.00153 | 0.09933 | [0.08196, 0.1088] | 15.17 | 8.608 | 0.278 | 0.256 |
| analytic_clipped_template_sideband_traditional | 0.2444 | 0.07902 | 0.08542 | [0.06603, 0.09771] | 15.00 | 7.182 | 0.585 | 0.183 |
| mlp | 0.2665 | -0.04525 | 0.1237 | [0.1112, 0.1355] | 15.22 | 8.578 | 0.322 | 0.202 |
| tiny_sequence_transformer | 0.3029 | -0.08437 | 0.08253 | [0.07244, 0.0940] | 25.48 | 17.08 | 0.412 | 0.149 |

The selected winner improves energy sigma68 by `-0.01433` relative to the traditional clipped-template comparator and has substantially lower pile-up separation error.

## Run-Held-Out Stability

The winner's per-run energy sigma68 values were `0.0458`, `0.0722`, `0.0777`, `0.0492`, and `0.0803` across held-out runs 58, 60, 62, 64, and 65.  Its false split rates across those runs were `0.2927`, `0.1707`, `0.2683`, `0.1220`, and `0.1220`, indicating that the score is not driven by a single held-out run.

## Systematics

The stratum scan covered pile-up spacing, amplitude ratio, saturation depth, pedestal state, morphology state, stave, and PID proxy class.  The worst stressors were close separations below 10 ns and deep missed-pileup tails.  PID was represented by stave and charge-support proxies because the reduced ROOT gate has no external particle label.

## Failure-Mode Hand Scan

A deterministic hand-scan ledger prioritized held-out injected failures by absolute energy residual, spacing error, missed-doublet status, and saturation depth.  The leading recurrent modes were missed close doublets, timing-swap/spacing errors, and large residuals in shifted-pedestal late-tail examples.  The ledger is not used to choose the winner; it is a pathology audit for repeated physical failure modes.

## Feature-Block Ablations

The fusion architecture was retrained on the same split with all inputs, with pedestal-subtraction information removed, and with clipped-tail-window features removed.  The all-input ablation reproduces the winner (`sigma68_E = 0.07110`).  Removing pedestal or clipped-tail information changed the held-out composite behavior, confirming that the reported winner uses the ticket-requested sideband information rather than only generic waveform amplitude.

## Caveats

Truth labels come from controlled overlays into raw-ROOT-derived clean pulses, so the study tests reconstruction under known pile-up and saturation truth but does not estimate the real beam pile-up frequency.  The ADC clipping threshold is a benchmark stressor rather than decoded electronics metadata.  The 18-sample readout imposes a sampling floor for close doublets and makes pedestal memory partly degenerate with broad late tails.  Run-block bootstrap intervals quantify transfer across the five held-out runs, not asymptotic event-counting uncertainty.

## Verdict

`result.json` names **`saturation_residual_fusion_new`** as the S43c winner.  The traditional clipped-template method remains the transparent fallback, while the fusion model is preferred for the registered held-out energy-plus-pile-up score.
