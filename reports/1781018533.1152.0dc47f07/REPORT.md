# S11d: S11c templates on real high-current candidate windows

- **Ticket:** `1781018533.1152.0dc47f07`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack ROOT runs 44-57; no detector Monte Carlo.
- **Split:** every event is scored by source run; low-current controls exclude their own run from training, and high-current runs use only low-current training.

## Reproduction first

The S10c topology gate was rerun from raw ROOT before S11c template scoring. Downstream selected-event fractions reproduce as 0.02312 at 2 nA and 0.03341 at 20 nA; all documented topology checks pass.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Traditional method

For each held-out run, S11c amplitude-binned/asymmetric templates are built from low-current training runs only. The fit scans timing and separation, allows separate primary/secondary template candidates, and reports both a fractional delta-SSE score and A2/(A1+A2).

S11c-template candidate-rate high-minus-low: **0.01046** [-0.00145, 0.02364]. Matched secondary-fraction high-minus-low: **-0.04149** [-0.08531, 0.00112].

## ML method

The ML comparator is a compact random-forest residual-shape classifier/regressor trained on low-current raw-pulse synthetic overlays. It uses normalized waveform samples plus one-pulse residual summaries, excluding identifiers, current labels, event numbers, and strata.

ML candidate-rate high-minus-low: **0.02417** [0.01729, 0.03023]. ML secondary-fraction high-minus-low: **0.00951** [0.00204, 0.01759].

## Candidate rates and stability

| candidate_definition   |   low_rate |   high_rate |   high_minus_low |       ci_low |    ci_high | bootstrap_unit                  |   n_bootstrap |
|:-----------------------|-----------:|------------:|-----------------:|-------------:|-----------:|:--------------------------------|--------------:|
| traditional_candidate  | 0.0342278  |  0.0446863  |        0.0104585 | -0.00145115  | 0.0236352  | source_run_within_current_group |           600 |
| ml_candidate           | 0.0363483  |  0.0605225  |        0.0241742 |  0.0172868   | 0.0302309  | source_run_within_current_group |           600 |
| joint_candidate        | 0.00113115 |  0.00313065 |        0.0019995 | -0.000311923 | 0.00486201 | source_run_within_current_group |           600 |
| either_candidate       | 0.0694449  |  0.102078   |        0.0326332 |  0.0204804   | 0.0422293  | source_run_within_current_group |           600 |

| sample           |   n |   traditional_candidate_rate |   ml_candidate_rate |   joint_candidate_rate |   trad_secondary_fraction_median |   trad_secondary_fraction_iqr |   trad_sep_sample_median |   ml_secondary_fraction_median |   ml_secondary_fraction_iqr |
|:-----------------|----:|-----------------------------:|--------------------:|-----------------------:|---------------------------------:|------------------------------:|-------------------------:|-------------------------------:|----------------------------:|
| top_high_current | 160 |                     0.3625   |            0.6      |             0.1375     |                         0.618734 |                      0.140401 |                      1.5 |                      0.120341  |                   0.145757  |
| low_controls     | 602 |                     0.051495 |            0.051495 |             0.00166113 |                         0.388366 |                      0.605035 |                      1   |                      0.0269977 |                   0.0831426 |

Joint traditional+ML candidate-rate high-minus-low is **0.00200** [-0.00031, 0.00486].

## Closure comparison

S11c injection closure remains the relevant benchmark: traditional S11c templates had 17.83 ns time RMS and AP 0.715, while the compact ML closure had 10.67 ns and AP 0.851. On real candidate windows there is no truth label, so the falsification target is stability under run-held-out controls and agreement with the ML diagnostic.

| group     |    n |   traditional_rate |   ml_rate |   joint_rate |   jaccard |   matthews_phi |   top_overlap |
|:----------|-----:|-------------------:|----------:|-------------:|----------:|---------------:|--------------:|
| high_20nA | 5462 |          0.0488832 | 0.0957525 |   0.00402783 | 0.0286458 |     -0.0102897 |             3 |
| low_2nA   |  602 |          0.051495  | 0.051495  |   0.00166113 | 0.0163934 |     -0.0202813 |             3 |

## Leakage checks

| check                                              |    value | flag   | note                                                                                                |
|:---------------------------------------------------|---------:|:-------|:----------------------------------------------------------------------------------------------------|
| s10c_gate_reproduced_first                         | 1        | False  | Raw-ROOT topology reproduction is required before candidate scoring.                                |
| heldout_run_excluded_from_template_and_ml_training | 1        | False  | Each source run is scored with low-current training runs excluding that source run when applicable. |
| identifier_features_excluded                       | 1        | False  | ML features exclude run, current, group, event number, candidate flag, and stratum labels.          |
| synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record synthetic training source runs.                                             |
| mean_synthetic_holdout_auc                         | 0.910763 | False  | Near-perfect synthetic discrimination triggers leakage review.                                      |
| mean_shuffled_label_synthetic_auc                  | 0.482722 | False  | Shuffled-label training should not classify held-out overlays.                                      |
| actual_current_auc_from_s11c_trad_score            | 0.434377 | False  | Flagged if S11c template score almost identifies beam current by itself.                            |
| actual_current_auc_from_ml_overlap_score           | 0.588694 | False  | Flagged if ML score almost identifies beam current by itself.                                       |

## Conclusion

S11c rich-template scoring does not produce a stable real high-current excess by itself: traditional candidate-rate high-minus-low is 0.01046 [-0.00145, 0.02364], while ML is 0.02417 [0.01729, 0.03023]. The joint excess is 0.00200 [-0.00031, 0.00486] against a matched S10c downstream excess of 0.02025. Leakage sentinels flag 0 checks.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `candidate_rate_ci.csv`, `method_delta_ci.csv`, `stability_summary.csv`, `inter_method_agreement.csv`, `leakage_checks.csv`, `event_scores.csv.gz`, template summaries, and two figures are in this folder.
