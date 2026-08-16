# S13f: external low-current-like support validation

- **Study ID:** S13f
- **Ticket:** `2427`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-07-10
- **Depends on:** S13b/S13d topology studies and S13e residual support-collapse atlas.
- **Input checksums:** `input_sha256.csv` pins all raw B-stack ROOT files used here.
- **Config:** `configs/s13f_2427_external_low_current_support_validation.json`

## 0. Question

Can quiet adjacent-current/external control runs expand the low-current support atoms used by S13e without importing current-label leakage? The decision metric is held-out high-current discrimination after leave-run-family-out splitting, with run-block bootstrap confidence intervals for AUC, AP, ECE, score excess, support loss, nuisance AUC, and method-minus-traditional deltas.

## 1. Raw ROOT Reproduction

The analysis rereads the raw B-stack ROOT files for runs 44-57. Baselines are the median of samples 0-3; selected pulses satisfy amplitude > 1000 ADC in B2, B4, B6, or B8. The S13b topology number is reproduced before any ML is fit.

| quantity                                |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S13b downstream-topology high/low ratio |        1.44497 |      1.44497 |       0 |       1e-12 | True   |
| S13b events with selected B-stack pulse |   243133       | 243133       |       0 |       0     | True   |
| S13b selected B-stack pulses            |   252266       | 252266       |       0 |       0     | True   |

The reproduction uses the same physical denominator as S13b: events with at least one selected B-stack pulse, selected-pulse multiplicity, and the high/low downstream-topology ratio. This is a raw-ROOT gate, not a copied report value.

## 2. Dataset and Atoms

The benchmark is pulse-level. Each selected B-stack pulse contributes a normalized 18-sample waveform, hand shape variables, the stave identity, event selected multiplicity, and whether the event contains a downstream selected stave. The weak label is the beam-current group: runs 46 and 47 are low current; runs 44,45,48-57 are high current. Runs 58,59,60,61,62,63,65 are support-only external controls: they are atomized, but never assigned high/low labels and never enter model training or held-out scoring.

Support atoms are frozen inside each training fold. Let \(g_i\) be the atom formed from charge bin, baseline-absolute bin, pulse-width bin, baseline-lowering flag, topology bin, downstream flag, anomaly taxon, and stave. The traditional null estimates

\[\hat p_g = \frac{k_g + 12\bar y}{n_g+12},\]

where \(k_g\) is the number of high-current training pulses in atom \(g\). External support is not used in \(\hat p_g\). It only expands the low-current support audit via \(\tilde n_{g,L}=n_{g,L}+w_E n_{g,E}\), with \(w_E=0.65\). A test pulse is on matched support only if its atom has at least the configured high-current floor, enough expanded low-current support, and residual-feature nearest-neighbor distance within the training 95th percentile.

Anomaly taxa are deterministic morphology labels: negative dropout, late activity, long tail, early pretrigger, broad pulse, or nominal. They are not trained labels.

## 3. Methods

The strong traditional method is `traditional_external_support_table`, the frozen matched-atom current table above with support-only external expansion. It is the nuisance-only null: a residual CWoLa method only adds information if it improves over this table on held-out run family.

ML/NN methods are fit only on training-family pulses. Scalar and waveform inputs are residualized by subtracting train-atom means before fitting. The compared methods are ridge logistic regression, gradient-boosted trees, tabular MLP, 1D CNN, and a new support-gated CNN. The new architecture is sensible here because a current score should shrink or abstain outside matched support; it receives the residual waveform plus scalar residuals and a learned gate that includes the train-fold support distance.

Controls are amplitude-only, topology-only, and shuffled-current. They diagnose whether apparent CWoLa separation is just charge/topology prevalence or split leakage.

The principal metrics are

\[\mathrm{AUC} = P(s_H>s_L), \quad \mathrm{AP}=\sum_n (R_n-R_{n-1})P_n,\]

\[\mathrm{ECE}=\sum_b \frac{n_b}{N}\left|\bar y_b-\bar s_b\right|, \quad \Delta_s=E[s\mid H]-E[s\mid L].\]

Bootstrap intervals resample source runs with replacement within low- and high-current groups. ML-minus-traditional deltas use paired bootstrap draws.

## 4. Support Atlas

| fold          | current_group   |    n |   support_loss_fraction |   atom_support_loss_fraction |   distance_support_loss_fraction |   mean_support_distance |
|:--------------|:----------------|-----:|------------------------:|-----------------------------:|---------------------------------:|------------------------:|
| family_a_to_b | high_20nA       | 9000 |               0.107111  |                    0.0735556 |                        0.0551111 |                0.451413 |
| family_a_to_b | low_2nA         | 1500 |               0.0893333 |                    0.0646667 |                        0.0453333 |                0.473631 |
| family_b_to_a | high_20nA       | 9000 |               0.188889  |                    0.0874444 |                        0.146889  |                0.937775 |
| family_b_to_a | low_2nA         |  687 |               0.0960699 |                    0.0378457 |                        0.0684134 |                0.624268 |

Matched atom inventory:

| fold          |   matched_cells |   all_cells |   matched_effective_pairs |   median_cell_count |
|:--------------|----------------:|------------:|--------------------------:|--------------------:|
| family_a_to_b |              52 |         279 |                   3453.6  |                   3 |
| family_b_to_a |              56 |         258 |                   3360.55 |                   3 |

External support audit:

| fold          |   all_cells |   supported_cells |   labeled_supported_cells |   cells_expanded_by_external |   support_expansion_fraction |   external_count_total |   expanded_low_support_total |   effective_pairs_total |
|:--------------|------------:|------------------:|--------------------------:|-----------------------------:|-----------------------------:|-----------------------:|-----------------------------:|------------------------:|
| family_a_to_b |         279 |                52 |                        27 |                           25 |                    0.0896057 |                   6056 |                       4623.4 |                 3453.6  |
| family_b_to_a |         258 |                56 |                        39 |                           17 |                    0.0658915 |                   6082 |                       5453.3 |                 3360.55 |

Support loss is therefore part of the endpoint, not a post-hoc exclusion. Large support loss means the residual CWoLa surface is being evaluated outside the matched nuisance cells that justify interpreting it as residual information.

## 5. Results

The overall held-out benchmark winner is **traditional_external_support_table** with AUC **0.5503** [0.3812, 0.8194], AP **0.9063**, ECE **0.0577**, and score excess **0.0070**. The best ML/NN candidate is **gradient_boosted_trees_residual** with AUC **0.5227** [0.2990, 0.8600] and AUC-minus-traditional **-0.0276**.

| method                             |      auc |   auc_ci_low |   auc_ci_high |   average_precision |   ece_10bin |   score_excess_high_minus_low |   support_loss_fraction |   nuisance_auc |   auc_minus_traditional |   null_minus_real_auc_gap |
|:-----------------------------------|---------:|-------------:|--------------:|--------------------:|------------:|------------------------------:|------------------------:|---------------:|------------------------:|--------------------------:|
| traditional_external_support_table | 0.550313 |     0.381166 |      0.819417 |            0.906294 |   0.0577289 |                   0.00700177  |                0.141873 |       0.550313 |               0         |                 0         |
| gradient_boosted_trees_residual    | 0.522692 |     0.298954 |      0.860041 |            0.894619 |   0.110171  |                   0.0454253   |                0.141873 |       0.550313 |              -0.0276213 |                 0.0276213 |
| amplitude_only_control             | 0.521732 |     0.309332 |      0.864384 |            0.901047 |   0.0623605 |                  -0.000897198 |                0.141873 |       0.550313 |              -0.0285808 |                 0.0285808 |
| cnn1d_residual                     | 0.472749 |     0.23896  |      0.839428 |            0.889133 |   0.0607189 |                  -0.00563769  |                0.141873 |       0.550313 |              -0.0775636 |                 0.0775636 |
| ridge_residual                     | 0.46831  |     0.242033 |      0.843841 |            0.888544 |   0.0618597 |                  -0.00709488  |                0.141873 |       0.550313 |              -0.0820034 |                 0.0820034 |
| support_gated_cnn_new              | 0.454642 |     0.202374 |      0.834884 |            0.883078 |   0.0727084 |                  -0.00928536  |                0.141873 |       0.550313 |              -0.0956707 |                 0.0956707 |
| mlp_residual                       | 0.45148  |     0.252107 |      0.818021 |            0.88619  |   0.0729443 |                  -0.00175629  |                0.141873 |       0.550313 |              -0.0988331 |                 0.0988331 |
| topology_only_control              | 0.418308 |     0.178703 |      0.840927 |            0.875461 |   0.0679375 |                  -0.01141     |                0.141873 |       0.550313 |              -0.132005  |                 0.132005  |
| shuffled_current_control           | 0.413432 |     0.170219 |      0.877781 |            0.867631 |   0.0719706 |                  -0.0133509   |                0.141873 |       0.550313 |              -0.136882  |                 0.136882  |

Paired method-minus-traditional bootstrap deltas:

| method                          | metric                                        |        value |     ci_low |   ci_high |
|:--------------------------------|:----------------------------------------------|-------------:|-----------:|----------:|
| amplitude_only_control          | auc_minus_traditional                         | -0.0285808   | -0.391461  | 0.382991  |
| amplitude_only_control          | brier_minus_traditional                       |  0.00029605  | -0.0783268 | 0.0743002 |
| amplitude_only_control          | score_excess_high_minus_low_minus_traditional | -0.00789897  | -0.138503  | 0.12435   |
| cnn1d_residual                  | auc_minus_traditional                         | -0.0775636   | -0.417204  | 0.346281  |
| cnn1d_residual                  | brier_minus_traditional                       | -0.00192532  | -0.0752818 | 0.069657  |
| cnn1d_residual                  | score_excess_high_minus_low_minus_traditional | -0.0126395   | -0.131685  | 0.093324  |
| gradient_boosted_trees_residual | auc_minus_traditional                         | -0.0276213   | -0.391467  | 0.362985  |
| gradient_boosted_trees_residual | brier_minus_traditional                       |  0.0164624   | -0.0601858 | 0.0944445 |
| gradient_boosted_trees_residual | score_excess_high_minus_low_minus_traditional |  0.0384235   | -0.111022  | 0.206871  |
| mlp_residual                    | auc_minus_traditional                         | -0.0988331   | -0.481895  | 0.328352  |
| mlp_residual                    | brier_minus_traditional                       |  0.00302988  | -0.0720169 | 0.0803296 |
| mlp_residual                    | score_excess_high_minus_low_minus_traditional | -0.00875806  | -0.146033  | 0.128935  |
| ridge_residual                  | auc_minus_traditional                         | -0.0820034   | -0.445081  | 0.339789  |
| ridge_residual                  | brier_minus_traditional                       | -0.00247167  | -0.0737856 | 0.0702322 |
| ridge_residual                  | score_excess_high_minus_low_minus_traditional | -0.0140967   | -0.131754  | 0.0800428 |
| shuffled_current_control        | auc_minus_traditional                         | -0.136882    | -0.563936  | 0.369903  |
| shuffled_current_control        | brier_minus_traditional                       | -0.00332844  | -0.0756181 | 0.0717914 |
| shuffled_current_control        | score_excess_high_minus_low_minus_traditional | -0.0203527   | -0.142571  | 0.0716571 |
| support_gated_cnn_new           | auc_minus_traditional                         | -0.0956707   | -0.496187  | 0.334649  |
| support_gated_cnn_new           | brier_minus_traditional                       |  0.000104508 | -0.0731715 | 0.0751516 |
| support_gated_cnn_new           | score_excess_high_minus_low_minus_traditional | -0.0162871   | -0.144656  | 0.0942929 |
| topology_only_control           | auc_minus_traditional                         | -0.132005    | -0.499821  | 0.364444  |
| topology_only_control           | brier_minus_traditional                       | -0.00360814  | -0.0775459 | 0.0694303 |
| topology_only_control           | score_excess_high_minus_low_minus_traditional | -0.0184117   | -0.133247  | 0.0793456 |

A positive AUC delta means residual information survives the matched null. A negative null-minus-real gap means the learned model is stronger than the nuisance table; a positive gap means support/matching has collapsed the learned score back to, or below, the nuisance surface.

## 6. Systematics and Caveats

The dominant systematic is low-current support: only two low-current runs exist in this panel, so leave-family-out folds stress extrapolation from one low-current run to the other. The bootstrap captures run-to-run variation but cannot create missing low-current phase space.

The high-current label is weak supervision, not truth pile-up. A classifier can identify current-dependent detector or acquisition morphology without proving a physical beam-pile-up mechanism. For that reason, topology-only and amplitude-only controls are reported beside the residual models, and the traditional matched null is treated as the primary comparator.

Residualization depends on deterministic atoms. Coarser atoms risk leaving nuisance information; finer atoms increase support loss. The selected atom set follows the ticket: charge, topology, anomaly taxon, baseline lowering, stave, and run-family blocking. Exact run-family matching is impossible under leave-family-out evaluation and is treated as an explicit extrapolation caveat.

No parametric detector model is fit, so chi-squared per degree of freedom is not an appropriate goodness-of-fit statistic. Calibration is summarized by ECE and Brier/log-loss, and discrimination by AUC/AP.

Leakage controls:

| fold          | check                           |       value | flag   | note                                                                                                 |
|:--------------|:--------------------------------|------------:|:-------|:-----------------------------------------------------------------------------------------------------|
| family_a_to_b | train_test_run_overlap          |     0       | False  | Leave-run-family-out folds must have disjoint runs.                                                  |
| family_a_to_b | external_rows_labeled           |     0       | False  | External control runs are support-only and never enter labeled train/test current arrays.            |
| family_a_to_b | external_train_test_run_overlap |     0       | False  | External support runs must be disjoint from all labeled high/low runs.                               |
| family_a_to_b | external_support_rows           |  6300       | False  | External control rows are atomized only to expand low-current-like support counts.                   |
| family_a_to_b | forbidden_columns_used          |     0       | False  | Model features exclude run number, event number, current label, current group, and run-family label. |
| family_a_to_b | support_distance_cut_train_q95  |     1.90609 | False  | Distance support gate is fit on train-fold residual features only.                                   |
| family_a_to_b | test_rows_scored                | 10500       | False  | Every capped held-out pulse receives a score and support label.                                      |
| family_b_to_a | train_test_run_overlap          |     0       | False  | Leave-run-family-out folds must have disjoint runs.                                                  |
| family_b_to_a | external_rows_labeled           |     0       | False  | External control runs are support-only and never enter labeled train/test current arrays.            |
| family_b_to_a | external_train_test_run_overlap |     0       | False  | External support runs must be disjoint from all labeled high/low runs.                               |
| family_b_to_a | external_support_rows           |  6300       | False  | External control rows are atomized only to expand low-current-like support counts.                   |
| family_b_to_a | forbidden_columns_used          |     0       | False  | Model features exclude run number, event number, current label, current group, and run-family label. |
| family_b_to_a | support_distance_cut_train_q95  |     1.90344 | False  | Distance support gate is fit on train-fold residual features only.                                   |
| family_b_to_a | test_rows_scored                |  9687       | False  | Every capped held-out pulse receives a score and support label.                                      |

## 7. Interpretation

The winner named in `result.json` is `traditional_external_support_table`. The relevant physics interpretation is whether its paired AUC and score-excess deltas over the matched null are materially positive while support loss remains acceptable. If the delta interval overlaps zero or support loss is large, the residual CWoLa score should be treated as collapsed to the nuisance/support surface rather than promoted as independent current information.

This result should therefore be used as an atlas: it identifies where current-score discrimination survives matched support and where it is dominated by charge/topology/anomaly/baseline/stave support. It does not by itself establish a calibrated pile-up probability.

## 8. Provenance

`manifest.json` records git commit, command, platform, random seed, input hashes, and output hashes. No novel follow-up ticket is appended by this result. Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s13f_1781173865_934_2a1e2781_external_low_current_support_validation.py --config configs/s13f_2427_external_low_current_support_validation.json
```

Artifacts include `reproduction_match_table.csv`, `topology_by_run.csv`, `pulse_scores.csv`, `support_atlas.csv`, `matched_atom_table.csv`, `external_support_audit.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `run_metrics.csv`, `leakage_checks.csv`, `result.json`, and `manifest.json`.

Runtime: 105.9 s.
