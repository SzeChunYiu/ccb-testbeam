# S11e: blinded waveform audit of S11b high-current candidates

- **Ticket:** `1781017996.1381.12c419dc`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack ROOT runs 44-57; data-derived low-current synthetic overlays only; no detector Monte Carlo.
- **Split:** every scored event is predicted by templates/ML with its source run held out; CIs bootstrap held-out source runs within current group.

## Reproduction first

The S11b raw-ROOT S10c topology gate was rerun before the audit. Downstream selected-event fraction is 0.02312 at 2 nA and 0.03341 at 20 nA; all documented topology fractions pass.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Blinded candidate audit

The audit regenerates the S11b run-held-out scoring pass, then blinds event identity with a salted hash. The top 160 real high-current candidates are selected by a rank-average audit score that combines bounded two-pulse delta-SSE, residual-ranked secondary fraction, ML overlap score, and ML secondary-fraction rank. Thresholded candidate rates use the 95th percentile of low-current controls for each method.

## Candidate-rate CIs

| candidate_definition   |   low_rate |   high_rate |   high_minus_low |      ci_low |   ci_high | bootstrap_unit                  |   n_bootstrap |
|:-----------------------|-----------:|------------:|-----------------:|------------:|----------:|:--------------------------------|--------------:|
| traditional_candidate  | 0.0407169  |  0.0204751  |     -0.0202418   | -0.0452664  | 0.0090332 | source_run_within_current_group |           600 |
| ml_candidate           | 0.0349102  |  0.0574384  |      0.0225282   |  0.00835063 | 0.0334482 | source_run_within_current_group |           600 |
| joint_candidate        | 0.00266512 |  0.00262337 |     -4.17515e-05 | -0.00330184 | 0.0033487 | source_run_within_current_group |           600 |
| either_candidate       | 0.072962   |  0.0752901  |      0.00232808  | -0.0300107  | 0.0388152 | source_run_within_current_group |           600 |

The S10c global downstream high-minus-low excess reproduced here is 0.01029; the matched S10c excess is 0.02025. The joint traditional+ML candidate-rate excess is -0.00004 [-0.00330, 0.00335].

## Traditional method

The traditional audit score is a bounded one-pulse versus two-pulse template fit using low-current empirical templates. It ranks events by fractional delta-SSE and reports A2/(A1+A2) with the held-out source run excluded.

Traditional candidate-rate high-minus-low: **-0.02024** [-0.04527, 0.00903].

## ML method

The ML method is the compact S11b residual-shape random forest trained only on low-current raw waveform overlays. Feature columns are normalized samples and one-pulse residual summaries; run, current, event number, and blind id are not features.

ML candidate-rate high-minus-low: **0.02253** [0.00835, 0.03345].

## Inter-method agreement

| group     |     n |   traditional_rate |   ml_rate |   joint_rate |   jaccard |   matthews_phi |   top160_overlap |
|:----------|------:|-------------------:|----------:|-------------:|----------:|---------------:|-----------------:|
| high_20nA | 11525 |          0.0224729 | 0.106377  |   0.00225597 | 0.0178204 |    -0.00294637 |                7 |
| low_2nA   |  1092 |          0.0503663 | 0.0503663 |   0.00274725 | 0.0280374 |     0.00440081 |                9 |

## Leakage checks

| check                                              |    value | flag   | note                                                                                                           |
|:---------------------------------------------------|---------:|:-------|:---------------------------------------------------------------------------------------------------------------|
| s10c_gate_reproduced_first                         | 1        | False  | Raw-ROOT topology reproduction is executed before candidate scoring.                                           |
| heldout_run_excluded_from_template_and_ml_training | 1        | False  | S11b fold diagnostics record run-held-out scoring for every source run.                                        |
| identifier_features_excluded                       | 1        | False  | ML features are waveform and one-pulse residual summaries; run/current/event ids are added only after scoring. |
| synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics store synthetic training source runs.                                                         |
| mean_synthetic_holdout_auc                         | 0.926386 | False  | Near-perfect synthetic discrimination would trigger a leakage review.                                          |
| mean_shuffled_label_synthetic_auc                  | 0.502467 | False  | Shuffled synthetic labels should not transfer to held-out overlays.                                            |
| actual_current_auc_from_ml_overlap_score           | 0.59557  | False  | Flagged if the residual-shape ML score almost identifies current by itself.                                    |
| actual_current_auc_from_blinded_audit_score        | 0.485613 | False  | Flagged if the combined audit rank is too current-separable.                                                   |

## Waveform gallery

`waveform_gallery_top_candidates.png` shows the first 16 blinded high-current candidates. `top_high_current_candidates_blinded.csv` lists the top candidates by blind id and scores without event numbers.

## Conclusion

The blinded top-candidate audit finds a joint traditional+ML candidate-rate excess of -0.00004 [-0.00330, 0.00335], smaller than the matched S10c downstream excess of 0.02025. The traditional-only excess is -0.02024 and the ML-only excess is 0.02253; inter-method agreement is partial rather than redundant. Leakage sentinels do not flag source-run, identifier, shuffled-label, or too-good current separation, so the top candidates are plausible waveform-shape enrichments but not a full accounting of the S10 topology excess.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `candidate_rate_ci.csv`, `inter_method_agreement.csv`, `leakage_checks.csv`, `top_high_current_candidates_blinded.csv`, `audited_event_scores.csv`, and the waveform gallery are in this folder.
