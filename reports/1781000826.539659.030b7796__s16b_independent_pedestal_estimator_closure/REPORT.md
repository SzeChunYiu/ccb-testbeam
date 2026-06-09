# Study report: S16b - Independent pedestal estimator closure

- **Study ID:** S16b
- **Ticket:** 1781000826.539659.030b7796
- **Author (worker label):** testbeam-laptop-4
- **Date:** 2026-06-09
- **Depends on:** S00a, S16
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `bbe447eca2a2c8f5f3fb123fa4db21573dc0fdf9`
- **Config:** `s16b_config.json`

## 0. Question

Which early-sample baseline estimator is least biased by pre-trigger activity?

Atomic steps:
- Reproduce the selected B-stave pulse count from raw `h101/HRDv` ROOT before using derived quantities.
- Compare strong non-ML early-sample estimators in a leave-one-pretrigger-sample closure test.
- Train one run-split ML closure estimator on the same target and benchmark it with held-out bootstrap CIs.
- Audit leakage because the ML closure can look very strong when later pulse-shape samples predict an early contaminated sample.

## 1. Reproduction

Raw ROOT reproduction used `data/root/root/hrdb_run_NNNN.root`, physical B-stack channels B2/B4/B6/B8, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Expected | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | 0 | yes |

## 2. Traditional method

The independent target is one excluded pre-trigger sample from samples 0-3. Every traditional estimator sees only the other three early samples. The strongest conventional option is `train_calibrated_low2`: the mean of the two lowest visible early samples with a Huber calibration trained only on non-held-out runs using holdout index, stave, early-sample range, amplitude, and peak sample.

Held-out runs were fixed as 57 and 65. Traditional benchmark:

| Method | MAE [ADC] | Mean bias [ADC] | n |
|---|---:|---:|---:|
| line3_predict | 169.34 | -28.63 | 981 |
| train_calibrated_low2 | 211.42 | -95.98 | 981 |
| low2_mean3 | 211.65 | -97.38 | 981 |
| min3 | 218.10 | -161.56 | 981 |
| mean3 | 227.96 | 12.21 | 981 |
| median3 | 229.76 | -33.19 | 981 |

Bias versus the visible pre-trigger activity proxy is in `fig_bias_by_pretrigger_activity.png`.

## 3. ML method

The ML method is a regularized ridge regressor predicting the excluded early sample. It uses the other early samples, full waveform samples except the excluded sample, stave, holdout index, provisional amplitude, and peak sample. The split is by run: runs 57 and 65 are never used in training or calibration; runs 56 and 64 are used only for final linear calibration.

Best CV setting: `{'alpha': 1000.0}` with non-held-out GroupKFold MAE `154.73 ADC`. The held-out ML MAE is `173.71 [149.60, 198.53] ADC`.

## 4. Head-to-head benchmark

All rows below use the same sampled held-out records and held-out bootstrap CIs.

| Method | Metric | Value +/- CI | Mean bias +/- CI |
|---|---|---:|---:|
| line3_predict | held-out excluded-sample MAE [ADC] | 169.34 [135.28, 200.24] | -28.63 [-63.36, 5.29] |
| ml_ridge_calibrated | held-out excluded-sample MAE [ADC] | 173.71 [149.60, 198.53] | -3.01 [-28.64, 26.76] |
| train_calibrated_low2 | held-out excluded-sample MAE [ADC] | 211.42 [167.23, 264.49] | -95.98 [-147.72, -51.69] |
| low2_mean3 | held-out excluded-sample MAE [ADC] | 211.65 [167.87, 256.87] | -97.38 [-147.22, -52.45] |
| min3 | held-out excluded-sample MAE [ADC] | 218.10 [166.72, 267.94] | -161.56 [-220.30, -112.24] |
| mean3 | held-out excluded-sample MAE [ADC] | 227.96 [187.39, 265.73] | 12.21 [-32.42, 56.25] |
| median3 | held-out excluded-sample MAE [ADC] | 229.76 [186.46, 275.98] | -33.19 [-81.92, 15.93] |

Paired ML minus best-traditional MAE delta: `4.38 [-15.61, 19.58]` ADC. Verdict: line3_predict remains the preferred non-ML estimator; ML is not accepted as a pedestal improvement under the leakage-aware win rule.

## 5. Leakage audit

| Check | Result |
|---|---|
| train/test runs disjoint | pass: train=[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 58, 59, 60, 61, 62, 63, 64] test=[57, 65] |
| excluded sample feature row-masked | pass: holdout 0 w00_minus_seed NaN fraction=1.000; holdout 1 w01_minus_seed NaN fraction=1.000; holdout 2 w02_minus_seed NaN fraction=1.000; holdout 3 w03_minus_seed NaN fraction=1.000 |
| train/test event-key overlap | pass: 0 |
| shuffled-target ML held-out MAE larger than real ML | pass: shuffled=508.63 real=173.71 |

The ML result is therefore treated as a closure predictor, not as an adopted pedestal estimator. Later waveform samples can encode the same pulse that contaminates the pre-trigger region; that is useful for diagnosing contamination but not an independent zero-signal pedestal measurement.

## 6. Threats to validity

- **No forced-trigger sample in this mirror:** this is a leave-one-early-sample closure, not a direct electronics pedestal truth test.
- **Target semantics:** a predicted early sample may include pre-trigger pulse activity; low MAE does not prove an unbiased pedestal.
- **Only two held-out runs:** the train/test split is by run, but bootstrap CIs are held-out record CIs and should be interpreted as conditional on these runs.
- **Estimator selection:** the non-ML candidates and ML grid are fixed in `s16b_config.json`.

## 7. Findings

The lowest-MAE traditional estimator is `line3_predict` with MAE 169.34 ADC and mean bias -28.63 ADC; its bias CI -28.63 [-63.36, 5.29] includes zero. ML reaches MAE 173.71 ADC, but the result is interpreted only as a contamination closure diagnostic.

Recommended follow-up tickets:
- S16d: search DAQ metadata and raw mirrors for forced/random-trigger HRD pedestal events, then repeat S16b with no-pulse targets.
- S16e: add the S16b pre-trigger activity proxy to S02 timing residual fits to test whether early contamination explains timing tails.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781000826.539659.030b7796__s16b_independent_pedestal_estimator_closure/run_s16b_analysis.py --config reports/1781000826.539659.030b7796__s16b_independent_pedestal_estimator_closure/s16b_config.json
```

Output artifacts include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `heldout_benchmark.csv`, `leakage_checks.csv`, and diagnostic figures.
