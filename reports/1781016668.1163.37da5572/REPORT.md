# P03d: P01b epoch/domain score as timing nuisance diagnostic

**Ticket:** 1781016668.1163.37da5572

## Raw-ROOT reproduction first

The S00 selected-pulse count gate was rerun from raw ROOT before fitting the domain score or timing models.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Split and score construction

The timing test is leave-one-run-out over runs `58, 59, 60, 61, 62, 63, 65`. For each fold, timing regressors, score residualization, and nuisance tests are fit without the held-out run. The P01b epoch score is a logistic sample-II probability from the P01b latent table plus pulse amplitude and stave; the classifier excludes the held-out run. The residualized score subtracts the component predictable from amplitude, peak sample, area/amplitude, and stave on timing-training rows.

## Held-out timing results

CIs are 95% run-block bootstrap intervals over the seven held-out runs.

| method                            |   sigma68_ns |   ci_low |   ci_high |   delta_vs_baseline_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:----------------------------------|-------------:|---------:|----------:|-----------------------:|---------------:|----------------:|-------------------:|
| ml_extra_trees_no_score           |      1.89668 |  1.75806 |   2.09388 |            -0.18452    |     -0.252575  |     -0.124578   |              11460 |
| ml_extra_trees_score_residualized |      1.89794 |  1.76071 |   2.09547 |            -0.183265   |     -0.253571  |     -0.116189   |              11460 |
| ml_extra_trees_plus_score         |      1.90168 |  1.762   |   2.08246 |            -0.179525   |     -0.259503  |     -0.118769   |              11460 |
| traditional_score_residualized    |      2.07132 |  1.89126 |   2.32868 |            -0.00987806 |     -0.012354  |      0.00719772 |              11460 |
| traditional_plus_score            |      2.0715  |  1.89125 |   2.32899 |            -0.00969667 |     -0.0126136 |      0.00744565 |              11460 |
| traditional_no_score              |      2.0812  |  1.89052 |   2.33517 |             0          |      0         |      0          |              11460 |
| cfd20_reference                   |      3.15027 |  3.01892 |   3.27284 |             1.06907    |      0.697353  |      1.36599    |              11460 |

## Traditional method

The traditional correction is a ridge-regularized analytic timewalk model using the S03a `amp_rise_shape_by_stave` feature family on top of `cfd20`. Adding the raw P01b score changes the run-block sigma68 by `-0.0097 ns`; adding the residualized score changes it by `-0.0099 ns`.

| method                         |   sigma68_ns |   ci_low |   ci_high |
|:-------------------------------|-------------:|---------:|----------:|
| traditional_score_residualized |      2.07132 |  1.89126 |   2.32868 |
| traditional_plus_score         |      2.0715  |  1.89125 |   2.32899 |
| traditional_no_score           |      2.0812  |  1.89052 |   2.33517 |

## ML method

The ML correction is an ExtraTrees residual regressor on normalized 18-sample waveforms, amplitude/area terms, and stave one-hot, trained per fold on timing-training runs only. Adding the raw P01b score changes the run-block sigma68 by `0.0050 ns` versus ML no-score; adding the residualized score changes it by `0.0013 ns` versus ML no-score.

| method                            |   sigma68_ns |   ci_low |   ci_high |
|:----------------------------------|-------------:|---------:|----------:|
| ml_extra_trees_no_score           |      1.89668 |  1.75806 |   2.09388 |
| ml_extra_trees_score_residualized |      1.89794 |  1.76071 |   2.09547 |
| ml_extra_trees_plus_score         |      1.90168 |  1.762   |   2.08246 |

## Leakage and proxy checks

The score model excludes the held-out run in every fold. Event identifiers are not used as features. The proxy audit below checks whether the score is mostly recoverable from amplitude/topology controls; the residualized-score variants are included because those proxies explain a non-trivial part of the raw score.

|   heldout_run |   domain_train_balanced_accuracy |   proxy_train_balanced_accuracy |   timing_train_score_proxy_r2 |   heldout_score_proxy_r2 |   heldout_score_amp_corr |   heldout_resid_amp_corr |   heldout_score_std |   heldout_resid_std |
|--------------:|---------------------------------:|--------------------------------:|------------------------------:|-------------------------:|-------------------------:|-------------------------:|--------------------:|--------------------:|
|            58 |                           0.7681 |                          0.7441 |                      0.408536 |                 0.454439 |                -0.266858 |               0.130033   |            1.0422   |            0.725729 |
|            59 |                           0.7489 |                          0.7297 |                      0.36618  |                 0.292603 |                -0.325341 |               0.0751679  |            0.696074 |            0.585342 |
|            60 |                           0.7529 |                          0.7307 |                      0.367906 |                 0.363525 |                -0.382883 |              -0.106964   |            0.823638 |            0.657093 |
|            61 |                           0.7479 |                          0.7282 |                      0.474302 |                 0.446105 |                -0.474153 |              -0.00116128 |            0.704659 |            0.522653 |
|            62 |                           0.7462 |                          0.7216 |                      0.391047 |                 0.318227 |                -0.474744 |              -0.0504749  |            0.87803  |            0.724776 |
|            63 |                           0.7575 |                          0.7342 |                      0.370111 |                 0.415556 |                -0.3799   |               0.0488236  |            0.832067 |            0.630058 |
|            65 |                           0.7556 |                          0.7292 |                      0.448372 |                 0.529343 |                -0.444391 |               0.193207   |            0.949285 |            0.638167 |

## Verdict

The P01b epoch/domain score is mainly a nuisance diagnostic, not a timing improvement: traditional plus-score delta is -0.0097 ns and residualized-score delta is -0.0099 ns versus the traditional no-score baseline; ML plus-score delta is +0.0050 ns and residualized-score delta is +0.0013 ns versus ML no-score. Amplitude/topology proxies explain enough of the raw score that the residualized variants should be preferred for any downstream nuisance use.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p03d_1781016668_1163_37da5572_epoch_score_timing.py --config configs/p03d_1781016668_1163_37da5572_epoch_score_timing.yaml
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `method_summary.csv`, `fold_metrics.csv`, `domain_score_leakage_checks.csv`, and the figures.
