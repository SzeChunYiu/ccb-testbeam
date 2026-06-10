# P10e: B2-included explicit correction closure

- **Ticket:** 1781025482.1523.5eba101d
- **Worker:** testbeam-laptop-2
- **Input:** raw B-stack ROOT under `data/root/root`
- **Monte Carlo:** none
- **Git commit:** 59aaa135cc66d8c8436398a612a2ca572620b9fb

## Raw Reproduction First

The selected-pulse table was rebuilt from raw `h101/HRDv` before fitting either correction.

| quantity                                             |   expected |   reproduced |   delta | pass   |
|:-----------------------------------------------------|-----------:|-------------:|--------:|:-------|
| S00/P10 selected B-stave pulses                      |     640737 |       640737 |       0 | True   |
| Sample-II analysis selected B-stave pulses           |     125096 |       125096 |       0 | True   |
| Sample-II calibration run 64 selected B-stave pulses |      14630 |        14630 |       0 | True   |

The P10f B2-held-out external closure number was then reproduced from the same raw pass before fitting the B2-included target.

| Reproduced P10f external method | sigma68 ns | 95% CI |
|---|---:|---:|
| Base phase template | 3.27235 | [3.04411, 3.51263] |
| Traditional explicit | 3.65126 | [3.44621, 3.86024] |
| ML explicit | 3.63616 | [3.42474, 3.85364] |

All-hit event counts for the timing population:

|   run |   n_events |   selected_pulses |   all_hit_b2_b4_b6_b8_events | used_for_external_timing   |
|------:|-----------:|------------------:|-----------------------------:|:---------------------------|
|    58 |      34141 |             16781 |                           72 | True                       |
|    59 |      42303 |             21377 |                          749 | True                       |
|    60 |      36074 |             17029 |                          802 | True                       |
|    61 |      36535 |             18965 |                          925 | True                       |
|    62 |      37584 |             19089 |                          798 | True                       |
|    63 |      37030 |             18817 |                          365 | True                       |
|    64 |      35943 |             14630 |                          207 | True                       |
|    65 |      38424 |             13038 |                           63 | True                       |

## Methods

Split: train only on run 64; evaluate held-out Sample-II analysis runs 58-63 and 65; bootstrap by held-out run.

Traditional method: empirical phase templates from run 64 plus a stave-by-amplitude-bin median residual correction. The B2-held-out mode fits B4/B6/B8 targets and leaves B2 uncorrected; the B2-included mode fits B2/B4/B6/B8 targets.

ML method: ridge residual correction with same-pulse amplitude, area/amplitude, peak, amplitude-bin, and target-stave one-hot features. Feature set `amp_bin_by_stave`, alpha `100.0`.

B2-held-out train target pulses: `621`; B2-included train target pulses: `828` including `207` B2 pulses.

## External B2-B8 Closure

Metric: per-run `sigma68` over all six B2/B4/B6/B8 pairs after geometry correction.

| Mode and method | sigma68 ns | 95% CI |
|---|---:|---:|
| B2-held-out traditional | 3.65126 | [3.44621, 3.86024] |
| B2-trained traditional | 2.35239 | [2.17195, 2.54176] |
| B2-held-out ML | 3.63616 | [3.42474, 3.85364] |
| B2-trained ML | 2.60598 | [2.41474, 2.81515] |
| B2-trained ML shuffled target | 3.6193 | [3.38208, 3.86119] |

| Paired delta | ns | 95% CI |
|---|---:|---:|
| Traditional B2-trained - B2-held-out | -1.29888 | [-1.49152, -1.13219] |
| ML B2-trained - B2-held-out | -1.03018 | [-1.20467, -0.869533] |
| B2-trained ML - traditional | 0.253594 | [0.17259, 0.342208] |

## Leakage Checks

| check                                          |         value | pass   |
|:-----------------------------------------------|--------------:|:-------|
| train_heldout_run_overlap                      |   0           | True   |
| train_heldout_event_overlap                    |   0           | True   |
| b2_heldout_b2_rows_used_in_target_fit          |   0           | True   |
| b2_included_b2_rows_used_in_target_fit         | 207           | True   |
| run_event_or_target_features_used              |   0           | True   |
| p10f_traditional_reproduction_abs_delta_ns     |   1.29721e-06 | True   |
| p10f_ml_reproduction_abs_delta_ns              |   1.26999e-06 | True   |
| b2_included_ml_shuffled_target_worse_than_real |   1.01332     | True   |
| too_good_external_sigma68_lt_1ns               |   0           | True   |

Run id, event id, event order, cross-stave timing, and held-out residuals are excluded from model inputs. Targets are computed only on run 64 for fitting. The shuffled-target control is evaluated on the same held-out runs.

## Finding

Including B2 as a fitted target improves the external all-six-pair closure relative to the B2-held-out correction.

Files: `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, correction tables, and leakage checks are in this report directory.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10e_1781025482_1523_5eba101d_b2_included_explicit_closure.py --config configs/p10e_1781025482_1523_5eba101d_b2_included_explicit_closure.json
```
