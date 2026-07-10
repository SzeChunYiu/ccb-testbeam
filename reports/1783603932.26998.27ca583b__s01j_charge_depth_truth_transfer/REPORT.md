# S01j Charge-Depth Truth Transfer for q-Template Support Atom

**Ticket:** `1783603932.26998.27ca583b`  
**Worker:** `testbeam-laptop-1`  
**Date:** 2026-07-11

## Abstract

This S01j study repeats the S01h/S01i transfer panel on a calibrated charge-depth detector-level label rather than the prior synthetic pile-up/dropout label. Raw ROOT reproduction is performed first. The held-out run winner is **traditional_charge_depth_rule** with ROC AUC **1.0000** [1.0000, 1.0000] and AP **1.0000** [1.0000, 1.0000]. The strongest traditional method is **traditional_charge_depth_rule** with ROC AUC **1.0000** [1.0000, 1.0000].

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
| charge_depth_threshold_train_quantile | 0.73461534907549                                    |
| train_positive_fraction               | 0.2499846191706657                                  |
| heldout_positive_fraction             | 0.565915915915916                                   |
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
| traditional_charge_depth_rule | traditional      | 33300 |       18845 |  1        |     1        |      1        |            1        |    1        |     1        |
| atom_gated_cnn_new            | new_architecture | 33300 |       18845 |  0.999881 |     0.999834 |      0.999922 |            0.999908 |    0.999854 |     0.999936 |
| mlp                           | nn               | 33300 |       18845 |  0.99988  |     0.999833 |      0.999919 |            0.999908 |    0.999839 |     0.999943 |
| gradient_boosted_trees        | ml               | 33300 |       18845 |  0.999757 |     0.999649 |      0.99985  |            0.999816 |    0.999713 |     0.999883 |
| ridge                         | ml               | 33300 |       18845 |  0.984828 |     0.982591 |      0.988152 |            0.989009 |    0.985161 |     0.991127 |
| traditional_atom_table        | traditional      | 33300 |       18845 |  0.89204  |     0.880387 |      0.906735 |            0.914232 |    0.877271 |     0.934331 |
| 1d_cnn                        | nn               | 33300 |       18845 |  0.675015 |     0.653748 |      0.693907 |            0.701237 |    0.589259 |     0.769901 |
| q_token_attention             | new_architecture | 33300 |       18845 |  0.460106 |     0.416051 |      0.528398 |            0.511475 |    0.426384 |     0.560108 |

## Per-Run Metrics

| method                        |   run |    n |   positives |   roc_auc |   average_precision |
|:------------------------------|------:|-----:|------------:|----------:|--------------------:|
| 1d_cnn                        |    58 | 2590 |         661 |  0.695864 |            0.468761 |
| 1d_cnn                        |    59 | 5719 |        3506 |  0.648749 |            0.710522 |
| 1d_cnn                        |    60 | 5727 |        3820 |  0.695963 |            0.794749 |
| 1d_cnn                        |    61 | 5859 |        3936 |  0.711019 |            0.801621 |
| 1d_cnn                        |    62 | 5729 |        3716 |  0.688151 |            0.777356 |
| 1d_cnn                        |    63 | 4806 |        2437 |  0.644186 |            0.629039 |
| 1d_cnn                        |    65 | 2870 |         769 |  0.643759 |            0.396063 |
| atom_gated_cnn_new            |    58 | 2590 |         661 |  0.999954 |            0.999867 |
| atom_gated_cnn_new            |    59 | 5719 |        3506 |  0.999786 |            0.999866 |
| atom_gated_cnn_new            |    60 | 5727 |        3820 |  0.999896 |            0.999948 |
| atom_gated_cnn_new            |    61 | 5859 |        3936 |  0.999884 |            0.999943 |
| atom_gated_cnn_new            |    62 | 5729 |        3716 |  0.999886 |            0.999938 |
| atom_gated_cnn_new            |    63 | 4806 |        2437 |  0.999832 |            0.999836 |
| atom_gated_cnn_new            |    65 | 2870 |         769 |  0.999939 |            0.999836 |
| gradient_boosted_trees        |    58 | 2590 |         661 |  0.999962 |            0.99989  |
| gradient_boosted_trees        |    59 | 5719 |        3506 |  0.999535 |            0.99971  |
| gradient_boosted_trees        |    60 | 5727 |        3820 |  0.999824 |            0.999913 |
| gradient_boosted_trees        |    61 | 5859 |        3936 |  0.999849 |            0.999926 |
| gradient_boosted_trees        |    62 | 5729 |        3716 |  0.999677 |            0.999827 |
| gradient_boosted_trees        |    63 | 4806 |        2437 |  0.999647 |            0.99967  |
| gradient_boosted_trees        |    65 | 2870 |         769 |  0.999851 |            0.999601 |
| mlp                           |    58 | 2590 |         661 |  0.999954 |            0.999869 |
| mlp                           |    59 | 5719 |        3506 |  0.999769 |            0.999855 |
| mlp                           |    60 | 5727 |        3820 |  0.99989  |            0.999945 |
| mlp                           |    61 | 5859 |        3936 |  0.999907 |            0.999955 |
| mlp                           |    62 | 5729 |        3716 |  0.999903 |            0.999948 |
| mlp                           |    63 | 4806 |        2437 |  0.999807 |            0.999816 |
| mlp                           |    65 | 2870 |         769 |  0.999861 |            0.999626 |
| q_token_attention             |    58 | 2590 |         661 |  0.65488  |            0.364824 |
| q_token_attention             |    59 | 5719 |        3506 |  0.403796 |            0.526513 |
| q_token_attention             |    60 | 5727 |        3820 |  0.39555  |            0.577663 |
| q_token_attention             |    61 | 5859 |        3936 |  0.422725 |            0.592644 |
| q_token_attention             |    62 | 5729 |        3716 |  0.407258 |            0.565068 |
| q_token_attention             |    63 | 4806 |        2437 |  0.477924 |            0.472587 |
| q_token_attention             |    65 | 2870 |         769 |  0.493683 |            0.257157 |
| ridge                         |    58 | 2590 |         661 |  0.993565 |            0.983613 |
| ridge                         |    59 | 5719 |        3506 |  0.982528 |            0.98978  |
| ridge                         |    60 | 5727 |        3820 |  0.98315  |            0.991768 |
| ridge                         |    61 | 5859 |        3936 |  0.984278 |            0.992487 |
| ridge                         |    62 | 5729 |        3716 |  0.981775 |            0.990503 |
| ridge                         |    63 | 4806 |        2437 |  0.982451 |            0.9845   |
| ridge                         |    65 | 2870 |         769 |  0.983555 |            0.962233 |
| traditional_atom_table        |    58 | 2590 |         661 |  0.94204  |            0.842002 |
| traditional_atom_table        |    59 | 5719 |        3506 |  0.877356 |            0.918231 |
| traditional_atom_table        |    60 | 5727 |        3820 |  0.890088 |            0.943212 |
| traditional_atom_table        |    61 | 5859 |        3936 |  0.887897 |            0.942602 |
| traditional_atom_table        |    62 | 5729 |        3716 |  0.879637 |            0.929732 |
| traditional_atom_table        |    63 | 4806 |        2437 |  0.880701 |            0.874569 |
| traditional_atom_table        |    65 | 2870 |         769 |  0.903149 |            0.768432 |
| traditional_charge_depth_rule |    58 | 2590 |         661 |  1        |            1        |
| traditional_charge_depth_rule |    59 | 5719 |        3506 |  1        |            1        |
| traditional_charge_depth_rule |    60 | 5727 |        3820 |  1        |            1        |
| traditional_charge_depth_rule |    61 | 5859 |        3936 |  1        |            1        |
| traditional_charge_depth_rule |    62 | 5729 |        3716 |  1        |            1        |
| traditional_charge_depth_rule |    63 | 4806 |        2437 |  1        |            1        |
| traditional_charge_depth_rule |    65 | 2870 |         769 |  1        |            1        |

## Transfer Diagnostics

| method                        | family           |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |
|:------------------------------|:-----------------|----------:|-------------:|--------------:|--------------------:|------------:|-------------:|
| traditional_charge_depth_rule | traditional      |  1        |     1        |      1        |            1        |    1        |     1        |
| atom_gated_cnn_new            | new_architecture |  0.999881 |     0.999834 |      0.999922 |            0.999908 |    0.999854 |     0.999936 |
| mlp                           | nn               |  0.99988  |     0.999833 |      0.999919 |            0.999908 |    0.999839 |     0.999943 |
| gradient_boosted_trees        | ml               |  0.999757 |     0.999649 |      0.99985  |            0.999816 |    0.999713 |     0.999883 |
| ridge                         | ml               |  0.984828 |     0.982591 |      0.988152 |            0.989009 |    0.985161 |     0.991127 |
| traditional_atom_table        | traditional      |  0.89204  |     0.880387 |      0.906735 |            0.914232 |    0.877271 |     0.934331 |
| 1d_cnn                        | nn               |  0.675015 |     0.653748 |      0.693907 |            0.701237 |    0.589259 |     0.769901 |
| q_token_attention             | new_architecture |  0.460106 |     0.416051 |      0.528398 |            0.511475 |    0.426384 |     0.560108 |

q-template diagnostic contrasts:

| contrast                                        |     value |   q_threshold |
|:------------------------------------------------|----------:|--------------:|
| target_rate_top_decile_q_minus_rest             | -0.375826 |      0.119398 |
| mean_charge_depth_score_top_decile_q_minus_rest | -1.66405  |      0.119398 |
| heldout_target_fraction                         |  0.565916 |      0.119398 |

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
/home/billy/anaconda3/bin/python scripts/s01j_1783603932_26998_27ca583b_charge_depth_truth_transfer.py --config configs/s01j_1783603932_26998_27ca583b_charge_depth_truth_transfer.yaml
```
