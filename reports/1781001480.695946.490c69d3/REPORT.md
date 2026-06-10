# Study report: S18b - Sample IV A-stack broadening

- **Ticket:** `1781001480.695946.490c69d3`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python reports/1781001480.695946.490c69d3/s18b_astack_broadening.py --config reports/1781001480.695946.490c69d3/s18b_config.json`

## Question

Question: is the wider Sample IV A1-A3 timing core caused by low coincidence statistics, a run-period timing-scale shift, or a different residual timewalk regime? Expected information gain: separates statistical instability from a real period-dependent A-stack timing effect by run-level bootstrap, fit-window sensitivity, and leave-one-run-out stability on the Sample IV A-stack pairs.

## Reproduction first

The S18 Sample IV A1-A3 timing number was reproduced from raw `HRDv` before the new tests:

| quantity                  |   expected |   reproduced |       delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |  127       |    127       | 0           |       0     | True   |
| sample_iv_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

The reproduced central S18 definition is `n=127`, robust width `1.794 ns`, and Gaussian core sigma `1.992 ns` in the ±2.5 ns fit window. The new run-held-out traditional baseline below is a stronger period-polynomial model, so its width is intentionally different from the reproduced S18 number.

## Traditional method

The traditional method is CFD20 with linear sub-sample interpolation, followed by a low-order parametric timewalk model in `log(A1)`, `log(A3)`, their squares/interactions, and a Sample-IV period intercept. Each Sample IV analysis run is held out; the model is trained only on other runs.

Traditional held-out robust width: **1.471 ns** with run-bootstrap 95% CI **[1.289, 1.685] ns**. The Gaussian core is **1.638 ns**.

The run-median-removed diagnostic gives **1.466 ns**. That is not a deployable correction, but it tests whether broadening is dominated by run-period timing offsets.

## ML method

The ML method is a standardized ridge residual corrector over amplitude, peak sample, area, tail fraction, and a Sample-IV period indicator. It excludes run id, event id, raw residual, and timing columns. Alpha is selected by group CV inside the training pool, and every quoted Sample IV prediction is for a held-out run.

ML held-out robust width: **1.935 ns** with run-bootstrap 95% CI **[1.687, 2.322] ns**. Paired run-bootstrap ML minus traditional is **[0.106, 0.899] ns**, p=`0.006`.

## Broadening tests

- **Low coincidence statistics:** downsampling Sample III residuals to 127 pairs gives median width `1.384 ns` and 95% interval `[1.186, 1.605] ns`; probability of a width at least as large as the reproduced Sample IV width is `0.000`.
- **Run-period timing shift:** run-median removal changes the Sample IV width from `1.471` to `1.466 ns`.
- **Residual timewalk regime:** ML is significantly worse than the traditional model on the paired run bootstrap, so it provides no evidence for a better residual-timewalk correction.
- **Fit-window sensitivity:** see `fit_window_sensitivity.csv`; the Sample IV core remains fit-window sensitive at low count.

Interpretation: low statistics alone do not reproduce the original S18 width, but the stronger run-held-out traditional timewalk model reduces Sample IV to a width compatible with 127-pair Sample III downsampling. That points to residual calibration/timewalk definition plus low-stat instability, not a coherent run-period timing-scale shift.

## Run-held-out table

|   run |   n_pairs |   raw_median_ns |   traditional_median_ns |   traditional_robust_width_ns |   ml_median_ns |   ml_robust_width_ns |
|------:|----------:|----------------:|------------------------:|------------------------------:|---------------:|---------------------:|
|    58 |        25 |         3.96937 |               0.208913  |                       1.10886 |     -0.382108  |              1.69106 |
|    59 |        11 |         3.95141 |               0.0534092 |                       0.9676  |     -0.126771  |              1.40357 |
|    60 |        11 |         3.42727 |              -0.549696  |                       1.00739 |     -1.4153    |              1.2395  |
|    61 |        18 |         3.40079 |              -0.360718  |                       1.5673  |      0.110056  |              2.12613 |
|    62 |         7 |         2.85688 |              -0.580757  |                       1.05017 |      1.703     |              2.51522 |
|    63 |        28 |         4.1351  |               0.271225  |                       1.29843 |      0.0246261 |              1.68485 |
|    65 |        27 |         3.73243 |              -0.169821  |                       1.66062 |      0.311876  |              1.54986 |

## Leakage checks

Leakage flags: **1**. The flagged row-split advantage is a warning against row-level validation; the adopted result uses run-held-out prediction. See `leakage_checks.csv`.

| check                              | value                  | flag   |
|:-----------------------------------|:-----------------------|:-------|
| forbidden_feature_overlap          |                        | False  |
| row_split_advantage_rmse_ns        | 1.400996107182404      | True   |
| group_split_r2_mean                | -0.00975563240097339   | False  |
| random_row_split_r2                | -0.16454449401681215   | False  |
| shuffled_target_r2                 | -0.0056270386069581235 | False  |
| train_width_vs_heldout_ml_width_ns | -0.3856639260632313    | False  |

## Conclusion

The wider original Sample IV A1-A3 core is best treated as residual timewalk/calibration-definition sensitivity amplified by only 127 coincidences, not as evidence for a clean detector-wide timing-scale shift. The run-median diagnostic barely changes the robust width, and the ML residual model is worse than the traditional run-held-out baseline.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `run_heldout_summary.csv`, `fit_window_sensitivity.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
