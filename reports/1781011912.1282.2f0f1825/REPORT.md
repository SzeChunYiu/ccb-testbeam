# P04e: externalized duplicate-readout ML closure

- **Ticket ID:** `1781011912.1282.2f0f1825`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/hrdb_run_*.root`; sorted B-stack summaries only for post-fit audits; no Monte Carlo.
- **Target:** paired odd-channel inverted duplicate readout amplitude; features use only the even-channel waveform and even-channel summaries.

## Raw reproduction first

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## Methods

- **Traditional:** per-stave Huber log-amplitude regression on even peak, charge, timing-shape, and lobe summary features.
- **ML:** ExtraTrees log-amplitude regression on the 18 even samples plus the same even-channel summaries.
- **Sentinels:** log-linear peak calibration and shuffled-target ML.

## Leave-one-run-family-out benchmark

| split                      | method             |      n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                           |   within_10pct |
|:---------------------------|:-------------------|-------:|-------------------:|-----------------:|:-----------------------------------------------|---------------:|
| holdout_sample_i_calib     | traditional_huber  | 248607 |       -0.00251779  |       0.0179106  | [0.015981933796222373, 0.02239559617457053]    |      0.91069   |
| holdout_sample_i_calib     | peak_loglinear     | 248607 |       -0.0196541   |       0.059608   | [0.03866207768508491, 0.08576402784290993]     |      0.823899  |
| holdout_sample_i_calib     | ml_extra_trees     | 248607 |       -0.000171913 |       0.00139399 | [0.001043117527815697, 0.002112731227213006]   |      0.990378  |
| holdout_sample_i_calib     | shuffled_target_ml | 248607 |       -0.261447    |       0.473361   | [0.4501907258259984, 0.5058230924331834]       |      0.0858061 |
| holdout_sample_i_analysis  | traditional_huber  | 252167 |       -0.0051937   |       0.0187125  | [0.01710119897390533, 0.022052474116895832]    |      0.923519  |
| holdout_sample_i_analysis  | peak_loglinear     | 252167 |       -0.0097237   |       0.0467178  | [0.032191568709738105, 0.07216070932119412]    |      0.850167  |
| holdout_sample_i_analysis  | ml_extra_trees     | 252167 |       -0.000174345 |       0.00142098 | [0.0012331764608107417, 0.001771677509101976]  |      0.991922  |
| holdout_sample_i_analysis  | shuffled_target_ml | 252167 |       -0.385636    |       0.509838   | [0.4973311850257387, 0.5215521161942634]       |      0.078682  |
| holdout_sample_ii_calib    | traditional_huber  |  14630 |        0.00772628  |       0.0263394  | [0.026339354431326116, 0.026339354431326116]   |      0.84149   |
| holdout_sample_ii_calib    | peak_loglinear     |  14630 |       -0.0786646   |       0.13176    | [0.13176036668961572, 0.13176036668961572]     |      0.525359  |
| holdout_sample_ii_calib    | ml_extra_trees     |  14630 |       -6.71601e-05 |       0.00252571 | [0.0025257082011583866, 0.0025257082011583866] |      0.982297  |
| holdout_sample_ii_calib    | shuffled_target_ml |  14630 |        0.466961    |       0.915104   | [0.9151038322134795, 0.9151038322134795]       |      0.103213  |
| holdout_sample_ii_analysis | traditional_huber  | 125078 |        0.0117274   |       0.0458258  | [0.02446591498043927, 0.06003244886393554]     |      0.825661  |
| holdout_sample_ii_analysis | peak_loglinear     | 125078 |       -0.0700344   |       0.122526   | [0.11027689576495404, 0.13181944421030592]     |      0.573514  |
| holdout_sample_ii_analysis | ml_extra_trees     | 125078 |        8.91998e-07 |       0.00363123 | [0.002331724352300548, 0.004930617082795177]   |      0.975975  |
| holdout_sample_ii_analysis | shuffled_target_ml | 125078 |        0.572707    |       0.998581   | [0.7971843141523184, 1.1229599296509516]       |      0.0903116 |

## Train on B4/B6/B8, hold out B2

| split                     | method             |      n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |   within_10pct |
|:--------------------------|:-------------------|-------:|-------------------:|-----------------:|:---------------------------------------------|---------------:|
| train_B4_B6_B8_holdout_B2 | traditional_huber  | 579172 |        -0.0981775  |        0.136999  | [0.1259315350714079, 0.14549454362314657]    |      0.476183  |
| train_B4_B6_B8_holdout_B2 | peak_loglinear     | 579172 |        -0.999824   |        0.999855  | [0.9998400405706963, 0.9998630566092443]     |      0         |
| train_B4_B6_B8_holdout_B2 | ml_extra_trees     | 579172 |        -0.00677261 |        0.0167779 | [0.013925539791349617, 0.019580792466833297] |      0.919855  |
| train_B4_B6_B8_holdout_B2 | shuffled_target_ml | 579172 |        -0.565742   |        0.67313   | [0.6593271999240399, 0.6800128638758707]     |      0.0412382 |

## Waveform-neighbor leakage probes

| split                      |   n_train |   n_test |   exact_waveform_hash_overlap |   nearest_norm_l2_p01 |   nearest_norm_l2_median |   nearest_norm_l2_under_0p01_frac |
|:---------------------------|----------:|---------:|------------------------------:|----------------------:|-------------------------:|----------------------------------:|
| holdout_sample_i_calib     |    391875 |   248607 |                             0 |             0.0109231 |                0.0273269 |                       0.00476667  |
| holdout_sample_i_analysis  |    388315 |   252167 |                             0 |             0.0109313 |                0.0255809 |                       0.0056      |
| holdout_sample_ii_calib    |    625852 |    14630 |                             0 |             0.0153567 |                0.0379262 |                       0.000478469 |
| holdout_sample_ii_analysis |    515404 |   125078 |                             0 |             0.0154271 |                0.0437082 |                       0.000566667 |
| train_B4_B6_B8_holdout_B2  |     61310 |   579172 |                             0 |             0.0238634 |                0.0577667 |                       0.000166667 |

## Downstream sorted-observable audit

| observable_bin        |     n |   median_abs_frac_error |   res68_abs_frac |   median_downstream_sum |
|:----------------------|------:|------------------------:|-----------------:|------------------------:|
| downstream_count_0    | 58298 |             0.000912918 |       0.00180744 |                     173 |
| downstream_count_1    | 25463 |             0.00248453  |       0.00637992 |                    3676 |
| downstream_count_ge2  | 41317 |             0.00275312  |       0.00634287 |                    7121 |
| downstream_max_lt1000 | 58294 |             0.000912769 |       0.00180729 |                     173 |
| downstream_max_ge1000 | 66784 |             0.00264667  |       0.00635643 |                    5873 |
| ts_spread_ge3         |  5177 |             0.00304919  |       0.00779733 |                    7730 |

## Finding

Leave-one-run-family-out duplicate-readout closure remains strong but no longer looks like a standalone energy result: the worst-family ML res68 is 0.0036, versus 0.0458 for the Huber traditional method and at least 0.4734 for the shuffled-target sentinel.  The stricter B4/B6/B8 -> B2 transfer is much weaker (ML res68=0.0168, traditional=0.1370), showing the one-percent P04c closure does not externalize across staves.  Exact waveform-hash train/test overlap is 0 and the largest near-neighbor under-0.01 fraction is 0.0056; the good family-split ML result is therefore not explained by repeated waveform hashes, but it is still a same-detector duplicate-readout closure.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04e_1781011912_1282_2f0f1825_externalized_duplicate_readout.py --config configs/p04e_1781011912_1282_2f0f1825_externalized_duplicate_readout.json
```
