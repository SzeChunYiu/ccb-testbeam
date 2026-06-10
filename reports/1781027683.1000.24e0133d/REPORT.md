# S14e: range-energy abstention support envelope

- **Ticket ID:** 1781027683.1000.24e0133d
- **Worker:** testbeam-laptop-4
- **Input:** raw B-stack `HRDv` ROOT plus existing S14b/P04b artifacts; checksums are in `input_sha256.csv` and `manifest.json`.
- **No Monte Carlo / no absolute energy or PID claim.** PSTAR is only a depth-order proxy anchor.

## Raw Reproduction First

| quantity                               |   expected |   reproduced |   delta | pass   |
|:---------------------------------------|-----------:|-------------:|--------:|:-------|
| S00 selected B-stave pulse records     |     640737 |       640737 |       0 | True   |
| S14b valid event rows after charge cut |     584406 |       584406 |       0 | True   |

## Methods

The target is the same S14b odd-duplicate range-energy proxy. The traditional method is PSTAR depth plus per-depth monotonic even-charge lookup. The ML method is a monotonic HGB trained only on train-run even-readout depth, charge, amplitude, multiplicity, and saturation features.

For abstention, both methods are ranked by a predeclared per-event P04b sensitivity score: scale even-readout charge/amplitude by `1 +/-` the S14b P04b external-charge res68 and take the larger fractional prediction shift. The combined reported res68 is `sqrt(model_proxy_res68^2 + P04b_sensitivity_res68^2)` on held-out runs.

## Nominal Geometry Abstention

| method                          |   uncertainty_threshold |   accepted_n |   accepted_fraction | accepted_fraction_ci95                    |   bias_median_frac |   combined_energy_proxy_res68 | combined_energy_proxy_res68_ci95             |   depth_order_violation_rate | clears_10pct_point   |
|:--------------------------------|------------------------:|-------------:|--------------------:|:------------------------------------------|-------------------:|------------------------------:|:---------------------------------------------|-----------------------------:|:---------------------|
| traditional_depth_charge_lookup |                   0.05  |        81863 |            0.245944 | [0.17403449460585393, 0.3372580310120774] |       -0.0201909   |                     0.0441828 | [0.042920293216260785, 0.04525773808326159]  |                            0 | True                 |
| traditional_depth_charge_lookup |                   0.075 |       118373 |            0.355633 | [0.2683523950296907, 0.4804747001473966]  |       -0.0185735   |                     0.0545705 | [0.05389489774001511, 0.05512177116706213]   |                            0 | True                 |
| traditional_depth_charge_lookup |                   0.1   |       129240 |            0.388281 | [0.2748846403243159, 0.5423144281793438]  |       -0.0181037   |                     0.0584112 | [0.056827004778327375, 0.059409314231212026] |                            0 | True                 |
| traditional_depth_charge_lookup |                   0.125 |       136607 |            0.410414 | [0.31408472577074087, 0.5554492431185213] |       -0.0178369   |                     0.0611659 | [0.05958877770379128, 0.06325180583195604]   |                            0 | True                 |
| traditional_depth_charge_lookup |                   0.15  |       142597 |            0.42841  | [0.3239977874662944, 0.5656881852819398]  |       -0.0176607   |                     0.0638237 | [0.06151564579078043, 0.0659860443522801]    |                            0 | True                 |
| traditional_depth_charge_lookup |                   0.2   |       154872 |            0.465288 | [0.36386747550510995, 0.6095590448876735] |       -0.01732     |                     0.068943  | [0.0659230809670384, 0.0721968905172897]     |                            0 | True                 |
| traditional_depth_charge_lookup |                   0.25  |       242509 |            0.728579 | [0.6759706404089276, 0.7829213420793193]  |       -0.015054    |                     0.215355  | [0.15096219126016341, 0.2261064863577736]    |                            0 | False                |
| traditional_depth_charge_lookup |                   0.3   |       332852 |            1        | [1.0, 1.0]                                |       -0.0122525   |                     0.246237  | [0.21864035025811487, 0.25155181869321325]   |                            0 | False                |
| traditional_depth_charge_lookup |                   0.4   |       332852 |            1        | [1.0, 1.0]                                |       -0.0122525   |                     0.246237  | [0.22665904092471464, 0.25135416010225736]   |                            0 | False                |
| traditional_depth_charge_lookup |                   1     |       332852 |            1        | [1.0, 1.0]                                |       -0.0122525   |                     0.246237  | [0.22905406759243382, 0.25194053676899525]   |                            0 | False                |
| ml_monotonic_hgb                |                   0.05  |        87849 |            0.263928 | [0.17453169323195578, 0.3523225306750191] |        0.0141113   |                     0.0520557 | [0.05025054002707877, 0.05558551215247475]   |                            0 | True                 |
| ml_monotonic_hgb                |                   0.075 |       113051 |            0.339643 | [0.2532881338404325, 0.4226328000076784]  |        0.0113432   |                     0.0575943 | [0.055368505432044295, 0.0598860017256026]   |                            0 | True                 |
| ml_monotonic_hgb                |                   0.1   |       131672 |            0.395587 | [0.29230359102256886, 0.537094874765127]  |        0.00949556  |                     0.0624153 | [0.059765961533243574, 0.06388178723357797]  |                            0 | True                 |
| ml_monotonic_hgb                |                   0.125 |       141198 |            0.424207 | [0.29634597822232733, 0.56665872705384]   |        0.00863622  |                     0.0662024 | [0.06427685250704525, 0.06751677117206605]   |                            0 | True                 |
| ml_monotonic_hgb                |                   0.15  |       158799 |            0.477086 | [0.3767362045540965, 0.6326931129184352]  |        0.00736219  |                     0.0707992 | [0.06907437923951854, 0.08325293462027568]   |                            0 | True                 |
| ml_monotonic_hgb                |                   0.2   |       263578 |            0.791877 | [0.7322924903489588, 0.8511909608672287]  |       -0.000640964 |                     0.166372  | [0.13543496850532433, 0.1778576033043617]    |                            0 | False                |
| ml_monotonic_hgb                |                   0.25  |       325907 |            0.979135 | [0.9750576501226619, 0.9838603072095014]  |       -0.00333538  |                     0.185653  | [0.16706119123536783, 0.19463733677275416]   |                            0 | False                |
| ml_monotonic_hgb                |                   0.3   |       332244 |            0.998173 | [0.9979142203132516, 0.9984415655131642]  |       -0.0034554   |                     0.186878  | [0.1692331211972342, 0.1951477395509733]     |                            0 | False                |
| ml_monotonic_hgb                |                   0.4   |       332823 |            0.999913 | [0.9998820921627958, 0.999948340900335]   |       -0.00345676  |                     0.187322  | [0.1674899064484535, 0.19489294254991327]    |                            0 | False                |
| ml_monotonic_hgb                |                   1     |       332852 |            1        | [1.0, 1.0]                                |       -0.00345676  |                     0.187487  | [0.1678403571389293, 0.19662637770945046]    |                            0 | False                |

## ML Minus Traditional

|   uncertainty_threshold |   traditional_combined_res68 |   ml_combined_res68 |   ml_minus_traditional_combined_res68 | ml_minus_traditional_combined_res68_ci95       |
|------------------------:|-----------------------------:|--------------------:|--------------------------------------:|:-----------------------------------------------|
|                   0.05  |                    0.0441828 |           0.0520557 |                            0.00787284 | [0.005855211805139897, 0.011352759903966112]   |
|                   0.075 |                    0.0545705 |           0.0575943 |                            0.00302381 | [0.0006640130239978339, 0.0055162737034099955] |
|                   0.1   |                    0.0584112 |           0.0624153 |                            0.00400416 | [0.0020964542302224975, 0.006074559935581476]  |
|                   0.125 |                    0.0611659 |           0.0662024 |                            0.00503646 | [0.002185830425229705, 0.007025751909878127]   |
|                   0.15  |                    0.0638237 |           0.0707992 |                            0.00697544 | [0.005182058781110874, 0.018721824097427526]   |
|                   0.2   |                    0.068943  |           0.166372  |                            0.0974293  | [0.06943348116526038, 0.1103907279042024]      |
|                   0.25  |                    0.215355  |           0.185653  |                           -0.0297021  | [-0.052964737709043225, 0.034624157090988296]  |
|                   0.3   |                    0.246237  |           0.186878  |                           -0.0593591  | [-0.07806461192131571, -0.03201595732712851]   |
|                   0.4   |                    0.246237  |           0.187322  |                           -0.0589149  | [-0.0767173916241709, -0.03717526328450917]    |
|                   1     |                    0.246237  |           0.187487  |                           -0.05875    | [-0.07584787610675402, -0.04236518904787259]   |

## Best Support Strata

| geometry   | method                          | support_stratum              |   accepted_n |   n_runs |   combined_energy_proxy_res68 |   bias_median_frac |   depth_order_violation_rate |   score_median | clears_10pct_point   |
|:-----------|:--------------------------------|:-----------------------------|-------------:|---------:|------------------------------:|-------------------:|-----------------------------:|---------------:|:---------------------|
| center_2cm | traditional_depth_charge_lookup | B2|q_lt_8k|sat0|B2           |        10964 |       21 |                     0.0220129 |        -0.00538843 |                          nan |     0.00660971 | True                 |
| center_4cm | traditional_depth_charge_lookup | B2|q_lt_8k|sat0|B2           |        10964 |       21 |                     0.0251636 |        -0.00618383 |                          nan |     0.00758879 | True                 |
| center_2cm | traditional_depth_charge_lookup | B8|q_ge_32k|sat0|B2_B4_B6_B8 |         4027 |       20 |                     0.0292765 |        -0.0022475  |                          nan |     0.0253704  | True                 |
| center_4cm | traditional_depth_charge_lookup | B8|q_ge_32k|sat0|B2_B4_B6_B8 |         4027 |       20 |                     0.0294632 |        -0.00226177 |                          nan |     0.0255376  | True                 |
| center_2cm | traditional_depth_charge_lookup | B6|q_ge_32k|sat_ge1|B2_B4_B6 |          644 |       20 |                     0.0310374 |        -0.00177626 |                          nan |     0.0288415  | True                 |
| center_4cm | traditional_depth_charge_lookup | B6|q_ge_32k|sat_ge1|B2_B4_B6 |          644 |       20 |                     0.0315062 |        -0.0018026  |                          nan |     0.029275   | True                 |
| center_2cm | traditional_depth_charge_lookup | B6|q_ge_32k|sat0|B2_B4_B6    |         6409 |       20 |                     0.0343443 |        -0.00572151 |                          nan |     0.0303817  | True                 |
| zero_4cm   | traditional_depth_charge_lookup | B8|q_ge_32k|sat0|B2_B4_B6_B8 |         4027 |       20 |                     0.0345403 |        -0.00264903 |                          nan |     0.0300909  | True                 |
| center_4cm | traditional_depth_charge_lookup | B6|q_ge_32k|sat0|B2_B4_B6    |         6409 |       20 |                     0.0348873 |        -0.00581164 |                          nan |     0.0308669  | True                 |
| center_2cm | ml_monotonic_hgb                | B2|q_8k_16k|sat0|B2          |        26590 |       21 |                     0.0359    |         0.0216398  |                          nan |     0.0234511  | True                 |
| center_2cm | traditional_depth_charge_lookup | B2|q_8k_16k|sat0|B2          |        26590 |       21 |                     0.0362628 |        -0.0205034  |                          nan |     0.0259357  | True                 |
| center_2cm | traditional_depth_charge_lookup | B4|q_8k_16k|sat0|B2_B4       |          510 |       20 |                     0.038824  |         0.0156423  |                          nan |     0.0104967  | True                 |
| zero_4cm   | traditional_depth_charge_lookup | B6|q_ge_32k|sat_ge1|B2_B4_B6 |          644 |       20 |                     0.0390339 |        -0.00222326 |                          nan |     0.0362221  | True                 |
| center_4cm | ml_monotonic_hgb                | B2|q_8k_16k|sat0|B2          |        26590 |       21 |                     0.0407369 |         0.0242875  |                          nan |     0.027349   | True                 |
| center_4cm | traditional_depth_charge_lookup | B4|q_8k_16k|sat0|B2_B4       |          510 |       20 |                     0.0408779 |         0.0164915  |                          nan |     0.0110488  | True                 |
| center_4cm | traditional_depth_charge_lookup | B2|q_8k_16k|sat0|B2          |        26590 |       21 |                     0.0412371 |        -0.0232548  |                          nan |     0.0295365  | True                 |
| zero_4cm   | traditional_depth_charge_lookup | B6|q_ge_32k|sat0|B2_B4_B6    |         6409 |       20 |                     0.0436105 |        -0.00723108 |                          nan |     0.0387326  | True                 |
| center_2cm | ml_monotonic_hgb                | B2|q_16k_32k|sat0|B2         |        44626 |       21 |                     0.0510891 |         0.00834559 |                          nan |     0.043377   | True                 |
| center_2cm | traditional_depth_charge_lookup | B2|q_16k_32k|sat0|B2         |        44626 |       21 |                     0.0521971 |        -0.016897   |                          nan |     0.0440366  | True                 |
| center_2cm | ml_monotonic_hgb                | B2|q_lt_8k|sat0|B2           |        10964 |       21 |                     0.052744  |         0.0452784  |                          nan |     0          | True                 |

## Leakage Checks

| check                                      | value    | pass   |
|:-------------------------------------------|:---------|:-------|
| train_heldout_run_overlap                  | []       | True   |
| train_heldout_event_key_overlap            | 0        | True   |
| features_exclude_run_event_and_odd_readout | true     | True   |
| nominal_shuffled_target_ml_res68           | 0.334877 | True   |
| best_real_combined_res68                   | 0.041104 | True   |
| passing_support_triggered_leakage_review   | True     | True   |

## Finding

After ticket-local P04b propagation, 30 geometry/method/uncertainty-threshold rows clear the 10 percent combined res68 preflight threshold. The best threshold row is traditional_depth_charge_lookup at center_2cm with accepted fraction 0.2733 and combined res68 0.0411. The best minimum-support stratum is B2|q_lt_8k|sat0|B2 with combined res68 0.0220. Shuffled-target ML remains broad at 0.3349, and there is no train/held-out run or event-key overlap. This exposes a small internal S14b/P04b support envelope under uncertainty-ranked abstention, but it remains a proxy support claim, not an absolute per-event proton energy calibration.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14e_1781027683_1000_24e0133d_support_envelope.py --config configs/s14e_1781027683_1000_24e0133d.yaml
```
