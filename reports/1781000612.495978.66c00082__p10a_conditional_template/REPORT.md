# Study report: P10a - Conditional template vs empirical amplitude bins

- **Ticket:** 1781000612.495978.66c00082
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** bd9702b70b7e47756fabe1fef4926857aefe8a0c
- **Config:** `configs/p10a_conditional_template.yaml`

## Question

Can a conditional template generator using only stave identity and log amplitude beat the S01 empirical median amplitude-bin family on the same held-out `q_template` MSE and downstream timing residual metrics?

## Reproduction gate

The S00/S01 selected-pulse count was rerun from raw ROOT before model fitting.

| quantity                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses |         640737 |       640737 |       0 |           0 | True   |
| analysis selected rows          |         377362 |       377362 |       0 |           0 | True   |

## Methods

Traditional baseline: S01-style empirical median templates per B stave and amplitude bin, trained only on calibration runs. Bins below 30 calibration pulses fall back to the stave median.

ML method: a conditional MLP maps `[standardized log(amplitude), stave one-hot]` to the aligned normalized waveform template. Hyperparameters were selected with GroupKFold by run on calibration pulses, then refit on calibration pulses only. Best model: hidden_dim=16, depth=2, train_pulses=120000, device=cpu.

## Held-out q_template MSE

Metric: mean squared residual to CFD20-aligned, amplitude-normalized waveforms on analysis runs, summarized by run-bootstrap 95% CIs.

| Method | Value | 95% CI |
|---|---:|---:|
| Empirical amplitude-bin template | 0.044414 | [0.0342219, 0.0553437] |
| Conditional MLP template | 0.078062 | [0.0661582, 0.0905688] |
| Delta conditional - empirical | 0.0336479 | [0.0276969, 0.0411134] |

Verdict on q_template MSE: empirical amplitude bins remain competitive or better.

## Downstream timing residual

Metric: Sample-II B4/B6/B8 all-hit pairwise `sigma68` after 2 cm geometry correction, evaluated only on held-out analysis runs 58-63 and 65. The value is the mean of per-run `sigma68`; CI is a bootstrap over held-out runs.

| Method | Value | 95% CI |
|---|---:|---:|
| Empirical amplitude-bin phase template | 3.83061 ns | [3.73249, 3.93441] |
| Conditional MLP phase template | 3.57886 ns | [3.48574, 3.6801] |
| Delta conditional - empirical | -0.25175 ns | [-0.37807, -0.133088] |

Verdict on timing: conditional generator wins.

## Leakage checks

- Calibration and analysis run sets are disjoint: `none` overlap.
- Timing train source and held-out timing runs are disjoint by construction; no held-out timing row is used in template fitting.
- Shuffled-target conditional control held-out MSE: 0.0742433; real conditional MSE: 0.078062.
- The ML inputs are only stave identity and local amplitude, not event id, run id, other-stave timing, or downstream residual labels.

The shuffled-target control being slightly below the real conditional model on q MSE is not a leakage success case; it is a warning that the conditional MLP is not learning a stable held-out shape model from stave/log-amplitude alone. The timing improvement is therefore reported as a downstream phase-template observation, not as evidence that P10a beat the S01 empirical template family overall.

## Files

`result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSV, and figures are in this report directory. No Monte Carlo was used.
