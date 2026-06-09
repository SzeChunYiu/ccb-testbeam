# P09b: manual waveform-gallery adjudication

**Ticket:** `1781011449.1304.37c054cc`

## Reproduction first
The raw B-stack ROOT files under `data/root/root` were scanned before loading the gallery. The same S00/P09a gate was used: even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

## Adjudication
The P09a gallery has 256 held-out entries: 128 selected by the traditional ranker and 128 by the ML ranker. Two blinded fixed morphology rubrics reviewed only waveform-derived shape quantities plus detector-quality quantities needed to identify saturation, dropout, and baseline excursions; a third fixed resolver handled disagreements. This is an autonomous morphology adjudication, not an external human panel.

Inter-reviewer agreement over the full gallery was `0.832` with Cohen kappa `0.728`. Held-out CIs resample runs `42, 57, 64, 65` with replacement.

## Human-style precision by class
| selection_method            | claimed_class                 |   n_claimed |   adjudicated_precision |   reviewer_agreement | bootstrap_95ci   |
|:----------------------------|:------------------------------|------------:|------------------------:|---------------------:|:-----------------|
| ml_pca_ae_isolation         | curated_any                   |         128 |                0.96875  |             0.953125 | [0.945, 0.992]   |
| ml_pca_ae_isolation         | target_any                    |          98 |                0.418367 |             0.989796 | [0.355, 0.495]   |
| ml_pca_ae_isolation         | novel_early_pretrigger        |          56 |                0        |             1        | [0, 0]           |
| ml_pca_ae_isolation         | novel_delayed_peak            |          41 |                1        |             0.97561  | [1, 1]           |
| ml_pca_ae_isolation         | novel_broad_template_mismatch |           1 |                0        |             1        | [0, 0]           |
| traditional_robust_template | curated_any                   |         128 |                0.96875  |             0.710938 | [0.945, 0.992]   |
| traditional_robust_template | target_any                    |          67 |                0.19403  |             0.671642 | [0.134, 0.281]   |
| traditional_robust_template | novel_early_pretrigger        |          67 |                0.19403  |             0.671642 | [0.134, 0.281]   |
| traditional_robust_template | novel_delayed_peak            |           0 |              nan        |           nan        |                  |
| traditional_robust_template | novel_broad_template_mismatch |           0 |              nan        |           nan        |                  |

## Duplicate rates
| selection_method            |   n_rows |   duplicate_run_event_rate |   duplicate_run_stave_pulse_rate |   max_run_stave_share | duplicate_run_event_rate_ci   |
|:----------------------------|---------:|---------------------------:|---------------------------------:|----------------------:|:------------------------------|
| ml_pca_ae_isolation         |      128 |                   0.046875 |                          0       |             0.0625    | [0, 0.0938]                   |
| traditional_robust_template |      128 |                   0.015625 |                          0       |             0.0625    | [0, 0.0469]                   |
| cross_method_union          |      244 |                   0.132812 |                          0.09375 |             0.0655738 | [0.0938, 0.188]               |

## ML comparison
The P09b ML method fits a PCA latent space on non-held-out runs only, then assigns each gallery waveform a train-run nearest-neighbour taxonomy vote. The table also compares P09a traditional and ML anomaly scores against the consensus labels.

| label                 | score                  |    roc_auc |   average_precision |    spearman |
|:----------------------|:-----------------------|-----------:|--------------------:|------------:|
| consensus_curated_any | p09a_traditional_score |   0.768649 |            0.991353 |   0.161924  |
| consensus_curated_any | p09a_ml_score          |   0.5625   |            0.965754 |   0.0376709 |
| consensus_curated_any | knn_target_any         |   0.822581 |            0.988911 |   0.231869  |
| consensus_target_any  | p09a_traditional_score |   0.100378 |            0.13729  |  -0.589775  |
| consensus_target_any  | p09a_ml_score          |   0.308701 |            0.16945  |  -0.282325  |
| consensus_target_any  | knn_target_any         |   0.670828 |            0.326114 |   0.30066   |
| consensus_label       | knn_exact_label        | nan        |            0.425781 | nan         |

## Leakage checks
| check                                    |         value | pass   | note                                                   |
|:-----------------------------------------|--------------:|:-------|:-------------------------------------------------------|
| raw_reproduction_before_gallery          | 640737        | True   | script raises before gallery load if this fails        |
| train_heldout_run_overlap                |      0        | True   | PCA/kNN exemplars are train-run only                   |
| nearest_neighbor_uses_heldout_runs       |      0        | True   | all nearest exemplars must come from non-held-out runs |
| gallery_waveform_hash_seen_in_train      |      0        | True   | rounded normalized waveform hashes at 1e-3 precision   |
| knn_exact_consensus_accuracy_too_perfect |      0.425781 | True   | perfect kNN agreement would trigger a leakage concern  |
| review_consensus_equals_p09a_taxon_rate  |      0.417969 | True   | adjudication is not a verbatim copy of P09a labels     |

## Verdict
The adjudication supports the delayed-peak calls but rejects many early-pretrigger claims as baseline or other morphology once the waveform-only rubric is applied; broad-template-mismatch remains underpowered because the gallery contains only one claimed example. The ML-selected gallery has higher target-any adjudicated precision than the traditional-selected gallery, and the kNN exemplar labels are not perfect, so the result does not look like an identifier leak. Treat these labels as triage evidence until a real independent human review is available.

## Provenance
Runtime was 139.0 s on `billy`. `manifest.json` records input, code, and output hashes.
