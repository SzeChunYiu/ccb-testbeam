# S11d: low-current downstream-template support sensitivity

- **Ticket:** `1781017990.1312.3c8f5f66`
- **Worker:** `testbeam-laptop-2`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** source-run held out; high-current events use low-current-only templates/synthetic overlays; low-current controls leave their own run out.

## Reproduction first

The S11b/S10c topology gate was rerun from raw ROOT before sensitivity scoring. All documented topology fractions pass:

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

The baseline S11b policy is also reproduced: traditional matched high-minus-low secondary fraction is **0.01806** [-0.01679, 0.05414], versus the source S11b value 0.01806. ML secondary fraction is **0.00437** and ML overlap score is **0.02007**.

## Low-current support

The downstream low-current template counts in the control folds are:

|   heldout_run |   training_runs | stave   |   raw_clean_count |   effective_template_count | template_source_stave   |   fallback_reason |
|--------------:|----------------:|:--------|------------------:|---------------------------:|:------------------------|------------------:|
|            46 |              47 | B4      |                31 |                         31 | B4                      |               nan |
|            46 |              47 | B6      |                22 |                         22 | B6                      |               nan |
|            46 |              47 | B8      |                14 |                         14 | B8                      |               nan |
|            47 |              46 | B4      |                 1 |                          1 | B4                      |               nan |
|            47 |              46 | B6      |                 2 |                          2 | B6                      |               nan |
|            47 |              46 | B8      |                 1 |                          1 | B8                      |               nan |

## Traditional sensitivity

The traditional method is the bounded two-pulse fit, rerun under deterministic support policies: B4/B6/B8 fallback ablations, minimum downstream-template count thresholds, and high-current single-run support checks. The largest absolute shift is `high_only_run46_support` at **+0.01734**.

| policy                   |     value |      ci_low |   ci_high |   delta_vs_baseline |
|:-------------------------|----------:|------------:|----------:|--------------------:|
| baseline_all_low_support | 0.0180645 | -0.0167945  | 0.0541375 |         0           |
| min_downstream_100       | 0.0193539 | -0.0173992  | 0.0577256 |         0.00128941  |
| min_downstream_250       | 0.0193539 | -0.0170389  | 0.055364  |         0.00128941  |
| min_downstream_500       | 0.0193539 | -0.018918   | 0.056674  |         0.00128941  |
| min_downstream_1000      | 0.0193539 | -0.0173698  | 0.0573867 |         0.00128941  |
| ablate_B4_to_B2          | 0.0181731 | -0.0197709  | 0.0563033 |         0.000108557 |
| ablate_B6_to_B2          | 0.0190013 | -0.0167185  | 0.0541363 |         0.000936788 |
| ablate_B8_to_B2          | 0.0183086 | -0.0178292  | 0.0541068 |         0.000244062 |
| high_only_run46_support  | 0.0354093 | -0.00150867 | 0.0717952 |         0.0173448   |
| high_only_run47_support  | 0.0156943 | -0.0205599  | 0.0517977 |        -0.0023702   |

## ML support diagnostic

The ML method is the same low-current-only synthetic-overlay residual classifier/regressor used in S11b, rerun for baseline plus selected support-stress policies. Fold diagnostics are stratified by minimum available downstream template count.

| policy                   | method_metric         |      value |       ci_low |   ci_high |   delta_vs_baseline |
|:-------------------------|:----------------------|-----------:|-------------:|----------:|--------------------:|
| baseline_all_low_support | ml_secondary_fraction | 0.00437376 | -0.00137663  | 0.0120591 |         0           |
| baseline_all_low_support | ml_overlap_score      | 0.0200722  | -0.0114264   | 0.051858  |         0           |
| min_downstream_500       | ml_secondary_fraction | 0.00626091 |  0.000258832 | 0.0138122 |         0.00188716  |
| min_downstream_500       | ml_overlap_score      | 0.0237792  | -0.00351854  | 0.0530179 |         0.00370694  |
| min_downstream_1000      | ml_secondary_fraction | 0.00709899 |  0.000673681 | 0.015326  |         0.00272523  |
| min_downstream_1000      | ml_overlap_score      | 0.0214195  | -0.00579397  | 0.0503424 |         0.00134722  |
| ablate_B4_to_B2          | ml_secondary_fraction | 0.00587173 | -0.00134859  | 0.0137601 |         0.00149797  |
| ablate_B4_to_B2          | ml_overlap_score      | 0.0195518  | -0.0112411   | 0.0507049 |        -0.000520457 |
| ablate_B6_to_B2          | ml_secondary_fraction | 0.00584017 | -0.000255212 | 0.0134027 |         0.00146641  |
| ablate_B6_to_B2          | ml_overlap_score      | 0.0167856  | -0.0105553   | 0.0470625 |        -0.00328668  |
| ablate_B8_to_B2          | ml_secondary_fraction | 0.00777836 |  0.00158522  | 0.0139028 |         0.0034046   |
| ablate_B8_to_B2          | ml_overlap_score      | 0.0185009  | -0.0117285   | 0.0499333 |        -0.00157138  |

## Leakage review

Leakage flags: **0**.

| policy                   | check                                              |    value | flag   | note                                                                                                   |
|:-------------------------|:---------------------------------------------------|---------:|:-------|:-------------------------------------------------------------------------------------------------------|
| ablate_B4_to_B2          | heldout_run_excluded_from_template_and_ml_training | 1        | False  | Every scored source run uses low-current template and ML training with held-out low controls excluded. |
| ablate_B4_to_B2          | identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.           |
| ablate_B4_to_B2          | actual_current_auc_from_ml_secondary_fraction      | 0.594296 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                         |
| ablate_B6_to_B2          | heldout_run_excluded_from_template_and_ml_training | 1        | False  | Every scored source run uses low-current template and ML training with held-out low controls excluded. |
| ablate_B6_to_B2          | identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.           |
| ablate_B6_to_B2          | actual_current_auc_from_ml_secondary_fraction      | 0.58991  | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                         |
| ablate_B8_to_B2          | heldout_run_excluded_from_template_and_ml_training | 1        | False  | Every scored source run uses low-current template and ML training with held-out low controls excluded. |
| ablate_B8_to_B2          | identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.           |
| ablate_B8_to_B2          | actual_current_auc_from_ml_secondary_fraction      | 0.627443 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                         |
| baseline_all_low_support | heldout_run_excluded_from_template_and_ml_training | 1        | False  | Every scored source run uses low-current template and ML training with held-out low controls excluded. |
| baseline_all_low_support | identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.           |
| baseline_all_low_support | actual_current_auc_from_ml_secondary_fraction      | 0.567954 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                         |
| min_downstream_1000      | heldout_run_excluded_from_template_and_ml_training | 1        | False  | Every scored source run uses low-current template and ML training with held-out low controls excluded. |
| min_downstream_1000      | identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.           |
| min_downstream_1000      | actual_current_auc_from_ml_secondary_fraction      | 0.614258 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                         |
| min_downstream_500       | heldout_run_excluded_from_template_and_ml_training | 1        | False  | Every scored source run uses low-current template and ML training with held-out low controls excluded. |
| min_downstream_500       | identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.           |
| min_downstream_500       | actual_current_auc_from_ml_secondary_fraction      | 0.633999 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                         |
| ablate_B4_to_B2          | synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used for synthetic overlay training.                           |
| ablate_B4_to_B2          | mean_synthetic_holdout_auc                         | 0.9268   | False  | Very high synthetic AUC would be suspicious under held-out source-run residuals.                       |
| ablate_B4_to_B2          | mean_shuffled_label_synthetic_auc                  | 0.486801 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                          |
| ablate_B6_to_B2          | synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used for synthetic overlay training.                           |
| ablate_B6_to_B2          | mean_synthetic_holdout_auc                         | 0.926978 | False  | Very high synthetic AUC would be suspicious under held-out source-run residuals.                       |
| ablate_B6_to_B2          | mean_shuffled_label_synthetic_auc                  | 0.516172 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                          |
| ablate_B8_to_B2          | synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used for synthetic overlay training.                           |
| ablate_B8_to_B2          | mean_synthetic_holdout_auc                         | 0.925708 | False  | Very high synthetic AUC would be suspicious under held-out source-run residuals.                       |
| ablate_B8_to_B2          | mean_shuffled_label_synthetic_auc                  | 0.503443 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                          |
| baseline_all_low_support | synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used for synthetic overlay training.                           |
| baseline_all_low_support | mean_synthetic_holdout_auc                         | 0.925521 | False  | Very high synthetic AUC would be suspicious under held-out source-run residuals.                       |
| baseline_all_low_support | mean_shuffled_label_synthetic_auc                  | 0.518107 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                          |
| min_downstream_1000      | synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used for synthetic overlay training.                           |
| min_downstream_1000      | mean_synthetic_holdout_auc                         | 0.925254 | False  | Very high synthetic AUC would be suspicious under held-out source-run residuals.                       |
| min_downstream_1000      | mean_shuffled_label_synthetic_auc                  | 0.501781 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                          |
| min_downstream_500       | synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used for synthetic overlay training.                           |
| min_downstream_500       | mean_synthetic_holdout_auc                         | 0.927571 | False  | Very high synthetic AUC would be suspicious under held-out source-run residuals.                       |
| min_downstream_500       | mean_shuffled_label_synthetic_auc                  | 0.507014 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                          |

## Conclusion

The S11b baseline is support-sensitive but not dominated by a single downstream low-current template. Traditional support policies shift matched high-minus-low secondary fraction by up to 0.01734; the ML secondary-fraction diagnostic shifts by up to 0.00340 across the selected support-stress policies. Minimum-count fallbacks and B4/B6/B8 deterministic ablations remain inside the broad run-bootstrap uncertainty, so sparse runs 46/47 downstream support is a systematic to report rather than a clear sign reversal.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `template_support_by_fold.csv`, `traditional_policy_summary.csv`, `traditional_policy_stratum_summary.csv`, `ml_policy_summary.csv`, `ml_fold_diagnostics.csv`, `ml_support_bucket_summary.csv`, `leakage_checks.csv`, and sampled score tables are in this folder.
