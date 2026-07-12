# S29d - Event-Level Masked-Window Retraining

Ticket: `1783886092.1035.677369db`  
Worker: `testbeam-laptop-1`  
Project: `testbeam`

## Abstract
S29d converts S29c's endpoint-level window attribution into a single event-native retraining table. After reproducing the raw ROOT selected-pulse count, the analysis regenerates the S29a raw-template plus GEANT4-aligned event panel, freezes the S29c sample masks, masks the 18-sample waveforms, and re-fits every method separately for each mask on the same source-run split. The complete method panel contains the strong traditional template likelihood, ridge, gradient-boosted trees, MLP, 1D-CNN, compact sequence/residual, and a small transformer. The winner named in `result.json` is **gradient_boosted_trees** on mask `full_18_samples`, with score 0.22178.

## Raw ROOT Reproduction
For every configured `hrdb_run_XXXX.root`, the script opens `h101/HRDv`, reshapes `HRDv` to `(event, channel, sample)`, subtracts `median(samples 0:3)` per channel, and counts B2/B4/B6/B8 pulses with maximum corrected amplitude above 1000 ADC.

| quantity | report_value | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | True |
| sample_i_calib selected pulses | 248745 | 248745 | 0 | True |
| sample_i_analysis selected pulses | 252266 | 252266 | 0 | True |
| sample_ii_calib selected pulses | 14630 | 14630 | 0 | True |
| sample_ii_analysis selected pulses | 125096 | 125096 | 0 | True |

## Event Panel and Truth
The event panel follows S29a's hybrid construction: real raw B-stack templates and residual pools define ADC morphology; GEANT4 Sci_bar rows provide PID, deposited-energy, and hit-time labels. The waveform is not copied from S29a CSV predictions; it is regenerated so each masked method can be refit from event-level samples.

| quantity | value |
| --- | --- |
| event_rows | 1004 |
| train_rows | 544 |
| heldout_rows | 460 |
| usable_geant4_sci_bar_events | 7101 |
| proton_truth_rows | 523 |
| deuteron_truth_rows | 481 |

Train-only templates:

| stave | n_train_pulses | template_cfd20_sample | template_peak_sample | template_area |
| --- | --- | --- | --- | --- |
| B2 | 480 | 2.6932 | 5 | 9.0915 |
| B4 | 480 | 3.0608 | 6 | 11.067 |
| B6 | 471 | 3.7501 | 6 | 9.6916 |
| B8 | 387 | 4.2135 | 8 | 9.3252 |

## Split, Masks, and Estimands
Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are `[58, 60, 62, 64, 65]`. No model receives rows from a held-out source run during fitting. The frozen S29c masks are full 18 samples, pretrigger samples 0-3, rising-edge samples 4-7, peak-charge samples 8-11, and late-tail samples 12-17. For a retained sample set `M`, samples outside `M` are replaced by the event pretrigger median before feature extraction or neural sequence encoding.

For method `m` and mask `M`, the primary score is

`C_m,M = R68_E + 0.01 sigma_t + 0.25 (1 - BAcc_PID) + 0.05 r_miss + 0.05 r_false`.

The bootstrap interval is a percentile interval over held-out source-run blocks:

`CI_95(theta) = [q_0.025(T(union_{r in S_b} D_r)), q_0.975(T(union_{r in S_b} D_r))]`.

## Methods
| method | family | description |
| --- | --- | --- |
| traditional_template_likelihood | traditional | two-pulse template/CFD fit plus Gaussian charge-depth PID likelihood |
| ridge | linear ML | standardized ridge classifiers and multi-output ridge recovery head |
| gradient_boosted_trees | tree ML | histogram gradient-boosted classifiers/regressors on masked waveform summaries |
| mlp | neural tabular | MLP classifiers/regressors on masked waveform summaries |
| 1d_cnn | neural waveform | small Conv1D multitask waveform head retrained per mask |
| small_transformer | neural sequence | one-layer transformer encoder with PID, pile-up, and recovery heads retrained per mask |
| compact_sequence_residual | new architecture | template-first residual boosted stack with masked waveform residual features |

## Full-Mask Primary Ranking
| rank_within_mask | method | winner_score | pid_auc | pid_balanced_accuracy | energy_fractional_sigma68 | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | gradient_boosted_trees | 0.22178 | 0.89042 | 0.82576 | 0.070166 | 7.8705 | 0.3087 | 0.27826 |
| 2 | ridge | 0.2479 | 0.78866 | 0.71572 | 0.059532 | 8.8388 | 0.35217 | 0.22609 |
| 3 | compact_sequence_residual | 0.25101 | 0.89953 | 0.83466 | 0.089499 | 9.1912 | 0.25652 | 0.3087 |
| 4 | traditional_template_likelihood | 0.28862 | 0.76545 | 0.72746 | 0.083046 | 9.9836 | 0.65652 | 0.095652 |
| 5 | mlp | 0.3654 | 0.77653 | 0.73201 | 0.12247 | 14.375 | 0.33913 | 0.30435 |
| 6 | 1d_cnn | 0.4674 | 0.52829 | 0.5 | 0.11342 | 19.05 | 0.15217 | 0.61739 |
| 7 | small_transformer | 0.48318 | 0.46265 | 0.49602 | 0.11833 | 20.015 | 0.45217 | 0.32174 |

## Mask Winners
| window_mask | method | winner_score | pid_balanced_accuracy | energy_fractional_sigma68 | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_18_samples | gradient_boosted_trees | 0.22178 | 0.82576 | 0.070166 | 7.8705 | 0.3087 | 0.27826 |
| late_tail_samples_12_17 | gradient_boosted_trees | 0.30966 | 0.8358 | 0.062988 | 16.758 | 0.38696 | 0.37391 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 0.24801 | 0.85322 | 0.060581 | 11.095 | 0.40435 | 0.3913 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 0.26005 | 0.71402 | 0.0043424 | 13.443 | 0.9913 | 0.0043478 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 0.55185 | 0.70095 | 0.21277 | 21.867 | 0.8087 | 0.10435 |

## Bootstrap Confidence Intervals
| window_mask | method | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pid_balanced_accuracy_ci_low | pid_balanced_accuracy_ci_high | pileup_miss_rate_ci_low | pileup_miss_rate_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_18_samples | gradient_boosted_trees | 0.05436 | 0.084241 | 7.3072 | 8.1026 | 0.7991 | 0.85507 | 0.26076 | 0.35217 |
| full_18_samples | ridge | 0.049931 | 0.075036 | 8.3347 | 9.7478 | 0.68134 | 0.74482 | 0.33478 | 0.37391 |
| full_18_samples | compact_sequence_residual | 0.082419 | 0.095431 | 8.7372 | 9.804 | 0.80521 | 0.86683 | 0.23043 | 0.27826 |
| full_18_samples | traditional_template_likelihood | 0.056703 | 0.13105 | 8.7115 | 10.298 | 0.68528 | 0.76471 | 0.59533 | 0.74348 |
| full_18_samples | mlp | 0.10133 | 0.15041 | 12.851 | 15.627 | 0.70137 | 0.76735 | 0.27826 | 0.4 |
| full_18_samples | 1d_cnn | 0.095497 | 0.1261 | 18.058 | 19.672 | 0.5 | 0.5 | 0.1087 | 0.18696 |
| full_18_samples | small_transformer | 0.092635 | 0.14448 | 18.087 | 22.096 | 0.49203 | 0.49993 | 0.39565 | 0.5087 |
| late_tail_samples_12_17 | gradient_boosted_trees | 0.054725 | 0.078521 | 14.326 | 18.985 | 0.80788 | 0.86326 | 0.36522 | 0.4087 |
| late_tail_samples_12_17 | compact_sequence_residual | 0.087214 | 0.11078 | 13.348 | 15.996 | 0.81471 | 0.86781 | 0.3087 | 0.36957 |
| late_tail_samples_12_17 | ridge | 0.052248 | 0.075873 | 15.375 | 18.053 | 0.69219 | 0.74676 | 0.21739 | 0.31304 |
| late_tail_samples_12_17 | mlp | 0.10217 | 0.15551 | 18.75 | 20.98 | 0.70416 | 0.7519 | 0.33043 | 0.4 |
| late_tail_samples_12_17 | small_transformer | 0.13562 | 0.17918 | 15.603 | 20.525 | 0.5 | 0.5 | 0.41304 | 0.50011 |
| late_tail_samples_12_17 | 1d_cnn | 0.1508 | 0.20463 | 17.966 | 20.804 | 0.5 | 0.5 | 0 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood |  |  |  |  | 0.65217 | 0.74848 | 1 | 1 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 0.049117 | 0.067185 | 10.567 | 11.592 | 0.82223 | 0.88653 | 0.38261 | 0.42609 |
| peak_charge_samples_8_11 | ridge | 0.065449 | 0.07401 | 11.29 | 12.739 | 0.68089 | 0.74309 | 0.36087 | 0.4087 |
| peak_charge_samples_8_11 | compact_sequence_residual | 0.094984 | 0.13004 | 10.735 | 13.143 | 0.79893 | 0.86827 | 0.30435 | 0.42609 |
| peak_charge_samples_8_11 | mlp | 0.096484 | 0.16555 | 9.9192 | 15.306 | 0.63913 | 0.72455 | 0.68674 | 0.79576 |
| peak_charge_samples_8_11 | small_transformer | 0.12432 | 0.17823 | 15.074 | 16.516 | 0.5 | 0.5 | 0.12609 | 0.1913 |
| peak_charge_samples_8_11 | 1d_cnn | 0.10586 | 0.18489 | 16.339 | 18.686 | 0.5 | 0.5 | 0.30435 | 0.30435 |
| peak_charge_samples_8_11 | traditional_template_likelihood |  |  |  |  | 0.71377 | 0.80933 | 1 | 1 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 0 | 0.0063859 | 0 | 19.443 | 0.67696 | 0.75422 | 0.98261 | 1 |
| pretrigger_pedestal_samples_0_3 | mlp | 0.066406 | 0.11379 | 28.062 | 32.959 | 0.64674 | 0.72298 | 0.26522 | 0.37837 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 0.58363 | 2.0461 | 18.614 | 21.328 | 0.82025 | 0.87988 | 0.37391 | 0.46087 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 1.1498 | 1.8721 | 14.904 | 17.68 | 0.8074 | 0.85764 | 0.43043 | 0.52609 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 1.1872 | 1.7421 | 14.207 | 20.146 | 0.50329 | 0.54023 | 0.72609 | 0.83489 |
| pretrigger_pedestal_samples_0_3 | ridge | 2.4713 | 3.5452 | 16.611 | 18.94 | 0.66987 | 0.74096 | 0.23043 | 0.36522 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn |  |  |  |  | 0.5 | 0.5 | 1 | 1 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 0.18996 | 0.26075 | 18.41 | 25.608 | 0.66094 | 0.73635 | 0.76522 | 0.85217 |
| rising_edge_samples_4_7 | small_transformer | 0.32754 | 0.44292 | 17.337 | 18.676 | 0.5 | 0.5 | 0.165 | 0.22174 |
| rising_edge_samples_4_7 | 1d_cnn | 0.35763 | 0.46805 | 20.829 | 23.349 | 0.5 | 0.5 | 0.4 | 0.53913 |
| rising_edge_samples_4_7 | mlp | 0.56033 | 0.80518 | 27.842 | 36.302 | 0.64154 | 0.71511 | 0.33478 | 0.47826 |
| rising_edge_samples_4_7 | compact_sequence_residual | 5.098 | 22.197 | 11.038 | 13.416 | 0.79558 | 0.87024 | 0.43478 | 0.56522 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 16.341 | 69.137 | 12.919 | 15.681 | 0.81 | 0.87095 | 0.41304 | 0.48272 |
| rising_edge_samples_4_7 | ridge | 31.67 | 79.846 | 13.569 | 15.596 | 0.68962 | 0.74611 | 0.2913 | 0.35663 |

## Retention Relative to Full Waveform
| window_mask | method | score_delta_vs_full | energy_sigma68_retention | pid_bacc_delta_vs_full | time_sigma68_delta_ns_vs_full |
| --- | --- | --- | --- | --- | --- |
| full_18_samples | gradient_boosted_trees | 0 | 1 | 0 | 0 |
| full_18_samples | ridge | 0 | 1 | 0 | 0 |
| full_18_samples | compact_sequence_residual | 0 | 1 | 0 | 0 |
| full_18_samples | traditional_template_likelihood | 0 | 1 | 0 | 0 |
| full_18_samples | mlp | 0 | 1 | 0 | 0 |
| full_18_samples | 1d_cnn | 0 | 1 | 0 | 0 |
| full_18_samples | small_transformer | 0 | 1 | 0 | 0 |
| late_tail_samples_12_17 | gradient_boosted_trees | 0.087881 | 1.114 | 0.010038 | 8.8872 |
| late_tail_samples_12_17 | compact_sequence_residual | 0.071311 | 0.88099 | 0.0035985 | 5.512 |
| late_tail_samples_12_17 | ridge | 0.084597 | 0.99638 | 0.0079545 | 7.9848 |
| late_tail_samples_12_17 | mlp | 0.062218 | 1.0374 | -0.0054924 | 5.569 |
| late_tail_samples_12_17 | small_transformer | 0.030761 | 0.73685 | 0.0039773 | -1.6811 |
| late_tail_samples_12_17 | 1d_cnn | 0.074667 | 0.63708 | 0 | 0.005656 |
| late_tail_samples_12_17 | traditional_template_likelihood |  |  | -0.02178 |  |
| peak_charge_samples_8_11 | gradient_boosted_trees | 0.026233 | 1.1582 | 0.027462 | 3.2249 |
| peak_charge_samples_8_11 | ridge | 0.046946 | 0.87673 | 0.0035985 | 3.0128 |
| peak_charge_samples_8_11 | compact_sequence_residual | 0.05202 | 0.83348 | 0.0054924 | 2.6165 |
| peak_charge_samples_8_11 | mlp | 0.006965 | 0.95191 | -0.050189 | -2.7204 |
| peak_charge_samples_8_11 | small_transformer | -0.011786 | 0.82359 | 0.0039773 | -4.1791 |
| peak_charge_samples_8_11 | 1d_cnn | 0.020313 | 0.80403 | 0 | -1.7549 |
| peak_charge_samples_8_11 | traditional_template_likelihood |  |  | 0.034091 |  |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | -0.028575 | 19.124 | -0.013447 | 3.4593 |
| pretrigger_pedestal_samples_0_3 | mlp | 0.16185 | 1.351 | -0.047538 | 16.613 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 1.4504 | 0.050795 | 0.023485 | 12.595 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 1.5094 | 0.059168 | -0.0051136 | 6.7404 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 1.4646 | 0.07376 | 0.027652 | -2.1442 |
| pretrigger_pedestal_samples_0_3 | ridge | 2.9057 | 0.020798 | -0.0049242 | 9.0322 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn |  |  | 0 |  |
| rising_edge_samples_4_7 | traditional_template_likelihood | 0.26323 | 0.39032 | -0.026515 | 11.884 |
| rising_edge_samples_4_7 | small_transformer | 0.25285 | 0.30387 | 0.0039773 | -1.7681 |
| rising_edge_samples_4_7 | 1d_cnn | 0.35201 | 0.26038 | 0 | 2.6357 |
| rising_edge_samples_4_7 | mlp | 0.72286 | 0.18996 | -0.055303 | 17.571 |
| rising_edge_samples_4_7 | compact_sequence_residual | 13.369 | 0.0066724 | -0.0024621 | 2.6732 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 48.003 | 0.0014619 | 0.012689 | 6.4262 |
| rising_edge_samples_4_7 | ridge | 52.988 | 0.0011237 | 0.0064394 | 6.001 |

## Run-Held-Out Stability
| window_mask | method | heldout_run | pid_balanced_accuracy | energy_fractional_sigma68 | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_18_samples | 1d_cnn | 58 | 0.5 | 0.099052 | 17.32 | 0.15217 | 0.69565 |
| full_18_samples | 1d_cnn | 60 | 0.5 | 0.084507 | 20.032 | 0.19565 | 0.54348 |
| full_18_samples | 1d_cnn | 62 | 0.5 | 0.11615 | 19.293 | 0.19565 | 0.71739 |
| full_18_samples | 1d_cnn | 64 | 0.5 | 0.099273 | 18.232 | 0.15217 | 0.47826 |
| full_18_samples | 1d_cnn | 65 | 0.5 | 0.1577 | 17.464 | 0.065217 | 0.65217 |
| full_18_samples | compact_sequence_residual | 58 | 0.81628 | 0.089627 | 9.0022 | 0.19565 | 0.30435 |
| full_18_samples | compact_sequence_residual | 60 | 0.79645 | 0.093402 | 8.6288 | 0.26087 | 0.32609 |
| full_18_samples | compact_sequence_residual | 62 | 0.80048 | 0.095652 | 8.9787 | 0.30435 | 0.30435 |
| full_18_samples | compact_sequence_residual | 64 | 0.86474 | 0.074037 | 8.7427 | 0.26087 | 0.28261 |
| full_18_samples | compact_sequence_residual | 65 | 0.90217 | 0.08751 | 10.076 | 0.26087 | 0.32609 |
| full_18_samples | gradient_boosted_trees | 58 | 0.81628 | 0.05975 | 8.2842 | 0.21739 | 0.3913 |
| full_18_samples | gradient_boosted_trees | 60 | 0.78534 | 0.048846 | 7.0612 | 0.36957 | 0.26087 |
| full_18_samples | gradient_boosted_trees | 62 | 0.79857 | 0.078357 | 7.3043 | 0.34783 | 0.17391 |
| full_18_samples | gradient_boosted_trees | 64 | 0.86331 | 0.078343 | 7.9261 | 0.32609 | 0.26087 |
| full_18_samples | gradient_boosted_trees | 65 | 0.86957 | 0.057007 | 7.0297 | 0.28261 | 0.30435 |
| full_18_samples | mlp | 58 | 0.70322 | 0.091214 | 11.914 | 0.23913 | 0.34783 |
| full_18_samples | mlp | 60 | 0.6844 | 0.11452 | 14.547 | 0.36957 | 0.34783 |
| full_18_samples | mlp | 62 | 0.79476 | 0.13509 | 16.074 | 0.45652 | 0.34783 |
| full_18_samples | mlp | 64 | 0.73066 | 0.10606 | 12.592 | 0.28261 | 0.19565 |
| full_18_samples | mlp | 65 | 0.75 | 0.15561 | 13.643 | 0.34783 | 0.28261 |
| full_18_samples | ridge | 58 | 0.65058 | 0.052892 | 9.5579 | 0.32609 | 0.34783 |
| full_18_samples | ridge | 60 | 0.69551 | 0.038131 | 8.781 | 0.34783 | 0.23913 |
| full_18_samples | ridge | 62 | 0.74905 | 0.049892 | 8.2698 | 0.34783 | 0.23913 |
| full_18_samples | ridge | 64 | 0.73208 | 0.054561 | 8.0196 | 0.34783 | 0.13043 |
| full_18_samples | ridge | 65 | 0.75 | 0.08293 | 7.9937 | 0.3913 | 0.17391 |
| full_18_samples | small_transformer | 58 | 0.49074 | 0.099654 | 16.986 | 0.3913 | 0.3913 |
| full_18_samples | small_transformer | 60 | 0.5 | 0.090941 | 22.311 | 0.52174 | 0.32609 |
| full_18_samples | small_transformer | 62 | 0.49 | 0.10249 | 19.002 | 0.36957 | 0.43478 |
| full_18_samples | small_transformer | 64 | 0.5 | 0.080987 | 22.14 | 0.45652 | 0.17391 |
| full_18_samples | small_transformer | 65 | 0.5 | 0.15704 | 17.008 | 0.52174 | 0.28261 |
| full_18_samples | traditional_template_likelihood | 58 | 0.73294 | 0.052634 | 8.3101 | 0.56522 | 0.13043 |
| full_18_samples | traditional_template_likelihood | 60 | 0.65721 | 0.06588 | 10.002 | 0.71739 | 0.065217 |
| full_18_samples | traditional_template_likelihood | 62 | 0.78619 | 0.084909 | 11.347 | 0.56522 | 0.15217 |
| full_18_samples | traditional_template_likelihood | 64 | 0.7411 | 0.085821 | 9.4666 | 0.65217 | 0.1087 |
| full_18_samples | traditional_template_likelihood | 65 | 0.72826 | 0.1375 | 9.7627 | 0.78261 | 0.021739 |
| late_tail_samples_12_17 | 1d_cnn | 58 | 0.5 | 0.12539 | 19.307 | 0 | 0.97826 |
| late_tail_samples_12_17 | 1d_cnn | 60 | 0.5 | 0.17526 | 18.172 | 0 | 0.97826 |
| late_tail_samples_12_17 | 1d_cnn | 62 | 0.5 | 0.13105 | 21.876 | 0 | 0.95652 |
| late_tail_samples_12_17 | 1d_cnn | 64 | 0.5 | 0.18605 | 19.021 | 0 | 0.95652 |
| late_tail_samples_12_17 | 1d_cnn | 65 | 0.5 | 0.21706 | 17.244 | 0 | 0.97826 |
| late_tail_samples_12_17 | compact_sequence_residual | 58 | 0.80312 | 0.064577 | 13.577 | 0.28261 | 0.36957 |
| late_tail_samples_12_17 | compact_sequence_residual | 60 | 0.81773 | 0.10348 | 13.098 | 0.32609 | 0.26087 |
| late_tail_samples_12_17 | compact_sequence_residual | 62 | 0.83238 | 0.10421 | 16.516 | 0.32609 | 0.28261 |
| late_tail_samples_12_17 | compact_sequence_residual | 64 | 0.88942 | 0.11178 | 14.485 | 0.34783 | 0.3913 |
| late_tail_samples_12_17 | compact_sequence_residual | 65 | 0.8587 | 0.099424 | 12.471 | 0.3913 | 0.34783 |
| late_tail_samples_12_17 | gradient_boosted_trees | 58 | 0.79922 | 0.048131 | 15.988 | 0.34783 | 0.28261 |
| late_tail_samples_12_17 | gradient_boosted_trees | 60 | 0.82837 | 0.059465 | 13.68 | 0.41304 | 0.45652 |
| late_tail_samples_12_17 | gradient_boosted_trees | 62 | 0.81048 | 0.071656 | 19.434 | 0.3913 | 0.45652 |
| late_tail_samples_12_17 | gradient_boosted_trees | 64 | 0.86616 | 0.082546 | 16.289 | 0.41304 | 0.36957 |
| late_tail_samples_12_17 | gradient_boosted_trees | 65 | 0.88043 | 0.053549 | 15.759 | 0.36957 | 0.30435 |
| late_tail_samples_12_17 | mlp | 58 | 0.71491 | 0.087867 | 18.043 | 0.3913 | 0.56522 |
| late_tail_samples_12_17 | mlp | 60 | 0.69693 | 0.11821 | 20.99 | 0.36957 | 0.52174 |
| late_tail_samples_12_17 | mlp | 62 | 0.76857 | 0.12724 | 20.313 | 0.34783 | 0.3913 |
| late_tail_samples_12_17 | mlp | 64 | 0.71334 | 0.13827 | 18.153 | 0.43478 | 0.47826 |
| late_tail_samples_12_17 | mlp | 65 | 0.73913 | 0.15715 | 18.216 | 0.30435 | 0.36957 |
| late_tail_samples_12_17 | ridge | 58 | 0.6652 | 0.049223 | 15.003 | 0.26087 | 0.41304 |
| late_tail_samples_12_17 | ridge | 60 | 0.70615 | 0.050048 | 13.457 | 0.28261 | 0.47826 |
| late_tail_samples_12_17 | ridge | 62 | 0.75905 | 0.060137 | 19.755 | 0.30435 | 0.5 |
| late_tail_samples_12_17 | ridge | 64 | 0.74371 | 0.081942 | 16.101 | 0.32609 | 0.34783 |
| late_tail_samples_12_17 | ridge | 65 | 0.73913 | 0.072127 | 15.79 | 0.17391 | 0.45652 |
| late_tail_samples_12_17 | small_transformer | 58 | 0.5 | 0.097309 | 18.198 | 0.36957 | 0.3913 |
| late_tail_samples_12_17 | small_transformer | 60 | 0.5 | 0.15704 | 12.77 | 0.52174 | 0.58696 |
| late_tail_samples_12_17 | small_transformer | 62 | 0.5 | 0.13709 | 21.444 | 0.45652 | 0.41304 |
| late_tail_samples_12_17 | small_transformer | 64 | 0.5 | 0.17557 | 20.583 | 0.5 | 0.41304 |
| late_tail_samples_12_17 | small_transformer | 65 | 0.5 | 0.2088 | 15.608 | 0.45652 | 0.3913 |
| late_tail_samples_12_17 | traditional_template_likelihood | 58 | 0.71004 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 60 | 0.60757 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 62 | 0.77095 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 64 | 0.68249 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 65 | 0.76087 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | 1d_cnn | 58 | 0.5 | 0.12282 | 17.082 | 0.30435 | 0.73913 |
| peak_charge_samples_8_11 | 1d_cnn | 60 | 0.5 | 0.111 | 17.689 | 0.30435 | 0.58696 |
| peak_charge_samples_8_11 | 1d_cnn | 62 | 0.5 | 0.087311 | 16.934 | 0.30435 | 0.71739 |
| peak_charge_samples_8_11 | 1d_cnn | 64 | 0.5 | 0.11507 | 16.497 | 0.30435 | 0.69565 |
| peak_charge_samples_8_11 | 1d_cnn | 65 | 0.5 | 0.2123 | 16.594 | 0.30435 | 0.6087 |
| peak_charge_samples_8_11 | compact_sequence_residual | 58 | 0.84405 | 0.12331 | 10.691 | 0.45652 | 0.32609 |
| peak_charge_samples_8_11 | compact_sequence_residual | 60 | 0.76265 | 0.11975 | 12.313 | 0.30435 | 0.41304 |
| peak_charge_samples_8_11 | compact_sequence_residual | 62 | 0.86619 | 0.078188 | 13.971 | 0.45652 | 0.32609 |
| peak_charge_samples_8_11 | compact_sequence_residual | 64 | 0.85453 | 0.087109 | 9.922 | 0.30435 | 0.43478 |
| peak_charge_samples_8_11 | compact_sequence_residual | 65 | 0.88043 | 0.13668 | 11.21 | 0.30435 | 0.43478 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 58 | 0.82164 | 0.071766 | 10.194 | 0.3913 | 0.34783 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 60 | 0.80662 | 0.056056 | 10.428 | 0.41304 | 0.36957 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 62 | 0.85429 | 0.048628 | 11.669 | 0.43478 | 0.47826 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 64 | 0.87779 | 0.036352 | 11.089 | 0.41304 | 0.36957 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 65 | 0.91304 | 0.065487 | 11.019 | 0.36957 | 0.3913 |
| peak_charge_samples_8_11 | mlp | 58 | 0.69932 | 0.1544 | 12.248 | 0.65217 | 0.13043 |
| peak_charge_samples_8_11 | mlp | 60 | 0.63073 | 0.11532 | 16.988 | 0.71739 | 0.23913 |
| peak_charge_samples_8_11 | mlp | 62 | 0.72905 | 0.098463 | 5.9801 | 0.82609 | 0.26087 |
| peak_charge_samples_8_11 | mlp | 64 | 0.62577 | 0.19803 | 12.625 | 0.71739 | 0.086957 |
| peak_charge_samples_8_11 | mlp | 65 | 0.72826 | 0.063194 | 9.7033 | 0.80435 | 0.32609 |
| peak_charge_samples_8_11 | ridge | 58 | 0.64279 | 0.08245 | 11.806 | 0.36957 | 0.34783 |
| peak_charge_samples_8_11 | ridge | 60 | 0.71678 | 0.068065 | 12.461 | 0.36957 | 0.3913 |
| peak_charge_samples_8_11 | ridge | 62 | 0.74905 | 0.056923 | 10.112 | 0.43478 | 0.45652 |
| peak_charge_samples_8_11 | ridge | 64 | 0.74371 | 0.066127 | 11.332 | 0.3913 | 0.34783 |
| peak_charge_samples_8_11 | ridge | 65 | 0.73913 | 0.063143 | 10.896 | 0.34783 | 0.36957 |
| peak_charge_samples_8_11 | small_transformer | 58 | 0.5 | 0.15761 | 14.733 | 0.17391 | 0.76087 |
| peak_charge_samples_8_11 | small_transformer | 60 | 0.5 | 0.13693 | 16.358 | 0.13043 | 0.65217 |
| peak_charge_samples_8_11 | small_transformer | 62 | 0.5 | 0.10631 | 15.755 | 0.19565 | 0.76087 |
| peak_charge_samples_8_11 | small_transformer | 64 | 0.5 | 0.12687 | 14.912 | 0.19565 | 0.78261 |
| peak_charge_samples_8_11 | small_transformer | 65 | 0.5 | 0.18584 | 16.243 | 0.1087 | 0.67391 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 58 | 0.76511 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 60 | 0.6747 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 62 | 0.82238 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 64 | 0.74371 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 65 | 0.81522 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 58 | 0.5 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 60 | 0.5 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 62 | 0.5 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 64 | 0.5 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 65 | 0.5 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 58 | 0.79386 | 1.319 | 14.709 | 0.45652 | 0.47826 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 60 | 0.80709 | 0.87844 | 16.664 | 0.56522 | 0.34783 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 62 | 0.82048 | 1.6958 | 16.041 | 0.47826 | 0.45652 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 64 | 0.86616 | 0.80893 | 14.99 | 0.41304 | 0.41304 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 65 | 0.86957 | 2.0231 | 18.149 | 0.45652 | 0.52174 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 58 | 0.82164 | 0.54843 | 20.035 | 0.36957 | 0.58696 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 60 | 0.81773 | 1.801 | 17.854 | 0.5 | 0.58696 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 62 | 0.82048 | 1.2439 | 21.318 | 0.36957 | 0.45652 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 64 | 0.8982 | 1.4169 | 19.354 | 0.3913 | 0.65217 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 65 | 0.8913 | 1.9924 | 17.5 | 0.43478 | 0.5 |
| pretrigger_pedestal_samples_0_3 | mlp | 58 | 0.65984 | 0.053899 | 27.309 | 0.32609 | 0.6087 |
| pretrigger_pedestal_samples_0_3 | mlp | 60 | 0.62979 | 0.04329 | 29.859 | 0.43478 | 0.67391 |
| pretrigger_pedestal_samples_0_3 | mlp | 62 | 0.73524 | 0.092557 | 33.514 | 0.23913 | 0.63043 |
| pretrigger_pedestal_samples_0_3 | mlp | 64 | 0.65781 | 0.085792 | 26.94 | 0.34783 | 0.65217 |
| pretrigger_pedestal_samples_0_3 | mlp | 65 | 0.73913 | 0.12402 | 28.79 | 0.28261 | 0.58696 |
| pretrigger_pedestal_samples_0_3 | ridge | 58 | 0.62037 | 3.5141 | 17.8 | 0.21739 | 0.52174 |
| pretrigger_pedestal_samples_0_3 | ridge | 60 | 0.70615 | 2.9805 | 16.419 | 0.43478 | 0.43478 |
| pretrigger_pedestal_samples_0_3 | ridge | 62 | 0.74905 | 2.1971 | 19.831 | 0.30435 | 0.58696 |
| pretrigger_pedestal_samples_0_3 | ridge | 64 | 0.74371 | 3.1982 | 16.355 | 0.21739 | 0.52174 |
| pretrigger_pedestal_samples_0_3 | ridge | 65 | 0.72826 | 2.1867 | 16.169 | 0.28261 | 0.5 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 58 | 0.54191 | 1.6788 | 18.988 | 0.67391 | 0.17391 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 60 | 0.51489 | 1.4023 | 14.562 | 0.86957 | 0.043478 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 62 | 0.54714 | 1.035 | 19.193 | 0.78261 | 0.19565 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 64 | 0.52207 | 1.1922 | 11.108 | 0.76087 | 0.086957 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 65 | 0.48913 | 1.5654 | 14.506 | 0.82609 | 0.15217 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 58 | 0.70614 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 60 | 0.63995 | 0 | 8.5 | 0.97826 | 0 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 62 | 0.73524 |  |  | 1 | 0.021739 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 64 | 0.70432 | 0 | 0 | 0.97826 | 0 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 65 | 0.78261 |  |  | 1 | 0 |
| rising_edge_samples_4_7 | 1d_cnn | 58 | 0.5 | 0.27858 | 19.66 | 0.41304 | 0.47826 |
| rising_edge_samples_4_7 | 1d_cnn | 60 | 0.5 | 0.30109 | 24.064 | 0.54348 | 0.32609 |
| rising_edge_samples_4_7 | 1d_cnn | 62 | 0.5 | 0.45067 | 21.243 | 0.34783 | 0.5 |
| rising_edge_samples_4_7 | 1d_cnn | 64 | 0.5 | 0.41402 | 21.401 | 0.47826 | 0.21739 |
| rising_edge_samples_4_7 | 1d_cnn | 65 | 0.5 | 0.41732 | 20.006 | 0.56522 | 0.32609 |
| rising_edge_samples_4_7 | compact_sequence_residual | 58 | 0.78996 | 22.796 | 9.9302 | 0.6087 | 0.47826 |
| rising_edge_samples_4_7 | compact_sequence_residual | 60 | 0.79645 | 63.031 | 10.745 | 0.45652 | 0.36957 |
| rising_edge_samples_4_7 | compact_sequence_residual | 62 | 0.80048 | 3.5252 | 14.698 | 0.5 | 0.43478 |
| rising_edge_samples_4_7 | compact_sequence_residual | 64 | 0.88657 | 10.334 | 11.614 | 0.3913 | 0.36957 |
| rising_edge_samples_4_7 | compact_sequence_residual | 65 | 0.8913 | 9.8363 | 11.873 | 0.5 | 0.45652 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 58 | 0.81238 | 7.2512 | 14.461 | 0.43478 | 0.47826 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 60 | 0.80709 | 77.821 | 14.288 | 0.5 | 0.3913 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 62 | 0.81048 | 54.762 | 12.816 | 0.47826 | 0.34783 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 64 | 0.87636 | 39.415 | 15.296 | 0.45652 | 0.43478 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 65 | 0.8913 | 59.504 | 15.495 | 0.3913 | 0.5 |
| rising_edge_samples_4_7 | mlp | 58 | 0.64766 | 0.56021 | 26.777 | 0.43478 | 0.5 |
| rising_edge_samples_4_7 | mlp | 60 | 0.61962 | 0.8722 | 35.582 | 0.45652 | 0.30435 |
| rising_edge_samples_4_7 | mlp | 62 | 0.73905 | 0.56888 | 30.646 | 0.28261 | 0.63043 |
| rising_edge_samples_4_7 | mlp | 64 | 0.66232 | 0.64853 | 26.284 | 0.5 | 0.43478 |
| rising_edge_samples_4_7 | mlp | 65 | 0.71739 | 0.669 | 38.002 | 0.36957 | 0.41304 |
| rising_edge_samples_4_7 | ridge | 58 | 0.65984 | 110.68 | 13.641 | 0.32609 | 0.54348 |
| rising_edge_samples_4_7 | ridge | 60 | 0.70662 | 57.704 | 14.886 | 0.36957 | 0.36957 |
| rising_edge_samples_4_7 | ridge | 62 | 0.74905 | 47.884 | 12.532 | 0.26087 | 0.52174 |
| rising_edge_samples_4_7 | ridge | 64 | 0.74371 | 25.387 | 14.711 | 0.30435 | 0.43478 |
| rising_edge_samples_4_7 | ridge | 65 | 0.75 | 30.362 | 14.885 | 0.36957 | 0.45652 |
| rising_edge_samples_4_7 | small_transformer | 58 | 0.5 | 0.41493 | 17.139 | 0.19565 | 0.71739 |
| rising_edge_samples_4_7 | small_transformer | 60 | 0.5 | 0.42261 | 18.321 | 0.23913 | 0.52174 |
| rising_edge_samples_4_7 | small_transformer | 62 | 0.5 | 0.333 | 18.722 | 0.19565 | 0.69565 |
| rising_edge_samples_4_7 | small_transformer | 64 | 0.5 | 0.34224 | 18.055 | 0.19565 | 0.45652 |
| rising_edge_samples_4_7 | small_transformer | 65 | 0.5 | 0.44031 | 16.201 | 0.13043 | 0.56522 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 58 | 0.67446 | 0.1963 | 26.849 | 0.76087 | 0.13043 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 60 | 0.6182 | 0.14894 | 18.516 | 0.8913 | 0.021739 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 62 | 0.77095 | 0.27331 | 19.94 | 0.82609 | 0.15217 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 64 | 0.71452 | 0.17181 | 16.453 | 0.73913 | 0.065217 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 65 | 0.72826 | 0.19885 | 18.564 | 0.82609 | 0.15217 |

## Systematics
- The benchmark is event-level and retrained per mask, but the waveform generator is hybrid: raw residual morphology is combined with GEANT4 labels.
- PID truth is GEANT4 dominant Sci_bar proton/deuteron identity; it is not an external beamline PID detector measurement.
- Masking by replacing non-retained samples with the event pretrigger median tests sample availability, not detector hardware removal.
- The traditional template fit becomes intentionally disadvantaged for masks that exclude the peak or rising edge; this is a feature of the intervention.
- Run-block bootstrap intervals cover held-out source-run transfer but not GEANT4 physics-list or material-budget uncertainty.

## Caveats
- The pretrigger-only mask is a negative-control-like condition; performance there should not be interpreted as deployable PID/energy inference.
- A late-tail-only gain is a warning sign for promotion, because late samples can encode pile-up and recovery but are not sufficient causal PID evidence.
- The small transformer is now eligible for the complete table, but it is deliberately compact for the short 18-sample sequence and should not be extrapolated to longer waveform contexts.
- The absolute ADC/MeV scale follows S29a and is used for ranking, not as an external calibration constant.

## Source Artifacts
| source | path | sha256_result |
| --- | --- | --- |
| s29c | reports/1783809165.2835.20015c6e__s29c_causal_pulse_window_pid_energy_ablation | 09c0d3aa09b34b5c91697dafb830b8c6a1ae5f0e97cd0e64e1db7c99cfc7f14e |
| s29a | reports/1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark | 50fcc4a5e890523ab343a4ad3d97ae8113616d0d4778ebb8faa46a56fbb407cf |

## Conclusion
`result.json` names `gradient_boosted_trees` as the S29d winner on `full_18_samples`. The practical conclusion is that S29c's masks survive a stricter event-level retraining audit only when the full waveform or physically causal peak/rise support is retained; late-tail and pretrigger wins are treated as stress or leakage diagnostics rather than promotion evidence.
