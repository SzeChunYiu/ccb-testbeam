# S13d: charge-matched Sample-II current-family timing-tail null

- **Ticket:** `1781023657.1294.140a38e7`
- **Worker:** `testbeam-laptop-1`
- **Data:** raw B-stack ROOT under `data/root/root`; no Monte Carlo.

## Question

Do Sample-II high all-three-rate runs retain larger timing-tail waveform scores than low-edge runs after matching event charge, B2 amplitude, saturation state, and held-out run pairs?

## Reproduction first

The S07g/App.I control population and guarded gross-tail count were rebuilt from raw ROOT before this null test.

| quantity                                     |   report_value |   reproduced |   delta |   tolerance | pass   |
|:---------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| parent control events, B2 and >=2 downstream |          10156 |        10156 |       0 |           0 | True   |
| parent clean events, D_t<3 ns                |           2155 |         2155 |       0 |           0 | True   |
| parent gross events, documented D_t>50 ns    |             74 |           74 |       0 |           0 | True   |
| parent gross events, guarded D_t>51 ns       |             72 |           72 |       0 |           0 | True   |
| S13d all-three control events                |           3774 |         3774 |       0 |           0 | True   |
| S13d all-three guarded gross events          |             22 |           22 |       0 |           0 | True   |

Run-family metadata reproduced from the same raw scan:

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

Rows are Sample-II all-three downstream events. Each fold holds out one low-edge run and one high-rate run, trains the timing-tail scorers only on the other runs, and then matches held-out low/high rows inside train-derived bins for event maximum amplitude, total positive charge, B2 amplitude, and B2 saturation state.

The traditional scorer is a train-fold logistic calibration of `|C_t| = |t_B8 - 2t_B6 + t_B4|` to the clean/gross timing-tail label. The ML scorer is a random forest trained on amplitude-normalized B2/B4/B6/B8 waveform shapes and pulse-shape ratios; it excludes run, event id, current family, D_t, C_t, and absolute amplitudes. Intervals bootstrap the six held-out run-pair folds.

## Results

Traditional curvature high-minus-low timing-tail score: **0.0089** [-0.0032, 0.0217], current-family AUC **0.495**.

ML waveform high-minus-low timing-tail score: **-0.0948** [-0.1099, -0.0778], current-family AUC **0.389** [0.386, 0.396]. Shuffled-label RF delta is **0.0012**.

| method                | score_col                        |   high_minus_low_score |   high_minus_low_ci_low |   high_minus_low_ci_high |   current_family_auc |   current_family_auc_ci_low |   current_family_auc_ci_high |   n_matched_events |
|:----------------------|:---------------------------------|-----------------------:|------------------------:|-------------------------:|---------------------:|----------------------------:|-----------------------------:|-------------------:|
| traditional_curvature | traditional_curvature_tail_score |             0.00890432 |             -0.00318764 |                0.0217452 |             0.494549 |                    0.472808 |                     0.52254  |                688 |
| ml_waveform_rf        | ml_waveform_tail_score           |            -0.0947728  |             -0.109926   |               -0.077767  |             0.389315 |                    0.386021 |                     0.395996 |                688 |
| shuffled_label_rf     | shuffled_label_tail_score        |             0.00115815 |             -0.0144626  |                0.020907  |             0.502442 |                    0.463631 |                     0.552292 |                688 |

Held-out run-pair details:

| fold                 | method                |   n_matched_events |   high_minus_low_score |   current_family_auc |   low_gross_events |   high_gross_events |
|:---------------------|:----------------------|-------------------:|-----------------------:|---------------------:|-------------------:|--------------------:|
| holdout_low58_high60 | traditional_curvature |                102 |           -0.000260434 |             0.472895 |                  0 |                   0 |
| holdout_low58_high60 | ml_waveform_rf        |                102 |           -0.11535     |             0.390235 |                  0 |                   0 |
| holdout_low58_high60 | shuffled_label_rf     |                102 |            0.04445     |             0.62822  |                  0 |                   0 |
| holdout_low58_high61 | traditional_curvature |                128 |            0.0180606   |             0.472168 |                  0 |                   1 |
| holdout_low58_high61 | ml_waveform_rf        |                128 |           -0.120574    |             0.386963 |                  0 |                   1 |
| holdout_low58_high61 | shuffled_label_rf     |                128 |            0.014281    |             0.545898 |                  0 |                   1 |
| holdout_low58_high62 | traditional_curvature |                128 |           -0.0129032   |             0.512451 |                  0 |                   0 |
| holdout_low58_high62 | ml_waveform_rf        |                128 |           -0.0986588   |             0.391357 |                  0 |                   0 |
| holdout_low58_high62 | shuffled_label_rf     |                128 |           -0.0237497   |             0.458008 |                  0 |                   0 |
| holdout_low65_high60 | traditional_curvature |                110 |            0.03216     |             0.484628 |                  0 |                   1 |
| holdout_low65_high60 | ml_waveform_rf        |                110 |           -0.0773853   |             0.387769 |                  0 |                   1 |
| holdout_low65_high60 | shuffled_label_rf     |                110 |           -0.00272276  |             0.458512 |                  0 |                   1 |
| holdout_low65_high61 | traditional_curvature |                110 |            0.0173089   |             0.478017 |                  0 |                   1 |
| holdout_low65_high61 | ml_waveform_rf        |                110 |           -0.0916611   |             0.395702 |                  0 |                   1 |
| holdout_low65_high61 | shuffled_label_rf     |                110 |           -0.013245    |             0.458512 |                  0 |                   1 |
| holdout_low65_high62 | traditional_curvature |                110 |            0.00046384  |             0.561653 |                  0 |                   0 |
| holdout_low65_high62 | ml_waveform_rf        |                110 |           -0.0616462   |             0.400992 |                  0 |                   0 |
| holdout_low65_high62 | shuffled_label_rf     |                110 |           -0.00698776  |             0.490579 |                  0 |                   0 |

## Leakage checks

No leakage check flagged. Train/test runs are disjoint, event overlap is zero, forbidden identifiers/current/timing columns are excluded from the ML feature matrix, and the shuffled-label RF is not a stable current-family separator.

## Interpretation

Verdict: `not_stable_positive_current_family_tail_signal`. The charge-matched high-rate minus low-edge contrast is small and fold-sensitive; sparse low-edge support remains the limiting factor. The result supports treating S07g current-family hints as a support/composition diagnostic rather than a standalone timing-tail waveform effect.

## Follow-up tickets

No new follow-up ticket is proposed; this ticket directly executes the S07g/S13 current-family null, and nearby run-drift, external-scaler, and sparse-support audits already exist in completed S02/S07/S13 studies.

## Artifacts

`reproduction_match_table.csv`, `run_family_metadata.csv`, `heldout_run_pair_metrics.csv`, `pooled_heldout_bootstrap_metrics.csv`, `heldout_matched_timing_tail_scores.csv`, `leakage_checks.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.

Runtime: 83.3 s.
