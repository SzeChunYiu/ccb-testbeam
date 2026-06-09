# P04b External Charge Validation

- **Ticket:** `1781005862.2131.4dbf3cf0`
- **Worker:** `testbeam-laptop-2`
- **Raw input:** `data/root/root` HRD B-stack ROOT; no Monte Carlo.
- **External proxy:** penetrating Sample II events with B2/B4/B6/B8 physical even channels selected; target is `B4+B6+B8` positive-lobe charge.
- **Split:** leave-one-run-out over runs `58,59,60,61,62,63,65`; CIs are run-block bootstraps.

## Raw-ROOT P04 Gate

P04 selected-pulse reproduction ran first from raw ROOT: `640,737` vs expected `640,737` (delta `0`).
The reproduced P04 duplicate-readout charge res68 is `0.01528` for ML and `0.19541` for the integral baseline; the stored P04 reference values are `0.01507` and `0.19541`.

## External Benchmark

| method                    |    n |   bias_median_frac | bias_ci95                                     |   res68_abs_frac | res68_ci95                                 |   full_rms_frac |   within_10pct |
|:--------------------------|-----:|-------------------:|:----------------------------------------------|-----------------:|:-------------------------------------------|----------------:|---------------:|
| traditional_loglinear     | 3774 |         -0.0208786 | [-0.07818445128542939, 0.0454019028353824]    |         0.224952 | [0.20815880642356074, 0.2383832442514794]  |        0.358759 |       0.325914 |
| p04_duplicate_ml_transfer | 3774 |         -0.0426987 | [-0.09708073522010001, 0.03481148570034363]   |         0.246971 | [0.2288374196883315, 0.27308179700835594]  |        0.541331 |       0.294383 |
| external_ml_hgb           | 3774 |         -0.0177479 | [-0.058092484863217865, 0.029049075115631724] |         0.211886 | [0.20185244850112732, 0.22896597547782233] |        0.267053 |       0.351351 |
| shuffled_external_ml      | 3774 |         -0.0529666 | [-0.10612794644977706, 0.019189255786429965]  |         0.281161 | [0.2688417889681853, 0.2979973328027958]   |        0.612416 |       0.265236 |

Same B2 waveform ML on the same leave-one-run-out rows still closes the duplicate readout at `0.02127` res68, while the best external-proxy result is `0.21189`. That is `14.1x` wider than the original P04 duplicate-readout ML charge number.

## B2 Amplitude Dependence

| b2_amp_bin   | method                    |    n |   bias_median_frac |   res68_abs_frac |   within_10pct |
|:-------------|:--------------------------|-----:|-------------------:|-----------------:|---------------:|
| 1000_2000    | traditional_loglinear     |  516 |          0.077217  |         0.269222 |       0.296512 |
| 1000_2000    | p04_duplicate_ml_transfer |  516 |          0.0650255 |         0.281534 |       0.292636 |
| 1000_2000    | external_ml_hgb           |  516 |          0.0036544 |         0.245884 |       0.346899 |
| 2000_3000    | traditional_loglinear     | 1932 |         -0.0322826 |         0.205281 |       0.34472  |
| 2000_3000    | p04_duplicate_ml_transfer | 1932 |         -0.0622963 |         0.22716  |       0.305383 |
| 2000_3000    | external_ml_hgb           | 1932 |         -0.0229723 |         0.207304 |       0.350932 |
| 3000_5000    | traditional_loglinear     | 1121 |         -0.0602919 |         0.22944  |       0.309545 |
| 3000_5000    | p04_duplicate_ml_transfer | 1121 |         -0.089039  |         0.248353 |       0.291704 |
| 3000_5000    | external_ml_hgb           | 1121 |         -0.010023  |         0.20463  |       0.357716 |
| 5000_7000    | traditional_loglinear     |  132 |          0.073657  |         0.379234 |       0.310606 |
| 5000_7000    | p04_duplicate_ml_transfer |  132 |          0.178727  |         0.409957 |       0.204545 |
| 5000_7000    | external_ml_hgb           |  132 |         -0.0369918 |         0.301398 |       0.30303  |
| 7000_inf     | traditional_loglinear     |   73 |          0.0313726 |         0.229218 |       0.315068 |
| 7000_inf     | p04_duplicate_ml_transfer |   73 |          0.290422  |         0.409943 |       0.219178 |
| 7000_inf     | external_ml_hgb           |   73 |          0.0237673 |         0.21303  |       0.383562 |

## Leakage Audit

- Models are refit separately for each held-out run; no prediction is made by a model trained on that run.
- Feature matrices exclude run id, event ids, downstream charge, downstream stave charges, and same-event target columns.
- Shuffled-target external ML res68 is `0.28116`, well worse than the real external ML result.
- The duplicate-readout result remains very small (`0.02127`), so the much larger external-proxy spread is not a run split implementation artifact.

## Finding

The original P04 duplicate-readout ML charge closure reproduces at res68 0.01528 against the stored 0.01507 reference, but the best run-held-out external downstream-charge proxy is external_ml_hgb with res68 0.21189 [0.20185, 0.22897]. On the same external rows, B2 duplicate-readout ML closure is 0.02127; therefore most of the P04 one-percent-level result is same-event duplicate-readout closure, not demonstrated deposited-energy recovery.

## Artifacts

`result.json`, `manifest.json`, `p04_reproduction_charge.csv`, `external_summary.csv`, `external_by_run.csv`, `external_by_b2_amp.csv`, `external_predictions.csv`, and `counts_by_run.csv`.
