# P10c: Sample-II-only explicit timewalk transfer check

- **Ticket:** 1781012359.1143.5d9c3b2a
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input:** raw ROOT under `data/root/root`
- **Git commit:** 41c2556a71c7f0be7299f8bb046ec890773df984

## Raw reproduction first

The script rebuilt the selected B-stave pulse table directly from `h101/HRDv` before fitting any correction.

| quantity                                             |   expected |   reproduced |   delta | pass   |
|:-----------------------------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses                      |     640737 |       640737 |       0 | True   |
| Sample-II analysis selected B-stave pulses           |     125096 |       125096 |       0 | True   |
| Sample-II calibration run 64 selected B-stave pulses |      14630 |        14630 |       0 | True   |

## Methods

Held-out evaluation uses Sample-II analysis runs 58-63 and 65. The split is by run: run 64 is the Sample-II-only calibration; the pooled calibration is Sample-I calibration runs 31-42 plus run 64.

Traditional method: train-run-only empirical phase templates, then a hand-built explicit timewalk correction using median target residuals in stave by amplitude bins, with stave fallback for sparse bins.

ML method: a ridge residual model using only same-pulse amplitude-derived features, peak sample, area/amplitude, amplitude-bin terms, and stave identity. Pooled hyperparameters are selected by GroupKFold over train runs; the single-run case uses the predeclared `amp_bin_by_stave`, alpha 100 setting.

## Held-out timing

Values are means of per-run B4/B6/B8 pairwise sigma68; 95% CIs bootstrap held-out runs.

| calibration | base phase template | traditional explicit | ML explicit | shuffled ML |
|---|---:|---:|---:|---:|
| sample_ii_only | 2.787 ns [2.689, 2.889] | 2.053 ns [1.91, 2.24] | 1.989 ns [1.872, 2.133] | 3.15 ns [3.021, 3.283] |
| pooled | 3.831 ns [3.724, 3.936] | 2.808 ns [2.659, 2.959] | 2.756 ns [2.64, 2.873] | 4.024 ns [3.917, 4.132] |

## Transfer comparison

| comparison | delta | 95% CI |
|---|---:|---:|
| sample-II-only traditional - pooled traditional | -0.7551 ns | [-0.9079, -0.6118] |
| sample-II-only ML - pooled ML | -0.7666 ns | [-0.8966, -0.611] |

Negative values favor Sample-II-only calibration; positive values favor pooled calibration.

## Leakage checks

| scenario       | check                                 |   value | pass   |
|:---------------|:--------------------------------------|--------:|:-------|
| sample_ii_only | train_eval_run_overlap                | 0       | True   |
| sample_ii_only | train_eval_event_overlap              | 0       | True   |
| sample_ii_only | model_inputs_exclude_run_event_target | 1       | True   |
| sample_ii_only | ml_shuffled_target_worse_than_real    | 1.16074 | True   |
| pooled         | train_eval_run_overlap                | 0       | True   |
| pooled         | train_eval_event_overlap              | 0       | True   |
| pooled         | model_inputs_exclude_run_event_target | 1       | True   |
| pooled         | ml_shuffled_target_worse_than_real    | 1.26832 | True   |

No run or event identifier enters either correction model. Targets are computed only on calibration runs for fitting; held-out run residuals are used only after predictions are fixed. Shuffled-target ML controls are worse than the corresponding real ML fits, and no train/eval run or event overlap was found.

## Finding

Run-64-only Sample-II traditional explicit calibration is better than pooled calibration on held-out Sample-II timing.

No Monte Carlo was used. `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV tables, correction tables, leakage checks, and figures are in this directory.

## Reproduce

```bash
/home/billy/anaconda3/bin/python p10c_sample_ii_explicit_timewalk_transfer.py --config p10c_config.json
```
