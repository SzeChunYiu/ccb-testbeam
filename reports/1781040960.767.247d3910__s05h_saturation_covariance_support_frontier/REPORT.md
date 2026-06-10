# S05h: Saturation-aware covariance support frontier

- **Ticket:** `1781040960.767.247d3910`
- **Worker:** `testbeam-laptop-3`
- **Raw input:** `/home/billy/ccb-data/extracted/root/root`
- **Input checksums:** `input_sha256.csv`
- **No Monte Carlo:** raw HRD ROOT only

## Question

Where do the newest S05d/S05e saturation-aware covariance gains remain valid once B2 saturation depth, q-template shift, amplitude, topology, baseline lowering, pile-up candidates, and run family are matched?

## Abstract

This study rebuilds the B-stack coincidence table from raw `HRDv` ROOT and audits the S05d/S05e saturation-aware covariance gain after matching on B2 saturation depth, q-template-shift proxy, amplitude, topology, baseline lowering, pile-up candidate status, and run family. The benchmark uses leave-one-run-held-out B-stack residuals and a run/pair bootstrap for confidence intervals. The method panel contains the requested strong traditional comparator and learned alternatives: ridge, gradient-boosted trees, S05e-style ExtraTrees, MLP, 1D-CNN, and a new support-gated CNN. Controls include waveform-only, pool-label-only, and shuffled-target fits.

The winner named in `result.json` is **extra_trees_s05e_dynamic**, selected by lowest held-out B-stack mean absolute pair covariance among non-control methods. Its covariance is **36.063 ns^2**, versus **59.162 ns^2** for the traditional S05d static-prior Ridge and **228.535 ns^2** for pair-median centering. The support-frontier winner is **traditional_s05d_static_priors** and the primary safety verdict is **benchmark_winner_not_adopted_as_safe_gate**.

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

Runs are the split unit. Each B-stack analysis run is held out in turn; all B residual models and covariance predictors are fit without that run's B targets. The raw features are waveform-derived summaries only: amplitude, tail, peak sample, area, baseline, normalized 18-sample shape, saturation depth, and pile-up proxies.

Traditional: train-run B pair medians are retained as the non-parametric S05c baseline. The strong traditional comparator, `traditional_s05d_static_priors`, is a Ridge residual model with S05d-style static priors and explicit B waveform/support covariates: amplitude, tail, peak, baseline, q-template-shift proxy, B2 saturation depth, pair topology, and run family.

ML/NN: `ridge`, `gradient_boosted_trees`, `extra_trees_s05e_dynamic`, `mlp`, `cnn_1d`, and `support_gated_cnn_new` are trained on the same train runs and evaluated on the same held-out run. The 1D-CNN consumes left/right normalized waveforms and support auxiliary features. The new support-gated CNN uses a learned sigmoid support gate on the convolutional representation, which is sensible here because corrections should shrink outside matched saturation/amplitude/topology support.

Controls: `waveform_only_mlp` removes tabular support covariates, `pool_label_control` uses only pair and run-family labels, and `ml_shuffled_target_control` shuffles training targets within the run-held-out fold.

## Estimands and equations

For B pair residuals, `r_ij = (t_j - t_i) - TOF_ij`. For method `m`, the held-out residual is `e_i(m)=r_i-hat r_m(x_i)`. The robust width is

`W_68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

For each run, residuals are pivoted to event by pair. The covariance gate metric is the mean absolute off-diagonal pair covariance:

`C_m = mean_{runs} mean_{p<q} |Cov(e_p(m), e_q(m))|`.

Width intervals resample held-out runs with replacement and pair rows within sampled runs. Covariance intervals resample precomputed per-run covariance values. Support atoms are Cartesian cells over run family, topology, B2 saturation-depth bin, q-template-shift-proxy bin, pair-amplitude bin, baseline-lowering flag, and pile-up candidate flag. An atom is accepted support when it has at least `250` pair rows and `4` runs.

## Held-out residuals

| method                         | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                                                                                         |
|:-------------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:-----------------------------------------------------------------------------------------------------------------------------|
| pair_median                    | traditional    |         65484 |       21 |      2.0905  |             1.80811 |              2.27674 |      20.6803  |             15.2767  |              26.3972  |                   0.141775 |              0.366419 |                228.535  | strong traditional B-pair train-median centering                                                                             |
| traditional_s05d_static_priors | traditional    |         65484 |       21 |      7.81113 |             7.42459 |              9.27801 |      10.8219  |              9.9995  |              12.0492  |                   0.484531 |              0.393702 |                 59.1618 | traditional S05d-style Ridge using static priors plus B saturation/support covariates                                        |
| ridge                          | ml             |         65484 |       21 |      7.07174 |             6.48018 |              7.60231 |      10.4992  |             10.1641  |              11.1915  |                   0.448873 |              0.380034 |                 55.5307 | standardized Ridge residual model with saturation, q-shift, amplitude, topology, baseline, and run-family support covariates |
| gradient_boosted_trees         | ml             |         65484 |       21 |      3.92221 |             3.63043 |              4.28583 |      12.3493  |             11.453   |              14.3997  |                   0.197224 |              0.322029 |                 69.805  | gradient-boosted tree residual model with B saturation/support covariates                                                    |
| extra_trees_s05e_dynamic       | ml             |         65484 |       21 |      2.19839 |             2.0123  |              3.01137 |       8.85958 |              8.32365 |               9.11178 |                   0.160406 |              0.291143 |                 36.0633 | S05e-style ExtraTrees dynamic-weight residual model with explicit B2 saturation features                                     |
| mlp                            | ml             |         65484 |       21 |      4.26916 |             4.02466 |              5.54644 |      19.1859  |             16.0054  |              22.8449  |                   0.245984 |              0.373519 |                207.016  | tabular MLP residual model with B saturation/support covariates                                                              |
| cnn_1d                         | ml             |         65484 |       21 |      5.7971  |             4.20431 |              5.94763 |      20.5232  |             19.9334  |              24.9475  |                   0.370762 |              0.376025 |                233.696  | compact two-channel 1D-CNN over left/right waveforms with support auxiliaries                                                |
| support_gated_cnn_new          | ml             |         65484 |       21 |      4.88826 |             4.36981 |              5.72628 |      20.33    |             17.5499  |              27.6684  |                   0.307251 |              0.371429 |                228.154  | new support-gated residual CNN suppressing waveform corrections outside A/B support                                          |
| waveform_only_mlp              | control        |         65484 |       21 |      3.88921 |             3.70692 |              4.26398 |      19.7032  |             15.8372  |              24.3626  |                   0.218313 |              0.378737 |                221.301  | control: waveform-only MLP without A/B support priors                                                                        |
| pool_label_control             | control        |         65484 |       21 |      6.38561 |             5.32043 |              9.73998 |      19.5712  |             15.3057  |              19.9606  |                   0.469382 |              0.366419 |                228.535  | control: pair and run-family/pool labels only                                                                                |
| ml_shuffled_target_control     | control        |         65484 |       21 |      5.00568 |             4.71289 |              7.72421 |      20.6531  |             17.215   |              22.1375  |                   0.316306 |              0.376717 |                236.074  | control: S05e-style ExtraTrees trained on shuffled targets                                                                   |

Pair-median sigma68 is `2.091` ns with CI `[1.808, 2.277]`. The traditional S05d static-prior Ridge is `7.811` ns with CI `[7.425, 9.278]`. The winner `extra_trees_s05e_dynamic` has sigma68 `2.198` ns with CI `[2.012, 3.011]`.

Winner-minus-pair-median delta: sigma68 `0.108` ns with CI `[-0.501, 0.194]`; covariance `-192.471` ns^2 with CI `[-234.125, -174.442]`.

Winner-minus-traditional-gate delta: sigma68 `-5.613` ns with CI `[-5.761, -5.385]`; covariance `-23.099` ns^2 with CI `[-28.060, -21.457]`.

Full paired deltas are in `method_delta_bootstrap.csv`:

| method                     | baseline                       | comparison                                                      |   delta_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   delta_mean_abs_pair_cov_ns2 |   cov_ci_low_ns2 |   cov_ci_high_ns2 |   p_two_sided_sigma68 |
|:---------------------------|:-------------------------------|:----------------------------------------------------------------|-------------------:|--------------------:|---------------------:|------------------------------:|-----------------:|------------------:|----------------------:|
| ridge                      | pair_median                    | ridge_minus_pair_median                                         |           4.98124  |            4.66978  |             5.32576  |                   -173.004    |   -209.964       |    -138.682       |                  0    |
| ridge                      | traditional_s05d_static_priors | ridge_minus_traditional_s05d_static_priors                      |          -0.739385 |           -1.04096  |            -0.494866 |                     -3.63119  |     -5.77859     |      -1.80962     |                  0    |
| gradient_boosted_trees     | pair_median                    | gradient_boosted_trees_minus_pair_median                        |           1.8317   |            1.39573  |             1.84872  |                   -158.73     |   -178.621       |    -134.205       |                  0    |
| gradient_boosted_trees     | traditional_s05d_static_priors | gradient_boosted_trees_minus_traditional_s05d_static_priors     |          -3.88892  |           -4.30169  |            -3.5482   |                     10.6432   |      6.83466     |      17.2223      |                  0    |
| extra_trees_s05e_dynamic   | pair_median                    | extra_trees_s05e_dynamic_minus_pair_median                      |           0.107889 |           -0.500912 |             0.194293 |                   -192.471    |   -234.125       |    -174.442       |                  0.75 |
| extra_trees_s05e_dynamic   | traditional_s05d_static_priors | extra_trees_s05e_dynamic_minus_traditional_s05d_static_priors   |          -5.61273  |           -5.76148  |            -5.38462  |                    -23.0985   |    -28.0601      |     -21.4569      |                  0    |
| mlp                        | pair_median                    | mlp_minus_pair_median                                           |           2.17866  |           -0.326691 |             2.34224  |                    -21.5186   |    -31.2317      |     -15.2358      |                  0.25 |
| mlp                        | traditional_s05d_static_priors | mlp_minus_traditional_s05d_static_priors                        |          -3.54196  |           -3.80903  |            -3.29113  |                    147.854    |    141.588       |     183.899       |                  0    |
| cnn_1d                     | pair_median                    | cnn_1d_minus_pair_median                                        |           3.70659  |            2.44099  |             3.93454  |                      5.16162  |     -0.30619     |       9.33134     |                  0    |
| cnn_1d                     | traditional_s05d_static_priors | cnn_1d_minus_traditional_s05d_static_priors                     |          -2.01403  |           -3.31917  |            -1.66542  |                    174.534    |    140.464       |     225.396       |                  0    |
| support_gated_cnn_new      | pair_median                    | support_gated_cnn_new_minus_pair_median                         |           2.79776  |            1.74545  |             2.8086   |                     -0.380511 |     -1.93672     |       0.38041     |                  0    |
| support_gated_cnn_new      | traditional_s05d_static_priors | support_gated_cnn_new_minus_traditional_s05d_static_priors      |          -2.92286  |           -3.74963  |            11.0352   |                    168.992    |    152.478       |     207.688       |                  0.25 |
| waveform_only_mlp          | pair_median                    | waveform_only_mlp_minus_pair_median                             |           1.79871  |            0.152336 |             1.92551  |                     -7.23362  |    -12.4051      |      -5.12064     |                  0    |
| waveform_only_mlp          | traditional_s05d_static_priors | waveform_only_mlp_minus_traditional_s05d_static_priors          |          -3.92191  |           -4.35911  |            -3.42018  |                    162.139    |    129.342       |     194.807       |                  0    |
| pool_label_control         | pair_median                    | pool_label_control_minus_pair_median                            |           4.2951   |            3.34079  |             5.52715  |                      0        |     -1.18705e-14 |       5.01821e-15 |                  0    |
| pool_label_control         | traditional_s05d_static_priors | pool_label_control_minus_traditional_s05d_static_priors         |          -1.42552  |           -2.56318  |             0.390482 |                    169.373    |    126.747       |     197.681       |                  0.25 |
| ml_shuffled_target_control | pair_median                    | ml_shuffled_target_control_minus_pair_median                    |           2.91518  |            2.64847  |             3.08634  |                      7.53927  |      3.77003     |      16.5722      |                  0    |
| ml_shuffled_target_control | traditional_s05d_static_priors | ml_shuffled_target_control_minus_traditional_s05d_static_priors |          -2.80544  |           -2.92881  |            -2.30814  |                    176.912    |    160.654       |     215.231       |                  0    |

## Support Frontier

Accepted support atoms and method-level support summaries:

| method                         |   n_supported_atoms |   supported_fraction_sum |   median_atom_sigma68_ns |   max_abs_residual_envelope_endpoint_ns |   median_b2_covariance_component_error_ns2 |   tail_fraction_median |
|:-------------------------------|--------------------:|-------------------------:|-------------------------:|----------------------------------------:|-------------------------------------------:|-----------------------:|
| cnn_1d                         |                  51 |                 0.844649 |                  4.54036 |                                134.282  |                                    32.134  |              0.268392  |
| extra_trees_s05e_dynamic       |                  51 |                 0.844649 |                  1.63847 |                                 89.4462 |                                    20.997  |              0.0776567 |
| gradient_boosted_trees         |                  51 |                 0.844649 |                  3.20055 |                                 94.7275 |                                    27.8621 |              0.138235  |
| ml_shuffled_target_control     |                  51 |                 0.844649 |                  4.1656  |                                131.146  |                                    32.5697 |              0.226298  |
| mlp                            |                  51 |                 0.844649 |                  3.34327 |                                132.863  |                                    31.2988 |              0.127818  |
| pair_median                    |                  51 |                 0.844649 |                  1.66479 |                                140.806  |                                    32.0466 |              0.0476434 |
| pool_label_control             |                  51 |                 0.844649 |                  2.21957 |                                122.965  |                                    32.0466 |              0.0843195 |
| ridge                          |                  51 |                 0.844649 |                  6.42205 |                                 82.0292 |                                    25.6426 |              0.396341  |
| support_gated_cnn_new          |                  51 |                 0.844649 |                  3.94047 |                                131.029  |                                    32.1677 |              0.205651  |
| traditional_s05d_static_priors |                  51 |                 0.844649 |                  6.34684 |                                 80.9047 |                                    17.9543 |              0.402645  |
| waveform_only_mlp              |                  51 |                 0.844649 |                  3.00907 |                                135.01   |                                    31.0595 |              0.1       |

Top support-frontier rows:

| support_atom                                                                                        | method                         |   n_pair_rows |   n_runs |   accepted_support_fraction | support_pass   |   median_bias_ns |   residual_envelope_low_ns |   residual_envelope_high_ns |   sigma68_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |   mean_abs_pair_cov_ns2 |   covariance_component_error_ns2 | run_family         | topology      | b2_saturation_depth_bin   | q_template_shift_bin   | amplitude_bin   | baseline_bin     | pileup_bin      |
|:----------------------------------------------------------------------------------------------------|:-------------------------------|--------------:|---------:|----------------------------:|:---------------|-----------------:|---------------------------:|----------------------------:|-------------:|--------------:|---------------------------:|------------------------:|---------------------------------:|:-------------------|:--------------|:--------------------------|:-----------------------|:----------------|:-----------------|:----------------|
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | cnn_1d                         |          4660 |        7 |                   0.0711624 | True           |       -1.40216   |                   -9.24487 |                    8.53949  |      5.23452 |       6.47187 |                  0.325966  |                 9.71183 |                        6.23583   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | extra_trees_s05e_dynamic       |          4660 |        7 |                   0.0711624 | True           |       -0.132598  |                   -7.09195 |                    6.01032  |      1.61572 |       4.80637 |                  0.0690987 |                 3.90815 |                        2.66527   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | gradient_boosted_trees         |          4660 |        7 |                   0.0711624 | True           |       -5.07253   |                  -11.4662  |                    1.7753   |      2.27259 |       5.38768 |                  0.101502  |                 5.2667  |                        0.958607  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | ml_shuffled_target_control     |          4660 |        7 |                   0.0711624 | True           |       -6.35748   |                  -13.6111  |                    0.221981 |      3.09527 |       5.39477 |                  0.122961  |                 7.92605 |                        2.75605   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | mlp                            |          4660 |        7 |                   0.0711624 | True           |       -0.47503   |                   -5.76197 |                    5.40535  |      2.50485 |       5.05443 |                  0.072103  |                 5.90476 |                        4.25438   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | pair_median                    |          4660 |        7 |                   0.0711624 | True           |       -0.432339  |                   -5.87531 |                    2.55294  |      1.98389 |       5.12196 |                  0.0403433 |                 5.2098  |                        3.31708   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | pool_label_control             |          4660 |        7 |                   0.0711624 | True           |       -5.28213   |                  -12.1282  |                   -1.11971  |      1.90411 |       5.1638  |                  0.0620172 |                 5.2098  |                        3.31708   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | ridge                          |          4660 |        7 |                   0.0711624 | True           |       -0.206771  |                  -20.3821  |                   13.5825   |      6.49007 |       8.27044 |                  0.405794  |                26.3588  |                       10.2075    | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | support_gated_cnn_new          |          4660 |        7 |                   0.0711624 | True           |       -3.2646    |                  -15.1356  |                    4.06279  |      4.49517 |       6.30382 |                  0.262232  |                 9.06494 |                        6.50979   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | traditional_s05d_static_priors |          4660 |        7 |                   0.0711624 | True           |       -0.0661831 |                  -18.5655  |                   14.151    |      6.34684 |       7.75121 |                  0.401288  |                16.3994  |                       -1.77947   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | waveform_only_mlp              |          4660 |        7 |                   0.0711624 | True           |        0.107458  |                   -5.43482 |                    5.10245  |      1.979   |       5.41743 |                  0.054721  |                 4.54448 |                        2.84686   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | cnn_1d                         |          3904 |        7 |                   0.0596176 | True           |       -2.7627    |                   -8.92598 |                   25.2342   |      4.21541 |       7.00598 |                  0.218494  |                20.1081  |                        1.9708    | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | extra_trees_s05e_dynamic       |          3904 |        7 |                   0.0596176 | True           |       -0.312492  |                   -3.29216 |                   20.6719   |      1.20484 |       4.93535 |                  0.048668  |                12.9484  |                       -2.47294   | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | gradient_boosted_trees         |          3904 |        7 |                   0.0596176 | True           |       -4.42435   |                   -7.488   |                   19.9084   |      2.95756 |       5.87211 |                  0.102715  |                15.9287  |                       12.5783    | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | ml_shuffled_target_control     |          3904 |        7 |                   0.0596176 | True           |       -6.48686   |                  -13.1444  |                   18.4279   |      3.77138 |       6.44348 |                  0.184939  |                20.7617  |                       -0.0471507 | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | mlp                            |          3904 |        7 |                   0.0596176 | True           |       -1.78833   |                   -6.12496 |                   25.8538   |      3.45968 |       6.59776 |                  0.127818  |                20.047   |                        0.975851  | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | pair_median                    |          3904 |        7 |                   0.0596176 | True           |       -0.542401  |                   -2.97991 |                   25.7395   |      1.25694 |       5.90699 |                  0.0476434 |                20.6958  |                        1.15533   | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | pool_label_control             |          3904 |        7 |                   0.0596176 | True           |       -5.46217   |                   -9.09081 |                   20.7205   |      1.82781 |       6.10097 |                  0.0596824 |                20.6958  |                        1.15533   | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | ridge                          |          3904 |        7 |                   0.0596176 | True           |        1.71737   |                   -8.04072 |                   15.2028   |      4.70243 |       5.6373  |                  0.290215  |                10.9578  |                       -3.08765   | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | support_gated_cnn_new          |          3904 |        7 |                   0.0596176 | True           |       -1.7142    |                   -7.78979 |                   24.5133   |      4.20681 |       6.62597 |                  0.201588  |                20.0801  |                        2.05441   | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |

The full table is `support_frontier.csv`; `support_summary.csv` is the compact method-level ledger. Support-atom residual envelopes are the central 95% held-out residual range inside the matched cell; bootstrap CIs are reported in the primary method and delta tables above. The covariance-component error is the atom covariance minus the downstream-only covariance available in the same support cell; it is blank when the atom has no downstream reference rows.

## Covariance transfer

Run-level covariance interval coverage:

| method                      | target              |   coverage |
|:----------------------------|:--------------------|-----------:|
| ml_extratrees_covariance    | correlated_fraction |   0.4      |
| ml_extratrees_covariance    | sigma68             |   0.428571 |
| traditional_s05d_covariance | correlated_fraction |   0.65     |
| traditional_s05d_covariance | sigma68             |   0.761905 |

Per-held-out-run predictions are in `run_level_covariance_predictions.csv`. The traditional covariance model is the static-prior transfer test; the ML covariance model adds B pulse summaries and is more flexible but not treated as independent evidence if leakage checks fail.

## Leakage checks

| check                                       | value               | flag   |
|:--------------------------------------------|:--------------------|:-------|
| forbidden_feature_overlap                   |                     | False  |
| train_heldout_run_overlap                   | 0.0                 | False  |
| nominal_width_minus_shuffled_control_ns     | -0.1174200095141762 | True   |
| nominal_width_minus_pool_label_control_ns   | -1.4973447196036682 | False  |
| nominal_cov_minus_waveform_only_control_ns2 | 6.853113597508326   | True   |
| random_row_split_r2                         | 0.9303237285133137  | False  |
| group_cv_ridge_rmse_ns                      | 10.022089672566334  | False  |

Control metrics:

| method                     | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                       |
|:---------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:-----------------------------------------------------------|
| waveform_only_mlp          | control        |         65484 |       21 |      3.88921 |             3.70692 |              4.26398 |       19.7032 |              15.8372 |               24.3626 |                   0.218313 |              0.378737 |                 221.301 | control: waveform-only MLP without A/B support priors      |
| pool_label_control         | control        |         65484 |       21 |      6.38561 |             5.32043 |              9.73998 |       19.5712 |              15.3057 |               19.9606 |                   0.469382 |              0.366419 |                 228.535 | control: pair and run-family/pool labels only              |
| ml_shuffled_target_control | control        |         65484 |       21 |      5.00568 |             4.71289 |              7.72421 |       20.6531 |              17.215  |               22.1375 |                   0.316306 |              0.376717 |                 236.074 | control: S05e-style ExtraTrees trained on shuffled targets |

## Systematics And Caveats

The q-template axis is a waveform-derived proxy, not a full refit of the S01 amplitude-adaptive template library. It combines late charge and peak-sample displacement, so it should be read as a support coordinate for shape shift rather than an absolute template-fit quality. The baseline-lowering flag uses the lower tail of the raw pre-trigger baseline distribution in the selected pair sample; it is sensitive to run composition and should not be interpreted as an independent pedestal calibration.

The support frontier is intentionally conservative. Cells below `250` pair rows or `4` runs are excluded from the accepted-support summary even if their point estimates look favorable. The support-atom residual envelopes are descriptive central 95% ranges, while the formal bootstrap CIs are the run-block intervals in the method and delta tables. MLP convergence warnings are possible under the short laptop iteration budget and are treated as a model-quality caveat, not as evidence for the MLP.

The covariance-component error is defined against downstream-only rows matched on run family, saturation-depth bin, q-shift bin, amplitude bin, baseline bin, and pile-up-candidate bin, with topology left free for the contrast. It is blank when no downstream reference exists. The winner is therefore a held-out benchmark winner and support-frontier candidate, not a proof that dynamic covariance weights are calibrated outside the populated support atoms.

## Conclusion

The saturation-aware ML winner improves the held-out covariance point estimate, but the support frontier is narrower than the global result: deep B2 saturation, high q-shift, low-baseline, and pile-up-like atoms remain the places where bias and covariance-component errors should be treated as systematics rather than calibrated corrections. The result is therefore a benchmark winner plus an explicit support frontier, not an unconditional recommendation to use dynamic covariance weights everywhere.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `astack_run_summaries.csv`, `bstack_pair_table_preview.csv`, `heldout_pair_residuals.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `support_frontier.csv`, `support_summary.csv`, `run_level_covariance_predictions.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
