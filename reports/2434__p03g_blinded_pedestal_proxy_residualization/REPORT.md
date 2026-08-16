# P03g: pedestal-residualized samples 0-3 before P03f multimodel ablation

- **Ticket:** `#2434`
- **Issue URL:** https://github.com/SzeChunYiu/factory-tickets/issues/2434
- **Worker:** `testbeam-laptop-3`
- **Claimed study:** P03g: blinded pedestal-proxy residualization of samples 0-3
- **Input:** raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **P03e variants:** `['waveform_only', 'waveform_stave_onehot', 'waveform_amp_shape', 'waveform_amp_shape_stave']`

## Question and preregistered estimand

The ticket asks whether the P03f `no_samples_0_3` and `only_samples_0_3` conclusions remain unchanged when samples 0-3 are retained but residualized against blinded pedestal/baseline proxies before the multimodel ablation is repeated. The estimand is the B4/B6/B8 event-paired timing width after a fold-local S03a analytic timewalk correction:

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

For every held-out run, the other six Sample-II runs define all train-only objects: S02 templates, the best S02 template-phase pickoff, and the S03a analytic amplitude-timewalk closure. The traditional comparator is `analytic_timewalk`.

The residual learners target `y_i = t_i(analytic) - mean(t_j(analytic), t_k(analytic))` within the same event and predict a same-pulse correction. Five model families are benchmarked under the four P03e feature variants:

- `ridge`: standardized linear Ridge regression.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: heteroskedastic fully connected neural net.
- `cnn1d`: compact one-dimensional convolutional network over 18 samples.
- `feature_gated`: new architecture with separate waveform and auxiliary-feature branches mixed by a learned gate.

The feature variants are `waveform_only`, `waveform_stave_onehot`, `waveform_amp_shape`, and `waveform_amp_shape_stave`. Features exclude run id, event id, event order, other-stave timings, and pair residuals. Stave-offset guardrails use only amplitude summaries plus stave one-hot with no waveform samples. Shuffled-target controls repeat every nominal model with train targets permuted.

### Tuning and implementation notes

All training/tuning operations are scoped to the six non-held-out Sample-II runs in each fold. The analytic baseline uses grouped-run CV over the S03a candidate family and ridge alpha. Ridge residual models use grouped-run CV over `alpha` on the training runs; HGB and neural hyperparameters are fixed from the preregistered config to avoid tuning on the held-out run. The ridge alpha scan emits ill-conditioned-matrix warnings for nearly collinear feature sets, especially when waveform summaries and stave one-hot are both present; this is treated as a numerical caveat for ridge rows and does not affect the HGB winner.

The new `feature_gated` architecture embeds the 18-sample normalized waveform and the auxiliary P03e feature block separately, learns an auxiliary-dependent scalar gate, and predicts a heteroskedastic residual correction. For variants without auxiliary features the auxiliary block is a constant zero column, so the architecture reduces to a waveform-gated control rather than receiving hidden identifiers.

### Pedestal-proxy residualization

For each leave-one-run fold and feature variant, samples 0-3 are replaced by train-fold residuals

`x'_s = x_s - \hat f_s(z) + mean_train(x_s), s in {0,1,2,3}`,

where `z` contains blinded pedestal proxies only: mean/slope/RMS of samples 0-3, the contrast between samples 0-3 and 4-7, log amplitude, peak sample, area over amplitude, and downstream-stave one-hot. The Ridge residualizer is fitted on training runs only and then applied to the held-out run. It never sees timing targets, event ids, run ids, event order, other-stave times, or pair residuals.

Average train-fold proxy removal:

|   sample |   train_r2 |   train_original_std |   train_residualized_std |
|---------:|-----------:|---------------------:|-------------------------:|
|        0 |   0.998894 |            0.178432  |               0.00592812 |
|        1 |   0.978108 |            0.0977037 |               0.0144524  |
|        2 |   0.980593 |            0.0979695 |               0.0136476  |
|        3 |   0.999626 |            0.271825  |               0.00525415 |

## Pooled Benchmark

| method                                 | family      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:---------------------------------------|:------------|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------:|
| hgb_waveform_amp_shape_stave           | ml          |      1.10885 |  1.07648 |   1.16491 |               -0.442245   |    -0.844942   |      -0.235194  |              11460 |
| hgb_waveform_stave_onehot              | ml          |      1.13584 |  1.08978 |   1.18906 |               -0.415251   |    -0.84638    |      -0.203016  |              11460 |
| mlp_waveform_amp_shape_stave           | ml          |      1.17307 |  1.13779 |   1.22612 |               -0.378018   |    -0.77767    |      -0.170156  |              11460 |
| mlp_waveform_stave_onehot              | ml          |      1.23415 |  1.15197 |   1.2941  |               -0.316945   |    -0.756192   |      -0.0897879 |              11460 |
| ridge_waveform_stave_onehot            | ml          |      1.24693 |  1.17542 |   1.3196  |               -0.304162   |    -0.73629    |      -0.0916574 |              11460 |
| feature_gated_waveform_stave_onehot    | ml          |      1.25048 |  1.2028  |   1.31444 |               -0.300613   |    -0.697791   |      -0.10303   |              11460 |
| feature_gated_waveform_amp_shape_stave | ml          |      1.25388 |  1.20474 |   1.30296 |               -0.297208   |    -0.666741   |      -0.0952246 |              11460 |
| cnn1d_waveform_amp_shape_stave         | ml          |      1.26629 |  1.20897 |   1.34746 |               -0.284798   |    -0.68846    |      -0.0795721 |              11460 |
| ridge_waveform_amp_shape_stave         | ml          |      1.32007 |  1.27788 |   1.3738  |               -0.231024   |    -0.633105   |      -0.0342385 |              11460 |
| cnn1d_waveform_stave_onehot            | ml          |      1.37765 |  1.33997 |   1.45204 |               -0.173438   |    -0.545056   |       0.0479354 |              11460 |
| hgb_waveform_amp_shape                 | ml          |      1.4706  |  1.3838  |   1.58912 |               -0.0804877  |    -0.351813   |       0.0398152 |              11460 |
| hgb_waveform_only                      | ml          |      1.50937 |  1.42632 |   1.63718 |               -0.0417233  |    -0.281518   |       0.0800574 |              11460 |
| cnn1d_waveform_only                    | ml          |      1.54503 |  1.36376 |   1.92469 |               -0.00606029 |    -0.0555626  |       0.0541349 |              11460 |
| analytic_timewalk                      | traditional |      1.55109 |  1.36375 |   1.93624 |                0          |     0          |       0         |              11460 |
| feature_gated_waveform_only            | ml          |      1.56345 |  1.36495 |   1.94629 |                0.0123615  |    -0.0552386  |       0.0662194 |              11460 |
| mlp_waveform_only                      | ml          |      1.60439 |  1.41742 |   1.95592 |                0.0532973  |    -0.0124049  |       0.126542  |              11460 |
| mlp_waveform_amp_shape                 | ml          |      1.61402 |  1.51633 |   1.76913 |                0.0629287  |    -0.159124   |       0.181266  |              11460 |
| ridge_waveform_only                    | ml          |      1.63339 |  1.48354 |   1.94405 |                0.0822945  |    -0.00996316 |       0.143316  |              11460 |
| feature_gated_waveform_amp_shape       | ml          |      1.75917 |  1.60578 |   2.01461 |                0.208079   |     0.0619676  |       0.289381  |              11460 |
| cnn1d_waveform_amp_shape               | ml          |      1.78076 |  1.63986 |   1.99286 |                0.229673   |     0.0472377  |       0.320926  |              11460 |
| ridge_waveform_amp_shape               | ml          |      1.84772 |  1.67822 |   2.09533 |                0.296627   |     0.153375   |       0.356412  |              11460 |

## Feature-Variant Summary

| variant                  | best_method                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_pair_residuals |
|:-------------------------|:-----------------------------|-------------:|---------:|----------:|--------------------------:|-------------------:|
| waveform_amp_shape_stave | hgb_waveform_amp_shape_stave |      1.10885 |  1.07648 |   1.16491 |                -0.442245  |              11460 |
| waveform_stave_onehot    | hgb_waveform_stave_onehot    |      1.13584 |  1.08978 |   1.18906 |                -0.415251  |              11460 |
| waveform_amp_shape       | hgb_waveform_amp_shape       |      1.4706  |  1.3838  |   1.58912 |                -0.0804877 |              11460 |
| waveform_only            | hgb_waveform_only            |      1.50937 |  1.42632 |   1.63718 |                -0.0417233 |              11460 |

## Controls

| method                                          | family                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:------------------------------------------------|:------------------------|-------------:|---------:|----------:|--------------------------:|
| hgb_stave_offset_guardrail                      | stave_offset_guardrail  |      1.15156 |  1.11007 |   1.2069  |              -0.39953     |
| ridge_stave_offset_guardrail                    | stave_offset_guardrail  |      1.26259 |  1.2021  |   1.32625 |              -0.288498    |
| feature_gated_waveform_amp_shape_stave_shuffled | shuffled_target_control |      1.54607 |  1.35187 |   1.93687 |              -0.00501988  |
| cnn1d_waveform_amp_shape_stave_shuffled         | shuffled_target_control |      1.54817 |  1.36629 |   1.91425 |              -0.00291854  |
| cnn1d_waveform_only_shuffled                    | shuffled_target_control |      1.54958 |  1.36334 |   1.9392  |              -0.00150755  |
| mlp_waveform_only_shuffled                      | shuffled_target_control |      1.55138 |  1.37069 |   1.93142 |               0.000289057 |
| feature_gated_waveform_only_shuffled            | shuffled_target_control |      1.55405 |  1.37005 |   1.93942 |               0.00295772  |
| feature_gated_waveform_amp_shape_shuffled       | shuffled_target_control |      1.55683 |  1.37665 |   1.92693 |               0.00574256  |
| mlp_waveform_amp_shape_shuffled                 | shuffled_target_control |      1.55722 |  1.36492 |   1.92681 |               0.00613311  |
| feature_gated_waveform_stave_onehot_shuffled    | shuffled_target_control |      1.55766 |  1.37033 |   1.9214  |               0.00657255  |
| ridge_waveform_amp_shape_stave_shuffled         | shuffled_target_control |      1.55857 |  1.35693 |   1.91943 |               0.00748213  |
| ridge_waveform_only_shuffled                    | shuffled_target_control |      1.56025 |  1.36409 |   1.94157 |               0.00915529  |
| cnn1d_waveform_amp_shape_shuffled               | shuffled_target_control |      1.5657  |  1.36389 |   1.93222 |               0.0146075   |
| ridge_waveform_stave_onehot_shuffled            | shuffled_target_control |      1.56885 |  1.35725 |   1.92663 |               0.0177609   |
| mlp_waveform_stave_onehot_shuffled              | shuffled_target_control |      1.57147 |  1.35548 |   1.92821 |               0.0203817   |
| cnn1d_waveform_stave_onehot_shuffled            | shuffled_target_control |      1.57431 |  1.37487 |   1.86115 |               0.0232152   |
| mlp_waveform_amp_shape_stave_shuffled           | shuffled_target_control |      1.58145 |  1.39415 |   1.97781 |               0.0303603   |
| ridge_waveform_amp_shape_shuffled               | shuffled_target_control |      1.58226 |  1.35778 |   1.92978 |               0.0311692   |
| hgb_waveform_stave_onehot_shuffled              | shuffled_target_control |      1.62333 |  1.43933 |   1.97158 |               0.0722365   |
| hgb_waveform_amp_shape_stave_shuffled           | shuffled_target_control |      1.63838 |  1.45055 |   1.9235  |               0.0872915   |
| hgb_waveform_only_shuffled                      | shuffled_target_control |      1.65587 |  1.44396 |   1.98377 |               0.104775    |
| hgb_waveform_amp_shape_shuffled                 | shuffled_target_control |      1.66364 |  1.43734 |   1.994   |               0.112546    |

Shuffled-target rows are interpreted as stability/leakage warnings, not as positive evidence. A shuffled control that matches or beats its nominal counterpart means that model/variant combination is not causally interpretable.

## Held-Out Runs

|   heldout_run | method                                 | family                 |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_events |
|--------------:|:---------------------------------------|:-----------------------|-------------:|---------:|----------:|--------------------------:|-----------:|
|            58 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     0.999863 | 0.878537 |   1.21483 |              -0.18762     |         73 |
|            58 | feature_gated_waveform_stave_onehot    | ml                     |     1.00553  | 0.944493 |   1.11044 |              -0.181957    |         73 |
|            58 | ridge_waveform_stave_onehot            | ml                     |     1.04711  | 0.959874 |   1.18612 |              -0.140378    |         73 |
|            58 | feature_gated_waveform_amp_shape_stave | ml                     |     1.05747  | 0.928969 |   1.27204 |              -0.13001     |         73 |
|            58 | hgb_waveform_amp_shape_stave           | ml                     |     1.05764  | 0.858417 |   1.33464 |              -0.129839    |         73 |
|            58 | hgb_waveform_stave_onehot              | ml                     |     1.08563  | 0.94783  |   1.32557 |              -0.101854    |         73 |
|            58 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.09812  | 0.947827 |   1.31561 |              -0.0893612   |         73 |
|            58 | mlp_waveform_amp_shape_stave           | ml                     |     1.10094  | 0.839286 |   1.25288 |              -0.0865483   |         73 |
|            58 | ridge_waveform_amp_shape_stave         | ml                     |     1.13783  | 1.03062  |   1.33621 |              -0.0496531   |         73 |
|            58 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.15131  | 1.01333  |   1.32408 |              -0.0361735   |         73 |
|            58 | mlp_waveform_stave_onehot              | ml                     |     1.16068  | 1.04671  |   1.32422 |              -0.0268003   |         73 |
|            58 | feature_gated_waveform_only            | ml                     |     1.18573  | 1.13524  |   1.41476 |              -0.0017562   |         73 |
|            58 | analytic_timewalk                      | traditional            |     1.18748  | 1.13423  |   1.41572 |               0           |         73 |
|            58 | cnn1d_waveform_only                    | ml                     |     1.19643  | 1.14288  |   1.42223 |               0.00894492  |         73 |
|            58 | cnn1d_waveform_stave_onehot            | ml                     |     1.28503  | 1.20657  |   1.37787 |               0.0975492   |         73 |
|            58 | mlp_waveform_only                      | ml                     |     1.28671  | 1.17802  |   1.47246 |               0.0992243   |         73 |
|            58 | ridge_waveform_only                    | ml                     |     1.43403  | 1.23336  |   1.62158 |               0.246542    |         73 |
|            58 | cnn1d_waveform_amp_shape               | ml                     |     1.55388  | 1.41997  |   1.81349 |               0.366397    |         73 |
|            58 | feature_gated_waveform_amp_shape       | ml                     |     1.57814  | 1.35797  |   1.76962 |               0.390657    |         73 |
|            58 | mlp_waveform_amp_shape                 | ml                     |     1.5927   | 1.3311   |   1.8614  |               0.405212    |         73 |
|            58 | ridge_waveform_amp_shape               | ml                     |     1.67589  | 1.46124  |   1.94728 |               0.48841     |         73 |
|            58 | hgb_waveform_amp_shape                 | ml                     |     1.69223  | 1.49655  |   1.92038 |               0.504749    |         73 |
|            58 | hgb_waveform_only                      | ml                     |     1.70436  | 1.4714   |   1.83653 |               0.516872    |         73 |
|            59 | hgb_waveform_amp_shape_stave           | ml                     |     1.09141  | 1.02838  |   1.14176 |              -0.367298    |        763 |
|            59 | hgb_waveform_stave_onehot              | ml                     |     1.1236   | 1.06209  |   1.18368 |              -0.335108    |        763 |
|            59 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.15319  | 1.08616  |   1.21954 |              -0.305518    |        763 |
|            59 | mlp_waveform_amp_shape_stave           | ml                     |     1.15827  | 1.0908   |   1.21878 |              -0.300438    |        763 |
|            59 | feature_gated_waveform_stave_onehot    | ml                     |     1.27183  | 1.23702  |   1.34569 |              -0.186875    |        763 |
|            59 | mlp_waveform_stave_onehot              | ml                     |     1.28176  | 1.21332  |   1.34282 |              -0.176946    |        763 |
|            59 | feature_gated_waveform_amp_shape_stave | ml                     |     1.28302  | 1.21418  |   1.34906 |              -0.175686    |        763 |
|            59 | ridge_waveform_stave_onehot            | ml                     |     1.31035  | 1.25054  |   1.36588 |              -0.148357    |        763 |
|            59 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.32783  | 1.27368  |   1.39175 |              -0.130882    |        763 |
|            59 | ridge_waveform_amp_shape_stave         | ml                     |     1.33319  | 1.27008  |   1.39507 |              -0.125515    |        763 |
|            59 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.3542   | 1.28749  |   1.40336 |              -0.104508    |        763 |
|            59 | hgb_waveform_amp_shape                 | ml                     |     1.39203  | 1.34359  |   1.43965 |              -0.0666805   |        763 |
|            59 | hgb_waveform_only                      | ml                     |     1.42194  | 1.3648   |   1.4743  |              -0.0367724   |        763 |
|            59 | cnn1d_waveform_only                    | ml                     |     1.43601  | 1.35354  |   1.50789 |              -0.0226955   |        763 |
|            59 | cnn1d_waveform_stave_onehot            | ml                     |     1.44303  | 1.40224  |   1.48571 |              -0.0156803   |        763 |
|            59 | feature_gated_waveform_only            | ml                     |     1.45843  | 1.39908  |   1.53803 |              -0.000275481 |        763 |
|            59 | analytic_timewalk                      | traditional            |     1.45871  | 1.38149  |   1.5296  |               0           |        763 |
|            59 | mlp_waveform_amp_shape                 | ml                     |     1.522    | 1.46819  |   1.57076 |               0.0632879   |        763 |
|            59 | ridge_waveform_only                    | ml                     |     1.56092  | 1.50804  |   1.62426 |               0.102217    |        763 |
|            59 | mlp_waveform_only                      | ml                     |     1.58537  | 1.53265  |   1.63381 |               0.126666    |        763 |
|            59 | feature_gated_waveform_amp_shape       | ml                     |     1.70929  | 1.65589  |   1.759   |               0.250585    |        763 |
|            59 | cnn1d_waveform_amp_shape               | ml                     |     1.76043  | 1.69899  |   1.81258 |               0.301726    |        763 |
|            59 | ridge_waveform_amp_shape               | ml                     |     1.7865   | 1.71144  |   1.83967 |               0.327794    |        763 |
|            60 | hgb_waveform_amp_shape_stave           | ml                     |     1.10822  | 1.04701  |   1.17209 |              -0.23548     |        808 |
|            60 | hgb_waveform_stave_onehot              | ml                     |     1.13295  | 1.07996  |   1.20124 |              -0.210753    |        808 |
|            60 | mlp_waveform_amp_shape_stave           | ml                     |     1.16934  | 1.11158  |   1.23676 |              -0.174366    |        808 |
|            60 | feature_gated_waveform_stave_onehot    | ml                     |     1.18094  | 1.13854  |   1.23697 |              -0.16276     |        808 |
|            60 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.18895  | 1.12437  |   1.25474 |              -0.154758    |        808 |
|            60 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.19922  | 1.12309  |   1.27474 |              -0.14448     |        808 |
|            60 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.22195  | 1.1571   |   1.30791 |              -0.121756    |        808 |
|            60 | ridge_waveform_stave_onehot            | ml                     |     1.2225   | 1.15482  |   1.28747 |              -0.121201    |        808 |
|            60 | feature_gated_waveform_amp_shape_stave | ml                     |     1.25749  | 1.20514  |   1.33613 |              -0.0862163   |        808 |
|            60 | ridge_waveform_amp_shape_stave         | ml                     |     1.29511  | 1.23894  |   1.35301 |              -0.0485896   |        808 |
|            60 | mlp_waveform_stave_onehot              | ml                     |     1.30948  | 1.24798  |   1.37068 |              -0.0342269   |        808 |
|            60 | analytic_timewalk                      | traditional            |     1.3437   | 1.282    |   1.41118 |               0           |        808 |
|            60 | feature_gated_waveform_only            | ml                     |     1.34423  | 1.29296  |   1.41447 |               0.000526711 |        808 |
|            60 | cnn1d_waveform_only                    | ml                     |     1.34643  | 1.28847  |   1.4085  |               0.002725    |        808 |
|            60 | hgb_waveform_amp_shape                 | ml                     |     1.35705  | 1.30135  |   1.40709 |               0.013344    |        808 |
|            60 | cnn1d_waveform_stave_onehot            | ml                     |     1.38785  | 1.33503  |   1.46414 |               0.0441492   |        808 |
|            60 | mlp_waveform_only                      | ml                     |     1.40127  | 1.35282  |   1.45662 |               0.0575667   |        808 |
|            60 | hgb_waveform_only                      | ml                     |     1.40919  | 1.35566  |   1.44931 |               0.0654844   |        808 |
|            60 | ridge_waveform_only                    | ml                     |     1.4692   | 1.42168  |   1.51704 |               0.125495    |        808 |
|            60 | mlp_waveform_amp_shape                 | ml                     |     1.4937   | 1.44562  |   1.55132 |               0.149994    |        808 |
|            60 | feature_gated_waveform_amp_shape       | ml                     |     1.55143  | 1.48932  |   1.60979 |               0.207723    |        808 |
|            60 | cnn1d_waveform_amp_shape               | ml                     |     1.59514  | 1.51155  |   1.66044 |               0.251434    |        808 |
|            60 | ridge_waveform_amp_shape               | ml                     |     1.65598  | 1.58977  |   1.71619 |               0.312271    |        808 |
|            61 | hgb_waveform_amp_shape_stave           | ml                     |     1.08514  | 1.0441   |   1.13718 |              -1.04483     |        933 |
|            61 | hgb_waveform_stave_onehot              | ml                     |     1.08635  | 1.02621  |   1.14437 |              -1.04361     |        933 |
|            61 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.13113  | 1.0863   |   1.18351 |              -0.998832    |        933 |
|            61 | mlp_waveform_amp_shape_stave           | ml                     |     1.15308  | 1.10168  |   1.20509 |              -0.976886    |        933 |
|            61 | mlp_waveform_stave_onehot              | ml                     |     1.15916  | 1.10065  |   1.22356 |              -0.970803    |        933 |
|            61 | feature_gated_waveform_stave_onehot    | ml                     |     1.24159  | 1.18173  |   1.30992 |              -0.888376    |        933 |
|            61 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.25247  | 1.18538  |   1.31694 |              -0.877489    |        933 |
|            61 | ridge_waveform_stave_onehot            | ml                     |     1.25359  | 1.18526  |   1.32566 |              -0.876373    |        933 |
|            61 | cnn1d_waveform_stave_onehot            | ml                     |     1.25872  | 1.14926  |   1.30289 |              -0.87124     |        933 |
|            61 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.26533  | 1.18881  |   1.32521 |              -0.864639    |        933 |
|            61 | feature_gated_waveform_amp_shape_stave | ml                     |     1.27985  | 1.22016  |   1.34917 |              -0.850112    |        933 |
|            61 | ridge_waveform_amp_shape_stave         | ml                     |     1.30248  | 1.24127  |   1.3559  |              -0.827482    |        933 |
|            61 | hgb_waveform_amp_shape                 | ml                     |     1.65012  | 1.58933  |   1.71566 |              -0.479845    |        933 |
|            61 | hgb_waveform_only                      | ml                     |     1.72737  | 1.65967  |   1.80412 |              -0.402596    |        933 |
|            61 | mlp_waveform_amp_shape                 | ml                     |     1.89177  | 1.79585  |   1.97472 |              -0.238199    |        933 |
|            61 | ridge_waveform_only                    | ml                     |     2.127    | 2.04869  |   2.21611 |              -0.00296812  |        933 |
|            61 | cnn1d_waveform_only                    | ml                     |     2.12705  | 1.97062  |   2.20416 |              -0.00291381  |        933 |
|            61 | analytic_timewalk                      | traditional            |     2.12996  | 1.98719  |   2.21756 |               0           |        933 |
|            61 | mlp_waveform_only                      | ml                     |     2.13344  | 2.05046  |   2.24632 |               0.00347765  |        933 |
|            61 | feature_gated_waveform_only            | ml                     |     2.14928  | 2.02929  |   2.24669 |               0.0193169   |        933 |
|            61 | cnn1d_waveform_amp_shape               | ml                     |     2.17384  | 2.09418  |   2.26367 |               0.0438728   |        933 |
|            61 | feature_gated_waveform_amp_shape       | ml                     |     2.20415  | 2.10233  |   2.28759 |               0.0741834   |        933 |
|            61 | ridge_waveform_amp_shape               | ml                     |     2.2632   | 2.15482  |   2.37123 |               0.133232    |        933 |
|            62 | hgb_waveform_stave_onehot              | ml                     |     1.1325   | 1.06764  |   1.2281  |              -0.336507    |        807 |
|            62 | hgb_waveform_amp_shape_stave           | ml                     |     1.15212  | 1.09478  |   1.20215 |              -0.316882    |        807 |
|            62 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.16536  | 1.09815  |   1.22622 |              -0.303641    |        807 |
|            62 | mlp_waveform_amp_shape_stave           | ml                     |     1.17516  | 1.11446  |   1.22752 |              -0.293844    |        807 |
|            62 | feature_gated_waveform_amp_shape_stave | ml                     |     1.18695  | 1.11935  |   1.24523 |              -0.282056    |        807 |
|            62 | feature_gated_waveform_stave_onehot    | ml                     |     1.23269  | 1.18221  |   1.29494 |              -0.236319    |        807 |
|            62 | mlp_waveform_stave_onehot              | ml                     |     1.26442  | 1.18091  |   1.3213  |              -0.204581    |        807 |
|            62 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.29384  | 1.2267   |   1.37392 |              -0.17517     |        807 |
|            62 | ridge_waveform_stave_onehot            | ml                     |     1.29546  | 1.23584  |   1.35858 |              -0.17355     |        807 |
|            62 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.30879  | 1.23631  |   1.37431 |              -0.160211    |        807 |
|            62 | ridge_waveform_amp_shape_stave         | ml                     |     1.3687   | 1.30105  |   1.41062 |              -0.100309    |        807 |
|            62 | cnn1d_waveform_stave_onehot            | ml                     |     1.37859  | 1.31116  |   1.43558 |              -0.0904156   |        807 |
|            62 | hgb_waveform_amp_shape                 | ml                     |     1.4373   | 1.38628  |   1.48463 |              -0.0317066   |        807 |
|            62 | feature_gated_waveform_only            | ml                     |     1.4527   | 1.3916   |   1.51038 |              -0.0163094   |        807 |
|            62 | cnn1d_waveform_only                    | ml                     |     1.46316  | 1.39737  |   1.52504 |              -0.00584337  |        807 |
|            62 | mlp_waveform_only                      | ml                     |     1.46388  | 1.40635  |   1.52307 |              -0.00512823  |        807 |
|            62 | analytic_timewalk                      | traditional            |     1.469    | 1.40836  |   1.53088 |               0           |        807 |
|            62 | hgb_waveform_only                      | ml                     |     1.49115  | 1.43597  |   1.54323 |               0.0221421   |        807 |
|            62 | ridge_waveform_only                    | ml                     |     1.5674   | 1.49742  |   1.63669 |               0.0983966   |        807 |
|            62 | mlp_waveform_amp_shape                 | ml                     |     1.60868  | 1.55271  |   1.66796 |               0.139677    |        807 |
|            62 | ridge_waveform_amp_shape               | ml                     |     1.74228  | 1.66808  |   1.80725 |               0.273278    |        807 |
|            62 | feature_gated_waveform_amp_shape       | ml                     |     1.74481  | 1.69203  |   1.80616 |               0.275802    |        807 |
|            62 | cnn1d_waveform_amp_shape               | ml                     |     1.76769  | 1.70807  |   1.81242 |               0.298688    |        807 |
|            63 | mlp_waveform_stave_onehot              | ml                     |     1.12085  | 1.02807  |   1.20713 |              -0.270471    |        370 |
|            63 | hgb_waveform_amp_shape_stave           | ml                     |     1.21011  | 1.11738  |   1.30102 |              -0.181211    |        370 |
|            63 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.21167  | 1.11829  |   1.29794 |              -0.179655    |        370 |
|            63 | hgb_waveform_stave_onehot              | ml                     |     1.22154  | 1.13046  |   1.31208 |              -0.169782    |        370 |
|            63 | feature_gated_waveform_amp_shape_stave | ml                     |     1.26299  | 1.15639  |   1.37818 |              -0.128327    |        370 |
|            63 | mlp_waveform_amp_shape_stave           | ml                     |     1.28833  | 1.16958  |   1.37433 |              -0.102987    |        370 |
|            63 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.33211  | 1.23086  |   1.45221 |              -0.0592122   |        370 |
|            63 | feature_gated_waveform_stave_onehot    | ml                     |     1.33423  | 1.27338  |   1.43613 |              -0.0570941   |        370 |
|            63 | ridge_waveform_stave_onehot            | ml                     |     1.35021  | 1.26526  |   1.43585 |              -0.04111     |        370 |
|            63 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.3529   | 1.23845  |   1.4252  |              -0.0384231   |        370 |
|            63 | ridge_waveform_amp_shape_stave         | ml                     |     1.39034  | 1.27951  |   1.47095 |              -0.000979694 |        370 |
|            63 | analytic_timewalk                      | traditional            |     1.39132  | 1.30359  |   1.46925 |               0           |        370 |
|            63 | cnn1d_waveform_only                    | ml                     |     1.39192  | 1.30489  |   1.47255 |               0.000594914 |        370 |
|            63 | feature_gated_waveform_only            | ml                     |     1.39687  | 1.30822  |   1.46859 |               0.00554836  |        370 |
|            63 | hgb_waveform_amp_shape                 | ml                     |     1.44978  | 1.37923  |   1.55278 |               0.0584591   |        370 |
|            63 | hgb_waveform_only                      | ml                     |     1.4716   | 1.398    |   1.5576  |               0.0802745   |        370 |
|            63 | ridge_waveform_only                    | ml                     |     1.47692  | 1.40862  |   1.55408 |               0.085603    |        370 |
|            63 | cnn1d_waveform_stave_onehot            | ml                     |     1.48016  | 1.36504  |   1.53984 |               0.0888377   |        370 |
|            63 | mlp_waveform_only                      | ml                     |     1.49002  | 1.40981  |   1.57007 |               0.0987028   |        370 |
|            63 | mlp_waveform_amp_shape                 | ml                     |     1.58011  | 1.50008  |   1.6445  |               0.18879     |        370 |
|            63 | feature_gated_waveform_amp_shape       | ml                     |     1.60537  | 1.51686  |   1.68277 |               0.214047    |        370 |
|            63 | cnn1d_waveform_amp_shape               | ml                     |     1.62315  | 1.5486   |   1.71662 |               0.231826    |        370 |
|            63 | ridge_waveform_amp_shape               | ml                     |     1.72638  | 1.6122   |   1.81819 |               0.33506     |        370 |
|            65 | mlp_waveform_stave_onehot              | ml                     |     1.10884  | 0.750562 |   1.39406 |              -0.385798    |         66 |
|            65 | hgb_waveform_amp_shape_stave           | ml                     |     1.17239  | 0.974806 |   1.45912 |              -0.322249    |         66 |
|            65 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.2868   | 1.05946  |   1.53734 |              -0.207836    |         66 |
|            65 | mlp_waveform_amp_shape_stave           | ml                     |     1.29781  | 1.03793  |   1.57009 |              -0.196831    |         66 |
|            65 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.31856  | 1.06876  |   1.59192 |              -0.176083    |         66 |
|            65 | feature_gated_waveform_stave_onehot    | ml                     |     1.34877  | 1.23299  |   1.52165 |              -0.145873    |         66 |
|            65 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.38255  | 1.15809  |   1.56986 |              -0.112091    |         66 |
|            65 | ridge_waveform_stave_onehot            | ml                     |     1.39346  | 1.13449  |   1.65763 |              -0.101175    |         66 |
|            65 | hgb_waveform_only                      | ml                     |     1.41733  | 1.28073  |   1.55674 |              -0.0773099   |         66 |
|            65 | mlp_waveform_only                      | ml                     |     1.42186  | 1.34845  |   1.68044 |              -0.0727829   |         66 |
|            65 | feature_gated_waveform_only            | ml                     |     1.42347  | 1.32018  |   1.66506 |              -0.0711674   |         66 |
|            65 | hgb_waveform_stave_onehot              | ml                     |     1.42511  | 1.09218  |   1.60883 |              -0.0695329   |         66 |
|            65 | cnn1d_waveform_stave_onehot            | ml                     |     1.42564  | 1.20613  |   1.68186 |              -0.0689977   |         66 |
|            65 | hgb_waveform_amp_shape                 | ml                     |     1.44644  | 1.18231  |   1.62287 |              -0.0481977   |         66 |
|            65 | cnn1d_waveform_only                    | ml                     |     1.45999  | 1.31424  |   1.65905 |              -0.034654    |         66 |
|            65 | ridge_waveform_amp_shape_stave         | ml                     |     1.46402  | 1.21893  |   1.66976 |              -0.0306195   |         66 |
|            65 | feature_gated_waveform_amp_shape_stave | ml                     |     1.47618  | 1.25998  |   1.68047 |              -0.0184581   |         66 |
|            65 | analytic_timewalk                      | traditional            |     1.49464  | 1.32251  |   1.66333 |               0           |         66 |
|            65 | ridge_waveform_only                    | ml                     |     1.58382  | 1.42406  |   1.76149 |               0.0891839   |         66 |
|            65 | ridge_waveform_amp_shape               | ml                     |     1.62406  | 1.41951  |   1.90413 |               0.129422    |         66 |
|            65 | cnn1d_waveform_amp_shape               | ml                     |     1.63185  | 1.42733  |   1.88217 |               0.13721     |         66 |
|            65 | feature_gated_waveform_amp_shape       | ml                     |     1.66483  | 1.45216  |   1.90092 |               0.170185    |         66 |
|            65 | mlp_waveform_amp_shape                 | ml                     |     1.68615  | 1.433    |   1.88525 |               0.191511    |         66 |

## Leakage and Systematics

|   heldout_run | check                                                        |       value | pass   |
|--------------:|:-------------------------------------------------------------|------------:|:-------|
|            58 | train_heldout_run_overlap                                    |  0          | True   |
|            58 | train_heldout_event_id_overlap                               |  0          | True   |
|            58 | feature_audit                                                |  0          | True   |
|            58 | shuffled_target_worse:ridge_waveform_only                    | -0.21828    | False  |
|            58 | shuffled_target_worse:hgb_waveform_only                      | -0.476786   | False  |
|            58 | shuffled_target_worse:mlp_waveform_only                      | -0.0935719  | False  |
|            58 | shuffled_target_worse:cnn1d_waveform_only                    |  0.0119723  | True   |
|            58 | shuffled_target_worse:feature_gated_waveform_only            | -0.00185922 | False  |
|            58 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.146936   | True   |
|            58 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.194846   | True   |
|            58 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.035729   | True   |
|            58 | shuffled_target_worse:cnn1d_waveform_stave_onehot            | -0.153389   | False  |
|            58 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.117735   | True   |
|            58 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.460173   | False  |
|            58 | shuffled_target_worse:hgb_waveform_amp_shape                 | -0.418472   | False  |
|            58 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.401093   | False  |
|            58 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.30349    | False  |
|            58 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.372158   | False  |
|            58 | shuffled_target_worse:ridge_waveform_amp_shape_stave         |  0.0156974  | True   |
|            58 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.137904   | True   |
|            58 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.101241   | True   |
|            58 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.0534562  | True   |
|            58 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.249932   | True   |
|            59 | train_heldout_run_overlap                                    |  0          | True   |
|            59 | train_heldout_event_id_overlap                               |  0          | True   |
|            59 | feature_audit                                                |  0          | True   |
|            59 | shuffled_target_worse:ridge_waveform_only                    | -0.0902672  | False  |
|            59 | shuffled_target_worse:hgb_waveform_only                      |  0.141139   | True   |
|            59 | shuffled_target_worse:mlp_waveform_only                      | -0.130775   | False  |
|            59 | shuffled_target_worse:cnn1d_waveform_only                    |  0.0233776  | True   |
|            59 | shuffled_target_worse:feature_gated_waveform_only            |  0.00043752 | True   |
|            59 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.126495   | True   |
|            59 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.412944   | True   |
|            59 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.186257   | True   |
|            59 | shuffled_target_worse:cnn1d_waveform_stave_onehot            |  0.0397799  | True   |
|            59 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.208925   | True   |
|            59 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.339837   | False  |
|            59 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.13778    | True   |
|            59 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.0565002  | False  |
|            59 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.350937   | False  |
|            59 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.249927   | False  |
|            59 | shuffled_target_worse:ridge_waveform_amp_shape_stave         |  0.141976   | True   |
|            59 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.415432   | True   |
|            59 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.352982   | True   |
|            59 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.109107   | True   |
|            59 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.133262   | True   |
|            60 | train_heldout_run_overlap                                    |  0          | True   |
|            60 | train_heldout_event_id_overlap                               |  0          | True   |
|            60 | feature_audit                                                |  0          | True   |
|            60 | shuffled_target_worse:ridge_waveform_only                    | -0.140794   | False  |
|            60 | shuffled_target_worse:hgb_waveform_only                      |  0.0173576  | True   |
|            60 | shuffled_target_worse:mlp_waveform_only                      | -0.0475404  | False  |
|            60 | shuffled_target_worse:cnn1d_waveform_only                    | -0.0120489  | False  |
|            60 | shuffled_target_worse:feature_gated_waveform_only            |  0.00275334 | True   |
|            60 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.0904026  | True   |
|            60 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.278741   | True   |
|            60 | shuffled_target_worse:mlp_waveform_stave_onehot              | -0.00327349 | False  |
|            60 | shuffled_target_worse:cnn1d_waveform_stave_onehot            | -0.065659   | False  |
|            60 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.17737    | True   |
|            60 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.330593   | False  |
|            60 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.0778482  | True   |
|            60 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.142509   | False  |
|            60 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.268363   | False  |
|            60 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.200737   | False  |
|            60 | shuffled_target_worse:ridge_waveform_amp_shape_stave         | -0.00129381 | False  |
|            60 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.368047   | True   |
|            60 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.204947   | True   |
|            60 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.150418   | True   |
|            60 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.0799988  | True   |
|            61 | train_heldout_run_overlap                                    |  0          | True   |
|            61 | train_heldout_event_id_overlap                               |  0          | True   |
|            61 | feature_audit                                                |  0          | True   |
|            61 | shuffled_target_worse:ridge_waveform_only                    |  0.00329033 | True   |
|            61 | shuffled_target_worse:hgb_waveform_only                      |  0.451514   | True   |
|            61 | shuffled_target_worse:mlp_waveform_only                      |  0.00184882 | True   |
|            61 | shuffled_target_worse:cnn1d_waveform_only                    |  0.0020737  | True   |
|            61 | shuffled_target_worse:feature_gated_waveform_only            | -0.0204242  | False  |
|            61 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.862312   | True   |
|            61 | shuffled_target_worse:hgb_waveform_stave_onehot              |  1.07324    | True   |
|            61 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.986689   | True   |
|            61 | shuffled_target_worse:cnn1d_waveform_stave_onehot            |  0.764255   | True   |
|            61 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.882006   | True   |
|            61 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.185297   | False  |
|            61 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.547894   | True   |
|            61 | shuffled_target_worse:mlp_waveform_amp_shape                 |  0.220564   | True   |
|            61 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.0394264  | False  |
|            61 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.111608   | False  |
|            61 | shuffled_target_worse:ridge_waveform_amp_shape_stave         |  0.815424   | True   |
|            61 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  1.05671    | True   |
|            61 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  1.01864    | True   |
|            61 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.842337   | True   |
|            61 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.868163   | True   |
|            62 | train_heldout_run_overlap                                    |  0          | True   |
|            62 | train_heldout_event_id_overlap                               |  0          | True   |
|            62 | feature_audit                                                |  0          | True   |
|            62 | shuffled_target_worse:ridge_waveform_only                    | -0.10329    | False  |
|            62 | shuffled_target_worse:hgb_waveform_only                      |  0.058122   | True   |
|            62 | shuffled_target_worse:mlp_waveform_only                      | -0.00979126 | False  |
|            62 | shuffled_target_worse:cnn1d_waveform_only                    |  0.0105662  | True   |
|            62 | shuffled_target_worse:feature_gated_waveform_only            |  0.0228998  | True   |
|            62 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.182201   | True   |
|            62 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.421537   | True   |
|            62 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.175066   | True   |
|            62 | shuffled_target_worse:cnn1d_waveform_stave_onehot            |  0.176897   | True   |
|            62 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.26297    | True   |
|            62 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.246129   | False  |
|            62 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.142486   | True   |
|            62 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.132794   | False  |
|            62 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.284577   | False  |
|            62 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.289637   | False  |
|            62 | shuffled_target_worse:ridge_waveform_amp_shape_stave         |  0.108262   | True   |
|            62 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.393716   | True   |
|            62 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.271927   | True   |
|            62 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.157139   | True   |
|            62 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.255268   | True   |
|            63 | train_heldout_run_overlap                                    |  0          | True   |
|            63 | train_heldout_event_id_overlap                               |  0          | True   |
|            63 | feature_audit                                                |  0          | True   |
|            63 | shuffled_target_worse:ridge_waveform_only                    | -0.0998102  | False  |
|            63 | shuffled_target_worse:hgb_waveform_only                      | -0.0728787  | False  |

Main caveats:

- Sample-II run 65 has low statistics; the pooled CI therefore uses runs as the outer bootstrap unit.
- The residual target is internally defined from same-event downstream staves, so all claims are relative timing-closure claims, not absolute beam-time truth.
- Stave-aware variants intentionally include detector identity. They are useful predictors but remain vulnerable to detector-condition leakage; the stave-offset guardrail quantifies the part explainable without waveform samples.
- Histogram-gradient boosting is a strong nonlinear tabular learner but is not monotonicity constrained here.

## Verdict

Winner in `result.json`: `hgb_waveform_amp_shape_stave` with pooled `sigma68 = 1.109 ns` and CI `[1.076, 1.165] ns`.

Interpretation: The P03e waveform_amp_shape_stave gain survives beyond run 65 in the leave-one-run repetition: stave-aware amplitude/shape models beat their stave-blind analogues in most held-out runs and in the run-block pooled estimate. 54 shuffled-target checks beat their nominal model and are flagged as stability caveats.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03g_1781097097_1022_02db7832_pedestal_residualized_samples.py --config configs/p03g_1781097097_1022_02db7832_pedestal_residualized_samples.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `leakage_checks.csv`, `model_diagnostics.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
