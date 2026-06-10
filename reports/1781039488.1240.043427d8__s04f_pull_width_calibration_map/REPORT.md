# Study report: S04f - waveform timing pull-width calibration map

- **Ticket:** 1781039488.1240.043427d8
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo truth labels
- **Split:** leave one Sample-II analysis run out across runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/s04f_1781039488_1240_043427d8_pull_width_calibration_map.yaml`
- **Git commit:** `8cfc49c17d1d36a57581a6c221a5997b18d99bae`

## Abstract

The production point-score winner recorded in `result.json` is **ridge_conformal** with pooled primary calibration score `0.0499`. The score combines absolute pull-width error, absolute central-interval coverage error at 68.27%, 90%, and 95%, and a small sharpness penalty on median predicted sigma. Lower is better; all headline intervals use run-block bootstrap CIs over held-out runs. The verdict field records whether that point-score win is CI-separated from the traditional width map.

## 1. Reproduction from raw ROOT

The gate reads `h101/HRDv` from the raw B-stack ROOT files, reshapes each event to `(8, 18)`, subtracts the median of samples 0--3 for every B stave, and counts pulses with baseline-subtracted amplitude greater than 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Estimand and equations

The point-time anchor is the S03 analytic timewalk correction fitted only on training runs.  For event `e` and downstream stave `s`,

`u_es = t^S03_es - z_s v_TOF`, with `v_TOF = 0.078 ns/cm` and the nominal 2 cm downstream spacing.

The self-supervised calibration residual is

`r_es = u_es - (1/2) sum_{q != s} u_eq`,

where the sum runs over the other two downstream staves in the same event.  A method predicts mean `mu_es` and uncertainty `sigma_es`; evaluation uses `epsilon_es = r_es - mu_es` and pull `p_es = epsilon_es / sigma_es` on the held-out run only.

The primary score is

`|sigma68(p)-1| + |C_68-0.6827| + |C_90-0.90| + |C_95-0.95| + 0.01 median(sigma)`,

where `C_a` is the observed central coverage.  The 90% and 95% interval multipliers are conformal quantiles calibrated on training residuals.

## 3. Methods

The traditional method is a robust width map over training-run strata `(stave, amplitude quartile, template-quality tertile, peak-phase bin)` with hierarchical fallback to coarser strata.  Its location is the train-run median residual and its width is train-run `sigma68`, so it is a strong transparent uncertainty baseline rather than a constant global error bar.

ML methods use the same run split and same target.  Ridge and histogram gradient-boosted trees train a mean residual model, then train a second model on out-of-fold log absolute residuals; a conformal scale forces training-run pull `sigma68` to unity.  The MLP, 1D-CNN, and gated waveform-tabular CNN optimize Gaussian negative log likelihood and then receive the same scalar conformal width correction.  The gated CNN is the new architecture: a small waveform convolutional encoder is multiplicatively gated by tabular amplitude/shape/stave/template-quality features before the residual head.

Controls are not eligible for the production winner.  They include amplitude-only ridge, run-only width, shuffled-target ridge, phase-scrambled CNN, and fixed sample-permuted CNN.

## 4. Head-to-head benchmark

| method                              | family                         |   primary_score |   primary_score_ci_low |   primary_score_ci_high |   pull_sigma68 |   pull_sigma68_ci_low |   pull_sigma68_ci_high |   coverage68 |   coverage90 |   coverage95 |   pred_sigma_median_ns |   mae_ns |   n_heldout_runs |
|:------------------------------------|:-------------------------------|----------------:|-----------------------:|------------------------:|---------------:|----------------------:|-----------------------:|-------------:|-------------:|-------------:|-----------------------:|---------:|-----------------:|
| ridge_conformal                     | ridge                          |       0.0499162 |              0.0441    |                0.215329 |        0.99225 |              0.926249 |                1.07578 |     0.682723 |     0.887784 |     0.931763 |               1.16898  | 1.02522  |                7 |
| gated_waveform_tabular_cnn          | new_gated_waveform_tabular_cnn |       0.0693188 |              0.043481  |                0.376296 |        1.01    |              0.914892 |                1.16041 |     0.667539 |     0.887522 |     0.933421 |               1.50995  | 1.45389  |                7 |
| gradient_boosted_trees_conformal    | gradient_boosted_trees         |       0.0954621 |              0.0509528 |                0.339995 |        1.01228 |              0.917299 |                1.13227 |     0.672251 |     0.869372 |     0.917888 |               0.999451 | 0.918998 |                7 |
| traditional_stratified_robust_width | traditional                    |       0.122019  |              0.098858  |                0.364558 |        1.01275 |              0.934483 |                1.13547 |     0.677661 |     0.85349  |     0.903927 |               1.16491  | 0.951774 |                7 |
| mlp_heteroskedastic                 | mlp                            |       0.144144  |              0.0953455 |                0.320093 |        1.01576 |              0.921069 |                1.10574 |     0.659337 |     0.853316 |     0.902618 |               1.09524  | 1.19833  |                7 |
| cnn_1d_heteroskedastic              | cnn_1d                         |       0.1504    |              0.0888118 |                0.403883 |        1.02039 |              0.912071 |                1.14386 |     0.664049 |     0.852531 |     0.89651  |               1.03947  | 1.08882  |                7 |

## 5. Negative controls

| method                        | family                  |   primary_score |   primary_score_ci_low |   primary_score_ci_high |   pull_sigma68 |   coverage68 |   coverage90 |   coverage95 |   pred_sigma_median_ns |
|:------------------------------|:------------------------|----------------:|-----------------------:|------------------------:|---------------:|-------------:|-------------:|-------------:|-----------------------:|
| control_shuffled_target_ridge | control_shuffled_target |       0.0792162 |              0.0690425 |                0.421421 |        1.00195 |     0.647557 |     0.890052 |     0.935602 |               1.77802  |
| control_run_only_width        | control_run_only        |       0.133744  |              0.0926017 |                0.455541 |        1.00375 |     0.627923 |     0.870506 |     0.92164  |               1.73583  |
| control_amplitude_only_ridge  | control_amplitude_only  |       0.159469  |              0.150462  |                0.432624 |        0.98716 |     0.68438  |     0.835166 |     0.879319 |               0.943356 |
| control_sample_permuted_cnn   | control_sample_permuted |       0.163355  |              0.112429  |                0.451498 |        1.02107 |     0.670855 |     0.84171  |     0.887958 |               1.01123  |
| control_phase_scrambled_cnn   | control_phase_scrambled |       0.185138  |              0.135174  |                0.529756 |        1.02768 |     0.665358 |     0.835428 |     0.884642 |               1.01861  |

## 6. Per-run held-out metrics

|   heldout_run | method                              |   primary_score |   pull_sigma68 |   coverage68 |   coverage90 |   coverage95 |   pred_sigma_median_ns |   pairwise_sigma68_ns |   n_pulses |
|--------------:|:------------------------------------|----------------:|---------------:|-------------:|-------------:|-------------:|-----------------------:|----------------------:|-----------:|
|            58 | control_run_only_width              |       0.179824  |       0.931474 |     0.616438 |     0.926941 |     0.949772 |               1.78669  |              1.18748  |        219 |
|            58 | gradient_boosted_trees_conformal    |       0.201854  |       1.07532  |     0.648402 |     0.858447 |     0.908676 |               0.936323 |              1.15488  |        219 |
|            58 | control_shuffled_target_ridge       |       0.217093  |       0.889095 |     0.712329 |     0.945205 |     0.96347  |               1.78836  |              1.145    |        219 |
|            58 | traditional_stratified_robust_width |       0.25763   |       0.846106 |     0.748858 |     0.890411 |     0.926941 |               0.49293  |              0.873471 |        219 |
|            58 | mlp_heteroskedastic                 |       0.312894  |       0.824809 |     0.780822 |     0.922374 |     0.945205 |               1.24117  |              0.979283 |        219 |
|            58 | ridge_conformal                     |       0.338062  |       0.793615 |     0.767123 |     0.931507 |     0.954338 |               1.14087  |              1.12236  |        219 |
|            58 | gated_waveform_tabular_cnn          |       0.342011  |       0.799355 |     0.767123 |     0.936073 |     0.954338 |               1.65314  |              1.18457  |        219 |
|            58 | control_sample_permuted_cnn         |       0.355859  |       0.799584 |     0.799087 |     0.922374 |     0.945205 |               1.18869  |              1.0476   |        219 |
|            58 | control_phase_scrambled_cnn         |       0.471639  |       0.720794 |     0.821918 |     0.940639 |     0.949772 |               1.23481  |              0.868601 |        219 |
|            58 | cnn_1d_heteroskedastic              |       0.523525  |       0.646068 |     0.803653 |     0.936073 |     0.949772 |               1.23395  |              0.768353 |        219 |
|            58 | control_amplitude_only_ridge        |       0.601474  |       0.582609 |     0.817352 |     0.936073 |     0.954338 |               0.902019 |              1.07833  |        219 |
|            59 | control_sample_permuted_cnn         |       0.0330753 |       1.00848  |     0.678462 |     0.907383 |     0.952818 |               1.01522  |              1.32508  |       2289 |
|            59 | cnn_1d_heteroskedastic              |       0.0491903 |       1.01529  |     0.66754  |     0.905199 |     0.953255 |               1.0286   |              1.21861  |       2289 |
|            59 | control_phase_scrambled_cnn         |       0.0630831 |       0.969525 |     0.684578 |     0.915684 |     0.955439 |               0.96071  |              1.11456  |       2289 |
|            59 | mlp_heteroskedastic                 |       0.0646011 |       0.974619 |     0.689384 |     0.912626 |     0.959371 |               1.05396  |              1.22652  |       2289 |
|            59 | ridge_conformal                     |       0.0675181 |       0.981974 |     0.692005 |     0.916994 |     0.961118 |               1.20743  |              1.31639  |       2289 |
|            59 | gated_waveform_tabular_cnn          |       0.0716954 |       0.978525 |     0.6955   |     0.916121 |     0.959808 |               1.14916  |              1.30126  |       2289 |
|            59 | control_run_only_width              |       0.079969  |       0.954441 |     0.669288 |     0.903014 |     0.949323 |               1.73063  |              1.45871  |       2289 |
|            59 | control_amplitude_only_ridge        |       0.0944204 |       0.957895 |     0.697685 |     0.917868 |     0.959808 |               0.96547  |              1.36261  |       2289 |
|            59 | gradient_boosted_trees_conformal    |       0.12525   |       0.92374  |     0.702927 |     0.912626 |     0.955876 |               1.02616  |              1.04559  |       2289 |
|            59 | control_shuffled_target_ridge       |       0.133525  |       0.93466  |     0.685889 |     0.932722 |     0.964613 |               1.76601  |              1.51857  |       2289 |
|            59 | traditional_stratified_robust_width |       0.146596  |       0.929686 |     0.716907 |     0.890782 |     0.929664 |               1.25204  |              1.21426  |       2289 |
|            60 | control_run_only_width              |       0.11983   |       0.934774 |     0.653465 |     0.89934  |     0.942244 |               1.69542  |              1.3437   |       2424 |
|            60 | ridge_conformal                     |       0.152643  |       0.9113   |     0.72071  |     0.912954 |     0.949257 |               1.2237   |              1.31744  |       2424 |
|            60 | traditional_stratified_robust_width |       0.154978  |       0.936065 |     0.705446 |     0.874587 |     0.918317 |               1.1202   |              1.19685  |       2424 |
|            60 | mlp_heteroskedastic                 |       0.159312  |       0.898903 |     0.667079 |     0.917904 |     0.963284 |               1.14065  |              1.0544   |       2424 |
|            60 | cnn_1d_heteroskedastic              |       0.174524  |       0.894287 |     0.701733 |     0.92533  |     0.963696 |               1.0752   |              1.14121  |       2424 |
|            60 | control_sample_permuted_cnn         |       0.176722  |       0.895512 |     0.714109 |     0.918729 |     0.961634 |               1.04614  |              1.24741  |       2424 |
|            60 | control_phase_scrambled_cnn         |       0.200261  |       0.87944  |     0.709158 |     0.932756 |     0.959571 |               1.09163  |              1.0735   |       2424 |
|            60 | control_shuffled_target_ridge       |       0.206774  |       0.90282  |     0.727723 |     0.928218 |     0.969059 |               1.72937  |              1.31955  |       2424 |
|            60 | gated_waveform_tabular_cnn          |       0.208763  |       0.899413 |     0.72401  |     0.931518 |     0.970297 |               1.50512  |              1.14429  |       2424 |
|            60 | gradient_boosted_trees_conformal    |       0.211771  |       0.877535 |     0.734736 |     0.917079 |     0.959158 |               1.10326  |              1.0971   |       2424 |
|            60 | control_amplitude_only_ridge        |       0.267302  |       0.832644 |     0.737624 |     0.924505 |     0.960809 |               0.970879 |              1.24603  |       2424 |
|            61 | ridge_conformal                     |       0.301353  |       1.13281  |     0.609861 |     0.849589 |     0.915684 |               1.09783  |              1.27139  |       2799 |
|            61 | mlp_heteroskedastic                 |       0.398468  |       1.20301  |     0.602715 |     0.834227 |     0.910682 |               1.03862  |              1.25065  |       2799 |
|            61 | gradient_boosted_trees_conformal    |       0.427593  |       1.20608  |     0.594141 |     0.82851  |     0.898178 |               0.963752 |              1.09861  |       2799 |
|            61 | cnn_1d_heteroskedastic              |       0.491689  |       1.25629  |     0.57592  |     0.821722 |     0.909611 |               0.994639 |              1.19144  |       2799 |
|            61 | control_amplitude_only_ridge        |       0.537314  |       1.32236  |     0.593426 |     0.828867 |     0.904252 |               0.880349 |              1.25907  |       2799 |
|            61 | control_sample_permuted_cnn         |       0.545584  |       1.309    |     0.576635 |     0.823151 |     0.906038 |               0.970839 |              1.23389  |       2799 |
|            61 | traditional_stratified_robust_width |       0.566527  |       1.23988  |     0.592712 |     0.779207 |     0.845302 |               1.11679  |              1.24705  |       2799 |
|            61 | gated_waveform_tabular_cnn          |       0.644162  |       1.28911  |     0.534477 |     0.788496 |     0.870668 |               1.5996   |              1.89976  |       2799 |
|            61 | control_phase_scrambled_cnn         |       0.671001  |       1.3788   |     0.560915 |     0.807074 |     0.882815 |               1.03061  |              1.30915  |       2799 |
|            61 | control_shuffled_target_ridge       |       0.745338  |       1.33486  |     0.498035 |     0.771347 |     0.871383 |               1.85383  |              2.06065  |       2799 |
|            61 | control_run_only_width              |       0.773677  |       1.35524  |     0.52483  |     0.770275 |     0.837442 |               1.82864  |              2.12996  |       2799 |
|            62 | gradient_boosted_trees_conformal    |       0.0318374 |       0.99745  |     0.67658  |     0.892193 |     0.944651 |               1.00118  |              1.0981   |       2421 |
|            62 | control_phase_scrambled_cnn         |       0.0596461 |       0.967865 |     0.688558 |     0.907889 |     0.953738 |               1.00253  |              1.22972  |       2421 |
|            62 | control_sample_permuted_cnn         |       0.0664572 |       0.975751 |     0.691863 |     0.912846 |     0.959934 |               1.02656  |              1.16239  |       2421 |
|            62 | cnn_1d_heteroskedastic              |       0.0929791 |       0.950266 |     0.692689 |     0.916563 |     0.956216 |               1.04763  |              1.20878  |       2421 |
|            62 | control_shuffled_target_ridge       |       0.0979552 |       0.989181 |     0.666254 |     0.933086 |     0.969847 |               1.77566  |              1.51522  |       2421 |
|            62 | control_run_only_width              |       0.103524  |       0.948317 |     0.654688 |     0.903346 |     0.952912 |               1.75718  |              1.469    |       2421 |
|            62 | control_amplitude_only_ridge        |       0.111191  |       0.932994 |     0.695993 |     0.913672 |     0.957456 |               0.976423 |              1.35613  |       2421 |
|            62 | ridge_conformal                     |       0.117058  |       0.943377 |     0.708798 |     0.914085 |     0.958282 |               1.19697  |              1.31244  |       2421 |
|            62 | mlp_heteroskedastic                 |       0.122323  |       0.964139 |     0.641057 |     0.921107 |     0.961173 |               1.25386  |              1.28435  |       2421 |
|            62 | traditional_stratified_robust_width |       0.126339  |       0.95916  |     0.697646 |     0.868649 |     0.922759 |               1.19615  |              1.22131  |       2421 |
|            62 | gated_waveform_tabular_cnn          |       0.126494  |       0.954897 |     0.699298 |     0.926477 |     0.971499 |               1.68178  |              1.4549   |       2421 |
|            63 | ridge_conformal                     |       0.0322977 |       0.992    |     0.683784 |     0.910811 |     0.94955  |               1.19527  |              1.39261  |       1110 |
|            63 | gradient_boosted_trees_conformal    |       0.0726572 |       1.03359  |     0.665766 |     0.893694 |     0.944144 |               0.996726 |              1.1682   |       1110 |
|            63 | traditional_stratified_robust_width |       0.100334  |       0.981727 |     0.692793 |     0.871171 |     0.918919 |               1.20574  |              1.28012  |       1110 |
|            63 | control_phase_scrambled_cnn         |       0.105579  |       0.931843 |     0.706306 |     0.9      |     0.945946 |               0.976104 |              1.26831  |       1110 |
|            63 | cnn_1d_heteroskedastic              |       0.107227  |       0.935904 |     0.697297 |     0.891892 |     0.93964  |               1.00648  |              1.31139  |       1110 |
|            63 | control_run_only_width              |       0.114109  |       0.908922 |     0.68018  |     0.902703 |     0.95045  |               1.73583  |              1.39132  |       1110 |
|            63 | control_amplitude_only_ridge        |       0.130535  |       0.912187 |     0.712613 |     0.898198 |     0.948649 |               0.965602 |              1.40261  |       1110 |
|            63 | gated_waveform_tabular_cnn          |       0.133418  |       0.935585 |     0.718018 |     0.917117 |     0.954054 |               1.25139  |              1.25858  |       1110 |
|            63 | control_sample_permuted_cnn         |       0.135231  |       0.917278 |     0.716216 |     0.895495 |     0.945045 |               0.953305 |              1.35318  |       1110 |
|            63 | mlp_heteroskedastic                 |       0.162924  |       0.912761 |     0.731532 |     0.912613 |     0.946847 |               1.1088   |              1.17907  |       1110 |
|            63 | control_shuffled_target_ridge       |       0.198964  |       0.897467 |     0.711712 |     0.931532 |     0.968468 |               1.74191  |              1.34029  |       1110 |
|            65 | traditional_stratified_robust_width |       0.0614284 |       0.998226 |     0.676768 |     0.888889 |     0.919192 |               1.18029  |              1.22768  |        198 |
|            65 | gradient_boosted_trees_conformal    |       0.0824282 |       1.03084  |     0.666667 |     0.878788 |     0.954545 |               0.98005  |              1.1258   |        198 |
|            65 | control_phase_scrambled_cnn         |       0.102033  |       0.977277 |     0.69697  |     0.929293 |     0.974747 |               1.10006  |              1.27957  |        198 |
|            65 | control_run_only_width              |       0.117451  |       0.933363 |     0.686869 |     0.914141 |     0.964646 |               1.78577  |              1.49464  |        198 |
|            65 | mlp_heteroskedastic                 |       0.134621  |       0.957767 |     0.70202  |     0.934343 |     0.974747 |               1.39772  |              1.52134  |        198 |
|            65 | control_shuffled_target_ridge       |       0.142196  |       0.955972 |     0.676768 |     0.949495 |     0.974747 |               1.79932  |              1.46046  |        198 |
|            65 | ridge_conformal                     |       0.181492  |       0.918914 |     0.722222 |     0.919192 |     0.979798 |               1.18937  |              1.41934  |        198 |
|            65 | cnn_1d_heteroskedastic              |       0.245839  |       0.848189 |     0.717172 |     0.929293 |     0.969697 |               1.05658  |              1.2966   |        198 |
|            65 | control_amplitude_only_ridge        |       0.275432  |       0.85303  |     0.717172 |     0.944444 |     0.989899 |               0.964663 |              1.43491  |        198 |
|            65 | control_sample_permuted_cnn         |       0.291933  |       0.827676 |     0.732323 |     0.929293 |     0.979798 |               1.08949  |              1.30687  |        198 |
|            65 | gated_waveform_tabular_cnn          |       0.305761  |       0.817986 |     0.752525 |     0.919192 |     0.969697 |               1.50337  |              1.20271  |        198 |

## 7. Falsification and leakage checks

Pre-registered falsifier: if a destroyed-signal control matched or beat all production methods, or if the traditional robust-width map remained statistically tied with the best ML method by the run-block CI, then the claim that waveform ML supplies useful calibrated sigma structure would not be supported.  The production winner is chosen before looking at controls, and controls are reported separately.

Falsification result: best control `control_shuffled_target_ridge` has primary score `0.0792` and does not beat the production winner. The traditional comparison is `winner_and_traditional_ci_overlap`; therefore the point-score winner is named, but the statistical claim is limited by the seven-run bootstrap interval.

|   heldout_run | check                          |   value | pass   | detail                                                                                                                                                            |
|--------------:|:-------------------------------|--------:|:-------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|            58 | feature_audit                  |      33 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            58 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            58 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            59 | feature_audit                  |      33 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            59 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            59 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            60 | feature_audit                  |      33 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            60 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            60 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            61 | feature_audit                  |      33 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            61 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            61 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            62 | feature_audit                  |      33 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            62 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            62 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            63 | feature_audit                  |      33 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            63 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            63 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            65 | feature_audit                  |      33 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            65 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            65 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |

## 8. Systematics and caveats

The target is a downstream closure residual, not an external truth time.  Therefore a common event-time fluctuation shared by all three staves is invisible.  The run-block bootstrap has only seven held-out blocks and should be read as a stability interval.  The traditional map has finite support in high-dimensional strata, so it uses predeclared hierarchical fallback rather than dropping sparse atoms.  Neural widths are conformally scaled using training residuals; this guards first-order miscalibration but cannot prove tail transport to future beam conditions.  The template-quality feature is a train-template SSE proxy, not the full S01 `q_template` artifact.

## 9. Verdict

`result.json` verdict: `ml_uncertainty_calibration_point_winner_ci_overlaps_traditional`. Point-score winner: `ridge_conformal`. Best control: `control_shuffled_target_ridge`. The benchmark covers ridge, gradient-boosted trees, MLP, 1D-CNN, and the new gated waveform-tabular CNN, all split by run with run-block bootstrap confidence intervals.

## 10. Reproducibility

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with torch --with pyyaml --with tabulate python scripts/s04f_1781039488_1240_043427d8_pull_width_calibration_map.py --config configs/s04f_1781039488_1240_043427d8_pull_width_calibration_map.yaml
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `downstream_counts_by_run.csv`, `heldout_run_summary.csv`, `pooled_method_summary.csv`, `heldout_pulse_predictions.csv.gz`, `analytic_cv_scan.csv`, `analytic_coefficients.csv`, `stratified_width_map.csv`, `leakage_checks.csv`, and PNG figures.
