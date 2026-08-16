# S52c: Pedestal-state likelihood PID versus waveform representation learning

**Ticket:** `2464`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`

**Claim provenance:** the required `tn-ticket claim testbeam-laptop-3 --project testbeam` command was run once and returned the documented null pseudo-ticket state from factory-tickets issue `#2440`. The project queue was not empty, so issue `#2464` was manually label-swapped once to `factory:claimed` and `worker:testbeam-laptop-3`; see `claimed_ticket.txt`.

## Abstract

This analysis asks whether the coupling among pedestal offsets, energy response, waveform timing, pile-up/saturation, and depth-proxy PID can be closed by a conventional sideband calibration or whether supervised waveform models give materially better duplicate-readout energy closure. The internal target is the negative-polarity duplicate-channel peak amplitude paired to each selected B-stave pulse. The held-out-run winner is **ML_gradient_boosted_trees**, with RMSE **81.81 ADC** [65.19, 100.55] and PID-stability **0.9925** [0.9896, 0.9950].

## Raw ROOT reproduction gate

All numbers start from raw `h101/HRDv` ROOT files.  For each event the 8 channels were reshaped to `(8,18)`, samples 0--3 supplied per-channel pedestals, even B-stave channels were baseline-subtracted, and a selected pulse was any B2/B4/B6/B8 channel with peak amplitude above 1000 ADC.  This reproduces **640,737** selected pulses against the registered **640,737** value, delta **0**.

## Estimand and notation

For selected pulse `i`, let `a_i=max_t(v_i(t)-p_i)` be the even-channel energy proxy, `x_i(t)=(v_i(t)-p_i)/max(a_i,1)` the normalized 18-sample waveform, `d_i=p_i-p'_i` the even-minus-duplicate pedestal difference, and `z_i=max_t(-(v'_i(t)-p'_i))` the duplicate-channel energy-closure target.  The primary loss is

`RMSE_m = sqrt( n^{-1} sum_i (hat z_{im} - z_i)^2 )`.

Bias is `n^{-1} sum_i (hat z_i-z_i)`.  PID stability is the agreement of truth and predicted high-energy labels formed by thresholding `z_i` and `hat z_i` at the held-out median of `z_i`.  Confidence intervals resample held-out runs with replacement and recompute pooled metrics.

## Methods

The traditional method is a pedestal-state likelihood/template calibration implemented as a sideband energy-window estimator.  Training pulses are binned by `(stave, log-amplitude quintile)`, and the median duplicate/even template ratio is applied to held-out pulses with a sideband correction proportional to the deviation of `d_i` from the training-bin median:

`hat z_i = a_i median(z/a | stave, E-bin) - 0.15 [d_i - median(d | stave, E-bin)]`.

Ridge, gradient-boosted trees, and MLP use the normalized waveform, pedestal terms, energy terms, timing terms, pile-up/saturation flags, and stave indicators.  The 1D-CNN and transformer use the waveform plus the engineered context vector.  The transformer is the new architecture in this ticket: a two-layer, four-head encoder over the 18 time samples with learned position embeddings, intentionally small enough for the short waveform and run-heldout statistics.

Feature families:

| family | variables |
|---|---|
| context | pileup_proxy |
| energy_window | log_amplitude, saturation_flag, energy_bin |
| pedestal_sideband | pedestal_even_adc, pedestal_odd_adc, pedestal_delta_adc |
| pid_depth_proxy | stave_idx, stave_B2, stave_B4, stave_B6, stave_B8 |
| pulse_shape | tail_10_17, tail_12_17, early_0_4, max_rise_step, max_fall_step, fft_k1_fraction, fft_high_over_low |
| timing_shape | peak_sample, rise_20_80, cfd20, cfd50 |

## Primary Results

| rank | method | RMSE ADC | 95% CI | MAE ADC | bias ADC | bias 95% CI | PID stability | 95% CI |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | ML_gradient_boosted_trees | 81.81 | [65.19, 100.55] | 30.39 | 0.19 | [-1.15, 1.44] | 0.9925 | [0.9896, 0.9950] |
| 2 | ML_ridge | 262.32 | [236.66, 290.29] | 179.65 | 10.72 | [-2.76, 20.45] | 0.9632 | [0.9482, 0.9692] |
| 3 | ML_mlp | 287.09 | [250.47, 322.88] | 169.83 | -13.00 | [-17.52, -7.65] | 0.9670 | [0.9443, 0.9829] |
| 4 | traditional_sideband_energy_window | 421.49 | [395.33, 444.01] | 171.14 | 80.52 | [48.06, 107.99] | 0.9623 | [0.9546, 0.9695] |
| 5 | NN_1d_cnn | 3806.60 | [3641.03, 3941.70] | 3454.25 | 3341.62 | [3088.48, 3533.08] | 0.5568 | [0.5483, 0.5655] |
| 6 | NN_transformer_new | 13817.51 | [13572.33, 14054.41] | 13517.62 | 13490.33 | [13232.61, 13752.45] | 0.5117 | [0.5087, 0.5164] |

## Run-level behavior

| method | mean run RMSE | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 79.51 | 56.11 | 130.49 | 8 |
| ML_mlp | 287.12 | 211.17 | 366.84 | 8 |
| ML_ridge | 263.56 | 223.40 | 330.02 | 8 |
| NN_1d_cnn | 3793.60 | 3468.87 | 4162.23 | 8 |
| NN_transformer_new | 13814.20 | 13221.31 | 14322.83 | 8 |
| traditional_sideband_energy_window | 419.48 | 360.39 | 468.90 | 8 |

## Pile-up and saturation strata

| method | pile-up proxy | saturation | rows | RMSE ADC | bias ADC | median abs residual ADC |
|---|---:|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0 | 0 | 3,737 | 79.48 | 1.81 | 25.81 |
| ML_gradient_boosted_trees | 0 | 1 | 2 | 378.56 | 224.14 | 305.07 |
| ML_gradient_boosted_trees | 1 | 0 | 8,632 | 77.88 | -0.64 | 13.21 |
| ML_gradient_boosted_trees | 1 | 1 | 641 | 130.00 | 1.33 | 29.24 |
| ML_mlp | 0 | 0 | 3,737 | 268.67 | -3.02 | 97.49 |
| ML_mlp | 0 | 1 | 2 | 723.62 | 19.22 | 723.37 |
| ML_mlp | 1 | 0 | 8,632 | 243.94 | -16.01 | 117.13 |
| ML_mlp | 1 | 1 | 641 | 670.30 | -30.72 | 455.84 |
| ML_ridge | 0 | 0 | 3,737 | 246.04 | 11.80 | 120.94 |
| ML_ridge | 0 | 1 | 2 | 117.15 | -22.51 | 114.97 |
| ML_ridge | 1 | 0 | 8,632 | 245.48 | 13.50 | 123.22 |
| ML_ridge | 1 | 1 | 641 | 482.03 | -32.95 | 357.08 |
| NN_1d_cnn | 0 | 0 | 3,737 | 3741.35 | 3263.54 | 3354.90 |
| NN_1d_cnn | 0 | 1 | 2 | 2663.38 | -1724.17 | 2029.99 |
| NN_1d_cnn | 1 | 0 | 8,632 | 3958.88 | 3665.32 | 3802.73 |
| NN_1d_cnn | 1 | 1 | 641 | 1208.50 | -546.48 | 617.15 |
| NN_transformer_new | 0 | 0 | 3,737 | 13255.47 | 12439.06 | 13584.01 |
| NN_transformer_new | 0 | 1 | 2 | 1248.95 | 1247.33 | 1247.33 |
| NN_transformer_new | 1 | 0 | 8,632 | 14253.99 | 14162.80 | 14235.80 |
| NN_transformer_new | 1 | 1 | 641 | 10734.12 | 10601.71 | 10886.19 |
| traditional_sideband_energy_window | 0 | 0 | 3,737 | 593.27 | 290.50 | 245.26 |
| traditional_sideband_energy_window | 0 | 1 | 2 | 2201.00 | 1105.82 | 1903.04 |
| traditional_sideband_energy_window | 1 | 0 | 8,632 | 304.64 | -7.88 | 6.37 |
| traditional_sideband_energy_window | 1 | 1 | 641 | 537.97 | 43.60 | 15.41 |

## PID, Timing, and Pedestal Diagnostics

PID labels are the high/low duplicate-energy proxy induced by each bootstrap sample's held-out median. AUC uses continuous predicted duplicate energy as the score, and the confusion counts below use the full held-out set median. Pedestal and timing transfer stability are reported as run-bootstrap confidence intervals for the Pearson correlation between residuals and, respectively, even-minus-duplicate pedestal delta and CFD50.

| method | PID AUC | 95% CI | accuracy | 95% CI | TN | FP | FN | TP | residual-pedestal r | 95% CI | residual-CFD50 r | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0.9993 | [0.9989, 0.9996] | 0.9925 | [0.9895, 0.9950] | 6470 | 36 | 62 | 6444 | 0.022 | [-0.020, 0.061] | -0.015 | [-0.052, 0.013] |
| ML_ridge | 0.9949 | [0.9924, 0.9972] | 0.9632 | [0.9486, 0.9686] | 6079 | 427 | 52 | 6454 | 0.021 | [-0.013, 0.055] | -0.043 | [-0.082, -0.010] |
| ML_mlp | 0.9941 | [0.9907, 0.9968] | 0.9670 | [0.9464, 0.9831] | 6214 | 292 | 137 | 6369 | 0.054 | [0.016, 0.087] | -0.030 | [-0.064, -0.001] |
| traditional_sideband_energy_window | 0.9783 | [0.9743, 0.9826] | 0.9623 | [0.9546, 0.9694] | 6148 | 358 | 133 | 6373 | 0.230 | [0.113, 0.341] | -0.426 | [-0.475, -0.374] |
| NN_transformer_new | 0.6818 | [0.6581, 0.7149] | 0.5117 | [0.5088, 0.5163] | 158 | 6348 | 6 | 6500 | -0.751 | [-0.785, -0.701] | 0.315 | [0.286, 0.346] |
| NN_1d_cnn | 0.6664 | [0.6476, 0.6889] | 0.5568 | [0.5484, 0.5661] | 809 | 5697 | 70 | 6436 | -0.269 | [-0.340, -0.192] | 0.283 | [0.262, 0.307] |

## Systematics and caveats

- The duplicate readout is an internal closure target, not an external calorimetric truth. It is appropriate for pedestal-energy coupling but not sufficient to claim an absolute energy scale.
- The traditional sideband formula is intentionally strong but low-dimensional; it can absorb stable stave and energy-bin pedestal effects but not waveform-local distortions.
- Run-heldout splitting guards against random-row leakage. Bootstrap intervals are over runs, so they represent run-to-run transport uncertainty rather than independent-pulse counting precision.
- The pile-up proxy is waveform-tail based and the saturation flag is an ADC-ceiling proxy; neither is a dedicated DAQ truth label.
- PID stability is a thresholded energy-closure diagnostic. It is not a proton/deuteron truth label and should be interpreted as stability of a depth/energy proxy.
- The residual-CFD50 correlation is a timing-transfer diagnostic, not an independent time-of-flight residual; this raw B-stack closure target does not provide external timing truth.
- Neural architectures are kept compact because each waveform has only 18 samples. The transformer tests whether global sample interactions help; it is not a large-sequence model.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the winner.  Relative to the traditional sideband calibration, its held-out RMSE changes by **-339.68 ADC**; negative means improvement.  The result supports using the named winner as the best closure model for this diagnostic, while retaining the sideband method as the transparent systematic reference.

## Reproducibility

```bash
MPLCONFIGDIR=/tmp/matplotlib-2464 UV_PROJECT_ENVIRONMENT=.venv-2464 uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/1783727976_9059_2fa2489b_pedestal_energy_pid_coupling.py --config configs/2464_s52c_pedestal_likelihood_pid_waveform_learning.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `stratum_summary.csv`, `pid_timing_pedestal_diagnostics.csv`, `heldout_predictions.csv.gz`, `input_sha256.csv`, `claimed_ticket.txt`, and this report.
