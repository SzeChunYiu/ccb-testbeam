# S18k: Fixed-efficiency A-gate covariance transfer

- **Ticket:** `1781125119.10600.08d70fd7`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** `/home/billy/ccb-data/extracted/root/root`
- **Input checksums:** `input_sha256.csv`
- **No Monte Carlo:** raw HRD ROOT only

## Question

Repeat S18j with per-run fixed-efficiency A-stack gates and a blinded B-stack covariance endpoint, so the A-gate threshold is determined without looking at B covariance and the control-gap/adoption rule is tested prospectively.

## Abstract

This study rebuilds the A-stack and B-stack coincidence tables from raw `HRDv` ROOT, then asks whether a per-run fixed-efficiency A-stack timing gate can safely stratify a blinded B-stack pair-covariance endpoint. The A threshold is computed from A1/A3 amplitudes within each run before any B covariance is evaluated. The benchmark uses leave-one-run-held-out B-stack residuals and a run/pair bootstrap for confidence intervals. The method panel contains the requested strong traditional comparator and learned alternatives: ridge, gradient-boosted trees, S18e-style ExtraTrees, MLP, 1D-CNN, and a new support-gated CNN. Controls include waveform-only, pool-label-only, and shuffled-target fits.

The winner named in `result.json` is **extra_trees_s18e_style**, selected by lowest held-out B-stack mean absolute pair covariance among non-control methods. Its covariance is **37.961 ns^2**, versus **64.206 ns^2** for the traditional A-width gate Ridge and **228.535 ns^2** for pair-median centering. The primary safety verdict is **benchmark_winner_not_adopted_as_safe_gate**.

## Reproduction first

Raw ROOT anchors were rebuilt before the transfer test:

| quantity                                         |    expected |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------------------|------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses                          | 640737      |  640737      |       0 |       0     | True   |
| sample_i_analysis_b_selected_pulses              | 252266      |  252266      |       0 |       0     | True   |
| sample_ii_analysis_b_selected_pulses             | 125096      |  125096      |       0 |       0     | True   |
| fixed_efficiency_reference_events                | 798651      |  798651      |       0 |       0     | True   |
| fixed_efficiency_reference_pairs                 |   6377      |    6377      |       0 |       0     | True   |
| sample_iv_fixed_efficiency_a1_a3_pairs           |   2110      |    2110      |       0 |       0     | True   |
| sample_iv_fixed_efficiency_a1_a3_robust_width_ns |     39.7132 |      39.7132 |       0 |       1e+06 | True   |

## Methods

Runs are the split unit. Each B-stack analysis run is held out in turn; all B residual models and covariance predictors are fit without that run's B targets. Held-out A-stack robust summaries are allowed only as external same-run control observables.

Traditional: train-run B pair medians are retained as the non-parametric strong baseline. The A-stack transfer comparator is `traditional_a_width_gate_ridge`, a Ridge residual model using the fixed-efficiency A-stack robust-width priors: percentile-68, MAD, IQR, trimmed sigma, Student-t width, A full RMS, and pair count, plus B-pair local amplitude/shape summaries. This implements the requested blinded A1-A3 width transfer without low-statistics Gaussian-core selection.

ML/NN: `ridge`, `gradient_boosted_trees`, `extra_trees_s18e_style`, `mlp`, `cnn_1d`, and `support_gated_cnn_new` are trained on the same train runs and evaluated on the same held-out run. The 1D-CNN consumes left/right normalized waveforms and A-gate auxiliary features. The new support-gated CNN uses a learned sigmoid support gate on the convolutional representation, which is sensible here because A-to-B transfer should be suppressed when B waveform support does not match the A-stack gate support.

Controls: `waveform_only_mlp` removes A robust-width priors, `pool_label_control` uses only pair and run-family labels, and `ml_shuffled_target_control` shuffles training targets within the run-held-out fold.

## Estimands and equations

For run `u`, the fixed-efficiency A gate computes `s_i=min(A1_i,A3_i)` and chooses threshold `tau_u` as the empirical `(1-efficiency)` quantile over all A events in that run; A pairs with `s_i >= tau_u` enter the A-stack run summary. For B pair residuals, `r_ij = (t_j - t_i) - TOF_ij`. For method `m`, the held-out residual is `e_i(m)=r_i-hat r_m(x_i)`. The robust width is

`W_68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

For each run, residuals are pivoted to event by pair. The covariance gate metric is the mean absolute off-diagonal pair covariance:

`C_m = mean_{runs} mean_{p<q} |Cov(e_p(m), e_q(m))|`.

Width intervals resample held-out runs with replacement and pair rows within sampled runs. Covariance intervals resample precomputed per-run covariance values, which is the relevant run-block uncertainty for an external gate. A-gate calibration maps the A percentile-68 run score to the probability that the run is above-median in B pair-median covariance; Brier and three-bin ECE are reported as calibration diagnostics.

## Held-out residuals

| method                         | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                                                                              |
|:-------------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:------------------------------------------------------------------------------------------------------------------|
| pair_median                    | traditional    |         65484 |       21 |      2.0905  |             1.80436 |             11.2435  |      20.6803  |             16.8889  |               25.3417 |                   0.141775 |              0.366419 |                228.535  | strong traditional B-pair train-median centering                                                                  |
| traditional_a_width_gate_ridge | traditional    |         65484 |       21 |      8.33937 |             7.78748 |              9.27449 |      11.7191  |             10.6362  |               13.0445 |                   0.517424 |              0.397272 |                 64.2061 | traditional A-width gate Ridge using A percentile/MAD/IQR/trimmed robust-width priors plus B pair shape summaries |
| ridge                          | ml             |         65484 |       21 |      7.87268 |             7.43303 |              8.74069 |      11.4943  |             10.5598  |               12.712  |                   0.4918   |              0.371138 |                 59.3921 | standardized Ridge residual model with S18-style A robust-width priors                                            |
| gradient_boosted_trees         | ml             |         65484 |       21 |      3.91173 |             3.52697 |              6.27141 |      13.6109  |             12.1093  |               17.2228 |                   0.191925 |              0.333672 |                 87.943  | histogram gradient-boosted tree residual model with B shape plus A gate priors                                    |
| extra_trees_s18e_style         | ml             |         65484 |       21 |      2.38046 |             2.15857 |              3.59897 |       9.11773 |              7.68006 |               11.3749 |                   0.170255 |              0.286267 |                 37.9614 | S18e-style ExtraTrees residual gate model with B shape plus A gate priors                                         |
| mlp                            | ml             |         65484 |       21 |      3.85622 |             3.51798 |              4.63585 |      19.8226  |             16.1682  |               28.1288 |                   0.199774 |              0.365971 |                214.458  | tabular MLP residual model with B shape plus A gate priors                                                        |
| cnn_1d                         | ml             |         65484 |       21 |      6.58279 |             4.4427  |              7.46381 |      20.5364  |             16.25    |               24.5243 |                   0.407138 |              0.371273 |                230.042  | compact two-channel 1D-CNN over left/right waveforms with A gate auxiliaries                                      |
| support_gated_cnn_new          | ml             |         65484 |       21 |      4.828   |             3.58526 |              9.1712  |      20.3431  |             17.1279  |               29.5142 |                   0.301448 |              0.372338 |                230.204  | new support-gated residual CNN suppressing waveform corrections outside A/B support                               |
| waveform_only_mlp              | control        |         65484 |       21 |      3.88921 |             3.39497 |              9.51155 |      19.7032  |             17.8622  |               29.23   |                   0.218313 |              0.378737 |                221.301  | control: waveform-only MLP without A gate priors                                                                  |
| pool_label_control             | control        |         65484 |       21 |      6.38561 |             4.96002 |             16.7965  |      19.5712  |             16.4027  |               30.1853 |                   0.469382 |              0.366419 |                228.535  | control: pair and run-family/pool labels only                                                                     |
| ml_shuffled_target_control     | control        |         65484 |       21 |      4.96262 |             4.53965 |             17.0351  |      20.7074  |             17.2131  |               26.4973 |                   0.310656 |              0.370335 |                230.957  | control: S18e-style ExtraTrees trained on shuffled targets                                                        |

Pair-median sigma68 is `2.091` ns with CI `[1.804, 11.244]`. The traditional A-width gate Ridge is `8.339` ns with CI `[7.787, 9.274]`. The winner `extra_trees_s18e_style` has sigma68 `2.380` ns with CI `[2.159, 3.599]`.

Winner-minus-pair-median delta: sigma68 `0.290` ns with CI `[-1.954, 0.524]`; covariance `-190.573` ns^2 with CI `[-238.066, -157.747]`.

Winner-minus-traditional-gate delta: sigma68 `-5.959` ns with CI `[-6.316, -5.736]`; covariance `-26.245` ns^2 with CI `[-31.193, -20.727]`.

Full paired deltas are in `method_delta_bootstrap.csv`:

| method                     | baseline                       | comparison                                                      |   delta_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   delta_mean_abs_pair_cov_ns2 |   cov_ci_low_ns2 |   cov_ci_high_ns2 |   p_two_sided_sigma68 |
|:---------------------------|:-------------------------------|:----------------------------------------------------------------|-------------------:|--------------------:|---------------------:|------------------------------:|-----------------:|------------------:|----------------------:|
| ridge                      | pair_median                    | ridge_minus_pair_median                                         |           5.78218  |            4.24998  |             6.10378  |                    -169.142   |    -217.729      |    -116.862       |                  0    |
| ridge                      | traditional_a_width_gate_ridge | ridge_minus_traditional_a_width_gate_ridge                      |          -0.466686 |           -0.811721 |            -0.122546 |                      -4.81398 |      -7.14669    |      -2.20746     |                  0    |
| gradient_boosted_trees     | pair_median                    | gradient_boosted_trees_minus_pair_median                        |           1.82123  |            1.575    |             1.88872  |                    -140.592   |    -185.427      |    -116.939       |                  0    |
| gradient_boosted_trees     | traditional_a_width_gate_ridge | gradient_boosted_trees_minus_traditional_a_width_gate_ridge     |          -4.42764  |           -4.79889  |            -3.73132  |                      23.7369  |      14.6748     |      30.8755      |                  0    |
| extra_trees_s18e_style     | pair_median                    | extra_trees_s18e_style_minus_pair_median                        |           0.289957 |           -1.95352  |             0.524104 |                    -190.573   |    -238.066      |    -157.747       |                  0.16 |
| extra_trees_s18e_style     | traditional_a_width_gate_ridge | extra_trees_s18e_style_minus_traditional_a_width_gate_ridge     |          -5.95891  |           -6.31633  |            -5.73587  |                     -26.2447  |     -31.1932     |     -20.7269      |                  0    |
| mlp                        | pair_median                    | mlp_minus_pair_median                                           |           1.76572  |            0.117328 |             1.8724   |                     -14.0762  |     -20.3207     |     -10.0439      |                  0    |
| mlp                        | traditional_a_width_gate_ridge | mlp_minus_traditional_a_width_gate_ridge                        |          -4.48315  |           -5.06835  |            -0.930772 |                     150.252   |     108.751      |     176.64        |                  0.08 |
| cnn_1d                     | pair_median                    | cnn_1d_minus_pair_median                                        |           4.49229  |            1.26868  |             5.54607  |                       1.5078  |      -6.0205     |       4.99418     |                  0    |
| cnn_1d                     | traditional_a_width_gate_ridge | cnn_1d_minus_traditional_a_width_gate_ridge                     |          -1.75658  |           -3.69473  |            -1.01695  |                     165.836   |     125.634      |     218.794       |                  0    |
| support_gated_cnn_new      | pair_median                    | support_gated_cnn_new_minus_pair_median                         |           2.73749  |            0.292737 |             3.25938  |                       1.66989 |      -2.44498    |       7.46684     |                  0.08 |
| support_gated_cnn_new      | traditional_a_width_gate_ridge | support_gated_cnn_new_minus_traditional_a_width_gate_ridge      |          -3.51137  |           -4.33585  |             1.15725  |                     165.998   |     119.271      |     213.357       |                  0.08 |
| waveform_only_mlp          | pair_median                    | waveform_only_mlp_minus_pair_median                             |           1.79871  |            0.262338 |             1.86746  |                      -7.23362 |     -11.8882     |      -2.08044     |                  0.08 |
| waveform_only_mlp          | traditional_a_width_gate_ridge | waveform_only_mlp_minus_traditional_a_width_gate_ridge          |          -4.45016  |           -4.89296  |            -2.17694  |                     157.095   |     102.593      |     193.98        |                  0.08 |
| pool_label_control         | pair_median                    | pool_label_control_minus_pair_median                            |           4.2951   |            3.23883  |             7.21193  |                       0       |      -1.3749e-14 |       1.10845e-14 |                  0    |
| pool_label_control         | traditional_a_width_gate_ridge | pool_label_control_minus_traditional_a_width_gate_ridge         |          -1.95376  |           -2.99267  |             0.780901 |                     164.329   |     129.519      |     195.789       |                  0.48 |
| ml_shuffled_target_control | pair_median                    | ml_shuffled_target_control_minus_pair_median                    |           2.87212  |            1.12178  |             2.99352  |                       2.42266 |      -2.35019    |       7.60117     |                  0    |
| ml_shuffled_target_control | traditional_a_width_gate_ridge | ml_shuffled_target_control_minus_traditional_a_width_gate_ridge |          -3.37675  |           -3.68632  |             4.77472  |                     166.751   |     124.852      |     199.896       |                  0.08 |

## A-gate strata

The A percentile-68 run score defines low/mid/high A-width strata. This table shows whether covariance changes monotonically with the external gate:

| method                         | a_gate_stratum    |   n_runs |   n_pair_rows |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_abs_pair_cov_ns2 |   cov_ci_low_ns2 |   cov_ci_high_ns2 |   correlated_fraction |
|:-------------------------------|:------------------|---------:|--------------:|-------------:|--------------------:|---------------------:|------------------------:|-----------------:|------------------:|----------------------:|
| pair_median                    | all               |       21 |         65484 |      2.0905  |             1.80546 |             10.9393  |                228.535  |         187.884  |          292.882  |              0.366419 |
| pair_median                    | high_A_width_gate |        7 |         37219 |      1.90049 |             1.73027 |              4.82573 |                212.14   |         128.875  |          310.255  |              0.351877 |
| pair_median                    | low_A_width_gate  |        7 |          5630 |     10.3824  |             6.46291 |             14.3145  |                279.922  |         220.614  |          350.377  |              0.373505 |
| pair_median                    | mid_A_width_gate  |        7 |         22635 |      2.22291 |             1.67766 |             22.9758  |                200.884  |         109.061  |          300.4    |              0.376373 |
| traditional_a_width_gate_ridge | all               |       21 |         65484 |      8.33937 |             7.75395 |              9.39537 |                 64.2061 |          52.6922 |           78.0318 |              0.397272 |
| traditional_a_width_gate_ridge | high_A_width_gate |        7 |         37219 |      7.98313 |             7.51735 |              8.57348 |                 53.7962 |          41.6586 |           69.2782 |              0.384167 |
| traditional_a_width_gate_ridge | low_A_width_gate  |        7 |          5630 |     10.4541  |             9.56324 |             11.2573  |                 71.7395 |          57.8846 |           83.5574 |              0.393711 |
| traditional_a_width_gate_ridge | mid_A_width_gate  |        7 |         22635 |      8.30313 |             7.12689 |             11.5697  |                 68.1589 |          52.2662 |          104.479  |              0.412941 |
| ridge                          | all               |       21 |         65484 |      7.87268 |             7.31007 |              9.36086 |                 59.3921 |          50.7668 |           75.8116 |              0.371138 |
| ridge                          | high_A_width_gate |        7 |         37219 |      7.20488 |             6.66171 |              9.48544 |                 46.0605 |          26.9614 |           57.4961 |              0.348837 |
| ridge                          | low_A_width_gate  |        7 |          5630 |     10.5021  |             9.66059 |             11.2856  |                 69.2708 |          57.6646 |           80.999  |              0.373404 |
| ridge                          | mid_A_width_gate  |        7 |         22635 |      8.2872  |             7.38069 |             11.5571  |                 64.2563 |          41.2958 |           88.0658 |              0.388108 |
| gradient_boosted_trees         | all               |       21 |         65484 |      3.91173 |             3.5398  |             10.9784  |                 87.943  |          72.6235 |          107.866  |              0.333672 |
| gradient_boosted_trees         | high_A_width_gate |        7 |         37219 |      3.7084  |             3.38978 |              4.34895 |                 75.6468 |          22.1172 |          113.442  |              0.317232 |
| gradient_boosted_trees         | low_A_width_gate  |        7 |          5630 |      9.37069 |             6.62077 |             12.2869  |                104.73   |          83.5696 |          124.219  |              0.325014 |
| gradient_boosted_trees         | mid_A_width_gate  |        7 |         22635 |      4.07002 |             3.53111 |             15.5108  |                 85.8502 |          49.1639 |          119.466  |              0.362273 |
| extra_trees_s18e_style         | all               |       21 |         65484 |      2.38046 |             2.01803 |              5.24604 |                 37.9614 |          33.3942 |           47.9545 |              0.286267 |
| extra_trees_s18e_style         | high_A_width_gate |        7 |         37219 |      1.94106 |             1.81685 |              7.73307 |                 24.6503 |          14.9129 |           31.7359 |              0.236477 |
| extra_trees_s18e_style         | low_A_width_gate  |        7 |          5630 |      5.21463 |             4.81006 |              5.69916 |                 45.788  |          30.9863 |           53.7124 |              0.270778 |
| extra_trees_s18e_style         | mid_A_width_gate  |        7 |         22635 |      2.74669 |             2.57012 |              8.61804 |                 44.564  |          26.2739 |           60.8083 |              0.345908 |
| mlp                            | all               |       21 |         65484 |      3.85622 |             3.42243 |             16.0518  |                214.458  |         185.34   |          267.433  |              0.365971 |
| mlp                            | high_A_width_gate |        7 |         37219 |      3.50509 |             3.07627 |              5.62277 |                197.847  |          67.9152 |          274.597  |              0.347404 |
| mlp                            | low_A_width_gate  |        7 |          5630 |     10.528   |             6.43341 |             14.9278  |                263.597  |         218.405  |          322.904  |              0.377255 |
| mlp                            | mid_A_width_gate  |        7 |         22635 |      4.09361 |             3.71536 |             25.8471  |                188.95   |         121.715  |          276.623  |              0.375505 |
| cnn_1d                         | all               |       21 |         65484 |      6.58279 |             4.78329 |              9.11915 |                230.042  |         185.892  |          271.018  |              0.371273 |
| cnn_1d                         | high_A_width_gate |        7 |         37219 |      6.16483 |             4.1425  |             19.2528  |                210.3    |         106.932  |          310.437  |              0.356338 |
| cnn_1d                         | low_A_width_gate  |        7 |          5630 |     11.066   |             6.707   |             15.2125  |                288.751  |         194.732  |          348.179  |              0.382239 |
| cnn_1d                         | mid_A_width_gate  |        7 |         22635 |      5.29946 |             3.86828 |             24.0489  |                199.464  |          86.8179 |          286.86   |              0.376777 |
| support_gated_cnn_new          | all               |       21 |         65484 |      4.828   |             4.22927 |              6.42291 |                230.204  |         170.614  |          276.364  |              0.372338 |
| support_gated_cnn_new          | high_A_width_gate |        7 |         37219 |      3.86989 |             3.21613 |              4.29398 |                210.867  |         108.973  |          309.089  |              0.353695 |
| support_gated_cnn_new          | low_A_width_gate  |        7 |          5630 |     11.7779  |             8.30147 |             16.5059  |                292.331  |         227.031  |          338.732  |              0.385297 |
| support_gated_cnn_new          | mid_A_width_gate  |        7 |         22635 |      4.4511  |             3.74002 |             28.1928  |                196.291  |         112.423  |          273.535  |              0.379949 |

## A-gate calibration

| gate                      | target                                              |   n_runs |    brier |      ece |   positive_rate |   score_min |   score_max |
|:--------------------------|:----------------------------------------------------|---------:|---------:|---------:|----------------:|------------:|------------:|
| A_percentile68_width_rank | above_median_B_pair_median_mean_abs_pair_covariance |       20 | 0.424811 | 0.429998 |             0.5 |           0 |           1 |

## Covariance transfer

Run-level covariance interval coverage:

| method                         | target              |   coverage |
|:-------------------------------|:--------------------|-----------:|
| ml_extratrees_covariance       | correlated_fraction |   0.5      |
| ml_extratrees_covariance       | sigma68             |   0.333333 |
| traditional_a_width_covariance | correlated_fraction |   0.65     |
| traditional_a_width_covariance | sigma68             |   0.619048 |

Per-held-out-run predictions are in `run_level_covariance_predictions.csv`. The A-width-only traditional covariance model is the direct transfer test; the ML covariance model adds B pulse summaries and is more flexible but not treated as independent evidence if leakage checks fail.

## Leakage checks

| check                                       | value                | flag   |
|:--------------------------------------------|:---------------------|:-------|
| forbidden_feature_overlap                   |                      | False  |
| train_heldout_run_overlap                   | 0.0                  | False  |
| nominal_width_minus_shuffled_control_ns     | -0.13462765839453894 | True   |
| nominal_width_minus_pool_label_control_ns   | -1.5576125801726288  | False  |
| nominal_cov_minus_waveform_only_control_ns2 | 8.903509822469005    | True   |
| random_row_split_r2                         | 0.9207589026918694   | False  |
| group_cv_ridge_rmse_ns                      | 11.1679361665368     | False  |

Control metrics:

| method                     | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                       |
|:---------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:-----------------------------------------------------------|
| waveform_only_mlp          | control        |         65484 |       21 |      3.88921 |             3.39497 |              9.51155 |       19.7032 |              17.8622 |               29.23   |                   0.218313 |              0.378737 |                 221.301 | control: waveform-only MLP without A gate priors           |
| pool_label_control         | control        |         65484 |       21 |      6.38561 |             4.96002 |             16.7965  |       19.5712 |              16.4027 |               30.1853 |                   0.469382 |              0.366419 |                 228.535 | control: pair and run-family/pool labels only              |
| ml_shuffled_target_control | control        |         65484 |       21 |      4.96262 |             4.53965 |             17.0351  |       20.7074 |              17.2131 |               26.4973 |                   0.310656 |              0.370335 |                 230.957 | control: S18e-style ExtraTrees trained on shuffled targets |

## Systematics and caveats

The dominant systematic risk is run-level non-exchangeability: the B-stack covariance endpoint varies strongly by run and pair support, so all primary intervals are run-block bootstraps rather than row-only intervals. The leave-one-run-held-out folds in `fold_summary.csv` are therefore part of the estimand, not only a validation convenience.

The A gate is fixed-efficiency and per-run, with thresholds computed only from A1/A3 amplitudes before evaluating B covariance. This removes a direct B-stack threshold look-elsewhere effect, but it does not prove that the A robust-width ordering is a calibrated proxy for B covariance. The calibration table reports a Brier score and ECE for that proxy, and the conclusion treats the A gate as a weak external control rather than a production selection rule.

The machine-learning methods can still exploit B waveform shape, pair identity, and run-family structure. For that reason the report includes waveform-only, pool-label, shuffled-target, forbidden-feature, and train/held-out-overlap controls. Any method whose gain is comparable to these controls should be read as a benchmark result, not as an adopted covariance gate.

CNN-family results are especially sensitive to support mismatch and the limited number of held-out runs. The new support-gated CNN is included because it encodes that support concern explicitly, but its covariance point estimate is not better than the ExtraTrees winner and its intervals remain broad. The reported winner is selected by held-out mean absolute pair covariance only; the safety verdict remains conditional on future external validation.

## Conclusion

The A-stack robust-width priors are useful as weak external controls, but they are not by themselves a secure B-stack covariance gate. The learned winner improves the held-out covariance point estimate, yet the adoption decision is gated by the shuffled-target, pool-label, waveform-only, and run-split controls plus the A-gate calibration diagnostics. The result is therefore a benchmark winner, not an unconditional recommendation to use A-stack ML timing as a production B-stack covariance gate.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `astack_run_summaries.csv`, `bstack_pair_table_preview.csv`, `heldout_pair_residuals.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `gate_stratum_summary.csv`, `a_gate_calibration.csv`, `run_level_covariance_predictions.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
