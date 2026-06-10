# S13c: charge-matched current weak-supervision null

- **Ticket:** `1781021831.1960.52610a78`
- **Worker:** `testbeam-laptop-2`
- **Data:** raw B-stack ROOT under `data/root/root`; no Monte Carlo.

## Question

After matching charge proxy, topology, anomaly taxon, baseline-lowering proxy, run family, and stave, does a current weak-supervision classifier retain stable held-out current information beyond a frozen traditional matched-stratum excess table?

## Reproduction first

The S10 downstream occupancy excess was rerun from raw ROOT before the S13c analysis. The reproduced high-minus-low downstream rate is **0.0102897471**; low and high downstream rates are **0.0231243577** and **0.0334141048**.

| quantity                                         |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S10 downstream high-minus-low per selected event |      0.0102897 |    0.0102897 |       0 |       1e-12 | True   |
| S10 low-current downstream per selected event    |      0.0231244 |    0.0231244 |       0 |       0     | True   |
| S10 high-current downstream per selected event   |      0.0334141 |    0.0334141 |       0 |       0     | True   |

## Methods

Pulses are matched separately inside run families on charge quantile, S10 topology bin, anomaly taxon, S16 baseline-lowering proxy, run family, and stave. The traditional method is a frozen train-family stratum table: each held-out pulse receives the train-family high-current fraction for its matched nuisance stratum. The ML method is a calibrated random-forest CWoLa classifier trained leave-one-run-family-out on normalized waveform samples plus pulse-shape latent summaries after linear residualization against the matched nuisance one-hot matrix.

Metrics are held-out high-minus-low score excess, current AUC/AP, calibration ECE, nuisance-only current AUC after matching/residualization, and the ML-minus-traditional excess. Intervals are stratified run-block bootstrap 95% CIs over held-out runs.

## Results

Traditional matched-stratum excess: **-0.0233** [-0.2191, 0.0560], AUC **0.450**.

Residualized CWoLa excess: **0.0014** [-0.1776, 0.0776], AUC **0.526** [0.086, 0.704], AP **0.644**, ECE **0.150**. ML-minus-traditional excess is **0.0247** [0.0163, 0.0455].

Nuisance-only AUC after matching is **0.495**; shuffled-label AUC is **0.501**.

Although the ML-minus-traditional delta is positive, the residualized CWoLa high-minus-low excess CI includes zero, so this is not counted as a stable positive current signal.

| method                       |   high_minus_low_excess |   high_minus_low_ci_low |   high_minus_low_ci_high |      auc |   auc_ci_low |   auc_ci_high |       ap |      ece |   ml_minus_traditional_delta |   ml_minus_traditional_ci_low |   ml_minus_traditional_ci_high |
|:-----------------------------|------------------------:|------------------------:|-------------------------:|---------:|-------------:|--------------:|---------:|---------:|-----------------------------:|------------------------------:|-------------------------------:|
| traditional_matched_stratum  |            -0.0232993   |             -0.219126   |              0.0560026   | 0.449608 |    0.0271132 |      0.635082 | 0.625558 | 0.180762 |                  nan         |                   nan         |                    nan         |
| residualized_cwola_rf        |             0.00138045  |             -0.177607   |              0.0776094   | 0.526426 |    0.0860533 |      0.704365 | 0.644351 | 0.149514 |                    0.0246797 |                     0.0163364 |                      0.0454939 |
| nuisance_only_after_matching |            -0.000348025 |             -0.00331974 |              0.000948231 | 0.49524  |    0.454655  |      0.516429 | 0.643833 | 0.142965 |                  nan         |                   nan         |                    nan         |
| shuffled_label_rf            |             1.49257e-05 |             -0.00304769 |              0.0016997   | 0.500687 |    0.490984  |      0.512237 | 0.655237 | 0.143848 |                  nan         |                   nan         |                    nan         |

Held-out family details:

| fold             | method                       |   high_minus_low_excess |      auc |       ap |       ece |   ml_minus_traditional_delta |   ml_minus_traditional_ci_low |   ml_minus_traditional_ci_high |   n_scored_pulses |
|:-----------------|:-----------------------------|------------------------:|---------:|---------:|----------:|-----------------------------:|------------------------------:|-------------------------------:|------------------:|
| holdout_family_B | traditional_matched_stratum  |             0           | 0.5      | 0.671081 | 0.171081  |                  nan         |                   nan         |                    nan         |              6947 |
| holdout_family_B | residualized_cwola_rf        |             0.020692    | 0.59462  | 0.73217  | 0.167445  |                    0.020692  |                     0.0154477 |                      0.0261029 |              6947 |
| holdout_family_B | nuisance_only_after_matching |             0           | 0.5      | 0.671081 | 0.171081  |                  nan         |                   nan         |                    nan         |              6947 |
| holdout_family_B | shuffled_label_rf            |             6.91414e-05 | 0.499082 | 0.6787   | 0.17209   |                  nan         |                   nan         |                    nan         |              6947 |
| holdout_family_A | traditional_matched_stratum  |             0           | 0.5      | 0.5      | 0.231179  |                  nan         |                   nan         |                    nan         |              1334 |
| holdout_family_A | residualized_cwola_rf        |             0.0350326   | 0.609533 | 0.601143 | 0.216689  |                    0.0350326 |                     0.0315401 |                      0.0427034 |              1334 |
| holdout_family_A | nuisance_only_after_matching |             0           | 0.5      | 0.5      | 0.0131383 |                  nan         |                   nan         |                    nan         |              1334 |
| holdout_family_A | shuffled_label_rf            |             0.00219767  | 0.519153 | 0.516287 | 0.0076022 |                  nan         |                   nan         |                    nan         |              1334 |

## Leakage checks

No leakage check flagged. Train/test runs and events are disjoint, forbidden identifiers are excluded from current models, shuffled-label transfer is near chance, nuisance-only AUC is below the preregistered flag threshold, and residualized CWoLa AUC is not suspiciously close to one.

## Interpretation

The matched null is not exactly zero, but residualized CWoLa does not show a stable useful gain over the frozen nuisance-stratum table. The remaining current information is compatible with small unmatched waveform-shape differences rather than a robust leakage-free weak-supervision signal.

## Artifacts

`reproduction_match_table.csv`, `s10_reproduction_downstream_by_group.csv`, `matched_stratum_population.csv`, `nuisance_balance_table.csv`, `heldout_family_metrics.csv`, `pooled_run_bootstrap_metrics.csv`, `heldout_matched_scores_by_pulse.csv`, `leakage_checks.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.

Runtime: 110.1 s.
