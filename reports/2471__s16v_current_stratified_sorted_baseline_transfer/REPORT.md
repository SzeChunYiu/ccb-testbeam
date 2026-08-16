# S16v: Current-Stratified Sorted-Baseline Timing-Tail Transfer

## Abstract

Ticket `#2471` asks whether the sorted-baseline timing-tail proxy from S16u/S16t keeps the same sign after stratifying by an external electronics-current ledger. I claimed the ticket for `testbeam-laptop-3` after the `tn-ticket claim` helper returned the known `null|null|null` edge-case response, then performed a fresh raw ROOT reproduction gate and a run-held-out benchmark across Sample-I and Sample-II analysis runs. The named winner in `result.json` is **mlp** on pooled held-out `sigma68_ns`. The sign-transfer verdict is **same_point_sign_but_ci_ambiguous**.

## Raw ROOT Reproduction

Raw B-stack ROOT files under `/home/billy/ccb-data/data/extracted/root/root` were scanned directly from `h101/HRDv`. For event `i`, stave `s`, and sample `t`, the reproduced selection is

`A_is = max_t(x_ist - median(x_is0,x_is1,x_is2,x_is3)) > 1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis B2               |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4               |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6               |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8               |           1299 |         1299 |       0 |           0 | True   |
| sample_i_analysis selected_pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |

This exactly reproduces the 640,737 selected B-stave pulses and the Sample-I/Sample-II analysis-period counts used by the downstream timing-tail benchmark.

## Estimand

For a downstream pair `(a,b)` in event `i`, the raw timing residual is

`r_iab = (t_ia^CFD20 - t_ib^CFD20) - (x_a - x_b) * tau`,

where `tau = 0.078` ns/cm and CFD20 uses the raw four-sample median pedestal. A model estimates a correction `c_iab = f(z_iab)` from run-held-out training data and is scored on `r_iab - c_iab`. The primary width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The sorted-baseline signed proxy is `u_iab = u_ia - u_ib`, where `u_ip = b_ip^sorted - median(raw pretrigger)`. The sign-transfer diagnostic fits a standardized ridge model inside each current family and reports the coefficient of `u_iab`; bootstrap CIs resample source runs.

## External Current Ledger

Sample roles and raw-product identity are taken from `configs/daq/run_ledger.yaml`. Current-family labels follow the repository's electronics-current convention used by prior current studies: Sample-I runs 46-47 are `low_2nA`, while runs 44,45,48-57 are `high_20nA`. Sample-II lacks literal 2 nA/20 nA labels in the ledger, so the externally audited all-three-rate families are used: runs 58 and 65 are low-edge, 59 and 63 mid-rate, and 60-62 high-rate.

## Methods

The traditional method is the S16t hierarchical binned median correction over pair identity, amplitude-ratio bin, raw pretrigger-dispersion bin, and sorted-proxy magnitude bin, with coarser fallbacks. The ML/NN panel is ridge regression, histogram gradient-boosted trees, MLP, a 1D-CNN over raw paired waveforms, and the new nuisance-gated pair CNN. All methods are trained in leave-one-run-out folds separately inside Sample-I and Sample-II, then evaluated on held-out runs. Bootstrap intervals resample held-out source runs and preserve all paired predictions within a sampled run.

## Pooled Method Benchmark

| method                    |   n_pairs |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_abs_gt_0p5_ns |   tail_abs_gt_0p5_ns_ci_low |   tail_abs_gt_0p5_ns_ci_high |     bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |
|:--------------------------|----------:|-------------:|--------------------:|---------------------:|---------------------:|----------------------------:|-----------------------------:|------------:|-----------------:|------------------:|
| mlp                       |     21528 |      1.15667 |             1.08429 |              1.31406 |             0.632153 |                    0.610313 |                     0.674812 |  0.0962725  |       -0.0853082 |         0.271025  |
| gradient_boosted_trees    |     21528 |      1.23928 |             1.20372 |              1.32586 |             0.666713 |                    0.659438 |                     0.685423 | -0.011982   |       -0.111174  |         0.0817947 |
| nuisance_gated_pair_cnn   |     21528 |      1.39052 |             1.3449  |              1.54507 |             0.700901 |                    0.690526 |                     0.727606 | -0.363508   |       -0.465366  |        -0.202402  |
| one_dimensional_cnn       |     21528 |      1.39703 |             1.3487  |              1.54206 |             0.702109 |                    0.693337 |                     0.727793 | -0.292648   |       -0.369429  |        -0.17339   |
| traditional_binned_median |     21528 |      1.40714 |             1.36872 |              1.47165 |             0.720596 |                    0.706678 |                     0.735163 | -0.429516   |       -0.555296  |        -0.26861   |
| ridge                     |     21528 |      2.34893 |             2.24873 |              2.42278 |             0.820281 |                    0.810646 |                     0.828165 | -0.00798478 |       -0.226492  |         0.235635  |
| uncorrected               |     21528 |      2.93327 |             2.84319 |              3.00916 |             0.923774 |                    0.918344 |                     0.929872 | -3.4383     |       -3.5773    |        -3.32609   |

## Current-Stratified Results

| sample_period   | current_family          | method                    |   n_pairs |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_abs_gt_0p5_ns |     bias_ns |
|:----------------|:------------------------|:--------------------------|----------:|-------------:|--------------------:|---------------------:|---------------------:|------------:|
| sample_i        | high_20nA               | gradient_boosted_trees    |      3383 |      1.45665 |            1.40818  |              1.52217 |             0.721845 | -0.0181726  |
| sample_i        | high_20nA               | traditional_binned_median |      3383 |      1.57229 |            1.53661  |              1.62872 |             0.752586 | -0.351734   |
| sample_i        | high_20nA               | mlp                       |      3383 |      1.67617 |            1.58985  |              1.73235 |             0.757907 | -0.0487899  |
| sample_i        | high_20nA               | nuisance_gated_pair_cnn   |      3383 |      1.73201 |            1.65519  |              1.81495 |             0.763523 | -0.27303    |
| sample_i        | high_20nA               | one_dimensional_cnn       |      3383 |      1.80497 |            1.71997  |              1.88581 |             0.772391 | -0.204677   |
| sample_i        | high_20nA               | ridge                     |      3383 |      2.14076 |            2.02516  |              2.22333 |             0.802247 | -0.0103453  |
| sample_i        | high_20nA               | uncorrected               |      3383 |      2.84404 |            2.7567   |              2.94617 |             0.930239 | -3.5779     |
| sample_i        | low_2nA                 | gradient_boosted_trees    |        47 |      1.0978  |            1.08179  |              1.4532  |             0.702128 | -0.0760698  |
| sample_i        | low_2nA                 | traditional_binned_median |        47 |      1.23167 |            1.17348  |              1.80469 |             0.744681 | -0.0388429  |
| sample_i        | low_2nA                 | one_dimensional_cnn       |        47 |      1.54689 |            1.33312  |              3.56451 |             0.829787 | -0.0921122  |
| sample_i        | low_2nA                 | nuisance_gated_pair_cnn   |        47 |      1.67627 |            1.60425  |              3.40836 |             0.765957 | -0.00919627 |
| sample_i        | low_2nA                 | mlp                       |        47 |      1.76287 |            1.53482  |              3.23916 |             0.787234 | -0.106943   |
| sample_i        | low_2nA                 | ridge                     |        47 |      2.16716 |            1.34315  |              2.16716 |             0.744681 |  0.0379101  |
| sample_i        | low_2nA                 | uncorrected               |        47 |      2.6392  |            2.56943  |              3.91174 |             0.893617 | -3.37223    |
| sample_ii       | high_all_three_rate     | mlp                       |     11778 |      1.02828 |            0.978735 |              1.07299 |             0.598659 |  0.200331   |
| sample_ii       | high_all_three_rate     | gradient_boosted_trees    |     11778 |      1.18518 |            1.16393  |              1.19992 |             0.653507 |  0.0270312  |
| sample_ii       | high_all_three_rate     | one_dimensional_cnn       |     11778 |      1.31607 |            1.28234  |              1.34904 |             0.68628  | -0.3108     |
| sample_ii       | high_all_three_rate     | nuisance_gated_pair_cnn   |     11778 |      1.32323 |            1.27947  |              1.35101 |             0.688996 | -0.415417   |
| sample_ii       | high_all_three_rate     | traditional_binned_median |     11778 |      1.3727  |            1.33023  |              1.38438 |             0.722024 | -0.409821   |
| sample_ii       | high_all_three_rate     | ridge                     |     11778 |      2.41539 |            2.36089  |              2.43687 |             0.827135 | -0.010935   |
| sample_ii       | high_all_three_rate     | uncorrected               |     11778 |      2.90648 |            2.75276  |              3.00871 |             0.918577 | -3.36301    |
| sample_ii       | low_all_three_rate_edge | mlp                       |       751 |      1.36794 |            1.34405  |              1.42443 |             0.6751   |  0.575354   |
| sample_ii       | low_all_three_rate_edge | one_dimensional_cnn       |       751 |      1.42219 |            1.36737  |              1.48919 |             0.713715 |  0.247852   |
| sample_ii       | low_all_three_rate_edge | nuisance_gated_pair_cnn   |       751 |      1.45075 |            1.45075  |              1.5492  |             0.720373 |  0.204508   |
| sample_ii       | low_all_three_rate_edge | traditional_binned_median |       751 |      1.47362 |            1.39321  |              1.59243 |             0.723036 |  0.0293707  |
| sample_ii       | low_all_three_rate_edge | gradient_boosted_trees    |       751 |      1.48576 |            1.3837   |              1.58486 |             0.704394 |  0.622824   |
| sample_ii       | low_all_three_rate_edge | uncorrected               |       751 |      2.73683 |            2.58596  |              2.8719  |             0.934754 | -3.14631    |
| sample_ii       | low_all_three_rate_edge | ridge                     |       751 |      3.22686 |            2.97988  |              3.27849 |             0.874834 |  1.36847    |
| sample_ii       | mid_all_three_rate      | mlp                       |      5569 |      1.06459 |            1.01823  |              1.18217 |             0.619501 | -0.098573   |
| sample_ii       | mid_all_three_rate      | gradient_boosted_trees    |      5569 |      1.1755  |            1.14883  |              1.22604 |             0.655773 | -0.175796   |
| sample_ii       | mid_all_three_rate      | nuisance_gated_pair_cnn   |      5569 |      1.31413 |            1.29874  |              1.35216 |             0.684863 | -0.388275   |
| sample_ii       | mid_all_three_rate      | one_dimensional_cnn       |      5569 |      1.34126 |            1.32508  |              1.36314 |             0.69025  | -0.382279   |
| sample_ii       | mid_all_three_rate      | traditional_binned_median |      5569 |      1.35193 |            1.31259  |              1.44228 |             0.697612 | -0.583598   |
| sample_ii       | mid_all_three_rate      | ridge                     |      5569 |      2.20959 |            2.18196  |              2.29814 |             0.81002  | -0.186318   |
| sample_ii       | mid_all_three_rate      | uncorrected               |      5569 |      3.03624 |            2.95744  |              3.18547 |             0.92961  | -3.55265    |

## Proxy Coefficient Sign Transfer

| sample_period   | current_family          |   n_runs |   n_pairs |   standardized_proxy_coef_ns |   coef_ci_low |   coef_ci_high | sign     |   positive_bootstrap_fraction |
|:----------------|:------------------------|---------:|----------:|-----------------------------:|--------------:|---------------:|:---------|------------------------------:|
| sample_i        | high_20nA               |       12 |      3383 |                    -1.03844  |     -1.97582  |      0.0169086 | negative |                     0.0266667 |
| sample_ii       | high_all_three_rate     |        3 |     11778 |                    -1.04992  |     -2.71023  |      0.40276   | negative |                     0.0566667 |
| sample_ii       | low_all_three_rate_edge |        2 |       751 |                     0.425424 |     -0.289368 |      0.425424  | positive |                     0.76      |
| sample_ii       | mid_all_three_rate      |        2 |      5569 |                    -0.55824  |     -2.75149  |      1.22673   | negative |                     0.22      |

The decision rule is conservative: sign transfer is accepted only when Sample-I high-current and Sample-II high-rate coefficients share the same CI-excluding sign. Ambiguous intervals are reported as non-adoptable even when point estimates agree.

## Run-Held-Out Stability

| method                    |   run | sample_period   | current_family          |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |     bias_ns |
|:--------------------------|------:|:----------------|:------------------------|----------:|-------------:|---------------------:|------------:|
| gradient_boosted_trees    |    44 | sample_i        | high_20nA               |        45 |     1.68156  |             0.8      |  0.642425   |
| gradient_boosted_trees    |    45 | sample_i        | high_20nA               |       494 |     1.47879  |             0.742915 | -0.0319884  |
| gradient_boosted_trees    |    46 | sample_i        | low_2nA                 |         3 |     0.988175 |             1        | -0.903998   |
| gradient_boosted_trees    |    47 | sample_i        | low_2nA                 |        44 |     1.0898   |             0.681818 | -0.0196201  |
| gradient_boosted_trees    |    48 | sample_i        | high_20nA               |       306 |     1.3306   |             0.676471 |  0.38369    |
| gradient_boosted_trees    |    49 | sample_i        | high_20nA               |       322 |     1.36871  |             0.701863 | -0.0289724  |
| gradient_boosted_trees    |    50 | sample_i        | high_20nA               |       335 |     1.5034   |             0.704478 |  0.448497   |
| gradient_boosted_trees    |    51 | sample_i        | high_20nA               |       174 |     1.39117  |             0.649425 | -1.45348    |
| gradient_boosted_trees    |    52 | sample_i        | high_20nA               |        95 |     1.31399  |             0.757895 |  1.22992    |
| gradient_boosted_trees    |    53 | sample_i        | high_20nA               |       307 |     1.50285  |             0.723127 | -0.149358   |
| gradient_boosted_trees    |    54 | sample_i        | high_20nA               |       281 |     1.46782  |             0.736655 | -0.417887   |
| gradient_boosted_trees    |    55 | sample_i        | high_20nA               |       217 |     1.3264   |             0.723502 |  0.629808   |
| gradient_boosted_trees    |    56 | sample_i        | high_20nA               |       460 |     1.43939  |             0.717391 | -0.690714   |
| gradient_boosted_trees    |    57 | sample_i        | high_20nA               |       347 |     1.67052  |             0.775216 |  0.425044   |
| gradient_boosted_trees    |    58 | sample_ii       | low_all_three_rate_edge |       353 |     1.38252  |             0.711048 |  1.22399    |
| gradient_boosted_trees    |    59 | sample_ii       | mid_all_three_rate      |      3753 |     1.1475   |             0.65361  | -0.129494   |
| gradient_boosted_trees    |    60 | sample_ii       | high_all_three_rate     |      3700 |     1.17188  |             0.656216 |  0.045913   |
| gradient_boosted_trees    |    61 | sample_ii       | high_all_three_rate     |      4245 |     1.16387  |             0.653004 |  0.0319801  |
| gradient_boosted_trees    |    62 | sample_ii       | high_all_three_rate     |      3833 |     1.19983  |             0.651448 |  0.00332384 |
| gradient_boosted_trees    |    63 | sample_ii       | mid_all_three_rate      |      1816 |     1.22506  |             0.660242 | -0.271486   |
| gradient_boosted_trees    |    65 | sample_ii       | low_all_three_rate_edge |       398 |     1.58003  |             0.698492 |  0.0896288  |
| mlp                       |    44 | sample_i        | high_20nA               |        45 |     1.79223  |             0.755556 | -0.167186   |
| mlp                       |    45 | sample_i        | high_20nA               |       494 |     1.80444  |             0.773279 |  0.0725901  |
| mlp                       |    46 | sample_i        | low_2nA                 |         3 |     2.20263  |             1        | -1.54163    |
| mlp                       |    47 | sample_i        | low_2nA                 |        44 |     1.54142  |             0.772727 | -0.0091235  |
| mlp                       |    48 | sample_i        | high_20nA               |       306 |     1.71515  |             0.764706 | -0.18325    |
| mlp                       |    49 | sample_i        | high_20nA               |       322 |     1.61275  |             0.773292 | -0.184776   |
| mlp                       |    50 | sample_i        | high_20nA               |       335 |     1.65303  |             0.767164 |  1.09715    |
| mlp                       |    51 | sample_i        | high_20nA               |       174 |     1.42292  |             0.678161 | -1.08151    |
| mlp                       |    52 | sample_i        | high_20nA               |        95 |     1.46606  |             0.747368 |  1.15143    |
| mlp                       |    53 | sample_i        | high_20nA               |       307 |     1.73576  |             0.781759 |  0.0948742  |
| mlp                       |    54 | sample_i        | high_20nA               |       281 |     1.74781  |             0.743772 | -0.260096   |
| mlp                       |    55 | sample_i        | high_20nA               |       217 |     1.53472  |             0.764977 |  0.709259   |
| mlp                       |    56 | sample_i        | high_20nA               |       460 |     1.62374  |             0.767391 | -1.0739     |
| mlp                       |    57 | sample_i        | high_20nA               |       347 |     1.53075  |             0.723343 |  0.0503606  |
| mlp                       |    58 | sample_ii       | low_all_three_rate_edge |       353 |     1.41509  |             0.674221 |  1.0728     |
| mlp                       |    59 | sample_ii       | mid_all_three_rate      |      3753 |     1.01792  |             0.597389 | -0.0881856  |
| mlp                       |    60 | sample_ii       | high_all_three_rate     |      3700 |     0.978735 |             0.572162 |  0.392769   |
| mlp                       |    61 | sample_ii       | high_all_three_rate     |      4245 |     1.07297  |             0.62285  | -0.0509591  |
| mlp                       |    62 | sample_ii       | high_all_three_rate     |      3833 |     1.03103  |             0.597443 |  0.292871   |
| mlp                       |    63 | sample_ii       | mid_all_three_rate      |      1816 |     1.18061  |             0.665198 | -0.12004    |
| mlp                       |    65 | sample_ii       | low_all_three_rate_edge |       398 |     1.33875  |             0.675879 |  0.134153   |
| nuisance_gated_pair_cnn   |    44 | sample_i        | high_20nA               |        45 |     2.16683  |             0.777778 | -0.35224    |
| nuisance_gated_pair_cnn   |    45 | sample_i        | high_20nA               |       494 |     1.84847  |             0.791498 | -0.274687   |
| nuisance_gated_pair_cnn   |    46 | sample_i        | low_2nA                 |         3 |     2.31769  |             1        | -1.30943    |
| nuisance_gated_pair_cnn   |    47 | sample_i        | low_2nA                 |        44 |     1.60561  |             0.75     |  0.0794561  |
| nuisance_gated_pair_cnn   |    48 | sample_i        | high_20nA               |       306 |     1.55858  |             0.715686 |  0.0733578  |
| nuisance_gated_pair_cnn   |    49 | sample_i        | high_20nA               |       322 |     1.64573  |             0.729814 | -0.591007   |
| nuisance_gated_pair_cnn   |    50 | sample_i        | high_20nA               |       335 |     1.64203  |             0.731343 |  0.375487   |
| nuisance_gated_pair_cnn   |    51 | sample_i        | high_20nA               |       174 |     2.03222  |             0.793103 | -1.81142    |
| nuisance_gated_pair_cnn   |    52 | sample_i        | high_20nA               |        95 |     1.7607   |             0.810526 |  1.2125     |
| nuisance_gated_pair_cnn   |    53 | sample_i        | high_20nA               |       307 |     1.65756  |             0.762215 | -0.0407154  |
| nuisance_gated_pair_cnn   |    54 | sample_i        | high_20nA               |       281 |     1.66176  |             0.765125 | -0.568159   |
| nuisance_gated_pair_cnn   |    55 | sample_i        | high_20nA               |       217 |     1.73013  |             0.797235 |  0.468045   |
| nuisance_gated_pair_cnn   |    56 | sample_i        | high_20nA               |       460 |     1.69408  |             0.769565 | -1.06689    |
| nuisance_gated_pair_cnn   |    57 | sample_i        | high_20nA               |       347 |     1.79412  |             0.769452 |  0.090238   |
| nuisance_gated_pair_cnn   |    58 | sample_ii       | low_all_three_rate_edge |       353 |     1.44597  |             0.708215 |  0.573033   |
| nuisance_gated_pair_cnn   |    59 | sample_ii       | mid_all_three_rate      |      3753 |     1.29835  |             0.688516 | -0.283016   |
| nuisance_gated_pair_cnn   |    60 | sample_ii       | high_all_three_rate     |      3700 |     1.27382  |             0.675405 | -0.498964   |
| nuisance_gated_pair_cnn   |    61 | sample_ii       | high_all_three_rate     |      4245 |     1.35089  |             0.687868 | -0.354867   |
| nuisance_gated_pair_cnn   |    62 | sample_ii       | high_all_three_rate     |      3833 |     1.31161  |             0.703366 | -0.401829   |
| nuisance_gated_pair_cnn   |    63 | sample_ii       | mid_all_three_rate      |      1816 |     1.34976  |             0.677313 | -0.605806   |
| nuisance_gated_pair_cnn   |    65 | sample_ii       | low_all_three_rate_edge |       398 |     1.5238   |             0.731156 | -0.12235    |
| one_dimensional_cnn       |    44 | sample_i        | high_20nA               |        45 |     1.82449  |             0.711111 | -0.414142   |
| one_dimensional_cnn       |    45 | sample_i        | high_20nA               |       494 |     1.87276  |             0.767206 | -0.371101   |
| one_dimensional_cnn       |    46 | sample_i        | low_2nA                 |         3 |     2.42386  |             1        | -0.888779   |
| one_dimensional_cnn       |    47 | sample_i        | low_2nA                 |        44 |     1.33994  |             0.818182 | -0.037794   |
| one_dimensional_cnn       |    48 | sample_i        | high_20nA               |       306 |     1.56914  |             0.732026 |  0.364542   |
| one_dimensional_cnn       |    49 | sample_i        | high_20nA               |       322 |     1.62855  |             0.76087  | -0.234265   |
| one_dimensional_cnn       |    50 | sample_i        | high_20nA               |       335 |     1.89747  |             0.749254 |  0.228049   |
| one_dimensional_cnn       |    51 | sample_i        | high_20nA               |       174 |     1.90587  |             0.833333 | -2.001      |
| one_dimensional_cnn       |    52 | sample_i        | high_20nA               |        95 |     2.16536  |             0.768421 |  1.50265    |
| one_dimensional_cnn       |    53 | sample_i        | high_20nA               |       307 |     1.7075   |             0.775244 |  0.145177   |
| one_dimensional_cnn       |    54 | sample_i        | high_20nA               |       281 |     1.51849  |             0.772242 | -0.549995   |
| one_dimensional_cnn       |    55 | sample_i        | high_20nA               |       217 |     1.70685  |             0.774194 |  0.185406   |
| one_dimensional_cnn       |    56 | sample_i        | high_20nA               |       460 |     1.84797  |             0.78913  | -0.786734   |
| one_dimensional_cnn       |    57 | sample_i        | high_20nA               |       347 |     1.86927  |             0.801153 |  0.0982479  |
| one_dimensional_cnn       |    58 | sample_ii       | low_all_three_rate_edge |       353 |     1.36572  |             0.699717 |  0.473503   |
| one_dimensional_cnn       |    59 | sample_ii       | mid_all_three_rate      |      3753 |     1.32497  |             0.692246 | -0.338992   |
| one_dimensional_cnn       |    60 | sample_ii       | high_all_three_rate     |      3700 |     1.28234  |             0.684595 | -0.386296   |
| one_dimensional_cnn       |    61 | sample_ii       | high_all_three_rate     |      4245 |     1.34896  |             0.684806 | -0.356052   |
| one_dimensional_cnn       |    62 | sample_ii       | high_all_three_rate     |      3833 |     1.34405  |             0.689538 | -0.187809   |
| one_dimensional_cnn       |    63 | sample_ii       | mid_all_three_rate      |      1816 |     1.36112  |             0.686123 | -0.471739   |
| one_dimensional_cnn       |    65 | sample_ii       | low_all_three_rate_edge |       398 |     1.48463  |             0.726131 |  0.0477132  |
| ridge                     |    44 | sample_i        | high_20nA               |        45 |     2.32261  |             0.777778 | -0.426326   |
| ridge                     |    45 | sample_i        | high_20nA               |       494 |     2.27318  |             0.797571 |  0.14907    |
| ridge                     |    46 | sample_i        | low_2nA                 |         3 |     0.913343 |             0.666667 | -2.10626    |
| ridge                     |    47 | sample_i        | low_2nA                 |        44 |     1.64826  |             0.75     |  0.184103   |
| ridge                     |    48 | sample_i        | high_20nA               |       306 |     1.88687  |             0.816993 | -0.0858774  |
| ridge                     |    49 | sample_i        | high_20nA               |       322 |     2.065    |             0.779503 | -0.345909   |
| ridge                     |    50 | sample_i        | high_20nA               |       335 |     1.7881   |             0.802985 |  0.68459    |
| ridge                     |    51 | sample_i        | high_20nA               |       174 |     2.56552  |             0.862069 | -1.56065    |
| ridge                     |    52 | sample_i        | high_20nA               |        95 |     2.00647  |             0.736842 |  0.626596   |
| ridge                     |    53 | sample_i        | high_20nA               |       307 |     2.08829  |             0.76873  |  0.293617   |
| ridge                     |    54 | sample_i        | high_20nA               |       281 |     2.19423  |             0.829181 | -0.14404    |
| ridge                     |    55 | sample_i        | high_20nA               |       217 |     2.0993   |             0.746544 |  0.692587   |
| ridge                     |    56 | sample_i        | high_20nA               |       460 |     2.21731  |             0.826087 | -0.621147   |
| ridge                     |    57 | sample_i        | high_20nA               |       347 |     2.15429  |             0.818444 |  0.336216   |
| ridge                     |    58 | sample_ii       | low_all_three_rate_edge |       353 |     3.26775  |             0.88102  |  2.24594    |
| ridge                     |    59 | sample_ii       | mid_all_three_rate      |      3753 |     2.17973  |             0.811617 | -0.126214   |
| ridge                     |    60 | sample_ii       | high_all_three_rate     |      3700 |     2.348    |             0.827297 |  0.251815   |
| ridge                     |    61 | sample_ii       | high_all_three_rate     |      4245 |     2.43617  |             0.836749 | -0.40989    |
| ridge                     |    62 | sample_ii       | high_all_three_rate     |      3833 |     2.41038  |             0.816332 |  0.17727    |
| ridge                     |    63 | sample_ii       | mid_all_three_rate      |      1816 |     2.29247  |             0.806718 | -0.310532   |
| ridge                     |    65 | sample_ii       | low_all_three_rate_edge |       398 |     2.97865  |             0.869347 |  0.590205   |
| traditional_binned_median |    44 | sample_i        | high_20nA               |        45 |     2.29948  |             0.755556 | -0.369309   |
| traditional_binned_median |    45 | sample_i        | high_20nA               |       494 |     1.6106   |             0.759109 | -0.186048   |
| traditional_binned_median |    46 | sample_i        | low_2nA                 |         3 |     1.22719  |             1        | -1.16828    |
| traditional_binned_median |    47 | sample_i        | low_2nA                 |        44 |     1.17487  |             0.727273 |  0.0381642  |
| traditional_binned_median |    48 | sample_i        | high_20nA               |       306 |     1.47906  |             0.738562 | -0.0242188  |
| traditional_binned_median |    49 | sample_i        | high_20nA               |       322 |     1.48782  |             0.745342 | -0.544923   |
| traditional_binned_median |    50 | sample_i        | high_20nA               |       335 |     1.58195  |             0.737313 | -0.153198   |
| traditional_binned_median |    51 | sample_i        | high_20nA               |       174 |     1.61881  |             0.741379 | -2.0708     |
| traditional_binned_median |    52 | sample_i        | high_20nA               |        95 |     1.75094  |             0.789474 |  1.94559    |
| traditional_binned_median |    53 | sample_i        | high_20nA               |       307 |     1.57655  |             0.745928 | -0.0807237  |
| traditional_binned_median |    54 | sample_i        | high_20nA               |       281 |     1.45703  |             0.786477 | -0.758694   |
| traditional_binned_median |    55 | sample_i        | high_20nA               |       217 |     1.60481  |             0.751152 |  0.319419   |
| traditional_binned_median |    56 | sample_i        | high_20nA               |       460 |     1.52846  |             0.728261 | -1.0607     |
| traditional_binned_median |    57 | sample_i        | high_20nA               |       347 |     1.57627  |             0.783862 | -0.0435677  |
| traditional_binned_median |    58 | sample_ii       | low_all_three_rate_edge |       353 |     1.38754  |             0.696884 |  0.197775   |
| traditional_binned_median |    59 | sample_ii       | mid_all_three_rate      |      3753 |     1.31247  |             0.682121 | -0.518544   |
| traditional_binned_median |    60 | sample_ii       | high_all_three_rate     |      3700 |     1.33023  |             0.716486 | -0.608007   |
| traditional_binned_median |    61 | sample_ii       | high_all_three_rate     |      4245 |     1.36243  |             0.722733 | -0.22466    |
| traditional_binned_median |    62 | sample_ii       | high_all_three_rate     |      3833 |     1.36418  |             0.726585 | -0.423575   |
| traditional_binned_median |    63 | sample_ii       | mid_all_three_rate      |      1816 |     1.44158  |             0.729626 | -0.71804    |
| traditional_binned_median |    65 | sample_ii       | low_all_three_rate_edge |       398 |     1.58763  |             0.746231 | -0.119993   |
| uncorrected               |    44 | sample_i        | high_20nA               |        45 |     3.27746  |             0.866667 | -3.70525    |
| uncorrected               |    45 | sample_i        | high_20nA               |       494 |     2.94064  |             0.917004 | -3.45879    |
| uncorrected               |    46 | sample_i        | low_2nA                 |         3 |     2.65999  |             0.666667 | -4.86485    |
| uncorrected               |    47 | sample_i        | low_2nA                 |        44 |     2.5728   |             0.909091 | -3.27046    |
| uncorrected               |    48 | sample_i        | high_20nA               |       306 |     2.77081  |             0.918301 | -3.129      |
| uncorrected               |    49 | sample_i        | high_20nA               |       322 |     2.61914  |             0.931677 | -3.75887    |
| uncorrected               |    50 | sample_i        | high_20nA               |       335 |     2.77875  |             0.931343 | -3.25099    |
| uncorrected               |    51 | sample_i        | high_20nA               |       174 |     3.11159  |             0.95977  | -5.3064     |
| uncorrected               |    52 | sample_i        | high_20nA               |        95 |     3.15536  |             0.894737 | -1.76642    |
| uncorrected               |    53 | sample_i        | high_20nA               |       307 |     2.79905  |             0.912052 | -3.26165    |
| uncorrected               |    54 | sample_i        | high_20nA               |       281 |     2.59401  |             0.935943 | -4.0171     |
| uncorrected               |    55 | sample_i        | high_20nA               |       217 |     3.06053  |             0.967742 | -2.93454    |
| uncorrected               |    56 | sample_i        | high_20nA               |       460 |     2.77743  |             0.932609 | -4.23353    |
| uncorrected               |    57 | sample_i        | high_20nA               |       347 |     2.66173  |             0.945245 | -3.36095    |
| uncorrected               |    58 | sample_ii       | low_all_three_rate_edge |       353 |     2.8642   |             0.923513 | -2.85184    |
| uncorrected               |    59 | sample_ii       | mid_all_three_rate      |      3753 |     2.95704  |             0.928324 | -3.47279    |
| uncorrected               |    60 | sample_ii       | high_all_three_rate     |      3700 |     2.96349  |             0.917027 | -3.51308    |
| uncorrected               |    61 | sample_ii       | high_all_three_rate     |      4245 |     2.7526   |             0.912603 | -3.26935    |
| uncorrected               |    62 | sample_ii       | high_all_three_rate     |      3833 |     3.00859  |             0.926689 | -3.32187    |
| uncorrected               |    63 | sample_ii       | mid_all_three_rate      |      1816 |     3.18528  |             0.932269 | -3.71769    |
| uncorrected               |    65 | sample_ii       | low_all_three_rate_edge |       398 |     2.58048  |             0.944724 | -3.40749    |

## Systematics and Caveats

The response is a pair-residual timing-tail proxy, not an external clock truth. Sample-II current families are rate-derived external strata rather than literal electronics-current set points, so the Sample-I/Sample-II comparison tests sign portability across matched current-like operating states rather than a calibrated current scale. The sorted ROOT branches are reconstruction products; they are used here as diagnostic covariates and not as permission to alter the raw CFD20 pedestal definition. Low-current support is sparse, with only two Sample-I low-current and two Sample-II low-edge runs, so bootstrap CIs are conditional and should not be read as population intervals. Neural models are compact CPU-reproducible benchmarks, not exhaustive architecture searches.

## Conclusion

The best pooled held-out method is **mlp**. The current-stratified coefficient table is the ticket's decisive systematic: the sorted-baseline signed-difference coefficient is only transferable if the high-current Sample-I and high-rate Sample-II signs agree with run-bootstrap support. The reported verdict is **same_point_sign_but_ci_ambiguous**, so downstream adoption should follow that verdict rather than the pooled method winner alone.
