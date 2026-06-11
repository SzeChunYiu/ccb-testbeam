# P01l: sample-6 smoothing causality null atlas

- **Ticket:** `1781049810.1116.3eb03e19`
- **Worker:** `testbeam-laptop-4`
- **Claimed study:** sample-6 smoothing causality null atlas against timing residuals
- **Input:** raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Sample under test:** waveform sample `6` of the 18-sample, 10 ns waveform

## Question and preregistered estimand

The ticket asks whether the previously observed timing gain from sample-6 smoothing is causal waveform information or a replacement/quantization artifact.  The estimand is the B4/B6/B8 event-paired timing width after a train-only traditional timing closure:

`r_ab(e; m) = [t_a(e;m) - z_a v^-1] - [t_b(e;m) - z_b v^-1]`,

where `m` is a timing method, `z` is the stave spacing coordinate, and `v^-1 = 0.078 ns/cm`.  The headline metric is

`sigma68(m) = (Q84({r_ab}) - Q16({r_ab})) / 2`.

CIs are event bootstraps inside each held-out run and a nested run-block/event bootstrap for the pooled summary. Lower `sigma68`, lower full RMS, and lower tail fraction are better.

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

For every held-out run, the other six Sample-II runs define all train-only objects: the S02 global templates, amplitude-binned S02b template SSE nuisance, and polynomial/ridge timewalk closure. The strong traditional comparator is `s02b_global_template_timewalk`, which combines the conventional template-phase pickoff with train-only amplitude/timewalk corrections.

The sample-6 null atlas applies three replacements before recomputing conventional pickoffs:

- `local_linear`: `x_6 <- (x_5 + x_7) / 2`.
- `amplitude_bin_template`: `x_6 <- A_i median_train[x_6/A_i | stave, amplitude bin]`.
- `control_stratum`: `x_6 <- A_i median_train[x_6/A_i | stave, run-family, amplitude bin]`, with train-only fallback to the amplitude-bin template.

These replacements are evaluated against CFD20, template phase, and the configured optimal-filter windows. If replacing sample 6 improves a pickoff about as much as using it directly, the gain is not evidence that the raw sample carries unique causal timing information.

The residual learners target `y_i = t_i(S02b) - mean(t_j(S02b), t_k(S02b))` within the same event and predict a same-pulse correction. Six model families are benchmarked under three waveform masks:

- `ridge`: standardized linear Ridge regression.
- `hgb`: histogram gradient-boosted regression trees.
- `extra_trees`: no-sample-6-capable randomized tree ensemble.
- `mlp`: heteroskedastic fully connected neural net.
- `cnn1d`: compact one-dimensional convolutional network over 18 samples.
- `early_late_gated`: new architecture with a sample-6 branch and a complement branch mixed by a learned auxiliary-feature gate.

Masks are `full`, `no_sample6`, and `only_sample6`. Features exclude run id, event id, event order, other-stave timings, and pair residuals. Run-family controls use only hand summaries, stave, and coarse predeclared family (`early`, `middle`, `late`) without waveform samples. Shuffled-target controls repeat every nominal waveform model with train targets permuted.

## Traditional Sample-6 Replacement Atlas

| pickoff        | variant                |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_raw_same_pickoff_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:---------------|:-----------------------|-------------:|---------:|----------:|--------------:|-------------------------------:|---------------:|----------------:|-------------------:|
| cfd20          | amplitude_bin_template |      2.46823 |  2.34171 |   2.64821 |       3.25348 |                     -0.682035  |   -0.810215    |     -0.518467   |              11460 |
| cfd20          | local_linear           |      2.76885 |  2.66345 |   2.90881 |       6.11756 |                     -0.381413  |   -0.453118    |     -0.300961   |              11460 |
| cfd20          | control_stratum        |      3.00692 |  2.36498 |   3.97942 |       7.20598 |                     -0.14335   |   -0.683221    |      0.760795   |              11460 |
| cfd20          | raw                    |      3.15027 |  3.04377 |   3.27527 |       6.20431 |                      0         |    0           |      0          |              11460 |
| of_1_9         | local_linear           |      3.21333 |  3.14292 |   3.31627 |       3.57495 |                     -0.200684  |   -0.312425    |     -0.122913   |              11460 |
| of_1_9         | raw                    |      3.41402 |  3.30527 |   3.53031 |       3.83011 |                      0         |    0           |      0          |              11460 |
| of_1_9         | amplitude_bin_template |      4.18563 |  4.07725 |   4.30334 |       4.02572 |                      0.771609  |    0.602555    |      0.899218   |              11460 |
| of_1_9         | control_stratum        |      4.62048 |  4.14755 |   5.44287 |       4.5837  |                      1.20647   |    0.745204    |      1.93754    |              11460 |
| of_2_10        | local_linear           |      3.29339 |  3.22778 |   3.3563  |       3.62264 |                     -0.166552  |   -0.274055    |     -0.112      |              11460 |
| of_2_10        | raw                    |      3.45995 |  3.35489 |   3.5549  |       3.87621 |                      0         |    0           |      0          |              11460 |
| of_2_10        | amplitude_bin_template |      4.33692 |  4.23052 |   4.47186 |       4.1749  |                      0.876969  |    0.729435    |      1.02999    |              11460 |
| of_2_10        | control_stratum        |      4.75938 |  4.26533 |   5.51379 |       4.71129 |                      1.29944   |    0.82281     |      2.02959    |              11460 |
| of_3_11        | local_linear           |      3.34358 |  3.28994 |   3.41667 |       3.66404 |                     -0.0942494 |   -0.166044    |     -0.0329699  |              11460 |
| of_3_11        | raw                    |      3.43783 |  3.30765 |   3.53489 |       3.88769 |                      0         |    0           |      0          |              11460 |
| of_3_11        | amplitude_bin_template |      4.35208 |  4.22874 |   4.49157 |       4.28567 |                      0.914257  |    0.776744    |      1.05499    |              11460 |
| of_3_11        | control_stratum        |      4.79018 |  4.22462 |   5.6073  |       4.80166 |                      1.35235   |    0.830948    |      2.08702    |              11460 |
| of_4_12        | local_linear           |      3.32092 |  3.24062 |   3.39673 |       3.82772 |                     -0.0461844 |   -0.111441    |      0.00519027 |              11460 |
| of_4_12        | raw                    |      3.36711 |  3.263   |   3.47521 |       4.02931 |                      0         |    0           |      0          |              11460 |
| of_4_12        | amplitude_bin_template |      4.24772 |  4.09332 |   4.39015 |       4.495   |                      0.880614  |    0.768931    |      0.98135    |              11460 |
| of_4_12        | control_stratum        |      4.7423  |  4.18767 |   5.42541 |       4.97765 |                      1.3752    |    0.862822    |      2.0241     |              11460 |
| template_phase | local_linear           |      2.65732 |  2.62333 |   2.70351 |       3.22255 |                     -0.0840958 |   -0.25        |     -0.0213754  |              11460 |
| template_phase | raw                    |      2.74141 |  2.68081 |   2.98617 |       3.30837 |                      0         |    0           |      0          |              11460 |
| template_phase | amplitude_bin_template |      2.90732 |  2.70351 |   3.12333 |       3.92072 |                      0.165904  |    0           |      0.25       |              11460 |
| template_phase | control_stratum        |      3.03246 |  2.70351 |   3.67068 |       4.26175 |                      0.291044  |    3.55271e-15 |      0.768521   |              11460 |

## Pooled Benchmark

| method                        | family      |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:------------------------------|:------------|-------------:|---------:|----------:|--------------:|--------------------------:|---------------:|----------------:|-------------------:|
| extra_trees_full              | ml          |      1.09853 |  1.0634  |   1.13137 |       2.13299 |                -0.593827  |      -0.9312   |      -0.405294  |              11460 |
| extra_trees_no_sample6        | ml          |      1.10339 |  1.06779 |   1.13324 |       2.14018 |                -0.588973  |      -0.927179 |      -0.402961  |              11460 |
| extra_trees_only_sample6      | ml          |      1.15311 |  1.12131 |   1.20029 |       2.19282 |                -0.539248  |      -0.884167 |      -0.334932  |              11460 |
| hgb_full                      | ml          |      1.17249 |  1.13584 |   1.21075 |       2.1538  |                -0.519872  |      -0.833617 |      -0.331871  |              11460 |
| hgb_no_sample6                | ml          |      1.17253 |  1.13446 |   1.21728 |       2.15953 |                -0.519831  |      -0.815754 |      -0.328642  |              11460 |
| hgb_only_sample6              | ml          |      1.18504 |  1.14291 |   1.22453 |       2.13962 |                -0.50732   |      -0.866643 |      -0.314862  |              11460 |
| ridge_only_sample6            | ml          |      1.34957 |  1.29396 |   1.3945  |       2.34844 |                -0.342788  |      -0.714261 |      -0.147065  |              11460 |
| ridge_no_sample6              | ml          |      1.36379 |  1.29338 |   1.40981 |       2.33688 |                -0.328566  |      -0.737677 |      -0.124516  |              11460 |
| ridge_full                    | ml          |      1.36386 |  1.30548 |   1.417   |       2.33689 |                -0.328502  |      -0.701963 |      -0.116617  |              11460 |
| cnn1d_only_sample6            | ml          |      1.40357 |  1.35186 |   1.54905 |       2.41686 |                -0.28879   |      -0.474302 |      -0.130898  |              11460 |
| early_late_gated_only_sample6 | ml          |      1.42499 |  1.33641 |   1.56663 |       2.42839 |                -0.267366  |      -0.463931 |      -0.141123  |              11460 |
| cnn1d_no_sample6              | ml          |      1.43185 |  1.23109 |   1.73816 |       2.44968 |                -0.260507  |      -0.336133 |      -0.214507  |              11460 |
| early_late_gated_no_sample6   | ml          |      1.45742 |  1.32685 |   1.72708 |       2.44803 |                -0.234937  |      -0.314524 |      -0.146127  |              11460 |
| cnn1d_full                    | ml          |      1.48177 |  1.30801 |   1.76192 |       2.48308 |                -0.210584  |      -0.270391 |      -0.158519  |              11460 |
| mlp_only_sample6              | ml          |      1.5271  |  1.35126 |   1.72924 |       2.48856 |                -0.165256  |      -0.291975 |      -0.0755872 |              11460 |
| early_late_gated_full         | ml          |      1.55743 |  1.30062 |   1.95822 |       2.53327 |                -0.134931  |      -0.300724 |      -0.048057  |              11460 |
| mlp_full                      | ml          |      1.56318 |  1.43881 |   1.86577 |       2.51495 |                -0.129182  |      -0.169127 |      -0.0735404 |              11460 |
| mlp_no_sample6                | ml          |      1.65349 |  1.43171 |   1.8234  |       2.55271 |                -0.0388698 |      -0.216839 |       0.0549402 |              11460 |
| s02b_global_template_timewalk | traditional |      1.69236 |  1.52957 |   2.01783 |       2.59151 |                 0         |       0        |       0         |              11460 |

## Sample-6 Ablation

| method                        |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_traditional_ns |   tail_frac_vs_traditional_p95 |
|:------------------------------|-------------:|---------:|----------:|--------------:|--------------------------:|-------------------------------:|
| cnn1d_full                    |      1.48177 |  1.30801 |   1.76192 |       2.48308 |                -0.210584  |                      0.0390925 |
| cnn1d_no_sample6              |      1.43185 |  1.23109 |   1.73816 |       2.44968 |                -0.260507  |                      0.0376091 |
| cnn1d_only_sample6            |      1.40357 |  1.35186 |   1.54905 |       2.41686 |                -0.28879   |                      0.0307155 |
| early_late_gated_full         |      1.55743 |  1.30062 |   1.95822 |       2.53327 |                -0.134931  |                      0.0471204 |
| early_late_gated_no_sample6   |      1.45742 |  1.32685 |   1.72708 |       2.44803 |                -0.234937  |                      0.0348168 |
| early_late_gated_only_sample6 |      1.42499 |  1.33641 |   1.56663 |       2.42839 |                -0.267366  |                      0.0340314 |
| extra_trees_full              |      1.09853 |  1.0634  |   1.13137 |       2.13299 |                -0.593827  |                      0.0205061 |
| extra_trees_no_sample6        |      1.10339 |  1.06779 |   1.13324 |       2.14018 |                -0.588973  |                      0.0206806 |
| extra_trees_only_sample6      |      1.15311 |  1.12131 |   1.20029 |       2.19282 |                -0.539248  |                      0.0224258 |
| hgb_full                      |      1.17249 |  1.13584 |   1.21075 |       2.1538  |                -0.519872  |                      0.0235602 |
| hgb_no_sample6                |      1.17253 |  1.13446 |   1.21728 |       2.15953 |                -0.519831  |                      0.024171  |
| hgb_only_sample6              |      1.18504 |  1.14291 |   1.22453 |       2.13962 |                -0.50732   |                      0.021815  |
| mlp_full                      |      1.56318 |  1.43881 |   1.86577 |       2.51495 |                -0.129182  |                      0.0417976 |
| mlp_no_sample6                |      1.65349 |  1.43171 |   1.8234  |       2.55271 |                -0.0388698 |                      0.0434555 |
| mlp_only_sample6              |      1.5271  |  1.35126 |   1.72924 |       2.48856 |                -0.165256  |                      0.0390925 |
| ridge_full                    |      1.36386 |  1.30548 |   1.417   |       2.33689 |                -0.328502  |                      0.0273997 |
| ridge_no_sample6              |      1.36379 |  1.29338 |   1.40981 |       2.33688 |                -0.328566  |                      0.0273997 |
| ridge_only_sample6            |      1.34957 |  1.29396 |   1.3945  |       2.34844 |                -0.342788  |                      0.028185  |

## Controls

| method                                 | family                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:---------------------------------------|:------------------------|-------------:|---------:|----------:|--------------------------:|
| hgb_run_family_control                 | run_family_control      |      1.20877 |  1.16721 |   1.25483 |               -0.483587   |
| ridge_run_family_control               | run_family_control      |      1.37784 |  1.32166 |   1.42795 |               -0.314514   |
| cnn1d_full_shuffled                    | shuffled_target_control |      1.62795 |  1.48881 |   1.8668  |               -0.0644061  |
| ridge_only_sample6_shuffled            | shuffled_target_control |      1.68824 |  1.51287 |   2.00205 |               -0.0041171  |
| cnn1d_no_sample6_shuffled              | shuffled_target_control |      1.69743 |  1.48894 |   2.05049 |                0.0050762  |
| ridge_no_sample6_shuffled              | shuffled_target_control |      1.7002  |  1.54801 |   2.00581 |                0.00784252 |
| early_late_gated_full_shuffled         | shuffled_target_control |      1.70195 |  1.47628 |   2.03568 |                0.00959622 |
| mlp_only_sample6_shuffled              | shuffled_target_control |      1.70473 |  1.51311 |   2.0106  |                0.0123762  |
| early_late_gated_only_sample6_shuffled | shuffled_target_control |      1.7071  |  1.55347 |   1.96073 |                0.0147429  |
| cnn1d_only_sample6_shuffled            | shuffled_target_control |      1.70841 |  1.54096 |   2.0513  |                0.0160518  |
| ridge_full_shuffled                    | shuffled_target_control |      1.71029 |  1.55493 |   2.04919 |                0.0179297  |
| mlp_no_sample6_shuffled                | shuffled_target_control |      1.71745 |  1.55035 |   1.97421 |                0.0250895  |
| hgb_no_sample6_shuffled                | shuffled_target_control |      1.7191  |  1.54407 |   2.02817 |                0.0267377  |
| early_late_gated_no_sample6_shuffled   | shuffled_target_control |      1.71922 |  1.5917  |   1.95272 |                0.026858   |
| hgb_full_shuffled                      | shuffled_target_control |      1.72509 |  1.57083 |   2.03817 |                0.0327286  |
| mlp_full_shuffled                      | shuffled_target_control |      1.74654 |  1.58517 |   2.03254 |                0.0541768  |
| hgb_only_sample6_shuffled              | shuffled_target_control |      1.7497  |  1.56536 |   2.07083 |                0.0573442  |
| extra_trees_only_sample6_shuffled      | shuffled_target_control |      1.77961 |  1.62191 |   2.04289 |                0.0872514  |
| extra_trees_full_shuffled              | shuffled_target_control |      1.83583 |  1.64004 |   2.05061 |                0.14347    |
| extra_trees_no_sample6_shuffled        | shuffled_target_control |      1.8516  |  1.64741 |   2.14484 |                0.15924    |

Shuffled-target rows are interpreted as stability/leakage warnings, not as positive evidence. A shuffled control that matches or beats its nominal counterpart means that model/mask combination is not causally interpretable.

## Held-Out Runs

|   heldout_run | method                        | family             |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_traditional_ns |   n_events |
|--------------:|:------------------------------|:-------------------|-------------:|---------:|----------:|--------------:|--------------------------:|-----------:|
|            58 | extra_trees_no_sample6        | ml                 |      1.00004 | 0.873258 |   1.27218 |       2.54661 |                -0.522756  |         73 |
|            58 | extra_trees_full              | ml                 |      1.00207 | 0.871544 |   1.26382 |       2.54022 |                -0.520725  |         73 |
|            58 | hgb_full                      | ml                 |      1.02249 | 0.88656  |   1.24084 |       2.53471 |                -0.5003    |         73 |
|            58 | hgb_run_family_control        | run_family_control |      1.06951 | 0.926324 |   1.24509 |       2.58601 |                -0.453287  |         73 |
|            58 | extra_trees_only_sample6      | ml                 |      1.12198 | 0.97285  |   1.3619  |       2.64994 |                -0.400808  |         73 |
|            58 | hgb_no_sample6                | ml                 |      1.14848 | 1.03074  |   1.39584 |       2.56996 |                -0.374315  |         73 |
|            58 | cnn1d_full                    | ml                 |      1.17139 | 0.925027 |   1.44029 |       2.7631  |                -0.351401  |         73 |
|            58 | hgb_only_sample6              | ml                 |      1.20687 | 1.04569  |   1.44663 |       2.59656 |                -0.315924  |         73 |
|            58 | early_late_gated_only_sample6 | ml                 |      1.26063 | 0.972956 |   1.51099 |       2.65988 |                -0.262165  |         73 |
|            58 | cnn1d_only_sample6            | ml                 |      1.3245  | 1.06157  |   1.65952 |       2.64658 |                -0.198289  |         73 |
|            58 | cnn1d_no_sample6              | ml                 |      1.34803 | 1.07515  |   1.61713 |       2.66406 |                -0.174761  |         73 |
|            58 | ridge_run_family_control      | run_family_control |      1.34856 | 1.20044  |   1.53815 |       2.7798  |                -0.174236  |         73 |
|            58 | early_late_gated_full         | ml                 |      1.36084 | 1.04189  |   1.65257 |       2.69275 |                -0.16195   |         73 |
|            58 | early_late_gated_no_sample6   | ml                 |      1.36869 | 1.07876  |   1.69975 |       2.73582 |                -0.154105  |         73 |
|            58 | ridge_only_sample6            | ml                 |      1.37056 | 1.1781   |   1.52382 |       2.75534 |                -0.152229  |         73 |
|            58 | ridge_no_sample6              | ml                 |      1.37526 | 1.24758  |   1.52023 |       2.76603 |                -0.147532  |         73 |
|            58 | ridge_full                    | ml                 |      1.3753  | 1.24757  |   1.52027 |       2.76604 |                -0.147497  |         73 |
|            58 | mlp_only_sample6              | ml                 |      1.40346 | 1.11902  |   1.71896 |       2.74137 |                -0.119333  |         73 |
|            58 | mlp_no_sample6                | ml                 |      1.47268 | 1.12825  |   1.76414 |       2.72695 |                -0.0501124 |         73 |
|            58 | s02b_global_template_timewalk | traditional        |      1.52279 | 1.2176   |   1.87879 |       2.75002 |                 0         |         73 |
|            58 | mlp_full                      | ml                 |      1.56104 | 1.21618  |   1.89363 |       2.58613 |                 0.0382479 |         73 |
|            59 | extra_trees_no_sample6        | ml                 |      1.07775 | 1.01092  |   1.1353  |       2.16001 |                -0.519012  |        763 |
|            59 | extra_trees_full              | ml                 |      1.07827 | 1.01495  |   1.13235 |       2.16978 |                -0.518491  |        763 |
|            59 | extra_trees_only_sample6      | ml                 |      1.13448 | 1.07889  |   1.19276 |       2.1666  |                -0.462276  |        763 |
|            59 | hgb_run_family_control        | run_family_control |      1.15393 | 1.11437  |   1.21282 |       2.16452 |                -0.442831  |        763 |
|            59 | hgb_no_sample6                | ml                 |      1.15648 | 1.09111  |   1.22774 |       2.24387 |                -0.440279  |        763 |
|            59 | hgb_only_sample6              | ml                 |      1.15835 | 1.10091  |   1.21153 |       2.16993 |                -0.438412  |        763 |
|            59 | hgb_full                      | ml                 |      1.16039 | 1.09122  |   1.21712 |       2.26726 |                -0.43637   |        763 |
|            59 | cnn1d_no_sample6              | ml                 |      1.25578 | 1.20627  |   1.30271 |       2.32093 |                -0.340981  |        763 |
|            59 | early_late_gated_full         | ml                 |      1.32509 | 1.27767  |   1.37985 |       2.33584 |                -0.271671  |        763 |
|            59 | mlp_only_sample6              | ml                 |      1.32673 | 1.2749   |   1.37459 |       2.3474  |                -0.270027  |        763 |
|            59 | ridge_only_sample6            | ml                 |      1.34055 | 1.28937  |   1.40393 |       2.31051 |                -0.25621   |        763 |
|            59 | cnn1d_only_sample6            | ml                 |      1.34235 | 1.28891  |   1.38791 |       2.35294 |                -0.254409  |        763 |
|            59 | early_late_gated_only_sample6 | ml                 |      1.35323 | 1.30207  |   1.41187 |       2.33281 |                -0.24353   |        763 |
|            59 | ridge_full                    | ml                 |      1.35699 | 1.30235  |   1.4055  |       2.30178 |                -0.239769  |        763 |
|            59 | ridge_no_sample6              | ml                 |      1.35705 | 1.30234  |   1.4055  |       2.30178 |                -0.239711  |        763 |
|            59 | ridge_run_family_control      | run_family_control |      1.36736 | 1.30604  |   1.43296 |       2.323   |                -0.229404  |        763 |
|            59 | early_late_gated_no_sample6   | ml                 |      1.3914  | 1.34555  |   1.44505 |       2.383   |                -0.205365  |        763 |
|            59 | cnn1d_full                    | ml                 |      1.42329 | 1.38843  |   1.4731  |       2.38725 |                -0.173466  |        763 |
|            59 | mlp_full                      | ml                 |      1.49367 | 1.45882  |   1.55645 |       2.42481 |                -0.103093  |        763 |
|            59 | s02b_global_template_timewalk | traditional        |      1.59676 | 1.5568   |   1.65124 |       2.48616 |                 0         |        763 |
|            59 | mlp_no_sample6                | ml                 |      1.64418 | 1.60513  |   1.69255 |       2.52072 |                 0.0474152 |        763 |
|            60 | extra_trees_full              | ml                 |      1.12669 | 1.07092  |   1.20888 |       1.9779  |                -0.345203  |        808 |
|            60 | extra_trees_no_sample6        | ml                 |      1.13602 | 1.07838  |   1.19871 |       1.97474 |                -0.335875  |        808 |
|            60 | cnn1d_no_sample6              | ml                 |      1.15464 | 1.09088  |   1.20159 |       2.08413 |                -0.317255  |        808 |
|            60 | hgb_no_sample6                | ml                 |      1.16268 | 1.11115  |   1.2518  |       2.01037 |                -0.309217  |        808 |
|            60 | hgb_full                      | ml                 |      1.18122 | 1.12552  |   1.25399 |       1.99719 |                -0.290675  |        808 |
|            60 | extra_trees_only_sample6      | ml                 |      1.18709 | 1.11277  |   1.25538 |       2.03086 |                -0.284806  |        808 |
|            60 | early_late_gated_no_sample6   | ml                 |      1.21848 | 1.17126  |   1.28138 |       2.13775 |                -0.253417  |        808 |
|            60 | hgb_only_sample6              | ml                 |      1.23187 | 1.17289  |   1.29859 |       2.02371 |                -0.240028  |        808 |
|            60 | cnn1d_full                    | ml                 |      1.25802 | 1.21545  |   1.31667 |       2.17647 |                -0.213876  |        808 |
|            60 | hgb_run_family_control        | run_family_control |      1.28077 | 1.19628  |   1.3577  |       2.07627 |                -0.191123  |        808 |
|            60 | mlp_no_sample6                | ml                 |      1.29179 | 1.25402  |   1.34271 |       2.18594 |                -0.180111  |        808 |
|            60 | early_late_gated_only_sample6 | ml                 |      1.31199 | 1.25961  |   1.35194 |       2.16487 |                -0.159909  |        808 |
|            60 | early_late_gated_full         | ml                 |      1.31794 | 1.27593  |   1.3819  |       2.20349 |                -0.153962  |        808 |
|            60 | cnn1d_only_sample6            | ml                 |      1.33847 | 1.29793  |   1.40396 |       2.19178 |                -0.133424  |        808 |
|            60 | mlp_full                      | ml                 |      1.38992 | 1.34847  |   1.43531 |       2.1989  |                -0.0819806 |        808 |
|            60 | mlp_only_sample6              | ml                 |      1.39324 | 1.35413  |   1.43791 |       2.22601 |                -0.078658  |        808 |
|            60 | ridge_only_sample6            | ml                 |      1.40195 | 1.32534  |   1.45912 |       2.22361 |                -0.0699469 |        808 |
|            60 | ridge_run_family_control      | run_family_control |      1.40503 | 1.34445  |   1.48702 |       2.23119 |                -0.066865  |        808 |
|            60 | ridge_no_sample6              | ml                 |      1.42184 | 1.35262  |   1.50143 |       2.23292 |                -0.0500596 |        808 |
|            60 | ridge_full                    | ml                 |      1.422   | 1.35265  |   1.50142 |       2.23295 |                -0.0498928 |        808 |
|            60 | s02b_global_template_timewalk | traditional        |      1.4719  | 1.42985  |   1.51316 |       2.27149 |                 0         |        808 |
|            61 | extra_trees_full              | ml                 |      1.09682 | 1.05555  |   1.15762 |       2.26663 |                -1.0916    |        933 |
|            61 | extra_trees_no_sample6        | ml                 |      1.09742 | 1.0526   |   1.15481 |       2.27468 |                -1.091     |        933 |
|            61 | extra_trees_only_sample6      | ml                 |      1.15903 | 1.10853  |   1.19895 |       2.32865 |                -1.02938   |        933 |
|            61 | hgb_only_sample6              | ml                 |      1.16025 | 1.10849  |   1.20423 |       2.24005 |                -1.02817   |        933 |
|            61 | hgb_full                      | ml                 |      1.16454 | 1.11267  |   1.21977 |       2.2937  |                -1.02387   |        933 |
|            61 | hgb_no_sample6                | ml                 |      1.17001 | 1.12413  |   1.21996 |       2.29428 |                -1.01841   |        933 |
|            61 | hgb_run_family_control        | run_family_control |      1.1791  | 1.12553  |   1.21792 |       2.26922 |                -1.00932   |        933 |
|            61 | ridge_only_sample6            | ml                 |      1.28083 | 1.20907  |   1.31905 |       2.41842 |                -0.907584  |        933 |
|            61 | ridge_full                    | ml                 |      1.28172 | 1.21929  |   1.33321 |       2.40737 |                -0.906693  |        933 |
|            61 | ridge_no_sample6              | ml                 |      1.28176 | 1.2192   |   1.33327 |       2.40736 |                -0.906653  |        933 |
|            61 | ridge_run_family_control      | run_family_control |      1.29081 | 1.22382  |   1.34049 |       2.43441 |                -0.897609  |        933 |
|            61 | cnn1d_only_sample6            | ml                 |      1.61652 | 1.54416  |   1.70213 |       2.6432  |                -0.571893  |        933 |
|            61 | early_late_gated_only_sample6 | ml                 |      1.63901 | 1.56287  |   1.71697 |       2.66195 |                -0.549412  |        933 |
|            61 | early_late_gated_no_sample6   | ml                 |      1.8723  | 1.80768  |   1.95511 |       2.76953 |                -0.316115  |        933 |
|            61 | mlp_only_sample6              | ml                 |      1.87423 | 1.79963  |   1.95538 |       2.78341 |                -0.314189  |        933 |
|            61 | cnn1d_full                    | ml                 |      1.87522 | 1.81294  |   1.94882 |       2.77781 |                -0.313198  |        933 |
|            61 | cnn1d_no_sample6              | ml                 |      1.91871 | 1.85143  |   2.00414 |       2.80908 |                -0.269711  |        933 |

## Atlas By Held-Out Run

| scope   | pickoff        | variant                |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_raw_same_pickoff_ns |
|:--------|:---------------|:-----------------------|-------------:|---------:|----------:|--------------:|-------------------------------:|
| run_58  | cfd20          | amplitude_bin_template |      1.9399  |  1.52198 |   2.18297 |       3.99939 |                   -1.17552     |
| run_58  | cfd20          | control_stratum        |      2.02968 |  1.74539 |   2.4762  |       4.09543 |                   -1.08574     |
| run_58  | cfd20          | raw                    |      3.11542 |  2.88617 |   3.34259 |       4.8861  |                    0           |
| run_58  | cfd20          | local_linear           |      3.14369 |  2.78005 |   3.39075 |       4.63202 |                    0.0282642   |
| run_58  | of_1_9         | local_linear           |      3.44268 |  3.17281 |   3.81718 |       3.39965 |                   -0.344396    |
| run_58  | of_1_9         | raw                    |      3.78707 |  3.37874 |   4.25398 |       3.84368 |                    0           |
| run_58  | of_1_9         | amplitude_bin_template |      4.41827 |  3.89927 |   4.87198 |       4.15686 |                    0.6312      |
| run_58  | of_1_9         | control_stratum        |      4.55958 |  4.17298 |   5.08252 |       4.24734 |                    0.772507    |
| run_58  | of_2_10        | local_linear           |      3.67988 |  3.22821 |   4.11788 |       3.67235 |                   -0.447903    |
| run_58  | of_2_10        | raw                    |      4.12779 |  3.59975 |   4.6447  |       4.11477 |                    0           |
| run_58  | of_2_10        | amplitude_bin_template |      4.66785 |  4.0871  |   5.23384 |       4.47224 |                    0.540063    |
| run_58  | of_2_10        | control_stratum        |      4.90887 |  4.50462 |   5.45356 |       4.56231 |                    0.781085    |
| run_58  | of_3_11        | local_linear           |      3.48151 |  3.25503 |   3.9036  |       3.60525 |                   -0.31778     |
| run_58  | of_3_11        | raw                    |      3.79929 |  3.42889 |   4.09091 |       4.05633 |                    0           |
| run_58  | of_3_11        | amplitude_bin_template |      4.336   |  4.0108  |   5.11921 |       4.39816 |                    0.536712    |
| run_58  | of_3_11        | control_stratum        |      4.70772 |  4.41112 |   5.36712 |       4.45135 |                    0.908431    |
| run_58  | of_4_12        | local_linear           |      3.07521 |  2.75321 |   3.64059 |       3.80159 |                   -0.123041    |
| run_58  | of_4_12        | raw                    |      3.19825 |  2.94715 |   3.79094 |       4.24566 |                    0           |
| run_58  | of_4_12        | amplitude_bin_template |      3.94339 |  3.57985 |   5.02794 |       4.55272 |                    0.745141    |
| run_58  | of_4_12        | control_stratum        |      4.40762 |  3.93634 |   5.25478 |       4.57167 |                    1.20937     |
| run_58  | template_phase | local_linear           |      2.6428  |  2.6428  |   2.64711 |       3.34001 |                    0           |
| run_58  | template_phase | raw                    |      2.6428  |  2.6428  |   2.77317 |       3.54397 |                    0           |
| run_58  | template_phase | amplitude_bin_template |      2.78753 |  2.6428  |   3.02317 |       5.31749 |                    0.144725    |
| run_58  | template_phase | control_stratum        |      2.90845 |  2.6428  |   3.27317 |       5.34932 |                    0.265644    |
| run_59  | cfd20          | amplitude_bin_template |      2.45871 |  2.31469 |   2.55874 |       3.9423  |                   -0.731687    |
| run_59  | cfd20          | local_linear           |      2.78209 |  2.67853 |   2.87207 |       5.67175 |                   -0.408309    |
| run_59  | cfd20          | raw                    |      3.19039 |  3.11345 |   3.26294 |       5.79544 |                    0           |
| run_59  | cfd20          | control_stratum        |      5.33575 |  5.06003 |   5.66413 |      12.7861  |                    2.14536     |
| run_59  | of_1_9         | local_linear           |      3.29419 |  3.15739 |   3.4243  |       3.57688 |                   -0.178154    |
| run_59  | of_1_9         | raw                    |      3.47235 |  3.37128 |   3.56262 |       3.85049 |                    0           |
| run_59  | of_1_9         | amplitude_bin_template |      4.05323 |  3.85641 |   4.21948 |       3.93495 |                    0.580883    |
| run_59  | of_1_9         | control_stratum        |      6.36128 |  6.1935  |   6.6159  |       6.13936 |                    2.88894     |
| run_59  | of_2_10        | local_linear           |      3.31771 |  3.20636 |   3.4148  |       3.60157 |                   -0.163646    |
| run_59  | of_2_10        | raw                    |      3.48136 |  3.37511 |   3.58392 |       3.87238 |                    0           |
| run_59  | of_2_10        | amplitude_bin_template |      4.22285 |  3.99742 |   4.36125 |       4.05932 |                    0.741498    |
| run_59  | of_2_10        | control_stratum        |      6.38602 |  6.2132  |   6.62213 |       6.22166 |                    2.90467     |
| run_59  | of_3_11        | local_linear           |      3.33958 |  3.21059 |   3.41803 |       3.58467 |                   -0.0790543   |
| run_59  | of_3_11        | raw                    |      3.41864 |  3.32674 |   3.53414 |       3.829   |                    0           |
| run_59  | of_3_11        | amplitude_bin_template |      4.20135 |  4.02869 |   4.45939 |       4.14545 |                    0.782712    |
| run_59  | of_3_11        | control_stratum        |      6.17543 |  5.97057 |   6.42942 |       6.25441 |                    2.75679     |
| run_59  | of_4_12        | local_linear           |      3.28521 |  3.16859 |   3.42565 |       3.66057 |                   -0.0727627   |
| run_59  | of_4_12        | raw                    |      3.35797 |  3.25957 |   3.50124 |       3.88264 |                    0           |
| run_59  | of_4_12        | amplitude_bin_template |      4.14517 |  3.93884 |   4.35446 |       4.30538 |                    0.787201    |
| run_59  | of_4_12        | control_stratum        |      6.02032 |  5.81358 |   6.16191 |       6.31612 |                    2.66235     |
| run_59  | template_phase | local_linear           |      2.74232 |  2.62333 |   2.74232 |       3.2543  |                   -0.25        |
| run_59  | template_phase | raw                    |      2.99232 |  2.87333 |   3.12333 |       3.34278 |                    0           |
| run_59  | template_phase | amplitude_bin_template |      3.12333 |  2.99232 |   3.12333 |       3.68846 |                    0.131007    |
| run_59  | template_phase | control_stratum        |      4       |  3.87333 |   4.24232 |       4.80279 |                    1.00768     |
| run_60  | cfd20          | amplitude_bin_template |      2.70167 |  2.58416 |   2.8493  |       2.984   |                   -0.436952    |
| run_60  | cfd20          | control_stratum        |      2.72024 |  2.60259 |   2.85973 |       2.9684  |                   -0.418376    |
| run_60  | cfd20          | local_linear           |      2.84591 |  2.75075 |   2.93539 |       7.21916 |                   -0.292706    |
| run_60  | cfd20          | raw                    |      3.13862 |  3.07371 |   3.21679 |       7.26201 |                    0           |
| run_60  | of_1_9         | local_linear           |      3.27098 |  3.09201 |   3.38443 |       3.61178 |                   -0.143265    |
| run_60  | of_1_9         | raw                    |      3.41424 |  3.27824 |   3.56768 |       3.90972 |                    0           |
| run_60  | of_1_9         | control_stratum        |      4.17028 |  3.99066 |   4.34977 |       3.99746 |                    0.756045    |
| run_60  | of_1_9         | amplitude_bin_template |      4.29598 |  4.09978 |   4.4644  |       4.0342  |                    0.881742    |
| run_60  | of_2_10        | local_linear           |      3.30016 |  3.17582 |   3.41025 |       3.62201 |                   -0.159342    |
| run_60  | of_2_10        | raw                    |      3.4595  |  3.35284 |   3.60627 |       3.92712 |                    0           |
| run_60  | of_2_10        | control_stratum        |      4.31414 |  4.15325 |   4.49648 |       4.13993 |                    0.854635    |
| run_60  | of_2_10        | amplitude_bin_template |      4.49103 |  4.29066 |   4.6303  |       4.18156 |                    1.03153     |
| run_60  | of_3_11        | local_linear           |      3.37932 |  3.28723 |   3.49671 |       3.64077 |                   -0.157143    |
| run_60  | of_3_11        | raw                    |      3.53646 |  3.43171 |   3.66473 |       3.92103 |                    0           |
| run_60  | of_3_11        | control_stratum        |      4.35028 |  4.20746 |   4.52076 |       4.27683 |                    0.813818    |
| run_60  | of_3_11        | amplitude_bin_template |      4.56602 |  4.32648 |   4.73083 |       4.32637 |                    1.02955     |
| run_60  | of_4_12        | local_linear           |      3.40385 |  3.3053  |   3.5112  |       3.82028 |                   -0.121675    |
| run_60  | of_4_12        | raw                    |      3.52553 |  3.39525 |   3.66253 |       4.08022 |                    0           |
| run_60  | of_4_12        | control_stratum        |      4.39025 |  4.23606 |   4.58959 |       4.5499  |                    0.864722    |
| run_60  | of_4_12        | amplitude_bin_template |      4.49239 |  4.30423 |   4.6843  |       4.60198 |                    0.966864    |
| run_60  | template_phase | local_linear           |      2.4613  |  2.4613  |   2.4613  |       3.139   |                   -0.202625    |
| run_60  | template_phase | raw                    |      2.66393 |  2.66393 |   2.7113  |       3.279   |                    0           |
| run_60  | template_phase | amplitude_bin_template |      2.7113  |  2.7113  |   2.91393 |       3.89453 |                    0.0473745   |
| run_60  | template_phase | control_stratum        |      2.7113  |  2.7113  |   2.7113  |       4.04318 |                    0.0473745   |
| run_61  | cfd20          | control_stratum        |      2.2659  |  2.16596 |   2.38488 |       3.30962 |                   -0.648179    |
| run_61  | cfd20          | amplitude_bin_template |      2.27392 |  2.1405  |   2.38822 |       3.32105 |                   -0.640164    |
| run_61  | cfd20          | local_linear           |      2.52212 |  2.43477 |   2.643   |       6.52632 |                   -0.391964    |
| run_61  | cfd20          | raw                    |      2.91408 |  2.84557 |   3.00224 |       6.59866 |                    0           |
| run_61  | of_1_9         | local_linear           |      3.10227 |  2.97654 |   3.19062 |       3.57485 |                   -0.110907    |
| run_61  | of_1_9         | raw                    |      3.21318 |  3.11336 |   3.34174 |       3.78716 |                    0           |
| run_61  | of_1_9         | control_stratum        |      4.09885 |  3.95293 |   4.29168 |       4.05371 |                    0.885673    |
| run_61  | of_1_9         | amplitude_bin_template |      4.19942 |  4.07828 |   4.32861 |       4.05182 |                    0.986237    |
| run_61  | of_2_10        | local_linear           |      3.20967 |  3.11442 |   3.32827 |       3.65338 |                   -0.121874    |
| run_61  | of_2_10        | raw                    |      3.33154 |  3.19779 |   3.42938 |       3.86708 |                    0           |
| run_61  | of_2_10        | control_stratum        |      4.22794 |  4.06746 |   4.4122  |       4.19655 |                    0.896402    |
| run_61  | of_2_10        | amplitude_bin_template |      4.32603 |  4.16011 |   4.49455 |       4.20854 |                    0.994494    |
| run_61  | of_3_11        | local_linear           |      3.26917 |  3.14267 |   3.37811 |       3.72363 |                   -0.00703535  |
| run_61  | of_3_11        | raw                    |      3.27621 |  3.14866 |   3.38569 |       3.91526 |                    0           |
| run_61  | of_3_11        | control_stratum        |      4.25252 |  4.03688 |   4.46252 |       4.25633 |                    0.976315    |
| run_61  | of_3_11        | amplitude_bin_template |      4.30416 |  4.1294  |   4.50471 |       4.29514 |                    1.02796     |
| run_61  | of_4_12        | raw                    |      3.17018 |  3.05165 |   3.32173 |       4.06163 |                    0           |
| run_61  | of_4_12        | local_linear           |      3.18912 |  3.08954 |   3.33498 |       3.88205 |                    0.0189419   |
| run_61  | of_4_12        | control_stratum        |      4.15877 |  3.92799 |   4.32599 |       4.40499 |                    0.988591    |
| run_61  | of_4_12        | amplitude_bin_template |      4.16475 |  3.92244 |   4.34345 |       4.46458 |                    0.994573    |
| run_61  | template_phase | local_linear           |      2.70351 |  2.56459 |   2.70351 |       3.17724 |                   -5.77316e-15 |
| run_61  | template_phase | amplitude_bin_template |      2.70351 |  2.70351 |   2.70351 |       4.04422 |                    0           |
| run_61  | template_phase | control_stratum        |      2.70351 |  2.70351 |   2.70351 |       3.9539  |                    0           |
| run_61  | template_phase | raw                    |      2.70351 |  2.70351 |   2.70351 |       3.20716 |                    0           |
| run_62  | cfd20          | control_stratum        |      2.38691 |  2.27105 |   2.46499 |       2.81149 |                   -0.844772    |
| run_62  | cfd20          | amplitude_bin_template |      2.40272 |  2.27746 |   2.521   |       2.8301  |                   -0.828965    |
| run_62  | cfd20          | local_linear           |      2.74446 |  2.65604 |   2.84583 |       4.79742 |                   -0.48723     |
| run_62  | cfd20          | raw                    |      3.23169 |  3.1388  |   3.34896 |       4.95545 |                    0           |

## Leakage and Systematics

|   heldout_run | check                                               |      value | pass   |
|--------------:|:----------------------------------------------------|-----------:|:-------|
|            58 | train_heldout_run_overlap                           |  0         | True   |
|            58 | train_heldout_event_id_overlap                      |  0         | True   |
|            58 | feature_audit                                       |  0         | True   |
|            58 | shuffled_target_worse:ridge_full                    |  0.27286   | True   |
|            58 | shuffled_target_worse:hgb_full                      |  0.561495  | True   |
|            58 | shuffled_target_worse:extra_trees_full              |  0.664807  | True   |
|            58 | shuffled_target_worse:mlp_full                      |  0.0173259 | True   |
|            58 | shuffled_target_worse:cnn1d_full                    |  0.323085  | True   |
|            58 | shuffled_target_worse:early_late_gated_full         |  0.377514  | True   |
|            58 | shuffled_target_worse:ridge_no_sample6              |  0.244226  | True   |
|            58 | shuffled_target_worse:hgb_no_sample6                |  0.338097  | True   |
|            58 | shuffled_target_worse:extra_trees_no_sample6        |  0.713932  | True   |
|            58 | shuffled_target_worse:mlp_no_sample6                |  0.29243   | True   |
|            58 | shuffled_target_worse:cnn1d_no_sample6              |  0.124959  | True   |
|            58 | shuffled_target_worse:early_late_gated_no_sample6   |  0.252263  | True   |
|            58 | shuffled_target_worse:ridge_only_sample6            |  0.152428  | True   |
|            58 | shuffled_target_worse:hgb_only_sample6              |  0.407689  | True   |
|            58 | shuffled_target_worse:extra_trees_only_sample6      |  0.501919  | True   |
|            58 | shuffled_target_worse:mlp_only_sample6              |  0.147543  | True   |
|            58 | shuffled_target_worse:cnn1d_only_sample6            |  0.311918  | True   |
|            58 | shuffled_target_worse:early_late_gated_only_sample6 |  0.234994  | True   |
|            59 | train_heldout_run_overlap                           |  0         | True   |
|            59 | train_heldout_event_id_overlap                      |  0         | True   |
|            59 | feature_audit                                       |  0         | True   |
|            59 | shuffled_target_worse:ridge_full                    |  0.266079  | True   |
|            59 | shuffled_target_worse:hgb_full                      |  0.497455  | True   |
|            59 | shuffled_target_worse:extra_trees_full              |  0.757286  | True   |
|            59 | shuffled_target_worse:mlp_full                      |  0.120297  | True   |
|            59 | shuffled_target_worse:cnn1d_full                    |  0.224313  | True   |
|            59 | shuffled_target_worse:early_late_gated_full         |  0.16072   | True   |
|            59 | shuffled_target_worse:ridge_no_sample6              |  0.239406  | True   |
|            59 | shuffled_target_worse:hgb_no_sample6                |  0.467941  | True   |
|            59 | shuffled_target_worse:extra_trees_no_sample6        |  0.66102   | True   |
|            59 | shuffled_target_worse:mlp_no_sample6                |  0.0423043 | True   |
|            59 | shuffled_target_worse:cnn1d_no_sample6              |  0.378054  | True   |
|            59 | shuffled_target_worse:early_late_gated_no_sample6   |  0.307973  | True   |
|            59 | shuffled_target_worse:ridge_only_sample6            |  0.251173  | True   |
|            59 | shuffled_target_worse:hgb_only_sample6              |  0.453812  | True   |
|            59 | shuffled_target_worse:extra_trees_only_sample6      |  0.559643  | True   |
|            59 | shuffled_target_worse:mlp_only_sample6              |  0.328326  | True   |
|            59 | shuffled_target_worse:cnn1d_only_sample6            |  0.28922   | True   |
|            59 | shuffled_target_worse:early_late_gated_only_sample6 |  0.22719   | True   |
|            60 | train_heldout_run_overlap                           |  0         | True   |
|            60 | train_heldout_event_id_overlap                      |  0         | True   |
|            60 | feature_audit                                       |  0         | True   |
|            60 | shuffled_target_worse:ridge_full                    |  0.0531545 | True   |
|            60 | shuffled_target_worse:hgb_full                      |  0.353934  | True   |
|            60 | shuffled_target_worse:extra_trees_full              |  0.423146  | True   |
|            60 | shuffled_target_worse:mlp_full                      |  0.164735  | True   |
|            60 | shuffled_target_worse:cnn1d_full                    |  0.147238  | True   |
|            60 | shuffled_target_worse:early_late_gated_full         |  0.0677609 | True   |
|            60 | shuffled_target_worse:ridge_no_sample6              |  0.0734598 | True   |
|            60 | shuffled_target_worse:hgb_no_sample6                |  0.323688  | True   |
|            60 | shuffled_target_worse:extra_trees_no_sample6        |  0.442934  | True   |
|            60 | shuffled_target_worse:mlp_no_sample6                |  0.164233  | True   |
|            60 | shuffled_target_worse:cnn1d_no_sample6              |  0.228653  | True   |
|            60 | shuffled_target_worse:early_late_gated_no_sample6   |  0.298353  | True   |
|            60 | shuffled_target_worse:ridge_only_sample6            |  0.0623574 | True   |
|            60 | shuffled_target_worse:hgb_only_sample6              |  0.281261  | True   |
|            60 | shuffled_target_worse:extra_trees_only_sample6      |  0.427762  | True   |
|            60 | shuffled_target_worse:mlp_only_sample6              | -0.0169279 | False  |
|            60 | shuffled_target_worse:cnn1d_only_sample6            |  0.135993  | True   |
|            60 | shuffled_target_worse:early_late_gated_only_sample6 |  0.208803  | True   |
|            61 | train_heldout_run_overlap                           |  0         | True   |
|            61 | train_heldout_event_id_overlap                      |  0         | True   |
|            61 | feature_audit                                       |  0         | True   |
|            61 | shuffled_target_worse:ridge_full                    |  0.960053  | True   |
|            61 | shuffled_target_worse:hgb_full                      |  1.06184   | True   |
|            61 | shuffled_target_worse:extra_trees_full              |  1.09461   | True   |
|            61 | shuffled_target_worse:mlp_full                      |  0.169666  | True   |
|            61 | shuffled_target_worse:cnn1d_full                    |  0.141215  | True   |
|            61 | shuffled_target_worse:early_late_gated_full         |  0.0728707 | True   |
|            61 | shuffled_target_worse:ridge_no_sample6              |  0.880581  | True   |
|            61 | shuffled_target_worse:hgb_no_sample6                |  0.996887  | True   |
|            61 | shuffled_target_worse:extra_trees_no_sample6        |  1.19643   | True   |
|            61 | shuffled_target_worse:mlp_no_sample6                |  0.216161  | True   |
|            61 | shuffled_target_worse:cnn1d_no_sample6              |  0.29556   | True   |
|            61 | shuffled_target_worse:early_late_gated_no_sample6   |  0.247187  | True   |
|            61 | shuffled_target_worse:ridge_only_sample6            |  0.887309  | True   |
|            61 | shuffled_target_worse:hgb_only_sample6              |  1.08168   | True   |
|            61 | shuffled_target_worse:extra_trees_only_sample6      |  1.02      | True   |
|            61 | shuffled_target_worse:mlp_only_sample6              |  0.29658   | True   |
|            61 | shuffled_target_worse:cnn1d_only_sample6            |  0.63613   | True   |
|            61 | shuffled_target_worse:early_late_gated_only_sample6 |  0.455861  | True   |
|            62 | train_heldout_run_overlap                           |  0         | True   |
|            62 | train_heldout_event_id_overlap                      |  0         | True   |
|            62 | feature_audit                                       |  0         | True   |
|            62 | shuffled_target_worse:ridge_full                    |  0.265741  | True   |
|            62 | shuffled_target_worse:hgb_full                      |  0.545702  | True   |
|            62 | shuffled_target_worse:extra_trees_full              |  0.636147  | True   |
|            62 | shuffled_target_worse:mlp_full                      |  0.191434  | True   |
|            62 | shuffled_target_worse:cnn1d_full                    |  0.223802  | True   |
|            62 | shuffled_target_worse:early_late_gated_full         |  0.606895  | True   |
|            62 | shuffled_target_worse:ridge_no_sample6              |  0.314066  | True   |
|            62 | shuffled_target_worse:hgb_no_sample6                |  0.527964  | True   |
|            62 | shuffled_target_worse:extra_trees_no_sample6        |  0.649886  | True   |
|            62 | shuffled_target_worse:mlp_no_sample6                | -0.0249128 | False  |
|            62 | shuffled_target_worse:cnn1d_no_sample6              |  0.266491  | True   |
|            62 | shuffled_target_worse:early_late_gated_no_sample6   |  0.395051  | True   |
|            62 | shuffled_target_worse:ridge_only_sample6            |  0.313863  | True   |
|            62 | shuffled_target_worse:hgb_only_sample6              |  0.505192  | True   |
|            62 | shuffled_target_worse:extra_trees_only_sample6      |  0.492375  | True   |
|            62 | shuffled_target_worse:mlp_only_sample6              |  0.0983673 | True   |
|            62 | shuffled_target_worse:cnn1d_only_sample6            |  0.324849  | True   |
|            62 | shuffled_target_worse:early_late_gated_only_sample6 |  0.46658   | True   |
|            63 | train_heldout_run_overlap                           |  0         | True   |
|            63 | train_heldout_event_id_overlap                      |  0         | True   |
|            63 | feature_audit                                       |  0         | True   |
|            63 | shuffled_target_worse:ridge_full                    |  0.231844  | True   |
|            63 | shuffled_target_worse:hgb_full                      |  0.29131   | True   |
|            63 | shuffled_target_worse:extra_trees_full              |  0.554877  | True   |
|            63 | shuffled_target_worse:mlp_full                      |  0.205296  | True   |
|            63 | shuffled_target_worse:cnn1d_full                    |  0.100404  | True   |
|            63 | shuffled_target_worse:early_late_gated_full         |  0.0738592 | True   |
|            63 | shuffled_target_worse:ridge_no_sample6              |  0.177621  | True   |
|            63 | shuffled_target_worse:hgb_no_sample6                |  0.311544  | True   |
|            63 | shuffled_target_worse:extra_trees_no_sample6        |  0.59932   | True   |
|            63 | shuffled_target_worse:mlp_no_sample6                |  0.299519  | True   |
|            63 | shuffled_target_worse:cnn1d_no_sample6              |  0.310286  | True   |
|            63 | shuffled_target_worse:early_late_gated_no_sample6   |  0.005607  | True   |

Main caveats:

- The sample-6 replacements are falsification operators, not proposed production corrections. They intentionally test whether a smooth/interpolated value can mimic or improve the raw sample.
- Sample-II run 65 has low statistics; the pooled CI therefore uses runs as the outer bootstrap unit.
- The S02b target is internally defined from same-event downstream staves, so all claims are relative timing-closure claims, not absolute beam-time truth.
- Run-family controls are coarse and predeclared; they diagnose gross family nuisance but cannot exclude all detector-condition drift.
- Multiple model families and masks are screened. The named winner is a benchmark winner, while adoption requires the control rows and atlas deltas to be physically coherent.

## Verdict

Winner in `result.json`: `extra_trees_full` with pooled `sigma68 = 1.099 ns` and CI `[1.063, 1.131] ns`.

Interpretation: Sample 6 is not required for the best residual correction; gains persist when it is removed, so the sample-6 smoothing gain is consistent with nuisance/replacement structure rather than a unique causal timing source. 4 shuffled-target checks beat their nominal model and are flagged as stability caveats.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p01l_1781049810_1116_3eb03e19_sample6_smoothing_causality.py --config configs/p01l_1781049810_1116_3eb03e19_sample6_smoothing_causality.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `sample6_atlas_pooled.csv`, `sample6_atlas_by_run.csv`, `leakage_checks.csv`, `model_diagnostics.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
