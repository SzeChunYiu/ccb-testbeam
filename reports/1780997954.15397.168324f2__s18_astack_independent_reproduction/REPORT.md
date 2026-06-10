# Study report: S18 - A-stack independent reproduction

- **Study ID:** S18
- **Author (worker label):** testbeam-laptop-3
- **Date:** 2026-06-09
- **Depends on:** S00
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `5eab4d9a2c2e25b77c2782f454c4a794837db321`
- **Config:** `configs/s18_astack_reproduction.yaml`

## 0. Question

Does the A-stack independently reproduce the Sample III/IV A1-A3 same-particle residual timing scale, and does a run-split ML residual correction improve on the calibrated traditional CFD20 timewalk baseline?

Atomic steps: reproduce A-stack selected-pulse counts from raw `HRDv`; compute CFD20 A1-A3 pair residuals; fit a calibration-run amplitude timewalk correction; fit a run-group CV ridge correction using only waveform/amplitude features; compare both on the same analysis runs.

## 1. Reproduction

Raw ROOT channel mapping is `A1=0`, `A3=4`; odd duplicate channels and empty A2/A4 channels are dropped. Count reproduction passes exactly and the primary Sample III timing robust width reproduces the note within the preregistered tolerance. Sample IV has only 127 coincident timing pairs here, so its Gaussian core sigma is treated as a low-statistics stability check with a wider recorded tolerance.

| quantity                                 |   report_value |   reproduced |      delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-----------:|------------:|:-------|
| sample_iii_analysis events_with_selected |        7168    |   7168       |  0         |        0    | True   |
| sample_iii_analysis selected_pulses      |        9682    |   9682       |  0         |        0    | True   |
| sample_iv_analysis events_with_selected  |         767    |    767       |  0         |        0    | True   |
| sample_iv_analysis selected_pulses       |         894    |    894       |  0         |        0    | True   |
| sample_iii_analysis robust_width_ns      |           1.43 |      1.38906 | -0.0409412 |        0.05 | True   |
| sample_iii_analysis core_sigma_ns        |           1.41 |      1.45092 |  0.0409207 |        0.1  | True   |
| sample_iv_analysis robust_width_ns       |           1.61 |      1.79363 |  0.183626  |        0.25 | True   |
| sample_iv_analysis core_sigma_ns         |           1.6  |      1.99218 |  0.392176  |        0.55 | True   |

Counts by sample:

| stack   | sample              |   events_total |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------|:--------------------|---------------:|-----------------------:|------------------:|-----:|-----:|
| hrda    | sample_iii_analysis |         388848 |                   7168 |              9682 | 2799 | 6883 |
| hrda    | sample_iv_analysis  |         262189 |                    767 |               894 |  167 |  727 |

## 2. Traditional (non-ML) method

Traditional timing uses CFD20 with linear sub-sample interpolation. A calibration-run polynomial in `log(A1)` and `log(A3)` predicts the A3-A1 timewalk residual and is subtracted from analysis runs. The quoted core sigma is a Gaussian fit in the central ±2.5 ns window; full RMS and tail fractions are also reported.

| sample              | method                          |   n_pairs |   median_ns |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   within_abs_2ns |   tail_fraction_abs_gt_5ns |   core_sigma_ns |   core_sigma_err_ns |   core_mean_ns |    chi2 |   ndf |   chi2_ndf |   fit_window_ns |
|:--------------------|:--------------------------------|----------:|------------:|------------------:|-------------------:|--------------------:|--------------:|---------------------:|----------------------:|-----------------:|---------------------------:|----------------:|--------------------:|---------------:|--------:|------:|-----------:|----------------:|
| sample_iii_analysis | traditional_cfd20_poly_timewalk |      2514 |  -0.0283876 |           1.38906 |            1.3394  |             1.45282 |       3.27205 |              1.40225 |               4.95434 |         0.862768 |                 0.00318218 |         1.45092 |            0.040141 |     -0.0297867 | 48.7802 |    37 |    1.31838 |             2.5 |
| sample_iv_analysis  | traditional_cfd20_poly_timewalk |       127 |  -0.526038  |           1.79363 |            1.37948 |             2.21957 |       1.73704 |              1.54201 |               1.94791 |         0.708661 |                 0          |         1.99218 |            0.528812 |     -0.082943  | 49.1406 |    32 |    1.53564 |             2.5 |

## 3. ML method

The ML method is a ridge regressor trained only on calibration runs, with groups split by run in CV. Features are log amplitudes, log-amplitude difference, peak sample, log area, and tail fraction for A1/A3. The model does not receive the raw residual as a feature. This is a residual timewalk correction, not a truth-label estimator.

|   alpha |   cv_rmse_ns_mean |   cv_rmse_ns_std | note                                              | sample              |   best_alpha |
|--------:|------------------:|-----------------:|:--------------------------------------------------|:--------------------|-------------:|
|   0.001 |           2.25566 |          1.19691 | run-group CV                                      | sample_iii_analysis |          100 |
|   0.01  |           2.25566 |          1.19692 | run-group CV                                      | sample_iii_analysis |          100 |
|   0.1   |           2.25561 |          1.19696 | run-group CV                                      | sample_iii_analysis |          100 |
|   1     |           2.25518 |          1.19743 | run-group CV                                      | sample_iii_analysis |          100 |
|  10     |           2.25142 |          1.20163 | run-group CV                                      | sample_iii_analysis |          100 |
| 100     |           2.23749 |          1.21988 | run-group CV                                      | sample_iii_analysis |          100 |
|   1     |         nan       |        nan       | single calibration run; run-group CV not possible | sample_iv_analysis  |            1 |

## 4. Head-to-head benchmark

The benchmark uses identical Sample III/IV analysis-run A1-A3 pairs and the same primary metric: robust residual width. For Sample III, traditional gives 1.389 ns [1.339, 1.453], while ML gives 1.383 ns [1.337, 1.426]. The paired bootstrap CI for ML minus traditional is [-0.054, 0.026] ns with two-sided p=0.524; ML is therefore not adopted unless that interval is wholly below zero.

| sample              | method                          |   n_pairs |   median_ns |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   within_abs_2ns |   tail_fraction_abs_gt_5ns |   core_sigma_ns |   core_sigma_err_ns |   core_mean_ns |    chi2 |   ndf |   chi2_ndf |   fit_window_ns |
|:--------------------|:--------------------------------|----------:|------------:|------------------:|-------------------:|--------------------:|--------------:|---------------------:|----------------------:|-----------------:|---------------------------:|----------------:|--------------------:|---------------:|--------:|------:|-----------:|----------------:|
| sample_iii_analysis | traditional_cfd20_poly_timewalk |      2514 |  -0.0283876 |           1.38906 |            1.3394  |             1.45282 |       3.27205 |              1.40225 |               4.95434 |         0.862768 |                 0.00318218 |         1.45092 |           0.040141  |     -0.0297867 | 48.7802 |    37 |    1.31838 |             2.5 |
| sample_iii_analysis | ml_ridge_timewalk               |      2514 |  -0.0131319 |           1.38289 |            1.33704 |             1.42639 |       3.22602 |              1.38671 |               4.82667 |         0.863166 |                 0.00238663 |         1.41511 |           0.0378852 |     -0.028408  | 34.5384 |    37 |    0.93347 |             2.5 |
| sample_iv_analysis  | traditional_cfd20_poly_timewalk |       127 |  -0.526038  |           1.79363 |            1.37948 |             2.21957 |       1.73704 |              1.54201 |               1.94791 |         0.708661 |                 0          |         1.99218 |           0.528812  |     -0.082943  | 49.1406 |    32 |    1.53564 |             2.5 |
| sample_iv_analysis  | ml_ridge_timewalk               |       127 |  -0.097558  |           1.55924 |            1.33365 |             1.78015 |       1.53093 |              1.35673 |               1.70431 |         0.80315  |                 0          |         1.80776 |           0.380696  |      0.135491  | 36.1351 |    35 |    1.03243 |             2.5 |

B-stack scale comparison, computed with the same CFD20 + polynomial correction machinery:

| sample              | method                          |   n_pairs |   median_ns |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   within_abs_2ns |   tail_fraction_abs_gt_5ns |   core_sigma_ns |   core_sigma_err_ns |   core_mean_ns |    chi2 |   ndf |   chi2_ndf |   fit_window_ns | comparison   |
|:--------------------|:--------------------------------|----------:|------------:|------------------:|-------------------:|--------------------:|--------------:|---------------------:|----------------------:|-----------------:|---------------------------:|----------------:|--------------------:|---------------:|--------:|------:|-----------:|----------------:|:-------------|
| sample_iii_analysis | traditional_cfd20_poly_timewalk |      2514 |  -0.0283876 |           1.38906 |            1.3394  |             1.45282 |       3.27205 |              1.40225 |               4.95434 |         0.862768 |                 0.00318218 |         1.45092 |           0.040141  |   -0.0297867   | 48.7802 |    37 |    1.31838 |             2.5 | A1-A3        |
| sample_ii_analysis  | traditional_cfd20_poly_timewalk |     10148 |  -0.776386  |           1.68646 |            1.65787 |             1.72177 |       6.14672 |              5.19223 |               7.13009 |         0.761037 |                 0.0200039  |         1.61996 |           0.0282829 |   -0.0272238   | 33.0628 |    37 |    0.89359 |             2.5 | B4-B6        |
| sample_ii_analysis  | traditional_cfd20_poly_timewalk |      4079 |  -0.388317  |           1.15971 |            1.11984 |             1.19821 |       4.79454 |              3.1948  |               6.03939 |         0.89164  |                 0.00858053 |         1.11662 |           0.0178702 |    0.000701692 | 46.4452 |    37 |    1.25528 |             2.5 | B6-B8        |

## 5. Falsification

- **Pre-registration:** primary metric was held-out-run A1-A3 robust residual width, appended to the ticket before inspecting S18 outputs.
- **Falsification test:** ML wins only if paired bootstrap on identical held-out analysis pairs shows robust-width improvement over the traditional correction.
- **Result:** the ML-minus-traditional paired bootstrap CI is [-0.054, 0.026] ns, p=0.524, with 6 ridge alpha values scanned. The ML win claim is rejected unless the CI is wholly below zero.

## 6. Threats to validity

- **Benchmark/selection:** the baseline is the calibrated CFD20 amplitude correction that reproduces the note's robust width; ML uses the same held-out pairs.
- **Data leakage:** splits are by run; calibration runs train corrections and analysis runs evaluate them; the ML feature matrix excludes the residual target.
- **Metric misuse:** robust width, Gaussian core sigma with chi2/ndf, full RMS, within-2 ns fraction, and tail fraction are all reported.
- **Post-hoc selection:** CFD20 and the primary robust-width metric were pre-registered. The Gaussian core is fit-definition sensitive, so the fit window is recorded and residual histograms are committed.

## 7. Provenance manifest

See `manifest.json`. It records input ROOT hashes, command, random seed, environment, and output hashes.

## 8. Findings & next steps

S18 supports the existing A-stack timing scale: the raw count table reproduces exactly and the Sample III robust width is consistent with 1.43 ns. The full RMS remains much larger than the core width, so tails matter. The B-stack comparison shows the A-stack two-stave cross-check is wider than clean downstream B-stack pairs, consistent with A-stack being a weaker external telescope rather than a B-stack calibration source.

Hypothesis: the A-stack timing core is stable enough as an external scale check, but its tails and Sample IV broadening are driven by low coincidence statistics plus period-dependent timewalk residuals rather than a universal detector resolution shift.

Queued follow-ups:
- S18b: quantify why Sample IV A-stack timing is wider and low-statistics; expected information gain is separating statistical instability from a run-period timing-scale shift.
- S05a: repeat correlated-clock residual decomposition with A-stack as an external event-level control; expected information gain is testing whether B-stack pair residuals contain common-mode electronics timing.

## 9. Reproducibility

```bash
python scripts/s18_astack_reproduction.py --config configs/s18_astack_reproduction.yaml
```

Artifacts are all in `reports/1780997954.15397.168324f2__s18_astack_independent_reproduction`.
