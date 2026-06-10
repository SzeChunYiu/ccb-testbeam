# P10f: Run64-only external B2-B8 closure

- **Ticket:** 1781024829.1351.5f391cfe
- **Worker:** testbeam-laptop-3
- **Input:** raw B-stack ROOT under `data/root/root`
- **Monte Carlo:** none
- **Git commit:** 8619515b20fbfeb3a66b29b4ede17cc7614d28bf

## Raw reproduction first

The selected-pulse table was rebuilt from raw `h101/HRDv` before fitting either correction.

| quantity                                             |   expected |   reproduced |   delta | pass   |
|:-----------------------------------------------------|-----------:|-------------:|--------:|:-------|
| S00/P10 selected B-stave pulses                      |     640737 |       640737 |       0 | True   |
| Sample-II analysis selected B-stave pulses           |     125096 |       125096 |       0 | True   |
| Sample-II calibration run 64 selected B-stave pulses |      14630 |        14630 |       0 | True   |

The original P10c run64-only downstream number was then recomputed on B4/B6/B8 all-hit events before the external B2-inclusive test.

| P10c downstream method | sigma68 ns | 95% CI |
|---|---:|---:|
| Base phase template | 2.78661 | [2.69164, 2.88897] |
| Traditional explicit | 2.05255 | [1.91544, 2.24604] |
| ML explicit | 1.98898 | [1.86869, 2.13262] |

## Methods

Split: train only on run 64; evaluate held-out Sample-II analysis runs 58-63 and 65, then bootstrap by held-out run.

Traditional method: P10c train-run-only empirical phase templates plus a stave-by-amplitude-bin median explicit timewalk correction. B2 is not used as a fitted target and receives no explicit correction in the external closure.

ML method: P10c ridge residual correction using same-pulse amplitude, area/amplitude, peak, amplitude-bin, and stave features. The single-run default is `amp_bin_by_stave` at alpha `100.0`.

External population: B2/B4/B6/B8 all have `A>1000 ADC`; train target pulses `621`; traditional fallback bins `15`.

## External B2-B8 Closure

Metric: per-run `sigma68` over all six B2/B4/B6/B8 pairs after geometry correction; values and CIs bootstrap held-out runs.

| Method | sigma68 ns | 95% CI |
|---|---:|---:|
| Base phase template | 3.27235 | [3.04411, 3.50092] |
| Traditional explicit | 3.65126 | [3.42481, 3.85939] |
| ML explicit | 3.63616 | [3.40901, 3.85738] |
| ML shuffled target | 3.80459 | [3.51499, 4.11669] |

| Delta | ns | 95% CI |
|---|---:|---:|
| Traditional - base | 0.378912 | [0.167824, 0.651202] |
| ML - base | 0.363811 | [0.135482, 0.612818] |
| ML - traditional | -0.0151007 | [-0.0781574, 0.0527396] |
| ML shuffled - ML | 0.168432 | [-0.116616, 0.417042] |

## Leakage Checks

| check                                       |    value | pass   |
|:--------------------------------------------|---------:|:-------|
| train_heldout_run_overlap                   | 0        | True   |
| train_heldout_event_overlap                 | 0        | True   |
| b2_rows_used_in_target_fit                  | 0        | True   |
| run_event_or_target_features_used           | 0        | True   |
| ml_shuffled_target_worse_than_real_external | 0.168432 | True   |
| too_good_external_sigma68_lt_1ns            | 0        | True   |

Run id, event id, event order, cross-stave timing, and held-out residuals are excluded from model inputs. Targets are computed only on run 64 for fitting. No train/held-out event or run overlap was found, and the shuffled-target ML control is worse than the real ML fit.

## Finding

The run64-only correction does not give a resolved improvement on the B2-inclusive all-hit closure.

Files: `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, correction tables, and leakage checks are in this report directory.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.py --config configs/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.json
```
