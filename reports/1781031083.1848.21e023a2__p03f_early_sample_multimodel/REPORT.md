# P03f: early-sample waveform ablation against S02b residuals

- **Ticket:** `1781031083.1848.21e023a2`
- **Worker:** `testbeam-laptop-4`
- **Claimed study:** early-sample waveform ablation against S02b residuals with multimodel controls
- **Input:** raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Early window:** waveform samples `[0, 1, 2, 3]` (the same samples used for the nominal median baseline)

## Question and preregistered estimand

The ticket asks whether samples 0-3 carry causal timing information, or mainly nuisance/run structure, before proxy terms are adopted downstream.  The estimand is the B4/B6/B8 event-paired timing width after the S02b global-template timewalk correction:

`r_ab(e; m) = [t_a(e;m) - z_a v^-1] - [t_b(e;m) - z_b v^-1]`,

where `m` is a timing method, `z` is the stave spacing coordinate, and `v^-1 = 0.078 ns/cm`.  The headline metric is

`sigma68(m) = (Q84({r_ab}) - Q16({r_ab})) / 2`.

CIs are event bootstraps inside each held-out run and a nested run-block/event bootstrap for the pooled summary.

## Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before fitting any timing or ML model.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Methods

For every held-out run, the other six Sample-II runs define all train-only objects: the S02 global templates, amplitude-binned S02b template SSE nuisance, and polynomial/ridge timewalk closure. The traditional comparator is `s02b_global_template_timewalk`.

The residual learners target `y_i = t_i(S02b) - mean(t_j(S02b), t_k(S02b))` within the same event and predict a same-pulse correction. Five model families are benchmarked under three waveform masks:

- `ridge`: standardized linear Ridge regression.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: heteroskedastic fully connected neural net.
- `cnn1d`: compact one-dimensional convolutional network over 18 samples.
- `early_late_gated`: new architecture with separate samples-0-3 and samples-4-17 branches mixed by a learned auxiliary-feature gate.

Masks are `full`, `no_samples_0_3`, and `only_samples_0_3`. Features exclude run id, event id, event order, other-stave timings, and pair residuals. Run-family controls use only hand summaries, stave, and coarse predeclared family (`early`, `middle`, `late`) without waveform samples. Shuffled-target controls repeat every nominal waveform model with train targets permuted.

## Pooled Benchmark

| method                            | family      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:----------------------------------|:------------|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------:|
| hgb_no_samples_0_3                | ml          |      1.17068 |  1.13502 |   1.21679 |                 -0.521682 |      -0.832134 |      -0.324511  |              11460 |
| hgb_full                          | ml          |      1.17489 |  1.14333 |   1.22409 |                 -0.517466 |      -0.830302 |      -0.322176  |              11460 |
| hgb_only_samples_0_3              | ml          |      1.20058 |  1.16524 |   1.23786 |                 -0.491783 |      -0.810042 |      -0.29589   |              11460 |
| mlp_full                          | ml          |      1.29302 |  1.24504 |   1.34519 |                 -0.399335 |      -0.729418 |      -0.200804  |              11460 |
| mlp_no_samples_0_3                | ml          |      1.3267  |  1.25581 |   1.3999  |                 -0.365662 |      -0.71657  |      -0.127478  |              11460 |
| ridge_no_samples_0_3              | ml          |      1.36131 |  1.2968  |   1.41945 |                 -0.331046 |      -0.692356 |      -0.116848  |              11460 |
| ridge_full                        | ml          |      1.36386 |  1.29107 |   1.41254 |                 -0.328502 |      -0.696985 |      -0.117868  |              11460 |
| early_late_gated_no_samples_0_3   | ml          |      1.36703 |  1.32405 |   1.42803 |                 -0.32533  |      -0.633231 |      -0.121951  |              11460 |
| ridge_only_samples_0_3            | ml          |      1.38244 |  1.3303  |   1.43766 |                 -0.309918 |      -0.658316 |      -0.115676  |              11460 |
| cnn1d_full                        | ml          |      1.38734 |  1.29665 |   1.44659 |                 -0.305017 |      -0.693753 |      -0.1035    |              11460 |
| early_late_gated_full             | ml          |      1.41988 |  1.33986 |   1.47291 |                 -0.272477 |      -0.650706 |      -0.0711303 |              11460 |
| mlp_only_samples_0_3              | ml          |      1.42584 |  1.32714 |   1.5373  |                 -0.266523 |      -0.649691 |      -0.0107569 |              11460 |
| early_late_gated_only_samples_0_3 | ml          |      1.44715 |  1.34113 |   1.54717 |                 -0.245211 |      -0.643007 |       0.0153011 |              11460 |
| cnn1d_only_samples_0_3            | ml          |      1.45237 |  1.3559  |   1.51619 |                 -0.239988 |      -0.626059 |      -0.0173674 |              11460 |
| cnn1d_no_samples_0_3              | ml          |      1.47948 |  1.33715 |   1.57989 |                 -0.212881 |      -0.648252 |       0.0337277 |              11460 |
| s02b_global_template_timewalk     | traditional |      1.69236 |  1.52208 |   2.00136 |                  0        |       0        |       0         |              11460 |

## Early-Sample Ablation

| method                            |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   tail_frac_vs_traditional_p95 |
|:----------------------------------|-------------:|---------:|----------:|--------------------------:|-------------------------------:|
| cnn1d_full                        |      1.38734 |  1.29665 |   1.44659 |                 -0.305017 |                      0.0288831 |
| cnn1d_no_samples_0_3              |      1.47948 |  1.33715 |   1.57989 |                 -0.212881 |                      0.0337696 |
| cnn1d_only_samples_0_3            |      1.45237 |  1.3559  |   1.51619 |                 -0.239988 |                      0.0323735 |
| early_late_gated_full             |      1.41988 |  1.33986 |   1.47291 |                 -0.272477 |                      0.030541  |
| early_late_gated_no_samples_0_3   |      1.36703 |  1.32405 |   1.42803 |                 -0.32533  |                      0.0270506 |
| early_late_gated_only_samples_0_3 |      1.44715 |  1.34113 |   1.54717 |                 -0.245211 |                      0.0316754 |
| hgb_full                          |      1.17489 |  1.14333 |   1.22409 |                 -0.517466 |                      0.0239092 |
| hgb_no_samples_0_3                |      1.17068 |  1.13502 |   1.21679 |                 -0.521682 |                      0.0237347 |
| hgb_only_samples_0_3              |      1.20058 |  1.16524 |   1.23786 |                 -0.491783 |                      0.0233857 |
| mlp_full                          |      1.29302 |  1.24504 |   1.34519 |                 -0.399335 |                      0.0260035 |
| mlp_no_samples_0_3                |      1.3267  |  1.25581 |   1.3999  |                 -0.365662 |                      0.0252182 |
| mlp_only_samples_0_3              |      1.42584 |  1.32714 |   1.5373  |                 -0.266523 |                      0.0319372 |
| ridge_full                        |      1.36386 |  1.29107 |   1.41254 |                 -0.328502 |                      0.0273997 |
| ridge_no_samples_0_3              |      1.36131 |  1.2968  |   1.41945 |                 -0.331046 |                      0.0270506 |
| ridge_only_samples_0_3            |      1.38244 |  1.3303  |   1.43766 |                 -0.309918 |                      0.0290576 |

## Controls

| method                                     | family                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:-------------------------------------------|:------------------------|-------------:|---------:|----------:|--------------------------:|
| hgb_run_family_control                     | run_family_control      |      1.20895 |  1.15311 |   1.26352 |               -0.483405   |
| ridge_run_family_control                   | run_family_control      |      1.37784 |  1.31646 |   1.42376 |               -0.314514   |
| cnn1d_only_samples_0_3_shuffled            | shuffled_target_control |      1.66517 |  1.48238 |   1.97111 |               -0.0271868  |
| mlp_full_shuffled                          | shuffled_target_control |      1.67301 |  1.50371 |   1.98647 |               -0.0193497  |
| ridge_only_samples_0_3_shuffled            | shuffled_target_control |      1.69394 |  1.48851 |   1.9951  |                0.00158147 |
| cnn1d_no_samples_0_3_shuffled              | shuffled_target_control |      1.69746 |  1.55093 |   1.92696 |                0.00509836 |
| early_late_gated_full_shuffled             | shuffled_target_control |      1.69895 |  1.52899 |   1.97987 |                0.00658692 |
| early_late_gated_only_samples_0_3_shuffled | shuffled_target_control |      1.70145 |  1.49485 |   2.02355 |                0.00909312 |
| ridge_no_samples_0_3_shuffled              | shuffled_target_control |      1.70512 |  1.53876 |   2.02193 |                0.0127667  |
| early_late_gated_no_samples_0_3_shuffled   | shuffled_target_control |      1.70858 |  1.51848 |   2.01472 |                0.0162189  |
| ridge_full_shuffled                        | shuffled_target_control |      1.71029 |  1.5334  |   2.05246 |                0.0179297  |
| mlp_only_samples_0_3_shuffled              | shuffled_target_control |      1.71269 |  1.50045 |   2.01866 |                0.0203289  |
| mlp_no_samples_0_3_shuffled                | shuffled_target_control |      1.72095 |  1.54583 |   2.03602 |                0.028595   |
| hgb_no_samples_0_3_shuffled                | shuffled_target_control |      1.72662 |  1.54714 |   2.0552  |                0.0342617  |
| cnn1d_full_shuffled                        | shuffled_target_control |      1.73053 |  1.54605 |   2.1034  |                0.0381762  |
| hgb_full_shuffled                          | shuffled_target_control |      1.73575 |  1.56678 |   2.07475 |                0.0433881  |
| hgb_only_samples_0_3_shuffled              | shuffled_target_control |      1.75071 |  1.55784 |   2.08456 |                0.0583548  |

Shuffled-target rows are interpreted as stability/leakage warnings, not as positive evidence. A shuffled control that matches or beats its nominal counterpart means that model/mask combination is not causally interpretable.

## Held-Out Runs

|   heldout_run | method                            | family             |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_events |
|--------------:|:----------------------------------|:-------------------|-------------:|---------:|----------:|--------------------------:|-----------:|
|            58 | hgb_full                          | ml                 |      1.06716 | 0.877674 |   1.25601 |               -0.455629   |         73 |
|            58 | hgb_run_family_control            | run_family_control |      1.06951 | 0.925237 |   1.22657 |               -0.453287   |         73 |
|            58 | hgb_only_samples_0_3              | ml                 |      1.1486  | 0.953084 |   1.35573 |               -0.374192   |         73 |
|            58 | hgb_no_samples_0_3                | ml                 |      1.14929 | 0.955936 |   1.38232 |               -0.373499   |         73 |
|            58 | mlp_no_samples_0_3                | ml                 |      1.23185 | 0.994161 |   1.50624 |               -0.290938   |         73 |
|            58 | mlp_full                          | ml                 |      1.23615 | 1.05391  |   1.51012 |               -0.286644   |         73 |
|            58 | cnn1d_no_samples_0_3              | ml                 |      1.30596 | 1.11745  |   1.47188 |               -0.216831   |         73 |
|            58 | early_late_gated_full             | ml                 |      1.31856 | 1.17235  |   1.58694 |               -0.204236   |         73 |
|            58 | ridge_run_family_control          | run_family_control |      1.34856 | 1.18746  |   1.56113 |               -0.174236   |         73 |
|            58 | ridge_no_samples_0_3              | ml                 |      1.35919 | 1.22335  |   1.49685 |               -0.163605   |         73 |
|            58 | ridge_only_samples_0_3            | ml                 |      1.36913 | 1.21007  |   1.60442 |               -0.153663   |         73 |
|            58 | ridge_full                        | ml                 |      1.3753  | 1.24815  |   1.51729 |               -0.147497   |         73 |
|            58 | mlp_only_samples_0_3              | ml                 |      1.4102  | 1.2112   |   1.68602 |               -0.112592   |         73 |
|            58 | cnn1d_full                        | ml                 |      1.43592 | 1.30412  |   1.59482 |               -0.0868695  |         73 |
|            58 | early_late_gated_only_samples_0_3 | ml                 |      1.46345 | 1.24256  |   1.62339 |               -0.0593424  |         73 |
|            58 | s02b_global_template_timewalk     | traditional        |      1.52279 | 1.28487  |   1.86293 |                0          |         73 |
|            58 | cnn1d_only_samples_0_3            | ml                 |      1.52628 | 1.3433   |   1.67616 |                0.00348641 |         73 |
|            58 | early_late_gated_no_samples_0_3   | ml                 |      1.52929 | 1.34871  |   1.75346 |                0.00649693 |         73 |
|            59 | hgb_no_samples_0_3                | ml                 |      1.14656 | 1.079    |   1.19978 |               -0.4502     |        763 |
|            59 | hgb_run_family_control            | run_family_control |      1.15198 | 1.10127  |   1.21022 |               -0.444777   |        763 |
|            59 | hgb_full                          | ml                 |      1.15721 | 1.09708  |   1.21658 |               -0.439547   |        763 |
|            59 | hgb_only_samples_0_3              | ml                 |      1.20128 | 1.13142  |   1.26321 |               -0.395484   |        763 |
|            59 | mlp_full                          | ml                 |      1.24431 | 1.18017  |   1.30978 |               -0.352448   |        763 |
|            59 | mlp_no_samples_0_3                | ml                 |      1.25353 | 1.1793   |   1.33163 |               -0.343231   |        763 |
|            59 | early_late_gated_no_samples_0_3   | ml                 |      1.28486 | 1.21096  |   1.36006 |               -0.311898   |        763 |
|            59 | mlp_only_samples_0_3              | ml                 |      1.33727 | 1.28127  |   1.38582 |               -0.259491   |        763 |
|            59 | ridge_no_samples_0_3              | ml                 |      1.34619 | 1.28895  |   1.40131 |               -0.250573   |        763 |
|            59 | ridge_full                        | ml                 |      1.35699 | 1.29136  |   1.40813 |               -0.239769   |        763 |
|            59 | ridge_run_family_control          | run_family_control |      1.36736 | 1.30362  |   1.4303  |               -0.229404   |        763 |
|            59 | ridge_only_samples_0_3            | ml                 |      1.38151 | 1.30948  |   1.44435 |               -0.215253   |        763 |
|            59 | early_late_gated_only_samples_0_3 | ml                 |      1.38603 | 1.32831  |   1.45331 |               -0.210727   |        763 |
|            59 | cnn1d_no_samples_0_3              | ml                 |      1.40373 | 1.34404  |   1.46565 |               -0.193032   |        763 |
|            59 | early_late_gated_full             | ml                 |      1.42948 | 1.37246  |   1.50345 |               -0.167282   |        763 |
|            59 | cnn1d_full                        | ml                 |      1.46082 | 1.40362  |   1.52898 |               -0.135936   |        763 |
|            59 | cnn1d_only_samples_0_3            | ml                 |      1.51843 | 1.43272  |   1.576   |               -0.0783341  |        763 |
|            59 | s02b_global_template_timewalk     | traditional        |      1.59676 | 1.54544  |   1.6474  |                0          |        763 |
|            60 | hgb_no_samples_0_3                | ml                 |      1.17817 | 1.10524  |   1.24018 |               -0.293728   |        808 |
|            60 | hgb_full                          | ml                 |      1.19231 | 1.12187  |   1.25862 |               -0.279582   |        808 |
|            60 | hgb_only_samples_0_3              | ml                 |      1.22452 | 1.15625  |   1.31469 |               -0.24738    |        808 |
|            60 | hgb_run_family_control            | run_family_control |      1.27725 | 1.20739  |   1.35521 |               -0.19465    |        808 |
|            60 | mlp_full                          | ml                 |      1.29251 | 1.22511  |   1.36775 |               -0.179392   |        808 |
|            60 | early_late_gated_no_samples_0_3   | ml                 |      1.34602 | 1.28174  |   1.43582 |               -0.125873   |        808 |
|            60 | ridge_run_family_control          | run_family_control |      1.40503 | 1.34931  |   1.49325 |               -0.066865   |        808 |
|            60 | cnn1d_full                        | ml                 |      1.41413 | 1.35148  |   1.49098 |               -0.0577698  |        808 |
|            60 | ridge_full                        | ml                 |      1.422   | 1.35742  |   1.49733 |               -0.0498928  |        808 |
|            60 | ridge_no_samples_0_3              | ml                 |      1.42418 | 1.36518  |   1.49334 |               -0.0477203  |        808 |
|            60 | ridge_only_samples_0_3            | ml                 |      1.43495 | 1.37099  |   1.50181 |               -0.0369514  |        808 |
|            60 | mlp_no_samples_0_3                | ml                 |      1.44409 | 1.38009  |   1.51174 |               -0.0278086  |        808 |
|            60 | early_late_gated_full             | ml                 |      1.46181 | 1.40276  |   1.53179 |               -0.010088   |        808 |
|            60 | s02b_global_template_timewalk     | traditional        |      1.4719  | 1.42599  |   1.51921 |                0          |        808 |
|            60 | cnn1d_only_samples_0_3            | ml                 |      1.5235  | 1.47082  |   1.60333 |                0.0516074  |        808 |
|            60 | mlp_only_samples_0_3              | ml                 |      1.59135 | 1.52141  |   1.6676  |                0.119457   |        808 |
|            60 | cnn1d_no_samples_0_3              | ml                 |      1.6064  | 1.55118  |   1.69853 |                0.134503   |        808 |
|            60 | early_late_gated_only_samples_0_3 | ml                 |      1.63258 | 1.58309  |   1.71167 |                0.160682   |        808 |
|            61 | hgb_full                          | ml                 |      1.16316 | 1.11713  |   1.21233 |               -1.02526    |        933 |
|            61 | hgb_run_family_control            | run_family_control |      1.16825 | 1.12393  |   1.21264 |               -1.02016    |        933 |
|            61 | hgb_no_samples_0_3                | ml                 |      1.16904 | 1.11917  |   1.20975 |               -1.01938    |        933 |
|            61 | hgb_only_samples_0_3              | ml                 |      1.20108 | 1.15593  |   1.2528  |               -0.987334   |        933 |
|            61 | cnn1d_no_samples_0_3              | ml                 |      1.26073 | 1.20598  |   1.3287  |               -0.927691   |        933 |
|            61 | mlp_no_samples_0_3                | ml                 |      1.26654 | 1.23094  |   1.32583 |               -0.921873   |        933 |
|            61 | cnn1d_full                        | ml                 |      1.2757  | 1.19996  |   1.3294  |               -0.912721   |        933 |
|            61 | ridge_no_samples_0_3              | ml                 |      1.27953 | 1.22143  |   1.34891 |               -0.908884   |        933 |
|            61 | mlp_full                          | ml                 |      1.28029 | 1.2297   |   1.33437 |               -0.908128   |        933 |
|            61 | ridge_full                        | ml                 |      1.28172 | 1.22479  |   1.34708 |               -0.906693   |        933 |
|            61 | ridge_run_family_control          | run_family_control |      1.29081 | 1.23739  |   1.35085 |               -0.897609   |        933 |
|            61 | mlp_only_samples_0_3              | ml                 |      1.2942  | 1.24132  |   1.36595 |               -0.894215   |        933 |
|            61 | ridge_only_samples_0_3            | ml                 |      1.30833 | 1.2431   |   1.36202 |               -0.880088   |        933 |
|            61 | early_late_gated_full             | ml                 |      1.31174 | 1.25337  |   1.37813 |               -0.876681   |        933 |
|            61 | early_late_gated_no_samples_0_3   | ml                 |      1.319   | 1.27602  |   1.38463 |               -0.869421   |        933 |
|            61 | cnn1d_only_samples_0_3            | ml                 |      1.32055 | 1.25934  |   1.38092 |               -0.867867   |        933 |
|            61 | early_late_gated_only_samples_0_3 | ml                 |      1.32336 | 1.25377  |   1.38034 |               -0.865062   |        933 |
|            61 | s02b_global_template_timewalk     | traditional        |      2.18842 | 2.08553  |   2.26924 |                0          |        933 |
|            62 | hgb_full                          | ml                 |      1.14274 | 1.08531  |   1.20965 |               -0.487209   |        807 |
|            62 | hgb_no_samples_0_3                | ml                 |      1.14824 | 1.09137  |   1.21835 |               -0.481707   |        807 |
|            62 | hgb_only_samples_0_3              | ml                 |      1.17948 | 1.12434  |   1.23405 |               -0.450466   |        807 |
|            62 | hgb_run_family_control            | run_family_control |      1.24008 | 1.18504  |   1.31054 |               -0.389869   |        807 |
|            62 | mlp_no_samples_0_3                | ml                 |      1.29155 | 1.23895  |   1.35871 |               -0.338393   |        807 |
|            62 | ridge_full                        | ml                 |      1.32823 | 1.27728  |   1.37986 |               -0.301714   |        807 |
|            62 | mlp_full                          | ml                 |      1.33245 | 1.26123  |   1.39642 |               -0.297494   |        807 |
|            62 | ridge_no_samples_0_3              | ml                 |      1.3348  | 1.27318  |   1.38583 |               -0.295147   |        807 |

## Leakage and Systematics

|   heldout_run | check                                                   |       value | pass   |
|--------------:|:--------------------------------------------------------|------------:|:-------|
|            58 | train_heldout_run_overlap                               |  0          | True   |
|            58 | train_heldout_event_id_overlap                          |  0          | True   |
|            58 | feature_audit                                           |  0          | True   |
|            58 | shuffled_target_worse:ridge_full                        |  0.27286    | True   |
|            58 | shuffled_target_worse:hgb_full                          |  0.516824   | True   |
|            58 | shuffled_target_worse:mlp_full                          |  0.270935   | True   |
|            58 | shuffled_target_worse:cnn1d_full                        |  0.146725   | True   |
|            58 | shuffled_target_worse:early_late_gated_full             |  0.17698    | True   |
|            58 | shuffled_target_worse:ridge_no_samples_0_3              |  0.239155   | True   |
|            58 | shuffled_target_worse:hgb_no_samples_0_3                |  0.40038    | True   |
|            58 | shuffled_target_worse:mlp_no_samples_0_3                |  0.397697   | True   |
|            58 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.187209   | True   |
|            58 | shuffled_target_worse:early_late_gated_no_samples_0_3   | -0.0376169  | False  |
|            58 | shuffled_target_worse:ridge_only_samples_0_3            |  0.155518   | True   |
|            58 | shuffled_target_worse:hgb_only_samples_0_3              |  0.393895   | True   |
|            58 | shuffled_target_worse:mlp_only_samples_0_3              |  0.130868   | True   |
|            58 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.0255596  | True   |
|            58 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.0500226  | True   |
|            59 | train_heldout_run_overlap                               |  0          | True   |
|            59 | train_heldout_event_id_overlap                          |  0          | True   |
|            59 | feature_audit                                           |  0          | True   |
|            59 | shuffled_target_worse:ridge_full                        |  0.266079   | True   |
|            59 | shuffled_target_worse:hgb_full                          |  0.510636   | True   |
|            59 | shuffled_target_worse:mlp_full                          |  0.356696   | True   |
|            59 | shuffled_target_worse:cnn1d_full                        |  0.156704   | True   |
|            59 | shuffled_target_worse:early_late_gated_full             |  0.205537   | True   |
|            59 | shuffled_target_worse:ridge_no_samples_0_3              |  0.259806   | True   |
|            59 | shuffled_target_worse:hgb_no_samples_0_3                |  0.491989   | True   |
|            59 | shuffled_target_worse:mlp_no_samples_0_3                |  0.353375   | True   |
|            59 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.199703   | True   |
|            59 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.347039   | True   |
|            59 | shuffled_target_worse:ridge_only_samples_0_3            |  0.219423   | True   |
|            59 | shuffled_target_worse:hgb_only_samples_0_3              |  0.439034   | True   |
|            59 | shuffled_target_worse:mlp_only_samples_0_3              |  0.347907   | True   |
|            59 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.0892408  | True   |
|            59 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.265944   | True   |
|            60 | train_heldout_run_overlap                               |  0          | True   |
|            60 | train_heldout_event_id_overlap                          |  0          | True   |
|            60 | feature_audit                                           |  0          | True   |
|            60 | shuffled_target_worse:ridge_full                        |  0.0531545  | True   |
|            60 | shuffled_target_worse:hgb_full                          |  0.346724   | True   |
|            60 | shuffled_target_worse:mlp_full                          |  0.179377   | True   |
|            60 | shuffled_target_worse:cnn1d_full                        |  0.0974096  | True   |
|            60 | shuffled_target_worse:early_late_gated_full             |  0.0128121  | True   |
|            60 | shuffled_target_worse:ridge_no_samples_0_3              |  0.0570082  | True   |
|            60 | shuffled_target_worse:hgb_no_samples_0_3                |  0.324735   | True   |
|            60 | shuffled_target_worse:mlp_no_samples_0_3                |  0.068006   | True   |
|            60 | shuffled_target_worse:cnn1d_no_samples_0_3              | -0.0911192  | False  |
|            60 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.118805   | True   |
|            60 | shuffled_target_worse:ridge_only_samples_0_3            |  0.0279267  | True   |
|            60 | shuffled_target_worse:hgb_only_samples_0_3              |  0.296625   | True   |
|            60 | shuffled_target_worse:mlp_only_samples_0_3              | -0.181477   | False  |
|            60 | shuffled_target_worse:cnn1d_only_samples_0_3            | -0.0969282  | False  |
|            60 | shuffled_target_worse:early_late_gated_only_samples_0_3 | -0.240311   | False  |
|            61 | train_heldout_run_overlap                               |  0          | True   |
|            61 | train_heldout_event_id_overlap                          |  0          | True   |
|            61 | feature_audit                                           |  0          | True   |
|            61 | shuffled_target_worse:ridge_full                        |  0.960053   | True   |
|            61 | shuffled_target_worse:hgb_full                          |  1.07849    | True   |
|            61 | shuffled_target_worse:mlp_full                          |  0.87731    | True   |
|            61 | shuffled_target_worse:cnn1d_full                        |  1.02815    | True   |
|            61 | shuffled_target_worse:early_late_gated_full             |  0.824199   | True   |
|            61 | shuffled_target_worse:ridge_no_samples_0_3              |  0.895037   | True   |
|            61 | shuffled_target_worse:hgb_no_samples_0_3                |  1.01552    | True   |
|            61 | shuffled_target_worse:mlp_no_samples_0_3                |  0.95609    | True   |
|            61 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.827052   | True   |
|            61 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.897025   | True   |
|            61 | shuffled_target_worse:ridge_only_samples_0_3            |  0.860335   | True   |
|            61 | shuffled_target_worse:hgb_only_samples_0_3              |  1.04339    | True   |
|            61 | shuffled_target_worse:mlp_only_samples_0_3              |  0.916819   | True   |
|            61 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.821907   | True   |
|            61 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.866435   | True   |
|            62 | train_heldout_run_overlap                               |  0          | True   |
|            62 | train_heldout_event_id_overlap                          |  0          | True   |
|            62 | feature_audit                                           |  0          | True   |
|            62 | shuffled_target_worse:ridge_full                        |  0.265741   | True   |
|            62 | shuffled_target_worse:hgb_full                          |  0.555672   | True   |
|            62 | shuffled_target_worse:mlp_full                          |  0.24632    | True   |
|            62 | shuffled_target_worse:cnn1d_full                        |  0.294383   | True   |
|            62 | shuffled_target_worse:early_late_gated_full             |  0.253061   | True   |
|            62 | shuffled_target_worse:ridge_no_samples_0_3              |  0.310935   | True   |
|            62 | shuffled_target_worse:hgb_no_samples_0_3                |  0.515088   | True   |
|            62 | shuffled_target_worse:mlp_no_samples_0_3                |  0.339083   | True   |
|            62 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.179537   | True   |
|            62 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.291462   | True   |
|            62 | shuffled_target_worse:ridge_only_samples_0_3            |  0.289632   | True   |
|            62 | shuffled_target_worse:hgb_only_samples_0_3              |  0.494144   | True   |
|            62 | shuffled_target_worse:mlp_only_samples_0_3              |  0.24241    | True   |
|            62 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.150967   | True   |
|            62 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.217428   | True   |
|            63 | train_heldout_run_overlap                               |  0          | True   |
|            63 | train_heldout_event_id_overlap                          |  0          | True   |
|            63 | feature_audit                                           |  0          | True   |
|            63 | shuffled_target_worse:ridge_full                        |  0.231844   | True   |
|            63 | shuffled_target_worse:hgb_full                          |  0.289061   | True   |
|            63 | shuffled_target_worse:mlp_full                          |  0.242202   | True   |
|            63 | shuffled_target_worse:cnn1d_full                        |  0.169442   | True   |
|            63 | shuffled_target_worse:early_late_gated_full             |  0.068394   | True   |
|            63 | shuffled_target_worse:ridge_no_samples_0_3              |  0.183359   | True   |
|            63 | shuffled_target_worse:hgb_no_samples_0_3                |  0.310122   | True   |
|            63 | shuffled_target_worse:mlp_no_samples_0_3                |  0.259941   | True   |
|            63 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.128268   | True   |
|            63 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.0684511  | True   |
|            63 | shuffled_target_worse:ridge_only_samples_0_3            |  0.10803    | True   |
|            63 | shuffled_target_worse:hgb_only_samples_0_3              |  0.300383   | True   |
|            63 | shuffled_target_worse:mlp_only_samples_0_3              |  0.178358   | True   |
|            63 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.0431679  | True   |
|            63 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.184532   | True   |
|            65 | train_heldout_run_overlap                               |  0          | True   |
|            65 | train_heldout_event_id_overlap                          |  0          | True   |
|            65 | feature_audit                                           |  0          | True   |
|            65 | shuffled_target_worse:ridge_full                        |  0.115124   | True   |
|            65 | shuffled_target_worse:hgb_full                          |  0.303955   | True   |
|            65 | shuffled_target_worse:mlp_full                          |  0.166261   | True   |
|            65 | shuffled_target_worse:cnn1d_full                        |  0.00406628 | True   |
|            65 | shuffled_target_worse:early_late_gated_full             |  0.0870293  | True   |
|            65 | shuffled_target_worse:ridge_no_samples_0_3              |  0.118056   | True   |
|            65 | shuffled_target_worse:hgb_no_samples_0_3                |  0.288273   | True   |
|            65 | shuffled_target_worse:mlp_no_samples_0_3                |  0.285942   | True   |
|            65 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.0546631  | True   |

Main caveats:

- Samples 0-3 are baseline-defining samples. Any apparent gain from `only_samples_0_3` can be pedestal/run structure rather than pulse-time information.
- Sample-II run 65 has low statistics; the pooled CI therefore uses runs as the outer bootstrap unit.
- The S02b target is internally defined from same-event downstream staves, so all claims are relative timing-closure claims, not absolute beam-time truth.
- Run-family controls are coarse and predeclared; they diagnose gross family nuisance but cannot exclude all detector-condition drift.

## Verdict

Winner in `result.json`: `hgb_no_samples_0_3` with pooled `sigma68 = 1.171 ns` and CI `[1.135, 1.217] ns`.

Interpretation: Samples 0-3 are not required for the best residual correction; gains persist when they are removed, so the early samples are mainly nuisance/run-structure diagnostics rather than a causal timing source. 6 shuffled-target checks beat their nominal model and are flagged as stability caveats.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03f_1781031083_1848_21e023a2_early_sample_multimodel.py --config configs/p03f_1781031083_1848_21e023a2_early_sample_multimodel.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `model_diagnostics.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
