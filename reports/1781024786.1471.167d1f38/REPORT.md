# S07i: S07f injected-score transfer to real current strata

- **Ticket:** `1781024786.1471.167d1f38`
- **Worker:** `testbeam-laptop-4`
- **Data:** raw B-stack ROOT only; no Monte Carlo.
- **Split:** held-out run pairs, one low all-three-rate edge run plus one high all-three-rate run.

## Reproduction first

The S07f injected-corruption benchmark was rebuilt from raw ROOT before the real-current transfer test.

| quantity                                 |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| parent App.I guarded gross D_t>51 ns     |      72        |    72        |       0 |       0     | True   |
| all-three control events                 |    3774        |  3774        |       0 |       0     | True   |
| all-three guarded gross D_t>51 ns        |      22        |    22        |       0 |       0     | True   |
| S07f injected all-three shape RF ROC AUC |       0.822118 |     0.822118 |       0 |       0.001 | True   |

| method                                    |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |    brier |   brier_ci_low |   brier_ci_high | notes                                                                                                                                                       |
|:------------------------------------------|----------:|-----------------:|------------------:|--------------------:|------------:|-------------:|---------:|---------------:|----------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| traditional fold-selected timing/template |  0.605954 |         0.598605 |          0.618069 |            0.570681 |    0.561867 |     0.583083 | 0.239508 |       0.237077 |        0.241699 | Fold-local best signed timing, curvature, shape-summary, or matched-template score.                                                                         |
| direct D_t/curvature cross-check          |  0.530522 |         0.51749  |          0.537119 |            0.581449 |    0.566058 |     0.597987 | 0.24422  |       0.240807 |        0.247804 | Not label-defining here; target is injected two-pulse truth.                                                                                                |
| all-three shape-only RF                   |  0.822118 |         0.80083  |          0.844361 |            0.83589  |    0.81471  |     0.860373 | 0.177242 |       0.164769 |        0.190468 | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, run/event ids, injection params, amplitudes, and topology flags. |

Run-family metadata from the same raw scan:

|   run | current_run_family      |   raw_events |   parent_control_events |   all_three_events |   all_three_rate |
|------:|:------------------------|-------------:|------------------------:|-------------------:|-----------------:|
|    58 | low_all_three_rate_edge |        34141 |                     201 |                 72 |       0.0021089  |
|    59 | mid_all_three_rate      |        42303 |                    2161 |                749 |       0.0177056  |
|    60 | high_all_three_rate     |        36074 |                    2025 |                802 |       0.0222321  |
|    61 | high_all_three_rate     |        36535 |                    2319 |                925 |       0.0253182  |
|    62 | high_all_three_rate     |        37584 |                    2154 |                798 |       0.0212324  |
|    63 | mid_all_three_rate      |        37030 |                    1045 |                365 |       0.00985687 |
|    65 | low_all_three_rate_edge |        38424 |                     251 |                 63 |       0.0016396  |

## Methods

For each held-out low/high run pair, the S07f-style RF keeps the S07f strict shape feature family and best hyperparameters. It is trained only on injected clean/corrupted rows from the other runs; isotonic calibration and the 95% clean-efficiency threshold are learned only from injected folds. It is then applied to real all-three high-current and low-edge rows matched in train-derived bins for amplitude, charge, B2 amplitude, B2 saturation, baseline-lowering proxy, anomaly-shape proxy, and run family.

The traditional comparator is a fold-local one-dimensional timing/template score selected on the same injected training rows from curvature, timing spread, downstream shape summaries, and a train-only matched secondary-template residual.

## Results

Traditional score shift high-minus-low: **-0.1046** [-0.2184, 0.0128], candidate-excess delta **-0.0529**.

S07f RF score shift high-minus-low: **0.0114** [-0.0077, 0.0321], candidate-excess delta **0.0118** [-0.0267, 0.0556]. Current-family AUC is **0.528**.

Amplitude-only sentinel shift is **0.0117**; shuffled-label RF shift is **-0.0020**.

| method               | score_col                  |   score_shift_high_minus_low |   score_shift_ci_low |   score_shift_ci_high |   candidate_excess_high_minus_low |   candidate_excess_ci_low |   candidate_excess_ci_high |   current_family_auc |   current_family_auc_ci_low |   current_family_auc_ci_high |   n_matched_events |
|:---------------------|:---------------------------|-----------------------------:|---------------------:|----------------------:|----------------------------------:|--------------------------:|---------------------------:|---------------------:|----------------------------:|-----------------------------:|-------------------:|
| traditional_template | traditional_template_score |                  -0.104575   |          -0.218427   |             0.0128452 |                        -0.0529412 |                -0.0994152 |                 -0.0116229 |             0.466955 |                    0.433126 |                     0.500059 |                340 |
| s07f_shape_rf        | s07f_shape_rf_score        |                   0.011363   |          -0.00774774 |             0.0320984 |                         0.0117647 |                -0.026738  |                  0.0555556 |             0.527716 |                    0.483266 |                     0.576737 |                340 |
| amplitude_only_rf    | amplitude_only_rf_score    |                   0.0117026  |          -0.00703986 |             0.0249953 |                         0.0705882 |                -0.0127389 |                  0.148218  |             0.534913 |                    0.45741  |                     0.596939 |                340 |
| shuffled_label_rf    | shuffled_label_rf_score    |                  -0.00196002 |          -0.0112038  |             0.0111123 |                        -0.0117647 |                -0.0342906 |                  0         |             0.50526  |                    0.455952 |                     0.568713 |                340 |

Held-out fold details:

| fold                 | method               |   n_matched_events |   score_shift_high_minus_low |   candidate_excess_high_minus_low |   current_family_auc |   low_gross_events |   high_gross_events |
|:---------------------|:---------------------|-------------------:|-----------------------------:|----------------------------------:|---------------------:|-------------------:|--------------------:|
| holdout_low58_high60 | traditional_template |                 64 |                   0.0625     |                         0         |             0.502441 |                  0 |                   2 |
| holdout_low58_high60 | s07f_shape_rf        |                 64 |                   0.00399346 |                         0         |             0.519531 |                  0 |                   2 |
| holdout_low58_high60 | amplitude_only_rf    |                 64 |                   0.0293802  |                         0.125     |             0.616211 |                  0 |                   2 |
| holdout_low58_high60 | shuffled_label_rf    |                 64 |                  -0.0182944  |                         0         |             0.412109 |                  0 |                   2 |
| holdout_low58_high61 | traditional_template |                 64 |                  -0.138889   |                        -0.15625   |             0.457031 |                  0 |                   0 |
| holdout_low58_high61 | s07f_shape_rf        |                 64 |                   0.0226261  |                         0         |             0.544922 |                  0 |                   0 |
| holdout_low58_high61 | amplitude_only_rf    |                 64 |                   0.0293886  |                         0.21875   |             0.598633 |                  0 |                   0 |
| holdout_low58_high61 | shuffled_label_rf    |                 64 |                  -0.00452906 |                        -0.0625    |             0.496094 |                  0 |                   0 |
| holdout_low58_high62 | traditional_template |                 68 |                  -0.333333   |                        -0.0588235 |             0.397491 |                  0 |                   0 |
| holdout_low58_high62 | s07f_shape_rf        |                 68 |                  -0.0261386  |                        -0.0588235 |             0.442907 |                  0 |                   0 |
| holdout_low58_high62 | amplitude_only_rf    |                 68 |                   0.0193749  |                         0.0588235 |             0.589965 |                  0 |                   0 |
| holdout_low58_high62 | shuffled_label_rf    |                 68 |                  -0.0124654  |                         0         |             0.476644 |                  0 |                   0 |
| holdout_low65_high60 | traditional_template |                 42 |                   0.047619   |                         0         |             0.496599 |                  0 |                   0 |
| holdout_low65_high60 | s07f_shape_rf        |                 42 |                   0.0616661  |                         0.047619  |             0.634921 |                  0 |                   0 |
| holdout_low65_high60 | amplitude_only_rf    |                 42 |                   0.0195094  |                         0.0952381 |             0.54195  |                  0 |                   0 |
| holdout_low65_high60 | shuffled_label_rf    |                 42 |                   0.027048   |                         0         |             0.662132 |                  0 |                   0 |
| holdout_low65_high61 | traditional_template |                 48 |                  -0.0138889  |                         0         |             0.517361 |                  0 |                   1 |
| holdout_low65_high61 | s07f_shape_rf        |                 48 |                   0.02626    |                         0.125     |             0.572917 |                  0 |                   1 |
| holdout_low65_high61 | amplitude_only_rf    |                 48 |                  -0.024253   |                        -0.0416667 |             0.375    |                  0 |                   1 |
| holdout_low65_high61 | shuffled_label_rf    |                 48 |                   0.0171536  |                         0         |             0.579861 |                  0 |                   1 |
| holdout_low65_high62 | traditional_template |                 54 |                  -0.17284    |                        -0.0740741 |             0.453361 |                  0 |                   0 |
| holdout_low65_high62 | s07f_shape_rf        |                 54 |                   0.00160652 |                         0         |             0.508916 |                  0 |                   0 |
| holdout_low65_high62 | amplitude_only_rf    |                 54 |                  -0.0139826  |                        -0.0740741 |             0.440329 |                  0 |                   0 |
| holdout_low65_high62 | shuffled_label_rf    |                 54 |                  -0.00587867 |                         0         |             0.462277 |                  0 |                   0 |

Injected-fold calibration diagnostics:

| method               |   oof_auc |   oof_ap |   oof_brier |     oof_ece |
|:---------------------|----------:|---------:|------------:|------------:|
| amplitude_only_rf    |  0.556065 | 0.56099  |    0.244138 | 3.71268e-17 |
| s07f_shape_rf        |  0.81184  | 0.821971 |    0.171111 | 7.79601e-17 |
| shuffled_label_rf    |  0.487789 | 0.494619 |    0.250818 | 0.0227639   |
| traditional_template |  0.603658 | 0.57109  |    0.243898 | 0.0296031   |

## Leakage hunt

No leakage sentinel flagged: train/test runs and events are disjoint, forbidden identifiers/timing/current columns are absent from the main RF, shuffled injected labels do not stably separate current family, and the S07f RF is not suspiciously perfect.

## Interpretation

Verdict: `no_stable_positive_s07f_transfer`. S07f reproduces from raw ROOT at AUC 0.822118. On real matched current strata, the S07f RF high-minus-low score shift is 0.0114 [-0.0077, 0.0321], while the traditional timing/template shift is -0.1046 [-0.2184, 0.0128]. Leakage sentinels flagged 0 checks, so this is a calibrated transfer diagnostic rather than a truth-labelled pile-up rate.

## Follow-up tickets

No new follow-up ticket is proposed here; S07l/S07m-style injected morphology support, current-family nulls, and sparse-support audits are already present in the queue or completed studies.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07f_injection_scoreboard.csv`, `run_family_metadata.csv`, `heldout_matched_transfer_scores.csv`, `heldout_run_pair_metrics.csv`, `pooled_heldout_bootstrap_metrics.csv`, `injected_fold_calibration.csv`, `template_rf_agreement.csv`, and `leakage_checks.csv`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07i_1781024786_1471_167d1f38_score_transfer.py --config configs/s07i_1781024786_1471_167d1f38.json
```
