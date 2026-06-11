# S13e: residual CWoLa support-collapse atlas

- **Study ID:** S13e
- **Ticket:** `1781059683.869.4bca6f7e`
- **Author:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Depends on:** S13b/S13d CWoLa topology studies.
- **Input checksums:** `input_sha256.csv` pins all raw B-stack ROOT files used here.
- **Config:** `configs/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.json`

## 0. Question

Where does the residualized CWoLa current score lose support or collapse to the charge/topology/anomaly/baseline-lowering matched null? The decision metric is held-out high-current discrimination after leave-run-family-out splitting, with run-block bootstrap confidence intervals for AUC, AP, ECE, score excess, support loss, nuisance AUC, and method-minus-traditional deltas.

## 1. Raw ROOT Reproduction

The analysis rereads the raw B-stack ROOT files for runs 44-57. Baselines are the median of samples 0-3; selected pulses satisfy amplitude > 1000 ADC in B2, B4, B6, or B8. The S13b topology number is reproduced before any ML is fit.

| quantity                                |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S13b downstream-topology high/low ratio |        1.44497 |      1.44497 |       0 |       1e-12 | True   |
| S13b events with selected B-stack pulse |   243133       | 243133       |       0 |       0     | True   |
| S13b selected B-stack pulses            |   252266       | 252266       |       0 |       0     | True   |

The reproduction uses the same physical denominator as S13b: events with at least one selected B-stack pulse, selected-pulse multiplicity, and the high/low downstream-topology ratio. This is a raw-ROOT gate, not a copied report value.

## 2. Dataset and Atoms

The benchmark is pulse-level. Each selected B-stack pulse contributes a normalized 18-sample waveform, hand shape variables, the stave identity, event selected multiplicity, and whether the event contains a downstream selected stave. The weak label is the beam-current group: runs 46 and 47 are low current; runs 44,45,48-57 are high current.

Support atoms are frozen inside each training fold. Let \(g_i\) be the atom formed from charge bin, baseline-absolute bin, pulse-width bin, baseline-lowering flag, topology bin, downstream flag, anomaly taxon, and stave. The traditional null estimates

\[\hat p_g = \frac{k_g + 12\bar y}{n_g+12},\]

where \(k_g\) is the number of high-current training pulses in atom \(g\). A test pulse is on matched support only if its atom has at least the configured low- and high-current count floor and its residual-feature nearest-neighbor distance is within the training 95th percentile. The ticket mentions run-family matching; here run family is the held-out blocking variable, so exact family matching is deliberately unavailable in the test fold and appears as a support-transfer stress rather than a fitted input feature.

Anomaly taxa are deterministic morphology labels: negative dropout, late activity, long tail, early pretrigger, broad pulse, or nominal. They are not trained labels.

## 3. Methods

The strong traditional method is `traditional_matched_null`, the frozen matched-atom current table above. It is the nuisance-only null: a residual CWoLa method only adds information if it improves over this table on held-out run family.

ML/NN methods are fit only on training-family pulses. Scalar and waveform inputs are residualized by subtracting train-atom means before fitting. The compared methods are ridge logistic regression, gradient-boosted trees, tabular MLP, 1D CNN, and a new support-gated CNN. The new architecture is sensible here because a current score should shrink or abstain outside matched support; it receives the residual waveform plus scalar residuals and a learned gate that includes the train-fold support distance.

Controls are amplitude-only, topology-only, and shuffled-current. They diagnose whether apparent CWoLa separation is just charge/topology prevalence or split leakage.

The principal metrics are

\[\mathrm{AUC} = P(s_H>s_L), \quad \mathrm{AP}=\sum_n (R_n-R_{n-1})P_n,\]

\[\mathrm{ECE}=\sum_b \frac{n_b}{N}\left|\bar y_b-\bar s_b\right|, \quad \Delta_s=E[s\mid H]-E[s\mid L].\]

Bootstrap intervals resample source runs with replacement within low- and high-current groups. ML-minus-traditional deltas use paired bootstrap draws.

## 4. Support Atlas

| fold          | current_group   |     n |   support_loss_fraction |   atom_support_loss_fraction |   distance_support_loss_fraction |   mean_support_distance |
|:--------------|:----------------|------:|------------------------:|-----------------------------:|---------------------------------:|------------------------:|
| family_a_to_b | high_20nA       | 10800 |                0.255926 |                    0.234352  |                        0.0628704 |                0.455373 |
| family_a_to_b | low_2nA         |  1800 |                0.172778 |                    0.152778  |                        0.0466667 |                0.502731 |
| family_b_to_a | high_20nA       | 10800 |                0.199444 |                    0.121019  |                        0.15037   |                0.864324 |
| family_b_to_a | low_2nA         |   687 |                0.100437 |                    0.0494905 |                        0.077147  |                0.532873 |

Matched atom inventory:

| fold          |   matched_cells |   all_cells |   matched_effective_pairs |   median_cell_count |
|:--------------|----------------:|------------:|--------------------------:|--------------------:|
| family_a_to_b |              30 |         279 |                       686 |                   4 |
| family_b_to_a |              36 |         215 |                      1797 |                   3 |

Support loss is therefore part of the endpoint, not a post-hoc exclusion. Large support loss means the residual CWoLa surface is being evaluated outside the matched nuisance cells that justify interpreting it as residual information.

## 5. Results

The held-out candidate winner is **gradient_boosted_trees_residual** with AUC **0.5501** [0.3982, 0.8284], AP **0.9095**, ECE **0.0854**, and score excess **0.0325**. The traditional matched null has AUC **0.5096** [0.3118, 0.8588] and score excess **-0.0019**.

| method                          |      auc |   auc_ci_low |   auc_ci_high |   average_precision |   ece_10bin |   score_excess_high_minus_low |   support_loss_fraction |   nuisance_auc |   auc_minus_traditional |   null_minus_real_auc_gap |
|:--------------------------------|---------:|-------------:|--------------:|--------------------:|------------:|------------------------------:|------------------------:|---------------:|------------------------:|--------------------------:|
| gradient_boosted_trees_residual | 0.55006  |     0.398186 |      0.828429 |            0.909459 |   0.0854108 |                     0.0324839 |                0.219953 |       0.509588 |               0.0404717 |                -0.0404717 |
| traditional_matched_null        | 0.509588 |     0.311831 |      0.8588   |            0.904641 |   0.0583692 |                    -0.0019394 |                0.219953 |       0.509588 |               0         |                 0         |
| amplitude_only_control          | 0.48811  |     0.267079 |      0.870731 |            0.899922 |   0.0759028 |                    -0.0077185 |                0.219953 |       0.509588 |              -0.0214783 |                 0.0214783 |
| cnn1d_residual                  | 0.428674 |     0.195481 |      0.858933 |            0.880407 |   0.0790977 |                    -0.0141917 |                0.219953 |       0.509588 |              -0.0809139 |                 0.0809139 |
| ridge_residual                  | 0.425887 |     0.201682 |      0.848408 |            0.879675 |   0.0791335 |                    -0.0149896 |                0.219953 |       0.509588 |              -0.0837015 |                 0.0837015 |
| support_gated_cnn_new           | 0.4187   |     0.186339 |      0.86414  |            0.875722 |   0.0830687 |                    -0.014966  |                0.219953 |       0.509588 |              -0.0908882 |                 0.0908882 |
| topology_only_control           | 0.400983 |     0.181688 |      0.840128 |            0.878144 |   0.0783473 |                    -0.0163796 |                0.219953 |       0.509588 |              -0.108605  |                 0.108605  |
| shuffled_current_control        | 0.384655 |     0.163241 |      0.838574 |            0.865495 |   0.0831655 |                    -0.0186395 |                0.219953 |       0.509588 |              -0.124933  |                 0.124933  |
| mlp_residual                    | 0.369799 |     0.145374 |      0.823244 |            0.860376 |   0.0837018 |                    -0.0199318 |                0.219953 |       0.509588 |              -0.13979   |                 0.13979   |

Paired method-minus-traditional bootstrap deltas:

| method                          | metric                                        |        value |     ci_low |   ci_high |
|:--------------------------------|:----------------------------------------------|-------------:|-----------:|----------:|
| amplitude_only_control          | auc_minus_traditional                         | -0.0214783   | -0.47605   | 0.450579  |
| amplitude_only_control          | brier_minus_traditional                       | -0.00027465  | -0.0857929 | 0.0842466 |
| amplitude_only_control          | score_excess_high_minus_low_minus_traditional | -0.0057791   | -0.148714  | 0.130047  |
| cnn1d_residual                  | auc_minus_traditional                         | -0.0809139   | -0.529371  | 0.441779  |
| cnn1d_residual                  | brier_minus_traditional                       | -0.00113868  | -0.085971  | 0.0828496 |
| cnn1d_residual                  | score_excess_high_minus_low_minus_traditional | -0.0122523   | -0.144638  | 0.107707  |
| gradient_boosted_trees_residual | auc_minus_traditional                         |  0.0404717   | -0.366044  | 0.393475  |
| gradient_boosted_trees_residual | brier_minus_traditional                       |  0.00827916  | -0.0762115 | 0.0961512 |
| gradient_boosted_trees_residual | score_excess_high_minus_low_minus_traditional |  0.0344233   | -0.124032  | 0.206387  |
| mlp_residual                    | auc_minus_traditional                         | -0.13979     | -0.556449  | 0.39603   |
| mlp_residual                    | brier_minus_traditional                       | -0.00235917  | -0.0858922 | 0.0783046 |
| mlp_residual                    | score_excess_high_minus_low_minus_traditional | -0.0179924   | -0.141227  | 0.087554  |
| ridge_residual                  | auc_minus_traditional                         | -0.0837015   | -0.539713  | 0.426984  |
| ridge_residual                  | brier_minus_traditional                       | -0.002331    | -0.0852697 | 0.0829194 |
| ridge_residual                  | score_excess_high_minus_low_minus_traditional | -0.0130502   | -0.146823  | 0.0955689 |
| shuffled_current_control        | auc_minus_traditional                         | -0.124933    | -0.544146  | 0.394029  |
| shuffled_current_control        | brier_minus_traditional                       | -0.00269256  | -0.0847997 | 0.0799745 |
| shuffled_current_control        | score_excess_high_minus_low_minus_traditional | -0.0167001   | -0.145324  | 0.0842098 |
| support_gated_cnn_new           | auc_minus_traditional                         | -0.0908882   | -0.546537  | 0.416637  |
| support_gated_cnn_new           | brier_minus_traditional                       |  0.000993847 | -0.08402   | 0.0844356 |
| support_gated_cnn_new           | score_excess_high_minus_low_minus_traditional | -0.0130266   | -0.154309  | 0.117921  |
| topology_only_control           | auc_minus_traditional                         | -0.108605    | -0.542827  | 0.403833  |
| topology_only_control           | brier_minus_traditional                       | -0.00304595  | -0.0867422 | 0.0799366 |
| topology_only_control           | score_excess_high_minus_low_minus_traditional | -0.0144402   | -0.142743  | 0.0907854 |

A positive AUC delta means residual information survives the matched null. A negative null-minus-real gap means the learned model is stronger than the nuisance table; a positive gap means support/matching has collapsed the learned score back to, or below, the nuisance surface.

## 6. Systematics and Caveats

The dominant systematic is low-current support: only two low-current runs exist in this panel, so leave-family-out folds stress extrapolation from one low-current run to the other. The bootstrap captures run-to-run variation but cannot create missing low-current phase space.

The high-current label is weak supervision, not truth pile-up. A classifier can identify current-dependent detector or acquisition morphology without proving a physical beam-pile-up mechanism. For that reason, topology-only and amplitude-only controls are reported beside the residual models, and the traditional matched null is treated as the primary comparator.

Residualization depends on deterministic atoms. Coarser atoms risk leaving nuisance information; finer atoms increase support loss. The selected atom set follows the ticket: charge, topology, anomaly taxon, baseline lowering, stave, and run-family blocking. Exact run-family matching is impossible under leave-family-out evaluation and is treated as an explicit extrapolation caveat.

No parametric detector model is fit, so chi-squared per degree of freedom is not an appropriate goodness-of-fit statistic. Calibration is summarized by ECE and Brier/log-loss, and discrimination by AUC/AP.

Leakage controls:

| fold          | check                          |       value | flag   | note                                                                                                 |
|:--------------|:-------------------------------|------------:|:-------|:-----------------------------------------------------------------------------------------------------|
| family_a_to_b | train_test_run_overlap         |     0       | False  | Leave-run-family-out folds must have disjoint runs.                                                  |
| family_a_to_b | forbidden_columns_used         |     0       | False  | Model features exclude run number, event number, current label, current group, and run-family label. |
| family_a_to_b | support_distance_cut_train_q95 |     1.75999 | False  | Distance support gate is fit on train-fold residual features only.                                   |
| family_a_to_b | test_rows_scored               | 12600       | False  | Every capped held-out pulse receives a score and support label.                                      |
| family_b_to_a | train_test_run_overlap         |     0       | False  | Leave-run-family-out folds must have disjoint runs.                                                  |
| family_b_to_a | forbidden_columns_used         |     0       | False  | Model features exclude run number, event number, current label, current group, and run-family label. |
| family_b_to_a | support_distance_cut_train_q95 |     1.58169 | False  | Distance support gate is fit on train-fold residual features only.                                   |
| family_b_to_a | test_rows_scored               | 11487       | False  | Every capped held-out pulse receives a score and support label.                                      |

## 7. Interpretation

The winner named in `result.json` is `gradient_boosted_trees_residual`. The relevant physics interpretation is whether its paired AUC and score-excess deltas over the matched null are materially positive while support loss remains acceptable. If the delta interval overlaps zero or support loss is large, the residual CWoLa score should be treated as collapsed to the nuisance/support surface rather than promoted as independent current information.

This result should therefore be used as an atlas: it identifies where current-score discrimination survives matched support and where it is dominated by charge/topology/anomaly/baseline/stave support. It does not by itself establish a calibrated pile-up probability.

## 8. Provenance

`manifest.json` records git commit, command, platform, random seed, input hashes, and output hashes. Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.py --config configs/s13e_1781059683_869_4bca6f7e_residual_cwola_support_collapse_atlas.json
```

Artifacts include `reproduction_match_table.csv`, `topology_by_run.csv`, `pulse_scores.csv`, `support_atlas.csv`, `matched_atom_table.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `run_metrics.csv`, `leakage_checks.csv`, `result.json`, and `manifest.json`.

Runtime: 388.6 s.
