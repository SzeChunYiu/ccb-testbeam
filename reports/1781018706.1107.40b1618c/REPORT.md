# P01e: derivative-stability check for sample-6 timing smoothing

**Ticket:** 1781018706.1107.40b1618c

## Reproduction first
Raw B-stack ROOT was read from `data/root/root` before any timing or
ML modelling. The selected-pulse gate reproduced **640,737**
versus **640,737**. The P01d
sample-6 non-CFD sign pattern also reproduced before this study's derivative
tests.

| quantity                                     |   report_value |   reproduced |   delta |   tolerance | pass   |   ci_low |   ci_high |
|:---------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|---------:|----------:|
| total selected B-stave pulses                |      6.407e+05 |    6.407e+05 |       0 |        0    | True   | nan      |  nan      |
| p01d_sample6_cfd20_delta_sigma68_ns          |     -0.9299    |   -0.9299    |       0 |        0.02 | True   |  -1.076  |   -0.6579 |
| p01d_sample6_template_phase_delta_sigma68_ns |     -0.2639    |   -0.2639    |       0 |        0.02 | True   |  -0.5    |    0.2361 |
| p01d_sample6_of_5_13_delta_sigma68_ns        |     -0.3602    |   -0.3602    |       0 |        0.02 | True   |  -0.4955 |   -0.1889 |

## Split and methods
All fits, templates, amplitude bins, and ML models use train runs only; held-out
runs are `42, 57, 64, 65`.
Confidence intervals are paired run bootstraps over those held-out runs.

Traditional replacements are:
`control_stratum_mean` from P01d, `local_linear_bridge` from samples 5 and 7,
and `ampbin_template_curvature`, which preserves the event's local endpoints
while injecting train-run amplitude-bin curvature at sample 6.

## Traditional derivative and curvature checks
Positive deltas mean the replacement worsened timing; negative deltas mean the
replacement made timing narrower than the untouched waveform.

| variant                   | method         |   delta_sigma68_ns |   ci_low |    ci_high |
|:--------------------------|:---------------|-------------------:|---------:|-----------:|
| ampbin_template_curvature | cfd20          |           -0.1653  |  -0.2904 | -0.01536   |
| ampbin_template_curvature | of_5_13        |           -0.08591 |  -0.2276 |  0.1675    |
| ampbin_template_curvature | template_phase |           -0.01393 |  -0.25   |  3.553e-15 |
| control_stratum_mean      | cfd20          |           -0.9299  |  -1.082  | -0.6579    |
| control_stratum_mean      | of_5_13        |           -0.3602  |  -0.4848 | -0.1889    |
| control_stratum_mean      | template_phase |           -0.2639  |  -0.5    |  0.2361    |
| local_linear_bridge       | cfd20          |           -0.1628  |  -0.2823 | -0.00534   |
| local_linear_bridge       | of_5_13        |           -0.1519  |  -0.2689 |  0.0337    |
| local_linear_bridge       | template_phase |           -0.25    |  -0.4861 |  0         |

## ML sample-6 imputation
The ML arm is a run-CV Ridge model that predicts normalized sample 6 from all
other normalized waveform samples plus stave one-hot; sample 6 and amplitude
are excluded from features.

Run-CV on train runs:

|   alpha |   fold | run_group_split   |     mse |       mae |       r2 |      n |
|--------:|-------:|:------------------|--------:|----------:|---------:|-------:|
|    0.01 |      0 | train_run_cv      | 0.0448  |   0.08449 |   0.6508 | 141858 |
|    0.01 |      1 | train_run_cv      | 0.07531 |   0.0997  |   0.5804 | 146028 |
|    0.01 |      2 | train_run_cv      | 0.06896 |   0.08986 |   0.62   | 148925 |
|    0.01 |      3 | train_run_cv      | 0.05188 |   0.08291 |   0.6414 | 144313 |
|    0.01 |     -1 | train_run_cv_mean | 0.06024 | nan       | nan      | 581124 |
|    0.1  |      0 | train_run_cv      | 0.0448  |   0.08449 |   0.6508 | 141858 |
|    0.1  |      1 | train_run_cv      | 0.07531 |   0.0997  |   0.5804 | 146028 |
|    0.1  |      2 | train_run_cv      | 0.06896 |   0.08986 |   0.62   | 148925 |
|    0.1  |      3 | train_run_cv      | 0.05188 |   0.08291 |   0.6414 | 144313 |
|    0.1  |     -1 | train_run_cv_mean | 0.06024 | nan       | nan      | 581124 |
|    1    |      0 | train_run_cv      | 0.0448  |   0.08448 |   0.6508 | 141858 |
|    1    |      1 | train_run_cv      | 0.07531 |   0.0997  |   0.5804 | 146028 |
|    1    |      2 | train_run_cv      | 0.06896 |   0.08986 |   0.62   | 148925 |
|    1    |      3 | train_run_cv      | 0.05188 |   0.08291 |   0.6414 | 144313 |
|    1    |     -1 | train_run_cv_mean | 0.06024 | nan       | nan      | 581124 |
|   10    |      0 | train_run_cv      | 0.0448  |   0.08444 |   0.6509 | 141858 |
|   10    |      1 | train_run_cv      | 0.07532 |   0.09967 |   0.5804 | 146028 |
|   10    |      2 | train_run_cv      | 0.06896 |   0.08982 |   0.62   | 148925 |
|   10    |      3 | train_run_cv      | 0.05188 |   0.08287 |   0.6414 | 144313 |
|   10    |     -1 | train_run_cv_mean | 0.06024 | nan       | nan      | 581124 |
|  100    |      0 | train_run_cv      | 0.04477 |   0.08401 |   0.6511 | 141858 |
|  100    |      1 | train_run_cv      | 0.07534 |   0.0994  |   0.5803 | 146028 |
|  100    |      2 | train_run_cv      | 0.06897 |   0.0895  |   0.6199 | 148925 |
|  100    |      3 | train_run_cv      | 0.05187 |   0.08253 |   0.6414 | 144313 |
|  100    |     -1 | train_run_cv_mean | 0.06024 | nan       | nan      | 581124 |

Held-out mean by model:

| model                 |     mse |    mae |       r2 |
|:----------------------|--------:|-------:|---------:|
| ridge_sample6_imputer | 0.05221 | 0.096  |  0.7356  |
| ridge_target_shuffle  | 0.1838  | 0.2444 | -0.07911 |

Timing deltas:

| variant                 | method         |   delta_sigma68_ns |   ci_low |    ci_high |
|:------------------------|:---------------|-------------------:|---------:|-----------:|
| ml_ridge_impute         | cfd20          |           -0.1698  | -0.2906  | -0.02956   |
| ml_ridge_impute         | of_5_13        |            0.09607 | -0.05625 |  0.3078    |
| ml_ridge_impute         | template_phase |           -0.01393 | -0.25    |  0.01393   |
| ml_ridge_shuffle_impute | cfd20          |           -1.072   | -1.298   | -0.8972    |
| ml_ridge_shuffle_impute | of_5_13        |           -0.7748  | -0.8714  | -0.5398    |
| ml_ridge_shuffle_impute | template_phase |           -0.5     | -0.7361  |  3.553e-15 |

## Leakage checks
| check                                    | value               | detail                                                                                                |
|:-----------------------------------------|:--------------------|:------------------------------------------------------------------------------------------------------|
| run_overlap                              | 0                   | must be zero for train/heldout split                                                                  |
| sample6_feature_excluded                 | 1                   | ML sample-6 imputer uses normalized samples except sample 6 plus stave one-hot; amplitude is excluded |
| target_shuffle_r2                        | -0.0791097236924746 | held-out sample-6 imputer trained on shuffled train targets                                           |
| target_shuffle_mse_over_real_mse         | 3.520789873650166   | large ratio is expected if local-shape prediction is real rather than leakage                         |
| target_shuffle_timing_min_delta_ns       | -1.0721610838389406 | bad shape model can still narrow timing, so timing deltas alone are not accepted as ML evidence       |
| train_selected_of_window                 | of_5_13             | optimal-filter window selected by train-run sigma68 before held-out evaluation                        |
| p01d_non_cfd_negative_methods_reproduced | 2                   | template-phase and train-selected OF both remain negative before derivative replacements              |

## Conclusion
The original P01d sample-6 negative sign reproduces, but it is not stable to shape-aware replacement. Train-run local curvature and the no-sample-6 ML imputer remove most of the favorable OF/template response, while the target-shuffle timing artifact shows that timing narrowing alone can be produced by bad sample-6 smoothing. Sample 6 is therefore better interpreted as a local shape/tuning artifact of the control replacement than as a standalone smoothing robustness claim.
