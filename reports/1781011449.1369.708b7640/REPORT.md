# S02d: anomaly-taxonomy timing-tail closure

**Ticket:** `1781011449.1369.708b7640`

## Reproduction first
Raw B-stack ROOT files were scanned before any modeling. The S00/S02 selected-pulse gates all reproduced exactly.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Split and target
Training runs were all configured B-stack runs except held-out runs `42, 57, 64, 65`. Timing used downstream staves `B4, B6, B8` with CFD20 plus a train-run amplitude-bin timewalk correction. The residual-tail threshold was the train-run 95th percentile of absolute corrected pair residuals: `4.0076 ns`.

## Traditional Closure
The traditional audit applied fixed P09a anomaly-class exclusions on held-out runs and measured tail rate, full RMS, q95 absolute residual, charge drift, and pair-composition drift.

| action                                      |   n_pairs |   tail_rate |   full_rms_ns |   q95_abs_ns |   kept_pair_fraction |   median_log_amp_delta |   max_pair_composition_drift |
|:--------------------------------------------|----------:|------------:|--------------:|-------------:|---------------------:|-----------------------:|-----------------------------:|
| baseline                                    |      2178 |   0.0486685 |       4.26453 |      3.9692  |             1        |            0           |                  0           |
| exclude_taxon_baseline_excursion            |      2172 |   0.0488029 |       4.26663 |      3.97068 |             0.997245 |           -0.000143809 |                  0.000181372 |
| exclude_taxon_dropout                       |      2178 |   0.0486685 |       4.26453 |      3.9692  |             1        |            0           |                  0           |
| exclude_taxon_novel_broad_template_mismatch |      2177 |   0.0482315 |       4.22731 |      3.95737 |             0.999541 |           -4.79317e-05 |                  0.000183275 |
| exclude_taxon_novel_delayed_peak            |      1833 |   0.0507365 |       3.55403 |      4.02299 |             0.841598 |            0.000527111 |                  0.00423142  |
| exclude_taxon_novel_early_pretrigger        |      2123 |   0.0485163 |       4.23814 |      3.93409 |             0.974747 |            0.00540167  |                  0.00261922  |
| exclude_taxon_pileup_or_long_tail           |      2132 |   0.0492495 |       4.30107 |      3.97883 |             0.97888  |           -0.00470843  |                  0.00311748  |
| exclude_ml_high_risk                        |      1663 |   0.0282622 |       2.28846 |      3.55741 |             0.763545 |            0.0442079   |                  0.0227815   |

Best class exclusion by tail rate was `exclude_taxon_novel_broad_template_mismatch`: tail rate `0.0482` vs baseline `0.0487`, with kept-pair fraction `1.000`.

## ML Classifier
The ML method trained a run-heldout RandomForest tail classifier from P09a scores, P09a taxa, and train-fit PCA waveform latents. It used no run id, event id, or stave id features.

| split                          |    n |   positive_rate |   average_precision |   roc_auc | selection             |   n_selected |   selected_fraction |   precision |   baseline_tail_rate |
|:-------------------------------|-----:|----------------:|--------------------:|----------:|:----------------------|-------------:|--------------------:|------------:|---------------------:|
| heldout_fixed_threshold_scores | 6187 |       0.0341038 |            0.103536 |  0.701449 | fixed_train_threshold |          726 |            0.117343 |    0.104683 |            0.0341038 |
| heldout_top_decile_scores      | 6187 |       0.0341038 |            0.103536 |  0.701449 | top_decile_per_run    |          620 |            0.10021  |    0.106452 |            0.0341038 |

Fixed-threshold ML exclusion changed held-out tail rate from `0.0487` to `0.0283` while keeping `0.764` of pairs. Fixed-threshold pulse precision was `0.1047`.

## Held-Out Bootstrap CIs
CIs are nonparametric bootstraps over held-out runs.

| action                                      | metric             |    ci_low |   ci_high |
|:--------------------------------------------|:-------------------|----------:|----------:|
| baseline                                    | tail_rate          | 0.0420757 | 0.0529876 |
| baseline                                    | full_rms_ns        | 2.35803   | 4.97801   |
| baseline                                    | q95_abs_ns         | 3.80041   | 4.11315   |
| baseline                                    | sigma68_ns         | 1.98265   | 2.06891   |
| baseline                                    | kept_pair_fraction | 1         | 1         |
| exclude_taxon_novel_broad_template_mismatch | tail_rate          | 0.0420757 | 0.0521862 |
| exclude_taxon_novel_broad_template_mismatch | full_rms_ns        | 2.35803   | 4.94163   |
| exclude_taxon_novel_broad_template_mismatch | q95_abs_ns         | 3.80041   | 4.10988   |
| exclude_taxon_novel_broad_template_mismatch | sigma68_ns         | 1.97073   | 2.06891   |
| exclude_taxon_novel_broad_template_mismatch | kept_pair_fraction | 0.999159  | 1         |
| exclude_ml_high_risk                        | tail_rate          | 0.0217519 | 0.0363322 |
| exclude_ml_high_risk                        | full_rms_ns        | 1.85405   | 2.58965   |
| exclude_ml_high_risk                        | q95_abs_ns         | 3.48907   | 3.70708   |
| exclude_ml_high_risk                        | sigma68_ns         | 1.83142   | 1.88725   |
| exclude_ml_high_risk                        | kept_pair_fraction | 0.731058  | 0.830295  |

## Leakage Checks
| check                                        |     value | pass   | note                                          |
|:---------------------------------------------|----------:|:-------|:----------------------------------------------|
| train_heldout_run_overlap                    | 0         | True   | run-disjoint split                            |
| model_features_include_run_event_or_stave_id | 0         | True   | none                                          |
| rounded_waveform_hash_overlap_train_heldout  | 0         | True   | normalized waveforms rounded to 1e-3          |
| stave_only_proxy_average_precision           | 0.0465062 | True   | proxy should underperform full no-id model    |
| suspicious_result_triggered_extra_checks     | 0         | True   | triggered if precision >0.90 or enrichment >5 |

## Verdict
P09a anomaly taxa are useful diagnostics for timing tails, but no single class closes the tail without also changing sample composition. The ML risk flag gives a stronger tail-enriched selection than deterministic class cuts, so the next step should validate whether those high-risk pulses share a physical waveform failure mode rather than using the classifier as a production cut.

## Provenance
Runtime was 339.8 s on `billy`. `manifest.json` records input and output hashes.
