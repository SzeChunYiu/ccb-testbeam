# Study report: P10b - Explicit timewalk terms for amplitude-bin phase templates

- **Ticket:** 1781006250.1276.49814de9
- **Worker:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT under `data/root/root`
- **Config:** `configs/p10b_explicit_timewalk_terms.yaml`
- **Git commit:** 64449c7771e1465b32766ecd30967cc8dcf918ed

## Question

Can explicit train-run-only timewalk terms make the empirical amplitude-bin phase-template timing metric match or beat the P10a conditional timing observation while preserving the S01 q-template advantage?

## Raw-ROOT reproduction gate

The selected-pulse count was rerun from raw ROOT before fitting either method.

| quantity                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses |         640737 |       640737 |       0 |           0 | True   |
| analysis selected rows          |         377362 |       377362 |       0 |           0 | True   |

## Methods

Traditional method: S01-style empirical median templates per B stave and amplitude bin, fit on calibration runs only. For timing, the empirical phase-template pickoff is corrected with explicit same-pulse timewalk terms selected by GroupKFold over train runs and refit only on train runs.

Selected explicit correction: feature_set `amp_bin_by_stave`, ridge alpha `100.0`, train pulses `2460`.

ML method: the P10a conditional MLP maps `[standardized log(amplitude), stave one-hot]` to the waveform template. Hyperparameters were selected by GroupKFold over calibration runs, then the timing model was refit on raw normalized waveforms from calibration runs only.

Selected ML model: hidden_dim=16, depth=2, train_pulses=120000, device=cpu.

## Held-out q_template MSE

Metric: mean squared residual to CFD20-aligned, amplitude-normalized waveforms on analysis runs, summarized by run-bootstrap 95% CIs.

| Method | Value | 95% CI |
|---|---:|---:|
| Empirical amplitude-bin template | 0.044414 | [0.0342219, 0.0553437] |
| Conditional MLP template | 0.078062 | [0.0661582, 0.0905688] |
| Delta conditional - empirical | 0.0336479 | [0.0276969, 0.0411134] |

Verdict on q_template MSE: empirical amplitude bins preserve the S01 advantage.

## Downstream timing residual

Metric: Sample-II B4/B6/B8 all-hit pairwise `sigma68` after geometry correction, evaluated only on held-out runs 58-63 and 65. Values are means of per-run `sigma68`; CIs bootstrap held-out runs.

| Method | Value | 95% CI |
|---|---:|---:|
| Empirical amplitude-bin phase template | 3.83061 ns | [3.73249, 3.93441] |
| Empirical + explicit timewalk terms | 2.75554 ns | [2.64609, 2.86769] |
| Conditional MLP phase template | 3.57886 ns | [3.48574, 3.6801] |
| Delta conditional - explicit timewalk | 0.823316 ns | [0.652502, 0.958597] |

Verdict on timing: explicit timewalk matches or beats the P10a conditional observation.

## Leakage checks

| check                                |     value | unit   |
|:-------------------------------------|----------:|:-------|
| q_calib_analysis_run_overlap         | 0         | runs   |
| timing_train_heldout_run_overlap     | 0         | runs   |
| timing_train_heldout_event_overlap   | 0         | events |
| explicit_shuffled_target_sigma68     | 3.61445   | ns     |
| explicit_uses_run_or_event_features  | 0         | bool   |
| explicit_final_fit_uses_heldout_rows | 0         | bool   |
| conditional_shuffled_q_mse           | 0.0742433 | mse    |

Feature audit: the explicit correction uses only same-pulse amplitude-derived terms, area/amp, peak sample, and stave identity. It does not use run number, event id, event order, other-stave timing, or held-out labels as model inputs. The target uses same-event downstream residuals only on train runs for fitting; held-out targets are computed only for diagnostics. The ML comparator uses the P10a stave/log-amplitude inputs.

## Files

`result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSVs, leakage checks, and figures are in this report directory. No Monte Carlo was used.
