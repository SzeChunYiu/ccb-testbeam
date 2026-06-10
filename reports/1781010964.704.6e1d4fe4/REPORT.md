# S14b: range-energy calibration preflight from P04 closure

- **Ticket ID:** 1781010964.704.6e1d4fe4
- **Worker:** testbeam-laptop-1
- **Input:** raw `data/root/root/hrdb_run_*.root` only; checksums in `manifest.json` and `input_sha256.csv`.
- **No Monte Carlo / no Birks model / no absolute PID claim.** This is a table-lookup and leakage preflight.

## 1. Raw reproduction gate

The script rebuilds selected B-stack pulses from `HRDv`: median(samples 0..3) baseline, positive channels B2/B4/B6/B8, and `A > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## 2. Proxy definition

PSTAR is used only as a depth-order anchor. For each geometry variant, stave center depth is converted to a proton CSDA energy by log-log interpolation of the configured PSTAR plastic-scintillator table. Within each penetration-depth bin, an independent odd-duplicate total charge rank maps monotonically into the bracket between neighboring depth anchors. This defines the held-out energy proxy. Predictors see only even-readout amplitudes, charges, depth, multiplicity, and saturation flags.

## 3. Methods and held-out split

- **Train runs:** 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64.
- **Held-out runs:** 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65. Bootstrap CIs resample held-out runs as blocks.
- **Traditional:** PSTAR depth plus per-depth monotonic even-charge quantile lookup.
- **ML:** monotonic `HistGradientBoostingRegressor` on the even amplitude vector, even charge vector, penetration depth, multiplicity, and saturation flags.

## 4. Nominal held-out benchmark

| method                          |      n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   |   depth_order_violation_rate | depth_violation_ci95   |
|:--------------------------------|-------:|-------------------:|-----------------:|:---------------------------------------------|-----------------------------:|:-----------------------|
| pstar_depth_only                | 332852 |        -0.00715907 |        0.261461  | []                                           |                            0 | []                     |
| traditional_depth_charge_lookup | 332852 |        -0.0122525  |        0.0211892 | [0.019759173376975067, 0.022616709286844058] |                            0 | [0.0, 0.0]             |
| ml_monotonic_hgb                | 332852 |        -0.00329812 |        0.0250078 | [0.022795672304338082, 0.02847725106827667]  |                            0 | [0.0, 0.0]             |

## 5. Run-split checks

|   run | method                          |     n |   res68_abs_frac |   depth_order_violation_rate |
|------:|:--------------------------------|------:|-----------------:|-----------------------------:|
|    44 | traditional_depth_charge_lookup |  1911 |        0.0218948 |                            0 |
|    44 | ml_monotonic_hgb                |  1911 |        0.0267085 |                            0 |
|    45 | traditional_depth_charge_lookup | 22999 |        0.022135  |                            0 |
|    45 | ml_monotonic_hgb                | 22999 |        0.0279991 |                            0 |
|    46 | traditional_depth_charge_lookup |   676 |        0.021328  |                            0 |
|    46 | ml_monotonic_hgb                |   676 |        0.023496  |                            0 |
|    47 | traditional_depth_charge_lookup |  5160 |        0.020721  |                            0 |
|    47 | ml_monotonic_hgb                |  5160 |        0.0244818 |                            0 |
|    48 | traditional_depth_charge_lookup | 13175 |        0.0220346 |                            0 |
|    48 | ml_monotonic_hgb                | 13175 |        0.0260205 |                            0 |
|    49 | traditional_depth_charge_lookup | 13921 |        0.0220447 |                            0 |
|    49 | ml_monotonic_hgb                | 13921 |        0.0262889 |                            0 |
|    50 | traditional_depth_charge_lookup | 34254 |        0.0182003 |                            0 |
|    50 | ml_monotonic_hgb                | 34254 |        0.0246351 |                            0 |
|    51 | traditional_depth_charge_lookup | 14294 |        0.0193999 |                            0 |
|    51 | ml_monotonic_hgb                | 14294 |        0.0245163 |                            0 |
|    52 | traditional_depth_charge_lookup |  6933 |        0.0196008 |                            0 |
|    52 | ml_monotonic_hgb                |  6933 |        0.0250131 |                            0 |
|    53 | traditional_depth_charge_lookup | 31382 |        0.0172177 |                            0 |
|    53 | ml_monotonic_hgb                | 31382 |        0.0193372 |                            0 |
|    54 | traditional_depth_charge_lookup | 29664 |        0.0170331 |                            0 |
|    54 | ml_monotonic_hgb                | 29664 |        0.0193838 |                            0 |
|    55 | traditional_depth_charge_lookup | 16836 |        0.0190488 |                            0 |
|    55 | ml_monotonic_hgb                | 16836 |        0.0244325 |                            0 |
|    56 | traditional_depth_charge_lookup | 38925 |        0.0193482 |                            0 |
|    56 | ml_monotonic_hgb                | 38925 |        0.0254167 |                            0 |
|    57 | traditional_depth_charge_lookup | 12928 |        0.0217318 |                            0 |
|    57 | ml_monotonic_hgb                | 12928 |        0.0264824 |                            0 |
|    58 | traditional_depth_charge_lookup | 15919 |        0.0213221 |                            0 |
|    58 | ml_monotonic_hgb                | 15919 |        0.0149365 |                            0 |
|    59 | traditional_depth_charge_lookup | 13861 |        0.0246647 |                            0 |
|    59 | ml_monotonic_hgb                | 13861 |        0.0386133 |                            0 |
|    60 | traditional_depth_charge_lookup | 10133 |        0.0241374 |                            0 |
|    60 | ml_monotonic_hgb                | 10133 |        0.040258  |                            0 |
|    61 | traditional_depth_charge_lookup | 11287 |        0.0241232 |                            0 |
|    61 | ml_monotonic_hgb                | 11287 |        0.03946   |                            0 |
|    62 | traditional_depth_charge_lookup | 11911 |        0.0241434 |                            0 |
|    62 | ml_monotonic_hgb                | 11911 |        0.0357343 |                            0 |
|    63 | traditional_depth_charge_lookup | 14779 |        0.0234886 |                            0 |
|    63 | ml_monotonic_hgb                | 14779 |        0.0278653 |                            0 |
|    65 | traditional_depth_charge_lookup | 11904 |        0.0238393 |                            0 |
|    65 | ml_monotonic_hgb                | 11904 |        0.0239465 |                            0 |

## 6. Geometry systematic envelope

| geometry   |   B2_anchor_mev |   B8_anchor_mev |   traditional_res68 |   ml_res68 |   ml_minus_traditional_res68 |
|:-----------|----------------:|----------------:|--------------------:|-----------:|-----------------------------:|
| center_4cm |         40.0414 |        117.965  |           0.0211892 |  0.0250078 |                   0.00381858 |
| center_2cm |         28.3218 |         79.6511 |           0.0191036 |  0.0229994 |                   0.00389578 |
| zero_4cm   |         20.0778 |        108.08   |           0.0663057 |  0.0570218 |                  -0.00928386 |

## 7. Leakage audit

| check                                      | value    | pass   |
|:-------------------------------------------|:---------|:-------|
| train_heldout_run_overlap                  | []       | True   |
| train_heldout_event_key_overlap            | 0        | True   |
| features_exclude_run_event_and_odd_readout | true     | True   |
| depth_only_res68                           | 0.261461 | True   |
| shuffled_target_ml_res68                   | 0.319485 | True   |

The ML-minus-traditional residual delta is negative if ML improves the closure. The shuffled-target and depth-only checks are kept because the ML closure is strong enough that leakage would otherwise be a credible failure mode.

## 8. Finding

The nominal 4 cm geometry preflight reproduces S00 exactly and gives held-out odd-readout energy-proxy res68 0.0212 for the PSTAR/depth/even-charge lookup versus 0.0250 for monotonic HGB (ML - traditional 0.0038, run-block 95% CI 0.0019 to 0.0058). Across explicit geometry variants, traditional res68 spans 0.0191-0.0663 and ML spans 0.0230-0.0570. This passes as an internal charge/depth preflight, but it is not an absolute energy calibration: Birks quenching, material budget, and external particle truth remain unresolved.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14b_range_energy_preflight.py --config configs/s14b_range_energy_preflight.yaml
```
