# P09d: enriched broad-template-mismatch gallery

**Ticket:** `1781021714.1215.508e2136`

## Reproduction first
The raw B-stack ROOT files under `data/root/root` were scanned before any selector or gallery load. The same S00/P09a gate was used: even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |
| P09b claimed broad examples | 1 | 1 | True |

## Methods
Held-out runs were `42, 57, 64, 65`. The traditional selector intentionally reserves slots for q_template-high/non-width-broad pulses and width-broad pulses in each run/stave. The ML selector is a run-heldout RandomForest source classifier using PCA waveform coordinates plus scalar pulse-shape quantities; it uses no run, event, stave, or source index features. Both selectors draw at most 10 candidates per held-out run/stave.

For gallery enrichment, q_template-only means train-run q_template RMSE above the frozen P09a q995 threshold while not width-broad, known, early, or delayed; the stricter P09a q999 template-only source is still tracked separately. A second ML fit removed q_template and width features as a leakage/tautology hunt because the source target is partly defined by those quantities. Full ML held-out AP was `1.000` and ROC-AUC `1.000`; the no-q/width AP was `0.916`.

## Enriched Gallery Precision
CIs are held-out-run bootstrap intervals over runs, not row bootstraps.

| method                      |   n_selected |   p09a_broad_fraction |   source_qtemplate_or_broad_fraction |   adjudicated_broad_precision |   adjudicated_curated_precision |   q_template_only_share |   p09a_strict_q_template_only_share |   broad_width_share |   duplicate_run_event_rate |   max_run_stave_share | adjudicated_broad_precision_ci   | p09a_broad_fraction_ci   | source_qtemplate_or_broad_fraction_ci   | q_template_only_share_ci   | p09a_strict_q_template_only_share_ci   | broad_width_share_ci   |
|:----------------------------|-------------:|----------------------:|-------------------------------------:|------------------------------:|--------------------------------:|------------------------:|------------------------------------:|--------------------:|---------------------------:|----------------------:|:---------------------------------|:-------------------------|:----------------------------------------|:---------------------------|:---------------------------------------|:-----------------------|
| ml_pca_shape_rf             |          160 |              0.30625  |                              0.30625 |                       0.5375  |                        1        |               0         |                           0         |            0.30625  |                     0.0125 |              0.0625   | [0.463, 0.662]                   | [0.275, 0.338]           | [0.275, 0.338]                          | [0, 0]                     | [0, 0]                                 | [0.275, 0.338]         |
| traditional_qtemplate_width |           49 |              0.979592 |                              1       |                       0.55102 |                        0.979592 |               0.0408163 |                           0.0204082 |            0.959184 |                     0      |              0.204082 | [0.25, 0.84]                     | [0.94, 1]                | [1, 1]                                  | [0, 0.12]                  | [0, 0.06]                              | [0.88, 1]              |

## Per-run Split
| method                      |   run |   n_selected |   p09a_broad_fraction |   adjudicated_broad_precision |   q_template_only_share |   p09a_strict_q_template_only_share |   broad_width_share |
|:----------------------------|------:|-------------:|----------------------:|------------------------------:|------------------------:|------------------------------------:|--------------------:|
| ml_pca_shape_rf             |    42 |           40 |              0.325    |                      0.45     |                0        |                           0         |            0.325    |
| ml_pca_shape_rf             |    57 |           40 |              0.275    |                      0.475    |                0        |                           0         |            0.275    |
| ml_pca_shape_rf             |    64 |           40 |              0.35     |                      0.725    |                0        |                           0         |            0.35     |
| ml_pca_shape_rf             |    65 |           40 |              0.275    |                      0.5      |                0        |                           0         |            0.275    |
| traditional_qtemplate_width |    42 |           13 |              0.923077 |                      0.307692 |                0.153846 |                           0.0769231 |            0.846154 |
| traditional_qtemplate_width |    57 |           11 |              1        |                      0.181818 |                0        |                           0         |            1        |
| traditional_qtemplate_width |    64 |           14 |              1        |                      0.928571 |                0        |                           0         |            1        |
| traditional_qtemplate_width |    65 |           11 |              1        |                      0.727273 |                0        |                           0         |            1        |

## ML Feature Importance
| feature         |   importance |
|:----------------|-------------:|
| width_half      |   0.359289   |
| post_peak_min   |   0.177621   |
| area_norm       |   0.166373   |
| pca_00          |   0.0910531  |
| late_fraction   |   0.0537905  |
| pca_02          |   0.0288716  |
| secondary_sep   |   0.0254127  |
| q_template_rmse |   0.0249538  |
| pca_03          |   0.0137365  |
| amplitude_adc   |   0.0127349  |
| pca_01          |   0.0112722  |
| early_fraction  |   0.00875297 |

## Leakage Checks
| check                               |          value | pass   | note                                                                                       |
|:------------------------------------|---------------:|:-------|:-------------------------------------------------------------------------------------------|
| raw_reproduction_before_selector    | 640737         | True   | script raises before selector work if this fails                                           |
| p09b_prior_broad_claim_count        |      1         | True   | reproduces the single-example bottleneck from P09b artifacts                               |
| train_heldout_run_overlap           |      0         | True   | models and templates train only on non-held-out runs                                       |
| gallery_rows_all_heldout            |      0         | True   | all gallery rows must come from held-out runs                                              |
| model_features_include_ids          |      0         | True   | run, event, stave, and source_index are absent from ML features                            |
| gallery_waveform_hash_seen_in_train |      0         | True   | rounded normalized waveform hashes at 1e-3 precision                                       |
| qwidth_ablation_ap_drop             |      0.0835425 | True   | large positive drop means strong result is q_template/width-driven, not identifier leakage |
| adjudication_equals_p09a_broad_rate |      0.248804  | True   | monitors whether fixed adjudication simply copies the P09a broad label                     |

## Verdict
The enriched gallery removes the P09b single-example bottleneck for `novel_broad_template_mismatch`: both run-heldout selectors return broad candidates across multiple runs and staves, and the traditional selector deliberately covers both q_template-high/non-width-broad and width-broad sources. The apparent ML strength is not treated as an independent discovery, because the leakage hunt shows that q_template/width carry much of the source label; it is still useful as a triage selector for reviewable waveform examples.

## Provenance
Runtime was 138.2 s on `billy`. `manifest.json` records input, code, and output hashes.
