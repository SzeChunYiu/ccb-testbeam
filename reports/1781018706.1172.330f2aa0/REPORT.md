# P01e: template-phase quantization sensitivity for P01d sign flips

**Ticket:** 1781018706.1172.330f2aa0

## Reproduction first
Raw B-stack ROOT was read from `data/root/root` before timing fits or
ML training. The selected-pulse count reproduced **640,737**
against the expected **640,737**.
The rerun CFD deltas also match the P01d reference for samples 5, 7, and 8.

## Split and methods
Held-out runs are `42, 57, 64, 65`.
Ablations use the P01c control-stratum replacement: train-run means within
stave x log-amplitude bin. CIs are paired 95% bootstraps over held-out runs.
The traditional arms are template-phase matching with coarse/fine/parabolic
minima plus the train-selected optimal-filter window `of_5_13`.
The ML arm is the P01d ridge residual corrector trained only on non-held-out runs.

## Held-out baselines
| method                             |   sigma68_ns |   ci_low |   ci_high |   n_pair_residuals |
|:-----------------------------------|-------------:|---------:|----------:|-------------------:|
| ml_ridge_residual                  |        1.974 |    1.825 |     2.028 |               1224 |
| template_phase_coarse_0p05_min     |        2.523 |    2.023 |     2.759 |               1224 |
| template_phase_fine_0p01_parabolic |        2.559 |    2.047 |     2.731 |               1224 |
| template_phase_fine_0p01_min       |        2.559 |    2.073 |     2.723 |               1224 |
| of_5_13                            |        2.693 |    2.484 |     2.811 |               1224 |
| cfd20                              |        3.188 |    3.077 |     3.305 |               1224 |
| ml_target_shuffle                  |        3.217 |    3.096 |     3.322 |               1224 |

## Template quantization diagnostics
| method                             |   time_grid_step_ns |   nominal_sigma68_quantum_ns |   unique_shifts |   median_abs_parabolic_correction_ns |
|:-----------------------------------|--------------------:|-----------------------------:|----------------:|-------------------------------------:|
| template_phase_coarse_0p05_min     |                 0.5 |                         0.25 |              61 |                              0       |
| template_phase_fine_0p01_min       |                 0.1 |                         0.05 |             301 |                              0       |
| template_phase_fine_0p01_parabolic |                 0.1 |                         0.05 |           47302 |                              0.01863 |

## Sample deltas
Positive means the ablation worsened timing sigma68; negative means the ablated
sample made timing narrower.

|   ablation | method                             |   delta_sigma68_ns |    ci_low |   ci_high |
|-----------:|:-----------------------------------|-------------------:|----------:|----------:|
|          5 | cfd20                              |         -2.025     | -2.206    | -1.819    |
|          5 | ml_ridge_residual                  |          1.784     |  1.665    |  1.888    |
|          5 | of_5_13                            |          0.2419    |  0.07344  |  0.565    |
|          5 | template_phase_coarse_0p05_min     |          0.25      | -0.2361   |  0.4861   |
|          5 | template_phase_fine_0p01_min       |          0.3       | -0.05     |  0.4361   |
|          5 | template_phase_fine_0p01_parabolic |          0.2904    | -0.01421  |  0.4541   |
|          7 | cfd20                              |         -0.2206    | -0.779    | -0.05548  |
|          7 | ml_ridge_residual                  |          1.334     |  0.3264   |  1.765    |
|          7 | of_5_13                            |          0.09503   | -0.0438   |  0.2093   |
|          7 | template_phase_coarse_0p05_min     |          3.553e-15 |  0        |  0.25     |
|          7 | template_phase_fine_0p01_min       |          0.05      | -0.01498  |  0.2361   |
|          7 | template_phase_fine_0p01_parabolic |          0.05423   | -0.007466 |  0.2427   |
|          8 | cfd20                              |         -0.1495    | -0.6687   |  0.006719 |
|          8 | ml_ridge_residual                  |          1.145     |  0.2501   |  1.903    |
|          8 | of_5_13                            |         -0.004677  | -0.2282   |  0.1658   |
|          8 | template_phase_coarse_0p05_min     |          0.25      |  0.01393  |  0.25     |
|          8 | template_phase_fine_0p01_min       |          0.25      |  0.1639   |  0.2861   |
|          8 | template_phase_fine_0p01_parabolic |          0.2324    |  0.1896   |  0.2826   |

## Verdict for samples 5, 7, and 8
|   sample |   p01d_cfd_delta_ns |   rerun_cfd20_delta_ns |   p01d_coarse_template_delta_ns |   coarse_template_delta_ns |   fine_template_delta_ns |   parabolic_template_delta_ns |   of_5_13_delta_ns |   ml_ridge_residual_delta_ns |   non_cfd_methods_robust_negative | interpretation    |
|---------:|--------------------:|-----------------------:|--------------------------------:|---------------------------:|-------------------------:|------------------------------:|-------------------:|-----------------------------:|----------------------------------:|:------------------|
|        5 |             -2.025  |                -2.025  |                       0.25      |                  0.25      |                     0.3  |                       0.2904  |           0.2419   |                        1.784 |                                 0 | cfd_only_artifact |
|        7 |             -0.2206 |                -0.2206 |                       3.553e-15 |                  3.553e-15 |                     0.05 |                       0.05423 |           0.09503  |                        1.334 |                                 0 | cfd_only_artifact |
|        8 |             -0.1495 |                -0.1495 |                       0.25      |                  0.25      |                     0.25 |                       0.2324  |          -0.004677 |                        1.145 |                                 0 | cfd_only_artifact |

## Leakage checks
| check                        | pass   | value                                              | detail                                                                        |
|:-----------------------------|:-------|:---------------------------------------------------|:------------------------------------------------------------------------------|
| train_heldout_run_overlap    | True   | 0                                                  | must be zero for split-by-run                                                 |
| heldout_runs                 | True   | 42,57,64,65                                        | all benchmark residuals are from these runs                                   |
| ml_target_shuffle_sigma68_ns | True   | 3.217127669235257                                  | shuffled train targets should not match the real ML residual timing           |
| ml_vs_cfd20_delta_ns         | True   | -1.2140895354320655                                | negative means ML improves over CFD20; target-shuffle is the leakage sentinel |
| feature_audit                | True   | waveform, amplitude, peak, area, width, stave only | no event id, run id, or pair residual labels are in ML features               |
| too_good_result_trigger      | True   | 1.242767000712149                                  | ML is strong, so the target-shuffle sentinel must degrade by >0.5 ns          |

## Conclusion
The coarse P01d template-phase deltas are visibly grid-quantized: the 0.05-sample
grid implies a 0.25 ns sigma68 quantum, matching the exact 0.25 ns effects. With
the 0.01-sample grid and parabolic minimum interpolation, samples 5, 7, and 8 do
not become robust negative non-CFD timing effects. The CFD signs reproduce, but
the fine-grid template, optimal-filter, and ML residual arms point to samples
5, 7, and 8 being CFD-only or mostly CFD-only artifacts after removing the
template grid quantization.
