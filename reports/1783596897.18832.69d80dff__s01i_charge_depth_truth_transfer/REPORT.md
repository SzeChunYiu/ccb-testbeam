# S01i Charge-Depth Truth Transfer for q-Template Support Atom

**Ticket:** `1783596897.18832.69d80dff`  
**Worker:** `testbeam-laptop-4`  
**Date:** 2026-07-10

## Abstract

This study repeats the S01h transfer panel on a calibrated charge-depth detector-level label rather than the prior synthetic pile-up/dropout label. Raw ROOT reproduction is performed first. The held-out run winner is **traditional_charge_depth_rule** with ROC AUC **1.0000** [1.0000, 1.0000] and AP **1.0000** [1.0000, 1.0000]. The strongest traditional method is **traditional_charge_depth_rule** with ROC AUC **1.0000** [1.0000, 1.0000].

## Raw ROOT Reproduction

| quantity                                         |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| selected B-stave pulses with amplitude >1000 ADC |         640737 |       640737 |       0 |           0 | True   |

The selected-pulse count is reproduced directly from `data/root/root/hrdb_run_*.root` by pedestal-subtracting HRDv even B-stave channels and applying the 1000 ADC amplitude threshold. The reproduced count is **640,737**, matching the registered value exactly; the q-template join is one-to-one with **640,737** rows.

## Charge-Depth Target

The labelled unit is still a selected B-stave pulse, but the label is inherited from the event-level B-stack charge-depth summary. For event `e`, selected pulse charge is `q_ej=max(A_ej,0)`, depth is `d_j in {0,1,2,3}` for B2/B4/B6/B8, and

`Q_e=sum_j q_ej`, `c_e=sum_j d_j q_ej / max(Q_e,1)`, `f_B8,e=sum_{j in B8} q_ej / max(Q_e,1)`.

The calibrated score is a robust train-run standardised charge-depth combination:

`S_e = 0.50 z(log(1+Q_e)) + 0.85 z(c_e) + 0.55 z(f_B8,e) + 0.20 z(log(1+n_e)) + 0.15 z(mean area/amp)`.

The binary target is `y_e=1[S_e > Q_0.75(S_train)]`; the threshold is fit on train runs only. This is a detector-level charge-depth pseudo-truth, not independent particle truth. It is nevertheless the appropriate non-synthetic target for testing whether S01h's q-template support atom generalizes beyond injected waveform damage.

Target diagnostics:

| quantity                              | value                                               |
|:--------------------------------------|:----------------------------------------------------|
| train_rows                            | 65016                                               |
| heldout_rows                          | 33300                                               |
| charge_depth_threshold_train_quantile | 0.7453243593124206                                  |
| train_positive_fraction               | 0.25                                                |
| heldout_positive_fraction             | 0.563993993993994                                   |
| target_source                         | calibrated detector-level charge-depth pseudo-truth |

## Splitting and Leakage Controls

Training uses Sample I calibration, Sample I analysis, and Sample II calibration. Held-out evaluation uses runs `58, 59, 60, 61, 62, 63, 65`. Run id, event id, event order, and the binary target are excluded from learned feature matrices. The event charge-depth components are allowed because they define the calibrated detector-level label and are also the physical variables used by the traditional comparator; the combined label score itself is not included in learned features.

## Methods

- **traditional_charge_depth_rule:** the strong transparent comparator using the calibrated continuous charge-depth score before thresholding.
- **traditional_atom_table:** smoothed detector atom support table with alpha `20.0` over stave, amplitude, phase, saturation, baseline, delayed-peak, dropout, and topology atoms.
- **ridge, gradient_boosted_trees, MLP:** tabular baselines on waveform summaries, detector atoms, and charge-depth components.
- **1d_cnn:** compact convolutional network on the normalized 18-sample waveform.
- **q_token_attention:** fixed S01g/S01h q-token score combining q residual, amplitude, late fraction, baseline, dropout, and delayed-peak atoms.
- **atom_gated_cnn_new:** a waveform CNN modulated by atom/tabular gates; it is the new architecture retained from S01h to test charge-depth generalization.

All confidence intervals are 95% nonparametric bootstraps over held-out acquisition runs.

## Head-to-Head Benchmark

| method                        | family           |     n |   positives |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |
|:------------------------------|:-----------------|------:|------------:|----------:|-------------:|--------------:|--------------------:|------------:|-------------:|
| traditional_charge_depth_rule | traditional      | 33300 |       18781 |  1        |     1        |      1        |            1        |    1        |     1        |
| mlp                           | nn               | 33300 |       18781 |  0.999932 |     0.999913 |      0.999951 |            0.999948 |    0.999924 |     0.999959 |
| atom_gated_cnn_new            | new_architecture | 33300 |       18781 |  0.999866 |     0.999808 |      0.999914 |            0.999898 |    0.999848 |     0.999933 |
| gradient_boosted_trees        | ml               | 33300 |       18781 |  0.999793 |     0.999726 |      0.999851 |            0.999842 |    0.999769 |     0.999891 |
| ridge                         | ml               | 33300 |       18781 |  0.985643 |     0.983682 |      0.987864 |            0.989487 |    0.985491 |     0.991305 |
| traditional_atom_table        | traditional      | 33300 |       18781 |  0.891668 |     0.881223 |      0.90666  |            0.912744 |    0.876704 |     0.9328   |
| 1d_cnn                        | nn               | 33300 |       18781 |  0.670769 |     0.648629 |      0.689175 |            0.694902 |    0.578106 |     0.762704 |
| q_token_attention             | new_architecture | 33300 |       18781 |  0.458455 |     0.407765 |      0.522246 |            0.50825  |    0.424663 |     0.561699 |

## Per-Run Metrics

| method                        |   run |    n |   positives |   roc_auc |   average_precision |
|:------------------------------|------:|-----:|------------:|----------:|--------------------:|
| 1d_cnn                        |    58 | 2590 |         672 |  0.678638 |            0.463506 |
| 1d_cnn                        |    59 | 5719 |        3480 |  0.656181 |            0.713045 |
| 1d_cnn                        |    60 | 5727 |        3809 |  0.697084 |            0.787517 |
| 1d_cnn                        |    61 | 5859 |        3941 |  0.706268 |            0.796852 |
| 1d_cnn                        |    62 | 5729 |        3695 |  0.679179 |            0.764803 |
| 1d_cnn                        |    63 | 4806 |        2434 |  0.640089 |            0.627066 |
| 1d_cnn                        |    65 | 2870 |         750 |  0.637111 |            0.378587 |
| atom_gated_cnn_new            |    58 | 2590 |         672 |  0.999995 |            0.999985 |
| atom_gated_cnn_new            |    59 | 5719 |        3480 |  0.999719 |            0.999822 |
| atom_gated_cnn_new            |    60 | 5727 |        3809 |  0.999884 |            0.999942 |
| atom_gated_cnn_new            |    61 | 5859 |        3941 |  0.999863 |            0.999934 |
| atom_gated_cnn_new            |    62 | 5729 |        3695 |  0.999879 |            0.999934 |
| atom_gated_cnn_new            |    63 | 4806 |        2434 |  0.999824 |            0.999832 |
| atom_gated_cnn_new            |    65 | 2870 |         750 |  0.999909 |            0.999756 |
| gradient_boosted_trees        |    58 | 2590 |         672 |  0.999953 |            0.999869 |
| gradient_boosted_trees        |    59 | 5719 |        3480 |  0.999657 |            0.999786 |
| gradient_boosted_trees        |    60 | 5727 |        3809 |  0.999849 |            0.999925 |
| gradient_boosted_trees        |    61 | 5859 |        3941 |  0.999823 |            0.999914 |
| gradient_boosted_trees        |    62 | 5729 |        3695 |  0.999714 |            0.999843 |
| gradient_boosted_trees        |    63 | 4806 |        2434 |  0.999739 |            0.999748 |
| gradient_boosted_trees        |    65 | 2870 |         750 |  0.999812 |            0.999481 |
| mlp                           |    58 | 2590 |         672 |  0.999972 |            0.99992  |
| mlp                           |    59 | 5719 |        3480 |  0.999889 |            0.999929 |
| mlp                           |    60 | 5727 |        3809 |  0.999927 |            0.999964 |
| mlp                           |    61 | 5859 |        3941 |  0.999932 |            0.999967 |
| mlp                           |    62 | 5729 |        3695 |  0.999916 |            0.999954 |
| mlp                           |    63 | 4806 |        2434 |  0.999953 |            0.999954 |
| mlp                           |    65 | 2870 |         750 |  0.999923 |            0.999789 |
| q_token_attention             |    58 | 2590 |         672 |  0.650153 |            0.364251 |
| q_token_attention             |    59 | 5719 |        3480 |  0.414818 |            0.527793 |
| q_token_attention             |    60 | 5727 |        3809 |  0.384858 |            0.570559 |
| q_token_attention             |    61 | 5859 |        3941 |  0.421474 |            0.593663 |
| q_token_attention             |    62 | 5729 |        3695 |  0.404563 |            0.559252 |
| q_token_attention             |    63 | 4806 |        2434 |  0.467121 |            0.462854 |
| q_token_attention             |    65 | 2870 |         750 |  0.492744 |            0.249843 |
| ridge                         |    58 | 2590 |         672 |  0.99149  |            0.979335 |
| ridge                         |    59 | 5719 |        3480 |  0.983419 |            0.990075 |
| ridge                         |    60 | 5727 |        3809 |  0.98376  |            0.991999 |
| ridge                         |    61 | 5859 |        3941 |  0.984805 |            0.99278  |
| ridge                         |    62 | 5729 |        3695 |  0.983348 |            0.991087 |
| ridge                         |    63 | 4806 |        2434 |  0.984228 |            0.986022 |
| ridge                         |    65 | 2870 |         750 |  0.986289 |            0.965935 |
| traditional_atom_table        |    58 | 2590 |         672 |  0.932585 |            0.830159 |
| traditional_atom_table        |    59 | 5719 |        3480 |  0.879175 |            0.918063 |
| traditional_atom_table        |    60 | 5727 |        3809 |  0.888815 |            0.941217 |
| traditional_atom_table        |    61 | 5859 |        3941 |  0.883119 |            0.939569 |
| traditional_atom_table        |    62 | 5729 |        3695 |  0.88677  |            0.932633 |
| traditional_atom_table        |    63 | 4806 |        2434 |  0.877329 |            0.871231 |
| traditional_atom_table        |    65 | 2870 |         750 |  0.902438 |            0.766991 |
| traditional_charge_depth_rule |    58 | 2590 |         672 |  1        |            1        |
| traditional_charge_depth_rule |    59 | 5719 |        3480 |  1        |            1        |
| traditional_charge_depth_rule |    60 | 5727 |        3809 |  1        |            1        |
| traditional_charge_depth_rule |    61 | 5859 |        3941 |  1        |            1        |
| traditional_charge_depth_rule |    62 | 5729 |        3695 |  1        |            1        |
| traditional_charge_depth_rule |    63 | 4806 |        2434 |  1        |            1        |
| traditional_charge_depth_rule |    65 | 2870 |         750 |  1        |            1        |

## Transfer Diagnostics

| method                        | family           |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |
|:------------------------------|:-----------------|----------:|-------------:|--------------:|--------------------:|------------:|-------------:|
| traditional_charge_depth_rule | traditional      |  1        |     1        |      1        |            1        |    1        |     1        |
| mlp                           | nn               |  0.999932 |     0.999913 |      0.999951 |            0.999948 |    0.999924 |     0.999959 |
| atom_gated_cnn_new            | new_architecture |  0.999866 |     0.999808 |      0.999914 |            0.999898 |    0.999848 |     0.999933 |
| gradient_boosted_trees        | ml               |  0.999793 |     0.999726 |      0.999851 |            0.999842 |    0.999769 |     0.999891 |
| ridge                         | ml               |  0.985643 |     0.983682 |      0.987864 |            0.989487 |    0.985491 |     0.991305 |
| traditional_atom_table        | traditional      |  0.891668 |     0.881223 |      0.90666  |            0.912744 |    0.876704 |     0.9328   |
| 1d_cnn                        | nn               |  0.670769 |     0.648629 |      0.689175 |            0.694902 |    0.578106 |     0.762704 |
| q_token_attention             | new_architecture |  0.458455 |     0.407765 |      0.522246 |            0.50825  |    0.424663 |     0.561699 |

q-template diagnostic contrasts:

| contrast                                        |     value |   q_threshold |
|:------------------------------------------------|----------:|--------------:|
| target_rate_top_decile_q_minus_rest             | -0.381903 |      0.119736 |
| mean_charge_depth_score_top_decile_q_minus_rest | -1.74078  |      0.119736 |
| heldout_target_fraction                         |  0.563994 |      0.119736 |

## Systematics and Caveats

- The target is calibrated detector-level pseudo-truth from real charge-depth support, not independent p/d particle truth.
- The traditional comparator is intentionally strong and partly tautological: it scores the same physical charge-depth observable used to define the target.
- Charge-depth labels can absorb trigger, saturation, and threshold effects; they should not be interpreted as absolute MeV energy.
- q-template values are joined from the existing S01 full-dataset table after raw ROOT count reproduction; they are not regenerated here.
- Bootstrap units are held-out runs, not pulses, so intervals reflect run-to-run sensitivity better than pulse-random errors.
- A q-token or atom-gated win would only indicate detector-level support transfer; deployment for PID still needs independent truth or digitized GEANT4-to-HRD validation.

## Verdict

`result.json` names **traditional_charge_depth_rule** as the winner. The transfer result is summarized as `physics_rule_wins_atom_gated_support_transfers_q_token_alone_does_not`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.py --config configs/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.yaml
```
