# S03m external shared-bin timewalk anchor

- **Ticket:** `1781163916.1315.567b2c03`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** ROOT files under `data/root/root`
- **Config:** `configs/s03m_1781163916_1315_567b2c03_external_anchor.yaml`
- **Git commit:** `0574a649d0919344642222dae9942c4b4ad50ad0`

## Abstract

This study tests whether the S03 shared-bin idea survives contact with an independent timing observable that is not one of the B-stack downstream-pair closure residuals. The external anchor is the A-stack A1--A3 duplicate timing residual, read directly from raw `h101/HRDv` ROOT records. The raw reproduction gate passes both the S18 A-stack selected-pulse counts and the canonical B-stack selected-pulse count of 640,737. On the primary Sample-III analysis split, the benchmark winner is **gradient_boosted_trees** with `sigma68=0.331` ns and run-block 95% CI `[0.323, 0.353]` ns. The frozen shared-bin correction itself obtains `sigma68=1.515` ns, so it is reported as an external-anchor diagnostic rather than automatically adopted as the global winner.

## Raw ROOT reproduction

The pulse table is derived from raw ROOT only. For each event, `HRDv` is reshaped to `(8,18)`, the median of samples 0--3 is subtracted, and a pulse is selected when the baseline-subtracted maximum exceeds 1000 ADC. The script can reuse raw-derived intermediate CSV caches on rerun; deleting `astack_pair_table.csv.gz`, `astack_counts.csv`, `bstack_counts.csv`, and `input_sha256.csv` forces a full ROOT rescan.

| gate                                  | quantity                                 |   expected |   reproduced |   delta | pass   |
|:--------------------------------------|:-----------------------------------------|-----------:|-------------:|--------:|:-------|
| A-stack raw ROOT selected-pulse count | sample_iii_analysis.events_with_selected |       7168 |         7168 |       0 | True   |
| A-stack raw ROOT selected-pulse count | sample_iii_analysis.selected_pulses      |       9682 |         9682 |       0 | True   |
| A-stack raw ROOT selected-pulse count | sample_iv_analysis.events_with_selected  |        767 |          767 |       0 | True   |
| A-stack raw ROOT selected-pulse count | sample_iv_analysis.selected_pulses       |        894 |          894 |       0 | True   |
| B-stack raw ROOT selected-pulse count | total_selected_pulses                    |     640737 |       640737 |       0 | True   |
| B-stack raw ROOT selected-pulse count | sample_ii_analysis.selected_pulses       |     125096 |       125096 |       0 | True   |
| B-stack raw ROOT selected-pulse count | sample_ii_analysis.B2                    |      88213 |        88213 |       0 | True   |
| B-stack raw ROOT selected-pulse count | sample_ii_analysis.B4                    |      21229 |        21229 |       0 | True   |
| B-stack raw ROOT selected-pulse count | sample_ii_analysis.B6                    |      11148 |        11148 |       0 | True   |
| B-stack raw ROOT selected-pulse count | sample_ii_analysis.B8                    |       4506 |         4506 |       0 | True   |

A-stack count table:

| stack   | sample              |   events_total |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------|:--------------------|---------------:|-----------------------:|------------------:|-----:|-----:|
| hrda    | sample_iii_analysis |         388848 |                   7168 |              9682 | 2799 | 6883 |
| hrda    | sample_iv_analysis  |         262189 |                    767 |               894 |  167 |  727 |

B-stack count table:

| stack   | sample              |   events_total |   events_with_selected |   selected_pulses |     B2 |    B4 |    B6 |   B8 |
|:--------|:--------------------|---------------:|-----------------------:|------------------:|-------:|------:|------:|-----:|
| hrdb    | sample_iii_calib    |         409815 |                 239559 |            248745 | 237882 |  6747 |  2940 | 1176 |
| hrdb    | sample_iii_analysis |         388879 |                 243133 |            252266 | 241422 |  6451 |  3094 | 1299 |
| hrdb    | sample_iv_calib     |          35943 |                  12103 |             14630 |  11907 |  1689 |   763 |  271 |
| hrdb    | sample_iv_analysis  |         262091 |                  89807 |            125096 |  88213 | 21229 | 11148 | 4506 |

## Estimands

For event `e`, run `r`, and A-stack channels `a=A1`, `b=A3`, the raw CFD20 residual is

`y_e = t_{e,b}^{CFD20} - t_{e,a}^{CFD20}`.

Each correction method estimates a calibration function `f_m(x_e)` using only calibration runs. The evaluated residual is

`r_{e,m} = y_e - f_m(x_e)`.

The primary width is the central robust scale

`sigma68(r) = [Q_84(r - median(r)) - Q_16(r - median(r))] / 2`.

Uncertainty intervals resample whole held-out analysis runs with replacement. For method comparisons the delta is

`Delta_m = sigma68(r_m) - sigma68(r_traditional)`;

negative values improve over the strong traditional polynomial timewalk baseline.

## Methods

The strong traditional method is a least-squares quadratic polynomial in `log(A1)`, `log(A3)`, and their interaction. The S03-style shared-bin method sorts calibration events by `log(min(A1,A3))`, estimates the median residual per amplitude bin, and shrinks each bin median toward the global calibration median by `n/(n+lambda)`, with `lambda=80.0`. This freezes a common amplitude-bin timewalk curve before looking at analysis runs.

The ML/NN panel uses the same train/test split by run. Ridge, gradient-boosted trees, and MLP receive scalar pulse features and normalized 18-sample waveforms from both channels. The 1D-CNN consumes the two normalized waveforms as channels plus scalar metadata. The new architecture is a gated CNN whose scalar branch multiplicatively gates the convolutional residual prediction, allowing the waveform correction strength to vary smoothly with amplitude and phase.

## Benchmark

| sample              | method                  | model_family                           |   n_pairs |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   median_ns |   tail_frac_abs_gt5ns |   delta_vs_traditional_ns |   delta_ci_low_ns |   delta_ci_high_ns |
|:--------------------|:------------------------|:---------------------------------------|----------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|------------:|----------------------:|--------------------------:|------------------:|-------------------:|
| sample_iii_analysis | gradient_boosted_trees  | gradient_boosted_trees                 |      2514 |       14 |      0.33068 |            0.322504 |             0.352528 |       2.47617 |             0.693645 |               4.353   |  0.00378127 |            0.00596659 |                -1.05838   |        -1.12855   |          -1.01054  |
| sample_iii_analysis | mlp                     | mlp                                    |      2514 |       14 |      0.6474  |            0.629963 |             0.685049 |       2.44753 |             1.10892  |               3.80459 | -0.0185235  |            0.00556881 |                -0.741659  |        -0.812871  |          -0.686506 |
| sample_iii_analysis | ridge                   | ridge                                  |      2514 |       14 |      0.88436 |            0.861986 |             0.936407 |       2.2558  |             1.43178  |               3.83742 |  0.0057016  |            0.00676213 |                -0.504699  |        -0.56736   |          -0.440559 |
| sample_iii_analysis | traditional_poly_logamp | strong_traditional_polynomial_timewalk |      2514 |       14 |      1.38906 |            1.33671  |             1.47115  |       3.27205 |             1.43594  |               5.26504 | -0.0283876  |            0.00318218 |                 0         |         0         |           0        |
| sample_iii_analysis | cnn1d                   | 1d_cnn                                 |      2514 |       14 |      1.40343 |            1.34397  |             1.47324  |      15.9111  |            12.3532   |              17.7395  | -0.0394575  |            0.0222753  |                 0.0143691 |        -0.0335846 |           0.031593 |
| sample_iii_analysis | shared_bin_timewalk     | traditional_shared_bin_timewalk        |      2514 |       14 |      1.51495 |            1.48294  |             1.55177  |       3.31406 |             1.54849  |               5.26402 |  0.0631064  |            0.00238663 |                 0.125891  |         0.0750007 |           0.159857 |
| sample_iii_analysis | gated_cnn               | new_gated_cnn_architecture             |      2514 |       14 |      1.52777 |            1.45994  |             1.58148  |       8.41792 |             7.23899  |               9.27371 | -0.049351   |            0.0218775  |                 0.138713  |         0.0782511 |           0.16192  |
| sample_iv_analysis  | gated_cnn               | new_gated_cnn_architecture             |       127 |        7 |      1.55436 |            1.28662  |             1.73162  |       1.51692 |             1.30069  |               1.66823 | -0.0719489  |            0          |                -0.239264  |        -0.533338  |           0.280693 |
| sample_iv_analysis  | cnn1d                   | 1d_cnn                                 |       127 |        7 |      1.55821 |            1.29141  |             1.75337  |       1.5181  |             1.29685  |               1.66393 | -0.0838969  |            0          |                -0.235415  |        -0.551176  |           0.264335 |
| sample_iv_analysis  | mlp                     | mlp                                    |       127 |        7 |      1.55867 |            1.34757  |             1.7913   |       1.68105 |             1.51006  |               1.81666 |  1.15142    |            0.00787402 |                -0.234956  |        -0.480747  |           0.224169 |
| sample_iv_analysis  | gradient_boosted_trees  | gradient_boosted_trees                 |       127 |        7 |      1.60997 |            1.25337  |             1.71044  |       1.49924 |             1.25708  |               1.65432 | -0.22214    |            0          |                -0.183655  |        -0.53182   |           0.234723 |
| sample_iv_analysis  | shared_bin_timewalk     | traditional_shared_bin_timewalk        |       127 |        7 |      1.61029 |            1.35989  |             1.71578  |       1.50042 |             1.28784  |               1.67481 |  0.101833   |            0          |                -0.183336  |        -0.548763  |           0.225379 |
| sample_iv_analysis  | traditional_poly_logamp | strong_traditional_polynomial_timewalk |       127 |        7 |      1.79363 |            1.36366  |             2.0452   |       1.73704 |             1.54064  |               1.94171 | -0.526038   |            0          |                 0         |         0         |           0        |
| sample_iv_analysis  | ridge                   | ridge                                  |       127 |        7 |      1.97037 |            1.55988  |             4.71202  |       3.75829 |             3.10866  |               4.6325  |  0.7152     |            0.15748    |                 0.176743  |        -0.26027   |           2.88603  |

## Diagnostics

| bin            | n_train   | raw_median_ns      | shrink_weight        | correction_ns      | sample              | diagnostic   | value   | method   | alpha   | cv_sigma68_ns      | sample_eval         | note                                                 |
|:---------------|:----------|:-------------------|:---------------------|:-------------------|:--------------------|:-------------|:--------|:---------|:--------|:-------------------|:--------------------|:-----------------------------------------------------|
| (6.909, 7.073] | 480.0     | 3.4367202019823697 | 0.8571428571428571   | 3.5150777512399607 | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
| (7.073, 7.191] | 475.0     | 3.496724193032918  | 0.8558558558558559   | 3.5671384422224803 | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
| (7.191, 7.294] | 477.0     | 3.737523289032417  | 0.8563734290843806   | 3.773099555855123  | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
| (7.294, 7.384] | 478.0     | 3.851273811695691  | 0.8566308243727598   | 3.870478003106417  | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
| (7.384, 7.472] | 477.0     | 4.120728342095191  | 0.8563734290843806   | 4.101266181188953  | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
| (7.472, 7.566] | 475.0     | 4.228926860656323  | 0.8558558558558559   | 4.19379838298125   | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
| (7.566, 7.675] | 477.0     | 4.335630759699523  | 0.8563734290843806   | 4.285302901471298  | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
| (7.675, 7.983] | 477.0     | 4.398762545755108  | 0.8563734290843806   | 4.339367285579941  | sample_iii_analysis |              |         |          |         |                    | sample_iii_analysis |                                                      |
|                |           |                    |                      |                    | sample_iii_analysis | torch_status | ok      |          |         |                    | sample_iii_analysis |                                                      |
|                |           |                    |                      |                    | sample_iii_analysis | ridge_cv     |         | ridge    | 0.01    | 1.1288639132311387 | sample_iii_analysis |                                                      |
|                |           |                    |                      |                    | sample_iii_analysis | ridge_cv     |         | ridge    | 0.1     | 1.1162153523457716 | sample_iii_analysis |                                                      |
|                |           |                    |                      |                    | sample_iii_analysis | ridge_cv     |         | ridge    | 1.0     | 1.0677584483978835 | sample_iii_analysis |                                                      |
|                |           |                    |                      |                    | sample_iii_analysis | ridge_cv     |         | ridge    | 10.0    | 1.100406200108507  | sample_iii_analysis |                                                      |
|                |           |                    |                      |                    | sample_iii_analysis | ridge_cv     |         | ridge    | 100.0   | 1.1816367908249925 | sample_iii_analysis |                                                      |
| (6.991, 7.125] | 2.0       | 4.916967729308549  | 0.024390243902439025 | 3.6379246999855486 | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
| (7.125, 7.222] | 2.0       | 3.4584978008697114 | 0.024390243902439025 | 3.6023522627065527 | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
| (7.222, 7.274] | 2.0       | 4.057642544933747  | 0.024390243902439025 | 3.616965549147139  | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
| (7.274, 7.295] | 2.0       | 3.0573602853780173 | 0.024390243902439025 | 3.5925684208652915 | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
| (7.295, 7.353] | 2.0       | 4.039481433476386  | 0.024390243902439025 | 3.616522595209154  | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
| (7.353, 7.463] | 2.0       | 3.2383016980720036 | 0.024390243902439025 | 3.59698162605295   | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
| (7.463, 7.588] | 2.0       | 4.51754829679998   | 0.024390243902439025 | 3.628182762607291  | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
| (7.588, 7.72]  | 2.0       | 4.2863285003945375 | 0.024390243902439025 | 3.62254325537789   | sample_iv_analysis  |              |         |          |         |                    | sample_iv_analysis  |                                                      |
|                |           |                    |                      |                    | sample_iv_analysis  | torch_status | ok      |          |         |                    | sample_iv_analysis  |                                                      |
|                |           |                    |                      |                    | sample_iv_analysis  | ridge_cv     |         | ridge    | 0.01    |                    | sample_iv_analysis  | single calibration run; leave-one-run CV not defined |

## Systematics and caveats

- **Split discipline:** calibration and analysis runs are disjoint; CIs resample held-out runs, not individual events.
- **External-anchor limitation:** A1--A3 is an independent timing observable, but it is not the same transport path as B-stack downstream-pair closure. Agreement supports portability; disagreement is not by itself a B-stack falsification.
- **Shared-bin sensitivity:** bin medians are robust to tails but can underfit phase-local pulse-shape effects. Shrinkage is fixed before scoring.
- **Neural-network variance:** CNN rows are intentionally small models trained on the local calibration split. They test architecture class plausibility, not a production hyperparameter search.
- **MLP optimizer budget:** the local MLP uses `max_iter=80` for bounded runtime. A convergence warning means the MLP row is a fixed-budget comparator rather than a fully optimized neural baseline.
- **Tail behavior:** `full_rms` and `P(|r-median|>5 ns)` are reported because a narrow core can hide rare pathological timing tails.
- **Raw-data caveat:** ROOT checksums are recorded in `input_sha256.csv`; the large raw archives themselves are gitignored.

## Verdict

`result.json` names **gradient_boosted_trees** as the winner on the primary Sample-III analysis A-stack anchor. The shared-bin correction is a meaningful independent diagnostic if its run-block CI overlaps the winner and beats the polynomial baseline; otherwise it should remain a support-dependent correction rather than a blanket replacement for downstream timing.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03m_1781163916_1315_567b2c03_external_sharedbin_astack_anchor.py --config configs/s03m_1781163916_1315_567b2c03_external_anchor.yaml
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `astack_counts.csv`, `bstack_counts.csv`, `benchmark.csv`, `residuals_sample_iii_analysis.csv.gz`, `residuals_sample_iv_analysis.csv.gz`, `diagnostics.csv`, `input_sha256.csv`, and `manifest.json`.
