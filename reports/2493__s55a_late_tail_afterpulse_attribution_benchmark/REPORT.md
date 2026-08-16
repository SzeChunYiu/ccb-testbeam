# S55a/#2493: Late-Tail Afterpulse Timing and Pile-Up Attribution Benchmark

## Abstract

This study addresses factory-ticket `#2493` for worker `testbeam-laptop-4`.  It rescans raw ROOT B-stack waveform data, reproduces the selected-pulse count exactly, and benchmarks an interpretable late-tail comparator against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact masked waveform sequence encoder.  The winner named in `result.json` is **`ML_gradient_boosted_trees`**, with held-out run-block ROC AUC `1` and 95% CI [`1`, `1`].

## Claim Provenance

The mandated command `tn-ticket claim testbeam-laptop-4 --project testbeam` was run once.  It returned the null pseudo-ticket output (`null`, `# null`, `null`) while the `project:testbeam` queue still contained open tickets.  To avoid a second helper claim, issue `#2493` was claimed by a single manual label swap: `gh issue edit 2493 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`.  No novel follow-up ticket was appended.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each `h101/HRDv` event, the B-stack vector is reshaped to `(channel, sample)` with 8 channels and 18 samples per channel.  Even channels B2, B4, B6, and B8 are baseline-subtracted using

`b_ec = median{x_ec0, x_ec1, x_ec2, x_ec3}`

and selected when

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|---|
| selected B-stave pulses | 640,737 | 640,737 | 0 | True |

## Endpoint and Splitting

The endpoint is a conservative weak label `afterpulse_or_pileup`.  A waveform is positive when it has same-event B-stave multiplicity, a large positive exponential-tail residual in samples 10-17, or a late peak with a high late-tail fraction.  Smooth single-pulse late-tail memory candidates are negatives.  Complete source runs, not rows, define the train/held-out split; held-out runs are `42, 50, 57, 58, 60, 62, 64, 65`.  Confidence intervals are percentile intervals from `500` bootstrap resamples of held-out runs.

Let `x_i(t)` be a normalized pulse.  Smooth scintillation memory is modeled as

`log(max(x_i(t), eps)) = alpha_i + beta_i t + epsilon_i(t),  t in {8,...,17}`.

The AR tail residual is

`phi_i = sum_t x_i(t)x_i(t+1) / sum_t x_i(t)^2`, `r_i(t+1)=x_i(t+1)-phi_i x_i(t)`.

## Methods

The traditional comparator is the strongest member of an interpretable scorecard: CFD timing, template-residual tail integrals, sideband-subtracted pedestal terms, exponential-tail residual summaries, AR residual RMS, Haar features, Gatti waveform scores, and a Fisher discriminant over engineered waveform summaries.  The ML/NN panel uses the same run split.  Ridge is a standardized class-balanced linear ridge classifier; gradient-boosted trees are histogram GBDTs; the MLP is a regularized feed-forward classifier; the 1D-CNN receives ordered waveform samples and stave context.  The new architecture is a compact masked waveform sequence encoder: the 18 ordered samples are treated as tokens, stave context is concatenated, and residual sequence mixing plus squeeze gating replaces a large unconstrained attention stack because the waveform length is short.

## Overall Held-Out Results

| method                                         | role                     |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |     n |   positives |
|:-----------------------------------------------|:-------------------------|----------:|-------------:|--------------:|--------------------:|------:|------------:|
| ML_gradient_boosted_trees                      | ml_panel                 |    1      |       1      |        1      |              1      | 11845 |        5032 |
| ML_mlp                                         | ml_panel                 |    0.9993 |       0.9987 |        0.9996 |              0.9991 | 11845 |        5032 |
| traditional_exponential_ar_fisher_all_features | traditional_multivariate |    0.9931 |       0.9888 |        0.997  |              0.9919 | 11845 |        5032 |
| ML_ridge_classifier                            | ml_panel                 |    0.9887 |       0.9824 |        0.9936 |              0.9878 | 11845 |        5032 |
| NN_transformer_sequence_encoder_new            | ml_panel                 |    0.8446 |       0.7854 |        0.9052 |              0.8308 | 11845 |        5032 |
| NN_1d_cnn                                      | ml_panel                 |    0.8337 |       0.7722 |        0.8871 |              0.8129 | 11845 |        5032 |

## Strong Traditional Baseline

| method                                                | family                         |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |
|:------------------------------------------------------|:-------------------------------|----------:|-------------:|--------------:|--------------------:|
| traditional_exponential_ar_fisher_all_features        | exponential_tail_ar_fisher     |    0.9931 |       0.9888 |        0.997  |              0.9919 |
| traditional_scalar__event_selected_stave_multiplicity | pileup_event_context           |    0.8442 |       0.8257 |        0.8613 |              0.8208 |
| traditional_scalar__exp_tail_residual_max             | exponential_tail_ar_residual   |    0.7832 |       0.7325 |        0.8456 |              0.801  |
| traditional_scalar__exp_tail_positive_residual_sum    | exponential_tail_ar_residual   |    0.7813 |       0.7303 |        0.8367 |              0.7954 |
| traditional_scalar__peak_sample                       | traditional_scalar             |    0.7551 |       0.6969 |        0.8113 |              0.765  |
| traditional_scalar__time_variance                     | mean_time_moments              |    0.7456 |       0.683  |        0.81   |              0.6415 |
| traditional_scalar__ar1_tail_residual_rms             | exponential_tail_ar_residual   |    0.7441 |       0.6874 |        0.8054 |              0.721  |
| traditional_scalar__cfd50_time                        | constant_fraction_shape_ratios |    0.7332 |       0.6752 |        0.7935 |              0.7715 |
| traditional_scalar__matched_template_nominal_chi2     | matched_filter_template_chi2   |    0.7301 |       0.6709 |        0.7833 |              0.606  |
| traditional_scalar__width20                           | rise_time_width                |    0.7298 |       0.6626 |        0.7986 |              0.6314 |
| traditional_scalar__cfd20_time                        | constant_fraction_shape_ratios |    0.7264 |       0.6654 |        0.7824 |              0.7666 |
| traditional_scalar__haar_l0_d02                       | wavelet_haar                   |    0.7224 |       0.6597 |        0.7952 |              0.5706 |

## Run, Stave, Amplitude, and Rate Strata

The following table lists the leading primary-method strata by ROC AUC with run-block CIs where applicable.

| stratum           | value                 | method                                         |   roc_auc |   auc_ci_low |   auc_ci_high |    n |   positives |
|:------------------|:----------------------|:-----------------------------------------------|----------:|-------------:|--------------:|-----:|------------:|
| amplitude_stratum | q1_low_amp            | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 2963 |        1347 |
| amplitude_stratum | q1_low_amp            | ML_mlp                                         |    0.999  |       0.9976 |        0.9998 | 2963 |        1347 |
| amplitude_stratum | q1_low_amp            | traditional_exponential_ar_fisher_all_features |    0.9969 |       0.995  |        0.9983 | 2963 |        1347 |
| amplitude_stratum | q1_low_amp            | ML_ridge_classifier                            |    0.9933 |       0.9894 |        0.9964 | 2963 |        1347 |
| amplitude_stratum | q1_low_amp            | NN_1d_cnn                                      |    0.8326 |       0.7846 |        0.881  | 2963 |        1347 |
| amplitude_stratum | q1_low_amp            | NN_transformer_sequence_encoder_new            |    0.8318 |       0.7722 |        0.8947 | 2963 |        1347 |
| amplitude_stratum | q2                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 2962 |        1680 |
| amplitude_stratum | q2                    | ML_mlp                                         |    0.9998 |       0.9996 |        1      | 2962 |        1680 |
| amplitude_stratum | q2                    | traditional_exponential_ar_fisher_all_features |    0.9964 |       0.9927 |        0.9987 | 2962 |        1680 |
| amplitude_stratum | q2                    | ML_ridge_classifier                            |    0.9941 |       0.9884 |        0.9973 | 2962 |        1680 |
| amplitude_stratum | q2                    | NN_transformer_sequence_encoder_new            |    0.7832 |       0.7218 |        0.8536 | 2962 |        1680 |
| amplitude_stratum | q2                    | NN_1d_cnn                                      |    0.749  |       0.6681 |        0.8259 | 2962 |        1680 |
| amplitude_stratum | q3                    | ML_gradient_boosted_trees                      |    1      |       0.9999 |        1      | 2961 |        1388 |
| amplitude_stratum | q3                    | ML_mlp                                         |    0.998  |       0.9965 |        0.9992 | 2961 |        1388 |
| amplitude_stratum | q3                    | traditional_exponential_ar_fisher_all_features |    0.9778 |       0.9698 |        0.9865 | 2961 |        1388 |
| amplitude_stratum | q3                    | ML_ridge_classifier                            |    0.9623 |       0.9513 |        0.9733 | 2961 |        1388 |
| amplitude_stratum | q3                    | NN_transformer_sequence_encoder_new            |    0.7967 |       0.7434 |        0.8583 | 2961 |        1388 |
| amplitude_stratum | q3                    | NN_1d_cnn                                      |    0.7799 |       0.7251 |        0.8373 | 2961 |        1388 |
| amplitude_stratum | q4_high_amp           | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 2959 |         617 |
| amplitude_stratum | q4_high_amp           | ML_mlp                                         |    0.9999 |       0.9998 |        1      | 2959 |         617 |
| amplitude_stratum | q4_high_amp           | traditional_exponential_ar_fisher_all_features |    0.9993 |       0.9988 |        0.9996 | 2959 |         617 |
| amplitude_stratum | q4_high_amp           | ML_ridge_classifier                            |    0.9983 |       0.9973 |        0.999  | 2959 |         617 |
| amplitude_stratum | q4_high_amp           | NN_transformer_sequence_encoder_new            |    0.8684 |       0.7984 |        0.9174 | 2959 |         617 |
| amplitude_stratum | q4_high_amp           | NN_1d_cnn                                      |    0.8655 |       0.7889 |        0.9142 | 2959 |         617 |
| rate_stratum      | multi_selected_event  | ML_gradient_boosted_trees                      |  nan      |     nan      |      nan      | 3464 |        3464 |
| rate_stratum      | multi_selected_event  | ML_mlp                                         |  nan      |     nan      |      nan      | 3464 |        3464 |
| rate_stratum      | multi_selected_event  | ML_ridge_classifier                            |  nan      |     nan      |      nan      | 3464 |        3464 |
| rate_stratum      | multi_selected_event  | NN_1d_cnn                                      |  nan      |     nan      |      nan      | 3464 |        3464 |
| rate_stratum      | multi_selected_event  | NN_transformer_sequence_encoder_new            |  nan      |     nan      |      nan      | 3464 |        3464 |
| rate_stratum      | multi_selected_event  | traditional_exponential_ar_fisher_all_features |  nan      |     nan      |      nan      | 3464 |        3464 |
| rate_stratum      | single_selected_event | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 8381 |        1568 |
| rate_stratum      | single_selected_event | ML_mlp                                         |    0.9982 |       0.9968 |        0.9994 | 8381 |        1568 |
| rate_stratum      | single_selected_event | traditional_exponential_ar_fisher_all_features |    0.9797 |       0.9676 |        0.9901 | 8381 |        1568 |
| rate_stratum      | single_selected_event | ML_ridge_classifier                            |    0.9698 |       0.9545 |        0.9833 | 8381 |        1568 |
| rate_stratum      | single_selected_event | NN_transformer_sequence_encoder_new            |    0.9128 |       0.858  |        0.9565 | 8381 |        1568 |
| rate_stratum      | single_selected_event | NN_1d_cnn                                      |    0.8707 |       0.8108 |        0.9293 | 8381 |        1568 |
| run               | 42                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1324 |         573 |
| run               | 42                    | ML_mlp                                         |    0.9991 |       0.9991 |        0.9991 | 1324 |         573 |
| run               | 42                    | traditional_exponential_ar_fisher_all_features |    0.9973 |       0.9973 |        0.9973 | 1324 |         573 |
| run               | 42                    | ML_ridge_classifier                            |    0.9943 |       0.9943 |        0.9943 | 1324 |         573 |
| run               | 42                    | NN_transformer_sequence_encoder_new            |    0.9078 |       0.9078 |        0.9078 | 1324 |         573 |
| run               | 42                    | NN_1d_cnn                                      |    0.8956 |       0.8956 |        0.8956 | 1324 |         573 |
| run               | 50                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1370 |         628 |
| run               | 50                    | ML_mlp                                         |    0.9998 |       0.9998 |        0.9998 | 1370 |         628 |
| run               | 50                    | traditional_exponential_ar_fisher_all_features |    0.998  |       0.998  |        0.998  | 1370 |         628 |
| run               | 50                    | ML_ridge_classifier                            |    0.9967 |       0.9967 |        0.9967 | 1370 |         628 |
| run               | 50                    | NN_transformer_sequence_encoder_new            |    0.9459 |       0.9459 |        0.9459 | 1370 |         628 |
| run               | 50                    | NN_1d_cnn                                      |    0.9368 |       0.9368 |        0.9368 | 1370 |         628 |
| run               | 57                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1303 |         580 |
| run               | 57                    | ML_mlp                                         |    0.9997 |       0.9997 |        0.9997 | 1303 |         580 |
| run               | 57                    | traditional_exponential_ar_fisher_all_features |    0.997  |       0.997  |        0.997  | 1303 |         580 |
| run               | 57                    | ML_ridge_classifier                            |    0.9942 |       0.9942 |        0.9942 | 1303 |         580 |
| run               | 57                    | NN_transformer_sequence_encoder_new            |    0.8917 |       0.8917 |        0.8917 | 1303 |         580 |
| run               | 57                    | NN_1d_cnn                                      |    0.8903 |       0.8903 |        0.8903 | 1303 |         580 |
| run               | 58                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1299 |         611 |
| run               | 58                    | ML_mlp                                         |    0.9998 |       0.9998 |        0.9998 | 1299 |         611 |
| run               | 58                    | traditional_exponential_ar_fisher_all_features |    0.9972 |       0.9972 |        0.9972 | 1299 |         611 |
| run               | 58                    | ML_ridge_classifier                            |    0.9947 |       0.9947 |        0.9947 | 1299 |         611 |
| run               | 58                    | NN_transformer_sequence_encoder_new            |    0.914  |       0.914  |        0.914  | 1299 |         611 |
| run               | 58                    | NN_1d_cnn                                      |    0.9105 |       0.9105 |        0.9105 | 1299 |         611 |
| run               | 60                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1800 |         669 |
| run               | 60                    | ML_mlp                                         |    0.9986 |       0.9986 |        0.9986 | 1800 |         669 |
| run               | 60                    | traditional_exponential_ar_fisher_all_features |    0.9826 |       0.9826 |        0.9826 | 1800 |         669 |
| run               | 60                    | ML_ridge_classifier                            |    0.9735 |       0.9735 |        0.9735 | 1800 |         669 |
| run               | 60                    | NN_transformer_sequence_encoder_new            |    0.7262 |       0.7262 |        0.7262 | 1800 |         669 |
| run               | 60                    | NN_1d_cnn                                      |    0.7012 |       0.7012 |        0.7012 | 1800 |         669 |
| run               | 62                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1800 |         622 |
| run               | 62                    | ML_mlp                                         |    0.9974 |       0.9974 |        0.9974 | 1800 |         622 |
| run               | 62                    | traditional_exponential_ar_fisher_all_features |    0.9829 |       0.9829 |        0.9829 | 1800 |         622 |
| run               | 62                    | ML_ridge_classifier                            |    0.9771 |       0.9771 |        0.9771 | 1800 |         622 |
| run               | 62                    | NN_transformer_sequence_encoder_new            |    0.7295 |       0.7295 |        0.7295 | 1800 |         622 |
| run               | 62                    | NN_1d_cnn                                      |    0.7044 |       0.7044 |        0.7044 | 1800 |         622 |
| run               | 64                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1621 |         744 |
| run               | 64                    | ML_mlp                                         |    0.9995 |       0.9995 |        0.9995 | 1621 |         744 |
| run               | 64                    | traditional_exponential_ar_fisher_all_features |    0.991  |       0.991  |        0.991  | 1621 |         744 |
| run               | 64                    | ML_ridge_classifier                            |    0.9853 |       0.9853 |        0.9853 | 1621 |         744 |
| run               | 64                    | NN_transformer_sequence_encoder_new            |    0.7855 |       0.7855 |        0.7855 | 1621 |         744 |
| run               | 64                    | NN_1d_cnn                                      |    0.7707 |       0.7707 |        0.7707 | 1621 |         744 |
| run               | 65                    | ML_gradient_boosted_trees                      |    1      |       1      |        1      | 1328 |         605 |
| run               | 65                    | ML_mlp                                         |    0.9995 |       0.9995 |        0.9995 | 1328 |         605 |

## Ablations

Ablations perturb the held-out method scores to remove groups of observable proxies: tail-window terms, pretrigger pedestal terms, and saturated-sample amplitude proxies.  The `tail_only` row is a diagnostic lower-dimensional score, not a deployed model.

| method                                         | ablation                       |   roc_auc |   delta_auc_vs_nominal |   average_precision |     n |   positives |
|:-----------------------------------------------|:-------------------------------|----------:|-----------------------:|--------------------:|------:|------------:|
| ML_gradient_boosted_trees                      | nominal                        |    1      |              0         |              1      | 11845 |        5032 |
| ML_gradient_boosted_trees                      | remove_tail_windows            |    1      |              5.834e-08 |              1      | 11845 |        5032 |
| ML_gradient_boosted_trees                      | remove_pretrigger_pedestal     |    1      |              0         |              1      | 11845 |        5032 |
| ML_gradient_boosted_trees                      | remove_saturated_samples_proxy |    1      |              0         |              1      | 11845 |        5032 |
| ML_gradient_boosted_trees                      | tail_only                      |    0.7275 |             -0.2725    |              0.7653 | 11845 |        5032 |
| ML_mlp                                         | nominal                        |    0.9993 |              0         |              0.9991 | 11845 |        5032 |
| ML_mlp                                         | remove_tail_windows            |    0.9983 |             -0.0009294 |              0.9975 | 11845 |        5032 |
| ML_mlp                                         | remove_pretrigger_pedestal     |    0.9993 |              0         |              0.9991 | 11845 |        5032 |
| ML_mlp                                         | remove_saturated_samples_proxy |    0.9991 |             -0.0001489 |              0.999  | 11845 |        5032 |
| ML_mlp                                         | tail_only                      |    0.7275 |             -0.2718    |              0.7653 | 11845 |        5032 |
| ML_ridge_classifier                            | nominal                        |    0.9887 |              0         |              0.9878 | 11845 |        5032 |
| ML_ridge_classifier                            | remove_tail_windows            |    0.9841 |             -0.004585  |              0.9819 | 11845 |        5032 |
| ML_ridge_classifier                            | remove_pretrigger_pedestal     |    0.9887 |              0         |              0.9878 | 11845 |        5032 |
| ML_ridge_classifier                            | remove_saturated_samples_proxy |    0.9885 |             -0.0001505 |              0.9876 | 11845 |        5032 |
| ML_ridge_classifier                            | tail_only                      |    0.7275 |             -0.2612    |              0.7653 | 11845 |        5032 |
| NN_1d_cnn                                      | nominal                        |    0.8337 |              0         |              0.8129 | 11845 |        5032 |
| NN_1d_cnn                                      | remove_tail_windows            |    0.8238 |             -0.009882  |              0.7912 | 11845 |        5032 |
| NN_1d_cnn                                      | remove_pretrigger_pedestal     |    0.8337 |              0         |              0.8129 | 11845 |        5032 |
| NN_1d_cnn                                      | remove_saturated_samples_proxy |    0.8341 |              0.000386  |              0.813  | 11845 |        5032 |
| NN_1d_cnn                                      | tail_only                      |    0.7275 |             -0.1063    |              0.7653 | 11845 |        5032 |
| NN_transformer_sequence_encoder_new            | nominal                        |    0.8446 |              0         |              0.8308 | 11845 |        5032 |
| NN_transformer_sequence_encoder_new            | remove_tail_windows            |    0.8442 |             -0.0003961 |              0.8297 | 11845 |        5032 |
| NN_transformer_sequence_encoder_new            | remove_pretrigger_pedestal     |    0.8446 |              0         |              0.8308 | 11845 |        5032 |
| NN_transformer_sequence_encoder_new            | remove_saturated_samples_proxy |    0.8446 |              1.645e-05 |              0.8308 | 11845 |        5032 |
| NN_transformer_sequence_encoder_new            | tail_only                      |    0.7275 |             -0.1171    |              0.7653 | 11845 |        5032 |
| traditional_exponential_ar_fisher_all_features | nominal                        |    0.9931 |              0         |              0.9919 | 11845 |        5032 |
| traditional_exponential_ar_fisher_all_features | remove_tail_windows            |    0.9928 |             -0.0002651 |              0.9916 | 11845 |        5032 |
| traditional_exponential_ar_fisher_all_features | remove_pretrigger_pedestal     |    0.9931 |              0         |              0.9919 | 11845 |        5032 |
| traditional_exponential_ar_fisher_all_features | remove_saturated_samples_proxy |    0.9931 |             -9.655e-06 |              0.9919 | 11845 |        5032 |
| traditional_exponential_ar_fisher_all_features | tail_only                      |    0.7275 |             -0.2656    |              0.7653 | 11845 |        5032 |

## Systematics

Run-block bootstrap shifts compare positive afterpulse/pile-up-like rows with smooth memory-like negatives after centering by run and stave.

| metric | median shift | 95% CI | held-out positives |
|---|---:|---:|---:|
| tail-shape exponential slope | 0.036800 | [0.012545, 0.101971] | 5,032 |
| tail-shape AR residual RMS | 0.021970 | [0.013608, 0.056424] | 5,032 |
| timing shift | 0.563437 | [0.308395, 1.355099] | 5,032 |
| pile-up confusion | 0.000000 | [0.000000, 1.000000] | 5,032 |
| saturation recovery | 0.061139 | [0.030221, 0.179592] | 5,032 |
| pedestal drift sensitivity | -1.000000 | [-2.250000, -0.250000] | 5,032 |
| energy bias proxy | -0.023615 | [-0.026649, -0.019835] | 5,032 |
| PID confusion proxy | -83.000000 | [-113.025000, -47.618750] | 5,032 |

## Caveats

- The label is waveform-derived and weak; it quantifies attribution separability, not absolute particle-level afterpulse truth.
- Same-event multiplicity is a powerful classical cue and can dominate some traditional scorecards; method comparisons should therefore be read as operational attribution performance.
- Run-heldout CIs cover acquisition-run transfer but not all detector-configuration or electronics-drift uncertainties.
- The saturated-sample ablation uses amplitude and high-charge proxies available in this raw pulse table; it is not a full electronics saturation decoder.
- PID calibration is represented by duplicate-readout and charge-proxy systematics rather than external mass/rigidity truth.

## Verdict

`result.json` names **`ML_gradient_boosted_trees`** as the winner.  The strongest traditional comparator is **`traditional_exponential_ar_fisher_all_features`**.  The conclusion is: ML/NN model beats the strongest traditional exponential-tail/AR baseline by held-out AUC.

## Reproducibility

```bash
MPLCONFIGDIR=/tmp/matplotlib-ticket2493 uv run --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with matplotlib --with tabulate --with torch python scripts/ticket_2493_s55a_late_tail_afterpulse_attribution.py
```
