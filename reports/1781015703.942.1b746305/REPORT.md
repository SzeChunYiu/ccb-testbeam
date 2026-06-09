# S18g: A-stack robust-width transfer to B-stack covariance

- **Ticket:** `1781015703.942.1b746305`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** `/home/billy/ccb-data/extracted/root/root`
- **Input checksums:** `input_sha256.csv`
- **No Monte Carlo:** raw HRD ROOT only

## Question

Can robust A-stack timing-width estimators predict or constrain B-stack correlated covariance without relying on low-statistics binned Gaussian core fits?

## Reproduction first

Raw ROOT anchors were rebuilt before the transfer test:

| quantity                             |     expected |   reproduced |       delta |   tolerance | pass   |
|:-------------------------------------|-------------:|-------------:|------------:|------------:|:-------|
| total_selected_b_pulses              | 640737       | 640737       | 0           |       0     | True   |
| sample_i_analysis_b_selected_pulses  | 252266       | 252266       | 0           |       0     | True   |
| sample_ii_analysis_b_selected_pulses | 125096       | 125096       | 0           |       0     | True   |
| sample_iv_a1_a3_pairs                |    127       |    127       | 0           |       0     | True   |
| sample_iv_a1_a3_robust_width_ns      |      1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |

## Methods

Runs are the split unit. Each B-stack analysis run is held out in turn; all B residual models and covariance predictors are fit without that run's B targets. Held-out A-stack robust summaries are allowed only as external same-run control observables.

Traditional: train-run B pair medians are the strong residual-width comparator. The A-stack transfer itself is a run-level Ridge covariance model that predicts held-out B sigma68 and correlated fraction from only the A percentile-68/MAD/IQR/trimmed/Student-t width prior set. A row-level A-prior Ridge timewalk correction is also reported as a diagnostic, but it is not the adopted traditional baseline because it broadens held-out residuals.

ML: ExtraTrees residual and covariance predictors using the same A prior set plus B amplitude and pulse-shape summaries. The model excludes run id, event id, raw times, raw residuals, and target residuals.

## Held-out residuals

| method                     |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                              |
|:---------------------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|------------------------:|:------------------------------------------------------------------|
| pair_median                |         65484 |       21 |      2.0905  |             1.81404 |              8.43445 |      20.6803  |              0.366419 |                228.535  | B pair train-median centering                                     |
| traditional_a_prior_ridge  |         65484 |       21 |      8.12426 |             7.53164 |              9.7074  |      11.647   |              0.397538 |                 63.0129 | Ridge timewalk residual model with A robust-width priors          |
| ml_extra_trees_a_prior     |         65484 |       21 |      1.40269 |             1.26061 |              1.78641 |       5.28666 |              0.286922 |                 12.4521 | ExtraTrees residual model with B shape plus A robust-width priors |
| ml_shuffled_target_control |         65484 |       21 |      4.24928 |             3.74616 |              7.5323  |      20.6996  |              0.36784  |                230.066  | ExtraTrees trained on shuffled targets                            |

Pair-median traditional sigma68 is `2.091` ns with CI `[1.814, 8.434]`. The row-level A-prior Ridge diagnostic is `8.124` ns and is not adopted. ML ExtraTrees is `1.403` ns with CI `[1.261, 1.786]`. ML-minus-pair-median is `-0.688` ns with paired run/bootstrap CI `[-7.413, -0.506]`; ML-minus-Ridge diagnostic is `-6.722` ns.

## Covariance transfer

Run-level covariance interval coverage:

| method                         | target              |   coverage |
|:-------------------------------|:--------------------|-----------:|
| ml_extratrees_covariance       | correlated_fraction |   0.35     |
| ml_extratrees_covariance       | sigma68             |   0.428571 |
| traditional_a_width_covariance | correlated_fraction |   0.65     |
| traditional_a_width_covariance | sigma68             |   0.761905 |

Per-held-out-run predictions are in `run_level_covariance_predictions.csv`. The A-width-only traditional covariance model is the direct transfer test; the ML covariance model adds B pulse summaries and is more flexible but not treated as independent evidence if leakage checks fail.

## Leakage checks

| check                              | value               | flag   |
|:-----------------------------------|:--------------------|:-------|
| forbidden_feature_overlap          |                     | False  |
| train_heldout_run_overlap          | 0.0                 | False  |
| ml_width_minus_shuffled_control_ns | -2.8465898996732424 | False  |
| random_row_split_r2                | 0.9261681971839637  | False  |
| group_cv_ridge_rmse_ns             | 11.248258268611302  | False  |

## Conclusion

The A-stack robust-width priors do not securely constrain B-stack covariance on their own. They can be included as weak external controls, but the held-out B residual width and correlated fraction remain dominated by B-stack pulse/topology information. The ML residual model improves the B residual width relative to the pair-median traditional comparator, but the covariance-transfer claim is bounded by the run-level interval coverage rather than by a point improvement.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `astack_run_summaries.csv`, `bstack_pair_table_preview.csv`, `heldout_pair_residuals.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `run_level_covariance_predictions.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
