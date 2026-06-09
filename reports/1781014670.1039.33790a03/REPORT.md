# Study report: S18e - A-stack core-width estimator standardization

- **Ticket:** `1781014670.1039.33790a03`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18e_1781014670_1039_33790a03_core_width_estimators.py --config configs/s18e_1781014670_1039_33790a03.json`

## Question

Question: can the A-stack timing note replace the low-stat binned Gaussian core sigma with a preregistered unbinned robust core estimator that is stable by run? Expected information gain: rerun A1-A3 Sample III/IV with Student-t, MAD/IQR, percentile-68, and trimmed-normal estimators as primary/secondary metrics, then propose a single standard estimator and tolerance table for future A-stack tickets.

## Reproduction first

The historical Sample IV A1-A3 number was reproduced from raw `HRDv` before changing the estimator:

| quantity                  |   expected |   reproduced |       delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |  127       |    127       | 0           |       0     | True   |
| sample_iv_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

The reproduced central definition is `n=127`, percentile-68 width `1.794 ns`, and binned Gaussian core sigma `1.992 ns` in the +/-2.5 ns fit window.

## Methods

Traditional is CFD20 with linear interpolation and an ordinary least-squares polynomial in `log(A1)`, `log(A3)`, their squares, and interaction. Each analysis run is held out; training uses calibration runs plus the other analysis runs in the same sample.

ML is a standardized ridge residual corrector with log amplitude, log-amplitude difference, peak sample, log area, and tail fraction. Alpha is selected by run-group CV inside the training pool. The model excludes run id, event id, raw residual, and timing columns.

Primary estimator: unbinned percentile-68 half width after median centering. Secondary estimators: MAD sigma, IQR sigma, 10% each-tail trimmed-normal sigma, and Student-t fitted central 68% half width.

## Head-to-head

| sample     |   traditional_percentile68_ns | traditional_ci   |   ml_percentile68_ns | ml_ci          |
|:-----------|------------------------------:|:-----------------|---------------------:|:---------------|
| sample_iii |                       1.39426 | [1.331, 1.485]   |              1.46123 | [1.410, 1.513] |
| sample_iv  |                       1.63748 | [1.311, 1.719]   |              1.38361 | [1.085, 1.491] |

Paired run-bootstrap ML-minus-traditional deltas on the primary estimator:

| sample     | comparison           | metric          |   ci_low_ns |   ci_high_ns |   p_value |
|:-----------|:---------------------|:----------------|------------:|-------------:|----------:|
| sample_iii | ml_minus_traditional | percentile68_ns |  0.00431304 |    0.114874  |     0.03  |
| sample_iv  | ml_minus_traditional | percentile68_ns | -0.443657   |   -0.0978649 |     0.009 |

ML is not adopted as the standard estimator path. It is worse on Sample III, and although it is significantly narrower on Sample IV, that is the "too good" case: the leakage audit has a Sample IV shuffled-target control flag, so the ML gain is treated as an analysis clue rather than a tolerance-table basis.

## Estimator comparison

| sample     | method      |   n_pairs |   n_runs |   percentile68_ns |   percentile68_ns_ci_low |   percentile68_ns_ci_high |   mad_sigma_ns |   iqr_sigma_ns |   trimmed_normal_sigma_ns |   student_t_width68_ns |   student_t_df |   gaussian_core_sigma_ns |   gaussian_core_chi2_ndf |   full_rms_ns |
|:-----------|:------------|----------:|---------:|------------------:|-------------------------:|--------------------------:|---------------:|---------------:|--------------------------:|-----------------------:|---------------:|-------------------------:|-------------------------:|--------------:|
| sample_iii | traditional |      2514 |       14 |           1.39426 |                  1.33142 |                   1.48542 |        1.45084 |        1.44712 |                   1.42632 |                1.32315 |        7.10527 |                  1.43569 |                  1.24916 |       3.27104 |
| sample_iii | ml          |      2514 |       14 |           1.46123 |                  1.40996 |                   1.51285 |        1.49191 |        1.49299 |                   1.47805 |                1.37865 |        6.97826 |                  1.5324  |                  1.10996 |       3.24543 |
| sample_iv  | traditional |       127 |        7 |           1.63748 |                  1.31102 |                   1.7186  |        1.68642 |        1.63716 |                   1.63277 |                1.49143 |      200       |                  2.00185 |                  1.36144 |       1.49883 |
| sample_iv  | ml          |       127 |        7 |           1.38361 |                  1.08466 |                   1.49094 |        1.35107 |        1.31986 |                   1.35929 |                1.23859 |      200       |                  1.73415 |                  1.23022 |       1.24315 |

The binned Gaussian is visibly less suitable as the standard low-stat metric: it depends on histogram binning/windowing and gives unstable chi2/ndf in Sample IV. The unbinned percentile-68 width is closest to the existing robust-width definition, is defined for every held-out run, and has transparent bootstrap coverage. MAD and IQR should remain secondary because they agree directionally but can overreact to the very small per-run Sample IV counts. Student-t is useful as a tail diagnostic, but its degrees of freedom fluctuate on sparse runs.

## Tolerance table

| sample     | standard_estimator   |   reference_traditional_width_ns |   bootstrap_ci_low_ns |   bootstrap_ci_high_ns |   run_to_run_mad_ns |   recommended_tolerance_ns |   accept_low_ns |   accept_high_ns | notes                                                                         |
|:-----------|:---------------------|---------------------------------:|----------------------:|-----------------------:|--------------------:|---------------------------:|----------------:|-----------------:|:------------------------------------------------------------------------------|
| sample_iii | percentile68_ns      |                          1.39426 |               1.33142 |                1.48542 |            0.212344 |                   0.212344 |         1.18192 |          1.6066  | Use on run-held-out A1-A3 residuals; quote MAD/IQR as secondary cross-checks. |
| sample_iv  | percentile68_ns      |                          1.63748 |               1.31102 |                1.7186  |            0.164673 |                   0.203791 |         1.43369 |          1.84127 | Use on run-held-out A1-A3 residuals; quote MAD/IQR as secondary cross-checks. |

Recommended standard for future A-stack tickets: **percentile68_ns** on run-held-out A1-A3 residuals, quoted with a run bootstrap CI. The tolerance is the larger of 0.05 ns, the CI half-width, and run-to-run MAD of the per-run traditional widths.

## Run stability

| sample     |   run |   n_pairs |   traditional_percentile68_ns |   traditional_mad_sigma_ns |   traditional_iqr_sigma_ns |   traditional_trimmed_normal_sigma_ns |   traditional_student_t_width68_ns |   ml_percentile68_ns |
|:-----------|------:|----------:|------------------------------:|---------------------------:|---------------------------:|--------------------------------------:|-----------------------------------:|---------------------:|
| sample_iii |    44 |        69 |                      1.61319  |                   1.77747  |                   1.80928  |                              1.71581  |                            1.58114 |             1.52017  |
| sample_iii |    45 |       672 |                      1.35638  |                   1.47827  |                   1.47479  |                              1.40827  |                            1.31638 |             1.47853  |
| sample_iii |    46 |         9 |                      1.1446   |                   1.59856  |                   1.39018  |                              1.38661  |                            1.17061 |             1.5456   |
| sample_iii |    47 |       103 |                      1.49943  |                   1.36363  |                   1.54068  |                              1.52066  |                            1.46653 |             1.45402  |
| sample_iii |    48 |       510 |                      1.50908  |                   1.51036  |                   1.54305  |                              1.51297  |                            1.39534 |             1.50413  |
| sample_iii |    49 |       489 |                      1.38912  |                   1.42146  |                   1.45942  |                              1.44054  |                            1.31676 |             1.4049   |
| sample_iii |    50 |        60 |                      1.29752  |                   1.46527  |                   1.37032  |                              1.38289  |                            1.18196 |             1.39159  |
| sample_iii |    51 |         7 |                      1.14392  |                   1.53161  |                   1.38718  |                              1.44838  |                            1.11989 |             1.11097  |
| sample_iii |    52 |         6 |                      1.16718  |                   1.48174  |                   1.11683  |                              1.28401  |                            1.21676 |             1.14124  |
| sample_iii |    53 |         4 |                      0.534927 |                   0.317005 |                   0.437141 |                            nan        |                          nan       |             1.18462  |
| sample_iii |    54 |         5 |                      0.886941 |                   0.992738 |                   0.638635 |                              0.683617 |                            1.11162 |             2.9245   |
| sample_iii |    55 |         6 |                      0.961847 |                   1.22684  |                   1.039    |                              1.10347  |                            1.00993 |             0.768666 |
| sample_iii |    56 |        91 |                      1.39725  |                   1.47656  |                   1.4013   |                              1.4047   |                            1.34969 |             1.5234   |
| sample_iii |    57 |       483 |                      1.27745  |                   1.32036  |                   1.32453  |                              1.31263  |                            1.27359 |             1.36444  |
| sample_iv  |    58 |        25 |                      1.26469  |                   1.55621  |                   1.62873  |                              1.39161  |                            1.3276  |             0.975205 |
| sample_iv  |    59 |        11 |                      1.17777  |                   1.02527  |                   1.30484  |                              1.42709  |                            1.13209 |             0.774135 |
| sample_iv  |    60 |        11 |                      1.09992  |                   1.57021  |                   1.23593  |                              1.40441  |                            1.10174 |             0.733032 |
| sample_iv  |    61 |        18 |                      1.61324  |                   1.6952   |                   1.682    |                              1.7748   |                            1.68184 |             1.16493  |
| sample_iv  |    62 |         7 |                      1.15362  |                   0.793369 |                   1.02694  |                              1.33386  |                            1.48161 |             1.04451  |
| sample_iv  |    63 |        28 |                      1.35193  |                   1.76191  |                   1.76117  |                              1.63826  |                            1.38789 |             1.25569  |
| sample_iv  |    65 |        27 |                      1.82054  |                   1.97926  |                   1.78521  |                              1.8738   |                            1.66829 |             1.64516  |

## Leakage checks

Leakage flags: **2**. Flagged row-split advantage means row-level validation is misleading; the Sample IV shuffled-target flag is why the narrower ML result is not used to define the standard tolerance.

| sample     | check                               | value                  | flag   |
|:-----------|:------------------------------------|:-----------------------|:-------|
| sample_iii | forbidden_feature_overlap           |                        | False  |
| sample_iii | row_split_advantage_rmse_ns         | 0.7143084866988858     | True   |
| sample_iii | group_split_r2_mean                 | 0.09089135500224747    | False  |
| sample_iii | random_row_split_r2                 | 0.12228598119294276    | False  |
| sample_iii | shuffled_target_r2                  | -0.0012680374162532537 | False  |
| sample_iii | ml_width_minus_traditional_width_ns | 0.06697226883727891    | False  |
| sample_iv  | forbidden_feature_overlap           |                        | False  |
| sample_iv  | row_split_advantage_rmse_ns         | -0.09298365240646156   | False  |
| sample_iv  | group_split_r2_mean                 | 0.21194514012545143    | False  |
| sample_iv  | random_row_split_r2                 | 0.06754798043065513    | False  |
| sample_iv  | shuffled_target_r2                  | 0.1076604385522908     | True   |
| sample_iv  | ml_width_minus_traditional_width_ns | -0.2538733491752623    | False  |

## Conclusion

Replace the low-stat binned Gaussian core sigma with percentile-68 as the A-stack primary core-width estimator. For this run-held-out rerun, the traditional percentile-68 width is `1.394 ns` for Sample III and `1.637 ns` for Sample IV. ML is inconsistent across samples and the Sample IV improvement trips a shuffled-target control, so it is not adopted for standards. Keep MAD, IQR, trimmed-normal, and Student-t in the tolerance table as diagnostics, not primary acceptance metrics.

Queued follow-ups:
- S18f: freeze the percentile-68 tolerance table and rerun S18/S18b/S18c/S18d reports with the same estimator columns; expected information gain is a single comparable A-stack timing ledger.
- S18g: stress-test percentile-68 against alternate CFD fractions and A1/A3 amplitude cuts; expected information gain is deciding whether the standard estimator or the pulse-selection gate dominates run-to-run width changes.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_deltas.csv`, `run_stability_table.csv`, `tolerance_table.csv`, `heldout_pair_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
