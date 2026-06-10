# P09c: independent waveform-gallery review against P09b

**Ticket:** `1781021714.1194.414e1474`

## Reproduction first
Raw B-stack ROOT files were scanned before loading the gallery or P09b adjudication labels, using the P09a/S00 gate: even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

## Blinded review
Two independent fixed morphology reviewers were run on waveform and detector-quality quantities only. The review table intentionally omits P09a taxon names from the review feature frame; P09b consensus labels are joined only after the independent labels are frozen for comparison.

External reviewer agreement was `0.961` with Cohen kappa `0.914` over 256 gallery rows. Held-out CIs resample runs `42, 57, 64, 65` with replacement.

## Main comparison to P09b
| reviewer_or_method           | selection_method   |   n |   exact_agreement |   target_precision |   target_recall |   target_f1 |   curated_precision |   curated_recall |   curated_f1 | target_f1_ci   | exact_agreement_ci   |
|:-----------------------------|:-------------------|----:|------------------:|-------------------:|----------------:|------------:|--------------------:|-----------------:|-------------:|:---------------|:---------------------|
| traditional_fixed_morphology | all_gallery        | 256 |          0.75     |           1        |        0.672131 |    0.803922 |            0.976378 |         1        |     0.988048 | [0.775, 0.843] | [0.703, 0.797]       |
| ml_loro_random_forest        | all_gallery        | 256 |          0.949219 |           0.933333 |        0.918033 |    0.92562  |            0.987805 |         0.979839 |     0.983806 | [0.879, 0.982] | [0.898, 0.988]       |

## Selection-method split
| reviewer_or_method           | selection_method            |   n |   exact_agreement |   target_precision |   target_recall |   target_f1 |   curated_precision |   curated_recall |   curated_f1 | target_f1_ci   |
|:-----------------------------|:----------------------------|----:|------------------:|-------------------:|----------------:|------------:|--------------------:|-----------------:|-------------:|:---------------|
| traditional_fixed_morphology | ml_pca_ae_isolation         | 128 |          0.90625  |           1        |        0.886364 |    0.939759 |            0.984127 |         1        |     0.992    | [0.884, 1]     |
| traditional_fixed_morphology | traditional_robust_template | 128 |          0.59375  |           1        |        0.117647 |    0.210526 |            0.96875  |         1        |     0.984127 | [0, 0.4]       |
| ml_loro_random_forest        | ml_pca_ae_isolation         | 128 |          0.945312 |           0.954545 |        0.954545 |    0.954545 |            0.98374  |         0.975806 |     0.979757 | [0.917, 1]     |
| ml_loro_random_forest        | traditional_robust_template | 128 |          0.953125 |           0.875    |        0.823529 |    0.848485 |            0.99187  |         0.983871 |     0.987854 | [0.778, 0.957] |

## Label counts
| label_source                       | label                         |   count |
|:-----------------------------------|:------------------------------|--------:|
| external_reviewer_alpha_label      | dropout                       |     187 |
| external_reviewer_alpha_label      | novel_delayed_peak            |      39 |
| external_reviewer_alpha_label      | baseline_excursion            |      27 |
| external_reviewer_alpha_label      | unassigned_common             |       2 |
| external_reviewer_alpha_label      | novel_broad_template_mismatch |       1 |
| external_reviewer_beta_label       | dropout                       |     178 |
| external_reviewer_beta_label       | novel_delayed_peak            |      39 |
| external_reviewer_beta_label       | baseline_excursion            |      35 |
| external_reviewer_beta_label       | unassigned_common             |       4 |
| traditional_fixed_morphology_label | dropout                       |     186 |
| traditional_fixed_morphology_label | novel_delayed_peak            |      39 |
| traditional_fixed_morphology_label | baseline_excursion            |      27 |
| traditional_fixed_morphology_label | novel_broad_template_mismatch |       2 |
| traditional_fixed_morphology_label | unassigned_common             |       2 |
| ml_loro_label                      | dropout                       |     126 |
| ml_loro_label                      | baseline_excursion            |      60 |
| ml_loro_label                      | novel_delayed_peak            |      41 |
| ml_loro_label                      | novel_early_pretrigger        |      14 |
| ml_loro_label                      | unassigned_common             |      10 |
| ml_loro_label                      | novel_broad_template_mismatch |       5 |
| p09b_consensus_label               | dropout                       |     126 |
| p09b_consensus_label               | baseline_excursion            |      60 |
| p09b_consensus_label               | novel_delayed_peak            |      42 |
| p09b_consensus_label               | novel_early_pretrigger        |      13 |
| p09b_consensus_label               | unassigned_common             |       8 |
| p09b_consensus_label               | novel_broad_template_mismatch |       6 |
| p09b_consensus_label               | pileup_or_long_tail           |       1 |

## Leakage checks
| check                                   |         value | pass   | note                                                                                               |
|:----------------------------------------|--------------:|:-------|:---------------------------------------------------------------------------------------------------|
| raw_reproduction_before_gallery         | 640737        | True   | script raises before gallery/P09b load if this fails                                               |
| p09a_taxon_absent_from_review_features  |      0        | True   | review and ML feature columns exclude P09a taxon names                                             |
| identifier_absent_from_ml_features      |      0        | True   | run/event/stave fields are split keys only                                                         |
| ml_train_test_run_overlap               |      0        | True   | leave-one-run-out folds train only on other gallery runs                                           |
| duplicate_gallery_waveform_hashes_1e3   |     12        | True   | duplicates are expected from cross-method gallery overlap; cross-run leakage is checked separately |
| cross_run_duplicate_gallery_hashes_1e3  |      0        | True   | same rounded waveform must not appear in more than one held-out run                                |
| ml_loro_train_test_hash_overlap_1e3     |      0        | True   | no rounded waveform hash crosses a leave-one-run-out ML fold                                       |
| traditional_exact_agreement_too_perfect |      0.75     | True   | near-perfect agreement would suggest copied P09b rubric                                            |
| ml_exact_agreement_too_perfect          |      0.949219 | True   | near-perfect LORO agreement would suggest leakage                                                  |

## Verdict
The independent traditional morphology review agrees with P09b on most curated-vs-common calls but is stricter on target taxa. The leave-one-run-out ML comparator is intentionally trained only on other held-out runs and does not reach perfect agreement, so the result looks like a reproducibility check rather than an identifier leak. The broad-template class remains weakly constrained by the gallery composition.

## Provenance
Runtime was 289.9 s on `billy`. `manifest.json` records input, code, and output hashes.
