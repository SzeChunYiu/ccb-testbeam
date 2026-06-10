# Study report: S16 - Pedestal/baseline validation

- **Study ID:** S16
- **Author (worker label):** testbeam-laptop-1
- **Date:** 2026-06-09
- **Depends on:** S00
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `5eab4d9a2c2e25b77c2782f454c4a794837db321`
- **Config:** `s16_config.json`

## 0. Question

Is the adaptive positivity-constrained pedestal unbiased for selected B-stack pulses, especially at low amplitude, when tested against pre-trigger samples that were not used to build the pedestal estimate?

Atomic steps:
- Reproduce the S00 selected-pulse population from raw ROOT.
- Reproduce the constructed adaptive-pedestal guarantee that corrected non-jagged samples are above `-epsilon(A)`.
- Benchmark simple pre-trigger estimators, adaptive positivity correction, and a run-split ML regressor against held-out pre-trigger samples.
- Quantify bias versus amplitude and identify whether forced/random-trigger pedestal data exists in the current mirror.

## 1. Reproduction

Raw ROOT reproduction used `h101/HRDv` from `data/root/root/hrdb_run_NNNN.root`, the S00 B-stave channel map, median samples 0-3, and the fixed `A > 1000 ADC` cut.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| adaptive post-correction violations | 0 | 0 | 0 | 0 | yes |

The second line is a sanity reproduction only: the zero-violation result is true by construction and is not accepted as an independent validation.

## 2. Traditional (non-ML) method

The validation target is a held-out pre-trigger sample. For each selected pulse and each pre-trigger index k in samples 0-3, the estimator used only the other three pre-trigger samples. The benchmark then compared the pedestal estimate to sample k. The adaptive method starts from the leave-one-out median and lowers the pedestal only enough to satisfy `min(non-jagged corrected samples excluding k) >= -epsilon(A)`, with `epsilon=max(25 ADC, 0.015*A)`.

Held-out runs were fixed before analysis: 57 and 65. Traditional benchmark on those runs:

| Method | MAE [ADC] | Mean bias [ADC] | RMSE [ADC] | n |
|---|---:|---:|---:|---:|
| median3 | 273.64 | -51.19 | 929.83 | 3761 |
| mean3 | 260.70 | -14.79 | 833.33 | 3761 |
| adaptive_pc | 341.04 | -310.69 | 1211.69 | 3761 |

No parametric fit is used, so chi2/ndf is not applicable. Full residual distributions are in `fig_heldout_residual_distributions.png`; amplitude-binned bias is in `fig_bias_by_amplitude.png`; adaptive lowering is in `fig_adaptive_lowering.png`.

## 3. ML method

The ML method is a histogram-gradient-boosted regressor predicting the held-out pre-trigger sample from the other pre-trigger samples, waveform samples excluding the held-out sample, stave, holdout index, provisional amplitude, and peak sample. The split is by run: test runs 57 and 65, calibration runs 56 and 64, all remaining configured runs for model development. Hyperparameter CV scanned `max_leaf_nodes`, `learning_rate`, and `l2_regularization`; the best setting was `{'max_leaf_nodes': 31.0, 'learning_rate': 0.08, 'l2_regularization': 0.0}` with CV MAE `39.90 ADC`.

The final regressor was linearly calibrated on runs 56 and 64. Calibration is a regression bias correction, not probability calibration. Its held-out calibration check is shown in `fig_ml_calibration.png`.

## 4. Head-to-head benchmark

All methods are evaluated on the same held-out LOPO records from runs 57 and 65 with the same metric.

| Method | Metric | Value +/- CI | Notes |
|---|---|---:|---|
| ml_hgbr_calibrated | held-out pre-trigger MAE [ADC] | 48.88 [43.82, 55.29] | run-split ML |
| mean3 | held-out pre-trigger MAE [ADC] | 260.70 [236.25, 287.99] | traditional |
| median3 | held-out pre-trigger MAE [ADC] | 273.64 [244.24, 302.67] | traditional |
| adaptive_pc | held-out pre-trigger MAE [ADC] | 341.04 [300.45, 373.27] | traditional |

Verdict: ML has the lowest held-out MAE (48.88 ADC), beating adaptive_pc by 292.16 ADC; the gain is small relative to the residual width, so the simple median remains the pragmatic pedestal estimator unless a forced-trigger validation shows otherwise.

## 5. Falsification

- **Pre-registration:** `s16_config.json` fixed the primary metric before running the scan: held-out pre-trigger residual MAE and mean bias on runs 57 and 65. The adaptive pedestal would be considered unbiased only if its mean-bias CI included 0 ADC and its MAE was not worse than the simple leave-one-out median by more than 5 ADC.
- **Falsification test:** the adaptive method fails the primary claim if the held-out mean-bias CI excludes 0 ADC or if its held-out MAE exceeds the median baseline by more than 5 ADC.
- **Result:** adaptive mean-bias CI -310.69 [-347.59, -277.34] ADC; MAE 341.04 [300.45, 373.27] ADC versus median MAE 273.64 [244.24, 302.67] ADC. The pre-registered adaptive-unbiased criterion fails.

## 6. Threats to validity

- **Benchmark/selection:** the simple median/mean baselines are strong for four pre-trigger samples; the adaptive method is not credited for satisfying its own positivity constraint.
- **Data leakage:** ML and benchmark splits are by run. The held-out pre-trigger sample is excluded from all estimator features and from the adaptive positivity constraint.
- **Metric misuse:** the primary metric is residual bias/MAE against an independent pre-trigger sample, with full residual distributions and amplitude-binned summaries. This does not prove the true zero-signal pedestal for pulses whose pre-trigger region is already contaminated.
- **Post-hoc selection:** amplitude bins, held-out runs, jagged definition, ML hyperparameter grid, and pass/fail rule are fixed in `s16_config.json`.

## 7. Provenance manifest

`manifest.json` records the command, input ROOT hashes, output hashes, random seed, git commit, and config. All generated artifacts are in this report directory.

## 8. Findings & next steps

The current data mirror contains beam-triggered HRD ROOT files but no separate forced/random-trigger pedestal sample found by filename or ROOT branch inspection. The leave-one-pre-trigger-out test is therefore the available independent check in this sandbox.

The adaptive pedestal lowers the leave-one-out median in 9.75% of LOPO records, but on the held-out pre-trigger benchmark its mean bias is -310.69 ADC and its MAE is 341.04 ADC. The simple median3 baseline has MAE 273.64 ADC, and the calibrated ML regressor has MAE 48.88 ADC.

Hypothesis: large adaptive lowering is mainly a diagnostic for early waveform contamination or pulse-shape pathologies, not an independent proof of pedestal accuracy; a true forced-trigger pedestal sample should show near-zero bias without needing the positivity constraint.

Recommended next tickets:
- S16b: acquire or locate forced/random-trigger pedestal events and repeat this benchmark with no pulse signal in the validation target. Expected information gain: separates true electronics pedestal bias from pre-trigger contamination in physics events.
- S16c: propagate adaptive-pedestal lowering into S02/S04 timing residuals as a nuisance covariate. Expected information gain: tests whether baseline contamination is a timing-resolution tail driver rather than only an amplitude diagnostic.

## 9. Reproducibility

```bash
python reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/run_s16_analysis.py --config reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/s16_config.json
```

Output artifacts:
`reproduction_match_table.csv`, `run_counts.csv`, `traditional_summary.csv`, `bias_by_amp_stave.csv`, `heldout_benchmark.csv`, `ml_cv_scan.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and the four PNG figures.
