# Study report: S03f - Sample-I downstream-only topology stratification

- **Ticket:** 1781020836.1200.49ae531d
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `/home/billy/Desktop/test_beam/data/root/root`
- **Split:** train on Sample-I run/topology strata; blind held-out evaluation on Sample-II runs 58-63 and 65; CIs resample held-out runs
- **Config:** `configs/s03f_1781020836_1200_49ae531d_topology_stratified_transfer.yaml`
- **Monte Carlo:** none

## 1. Raw-ROOT reproduction gate

The raw selected-pulse counts were rebuilt first. The original S03e all-three-downstream transfer number is then reproduced by the `all3_downstream` stratum before interpreting any new topology result.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

| quantity                            |   report_value |   reproduced |        delta |   tolerance | pass   |
|:------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| s03e all3 template_phase_base       |        2.04594 |      2.04594 |  0           |       1e-09 | True   |
| s03e all3 analytic_amp_only         |        1.49467 |      1.49467 | -1.66533e-14 |       1e-09 | True   |
| s03e all3 monotonic_binned_timewalk |        1.39797 |      1.39797 |  0           |       1e-09 | True   |
| s03e all3 waveform_ridge            |        1.47404 |      1.47404 |  3.33067e-15 |       1e-09 | True   |

## 2. Training strata

| stratum                        |   train_runs |   train_events |   train_pulses |   events_downstream_2 |   events_downstream_3 |   events_b2_selected |   events_b2_terminal_like |   events_b2_penetrating_like |   analytic_alpha |   binned_n_bins |   ml_alpha |
|:-------------------------------|-------------:|---------------:|---------------:|----------------------:|----------------------:|---------------------:|--------------------------:|-----------------------------:|-----------------:|----------------:|-----------:|
| all3_downstream                |           25 |           1260 |           3780 |                     0 |                  1260 |                 1206 |                         0 |                         1194 |              100 |               4 |        100 |
| all3_b2_selected               |           25 |           1206 |           3618 |                     0 |                  1206 |                 1206 |                         0 |                         1194 |              100 |               6 |        100 |
| all3_b2_not_selected           |           15 |             54 |            162 |                     0 |                    54 |                    0 |                         0 |                            0 |              100 |               4 |        100 |
| exactly2_downstream            |           24 |           2986 |           5972 |                  2986 |                     0 |                 2815 |                         0 |                         2717 |               10 |               4 |        100 |
| ge2_excluding_b2_terminal_like |           25 |           4246 |           9752 |                  2986 |                  1260 |                 4021 |                         0 |                         3911 |              100 |               8 |        100 |
| b2_penetrating_ge2             |           25 |           3911 |           9016 |                  2717 |                  1194 |                 3911 |                         0 |                         3911 |              100 |              10 |        100 |

The P08a terminal-B2-like definition requires B2 selected with zero downstream selected staves and low downstream charge. It is therefore explicitly excluded from the `ge2_excluding_b2_terminal_like` training set, but the exclusion removes zero events once at least two downstream staves are required.

## 3. Blind Sample-II transfer

Pooled values are pairwise B4/B6/B8 `sigma68` on Sample-II all-hit events. Lower is better.

| stratum                        | method                    |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-------------------------------|:--------------------------|---------:|---------:|----------:|-------------------:|----------------------:|
| all3_b2_not_selected           | analytic_amp_only         |  1.51887 |  1.49086 |   1.54117 |              11460 |             0.0911867 |
| all3_b2_not_selected           | monotonic_binned_timewalk |  2.8119  |  2.8119  |   2.8119  |              11460 |             0.090925  |
| all3_b2_not_selected           | template_phase_base       |  5.6238  |  5.6238  |   5.6238  |              11460 |             0.385428  |
| all3_b2_not_selected           | waveform_ridge            |  1.39042 |  1.36389 |   1.42848 |              11460 |             0.0905759 |
| all3_b2_selected               | analytic_amp_only         |  2.17879 |  2.02422 |   2.35681 |              11460 |             0.0267016 |
| all3_b2_selected               | monotonic_binned_timewalk |  2.19746 |  2       |   2.32483 |              11460 |             0.0382199 |
| all3_b2_selected               | template_phase_base       |  3.39966 |  3.14966 |   3.39966 |              11460 |             0.349476  |
| all3_b2_selected               | waveform_ridge            |  2.08973 |  1.93391 |   2.34108 |              11460 |             0.0236475 |
| all3_downstream                | analytic_amp_only         |  1.49467 |  1.37272 |   1.70992 |              11460 |             0.0207679 |
| all3_downstream                | monotonic_binned_timewalk |  1.39797 |  1.23179 |   1.5     |              11460 |             0.0356021 |
| all3_downstream                | template_phase_base       |  2.04594 |  1.79594 |   2.04594 |              11460 |             0.0997382 |
| all3_downstream                | waveform_ridge            |  1.47404 |  1.41166 |   1.62844 |              11460 |             0.0178883 |
| b2_penetrating_ge2             | analytic_amp_only         |  3.46598 |  3.4238  |   3.50621 |              11460 |             0.119895  |
| b2_penetrating_ge2             | monotonic_binned_timewalk |  3.83003 |  3.62418 |   3.88353 |              11460 |             0.181239  |
| b2_penetrating_ge2             | template_phase_base       |  3.23706 |  3.23706 |   3.48706 |              11460 |             0.183508  |
| b2_penetrating_ge2             | waveform_ridge            |  3.49274 |  3.41499 |   3.58389 |              11460 |             0.13377   |
| exactly2_downstream            | analytic_amp_only         | 12.0448  | 11.954   |  12.1512  |              11460 |             0.769546  |
| exactly2_downstream            | monotonic_binned_timewalk | 13.225   | 13.2087  |  13.4587  |              11460 |             0.818586  |
| exactly2_downstream            | template_phase_base       | 10.4453  |  9.66937 |  10.9291  |              11460 |             0.395812  |
| exactly2_downstream            | waveform_ridge            | 11.9022  | 11.8215  |  11.9922  |              11460 |             0.766579  |
| ge2_excluding_b2_terminal_like | analytic_amp_only         |  2.87553 |  2.86354 |   2.89261 |              11460 |             0.0255672 |
| ge2_excluding_b2_terminal_like | monotonic_binned_timewalk |  2.97999 |  2.97999 |   2.97999 |              11460 |             0.0276614 |
| ge2_excluding_b2_terminal_like | template_phase_base       |  2.62991 |  2.37991 |   2.87991 |              11460 |             0.132635  |
| ge2_excluding_b2_terminal_like | waveform_ridge            |  2.86705 |  2.81921 |   2.92733 |              11460 |             0.0235602 |

Compact view:

| stratum                        |   analytic_amp_only |   monotonic_binned_timewalk |   template_phase_base |   waveform_ridge |
|:-------------------------------|--------------------:|----------------------------:|----------------------:|-----------------:|
| all3_b2_not_selected           |             1.51887 |                     2.8119  |               5.6238  |          1.39042 |
| all3_b2_selected               |             2.17879 |                     2.19746 |               3.39966 |          2.08973 |
| all3_downstream                |             1.49467 |                     1.39797 |               2.04594 |          1.47404 |
| b2_penetrating_ge2             |             3.46598 |                     3.83003 |               3.23706 |          3.49274 |
| exactly2_downstream            |            12.0448  |                    13.225   |              10.4453  |         11.9022  |
| ge2_excluding_b2_terminal_like |             2.87553 |                     2.97999 |               2.62991 |          2.86705 |

## 4. Held-out runs

| stratum                        |   heldout_run | method                    |     value |    ci_low |   ci_high |   n_pair_residuals |
|:-------------------------------|--------------:|:--------------------------|----------:|----------:|----------:|-------------------:|
| all3_b2_not_selected           |            58 | analytic_amp_only         |  1.73144  |  1.55332  |  2.12516  |                219 |
| all3_b2_not_selected           |            58 | monotonic_binned_timewalk |  2.8119   |  2.8119   |  2.8119   |                219 |
| all3_b2_not_selected           |            58 | template_phase_base       |  5.6238   |  5.6238   |  5.6238   |                219 |
| all3_b2_not_selected           |            58 | waveform_ridge            |  1.66558  |  1.46505  |  1.95435  |                219 |
| all3_b2_not_selected           |            59 | analytic_amp_only         |  1.4826   |  1.43289  |  1.54027  |               2289 |
| all3_b2_not_selected           |            59 | monotonic_binned_timewalk |  2.8119   |  2.8119   |  2.8119   |               2289 |
| all3_b2_not_selected           |            59 | template_phase_base       |  5.6238   |  5.6238   |  5.6238   |               2289 |
| all3_b2_not_selected           |            59 | waveform_ridge            |  1.37168  |  1.32477  |  1.42497  |               2289 |
| all3_b2_not_selected           |            60 | analytic_amp_only         |  1.56036  |  1.51042  |  1.60183  |               2424 |
| all3_b2_not_selected           |            60 | monotonic_binned_timewalk |  2.8119   |  2.8119   |  2.8119   |               2424 |
| all3_b2_not_selected           |            60 | template_phase_base       |  5.6238   |  5.6238   |  5.6238   |               2424 |
| all3_b2_not_selected           |            60 | waveform_ridge            |  1.45509  |  1.40367  |  1.52254  |               2424 |
| all3_b2_not_selected           |            61 | analytic_amp_only         |  1.5367   |  1.50091  |  1.56532  |               2799 |
| all3_b2_not_selected           |            61 | monotonic_binned_timewalk |  2.8119   |  2.8119   |  2.8119   |               2799 |
| all3_b2_not_selected           |            61 | template_phase_base       |  5.6238   |  5.6238   |  5.6238   |               2799 |
| all3_b2_not_selected           |            61 | waveform_ridge            |  1.35589  |  1.3123   |  1.39392  |               2799 |
| all3_b2_not_selected           |            62 | analytic_amp_only         |  1.51094  |  1.46333  |  1.55255  |               2421 |
| all3_b2_not_selected           |            62 | monotonic_binned_timewalk |  2.8119   |  2.8119   |  2.8119   |               2421 |
| all3_b2_not_selected           |            62 | template_phase_base       |  5.6238   |  5.6238   |  5.6238   |               2421 |
| all3_b2_not_selected           |            62 | waveform_ridge            |  1.39122  |  1.34062  |  1.44326  |               2421 |
| all3_b2_not_selected           |            63 | analytic_amp_only         |  1.48526  |  1.42261  |  1.60313  |               1110 |
| all3_b2_not_selected           |            63 | monotonic_binned_timewalk |  2.8119   |  2.8119   |  2.8119   |               1110 |
| all3_b2_not_selected           |            63 | template_phase_base       |  5.6238   |  5.6238   |  5.6238   |               1110 |
| all3_b2_not_selected           |            63 | waveform_ridge            |  1.37472  |  1.27041  |  1.44989  |               1110 |
| all3_b2_not_selected           |            65 | analytic_amp_only         |  1.47544  |  1.3486   |  1.56744  |                198 |
| all3_b2_not_selected           |            65 | monotonic_binned_timewalk |  2.8119   |  2.8119   |  2.8119   |                198 |
| all3_b2_not_selected           |            65 | template_phase_base       |  5.6238   |  5.6238   |  5.6238   |                198 |
| all3_b2_not_selected           |            65 | waveform_ridge            |  1.31799  |  1.20049  |  1.40855  |                198 |
| all3_b2_selected               |            58 | analytic_amp_only         |  1.91725  |  1.81951  |  1.96703  |                219 |
| all3_b2_selected               |            58 | monotonic_binned_timewalk |  1.57483  |  1.57483  |  1.59608  |                219 |
| all3_b2_selected               |            58 | template_phase_base       |  3.14966  |  3.14966  |  3.14966  |                219 |
| all3_b2_selected               |            58 | waveform_ridge            |  1.87791  |  1.7537   |  1.96102  |                219 |
| all3_b2_selected               |            59 | analytic_amp_only         |  2.03815  |  1.91382  |  2.09178  |               2289 |
| all3_b2_selected               |            59 | monotonic_binned_timewalk |  2        |  1.93483  |  2.07483  |               2289 |
| all3_b2_selected               |            59 | template_phase_base       |  3.39966  |  3.14966  |  3.64966  |               2289 |
| all3_b2_selected               |            59 | waveform_ridge            |  1.93597  |  1.87029  |  2.03776  |               2289 |
| all3_b2_selected               |            60 | analytic_amp_only         |  2.11547  |  2.03294  |  2.19222  |               2424 |
| all3_b2_selected               |            60 | monotonic_binned_timewalk |  2.07483  |  2.07483  |  2.25     |               2424 |
| all3_b2_selected               |            60 | template_phase_base       |  3.39966  |  3.14966  |  3.64966  |               2424 |
| all3_b2_selected               |            60 | waveform_ridge            |  2.00369  |  1.92835  |  2.07464  |               2424 |
| all3_b2_selected               |            61 | analytic_amp_only         |  2.57711  |  2.50876  |  2.73584  |               2799 |
| all3_b2_selected               |            61 | monotonic_binned_timewalk |  2.5      |  2.44746  |  2.57483  |               2799 |
| all3_b2_selected               |            61 | template_phase_base       |  3.39966  |  3.14966  |  3.64966  |               2799 |
| all3_b2_selected               |            61 | waveform_ridge            |  2.53162  |  2.42618  |  2.62799  |               2799 |
| all3_b2_selected               |            62 | analytic_amp_only         |  2.08151  |  1.95953  |  2.18374  |               2421 |
| all3_b2_selected               |            62 | monotonic_binned_timewalk |  2        |  1.94746  |  2.19746  |               2421 |
| all3_b2_selected               |            62 | template_phase_base       |  3.39966  |  3.14966  |  3.64966  |               2421 |
| all3_b2_selected               |            62 | waveform_ridge            |  2.00443  |  1.93498  |  2.11614  |               2421 |
| all3_b2_selected               |            63 | analytic_amp_only         |  2.03438  |  1.90722  |  2.18288  |               1110 |
| all3_b2_selected               |            63 | monotonic_binned_timewalk |  2        |  1.82483  |  2.19746  |               1110 |
| all3_b2_selected               |            63 | template_phase_base       |  3.39966  |  3.14966  |  3.89966  |               1110 |
| all3_b2_selected               |            63 | waveform_ridge            |  1.98575  |  1.87657  |  2.09544  |               1110 |
| all3_b2_selected               |            65 | analytic_amp_only         |  1.85606  |  1.70112  |  2.13715  |                198 |
| all3_b2_selected               |            65 | monotonic_binned_timewalk |  1.75     |  1.57483  |  2.22285  |                198 |
| all3_b2_selected               |            65 | template_phase_base       |  3.14966  |  3.14966  |  3.40266  |                198 |
| all3_b2_selected               |            65 | waveform_ridge            |  1.86806  |  1.70056  |  2.01643  |                198 |
| all3_downstream                |            58 | analytic_amp_only         |  1.33262  |  1.25483  |  1.37901  |                219 |
| all3_downstream                |            58 | monotonic_binned_timewalk |  0.897972 |  0.897972 |  0.897972 |                219 |
| all3_downstream                |            58 | template_phase_base       |  1.79594  |  1.79594  |  1.79594  |                219 |
| all3_downstream                |            58 | waveform_ridge            |  1.31124  |  1.182    |  1.39915  |                219 |
| all3_downstream                |            59 | analytic_amp_only         |  1.37481  |  1.34674  |  1.47829  |               2289 |
| all3_downstream                |            59 | monotonic_binned_timewalk |  1.25     |  1.14797  |  1.38643  |               2289 |
| all3_downstream                |            59 | template_phase_base       |  2.25     |  2.04594  |  2.45999  |               2289 |
| all3_downstream                |            59 | waveform_ridge            |  1.40438  |  1.3662   |  1.45928  |               2289 |
| all3_downstream                |            60 | analytic_amp_only         |  1.41724  |  1.36029  |  1.51624  |               2424 |
| all3_downstream                |            60 | monotonic_binned_timewalk |  1.25     |  1.14797  |  1.39797  |               2424 |
| all3_downstream                |            60 | template_phase_base       |  1.79594  |  1.79594  |  2.04594  |               2424 |
| all3_downstream                |            60 | waveform_ridge            |  1.44071  |  1.39531  |  1.49856  |               2424 |
| all3_downstream                |            61 | analytic_amp_only         |  1.79299  |  1.74573  |  1.9144   |               2799 |
| all3_downstream                |            61 | monotonic_binned_timewalk |  1.64797  |  1.5      |  1.73193  |               2799 |
| all3_downstream                |            61 | template_phase_base       |  2.25     |  2.04594  |  2.29594  |               2799 |
| all3_downstream                |            61 | waveform_ridge            |  1.78197  |  1.69054  |  1.84122  |               2799 |
| all3_downstream                |            62 | analytic_amp_only         |  1.41333  |  1.36377  |  1.50535  |               2421 |
| all3_downstream                |            62 | monotonic_binned_timewalk |  1.25     |  1.14797  |  1.39797  |               2421 |
| all3_downstream                |            62 | template_phase_base       |  2        |  1.79594  |  2.04594  |               2421 |
| all3_downstream                |            62 | waveform_ridge            |  1.4394   |  1.39819  |  1.49739  |               2421 |
| all3_downstream                |            63 | analytic_amp_only         |  1.40432  |  1.36393  |  1.53533  |               1110 |
| all3_downstream                |            63 | monotonic_binned_timewalk |  1.25     |  1.14797  |  1.39797  |               1110 |
| all3_downstream                |            63 | template_phase_base       |  2.04594  |  1.79594  |  2.46358  |               1110 |
| all3_downstream                |            63 | waveform_ridge            |  1.4475   |  1.39913  |  1.53489  |               1110 |
| all3_downstream                |            65 | analytic_amp_only         |  1.30732  |  1.23883  |  1.44661  |                198 |
| all3_downstream                |            65 | monotonic_binned_timewalk |  1        |  0.897972 |  1.39797  |                198 |
| all3_downstream                |            65 | template_phase_base       |  1.79594  |  1.79594  |  2.29594  |                198 |
| all3_downstream                |            65 | waveform_ridge            |  1.28907  |  1.15633  |  1.40153  |                198 |
| b2_penetrating_ge2             |            58 | analytic_amp_only         |  3.57898  |  3.39919  |  3.6326   |                219 |
| b2_penetrating_ge2             |            58 | monotonic_binned_timewalk |  3.83003  |  3.83003  |  3.83003  |                219 |
| b2_penetrating_ge2             |            58 | template_phase_base       |  2.73706  |  2.73706  |  3.01706  |                219 |
| b2_penetrating_ge2             |            58 | waveform_ridge            |  3.55725  |  3.26071  |  3.67168  |                219 |
| b2_penetrating_ge2             |            59 | analytic_amp_only         |  3.39658  |  3.11038  |  3.49725  |               2289 |
| b2_penetrating_ge2             |            59 | monotonic_binned_timewalk |  3.58003  |  3.33003  |  3.83003  |               2289 |
| b2_penetrating_ge2             |            59 | template_phase_base       |  3.48706  |  3.23706  |  3.73706  |               2289 |
| b2_penetrating_ge2             |            59 | waveform_ridge            |  3.37019  |  3.21234  |  3.49658  |               2289 |
| b2_penetrating_ge2             |            60 | analytic_amp_only         |  3.49094  |  3.38561  |  3.54934  |               2424 |
| b2_penetrating_ge2             |            60 | monotonic_binned_timewalk |  3.83003  |  3.58003  |  3.83003  |               2424 |
| b2_penetrating_ge2             |            60 | template_phase_base       |  3.2412   |  2.98706  |  3.48706  |               2424 |
| b2_penetrating_ge2             |            60 | waveform_ridge            |  3.4959   |  3.38135  |  3.56663  |               2424 |
| b2_penetrating_ge2             |            61 | analytic_amp_only         |  3.57123  |  3.40588  |  3.70549  |               2799 |
| b2_penetrating_ge2             |            61 | monotonic_binned_timewalk |  3.9932   |  3.57815  |  4.08003  |               2799 |
| b2_penetrating_ge2             |            61 | template_phase_base       |  3.48706  |  3.23706  |  3.48706  |               2799 |
| b2_penetrating_ge2             |            61 | waveform_ridge            |  3.68607  |  3.55738  |  3.82474  |               2799 |
| b2_penetrating_ge2             |            62 | analytic_amp_only         |  3.40036  |  3.20488  |  3.48476  |               2421 |
| b2_penetrating_ge2             |            62 | monotonic_binned_timewalk |  3.58469  |  3.33003  |  3.83003  |               2421 |
| b2_penetrating_ge2             |            62 | template_phase_base       |  3.23706  |  2.98706  |  3.48706  |               2421 |
| b2_penetrating_ge2             |            62 | waveform_ridge            |  3.41344  |  3.31608  |  3.50407  |               2421 |
| b2_penetrating_ge2             |            63 | analytic_amp_only         |  3.46836  |  3.29668  |  3.55213  |               1110 |
| b2_penetrating_ge2             |            63 | monotonic_binned_timewalk |  3.83003  |  3.58003  |  3.83003  |               1110 |
| b2_penetrating_ge2             |            63 | template_phase_base       |  3.23706  |  2.73706  |  3.48706  |               1110 |
| b2_penetrating_ge2             |            63 | waveform_ridge            |  3.45464  |  3.31954  |  3.55141  |               1110 |
| b2_penetrating_ge2             |            65 | analytic_amp_only         |  3.47625  |  2.94121  |  3.64801  |                198 |
| b2_penetrating_ge2             |            65 | monotonic_binned_timewalk |  3.83003  |  3.07902  |  3.83003  |                198 |
| b2_penetrating_ge2             |            65 | template_phase_base       |  2.86379  |  2.73706  |  3.60706  |                198 |
| b2_penetrating_ge2             |            65 | waveform_ridge            |  3.49097  |  3.06235  |  3.6836   |                198 |
| exactly2_downstream            |            58 | analytic_amp_only         | 11.065    |  9.83038  | 11.9967   |                219 |
| exactly2_downstream            |            58 | monotonic_binned_timewalk | 12.253    | 10.755    | 12.9757   |                219 |
| exactly2_downstream            |            58 | template_phase_base       | 12.5234   | 10.1791   | 13.0163   |                219 |
| exactly2_downstream            |            58 | waveform_ridge            | 11.0881   |  9.80388  | 11.8052   |                219 |
| exactly2_downstream            |            59 | analytic_amp_only         | 12.1985   | 12.1079   | 12.2734   |               2289 |
| exactly2_downstream            |            59 | monotonic_binned_timewalk | 13.475    | 12.975    | 13.7087   |               2289 |
| exactly2_downstream            |            59 | template_phase_base       |  8.94403  |  8.26587  | 10        |               2289 |
| exactly2_downstream            |            59 | waveform_ridge            | 12.0469   | 11.932    | 12.1199   |               2289 |
| exactly2_downstream            |            60 | analytic_amp_only         | 12.0269   | 11.8731   | 12.1486   |               2424 |
| exactly2_downstream            |            60 | monotonic_binned_timewalk | 13.225    | 13.2087   | 13.4587   |               2424 |
| exactly2_downstream            |            60 | template_phase_base       | 10.6953   | 10.1951   | 11        |               2424 |
| exactly2_downstream            |            60 | waveform_ridge            | 11.8329   | 11.7109   | 11.9583   |               2424 |
| exactly2_downstream            |            61 | analytic_amp_only         | 11.9232   | 11.743    | 12.0463   |               2799 |
| exactly2_downstream            |            61 | monotonic_binned_timewalk | 12.975    | 12.9587   | 13.225    |               2799 |
| exactly2_downstream            |            61 | template_phase_base       |  9.94533  |  8.69533  | 10.4291   |               2799 |
| exactly2_downstream            |            61 | waveform_ridge            | 11.8128   | 11.6449   | 11.9607   |               2799 |
| exactly2_downstream            |            62 | analytic_amp_only         | 11.9653   | 11.7991   | 12.1051   |               2421 |
| exactly2_downstream            |            62 | monotonic_binned_timewalk | 13.2087   | 12.9587   | 13.225    |               2421 |
| exactly2_downstream            |            62 | template_phase_base       |  9.92906  |  8.42906  | 10.9291   |               2421 |
| exactly2_downstream            |            62 | waveform_ridge            | 11.8047   | 11.6627   | 11.9146   |               2421 |
| exactly2_downstream            |            63 | analytic_amp_only         | 12.1053   | 11.8389   | 12.2298   |               1110 |
| exactly2_downstream            |            63 | monotonic_binned_timewalk | 13.225    | 12.9676   | 13.4589   |               1110 |
| exactly2_downstream            |            63 | template_phase_base       | 10.5163   |  9.09817  | 11        |               1110 |
| exactly2_downstream            |            63 | waveform_ridge            | 11.911    | 11.7338   | 12.0645   |               1110 |
| exactly2_downstream            |            65 | analytic_amp_only         | 12.2969   | 11.5391   | 12.6569   |                198 |
| exactly2_downstream            |            65 | monotonic_binned_timewalk | 13.3372   | 12.4665   | 13.7087   |                198 |
| exactly2_downstream            |            65 | template_phase_base       | 10.9291   |  8.5908   | 11.4291   |                198 |
| exactly2_downstream            |            65 | waveform_ridge            | 12.1583   | 11.4404   | 12.4522   |                198 |
| ge2_excluding_b2_terminal_like |            58 | analytic_amp_only         |  2.87561  |  2.82018  |  2.90227  |                219 |
| ge2_excluding_b2_terminal_like |            58 | monotonic_binned_timewalk |  2.97999  |  2.97999  |  2.97999  |                219 |
| ge2_excluding_b2_terminal_like |            58 | template_phase_base       |  2.37991  |  2.12991  |  3.08529  |                219 |
| ge2_excluding_b2_terminal_like |            58 | waveform_ridge            |  2.83162  |  2.7006   |  2.91953  |                219 |
| ge2_excluding_b2_terminal_like |            59 | analytic_amp_only         |  2.85574  |  2.84094  |  2.86637  |               2289 |
| ge2_excluding_b2_terminal_like |            59 | monotonic_binned_timewalk |  2.97999  |  2.97999  |  2.97999  |               2289 |
| ge2_excluding_b2_terminal_like |            59 | template_phase_base       |  2.87991  |  2.83529  |  3.08529  |               2289 |
| ge2_excluding_b2_terminal_like |            59 | waveform_ridge            |  2.80723  |  2.7729   |  2.83977  |               2289 |
| ge2_excluding_b2_terminal_like |            60 | analytic_amp_only         |  2.8751   |  2.86314  |  2.88767  |               2424 |
| ge2_excluding_b2_terminal_like |            60 | monotonic_binned_timewalk |  2.97999  |  2.97999  |  2.97999  |               2424 |
| ge2_excluding_b2_terminal_like |            60 | template_phase_base       |  2.62991  |  2.62991  |  2.84957  |               2424 |
| ge2_excluding_b2_terminal_like |            60 | waveform_ridge            |  2.84923  |  2.81244  |  2.87815  |               2424 |
| ge2_excluding_b2_terminal_like |            61 | analytic_amp_only         |  2.89927  |  2.88655  |  2.91175  |               2799 |
| ge2_excluding_b2_terminal_like |            61 | monotonic_binned_timewalk |  2.97999  |  2.97999  |  2.97999  |               2799 |
| ge2_excluding_b2_terminal_like |            61 | template_phase_base       |  2.12991  |  2.12991  |  2.33529  |               2799 |
| ge2_excluding_b2_terminal_like |            61 | waveform_ridge            |  2.96326  |  2.93114  |  2.98686  |               2799 |
| ge2_excluding_b2_terminal_like |            62 | analytic_amp_only         |  2.86607  |  2.85117  |  2.87993  |               2421 |
| ge2_excluding_b2_terminal_like |            62 | monotonic_binned_timewalk |  2.97999  |  2.97999  |  2.97999  |               2421 |
| ge2_excluding_b2_terminal_like |            62 | template_phase_base       |  2.83529  |  2.62991  |  2.87991  |               2421 |
| ge2_excluding_b2_terminal_like |            62 | waveform_ridge            |  2.8341   |  2.79972  |  2.86734  |               2421 |
| ge2_excluding_b2_terminal_like |            63 | analytic_amp_only         |  2.85833  |  2.8347   |  2.88008  |               1110 |
| ge2_excluding_b2_terminal_like |            63 | monotonic_binned_timewalk |  2.97999  |  2.97999  |  2.97999  |               1110 |
| ge2_excluding_b2_terminal_like |            63 | template_phase_base       |  3.08529  |  2.83529  |  3.12991  |               1110 |
| ge2_excluding_b2_terminal_like |            63 | waveform_ridge            |  2.82102  |  2.75949  |  2.87237  |               1110 |
| ge2_excluding_b2_terminal_like |            65 | analytic_amp_only         |  2.90622  |  2.81312  |  2.9464   |                198 |
| ge2_excluding_b2_terminal_like |            65 | monotonic_binned_timewalk |  2.97999  |  2.97999  |  2.97999  |                198 |
| ge2_excluding_b2_terminal_like |            65 | template_phase_base       |  2.62991  |  2.33529  |  3.12991  |                198 |
| ge2_excluding_b2_terminal_like |            65 | waveform_ridge            |  2.86532  |  2.75476  |  2.95759  |                198 |

## 5. Leakage checks

All train/evaluation splits are by run. Model inputs exclude run id, event id, event order, sample label, and other-stave timing; inter-stave timing is used only to form train-fold targets and held-out scoring residuals. Shuffled-target controls are fit on each stratum and evaluated on Sample II.

| stratum                        | check                                          |    value |
|:-------------------------------|:-----------------------------------------------|---------:|
| all3_b2_not_selected           | analytic_amp_only_shuffled                     |  6.62797 |
| all3_b2_not_selected           | features_include_run_event_or_other_stave_time |  0       |
| all3_b2_not_selected           | fit_targets_use_heldout_sample_ii              |  0       |
| all3_b2_not_selected           | monotonic_binned_timewalk_shuffled             |  5.8635  |
| all3_b2_not_selected           | train_heldout_event_id_overlap                 |  0       |
| all3_b2_not_selected           | train_heldout_run_overlap                      |  0       |
| all3_b2_not_selected           | waveform_ridge_shuffled                        |  6.29459 |
| all3_b2_selected               | analytic_amp_only_shuffled                     |  3.47711 |
| all3_b2_selected               | features_include_run_event_or_other_stave_time |  0       |
| all3_b2_selected               | fit_targets_use_heldout_sample_ii              |  0       |
| all3_b2_selected               | monotonic_binned_timewalk_shuffled             |  3.39966 |
| all3_b2_selected               | train_heldout_event_id_overlap                 |  0       |
| all3_b2_selected               | train_heldout_run_overlap                      |  0       |
| all3_b2_selected               | waveform_ridge_shuffled                        |  3.2694  |
| all3_downstream                | analytic_amp_only_shuffled                     |  2.05691 |
| all3_downstream                | features_include_run_event_or_other_stave_time |  0       |
| all3_downstream                | fit_targets_use_heldout_sample_ii              |  0       |
| all3_downstream                | monotonic_binned_timewalk_shuffled             |  2.04594 |
| all3_downstream                | train_heldout_event_id_overlap                 |  0       |
| all3_downstream                | train_heldout_run_overlap                      |  0       |
| all3_downstream                | waveform_ridge_shuffled                        |  2.024   |
| b2_penetrating_ge2             | analytic_amp_only_shuffled                     |  3.25086 |
| b2_penetrating_ge2             | features_include_run_event_or_other_stave_time |  0       |
| b2_penetrating_ge2             | fit_targets_use_heldout_sample_ii              |  0       |
| b2_penetrating_ge2             | monotonic_binned_timewalk_shuffled             |  3.32594 |
| b2_penetrating_ge2             | train_heldout_event_id_overlap                 |  0       |
| b2_penetrating_ge2             | train_heldout_run_overlap                      |  0       |
| b2_penetrating_ge2             | waveform_ridge_shuffled                        |  3.30687 |
| exactly2_downstream            | analytic_amp_only_shuffled                     | 10.2354  |
| exactly2_downstream            | features_include_run_event_or_other_stave_time |  0       |
| exactly2_downstream            | fit_targets_use_heldout_sample_ii              |  0       |
| exactly2_downstream            | monotonic_binned_timewalk_shuffled             | 10.136   |
| exactly2_downstream            | train_heldout_event_id_overlap                 |  0       |
| exactly2_downstream            | train_heldout_run_overlap                      |  0       |
| exactly2_downstream            | waveform_ridge_shuffled                        | 10.4838  |
| ge2_excluding_b2_terminal_like | analytic_amp_only_shuffled                     |  2.67246 |
| ge2_excluding_b2_terminal_like | features_include_run_event_or_other_stave_time |  0       |
| ge2_excluding_b2_terminal_like | fit_targets_use_heldout_sample_ii              |  0       |
| ge2_excluding_b2_terminal_like | monotonic_binned_timewalk_shuffled             |  2.63722 |
| ge2_excluding_b2_terminal_like | train_heldout_event_id_overlap                 |  0       |
| ge2_excluding_b2_terminal_like | train_heldout_run_overlap                      |  0       |
| ge2_excluding_b2_terminal_like | waveform_ridge_shuffled                        |  2.79581 |

## 6. Verdict

The original all-three Sample-I subset reproduces the S03e result and remains the best transfer source: ML 1.474 ns versus exactly-two ML 11.902 ns; binned 1.398 ns versus exactly-two binned 13.225 ns. Adding exactly-two events through the ge2 terminal-excluded stratum weakens rather than improves the blind Sample-II result, so the strong transfer is consistent with the rare penetrating Sample-I topology rather than terminal-B2-like regimes. A too-good diagnostic was flagged but not promoted: all3_b2_not_selected waveform_ridge=1.390 ns from 54 events. Its train/event overlap checks are zero and shuffled-target controls are poor, but the support is below 100 events and the template baseline is unstable.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03f_1781020836_1200_49ae531d_topology_stratified_transfer.py --config configs/s03f_1781020836_1200_49ae531d_topology_stratified_transfer.yaml
```
