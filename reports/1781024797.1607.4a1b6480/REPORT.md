# Study report: S03h - HGB timewalk gain support map by amplitude and shape atoms

- **Ticket:** `1781024797.1607.4a1b6480`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03h_1781024797_1607_4a1b6480_support_map.yaml`

## 0. Question

In which raw waveform strata does the S03d HGB residual corrector gain over signed/analytic traditional timewalk models appear, fail, or become unsupported?

## 1. Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before any model fitting.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03d pooled numbers named in the ticket were reproduced from the raw-derived pulse table before the audit.

| method                 |   reference_sigma68_ns |   reproduced_sigma68_ns |   delta_ns |   tolerance_ns | pass   |
|:-----------------------|-----------------------:|------------------------:|-----------:|---------------:|:-------|
| s03a_amp_only          |                1.55109 |                 1.55109 |          0 |          0.005 | True   |
| hgb_full_unconstrained |                1.39397 |                 1.39397 |          0 |          0.005 | True   |

## 2. Methods

Traditional references are the frozen S03a amp-only Ridge correction, a physically signed shared-stave inverse-amplitude shrinkage model, the S03b monotone decreasing residual table, and a robust heavy-tail trimmed-median residual table. The ML audit compares the original HGB feature set with a log-amplitude monotonic constraint, amplitude-only, shape-only, and stave-only controls. No method uses run number, event id, event order, current, cross-stave timing, or held-out labels.

## 3. Held-out results

| method                  |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   full_rms_ns |   full_rms_ns_ci_low |   full_rms_ns_ci_high |   tail_frac_abs_gt5ns |   bias_vs_log_amp_slope_ns |   calibration_coverage_abs_le2ns |   n_pair_residuals |
|:------------------------|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|----------------------:|---------------------------:|---------------------------------:|-------------------:|
| template_phase_base     |      2.74141 |             2.68422 |              2.98617 |       3.30837 |              3.24703 |               3.35936 |             0.0813264 |                   3.74095  |                         0.560297 |              11460 |
| s03a_amp_only           |      1.55109 |             1.374   |              1.86354 |       2.66699 |              2.45451 |               2.89883 |             0.0191099 |                  -0.283729 |                         0.760297 |              11460 |
| signed_shared_shrinkage |      1.53985 |             1.26741 |              1.93303 |       2.70053 |              2.48806 |               2.9175  |             0.022164  |                   0.247162 |                         0.732635 |              11460 |
| monotone_residual_table |      1.64515 |             1.32175 |              1.93183 |       2.71603 |              2.48876 |               2.89287 |             0.019459  |                  -0.62603  |                         0.751745 |              11460 |
| robust_heavytail_table  |      1.5767  |             1.32559 |              1.90729 |       2.71823 |              2.47538 |               2.94205 |             0.0197208 |                  -0.491739 |                         0.754188 |              11460 |
| hgb_full_unconstrained  |      1.39397 |             1.23676 |              1.63834 |       2.38001 |              2.15682 |               2.58796 |             0.0156195 |                  -0.888168 |                         0.810908 |              11460 |
| full_monotone_log_amp   |      1.37252 |             1.20625 |              1.62115 |       2.42708 |              2.21601 |               2.58185 |             0.0150087 |                  -0.728472 |                         0.811169 |              11460 |
| amplitude_only          |      1.43646 |             1.28307 |              1.78702 |       2.54856 |              2.35487 |               2.74495 |             0.017801  |                  -0.977546 |                         0.785515 |              11460 |
| shape_only              |      1.3599  |             1.17715 |              1.66143 |       2.44264 |              2.24028 |               2.61305 |             0.0157068 |                  -0.556472 |                         0.815009 |              11460 |
| stave_only              |      1.37186 |             1.12186 |              1.78565 |       2.63832 |              2.4408  |               2.85722 |             0.0208551 |                   0.419832 |                         0.77644  |              11460 |

|   heldout_run | method                  |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_vs_log_amp_slope_ns |
|--------------:|:------------------------|-------------:|---------:|----------:|--------------:|----------------------:|---------------------------:|
|            58 | amplitude_only          |     1.16546  | 1.01056  |   1.59718 |       2.69643 |            0.0273973  |                 -0.718595  |
|            58 | full_monotone_log_amp   |     1.04612  | 0.953225 |   1.3399  |       2.55938 |            0.0182648  |                  0.23552   |
|            58 | hgb_full_unconstrained  |     1.0863   | 0.984964 |   1.29916 |       2.56038 |            0.0136986  |                  0.455704  |
|            58 | monotone_residual_table |     1.3214   | 1.3214   |   1.61026 |       2.78333 |            0.0319635  |                  0.0227206 |
|            58 | robust_heavytail_table  |     1.3214   | 1.3214   |   1.5714  |       2.78178 |            0.0319635  |                  0.15767   |
|            58 | s03a_amp_only           |     1.18748  | 1.13483  |   1.35884 |       2.67793 |            0.0182648  |                  0.497825  |
|            58 | shape_only              |     1.13192  | 0.94495  |   1.29956 |       2.54574 |            0.0182648  |                  0.54667   |
|            58 | signed_shared_shrinkage |     1.1876   | 1.16824  |   1.28298 |       2.76003 |            0.0319635  |                  0.778252  |
|            58 | stave_only              |     0.977862 | 0.977862 |   1       |       2.69645 |            0.0273973  |                  0.981195  |
|            58 | template_phase_base     |     2.6428   | 2.6428   |   2.77317 |       3.54397 |            0.0776256  |                  3.68782   |
|            59 | amplitude_only          |     1.29685  | 1.2676   |   1.40571 |       2.45879 |            0.0122324  |                 -1.34559   |
|            59 | full_monotone_log_amp   |     1.24522  | 1.18598  |   1.31127 |       2.46477 |            0.0131062  |                 -1.31308   |
|            59 | hgb_full_unconstrained  |     1.26298  | 1.21585  |   1.30043 |       2.39764 |            0.0122324  |                 -1.42354   |
|            59 | monotone_residual_table |     1.5      | 1.3456   |   1.56166 |       2.59383 |            0.0157274  |                 -1.18636   |
|            59 | robust_heavytail_table  |     1.48042  | 1.41517  |   1.56166 |       2.59649 |            0.0157274  |                 -1.08288   |
|            59 | s03a_amp_only           |     1.45871  | 1.39818  |   1.51981 |       2.54019 |            0.0144168  |                 -0.959826  |
|            59 | shape_only              |     1.22855  | 1.17519  |   1.28516 |       2.46191 |            0.0126693  |                 -1.19138   |
|            59 | signed_shared_shrinkage |     1.31744  | 1.26328  |   1.49915 |       2.57631 |            0.0174749  |                 -0.513133  |
|            59 | stave_only              |     1.39106  | 1.10894  |   1.49644 |       2.52147 |            0.017038   |                 -0.323298  |
|            59 | template_phase_base     |     2.99232  | 2.9828   |   3.12333 |       3.34278 |            0.0677152  |                  3.06363   |
|            60 | amplitude_only          |     1.23953  | 1.20366  |   1.3181  |       2.30735 |            0.0123762  |                 -1.15111   |
|            60 | full_monotone_log_amp   |     1.17399  | 1.11657  |   1.23729 |       2.14627 |            0.0123762  |                 -0.723157  |
|            60 | hgb_full_unconstrained  |     1.22758  | 1.16501  |   1.26839 |       2.10963 |            0.0165017  |                 -0.978776  |
|            60 | monotone_residual_table |     1.23065  | 1.23065  |   1.25    |       2.42144 |            0.0156766  |                 -0.327281  |
|            60 | robust_heavytail_table  |     1.24164  | 1.23065  |   1.26765 |       2.42047 |            0.0156766  |                 -0.275212  |
|            60 | s03a_amp_only           |     1.3437   | 1.28642  |   1.40037 |       2.39529 |            0.015264   |                  0.179917  |
|            60 | shape_only              |     1.16215  | 1.1236   |   1.18744 |       2.15715 |            0.0140264  |                 -0.392422  |
|            60 | signed_shared_shrinkage |     1.26741  | 1.21502  |   1.35454 |       2.4353  |            0.0165017  |                  0.817623  |
|            60 | stave_only              |     1.12186  | 1.0503   |   1.25    |       2.38599 |            0.0165017  |                  0.96696   |
|            60 | template_phase_base     |     2.66393  | 2.66393  |   2.7113  |       3.279   |            0.0944719  |                  4.08159   |
|            61 | amplitude_only          |     1.92439  | 1.84917  |   2.0825  |       2.84859 |            0.0278671  |                 -0.837736  |
|            61 | full_monotone_log_amp   |     1.84436  | 1.76469  |   1.90092 |       2.66994 |            0.0217935  |                 -0.487916  |
|            61 | hgb_full_unconstrained  |     1.81739  | 1.74733  |   1.92643 |       2.67476 |            0.022508   |                 -0.73385   |
|            61 | monotone_residual_table |     2.10176  | 2.10176  |   2.25257 |       3.07643 |            0.0310825  |                 -0.728796  |
|            61 | robust_heavytail_table  |     2.15729  | 2.10176  |   2.15729 |       3.07767 |            0.0321543  |                 -0.428359  |
|            61 | s03a_amp_only           |     2.12996  | 1.99696  |   2.20649 |       3.00806 |            0.0314398  |                 -0.267216  |
|            61 | shape_only              |     1.83097  | 1.78123  |   1.8893  |       2.73723 |            0.0232226  |                 -0.381994  |
|            61 | signed_shared_shrinkage |     2.12389  | 1.95025  |   2.20025 |       3.04553 |            0.035727   |                  0.282255  |
|            61 | stave_only              |     1.9666   | 1.77167  |   2.02167 |       2.96517 |            0.0307253  |                  0.465821  |
|            61 | template_phase_base     |     2.70351  | 2.70351  |   2.70351 |       3.20716 |            0.0428725  |                  4.29511   |
|            62 | amplitude_only          |     1.3579   | 1.29608  |   1.41382 |       2.47473 |            0.0115655  |                 -1.02894   |
|            62 | full_monotone_log_amp   |     1.28309  | 1.23823  |   1.35811 |       2.37521 |            0.0103263  |                 -0.913236  |
|            62 | hgb_full_unconstrained  |     1.2974   | 1.24559  |   1.36651 |       2.27287 |            0.00950021 |                 -1.01518   |
|            62 | monotone_residual_table |     1.43743  | 1.38816  |   1.57559 |       2.64762 |            0.0144568  |                 -0.743857  |
|            62 | robust_heavytail_table  |     1.5      | 1.3381   |   1.56257 |       2.64663 |            0.0144568  |                 -0.641538  |
|            62 | s03a_amp_only           |     1.469    | 1.40662  |   1.51263 |       2.58419 |            0.0128046  |                 -0.453692  |
|            62 | shape_only              |     1.26318  | 1.20635  |   1.33068 |       2.36612 |            0.0103263  |                 -0.742871  |
|            62 | signed_shared_shrinkage |     1.37314  | 1.31509  |   1.48528 |       2.60374 |            0.0148699  |                  0.092849  |
|            62 | stave_only              |     1.25     | 1.25     |   1.47032 |       2.54375 |            0.0128046  |                  0.293683  |
|            62 | template_phase_base     |     2.90117  | 2.90117  |   3.02631 |       3.35891 |            0.0929368  |                  3.78351   |
|            63 | amplitude_only          |     1.27544  | 1.17889  |   1.37357 |       2.43213 |            0.0171171  |                 -1.28111   |
|            63 | full_monotone_log_amp   |     1.2464   | 1.15164  |   1.31832 |       2.3057  |            0.0171171  |                 -0.930846  |
|            63 | hgb_full_unconstrained  |     1.27127  | 1.18348  |   1.33548 |       2.22036 |            0.0171171  |                 -1.02767   |
|            63 | monotone_residual_table |     1.43311  | 1.31436  |   1.56436 |       2.68746 |            0.0198198  |                 -1.0538    |
|            63 | robust_heavytail_table  |     1.43311  | 1.34297  |   1.56436 |       2.68872 |            0.0207207  |                 -0.972102  |
|            63 | s03a_amp_only           |     1.39132  | 1.30675  |   1.45699 |       2.62807 |            0.0207207  |                 -0.851434  |
|            63 | shape_only              |     1.2077   | 1.14727  |   1.32399 |       2.30113 |            0.018018   |                 -0.744303  |
|            63 | signed_shared_shrinkage |     1.11121  | 1.11121  |   1.48872 |       2.6404  |            0.0216216  |                 -0.284092  |
|            63 | stave_only              |     1.13298  | 1.05106  |   1.36702 |       2.58929 |            0.0198198  |                 -0.125315  |
|            63 | template_phase_base     |     2.87872  | 2.87872  |   3.01249 |       3.38179 |            0.0963964  |                  3.41413   |
|            65 | amplitude_only          |     1.35817  | 1.20875  |   1.58251 |       1.59163 |            0          |                 -0.660568  |
|            65 | full_monotone_log_amp   |     1.32552  | 1.14288  |   1.5529  |       1.53021 |            0.00505051 |                 -0.246787  |
|            65 | hgb_full_unconstrained  |     1.36865  | 1.18621  |   1.58297 |       1.54512 |            0.00505051 |                 -0.489704  |
|            65 | monotone_residual_table |     1.56958  | 1.33844  |   1.81958 |       1.83396 |            0.00505051 |                 -0.801151  |
|            65 | robust_heavytail_table  |     1.55926  | 1.36763  |   1.81958 |       1.82953 |            0.00505051 |                 -0.751509  |
|            65 | s03a_amp_only           |     1.49464  | 1.33335  |   1.64329 |       1.69913 |            0.00505051 |                 -0.674101  |
|            65 | shape_only              |     1.29789  | 1.09065  |   1.55457 |       1.50451 |            0          |                 -0.336838  |
|            65 | signed_shared_shrinkage |     1.44175  | 1.2373   |   1.65878 |       1.72997 |            0.00505051 |                 -0.31316   |
|            65 | stave_only              |     1.22728  | 1.06067  |   1.53861 |       1.619   |            0.00505051 |                 -0.0865046 |
|            65 | template_phase_base     |     2.88915  | 2.63915  |   3.20541 |       2.57669 |            0.0505051  |                  3.11219   |

## 4. Paired ML-minus-traditional deltas

| ml_method              | traditional_method      | metric                         |   delta_ml_minus_traditional |      ci_low |      ci_high | bootstrap_unit   |
|:-----------------------|:------------------------|:-------------------------------|-----------------------------:|------------:|-------------:|:-----------------|
| hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns                     |                  -0.126251   | -0.298535   | -0.014087    | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | full_rms_ns                    |                  -0.322648   | -0.372219   | -0.237839    | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | tail_frac_abs_gt5ns            |                  -0.00586836 | -0.0131447  | -0.00271964  | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | bias_vs_log_amp_slope_ns       |                  -1.12993    | -1.41054    | -0.858517    | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | calibration_coverage_abs_le2ns |                   0.0558581  |  0.0414032  |  0.140414    | heldout_run      |
| full_monotone_log_amp  | signed_shared_shrinkage | sigma68_ns                     |                  -0.158629   | -0.291078   | -0.0304932   | heldout_run      |
| full_monotone_log_amp  | signed_shared_shrinkage | full_rms_ns                    |                  -0.279752   | -0.346947   | -0.174063    | heldout_run      |
| full_monotone_log_amp  | signed_shared_shrinkage | tail_frac_abs_gt5ns            |                  -0.00630998 | -0.0133235  | -0.00330169  | heldout_run      |
| full_monotone_log_amp  | signed_shared_shrinkage | bias_vs_log_amp_slope_ns       |                  -0.965863   | -1.20397    | -0.724675    | heldout_run      |
| full_monotone_log_amp  | signed_shared_shrinkage | calibration_coverage_abs_le2ns |                   0.0571533  |  0.0413867  |  0.154301    | heldout_run      |
| amplitude_only         | signed_shared_shrinkage | sigma68_ns                     |                  -0.0820672  | -0.193375   |  0.0334706   | heldout_run      |
| amplitude_only         | signed_shared_shrinkage | full_rms_ns                    |                  -0.152198   | -0.18336    | -0.121601    | heldout_run      |
| amplitude_only         | signed_shared_shrinkage | tail_frac_abs_gt5ns            |                  -0.00411702 | -0.00862984 | -0.00277855  | heldout_run      |
| amplitude_only         | signed_shared_shrinkage | bias_vs_log_amp_slope_ns       |                  -1.21819    | -1.58015    | -0.929768    | heldout_run      |
| amplitude_only         | signed_shared_shrinkage | calibration_coverage_abs_le2ns |                   0.0407385  |  0.0153482  |  0.118736    | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | sigma68_ns                     |                  -0.196222   | -0.327411   | -0.0689971   | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | full_rms_ns                    |                  -0.337354   | -0.39807    | -0.262911    | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | tail_frac_abs_gt5ns            |                  -0.00438497 | -0.010963   | -0.00146448  | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | bias_vs_log_amp_slope_ns       |                  -0.238      | -0.503042   | -0.0291469   | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | calibration_coverage_abs_le2ns |                   0.0637904  |  0.0520072  |  0.173638    | heldout_run      |
| hgb_full_unconstrained | robust_heavytail_table  | sigma68_ns                     |                  -0.16907    | -0.288483   | -0.0793394   | heldout_run      |
| hgb_full_unconstrained | robust_heavytail_table  | full_rms_ns                    |                  -0.339923   | -0.39646    | -0.266697    | heldout_run      |
| hgb_full_unconstrained | robust_heavytail_table  | tail_frac_abs_gt5ns            |                  -0.00465019 | -0.0115481  | -0.00176432  | heldout_run      |
| hgb_full_unconstrained | robust_heavytail_table  | bias_vs_log_amp_slope_ns       |                  -0.385716   | -0.56273    | -0.194955    | heldout_run      |
| hgb_full_unconstrained | robust_heavytail_table  | calibration_coverage_abs_le2ns |                   0.0957867  |  0.0504463  |  0.17576     | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | sigma68_ns                     |                  -0.16375    | -0.260151   | -0.12592     | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | full_rms_ns                    |                  -0.287526   | -0.342662   | -0.205763    | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | tail_frac_abs_gt5ns            |                  -0.00355944 | -0.00745774 | -0.000554955 | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | bias_vs_log_amp_slope_ns       |                  -0.590654   | -0.863971   | -0.332462    | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | calibration_coverage_abs_le2ns |                   0.0484504  |  0.030984   |  0.0592372   | heldout_run      |

## 5. Support map

Strata are attached to held-out pair residuals from raw pulse features: mean amplitude, stave pair, max peak-sample bin, max train-template RMSE, saturation boundary proxy, max pretrigger RMS bin, and P09a-like anomaly atom. Rows below are the supported primary HGB-minus-signed-prior sigma68 deltas.

| stratum_type                | stratum_value                    | ml_method              | traditional_method      | metric     |   support_count_pairs |   delta_ml_minus_traditional |     ci_low |      ci_high | bootstrap_unit   |
|:----------------------------|:---------------------------------|:-----------------------|:------------------------|:-----------|----------------------:|-----------------------------:|-----------:|-------------:|:-----------------|
| amplitude_stratum           | amp[4000,7000)                   | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   492 |                   -0.853923  | -0.986546  | -0.623392    | heldout_run      |
| amplitude_stratum           | amp[1500,2500)                   | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  3901 |                   -0.159725  | -0.262097  | -0.0989029   | heldout_run      |
| amplitude_stratum           | amp[2500,4000)                   | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  6811 |                   -0.105418  | -0.266716  |  0.0314455   | heldout_run      |
| amplitude_stratum           | amp[1000,1500)                   | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   256 |                    0.164261  | -0.0478637 |  0.330378    | heldout_run      |
| anomaly_stratum             | broad_width                      | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   252 |                   -0.720147  | -0.845984  | -0.416598    | heldout_run      |
| anomaly_stratum             | delayed_peak+saturation_boundary | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   233 |                   -0.270931  | -0.531311  |  0.000383094 | heldout_run      |
| anomaly_stratum             | delayed_peak                     | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  4549 |                   -0.240584  | -0.368734  | -0.0243868   | heldout_run      |
| anomaly_stratum             | undershoot_area                  | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  1351 |                   -0.191667  | -0.251607  | -0.15336     | heldout_run      |
| anomaly_stratum             | saturation_boundary              | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   831 |                   -0.160341  | -0.250295  | -0.0560875   | heldout_run      |
| anomaly_stratum             | common                           | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  4016 |                   -0.158917  | -0.221415  | -0.0486765   | heldout_run      |
| peak_sample_stratum         | peak[8,12)                       | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  6883 |                   -0.298538  | -0.387352  | -0.230685    | heldout_run      |
| peak_sample_stratum         | peak[6,8)                        | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  2155 |                   -0.20707   | -0.261711  | -0.107972    | heldout_run      |
| peak_sample_stratum         | peak[4,6)                        | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  1474 |                   -0.20287   | -0.251673  | -0.156793    | heldout_run      |
| peak_sample_stratum         | peak[12,99)                      | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   906 |                   -0.144605  | -0.205465  | -0.0829625   | heldout_run      |
| pretrigger_stratum          | pre_rms[0,20)                    | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  7607 |                   -0.266738  | -0.376259  | -0.13125     | heldout_run      |
| pretrigger_stratum          | pre_rms[60,99999)                | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  3132 |                   -0.209642  | -0.261466  | -0.160335    | heldout_run      |
| pretrigger_stratum          | pre_rms[20,60)                   | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   721 |                   -0.166371  | -0.239523  | -0.0538788   | heldout_run      |
| q_template_stratum          | q[0.1,0.16)                      | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  3456 |                   -0.354183  | -0.472059  | -0.267686    | heldout_run      |
| q_template_stratum          | q[0.06,0.1)                      | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  2097 |                   -0.278223  | -0.416223  | -0.205112    | heldout_run      |
| q_template_stratum          | q[0.16,999)                      | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  5202 |                   -0.167888  | -0.219569  | -0.0763469   | heldout_run      |
| q_template_stratum          | q[0,0.06)                        | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                   705 |                   -0.0848604 | -0.197827  | -0.00793483  | heldout_run      |
| saturation_boundary_stratum | near_or_clipped                  | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  2145 |                   -0.207537  | -0.322828  | -0.0569893   | heldout_run      |
| saturation_boundary_stratum | clear                            | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  9315 |                   -0.122921  | -0.269099  | -0.0113248   | heldout_run      |
| stave_stratum               | B6-B8                            | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  3820 |                   -0.093664  | -0.252592  |  0.0692596   | heldout_run      |
| stave_stratum               | B4-B8                            | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  3820 |                   -0.0856874 | -0.257881  |  0.0946111   | heldout_run      |
| stave_stratum               | B4-B6                            | hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns |                  3820 |                   -0.0321353 | -0.15098   |  0.0901515   | heldout_run      |

Full support-map metrics are in `support_map_metrics.csv`; paired support deltas are in `support_map_paired_deltas.csv`.

## 6. Leakage checks

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| amplitude_only_shuffled_target_sigma68            |     2.67456 |        2.88915 |     3.005   |
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| full_monotone_log_amp_shuffled_target_sigma68     |     2.68173 |        2.8487  |     3.0104  |
| full_unconstrained_shuffled_target_sigma68        |     2.68756 |        2.83371 |     3.01676 |
| monotone_log_amp_best_direction                   |    -1       |       -1       |     1       |
| shape_only_shuffled_target_sigma68                |     2.6962  |        2.8537  |     2.99896 |
| stave_only_shuffled_target_sigma68                |     2.65388 |        2.83138 |     2.99863 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

## 7. Verdict

`result.json` verdict: `hgb_gain_support_map_inconclusive_or_leakage_limited`.
Original HGB sigma68 is `1.394 ns` versus S03a `1.551 ns`, signed shrinkage `1.540 ns`, monotone table `1.645 ns`, and robust heavy-tail table `1.577 ns`.
Supported strata with HGB sigma68 gain over signed prior: `20`; unsupported/failing strata: `26`.
The monotone-log-amplitude HGB is `1.373 ns`; shape-only is `1.360 ns`; stave-only is `1.372 ns`.

## 8. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03h_1781024797_1607_4a1b6480_support_map.py --config configs/s03h_1781024797_1607_4a1b6480_support_map.yaml
```

Artifacts: `reproduction_match_table.csv`, `reference_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `paired_deltas.csv`, `support_map_metrics.csv`, `support_map_paired_deltas.csv`, `pairwise_residuals.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
