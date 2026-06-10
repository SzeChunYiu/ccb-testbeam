# Study report: S16e - tagged random-trigger pedestal validation

- **Ticket:** 1781007587.2616.535e78de
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Depends on:** S00, S16
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `1b0991048977edbb36fff268733b5cbb6e3174ca`
- **Config:** `s16e_config.json`

## 0. Question

Once tagged forced/random B-stack pedestal events exist, does `adaptive_pc_excluding_target` have zero mean bias against held-out no-pulse samples by run?

## 1. Reproduction and gate

Raw ROOT was audited before modeling. The ticket premise requires tagged random/forced B-stack no-pulse entries; the current mirror does not contain them.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| tagged random/forced B-stack entries | 1 | 0 | -1 | minimum | no |

The tagged-random count uses raw `h101/TRIGGER` and filename tags. Across all raw HRD files there are `3302310` entries and `0` entries with `TRIGGER != 1`; B-stack contributes `0` tagged candidates. Sorted B-stack files were also scanned for tag-like branches and have `0` tag-like branches. This fails the primary S16e data-availability gate, so no true random-trigger pedestal validation can be claimed.

## 2. Traditional method

Because the tagged no-pulse sample is absent, the only valid traditional result in this report is a reproduction of the prior S16 leave-one-pre-trigger-out baseline from raw ROOT. It uses held-out runs `[57, 65]`, excludes the target pre-trigger sample from each estimate, and reports run-heldout bootstrap intervals.

Traditional estimators are `median3`, `mean3`, and `adaptive_pc`, where `adaptive_pc` is the S16 positivity-constrained lowering with the target sample excluded. This is not a substitute for true tagged random triggers.

## 3. ML method

The fallback ML reproduction is a run-split ridge regressor with group CV by run and linear calibration on runs `[56, 64]`. Features exclude run ID, event identifiers, and the target held-out sample. Best CV setting: `{'alpha': 100.0, 'cv_mae_adc': 173.18638012247075, 'cv_mae_std_adc': 5.216573145287647}`.

## 4. Head-to-head fallback benchmark

All rows below are the fallback S16 pre-trigger benchmark, not a tagged-random benchmark.

| Method | n | MAE [ADC] | Mean bias [ADC] | RMSE [ADC] |
|---|---:|---:|---:|---:|
| ml_ridge_calibrated | 962 | 197.28 [149.13, 244.90] | -15.53 [-49.57, 22.67] | 460.85 [336.05, 575.83] |
| mean3 | 962 | 241.63 [146.43, 342.92] | 1.73 [-48.62, 53.50] | 752.48 [521.00, 945.48] |
| median3 | 962 | 260.27 [165.72, 349.46] | -32.83 [-86.36, 25.52] | 866.04 [647.02, 1052.09] |
| adaptive_pc | 962 | 293.02 [154.60, 464.31] | -267.02 [-423.08, -136.03] | 1160.32 [643.52, 1659.32] |

Held-out run breakdown:

| Method | Run | n | Mean bias [ADC] | MAE [ADC] |
|---|---:|---:|---:|---:|
| adaptive_pc | 57 | 499 | -361.87 | 395.16 |
| adaptive_pc | 65 | 463 | -164.80 | 182.94 |
| mean3 | 57 | 499 | 15.00 | 306.54 |
| mean3 | 65 | 463 | -12.56 | 171.66 |
| median3 | 57 | 499 | -15.44 | 320.45 |
| median3 | 65 | 463 | -51.57 | 195.41 |
| ml_ridge_calibrated | 57 | 499 | 0.69 | 229.87 |
| ml_ridge_calibrated | 65 | 463 | -33.00 | 162.16 |

On the sampled fallback head-to-head, adaptive mean bias is -267.02 ADC and MAE is 293.02 ADC. The prior S16 conclusion remains falsified on the pre-trigger benchmark: adaptive bias CI excludes zero, and adaptive MAE is +32.75 ADC versus `median3`. ML MAE is 197.28 ADC, but that does not answer the S16e tagged-random question.

## 5. Leakage checks

| Check | Result |
|---|---|
| tagged_random_gate | failed: 0 tagged B-stack candidates |
| real_ml_feature_exclusion | fallback ML excludes run, pulse_index/event IDs, and target_adc; feature_columns=stave_idx;holdout_sample;amplitude_adc;peak_sample;pre_mean3;pre_median3;pre_std3;pre_min3;pre_max3;w01_minus_seed;w02_minus_seed;w03_minus_seed;w04_minus_seed;w05_minus_seed;w06_minus_seed;w07_minus_seed;w08_minus_seed;w09_minus_seed;w10_minus_seed;w11_minus_seed;w12_minus_seed;w13_minus_seed;w14_minus_seed;w15_minus_seed;w16_minus_seed;w17_minus_seed;w00_minus_seed |
| shuffled_training_target_control | fallback shuffled-target ridge MAE 489.38 ADC; far worse than real ML means the real fallback signal is not explained by direct target leakage in the training labels |
| proxy_guard | no quiet-event amplitude-selected proxy is promoted to tagged-random validation |

No too-good tagged-random result exists to explain; the main leakage risk is mistaking beam-triggered pre-trigger or quiet-amplitude-selected proxies for true random triggers.

## 6. Threats to validity

- **Benchmark/selection:** The primary tagged-random benchmark is not run because the required tagged sample is absent. The fallback S16 reproduction is clearly labeled.
- **Data leakage:** Fallback ML splits by run; target sample, run ID, and event IDs are excluded from real features.
- **Metric misuse:** The pre-trigger fallback metric is not a no-pulse random-trigger pedestal metric.
- **Post-hoc selection:** The gate, held-out runs, and hyperparameter grid are fixed in `s16e_config.json`.

## 7. Provenance

`manifest.json` records command, git commit, random seed, input sha256s, output sha256s, and environment. `input_sha256.csv` contains the raw ROOT inputs used for the audit and fallback reproduction.

## 8. Findings and next steps

Finding: S16e cannot yet confirm or falsify `adaptive_pc_excluding_target` on tagged random triggers because the data mirror has zero tagged B-stack random/forced pedestal entries. The correct scientific conclusion is a failed data-availability gate, not a proxy validation.

Follow-up tickets queued from this run:
- `S16f: inventory DAQ/run-log sources for true B-stack random or forced-trigger pedestal runs. Expected information gain: resolves whether the S16e gate failed because the sample was never recorded or only missing from this ROOT mirror.`
- `S16g: rerun S16e immediately after tagged random-trigger ROOT is added, with no quiet-event amplitude selection. Expected information gain: directly confirms or falsifies adaptive pedestal zero-bias on true no-pulse samples.`

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python3.7 reports/1781007587.2616.535e78de/s16e_tagged_random_pedestal.py --config reports/1781007587.2616.535e78de/s16e_config.json
```

Outputs: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `trigger_audit.csv`, `sorted_b_tag_audit.csv`, `reproduction_match_table.csv`, `fallback_heldout_benchmark.csv`, `fallback_heldout_by_run.csv`, `ml_cv_scan.csv`, and PNG figures.
