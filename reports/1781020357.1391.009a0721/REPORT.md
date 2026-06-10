# S14d: PSTAR material-budget and geometry envelope audit

- **Ticket ID:** 1781020357.1391.009a0721
- **Worker:** testbeam-laptop-3
- **Input:** raw `data/root/root/hrdb_run_*.root` only; checksums in `manifest.json` and `input_sha256.csv`.
- **No Monte Carlo / no GEANT4 / no Birks model / no absolute PID claim.** This is a material-budget and closure audit.

## 1. Raw reproduction gate

The script rebuilds selected B-stack pulses from `HRDv`: median(samples 0..3) baseline, positive channels B2/B4/B6/B8, and `A > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## 2. Material-budget proxy definition

PSTAR is used only as a depth-order anchor. The scan varies first stave center, center spacing, active thickness, dead layer per downstream stave, PSTAR density, and a PSTAR range-scale nuisance. Each material-budget variant converts effective stave depths to proton CSDA energies by log-log interpolation of the configured plastic-scintillator PSTAR table. Within each penetration-depth bin, an independent odd-duplicate total charge rank maps monotonically into the bracket between neighboring depth anchors. This defines the held-out energy proxy. Predictors see only even-readout amplitudes, charges, depth, multiplicity, and saturation flags.

## 3. Methods and held-out split

- **Train runs:** 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64.
- **Held-out runs:** 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65. Bootstrap CIs resample held-out runs as blocks.
- **Traditional:** PSTAR depth plus per-depth monotonic even-charge quantile lookup.
- **ML:** monotonic `HistGradientBoostingRegressor` on the even amplitude vector, even charge vector, penetration depth, multiplicity, and saturation flags.

## 4. Nominal held-out benchmark

| method                          |      n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   |   depth_order_violation_rate | depth_violation_ci95   |
|:--------------------------------|-------:|-------------------:|-----------------:|:---------------------------------------------|-----------------------------:|:-----------------------|
| pstar_depth_only                | 332852 |        -0.00715907 |        0.261461  | []                                           |                            0 | []                     |
| traditional_depth_charge_lookup | 332852 |        -0.0122525  |        0.0211892 | [0.019347728214226454, 0.021953897607786085] |                            0 | [0.0, 0.0]             |
| ml_monotonic_hgb                | 332852 |        -0.00322572 |        0.0248339 | [0.023457684862562046, 0.029307484970070557] |                            0 | [0.0, 0.0]             |

## 5. Run-split checks

|   run | method                          |     n |   res68_abs_frac |   depth_order_violation_rate |
|------:|:--------------------------------|------:|-----------------:|-----------------------------:|
|    44 | traditional_depth_charge_lookup |  1911 |        0.0218948 |                            0 |
|    44 | ml_monotonic_hgb                |  1911 |        0.0272004 |                            0 |
|    45 | traditional_depth_charge_lookup | 22999 |        0.022135  |                            0 |
|    45 | ml_monotonic_hgb                | 22999 |        0.0275519 |                            0 |
|    46 | traditional_depth_charge_lookup |   676 |        0.021328  |                            0 |
|    46 | ml_monotonic_hgb                |   676 |        0.0248699 |                            0 |
|    47 | traditional_depth_charge_lookup |  5160 |        0.020721  |                            0 |
|    47 | ml_monotonic_hgb                |  5160 |        0.0248296 |                            0 |
|    48 | traditional_depth_charge_lookup | 13175 |        0.0220346 |                            0 |
|    48 | ml_monotonic_hgb                | 13175 |        0.0258779 |                            0 |
|    49 | traditional_depth_charge_lookup | 13921 |        0.0220447 |                            0 |
|    49 | ml_monotonic_hgb                | 13921 |        0.0262058 |                            0 |
|    50 | traditional_depth_charge_lookup | 34254 |        0.0182003 |                            0 |
|    50 | ml_monotonic_hgb                | 34254 |        0.0240337 |                            0 |
|    51 | traditional_depth_charge_lookup | 14294 |        0.0193999 |                            0 |
|    51 | ml_monotonic_hgb                | 14294 |        0.0239771 |                            0 |
|    52 | traditional_depth_charge_lookup |  6933 |        0.0196008 |                            0 |
|    52 | ml_monotonic_hgb                |  6933 |        0.0242729 |                            0 |
|    53 | traditional_depth_charge_lookup | 31382 |        0.0172177 |                            0 |
|    53 | ml_monotonic_hgb                | 31382 |        0.0192253 |                            0 |
|    54 | traditional_depth_charge_lookup | 29664 |        0.0170331 |                            0 |
|    54 | ml_monotonic_hgb                | 29664 |        0.0191119 |                            0 |
|    55 | traditional_depth_charge_lookup | 16836 |        0.0190488 |                            0 |
|    55 | ml_monotonic_hgb                | 16836 |        0.0239335 |                            0 |
|    56 | traditional_depth_charge_lookup | 38925 |        0.0193482 |                            0 |
|    56 | ml_monotonic_hgb                | 38925 |        0.0247418 |                            0 |
|    57 | traditional_depth_charge_lookup | 12928 |        0.0217318 |                            0 |
|    57 | ml_monotonic_hgb                | 12928 |        0.0262829 |                            0 |
|    58 | traditional_depth_charge_lookup | 15919 |        0.0213221 |                            0 |
|    58 | ml_monotonic_hgb                | 15919 |        0.0163343 |                            0 |
|    59 | traditional_depth_charge_lookup | 13861 |        0.0246647 |                            0 |
|    59 | ml_monotonic_hgb                | 13861 |        0.0385312 |                            0 |
|    60 | traditional_depth_charge_lookup | 10133 |        0.0241374 |                            0 |
|    60 | ml_monotonic_hgb                | 10133 |        0.044327  |                            0 |
|    61 | traditional_depth_charge_lookup | 11287 |        0.0241232 |                            0 |
|    61 | ml_monotonic_hgb                | 11287 |        0.042297  |                            0 |
|    62 | traditional_depth_charge_lookup | 11911 |        0.0241434 |                            0 |
|    62 | ml_monotonic_hgb                | 11911 |        0.0384092 |                            0 |
|    63 | traditional_depth_charge_lookup | 14779 |        0.0234886 |                            0 |
|    63 | ml_monotonic_hgb                | 14779 |        0.027392  |                            0 |
|    65 | traditional_depth_charge_lookup | 11904 |        0.0238393 |                            0 |
|    65 | ml_monotonic_hgb                | 11904 |        0.0245007 |                            0 |

## 6. Material-budget/PSTAR envelope

| geometry                  | description                                                                                 |   first_center_cm |   spacing_cm |   active_thickness_cm |   dead_layer_cm |   pstar_density_g_cm3 |   pstar_range_scale |   B2_effective_depth_cm |   B8_effective_depth_cm |   B2_anchor_mev |   B8_anchor_mev |   traditional_res68 |   ml_res68 |   ml_minus_traditional_res68 |
|:--------------------------|:--------------------------------------------------------------------------------------------|------------------:|-------------:|----------------------:|----------------:|----------------------:|--------------------:|------------------------:|------------------------:|----------------:|----------------:|--------------------:|-----------:|-----------------------------:|
| nominal_budget            | nominal first-center, spacing, active thickness, dead layer, density, and PSTAR range scale |               2   |          4   |                   1   |             0   |                 1.032 |                1    |                     2   |                    14   |         40.0414 |         117.965 |           0.0211892 |  0.0248339 |                   0.00364463 |
| first_center_cm_1p5       | one-at-a-time scan: first_center_cm=1.5                                                     |               1.5 |          4   |                   1   |             0   |                 1.032 |                1    |                     1.5 |                    13.5 |         34.6653 |         115.554 |           0.0271169 |  0.0301401 |                   0.00302325 |
| first_center_cm_2         | one-at-a-time scan: first_center_cm=2                                                       |               2   |          4   |                   1   |             0   |                 1.032 |                1    |                     2   |                    14   |         40.0414 |         117.965 |           0.0211892 |  0.0253316 |                   0.00414233 |
| first_center_cm_2p5       | one-at-a-time scan: first_center_cm=2.5                                                     |               2.5 |          4   |                   1   |             0   |                 1.032 |                1    |                     2.5 |                    14.5 |         45.1027 |         120.339 |           0.0172518 |  0.0207976 |                   0.00354583 |
| spacing_cm_3p8            | one-at-a-time scan: spacing_cm=3.8                                                          |               2   |          3.8 |                   1   |             0   |                 1.032 |                1    |                     2   |                    13.4 |         40.0414 |         115.067 |           0.020111  |  0.0238374 |                   0.00372642 |
| spacing_cm_4              | one-at-a-time scan: spacing_cm=4                                                            |               2   |          4   |                   1   |             0   |                 1.032 |                1    |                     2   |                    14   |         40.0414 |         117.965 |           0.0211892 |  0.0259704 |                   0.00478118 |
| spacing_cm_4p2            | one-at-a-time scan: spacing_cm=4.2                                                          |               2   |          4.2 |                   1   |             0   |                 1.032 |                1    |                     2   |                    14.6 |         40.0414 |         120.809 |           0.022262  |  0.0261268 |                   0.00386488 |
| active_thickness_cm_0p8   | one-at-a-time scan: active_thickness_cm=0.8                                                 |               2   |          4   |                   0.8 |             0   |                 1.032 |                1    |                     1.9 |                    13.9 |         39.0232 |         117.486 |           0.0221259 |  0.0259508 |                   0.00382492 |
| active_thickness_cm_1     | one-at-a-time scan: active_thickness_cm=1                                                   |               2   |          4   |                   1   |             0   |                 1.032 |                1    |                     2   |                    14   |         40.0414 |         117.965 |           0.0211892 |  0.0257709 |                   0.00458168 |
| active_thickness_cm_1p2   | one-at-a-time scan: active_thickness_cm=1.2                                                 |               2   |          4   |                   1.2 |             0   |                 1.032 |                1    |                     2.1 |                    14.1 |         41.0972 |         118.442 |           0.0202506 |  0.0240287 |                   0.0037781  |
| dead_layer_cm_0           | one-at-a-time scan: dead_layer_cm=0                                                         |               2   |          4   |                   1   |             0   |                 1.032 |                1    |                     2   |                    14   |         40.0414 |         117.965 |           0.0211892 |  0.0255375 |                   0.00434827 |
| dead_layer_cm_0p1         | one-at-a-time scan: dead_layer_cm=0.1                                                       |               2   |          4   |                   1   |             0.1 |                 1.032 |                1    |                     2   |                    14.3 |         40.0414 |         119.393 |           0.0217198 |  0.0259333 |                   0.00421354 |
| dead_layer_cm_0p2         | one-at-a-time scan: dead_layer_cm=0.2                                                       |               2   |          4   |                   1   |             0.2 |                 1.032 |                1    |                     2   |                    14.6 |         40.0414 |         120.809 |           0.022262  |  0.0264822 |                   0.00422029 |
| pstar_density_g_cm3_1     | one-at-a-time scan: pstar_density_g_cm3=1                                                   |               2   |          4   |                   1   |             0   |                 1     |                1    |                     2   |                    14   |         39.4121 |         115.874 |           0.0210779 |  0.0258213 |                   0.00474337 |
| pstar_density_g_cm3_1p032 | one-at-a-time scan: pstar_density_g_cm3=1.032                                               |               2   |          4   |                   1   |             0   |                 1.032 |                1    |                     2   |                    14   |         40.0414 |         117.965 |           0.0211892 |  0.0250905 |                   0.0039013  |
| pstar_density_g_cm3_1p06  | one-at-a-time scan: pstar_density_g_cm3=1.06                                                |               2   |          4   |                   1   |             0   |                 1.06  |                1    |                     2   |                    14   |         40.6173 |         119.771 |           0.0212382 |  0.0251215 |                   0.00388338 |
| pstar_range_scale_0p97    | one-at-a-time scan: pstar_range_scale=0.97                                                  |               2   |          4   |                   1   |             0   |                 1.032 |                0.97 |                     2   |                    14   |         40.6973 |         120.022 |           0.0212446 |  0.0249764 |                   0.00373176 |
| pstar_range_scale_1       | one-at-a-time scan: pstar_range_scale=1                                                     |               2   |          4   |                   1   |             0   |                 1.032 |                1    |                     2   |                    14   |         40.0414 |         117.965 |           0.0211892 |  0.0246695 |                   0.00348027 |
| pstar_range_scale_1p03    | one-at-a-time scan: pstar_range_scale=1.03                                                  |               2   |          4   |                   1   |             0   |                 1.032 |                1.03 |                     2   |                    14   |         39.4504 |         116.002 |           0.0210853 |  0.0249504 |                   0.00386509 |
| corner_lofir_lodea_lopst  | corner envelope scan                                                                        |               1.5 |          3.8 |                   0.8 |             0   |                 1     |                0.97 |                     1.4 |                    12.8 |         33.4703 |         112.047 |           0.0273398 |  0.0308379 |                   0.00349813 |
| corner_lofir_lodea_hipst  | corner envelope scan                                                                        |               1.5 |          3.8 |                   0.8 |             0   |                 1.06  |                1.03 |                     1.4 |                    12.8 |         33.441  |         111.936 |           0.0273333 |  0.0308308 |                   0.00349749 |
| corner_lofir_hidea_lopst  | corner envelope scan                                                                        |               1.5 |          3.8 |                   0.8 |             0.2 |                 1     |                0.97 |                     1.4 |                    13.4 |         33.4703 |         115     |           0.0287703 |  0.0322201 |                   0.00344983 |
| corner_lofir_hidea_hipst  | corner envelope scan                                                                        |               1.5 |          3.8 |                   0.8 |             0.2 |                 1.06  |                1.03 |                     1.4 |                    13.4 |         33.441  |         114.885 |           0.0287635 |  0.0322144 |                   0.00345082 |
| corner_hifir_lodea_lopst  | corner envelope scan                                                                        |               2.5 |          4.2 |                   1.2 |             0   |                 1     |                0.97 |                     2.6 |                    15.2 |         46.0308 |         123.53  |           0.017481  |  0.0211995 |                   0.00371857 |
| corner_hifir_lodea_hipst  | corner envelope scan                                                                        |               2.5 |          4.2 |                   1.2 |             0   |                 1.06  |                1.03 |                     2.6 |                    15.2 |         45.9878 |         123.408 |           0.0174781 |  0.0211959 |                   0.00371785 |
| corner_hifir_hidea_lopst  | corner envelope scan                                                                        |               2.5 |          4.2 |                   1.2 |             0.2 |                 1     |                0.97 |                     2.6 |                    15.8 |         46.0308 |         126.286 |           0.0183235 |  0.0220025 |                   0.00367895 |
| corner_hifir_hidea_hipst  | corner envelope scan                                                                        |               2.5 |          4.2 |                   1.2 |             0.2 |                 1.06  |                1.03 |                     2.6 |                    15.8 |         45.9878 |         126.16  |           0.0183204 |  0.0219991 |                   0.00367872 |

## 7. Leakage audit

| check                                      | value    | pass   |
|:-------------------------------------------|:---------|:-------|
| train_heldout_run_overlap                  | []       | True   |
| train_heldout_event_key_overlap            | 0        | True   |
| features_exclude_run_event_and_odd_readout | true     | True   |
| depth_only_res68                           | 0.261461 | True   |
| shuffled_target_ml_res68                   | 0.319485 | True   |

The ML-minus-traditional residual delta is negative if ML improves the closure. The shuffled-target and depth-only checks are kept because a strong ML closure would otherwise make leakage a credible failure mode.

## 8. Finding

The nominal material-budget scan reproduces S00 exactly and gives held-out odd-readout energy-proxy res68 0.0212 for the PSTAR/depth/even-charge lookup versus 0.0248 for monotonic HGB (ML - traditional 0.0036, run-block 95% CI 0.0035 to 0.0076). Across explicit center/thickness/dead-layer/PSTAR variants, traditional res68 spans 0.0173-0.0288 and ML spans 0.0208-0.0322. This passes as an internal charge/depth preflight, but it is not an absolute energy calibration or PID claim: Birks quenching, GEANT4 transport, and external particle truth remain unresolved.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14d_1781020357_1391_009a0721_material_budget_audit.py --config configs/s14d_1781020357_1391_009a0721.yaml
```
