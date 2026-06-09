# Study report: S18d - A-stack core fit stability

- **Ticket:** `1781008255.1472.46fb0e58`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT `HRDv`, runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python reports/1781008255.1472.46fb0e58/s18d_core_fit_stability.py --config reports/1781008255.1472.46fb0e58/s18d_config.json`

## Question

Question: how much of the Sample IV A1-A3 core-sigma excess is caused by binned Gaussian fit-window choices rather than residual timing physics? Expected information gain: compare binned Gaussian, unbinned Student-t, MAD/IQR, and trimmed-likelihood core estimators by run with bootstrap intervals on the raw ROOT A-stack pairs.

## Reproduction first

The historical S18 A1-A3 numbers were reproduced directly from the raw ROOT before the new estimator comparisons. The reproduced binned Gaussian definition uses CFD20, the historical calibration-run polynomial, 40 bins, and a ±2.5 ns fit window.

| quantity                  |   expected |   reproduced |        delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|-------------:|------------:|:-------|
| sample_iii_A1_A3_pairs    | 2514       |   2514       |  0           |       0     | True   |
| sample_iii_core_sigma_ns  |    1.45092 |      1.45092 | -2.79233e-07 |       0.001 | True   |
| sample_iv_A1_A3_pairs     |  127       |    127       |  0           |       0     | True   |
| sample_iv_robust_width_ns |    1.79363 |      1.79363 | -3.62232e-08 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 | -4.61618e-07 |       0.001 | True   |

The reproduced binned-Gaussian Sample IV minus Sample III core-sigma excess is **0.541 ns** (`1.992 - 1.451`).

## Traditional method

The strong traditional method is a CFD20 residual correction with a quadratic polynomial in `log(A1)`, `log(A3)`, their interaction, and a Sample-IV period intercept. Every quoted analysis row is predicted in a run-held-out fold.

Sample IV estimator results:

| sample    | method                             | estimator            |   n_pairs |   value_ns |   ci_low_ns |   ci_high_ns |
|:----------|:-----------------------------------|:---------------------|----------:|-----------:|------------:|-------------:|
| sample_iv | traditional_period_poly_runheldout | binned_gaussian      |       127 |    2.07667 |     1.42629 |      5       |
| sample_iv | traditional_period_poly_runheldout | student_t_df4_scale  |       127 |    1.23987 |     1.05844 |      1.36846 |
| sample_iv | traditional_period_poly_runheldout | mad_sigma            |       127 |    1.54139 |     1.233   |      1.83352 |
| sample_iv | traditional_period_poly_runheldout | iqr_sigma            |       127 |    1.58929 |     1.23378 |      1.85335 |
| sample_iv | traditional_period_poly_runheldout | trimmed_normal_sigma |       127 |    1.16754 |     1.00894 |      1.28142 |
| sample_iv | traditional_period_poly_runheldout | percentile_68_width  |       127 |    1.50587 |     1.29576 |      1.68315 |

## ML method

The ML method is a standardized ridge regressor over amplitude, peak-sample, area, tail-fraction, and a Sample-IV indicator. It excludes run id, event id, timing columns, and the residual target. Alpha is tuned with group-by-run CV inside each training pool, and every quoted row is predicted for a held-out run.

Sample IV estimator results:

| sample    | method                             | estimator            |   n_pairs |   value_ns |   ci_low_ns |   ci_high_ns |
|:----------|:-----------------------------------|:---------------------|----------:|-----------:|------------:|-------------:|
| sample_iv | ml_ridge_shape_features_runheldout | binned_gaussian      |       127 |    2.20356 |     1.58688 |      5       |
| sample_iv | ml_ridge_shape_features_runheldout | student_t_df4_scale  |       127 |    1.45013 |     1.32133 |      1.61207 |
| sample_iv | ml_ridge_shape_features_runheldout | mad_sigma            |       127 |    1.86073 |     1.53356 |      2.16971 |
| sample_iv | ml_ridge_shape_features_runheldout | iqr_sigma            |       127 |    1.78567 |     1.5131  |      2.12765 |
| sample_iv | ml_ridge_shape_features_runheldout | trimmed_normal_sigma |       127 |    1.39837 |     1.26612 |      1.54928 |
| sample_iv | ml_ridge_shape_features_runheldout | percentile_68_width  |       127 |    1.77162 |     1.45609 |      2.02773 |

## Fit-window versus unbinned estimators

Under the run-held-out traditional correction, the binned Gaussian excess is **0.637 ns**. The median unbinned/robust excess across Student-t, MAD, IQR, trimmed-normal, and percentile-68 estimators is **0.088 ns**. Relative to the reproduced historical binned excess, about **0.453 ns** of the Sample IV excess is attributable to the binned Gaussian/window definition plus the old low-stat calibration choice, not a stable residual-timing width.

| method                             | estimator            |   sample_iv_minus_iii_ns |   ci_low_ns |   ci_high_ns |
|:-----------------------------------|:---------------------|-------------------------:|------------:|-------------:|
| traditional_period_poly_runheldout | binned_gaussian      |                0.636887  |  -0.0258523 |     3.57031  |
| traditional_period_poly_runheldout | student_t_df4_scale  |                0.0779086 |  -0.06764   |     0.210042 |
| traditional_period_poly_runheldout | mad_sigma            |                0.0882896 |  -0.238765  |     0.421685 |
| traditional_period_poly_runheldout | iqr_sigma            |                0.141773  |  -0.194506  |     0.407597 |
| traditional_period_poly_runheldout | trimmed_normal_sigma |                0.065425  |  -0.0909046 |     0.186167 |
| traditional_period_poly_runheldout | percentile_68_width  |                0.11339   |  -0.141054  |     0.286637 |
| ml_ridge_shape_features_runheldout | binned_gaussian      |                0.722964  |   0.0742157 |     3.56772  |
| ml_ridge_shape_features_runheldout | student_t_df4_scale  |                0.259737  |   0.102388  |     0.414814 |
| ml_ridge_shape_features_runheldout | mad_sigma            |                0.379895  |   0.0565596 |     0.717861 |
| ml_ridge_shape_features_runheldout | iqr_sigma            |                0.305807  |   0.022473  |     0.686757 |
| ml_ridge_shape_features_runheldout | trimmed_normal_sigma |                0.270407  |   0.123334  |     0.430482 |
| ml_ridge_shape_features_runheldout | percentile_68_width  |                0.328656  |  -0.0379011 |     0.569178 |

The full fit-window scan is in `fit_window_sensitivity.csv`; per-run estimator values are in `run_estimator_summary.csv`.

## Run-level check

| sample    |   run | method                             |   n_pairs |   binned_gaussian_ns |   student_t_df4_scale_ns |   mad_sigma_ns |   iqr_sigma_ns |   trimmed_normal_sigma_ns |   percentile_68_width_ns |
|:----------|------:|:-----------------------------------|----------:|---------------------:|-------------------------:|---------------:|---------------:|--------------------------:|-------------------------:|
| sample_iv |    58 | traditional_period_poly_runheldout |        25 |              2.41708 |                 1.04179  |       1.31016  |       1.27655  |                  0.940748 |                 1.14818  |
| sample_iv |    59 | traditional_period_poly_runheldout |        11 |              3.54284 |                 0.920215 |       1.09892  |       1.20109  |                  0.841781 |                 0.954478 |
| sample_iv |    60 | traditional_period_poly_runheldout |        11 |              3.292   |                 0.906555 |       1.18448  |       1.19108  |                  0.835442 |                 1.02014  |
| sample_iv |    61 | traditional_period_poly_runheldout |        18 |              5       |                 1.4451   |       1.79815  |       1.81523  |                  1.23846  |                 1.5191   |
| sample_iv |    62 | traditional_period_poly_runheldout |         7 |              2.27595 |                 1.21632  |       1.00228  |       1.02072  |                  0.934165 |                 1.04896  |
| sample_iv |    63 | traditional_period_poly_runheldout |        28 |              2.49271 |                 1.17155  |       1.36354  |       1.41116  |                  1.13177  |                 1.29011  |
| sample_iv |    65 | traditional_period_poly_runheldout |        27 |              5       |                 1.40514  |       2.15764  |       1.97595  |                  1.32526  |                 1.63768  |
| sample_iv |    58 | ml_ridge_shape_features_runheldout |        25 |              5       |                 1.33288  |       1.53182  |       1.61594  |                  1.2481   |                 1.64331  |
| sample_iv |    59 | ml_ridge_shape_features_runheldout |        11 |              5       |                 0.997912 |       1.15237  |       1.42961  |                  0.893503 |                 1.04719  |
| sample_iv |    60 | ml_ridge_shape_features_runheldout |        11 |              3.34069 |                 1.05331  |       0.932702 |       0.900858 |                  1.10626  |                 1.25521  |
| sample_iv |    61 | ml_ridge_shape_features_runheldout |        18 |              5       |                 1.68288  |       2.26066  |       2.15988  |                  1.53797  |                 1.95306  |
| sample_iv |    62 | ml_ridge_shape_features_runheldout |         7 |              5       |                 2.00492  |       2.23123  |       2.72288  |                  1.74549  |                 2.10526  |
| sample_iv |    63 | ml_ridge_shape_features_runheldout |        28 |              5       |                 1.35572  |       1.48356  |       1.45253  |                  1.28894  |                 1.70164  |
| sample_iv |    65 | ml_ridge_shape_features_runheldout |        27 |              5       |                 1.39138  |       1.73295  |       1.74668  |                  1.31467  |                 1.38346  |

## Leakage checks

Leakage flags: **0**.

| check                                      | value                                                        | flag   |
|:-------------------------------------------|:-------------------------------------------------------------|:-------|
| forbidden_feature_overlap                  |                                                              | False  |
| heldout_run_overlap                        | none; each analysis run was excluded from its own train fold | False  |
| row_split_advantage_rmse_ns                | -0.43494160763198275                                         | False  |
| group_split_r2_mean                        | 0.05944239320776275                                          | False  |
| random_row_split_r2                        | 0.059373932836772836                                         | False  |
| shuffled_target_r2                         | -0.00042317475324016307                                      | False  |
| sample_iv_ml_minus_traditional_width_ci_ns | [-0.0586715, 0.622073], p=0.085                              | False  |

## Conclusion

The old Sample IV core-sigma excess is not stable under estimator changes. The reproduced binned Gaussian excess is larger than the held-out robust/unbinned excess, while the run-held-out traditional model gives smaller and more consistent Sample IV widths than the old one-run calibration. The residual timing physics signal that survives robust estimators is therefore at most a small, low-statistics Sample IV broadening; the binned Gaussian fit-window choice is a major contributor to the quoted core-sigma excess.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `core_estimator_metrics.csv`, `sample_iv_excess_by_estimator.csv`, `run_estimator_summary.csv`, `fit_window_sensitivity.csv`, `heldout_pair_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
