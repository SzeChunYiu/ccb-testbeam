# S06a: charge-proxy timing-resolution monotonicity after S14b

- **Ticket:** 1781021805.1799.6d33505e
- **Worker:** testbeam-laptop-4
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo.
- **Split:** leave-one-run-out over Sample-II runs 58, 59, 60, 61, 62, 63, 65; CIs resample held-out runs as event-paired blocks.

## 1. Raw reproduction gate

| quantity                                                  |      reference |     reproduced |        delta | pass   |
|:----------------------------------------------------------|---------------:|---------------:|-------------:|:-------|
| total selected B-stave pulses                             | 640737         | 640737         |  0           | True   |
| sample_ii_analysis selected_pulses                        | 125096         | 125096         |  0           | True   |
| sample_ii_analysis B2                                     |  88213         |  88213         |  0           | True   |
| sample_ii_analysis B4                                     |  21229         |  21229         |  0           | True   |
| sample_ii_analysis B6                                     |  11148         |  11148         |  0           | True   |
| sample_ii_analysis B8                                     |   4506         |   4506         |  0           | True   |
| S00 selected B-stave pulses from raw ROOT                 | 640737         | 640737         |  0           | True   |
| S14b valid event rows after charge cut                    | 584406         | 584406         |  0           | True   |
| S14b invalid event rows removed after raw reproduction    |    196         |    196         |  0           | True   |
| S14b nominal traditional charge-depth res68 from raw ROOT |      0.0211892 |      0.0211892 |  3.49058e-11 | True   |
| S14b nominal ML charge-depth res68 from raw ROOT          |      0.0250078 |      0.0250078 | -1.82668e-11 | True   |

The S00/S14b raw extraction and nominal S14b charge-depth closure ran before timing model fitting.

## 2. Methods

Traditional timing is the S03d hierarchical amp-only timewalk model on the frozen S02 template-phase pickoff. The ML timing model is a regularized Ridge residual corrector trained by run split on waveform shape, P04/P07 charge proxy, S14b depth, saturation flags, and anomaly summaries; it excludes run number, event id, event order, other-stave timing, and held-out labels. The ML uncertainty model uses the same non-ID features and is used only for the pull-width diagnostic.

Matched strata combine S14b depth, saturation, peak-sample phase, late-charge pile-up proxy, baseline RMS proxy, and anomaly flag. Charge-bin slopes are in ns per full low-to-high charge-quantile span; negative means resolution improves at higher charge.

## 3. Pooled held-out timing

| method                   |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width |
|:-------------------------|-------------------:|------------:|-------------:|--------------:|----------------------:|-------------:|
| ml_charge_ridge          |              11460 |    1.14797  |      1.37578 |       2.50643 |             0.0162304 |      2.08819 |
| template_phase_base      |              11460 |   -3.72262  |      2.74141 |       3.30837 |             0.0813264 |      1.20681 |
| traditional_hierarchical |              11460 |    0.941629 |      1.251   |       2.50388 |             0.0153578 |      2.00151 |

| method                   | sigma68_ns_ci95                          | full_rms_ns_ci95                        | tail_frac_abs_gt5ns_ci95                     | pull_width_ci95                         | one_axis_sigma68_slope_ci95                | matched_sigma68_slope_ci95                 |
|:-------------------------|:-----------------------------------------|:----------------------------------------|:---------------------------------------------|:----------------------------------------|:-------------------------------------------|:-------------------------------------------|
| ml_charge_ridge          | [1.2006072966963288, 1.6512958892670921] | [2.322358880128902, 2.682941610532236]  | [0.011636488840954133, 0.020864926067157053] | [1.808477668640612, 2.2805500291305796] | [0.22026908115801414, 0.714998868329258]   | [0.08464394393748811, 0.4816522359641557]  |
| template_phase_base      | [2.6824285968099835, 2.992319268962799]  | [3.249117632829225, 3.3522148352440677] | [0.05563412697020568, 0.0923253485758073]    | [1.117033025011843, 1.2315744562838413] | [-0.03288576465031896, 0.2656447597664879] | [0.005525861463577646, 0.2073297416580752] |
| traditional_hierarchical | [1.0820899063255311, 1.4820126772993183] | [2.3277351737253147, 2.676836709818035] | [0.011635946650418063, 0.020169207860507226] | [1.799739332475361, 2.1764507903631034] | [0.26427650737149616, 0.8476727126927126]  | [0.09101074405453188, 0.4818028791187536]  |

ML-minus-traditional deltas:

| comparison                                     | sigma68_ns_ci95                            | full_rms_ns_ci95                              | tail_frac_abs_gt5ns_ci95                       | pull_width_ci95                             | one_axis_sigma68_slope_ci95                   | matched_sigma68_slope_ci95                   |
|:-----------------------------------------------|:-------------------------------------------|:----------------------------------------------|:-----------------------------------------------|:--------------------------------------------|:----------------------------------------------|:---------------------------------------------|
| ml_charge_ridge_minus_traditional_hierarchical | [0.07187274629117701, 0.19755603309595693] | [-0.023457349606485565, 0.018326014599757513] | [-0.0004911976688047455, 0.002327987584066219] | [-0.33776247909708945, 0.44151757273463277] | [-0.16695486383739938, -0.030974893378478967] | [-0.09139038130356063, 0.050701074393246934] |

## 4. Held-out runs

|   heldout_run | method                   |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width |   n_pair_residuals |
|--------------:|:-------------------------|-------------:|--------------:|----------------------:|-------------:|-------------------:|
|            58 | ml_charge_ridge          |     1.07551  |       2.3963  |            0.0182648  |     2.62874  |                219 |
|            58 | template_phase_base      |     2.6428   |       3.54397 |            0.0776256  |     1.34099  |                219 |
|            58 | traditional_hierarchical |     0.766925 |       2.55981 |            0.0182648  |     3.33775  |                219 |
|            59 | ml_charge_ridge          |     1.27433  |       2.38398 |            0.0117955  |     2.14095  |               2289 |
|            59 | template_phase_base      |     2.99232  |       3.34278 |            0.0677152  |     1.11712  |               2289 |
|            59 | traditional_hierarchical |     1.22376  |       2.40595 |            0.0122324  |     1.96603  |               2289 |
|            60 | ml_charge_ridge          |     1.16664  |       2.28738 |            0.0160891  |     1.59915  |               2424 |
|            60 | template_phase_base      |     2.66393  |       3.279   |            0.0944719  |     1.23089  |               2424 |
|            60 | traditional_hierarchical |     1.05251  |       2.2845  |            0.0127888  |     2.17053  |               2424 |
|            61 | ml_charge_ridge          |     1.82171  |       2.79873 |            0.0228653  |     2.32764  |               2799 |
|            61 | template_phase_base      |     2.70351  |       3.20716 |            0.0428725  |     1.18629  |               2799 |
|            61 | traditional_hierarchical |     1.63537  |       2.77569 |            0.0228653  |     1.69728  |               2799 |
|            62 | ml_charge_ridge          |     1.2958   |       2.46059 |            0.0107394  |     2.18208  |               2421 |
|            62 | template_phase_base      |     2.90117  |       3.35891 |            0.0929368  |     1.15778  |               2421 |
|            62 | traditional_hierarchical |     1.18377  |       2.44336 |            0.0107394  |     2.06404  |               2421 |
|            63 | ml_charge_ridge          |     1.19078  |       2.4707  |            0.0189189  |     1.87076  |               1110 |
|            63 | template_phase_base      |     2.87872  |       3.38179 |            0.0963964  |     1.17476  |               1110 |
|            63 | traditional_hierarchical |     1.11004  |       2.49556 |            0.0189189  |     2.24818  |               1110 |
|            65 | ml_charge_ridge          |     1.28143  |       1.53728 |            0.00505051 |     1.34524  |                198 |
|            65 | template_phase_base      |     2.88915  |       2.57669 |            0.0505051  |     0.891851 |                198 |
|            65 | traditional_hierarchical |     1.21984  |       1.44948 |            0.00505051 |     1.18826  |                198 |

## 5. Charge and depth controls

| method                   |   charge_bin |   n_pair_residuals |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width |
|:-------------------------|-------------:|-------------------:|-------------:|--------------:|----------------------:|-------------:|
| ml_charge_ridge          |            0 |               2292 |     1.07917  |       1.93576 |             0.0056719 |      2.20229 |
| ml_charge_ridge          |            1 |               2292 |     1.37645  |       2.04363 |             0.0061082 |      1.70554 |
| ml_charge_ridge          |            2 |               2292 |     1.46691  |       1.96028 |             0.0069808 |      1.76108 |
| ml_charge_ridge          |            3 |               2292 |     1.55463  |       2.61799 |             0.0139616 |      2.09249 |
| ml_charge_ridge          |            4 |               2292 |     1.58116  |       3.54971 |             0.0484293 |      2.5412  |
| traditional_hierarchical |            0 |               2292 |     0.859693 |       1.92465 |             0.0056719 |      2.23876 |
| traditional_hierarchical |            1 |               2292 |     1.25079  |       2.01613 |             0.0061082 |      1.61189 |
| traditional_hierarchical |            2 |               2292 |     1.34784  |       1.91609 |             0.0069808 |      1.42159 |
| traditional_hierarchical |            3 |               2292 |     1.45703  |       2.63043 |             0.0139616 |      1.80534 |
| traditional_hierarchical |            4 |               2292 |     1.52126  |       3.57266 |             0.0453752 |      2.34849 |

Depth-by-charge excerpt:

| method                   |   depth_idx |   charge_bin |   n_pair_residuals |   sigma68_ns |
|:-------------------------|------------:|-------------:|-------------------:|-------------:|
| ml_charge_ridge          |           3 |            0 |               2292 |     1.07917  |
| ml_charge_ridge          |           3 |            1 |               2292 |     1.37645  |
| ml_charge_ridge          |           3 |            2 |               2292 |     1.46691  |
| ml_charge_ridge          |           3 |            3 |               2292 |     1.55463  |
| ml_charge_ridge          |           3 |            4 |               2292 |     1.58116  |
| traditional_hierarchical |           3 |            0 |               2292 |     0.859693 |
| traditional_hierarchical |           3 |            1 |               2292 |     1.25079  |
| traditional_hierarchical |           3 |            2 |               2292 |     1.34784  |
| traditional_hierarchical |           3 |            3 |               2292 |     1.45703  |
| traditional_hierarchical |           3 |            4 |               2292 |     1.52126  |

Matched-stratum weighted slopes:

| method                   | metric     |   matched_slope_per_charge_quantile |   n_matched_strata |   n_pair_residuals |
|:-------------------------|:-----------|------------------------------------:|-------------------:|-------------------:|
| ml_charge_ridge          | sigma68_ns |                           0.328499  |                  7 |              10197 |
| template_phase_base      | sigma68_ns |                           0.0743778 |                  7 |              10197 |
| traditional_hierarchical | sigma68_ns |                           0.303041  |                  7 |              10197 |

## 6. Leakage audit

| check                                         |   min_value |   median_value |   max_value | pass_all   |
|:----------------------------------------------|------------:|---------------:|------------:|:-----------|
| features_exclude_run_event_cross_stave_target |     1       |        1       |     1       | True       |
| final_models_use_heldout_rows                 |     0       |        0       |     0       | True       |
| ml_shuffled_target_sigma68                    |     2.68882 |        2.82759 |     2.98835 | True       |
| train_heldout_event_id_overlap                |     0       |        0       |     0       | True       |
| train_heldout_run_overlap                     |     0       |        0       |     0       | True       |

## 7. Finding

Raw ROOT reproduction passed before modeling. Pooled held-out sigma68 is 2.741 ns for template phase, 1.251 ns for S03d hierarchical traditional timing, and 1.376 ns for charge-aware Ridge ML (ML - traditional +0.125 ns). The one-axis sigma68 slope versus charge quantile is +0.612 ns for traditional and +0.473 ns for ML; matched-stratum slopes are +0.303 ns and +0.328 ns. Thus charge proxy timing resolution does_not_consistently_improve with increasing charge after the matched controls. The strongest shuffled-target ML sentinel is 2.689 ns, with leakage_flag=False and too_good=False.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s06a_1781021805_1799_6d33505e_charge_proxy_timing_monotonicity.py --config configs/s06a_1781021805_1799_6d33505e_charge_proxy_timing_monotonicity.yaml
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `per_run_benchmark.csv`, `pooled_benchmark.csv`, `pairwise_residuals.csv`, `one_axis_charge_metrics.csv`, `depth_charge_metrics.csv`, `matched_stratum_charge_metrics.csv`, `matched_stratum_slopes.csv`, `run_block_bootstrap.csv`, `ml_minus_traditional_bootstrap.csv`, `leakage_checks.csv`, and `cv_scan.csv`.
