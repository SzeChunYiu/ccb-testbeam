# S18j: A-stack ML transfer covariance gate

- **Ticket:** `1781038027.1393.695b00c5`
- **Worker:** `testbeam-laptop-3`
- **Raw input:** `/home/billy/ccb-data/extracted/root/root`
- **Input checksums:** `input_sha256.csv`
- **No Monte Carlo:** raw HRD ROOT only

## Question

Can the newest S18d/S18e-style A-stack ML timing gains be used as an external covariance gate for B-stack timing, or do calibration-pool and leakage-control failures make the transfer unsafe?

## Abstract

This study rebuilds the A-stack and B-stack coincidence tables from raw `HRDv` ROOT, then asks whether an A-stack timing gate can safely stratify B-stack pair covariance. The benchmark uses leave-one-run-held-out B-stack residuals and a run/pair bootstrap for confidence intervals. The method panel contains the requested strong traditional comparator and learned alternatives: ridge, gradient-boosted trees, S18e-style ExtraTrees, MLP, 1D-CNN, and a new support-gated CNN. Controls include waveform-only, pool-label-only, and shuffled-target fits.

The winner named in `result.json` is **extra_trees_s18e_style**, selected by lowest held-out B-stack mean absolute pair covariance among non-control methods. Its covariance is **39.483 ns^2**, versus **64.202 ns^2** for the traditional A-width gate Ridge and **228.535 ns^2** for pair-median centering. The primary safety verdict is **benchmark_winner_not_adopted_as_safe_gate**.

## Reproduction first

Raw ROOT anchors were rebuilt before the transfer test:

| quantity                             |     expected |   reproduced |       delta |   tolerance | pass   |
|:-------------------------------------|-------------:|-------------:|------------:|------------:|:-------|
| total_selected_b_pulses              | 640737       | 640737       | 0           |       0     | True   |
| sample_i_analysis_b_selected_pulses  | 252266       | 252266       | 0           |       0     | True   |
| sample_ii_analysis_b_selected_pulses | 125096       | 125096       | 0           |       0     | True   |
| sample_iv_a1_a3_pairs                |    127       |    127       | 0           |       0     | True   |
| sample_iv_a1_a3_robust_width_ns      |      1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |

## Methods

Runs are the split unit. Each B-stack analysis run is held out in turn; all B residual models and covariance predictors are fit without that run's B targets. Held-out A-stack robust summaries are allowed only as external same-run control observables.

Traditional: train-run B pair medians are retained as the non-parametric strong baseline. The A-stack transfer comparator is `traditional_a_width_gate_ridge`, a Ridge residual model using the frozen A-stack robust-width priors: percentile-68, MAD, IQR, trimmed sigma, Student-t width, A full RMS, and pair count, plus B-pair local amplitude/shape summaries. This implements the requested robust A1-A3 width transfer without low-statistics Gaussian-core selection.

ML/NN: `ridge`, `gradient_boosted_trees`, `extra_trees_s18e_style`, `mlp`, `cnn_1d`, and `support_gated_cnn_new` are trained on the same train runs and evaluated on the same held-out run. The 1D-CNN consumes left/right normalized waveforms and A-gate auxiliary features. The new support-gated CNN uses a learned sigmoid support gate on the convolutional representation, which is sensible here because A-to-B transfer should be suppressed when B waveform support does not match the A-stack gate support.

Controls: `waveform_only_mlp` removes A robust-width priors, `pool_label_control` uses only pair and run-family labels, and `ml_shuffled_target_control` shuffles training targets within the run-held-out fold.

## Estimands and equations

For B pair residuals, `r_ij = (t_j - t_i) - TOF_ij`. For method `m`, the held-out residual is `e_i(m)=r_i-hat r_m(x_i)`. The robust width is

`W_68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

For each run, residuals are pivoted to event by pair. The covariance gate metric is the mean absolute off-diagonal pair covariance:

`C_m = mean_{runs} mean_{p<q} |Cov(e_p(m), e_q(m))|`.

Width intervals resample held-out runs with replacement and pair rows within sampled runs. Covariance intervals resample precomputed per-run covariance values, which is the relevant run-block uncertainty for an external gate. A-gate calibration maps the A percentile-68 run score to the probability that the run is above-median in B pair-median covariance; Brier and three-bin ECE are reported as calibration diagnostics.

## Held-out residuals

| method                         | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                                                                              |
|:-------------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:------------------------------------------------------------------------------------------------------------------|
| pair_median                    | traditional    |         65484 |       21 |      2.0905  |             1.80436 |             11.2435  |      20.6803  |             16.8889  |               25.3417 |                   0.141775 |              0.366419 |                228.535  | strong traditional B-pair train-median centering                                                                  |
| traditional_a_width_gate_ridge | traditional    |         65484 |       21 |      8.27883 |             7.73873 |              9.21636 |      11.726   |             10.6822  |               13.1095 |                   0.514889 |              0.397131 |                 64.2021 | traditional A-width gate Ridge using A percentile/MAD/IQR/trimmed robust-width priors plus B pair shape summaries |
| ridge                          | ml             |         65484 |       21 |      7.96513 |             7.42403 |              8.87733 |      11.5144  |             10.6132  |               12.7504 |                   0.492639 |              0.370609 |                 59.3312 | standardized Ridge residual model with S18-style A robust-width priors                                            |
| gradient_boosted_trees         | ml             |         65484 |       21 |      3.91174 |             3.52697 |              6.2714  |      13.6082  |             12.1073  |               17.2182 |                   0.191894 |              0.333703 |                 87.9265 | histogram gradient-boosted tree residual model with B shape plus A gate priors                                    |
| extra_trees_s18e_style         | ml             |         65484 |       21 |      2.40688 |             2.20858 |              3.56647 |       9.17438 |              7.75435 |               11.4812 |                   0.172378 |              0.291357 |                 39.4829 | S18e-style ExtraTrees residual gate model with B shape plus A gate priors                                         |
| mlp                            | ml             |         65484 |       21 |      3.89349 |             3.51551 |              4.7585  |      19.8894  |             16.2404  |               28.1776 |                   0.195742 |              0.367747 |                215.87   | tabular MLP residual model with B shape plus A gate priors                                                        |
| cnn_1d                         | ml             |         65484 |       21 |      5.79738 |             4.36843 |              7.32699 |      20.5167  |             16.1282  |               24.8272 |                   0.370762 |              0.37685  |                234.164  | compact two-channel 1D-CNN over left/right waveforms with A gate auxiliaries                                      |
| support_gated_cnn_new          | ml             |         65484 |       21 |      4.88826 |             3.63552 |              8.9228  |      20.33    |             17.0332  |               29.5614 |                   0.307251 |              0.371429 |                228.154  | new support-gated residual CNN suppressing waveform corrections outside A/B support                               |
| waveform_only_mlp              | control        |         65484 |       21 |      3.88921 |             3.39497 |              9.51155 |      19.7032  |             17.8622  |               29.23   |                   0.218313 |              0.378737 |                221.301  | control: waveform-only MLP without A gate priors                                                                  |
| pool_label_control             | control        |         65484 |       21 |      6.38561 |             4.96002 |             16.7965  |      19.5712  |             16.4027  |               30.1853 |                   0.469382 |              0.366419 |                228.535  | control: pair and run-family/pool labels only                                                                     |
| ml_shuffled_target_control     | control        |         65484 |       21 |      4.99736 |             4.4627  |             16.8395  |      20.7523  |             17.335   |               26.4409 |                   0.31791  |              0.371384 |                232.288  | control: S18e-style ExtraTrees trained on shuffled targets                                                        |

Pair-median sigma68 is `2.091` ns with CI `[1.804, 11.244]`. The traditional A-width gate Ridge is `8.279` ns with CI `[7.739, 9.216]`. The winner `extra_trees_s18e_style` has sigma68 `2.407` ns with CI `[2.209, 3.566]`.

Winner-minus-pair-median delta: sigma68 `0.316` ns with CI `[-2.000, 0.520]`; covariance `-189.052` ns^2 with CI `[-237.070, -156.484]`.

Winner-minus-traditional-gate delta: sigma68 `-5.872` ns with CI `[-6.220, -5.681]`; covariance `-24.719` ns^2 with CI `[-28.021, -20.117]`.

Full paired deltas are in `method_delta_bootstrap.csv`:

| method                     | baseline                       | comparison                                                      |   delta_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   delta_mean_abs_pair_cov_ns2 |   cov_ci_low_ns2 |   cov_ci_high_ns2 |   p_two_sided_sigma68 |
|:---------------------------|:-------------------------------|:----------------------------------------------------------------|-------------------:|--------------------:|---------------------:|------------------------------:|-----------------:|------------------:|----------------------:|
| ridge                      | pair_median                    | ridge_minus_pair_median                                         |           5.87462  |            4.59357  |            6.40439   |                   -169.203    |   -217.877       |    -116.898       |                  0    |
| ridge                      | traditional_a_width_gate_ridge | ridge_minus_traditional_a_width_gate_ridge                      |          -0.313707 |           -0.634201 |            0.0454334 |                     -4.87093  |     -7.18687     |      -2.24218     |                  0.16 |
| gradient_boosted_trees     | pair_median                    | gradient_boosted_trees_minus_pair_median                        |           1.82123  |            1.57514  |            1.88851   |                   -140.608    |   -185.467       |    -116.975       |                  0    |
| gradient_boosted_trees     | traditional_a_width_gate_ridge | gradient_boosted_trees_minus_traditional_a_width_gate_ridge     |          -4.3671   |           -4.77158  |           -3.76387   |                     23.7244   |     14.6198      |      30.9072      |                  0    |
| extra_trees_s18e_style     | pair_median                    | extra_trees_s18e_style_minus_pair_median                        |           0.316375 |           -2.00048  |            0.520108  |                   -189.052    |   -237.07        |    -156.484       |                  0.16 |
| extra_trees_s18e_style     | traditional_a_width_gate_ridge | extra_trees_s18e_style_minus_traditional_a_width_gate_ridge     |          -5.87196  |           -6.22007  |           -5.68067   |                    -24.7193   |    -28.0206      |     -20.1168      |                  0    |
| mlp                        | pair_median                    | mlp_minus_pair_median                                           |           1.80299  |            0.100907 |            1.89846   |                    -12.6649   |    -19.1451      |      -9.30137     |                  0    |
| mlp                        | traditional_a_width_gate_ridge | mlp_minus_traditional_a_width_gate_ridge                        |          -4.38534  |           -4.93946  |           -0.881744  |                    151.668    |    111.221       |     180.108       |                  0.08 |
| cnn_1d                     | pair_median                    | cnn_1d_minus_pair_median                                        |           3.70687  |            1.91261  |            4.36315   |                      5.62912  |      0.265113    |       9.21307     |                  0    |
| cnn_1d                     | traditional_a_width_gate_ridge | cnn_1d_minus_traditional_a_width_gate_ridge                     |          -2.48146  |           -3.89269  |           -1.28017   |                    169.962    |    127.635       |     222.915       |                  0    |
| support_gated_cnn_new      | pair_median                    | support_gated_cnn_new_minus_pair_median                         |           2.79776  |            0.243637 |            2.92939   |                     -0.380511 |     -3.64671     |       2.43377     |                  0.08 |
| support_gated_cnn_new      | traditional_a_width_gate_ridge | support_gated_cnn_new_minus_traditional_a_width_gate_ridge      |          -3.39057  |           -4.0785   |            0.626662  |                    163.952    |    115.495       |     215.236       |                  0.08 |
| waveform_only_mlp          | pair_median                    | waveform_only_mlp_minus_pair_median                             |           1.79871  |            0.262338 |            1.86746   |                     -7.23362  |    -11.8882      |      -2.08044     |                  0.08 |
| waveform_only_mlp          | traditional_a_width_gate_ridge | waveform_only_mlp_minus_traditional_a_width_gate_ridge          |          -4.38962  |           -4.81558  |           -2.16834   |                    157.099    |    102.584       |     193.968       |                  0.08 |
| pool_label_control         | pair_median                    | pool_label_control_minus_pair_median                            |           4.2951   |            3.23883  |            7.21193   |                      0        |     -1.93978e-14 |       3.48166e-15 |                  0    |
| pool_label_control         | traditional_a_width_gate_ridge | pool_label_control_minus_traditional_a_width_gate_ridge         |          -1.89323  |           -2.90988  |            0.876033  |                    164.332    |    129.497       |     195.79        |                  0.48 |
| ml_shuffled_target_control | pair_median                    | ml_shuffled_target_control_minus_pair_median                    |           2.90686  |            1.05721  |            3.21455   |                      3.75382  |     -1.32966     |       8.66571     |                  0    |
| ml_shuffled_target_control | traditional_a_width_gate_ridge | ml_shuffled_target_control_minus_traditional_a_width_gate_ridge |          -3.28147  |           -3.53664  |            4.75378   |                    168.086    |    126.086       |     199.187       |                  0.08 |

## A-gate strata

The A percentile-68 run score defines low/mid/high A-width strata. This table shows whether covariance changes monotonically with the external gate:

| method                         | a_gate_stratum    |   n_runs |   n_pair_rows |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_abs_pair_cov_ns2 |   cov_ci_low_ns2 |   cov_ci_high_ns2 |   correlated_fraction |
|:-------------------------------|:------------------|---------:|--------------:|-------------:|--------------------:|---------------------:|------------------------:|-----------------:|------------------:|----------------------:|
| pair_median                    | all               |       21 |         65484 |      2.0905  |             1.80546 |             10.9393  |                228.535  |         187.884  |          292.882  |              0.366419 |
| pair_median                    | high_A_width_gate |        7 |         17750 |      2.00708 |             1.71145 |             27.6836  |                250.568  |         142.583  |          340.929  |              0.3829   |
| pair_median                    | low_A_width_gate  |        7 |         25722 |      2.01628 |             1.69861 |             36.2799  |                228.768  |         182.322  |          326.344  |              0.35507  |
| pair_median                    | mid_A_width_gate  |        7 |         22012 |      2.25898 |             1.94232 |             18.7269  |                202.557  |         148.728  |          271.479  |              0.358207 |
| traditional_a_width_gate_ridge | all               |       21 |         65484 |      8.27883 |             7.72114 |             10.0522  |                 64.2021 |          54.4769 |           79.0874 |              0.397131 |
| traditional_a_width_gate_ridge | high_A_width_gate |        7 |         17750 |      8.69204 |             8.1689  |             12.4819  |                 61.0533 |          49.9583 |           71.0738 |              0.387545 |
| traditional_a_width_gate_ridge | low_A_width_gate  |        7 |         25722 |      7.67675 |             7.14675 |             12.5153  |                 68.7376 |          39.9716 |          103.781  |              0.405779 |
| traditional_a_width_gate_ridge | mid_A_width_gate  |        7 |         22012 |      8.64529 |             7.82664 |             10.5139  |                 62.5844 |          46.4257 |           80.4593 |              0.39718  |
| ridge                          | all               |       21 |         65484 |      7.96513 |             7.40578 |              8.60894 |                 59.3312 |          50.9525 |           71.1467 |              0.370609 |
| ridge                          | high_A_width_gate |        7 |         17750 |      8.76869 |             7.32619 |             12.2448  |                 59.0735 |          50.5383 |           69.7849 |              0.358566 |
| ridge                          | low_A_width_gate  |        7 |         25722 |      7.446   |             6.51629 |              9.34191 |                 60.1792 |          43.2087 |           80.3078 |              0.373325 |
| ridge                          | mid_A_width_gate  |        7 |         22012 |      7.94967 |             7.04536 |             10.1607  |                 58.6426 |          40.4863 |           78.4159 |              0.381916 |
| gradient_boosted_trees         | all               |       21 |         65484 |      3.91174 |             3.60676 |             10.3389  |                 87.9265 |          72.9448 |          104.012  |              0.333703 |
| gradient_boosted_trees         | high_A_width_gate |        7 |         17750 |      3.64297 |             3.18333 |             18.032   |                 88.8645 |          62.2941 |          112.028  |              0.320686 |
| gradient_boosted_trees         | low_A_width_gate  |        7 |         25722 |      3.88581 |             3.51507 |             14.5519  |                 91.3605 |          65.7462 |          119.132  |              0.327205 |
| gradient_boosted_trees         | mid_A_width_gate  |        7 |         22012 |      4.08043 |             3.77247 |             15.8478  |                 82.8258 |          43.5509 |          114.527  |              0.359842 |
| extra_trees_s18e_style         | all               |       21 |         65484 |      2.40688 |             2.13493 |              3.22871 |                 39.4829 |          30.4738 |           45.8711 |              0.291357 |
| extra_trees_s18e_style         | high_A_width_gate |        7 |         17750 |      2.48085 |             2.04908 |              8.83569 |                 39.2808 |          30.0113 |           49.212  |              0.257777 |
| extra_trees_s18e_style         | low_A_width_gate  |        7 |         25722 |      2.26562 |             2.02743 |              7.57879 |                 40.9835 |          25.6685 |           67.5628 |              0.289288 |
| extra_trees_s18e_style         | mid_A_width_gate  |        7 |         22012 |      2.52215 |             2.02708 |              5.42026 |                 37.9679 |          19.1662 |           60.5422 |              0.347131 |
| mlp                            | all               |       21 |         65484 |      3.89349 |             3.50773 |              6.57237 |                215.87   |         176.389  |          267.102  |              0.367747 |
| mlp                            | high_A_width_gate |        7 |         17750 |      3.56088 |             2.99984 |             29.9598  |                241.239  |         155.583  |          325.343  |              0.388346 |
| mlp                            | low_A_width_gate  |        7 |         25722 |      3.86125 |             3.51074 |             31.5486  |                210.881  |         118.979  |          292.041  |              0.350986 |
| mlp                            | mid_A_width_gate  |        7 |         22012 |      4.10876 |             3.54332 |             16.7559  |                192.092  |          99.2514 |          276.825  |              0.360729 |
| cnn_1d                         | all               |       21 |         65484 |      5.79738 |             4.291   |             14.1206  |                234.164  |         178.481  |          281.138  |              0.37685  |
| cnn_1d                         | high_A_width_gate |        7 |         17750 |      4.51257 |             3.65225 |             31.8514  |                260.71   |         175.99   |          360.106  |              0.396605 |
| cnn_1d                         | low_A_width_gate  |        7 |         25722 |      6.82192 |             4.40806 |             34.6433  |                232.338  |         164.996  |          326.03   |              0.364723 |
| cnn_1d                         | mid_A_width_gate  |        7 |         22012 |      5.16038 |             3.87661 |             25.5051  |                205.323  |         148.727  |          284.554  |              0.364852 |
| support_gated_cnn_new          | all               |       21 |         65484 |      4.88826 |             4.32487 |              7.93963 |                228.154  |         178.27   |          283.161  |              0.371429 |
| support_gated_cnn_new          | high_A_width_gate |        7 |         17750 |      3.79589 |             3.03301 |             27.2412  |                254.866  |         169.328  |          344.27   |              0.39089  |
| support_gated_cnn_new          | low_A_width_gate  |        7 |         25722 |      4.55547 |             3.77929 |             30.8483  |                225.739  |         118.681  |          313.792  |              0.355861 |
| support_gated_cnn_new          | mid_A_width_gate  |        7 |         22012 |      5.14511 |             3.86092 |             22.8856  |                199.809  |          94.2539 |          297.427  |              0.364212 |

## A-gate calibration

| gate                      | target                                              |   n_runs |    brier |      ece |   positive_rate |   score_min |   score_max |
|:--------------------------|:----------------------------------------------------|---------:|---------:|---------:|----------------:|------------:|------------:|
| A_percentile68_width_rank | above_median_B_pair_median_mean_abs_pair_covariance |       20 | 0.386281 | 0.350339 |             0.5 |           0 |           1 |

## Covariance transfer

Run-level covariance interval coverage:

| method                         | target              |   coverage |
|:-------------------------------|:--------------------|-----------:|
| ml_extratrees_covariance       | correlated_fraction |   0.4      |
| ml_extratrees_covariance       | sigma68             |   0.428571 |
| traditional_a_width_covariance | correlated_fraction |   0.65     |
| traditional_a_width_covariance | sigma68             |   0.761905 |

Per-held-out-run predictions are in `run_level_covariance_predictions.csv`. The A-width-only traditional covariance model is the direct transfer test; the ML covariance model adds B pulse summaries and is more flexible but not treated as independent evidence if leakage checks fail.

## Leakage checks

| check                                       | value                | flag   |
|:--------------------------------------------|:---------------------|:-------|
| forbidden_feature_overlap                   |                      | False  |
| train_heldout_run_overlap                   | 0.0                  | False  |
| nominal_width_minus_shuffled_control_ns     | -0.10909611097971617 | True   |
| nominal_width_minus_pool_label_control_ns   | -1.4973447196036682  | False  |
| nominal_cov_minus_waveform_only_control_ns2 | 6.8531135975082975   | True   |
| random_row_split_r2                         | 0.9188966649211275   | False  |
| group_cv_ridge_rmse_ns                      | 11.214087789402859   | False  |

Control metrics:

| method                     | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                       |
|:---------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:-----------------------------------------------------------|
| waveform_only_mlp          | control        |         65484 |       21 |      3.88921 |             3.39497 |              9.51155 |       19.7032 |              17.8622 |               29.23   |                   0.218313 |              0.378737 |                 221.301 | control: waveform-only MLP without A gate priors           |
| pool_label_control         | control        |         65484 |       21 |      6.38561 |             4.96002 |             16.7965  |       19.5712 |              16.4027 |               30.1853 |                   0.469382 |              0.366419 |                 228.535 | control: pair and run-family/pool labels only              |
| ml_shuffled_target_control | control        |         65484 |       21 |      4.99736 |             4.4627  |             16.8395  |       20.7523 |              17.335  |               26.4409 |                   0.31791  |              0.371384 |                 232.288 | control: S18e-style ExtraTrees trained on shuffled targets |

## Conclusion

The A-stack robust-width priors are useful as weak external controls, but they are not by themselves a secure B-stack covariance gate. The learned winner improves the held-out covariance point estimate, yet the adoption decision is gated by the shuffled-target, pool-label, waveform-only, and run-split controls plus the A-gate calibration diagnostics. The result is therefore a benchmark winner, not an unconditional recommendation to use A-stack ML timing as a production B-stack covariance gate.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `astack_run_summaries.csv`, `bstack_pair_table_preview.csv`, `heldout_pair_residuals.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `gate_stratum_summary.csv`, `a_gate_calibration.csv`, `run_level_covariance_predictions.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
