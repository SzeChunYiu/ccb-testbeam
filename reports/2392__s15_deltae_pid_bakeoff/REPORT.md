# S15: dE-E Particle ID p-vs-d Traditional/ML Bakeoff

Ticket: `#2392`  
Worker: `testbeam-laptop-3`  
Raw ROOT directory: `/home/billy/ccb-data/data/extracted/root/root`  
GEANT4 bridge: `reports/1783883140.39222.3c4045b1__g4_08_keyed_digitized_geant4_native_join/digitized_g4_08_keyed.root`  
Pre-registered metric: run-held-out PID ROC AUC with bootstrap 95% CI; `winner` is selected by this PID metric, while the registered multi-endpoint joint loss is reported as secondary context.

## Abstract

S15 benchmarks event-by-event proton/deuteron particle identification with a strong traditional dE-E/tail/pedestal likelihood baseline and five ML/NN competitors. The raw B-stack selected-pulse reproduction gate is **640,737**, matching the registered **640,737** pulses exactly. On the pre-registered run-held-out PID ROC AUC metric, `result.json` names **traditional_dE_E_tail_pedestal_likelihood** as the winner. The secondary multi-endpoint joint-loss winner is **gradient_boosted_trees**.

## Raw ROOT Reproduction

The reproduction gate opens every configured `hrdb_run_XXXX.root` file at `h101/HRDv`, reshapes each record to `(event, channel, sample)`, subtracts the median of samples 0-3 for each channel, and selects B2/B4/B6/B8 pulses whose corrected maximum exceeds 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|---|
| selected B-stave pulses | 640,737 | 640,737 | 0 | True |

## External Truth Construction

The benchmark labels are read from the keyed G4-08 digitized bridge. GEANT4 truth defines the PID target as dominant Sci_bar PDG, with proton `2212` mapped to 0 and deuteron `1000010020` mapped to 1. The calibrated energy target is `E_i = sum_h EDep_ih` over B-stack Sci_bar hits, evaluated as the run/stave-centered residual of `log(1+E_i)`.

The digitized waveform branch `HRDv_digitized` supplies the 18-sample ADC-like pulse. It preserves raw residual templates and native DAQ keys while the labels come from GEANT4, so PID and energy are no longer deterministic functions of the target waveform features as in S32c.

## Splits and Bootstrap

Requested held-out runs were `[42, 50, 57, 58, 60, 62, 64, 65]`; the keyed G4-08 bridge contains `[50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 62, 64, 65]`, so the run-held-out test uses the available intersection `[50, 57, 58, 60, 62, 64, 65]`. The particle-held-out split removes `external_high_energy_tail_family` from training. Bootstrap CIs resample held-out run blocks with replacement using `260` replicates.

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
| particle_heldout | 1d_cnn                                    |      0.32966 |           0.36974 |          0.51035 |        0.16283 |           0.77167 |               0.61613 |                0.94911 |                 0.43284 |
| run_heldout      | 1d_cnn                                    |      0.40982 |           0.36974 |          0.5119  |        0.34081 |           0.58268 |               0.63818 |                0.73075 |                 0.50596 |
| particle_heldout | spectral_transformer_new                  |      0.32084 |           0.37297 |          0.50524 |        0.16895 |           0.8275  |               0.63952 |                0.94375 |                 0.48657 |
| run_heldout      | spectral_transformer_new                  |      0.4251  |           0.37297 |          0.511   |        0.34375 |           0.59231 |               0.54262 |                0.64451 |                 0.50089 |
| particle_heldout | mlp                                       |      0.34683 |           0.38854 |          0.55738 |        0.28439 |           0.74889 |               0.61935 |                0.94107 |                 0.49254 |
| run_heldout      | mlp                                       |      0.43024 |           0.38854 |          0.5083  |        0.42915 |           0.65064 |               0.61762 |                0.77263 |                 0.49397 |

## Endpoint Bootstrap CIs

| split_name       | endpoint              | method                                    |   metric_value |   ci_low |   ci_high |   n |   positives |
|:-----------------|:----------------------|:------------------------------------------|---------------:|---------:|----------:|----:|------------:|
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.52207 |  0.49332 |   0.5636  | 624 |         311 |
| run_heldout      | pid_separation        | ridge                                     |        0.51854 |  0.48009 |   0.56478 | 624 |         311 |
| run_heldout      | pid_separation        | 1d_cnn                                    |        0.5119  |  0.46674 |   0.55559 | 624 |         311 |
| run_heldout      | pid_separation        | spectral_transformer_new                  |        0.511   |  0.47032 |   0.55638 | 624 |         311 |
| run_heldout      | pid_separation        | mlp                                       |        0.5083  |  0.48503 |   0.52933 | 624 |         311 |
| run_heldout      | pid_separation        | gradient_boosted_trees                    |        0.50535 |  0.46773 |   0.54333 | 624 |         311 |
| run_heldout      | energy_scale          | ridge                                     |        0.29668 |  0.27713 |   0.32279 | 624 |             |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.30622 |  0.28726 |   0.32593 | 624 |             |
| run_heldout      | energy_scale          | gradient_boosted_trees                    |        0.30719 |  0.28503 |   0.3247  | 624 |             |
| run_heldout      | energy_scale          | 1d_cnn                                    |        0.34081 |  0.31754 |   0.39211 | 624 |             |
| run_heldout      | energy_scale          | spectral_transformer_new                  |        0.34375 |  0.3063  |   0.38393 | 624 |             |
| run_heldout      | energy_scale          | mlp                                       |        0.42915 |  0.392   |   0.46699 | 624 |             |
| run_heldout      | pileup_sideband       | gradient_boosted_trees                    |        0.79658 |  0.77591 |   0.82399 | 624 |         312 |
| run_heldout      | pileup_sideband       | ridge                                     |        0.78548 |  0.76208 |   0.81204 | 624 |         312 |
| run_heldout      | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.78131 |  0.75097 |   0.81385 | 624 |         312 |
| run_heldout      | pileup_sideband       | mlp                                       |        0.65064 |  0.61059 |   0.70088 | 624 |         312 |
| run_heldout      | pileup_sideband       | spectral_transformer_new                  |        0.59231 |  0.56359 |   0.61845 | 624 |         312 |
| run_heldout      | pileup_sideband       | 1d_cnn                                    |        0.58268 |  0.53579 |   0.63927 | 624 |         312 |
| run_heldout      | saturation_clipping   | gradient_boosted_trees                    |        1       |  1       |   1       | 624 |         248 |
| run_heldout      | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.92956 |  0.91169 |   0.94671 | 624 |         248 |
| run_heldout      | saturation_clipping   | ridge                                     |        0.91679 |  0.89883 |   0.93332 | 624 |         248 |
| run_heldout      | saturation_clipping   | 1d_cnn                                    |        0.63818 |  0.61737 |   0.66009 | 624 |         248 |
| run_heldout      | saturation_clipping   | mlp                                       |        0.61762 |  0.57308 |   0.66095 | 624 |         248 |
| run_heldout      | saturation_clipping   | spectral_transformer_new                  |        0.54262 |  0.51413 |   0.56969 | 624 |         248 |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees                    |        0.9758  |  0.9555  |   0.99107 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | ridge                                     |        0.96804 |  0.92586 |   0.9877  | 624 |          57 |
| run_heldout      | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.96083 |  0.91682 |   0.98561 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | mlp                                       |        0.77263 |  0.66881 |   0.84969 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | 1d_cnn                                    |        0.73075 |  0.67836 |   0.77577 | 624 |          57 |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new                  |        0.64451 |  0.59586 |   0.68938 | 624 |          57 |
| run_heldout      | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.59421 |  0.55642 |   0.6385  | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | ridge                                     |        0.59333 |  0.5542  |   0.63219 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees                    |        0.56783 |  0.5313  |   0.60445 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                                    |        0.50596 |  0.47035 |   0.53081 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new                  |        0.50089 |  0.47596 |   0.52515 | 624 |         232 |
| run_heldout      | pulse_shape_harmonics | mlp                                       |        0.49397 |  0.47074 |   0.50972 | 624 |         232 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    |        0.56598 |  0.46163 |   0.66484 | 122 |          61 |
| particle_heldout | pid_separation        | mlp                                       |        0.55738 |  0.47599 |   0.64153 | 122 |          61 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.53615 |  0.4499  |   0.63955 | 122 |          61 |
| particle_heldout | pid_separation        | ridge                                     |        0.52943 |  0.4274  |   0.63962 | 122 |          61 |
| particle_heldout | pid_separation        | 1d_cnn                                    |        0.51035 |  0.42266 |   0.61465 | 122 |          61 |
| particle_heldout | pid_separation        | spectral_transformer_new                  |        0.50524 |  0.37295 |   0.63041 | 122 |          61 |
| particle_heldout | energy_scale          | 1d_cnn                                    |        0.16283 |  0.13541 |   0.18841 | 122 |             |
| particle_heldout | energy_scale          | spectral_transformer_new                  |        0.16895 |  0.13796 |   0.18838 | 122 |             |
| particle_heldout | energy_scale          | gradient_boosted_trees                    |        0.2009  |  0.14707 |   0.22713 | 122 |             |
| particle_heldout | energy_scale          | ridge                                     |        0.25137 |  0.20282 |   0.31669 | 122 |             |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.25519 |  0.21961 |   0.32651 | 122 |             |
| particle_heldout | energy_scale          | mlp                                       |        0.28439 |  0.23995 |   0.34921 | 122 |             |
| particle_heldout | pileup_sideband       | ridge                                     |        0.85889 |  0.80962 |   0.89749 | 122 |          50 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.84139 |  0.78251 |   0.90604 | 122 |          50 |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    |        0.83528 |  0.7834  |   0.8956  | 122 |          50 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  |        0.8275  |  0.74131 |   0.89761 | 122 |          50 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    |        0.77167 |  0.69328 |   0.85926 | 122 |          50 |
| particle_heldout | pileup_sideband       | mlp                                       |        0.74889 |  0.69236 |   0.80805 | 122 |          50 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    |        1       |  1       |   1       | 122 |          62 |
| particle_heldout | saturation_clipping   | ridge                                     |        0.93091 |  0.89813 |   0.96356 | 122 |          62 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.92581 |  0.89509 |   0.95551 | 122 |          62 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  |        0.63952 |  0.53556 |   0.71761 | 122 |          62 |
| particle_heldout | saturation_clipping   | mlp                                       |        0.61935 |  0.57118 |   0.67332 | 122 |          62 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    |        0.61613 |  0.52166 |   0.71092 | 122 |          62 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    |        1       |  1       |   1       | 122 |          10 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.99107 |  0.98124 |   1       | 122 |          10 |
| particle_heldout | pedestal_noise_color  | ridge                                     |        0.99107 |  0.98173 |   1       | 122 |          10 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    |        0.94911 |  0.88529 |   0.99409 | 122 |          10 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  |        0.94375 |  0.8644  |   0.99602 | 122 |          10 |
| particle_heldout | pedestal_noise_color  | mlp                                       |        0.94107 |  0.85452 |   0.99613 | 122 |          10 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    |        0.57123 |  0.48007 |   0.67906 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | mlp                                       |        0.49254 |  0.47344 |   0.5     | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  |        0.48657 |  0.40335 |   0.56733 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.47327 |  0.35408 |   0.62449 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | ridge                                     |        0.45129 |  0.33369 |   0.56175 | 122 |          55 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    |        0.43284 |  0.32898 |   0.54487 | 122 |          55 |

## Calibration

| split_name       | method                                    |     auc |        ece |   n |   positives |
|:-----------------|:------------------------------------------|--------:|-----------:|----:|------------:|
| particle_heldout | 1d_cnn                                    | 0.51035 | 0.052099   | 122 |          61 |
| particle_heldout | gradient_boosted_trees                    | 0.56598 | 0.16985    | 122 |          61 |
| particle_heldout | mlp                                       | 0.55738 | 0.10417    | 122 |          61 |
| particle_heldout | ridge                                     | 0.52943 | 0.034516   | 122 |          61 |
| particle_heldout | spectral_transformer_new                  | 0.50524 | 0.066491   | 122 |          61 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | 0.53615 | 0.023625   | 122 |          61 |
| run_heldout      | 1d_cnn                                    | 0.5119  | 0.00059401 | 624 |         311 |
| run_heldout      | gradient_boosted_trees                    | 0.50535 | 0.24598    | 624 |         311 |
| run_heldout      | mlp                                       | 0.5083  | 0.021968   | 624 |         311 |
| run_heldout      | ridge                                     | 0.51854 | 0.067922   | 624 |         311 |
| run_heldout      | spectral_transformer_new                  | 0.511   | 0.0041615  | 624 |         311 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | 0.52207 | 0.075771   | 624 |         311 |

## PID Method Table

| split_name       | method                                    |   metric_value |   ci_low |   ci_high |   n |   positives |
|:-----------------|:------------------------------------------|---------------:|---------:|----------:|----:|------------:|
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |        0.52207 |  0.49332 |   0.5636  | 624 |         311 |
| run_heldout      | ridge                                     |        0.51854 |  0.48009 |   0.56478 | 624 |         311 |
| run_heldout      | 1d_cnn                                    |        0.5119  |  0.46674 |   0.55559 | 624 |         311 |
| run_heldout      | spectral_transformer_new                  |        0.511   |  0.47032 |   0.55638 | 624 |         311 |
| run_heldout      | mlp                                       |        0.5083  |  0.48503 |   0.52933 | 624 |         311 |
| run_heldout      | gradient_boosted_trees                    |        0.50535 |  0.46773 |   0.54333 | 624 |         311 |
| particle_heldout | gradient_boosted_trees                    |        0.56598 |  0.46163 |   0.66484 | 122 |          61 |
| particle_heldout | mlp                                       |        0.55738 |  0.47599 |   0.64153 | 122 |          61 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |        0.53615 |  0.4499  |   0.63955 | 122 |          61 |
| particle_heldout | ridge                                     |        0.52943 |  0.4274  |   0.63962 | 122 |          61 |
| particle_heldout | 1d_cnn                                    |        0.51035 |  0.42266 |   0.61465 | 122 |          61 |
| particle_heldout | spectral_transformer_new                  |        0.50524 |  0.37295 |   0.63041 | 122 |          61 |

## Paired Bootstrap Deltas vs Traditional

| split_name       | endpoint              | method                   |   delta_vs_traditional |     ci_low |    ci_high | delta_definition                                             |
|:-----------------|:----------------------|:-------------------------|-----------------------:|-----------:|-----------:|:-------------------------------------------------------------|
| particle_heldout | energy_scale          | 1d_cnn                   |            -0.099781   | -0.15436   | -0.066859  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | gradient_boosted_trees   |            -0.068714   | -0.11474   | -0.032457  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | mlp                      |             0.027934   | -0.024219  |  0.075483  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | ridge                    |            -0.0078633  | -0.042448  |  0.030176  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | spectral_transformer_new |            -0.091272   | -0.14461   | -0.055568  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | 1d_cnn                   |            -0.041067   | -0.10293   |  0.0054128 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees   |             0.0083436  |  0         |  0.018951  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | mlp                      |            -0.046957   | -0.12225   |  0         | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | ridge                    |            -0.000207   | -0.00506   |  0.0038213 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new |            -0.047054   | -0.1292    |  0.0052293 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | 1d_cnn                   |            -0.029821   | -0.15641   |  0.089158  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | gradient_boosted_trees   |             0.023828   | -0.078143  |  0.12055   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | mlp                      |             0.01037    | -0.12951   |  0.1559    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | ridge                    |            -0.008032   | -0.038707  |  0.018131  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | spectral_transformer_new |            -0.035663   | -0.14404   |  0.071696  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | 1d_cnn                   |            -0.064039   | -0.15222   |  0.011168  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | gradient_boosted_trees   |            -0.0028726  | -0.054541  |  0.048271  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | mlp                      |            -0.092731   | -0.13997   | -0.052181  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | ridge                    |             0.017957   | -0.0018092 |  0.038759  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | spectral_transformer_new |            -0.015391   | -0.089378  |  0.049423  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                   |            -0.04708    | -0.22484   |  0.12718   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees   |             0.10499    | -0.025743  |  0.26036   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | mlp                      |             0.020679   | -0.11016   |  0.13965   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | ridge                    |            -0.023571   | -0.071248  |  0.022062  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new |             0.013573   | -0.13016   |  0.1715    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | 1d_cnn                   |            -0.31919    | -0.43378   | -0.20418   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | gradient_boosted_trees   |             0.069738   |  0.035651  |  0.10415   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | mlp                      |            -0.30782    | -0.35232   | -0.25977   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | ridge                    |             0.0028882  | -0.013667  |  0.01368   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | spectral_transformer_new |            -0.28984    | -0.4118    | -0.17033   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | 1d_cnn                   |             0.041283   |  0.0080621 |  0.088151  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | gradient_boosted_trees   |             0.0019257  | -0.018747  |  0.020128  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | mlp                      |             0.126      |  0.087601  |  0.16467   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | ridge                    |            -0.0083466  | -0.023834  |  0.0091026 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | spectral_transformer_new |             0.040503   |  0.013863  |  0.077498  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | 1d_cnn                   |            -0.22864    | -0.2849    | -0.18413   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees   |             0.01495    |  0.0012029 |  0.039121  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | mlp                      |            -0.19211    | -0.26625   | -0.12863   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | ridge                    |             0.0075245  |  0.0026535 |  0.014549  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new |            -0.31941    | -0.35063   | -0.28991   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | 1d_cnn                   |            -0.0095069  | -0.054044  |  0.034519  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | gradient_boosted_trees   |            -0.014759   | -0.047218  |  0.019217  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | mlp                      |            -0.01375    | -0.070219  |  0.036835  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | ridge                    |            -0.0024928  | -0.023746  |  0.021034  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | spectral_transformer_new |            -0.011196   | -0.0524    |  0.034369  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | 1d_cnn                   |            -0.19822    | -0.24464   | -0.15919   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | gradient_boosted_trees   |             0.015981   | -0.0041427 |  0.036025  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | mlp                      |            -0.13013    | -0.15435   | -0.10175   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | ridge                    |             0.0041072  | -0.0016099 |  0.0095293 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | spectral_transformer_new |            -0.18959    | -0.21494   | -0.16475   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                   |            -0.09066    | -0.14504   | -0.038377  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees   |            -0.026346   | -0.073523  |  0.020144  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | mlp                      |            -0.10083    | -0.15942   | -0.054188  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | ridge                    |            -0.00092203 | -0.010578  |  0.0098257 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new |            -0.093409   | -0.13035   | -0.05742   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | 1d_cnn                   |            -0.29122    | -0.30821   | -0.27241   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | gradient_boosted_trees   |             0.070053   |  0.05303   |  0.084927  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | mlp                      |            -0.31258    | -0.34346   | -0.27953   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | ridge                    |            -0.012166   | -0.019669  | -0.0030554 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | spectral_transformer_new |            -0.38623    | -0.41666   | -0.35581   | AUC gain for classification; sigma68 increase for regression |

## Stratified Systematics

| split_name       | endpoint       | stratum_axis         | stratum                          |   n | metric   |   value |
|:-----------------|:---------------|:---------------------|:---------------------------------|----:|:---------|--------:|
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_high                        |  41 | sigma68  | 0.27935 |
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_low                         |  41 | sigma68  | 0.23366 |
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_mid                         |  40 | sigma68  | 0.15745 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_memory                  |  41 | sigma68  | 0.25906 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_mid                     |  40 | sigma68  | 0.28106 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_quiet                   |  41 | sigma68  | 0.23424 |
| particle_heldout | energy_scale   | pulse_shape_bin      | high_harmonic                    |  41 | sigma68  | 0.20059 |
| particle_heldout | energy_scale   | pulse_shape_bin      | low_harmonic                     |  41 | sigma68  | 0.27262 |
| particle_heldout | energy_scale   | pulse_shape_bin      | mid_harmonic                     |  40 | sigma68  | 0.3212  |
| particle_heldout | energy_scale   | energy_bin           | energy_high                      |  41 | sigma68  | 0.2425  |
| particle_heldout | energy_scale   | energy_bin           | energy_low                       |  41 | sigma68  | 0.20002 |
| particle_heldout | energy_scale   | energy_bin           | energy_mid                       |  40 | sigma68  | 0.2472  |
| particle_heldout | energy_scale   | particle_family      | external_high_energy_tail_family | 122 | sigma68  | 0.25519 |
| particle_heldout | energy_scale   | pileup_flag          | pileup_truth                     |  50 | sigma68  | 0.19097 |
| particle_heldout | energy_scale   | pileup_flag          | single_truth                     |  72 | sigma68  | 0.29764 |
| particle_heldout | energy_scale   | saturation_flag      | linear_truth                     |  60 | sigma68  | 0.27044 |
| particle_heldout | energy_scale   | saturation_flag      | saturation_truth                 |  62 | sigma68  | 0.20779 |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_high                        |  41 | auc      | 0.50478 |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_low                         |  41 | auc      | 0.63333 |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_mid                         |  40 | auc      | 0.46717 |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_memory                  |  41 | auc      | 0.45    |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_mid                     |  40 | auc      | 0.655   |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_quiet                   |  41 | auc      | 0.54048 |
| particle_heldout | pid_separation | pulse_shape_bin      | high_harmonic                    |  41 | auc      | 0.63571 |
| particle_heldout | pid_separation | pulse_shape_bin      | low_harmonic                     |  41 | auc      | 0.49755 |
| particle_heldout | pid_separation | pulse_shape_bin      | mid_harmonic                     |  40 | auc      | 0.51151 |
| particle_heldout | pid_separation | energy_bin           | energy_high                      |  41 | auc      | 0.45897 |
| particle_heldout | pid_separation | energy_bin           | energy_low                       |  41 | auc      | 0.57598 |
| particle_heldout | pid_separation | energy_bin           | energy_mid                       |  40 | auc      | 0.62626 |
| particle_heldout | pid_separation | particle_family      | external_high_energy_tail_family | 122 | auc      | 0.53615 |
| particle_heldout | pid_separation | pileup_flag          | pileup_truth                     |  50 | auc      | 0.51232 |
| particle_heldout | pid_separation | pileup_flag          | single_truth                     |  72 | auc      | 0.54453 |
| particle_heldout | pid_separation | saturation_flag      | linear_truth                     |  60 | auc      | 0.51451 |
| particle_heldout | pid_separation | saturation_flag      | saturation_truth                 |  62 | auc      | 0.56635 |
| run_heldout      | energy_scale   | tail_amplitude_bin   | tail_high                        | 208 | sigma68  | 0.27074 |
| run_heldout      | energy_scale   | tail_amplitude_bin   | tail_low                         | 208 | sigma68  | 0.34401 |

## Leakage and Feature Audits

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |    pid_ece | external_truth_leakage_risk                                                                   |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|-----------:|:----------------------------------------------------------------------------------------------|
| particle_heldout | 1d_cnn                                    |   0.51035 |          0.16283 |         0.43284 |        0.94911 | 0.052099   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | gradient_boosted_trees                    |   0.56598 |          0.2009  |         0.57123 |        1       | 0.16985    | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | mlp                                       |   0.55738 |          0.28439 |         0.49254 |        0.94107 | 0.10417    | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | ridge                                     |   0.52943 |          0.25137 |         0.45129 |        0.99107 | 0.034516   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | spectral_transformer_new                  |   0.50524 |          0.16895 |         0.48657 |        0.94375 | 0.066491   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.53615 |          0.25519 |         0.47327 |        0.99107 | 0.023625   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | 1d_cnn                                    |   0.5119  |          0.34081 |         0.50596 |        0.73075 | 0.00059401 | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | gradient_boosted_trees                    |   0.50535 |          0.30719 |         0.56783 |        0.9758  | 0.24598    | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | mlp                                       |   0.5083  |          0.42915 |         0.49397 |        0.77263 | 0.021968   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | ridge                                     |   0.51854 |          0.29668 |         0.59333 |        0.96804 | 0.067922   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | spectral_transformer_new                  |   0.511   |          0.34375 |         0.50089 |        0.64451 | 0.0041615  | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.52207 |          0.30622 |         0.59421 |        0.96083 | 0.075771   | lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds |

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

- The benchmark is keyed digitized GEANT4 truth, not a direct event-by-event truth label for the real HRD run stream. This is the central S15 no-truth-label caveat.
- The G4-08 bridge does not contain run 42, so the requested run-held-out list is preserved by intersection rather than by adding unavailable data.
- The ADC/MeV scale in the digitized bridge is a ranking calibration, not a final detector energy calibration.
- Bootstrap intervals cover held-out run transfer within this bridge and do not include GEANT4 physics-list or material-budget uncertainty.
- Pedestal labels are independent pretrigger residual labels; they are not a zero-signal electronics truth campaign.

## Verdict

`result.json` names **traditional_dE_E_tail_pedestal_likelihood** as the S15 PID winner. The strong traditional dE-E baseline is reported on the same held-out rows and bootstrap blocks as the ML/NN methods; here it remains marginally ahead on run-held-out PID AUC, while **gradient_boosted_trees** is best for the secondary multi-endpoint loss. The result is a method benchmark and not an adopted event-by-event PID assignment for real beam data.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/ticket_2392_s15_deltae_pid_bakeoff.py --config configs/ticket_2392_s15_deltae_pid_bakeoff.json
```

