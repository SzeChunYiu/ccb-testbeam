# S05k: Rate-residual covariance atom sieve

- **Ticket:** `1781045406.539.02891975`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** `/home/billy/ccb-data/extracted/root/root`
- **Frozen residual panel:** `reports/1781040960.767.247d3910__s05h_saturation_covariance_support_frontier`
- **Frozen rate panel:** `reports/1781017418.11875.10723959`
- **No Monte Carlo:** raw HRD ROOT plus frozen leave-one-run-held-out data residuals

## Question

After S05e-rate showed that run-level A/B coincidence rate does not explain B2-local covariance, do residual A/B acceptance/current-rate atoms still bias B-pair covariance intervals in narrow support cells?

## Abstract

This study rebuilds the raw `HRDv` count anchors and combines two frozen run-held-out panels: S05h residuals for traditional/ML/NN B-pair timing models and S05e-rate A/B acceptance residuals. The rate residual is converted into tertile atoms and joined to B-pair rows by held-out run. Covariance and interval metrics are then recomputed inside rate-residual, current, and narrow support atoms. The benchmark includes `pair_median`, the strong traditional `traditional_s05d_static_priors`, `ridge`, `gradient_boosted_trees`, `extra_trees_s05e_dynamic`, `mlp`, `cnn_1d`, and the new `support_gated_cnn_new`; controls are kept out of winner selection.

The winner named in `result.json` is **extra_trees_s05e_dynamic**, selected by the smallest 95% rate-axis score `mean(abs coverage error) + 0.01 * mean interval width + 0.0005 * mean |B2-downstream covariance delta|`. Its score row is:

| method                   |   mean_abs_coverage_error_95 |   worst_abs_coverage_error_95 |   mean_interval_width_ns |   mean_abs_cov_delta_ns2 |   winner_score |
|:-------------------------|-----------------------------:|------------------------------:|-------------------------:|-------------------------:|---------------:|
| extra_trees_s05e_dynamic |                   0.00144785 |                    0.00326711 |                  41.0662 |                  111.255 |       0.467737 |

## Reproduction first

Raw ROOT anchors were rebuilt before rate-atom scoring:

| quantity                             |     expected |   reproduced |       delta |   tolerance | pass   |
|:-------------------------------------|-------------:|-------------:|------------:|------------:|:-------|
| total_selected_b_pulses              | 640737       | 640737       | 0           |       0     | True   |
| sample_i_analysis_b_selected_pulses  | 252266       | 252266       | 0           |       0     | True   |
| sample_ii_analysis_b_selected_pulses | 125096       | 125096       | 0           |       0     | True   |
| sample_iv_a1_a3_pairs                |    127       |    127       | 0           |       0     | True   |
| sample_iv_a1_a3_robust_width_ns      |      1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |

The joined S05e-rate run panel is:

|   run | sample             | target_setting       |   current_nA |   b_any_events |   target_rate |   pred_traditional_rate |   pred_ml_rate |   resid_traditional_rate_pp |   resid_ml_rate_pp |   b_downstream_frac |   b2_share | rate_residual_quantile   | traditional_rate_residual_quantile   | current_group        |
|------:|:-------------------|:---------------------|-------------:|---------------:|--------------:|------------------------:|---------------:|----------------------------:|-------------------:|--------------------:|-----------:|:-------------------------|:-------------------------------------|:---------------------|
|    44 | sample_i_analysis  | sample_i_cd2         |           20 |           1912 |    0.0394668  |             0.0643928   |     0.0279255  |                  -2.4926    |          1.15413   |           0.0606695 |   0.985356 | high_rate_residual       | low_rate_residual                    | nominal_current_20nA |
|    45 | sample_i_analysis  | sample_i_cd2         |           20 |          23004 |    0.0392741  |             0.0170735   |     0.0167429  |                   2.22006   |          2.25311   |           0.0498174 |   0.990132 | high_rate_residual       | high_rate_residual                   | nominal_current_20nA |
|    46 | sample_i_analysis  | sample_i_cd2         |            2 |            661 |    0.0294562  |             0.000160281 |     0.00243961 |                   2.92959   |          2.70166   |           0.0151286 |   0.996974 | high_rate_residual       | high_rate_residual                   | low_current_2nA      |
|    47 | sample_i_analysis  | sample_i_cd2         |            2 |           5141 |    0.0356865  |             0.870148    |     0.00563822 |                 -83.4461    |          3.00483   |           0.0241198 |   0.991441 | high_rate_residual       | low_rate_residual                    | low_current_2nA      |
|    48 | sample_i_analysis  | sample_i_cd2         |           20 |          13167 |    0.0424894  |             0.0184137   |     0.0258705  |                   2.40756   |          1.66189   |           0.0537708 |   0.989291 | high_rate_residual       | high_rate_residual                   | nominal_current_20nA |
|    49 | sample_i_analysis  | sample_i_cd2         |           20 |          13919 |    0.0395474  |             0.0298646   |     0.0258754  |                   0.968284  |          1.3672    |           0.0553201 |   0.988649 | high_rate_residual       | high_rate_residual                   | nominal_current_20nA |
|    50 | sample_i_analysis  | sample_i_cd2         |           20 |          34251 |    0.00480264 |             0.00216105  |     0.0026061  |                   0.264159  |          0.219654  |           0.0249336 |   0.995066 | mid_rate_residual        | high_rate_residual                   | nominal_current_20nA |
|    51 | sample_i_analysis  | sample_i_cd2         |           20 |          14291 |    0.00297369 |             0.00403921  |     0.00521806 |                  -0.106552  |         -0.224437  |           0.0279896 |   0.993352 | low_rate_residual        | mid_rate_residual                    | nominal_current_20nA |
|    52 | sample_i_analysis  | sample_i_cd2         |           20 |           6933 |    0.00151428 |             0.00131688  |     0.00405563 |                   0.0197398 |         -0.254135  |           0.0268282 |   0.99423  | low_rate_residual        | mid_rate_residual                    | nominal_current_20nA |
|    53 | sample_i_analysis  | sample_i_cd2         |           20 |          31385 |    0.00116294 |             0.00362347  |     0.0045451  |                  -0.246054  |         -0.338216  |           0.0231639 |   0.99487  | low_rate_residual        | low_rate_residual                    | nominal_current_20nA |
|    54 | sample_i_analysis  | sample_i_cd2         |           20 |          29638 |    0.00163636 |             0.00482736  |     0.00282055 |                  -0.3191    |         -0.118419  |           0.0240907 |   0.99423  | mid_rate_residual        | low_rate_residual                    | nominal_current_20nA |
|    55 | sample_i_analysis  | sample_i_cd2         |           20 |          16820 |    0.00270495 |             0.00358516  |     0.00413527 |                  -0.0880211 |         -0.143032  |           0.0284185 |   0.993698 | low_rate_residual        | mid_rate_residual                    | nominal_current_20nA |
|    56 | sample_i_analysis  | sample_i_cd2         |           20 |          38913 |    0.00558925 |             0.00248043  |     0.00329797 |                   0.310882  |          0.229128  |           0.0269833 |   0.994809 | mid_rate_residual        | high_rate_residual                   | nominal_current_20nA |
|    57 | sample_i_analysis  | sample_i_cd2         |           20 |          12925 |    0.0410413  |             0.0739388   |     0.0276476  |                  -3.28975   |          1.33937   |           0.0599613 |   0.987234 | high_rate_residual       | low_rate_residual                    | nominal_current_20nA |
|    58 | sample_ii_analysis | sample_ii_p_enriched |           20 |          15890 |    0.00437354 |             0.00170992  |     0.00951912 |                   0.266363  |         -0.514558  |           0.0446193 |   0.991945 | low_rate_residual        | high_rate_residual                   | nominal_current_20nA |
|    59 | sample_ii_analysis | sample_ii_p_enriched |           20 |          13863 |    0.00155078 |             0.00340457  |     0.00300297 |                  -0.18538   |         -0.145219  |           0.347832  |   0.978504 | low_rate_residual        | low_rate_residual                    | nominal_current_20nA |
|    60 | sample_ii_analysis | sample_ii_p_enriched |           20 |          10139 |    0.0020217  |             0.00283298  |     0.00180484 |                  -0.0811282 |          0.0216857 |           0.420456  |   0.973666 | mid_rate_residual        | mid_rate_residual                    | nominal_current_20nA |
|    61 | sample_ii_analysis | sample_ii_p_enriched |           20 |          11282 |    0.00226004 |             0.000512019 |     0.0017099  |                   0.174802  |          0.0550136 |           0.41092   |   0.975891 | mid_rate_residual        | mid_rate_residual                    | nominal_current_20nA |
|    62 | sample_ii_analysis | sample_ii_p_enriched |           20 |          11902 |    0.00155423 |             0.00286244  |     0.00196628 |                  -0.130821  |         -0.0412045 |           0.371954  |   0.976727 | mid_rate_residual        | mid_rate_residual                    | nominal_current_20nA |
|    63 | sample_ii_analysis | sample_ii_p_enriched |           20 |          14756 |    0.00545504 |             0.0030866   |     0.00432986 |                   0.236844  |          0.112518  |           0.189753  |   0.98543  | mid_rate_residual        | mid_rate_residual                    | nominal_current_20nA |
|    65 | sample_ii_analysis | sample_ii_p_enriched |           20 |          11875 |    0.00509431 |             0.0109358   |     0.0104201  |                  -0.584154  |         -0.53258   |           0.0789053 |   0.988547 | low_rate_residual        | low_rate_residual                    | nominal_current_20nA |

## Rate and support atoms

The primary rate coordinate is the S05e-rate leave-one-run-held-out ExtraTrees residual in percentage points, `100 * (p_AB - hat p_AB)`, split into tertiles. Narrow support atoms additionally include run family, topology, pair-amplitude tertile, B2 saturation depth, anomaly taxon, and rate-residual tertile.

The low-cardinality axes and largest narrow support atoms are shown below; the full support ledger is `rate_atom_counts.csv`.

| axis                   | stratum                                                                                                            |   n_pair_rows |   n_runs |   b2_fraction |   rate_residual_pp_median |   target_rate_percent_median |
|:-----------------------|:-------------------------------------------------------------------------------------------------------------------|--------------:|---------:|--------------:|--------------------------:|-----------------------------:|
| rate_residual_quantile | high_rate_residual                                                                                                 |          5630 |        7 |      0.722735 |                 1.66189   |                     3.95474  |
| rate_residual_quantile | low_rate_residual                                                                                                  |         16712 |        7 |      0.683042 |                -0.145219  |                     0.155078 |
| rate_residual_quantile | mid_rate_residual                                                                                                  |         43142 |        7 |      0.65996  |                 0.0216857 |                     0.20217  |
| current_group          | low_current_2nA                                                                                                    |           169 |        2 |      0.721893 |                 3.00483   |                     3.56865  |
| current_group          | nominal_current_20nA                                                                                               |         65315 |       19 |      0.671117 |                 0.0216857 |                     0.20217  |
| topology               | B2_containing                                                                                                      |         43956 |       21 |      1        |                 0.0216857 |                     0.20217  |
| topology               | downstream_only                                                                                                    |         21528 |       21 |      0        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_high|sat=none|anom=common_support|rateq=mid_rate_residual            |          4711 |        4 |      1        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_mid|sat=none|anom=common_support|rateq=mid_rate_residual             |          4409 |        4 |      1        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_low|sat=none|anom=common_support|rateq=mid_rate_residual             |          4337 |        4 |      1        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=downstream_only|amp=amp_mid|sat=none|anom=common_support|rateq=mid_rate_residual           |          3671 |        4 |      0        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=downstream_only|amp=amp_low|sat=none|anom=common_support|rateq=mid_rate_residual           |          3616 |        4 |      0        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_high|sat=mild|anom=saturation_boundary|rateq=mid_rate_residual       |          2203 |        4 |      1        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_mid|sat=none|anom=timing_tail_high_q_shift|rateq=mid_rate_residual   |          2055 |        4 |      1        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_low|sat=none|anom=common_support|rateq=low_rate_residual             |          1979 |        3 |      1        |                -0.145219  |                     0.155078 |
| rate_support_atom      | sample_ii_analysis|topo=downstream_only|amp=amp_mid|sat=none|anom=timing_tail_high_q_shift|rateq=mid_rate_residual |          1939 |        4 |      0        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_high|sat=none|anom=timing_tail_high_q_shift|rateq=mid_rate_residual  |          1723 |        4 |      1        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=downstream_only|amp=amp_high|sat=none|anom=common_support|rateq=mid_rate_residual          |          1688 |        4 |      0        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=downstream_only|amp=amp_low|sat=none|anom=timing_tail_high_q_shift|rateq=mid_rate_residual |          1647 |        4 |      0        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_mid|sat=none|anom=common_support|rateq=low_rate_residual             |          1617 |        3 |      1        |                -0.145219  |                     0.155078 |
| rate_support_atom      | sample_ii_analysis|topo=downstream_only|amp=amp_low|sat=none|anom=common_support|rateq=low_rate_residual           |          1499 |        3 |      0        |                -0.145219  |                     0.155078 |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_low|sat=none|anom=timing_tail_high_q_shift|rateq=mid_rate_residual   |          1350 |        4 |      1        |                 0.0550136 |                     0.226004 |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_high|sat=none|anom=common_support|rateq=low_rate_residual            |          1239 |        3 |      1        |                -0.145219  |                     0.155078 |
| rate_support_atom      | sample_ii_analysis|topo=B2_containing|amp=amp_high|sat=none|anom=baseline_contamination|rateq=mid_rate_residual    |          1235 |        4 |      1        |                 0.0216857 |                     0.20217  |
| rate_support_atom      | sample_ii_analysis|topo=downstream_only|amp=amp_mid|sat=none|anom=common_support|rateq=low_rate_residual           |          1073 |        3 |      0        |                -0.145219  |                     0.155078 |

## Methods and equations

For pair residual `r_i = (t_right - t_left) - TOF`, method `m` supplies held-out residual `e_i(m)=r_i-hat r_m(x_i)`. The robust width is

`W_68(m,s) = 0.5 [Q_84(e_i - median(e_i)) - Q_16(e_i - median(e_i))]`.

For a held-out run `k`, atom `s`, and nominal coverage `q`, the empirical interval is

`c_mks = median(e_train)`,
`h_mks(q) = Quantile_q(|e_train - c_mks|)`,
`I_mks = [c_mks - h_mks, c_mks + h_mks]`.

Covariance is evaluated by pivoting held-out residuals to `(run,event) x pair`. The signed contrast is

`Delta C_m(s) = mean Cov_B2(e_p,e_q | s) - mean Cov_downstream(e_p,e_q | s)`,

with run-block bootstrap confidence intervals. Exact downstream controls are used when the stratum contains downstream rows; otherwise a same-run downstream fallback is explicitly marked as a systematic sentinel.

## Head-to-head rate-atom residuals

| method                         | method_class   | axis                   | stratum            |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |
|:-------------------------------|:---------------|:-----------------------|:-------------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|
| pair_median                    | traditional    | rate_residual_quantile | high_rate_residual |          5630 |        7 |     10.3824  |             6.5333  |             13.1664  |      32.4081  |             30.4148  |              35.3982  |                   0.261634 |
| pair_median                    | traditional    | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      3.01582 |             2.14733 |             32.0159  |      23.2165  |             15.4459  |              41.5593  |                   0.198241 |
| pair_median                    | traditional    | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      1.84386 |             1.66359 |              9.70608 |      17.3914  |             12.0567  |              29.7276  |                   0.104144 |
| traditional_s05d_static_priors | traditional    | rate_residual_quantile | high_rate_residual |          5630 |        7 |      9.55162 |             9.01717 |             10.1309  |      15.2133  |             14.1465  |              16.0298  |                   0.601421 |
| traditional_s05d_static_priors | traditional    | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      8.06229 |             7.37017 |             10.8229  |      11.4379  |              9.83682 |              15.9893  |                   0.502573 |
| traditional_s05d_static_priors | traditional    | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      7.36708 |             7.00078 |              8.81284 |       9.86017 |              9.25774 |              11.4475  |                   0.457072 |
| ridge                          | ml             | rate_residual_quantile | high_rate_residual |          5630 |        7 |      9.4656  |             8.59172 |             10.0923  |      14.821   |             13.77    |              15.7984  |                   0.579041 |
| ridge                          | ml             | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      6.89011 |             5.93145 |              9.69867 |      10.7272  |              9.04123 |              14.9321  |                   0.434299 |
| ridge                          | ml             | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      6.84353 |             6.38661 |              7.92483 |       9.71337 |              8.93708 |              11.1095  |                   0.436303 |
| gradient_boosted_trees         | ml             | rate_residual_quantile | high_rate_residual |          5630 |        7 |      8.46633 |             6.40048 |             11.109   |      19.0975  |             17.4291  |              20.8007  |                   0.322913 |
| gradient_boosted_trees         | ml             | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      4.48519 |             4.07018 |             16.6789  |      13.7499  |             11.367   |              20.6001  |                   0.256103 |
| gradient_boosted_trees         | ml             | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      3.66846 |             3.36451 |              4.90922 |      10.4573  |              8.4899  |              16.0039  |                   0.162185 |
| extra_trees_s05e_dynamic       | ml             | rate_residual_quantile | high_rate_residual |          5630 |        7 |      4.17059 |             3.82125 |              4.66377 |      13.9052  |             12.0604  |              15.3965  |                   0.273179 |
| extra_trees_s05e_dynamic       | ml             | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      2.59369 |             2.04377 |              6.72261 |      10.1247  |              9.11368 |              14.2341  |                   0.202429 |
| extra_trees_s05e_dynamic       | ml             | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      1.89542 |             1.65819 |              3.10438 |       7.37163 |              6.41958 |               8.98361 |                   0.128552 |
| mlp                            | ml             | rate_residual_quantile | high_rate_residual |          5630 |        7 |     10.2825  |             6.90244 |             13.0099  |      30.1428  |             28.219   |              32.1928  |                   0.368917 |
| mlp                            | ml             | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      4.46332 |             3.90532 |             32.5413  |      21.4788  |             16.1318  |              38.9019  |                   0.274354 |
| mlp                            | ml             | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      4.09476 |             3.54822 |              5.0784  |      16.1519  |             12.2282  |              21.4348  |                   0.222289 |
| cnn_1d                         | ml             | rate_residual_quantile | high_rate_residual |          5630 |        7 |     12.2782  |             7.79053 |             15.0892  |      32.2951  |             30.3779  |              34.3106  |                   0.466963 |
| cnn_1d                         | ml             | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      6.3806  |             5.2642  |             33.0079  |      21.8774  |             15.7896  |              38.1836  |                   0.414911 |
| cnn_1d                         | ml             | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      4.66248 |             3.84387 |              6.24777 |      17.4073  |             12.6167  |              25.9609  |                   0.285916 |
| support_gated_cnn_new          | ml             | rate_residual_quantile | high_rate_residual |          5630 |        7 |     10.7153  |             7.50569 |             14.3674  |      31.546   |             29.612   |              34.4261  |                   0.37833  |
| support_gated_cnn_new          | ml             | rate_residual_quantile | low_rate_residual  |         16712 |        7 |      5.33915 |             4.02171 |             31.6122  |      22.9506  |             16.2704  |              41.8815  |                   0.292484 |
| support_gated_cnn_new          | ml             | rate_residual_quantile | mid_rate_residual  |         43142 |        7 |      4.76034 |             3.25748 |              5.72044 |      17.1943  |             11.9206  |              27.8891  |                   0.294493 |

## Interval coverage

Winner 95% rate-axis interval rows:

| method                   | axis                   | stratum              |   nominal_coverage |   n_runs |   n_pair_rows |   coverage |   coverage_ci_low |   coverage_ci_high |   coverage_error |   abs_coverage_error |   mean_interval_width_ns |   interval_width_ci_low_ns |   interval_width_ci_high_ns |   fallback_fraction |
|:-------------------------|:-----------------------|:---------------------|-------------------:|---------:|--------------:|-----------:|------------------:|-------------------:|-----------------:|---------------------:|-------------------------:|---------------------------:|----------------------------:|--------------------:|
| extra_trees_s05e_dynamic | current_group          | low_current_2nA      |               0.95 |        1 |           156 |   0.955128 |          0.955128 |           0.955128 |      0.00512821  |          0.00512821  |                  33.1343 |                    33.1343 |                     33.1343 |                   1 |
| extra_trees_s05e_dynamic | current_group          | nominal_current_20nA |               0.95 |       19 |         65315 |   0.950302 |          0.920182 |           0.967344 |      0.000302381 |          0.000302381 |                  34.1376 |                    32.3587 |                     35.5175 |                   0 |
| extra_trees_s05e_dynamic | rate_residual_quantile | high_rate_residual   |               0.95 |        6 |          5617 |   0.948193 |          0.934586 |           0.965074 |     -0.00180701  |          0.00180701  |                  54.7716 |                    52.0764 |                     57.698  |                   0 |
| extra_trees_s05e_dynamic | rate_residual_quantile | low_rate_residual    |               0.95 |        7 |         16712 |   0.953267 |          0.932742 |           0.957535 |      0.00326711  |          0.00326711  |                  47.661  |                    43.6772 |                     48.9251 |                   0 |
| extra_trees_s05e_dynamic | rate_residual_quantile | mid_rate_residual    |               0.95 |        7 |         43142 |   0.949585 |          0.91273  |           0.967493 |     -0.000414909 |          0.000414909 |                  27.6945 |                    25.277  |                     29.159  |                   0 |

Full interval rows are in `interval_coverage_by_run.csv`; summarized CIs are in `interval_coverage_summary.csv`.

## Covariance stress

Winner covariance rows:

|   b2_signed_cov_ns2 |   downstream_signed_cov_ns2 |   b2_minus_downstream_cov_ns2 |   b2_mean_abs_cov_ns2 |   downstream_mean_abs_cov_ns2 |   b2_minus_downstream_abs_cov_ns2 |   inferred_correlated_fraction | method                   | axis                   | stratum              |   n_b2_pair_rows |   n_downstream_pair_rows |   n_b2_runs |   n_downstream_runs | control_mode              |   delta_ci_low_ns2 |   delta_ci_high_ns2 | interval_excludes_zero   |
|--------------------:|----------------------------:|------------------------------:|----------------------:|------------------------------:|----------------------------------:|-------------------------------:|:-------------------------|:-----------------------|:---------------------|-----------------:|-------------------------:|------------:|--------------------:|:--------------------------|-------------------:|--------------------:|:-------------------------|
|            174.39   |                     7.72693 |                      166.663  |              174.39   |                       7.75615 |                          166.634  |                       0.955692 | extra_trees_s05e_dynamic | rate_residual_quantile | high_rate_residual   |             4069 |                     1561 |           7 |                   7 | same_rate_atom_downstream |          112.805   |             226.954 | True                     |
|            108.69   |                    29.8921  |                       78.7982 |              110.705  |                      29.9079  |                           80.797  |                       0.724979 | extra_trees_s05e_dynamic | rate_residual_quantile | low_rate_residual    |            11415 |                     5297 |           7 |                   7 | same_rate_atom_downstream |            9.77578 |             143.945 | True                     |
|             79.2405 |                     9.06244 |                       70.1781 |               79.2405 |                       9.66523 |                           69.5753 |                       0.885634 | extra_trees_s05e_dynamic | rate_residual_quantile | mid_rate_residual    |            28472 |                    14670 |           7 |                   7 | same_rate_atom_downstream |           33.6793  |             102.646 | True                     |
|            149.07   |                     8.55401 |                      140.516  |              149.07   |                       8.55401 |                          140.516  |                       0.942617 | extra_trees_s05e_dynamic | current_group          | low_current_2nA      |              122 |                       47 |           2 |                   2 | same_rate_atom_downstream |          140.516   |             140.516 | True                     |
|            116.463  |                    16.3416  |                      100.121  |              117.205  |                      16.5787  |                          100.626  |                       0.859684 | extra_trees_s05e_dynamic | current_group          | nominal_current_20nA |            43834 |                    21481 |          19 |                  19 | same_rate_atom_downstream |           64.0318  |             131.89  | True                     |
|            118.093  |                    15.9522  |                      102.141  |              118.798  |                      16.1774  |                          102.621  |                       0.864918 | extra_trees_s05e_dynamic | topology               | all                  |            43956 |                    21528 |          21 |                  21 | same_rate_atom_downstream |           68.7879  |             136.427 | True                     |

## Rate-feature covariance sentinels

The ticket requested covariance predictors with and without rate-residual features plus shuffled-rate, run-only, and topology-only sentinels. The low-dimensional run-held-out sentinel table below is deliberately descriptive: it predicts the extra-trees B2-downstream covariance delta by run from frozen rate/topology summaries, not from event labels.

| predictor                          |   n_runs |   rmse_ns2 |   mae_ns2 |   bias_ns2 |
|:-----------------------------------|---------:|-----------:|----------:|-----------:|
| extra_trees_with_rate_residual     |       21 |    83.2341 |   59.8023 |   2.5878   |
| extra_trees_without_rate_residual  |       21 |    78.0345 |   53.4153 |   0.462862 |
| gam_spline_like_with_rate_residual |       21 |    83.9642 |   63.4502 |   1.39698  |
| shuffled_rate_sentinel             |       21 |    84.382  |   60.5626 |  -0.352864 |
| run_only_sentinel                  |       21 |    86.3863 |   63.8402 |  -1.57665  |
| topology_only_sentinel             |       21 |    81.5082 |   54.5471 |   0.599825 |

## Winner scoring

| method                         |   mean_abs_coverage_error_95 |   worst_abs_coverage_error_95 |   mean_interval_width_ns |   mean_abs_cov_delta_ns2 |   winner_score |
|:-------------------------------|-----------------------------:|------------------------------:|-------------------------:|-------------------------:|---------------:|
| extra_trees_s05e_dynamic       |                  0.00144785  |                   0.00326711  |                  41.0662 |                 111.255  |       0.467737 |
| ridge                          |                  0.00341208  |                   0.0104476   |                  45.1256 |                  74.2123 |       0.491774 |
| traditional_s05d_static_priors |                  0.00489784  |                   0.0122427   |                  48.1824 |                 103.266  |       0.538355 |
| gradient_boosted_trees         |                  0.00252297  |                   0.00595979  |                  70.3656 |                 290.413  |       0.851385 |
| mlp                            |                  0.00085535  |                   0.00145095  |                 120.207  |                1082.51   |       1.74418  |
| cnn_1d                         |                  0.000394052 |                   0.000859951 |                 128.075  |                1220.98   |       1.89163  |
| support_gated_cnn_new          |                  0.000592242 |                   0.00128052  |                 127.698  |                1237.82   |       1.89648  |
| pair_median                    |                  0.000832056 |                   0.0015797   |                 131.807  |                1231.2    |       1.9345   |

## Systematics and caveats

Rate residual atoms are run-level atoms, not event-level beam-current truth. They are useful for testing whether a run-rate confound survives after waveform/support matching, but cannot identify within-run instantaneous rate fluctuations. Narrow `rate_support_atom` cells often lack exact downstream analogues, so rows with fallback downstream controls are diagnostics rather than matched estimates. The neural models are inherited from the S05h laptop budget and remain small; the result is a fair benchmark under that frozen budget, not a claim that larger neural architectures are impossible to improve.

The S05e-rate residual is itself a model output. To avoid target leakage, it is leave-one-run-held-out and joined only by run after the B-pair residuals are frozen. The result should therefore be read as a confound sieve: if rate residuals were explaining B2 covariance, the rate tertiles would dominate the covariance deltas and rate-feature sentinel predictors would clearly beat topology-only controls.

## Conclusion

S05k does not find evidence that residual A/B acceptance/current-rate atoms are the missing explanation for B2-local covariance. Rate residual tertiles change interval width and covariance point estimates, but the dominant covariance remains attached to B2/topology and waveform-support atoms. The named winner is the best rate-axis calibration/covariance benchmark under the declared score; downstream consumers should continue treating B2-local timing-tail and saturation atoms as detector-local systematics rather than rate corrections.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `rate_run_summary.csv`, `rate_atom_counts.csv`, `rate_residual_metrics.csv`, `interval_coverage_by_run.csv`, `interval_coverage_summary.csv`, `covariance_rate_stress.csv`, `rate_feature_sentinel_models.csv`, `winner_score_table.csv`, and PNG diagnostics are in this folder.
