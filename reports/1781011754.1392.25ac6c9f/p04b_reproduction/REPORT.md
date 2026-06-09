# P04b External Charge Validation

- **Ticket:** `1781011754.1392.25ac6c9f__p04b_reproduction`
- **Worker:** `testbeam-laptop-2`
- **Raw input:** `data/root/root` HRD B-stack ROOT; no Monte Carlo.
- **External proxy:** penetrating Sample II events with B2/B4/B6/B8 physical even channels selected; target is `B4+B6+B8` positive-lobe charge.
- **Split:** leave-one-run-out over runs `58,59,60,61,62,63,65`; CIs are run-block bootstraps.

## Raw-ROOT P04 Gate

P04 selected-pulse reproduction ran first from raw ROOT: `640,737` vs expected `640,737` (delta `0`).
The reproduced P04 duplicate-readout charge res68 is `0.01507` for ML and `0.19541` for the integral baseline; the stored P04 reference values are `0.01507` and `0.19541`.

## External Benchmark

| method                    |    n |   bias_median_frac | bias_ci95                                   |   res68_abs_frac | res68_ci95                                 |   full_rms_frac |   within_10pct |
|:--------------------------|-----:|-------------------:|:--------------------------------------------|-----------------:|:-------------------------------------------|----------------:|---------------:|
| traditional_loglinear     | 3774 |         -0.0208786 | [-0.07818445128543274, 0.04540190283537153] |         0.224952 | [0.20815880642356355, 0.2383832442514794]  |        0.358759 |       0.325914 |
| p04_duplicate_ml_transfer | 3774 |         -0.0429411 | [-0.09567772926612582, 0.03514820232894597] |         0.246126 | [0.2289559928316179, 0.27184168920435525]  |        0.541938 |       0.296237 |
| external_ml_hgb           | 3774 |         -0.0178855 | [-0.06114069090004423, 0.0256640044644938]  |         0.213174 | [0.20418351065467538, 0.23013743186034644] |        0.268405 |       0.344197 |
| shuffled_external_ml      | 3774 |         -0.054415  | [-0.10673836264760049, 0.02028161211865838] |         0.278239 | [0.26428086468561496, 0.29637065519030614] |        0.609485 |       0.263646 |

Same B2 waveform ML on the same leave-one-run-out rows still closes the duplicate readout at `0.02145` res68, while the best external-proxy result is `0.21317`. That is `14.1x` wider than the original P04 duplicate-readout ML charge number.

## B2 Amplitude Dependence

| b2_amp_bin   | method                    |    n |   bias_median_frac |   res68_abs_frac |   within_10pct |
|:-------------|:--------------------------|-----:|-------------------:|-----------------:|---------------:|
| 1000_2000    | traditional_loglinear     |  516 |         0.077217   |         0.269222 |       0.296512 |
| 1000_2000    | p04_duplicate_ml_transfer |  516 |         0.0651426  |         0.278024 |       0.292636 |
| 1000_2000    | external_ml_hgb           |  516 |        -0.00458435 |         0.245854 |       0.335271 |
| 2000_3000    | traditional_loglinear     | 1932 |        -0.0322826  |         0.205281 |       0.34472  |
| 2000_3000    | p04_duplicate_ml_transfer | 1932 |        -0.0624612  |         0.227415 |       0.306936 |
| 2000_3000    | external_ml_hgb           | 1932 |        -0.0244134  |         0.206365 |       0.348861 |
| 3000_5000    | traditional_loglinear     | 1121 |        -0.0602919  |         0.22944  |       0.309545 |
| 3000_5000    | p04_duplicate_ml_transfer | 1121 |        -0.0893867  |         0.248459 |       0.29438  |
| 3000_5000    | external_ml_hgb           | 1121 |        -0.0133939  |         0.209489 |       0.34612  |
| 5000_7000    | traditional_loglinear     |  132 |         0.073657   |         0.379234 |       0.310606 |
| 5000_7000    | p04_duplicate_ml_transfer |  132 |         0.175357   |         0.414779 |       0.212121 |
| 5000_7000    | external_ml_hgb           |  132 |        -0.0221431  |         0.303565 |       0.280303 |
| 7000_inf     | traditional_loglinear     |   73 |         0.0313726  |         0.229218 |       0.315068 |
| 7000_inf     | p04_duplicate_ml_transfer |   73 |         0.292012   |         0.417049 |       0.219178 |
| 7000_inf     | external_ml_hgb           |   73 |        -0.0042852  |         0.199411 |       0.369863 |

## Leakage Audit

- Models are refit separately for each held-out run; no prediction is made by a model trained on that run.
- Feature matrices exclude run id, event ids, downstream charge, downstream stave charges, and same-event target columns.
- Shuffled-target external ML res68 is `0.27824`, well worse than the real external ML result.
- The duplicate-readout result remains very small (`0.02145`), so the much larger external-proxy spread is not a run split implementation artifact.

## Finding

The original P04 duplicate-readout ML charge closure reproduces at res68 0.01507 against the stored 0.01507 reference, but the best run-held-out external downstream-charge proxy is external_ml_hgb with res68 0.21317 [0.20418, 0.23014]. On the same external rows, B2 duplicate-readout ML closure is 0.02145; therefore most of the P04 one-percent-level result is same-event duplicate-readout closure, not demonstrated deposited-energy recovery.

## Artifacts

`result.json`, `manifest.json`, `p04_reproduction_charge.csv`, `external_summary.csv`, `external_by_run.csv`, `external_by_b2_amp.csv`, `external_predictions.csv`, and `counts_by_run.csv`.
