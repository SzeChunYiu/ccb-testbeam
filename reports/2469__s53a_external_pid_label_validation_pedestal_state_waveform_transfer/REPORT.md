# S53a: external PID-label validation for pedestal-state waveform transfer

**Ticket:** `2469`  
**Worker:** `testbeam-laptop-4`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

S53a tests whether the S50c/S51c raw-waveform pedestal-state benchmark can be promoted from a charge/stave proxy study toward an externally anchored PID-energy transfer statement. The primary supervised target remains the event-aligned duplicate-readout energy-closure channel, while the GEANT4 PID benchmark is used as a non-keyed feasibility constraint because no one-to-one event key exists between the real HRD events and simulated tracks. The held-out-run winner is **ML_gradient_boosted_trees**, with RMSE **80.31 ADC** [70.04, 88.71] and PID-stability **0.9900** [0.9881, 0.9931].

## Raw ROOT reproduction gate

All numbers start from raw `h101/HRDv` ROOT files.  For each event the 8 channels were reshaped to `(8,18)`, samples 0--3 supplied per-channel pedestals, even B-stave channels were baseline-subtracted, and a selected pulse was any B2/B4/B6/B8 channel with peak amplitude above 1000 ADC.  This reproduces **640,737** selected pulses against the registered **640,737** value, delta **0**.

## Estimand and notation

For selected pulse `i`, let `a_i=max_t(v_i(t)-p_i)` be the even-channel energy proxy, `x_i(t)=(v_i(t)-p_i)/max(a_i,1)` the normalized 18-sample waveform, `d_i=p_i-p'_i` the even-minus-duplicate pedestal difference, and `z_i=max_t(-(v'_i(t)-p'_i))` the duplicate-channel energy-closure target.  The primary loss is

`RMSE_m = sqrt( n^{-1} sum_i (hat z_{im} - z_i)^2 )`.

Bias is `n^{-1} sum_i (hat z_i-z_i)`.  PID stability is the agreement of truth and predicted high-energy labels formed by thresholding `z_i` and `hat z_i` at the held-out median of `z_i`.  Confidence intervals resample held-out runs with replacement and recompute pooled metrics.

## External-truth bridge audit

I inspected the available GEANT4 PID truth bridge (`reports/1781181864.166893.491f3bde__s22_g4_truth_real_pid_transfer`) and the raw HRD benchmark table.  The GEANT4 table carries `event`, `track_id`, `pdg`, `particle`, `y_deuteron`, and `pseudo_run`, whereas the real raw waveform rows carry run-local `eventno/evt` identifiers; the two spaces are not event-aligned.  Therefore the honest S53a result is a negative external-truth gate plus a full pedestal-state bakeoff on the event-aligned real raw rows.  PID stability below is a high-energy/depth proxy, not proton/deuteron truth.

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
| 1 | ML_gradient_boosted_trees | 80.31 | [70.04, 88.71] | 31.39 | -0.26 | [-1.46, 0.99] | 0.9900 | [0.9881, 0.9931] |
| 2 | ML_ridge | 259.30 | [234.49, 287.11] | 180.77 | 8.23 | [-4.79, 17.31] | 0.9555 | [0.9452, 0.9656] |
| 3 | ML_mlp | 313.50 | [258.54, 370.31] | 181.25 | -15.86 | [-22.12, -10.73] | 0.9598 | [0.9430, 0.9791] |
| 4 | traditional_sideband_energy_window | 425.56 | [386.69, 460.89] | 166.41 | 75.77 | [44.71, 104.88] | 0.9654 | [0.9571, 0.9694] |
| 5 | NN_transformer_new | 1813.30 | [1541.74, 2160.69] | 1302.39 | -524.11 | [-876.43, -279.00] | 0.5987 | [0.5687, 0.6212] |
| 6 | NN_1d_cnn | 11437.85 | [11187.58, 11658.35] | 11129.94 | 11106.85 | [10832.82, 11356.29] | 0.5195 | [0.5145, 0.5254] |

## Run-level behavior

| method | mean run RMSE | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 78.82 | 54.21 | 101.87 | 8 |
| ML_mlp | 306.67 | 228.27 | 479.51 | 8 |
| ML_ridge | 260.86 | 195.19 | 315.96 | 8 |
| NN_1d_cnn | 11420.08 | 10770.71 | 11922.91 | 8 |
| NN_transformer_new | 1793.43 | 1435.90 | 2705.64 | 8 |
| traditional_sideband_energy_window | 420.53 | 329.32 | 499.65 | 8 |

## Pile-up and saturation strata

| method | pile-up proxy | saturation | rows | RMSE ADC | bias ADC | median abs residual ADC |
|---|---:|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0 | 0 | 3,284 | 69.61 | 0.33 | 25.06 |
| ML_gradient_boosted_trees | 1 | 0 | 7,924 | 74.09 | -0.91 | 14.19 |
| ML_gradient_boosted_trees | 1 | 1 | 637 | 163.30 | 4.79 | 29.46 |
| ML_mlp | 0 | 0 | 3,284 | 202.74 | -7.21 | 101.70 |
| ML_mlp | 1 | 0 | 7,924 | 252.30 | -19.11 | 129.08 |
| ML_mlp | 1 | 1 | 637 | 907.65 | -20.01 | 473.64 |
| ML_ridge | 0 | 0 | 3,284 | 242.35 | 4.55 | 125.48 |
| ML_ridge | 1 | 0 | 7,924 | 243.13 | 14.38 | 123.96 |
| ML_ridge | 1 | 1 | 637 | 460.57 | -49.23 | 358.22 |
| NN_1d_cnn | 0 | 0 | 3,284 | 11517.60 | 10653.13 | 11900.14 |
| NN_1d_cnn | 1 | 0 | 7,924 | 11634.87 | 11549.29 | 11615.41 |
| NN_1d_cnn | 1 | 1 | 637 | 8052.29 | 7942.22 | 8076.45 |
| NN_transformer_new | 0 | 0 | 3,284 | 1625.09 | 874.84 | 888.64 |
| NN_transformer_new | 1 | 0 | 7,924 | 1362.08 | -760.49 | 845.51 |
| NN_transformer_new | 1 | 1 | 637 | 4944.48 | -4795.74 | 4861.20 |
| traditional_sideband_energy_window | 0 | 0 | 3,284 | 581.47 | 287.07 | 252.46 |
| traditional_sideband_energy_window | 1 | 0 | 7,924 | 302.08 | -9.72 | 6.29 |
| traditional_sideband_energy_window | 1 | 1 | 637 | 699.54 | 49.90 | 15.15 |

## Systematics and caveats

- The duplicate readout is an internal closure target, not an external calorimetric truth. It is appropriate for pedestal-energy coupling but not sufficient to claim an absolute energy scale.
- The traditional sideband formula is intentionally strong but low-dimensional; it can absorb stable stave and energy-bin pedestal effects but not waveform-local distortions.
- Run-heldout splitting guards against random-row leakage. Bootstrap intervals are over runs, so they represent run-to-run transport uncertainty rather than independent-pulse counting precision.
- The pile-up proxy is waveform-tail based and the saturation flag is an ADC-ceiling proxy; neither is a dedicated DAQ truth label.
- PID stability is a thresholded energy-closure diagnostic. It is not a proton/deuteron truth label and should be interpreted as stability of a depth/energy proxy.
- Neural architectures are kept compact because each waveform has only 18 samples. The transformer tests whether global sample interactions help; it is not a large-sequence model.
- S53a specifically asks for external PID or digitized-GEANT4 truth. The available GEANT4 PID benchmark is not keyed to the real raw HRD event ids used here, so this report treats it as a support/feasibility constraint and does not claim event-level truth transfer.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the winner.  Relative to the traditional sideband calibration, its held-out RMSE changes by **-345.25 ADC**; negative means improvement.  The result supports using the named winner as the best closure model for this diagnostic, while retaining the sideband method as the transparent systematic reference.

## Reproducibility

```bash
MPLCONFIGDIR=/tmp/matplotlib-2469 UV_PROJECT_ENVIRONMENT=.venv-2469 uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/1783727976_9059_2fa2489b_pedestal_energy_pid_coupling.py --config configs/2469_s53a_external_pid_label_validation_pedestal_state_waveform_transfer.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `stratum_summary.csv`, `heldout_predictions.csv.gz`, `input_sha256.csv`, and this report.
