# S07e: all-three-downstream curvature-only timing-control RF audit

- **Ticket:** 1781006037.1500.1d8044e2
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT in `data/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65

## Question
If App.I is restricted to events with B2 and all three downstream staves selected, how much of the waveform RF score remains when missing-stave topology is removed and the conventional baseline is only curvature `|C_t| = |t_B8 - 2t_B6 + t_B4|`?

## Raw Reproduction First
The parent App.I control population is recomputed from raw ROOT with baseline median samples 0-3, `A>1000` ADC, CFD20 times, B2 selected, and at least two downstream staves selected.

| quantity                                     | report_value | reproduced | delta | tolerance | pass |
| -------------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| parent control events, B2 and >=2 downstream |              | 10156      |       |           | True |
| parent clean events, D_t<3 ns                |              | 2155       |       |           | True |
| parent gross events, documented D_t>50 ns    |              | 74         |       |           | True |
| parent gross events, guarded D_t>51 ns       | 72           | 72         | 0     | 0         | True |
| S07e all-three control events                |              | 3774       |       |           | True |
| S07e all-three guarded gross events          |              | 22         |       |           | True |

The guarded `D_t>51 ns` count reproduces the documented App.I **72 gross events** exactly before the S07e all-three restriction is applied. The all-three subset keeps 3774 control events and 22 guarded gross events.

Run-level counts:

| run | raw_events | parent_control_events | all_three_events |
| --- | ---------- | --------------------- | ---------------- |
| 58  | 34141      | 201                   | 72               |
| 59  | 42303      | 2161                  | 749              |
| 60  | 36074      | 2025                  | 802              |
| 61  | 36535      | 2319                  | 925              |
| 62  | 37584      | 2154                  | 798              |
| 63  | 37030      | 1045                  | 365              |
| 65  | 38424      | 251                   | 63               |

## Methods
Labels remain the App.I timing extremes: clean if `D_t<3 ns`, gross if `D_t>51 ns`; intermediate events are excluded from the classifier benchmark. All benchmark rows have B4, B6, and B8 selected, so the missing-stave topology channel is constant.

- **Traditional:** pre-registered curvature-only score `|C_t|`; no `D_t`, no amplitude, no topology.
- **ML:** random forest over amplitude-normalized waveform shapes for B2/B4/B6/B8 and downstream aggregate shape summaries. It excludes run id, event id, `D_t`, `C_t`, absolute amplitudes, present flags, and missing-stave slots.
- **Uncertainty:** leave-one-run-out predictions with run-block bootstrap 95% CIs.

## Head-to-Head
| method                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier      | notes                                                                                                          |
| -------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ---------- | -------------------------------------------------------------------------------------------------------------- |
| curvature-only traditional | 1        | 1              | 1               | 1                 | 1         | 1          | 0.00399976 | Pre-registered \|C_t\| only; all benchmark rows have B4/B6/B8 selected.                                        |
| shape-only RF              | 0.992778 | 0.980488       | 1               | 0.92781           | 0.766222  | 1          | 0.0074835  | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; normalized shape only; 143 features. |

At fixed 95% clean efficiency, mean gross rejection over held-out runs with gross examples is:

| method                     | gross_rejection |
| -------------------------- | --------------- |
| curvature-only traditional | 1               |
| shape-only RF              | 0.96            |

## Leakage Hunt
| probe                                  | roc_auc  | average_precision | notes                                                                       |
| -------------------------------------- | -------- | ----------------- | --------------------------------------------------------------------------- |
| missing-stave topology                 |          |                   | Removed by construction: n_downstream unique=[3].                           |
| curvature separation audit             | 1        | 1                 | Perfect because max clean \|C_t\|=5.436 ns and min gross \|C_t\|=51.995 ns. |
| absolute-amplitude-only RF             | 0.784896 | 0.267718          | Log amplitudes only; excluded from main RF.                                 |
| shape RF with shuffled training labels | 0.53203  | 0.0451046         | Null/leakage sanity check under the same run-held-out folds.                |
| leaky D_t score                        | 1        | 1                 | Forbidden label-defining ceiling; reported only to quantify self-reference. |
| forbidden feature audit                |          |                   | Forbidden columns in main RF: [].                                           |

The RF score is still very high after the all-three topology restriction (`ROC AUC=0.993`), but curvature-only is perfect (`ROC AUC=1.000`). This is not evidence of software leakage: in the raw-derived all-three extreme set, max clean `|C_t|` is 5.436 ns and min gross `|C_t|` is 51.995 ns. The shuffled-label control is near chance, so there is no obvious row/run leakage through the feature matrix. The leaky `D_t` control is perfect by construction and confirms that the target remains self-referential to downstream timing. The amplitude-only probe is non-trivial, so the RF should be treated as a morphology/amplitude-correlated timing-tail diagnostic, not an independent timing truth.

## Verdict
After removing missing-stave topology, most of the S07b-style RF ranking remains: shape-only RF AUC is 0.993 [0.980, 1.000], versus curvature-only AUC 1.000 [1.000, 1.000]. The result argues that missing-stave topology was not the dominant source of the high App.I RF score, but the label is still `D_t`-defined and the positive class is only 22 events in the all-three extreme benchmark.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python reports/1781006037.1500.1d8044e2__s07e_all_three_downstream_curvature_rf/s07e_all_three_downstream_curvature_rf.py --config reports/1781006037.1500.1d8044e2__s07e_all_three_downstream_curvature_rf/s07e_config.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `scoreboard.csv`, `leakage_checks.csv`, `heldout_fixed_efficiency.csv`, `oof_predictions.csv`, `run_counts.csv`, and `input_sha256.csv`.
