# S03d: exact-fold S02/S03 baselines for P01e candidates

**Ticket:** 1781018587.1274.0a8b49e5

## Reproduction gate

Raw B-stack ROOT files were scanned before modelling. No Monte Carlo or prior derived tables were used.

| quantity                      |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses |         640737 |       640737 |       0 |           0 | True   |

## Exact-fold head-to-head

All rows use leave-one-run-out held-out candidate runs 42, 57, 64, and 65. Confidence intervals are 95% event-block bootstraps.

| method                |   sigma68_ns |   ci_low |   ci_high |   delta_vs_p01e_cfd20_ns |   n_events |   n_pair_residuals |
|:----------------------|-------------:|---------:|----------:|-------------------------:|-----------:|-------------------:|
| P01e CFD20            |      3.18845 |  3.04948 |   3.32902 |                 0        |        408 |               1224 |
| P01e hand-shape ridge |      1.96164 |  1.89454 |   2.0577  |                -1.22681  |        408 |               1224 |
| P01e AE latent ridge  |      1.98026 |  1.86067 |   2.0732  |                -1.20819  |        408 |               1224 |
| S02 global template   |      2.54562 |  2.53944 |   2.78944 |                -0.642835 |        408 |               1224 |
| S02 ML ridge          |      1.89673 |  1.8126  |   2.01332 |                -1.29172  |        408 |               1224 |
| S03 analytic timewalk |      1.49377 |  1.4393  |   1.55327 |                -1.69468  |        408 |               1224 |

Per held-out run:

|   heldout_run | method                |   sigma68_ns |   ci_low |   ci_high |   n_events |   n_pair_residuals |
|--------------:|:----------------------|-------------:|---------:|----------:|-----------:|-------------------:|
|            42 | P01e CFD20            |      3.30472 |  3.0537  |   3.54769 |         68 |                204 |
|            42 | P01e hand-shape ridge |      1.70376 |  1.53725 |   1.96359 |         68 |                204 |
|            42 | P01e AE latent ridge  |      1.76528 |  1.49289 |   2.0407  |         68 |                204 |
|            42 | S02 global template   |      2.04498 |  2.04498 |   2.27111 |         68 |                204 |
|            42 | S02 ML ridge          |      1.61782 |  1.44306 |   2.01183 |         68 |                204 |
|            42 | S03 analytic timewalk |      1.38533 |  1.32217 |   1.51075 |         68 |                204 |
|            57 | P01e CFD20            |      3.26476 |  2.82049 |   3.60131 |         64 |                192 |
|            57 | P01e hand-shape ridge |      2.01541 |  1.74989 |   2.31297 |         64 |                192 |
|            57 | P01e AE latent ridge  |      2.05461 |  1.79601 |   2.24858 |         64 |                192 |
|            57 | S02 global template   |      2.2948  |  2.05709 |   2.55709 |         64 |                192 |
|            57 | S02 ML ridge          |      1.89778 |  1.64261 |   2.18141 |         64 |                192 |
|            57 | S03 analytic timewalk |      1.40279 |  1.33014 |   1.53072 |         64 |                192 |
|            64 | P01e CFD20            |      3.1468  |  2.97196 |   3.3239  |        210 |                630 |
|            64 | P01e hand-shape ridge |      2.00434 |  1.82884 |   2.12486 |        210 |                630 |
|            64 | P01e AE latent ridge  |      1.99925 |  1.83857 |   2.13781 |        210 |                630 |
|            64 | S02 global template   |      2.78944 |  2.54007 |   2.79007 |        210 |                630 |
|            64 | S02 ML ridge          |      1.98226 |  1.85695 |   2.10305 |        210 |                630 |
|            64 | S03 analytic timewalk |      1.55188 |  1.47695 |   1.69111 |        210 |                630 |
|            65 | P01e CFD20            |      2.99339 |  2.66662 |   3.3887  |         66 |                198 |
|            65 | P01e hand-shape ridge |      1.95782 |  1.72672 |   2.18916 |         66 |                198 |
|            65 | P01e AE latent ridge  |      1.89921 |  1.60225 |   2.09717 |         66 |                198 |
|            65 | S02 global template   |      2.5815  |  2.3315  |   3.07005 |         66 |                198 |
|            65 | S02 ML ridge          |      1.82914 |  1.5513  |   2.08921 |         66 |                198 |
|            65 | S03 analytic timewalk |      1.51958 |  1.37761 |   1.63597 |         66 |                198 |

## Fold model choices

|   heldout_run |   s02_ml_alpha | s03_candidate   |   s03_alpha |
|--------------:|---------------:|:----------------|------------:|
|            42 |            100 | amp_only        |           0 |
|            57 |            100 | amp_only        |           0 |
|            64 |            100 | amp_only        |           0 |
|            65 |            100 | amp_only        |           0 |

## Leakage checks

| check                           |   value | pass_all   | detail                                                                                    |
|:--------------------------------|--------:|:-----------|:------------------------------------------------------------------------------------------|
| amplitude_bin_feature_used      |       0 | True       | strict features are waveform shape or AE latent plus log amplitude and stave one-hot only |
| feature_audit                   |       0 | True       | no run id, event id, event order, amplitude-bin id, or held-out target columns            |
| forbidden_feature_audit         |       0 | True       | no run id, event id, event order, held-out label, or other-stave timing feature           |
| template_train_excludes_heldout |       0 | True       | must be zero                                                                              |
| train_heldout_event_overlap     |       0 | True       | must be zero                                                                              |
| train_heldout_run_overlap       |       0 | True       | must be zero                                                                              |

Feature audit: S02/S03 feature matrices exclude run number, event identifier, event order, and held-out targets. Templates, Ridge fits, and analytic CV choices are trained only on runs other than the held-out run.

## Verdict

On the same P01e candidate folds, S03 analytic timewalk is `1.494 ns` versus `1.980 ns` for the P01e AE latent ridge. The earlier scope mismatch was material: S02/S03 remain competitive when rebuilt on the exact P01e folds, and S03 is the best pooled method in this table.

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03d_1781018587_1274_0a8b49e5_exact_fold_baselines.py --config configs/s03d_1781018587_1274_0a8b49e5_exact_fold_baselines.json
```

`result.json` verdict: `s03_analytic_best_on_exact_p01e_candidate_folds`.
