# S36d: External PID-Label Join for Pedestal-Memory Calibration

## Abstract

Ticket `1784065854.140549.01267a91` asks whether the S36c pedestal-memory gains survive an event-level external PID/truth join. This rerun first reproduces the canonical raw B-stack selected-pulse count, then joins the keyed digitized-GEANT4 truth rows using native DAQ keys, and finally benchmarks AR(1) traditional calibration against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual temporal CNN. The winner written to `result.json` is **gradient_boosted_trees**.

## Raw ROOT Reproduction

For each raw `hrdb_run_NNNN.root`, `h101/HRDv` is reshaped to `(event, channel, sample)`. B2/B4/B6/B8 use baseline `b_c=median(x_c[0:4])`; a pulse is selected when `max_t(x_c(t)-b_c)>1000 ADC`.

| quantity                      |   report_value |   reproduced |   delta | pass   |
|:------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses |         640737 |       640737 |       0 | True   |

## External Truth Join

The external labels are read from the G4-08 keyed digitizer artifact. The scoring table is joined only through `(daq_run, EVENTNO, EVT, TRIGGER, g4_entry, digitizer_seed, native_row)`, never by run order.

| check                              |   value | pass   |
|:-----------------------------------|--------:|:-------|
| external_digitized_rows            |    1056 | True   |
| native_key_joined_rows             |    1056 | True   |
| duplicate_native_keys_in_truth     |       0 | True   |
| duplicate_native_keys_in_digitized |       0 | True   |

## Methods

The traditional comparator is `traditional_ar1_deltaE_over_E`. It estimates pre-peak pedestal memory with an AR(1) coefficient `phi=sum_t Delta x_t Delta x_{t-1}/sum_t Delta x_{t-1}^2`, an innovation RMS, baseline magnitude, charge, depth, and a dE/E-like proxy; PID is a balanced logistic likelihood and energy is a log-linear calibration.

Ridge uses L2-regularized logistic and linear models on the full pulse-shape plus pedestal feature set. Gradient-boosted trees fit shallow histogram-boosted classifiers/regressors. The MLP row is a deterministic random-feature ReLU network with logistic/ridge output heads, used to avoid the local MKL instability in iterative neural trainers. The 1D-CNN row uses a bank of temporal convolution filters over the 18 samples followed by learned logistic/ridge heads. The new architecture, `pedestal_memory_gated_residual_cnn_new`, gates those convolution channels with AR(1)/pedestal features and applies a boosted residual correction to log-energy, which is sensible here because the ticket is specifically about pedestal-memory calibration surviving external PID truth.

The winner minimizes `0.42(1-BAcc_PID)+0.34 sigma68_E+0.14 span_ped+0.10 ECE_PID`. Energy residuals are `(Ehat-E_G4)/E_G4`; `sigma68=0.5(Q84-Q16)`. Confidence intervals are 95% percentile intervals from held-out-run bootstrap resampling.

## Held-Out Results

| method                                 |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_ece |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   pedestal_counterfactual_span |
|:---------------------------------------|---------------:|----------:|------------------------:|----------:|----------------------------:|-----------------------------------:|------------------------------------:|-------------------------------:|
| gradient_boosted_trees                 |        0.17644 |   0.88366 |                 0.82393 |  0.098476 |                     0.26785 |                            0.24113 |                             0.29911 |                       0.011195 |
| pedestal_memory_gated_residual_cnn_new |        0.17863 |   0.87708 |                 0.82809 |  0.090022 |                     0.28071 |                            0.24313 |                             0.2949  |                       0.014184 |
| ridge                                  |        0.2241  |   0.78364 |                 0.73591 |  0.098095 |                     0.29413 |                            0.27168 |                             0.32106 |                       0.024097 |
| traditional_ar1_deltaE_over_E          |        0.22583 |   0.82911 |                 0.76739 |  0.14509  |                     0.32692 |                            0.30871 |                             0.35013 |                       0.017642 |
| 1d_cnn                                 |        0.23195 |   0.78534 |                 0.75115 |  0.086487 |                     0.33981 |                            0.31407 |                             0.37858 |                       0.023238 |
| mlp                                    |        0.2562  |   0.76855 |                 0.71932 |  0.092544 |                     0.35598 |                            0.33687 |                             0.37044 |                       0.057372 |

## True PID Confusion

| method                                 |   pid_confusion_tn |   pid_confusion_fp |   pid_confusion_fn |   pid_confusion_tp |   pid_balanced_accuracy |   pid_balanced_accuracy_ci_low |   pid_balanced_accuracy_ci_high |
|:---------------------------------------|-------------------:|-------------------:|-------------------:|-------------------:|------------------------:|-------------------------------:|--------------------------------:|
| gradient_boosted_trees                 |                190 |                 55 |                 30 |                205 |                 0.82393 |                        0.79382 |                         0.8633  |
| pedestal_memory_gated_residual_cnn_new |                191 |                 54 |                 29 |                206 |                 0.82809 |                        0.80728 |                         0.85512 |
| ridge                                  |                199 |                 46 |                 80 |                155 |                 0.73591 |                        0.71291 |                         0.75766 |
| traditional_ar1_deltaE_over_E          |                204 |                 41 |                 70 |                165 |                 0.76739 |                        0.75286 |                         0.78195 |
| 1d_cnn                                 |                195 |                 50 |                 69 |                166 |                 0.75115 |                        0.71941 |                         0.78191 |
| mlp                                    |                194 |                 51 |                 83 |                152 |                 0.71932 |                        0.69703 |                         0.74328 |

## Run-Held-Out Stability

| method                                 |   heldout_run |   pid_balanced_accuracy |   energy_fractional_sigma68 |   pid_ece |   n_events |   n_deuteron |
|:---------------------------------------|--------------:|------------------------:|----------------------------:|----------:|-----------:|-------------:|
| 1d_cnn                                 |            58 |                 0.73617 |                     0.32438 |  0.11286  |         96 |           39 |
| 1d_cnn                                 |            60 |                 0.77083 |                     0.34424 |  0.14509  |         96 |           48 |
| 1d_cnn                                 |            62 |                 0.70951 |                     0.39643 |  0.094003 |         96 |           49 |
| 1d_cnn                                 |            64 |                 0.72619 |                     0.29039 |  0.17709  |         96 |           54 |
| 1d_cnn                                 |            65 |                 0.81634 |                     0.33852 |  0.16324  |         96 |           45 |
| gradient_boosted_trees                 |            58 |                 0.8475  |                     0.26445 |  0.11592  |         96 |           39 |
| gradient_boosted_trees                 |            60 |                 0.88542 |                     0.28292 |  0.073179 |         96 |           48 |
| gradient_boosted_trees                 |            62 |                 0.78007 |                     0.25565 |  0.15467  |         96 |           49 |
| gradient_boosted_trees                 |            64 |                 0.79497 |                     0.23029 |  0.146    |         96 |           54 |
| gradient_boosted_trees                 |            65 |                 0.81176 |                     0.32741 |  0.12291  |         96 |           45 |
| mlp                                    |            58 |                 0.74494 |                     0.32861 |  0.096341 |         96 |           39 |
| mlp                                    |            60 |                 0.75    |                     0.36521 |  0.14908  |         96 |           48 |
| mlp                                    |            62 |                 0.67803 |                     0.36236 |  0.11188  |         96 |           49 |
| mlp                                    |            64 |                 0.69577 |                     0.32664 |  0.17573  |         96 |           54 |
| mlp                                    |            65 |                 0.73137 |                     0.34433 |  0.1255   |         96 |           45 |
| pedestal_memory_gated_residual_cnn_new |            58 |                 0.83873 |                     0.21881 |  0.10497  |         96 |           39 |
| pedestal_memory_gated_residual_cnn_new |            60 |                 0.875   |                     0.28922 |  0.0413   |         96 |           48 |
| pedestal_memory_gated_residual_cnn_new |            62 |                 0.80091 |                     0.23751 |  0.18039  |         96 |           49 |
| pedestal_memory_gated_residual_cnn_new |            64 |                 0.80688 |                     0.29391 |  0.13211  |         96 |           54 |
| pedestal_memory_gated_residual_cnn_new |            65 |                 0.82288 |                     0.28658 |  0.094368 |         96 |           45 |
| ridge                                  |            58 |                 0.75843 |                     0.29913 |  0.12179  |         96 |           39 |
| ridge                                  |            60 |                 0.70833 |                     0.32546 |  0.15642  |         96 |           48 |
| ridge                                  |            62 |                 0.69974 |                     0.26367 |  0.10351  |         96 |           49 |
| ridge                                  |            64 |                 0.75    |                     0.27039 |  0.15814  |         96 |           54 |
| ridge                                  |            65 |                 0.76209 |                     0.28312 |  0.10692  |         96 |           45 |
| traditional_ar1_deltaE_over_E          |            58 |                 0.76248 |                     0.32776 |  0.19091  |         96 |           39 |
| traditional_ar1_deltaE_over_E          |            60 |                 0.73958 |                     0.32502 |  0.2429   |         96 |           48 |
| traditional_ar1_deltaE_over_E          |            62 |                 0.78224 |                     0.35    |  0.1405   |         96 |           49 |
| traditional_ar1_deltaE_over_E          |            64 |                 0.76587 |                     0.28836 |  0.16423  |         96 |           54 |
| traditional_ar1_deltaE_over_E          |            65 |                 0.78301 |                     0.33663 |  0.12066  |         96 |           45 |

## Pedestal-State Counterfactuals

The table reports mean deuteron probability by held-out pedestal state. The span is a counterfactual sensitivity proxy: a large span means a method's PID score still moves with pedestal memory after the external truth join.

| method                                 | pedestal_state   |   mean_pid_score |   counterfactual_span |
|:---------------------------------------|:-----------------|-----------------:|----------------------:|
| 1d_cnn                                 | memory           |          0.49107 |              0.023238 |
| 1d_cnn                                 | middle           |          0.47311 |              0.023238 |
| 1d_cnn                                 | quiet            |          0.46783 |              0.023238 |
| gradient_boosted_trees                 | memory           |          0.50495 |              0.011195 |
| gradient_boosted_trees                 | middle           |          0.49702 |              0.011195 |
| gradient_boosted_trees                 | quiet            |          0.49376 |              0.011195 |
| mlp                                    | memory           |          0.42788 |              0.057372 |
| mlp                                    | middle           |          0.48525 |              0.057372 |
| mlp                                    | quiet            |          0.4718  |              0.057372 |
| pedestal_memory_gated_residual_cnn_new | memory           |          0.5071  |              0.014184 |
| pedestal_memory_gated_residual_cnn_new | middle           |          0.49291 |              0.014184 |
| pedestal_memory_gated_residual_cnn_new | quiet            |          0.50101 |              0.014184 |
| ridge                                  | memory           |          0.45442 |              0.024097 |
| ridge                                  | middle           |          0.45266 |              0.024097 |
| ridge                                  | quiet            |          0.47676 |              0.024097 |
| traditional_ar1_deltaE_over_E          | memory           |          0.49276 |              0.017642 |
| traditional_ar1_deltaE_over_E          | middle           |          0.49524 |              0.017642 |
| traditional_ar1_deltaE_over_E          | quiet            |          0.4776  |              0.017642 |

## Feature and Systematic Audits

Feature families inherited from the local pulse-shape benchmark are augmented with raw baseline, AR(1) coefficient, innovation RMS, dE/E proxy, and depth. The principal systematic limitations are the small keyed external sample, the hybrid GEANT4 digitization scale, and the fact that run-block bootstrap covers observed run variation but not ungenerated beam conditions.

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

## Caveats

- The raw ROOT reproduction uses the full B-stack mirror, but the external-truth benchmark is limited to the 1,056 keyed digitized rows available from G4-08.
- GEANT4 labels are external to the HRD waveform proxy, but the digitized waveforms are hybrid template/residual constructions rather than a fresh detector readout.
- Pedestal counterfactuals are observational state substitutions; they diagnose sensitivity, not a randomized hardware intervention.
- The conclusion is therefore about survival under the available keyed external truth join, not a final beamline PID calibration.

## Verdict

`gradient_boosted_trees` wins the S36d registered score. Relative to `traditional_ar1_deltaE_over_E`, the external-join result tests whether the proxy gains survive true PID confusion and calibrated energy residuals; the full numerical comparison is in `result.json` and `method_summary.csv`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s36d_1784065854_140549_01267a91_external_pid_pedestal_memory_benchmark.py --config configs/s36d_1784065854_140549_01267a91_external_pid_pedestal_memory_benchmark.json
```

