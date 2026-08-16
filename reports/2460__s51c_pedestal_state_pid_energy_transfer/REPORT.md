# S51c: Pedestal-state matched filtering versus multitask waveform networks

**Ticket:** `2460`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This analysis asks whether the coupling among pedestal offsets, energy response, waveform timing, pile-up/saturation, and depth-proxy PID can be closed by a conventional sideband calibration or whether supervised waveform models give materially better duplicate-readout energy closure. The internal target is the negative-polarity duplicate-channel peak amplitude paired to each selected B-stave pulse. The held-out-run winner is **ML_gradient_boosted_trees**, with RMSE **72.11 ADC** [61.54, 80.89] and PID-stability **0.9916** [0.9889, 0.9940].

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
| 1 | ML_gradient_boosted_trees | 72.11 | [61.54, 80.89] | 28.83 | -0.76 | [-1.91, 0.39] | 0.9916 | [0.9889, 0.9940] |
| 2 | ML_ridge | 256.68 | [232.47, 287.33] | 179.91 | 9.41 | [-5.11, 20.80] | 0.9600 | [0.9446, 0.9702] |
| 3 | ML_mlp | 294.03 | [254.22, 335.97] | 174.24 | -16.80 | [-22.94, -10.56] | 0.9612 | [0.9467, 0.9812] |
| 4 | traditional_sideband_energy_window | 408.87 | [383.54, 434.10] | 167.04 | 71.52 | [39.06, 100.57] | 0.9645 | [0.9567, 0.9688] |
| 5 | NN_transformer_new | 2941.84 | [2641.11, 3292.45] | 2383.95 | -2154.69 | [-2402.74, -1946.58] | 0.4825 | [0.4783, 0.4873] |
| 6 | NN_1d_cnn | 3131.42 | [2880.02, 3437.58] | 2640.97 | -2438.26 | [-2759.98, -2183.68] | 0.5354 | [0.5185, 0.5500] |

## Run-level behavior

| method | mean run RMSE | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 71.07 | 49.83 | 89.42 | 8 |
| ML_mlp | 293.17 | 220.40 | 391.16 | 8 |
| ML_ridge | 257.61 | 205.38 | 336.93 | 8 |
| NN_1d_cnn | 3122.93 | 2532.83 | 3904.05 | 8 |
| NN_transformer_new | 2937.96 | 2422.31 | 3917.26 | 8 |
| traditional_sideband_energy_window | 407.22 | 343.81 | 459.59 | 8 |

## Pile-up and saturation strata

| method | pile-up proxy | saturation | rows | RMSE ADC | bias ADC | median abs residual ADC |
|---|---:|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0 | 0 | 3,309 | 73.25 | 1.71 | 23.41 |
| ML_gradient_boosted_trees | 0 | 1 | 1 | 159.49 | 159.49 | 159.49 |
| ML_gradient_boosted_trees | 1 | 0 | 7,906 | 71.09 | -1.09 | 13.29 |
| ML_gradient_boosted_trees | 1 | 1 | 629 | 78.37 | -9.88 | 29.25 |
| ML_mlp | 0 | 0 | 3,309 | 322.97 | -8.32 | 97.39 |
| ML_mlp | 0 | 1 | 1 | 1317.13 | -1317.13 | 1317.13 |
| ML_mlp | 1 | 0 | 7,906 | 237.48 | -19.72 | 122.93 |
| ML_mlp | 1 | 1 | 629 | 606.33 | -22.61 | 442.89 |
| ML_ridge | 0 | 0 | 3,309 | 235.22 | 8.85 | 124.50 |
| ML_ridge | 0 | 1 | 1 | 17.17 | -17.17 | 17.17 |
| ML_ridge | 1 | 0 | 7,906 | 241.29 | 13.86 | 123.89 |
| ML_ridge | 1 | 1 | 629 | 466.76 | -43.66 | 357.84 |
| NN_1d_cnn | 0 | 0 | 3,309 | 2360.24 | -1117.19 | 1501.02 |
| NN_1d_cnn | 0 | 1 | 1 | 6679.50 | -6679.50 | 6679.50 |
| NN_1d_cnn | 1 | 0 | 7,906 | 3079.12 | -2717.71 | 2864.32 |
| NN_1d_cnn | 1 | 1 | 629 | 6009.32 | -5868.75 | 5833.05 |
| NN_transformer_new | 0 | 0 | 3,309 | 1967.79 | -969.61 | 1452.50 |
| NN_transformer_new | 0 | 1 | 1 | 6679.50 | -6679.50 | 6679.50 |
| NN_transformer_new | 1 | 0 | 7,906 | 2754.83 | -2280.91 | 2198.23 |
| NN_transformer_new | 1 | 1 | 629 | 6866.27 | -6795.37 | 6798.05 |
| traditional_sideband_energy_window | 0 | 0 | 3,309 | 583.23 | 281.95 | 235.13 |
| traditional_sideband_energy_window | 0 | 1 | 1 | 259.27 | -259.27 | 259.27 |
| traditional_sideband_energy_window | 1 | 0 | 7,906 | 305.02 | -10.69 | 6.39 |
| traditional_sideband_energy_window | 1 | 1 | 629 | 434.93 | -1.68 | 14.29 |

## Systematics and caveats

- The duplicate readout is an internal closure target, not an external calorimetric truth. It is appropriate for pedestal-energy coupling but not sufficient to claim an absolute energy scale.
- The traditional sideband formula is intentionally strong but low-dimensional; it can absorb stable stave and energy-bin pedestal effects but not waveform-local distortions.
- Run-heldout splitting guards against random-row leakage. Bootstrap intervals are over runs, so they represent run-to-run transport uncertainty rather than independent-pulse counting precision.
- The pile-up proxy is waveform-tail based and the saturation flag is an ADC-ceiling proxy; neither is a dedicated DAQ truth label.
- PID stability is a thresholded energy-closure diagnostic. It is not a proton/deuteron truth label and should be interpreted as stability of a depth/energy proxy.
- Neural architectures are kept compact because each waveform has only 18 samples. The transformer tests whether global sample interactions help; it is not a large-sequence model.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the winner.  Relative to the traditional sideband calibration, its held-out RMSE changes by **-336.76 ADC**; negative means improvement.  The result supports using the named winner as the best closure model for this diagnostic, while retaining the sideband method as the transparent systematic reference.

## Reproducibility

```bash
MPLCONFIGDIR=/tmp/matplotlib-2460 UV_PROJECT_ENVIRONMENT=.venv-2460 uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/1783727976_9059_2fa2489b_pedestal_energy_pid_coupling.py --config configs/2460_s51c_pedestal_state_pid_energy_transfer.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `stratum_summary.csv`, `heldout_predictions.csv.gz`, `input_sha256.csv`, and this report.
