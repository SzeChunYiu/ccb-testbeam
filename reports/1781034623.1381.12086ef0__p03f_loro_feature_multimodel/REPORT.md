# P03f: leave-one-run P03e feature ablation with multimodel controls

- **Ticket:** `1781034623.1381.12086ef0`
- **Worker:** `testbeam-laptop-4`
- **Claimed study:** leave-one-heldout-run repetition of P03e feature ablations with multimodel controls
- **Input:** raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **P03e variants:** `['waveform_only', 'waveform_stave_onehot', 'waveform_amp_shape', 'waveform_amp_shape_stave']`

## Question and preregistered estimand

The ticket asks whether the P03e stave-aware waveform/amplitude/shape gain seen on run 65 survives when each Sample-II analysis run is held out in turn.  The estimand is the B4/B6/B8 event-paired timing width after a fold-local S03a analytic timewalk correction:

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

## Pooled Benchmark

| method                                 | family      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:---------------------------------------|:------------|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------:|
| hgb_waveform_amp_shape_stave           | ml          |      1.10742 |  1.07531 |   1.15879 |                -0.443675  |     -0.84233   |     -0.241182   |              11460 |
| hgb_waveform_stave_onehot              | ml          |      1.12607 |  1.08906 |   1.18473 |                -0.425027  |     -0.829105  |     -0.205108   |              11460 |
| mlp_waveform_amp_shape_stave           | ml          |      1.1621  |  1.1062  |   1.23525 |                -0.388989  |     -0.818401  |     -0.166956   |              11460 |
| mlp_waveform_stave_onehot              | ml          |      1.22545 |  1.18    |   1.27476 |                -0.325645  |     -0.734754  |     -0.121596   |              11460 |
| ridge_waveform_stave_onehot            | ml          |      1.24442 |  1.17293 |   1.32178 |                -0.306677  |     -0.738723  |     -0.0892062  |              11460 |
| feature_gated_waveform_amp_shape_stave | ml          |      1.25349 |  1.21334 |   1.30812 |                -0.297601  |     -0.6712    |     -0.094782   |              11460 |
| feature_gated_waveform_stave_onehot    | ml          |      1.25505 |  1.21209 |   1.32063 |                -0.29604   |     -0.669682  |     -0.105388   |              11460 |
| cnn1d_waveform_amp_shape_stave         | ml          |      1.26387 |  1.21204 |   1.34277 |                -0.287227  |     -0.685886  |     -0.0859247  |              11460 |
| ridge_waveform_amp_shape_stave         | ml          |      1.32793 |  1.2811  |   1.38085 |                -0.223158  |     -0.636668  |     -0.00608294 |              11460 |
| cnn1d_waveform_stave_onehot            | ml          |      1.37531 |  1.33189 |   1.44732 |                -0.175785  |     -0.597929  |      0.0399627  |              11460 |
| hgb_waveform_amp_shape                 | ml          |      1.47412 |  1.38648 |   1.58286 |                -0.0769733 |     -0.362251  |      0.0474612  |              11460 |
| hgb_waveform_only                      | ml          |      1.51056 |  1.42749 |   1.65844 |                -0.0405306 |     -0.255874  |      0.0892726  |              11460 |
| cnn1d_waveform_only                    | ml          |      1.54673 |  1.36302 |   1.92491 |                -0.0043667 |     -0.0581138 |      0.0554829  |              11460 |
| analytic_timewalk                      | traditional |      1.55109 |  1.36375 |   1.93624 |                 0         |      0         |      0          |              11460 |
| feature_gated_waveform_only            | ml          |      1.56327 |  1.37597 |   1.94804 |                 0.0121826 |     -0.0519692 |      0.0711968  |              11460 |
| mlp_waveform_only                      | ml          |      1.60335 |  1.43515 |   1.95549 |                 0.0522619 |     -0.0138006 |      0.115321   |              11460 |
| mlp_waveform_amp_shape                 | ml          |      1.60898 |  1.46352 |   1.84024 |                 0.0578863 |     -0.0891209 |      0.146204   |              11460 |
| ridge_waveform_only                    | ml          |      1.65023 |  1.47233 |   2.00129 |                 0.0991389 |      0.0243855 |      0.148342   |              11460 |
| feature_gated_waveform_amp_shape       | ml          |      1.74987 |  1.59775 |   1.99584 |                 0.198782  |      0.0438778 |      0.278705   |              11460 |
| cnn1d_waveform_amp_shape               | ml          |      1.77387 |  1.64136 |   1.99026 |                 0.222778  |      0.0416658 |      0.321191   |              11460 |
| ridge_waveform_amp_shape               | ml          |      1.7817  |  1.63655 |   2.00948 |                 0.230609  |      0.0697784 |      0.296561   |              11460 |

## Feature-Variant Summary

| variant                  | best_method                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_pair_residuals |
|:-------------------------|:-----------------------------|-------------:|---------:|----------:|--------------------------:|-------------------:|
| waveform_amp_shape_stave | hgb_waveform_amp_shape_stave |      1.10742 |  1.07531 |   1.15879 |                -0.443675  |              11460 |
| waveform_stave_onehot    | hgb_waveform_stave_onehot    |      1.12607 |  1.08906 |   1.18473 |                -0.425027  |              11460 |
| waveform_amp_shape       | hgb_waveform_amp_shape       |      1.47412 |  1.38648 |   1.58286 |                -0.0769733 |              11460 |
| waveform_only            | hgb_waveform_only            |      1.51056 |  1.42749 |   1.65844 |                -0.0405306 |              11460 |

## Controls

| method                                          | family                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:------------------------------------------------|:------------------------|-------------:|---------:|----------:|--------------------------:|
| hgb_stave_offset_guardrail                      | stave_offset_guardrail  |      1.15156 |  1.11007 |   1.2069  |               -0.39953    |
| ridge_stave_offset_guardrail                    | stave_offset_guardrail  |      1.26259 |  1.2021  |   1.32625 |               -0.288498   |
| feature_gated_waveform_amp_shape_stave_shuffled | shuffled_target_control |      1.54435 |  1.3506  |   1.9288  |               -0.00674197 |
| feature_gated_waveform_only_shuffled            | shuffled_target_control |      1.54732 |  1.36297 |   1.94127 |               -0.00377288 |
| cnn1d_waveform_amp_shape_stave_shuffled         | shuffled_target_control |      1.54778 |  1.36329 |   1.91318 |               -0.00331227 |
| cnn1d_waveform_only_shuffled                    | shuffled_target_control |      1.54997 |  1.36368 |   1.93915 |               -0.00112298 |
| mlp_waveform_only_shuffled                      | shuffled_target_control |      1.55315 |  1.37282 |   1.93735 |                0.00206205 |
| ridge_waveform_amp_shape_stave_shuffled         | shuffled_target_control |      1.55363 |  1.35647 |   1.91792 |                0.00253431 |
| feature_gated_waveform_stave_onehot_shuffled    | shuffled_target_control |      1.55865 |  1.37159 |   1.92614 |                0.00755416 |
| feature_gated_waveform_amp_shape_shuffled       | shuffled_target_control |      1.56075 |  1.37982 |   1.92601 |                0.00966306 |
| mlp_waveform_amp_shape_shuffled                 | shuffled_target_control |      1.56313 |  1.36573 |   1.92465 |                0.0120376  |
| cnn1d_waveform_amp_shape_shuffled               | shuffled_target_control |      1.56605 |  1.36592 |   1.92956 |                0.0149546  |
| ridge_waveform_only_shuffled                    | shuffled_target_control |      1.56768 |  1.37162 |   1.94174 |                0.016586   |
| ridge_waveform_stave_onehot_shuffled            | shuffled_target_control |      1.57204 |  1.36253 |   1.92036 |                0.0209449  |
| cnn1d_waveform_stave_onehot_shuffled            | shuffled_target_control |      1.57307 |  1.37163 |   1.85903 |                0.0219743  |
| mlp_waveform_stave_onehot_shuffled              | shuffled_target_control |      1.57368 |  1.36937 |   1.9474  |                0.0225836  |
| mlp_waveform_amp_shape_stave_shuffled           | shuffled_target_control |      1.57645 |  1.38793 |   1.9488  |                0.0253623  |
| ridge_waveform_amp_shape_shuffled               | shuffled_target_control |      1.58633 |  1.35076 |   1.93089 |                0.0352424  |
| hgb_waveform_stave_onehot_shuffled              | shuffled_target_control |      1.61933 |  1.41745 |   1.94904 |                0.0682383  |
| hgb_waveform_amp_shape_stave_shuffled           | shuffled_target_control |      1.63164 |  1.42769 |   1.94109 |                0.0805464  |
| hgb_waveform_only_shuffled                      | shuffled_target_control |      1.63263 |  1.43499 |   1.92655 |                0.0815428  |
| hgb_waveform_amp_shape_shuffled                 | shuffled_target_control |      1.643   |  1.43782 |   1.98013 |                0.0919035  |

Shuffled-target rows are interpreted as stability/leakage warnings, not as positive evidence. A shuffled control that matches or beats its nominal counterpart means that model/variant combination is not causally interpretable.

## Held-Out Runs

|   heldout_run | method                                 | family                 |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_events |
|--------------:|:---------------------------------------|:-----------------------|-------------:|---------:|----------:|--------------------------:|-----------:|
|            58 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     0.999863 | 0.878537 |   1.21483 |              -0.18762     |         73 |
|            58 | mlp_waveform_amp_shape_stave           | ml                     |     1.02777  | 0.804712 |   1.26245 |              -0.15971     |         73 |
|            58 | ridge_waveform_stave_onehot            | ml                     |     1.03263  | 0.950067 |   1.18897 |              -0.15485     |         73 |
|            58 | hgb_waveform_amp_shape_stave           | ml                     |     1.03753  | 0.84649  |   1.25829 |              -0.149956    |         73 |
|            58 | hgb_waveform_stave_onehot              | ml                     |     1.09239  | 0.922383 |   1.26416 |              -0.0950926   |         73 |
|            58 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.09812  | 0.947827 |   1.31561 |              -0.0893612   |         73 |
|            58 | ridge_waveform_amp_shape_stave         | ml                     |     1.17078  | 1.00291  |   1.38106 |              -0.0167017   |         73 |
|            58 | feature_gated_waveform_stave_onehot    | ml                     |     1.17794  | 1.05367  |   1.24124 |              -0.00954585  |         73 |
|            58 | analytic_timewalk                      | traditional            |     1.18748  | 1.13423  |   1.41572 |               0           |         73 |
|            58 | feature_gated_waveform_amp_shape_stave | ml                     |     1.18944  | 1.02747  |   1.39228 |               0.00195166  |         73 |
|            58 | feature_gated_waveform_only            | ml                     |     1.18964  | 1.13563  |   1.4135  |               0.00215433  |         73 |
|            58 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.19107  | 1.00672  |   1.33434 |               0.00358874  |         73 |
|            58 | cnn1d_waveform_only                    | ml                     |     1.19273  | 1.14316  |   1.41854 |               0.00524554  |         73 |
|            58 | mlp_waveform_only                      | ml                     |     1.25263  | 1.16993  |   1.45602 |               0.0651513   |         73 |
|            58 | cnn1d_waveform_stave_onehot            | ml                     |     1.30448  | 1.23496  |   1.38617 |               0.117001    |         73 |
|            58 | mlp_waveform_stave_onehot              | ml                     |     1.35754  | 1.18881  |   1.49233 |               0.170052    |         73 |
|            58 | ridge_waveform_only                    | ml                     |     1.38733  | 1.20471  |   1.60734 |               0.199849    |         73 |
|            58 | mlp_waveform_amp_shape                 | ml                     |     1.47765  | 1.28955  |   1.62659 |               0.290162    |         73 |
|            58 | feature_gated_waveform_amp_shape       | ml                     |     1.5305   | 1.35388  |   1.78611 |               0.34302     |         73 |
|            58 | cnn1d_waveform_amp_shape               | ml                     |     1.5439   | 1.4191   |   1.80491 |               0.356417    |         73 |
|            58 | hgb_waveform_only                      | ml                     |     1.61423  | 1.41561  |   1.85291 |               0.426751    |         73 |
|            58 | ridge_waveform_amp_shape               | ml                     |     1.62064  | 1.37631  |   1.86635 |               0.433157    |         73 |
|            58 | hgb_waveform_amp_shape                 | ml                     |     1.64581  | 1.49541  |   1.83026 |               0.458325    |         73 |
|            59 | hgb_waveform_amp_shape_stave           | ml                     |     1.0669   | 1.01543  |   1.12576 |              -0.391812    |        763 |
|            59 | hgb_waveform_stave_onehot              | ml                     |     1.13466  | 1.06646  |   1.20474 |              -0.324052    |        763 |
|            59 | mlp_waveform_amp_shape_stave           | ml                     |     1.14195  | 1.07741  |   1.19936 |              -0.316759    |        763 |
|            59 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.15319  | 1.08616  |   1.21954 |              -0.305518    |        763 |
|            59 | mlp_waveform_stave_onehot              | ml                     |     1.26091  | 1.21265  |   1.33683 |              -0.1978      |        763 |
|            59 | feature_gated_waveform_stave_onehot    | ml                     |     1.28586  | 1.23655  |   1.33578 |              -0.172851    |        763 |
|            59 | ridge_waveform_stave_onehot            | ml                     |     1.30673  | 1.25294  |   1.37166 |              -0.151983    |        763 |
|            59 | ridge_waveform_amp_shape_stave         | ml                     |     1.31335  | 1.25149  |   1.36557 |              -0.145362    |        763 |
|            59 | feature_gated_waveform_amp_shape_stave | ml                     |     1.31387  | 1.22968  |   1.36436 |              -0.144839    |        763 |
|            59 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.32783  | 1.27368  |   1.39175 |              -0.130882    |        763 |
|            59 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.33737  | 1.27238  |   1.39093 |              -0.12134     |        763 |
|            59 | hgb_waveform_amp_shape                 | ml                     |     1.40764  | 1.36374  |   1.45336 |              -0.0510698   |        763 |
|            59 | hgb_waveform_only                      | ml                     |     1.418    | 1.38337  |   1.4642  |              -0.0407103   |        763 |
|            59 | cnn1d_waveform_only                    | ml                     |     1.43249  | 1.35022  |   1.50925 |              -0.026215    |        763 |
|            59 | cnn1d_waveform_stave_onehot            | ml                     |     1.43255  | 1.39307  |   1.47604 |              -0.0261541   |        763 |
|            59 | feature_gated_waveform_only            | ml                     |     1.44218  | 1.37194  |   1.516   |              -0.0165311   |        763 |
|            59 | analytic_timewalk                      | traditional            |     1.45871  | 1.38149  |   1.5296  |               0           |        763 |
|            59 | mlp_waveform_amp_shape                 | ml                     |     1.51758  | 1.46534  |   1.57932 |               0.0588762   |        763 |
|            59 | ridge_waveform_only                    | ml                     |     1.5569   | 1.49981  |   1.61047 |               0.0981904   |        763 |
|            59 | mlp_waveform_only                      | ml                     |     1.5575   | 1.49338  |   1.62121 |               0.0987871   |        763 |
|            59 | ridge_waveform_amp_shape               | ml                     |     1.68444  | 1.61376  |   1.75426 |               0.225731    |        763 |
|            59 | feature_gated_waveform_amp_shape       | ml                     |     1.70141  | 1.64579  |   1.75901 |               0.242701    |        763 |
|            59 | cnn1d_waveform_amp_shape               | ml                     |     1.76884  | 1.70183  |   1.81589 |               0.310136    |        763 |
|            60 | hgb_waveform_amp_shape_stave           | ml                     |     1.09797  | 1.044    |   1.18073 |              -0.245737    |        808 |
|            60 | hgb_waveform_stave_onehot              | ml                     |     1.14299  | 1.07233  |   1.21688 |              -0.200719    |        808 |
|            60 | mlp_waveform_amp_shape_stave           | ml                     |     1.17195  | 1.12029  |   1.22383 |              -0.171754    |        808 |
|            60 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.1909   | 1.1256   |   1.25506 |              -0.152808    |        808 |
|            60 | mlp_waveform_stave_onehot              | ml                     |     1.19249  | 1.13173  |   1.26035 |              -0.15121     |        808 |
|            60 | feature_gated_waveform_stave_onehot    | ml                     |     1.19503  | 1.12745  |   1.25521 |              -0.14867     |        808 |
|            60 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.19922  | 1.12309  |   1.27474 |              -0.14448     |        808 |
|            60 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.22195  | 1.1571   |   1.30791 |              -0.121756    |        808 |
|            60 | ridge_waveform_stave_onehot            | ml                     |     1.22431  | 1.14548  |   1.2884  |              -0.119392    |        808 |
|            60 | feature_gated_waveform_amp_shape_stave | ml                     |     1.24315  | 1.18054  |   1.3139  |              -0.100555    |        808 |
|            60 | cnn1d_waveform_only                    | ml                     |     1.34361  | 1.29006  |   1.41168 |              -9.26874e-05 |        808 |
|            60 | analytic_timewalk                      | traditional            |     1.3437   | 1.282    |   1.41118 |               0           |        808 |
|            60 | ridge_waveform_amp_shape_stave         | ml                     |     1.35441  | 1.3062   |   1.41636 |               0.0107053   |        808 |
|            60 | feature_gated_waveform_only            | ml                     |     1.35926  | 1.31054  |   1.42852 |               0.0155583   |        808 |
|            60 | hgb_waveform_amp_shape                 | ml                     |     1.35943  | 1.30959  |   1.40898 |               0.0157207   |        808 |
|            60 | cnn1d_waveform_stave_onehot            | ml                     |     1.37529  | 1.32477  |   1.45149 |               0.0315847   |        808 |
|            60 | mlp_waveform_only                      | ml                     |     1.39945  | 1.35105  |   1.45524 |               0.0557407   |        808 |
|            60 | mlp_waveform_amp_shape                 | ml                     |     1.42786  | 1.37563  |   1.47533 |               0.084153    |        808 |
|            60 | hgb_waveform_only                      | ml                     |     1.43701  | 1.39541  |   1.47376 |               0.0933029   |        808 |
|            60 | ridge_waveform_only                    | ml                     |     1.45244  | 1.4067   |   1.4974  |               0.10874     |        808 |
|            60 | feature_gated_waveform_amp_shape       | ml                     |     1.55467  | 1.49166  |   1.61094 |               0.210961    |        808 |
|            60 | cnn1d_waveform_amp_shape               | ml                     |     1.59538  | 1.51777  |   1.66554 |               0.251672    |        808 |
|            60 | ridge_waveform_amp_shape               | ml                     |     1.62455  | 1.56197  |   1.68687 |               0.280848    |        808 |
|            61 | hgb_waveform_amp_shape_stave           | ml                     |     1.08935  | 1.04306  |   1.13818 |              -1.04061     |        933 |
|            61 | hgb_waveform_stave_onehot              | ml                     |     1.10532  | 1.05889  |   1.16755 |              -1.02465     |        933 |
|            61 | mlp_waveform_amp_shape_stave           | ml                     |     1.11614  | 1.05175  |   1.1667  |              -1.01383     |        933 |
|            61 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.13113  | 1.0863   |   1.18351 |              -0.998832    |        933 |
|            61 | mlp_waveform_stave_onehot              | ml                     |     1.17324  | 1.10424  |   1.232   |              -0.956722    |        933 |
|            61 | ridge_waveform_stave_onehot            | ml                     |     1.23675  | 1.17783  |   1.30884 |              -0.893219    |        933 |
|            61 | feature_gated_waveform_stave_onehot    | ml                     |     1.25413  | 1.16765  |   1.34221 |              -0.875832    |        933 |
|            61 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.26475  | 1.19696  |   1.32162 |              -0.865216    |        933 |
|            61 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.26533  | 1.18881  |   1.32521 |              -0.864639    |        933 |
|            61 | feature_gated_waveform_amp_shape_stave | ml                     |     1.2753   | 1.21219  |   1.33644 |              -0.85466     |        933 |
|            61 | ridge_waveform_amp_shape_stave         | ml                     |     1.28457  | 1.22062  |   1.35256 |              -0.845393    |        933 |
|            61 | cnn1d_waveform_stave_onehot            | ml                     |     1.2889   | 1.21949  |   1.33056 |              -0.841061    |        933 |
|            61 | hgb_waveform_amp_shape                 | ml                     |     1.63325  | 1.58857  |   1.70362 |              -0.496714    |        933 |
|            61 | hgb_waveform_only                      | ml                     |     1.75875  | 1.69299  |   1.81212 |              -0.371218    |        933 |
|            61 | mlp_waveform_amp_shape                 | ml                     |     2.06617  | 1.98349  |   2.13394 |              -0.06379     |        933 |
|            61 | cnn1d_waveform_only                    | ml                     |     2.12922  | 1.97675  |   2.21105 |              -0.000739483 |        933 |
|            61 | analytic_timewalk                      | traditional            |     2.12996  | 1.98719  |   2.21756 |               0           |        933 |
|            61 | feature_gated_waveform_only            | ml                     |     2.15621  | 2.04042  |   2.26361 |               0.0262422   |        933 |
|            61 | mlp_waveform_only                      | ml                     |     2.17016  | 2.10134  |   2.29    |               0.0401943   |        933 |
|            61 | cnn1d_waveform_amp_shape               | ml                     |     2.17044  | 2.08276  |   2.25822 |               0.0404747   |        933 |
|            61 | feature_gated_waveform_amp_shape       | ml                     |     2.17966  | 2.07121  |   2.26458 |               0.049697    |        933 |
|            61 | ridge_waveform_amp_shape               | ml                     |     2.20013  | 2.09838  |   2.27134 |               0.0701647   |        933 |
|            61 | ridge_waveform_only                    | ml                     |     2.20264  | 2.12646  |   2.30558 |               0.0726787   |        933 |
|            62 | hgb_waveform_stave_onehot              | ml                     |     1.13647  | 1.08409  |   1.21186 |              -0.332536    |        807 |
|            62 | mlp_waveform_amp_shape_stave           | ml                     |     1.15566  | 1.08478  |   1.21101 |              -0.313348    |        807 |
|            62 | hgb_waveform_amp_shape_stave           | ml                     |     1.1568   | 1.08434  |   1.19624 |              -0.312208    |        807 |
|            62 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.16536  | 1.09815  |   1.22622 |              -0.303641    |        807 |
|            62 | feature_gated_waveform_amp_shape_stave | ml                     |     1.20428  | 1.13838  |   1.25513 |              -0.26472     |        807 |
|            62 | mlp_waveform_stave_onehot              | ml                     |     1.20453  | 1.13336  |   1.26805 |              -0.264475    |        807 |
|            62 | feature_gated_waveform_stave_onehot    | ml                     |     1.27661  | 1.20686  |   1.33171 |              -0.192396    |        807 |
|            62 | ridge_waveform_stave_onehot            | ml                     |     1.29282  | 1.22887  |   1.36444 |              -0.176183    |        807 |
|            62 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.29384  | 1.2267   |   1.37392 |              -0.17517     |        807 |
|            62 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.31009  | 1.24952  |   1.38618 |              -0.158918    |        807 |
|            62 | ridge_waveform_amp_shape_stave         | ml                     |     1.3199   | 1.2705   |   1.37362 |              -0.149102    |        807 |
|            62 | cnn1d_waveform_stave_onehot            | ml                     |     1.42131  | 1.32765  |   1.47598 |              -0.047696    |        807 |
|            62 | hgb_waveform_amp_shape                 | ml                     |     1.43919  | 1.38812  |   1.48805 |              -0.0298198   |        807 |
|            62 | feature_gated_waveform_only            | ml                     |     1.45822  | 1.40393  |   1.5205  |              -0.0107824   |        807 |
|            62 | hgb_waveform_only                      | ml                     |     1.46034  | 1.40684  |   1.51225 |              -0.00866789  |        807 |
|            62 | cnn1d_waveform_only                    | ml                     |     1.46386  | 1.4004   |   1.52374 |              -0.0051447   |        807 |
|            62 | analytic_timewalk                      | traditional            |     1.469    | 1.40836  |   1.53088 |               0           |        807 |
|            62 | mlp_waveform_only                      | ml                     |     1.49837  | 1.44328  |   1.56102 |               0.0293701   |        807 |
|            62 | ridge_waveform_only                    | ml                     |     1.55757  | 1.50057  |   1.63527 |               0.0885662   |        807 |
|            62 | mlp_waveform_amp_shape                 | ml                     |     1.62142  | 1.56266  |   1.66488 |               0.152412    |        807 |
|            62 | ridge_waveform_amp_shape               | ml                     |     1.69235  | 1.62341  |   1.77922 |               0.223343    |        807 |
|            62 | feature_gated_waveform_amp_shape       | ml                     |     1.7197   | 1.66447  |   1.7793  |               0.250692    |        807 |
|            62 | cnn1d_waveform_amp_shape               | ml                     |     1.75433  | 1.70266  |   1.80472 |               0.285325    |        807 |
|            63 | hgb_waveform_amp_shape_stave           | ml                     |     1.17366  | 1.09952  |   1.26397 |              -0.217666    |        370 |
|            63 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.21167  | 1.11829  |   1.29794 |              -0.179655    |        370 |
|            63 | hgb_waveform_stave_onehot              | ml                     |     1.22025  | 1.13243  |   1.32865 |              -0.171072    |        370 |
|            63 | mlp_waveform_stave_onehot              | ml                     |     1.25999  | 1.15434  |   1.36128 |              -0.131333    |        370 |
|            63 | feature_gated_waveform_amp_shape_stave | ml                     |     1.27525  | 1.1684   |   1.37909 |              -0.116075    |        370 |
|            63 | mlp_waveform_amp_shape_stave           | ml                     |     1.31501  | 1.21996  |   1.41403 |              -0.0763082   |        370 |
|            63 | feature_gated_waveform_stave_onehot    | ml                     |     1.32277  | 1.26005  |   1.41161 |              -0.0685543   |        370 |
|            63 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.34041  | 1.22059  |   1.44024 |              -0.0509153   |        370 |
|            63 | ridge_waveform_stave_onehot            | ml                     |     1.34707  | 1.25562  |   1.42466 |              -0.0442495   |        370 |
|            63 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.3529   | 1.23845  |   1.4252  |              -0.0384231   |        370 |
|            63 | analytic_timewalk                      | traditional            |     1.39132  | 1.30359  |   1.46925 |               0           |        370 |
|            63 | cnn1d_waveform_only                    | ml                     |     1.39697  | 1.30507  |   1.47282 |               0.00565002  |        370 |
|            63 | feature_gated_waveform_only            | ml                     |     1.40587  | 1.314    |   1.48313 |               0.0145491   |        370 |
|            63 | ridge_waveform_amp_shape_stave         | ml                     |     1.42312  | 1.32605  |   1.50268 |               0.0318014   |        370 |
|            63 | hgb_waveform_amp_shape                 | ml                     |     1.45387  | 1.38082  |   1.54166 |               0.0625514   |        370 |
|            63 | hgb_waveform_only                      | ml                     |     1.46146  | 1.39384  |   1.52033 |               0.0701387   |        370 |
|            63 | ridge_waveform_only                    | ml                     |     1.47613  | 1.40952  |   1.55735 |               0.0848087   |        370 |
|            63 | mlp_waveform_amp_shape                 | ml                     |     1.4766   | 1.39747  |   1.54153 |               0.0852789   |        370 |
|            63 | cnn1d_waveform_stave_onehot            | ml                     |     1.47731  | 1.35059  |   1.54041 |               0.0859883   |        370 |
|            63 | mlp_waveform_only                      | ml                     |     1.48193  | 1.39868  |   1.54694 |               0.0906048   |        370 |
|            63 | feature_gated_waveform_amp_shape       | ml                     |     1.6047   | 1.52064  |   1.67169 |               0.213374    |        370 |
|            63 | cnn1d_waveform_amp_shape               | ml                     |     1.62819  | 1.54668  |   1.70824 |               0.236873    |        370 |
|            63 | ridge_waveform_amp_shape               | ml                     |     1.64826  | 1.55436  |   1.7386  |               0.256936    |        370 |
|            65 | hgb_waveform_amp_shape_stave           | ml                     |     1.22328  | 0.939806 |   1.48958 |              -0.271363    |         66 |
|            65 | mlp_waveform_stave_onehot              | ml                     |     1.22528  | 0.97158  |   1.51121 |              -0.269359    |         66 |
|            65 | hgb_waveform_stave_onehot              | ml                     |     1.25035  | 0.945519 |   1.59179 |              -0.244288    |         66 |
|            65 | mlp_waveform_amp_shape_stave           | ml                     |     1.28316  | 1.02872  |   1.60759 |              -0.211482    |         66 |
|            65 | hgb_stave_offset_guardrail             | stave_offset_guardrail |     1.2868   | 1.05946  |   1.53734 |              -0.207836    |         66 |
|            65 | ridge_stave_offset_guardrail           | stave_offset_guardrail |     1.31856  | 1.06876  |   1.59192 |              -0.176083    |         66 |
|            65 | cnn1d_waveform_amp_shape_stave         | ml                     |     1.35225  | 1.12098  |   1.5671  |              -0.142387    |         66 |
|            65 | feature_gated_waveform_stave_onehot    | ml                     |     1.38818  | 1.29946  |   1.51916 |              -0.106457    |         66 |
|            65 | ridge_waveform_stave_onehot            | ml                     |     1.39117  | 1.1267   |   1.64731 |              -0.103473    |         66 |
|            65 | hgb_waveform_amp_shape                 | ml                     |     1.41774  | 1.22107  |   1.55744 |              -0.0769034   |         66 |
|            65 | cnn1d_waveform_stave_onehot            | ml                     |     1.4219   | 1.21495  |   1.68353 |              -0.0727417   |         66 |
|            65 | hgb_waveform_only                      | ml                     |     1.43901  | 1.28241  |   1.53619 |              -0.0556253   |         66 |
|            65 | feature_gated_waveform_only            | ml                     |     1.44608  | 1.31517  |   1.66544 |              -0.0485598   |         66 |
|            65 | cnn1d_waveform_only                    | ml                     |     1.45912  | 1.31227  |   1.65912 |              -0.03552     |         66 |
|            65 | mlp_waveform_only                      | ml                     |     1.48566  | 1.36289  |   1.69195 |              -0.00897874  |         66 |
|            65 | ridge_waveform_amp_shape_stave         | ml                     |     1.48689  | 1.31231  |   1.6715  |              -0.00774838  |         66 |
|            65 | feature_gated_waveform_amp_shape_stave | ml                     |     1.49201  | 1.27634  |   1.68314 |              -0.0026265   |         66 |
|            65 | analytic_timewalk                      | traditional            |     1.49464  | 1.32251  |   1.66333 |               0           |         66 |
|            65 | ridge_waveform_only                    | ml                     |     1.57146  | 1.43011  |   1.75942 |               0.076816    |         66 |
|            65 | mlp_waveform_amp_shape                 | ml                     |     1.5963   | 1.41961  |   1.80254 |               0.101662    |         66 |
|            65 | cnn1d_waveform_amp_shape               | ml                     |     1.62334  | 1.41868  |   1.88259 |               0.128697    |         66 |
|            65 | feature_gated_waveform_amp_shape       | ml                     |     1.66661  | 1.45405  |   1.92558 |               0.171974    |         66 |
|            65 | ridge_waveform_amp_shape               | ml                     |     1.7114   | 1.4696   |   1.87643 |               0.216758    |         66 |

## Leakage and Systematics

|   heldout_run | check                                                        |        value | pass   |
|--------------:|:-------------------------------------------------------------|-------------:|:-------|
|            58 | train_heldout_run_overlap                                    |  0           | True   |
|            58 | train_heldout_event_id_overlap                               |  0           | True   |
|            58 | feature_audit                                                |  0           | True   |
|            58 | shuffled_target_worse:ridge_waveform_only                    | -0.134669    | False  |
|            58 | shuffled_target_worse:hgb_waveform_only                      | -0.387068    | False  |
|            58 | shuffled_target_worse:mlp_waveform_only                      | -0.0466717   | False  |
|            58 | shuffled_target_worse:cnn1d_waveform_only                    |  0.00987095  | True   |
|            58 | shuffled_target_worse:feature_gated_waveform_only            |  0.000438549 | True   |
|            58 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.155637    | True   |
|            58 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.144204    | True   |
|            58 | shuffled_target_worse:mlp_waveform_stave_onehot              | -0.117366    | False  |
|            58 | shuffled_target_worse:cnn1d_waveform_stave_onehot            | -0.16922     | False  |
|            58 | shuffled_target_worse:feature_gated_waveform_stave_onehot    | -0.0535271   | False  |
|            58 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.387428    | False  |
|            58 | shuffled_target_worse:hgb_waveform_amp_shape                 | -0.319271    | False  |
|            58 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.291596    | False  |
|            58 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.291039    | False  |
|            58 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.305304    | False  |
|            58 | shuffled_target_worse:ridge_waveform_amp_shape_stave         | -0.0264583   | False  |
|            58 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.159928    | True   |
|            58 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.14739     | True   |
|            58 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.00984114  | True   |
|            58 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.112713    | True   |
|            59 | train_heldout_run_overlap                                    |  0           | True   |
|            59 | train_heldout_event_id_overlap                               |  0           | True   |
|            59 | feature_audit                                                |  0           | True   |
|            59 | shuffled_target_worse:ridge_waveform_only                    | -0.0937896   | False  |
|            59 | shuffled_target_worse:hgb_waveform_only                      |  0.145705    | True   |
|            59 | shuffled_target_worse:mlp_waveform_only                      | -0.0896543   | False  |
|            59 | shuffled_target_worse:cnn1d_waveform_only                    |  0.0290782   | True   |
|            59 | shuffled_target_worse:feature_gated_waveform_only            |  0.0158947   | True   |
|            59 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.134487    | True   |
|            59 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.377457    | True   |
|            59 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.205412    | True   |
|            59 | shuffled_target_worse:cnn1d_waveform_stave_onehot            |  0.0471848   | True   |
|            59 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.189837    | True   |
|            59 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.243225    | False  |
|            59 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.127092    | True   |
|            59 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.0361515   | False  |
|            59 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.359807    | False  |
|            59 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.242682    | False  |
|            59 | shuffled_target_worse:ridge_waveform_amp_shape_stave         |  0.158549    | True   |
|            59 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.385411    | True   |
|            59 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.406116    | True   |
|            59 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.123005    | True   |
|            59 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.108775    | True   |
|            60 | train_heldout_run_overlap                                    |  0           | True   |
|            60 | train_heldout_event_id_overlap                               |  0           | True   |
|            60 | feature_audit                                                |  0           | True   |
|            60 | shuffled_target_worse:ridge_waveform_only                    | -0.122441    | False  |
|            60 | shuffled_target_worse:hgb_waveform_only                      | -0.0103053   | False  |
|            60 | shuffled_target_worse:mlp_waveform_only                      | -0.0602124   | False  |
|            60 | shuffled_target_worse:cnn1d_waveform_only                    | -0.00353159  | False  |
|            60 | shuffled_target_worse:feature_gated_waveform_only            | -0.0176053   | False  |
|            60 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.10604     | True   |
|            60 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.243149    | True   |
|            60 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.137825    | True   |
|            60 | shuffled_target_worse:cnn1d_waveform_stave_onehot            | -0.0596316   | False  |
|            60 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.165731    | True   |
|            60 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.298507    | False  |
|            60 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.0502837   | True   |
|            60 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.0802844   | False  |
|            60 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.268209    | False  |
|            60 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.201433    | False  |
|            60 | shuffled_target_worse:ridge_waveform_amp_shape_stave         | -0.0699697   | False  |
|            60 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.361479    | True   |
|            60 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.187095    | True   |
|            60 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.153598    | True   |
|            60 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.0958507   | True   |
|            61 | train_heldout_run_overlap                                    |  0           | True   |
|            61 | train_heldout_event_id_overlap                               |  0           | True   |
|            61 | feature_audit                                                |  0           | True   |
|            61 | shuffled_target_worse:ridge_waveform_only                    | -0.0750832   | False  |
|            61 | shuffled_target_worse:hgb_waveform_only                      |  0.389747    | True   |
|            61 | shuffled_target_worse:mlp_waveform_only                      | -0.0384941   | False  |
|            61 | shuffled_target_worse:cnn1d_waveform_only                    | -0.00157823  | False  |
|            61 | shuffled_target_worse:feature_gated_waveform_only            | -0.0277186   | False  |
|            61 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.87051     | True   |
|            61 | shuffled_target_worse:hgb_waveform_stave_onehot              |  1.0365      | True   |
|            61 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.986063    | True   |
|            61 | shuffled_target_worse:cnn1d_waveform_stave_onehot            |  0.731815    | True   |
|            61 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.879821    | True   |
|            61 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.102508    | False  |
|            61 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.530748    | True   |
|            61 | shuffled_target_worse:mlp_waveform_amp_shape                 |  0.0266848   | True   |
|            61 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.0387151   | False  |
|            61 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.0879207   | False  |
|            61 | shuffled_target_worse:ridge_waveform_amp_shape_stave         |  0.851132    | True   |
|            61 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  1.04727     | True   |
|            61 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  1.03028     | True   |
|            61 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.833479    | True   |
|            61 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.854024    | True   |
|            62 | train_heldout_run_overlap                                    |  0           | True   |
|            62 | train_heldout_event_id_overlap                               |  0           | True   |
|            62 | feature_audit                                                |  0           | True   |
|            62 | shuffled_target_worse:ridge_waveform_only                    | -0.0805685   | False  |
|            62 | shuffled_target_worse:hgb_waveform_only                      |  0.10609     | True   |
|            62 | shuffled_target_worse:mlp_waveform_only                      | -0.0275337   | False  |
|            62 | shuffled_target_worse:cnn1d_waveform_only                    |  0.00620181  | True   |
|            62 | shuffled_target_worse:feature_gated_waveform_only            |  0.0112105   | True   |
|            62 | shuffled_target_worse:ridge_waveform_stave_onehot            |  0.191136    | True   |
|            62 | shuffled_target_worse:hgb_waveform_stave_onehot              |  0.418408    | True   |
|            62 | shuffled_target_worse:mlp_waveform_stave_onehot              |  0.234542    | True   |
|            62 | shuffled_target_worse:cnn1d_waveform_stave_onehot            |  0.140823    | True   |
|            62 | shuffled_target_worse:feature_gated_waveform_stave_onehot    |  0.235036    | True   |
|            62 | shuffled_target_worse:ridge_waveform_amp_shape               | -0.190872    | False  |
|            62 | shuffled_target_worse:hgb_waveform_amp_shape                 |  0.145179    | True   |
|            62 | shuffled_target_worse:mlp_waveform_amp_shape                 | -0.138961    | False  |
|            62 | shuffled_target_worse:cnn1d_waveform_amp_shape               | -0.272063    | False  |
|            62 | shuffled_target_worse:feature_gated_waveform_amp_shape       | -0.263587    | False  |
|            62 | shuffled_target_worse:ridge_waveform_amp_shape_stave         |  0.157873    | True   |
|            62 | shuffled_target_worse:hgb_waveform_amp_shape_stave           |  0.388079    | True   |
|            62 | shuffled_target_worse:mlp_waveform_amp_shape_stave           |  0.271743    | True   |
|            62 | shuffled_target_worse:cnn1d_waveform_amp_shape_stave         |  0.151464    | True   |
|            62 | shuffled_target_worse:feature_gated_waveform_amp_shape_stave |  0.237558    | True   |
|            63 | train_heldout_run_overlap                                    |  0           | True   |
|            63 | train_heldout_event_id_overlap                               |  0           | True   |
|            63 | feature_audit                                                |  0           | True   |
|            63 | shuffled_target_worse:ridge_waveform_only                    | -0.0703865   | False  |
|            63 | shuffled_target_worse:hgb_waveform_only                      | -0.0919136   | False  |

Main caveats:

- Sample-II run 65 has low statistics; the pooled CI therefore uses runs as the outer bootstrap unit.
- The residual target is internally defined from same-event downstream staves, so all claims are relative timing-closure claims, not absolute beam-time truth.
- Stave-aware variants intentionally include detector identity. They are useful predictors but remain vulnerable to detector-condition leakage; the stave-offset guardrail quantifies the part explainable without waveform samples.
- Histogram-gradient boosting is a strong nonlinear tabular learner but is not monotonicity constrained here.

## Verdict

Winner in `result.json`: `hgb_waveform_amp_shape_stave` with pooled `sigma68 = 1.107 ns` and CI `[1.075, 1.159] ns`.

Interpretation: The P03e waveform_amp_shape_stave gain survives beyond run 65 in the leave-one-run repetition: stave-aware amplitude/shape models beat their stave-blind analogues in most held-out runs and in the run-block pooled estimate. 61 shuffled-target checks beat their nominal model and are flagged as stability caveats.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03f_1781034623_1381_12086ef0_loro_feature_multimodel.py --config configs/p03f_1781034623_1381_12086ef0_loro_feature_multimodel.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `model_diagnostics.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
