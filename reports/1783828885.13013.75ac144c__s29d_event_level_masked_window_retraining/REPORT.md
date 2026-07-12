# S29d - Event-Level Masked-Window Retraining

Ticket: `1783828885.13013.75ac144c`  
Worker: `testbeam-laptop-3`  
Project: `testbeam`

## Abstract
S29d converts S29c's endpoint-level window attribution into a single event-native retraining table. After reproducing the raw ROOT selected-pulse count, the analysis regenerates the S29a raw-template plus GEANT4-aligned event panel, freezes the S29c sample masks, masks the 18-sample waveforms, and re-fits every method separately for each mask on the same source-run split. The complete method panel contains the strong traditional template likelihood, ridge, gradient-boosted trees, MLP, 1D-CNN, compact sequence/residual, and a small transformer. The winner named in `result.json` is **gradient_boosted_trees** on mask `full_18_samples`, with score 0.22926.

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
| proton_truth_rows | 498 |
| deuteron_truth_rows | 506 |

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
| 1 | gradient_boosted_trees | 0.22926 | 0.89624 | 0.84541 | 0.067377 | 9.5847 | 0.31739 | 0.23043 |
| 2 | compact_sequence_residual | 0.24082 | 0.90411 | 0.86963 | 0.09029 | 9.3371 | 0.28261 | 0.2087 |
| 3 | ridge | 0.26605 | 0.83164 | 0.75488 | 0.073294 | 10.212 | 0.32174 | 0.26522 |
| 4 | traditional_template_likelihood | 0.30547 | 0.77262 | 0.75223 | 0.11223 | 9.412 | 0.64783 | 0.095652 |
| 5 | mlp | 0.3952 | 0.74665 | 0.69859 | 0.14956 | 14.202 | 0.29565 | 0.26957 |
| 6 | small_transformer | 0.47143 | 0.5053 | 0.48407 | 0.14778 | 16.423 | 0.27826 | 0.33043 |
| 7 | 1d_cnn | 0.47761 | 0.5003 | 0.5 | 0.1541 | 16.786 | 0.27826 | 0.33478 |

## Mask Winners
| window_mask | method | winner_score | pid_balanced_accuracy | energy_fractional_sigma68 | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_18_samples | gradient_boosted_trees | 0.22926 | 0.84541 | 0.067377 | 9.5847 | 0.31739 | 0.23043 |
| late_tail_samples_12_17 | gradient_boosted_trees | 0.27957 | 0.85612 | 0.057405 | 14.641 | 0.44783 | 0.34783 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 0.24207 | 0.86471 | 0.065735 | 10.555 | 0.4 | 0.33913 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 0.23458 | 0.77107 | 0.0063488 | 12.122 | 0.98696 | 0.0086957 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 0.55964 | 0.77353 | 0.23611 | 22.256 | 0.78696 | 0.1 |

## Bootstrap Confidence Intervals
| window_mask | method | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pid_balanced_accuracy_ci_low | pid_balanced_accuracy_ci_high | pileup_miss_rate_ci_low | pileup_miss_rate_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_18_samples | gradient_boosted_trees | 0.057578 | 0.085051 | 8.9387 | 9.9117 | 0.82717 | 0.86362 | 0.23902 | 0.39565 |
| full_18_samples | compact_sequence_residual | 0.082626 | 0.10609 | 7.9399 | 10.125 | 0.83972 | 0.88952 | 0.22609 | 0.33043 |
| full_18_samples | ridge | 0.06698 | 0.083316 | 9.3646 | 10.436 | 0.70621 | 0.80395 | 0.24783 | 0.4087 |
| full_18_samples | traditional_template_likelihood | 0.07615 | 0.12658 | 8.5362 | 10.606 | 0.7302 | 0.77515 | 0.5825 | 0.7087 |
| full_18_samples | mlp | 0.13359 | 0.15877 | 13.292 | 15.548 | 0.66991 | 0.72636 | 0.22174 | 0.36109 |
| full_18_samples | small_transformer | 0.1265 | 0.18814 | 15.092 | 18.203 | 0.4463 | 0.52144 | 0.26087 | 0.30446 |
| full_18_samples | 1d_cnn | 0.13482 | 0.19637 | 15.816 | 17.265 | 0.5 | 0.5 | 0.23913 | 0.32174 |
| late_tail_samples_12_17 | gradient_boosted_trees | 0.051947 | 0.077495 | 12.505 | 15.72 | 0.83579 | 0.87666 | 0.43478 | 0.46522 |
| late_tail_samples_12_17 | compact_sequence_residual | 0.083727 | 0.10887 | 12.408 | 15.622 | 0.81527 | 0.87894 | 0.26076 | 0.39565 |
| late_tail_samples_12_17 | ridge | 0.058831 | 0.093802 | 15.661 | 17.863 | 0.7216 | 0.79892 | 0.24783 | 0.39565 |
| late_tail_samples_12_17 | mlp | 0.10554 | 0.15285 | 15.837 | 18.306 | 0.66352 | 0.72856 | 0.39565 | 0.46967 |
| late_tail_samples_12_17 | 1d_cnn | 0.15804 | 0.22344 | 17.39 | 19.663 | 0.5 | 0.5 | 0 | 0 |
| late_tail_samples_12_17 | small_transformer | 0.15652 | 0.26638 | 15.486 | 20.021 | 0.5 | 0.5 | 0.83902 | 0.91315 |
| late_tail_samples_12_17 | traditional_template_likelihood |  |  |  |  | 0.72594 | 0.75651 | 1 | 1 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 0.057682 | 0.070388 | 9.2408 | 11.933 | 0.85473 | 0.87537 | 0.33478 | 0.49565 |
| peak_charge_samples_8_11 | ridge | 0.054962 | 0.084211 | 10.229 | 12.621 | 0.72768 | 0.80324 | 0.26076 | 0.43054 |
| peak_charge_samples_8_11 | compact_sequence_residual | 0.085264 | 0.13196 | 9.7866 | 13.726 | 0.84381 | 0.86925 | 0.2563 | 0.3913 |
| peak_charge_samples_8_11 | mlp | 0.070378 | 0.099366 | 10.202 | 14.912 | 0.76664 | 0.79559 | 0.6087 | 0.64783 |
| peak_charge_samples_8_11 | small_transformer | 0.16267 | 0.19058 | 16.189 | 18.018 | 0.5 | 0.5 | 0.056522 | 0.10435 |
| peak_charge_samples_8_11 | 1d_cnn | 0.15974 | 0.19621 | 17.678 | 19.877 | 0.5 | 0.5 | 0 | 0.026196 |
| peak_charge_samples_8_11 | traditional_template_likelihood |  |  |  |  | 0.51425 | 0.55393 | 1 | 1 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 0.0063488 | 0.0093365 | 12.122 | 12.922 | 0.76248 | 0.78202 | 0.96087 | 1 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 0.34564 | 0.49584 | 16.962 | 19.346 | 0.83173 | 0.8937 | 0.4087 | 0.45652 |
| pretrigger_pedestal_samples_0_3 | mlp | 0.086592 | 0.17756 | 40.734 | 48.576 | 0.74534 | 0.78479 | 0.3 | 0.4262 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 0.39257 | 0.61446 | 16.236 | 19.163 | 0.83913 | 0.87008 | 0.35652 | 0.47391 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 0.73566 | 1.5449 | 16.307 | 20.701 | 0.5 | 0.5 | 0.73033 | 0.81739 |
| pretrigger_pedestal_samples_0_3 | ridge | 1.2073 | 2.1733 | 16.991 | 18.94 | 0.72933 | 0.81366 | 0.26924 | 0.3913 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 1.9622 | 2.6258 | 19.951 | 21.815 | 0.5 | 0.5 | 0 | 0 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 0.18981 | 0.29337 | 19.816 | 23.777 | 0.74757 | 0.78698 | 0.75217 | 0.83043 |
| rising_edge_samples_4_7 | 1d_cnn | 0.45168 | 0.50732 | 14.979 | 17.222 | 0.5 | 0.5 | 0.3 | 0.38261 |
| rising_edge_samples_4_7 | small_transformer | 0.40237 | 0.52024 | 15.484 | 16.713 | 0.48327 | 0.51957 | 0.1087 | 0.21304 |
| rising_edge_samples_4_7 | mlp | 2.1781 | 2.9358 | 32.048 | 37.181 | 0.76288 | 0.77793 | 0.28261 | 0.4087 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 2.5129 | 4.1815 | 12.982 | 14.572 | 0.83775 | 0.87734 | 0.37391 | 0.50435 |
| rising_edge_samples_4_7 | compact_sequence_residual | 3.7472 | 9.9872 | 10.323 | 15.274 | 0.84626 | 0.87034 | 0.36522 | 0.45217 |
| rising_edge_samples_4_7 | ridge | 68.536 | 141.73 | 13.366 | 15.798 | 0.71957 | 0.79981 | 0.25217 | 0.36967 |

## Retention Relative to Full Waveform
| window_mask | method | score_delta_vs_full | energy_sigma68_retention | pid_bacc_delta_vs_full | time_sigma68_delta_ns_vs_full |
| --- | --- | --- | --- | --- | --- |
| full_18_samples | gradient_boosted_trees | 0 | 1 | 0 | 0 |
| full_18_samples | compact_sequence_residual | 0 | 1 | 0 | 0 |
| full_18_samples | ridge | 0 | 1 | 0 | 0 |
| full_18_samples | traditional_template_likelihood | 0 | 1 | 0 | 0 |
| full_18_samples | mlp | 0 | 1 | 0 | 0 |
| full_18_samples | small_transformer | 0 | 1 | 0 | 0 |
| full_18_samples | 1d_cnn | 0 | 1 | 0 | 0 |
| late_tail_samples_12_17 | gradient_boosted_trees | 0.050308 | 1.1737 | 0.010707 | 5.0566 |
| late_tail_samples_12_17 | compact_sequence_residual | 0.064827 | 0.95062 | -0.01763 | 4.6598 |
| late_tail_samples_12_17 | ridge | 0.072294 | 1.0255 | 0.0069234 | 6.8021 |
| late_tail_samples_12_17 | mlp | 0.018747 | 1.2316 | -0.0021186 | 3.4173 |
| late_tail_samples_12_17 | 1d_cnn | 0.075595 | 0.79862 | 0 | 1.7391 |
| late_tail_samples_12_17 | small_transformer | 0.11074 | 0.61349 | 0.015928 | 0.63933 |
| late_tail_samples_12_17 | traditional_template_likelihood |  |  | -0.012825 |  |
| peak_charge_samples_8_11 | gradient_boosted_trees | 0.012806 | 1.025 | 0.019295 | 0.9707 |
| peak_charge_samples_8_11 | ridge | 0.013027 | 1.0688 | 0.0090421 | 1.3482 |
| peak_charge_samples_8_11 | compact_sequence_residual | 0.057906 | 0.87625 | -0.013166 | 3.1428 |
| peak_charge_samples_8_11 | mlp | -0.0863 | 1.8028 | 0.079411 | -1.7455 |
| peak_charge_samples_8_11 | small_transformer | 0.044014 | 0.85203 | 0.015928 | 0.86356 |
| peak_charge_samples_8_11 | 1d_cnn | 0.064967 | 0.84677 | 0 | 1.8604 |
| peak_charge_samples_8_11 | traditional_template_likelihood |  |  | -0.21826 |  |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | -0.070884 | 17.678 | 0.018841 | 2.7101 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 0.43839 | 0.1671 | 0.019295 | 8.6518 |
| pretrigger_pedestal_samples_0_3 | mlp | 0.3296 | 0.95385 | 0.066472 | 31.942 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 0.49439 | 0.18897 | -0.015285 | 8.3717 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 0.93375 | 0.14111 | 0.015928 | 2.4306 |
| pretrigger_pedestal_samples_0_3 | ridge | 1.9676 | 0.037457 | 0.018198 | 7.2179 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 2.305 | 0.064241 | 0 | 4.102 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 0.25417 | 0.47533 | 0.0213 | 12.844 |
| rising_edge_samples_4_7 | 1d_cnn | 0.31465 | 0.33096 | 0 | -0.33692 |
| rising_edge_samples_4_7 | small_transformer | 0.34518 | 0.3014 | 0.016571 | -0.038361 |
| rising_edge_samples_4_7 | mlp | 2.778 | 0.054675 | 0.071618 | 20.169 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 3.2618 | 0.020609 | 0.010707 | 4.4927 |
| rising_edge_samples_4_7 | compact_sequence_residual | 5.0568 | 0.017716 | -0.0091556 | 2.8799 |
| rising_edge_samples_4_7 | ridge | 99.296 | 0.00073798 | 0 | 4.3091 |

## Run-Held-Out Stability
| window_mask | method | heldout_run | pid_balanced_accuracy | energy_fractional_sigma68 | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_18_samples | 1d_cnn | 58 | 0.5 | 0.16471 | 14.372 | 0.23913 | 0.32609 |
| full_18_samples | 1d_cnn | 60 | 0.5 | 0.11055 | 16.992 | 0.30435 | 0.41304 |
| full_18_samples | 1d_cnn | 62 | 0.5 | 0.21613 | 16.212 | 0.32609 | 0.3913 |
| full_18_samples | 1d_cnn | 64 | 0.5 | 0.13851 | 16.603 | 0.19565 | 0.23913 |
| full_18_samples | 1d_cnn | 65 | 0.5 | 0.14519 | 16.007 | 0.32609 | 0.30435 |
| full_18_samples | compact_sequence_residual | 58 | 0.80567 | 0.076566 | 9.243 | 0.26087 | 0.30435 |
| full_18_samples | compact_sequence_residual | 60 | 0.89314 | 0.081393 | 6.6158 | 0.30435 | 0.23913 |
| full_18_samples | compact_sequence_residual | 62 | 0.88731 | 0.10844 | 9.4082 | 0.34783 | 0.21739 |
| full_18_samples | compact_sequence_residual | 64 | 0.88043 | 0.089221 | 9.8328 | 0.17391 | 0.13043 |
| full_18_samples | compact_sequence_residual | 65 | 0.88173 | 0.10069 | 8.9143 | 0.32609 | 0.15217 |
| full_18_samples | gradient_boosted_trees | 58 | 0.81631 | 0.056219 | 9.1821 | 0.23913 | 0.23913 |
| full_18_samples | gradient_boosted_trees | 60 | 0.87092 | 0.086809 | 9.0973 | 0.21739 | 0.23913 |
| full_18_samples | gradient_boosted_trees | 62 | 0.83333 | 0.07265 | 8.9828 | 0.45652 | 0.21739 |
| full_18_samples | gradient_boosted_trees | 64 | 0.83696 | 0.057116 | 8.8716 | 0.28261 | 0.19565 |
| full_18_samples | gradient_boosted_trees | 65 | 0.87212 | 0.061583 | 8.8312 | 0.3913 | 0.26087 |
| full_18_samples | mlp | 58 | 0.66359 | 0.15073 | 14.905 | 0.21739 | 0.36957 |
| full_18_samples | mlp | 60 | 0.7409 | 0.12943 | 12.692 | 0.28261 | 0.30435 |
| full_18_samples | mlp | 62 | 0.67614 | 0.1278 | 12.631 | 0.43478 | 0.19565 |
| full_18_samples | mlp | 64 | 0.73913 | 0.13717 | 15.911 | 0.19565 | 0.21739 |
| full_18_samples | mlp | 65 | 0.67692 | 0.13068 | 14.516 | 0.34783 | 0.26087 |
| full_18_samples | ridge | 58 | 0.69409 | 0.071745 | 9.6381 | 0.19565 | 0.34783 |
| full_18_samples | ridge | 60 | 0.84728 | 0.058994 | 10.064 | 0.23913 | 0.23913 |
| full_18_samples | ridge | 62 | 0.78598 | 0.08728 | 9.9547 | 0.47826 | 0.21739 |
| full_18_samples | ridge | 64 | 0.75 | 0.058565 | 9.2707 | 0.32609 | 0.28261 |
| full_18_samples | ridge | 65 | 0.69423 | 0.078254 | 9.3728 | 0.36957 | 0.23913 |
| full_18_samples | small_transformer | 58 | 0.42577 | 0.14574 | 15.026 | 0.28261 | 0.34783 |
| full_18_samples | small_transformer | 60 | 0.51135 | 0.10358 | 14.915 | 0.26087 | 0.43478 |
| full_18_samples | small_transformer | 62 | 0.5303 | 0.20369 | 18.375 | 0.26087 | 0.30435 |
| full_18_samples | small_transformer | 64 | 0.52174 | 0.12749 | 16.982 | 0.26087 | 0.21739 |
| full_18_samples | small_transformer | 65 | 0.43558 | 0.15299 | 17.753 | 0.32609 | 0.34783 |
| full_18_samples | traditional_template_likelihood | 58 | 0.71773 | 0.11073 | 5.9879 | 0.56522 | 0.15217 |
| full_18_samples | traditional_template_likelihood | 60 | 0.77187 | 0.11963 | 10.401 | 0.6087 | 0.15217 |
| full_18_samples | traditional_template_likelihood | 62 | 0.73011 | 0.085599 | 7.7662 | 0.71739 | 0.065217 |
| full_18_samples | traditional_template_likelihood | 64 | 0.78261 | 0.028514 | 8.1679 | 0.76087 | 0.086957 |
| full_18_samples | traditional_template_likelihood | 65 | 0.75962 | 0.10553 | 8.8057 | 0.58696 | 0.021739 |
| late_tail_samples_12_17 | 1d_cnn | 58 | 0.5 | 0.16409 | 17.103 | 0 | 1 |
| late_tail_samples_12_17 | 1d_cnn | 60 | 0.5 | 0.19048 | 16.339 | 0 | 1 |
| late_tail_samples_12_17 | 1d_cnn | 62 | 0.5 | 0.20866 | 19.221 | 0 | 1 |
| late_tail_samples_12_17 | 1d_cnn | 64 | 0.5 | 0.18347 | 18.526 | 0 | 1 |
| late_tail_samples_12_17 | 1d_cnn | 65 | 0.5 | 0.1255 | 19.627 | 0 | 1 |
| late_tail_samples_12_17 | compact_sequence_residual | 58 | 0.78345 | 0.098038 | 16.581 | 0.21739 | 0.47826 |
| late_tail_samples_12_17 | compact_sequence_residual | 60 | 0.85012 | 0.098299 | 10.941 | 0.43478 | 0.36957 |
| late_tail_samples_12_17 | compact_sequence_residual | 62 | 0.89962 | 0.11161 | 13.925 | 0.3913 | 0.30435 |
| late_tail_samples_12_17 | compact_sequence_residual | 64 | 0.8587 | 0.079344 | 12.827 | 0.32609 | 0.23913 |
| late_tail_samples_12_17 | compact_sequence_residual | 65 | 0.87212 | 0.10543 | 14.534 | 0.28261 | 0.32609 |
| late_tail_samples_12_17 | gradient_boosted_trees | 58 | 0.82695 | 0.046613 | 16.377 | 0.43478 | 0.45652 |
| late_tail_samples_12_17 | gradient_boosted_trees | 60 | 0.83853 | 0.07486 | 12.889 | 0.47826 | 0.32609 |
| late_tail_samples_12_17 | gradient_boosted_trees | 62 | 0.87689 | 0.073317 | 12.211 | 0.43478 | 0.32609 |
| late_tail_samples_12_17 | gradient_boosted_trees | 64 | 0.84783 | 0.054681 | 13.788 | 0.43478 | 0.30435 |
| late_tail_samples_12_17 | gradient_boosted_trees | 65 | 0.89135 | 0.044077 | 13.047 | 0.45652 | 0.32609 |
| late_tail_samples_12_17 | mlp | 58 | 0.71631 | 0.090185 | 17.175 | 0.3913 | 0.34783 |
| late_tail_samples_12_17 | mlp | 60 | 0.75012 | 0.092209 | 17.201 | 0.41304 | 0.43478 |
| late_tail_samples_12_17 | mlp | 62 | 0.64867 | 0.15779 | 18.444 | 0.45652 | 0.36957 |
| late_tail_samples_12_17 | mlp | 64 | 0.67391 | 0.13096 | 16.743 | 0.3913 | 0.3913 |
| late_tail_samples_12_17 | mlp | 65 | 0.68654 | 0.11567 | 14.58 | 0.5 | 0.34783 |
| late_tail_samples_12_17 | ridge | 58 | 0.70473 | 0.065959 | 17.031 | 0.17391 | 0.3913 |
| late_tail_samples_12_17 | ridge | 60 | 0.83664 | 0.053337 | 15.969 | 0.3913 | 0.36957 |
| late_tail_samples_12_17 | ridge | 62 | 0.77557 | 0.097792 | 18.735 | 0.36957 | 0.34783 |
| late_tail_samples_12_17 | ridge | 64 | 0.77174 | 0.055157 | 13.918 | 0.32609 | 0.52174 |
| late_tail_samples_12_17 | ridge | 65 | 0.72212 | 0.089493 | 17.68 | 0.41304 | 0.41304 |
| late_tail_samples_12_17 | small_transformer | 58 | 0.5 | 0.20142 | 15.333 | 0.86957 | 0.13043 |
| late_tail_samples_12_17 | small_transformer | 60 | 0.5 | 0.22258 | 18.547 | 0.82609 | 0 |
| late_tail_samples_12_17 | small_transformer | 62 | 0.5 | 0.27551 | 18.327 | 0.8913 | 0.021739 |
| late_tail_samples_12_17 | small_transformer | 64 | 0.5 | 0.21437 | 15.71 | 0.82609 | 0.021739 |
| late_tail_samples_12_17 | small_transformer | 65 | 0.5 | 0.046113 | 13.485 | 0.95652 | 0.021739 |
| late_tail_samples_12_17 | traditional_template_likelihood | 58 | 0.73901 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 60 | 0.77187 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 62 | 0.72917 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 64 | 0.71739 |  |  | 1 | 0 |
| late_tail_samples_12_17 | traditional_template_likelihood | 65 | 0.74327 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | 1d_cnn | 58 | 0.5 | 0.15394 | 16.976 | 0 | 0.91304 |
| peak_charge_samples_8_11 | 1d_cnn | 60 | 0.5 | 0.13228 | 16.936 | 0 | 1 |
| peak_charge_samples_8_11 | 1d_cnn | 62 | 0.5 | 0.19429 | 19.939 | 0 | 1 |
| peak_charge_samples_8_11 | 1d_cnn | 64 | 0.5 | 0.17901 | 18.965 | 0.043478 | 0.97826 |
| peak_charge_samples_8_11 | 1d_cnn | 65 | 0.5 | 0.22886 | 19.594 | 0.021739 | 0.95652 |
| peak_charge_samples_8_11 | compact_sequence_residual | 58 | 0.8279 | 0.075729 | 13.185 | 0.23913 | 0.32609 |
| peak_charge_samples_8_11 | compact_sequence_residual | 60 | 0.84965 | 0.087352 | 8.3467 | 0.21739 | 0.32609 |
| peak_charge_samples_8_11 | compact_sequence_residual | 62 | 0.87689 | 0.096817 | 14.035 | 0.41304 | 0.47826 |
| peak_charge_samples_8_11 | compact_sequence_residual | 64 | 0.8587 | 0.084057 | 13.517 | 0.43478 | 0.36957 |
| peak_charge_samples_8_11 | compact_sequence_residual | 65 | 0.86923 | 0.14131 | 11.047 | 0.32609 | 0.36957 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 58 | 0.83759 | 0.069236 | 10.196 | 0.36957 | 0.34783 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 60 | 0.87139 | 0.049955 | 8.2719 | 0.28261 | 0.28261 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 62 | 0.86648 | 0.050198 | 11.79 | 0.56522 | 0.43478 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 64 | 0.88043 | 0.057798 | 11.898 | 0.41304 | 0.32609 |
| peak_charge_samples_8_11 | gradient_boosted_trees | 65 | 0.86635 | 0.068769 | 10.332 | 0.36957 | 0.30435 |
| peak_charge_samples_8_11 | mlp | 58 | 0.76076 | 0.076948 | 17.693 | 0.63043 | 0.32609 |
| peak_charge_samples_8_11 | mlp | 60 | 0.81489 | 0.063918 | 9.9704 | 0.65217 | 0.28261 |
| peak_charge_samples_8_11 | mlp | 62 | 0.77462 | 0.082868 | 8.8645 | 0.65217 | 0.23913 |
| peak_charge_samples_8_11 | mlp | 64 | 0.77174 | 0.093865 | 9.3206 | 0.58696 | 0.26087 |
| peak_charge_samples_8_11 | mlp | 65 | 0.77212 | 0.061634 | 12.139 | 0.63043 | 0.32609 |
| peak_charge_samples_8_11 | ridge | 58 | 0.71631 | 0.05512 | 12.886 | 0.34783 | 0.34783 |
| peak_charge_samples_8_11 | ridge | 60 | 0.83664 | 0.050024 | 8.5893 | 0.23913 | 0.3913 |
| peak_charge_samples_8_11 | ridge | 62 | 0.78598 | 0.083225 | 9.9733 | 0.5 | 0.3913 |
| peak_charge_samples_8_11 | ridge | 64 | 0.76087 | 0.049795 | 12.621 | 0.32609 | 0.45652 |
| peak_charge_samples_8_11 | ridge | 65 | 0.71923 | 0.089496 | 10.408 | 0.23913 | 0.34783 |
| peak_charge_samples_8_11 | small_transformer | 58 | 0.5 | 0.14731 | 16.5 | 0.065217 | 0.71739 |
| peak_charge_samples_8_11 | small_transformer | 60 | 0.5 | 0.14228 | 15.589 | 0.13043 | 0.84783 |
| peak_charge_samples_8_11 | small_transformer | 62 | 0.5 | 0.18143 | 18.454 | 0.043478 | 0.93478 |
| peak_charge_samples_8_11 | small_transformer | 64 | 0.5 | 0.16393 | 17.796 | 0.065217 | 0.76087 |
| peak_charge_samples_8_11 | small_transformer | 65 | 0.5 | 0.20811 | 18.222 | 0.086957 | 0.76087 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 58 | 0.52955 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 60 | 0.55225 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 62 | 0.55871 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 64 | 0.48913 |  |  | 1 | 0 |
| peak_charge_samples_8_11 | traditional_template_likelihood | 65 | 0.53942 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 58 | 0.5 | 2.0286 | 18.509 | 0 | 1 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 60 | 0.5 | 1.9647 | 21.452 | 0 | 1 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 62 | 0.5 | 1.7888 | 20.518 | 0 | 1 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 64 | 0.5 | 2.6831 | 21.647 | 0 | 1 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn | 65 | 0.5 | 2.564 | 20.212 | 0 | 1 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 58 | 0.82742 | 0.59286 | 18.986 | 0.52174 | 0.30435 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 60 | 0.88251 | 0.43369 | 13.258 | 0.30435 | 0.6087 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 62 | 0.86553 | 0.54501 | 17.772 | 0.36957 | 0.52174 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 64 | 0.83696 | 0.35425 | 17.49 | 0.45652 | 0.41304 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 65 | 0.85962 | 0.29281 | 18.528 | 0.43478 | 0.45652 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 58 | 0.80473 | 0.29399 | 16.844 | 0.45652 | 0.32609 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 60 | 0.90378 | 0.33579 | 16.264 | 0.45652 | 0.67391 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 62 | 0.85511 | 0.44383 | 18.409 | 0.41304 | 0.54348 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 64 | 0.86957 | 0.62584 | 18.213 | 0.3913 | 0.6087 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 65 | 0.89135 | 0.35821 | 18.709 | 0.45652 | 0.5 |
| pretrigger_pedestal_samples_0_3 | mlp | 58 | 0.74917 | 0.06387 | 36.324 | 0.5 | 0.6087 |
| pretrigger_pedestal_samples_0_3 | mlp | 60 | 0.80473 | 0.092817 | 42.377 | 0.28261 | 0.69565 |
| pretrigger_pedestal_samples_0_3 | mlp | 62 | 0.75947 | 0.154 | 43.873 | 0.34783 | 0.71739 |
| pretrigger_pedestal_samples_0_3 | mlp | 64 | 0.77174 | 0.19576 | 42.081 | 0.32609 | 0.54348 |
| pretrigger_pedestal_samples_0_3 | mlp | 65 | 0.73462 | 0.16725 | 48.496 | 0.30435 | 0.45652 |
| pretrigger_pedestal_samples_0_3 | ridge | 58 | 0.72695 | 0.9929 | 15.659 | 0.41304 | 0.63043 |
| pretrigger_pedestal_samples_0_3 | ridge | 60 | 0.83759 | 1.9476 | 16.835 | 0.30435 | 0.65217 |
| pretrigger_pedestal_samples_0_3 | ridge | 62 | 0.82765 | 2.1623 | 17.809 | 0.21739 | 0.73913 |
| pretrigger_pedestal_samples_0_3 | ridge | 64 | 0.75 | 2.2026 | 17.925 | 0.30435 | 0.54348 |
| pretrigger_pedestal_samples_0_3 | ridge | 65 | 0.72212 | 1.1869 | 18.58 | 0.41304 | 0.36957 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 58 | 0.5 | 0.76013 | 12.976 | 0.84783 | 0.13043 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 60 | 0.5 | 1.2811 | 16.139 | 0.78261 | 0.15217 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 62 | 0.5 | 0.6584 | 14.919 | 0.78261 | 0.13043 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 64 | 0.5 | 0.88465 | 19.262 | 0.69565 | 0.086957 |
| pretrigger_pedestal_samples_0_3 | small_transformer | 65 | 0.5 | 1.2005 | 14.765 | 0.76087 | 0.065217 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 58 | 0.77139 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 60 | 0.79267 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 62 | 0.76136 |  |  | 1 | 0.021739 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 64 | 0.76087 |  |  | 1 | 0 |
| pretrigger_pedestal_samples_0_3 | traditional_template_likelihood | 65 | 0.76923 | 0.0063488 | 12.122 | 0.93478 | 0.021739 |
| rising_edge_samples_4_7 | 1d_cnn | 58 | 0.5 | 0.4298 | 16.141 | 0.3913 | 0.32609 |
| rising_edge_samples_4_7 | 1d_cnn | 60 | 0.5 | 0.44183 | 15.711 | 0.30435 | 0.52174 |
| rising_edge_samples_4_7 | 1d_cnn | 62 | 0.5 | 0.51194 | 15.294 | 0.34783 | 0.45652 |
| rising_edge_samples_4_7 | 1d_cnn | 64 | 0.5 | 0.47193 | 16.132 | 0.28261 | 0.30435 |
| rising_edge_samples_4_7 | 1d_cnn | 65 | 0.5 | 0.4603 | 15.604 | 0.3913 | 0.3913 |
| rising_edge_samples_4_7 | compact_sequence_residual | 58 | 0.85934 | 4.5783 | 8.6639 | 0.36957 | 0.34783 |
| rising_edge_samples_4_7 | compact_sequence_residual | 60 | 0.86076 | 3.5471 | 11.042 | 0.41304 | 0.47826 |
| rising_edge_samples_4_7 | compact_sequence_residual | 62 | 0.87689 | 4.2557 | 14.056 | 0.43478 | 0.47826 |
| rising_edge_samples_4_7 | compact_sequence_residual | 64 | 0.83696 | 6.142 | 13.625 | 0.34783 | 0.43478 |
| rising_edge_samples_4_7 | compact_sequence_residual | 65 | 0.86635 | 10.423 | 15.321 | 0.47826 | 0.6087 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 58 | 0.83806 | 2.2109 | 12.611 | 0.47826 | 0.34783 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 60 | 0.83806 | 3.2483 | 13.366 | 0.34783 | 0.5 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 62 | 0.87689 | 3.5678 | 13.652 | 0.52174 | 0.47826 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 64 | 0.83696 | 3.7401 | 14.653 | 0.34783 | 0.45652 |
| rising_edge_samples_4_7 | gradient_boosted_trees | 65 | 0.89135 | 2.9539 | 12.088 | 0.5 | 0.52174 |
| rising_edge_samples_4_7 | mlp | 58 | 0.76076 | 2.6368 | 31.776 | 0.30435 | 0.34783 |
| rising_edge_samples_4_7 | mlp | 60 | 0.77281 | 2.4964 | 30.271 | 0.32609 | 0.5 |
| rising_edge_samples_4_7 | mlp | 62 | 0.75947 | 2.4803 | 47.564 | 0.47826 | 0.43478 |
| rising_edge_samples_4_7 | mlp | 64 | 0.77174 | 2.942 | 31.771 | 0.26087 | 0.28261 |
| rising_edge_samples_4_7 | mlp | 65 | 0.78462 | 1.8009 | 33.306 | 0.30435 | 0.41304 |
| rising_edge_samples_4_7 | ridge | 58 | 0.70473 | 135.79 | 12.544 | 0.34783 | 0.43478 |
| rising_edge_samples_4_7 | ridge | 60 | 0.82553 | 56.366 | 13.998 | 0.23913 | 0.52174 |
| rising_edge_samples_4_7 | ridge | 62 | 0.77557 | 165.03 | 15.102 | 0.41304 | 0.52174 |
| rising_edge_samples_4_7 | ridge | 64 | 0.75 | 72.091 | 14.289 | 0.23913 | 0.3913 |
| rising_edge_samples_4_7 | ridge | 65 | 0.71923 | 66.232 | 10.5 | 0.30435 | 0.47826 |
| rising_edge_samples_4_7 | small_transformer | 58 | 0.46572 | 0.4134 | 16.373 | 0.065217 | 0.56522 |
| rising_edge_samples_4_7 | small_transformer | 60 | 0.50969 | 0.32726 | 15.6 | 0.23913 | 0.63043 |
| rising_edge_samples_4_7 | small_transformer | 62 | 0.53504 | 0.48411 | 16.976 | 0.19565 | 0.6087 |
| rising_edge_samples_4_7 | small_transformer | 64 | 0.5 | 0.50997 | 15.527 | 0.1087 | 0.52174 |
| rising_edge_samples_4_7 | small_transformer | 65 | 0.48846 | 0.53458 | 13.141 | 0.19565 | 0.63043 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 58 | 0.72742 | 0.22201 | 24.374 | 0.80435 | 0.13043 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 60 | 0.79314 | 0.072756 | 20.074 | 0.84783 | 0.13043 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 62 | 0.79261 | 0.22033 | 14.091 | 0.76087 | 0.086957 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 64 | 0.76087 | 0.19612 | 21.675 | 0.71739 | 0.086957 |
| rising_edge_samples_4_7 | traditional_template_likelihood | 65 | 0.79135 | 0.25798 | 20.516 | 0.80435 | 0.065217 |

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
