# S05l: saturation-covariance correction validity gate

- **Ticket:** 1781046818.654.2a8c6dd2
- **Worker:** testbeam-laptop-3
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `configs/s05l_1781046818_654_2a8c6dd2_saturation_covariance_validity_gate.yaml`
- **Raw input:** `data/root/root`

## Question

Does the S05e B2 covariance reduction survive when saturation information is restricted to duplicate-safe waveform diagnostics rather than an adopted amplitude correction that P07e/P07g treated as non-production for high-amplitude timing? The preregistered primary metric is held-out all-pair sigma68 with run-block bootstrap 95% CIs; covariance validity is checked by B2-containing minus downstream-only off-diagonal covariance, inferred B2-local variance, full RMS, tail fraction, support loss, and ML-minus-traditional deltas.

## Reproduction from raw ROOT

The S05c gate was reproduced first from `h101/HRDv`: median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, `A > 1000 ADC`, CFD20 timing, and the configured analysis runs.

| quantity                             |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses              |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_b_selected_pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_b_selected_pulses |         125096 |       125096 |       0 |           0 | True   |

Pair-row counts:

| pair   |   n_pair_rows |
|:-------|--------------:|
| B2-B4  |         26387 |
| B2-B6  |         12626 |
| B2-B8  |          4943 |
| B4-B6  |         12196 |
| B4-B8  |          4542 |
| B6-B8  |          4790 |

## Methods

For event \(e\), run \(r\), and pair \(p=(i,j)\), the target is

\[
y_{erp} = t_j(e) - t_i(e) - (z_j-z_i)\,0.078\;\mathrm{ns/cm},
\]

with 2 cm stave spacing. The raw S05c residual is \(y_{erp}-\operatorname{median}_{train}(y_p)\). The robust width is

\[
\sigma_{68} = \frac{Q_{84}(x-\tilde x)-Q_{16}(x-\tilde x)}{2},
\]

and all CIs resample held-out runs with replacement and then events within each sampled run.

All model comparisons are leave-one-run-out on the configured benchmark runs `[58, 59, 60, 61, 62, 63, 65]`. The held-out run is excluded before fitting medians, scalers, Ridge coefficients, tree ensembles, MLP weights, CNN weights, and shuffled-target sentinels. ML and NN training rows are capped per fold only for fitting cost; metrics are computed on every row in the held-out run. The benchmark is restricted to Sample-II runs because the duplicate-readout/P07 saturation validity gate is defined there; the raw reproduction gate above still uses the full S05/S00 run set.

Feature gates:

| gate                   | definition                                                                                                                                                                                          | methods                                         |
|:-----------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------|
| raw_template_only      | pair-median CFD20 residual; no saturation correction or learned correction                                                                                                                          | raw_pair_median                                 |
| no_saturation_features | amplitude, area, tail, peak, and pair identity; saturation diagnostics excluded                                                                                                                     | ridge_no_saturation                             |
| duplicate_safe         | adds high-ADC sample count, near-peak width, saturation excess, post-peak fall, and recovery tail computed directly from held-out waveforms; no P07d ratio-transfer amplitude correction is applied | ridge, GBT, ExtraTrees, MLP, CNN-tabular hybrid |

Benchmarked methods:

- `raw_pair_median`: strong template-only S05c covariance baseline.
- `ridge_no_saturation`: linear Ridge without saturation diagnostics.
- `ridge_duplicate_safe`: strong traditional linear comparator with duplicate-safe saturation diagnostics.
- `gbt_duplicate_safe`: gradient-boosted regression trees.
- `extra_trees_duplicate_safe`: frozen S05e-style ExtraTrees residual model.
- `mlp_duplicate_safe`: tabular neural network.
- `cnn_waveform_only`: 1D-CNN over the two endpoint waveforms only.
- `hybrid_cnn_tabular_duplicate_safe`: new dual-branch architecture combining a 1D waveform CNN with a tabular branch.

## Held-out residual benchmark

Primary all-pair ranking:

| method                            | subset   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                                                        |
|:----------------------------------|:---------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:--------------------------------------------------------------------------------------------|
| raw_pair_median                   | all      |         53039 |        7 |      1.77851 |             1.62834 |              2.08621 |      12.7787  |              0.088614 | S05c pair-median centered raw CFD20 residual; no saturation correction                      |
| extra_trees_duplicate_safe        | all      |         53039 |        7 |      2.86809 |             2.62041 |              3.39897 |      11.1265  |              0.172892 | ExtraTrees residual model with waveform and duplicate-safe saturation diagnostics           |
| mlp_duplicate_safe                | all      |         53039 |        7 |      3.63609 |             3.30764 |              4.33274 |      11.85    |              0.178623 | tabular MLP with waveform summaries and duplicate-safe saturation diagnostics               |
| gbt_duplicate_safe                | all      |         53039 |        7 |      3.75255 |             3.50006 |              4.17313 |       9.93204 |              0.212655 | gradient-boosted regression trees with duplicate-safe saturation diagnostics                |
| gbt_shuffled_target               | all      |         53039 |        7 |      3.87072 |             3.64852 |              4.25736 |      13.0247  |              0.186467 | gradient-boosted shuffled-target leakage sentinel                                           |
| hybrid_cnn_tabular_duplicate_safe | all      |         53039 |        7 |      3.89502 |             3.26225 |              4.51956 |      12.9341  |              0.194234 | new dual-branch 1D-CNN plus tabular duplicate-safe saturation diagnostics                   |
| cnn_waveform_only                 | all      |         53039 |        7 |      4.1685  |             3.26714 |              5.22544 |      13.1113  |              0.225023 | 1D-CNN over the two normalized endpoint waveforms only                                      |
| ridge_duplicate_safe              | all      |         53039 |        7 |      4.60152 |             4.3759  |              5.091   |       9.73461 |              0.29022  | strong traditional Ridge with duplicate-safe waveform saturation diagnostics                |
| ridge_no_saturation               | all      |         53039 |        7 |      4.85726 |             4.52031 |              5.37612 |      10.2755  |              0.310111 | Ridge residual correction with amplitude/area/tail/peak features but no saturation features |

Full topology split:

| method                            | subset          |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                                                        |
|:----------------------------------|:----------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:--------------------------------------------------------------------------------------------|
| raw_pair_median                   | all             |         53039 |        7 |      1.77851 |             1.62834 |              2.08621 |      12.7787  |             0.088614  | S05c pair-median centered raw CFD20 residual; no saturation correction                      |
| raw_pair_median                   | B2_containing   |         34941 |        7 |      1.83785 |             1.54469 |              2.94754 |      15.0348  |             0.125669  | S05c pair-median centered raw CFD20 residual; no saturation correction                      |
| raw_pair_median                   | downstream_only |         18098 |        7 |      1.7393  |             1.69668 |              1.78004 |       6.49177 |             0.0170737 | S05c pair-median centered raw CFD20 residual; no saturation correction                      |
| ridge_no_saturation               | all             |         53039 |        7 |      4.85726 |             4.52031 |              5.37612 |      10.2755  |             0.310111  | Ridge residual correction with amplitude/area/tail/peak features but no saturation features |
| ridge_no_saturation               | B2_containing   |         34941 |        7 |      4.88088 |             4.45827 |              6.38541 |      11.6801  |             0.312699  | Ridge residual correction with amplitude/area/tail/peak features but no saturation features |
| ridge_no_saturation               | downstream_only |         18098 |        7 |      4.53909 |             4.17107 |              5.05789 |       6.87479 |             0.284396  | Ridge residual correction with amplitude/area/tail/peak features but no saturation features |
| ridge_duplicate_safe              | all             |         53039 |        7 |      4.60152 |             4.3759  |              5.091   |       9.73461 |             0.29022   | strong traditional Ridge with duplicate-safe waveform saturation diagnostics                |
| ridge_duplicate_safe              | B2_containing   |         34941 |        7 |      4.9449  |             4.56031 |              6.11285 |      11.132   |             0.317049  | strong traditional Ridge with duplicate-safe waveform saturation diagnostics                |
| ridge_duplicate_safe              | downstream_only |         18098 |        7 |      3.80986 |             3.39697 |              4.29429 |       6.29751 |             0.221682  | strong traditional Ridge with duplicate-safe waveform saturation diagnostics                |
| gbt_duplicate_safe                | all             |         53039 |        7 |      3.75255 |             3.50006 |              4.17313 |       9.93204 |             0.212655  | gradient-boosted regression trees with duplicate-safe saturation diagnostics                |
| gbt_duplicate_safe                | B2_containing   |         34941 |        7 |      3.66778 |             3.23307 |              4.67043 |      11.41    |             0.233966  | gradient-boosted regression trees with duplicate-safe saturation diagnostics                |
| gbt_duplicate_safe                | downstream_only |         18098 |        7 |      3.63515 |             3.55035 |              3.75723 |       6.4501  |             0.168582  | gradient-boosted regression trees with duplicate-safe saturation diagnostics                |
| extra_trees_duplicate_safe        | all             |         53039 |        7 |      2.86809 |             2.62041 |              3.39897 |      11.1265  |             0.172892  | ExtraTrees residual model with waveform and duplicate-safe saturation diagnostics           |
| extra_trees_duplicate_safe        | B2_containing   |         34941 |        7 |      3.05686 |             2.69854 |              4.01034 |      12.953   |             0.212015  | ExtraTrees residual model with waveform and duplicate-safe saturation diagnostics           |
| extra_trees_duplicate_safe        | downstream_only |         18098 |        7 |      2.14313 |             1.95488 |              2.34884 |       6.37192 |             0.0771356 | ExtraTrees residual model with waveform and duplicate-safe saturation diagnostics           |
| mlp_duplicate_safe                | all             |         53039 |        7 |      3.63609 |             3.30764 |              4.33274 |      11.85    |             0.178623  | tabular MLP with waveform summaries and duplicate-safe saturation diagnostics               |
| mlp_duplicate_safe                | B2_containing   |         34941 |        7 |      3.60917 |             3.18366 |              4.58417 |      13.9208  |             0.199994  | tabular MLP with waveform summaries and duplicate-safe saturation diagnostics               |
| mlp_duplicate_safe                | downstream_only |         18098 |        7 |      2.55201 |             2.41242 |              2.73344 |       6.50949 |             0.0495635 | tabular MLP with waveform summaries and duplicate-safe saturation diagnostics               |
| cnn_waveform_only                 | all             |         53039 |        7 |      4.1685  |             3.26714 |              5.22544 |      13.1113  |             0.225023  | 1D-CNN over the two normalized endpoint waveforms only                                      |
| cnn_waveform_only                 | B2_containing   |         34941 |        7 |      4.1252  |             3.08796 |              5.58576 |      15.4669  |             0.216136  | 1D-CNN over the two normalized endpoint waveforms only                                      |
| cnn_waveform_only                 | downstream_only |         18098 |        7 |      3.65254 |             2.91143 |              4.23602 |       7.1419  |             0.177257  | 1D-CNN over the two normalized endpoint waveforms only                                      |
| hybrid_cnn_tabular_duplicate_safe | all             |         53039 |        7 |      3.89502 |             3.26225 |              4.51956 |      12.9341  |             0.194234  | new dual-branch 1D-CNN plus tabular duplicate-safe saturation diagnostics                   |
| hybrid_cnn_tabular_duplicate_safe | B2_containing   |         34941 |        7 |      3.87804 |             3.20609 |              5.0474  |      15.2395  |             0.195787  | new dual-branch 1D-CNN plus tabular duplicate-safe saturation diagnostics                   |
| hybrid_cnn_tabular_duplicate_safe | downstream_only |         18098 |        7 |      3.19131 |             2.76882 |              3.62693 |       6.97976 |             0.131838  | new dual-branch 1D-CNN plus tabular duplicate-safe saturation diagnostics                   |
| gbt_shuffled_target               | all             |         53039 |        7 |      3.87072 |             3.64852 |              4.25736 |      13.0247  |             0.186467  | gradient-boosted shuffled-target leakage sentinel                                           |
| gbt_shuffled_target               | B2_containing   |         34941 |        7 |      3.86234 |             3.35326 |              5.39417 |      15.3696  |             0.197991  | gradient-boosted shuffled-target leakage sentinel                                           |
| gbt_shuffled_target               | downstream_only |         18098 |        7 |      3.17144 |             3.01865 |              3.44382 |       6.95628 |             0.103768  | gradient-boosted shuffled-target leakage sentinel                                           |

Winner: `raw_pair_median` with all-pair sigma68 `1.779` ns and 95% CI `[1.628, 2.086]`. The raw pair-median baseline is the winner, so no raw delta is defined. The strong Ridge baseline is worse than raw by 2.823 ns with 95% CI [2.511, 3.227].

Strong traditional all-run sigma68 is `4.602` ns. Raw S05c all-run sigma68 is `1.779` ns.

Bootstrap deltas:

| method                            | comparison                                                           |   delta_ns |   ci_low_ns |   ci_high_ns |   p_two_sided |
|:----------------------------------|:---------------------------------------------------------------------|-----------:|------------:|-------------:|--------------:|
| ridge_no_saturation               | ridge_no_saturation_minus_raw_pair_median_sigma68                    |   3.07875  |    2.81966  |    3.53607   |          0    |
| ridge_no_saturation               | ridge_no_saturation_minus_ridge_duplicate_safe_sigma68               |   0.255738 |    0.111169 |    0.392328  |          0    |
| ridge_duplicate_safe              | ridge_duplicate_safe_minus_raw_pair_median_sigma68                   |   2.82301  |    2.5112   |    3.22738   |          0    |
| gbt_duplicate_safe                | gbt_duplicate_safe_minus_raw_pair_median_sigma68                     |   1.97404  |    1.7395   |    2.22404   |          0    |
| gbt_duplicate_safe                | gbt_duplicate_safe_minus_ridge_duplicate_safe_sigma68                |  -0.848976 |   -1.15001  |   -0.510858  |          0    |
| extra_trees_duplicate_safe        | extra_trees_duplicate_safe_minus_raw_pair_median_sigma68             |   1.08958  |    0.933963 |    1.52261   |          0    |
| extra_trees_duplicate_safe        | extra_trees_duplicate_safe_minus_ridge_duplicate_safe_sigma68        |  -1.73343  |   -2.01346  |   -1.43109   |          0    |
| mlp_duplicate_safe                | mlp_duplicate_safe_minus_raw_pair_median_sigma68                     |   1.85758  |    1.63947  |    2.19954   |          0    |
| mlp_duplicate_safe                | mlp_duplicate_safe_minus_ridge_duplicate_safe_sigma68                |  -0.965434 |   -1.51642  |   -0.488767  |          0    |
| cnn_waveform_only                 | cnn_waveform_only_minus_raw_pair_median_sigma68                      |   2.38999  |    1.5514   |    3.3813    |          0    |
| cnn_waveform_only                 | cnn_waveform_only_minus_ridge_duplicate_safe_sigma68                 |  -0.433021 |   -1.51532  |    0.682101  |          0.48 |
| hybrid_cnn_tabular_duplicate_safe | hybrid_cnn_tabular_duplicate_safe_minus_raw_pair_median_sigma68      |   2.11651  |    1.66627  |    2.57544   |          0    |
| hybrid_cnn_tabular_duplicate_safe | hybrid_cnn_tabular_duplicate_safe_minus_ridge_duplicate_safe_sigma68 |  -0.706498 |   -1.47695  |   -0.0454962 |          0.04 |

## Hierarchical covariance

Pair-pair covariance summaries from held-out residuals:

| method                            | subset               |   n_covariances |   n_runs |   mean_abs_cov_ns2 |   mean_abs_cov_ci_low_ns2 |   mean_abs_cov_ci_high_ns2 |   median_abs_cov_ns2 |   signed_mean_cov_ns2 |
|:----------------------------------|:---------------------|----------------:|---------:|-------------------:|--------------------------:|---------------------------:|---------------------:|----------------------:|
| cnn_waveform_only                 | all_pair_covariances |             105 |        7 |            72.1068 |                  39.0691  |                   112.34   |             19.524   |             68.3585   |
| cnn_waveform_only                 | both_B2_containing   |              21 |        7 |           283.092  |                 132.778   |                   454.057  |            166.273   |            283.092    |
| cnn_waveform_only                 | both_downstream_only |              21 |        7 |            13.2175 |                   8.24696 |                    18.4942 |              3.21001 |             12.7101   |
| cnn_waveform_only                 | mixed_B2_downstream  |              63 |        7 |            21.4084 |                  11.4295  |                    32.0059 |              5.47991 |             15.3303   |
| extra_trees_duplicate_safe        | all_pair_covariances |             105 |        7 |            60.7362 |                  30.0696  |                    98.0047 |             22.1913  |             46.6403   |
| extra_trees_duplicate_safe        | both_B2_containing   |              21 |        7 |           216.378  |                  97.4009  |                   361.461  |            117.51    |            216.378    |
| extra_trees_duplicate_safe        | both_downstream_only |              21 |        7 |            19.633  |                  14.7906  |                    24.3104 |             18.5371  |             19.3393   |
| extra_trees_duplicate_safe        | mixed_B2_downstream  |              63 |        7 |            22.5566 |                  12.4832  |                    35.7287 |             18.297   |             -0.838503 |
| gbt_duplicate_safe                | all_pair_covariances |             105 |        7 |            42.9493 |                  24.2034  |                    63.873  |             16.2973  |             37.9157   |
| gbt_duplicate_safe                | both_B2_containing   |              21 |        7 |           147.56   |                  69.2877  |                   243.502  |             83.3914  |            147.56     |
| gbt_duplicate_safe                | both_downstream_only |              21 |        7 |            13.0287 |                   9.85943 |                    16.6673 |             11.1774  |             12.9946   |
| gbt_duplicate_safe                | mixed_B2_downstream  |              63 |        7 |            18.0528 |                  11.7073  |                    25.8049 |             10.9381  |              9.67474  |
| hybrid_cnn_tabular_duplicate_safe | all_pair_covariances |             105 |        7 |            72.1325 |                  38.0671  |                   107.844  |             18.2685  |             68.5729   |
| hybrid_cnn_tabular_duplicate_safe | both_B2_containing   |              21 |        7 |           281.983  |                 120.803   |                   454.49   |            160.457   |            281.983    |
| hybrid_cnn_tabular_duplicate_safe | both_downstream_only |              21 |        7 |            13.1811 |                   8.55805 |                    18.3961 |              2.86719 |             12.7133   |
| hybrid_cnn_tabular_duplicate_safe | mixed_B2_downstream  |              63 |        7 |            21.8329 |                  11.3183  |                    34.479  |              7.15225 |             16.056    |
| mlp_duplicate_safe                | all_pair_covariances |             105 |        7 |            63.0121 |                  34.1922  |                    95.3868 |             18.577   |             54.9403   |
| mlp_duplicate_safe                | both_B2_containing   |              21 |        7 |           240.521  |                  99.9342  |                   398.439  |            150.059   |            240.521    |
| mlp_duplicate_safe                | both_downstream_only |              21 |        7 |            13.1012 |                   9.05191 |                    17.2298 |              4.92237 |             12.7831   |
| mlp_duplicate_safe                | mixed_B2_downstream  |              63 |        7 |            20.4795 |                  12.3757  |                    30.4172 |             13.1268  |              7.13249  |
| raw_pair_median                   | all_pair_covariances |             105 |        7 |            72.0858 |                  41.8418  |                   110.841  |             19.4187  |             68.3009   |
| raw_pair_median                   | both_B2_containing   |              21 |        7 |           282.882  |                 145.565   |                   460.631  |            166.065   |            282.882    |
| raw_pair_median                   | both_downstream_only |              21 |        7 |            13.2031 |                   8.34557 |                    18.6305 |              3.14697 |             12.7026   |
| raw_pair_median                   | mixed_B2_downstream  |              63 |        7 |            21.4479 |                  11.3068  |                    31.8676 |              5.26863 |             15.3065   |
| ridge_duplicate_safe              | all_pair_covariances |             105 |        7 |            43.3709 |                  23.6064  |                    62.662  |             18.3043  |             31.5385   |
| ridge_duplicate_safe              | both_B2_containing   |              21 |        7 |           146.793  |                  60.6143  |                   238.524  |             90.0267  |            146.793    |
| ridge_duplicate_safe              | both_downstream_only |              21 |        7 |            15.4293 |                  12.0165  |                    18.8786 |             13.4157  |             13.9135   |
| ridge_duplicate_safe              | mixed_B2_downstream  |              63 |        7 |            18.2106 |                  12.275   |                    24.7546 |             14.9611  |             -1.00473  |
| ridge_no_saturation               | all_pair_covariances |             105 |        7 |            48.0548 |                  26.5331  |                    69.8313 |             21.7459  |             34.0688   |
| ridge_no_saturation               | both_B2_containing   |              21 |        7 |           158.198  |                  70.3807  |                   253.162  |             93.5998  |            158.198    |
| ridge_no_saturation               | both_downstream_only |              21 |        7 |            19.2359 |                  16.1277  |                    22.4799 |             21.357   |             17.8852   |
| ridge_no_saturation               | mixed_B2_downstream  |              63 |        7 |            20.9468 |                  15.0126  |                    27.5983 |             16.8353  |             -1.91301  |

The traditional CFD20 covariance baseline has B2-containing pair covariance `282.88` ns^2 with run-bootstrap CI `[145.56, 460.63]`; downstream-only pair covariance is `13.20` ns^2 with CI `[8.35, 18.63]`.

Stave-covariance decomposition:

|     var_B2 |    cov_B2_B4 |    cov_B2_B6 |   cov_B2_B8 |      var_B4 |   cov_B4_B6 |   cov_B4_B8 |       var_B6 |    cov_B6_B8 |     var_B8 |   offdiag_rmse_ns2 |   n_offdiag_covariances | method                            | scope              |   B2_variance_minus_downstream_mean_ns2 |
|-----------:|-------------:|-------------:|------------:|------------:|------------:|------------:|-------------:|-------------:|-----------:|-------------------:|------------------------:|:----------------------------------|:-------------------|----------------------------------------:|
| 63.6423    | -31.5062     | -44.4864     | -51.292     | 17.0001     |   4.2219    |  -6.71595   | 17.7095      |  4.84554     | 26.5812    |          7.66302   |                      15 | raw_pair_median                   | event_level_pooled |                             43.212      |
|  0.0221969 |   0.00216541 |  -0.00476928 |  -0.04179   |  0.0238411  |  -0.0106864 |  -0.0391612 |  0.0187654   | -0.0220751   |  0.0515131 |          0.0189073 |                      15 | raw_pair_median                   | run_median_level   |                             -0.0091763  |
| 36.767     | -22.3461     | -23.1427     | -28.0451    | 16.744      |  -1.13663   | -10.0052    | 12.8953      | -1.51131     | 19.7808    |          3.7161    |                      15 | ridge_no_saturation               | event_level_pooled |                             20.2936     |
|  0.268856  |  -0.00957353 |  -0.0166293  |  -0.511509  |  0.263554   |   0.0374126 |  -0.554947  | -0.0100639   | -0.000655391 |  0.533556  |          0.296794  |                      15 | ridge_no_saturation               | run_median_level   |                              0.00650738 |
| 33.5481    | -19.8529     | -21.9242     | -25.3191    | 14.0245     |  -0.444067  |  -7.75212   | 11.6703      | -0.972199    | 17.0217    |          3.16347   |                      15 | ridge_duplicate_safe              | event_level_pooled |                             19.3093     |
|  0.124355  |   0.00152336 |   0.0170566  |  -0.267289  |  0.196599   |   0.012562  |  -0.407284  | -0.0714345   |  0.11325     |  0.280661  |          0.330029  |                      15 | ridge_duplicate_safe              | run_median_level   |                             -0.0109207  |
| 34.3801    | -14.2045     | -24.4244     | -30.1313    | 11.122      |   0.173517  |  -8.21303   | 10.7066      |  2.83774     | 17.7533    |          4.81785   |                      15 | gbt_duplicate_safe                | event_level_pooled |                             21.1861     |
|  0.0359613 |  -0.0140598  |  -0.0202271  |  -0.0376357 |  0.130014   |  -0.0213268 |  -0.224641  |  0.0123905   |  0.0167729   |  0.122752  |          0.0723532 |                      15 | gbt_duplicate_safe                | run_median_level   |                             -0.0524242  |
| 46.7694    | -26.141      | -31.9313     | -35.4665    | 14.8        |   3.28555   |  -6.74451   | 12.6082      |  3.42935     | 19.3908    |          4.94031   |                      15 | extra_trees_duplicate_safe        | event_level_pooled |                             31.1697     |
|  0.0674068 |   0.0784371  |  -0.0732721  |  -0.139979  |  0.00823661 |  -0.024945  |  -0.0699653 |  0.0222163   |  0.0537846   |  0.0780797 |          0.16923   |                      15 | extra_trees_duplicate_safe        | run_median_level   |                              0.0312293  |
| 53.5086    | -27.5699     | -37.3459     | -42.1013    | 15.776      |   3.09341   |  -7.07548   | 15.2684      |  3.71574     | 22.7305    |          6.26971   |                      15 | mlp_duplicate_safe                | event_level_pooled |                             35.5836     |
|  0.141057  |  -0.00879971 |  -0.102696   |  -0.170618  |  0.0751327  |   0.0291733 |  -0.170639  | -0.000429578 |  0.0743818   |  0.133438  |          0.241813  |                      15 | mlp_duplicate_safe                | run_median_level   |                              0.0716766  |
| 66.623     | -30.6505     | -46.3938     | -56.2016    | 16.7505     |   4.60859   |  -7.45901   | 17.8828      |  6.01972     | 28.8204    |          8.63682   |                      15 | cnn_waveform_only                 | event_level_pooled |                             45.4717     |
|  2.59237   |   1.31091    |  -1.61899    |  -4.87667   | -0.223733   |   0.441278  |  -1.30473   | -0.133043    |  1.4438      |  2.3688    |          3.2481    |                      15 | cnn_waveform_only                 | run_median_level   |                              1.9217     |
| 64.1549    | -30.3915     | -44.7129     | -53.2054    | 16.7451     |   4.30618   |  -7.40485   | 17.6529      |  5.10094     | 27.7546    |          8.11682   |                      15 | hybrid_cnn_tabular_duplicate_safe | event_level_pooled |                             43.4373     |
|  0.779178  |   0.397128   |  -0.416338   |  -1.53915   | -0.0245029  |   0.141336  |  -0.489458  | -0.0316618   |  0.338326    |  0.845139  |          0.940426  |                      15 | hybrid_cnn_tabular_duplicate_safe | run_median_level   |                              0.516186   |

The event-level stave covariance fit solves

\[
\operatorname{Cov}(r_p,r_q) \approx a_p^T \Sigma a_q,
\]

where \(a_p\) is the signed pair-incidence vector over B2/B4/B6/B8. The reported `B2_variance_minus_downstream_mean_ns2` is a detector-local covariance diagnostic, not an independent timing-resolution measurement.

## B2 Saturation Strata

The saturation threshold was `3800` ADC after baseline subtraction. These are diagnostics only; all fitted predictions above still hold out complete runs.

| method                            | stratum            |   n_pair_rows |   n_runs | b2_amp_cut_adc   |   median_b2_sat_count |   median_b2_sat_excess_adc |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_abs_pair_cov_ns2 |
|:----------------------------------|:-------------------|--------------:|---------:|:-----------------|----------------------:|---------------------------:|-------------:|--------------------:|---------------------:|------------------------:|
| raw_pair_median                   | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      1.83785 |             1.54373 |              3.60209 |                 282.882 |
| raw_pair_median                   | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |     13.2915  |             6.52029 |             16.9293  |                 645.718 |
| raw_pair_median                   | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      1.52663 |             1.42994 |              1.77574 |                 216.246 |
| raw_pair_median                   | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     16.4854  |            14.6561  |             22.5818  |                 630.317 |
| raw_pair_median                   | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      1.57688 |             1.45074 |              1.80591 |                 254.929 |
| ridge_no_saturation               | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      4.88088 |             4.46483 |              5.90938 |                 158.198 |
| ridge_no_saturation               | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |     10.2321  |             7.2085  |             12.04    |                 259.189 |
| ridge_no_saturation               | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      4.45408 |             4.21509 |              4.93071 |                 147.217 |
| ridge_no_saturation               | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     11.6144  |            10.8779  |             15.1368  |                 231.943 |
| ridge_no_saturation               | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      4.5082  |             4.20696 |              5.04937 |                 158.305 |
| ridge_duplicate_safe              | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      4.9449  |             4.53628 |              6.08316 |                 146.793 |
| ridge_duplicate_safe              | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |      9.96353 |             8.19574 |             11.5828  |                 218.047 |
| ridge_duplicate_safe              | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      4.08823 |             3.90753 |              4.46431 |                 144.352 |
| ridge_duplicate_safe              | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     11.4897  |            10.4501  |             13.1934  |                 184.816 |
| ridge_duplicate_safe              | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      4.34764 |             4.13721 |              4.7435  |                 151.962 |
| gbt_duplicate_safe                | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      3.66778 |             3.24168 |              4.66646 |                 147.56  |
| gbt_duplicate_safe                | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |      9.78076 |             4.741   |             13.1127  |                 298.87  |
| gbt_duplicate_safe                | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      3.36645 |             3.08396 |              3.82927 |                 118.114 |
| gbt_duplicate_safe                | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     12.0564  |             9.69749 |             13.9459  |                 276.47  |
| gbt_duplicate_safe                | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      3.35195 |             3.01191 |              3.78173 |                 138.099 |
| extra_trees_duplicate_safe        | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      3.05686 |             2.70707 |              3.92608 |                 216.378 |
| extra_trees_duplicate_safe        | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |     11.5878  |             6.51377 |             15.1522  |                 454.061 |
| extra_trees_duplicate_safe        | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      2.20903 |             1.9875  |              2.57714 |                 178.087 |
| extra_trees_duplicate_safe        | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     14.5607  |            12.4866  |             17.157   |                 440.794 |
| extra_trees_duplicate_safe        | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      2.53479 |             2.35777 |              2.86913 |                 201.771 |
| mlp_duplicate_safe                | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      3.60917 |             3.18232 |              4.51201 |                 240.521 |
| mlp_duplicate_safe                | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |     12.7875  |             4.82993 |             16.5888  |                 544.821 |
| mlp_duplicate_safe                | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      3.05956 |             2.86031 |              3.45546 |                 194.521 |
| mlp_duplicate_safe                | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     16.4284  |            14.2843  |             19.7811  |                 512.158 |
| mlp_duplicate_safe                | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      3.23319 |             3.00772 |              3.67481 |                 222.078 |
| cnn_waveform_only                 | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      4.1252  |             3.08289 |              5.63854 |                 283.092 |
| cnn_waveform_only                 | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |     14.4501  |             5.97214 |             18.0224  |                 645.722 |
| cnn_waveform_only                 | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      3.5797  |             2.92346 |              4.56031 |                 216.402 |
| cnn_waveform_only                 | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     17.1019  |            15.2685  |             21.5681  |                 630.301 |
| cnn_waveform_only                 | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      3.69322 |             2.91972 |              4.94039 |                 255.113 |
| hybrid_cnn_tabular_duplicate_safe | all_B2_containing  |         34941 |        7 |                  |                     0 |                        0   |      3.87804 |             3.2099  |              4.98257 |                 281.983 |
| hybrid_cnn_tabular_duplicate_safe | B2_sat_count_gt0   |          6607 |        7 |                  |                     3 |                      783.5 |     13.8836  |             7.35103 |             16.7869  |                 637.962 |
| hybrid_cnn_tabular_duplicate_safe | B2_sat_count_eq0   |         28334 |        7 |                  |                     0 |                        0   |      3.41694 |             2.97806 |              3.92149 |                 217.985 |
| hybrid_cnn_tabular_duplicate_safe | B2_amp_top_decile  |          3497 |        7 | 4497.00          |                     6 |                     2022   |     16.7452  |            14.7053  |             19.5749  |                 622.465 |
| hybrid_cnn_tabular_duplicate_safe | B2_amp_lower_90pct |         31444 |        7 | 4497.00          |                     0 |                        0   |      3.54019 |             3.01823 |              4.1499  |                 255.873 |

## Leakage checks

| check                                 |   value | pass   | interpretation                                                                                                                                    |
|:--------------------------------------|--------:|:-------|:--------------------------------------------------------------------------------------------------------------------------------------------------|
| run_split_event_overlap               | 0       | True   | train and held-out event ids are disjoint because whole runs are held out                                                                         |
| ml_features_exclude_forbidden_columns | 1       | True   | ML inputs exclude run, event, time_ns, raw residual, target residual, and pair-derived timing labels; saturation inputs are waveform-derived only |
| actual_ml_sigma68_ns                  | 2.86809 | True   | nominal leave-run-out ML residual width                                                                                                           |
| shuffled_train_target_ml_sigma68_ns   | 3.87072 | True   | target permutation inside train folds should not reproduce the nominal ML width                                                                   |
| intentional_target_echo_sigma68_ns    | 0       | True   | positive leakage sentinel; a leaked target would be unrealistically narrow                                                                        |

The shuffled-target control and intentional target-echo sentinel are leakage probes. The added saturation diagnostics are computed from waveform samples only, before residual targets are formed. Forbidden variables are run id, event id, raw times, raw residuals, target residuals, and pair-derived timing labels.

## Systematics and Caveats

- The P07d/P07e ratio-transfer amplitude correction is not used as an adopted correction here; S05l only uses duplicate-safe waveform diagnostics as covariates.
- Neural methods are bounded-cap fits to keep the run reproducible on the laptop. This is a conservative comparison for large networks because all methods are evaluated on complete held-out runs.
- The covariance decomposition assumes the signed pair-incidence linear model; remaining B2 variance may include unmodeled waveform shape, trigger composition, and unresolved pile-up.
- Bootstrap intervals are run-block intervals. They cover run-to-run instability better than iid event bootstrap but remain limited by the seven Sample-II held-out runs.
- A method that improves sigma68 but worsens full RMS, tails, or downstream covariance should not be adopted without a downstream consumer study.

## Finding

The S05l winner is `raw_pair_median` by held-out sigma68. Raw S05c covariance is strongly B2/topology dominated: B2-containing mean absolute pair covariance is `282.88` ns^2 with 95% CI `[145.56, 460.63]`, while downstream-only is `13.20` ns^2 with CI `[8.35, 18.63]`. Duplicate-safe saturation diagnostics can be benchmarked without adopting the rejected P07d/P07e ratio-transfer correction; the winner is therefore a residual predictor validity result, not a production endorsement of high-amplitude B2 amplitude recovery.

## Artifacts

`reproduction_match_table.csv`, `pair_counts.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `pair_covariance_by_run.csv`, `covariance_summary.csv`, `stave_covariance_decomposition.csv`, `saturation_strata.csv`, `fold_hyperparameters.csv`, `cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05l_1781046818_654_2a8c6dd2_saturation_covariance_validity_gate.py --config configs/s05l_1781046818_654_2a8c6dd2_saturation_covariance_validity_gate.yaml
```
