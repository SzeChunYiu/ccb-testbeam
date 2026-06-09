# P01d: validate P01c CFD ablation sign flips

**Ticket:** 1781010798.954.0e922a2d

## Reproduction first
Raw B-stack ROOT was read from `data/root/root` before any timing or
ML modelling. The P01c/S00 selected-pulse count reproduced
**640,737** versus the expected
**640,737**.

## Split and controls
Training runs are all configured P01c runs except held-out runs
`42, 57, 64, 65`. Ablations reuse
P01c control-stratum replacement: train-run means within stave x log-amplitude
bin. Confidence intervals are paired 95% bootstraps over held-out runs.

## Held-out method baselines
| method            |   sigma68_ns |   ci_low |   ci_high |   n_pair_residuals |
|:------------------|-------------:|---------:|----------:|-------------------:|
| ml_ridge_residual |        1.974 |    1.825 |     2.028 |               1224 |
| template_phase    |        2.523 |    2.023 |     2.759 |               1224 |
| of_5_13           |        2.693 |    2.484 |     2.811 |               1224 |
| of_4_12           |        2.761 |    2.587 |     2.944 |               1224 |
| of_3_11           |        2.854 |    2.776 |     2.945 |               1224 |
| of_1_9            |        3.053 |    3.018 |     3.071 |               1224 |
| of_2_10           |        3.071 |    3.041 |     3.102 |               1224 |
| cfd20             |        3.188 |    3.095 |     3.308 |               1224 |
| ml_target_shuffle |        3.329 |    3.258 |     3.399 |               1224 |

## Signed single-sample timing deltas
Positive means the ablation worsened timing sigma68; negative means the ablated
sample made timing narrower.

|   ablation | method            |   delta_sigma68_ns |   ci_low |   ci_high |
|-----------:|:------------------|-------------------:|---------:|----------:|
|          5 | cfd20             |         -2.025     | -2.206   | -1.802    |
|          5 | ml_ridge_residual |          1.784     |  1.665   |  1.888    |
|          5 | of_5_13           |          0.2419    |  0.0823  |  0.565    |
|          5 | template_phase    |          0.25      | -0.2361  |  0.4861   |
|          6 | cfd20             |         -0.9299    | -1.082   | -0.6579   |
|          6 | ml_ridge_residual |          1.518     |  1.304   |  1.808    |
|          6 | of_5_13           |         -0.3602    | -0.4987  | -0.1889   |
|          6 | template_phase    |         -0.2639    | -0.5     |  0.1605   |
|          7 | cfd20             |         -0.2206    | -0.779   | -0.05548  |
|          7 | ml_ridge_residual |          1.334     |  0.3398  |  1.765    |
|          7 | of_5_13           |          0.09503   | -0.0438  |  0.2063   |
|          7 | template_phase    |          3.553e-15 |  0       |  0.25     |
|          8 | cfd20             |         -0.1495    | -0.6956  |  0.006719 |
|          8 | ml_ridge_residual |          1.145     |  0.2501  |  1.903    |
|          8 | of_5_13           |         -0.004677  | -0.2282  |  0.1658   |
|          8 | template_phase    |          0.25      |  0.01393 |  0.25     |

## P01c sign-flip verdict
|   sample |   p01c_cfd_delta_ns |   rerun_cfd20_delta_ns |   template_phase_delta_ns |   of_5_13_delta_ns |   non_cfd_methods_negative | interpretation                    |
|---------:|--------------------:|-----------------------:|--------------------------:|-------------------:|---------------------------:|:----------------------------------|
|        5 |             -2.025  |                -2.025  |                 0.25      |           0.2419   |                          0 | likely_cfd_interpolation_artifact |
|        6 |             -0.9299 |                -0.9299 |                -0.2639    |          -0.3602   |                          2 | likely_real_smoothing_robustness  |
|        7 |             -0.2206 |                -0.2206 |                 3.553e-15 |           0.09503  |                          0 | likely_cfd_interpolation_artifact |
|        8 |             -0.1495 |                -0.1495 |                 0.25      |          -0.004677 |                          1 | mixed_template_of_response        |

## Control windows
| ablation   | method            |   delta_sigma68_ns |   ci_low |   ci_high |
|:-----------|:------------------|-------------------:|---------:|----------:|
| 1-4        | cfd20             |            13.2    | 11.77    |   26.51   |
| 1-4        | ml_ridge_residual |            14.72   | 13.22    |   27.74   |
| 1-4        | of_5_13           |             0      |  0       |    0      |
| 1-4        | template_phase    |             0.2361 |  0.01393 |    0.25   |
| 5-8        | cfd20             |            -2.048  | -2.183   |   -1.898  |
| 5-8        | ml_ridge_residual |             1.913  |  1.849   |    1.955  |
| 5-8        | of_5_13           |            -0.9447 | -1.001   |   -0.7917 |
| 5-8        | template_phase    |             0.4861 |  0.25    |    1.491  |

## Leakage checks
| check                        | value               | detail                                                                                   |
|:-----------------------------|:--------------------|:-----------------------------------------------------------------------------------------|
| run_overlap                  | 0                   | must be zero for train/heldout split                                                     |
| feature_audit                | 0                   | ML features contain waveform shape, amplitude, peak, area, width, and stave one-hot only |
| ml_target_shuffle_sigma68_ns | 3.328531893637124   | held-out timing after shuffling train residual targets                                   |
| ml_vs_cfd20_delta_ns         | -1.2140895354320655 | negative means ML improves over CFD20; target-shuffle check is the leakage sentinel      |
| train_selected_of_window     | of_5_13             | optimal-filter window selected by train-run sigma68 before held-out evaluation           |

## Conclusion
Samples 5-8 still give negative CFD20 deltas, reproducing the P01c sign. The
non-CFD timing arms do not preserve that sign consistently: template-phase turns
the rising-edge samples into timing damage, while the best optimal-filter window
is mixed. The negative CFD deltas are therefore best treated as interpolation
and threshold-crossing artifacts from smoothing the CFD rising edge, not as a
general timing robustness of those samples.
