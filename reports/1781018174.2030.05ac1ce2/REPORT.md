# P07e: duplicate-channel validation for saturation ratio transfer

Ticket `1781018174.2030.05ac1ce2`. Raw B-stack ROOT was read directly; no Monte Carlo was used.

## Raw reproduction first

| quantity                                        | expected     |   reproduced | delta   | pass   |
|:------------------------------------------------|:-------------|-------------:|:--------|:-------|
| S00 selected B-stave pulse records              | 640737       |       640737 | 0       | True   |
| P07d Sample-II analysis B2 selected pulses      | 88213        |        88213 | 0       | True   |
| B2 high-amplitude odd-duplicate validation rows | data-derived |       183132 |         | True   |

## Method

Rows are B2 pulses. The correction models are trained leave-one-run-out on clean even-channel B2 pulses after pseudo-saturation; the paired odd channel is never used as a feature or correction target.

- `observed_raw`: no saturation correction.
- `traditional_template`: P07d-style train-run median template scale using non-plateau even samples.
- `ml_ratio_transfer`: ExtraTrees regression on normalized even waveform ratio-transfer features.

Odd duplicate readout is used only for held-out validation. Charge closure predicts odd positive-lobe charge from the corrected even amplitude via a train-run Huber log-polynomial calibration. Timing closure compares corrected even CFD20 time to odd-channel CFD20 time after subtracting the train-run clean B2 even-minus-odd offset.

## Pseudo-saturation correction check

| method               |   res68_abs_frac |   bias_median_frac |   within10_frac |
|:---------------------|-----------------:|-------------------:|----------------:|
| ml_ratio_transfer    |        0.0366906 |         7.0742e-05 |        0.904478 |
| observed_raw         |        0.354839  |        -0.2        |        0.262127 |
| traditional_template |        0.2       |        -0.047619   |        0.45348  |

## Held-out duplicate closure

| method               |      n |   charge_bias_median_frac |   charge_res68_abs_frac |   time_bias_median_ns |   time_abs68_ns | run_block_charge_res68_abs_frac_ci95       | run_block_time_abs68_ns_ci95               | run_block_charge_bias_median_frac_ci95     | run_block_time_bias_median_ns_ci95            |
|:---------------------|-------:|--------------------------:|------------------------:|----------------------:|----------------:|:-------------------------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------------|
| ml_ratio_transfer    | 183132 |                  0.154948 |                0.176358 |             0.178406  |        0.220605 | [0.17304334869529975, 0.18060166173702746] | [0.2137683276636733, 0.23466475255692154]  | [0.1525778552913315, 0.15802435221286845]  | [0.17193704851629024, 0.18492282619839182]    |
| observed_raw         | 183132 |                  0.100448 |                0.120794 |            -0.0428608 |        0.148463 | [0.11700387021774719, 0.12536373643016782] | [0.11943029120390704, 0.1851321491324999]  | [0.09782159237209265, 0.10340914211350964] | [-0.06421228809703039, -0.018923137962426152] |
| traditional_template | 183132 |                  0.100449 |                0.120778 |            -0.0426048 |        0.148839 | [0.11616875861201786, 0.1248512145266728]  | [0.11498764643341562, 0.18108948870397104] | [0.09724743354911794, 0.10321446400358855] | [-0.06309106375260613, -0.015271620196904857] |

## Per-run closure

| method               |   runs |   min_n |   median_charge_res68 |   worst_charge_res68 |   median_time_abs68_ns |   worst_time_abs68_ns |
|:---------------------|-------:|--------:|----------------------:|---------------------:|-----------------------:|----------------------:|
| ml_ratio_transfer    |     33 |     144 |              0.186756 |             0.222238 |               0.274223 |              0.447689 |
| observed_raw         |     33 |     144 |              0.130269 |             0.164986 |               0.20951  |              0.547694 |
| traditional_template |     33 |     144 |              0.130269 |             0.164986 |               0.209776 |              0.547694 |

The full held-out per-run table, including event-bootstrap CIs for every run and method, is in `duplicate_closure_by_run.csv`.

## Leakage checks

- Split: `leave-one-run-out by run over all B-stack runs with high-amplitude B2 duplicate rows`.
- Correction features exclude run id, event id, odd-channel samples, odd charge, odd time, downstream channels, and held-out labels.
- Odd-channel charge calibration uses only training-run clean rows; held-out high-amplitude odd targets are evaluation-only.
- Exact even-waveform hash overlap between train clean rows and held-out high rows: `0`.
- Too-good trigger fired: `False`.

## Finding

Against 183132 held-out high-amplitude B2 duplicate rows, the P07d-style corrections do not improve odd-channel charge closure: raw charge res68 is 0.1208, traditional is 0.1208, and ML is 0.1764. Timing closure is also worse after correction: raw abs68 is 0.148 ns, traditional is 0.149 ns, and ML is 0.221 ns. The duplicate readout therefore does not support applying the ratio-transfer correction to real high-amplitude B2 pulses as a closure improvement.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.py --config configs/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.json
```
