# S14g: veto-ladder energy acceptance calibration

- **Ticket:** 1781051226.621.082271da
- **Worker:** testbeam-laptop-3
- **Config:** `configs/s14g_1781051226_621_082271da_veto_ladder_energy_acceptance.yaml`
- **Raw input:** `data/root/root`
- **Git commit at run:** `41365a704c10a5dbff3bbbe712f7b20bd2b64370`

## Abstract

This study asks whether the P09/S10/S16/P07 veto ladder is better interpreted as an
energy/PID support-acceptance calibration than as an energy-ordering improvement.  I
rebuilt the B-stack selected-pulse population from raw ROOT, fitted all accept/reject
rules with complete runs held out, and compared a transparent sequential veto ladder
to ridge, gradient-boosted tree, MLP, 1D-CNN, and a new residual-gated ensemble
selector.  The selectors were trained on pulse atoms only; stave/depth labels, run
numbers, event identifiers, and PID labels were excluded from the model feature set.

The named winner in `result.json` is **new_residual_gated_ensemble**.  In the nominal `center_4cm`
geometry it has energy-proxy res68 `0.00675` with run-block 95% CI
`[0.0061044, 0.0072673]` and acceptance `0.44658`.  The traditional transparent ladder
has energy-proxy res68 `0.00689` and acceptance `0.44437`.

## Raw-ROOT reproduction gate

The reproduced number is the selected B-stave pulse count from raw `h101/HRDv`.
For each configured B physical channel `B2/B4/B6/B8 = 0/2/4/6`, the script subtracts
the median of samples 0--3 and selects pulses satisfying

`max_t(HRDv_t - median(HRDv_0..3)) > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| all configured selected B-stave pulses | 640,737 | 640,737 | +0 | true |

Per-run selected counts:

|   run | run_group          |   events_total |   selected_pulses |
|------:|:-------------------|---------------:|------------------:|
|    31 | sample_i_calib     |          39990 |             27871 |
|    32 | sample_i_calib     |          41921 |             28240 |
|    33 | sample_i_calib     |          57173 |             48737 |
|    34 | sample_i_calib     |          39765 |             34118 |
|    35 | sample_i_calib     |          27786 |             11667 |
|    36 | sample_i_calib     |          21764 |             10391 |
|    37 | sample_i_calib     |          50513 |             24537 |
|    39 | sample_i_calib     |          30321 |             14218 |
|    40 | sample_i_calib     |          32613 |             14708 |
|    41 | sample_i_calib     |          33997 |             16146 |
|    42 | sample_i_calib     |          33972 |             18112 |
|    44 | sample_i_analysis  |           4294 |              2038 |
|    45 | sample_i_analysis  |          48181 |             24333 |
|    46 | sample_i_analysis  |           1441 |               687 |
|    47 | sample_i_analysis  |          10970 |              5276 |
|    48 | sample_i_analysis  |          31713 |             14000 |
|    49 | sample_i_analysis  |          32354 |             14815 |
|    50 | sample_i_analysis  |          44804 |             35217 |
|    51 | sample_i_analysis  |          20569 |             14740 |
|    52 | sample_i_analysis  |          10005 |              7152 |
|    53 | sample_i_analysis  |          39612 |             32200 |
|    54 | sample_i_analysis  |          37413 |             30440 |
|    55 | sample_i_analysis  |          24416 |             17387 |
|    56 | sample_i_analysis  |          51823 |             40148 |
|    57 | sample_i_analysis  |          31284 |             13833 |
|    58 | sample_ii_analysis |          34141 |             16781 |
|    59 | sample_ii_analysis |          42303 |             21377 |
|    60 | sample_ii_analysis |          36074 |             17029 |
|    61 | sample_ii_analysis |          36535 |             18965 |
|    62 | sample_ii_analysis |          37584 |             19089 |
|    63 | sample_ii_analysis |          37030 |             18817 |
|    64 | sample_ii_calib    |          35943 |             14630 |
|    65 | sample_ii_analysis |          38424 |             13038 |

## Data construction

For event `i`, stave `s`, and sample `t`, the even-channel waveform is

`x_ist = HRDv_even,ist - median(HRDv_even,is0..is3)`.

The duplicate-readout reference is the independent odd-channel negative lobe,

`y_is = sum_t max(-(HRDv_odd,ist - median(HRDv_odd,is0..is3)), 0)`.

This target is used only to define the support label and evaluation residuals; no
selector receives the odd channel, event number, run number, or stave/depth identity.
The support label in a training fold is

`z_i = 1[L_trad(i)=accept] * 1[|log Q_even,i - log Q_odd,i| <= q_tau]`,

where `q_tau` is the training-fold `0.72` quantile.  ML selectors are
thresholded in each fold to the training acceptance of the transparent ladder, so
lower residual width cannot be obtained by retaining an arbitrarily tiny sample.

## Veto ladder

The traditional method is a sequential transparent ladder:

1. **P09 anomaly:** high q-tail, abnormal half-width, or edge peak-time samples.
2. **S10 pile-up:** at least three selected B staves or a broad high-tail waveform.
3. **S16 baseline/lowering:** wide pretrigger baseline RMS.
4. **P07 saturation:** large saturation depth or peak amplitude above the ADC ceiling.

Thresholds are refit inside the training runs of each grouped fold and then applied
unchanged to the held-out runs.  The `traditional_veto_family` column records the
first family to fire.

## Energy proxy and metrics

For geometry `g`, the monotonic range-energy anchor for stave `s` is

`E_gs = interp(R_gs, R_PSTAR, E_PSTAR)`,

with PSTAR plastic-scintillator ranges converted from g cm^-2 to cm using
`rho = 1.032 g cm^-3`.  The duplicate-readout target and even-channel proxy are

`log E*_is = log E_gs + 0.25 (log Q_odd,is - median(log Q_odd))`,

`log Ehat_is = log E_gs + 0.25 (log Q_even,is - median(log Q_odd))`.

The primary width is `Q_0.68(|log Ehat - log E*|)` among accepted rows.
The charge-composition shift is the accepted median `log Q_odd` minus the full
population median.  The depth-order violation rate is the fraction of adjacent
accepted depth medians within each held-out run for which the downstream median is
not larger than the upstream median.  Confidence intervals resample held-out runs
with replacement.

## Rate residual model

The A/B coincidence support covariate is a run-level held-out residual.  For run `r`,

`p_r = (N(A_any and B_any) + 1/2)/(N(B_any)+1)`.

A weighted ridge model predicts `logit(p_r)` from current, sample setting, B-only
occupancy, and topology fractions; selectors see only the held-out residual
`100*(p_r - p_hat_r)`.

|   fold | heldout_runs   |   n_train_runs |   rate_rmse_pp |
|-------:|:---------------|---------------:|---------------:|
|      0 | 44,48,54,58,65 |             16 |       0.707757 |
|      1 | 49,53,59,63    |             17 |       0.276078 |
|      2 | 45,50,55,60    |             17 |       1.0092   |
|      3 | 46,51,56,61    |             17 |       0.382133 |
|      4 | 47,52,57,62    |             17 |      35.7204   |

Rate table:

|   run | run_group          |   current_nA |   b_any_events |   target_rate |   pred_rate_traditional |   rate_residual_pp |
|------:|:-------------------|-------------:|---------------:|--------------:|------------------------:|-------------------:|
|    44 | sample_i_analysis  |           20 |           1912 |    0.0394668  |             0.0206858   |         1.8781     |
|    45 | sample_i_analysis  |           20 |          23004 |    0.0392741  |             0.020308    |         1.8966     |
|    46 | sample_i_analysis  |            2 |            661 |    0.0294562  |             0.000968793 |         2.84874    |
|    47 | sample_i_analysis  |            2 |           5141 |    0.0356865  |             0.98636     |       -95.0674     |
|    48 | sample_i_analysis  |           20 |          13167 |    0.0424894  |             0.0284168   |         1.40726    |
|    49 | sample_i_analysis  |           20 |          13919 |    0.0395474  |             0.0409987   |        -0.145129   |
|    50 | sample_i_analysis  |           20 |          34251 |    0.00480264 |             0.00188359  |         0.291904   |
|    51 | sample_i_analysis  |           20 |          14291 |    0.00297369 |             0.00277777  |         0.0195918  |
|    52 | sample_i_analysis  |           20 |           6933 |    0.00151428 |             0.000434879 |         0.10794    |
|    53 | sample_i_analysis  |           20 |          31385 |    0.00116294 |             0.00496998  |        -0.380704   |
|    54 | sample_i_analysis  |           20 |          29638 |    0.00163636 |             0.00451824  |        -0.288189   |
|    55 | sample_i_analysis  |           20 |          16820 |    0.00270495 |             0.00275144  |        -0.00464838 |
|    56 | sample_i_analysis  |           20 |          38913 |    0.00558925 |             0.00239572  |         0.319353   |
|    57 | sample_i_analysis  |           20 |          12925 |    0.0410413  |             0.110298    |        -6.92568    |
|    58 | sample_ii_analysis |           20 |          15890 |    0.00437354 |             0.00336732  |         0.100622   |
|    59 | sample_ii_analysis |           20 |          13863 |    0.00155078 |             0.00247853  |        -0.0927752  |
|    60 | sample_ii_analysis |           20 |          10139 |    0.0020217  |             0.00100753  |         0.101417   |
|    61 | sample_ii_analysis |           20 |          11282 |    0.00226004 |             0.00101517  |         0.124486   |
|    62 | sample_ii_analysis |           20 |          11902 |    0.00155423 |             0.00330038  |        -0.174615   |
|    63 | sample_ii_analysis |           20 |          14756 |    0.00545504 |             0.00331933  |         0.213571   |
|    65 | sample_ii_analysis |           20 |          11875 |    0.00509431 |             0.00779405  |        -0.269974   |

## Fold diagnostics

|   fold | heldout_runs   |   n_train |   n_test |   traditional_train_acceptance |   support_target_positive_rate |   new_arch_test_acceptance |
|-------:|:---------------|----------:|---------:|-------------------------------:|-------------------------------:|---------------------------:|
|      0 | 44,48,55,56    |    303723 |    73550 |                       0.464127 |                       0.422168 |                   0.435772 |
|      1 | 47,50,51,63    |    303231 |    74042 |                       0.482197 |                       0.438923 |                   0.454553 |
|      2 | 49,53,61,65    |    298275 |    78998 |                       0.427636 |                       0.390529 |                   0.460404 |
|      3 | 46,52,54,58,62 |    303128 |    74145 |                       0.435542 |                       0.39324  |                   0.46641  |
|      4 | 45,57,59,60    |    300735 |    76538 |                       0.439237 |                       0.41211  |                   0.41578  |

## Main results

| geometry   | method                      | acceptance | acceptance_ci95    | charge_proxy_log_shift | charge_proxy_log_shift_ci95 | energy_proxy_res68 | energy_proxy_res68_ci95 | depth_order_violation_rate | depth_order_violation_rate_ci95 | delta_energy_res68_vs_traditional | delta_energy_res68_vs_traditional_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| center_2cm | new_residual_gated_ensemble | 0.44658    | [0.40409, 0.49566] | -0.19188               | [-0.25353, -0.03383]        | 0.0067459          | [0.0059296, 0.0071999]  | 0                          | [0, 0]                          | -0.00014402                       | [-0.00027373, -4.363e-05]              |
| center_2cm | mlp_support                 | 0.43868    | [0.39244, 0.48301] | -0.1795                | [-0.24885, -0.0099244]      | 0.0067974          | [0.0062559, 0.0072791]  | 0.017241                   | [0, 0.032258]                   | -9.2553e-05                       | [-0.00024603, -1.9697e-08]             |
| center_2cm | gradient_boosted_trees      | 0.44391    | [0.40915, 0.49766] | -0.22429               | [-0.27734, -0.057128]       | 0.0068549          | [0.006303, 0.0072973]   | 0.031746                   | [0, 0.055556]                   | -3.5028e-05                       | [-7.8581e-05, -4.4307e-06]             |
| center_2cm | traditional_veto_ladder     | 0.44437    | [0.39944, 0.48353] | -0.23082               | [-0.30593, -0.092825]       | 0.0068899          | [0.0064109, 0.0073181]  | 0.031746                   | [0, 0.055556]                   | 0                                 | [0, 0]                                 |
| center_2cm | ridge_support               | 0.44618    | [0.40666, 0.49979] | -0.17858               | [-0.255, -0.025262]         | 0.0069098          | [0.0063176, 0.0073592]  | 0.015873                   | [0, 0.030303]                   | 1.9894e-05                        | [-0.00011309, 0.00013055]              |
| center_2cm | cnn_1d_support              | 0.45014    | [0.4074, 0.4987]   | -0.19626               | [-0.2672, -0.025043]        | 0.0070827          | [0.0060377, 0.0076597]  | 0                          | [0, 0]                          | 0.00019275                        | [-0.00013587, 0.00037072]              |
| center_2cm | shuffled_target_hgb_control | 0.55034    | [0.46187, 0.64311] | -0.0031453             | [-0.28834, 0.097389]        | 0.010893           | [0.0097198, 0.012353]   | 0                          | [0, 0]                          | 0.0040034                         | [0.0027556, 0.0060277]                 |
| center_4cm | new_residual_gated_ensemble | 0.44658    | [0.41559, 0.49733] | -0.19188               | [-0.26976, -0.040113]       | 0.0067459          | [0.0061044, 0.0072673]  | 0                          | [0, 0]                          | -0.00014402                       | [-0.00029884, -4.0731e-05]             |
| center_4cm | mlp_support                 | 0.43868    | [0.40067, 0.48594] | -0.1795                | [-0.25983, -0.041962]       | 0.0067974          | [0.0061937, 0.0072931]  | 0.017241                   | [0, 0.032258]                   | -9.2553e-05                       | [-0.00020842, -5.7347e-07]             |
| center_4cm | gradient_boosted_trees      | 0.44391    | [0.40838, 0.5084]  | -0.22429               | [-0.29866, -0.026979]       | 0.0068549          | [0.0061749, 0.0072936]  | 0.031746                   | [0, 0.055556]                   | -3.5028e-05                       | [-6.6532e-05, -6.3294e-06]             |
| center_4cm | traditional_veto_ladder     | 0.44437    | [0.40596, 0.49329] | -0.23082               | [-0.31558, -0.087604]       | 0.0068899          | [0.0064294, 0.0072418]  | 0.031746                   | [0, 0.055556]                   | 0                                 | [0, 0]                                 |
| center_4cm | ridge_support               | 0.44618    | [0.39731, 0.49664] | -0.17858               | [-0.2489, -0.01254]         | 0.0069098          | [0.0062901, 0.0073694]  | 0.015873                   | [0, 0.030303]                   | 1.9894e-05                        | [-0.00014492, 0.00010323]              |
| center_4cm | cnn_1d_support              | 0.45014    | [0.40544, 0.5195]  | -0.19626               | [-0.25525, -0.029108]       | 0.0070827          | [0.0062251, 0.0076352]  | 0                          | [0, 0]                          | 0.00019275                        | [-0.00019662, 0.00038297]              |
| center_4cm | shuffled_target_hgb_control | 0.55034    | [0.45642, 0.62673] | -0.0031453             | [-0.22598, 0.11794]         | 0.010893           | [0.0098019, 0.012645]   | 0                          | [0, 0]                          | 0.0040034                         | [0.002655, 0.0067494]                  |
| zero_4cm   | new_residual_gated_ensemble | 0.44658    | [0.40948, 0.48544] | -0.19188               | [-0.26705, -0.037372]       | 0.0067459          | [0.0062005, 0.0072235]  | 0                          | [0, 0]                          | -0.00014402                       | [-0.00030162, -2.7293e-05]             |
| zero_4cm   | mlp_support                 | 0.43868    | [0.40459, 0.47927] | -0.1795                | [-0.26355, -0.018258]       | 0.0067974          | [0.006144, 0.0072707]   | 0                          | [0, 0]                          | -9.2553e-05                       | [-0.00021759, 2.6822e-05]              |
| zero_4cm   | gradient_boosted_trees      | 0.44391    | [0.40924, 0.4841]  | -0.22429               | [-0.30838, -0.067908]       | 0.0068549          | [0.0064154, 0.0072687]  | 0.015873                   | [0, 0.030303]                   | -3.5028e-05                       | [-7.7801e-05, -9.8275e-06]             |
| zero_4cm   | traditional_veto_ladder     | 0.44437    | [0.40431, 0.48754] | -0.23082               | [-0.29495, -0.053509]       | 0.0068899          | [0.0064041, 0.0072664]  | 0.015873                   | [0, 0.033333]                   | 0                                 | [0, 0]                                 |
| zero_4cm   | ridge_support               | 0.44618    | [0.40083, 0.4999]  | -0.17858               | [-0.24861, -0.039394]       | 0.0069098          | [0.0063701, 0.007303]   | 0                          | [0, 0]                          | 1.9894e-05                        | [-0.00011285, 0.00012344]              |
| zero_4cm   | cnn_1d_support              | 0.45014    | [0.40203, 0.51864] | -0.19626               | [-0.25943, -0.028525]       | 0.0070827          | [0.0063413, 0.0076407]  | 0                          | [0, 0]                          | 0.00019275                        | [-0.00022246, 0.0003575]               |
| zero_4cm   | shuffled_target_hgb_control | 0.55034    | [0.46613, 0.62282] | -0.0031453             | [-0.19436, 0.12688]         | 0.010893           | [0.009676, 0.012572]    | 0                          | [0, 0]                          | 0.0040034                         | [0.0029086, 0.0060237]                 |

## Veto-family acceptance map

Rows below condition on the transparent ladder's first veto family.  ML selectors
that accept many rows in a rejected family are not automatically wrong; the row
shows where they relax the transparent ladder and what residual width follows.

| geometry   | method                      | veto_family           | family_population | family_accepted | family_acceptance | charge_proxy_log_shift | energy_proxy_res68 | depth_order_violation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| center_2cm | cnn_1d_support              | accepted              | 167648            | 146339          | 0.87289           | -0.039209              | 0.0064684          | 0.031746                   |
| center_2cm | cnn_1d_support              | p07_saturation        | 102343            | 3627            | 0.03544           | -0.078253              | 0.010312           |                            |
| center_2cm | cnn_1d_support              | p09_anomaly           | 44709             | 8811            | 0.19707           | 0.55117                | 0.0087449          | 0.14815                    |
| center_2cm | cnn_1d_support              | s10_pileup            | 40823             | 10681           | 0.26164           | 0.56541                | 0.0080419          | 0                          |
| center_2cm | cnn_1d_support              | s16_baseline_lowering | 21750             | 367             | 0.016874          | 1.5623                 | 0.085573           | 0                          |
| center_2cm | gradient_boosted_trees      | accepted              | 167648            | 166101          | 0.99077           | 0.0031708              | 0.0068189          | 0.031746                   |
| center_2cm | gradient_boosted_trees      | p07_saturation        | 102343            | 500             | 0.0048855         | -0.089961              | 0.0094062          | 0                          |
| center_2cm | gradient_boosted_trees      | p09_anomaly           | 44709             | 409             | 0.009148          | 0.15421                | 0.0081126          | 0                          |
| center_2cm | gradient_boosted_trees      | s10_pileup            | 40823             | 316             | 0.0077407         | 0.599                  | 0.0086495          | 0                          |
| center_2cm | gradient_boosted_trees      | s16_baseline_lowering | 21750             | 150             | 0.0068966         | 0.99448                | 0.10882            | 0                          |
| center_2cm | mlp_support                 | accepted              | 167648            | 156807          | 0.93533           | 0.016926               | 0.0065593          | 0.017241                   |
| center_2cm | mlp_support                 | p07_saturation        | 102343            | 2703            | 0.026411          | -0.085379              | 0.0094933          | 0                          |
| center_2cm | mlp_support                 | p09_anomaly           | 44709             | 1884            | 0.042139          | 0.2087                 | 0.0074914          | 0.051282                   |
| center_2cm | mlp_support                 | s10_pileup            | 40823             | 3952            | 0.096808          | 0.65419                | 0.0084397          | 0                          |
| center_2cm | mlp_support                 | s16_baseline_lowering | 21750             | 157             | 0.0072184         | 1.4667                 | 0.051194           |                            |
| center_2cm | new_residual_gated_ensemble | accepted              | 167648            | 160714          | 0.95864           | 0.012581               | 0.0065821          | 0.031746                   |
| center_2cm | new_residual_gated_ensemble | p07_saturation        | 102343            | 406             | 0.0039671         | -0.078471              | 0.010552           |                            |
| center_2cm | new_residual_gated_ensemble | p09_anomaly           | 44709             | 4132            | 0.09242           | 0.56454                | 0.0085205          | 0.13514                    |
| center_2cm | new_residual_gated_ensemble | s10_pileup            | 40823             | 3177            | 0.077824          | 0.54739                | 0.007702           | 0.037037                   |
| center_2cm | new_residual_gated_ensemble | s16_baseline_lowering | 21750             | 54              | 0.0024828         | 1.5029                 | 0.10008            | 0                          |
| center_2cm | ridge_support               | accepted              | 167648            | 148370          | 0.88501           | -0.018719              | 0.0063905          | 0.031746                   |
| center_2cm | ridge_support               | p07_saturation        | 102343            | 4076            | 0.039827          | -0.076228              | 0.0096768          |                            |
| center_2cm | ridge_support               | p09_anomaly           | 44709             | 8049            | 0.18003           | 0.5123                 | 0.0084987          | 0.1                        |
| center_2cm | ridge_support               | s10_pileup            | 40823             | 7834            | 0.1919            | 0.60748                | 0.0083904          | 0                          |
| center_2cm | ridge_support               | s16_baseline_lowering | 21750             | 2               | 9.1954e-05        | 1.4843                 | 0.071781           |                            |
| center_2cm | shuffled_target_hgb_control | accepted              | 167648            | 86842           | 0.518             | -0.10165               | 0.0064827          | 0.016129                   |
| center_2cm | shuffled_target_hgb_control | p07_saturation        | 102343            | 64760           | 0.63277           | 0.0041266              | 0.011582           | 0                          |
| center_2cm | shuffled_target_hgb_control | p09_anomaly           | 44709             | 19593           | 0.43823           | -0.062163              | 0.027245           | 0.016667                   |
| center_2cm | shuffled_target_hgb_control | s10_pileup            | 40823             | 21576           | 0.52853           | -0.079178              | 0.019549           | 0                          |
| center_2cm | shuffled_target_hgb_control | s16_baseline_lowering | 21750             | 14857           | 0.68308           | -0.03671               | 0.39802            | 0.18868                    |
| center_2cm | traditional_veto_ladder     | accepted              | 167648            | 167648          | 1                 | 0                      | 0.0068899          | 0.031746                   |
| center_2cm | traditional_veto_ladder     | p07_saturation        | 102343            | 0               | 0                 |                        |                    |                            |
| center_2cm | traditional_veto_ladder     | p09_anomaly           | 44709             | 0               | 0                 |                        |                    |                            |
| center_2cm | traditional_veto_ladder     | s10_pileup            | 40823             | 0               | 0                 |                        |                    |                            |
| center_2cm | traditional_veto_ladder     | s16_baseline_lowering | 21750             | 0               | 0                 |                        |                    |                            |
| center_4cm | cnn_1d_support              | accepted              | 167648            | 146339          | 0.87289           | -0.039209              | 0.0064684          | 0.031746                   |
| center_4cm | cnn_1d_support              | p07_saturation        | 102343            | 3627            | 0.03544           | -0.078253              | 0.010312           |                            |
| center_4cm | cnn_1d_support              | p09_anomaly           | 44709             | 8811            | 0.19707           | 0.55117                | 0.0087449          | 0.14815                    |
| center_4cm | cnn_1d_support              | s10_pileup            | 40823             | 10681           | 0.26164           | 0.56541                | 0.0080419          | 0                          |
| center_4cm | cnn_1d_support              | s16_baseline_lowering | 21750             | 367             | 0.016874          | 1.5623                 | 0.085573           | 0                          |
| center_4cm | gradient_boosted_trees      | accepted              | 167648            | 166101          | 0.99077           | 0.0031708              | 0.0068189          | 0.031746                   |
| center_4cm | gradient_boosted_trees      | p07_saturation        | 102343            | 500             | 0.0048855         | -0.089961              | 0.0094062          | 0                          |
| center_4cm | gradient_boosted_trees      | p09_anomaly           | 44709             | 409             | 0.009148          | 0.15421                | 0.0081126          | 0                          |
| center_4cm | gradient_boosted_trees      | s10_pileup            | 40823             | 316             | 0.0077407         | 0.599                  | 0.0086495          | 0                          |
| center_4cm | gradient_boosted_trees      | s16_baseline_lowering | 21750             | 150             | 0.0068966         | 0.99448                | 0.10882            | 0                          |
| center_4cm | mlp_support                 | accepted              | 167648            | 156807          | 0.93533           | 0.016926               | 0.0065593          | 0.034483                   |
| center_4cm | mlp_support                 | p07_saturation        | 102343            | 2703            | 0.026411          | -0.085379              | 0.0094933          | 0                          |
| center_4cm | mlp_support                 | p09_anomaly           | 44709             | 1884            | 0.042139          | 0.2087                 | 0.0074914          | 0.051282                   |
| center_4cm | mlp_support                 | s10_pileup            | 40823             | 3952            | 0.096808          | 0.65419                | 0.0084397          | 0                          |
| center_4cm | mlp_support                 | s16_baseline_lowering | 21750             | 157             | 0.0072184         | 1.4667                 | 0.051194           |                            |
| center_4cm | new_residual_gated_ensemble | accepted              | 167648            | 160714          | 0.95864           | 0.012581               | 0.0065821          | 0.031746                   |
| center_4cm | new_residual_gated_ensemble | p07_saturation        | 102343            | 406             | 0.0039671         | -0.078471              | 0.010552           |                            |
| center_4cm | new_residual_gated_ensemble | p09_anomaly           | 44709             | 4132            | 0.09242           | 0.56454                | 0.0085205          | 0.13514                    |
| center_4cm | new_residual_gated_ensemble | s10_pileup            | 40823             | 3177            | 0.077824          | 0.54739                | 0.007702           | 0.037037                   |
| center_4cm | new_residual_gated_ensemble | s16_baseline_lowering | 21750             | 54              | 0.0024828         | 1.5029                 | 0.10008            | 0                          |
| center_4cm | ridge_support               | accepted              | 167648            | 148370          | 0.88501           | -0.018719              | 0.0063905          | 0.031746                   |
| center_4cm | ridge_support               | p07_saturation        | 102343            | 4076            | 0.039827          | -0.076228              | 0.0096768          |                            |
| center_4cm | ridge_support               | p09_anomaly           | 44709             | 8049            | 0.18003           | 0.5123                 | 0.0084987          | 0.1                        |
| center_4cm | ridge_support               | s10_pileup            | 40823             | 7834            | 0.1919            | 0.60748                | 0.0083904          | 0                          |
| center_4cm | ridge_support               | s16_baseline_lowering | 21750             | 2               | 9.1954e-05        | 1.4843                 | 0.071781           |                            |
| center_4cm | shuffled_target_hgb_control | accepted              | 167648            | 86842           | 0.518             | -0.10165               | 0.0064827          | 0.016129                   |
| center_4cm | shuffled_target_hgb_control | p07_saturation        | 102343            | 64760           | 0.63277           | 0.0041266              | 0.011582           | 0                          |
| center_4cm | shuffled_target_hgb_control | p09_anomaly           | 44709             | 19593           | 0.43823           | -0.062163              | 0.027245           | 0.016667                   |
| center_4cm | shuffled_target_hgb_control | s10_pileup            | 40823             | 21576           | 0.52853           | -0.079178              | 0.019549           | 0                          |
| center_4cm | shuffled_target_hgb_control | s16_baseline_lowering | 21750             | 14857           | 0.68308           | -0.03671               | 0.39802            | 0.18868                    |
| center_4cm | traditional_veto_ladder     | accepted              | 167648            | 167648          | 1                 | 0                      | 0.0068899          | 0.031746                   |
| center_4cm | traditional_veto_ladder     | p07_saturation        | 102343            | 0               | 0                 |                        |                    |                            |
| center_4cm | traditional_veto_ladder     | p09_anomaly           | 44709             | 0               | 0                 |                        |                    |                            |
| center_4cm | traditional_veto_ladder     | s10_pileup            | 40823             | 0               | 0                 |                        |                    |                            |
| center_4cm | traditional_veto_ladder     | s16_baseline_lowering | 21750             | 0               | 0                 |                        |                    |                            |
| zero_4cm   | cnn_1d_support              | accepted              | 167648            | 146339          | 0.87289           | -0.039209              | 0.0064684          | 0                          |
| zero_4cm   | cnn_1d_support              | p07_saturation        | 102343            | 3627            | 0.03544           | -0.078253              | 0.010312           |                            |
| zero_4cm   | cnn_1d_support              | p09_anomaly           | 44709             | 8811            | 0.19707           | 0.55117                | 0.0087449          | 0.11111                    |
| zero_4cm   | cnn_1d_support              | s10_pileup            | 40823             | 10681           | 0.26164           | 0.56541                | 0.0080419          | 0                          |
| zero_4cm   | cnn_1d_support              | s16_baseline_lowering | 21750             | 367             | 0.016874          | 1.5623                 | 0.085573           | 0                          |
| zero_4cm   | gradient_boosted_trees      | accepted              | 167648            | 166101          | 0.99077           | 0.0031708              | 0.0068189          | 0.015873                   |
| zero_4cm   | gradient_boosted_trees      | p07_saturation        | 102343            | 500             | 0.0048855         | -0.089961              | 0.0094062          | 0                          |
| zero_4cm   | gradient_boosted_trees      | p09_anomaly           | 44709             | 409             | 0.009148          | 0.15421                | 0.0081126          | 0                          |
| zero_4cm   | gradient_boosted_trees      | s10_pileup            | 40823             | 316             | 0.0077407         | 0.599                  | 0.0086495          | 0                          |
| zero_4cm   | gradient_boosted_trees      | s16_baseline_lowering | 21750             | 150             | 0.0068966         | 0.99448                | 0.10882            | 0                          |
| zero_4cm   | mlp_support                 | accepted              | 167648            | 156807          | 0.93533           | 0.016926               | 0.0065593          | 0                          |
| zero_4cm   | mlp_support                 | p07_saturation        | 102343            | 2703            | 0.026411          | -0.085379              | 0.0094933          | 0                          |
| zero_4cm   | mlp_support                 | p09_anomaly           | 44709             | 1884            | 0.042139          | 0.2087                 | 0.0074914          | 0.025641                   |
| zero_4cm   | mlp_support                 | s10_pileup            | 40823             | 3952            | 0.096808          | 0.65419                | 0.0084397          | 0                          |
| zero_4cm   | mlp_support                 | s16_baseline_lowering | 21750             | 157             | 0.0072184         | 1.4667                 | 0.051194           |                            |
| zero_4cm   | new_residual_gated_ensemble | accepted              | 167648            | 160714          | 0.95864           | 0.012581               | 0.0065821          | 0                          |
| zero_4cm   | new_residual_gated_ensemble | p07_saturation        | 102343            | 406             | 0.0039671         | -0.078471              | 0.010552           |                            |
| zero_4cm   | new_residual_gated_ensemble | p09_anomaly           | 44709             | 4132            | 0.09242           | 0.56454                | 0.0085205          | 0.13514                    |
| zero_4cm   | new_residual_gated_ensemble | s10_pileup            | 40823             | 3177            | 0.077824          | 0.54739                | 0.007702           | 0.018519                   |
| zero_4cm   | new_residual_gated_ensemble | s16_baseline_lowering | 21750             | 54              | 0.0024828         | 1.5029                 | 0.10008            | 0                          |
| zero_4cm   | ridge_support               | accepted              | 167648            | 148370          | 0.88501           | -0.018719              | 0.0063905          | 0.015873                   |
| zero_4cm   | ridge_support               | p07_saturation        | 102343            | 4076            | 0.039827          | -0.076228              | 0.0096768          |                            |
| zero_4cm   | ridge_support               | p09_anomaly           | 44709             | 8049            | 0.18003           | 0.5123                 | 0.0084987          | 0.06                       |
| zero_4cm   | ridge_support               | s10_pileup            | 40823             | 7834            | 0.1919            | 0.60748                | 0.0083904          | 0                          |
| zero_4cm   | ridge_support               | s16_baseline_lowering | 21750             | 2               | 9.1954e-05        | 1.4843                 | 0.071781           |                            |
| zero_4cm   | shuffled_target_hgb_control | accepted              | 167648            | 86842           | 0.518             | -0.10165               | 0.0064827          | 0.016129                   |
| zero_4cm   | shuffled_target_hgb_control | p07_saturation        | 102343            | 64760           | 0.63277           | 0.0041266              | 0.011582           | 0                          |
| zero_4cm   | shuffled_target_hgb_control | p09_anomaly           | 44709             | 19593           | 0.43823           | -0.062163              | 0.027245           | 0.016667                   |
| zero_4cm   | shuffled_target_hgb_control | s10_pileup            | 40823             | 21576           | 0.52853           | -0.079178              | 0.019549           | 0                          |
| zero_4cm   | shuffled_target_hgb_control | s16_baseline_lowering | 21750             | 14857           | 0.68308           | -0.03671               | 0.39802            | 0.09434                    |
| zero_4cm   | traditional_veto_ladder     | accepted              | 167648            | 167648          | 1                 | 0                      | 0.0068899          | 0.015873                   |
| zero_4cm   | traditional_veto_ladder     | p07_saturation        | 102343            | 0               | 0                 |                        |                    |                            |
| zero_4cm   | traditional_veto_ladder     | p09_anomaly           | 44709             | 0               | 0                 |                        |                    |                            |
| zero_4cm   | traditional_veto_ladder     | s10_pileup            | 40823             | 0               | 0                 |                        |                    |                            |
| zero_4cm   | traditional_veto_ladder     | s16_baseline_lowering | 21750             | 0               | 0                 |                        |                    |                            |

## Systematics and caveats

This remains a duplicate-readout and monotonic range-proxy study, not an absolute
calorimetric energy or particle-ID calibration.  The PSTAR term only anchors the
expected ordering of B2/B4/B6/B8; the charge term is an internal even/odd closure
proxy.  The rate residual is run-level, so it cannot see event-scale beam-current
microstructure.  ML features deliberately exclude run, event, and depth identifiers,
which makes the test conservative but also prevents a selector from learning genuine
geometry-specific inefficiencies.  The shuffled-target HGB control is retained as a
leakage sentinel; a real selector must beat it by run-block confidence intervals and
not merely by point estimate.

## Conclusion

The support selector winner is new_residual_gated_ensemble with nominal energy-proxy res68 0.00675 [0.00610, 0.00727] at acceptance 0.447.  The transparent ladder gives res68 0.00689 at acceptance 0.444, while the shuffled-target HGB control gives 0.01089.  The result supports treating the veto ladder as a support-acceptance calibration: it changes charge composition and protects low-support regions, but it should not be promoted to an absolute energy or PID improvement without external truth.

## Artifacts

`counts_by_run.csv`, `run_level_rates.csv`, `rate_cv.csv`, `analysis_rows_preview.csv`,
`fold_summary.csv`, `method_geometry_metrics.csv`,
`method_veto_family_metrics.csv`, `method_deltas.csv`, `input_sha256.csv`,
`manifest.json`, `result.json`, and this report.
The full out-of-fold selector dump `selector_oof.csv.gz` is generated locally and
listed in `manifest.json` as an ignored regenerated intermediate because the
repository excludes `*.gz`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14g_1781051226_621_082271da_veto_ladder_energy_acceptance.py --config configs/s14g_1781051226_621_082271da_veto_ladder_energy_acceptance.yaml
```
