# Pedestal-energy-PID coupling: sideband subtraction versus ML/NN

**Ticket:** `1783727976.9059.2fa2489b`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This analysis asks whether the coupling among pedestal offsets, energy response, waveform timing, pile-up/saturation, and depth-proxy PID can be closed by a conventional sideband calibration or whether supervised waveform models give materially better duplicate-readout energy closure. The internal target is the negative-polarity duplicate-channel peak amplitude paired to each selected B-stave pulse. The held-out-run winner is **ML_gradient_boosted_trees**, with RMSE **74.97 ADC** [65.13, 85.66] and PID-stability **0.9937** [0.9872, 0.9946].

## Raw ROOT reproduction gate

All numbers start from raw `h101/HRDv` ROOT files.  For each event the 8 channels were reshaped to `(8,18)`, samples 0--3 supplied per-channel pedestals, even B-stave channels were baseline-subtracted, and a selected pulse was any B2/B4/B6/B8 channel with peak amplitude above 1000 ADC.  This reproduces **640,737** selected pulses against the registered **640,737** value, delta **0**.

## Estimand and notation

For selected pulse `i`, let `a_i=max_t(v_i(t)-p_i)` be the even-channel energy proxy, `x_i(t)=(v_i(t)-p_i)/max(a_i,1)` the normalized 18-sample waveform, `d_i=p_i-p'_i` the even-minus-duplicate pedestal difference, and `z_i=max_t(-(v'_i(t)-p'_i))` the duplicate-channel energy-closure target.  The primary loss is

`RMSE_m = sqrt( n^{-1} sum_i (hat z_{im} - z_i)^2 )`.

Bias is `n^{-1} sum_i (hat z_i-z_i)`.  PID stability is the agreement of truth and predicted high-energy labels formed by thresholding `z_i` and `hat z_i` at the held-out median of `z_i`.  Confidence intervals resample held-out runs with replacement and recompute pooled metrics.

## Methods

The traditional method is a pedestal sideband plus energy-window calibration.  Training pulses are binned by `(stave, log-amplitude quintile)`, and the median duplicate/even ratio is applied to held-out pulses with a sideband correction proportional to the deviation of `d_i` from the training-bin median:

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
| 1 | ML_gradient_boosted_trees | 74.97 | [65.13, 85.66] | 32.18 | 0.46 | [-0.66, 1.67] | 0.9937 | [0.9872, 0.9946] |
| 2 | ML_ridge | 262.14 | [235.84, 286.16] | 181.59 | 11.76 | [-2.46, 22.51] | 0.9590 | [0.9429, 0.9711] |
| 3 | ML_mlp | 273.05 | [248.27, 299.52] | 174.93 | -23.26 | [-29.39, -16.02] | 0.9645 | [0.9471, 0.9814] |
| 4 | traditional_sideband_energy_window | 409.89 | [382.07, 433.82] | 167.89 | 71.95 | [38.97, 103.24] | 0.9634 | [0.9559, 0.9699] |
| 5 | NN_transformer_new | 3004.57 | [2692.98, 3416.35] | 2485.80 | -2156.06 | [-2458.30, -1963.17] | 0.4700 | [0.4640, 0.4781] |
| 6 | NN_1d_cnn | 4473.14 | [4258.29, 4643.82] | 3970.65 | 3910.45 | [3625.35, 4142.84] | 0.5018 | [0.5002, 0.5040] |

## Run-level behavior

| method | mean run RMSE | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 73.66 | 50.87 | 96.96 | 8 |
| ML_mlp | 273.64 | 231.18 | 348.69 | 8 |
| ML_ridge | 264.02 | 219.50 | 314.26 | 8 |
| NN_1d_cnn | 4450.07 | 3656.34 | 4893.26 | 8 |
| NN_transformer_new | 2999.97 | 2507.11 | 3859.31 | 8 |
| traditional_sideband_energy_window | 406.19 | 337.17 | 458.26 | 8 |

## Pile-up and saturation strata

| method | pile-up proxy | saturation | rows | RMSE ADC | bias ADC | median abs residual ADC |
|---|---:|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0 | 0 | 3,272 | 74.88 | 3.22 | 25.48 |
| ML_gradient_boosted_trees | 0 | 1 | 1 | 81.04 | -81.04 | 81.04 |
| ML_gradient_boosted_trees | 1 | 0 | 7,905 | 72.73 | -0.56 | 14.16 |
| ML_gradient_boosted_trees | 1 | 1 | 667 | 98.05 | -0.93 | 34.71 |
| ML_mlp | 0 | 0 | 3,272 | 213.04 | -3.36 | 99.88 |
| ML_mlp | 0 | 1 | 1 | 934.00 | -934.00 | 934.00 |
| ML_mlp | 1 | 0 | 7,905 | 247.07 | -25.08 | 123.72 |
| ML_mlp | 1 | 1 | 667 | 613.72 | -97.86 | 436.38 |
| ML_ridge | 0 | 0 | 3,272 | 243.49 | 19.61 | 124.97 |
| ML_ridge | 0 | 1 | 1 | 231.95 | -231.95 | 231.95 |
| ML_ridge | 1 | 0 | 7,905 | 245.79 | 14.81 | 127.01 |
| ML_ridge | 1 | 1 | 667 | 462.01 | -62.57 | 345.99 |
| NN_1d_cnn | 0 | 0 | 3,272 | 5718.94 | 5115.00 | 4775.64 |
| NN_1d_cnn | 0 | 1 | 1 | 1216.90 | 1216.90 | 1216.90 |
| NN_1d_cnn | 1 | 0 | 7,905 | 4036.49 | 3721.51 | 3688.55 |
| NN_1d_cnn | 1 | 1 | 667 | 1336.44 | 244.75 | 981.05 |
| NN_transformer_new | 0 | 0 | 3,272 | 2559.82 | -724.63 | 1763.31 |
| NN_transformer_new | 0 | 1 | 1 | 5797.60 | -5797.60 | 5797.60 |
| NN_transformer_new | 1 | 0 | 7,905 | 2682.10 | -2383.53 | 2293.89 |
| NN_transformer_new | 1 | 1 | 667 | 6547.03 | -6476.68 | 6472.42 |
| traditional_sideband_energy_window | 0 | 0 | 3,272 | 585.42 | 294.29 | 249.66 |
| traditional_sideband_energy_window | 0 | 1 | 1 | 586.68 | -586.68 | 586.68 |
| traditional_sideband_energy_window | 1 | 0 | 7,905 | 308.13 | -14.09 | 6.37 |
| traditional_sideband_energy_window | 1 | 1 | 667 | 420.34 | 1.93 | 14.74 |

## Systematics and caveats

- The duplicate readout is an internal closure target, not an external calorimetric truth. It is appropriate for pedestal-energy coupling but not sufficient to claim an absolute energy scale.
- The traditional sideband formula is intentionally strong but low-dimensional; it can absorb stable stave and energy-bin pedestal effects but not waveform-local distortions.
- Run-heldout splitting guards against random-row leakage. Bootstrap intervals are over runs, so they represent run-to-run transport uncertainty rather than independent-pulse counting precision.
- The pile-up proxy is waveform-tail based and the saturation flag is an ADC-ceiling proxy; neither is a dedicated DAQ truth label.
- PID stability is a thresholded energy-closure diagnostic. It is not a proton/deuteron truth label and should be interpreted as stability of a depth/energy proxy.
- Neural architectures are kept compact because each waveform has only 18 samples. The transformer tests whether global sample interactions help; it is not a large-sequence model.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the winner.  Relative to the traditional sideband calibration, its held-out RMSE changes by **-334.92 ADC**; negative means improvement.  The result supports using the named winner as the best closure model for this diagnostic, while retaining the sideband method as the transparent systematic reference.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/1783727976_9059_2fa2489b_pedestal_energy_pid_coupling.py --config configs/1783727976.9059.2fa2489b_pedestal_energy_pid_coupling.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `stratum_summary.csv`, `heldout_predictions.csv.gz`, `input_sha256.csv`, and this report.
