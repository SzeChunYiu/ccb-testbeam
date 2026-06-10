# P05c: real S11b candidate validation of P05a CNN

- **Ticket:** `1781018699.978.01857c74`
- **Worker:** `testbeam-laptop-1`
- **Inputs:** raw HRD ROOT files only; no Monte Carlo.
- **Split:** every score is source-run held out. High-current runs use low-current runs 46/47 only; low-current controls leave their own run out. CIs bootstrap source runs within current group.

## Reproduction first

The P05a injected anchor was rerun from raw ROOT before touching real candidates. The frozen template fit reproduced time RMS **13.90 ns** and the compact CNN **10.01 ns**, with CNN AP **0.868**.

| quantity                              |   report_value |    reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|--------------:|--------:|------------:|:-------|
| P05a selected B-stave pulses          |  640737        | 640737        |       0 |        0    | True   |
| P05a traditional heldout time RMS ns  |      13.8993   |     13.8993   |       0 |        0.05 | True   |
| P05a compact CNN heldout time RMS ns  |      10.0093   |     10.0093   |       0 |        0.05 | True   |
| P05a compact CNN heldout detection AP |       0.868415 |      0.868415 |       0 |        0.01 | True   |

The S11b/S10c real-candidate topology gate was then rerun from raw ROOT; all six documented low/high topology fractions pass.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Methods

Traditional method: the frozen S11a-style bounded two-pulse template fit used in S11b. Templates are median empirical pulse shapes from low-current training runs only, and each event reports A2/(A1+A2) after the constrained fit.

ML method: a compact P05a-style 18-sample 1D CNN with two convolution layers, a detection head, and a four-output decomposition head. It is trained only on data-driven two-pulse overlays made from low-current raw pulses under the same source-run holdout policy, then applied unchanged to real low/high candidate windows.

## Real candidate result

| method_metric           |      value |      ci_low |   ci_high | bootstrap_unit                  |   n_bootstrap |   n_scored_events |
|:------------------------|-----------:|------------:|----------:|:--------------------------------|--------------:|------------------:|
| trad_secondary_fraction | 0.0180645  | -0.0177331  | 0.0529963 | source_run_within_current_group |           500 |             12617 |
| cnn_secondary_fraction  | 0.00984466 |  0.00304651 | 0.0165309 | source_run_within_current_group |           500 |             12617 |
| cnn_overlap_score       | 0.0321328  |  0.00752589 | 0.0563207 | source_run_within_current_group |           500 |             12617 |

Traditional matched high-minus-low secondary fraction is **0.01806** [-0.01773, 0.05300]. The compact CNN secondary-fraction delta is **0.00984** [0.00305, 0.01653], and its overlap-score delta is **0.03213** [0.00753, 0.05632].

Largest positive CNN secondary-fraction strata:

| amp_bin       | baseline_bin       | p02_topology        |   low_n_scored |   high_n_scored |   low_mean |   high_mean |   high_minus_low |   match_weight |
|:--------------|:-------------------|:--------------------|---------------:|----------------:|-----------:|------------:|-----------------:|---------------:|
| amp_ge_4500   | s16_large_lowering | p02_broad_late      |             27 |            1465 | 0.00307099 |   0.16291   |       0.159839   |     0.00470465 |
| amp_ge_4500   | s16_large_lowering | p02_early_pathology |             45 |            1151 | 0.0185625  |   0.0617541 |       0.0431916  |     0.00784109 |
| amp_1000_2500 | s16_mild_lowering  | p02_broad_late      |             38 |             820 | 0.0293998  |   0.0714951 |       0.0420953  |     0.00662136 |
| amp_1000_2500 | s16_large_lowering | p02_early_pathology |            132 |            1637 | 0.0312258  |   0.0567507 |       0.0255248  |     0.0230005  |
| amp_2500_4500 | s16_no_lowering    | p02_broad_late      |            280 |            1680 | 0.019383   |   0.0373959 |       0.018013   |     0.293605   |
| amp_1000_2500 | s16_no_lowering    | p02_broad_late      |            239 |            1680 | 0.0274785  |   0.0427464 |       0.0152678  |     0.135738   |
| amp_ge_4500   | s16_no_lowering    | p02_broad_late      |            280 |            1680 | 0.0183913  |   0.0193969 |       0.00100567 |     0.519603   |
| amp_2500_4500 | s16_large_lowering | p02_early_pathology |             51 |            1412 | 0.0623054  |   0.0628138 |       0.00050842 |     0.00888657 |

## Leakage review

| check                                               |     value | flag   | note                                                                                                   |
|:----------------------------------------------------|----------:|:-------|:-------------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_cnn_training | 1         | False  | High-current runs are never in CNN/template training; low-current controls leave their source run out. |
| identifier_features_excluded                        | 1         | False  | CNN sees only 18 normalized waveform samples, not run, event number, current, or stratum.              |
| synthetic_train_source_runs_exclude_heldout         | 1         | False  | Fold diagnostics record raw source runs used to make low-current overlays.                             |
| mean_cnn_synthetic_holdout_auc                      | 0.912758  | False  | Near-perfect heldout overlay classification would be suspicious.                                       |
| mean_cnn_shuffled_label_synthetic_auc               | 0.454319  | False  | Shuffled-label CNN should not classify heldout overlays well.                                          |
| actual_current_auc_from_cnn_overlap_score           | 0.633819  | False  | Flagged if the CNN score nearly identifies beam current by itself.                                     |
| actual_current_auc_from_cnn_secondary_fraction      | 0.636495  | False  | Flagged if the CNN secondary estimate nearly identifies beam current by itself.                        |
| cnn_score_source_run_eta2                           | 0.0165395 | False  | Run-level variance fraction of the real CNN overlap score.                                             |
| source_run_predictability_from_waveform_samples     | 0.101162  | False  | Random-split sentinel accuracy for predicting source run from the same normalized samples.             |

Mean held-out overlay AUC for the CNN diagnostic is 0.913; shuffled-label AUC is 0.454.

## Conclusion

The injected P05a ranking reproduces from raw ROOT: CNN time RMS 10.01 ns versus template fit 13.90 ns. On real S11b candidate shapes the ranking does not transfer as a larger secondary-fraction excess: the template fit gives 0.01806 [-0.01773, 0.05300], while the compact CNN gives 0.00984 [0.00305, 0.01653] for secondary fraction and 0.03213 [0.00753, 0.05632] for overlap score. Leakage sentinels flag 0 checks, so this remains a diagnostic transfer test rather than a truth-labelled pile-up measurement.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p05c_1781018699_978_01857c74_real_s11b_cnn_validation.py --config configs/p05c_1781018699_978_01857c74.json
```
