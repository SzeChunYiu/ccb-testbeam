# S03 follow-up 2412: cross-sample physics-residual timewalk adoption gate

- **Ticket:** `2412`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Training split:** Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Evaluation split:** Sample-I runs `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]` plus diagnostic run 64
- **Primary estimand:** downstream B4/B6/B8 same-event pair residual width after a frozen Sample-II residual correction

## Abstract

Ticket #2412 asks whether the S03/P03f learned residual timewalk correction is a
portable amplitude-timewalk correction or a Sample-II run-family artifact.  This
study trains every correction on Sample-II analysis runs only, freezes the
templates, analytic S03 comparator, feature scaling, and residual learners, and
then scores Sample-I and run 64 without using those rows for fitting.  The raw
ROOT selected-pulse gate is reproduced first: `640737` selected B-stave pulses,
matching the canonical value exactly.

The primary Sample-I winner is **`cnn1d_waveform_amp_shape_stave`**
(`1d_cnn`), with `sigma68 = 0.903 ns`
and run-block 95% CI [0.880, 0.929].  The strong traditional comparator,
`analytic_timewalk`, has `sigma68 = 1.191 ns` with CI
[1.178, 1.209].  The winner changes Sample-I `sigma68` by
-0.289 ns relative to the comparator.  Run 64 is estimable under this strict endpoint with 630 pair residuals; its best ML row is `hgb_waveform_amp_shape_stave` at `sigma68 = 1.058 ns`, delta -0.507 ns versus analytic.

## Raw-ROOT reproduction gate

The count gate reads `h101/HRDv` directly, reshapes each event to `(8,18)`,
subtracts the median of samples 0--3 in each channel, and applies
`max_t x_c(t) > 1000 ADC` to B2/B4/B6/B8.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

All rows have zero tolerance.  Failure of this table would invalidate the
transfer benchmark.

## Estimand and equations

For event `e`, downstream stave `s`, and method `m`, the geometry-corrected time is

`tau_(e,s,m) = t_(e,s,m) - z_s v_TOF`,

where the downstream B-stave positions use 2 cm spacing and
`v_TOF = 0.078 ns/cm`.  For pair `(a,b)` in `{B4-B6, B4-B8, B6-B8}`,

`r_(e,a,b,m) = tau_(e,a,m) - tau_(e,b,m)`.

The primary width is

`sigma68(r_m) = [Q84(r_m) - Q16(r_m)] / 2`.

The learned residual models target the pulse-local analytic residual

`y_(e,s) = tau_(e,s,analytic) - mean_(k != s) tau_(e,k,analytic)`,

using only same-pulse waveform, amplitude/shape summaries, and a downstream
stave one-hot.  The corrected timestamp is

`t_(e,s,m) = t_(e,s,analytic) - f_m(x_(e,s))`.

No model receives run id, event id, event order, other-stave time, pair residual,
or a Sample-I/run-64 fitted amplitude correction.

## Methods

The strong traditional method is the S03 analytic timewalk comparator, fit on
Sample-II analysis runs after rebuilding S02 template-phase times from those
same training runs.  It scans the established S03 candidate family and ridge
penalties with grouped folds.

The ML/NN panel uses the required P03f families on the identical target and
feature set:

- `ridge_waveform_amp_shape_stave`: standardized Ridge regression with grouped
  alpha selection on Sample-II training runs.
- `hgb_waveform_amp_shape_stave`: histogram gradient-boosted regression trees.
- `mlp_waveform_amp_shape_stave`: compact heteroskedastic fully connected net.
- `cnn1d_waveform_amp_shape_stave`: compact 1D-CNN over the 18-sample waveform
  plus auxiliary pulse features.
- `feature_gated_waveform_amp_shape_stave`: new architecture with separate
  waveform and auxiliary branches mixed by a learned gate.

The new gated architecture is sensible here because transfer risk is exactly
about whether local waveform evidence or auxiliary amplitude/stave support is
driving the correction.  A gate makes that mixing explicit while preserving the
same leakage exclusions as the other learners.

## Primary Sample-I benchmark

| method                                 | model_family                      | family      |   n_runs |   n_pair_residuals |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |
|:---------------------------------------|:----------------------------------|:------------|---------:|-------------------:|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|--------------:|----------------------:|
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                            | ml          |       25 |               3780 |     0.902706 | 0.880448 |  0.929123 |                -0.288595  |     -0.320404  |     -0.258596   |       2.41411 |            0.00925926 |
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees            | ml          |       25 |               3780 |     0.942655 | 0.904715 |  0.992859 |                -0.248647  |     -0.288379  |     -0.202648   |       2.11447 |            0.010582   |
| mlp_waveform_amp_shape_stave           | mlp                               | ml          |       25 |               3780 |     1.03649  | 1.01493  |  1.06222  |                -0.154812  |     -0.178895  |     -0.130929   |       2.68542 |            0.0103175  |
| ridge_waveform_amp_shape_stave         | ridge                             | ml          |       25 |               3780 |     1.09398  | 1.06559  |  1.11637  |                -0.0973241 |     -0.130218  |     -0.0710933  |       2.29946 |            0.00925926 |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture    | ml          |       25 |               3780 |     1.15959  | 1.13589  |  1.18088  |                -0.0317083 |     -0.0628051 |     -0.00693676 |       2.54713 |            0.0100529  |
| analytic_timewalk                      | traditional_s03_analytic_timewalk | traditional |       25 |               3780 |     1.1913   | 1.1781   |  1.2095   |                 0         |      0         |      0          |       2.37207 |            0.0103175  |

## All evaluable held-out rows

| method                                 | model_family                      | family      |   n_runs |   n_pair_residuals |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |
|:---------------------------------------|:----------------------------------|:------------|---------:|-------------------:|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                            | ml          |       26 |               4410 |     0.936182 | 0.88646  |   1.0103  |                -0.284528  |      -0.313517 |      -0.249941  |
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees            | ml          |       26 |               4410 |     0.964988 | 0.917256 |   1.00478 |                -0.255722  |      -0.302309 |      -0.209363  |
| mlp_waveform_amp_shape_stave           | mlp                               | ml          |       26 |               4410 |     1.06186  | 1.02309  |   1.10264 |                -0.158846  |      -0.1888   |      -0.132131  |
| ridge_waveform_amp_shape_stave         | ridge                             | ml          |       26 |               4410 |     1.11337  | 1.07459  |   1.15633 |                -0.107338  |      -0.13255  |      -0.0763372 |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture    | ml          |       26 |               4410 |     1.1595   | 1.13603  |   1.17778 |                -0.0612081 |      -0.129272 |      -0.0157094 |
| analytic_timewalk                      | traditional_s03_analytic_timewalk | traditional |       26 |               4410 |     1.22071  | 1.1796   |   1.27915 |                 0         |       0        |       0         |

This table includes Sample-I plus the run-64 diagnostic rows.

## Split-by-run results

|   run | run_group         | method                                 |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_pair_residuals |
|------:|:------------------|:---------------------------------------|-------------:|---------:|----------:|--------------------------:|-------------------:|
|    31 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.886363 | 0.659601 |  1.2027   |              -0.413789    |                141 |
|    31 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.89412  | 0.751261 |  1.16431  |              -0.406032    |                141 |
|    31 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.07064  | 0.934064 |  1.22715  |              -0.229517    |                141 |
|    31 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     1.11326  | 0.852588 |  1.33379  |              -0.186894    |                141 |
|    31 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.13336  | 0.898058 |  1.361    |              -0.166795    |                141 |
|    31 | sample_i_calib    | analytic_timewalk                      |     1.30015  | 1.13757  |  1.47859  |               0           |                141 |
|    32 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.807265 | 0.712797 |  0.924444 |              -0.367921    |                120 |
|    32 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.895188 | 0.741284 |  1.13172  |              -0.279999    |                120 |
|    32 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     0.907884 | 0.775149 |  1.14086  |              -0.267303    |                120 |
|    32 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.02245  | 0.912942 |  1.20577  |              -0.152733    |                120 |
|    32 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.06952  | 0.890842 |  1.25753  |              -0.105666    |                120 |
|    32 | sample_i_calib    | analytic_timewalk                      |     1.17519  | 1.10933  |  1.23767  |               0           |                120 |
|    33 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.918001 | 0.789832 |  1.11677  |              -0.219571    |                177 |
|    33 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.08622  | 0.881215 |  1.19927  |              -0.0513567   |                177 |
|    33 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     1.12496  | 0.822364 |  1.35156  |              -0.0126156   |                177 |
|    33 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     1.13639  | 0.954469 |  1.33502  |              -0.00118703  |                177 |
|    33 | sample_i_calib    | analytic_timewalk                      |     1.13757  | 1.10565  |  1.21924  |               0           |                177 |
|    33 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.26445  | 1.06263  |  1.38974  |               0.126876    |                177 |
|    34 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.858584 | 0.759059 |  1.05985  |              -0.327945    |                150 |
|    34 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.930491 | 0.764348 |  1.13393  |              -0.256038    |                150 |
|    34 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     0.966285 | 0.838513 |  1.16472  |              -0.220244    |                150 |
|    34 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.06878  | 0.961545 |  1.2527   |              -0.117754    |                150 |
|    34 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.1858   | 1.06249  |  1.34296  |              -0.000726111 |                150 |
|    34 | sample_i_calib    | analytic_timewalk                      |     1.18653  | 1.15048  |  1.34003  |               0           |                150 |
|    35 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.871693 | 0.704761 |  1.14634  |              -0.352913    |                108 |
|    35 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     0.947479 | 0.845968 |  1.26092  |              -0.277126    |                108 |
|    35 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     1.05495  | 0.861874 |  1.36354  |              -0.169651    |                108 |
|    35 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     1.06633  | 0.852466 |  1.31864  |              -0.158271    |                108 |
|    35 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.08743  | 0.902301 |  1.27225  |              -0.137176    |                108 |
|    35 | sample_i_calib    | analytic_timewalk                      |     1.22461  | 1.11107  |  1.55615  |               0           |                108 |
|    36 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.903746 | 0.551671 |  1.39754  |              -0.48063     |                 66 |
|    36 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.931603 | 0.670762 |  1.30139  |              -0.452772    |                 66 |
|    36 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     0.958725 | 0.751237 |  1.39908  |              -0.425651    |                 66 |
|    36 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     0.990799 | 0.810566 |  1.51008  |              -0.393577    |                 66 |
|    36 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.13445  | 0.813248 |  1.4257   |              -0.249929    |                 66 |
|    36 | sample_i_calib    | analytic_timewalk                      |     1.38438  | 1.13558  |  1.91046  |               0           |                 66 |
|    37 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.866446 | 0.739955 |  1.03292  |              -0.370793    |                249 |
|    37 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     1.05885  | 0.90848  |  1.20728  |              -0.17839     |                249 |
|    37 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     1.08449  | 0.901332 |  1.23298  |              -0.152746    |                249 |
|    37 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.128    | 1.01775  |  1.23398  |              -0.109236    |                249 |
|    37 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.14869  | 1.00198  |  1.26807  |              -0.0885496   |                249 |
|    37 | sample_i_calib    | analytic_timewalk                      |     1.23724  | 1.15398  |  1.3268   |               0           |                249 |
|    39 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.811574 | 0.675081 |  1.11934  |              -0.426751    |                198 |
|    39 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.856689 | 0.688869 |  1.21741  |              -0.381636    |                198 |
|    39 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     0.972635 | 0.788079 |  1.20547  |              -0.26569     |                198 |
|    39 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.06397  | 0.923379 |  1.26555  |              -0.174356    |                198 |
|    39 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.10246  | 0.954456 |  1.24342  |              -0.135862    |                198 |
|    39 | sample_i_calib    | analytic_timewalk                      |     1.23832  | 1.17742  |  1.36433  |               0           |                198 |
|    40 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.899373 | 0.736233 |  1.1607   |              -0.294675    |                210 |
|    40 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.902773 | 0.773464 |  1.00102  |              -0.291275    |                210 |
|    40 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     1.04621  | 0.879496 |  1.20722  |              -0.147838    |                210 |
|    40 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.10922  | 0.939403 |  1.25229  |              -0.0848268   |                210 |
|    40 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.175    | 1.00219  |  1.38294  |              -0.0190437   |                210 |
|    40 | sample_i_calib    | analytic_timewalk                      |     1.19405  | 1.1322   |  1.29336  |               0           |                210 |
|    41 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.931088 | 0.798825 |  1.09423  |              -0.226509    |                207 |
|    41 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.940703 | 0.816406 |  1.13485  |              -0.216894    |                207 |
|    41 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     0.992556 | 0.849538 |  1.24565  |              -0.165041    |                207 |
|    41 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.13409  | 1.00616  |  1.30059  |              -0.0235027   |                207 |
|    41 | sample_i_calib    | analytic_timewalk                      |     1.1576   | 1.10545  |  1.2433   |               0           |                207 |
|    41 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.19413  | 1.03412  |  1.32469  |               0.0365305   |                207 |
|    42 | sample_i_calib    | cnn1d_waveform_amp_shape_stave         |     0.916684 | 0.792477 |  1.07135  |              -0.268995    |                204 |
|    42 | sample_i_calib    | hgb_waveform_amp_shape_stave           |     0.960362 | 0.78317  |  1.15315  |              -0.225318    |                204 |
|    42 | sample_i_calib    | mlp_waveform_amp_shape_stave           |     0.995341 | 0.880291 |  1.16599  |              -0.190339    |                204 |
|    42 | sample_i_calib    | ridge_waveform_amp_shape_stave         |     1.14756  | 1.04369  |  1.20011  |              -0.0381208   |                204 |
|    42 | sample_i_calib    | analytic_timewalk                      |     1.18568  | 1.12737  |  1.38605  |               0           |                204 |
|    42 | sample_i_calib    | feature_gated_waveform_amp_shape_stave |     1.22962  | 1.07593  |  1.34468  |               0.0439402   |                204 |
|    44 | sample_i_analysis | analytic_timewalk                      |     1.196    | 1.04399  |  1.77175  |               0           |                 21 |
|    44 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.23276  | 0.701701 |  1.63375  |               0.0367581   |                 21 |
|    44 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     1.25258  | 0.710128 |  1.60508  |               0.056579    |                 21 |
|    44 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.30587  | 0.750459 |  1.73523  |               0.109869    |                 21 |
|    44 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     1.422    | 0.807615 |  7.00854  |               0.226       |                 21 |
|    44 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.56927  | 0.909656 |  1.82639  |               0.373263    |                 21 |
|    45 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.862607 | 0.736233 |  0.959051 |              -0.338421    |                282 |
|    45 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.918424 | 0.747006 |  1.11187  |              -0.282604    |                282 |
|    45 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.0062   | 0.840539 |  1.15054  |              -0.194829    |                282 |
|    45 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.0588   | 0.960076 |  1.13937  |              -0.142232    |                282 |
|    45 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.10191  | 1.01618  |  1.2136   |              -0.099118    |                282 |
|    45 | sample_i_analysis | analytic_timewalk                      |     1.20103  | 1.1174   |  1.25397  |               0           |                282 |
|    46 | sample_i_analysis | analytic_timewalk                      |     0.223377 | 0.223377 |  0.223377 |               0           |                  3 |
|    46 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.875943 | 0.875943 |  0.875943 |               0.652566    |                  3 |
|    46 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     0.919306 | 0.919306 |  0.919306 |               0.695929    |                  3 |
|    46 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.986787 | 0.986787 |  0.986787 |               0.76341     |                  3 |
|    46 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.00623  | 1.00623  |  1.00623  |               0.782853    |                  3 |
|    46 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.0987   | 1.0987   |  1.0987   |               0.875327    |                  3 |
|    47 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.686512 | 0.475911 |  1.18456  |              -0.665902    |                 27 |
|    47 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.00556  | 0.672069 |  1.53401  |              -0.346853    |                 27 |
|    47 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     1.03112  | 0.702304 |  1.44072  |              -0.321295    |                 27 |
|    47 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.11373  | 0.888046 |  1.39862  |              -0.238685    |                 27 |
|    47 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.29528  | 0.947093 |  1.58677  |              -0.0571376   |                 27 |
|    47 | sample_i_analysis | analytic_timewalk                      |     1.35241  | 0.973059 |  1.75657  |               0           |                 27 |
|    48 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.928081 | 0.775944 |  1.12969  |              -0.206553    |                174 |
|    48 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.931812 | 0.785909 |  1.22664  |              -0.202822    |                174 |
|    48 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.06234  | 0.888597 |  1.24406  |              -0.0722909   |                174 |
|    48 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.11517  | 0.955265 |  1.35723  |              -0.0194585   |                174 |
|    48 | sample_i_analysis | analytic_timewalk                      |     1.13463  | 1.09539  |  1.2109   |               0           |                174 |
|    48 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.1519   | 0.940935 |  1.3385   |               0.017266    |                174 |
|    49 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.877076 | 0.733497 |  1.14812  |              -0.326636    |                168 |
|    49 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.951623 | 0.767286 |  1.28608  |              -0.252089    |                168 |
|    49 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     0.989754 | 0.81542  |  1.27528  |              -0.213959    |                168 |
|    49 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.10448  | 0.950252 |  1.27794  |              -0.0992349   |                168 |
|    49 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.16617  | 1.01697  |  1.40548  |              -0.0375382   |                168 |
|    49 | sample_i_analysis | analytic_timewalk                      |     1.20371  | 1.1232   |  1.35326  |               0           |                168 |
|    50 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.990102 | 0.81299  |  1.23488  |              -0.211213    |                180 |
|    50 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.994972 | 0.822165 |  1.26389  |              -0.206343    |                180 |
|    50 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.10039  | 0.937351 |  1.40816  |              -0.10092     |                180 |
|    50 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.10181  | 0.980899 |  1.3024   |              -0.0995052   |                180 |
|    50 | sample_i_analysis | analytic_timewalk                      |     1.20132  | 1.12539  |  1.28988  |               0           |                180 |
|    50 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.20642  | 1.03978  |  1.36268  |               0.00510214  |                180 |
|    51 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.946328 | 0.716659 |  1.28122  |              -0.303187    |                102 |
|    51 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.991904 | 0.720283 |  1.45714  |              -0.257612    |                102 |
|    51 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.11226  | 0.906021 |  1.5027   |              -0.137253    |                102 |
|    51 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.15781  | 0.998698 |  1.33735  |              -0.0917009   |                102 |
|    51 | sample_i_analysis | analytic_timewalk                      |     1.24952  | 1.14198  |  1.44925  |               0           |                102 |
|    51 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.27462  | 1.06244  |  1.47516  |               0.0251036   |                102 |
|    52 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.891304 | 0.688355 |  1.36986  |              -0.257091    |                 66 |
|    52 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.910653 | 0.643848 |  1.04311  |              -0.237743    |                 66 |
|    52 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.01116  | 0.751856 |  1.23276  |              -0.137231    |                 66 |
|    52 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.04336  | 0.89395  |  1.19575  |              -0.105037    |                 66 |
|    52 | sample_i_analysis | analytic_timewalk                      |     1.1484   | 1.07824  |  1.24959  |               0           |                 66 |
|    52 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.17768  | 0.831395 |  1.33709  |               0.0292872   |                 66 |
|    53 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.808841 | 0.699188 |  0.983114 |              -0.343028    |                177 |
|    53 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.945694 | 0.815639 |  1.13762  |              -0.206175    |                177 |
|    53 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     0.973509 | 0.880846 |  1.24228  |              -0.17836     |                177 |
|    53 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.03009  | 0.767669 |  1.28564  |              -0.121781    |                177 |
|    53 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.10089  | 1.01045  |  1.22348  |              -0.0509784   |                177 |
|    53 | sample_i_analysis | analytic_timewalk                      |     1.15187  | 1.07873  |  1.23369  |               0           |                177 |
|    54 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.79965  | 0.62171  |  0.891804 |              -0.340106    |                150 |
|    54 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.860303 | 0.756342 |  0.99632  |              -0.279453    |                150 |
|    54 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     0.877348 | 0.747891 |  1.10317  |              -0.262408    |                150 |
|    54 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.02915  | 0.908009 |  1.18633  |              -0.110602    |                150 |
|    54 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.11108  | 1.003    |  1.22147  |              -0.0286769   |                150 |
|    54 | sample_i_analysis | analytic_timewalk                      |     1.13976  | 1.09191  |  1.23989  |               0           |                150 |
|    55 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     0.86468  | 0.732228 |  1.14856  |              -0.357823    |                132 |
|    55 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     0.940097 | 0.794658 |  1.18091  |              -0.282405    |                132 |
|    55 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.942564 | 0.766301 |  1.09041  |              -0.279939    |                132 |
|    55 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     0.950067 | 0.840376 |  1.09226  |              -0.272436    |                132 |
|    55 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.09268  | 1.02944  |  1.35692  |              -0.129817    |                132 |
|    55 | sample_i_analysis | analytic_timewalk                      |     1.2225   | 1.15131  |  1.29665  |               0           |                132 |
|    56 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.854192 | 0.769705 |  0.991871 |              -0.342996    |                276 |
|    56 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     1.00241  | 0.873177 |  1.14003  |              -0.194779    |                276 |
|    56 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.05273  | 0.930326 |  1.18023  |              -0.144456    |                276 |
|    56 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.12737  | 0.978647 |  1.17755  |              -0.0698176   |                276 |
|    56 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.13557  | 1.01159  |  1.24409  |              -0.0616183   |                276 |
|    56 | sample_i_analysis | analytic_timewalk                      |     1.19719  | 1.1265   |  1.24366  |               0           |                276 |
|    57 | sample_i_analysis | cnn1d_waveform_amp_shape_stave         |     0.979439 | 0.842835 |  1.19993  |              -0.206386    |                192 |
|    57 | sample_i_analysis | hgb_waveform_amp_shape_stave           |     1.01649  | 0.763182 |  1.21798  |              -0.169333    |                192 |
|    57 | sample_i_analysis | mlp_waveform_amp_shape_stave           |     1.01733  | 0.897118 |  1.20113  |              -0.16849     |                192 |
|    57 | sample_i_analysis | ridge_waveform_amp_shape_stave         |     1.08252  | 0.945097 |  1.34968  |              -0.103307    |                192 |
|    57 | sample_i_analysis | analytic_timewalk                      |     1.18583  | 1.1497   |  1.33648  |               0           |                192 |
|    57 | sample_i_analysis | feature_gated_waveform_amp_shape_stave |     1.1873   | 1.05687  |  1.41157  |               0.00147294  |                192 |

## Amplitude-support audit

Support was measured against the Sample-II training-run 1st--99th percentile
amplitude interval per stave.  These numbers are diagnostics only; no
Sample-I-specific support correction was fit.

|   run | run_group          | stave   |   n_pulses |   amp_median_adc |   sample_ii_train_q01_adc |   sample_ii_train_q99_adc |   frac_inside_sample_ii_1_99_support |
|------:|:-------------------|:--------|-----------:|-----------------:|--------------------------:|--------------------------:|-------------------------------------:|
|    31 | sample_i_calib     | B4      |         47 |          2342    |                   1096.19 |                   4221.64 |                             0.957447 |
|    31 | sample_i_calib     | B6      |         47 |          2461    |                   1172.5  |                   3802.81 |                             0.978723 |
|    31 | sample_i_calib     | B8      |         47 |          3062    |                   1247.97 |                   6273.9  |                             0.978723 |
|    32 | sample_i_calib     | B4      |         40 |          2115.75 |                   1096.19 |                   4221.64 |                             0.975    |
|    32 | sample_i_calib     | B6      |         40 |          2436    |                   1172.5  |                   3802.81 |                             0.975    |
|    32 | sample_i_calib     | B8      |         40 |          3154.25 |                   1247.97 |                   6273.9  |                             0.975    |
|    33 | sample_i_calib     | B4      |         59 |          2386.5  |                   1096.19 |                   4221.64 |                             0.983051 |
|    33 | sample_i_calib     | B6      |         59 |          2391    |                   1172.5  |                   3802.81 |                             1        |
|    33 | sample_i_calib     | B8      |         59 |          2860.5  |                   1247.97 |                   6273.9  |                             0.898305 |
|    34 | sample_i_calib     | B4      |         50 |          2309.75 |                   1096.19 |                   4221.64 |                             1        |
|    34 | sample_i_calib     | B6      |         50 |          2462    |                   1172.5  |                   3802.81 |                             0.96     |
|    34 | sample_i_calib     | B8      |         50 |          3134.75 |                   1247.97 |                   6273.9  |                             0.92     |
|    35 | sample_i_calib     | B4      |         36 |          2417.75 |                   1096.19 |                   4221.64 |                             0.944444 |
|    35 | sample_i_calib     | B6      |         36 |          2750.25 |                   1172.5  |                   3802.81 |                             0.972222 |
|    35 | sample_i_calib     | B8      |         36 |          2724.75 |                   1247.97 |                   6273.9  |                             0.944444 |
|    36 | sample_i_calib     | B4      |         22 |          2371.75 |                   1096.19 |                   4221.64 |                             0.954545 |
|    36 | sample_i_calib     | B6      |         22 |          2590.75 |                   1172.5  |                   3802.81 |                             0.954545 |
|    36 | sample_i_calib     | B8      |         22 |          3443.25 |                   1247.97 |                   6273.9  |                             1        |
|    37 | sample_i_calib     | B4      |         83 |          2461.5  |                   1096.19 |                   4221.64 |                             0.951807 |
|    37 | sample_i_calib     | B6      |         83 |          2554    |                   1172.5  |                   3802.81 |                             0.939759 |
|    37 | sample_i_calib     | B8      |         83 |          3552    |                   1247.97 |                   6273.9  |                             0.987952 |
|    39 | sample_i_calib     | B4      |         66 |          2530.25 |                   1096.19 |                   4221.64 |                             0.954545 |
|    39 | sample_i_calib     | B6      |         66 |          2633.5  |                   1172.5  |                   3802.81 |                             1        |
|    39 | sample_i_calib     | B8      |         66 |          3289.75 |                   1247.97 |                   6273.9  |                             0.984848 |
|    40 | sample_i_calib     | B4      |         70 |          2472.25 |                   1096.19 |                   4221.64 |                             0.971429 |
|    40 | sample_i_calib     | B6      |         70 |          2476.75 |                   1172.5  |                   3802.81 |                             0.971429 |
|    40 | sample_i_calib     | B8      |         70 |          3217.75 |                   1247.97 |                   6273.9  |                             0.985714 |
|    41 | sample_i_calib     | B4      |         69 |          2349.5  |                   1096.19 |                   4221.64 |                             0.985507 |
|    41 | sample_i_calib     | B6      |         69 |          2486.5  |                   1172.5  |                   3802.81 |                             0.985507 |
|    41 | sample_i_calib     | B8      |         69 |          3389.5  |                   1247.97 |                   6273.9  |                             0.971014 |
|    42 | sample_i_calib     | B4      |         68 |          2461.5  |                   1096.19 |                   4221.64 |                             0.985294 |
|    42 | sample_i_calib     | B6      |         68 |          2562.5  |                   1172.5  |                   3802.81 |                             0.955882 |
|    42 | sample_i_calib     | B8      |         68 |          3225.75 |                   1247.97 |                   6273.9  |                             0.926471 |
|    44 | sample_i_analysis  | B4      |          7 |          2467    |                   1096.19 |                   4221.64 |                             0.857143 |
|    44 | sample_i_analysis  | B6      |          7 |          2355    |                   1172.5  |                   3802.81 |                             1        |
|    44 | sample_i_analysis  | B8      |          7 |          3255.5  |                   1247.97 |                   6273.9  |                             1        |
|    45 | sample_i_analysis  | B4      |         94 |          2254.5  |                   1096.19 |                   4221.64 |                             0.978723 |
|    45 | sample_i_analysis  | B6      |         94 |          2385.5  |                   1172.5  |                   3802.81 |                             0.968085 |
|    45 | sample_i_analysis  | B8      |         94 |          3289.5  |                   1247.97 |                   6273.9  |                             0.968085 |
|    46 | sample_i_analysis  | B4      |          1 |          2138    |                   1096.19 |                   4221.64 |                             1        |
|    46 | sample_i_analysis  | B6      |          1 |          2439.5  |                   1172.5  |                   3802.81 |                             1        |
|    46 | sample_i_analysis  | B8      |          1 |          2718    |                   1247.97 |                   6273.9  |                             1        |
|    47 | sample_i_analysis  | B4      |          9 |          2167    |                   1096.19 |                   4221.64 |                             1        |
|    47 | sample_i_analysis  | B6      |          9 |          2215    |                   1172.5  |                   3802.81 |                             1        |
|    47 | sample_i_analysis  | B8      |          9 |          3075.5  |                   1247.97 |                   6273.9  |                             0.888889 |
|    48 | sample_i_analysis  | B4      |         58 |          2327.5  |                   1096.19 |                   4221.64 |                             0.982759 |
|    48 | sample_i_analysis  | B6      |         58 |          2545.75 |                   1172.5  |                   3802.81 |                             0.948276 |
|    48 | sample_i_analysis  | B8      |         58 |          3303.25 |                   1247.97 |                   6273.9  |                             0.965517 |
|    49 | sample_i_analysis  | B4      |         56 |          2223.25 |                   1096.19 |                   4221.64 |                             0.964286 |
|    49 | sample_i_analysis  | B6      |         56 |          2289    |                   1172.5  |                   3802.81 |                             1        |
|    49 | sample_i_analysis  | B8      |         56 |          3127.75 |                   1247.97 |                   6273.9  |                             1        |
|    50 | sample_i_analysis  | B4      |         60 |          2443.5  |                   1096.19 |                   4221.64 |                             1        |
|    50 | sample_i_analysis  | B6      |         60 |          2290    |                   1172.5  |                   3802.81 |                             1        |
|    50 | sample_i_analysis  | B8      |         60 |          3284    |                   1247.97 |                   6273.9  |                             0.95     |
|    51 | sample_i_analysis  | B4      |         34 |          2237.25 |                   1096.19 |                   4221.64 |                             0.970588 |
|    51 | sample_i_analysis  | B6      |         34 |          2400.75 |                   1172.5  |                   3802.81 |                             0.970588 |
|    51 | sample_i_analysis  | B8      |         34 |          3405.25 |                   1247.97 |                   6273.9  |                             1        |
|    52 | sample_i_analysis  | B4      |         22 |          2171    |                   1096.19 |                   4221.64 |                             1        |
|    52 | sample_i_analysis  | B6      |         22 |          2568.75 |                   1172.5  |                   3802.81 |                             1        |
|    52 | sample_i_analysis  | B8      |         22 |          3299.25 |                   1247.97 |                   6273.9  |                             0.954545 |
|    53 | sample_i_analysis  | B4      |         59 |          2324.5  |                   1096.19 |                   4221.64 |                             0.983051 |
|    53 | sample_i_analysis  | B6      |         59 |          2380    |                   1172.5  |                   3802.81 |                             1        |
|    53 | sample_i_analysis  | B8      |         59 |          3321.5  |                   1247.97 |                   6273.9  |                             0.966102 |
|    54 | sample_i_analysis  | B4      |         50 |          2266.25 |                   1096.19 |                   4221.64 |                             1        |
|    54 | sample_i_analysis  | B6      |         50 |          2475    |                   1172.5  |                   3802.81 |                             0.98     |
|    54 | sample_i_analysis  | B8      |         50 |          3342.5  |                   1247.97 |                   6273.9  |                             0.98     |
|    55 | sample_i_analysis  | B4      |         44 |          2465.25 |                   1096.19 |                   4221.64 |                             1        |
|    55 | sample_i_analysis  | B6      |         44 |          2509.75 |                   1172.5  |                   3802.81 |                             1        |
|    55 | sample_i_analysis  | B8      |         44 |          3541.75 |                   1247.97 |                   6273.9  |                             0.954545 |
|    56 | sample_i_analysis  | B4      |         92 |          2363.75 |                   1096.19 |                   4221.64 |                             0.98913  |
|    56 | sample_i_analysis  | B6      |         92 |          2326.25 |                   1172.5  |                   3802.81 |                             0.978261 |
|    56 | sample_i_analysis  | B8      |         92 |          3247.5  |                   1247.97 |                   6273.9  |                             0.967391 |
|    57 | sample_i_analysis  | B4      |         64 |          2403.75 |                   1096.19 |                   4221.64 |                             0.984375 |
|    57 | sample_i_analysis  | B6      |         64 |          2532.25 |                   1172.5  |                   3802.81 |                             0.96875  |
|    57 | sample_i_analysis  | B8      |         64 |          3242    |                   1247.97 |                   6273.9  |                             0.96875  |
|    58 | sample_ii_analysis | B4      |         73 |          2365    |                   1096.19 |                   4221.64 |                             0.945205 |
|    58 | sample_ii_analysis | B6      |         73 |          2530    |                   1172.5  |                   3802.81 |                             0.972603 |
|    58 | sample_ii_analysis | B8      |         73 |          3265    |                   1247.97 |                   6273.9  |                             0.972603 |
|    59 | sample_ii_analysis | B4      |        763 |          2212    |                   1096.19 |                   4221.64 |                             0.976409 |
|    59 | sample_ii_analysis | B6      |        763 |          2253.5  |                   1172.5  |                   3802.81 |                             0.97772  |
|    59 | sample_ii_analysis | B8      |        763 |          3196.5  |                   1247.97 |                   6273.9  |                             0.984273 |
|    60 | sample_ii_analysis | B4      |        808 |          2628    |                   1096.19 |                   4221.64 |                             0.980198 |
|    60 | sample_ii_analysis | B6      |        808 |          2704.25 |                   1172.5  |                   3802.81 |                             0.983911 |
|    60 | sample_ii_analysis | B8      |        808 |          3539    |                   1247.97 |                   6273.9  |                             0.975248 |
|    61 | sample_ii_analysis | B4      |        933 |          2409.5  |                   1096.19 |                   4221.64 |                             0.984995 |
|    61 | sample_ii_analysis | B6      |        933 |          2580.5  |                   1172.5  |                   3802.81 |                             0.982851 |
|    61 | sample_ii_analysis | B8      |        933 |          3388    |                   1247.97 |                   6273.9  |                             0.978564 |
|    62 | sample_ii_analysis | B4      |        807 |          2342.5  |                   1096.19 |                   4221.64 |                             0.980173 |
|    62 | sample_ii_analysis | B6      |        807 |          2414    |                   1172.5  |                   3802.81 |                             0.977695 |
|    62 | sample_ii_analysis | B8      |        807 |          3313.5  |                   1247.97 |                   6273.9  |                             0.981413 |
|    63 | sample_ii_analysis | B4      |        370 |          2165    |                   1096.19 |                   4221.64 |                             0.981081 |
|    63 | sample_ii_analysis | B6      |        370 |          2242    |                   1172.5  |                   3802.81 |                             0.978378 |
|    63 | sample_ii_analysis | B8      |        370 |          3249.5  |                   1247.97 |                   6273.9  |                             0.983784 |
|    64 | sample_ii_calib    | B4      |        210 |          2038    |                   1096.19 |                   4221.64 |                             0.966667 |
|    64 | sample_ii_calib    | B6      |        210 |          2058.25 |                   1172.5  |                   3802.81 |                             0.966667 |
|    64 | sample_ii_calib    | B8      |        210 |          2977.25 |                   1247.97 |                   6273.9  |                             0.971429 |
|    65 | sample_ii_analysis | B4      |         66 |          1989    |                   1096.19 |                   4221.64 |                             0.954545 |
|    65 | sample_ii_analysis | B6      |         66 |          2181.25 |                   1172.5  |                   3802.81 |                             0.954545 |
|    65 | sample_ii_analysis | B8      |         66 |          3053.75 |                   1247.97 |                   6273.9  |                             0.954545 |

Run-64 strict-pair support:

|   run | method                                 |   n_pair_residuals |   sigma68_ns |   ci_low |   ci_high |
|------:|:---------------------------------------|-------------------:|-------------:|---------:|----------:|
|    64 | hgb_waveform_amp_shape_stave           |                630 |      1.05803 | 0.947379 |   1.15076 |
|    64 | feature_gated_waveform_amp_shape_stave |                630 |      1.17624 | 1.05186  |   1.3258  |
|    64 | cnn1d_waveform_amp_shape_stave         |                630 |      1.19274 | 1.06685  |   1.36736 |
|    64 | mlp_waveform_amp_shape_stave           |                630 |      1.21238 | 1.03255  |   1.36865 |
|    64 | ridge_waveform_amp_shape_stave         |                630 |      1.2831  | 1.16588  |   1.40555 |
|    64 | analytic_timewalk                      |                630 |      1.56539 | 1.42387  |   1.70712 |

## Model and leakage audit

| method                                 | model_family                   |   n_train_pulses |   n_features | feature_policy                                                                                 |
|:---------------------------------------|:-------------------------------|-----------------:|-------------:|:-----------------------------------------------------------------------------------------------|
| ridge_waveform_amp_shape_stave         | ridge                          |            11444 |           32 | same as waveform_amp_shape, except explicit downstream stave one-hot is intentionally included |
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees         |            11444 |           32 | same as waveform_amp_shape, except explicit downstream stave one-hot is intentionally included |
| mlp_waveform_amp_shape_stave           | mlp                            |            11444 |           32 | same as waveform_amp_shape, except explicit downstream stave one-hot is intentionally included |
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                         |            11444 |           32 | same as waveform_amp_shape, except explicit downstream stave one-hot is intentionally included |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture |            11444 |           32 | same as waveform_amp_shape, except explicit downstream stave one-hot is intentionally included |

Checks:

- Train runs and evaluation runs are disjoint by construction:
  `[]`.
- Sample-I and run 64 do not enter S02 template construction, S03 analytic
  coefficient fitting, feature scaling, ridge alpha selection, or neural/boosted
  model fitting.
- Event ids are file/run-local strings and are excluded from every feature
  vector.  They are used only for same-event residual grouping and bootstrapping.

## Systematics and caveats

- The endpoint is internal same-particle closure, not an external beam clock.
  A lower `sigma68` is evidence for relative timing consistency, not by itself
  absolute timing truth.
- The Sample-I amplitude distribution is only partly covered by Sample-II
  training support in high-amplitude tails.  The report therefore treats the
  result as an adoption gate, not a production replacement.
- Stave one-hot can encode detector-condition differences.  This is allowed in
  the P03f family because it was part of the prior winner, but it is also the
  main artifact risk when crossing sample families.
- Run 64 is evaluable, but it is a single diagnostic run with 630 pair residuals.  Its uncertainty is therefore event-bootstrap dominated rather than run-block dominated.
- Bootstrap intervals resample runs for pooled Sample-I estimates and events
  within run for split-by-run rows.  They do not include a second model-selection
  loop beyond the fixed method panel.

## Verdict

`result.json` names **`cnn1d_waveform_amp_shape_stave`** as the winner for the
primary Sample-I transfer endpoint.  The adoption decision is
**`adopt_for_sample_i_and_run64_support_matched_rows`**: The frozen Sample-II learned residual correction passes the Sample-I/run-64 transfer gate.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03_followup_2412_transfer_gate.py --config configs/s03_followup_2412_transfer_gate.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`,
`reproduction_match_table.csv`, `pairwise_residuals.csv`,
`sample_i_pooled_summary.csv`, `pooled_eval_summary.csv`,
`per_run_summary.csv`, `amplitude_support.csv`, `model_diagnostics.csv`, and
`input_sha256.csv`.
