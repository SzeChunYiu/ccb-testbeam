# S55c: ARX Pedestal-Memory Deconvolution Versus Multitask Neural Pulse Representations

## Abstract

Ticket `2484` asks whether a strong ARX/Kalman-style pedestal-memory deconvolution remains competitive with learned waveform representations when timing, pile-up, energy, and PID endpoints are scored by held-out run. This study first reproduces the canonical raw B-stack selected-pulse count from `h101/HRDv`, then uses the keyed digitized-GEANT4 bridge as an endpoint truth panel. The compared methods are the requested traditional ARX comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pedestal-memory transformer-style multitask head. The winner written to `result.json` is **gradient_boosted_trees**.

## Raw ROOT Reproduction

For each raw `hrdb_run_NNNN.root`, `h101/HRDv` is reshaped to `(event, channel, sample)`. B2/B4/B6/B8 use baseline `b_c=median(x_c[0:4])`; a pulse is selected when `max_t(x_c(t)-b_c)>1000 ADC`.

| quantity                      | report_value | reproduced | delta | pass |
| ----------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses | 640737       | 640737     | 0     | True |

## External Truth Join

The raw ROOT reproduction is the non-negotiable anchor; the keyed G4-08 digitizer artifact is used only after that anchor passes, because S55c needs endpoint labels for energy, PID, pile-up, and true time. The scoring table is joined only through `(daq_run, EVENTNO, EVT, TRIGGER, g4_entry, digitizer_seed, native_row)`, never by run order.

| check                              | value | pass |
| ---------------------------------- | ----- | ---- |
| external_digitized_rows            | 1056  | True |
| native_key_joined_rows             | 1056  | True |
| duplicate_native_keys_in_truth     | 0     | True |
| duplicate_native_keys_in_digitized | 0     | True |

## Methods

The traditional comparator is `traditional_ar1_deltaE_over_E`. It estimates pre-peak pedestal memory with an ARX/Kalman surrogate coefficient `phi=sum_t Delta x_t Delta x_{t-1}/sum_t Delta x_{t-1}^2`, an innovation RMS `sqrt(mean((Delta x_t-phi Delta x_{t-1})^2))`, baseline magnitude, charge, depth, and a sparse dE/E-like deconvolution proxy. Separate heads predict PID, log-energy, pedestal offset, pile-up state, and first-pulse time.

Ridge uses L2-regularized logistic and linear models on the full pulse-shape plus pedestal feature set. Gradient-boosted trees fit shallow histogram-boosted classifiers/regressors. The MLP row is a deterministic random-feature ReLU network with logistic/ridge output heads, used to avoid local iterative-neural instability while still testing a nonlinear dense representation. The 1D-CNN row uses a bank of temporal convolution filters over the 18 samples followed by learned heads. The new architecture, `pedestal_memory_transformer_multitask_new`, is a compact transformer-style surrogate: pedestal gates act as attention weights over the temporal filter bank, and multitask boosted heads share the gated representation for PID, energy, pedestal, pile-up, and timing. This is sensible here because S55c is explicitly a pedestal-memory multitask benchmark.

The winner minimizes `0.26(1-BAcc_PID)+0.24 sigma68_E+0.18 RMS_ped/RMS_ped,median+0.14 sigma68_t/sigma68_t,median+0.10(1-BAcc_pileup)+0.08 ECE_PID`. Energy residuals are `(Ehat-E_G4)/E_G4`; `sigma68=0.5(Q84-Q16)`. Confidence intervals are 95% percentile intervals from held-out-run bootstrap resampling.

## Held-Out Results

| method                                    | winner_score | pid_auc | pid_balanced_accuracy | pid_ece  | energy_fractional_sigma68 | pedestal_residual_rms_adc | timing_jitter_ns | pileup_balanced_accuracy |
| ----------------------------------------- | ------------ | ------- | --------------------- | -------- | ------------------------- | ------------------------- | ---------------- | ------------------------ |
| gradient_boosted_trees                    | 0.4105       | 0.88366 | 0.82393               | 0.098476 | 0.26785                   | 28.172                    | 2.3369           | 0.72917                  |
| ridge                                     | 0.43966      | 0.78364 | 0.73591               | 0.098095 | 0.29412                   | 28.172                    | 2.3369           | 0.72917                  |
| mlp                                       | 0.46846      | 0.73099 | 0.68359               | 0.10548  | 0.35501                   | 28.172                    | 2.3369           | 0.72917                  |
| traditional_ar1_deltaE_over_E             | 0.73523      | 0.82911 | 0.76739               | 0.14509  | 0.32692                   | 46.506                    | 5.9266           | 0.68333                  |
| pedestal_memory_transformer_multitask_new | 1.0451       | 0.87708 | 0.82809               | 0.090022 | 0.28071                   | 152.13                    | 2.9234           | 0.69792                  |
| 1d_cnn                                    | 1.0604       | 0.78534 | 0.75115               | 0.086487 | 0.33981                   | 150.75                    | 2.7096           | 0.69792                  |

## Bootstrap Confidence Intervals

| method                                    | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high | pedestal_residual_rms_adc_ci_low | pedestal_residual_rms_adc_ci_high | timing_jitter_ns_ci_low | timing_jitter_ns_ci_high | pileup_balanced_accuracy_ci_low | pileup_balanced_accuracy_ci_high |
| ----------------------------------------- | -------------------------------- | --------------------------------- | -------------------------------- | --------------------------------- | ----------------------- | ------------------------ | ------------------------------- | -------------------------------- |
| gradient_boosted_trees                    | 0.2407                           | 0.29985                           | 19.371                           | 35.711                            | 2.0599                  | 2.5343                   | 0.71875                         | 0.74375                          |
| ridge                                     | 0.27069                          | 0.32106                           | 18.976                           | 36.734                            | 2.1141                  | 2.5461                   | 0.71875                         | 0.74583                          |
| mlp                                       | 0.34182                          | 0.37143                           | 18.976                           | 36.227                            | 2.1141                  | 2.5473                   | 0.71875                         | 0.74583                          |
| traditional_ar1_deltaE_over_E             | 0.30623                          | 0.34906                           | 32.918                           | 59.129                            | 5.5621                  | 6.3432                   | 0.6625                          | 0.70635                          |
| pedestal_memory_transformer_multitask_new | 0.23892                          | 0.29381                           | 74.852                           | 202.15                            | 2.738                   | 3.1152                   | 0.6625                          | 0.7375                           |
| 1d_cnn                                    | 0.31406                          | 0.37859                           | 75.278                           | 205.3                             | 2.555                   | 2.8797                   | 0.66875                         | 0.72708                          |

## True PID Confusion

| method                                    | pid_confusion_tn | pid_confusion_fp | pid_confusion_fn | pid_confusion_tp | pid_balanced_accuracy | pid_balanced_accuracy_ci_low | pid_balanced_accuracy_ci_high |
| ----------------------------------------- | ---------------- | ---------------- | ---------------- | ---------------- | --------------------- | ---------------------------- | ----------------------------- |
| gradient_boosted_trees                    | 190              | 55               | 30               | 205              | 0.82393               | 0.79387                      | 0.8633                        |
| ridge                                     | 199              | 46               | 80               | 155              | 0.73591               | 0.71248                      | 0.75712                       |
| mlp                                       | 189              | 56               | 95               | 140              | 0.68359               | 0.66917                      | 0.70086                       |
| traditional_ar1_deltaE_over_E             | 204              | 41               | 70               | 165              | 0.76739               | 0.7525                       | 0.7808                        |
| pedestal_memory_transformer_multitask_new | 191              | 54               | 29               | 206              | 0.82809               | 0.8079                       | 0.85287                       |
| 1d_cnn                                    | 195              | 50               | 69               | 166              | 0.75115               | 0.7198                       | 0.78719                       |

## Run-Held-Out Stability

| method                                    | heldout_run | pid_balanced_accuracy | energy_fractional_sigma68 | pedestal_residual_rms_adc | timing_jitter_ns | pileup_balanced_accuracy | pid_ece  | n_events |
| ----------------------------------------- | ----------- | --------------------- | ------------------------- | ------------------------- | ---------------- | ------------------------ | -------- | -------- |
| 1d_cnn                                    | 58          | 0.73617               | 0.32438                   | 237.68                    | 2.8715           | 0.73958                  | 0.11286  | 96       |
| 1d_cnn                                    | 60          | 0.77083               | 0.34424                   | 116.21                    | 2.8949           | 0.73958                  | 0.14509  | 96       |
| 1d_cnn                                    | 62          | 0.70951               | 0.39643                   | 71.07                     | 2.5257           | 0.66667                  | 0.094003 | 96       |
| 1d_cnn                                    | 64          | 0.72619               | 0.29039                   | 190.31                    | 2.815            | 0.67708                  | 0.17709  | 96       |
| 1d_cnn                                    | 65          | 0.81634               | 0.33852                   | 48.61                     | 2.4651           | 0.66667                  | 0.16324  | 96       |
| gradient_boosted_trees                    | 58          | 0.8475                | 0.26445                   | 41.512                    | 2.5787           | 0.76042                  | 0.11592  | 96       |
| gradient_boosted_trees                    | 60          | 0.88542               | 0.28292                   | 21.549                    | 2.2906           | 0.72917                  | 0.073179 | 96       |
| gradient_boosted_trees                    | 62          | 0.78007               | 0.25565                   | 19.712                    | 2.4819           | 0.71875                  | 0.15467  | 96       |
| gradient_boosted_trees                    | 64          | 0.79497               | 0.23029                   | 33.358                    | 2.0892           | 0.71875                  | 0.146    | 96       |
| gradient_boosted_trees                    | 65          | 0.81176               | 0.32741                   | 16.718                    | 2.4392           | 0.71875                  | 0.12291  | 96       |
| mlp                                       | 58          | 0.70243               | 0.32868                   | 41.512                    | 2.5787           | 0.76042                  | 0.096837 | 96       |
| mlp                                       | 60          | 0.69792               | 0.36512                   | 21.549                    | 2.2906           | 0.72917                  | 0.14939  | 96       |
| mlp                                       | 62          | 0.65805               | 0.3553                    | 19.712                    | 2.4819           | 0.71875                  | 0.15977  | 96       |
| mlp                                       | 64          | 0.67063               | 0.3383                    | 33.358                    | 2.0892           | 0.71875                  | 0.17789  | 96       |
| mlp                                       | 65          | 0.68824               | 0.33968                   | 16.718                    | 2.4392           | 0.71875                  | 0.14189  | 96       |
| pedestal_memory_transformer_multitask_new | 58          | 0.83873               | 0.21881                   | 241.49                    | 3.0714           | 0.76042                  | 0.10497  | 96       |
| pedestal_memory_transformer_multitask_new | 60          | 0.875                 | 0.28922                   | 115.71                    | 3.084            | 0.63542                  | 0.0413   | 96       |
| pedestal_memory_transformer_multitask_new | 62          | 0.80091               | 0.23751                   | 70.03                     | 2.7335           | 0.72917                  | 0.18039  | 96       |
| pedestal_memory_transformer_multitask_new | 64          | 0.80688               | 0.29391                   | 191.58                    | 3.1662           | 0.6875                   | 0.13211  | 96       |
| pedestal_memory_transformer_multitask_new | 65          | 0.82288               | 0.28658                   | 49.074                    | 2.6295           | 0.67708                  | 0.094368 | 96       |
| ridge                                     | 58          | 0.75843               | 0.29914                   | 41.512                    | 2.5787           | 0.76042                  | 0.12179  | 96       |
| ridge                                     | 60          | 0.70833               | 0.32546                   | 21.549                    | 2.2906           | 0.72917                  | 0.15642  | 96       |
| ridge                                     | 62          | 0.69974               | 0.26367                   | 19.712                    | 2.4819           | 0.71875                  | 0.10351  | 96       |
| ridge                                     | 64          | 0.75                  | 0.27038                   | 33.358                    | 2.0892           | 0.71875                  | 0.15814  | 96       |
| ridge                                     | 65          | 0.76209               | 0.28312                   | 16.718                    | 2.4392           | 0.71875                  | 0.10692  | 96       |
| traditional_ar1_deltaE_over_E             | 58          | 0.76248               | 0.32776                   | 67.177                    | 6.2044           | 0.6875                   | 0.19091  | 96       |
| traditional_ar1_deltaE_over_E             | 60          | 0.73958               | 0.32502                   | 35.186                    | 6.4351           | 0.64583                  | 0.2429   | 96       |
| traditional_ar1_deltaE_over_E             | 62          | 0.78224               | 0.35                      | 33.47                     | 5.1158           | 0.72917                  | 0.1405   | 96       |
| traditional_ar1_deltaE_over_E             | 64          | 0.76587               | 0.28836                   | 54.621                    | 5.7306           | 0.6875                   | 0.16423  | 96       |
| traditional_ar1_deltaE_over_E             | 65          | 0.78301               | 0.33663                   | 30.976                    | 5.5651           | 0.66667                  | 0.12066  | 96       |

## Pedestal-State Counterfactuals

The table reports mean deuteron probability by held-out pedestal state. The span is a counterfactual sensitivity proxy: a large span means a method's PID score still moves with pedestal memory after the external truth join.

| method                                    | pedestal_state | mean_pid_score | counterfactual_span |
| ----------------------------------------- | -------------- | -------------- | ------------------- |
| 1d_cnn                                    | memory         | 0.49107        | 0.023238            |
| 1d_cnn                                    | middle         | 0.47311        | 0.023238            |
| 1d_cnn                                    | quiet          | 0.46783        | 0.023238            |
| gradient_boosted_trees                    | memory         | 0.50495        | 0.011195            |
| gradient_boosted_trees                    | middle         | 0.49702        | 0.011195            |
| gradient_boosted_trees                    | quiet          | 0.49376        | 0.011195            |
| mlp                                       | memory         | 0.42717        | 0.033713            |
| mlp                                       | middle         | 0.43817        | 0.033713            |
| mlp                                       | quiet          | 0.46089        | 0.033713            |
| pedestal_memory_transformer_multitask_new | memory         | 0.5071         | 0.014184            |
| pedestal_memory_transformer_multitask_new | middle         | 0.49291        | 0.014184            |
| pedestal_memory_transformer_multitask_new | quiet          | 0.50101        | 0.014184            |
| ridge                                     | memory         | 0.45442        | 0.024097            |
| ridge                                     | middle         | 0.45266        | 0.024097            |
| ridge                                     | quiet          | 0.47676        | 0.024097            |
| traditional_ar1_deltaE_over_E             | memory         | 0.49276        | 0.017642            |
| traditional_ar1_deltaE_over_E             | middle         | 0.49524        | 0.017642            |
| traditional_ar1_deltaE_over_E             | quiet          | 0.4776         | 0.017642            |

## Saturation-Mask Stress Test

The saturation-mask stress test recomputes headline endpoints after removing rows with `truth_saturation_label=1`. Large positive deltas in error-like quantities would indicate that a method's apparent held-out performance is dependent on saturated pulses rather than robust pedestal-memory handling.

| method                                    | n_all | n_unsaturated | saturated_fraction | delta_pid_balanced_accuracy_unsaturated_minus_all | delta_energy_sigma68_unsaturated_minus_all | delta_timing_jitter_ns_unsaturated_minus_all |
| ----------------------------------------- | ----- | ------------- | ------------------ | ------------------------------------------------- | ------------------------------------------ | -------------------------------------------- |
| 1d_cnn                                    | 480   | 301           | 0.37292            | -0.027913                                         | 0.020367                                   | -0.24466                                     |
| gradient_boosted_trees                    | 480   | 301           | 0.37292            | -0.0059824                                        | 0.051604                                   | -0.034385                                    |
| mlp                                       | 480   | 301           | 0.37292            | -0.031074                                         | -0.012541                                  | -0.034385                                    |
| pedestal_memory_transformer_multitask_new | 480   | 301           | 0.37292            | -0.01364                                          | 0.046024                                   | -0.22213                                     |
| ridge                                     | 480   | 301           | 0.37292            | -0.029784                                         | 0.032922                                   | -0.034385                                    |
| traditional_ar1_deltaE_over_E             | 480   | 301           | 0.37292            | -0.011362                                         | 0.021949                                   | 0.13533                                      |

## Feature and Systematic Audits

Feature families inherited from the local pulse-shape benchmark are augmented with raw baseline, AR(1) coefficient, innovation RMS, dE/E proxy, and depth. Counterfactual pedestal-shift and saturation-mask stress tests are summarized in `pedestal_counterfactuals.csv` and by the saturation/pile-up metrics above. The principal systematic limitations are the small keyed external sample, the hybrid GEANT4 digitization scale, and the fact that run-block bootstrap covers observed run variation but not ungenerated beam conditions.

| feature                   | family                         |
| ------------------------- | ------------------------------ |
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

## Caveats

- The raw ROOT reproduction uses the full B-stack mirror, but the multitask endpoint benchmark is limited to the 1,056 keyed digitized rows available from G4-08.
- GEANT4 labels are external to the HRD waveform proxy, but the digitized waveforms are hybrid template/residual constructions rather than a fresh detector readout.
- Pedestal counterfactuals are observational state substitutions; they diagnose sensitivity, not a randomized hardware intervention.
- The conclusion is therefore about survival under the available keyed external truth join, not a final beamline PID calibration.

## Verdict

`gradient_boosted_trees` wins the S55c registered composite score. Relative to `traditional_ar1_deltaE_over_E`, the result tests whether learned representations improve jointly on pedestal residual RMS, timing jitter, pile-up separation, energy bias/resolution, and PID calibration under held-out runs; the full numerical comparison is in `result.json` and `method_summary.csv`.

## Reproducibility

```bash
uv run --extra root python scripts/ticket_2484_s55c_arx_pedestal_memory_benchmark.py --config configs/ticket_2484_s55c_arx_pedestal_memory_benchmark.json
```

