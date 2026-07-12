# S32d: External-Truth PID-Energy Tail/Pedestal Validation

Ticket: `1783887596.850.1c4d2571`  
Worker: `testbeam-laptop-2`  
Raw ROOT directory: `data/root/root`  
GEANT4 bridge: `reports/1783883140.39222.3c4045b1__g4_08_keyed_digitized_geant4_native_join/digitized_g4_08_keyed.root`

## Abstract

S32d repeats the S32c method panel with independent GEANT4 truth labels for particle species and calibrated deposited energy. The raw B-stack selected-pulse reproduction gate is **640,737**, matching the registered **640,737** pulses exactly. Across the run-held-out and external particle-family-held-out splits, `result.json` names **gradient_boosted_trees** as the minimum mean joint-loss method.

## Raw ROOT Reproduction

The reproduction gate opens every configured `hrdb_run_XXXX.root` file at `h101/HRDv`, reshapes each record to `(event, channel, sample)`, subtracts the median of samples 0-3 for each channel, and selects B2/B4/B6/B8 pulses whose corrected maximum exceeds 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|---|
| selected B-stave pulses | 640,737 | 640,737 | 0 | True |

## External Truth Construction

The benchmark labels are read from the keyed G4-08 digitized bridge. GEANT4 truth defines the PID target as dominant Sci_bar PDG, with proton `2212` mapped to 0 and deuteron `1000010020` mapped to 1. The calibrated energy target is `E_i = sum_h EDep_ih` over B-stack Sci_bar hits, evaluated as the run/stave-centered residual of `log(1+E_i)`.

The digitized waveform branch `HRDv_digitized` supplies the 18-sample ADC-like pulse. It preserves raw residual templates and native DAQ keys while the labels come from GEANT4, so PID and energy are no longer deterministic functions of the target waveform features as in S32c.

## Splits and Bootstrap

Requested S32c held-out runs were `[42, 50, 57, 58, 60, 62, 64, 65]`; the keyed G4-08 bridge contains `[50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 62, 64, 65]`, so the run-held-out test uses the available intersection `[50, 57, 58, 60, 62, 64, 65]`. The particle-held-out split removes `external_high_energy_tail_family` from training. Bootstrap CIs resample held-out run blocks with replacement using `260` replicates.

For held-out blocks `D_r`, replicate `b` draws labels `S_b` with replacement and evaluates `theta_b = T(union_{r in S_b} D_r)`. The interval is `[Q_0.025(theta_b), Q_0.975(theta_b)]`. Classification endpoints use ROC AUC and calibration ECE; energy uses `sigma68 = 0.5[Q_0.84(yhat-y)-Q_0.16(yhat-y)]`.

## Methods and Equations

The traditional comparator is a regularized dE-E/tail/pedestal likelihood surrogate over engineered variables: log amplitude, duplicate-readout response, CFD times, pulse moments, Haar coefficients, late/early charge ratios, FFT fractions, and pedestal residuals. In compact notation, the comparator fits `f_trad([log A, dE/E, T_late, M_ped, H_fft])` using only these physics-motivated features.

Ridge minimizes `||y-X beta||_2^2 + lambda||beta||_2^2` or the corresponding L2 classification margin. Gradient-boosted trees fit `F_M(x)=sum_m eta h_m(x)`. The MLP is a two-layer ReLU model. The 1D-CNN learns local filters over the 18 samples. The new `spectral_transformer_new` embeds sample/time tokens and gates the pooled representation with normalized FFT magnitudes.

The joint loss is `0.34(1-AUC_PID)+0.30 sigma68_E+0.10(1-AUC_pileup)+0.08(1-AUC_sat)+0.08(1-AUC_ped)+0.10(1-AUC_tail)`. Lower is better.

## Primary Joint Results

| split_name       | method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:-----------------|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| particle_heldout | gradient_boosted_trees                    |      0.26719 |           0.29651 |          0.56598 |        0.2009  |           0.83528 |               1       |                1       |                 0.57123 |
| run_heldout      | gradient_boosted_trees                    |      0.32583 |           0.29651 |          0.50535 |        0.30719 |           0.79658 |               1       |                0.9758  |                 0.56783 |
| particle_heldout | ridge                                     |      0.31063 |           0.31733 |          0.52943 |        0.25137 |           0.85889 |               0.93091 |                0.99107 |                 0.45129 |
| run_heldout      | ridge                                     |      0.32403 |           0.31733 |          0.51854 |        0.29668 |           0.78548 |               0.91679 |                0.96804 |                 0.59333 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |      0.30945 |           0.31751 |          0.53615 |        0.25519 |           0.84139 |               0.92581 |                0.99107 |                 0.47327 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |      0.32558 |           0.31751 |          0.52207 |        0.30622 |           0.78131 |               0.92956 |                0.96083 |                 0.59421 |
| particle_heldout | spectral_transformer_new                  |      0.31983 |           0.36268 |          0.48078 |        0.16779 |           0.84389 |               0.63522 |                0.97589 |                 0.53758 |
| run_heldout      | spectral_transformer_new                  |      0.40552 |           0.36268 |          0.48179 |        0.34127 |           0.63697 |               0.63472 |                0.86194 |                 0.49624 |
| particle_heldout | 1d_cnn                                    |      0.32499 |           0.36395 |          0.49449 |        0.16967 |           0.76056 |               0.70887 |                0.92232 |                 0.51235 |
| run_heldout      | 1d_cnn                                    |      0.40291 |           0.36395 |          0.51079 |        0.34497 |           0.58601 |               0.63188 |                0.84585 |                 0.5009  |
| particle_heldout | mlp                                       |      0.35261 |           0.38779 |          0.46721 |        0.22076 |           0.74889 |               0.82876 |                0.8     |                 0.49579 |
| run_heldout      | mlp                                       |      0.42297 |           0.38779 |          0.49756 |        0.40924 |           0.68429 |               0.59896 |                0.79467 |                 0.50708 |

## Endpoint Bootstrap CIs

| split_name       | endpoint              | method                                    |   metric_value |   ci_low |   ci_high |   n |   positives |
|:-----------------|:----------------------|:------------------------------------------|---------------:|---------:|----------:|----:|------------:|
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.52207 |  0.48976 |   0.56591 | 624 |         311 |
| run_heldout      | pid_separation        | ridge                                     |        0.51854 |  0.47395 |   0.55873 | 624 |         311 |
| run_heldout      | pid_separation        | 1d_cnn                                    |        0.51079 |  0.45452 |   0.55127 | 624 |         311 |
| run_heldout      | pid_separation        | gradient_boosted_trees                    |        0.50535 |  0.47046 |   0.55307 | 624 |         311 |
| run_heldout      | pid_separation        | mlp                                       |        0.49756 |  0.47118 |   0.52713 | 624 |         311 |
| run_heldout      | pid_separation        | spectral_transformer_new                  |        0.48179 |  0.44182 |   0.52187 | 624 |         311 |
| run_heldout      | energy_scale          | ridge                                     |        0.29668 |  0.2751  |   0.31951 | 624 |             |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.30622 |  0.29069 |   0.32673 | 624 |             |
| run_heldout      | energy_scale          | gradient_boosted_trees                    |        0.30719 |  0.28285 |   0.32454 | 624 |             |
| run_heldout      | energy_scale          | spectral_transformer_new                  |        0.34127 |  0.31425 |   0.39372 | 624 |             |
| run_heldout      | energy_scale          | 1d_cnn                                    |        0.34497 |  0.31431 |   0.38095 | 624 |             |
| run_heldout      | energy_scale          | mlp                                       |        0.40924 |  0.37569 |   0.4333  | 624 |             |
| run_heldout      | pileup_sideband       | gradient_boosted_trees                    |        0.79658 |  0.77646 |   0.82088 | 624 |         312 |
| run_heldout      | pileup_sideband       | ridge                                     |        0.78548 |  0.76084 |   0.81204 | 624 |         312 |
| run_heldout      | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.78131 |  0.75196 |   0.81029 | 624 |         312 |
| run_heldout      | pileup_sideband       | mlp                                       |        0.68429 |  0.65276 |   0.7247  | 624 |         312 |
| run_heldout      | pileup_sideband       | spectral_transformer_new                  |        0.63697 |  0.59754 |   0.68013 | 624 |         312 |
| run_heldout      | pileup_sideband       | 1d_cnn                                    |        0.58601 |  0.56068 |   0.61627 | 624 |         312 |
| run_heldout      | saturation_clipping   | gradient_boosted_trees                    |        1       |  1       |   1       | 624 |         248 |
| run_heldout      | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.92956 |  0.91344 |   0.94568 | 624 |         248 |
| run_heldout      | saturation_clipping   | ridge                                     |        0.91679 |  0.90007 |   0.93339 | 624 |         248 |
| run_heldout      | saturation_clipping   | spectral_transformer_new                  |        0.63472 |  0.60481 |   0.66744 | 624 |         248 |
| run_heldout      | saturation_clipping   | 1d_cnn                                    |        0.63188 |  0.60396 |   0.65936 | 624 |         248 |
| run_heldout      | saturation_clipping   | mlp                                       |        0.59896 |  0.5682  |   0.63342 | 624 |         248 |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees                    |        0.9758  |  0.95537 |   0.99117 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | ridge                                     |        0.96804 |  0.93342 |   0.98994 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.96083 |  0.92569 |   0.98541 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new                  |        0.86194 |  0.82234 |   0.89616 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | 1d_cnn                                    |        0.84585 |  0.80104 |   0.87678 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | mlp                                       |        0.79467 |  0.66929 |   0.86483 | 624 |          57 |
| run_heldout      | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.59421 |  0.55522 |   0.64045 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | ridge                                     |        0.59333 |  0.5543  |   0.63431 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees                    |        0.56783 |  0.53505 |   0.60562 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | mlp                                       |        0.50708 |  0.49164 |   0.52837 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                                    |        0.5009  |  0.47408 |   0.53506 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new                  |        0.49624 |  0.4664  |   0.52367 | 624 |         232 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    |        0.56598 |  0.46608 |   0.684   | 122 |          61 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.53615 |  0.44099 |   0.614   | 122 |          61 |
| particle_heldout | pid_separation        | ridge                                     |        0.52943 |  0.42806 |   0.63345 | 122 |          61 |
| particle_heldout | pid_separation        | 1d_cnn                                    |        0.49449 |  0.35101 |   0.62251 | 122 |          61 |
| particle_heldout | pid_separation        | spectral_transformer_new                  |        0.48078 |  0.3643  |   0.59508 | 122 |          61 |
| particle_heldout | pid_separation        | mlp                                       |        0.46721 |  0.40066 |   0.5485  | 122 |          61 |
| particle_heldout | energy_scale          | spectral_transformer_new                  |        0.16779 |  0.13667 |   0.18918 | 122 |             |
| particle_heldout | energy_scale          | 1d_cnn                                    |        0.16967 |  0.14006 |   0.18666 | 122 |             |
| particle_heldout | energy_scale          | gradient_boosted_trees                    |        0.2009  |  0.14954 |   0.22608 | 122 |             |
| particle_heldout | energy_scale          | mlp                                       |        0.22076 |  0.18967 |   0.2797  | 122 |             |
| particle_heldout | energy_scale          | ridge                                     |        0.25137 |  0.20403 |   0.31983 | 122 |             |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.25519 |  0.22142 |   0.31905 | 122 |             |
| particle_heldout | pileup_sideband       | ridge                                     |        0.85889 |  0.81192 |   0.89859 | 122 |          50 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  |        0.84389 |  0.76383 |   0.90824 | 122 |          50 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.84139 |  0.77666 |   0.89179 | 122 |          50 |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    |        0.83528 |  0.77958 |   0.88709 | 122 |          50 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    |        0.76056 |  0.71093 |   0.80523 | 122 |          50 |
| particle_heldout | pileup_sideband       | mlp                                       |        0.74889 |  0.68799 |   0.79997 | 122 |          50 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    |        1       |  1       |   1       | 122 |          62 |
| particle_heldout | saturation_clipping   | ridge                                     |        0.93091 |  0.89746 |   0.9625  | 122 |          62 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.92581 |  0.89547 |   0.9549  | 122 |          62 |
| particle_heldout | saturation_clipping   | mlp                                       |        0.82876 |  0.76312 |   0.88264 | 122 |          62 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    |        0.70887 |  0.65449 |   0.76238 | 122 |          62 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  |        0.63522 |  0.54229 |   0.71926 | 122 |          62 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    |        1       |  1       |   1       | 122 |          10 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.99107 |  0.98221 |   1       | 122 |          10 |
| particle_heldout | pedestal_noise_color  | ridge                                     |        0.99107 |  0.98314 |   1       | 122 |          10 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  |        0.97589 |  0.94918 |   1       | 122 |          10 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    |        0.92232 |  0.86975 |   0.97224 | 122 |          10 |
| particle_heldout | pedestal_noise_color  | mlp                                       |        0.8     |  0.67386 |   0.9375  | 122 |          10 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    |        0.57123 |  0.47275 |   0.68075 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  |        0.53758 |  0.44555 |   0.65391 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    |        0.51235 |  0.40165 |   0.61747 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | mlp                                       |        0.49579 |  0.45963 |   0.52888 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.47327 |  0.33967 |   0.61301 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | ridge                                     |        0.45129 |  0.32684 |   0.56361 | 122 |          55 |

## Calibration

| split_name       | method                                    |     auc |       ece |   n |   positives |
|:-----------------|:------------------------------------------|--------:|----------:|----:|------------:|
| particle_heldout | 1d_cnn                                    | 0.49449 | 0.057417  | 122 |          61 |
| particle_heldout | gradient_boosted_trees                    | 0.56598 | 0.16985   | 122 |          61 |
| particle_heldout | mlp                                       | 0.46721 | 0.1843    | 122 |          61 |
| particle_heldout | ridge                                     | 0.52943 | 0.034516  | 122 |          61 |
| particle_heldout | spectral_transformer_new                  | 0.48078 | 0.059349  | 122 |          61 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | 0.53615 | 0.023625  | 122 |          61 |
| run_heldout      | 1d_cnn                                    | 0.51079 | 0.013901  | 624 |         311 |
| run_heldout      | gradient_boosted_trees                    | 0.50535 | 0.24598   | 624 |         311 |
| run_heldout      | mlp                                       | 0.49756 | 0.056405  | 624 |         311 |
| run_heldout      | ridge                                     | 0.51854 | 0.067922  | 624 |         311 |
| run_heldout      | spectral_transformer_new                  | 0.48179 | 0.0088467 | 624 |         311 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | 0.52207 | 0.075771  | 624 |         311 |

## Paired Bootstrap Deltas vs Traditional

| split_name       | endpoint              | method                   |   delta_vs_traditional |      ci_low |    ci_high | delta_definition                                             |
|:-----------------|:----------------------|:-------------------------|-----------------------:|------------:|-----------:|:-------------------------------------------------------------|
| particle_heldout | energy_scale          | 1d_cnn                   |            -0.092657   | -0.14201    | -0.061621  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | gradient_boosted_trees   |            -0.066049   | -0.1186     | -0.026142  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | mlp                      |            -0.035233   | -0.097451   |  0.020186  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | ridge                    |            -0.0082457  | -0.042469   |  0.032872  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | spectral_transformer_new |            -0.097431   | -0.15577    | -0.063852  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | 1d_cnn                   |            -0.0691     | -0.11612    | -0.016745  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees   |             0.0078406  |  0          |  0.017655  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | mlp                      |            -0.19045    | -0.3069     | -0.067712  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | ridge                    |            -0.00014425 | -0.0050468  |  0.0034276 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new |            -0.015099   | -0.046822   |  0.0062339 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | 1d_cnn                   |            -0.04667    | -0.1504     |  0.059236  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | gradient_boosted_trees   |             0.0251     | -0.066447   |  0.12247   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | mlp                      |            -0.068211   | -0.17822    |  0.024499  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | ridge                    |            -0.0069243  | -0.031451   |  0.018905  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | spectral_transformer_new |            -0.065167   | -0.17882    |  0.045469  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | 1d_cnn                   |            -0.083936   | -0.1588     | -0.016778  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | gradient_boosted_trees   |            -0.0058148  | -0.057971   |  0.053189  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | mlp                      |            -0.095211   | -0.15131    | -0.046496  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | ridge                    |             0.018428   | -0.0043861  |  0.039802  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | spectral_transformer_new |             0.0086539  | -0.09012    |  0.0842    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                   |             0.044234   | -0.15588    |  0.21328   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees   |             0.090398   | -0.039713   |  0.22515   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | mlp                      |             0.019548   | -0.13151    |  0.15869   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | ridge                    |            -0.025653   | -0.078833   |  0.02073   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new |             0.066564   | -0.0765     |  0.22203   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | 1d_cnn                   |            -0.21657    | -0.30031    | -0.14615   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | gradient_boosted_trees   |             0.072917   |  0.042486   |  0.10885   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | mlp                      |            -0.096615   | -0.14306    | -0.052771  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | ridge                    |             0.0026807  | -0.014426   |  0.014396  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | spectral_transformer_new |            -0.29181    | -0.40119    | -0.18325   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | 1d_cnn                   |             0.040843   |  0.011833   |  0.071599  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | gradient_boosted_trees   |             0.0010385  | -0.020729   |  0.01711   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | mlp                      |             0.10177    |  0.0757     |  0.13285   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | ridge                    |            -0.0083189  | -0.026977   |  0.008575  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | spectral_transformer_new |             0.0412     |  0.0085032  |  0.081004  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | 1d_cnn                   |            -0.11664    | -0.1514     | -0.088669  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees   |             0.014472   |  0.00022586 |  0.04154   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | mlp                      |            -0.1716     | -0.25701    | -0.11746   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | ridge                    |             0.0072704  |  0.0018829  |  0.015233  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new |            -0.099703   | -0.13707    | -0.071641  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | 1d_cnn                   |            -0.01118    | -0.055391   |  0.035355  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | gradient_boosted_trees   |            -0.015797   | -0.054605   |  0.019316  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | mlp                      |            -0.026915   | -0.07577    |  0.019481  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | ridge                    |            -0.0023865  | -0.025958   |  0.019591  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | spectral_transformer_new |            -0.041874   | -0.099428   |  0.0042215 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | 1d_cnn                   |            -0.19365    | -0.2151     | -0.16936   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | gradient_boosted_trees   |             0.014598   | -0.0050389  |  0.036912  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | mlp                      |            -0.096269   | -0.11237    | -0.078097  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | ridge                    |             0.0042806  | -0.0013336  |  0.010593  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | spectral_transformer_new |            -0.14425    | -0.17228    | -0.10982   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                   |            -0.093678   | -0.1251     | -0.058064  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees   |            -0.026401   | -0.075845   |  0.027108  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | mlp                      |            -0.084949   | -0.12822    | -0.040999  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | ridge                    |            -0.00053123 | -0.010042   |  0.0076136 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new |            -0.10143    | -0.16118    | -0.059095  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | 1d_cnn                   |            -0.29704    | -0.31716    | -0.27758   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | gradient_boosted_trees   |             0.070247   |  0.052056   |  0.084627  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | mlp                      |            -0.33058    | -0.35916    | -0.29986   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | ridge                    |            -0.013105   | -0.020203   | -0.0056684 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | spectral_transformer_new |            -0.29422    | -0.31498    | -0.27095   | AUC gain for classification; sigma68 increase for regression |

## Stratified Systematics

| split_name       | endpoint       | stratum_axis         | stratum                          |   n | metric   |   value |
|:-----------------|:---------------|:---------------------|:---------------------------------|----:|:---------|--------:|
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_high                        |  41 | sigma68  | 0.20292 |
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_low                         |  41 | sigma68  | 0.18217 |
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_mid                         |  40 | sigma68  | 0.11427 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_memory                  |  41 | sigma68  | 0.19196 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_mid                     |  40 | sigma68  | 0.19846 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_quiet                   |  41 | sigma68  | 0.20758 |
| particle_heldout | energy_scale   | pulse_shape_bin      | high_harmonic                    |  41 | sigma68  | 0.154   |
| particle_heldout | energy_scale   | pulse_shape_bin      | low_harmonic                     |  41 | sigma68  | 0.21628 |
| particle_heldout | energy_scale   | pulse_shape_bin      | mid_harmonic                     |  40 | sigma68  | 0.1915  |
| particle_heldout | energy_scale   | energy_bin           | energy_high                      |  41 | sigma68  | 0.13502 |
| particle_heldout | energy_scale   | energy_bin           | energy_low                       |  41 | sigma68  | 0.13791 |
| particle_heldout | energy_scale   | energy_bin           | energy_mid                       |  40 | sigma68  | 0.11745 |
| particle_heldout | energy_scale   | particle_family      | external_high_energy_tail_family | 122 | sigma68  | 0.2009  |
| particle_heldout | energy_scale   | pileup_flag          | pileup_truth                     |  50 | sigma68  | 0.14639 |
| particle_heldout | energy_scale   | pileup_flag          | single_truth                     |  72 | sigma68  | 0.21818 |
| particle_heldout | energy_scale   | saturation_flag      | linear_truth                     |  60 | sigma68  | 0.17039 |
| particle_heldout | energy_scale   | saturation_flag      | saturation_truth                 |  62 | sigma68  | 0.18798 |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_high                        |  41 | auc      | 0.53828 |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_low                         |  41 | auc      | 0.5     |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_mid                         |  40 | auc      | 0.63889 |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_memory                  |  41 | auc      | 0.44762 |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_mid                     |  40 | auc      | 0.5625  |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_quiet                   |  41 | auc      | 0.67381 |
| particle_heldout | pid_separation | pulse_shape_bin      | high_harmonic                    |  41 | auc      | 0.66667 |
| particle_heldout | pid_separation | pulse_shape_bin      | low_harmonic                     |  41 | auc      | 0.47549 |
| particle_heldout | pid_separation | pulse_shape_bin      | mid_harmonic                     |  40 | auc      | 0.52685 |
| particle_heldout | pid_separation | energy_bin           | energy_high                      |  41 | auc      | 0.43333 |
| particle_heldout | pid_separation | energy_bin           | energy_low                       |  41 | auc      | 0.6348  |
| particle_heldout | pid_separation | energy_bin           | energy_mid                       |  40 | auc      | 0.66162 |
| particle_heldout | pid_separation | particle_family      | external_high_energy_tail_family | 122 | auc      | 0.56598 |
| particle_heldout | pid_separation | pileup_flag          | pileup_truth                     |  50 | auc      | 0.65189 |
| particle_heldout | pid_separation | pileup_flag          | single_truth                     |  72 | auc      | 0.49844 |
| particle_heldout | pid_separation | saturation_flag      | linear_truth                     |  60 | auc      | 0.5692  |
| particle_heldout | pid_separation | saturation_flag      | saturation_truth                 |  62 | auc      | 0.55277 |
| run_heldout      | energy_scale   | tail_amplitude_bin   | tail_high                        | 208 | sigma68  | 0.29417 |
| run_heldout      | energy_scale   | tail_amplitude_bin   | tail_low                         | 208 | sigma68  | 0.34282 |

## Leakage and Feature Audits

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |   pid_ece | external_truth_leakage_risk                                                                   |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|----------:|:----------------------------------------------------------------------------------------------|
| particle_heldout | 1d_cnn                                    |   0.49449 |          0.16967 |         0.51235 |        0.92232 | 0.057417  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | gradient_boosted_trees                    |   0.56598 |          0.2009  |         0.57123 |        1       | 0.16985   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | mlp                                       |   0.46721 |          0.22076 |         0.49579 |        0.8     | 0.1843    | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | ridge                                     |   0.52943 |          0.25137 |         0.45129 |        0.99107 | 0.034516  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | spectral_transformer_new                  |   0.48078 |          0.16779 |         0.53758 |        0.97589 | 0.059349  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.53615 |          0.25519 |         0.47327 |        0.99107 | 0.023625  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | 1d_cnn                                    |   0.51079 |          0.34497 |         0.5009  |        0.84585 | 0.013901  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | gradient_boosted_trees                    |   0.50535 |          0.30719 |         0.56783 |        0.9758  | 0.24598   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | mlp                                       |   0.49756 |          0.40924 |         0.50708 |        0.79467 | 0.056405  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | ridge                                     |   0.51854 |          0.29668 |         0.59333 |        0.96804 | 0.067922  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | spectral_transformer_new                  |   0.48179 |          0.34127 |         0.49624 |        0.86194 | 0.0088467 | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.52207 |          0.30622 |         0.59421 |        0.96083 | 0.075771  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |

Feature-family audit:

| feature                   | family                         |
|:--------------------------|:-------------------------------|
| tail_10_17_over_total     | charge_comparison_psd          |
| tail_12_17_over_total     | charge_comparison_psd          |
| tail_14_17_over_total     | charge_comparison_psd          |
| early_0_4_over_total      | charge_comparison_psd          |
| middle_5_9_over_total     | charge_comparison_psd          |
| late_minus_early_asym     | charge_comparison_psd          |
| rise_10_50                | rise_time_width                |
| rise_20_80                | rise_time_width                |
| width20                   | rise_time_width                |
| width50                   | rise_time_width                |
| max_rise_step             | zero_crossing_derivative       |
| max_fall_step             | zero_crossing_derivative       |
| zero_crossings_derivative | zero_crossing_derivative       |
| mean_time                 | mean_time_moments              |
| time_variance             | mean_time_moments              |
| time_skewness             | mean_time_moments              |
| time_kurtosis             | mean_time_moments              |
| fft_k1_fraction           | frequency_domain_fft           |
| fft_k2_fraction           | frequency_domain_fft           |
| fft_high_over_low         | frequency_domain_fft           |
| cfd20_time                | constant_fraction_shape_ratios |
| cfd50_time                | constant_fraction_shape_ratios |
| le_ratio_s4_s7            | constant_fraction_shape_ratios |
| le_ratio_s5_s7            | constant_fraction_shape_ratios |
| cf_ratio_s6_s8            | constant_fraction_shape_ratios |
| haar_l0_d00               | wavelet_haar                   |
| haar_l0_d01               | wavelet_haar                   |
| haar_l0_d02               | wavelet_haar                   |
| haar_l0_d03               | wavelet_haar                   |
| haar_l0_d04               | wavelet_haar                   |
| haar_l0_d05               | wavelet_haar                   |
| haar_l0_d06               | wavelet_haar                   |
| haar_l0_d07               | wavelet_haar                   |
| haar_l1_d00               | wavelet_haar                   |
| haar_l1_d01               | wavelet_haar                   |
| haar_l1_d02               | wavelet_haar                   |
| haar_l1_d03               | wavelet_haar                   |
| haar_l2_d00               | wavelet_haar                   |
| haar_l2_d01               | wavelet_haar                   |
| haar_l3_d00               | wavelet_haar                   |

## Caveats

- The benchmark is keyed digitized GEANT4 truth, not a direct event-by-event truth label for the real HRD run stream.
- The G4-08 bridge does not contain run 42, so the S32c run-held-out list is preserved by intersection rather than by adding unavailable data.
- The ADC/MeV scale in the digitized bridge is a ranking calibration, not a final detector energy calibration.
- Bootstrap intervals cover held-out run transfer within this bridge and do not include GEANT4 physics-list or material-budget uncertainty.
- Pedestal labels are independent pretrigger residual labels; they are not a zero-signal electronics truth campaign.

## Verdict

`result.json` names **gradient_boosted_trees** as the winner. Relative to S32c, the key scientific change is that PID and energy targets are externally supplied by GEANT4 rather than defined from waveform thresholds; this substantially reduces self-referential proxy leakage while retaining explicit tail and pedestal stress tests.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s32d_1783887596_850_1c4d2571_external_truth_pid_energy_tail_pedestal_validation.py --config configs/s32d_1783887596_850_1c4d2571_external_truth_pid_energy_tail_pedestal_validation.json
```

