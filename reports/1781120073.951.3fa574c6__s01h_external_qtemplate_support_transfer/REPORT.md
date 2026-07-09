# S01h external q-template support transfer

**Ticket:** `1781120073.951.3fa574c6`
**Worker:** `testbeam-laptop-4`
**Date:** 2026-07-09

## Abstract

This study tests whether the S01g q-template risk atom transfers to an externally labeled support target. The external target is deterministic injected pile-up plus local dropout applied to raw-derived normalized B-stave waveforms; no S03 timing residual or timing-tail label is used. Raw ROOT reproduction is performed first. The held-out run winner is **gradient_boosted_trees** with ROC AUC **0.9986** [0.9984, 0.9989] and AP **0.9815** [0.9699, 0.9902]. The strongest traditional method is **traditional_atom_table** with ROC AUC **0.9771** [0.9740, 0.9788].

## Raw ROOT reproduction

| quantity                                         |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| selected B-stave pulses with amplitude >1000 ADC |         640737 |       640737 |       0 |           0 | True   |

The reproduced selected-pulse count is **640,737**, matching the registered raw B-stave count exactly. The q-template table join is one-to-one with **640,737** rows.

## Target and equations

For pulse waveform `x_i(t)`, a deterministic external perturbation is formed as a mixture of a delayed secondary-pulse overlay and a local dropout:

`p_i(t)=norm[x_i(t)+a x_i(t-d)]`, `d_i(t)=norm[x_i(t) * m(t)]`, and `z_i(t)=w p_i(t)+(1-w)d_i(t)`.

The injected support-damage score is

`D_i = RMSE(z_i,x_i) + 0.35 RMSE(Delta z_i, Delta x_i) + 0.06 max(sum_{t>=10} z_i(t)-x_i(t),0)`.

The binary target is `y_i=1[D_i > Q_0.85(D_train)]`; the threshold is fit on train runs only. This makes the target an injected pile-up/dropout support label rather than an S03b timing-tail proxy. All confidence intervals are 95% nonparametric bootstraps over held-out runs.

## Splitting and leakage controls

Training uses Sample I calibration, Sample I analysis, and Sample II calibration. Held-out evaluation uses runs `58, 59, 60, 61, 62, 63, 65`. Run id, event id, event order, and the binary target are excluded from all learned feature matrices. The traditional q-threshold and q-token attention rows intentionally receive q-template summaries because the ticket asks whether that risk atom transfers; the other ML baselines are reported with the same observable scalar/waveform support features.

## Methods

- **traditional_q_threshold:** train-run 90th-percentile threshold on `q_template_rmse`, scored directly as the q residual.
- **traditional_atom_table:** smoothed detector atom support table with alpha `20.0` over stave, amplitude, phase, saturation, baseline, delayed-peak, dropout, and topology atoms.
- **ridge, gradient_boosted_trees, MLP:** tabular baselines on waveform summaries and detector atoms.
- **1d_cnn:** compact convolutional network on the normalized 18-sample waveform.
- **q_token_attention:** fixed S01g-style q-token score combining q residual, amplitude, late fraction, baseline, dropout, and delayed-peak atoms.
- **atom_gated_cnn_new:** a waveform CNN modulated by atom/tabular gates; it is the new architecture because injected support failures are waveform-local but amplitude/stave/baseline conditional.

## Head-to-head benchmark

| method                  | family           |     n |   positives |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |
|:------------------------|:-----------------|------:|------------:|----------:|-------------:|--------------:|--------------------:|------------:|-------------:|
| gradient_boosted_trees  | ml               | 33300 |        2077 |  0.998644 |     0.998358 |      0.998933 |           0.981498  |   0.969925  |    0.990175  |
| atom_gated_cnn_new      | new_architecture | 33300 |        2077 |  0.99729  |     0.996709 |      0.997744 |           0.963186  |   0.944623  |    0.978487  |
| mlp                     | nn               | 33300 |        2077 |  0.996273 |     0.995111 |      0.997398 |           0.951839  |   0.915339  |    0.976332  |
| ridge                   | ml               | 33300 |        2077 |  0.980343 |     0.97652  |      0.98356  |           0.806576  |   0.72196   |    0.878996  |
| traditional_atom_table  | traditional      | 33300 |        2077 |  0.977113 |     0.973958 |      0.978818 |           0.663836  |   0.601014  |    0.728355  |
| 1d_cnn                  | nn               | 33300 |        2077 |  0.976103 |     0.971523 |      0.980663 |           0.59797   |   0.502545  |    0.726342  |
| traditional_q_threshold | traditional      | 33300 |        2077 |  0.407578 |     0.379664 |      0.436201 |           0.0824975 |   0.0763101 |    0.0947742 |
| q_token_attention       | new_architecture | 33300 |        2077 |  0.173721 |     0.138789 |      0.205078 |           0.0381628 |   0.0302439 |    0.0538306 |

## Per-run metrics

| method                  |   run |    n |   positives |   roc_auc |   average_precision |
|:------------------------|------:|-----:|------------:|----------:|--------------------:|
| 1d_cnn                  |    58 | 2590 |         508 |  0.985193 |           0.875238  |
| 1d_cnn                  |    59 | 5719 |         249 |  0.973211 |           0.527973  |
| 1d_cnn                  |    60 | 5727 |         333 |  0.967004 |           0.492416  |
| 1d_cnn                  |    61 | 5859 |         232 |  0.971632 |           0.481603  |
| 1d_cnn                  |    62 | 5729 |         231 |  0.978607 |           0.509888  |
| 1d_cnn                  |    63 | 4806 |         321 |  0.980523 |           0.664645  |
| 1d_cnn                  |    65 | 2870 |         203 |  0.973859 |           0.614829  |
| atom_gated_cnn_new      |    58 | 2590 |         508 |  0.997451 |           0.988599  |
| atom_gated_cnn_new      |    59 | 5719 |         249 |  0.995949 |           0.935163  |
| atom_gated_cnn_new      |    60 | 5727 |         333 |  0.997667 |           0.964321  |
| atom_gated_cnn_new      |    61 | 5859 |         232 |  0.996819 |           0.929965  |
| atom_gated_cnn_new      |    62 | 5729 |         231 |  0.997412 |           0.946799  |
| atom_gated_cnn_new      |    63 | 4806 |         321 |  0.996811 |           0.962778  |
| atom_gated_cnn_new      |    65 | 2870 |         203 |  0.997689 |           0.967948  |
| gradient_boosted_trees  |    58 | 2590 |         508 |  0.99907  |           0.996082  |
| gradient_boosted_trees  |    59 | 5719 |         249 |  0.99824  |           0.967619  |
| gradient_boosted_trees  |    60 | 5727 |         333 |  0.998477 |           0.977771  |
| gradient_boosted_trees  |    61 | 5859 |         232 |  0.998181 |           0.960795  |
| gradient_boosted_trees  |    62 | 5729 |         231 |  0.99858  |           0.971788  |
| gradient_boosted_trees  |    63 | 4806 |         321 |  0.998425 |           0.979873  |
| gradient_boosted_trees  |    65 | 2870 |         203 |  0.998762 |           0.986344  |
| mlp                     |    58 | 2590 |         508 |  0.997677 |           0.990665  |
| mlp                     |    59 | 5719 |         249 |  0.994951 |           0.924684  |
| mlp                     |    60 | 5727 |         333 |  0.994903 |           0.921572  |
| mlp                     |    61 | 5859 |         232 |  0.99474  |           0.89049   |
| mlp                     |    62 | 5729 |         231 |  0.995468 |           0.916243  |
| mlp                     |    63 | 4806 |         321 |  0.997408 |           0.968072  |
| mlp                     |    65 | 2870 |         203 |  0.997902 |           0.971568  |
| q_token_attention       |    58 | 2590 |         508 |  0.109056 |           0.111914  |
| q_token_attention       |    59 | 5719 |         249 |  0.209503 |           0.0304753 |
| q_token_attention       |    60 | 5727 |         333 |  0.226724 |           0.0393671 |
| q_token_attention       |    61 | 5859 |         232 |  0.200509 |           0.0258585 |
| q_token_attention       |    62 | 5729 |         231 |  0.184469 |           0.0361431 |
| q_token_attention       |    63 | 4806 |         321 |  0.168233 |           0.0386791 |
| q_token_attention       |    65 | 2870 |         203 |  0.176693 |           0.0426232 |
| ridge                   |    58 | 2590 |         508 |  0.986929 |           0.958074  |
| ridge                   |    59 | 5719 |         249 |  0.976493 |           0.732069  |
| ridge                   |    60 | 5727 |         333 |  0.978349 |           0.766225  |
| ridge                   |    61 | 5859 |         232 |  0.975287 |           0.689642  |
| ridge                   |    62 | 5729 |         231 |  0.980539 |           0.692468  |
| ridge                   |    63 | 4806 |         321 |  0.981173 |           0.82578   |
| ridge                   |    65 | 2870 |         203 |  0.976234 |           0.820374  |
| traditional_atom_table  |    58 | 2590 |         508 |  0.962731 |           0.792008  |
| traditional_atom_table  |    59 | 5719 |         249 |  0.979693 |           0.639472  |
| traditional_atom_table  |    60 | 5727 |         333 |  0.971783 |           0.624713  |
| traditional_atom_table  |    61 | 5859 |         232 |  0.976834 |           0.546255  |
| traditional_atom_table  |    62 | 5729 |         231 |  0.97792  |           0.581932  |
| traditional_atom_table  |    63 | 4806 |         321 |  0.978855 |           0.693287  |
| traditional_atom_table  |    65 | 2870 |         203 |  0.97107  |           0.630691  |
| traditional_q_threshold |    58 | 2590 |         508 |  0.394993 |           0.160314  |
| traditional_q_threshold |    59 | 5719 |         249 |  0.458756 |           0.074828  |
| traditional_q_threshold |    60 | 5727 |         333 |  0.408713 |           0.0915985 |
| traditional_q_threshold |    61 | 5859 |         232 |  0.377551 |           0.0813273 |
| traditional_q_threshold |    62 | 5729 |         231 |  0.394676 |           0.0752055 |
| traditional_q_threshold |    63 | 4806 |         321 |  0.43437  |           0.0946788 |
| traditional_q_threshold |    65 | 2870 |         203 |  0.479153 |           0.105498  |

## Transfer diagnostics

| method                  | family           |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |
|:------------------------|:-----------------|----------:|-------------:|--------------:|--------------------:|------------:|-------------:|
| gradient_boosted_trees  | ml               |  0.998644 |     0.998358 |      0.998933 |           0.981498  |   0.969925  |    0.990175  |
| atom_gated_cnn_new      | new_architecture |  0.99729  |     0.996709 |      0.997744 |           0.963186  |   0.944623  |    0.978487  |
| mlp                     | nn               |  0.996273 |     0.995111 |      0.997398 |           0.951839  |   0.915339  |    0.976332  |
| ridge                   | ml               |  0.980343 |     0.97652  |      0.98356  |           0.806576  |   0.72196   |    0.878996  |
| traditional_atom_table  | traditional      |  0.977113 |     0.973958 |      0.978818 |           0.663836  |   0.601014  |    0.728355  |
| 1d_cnn                  | nn               |  0.976103 |     0.971523 |      0.980663 |           0.59797   |   0.502545  |    0.726342  |
| traditional_q_threshold | traditional      |  0.407578 |     0.379664 |      0.436201 |           0.0824975 |   0.0763101 |    0.0947742 |
| q_token_attention       | new_architecture |  0.173721 |     0.138789 |      0.205078 |           0.0381628 |   0.0302439 |    0.0538306 |

q-template diagnostic contrasts:

| contrast                            |      value |   q_threshold |
|:------------------------------------|-----------:|--------------:|
| target_rate_top_decile_q_minus_rest | -0.015713  |      0.123964 |
| mean_damage_top_decile_q_minus_rest | -0.0370986 |      0.123964 |
| heldout_target_fraction             |  0.0623724 |      0.123964 |

## Systematics and caveats

- The external target is injected, not independent beam truth. It tests transfer away from S03 timing residuals but not absolute pile-up rates.
- The injection kernel is deterministic and laptop-safe; larger perturbation grids could change absolute AUCs.
- The q-template source table is reused after raw ROOT count reproduction, so q values are not regenerated from scratch in this script.
- Bootstrap units are runs, not pulses; this intentionally gives wider and more honest intervals.
- A model win on injected support damage is diagnostic unless confirmed on real labeled pile-up/dropout or calibrated charge-depth truth.

## Verdict

`result.json` names **gradient_boosted_trees** as the winner. The transfer result is summarized as `weak_or_no_q_template_transfer`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s01h_1781120073_951_3fa574c6_external_qtemplate_support_transfer.py --config configs/s01h_1781120073_951_3fa574c6_external_qtemplate_support_transfer.yaml
```
