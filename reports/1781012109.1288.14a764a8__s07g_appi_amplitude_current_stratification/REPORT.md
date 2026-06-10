# S07g: all-three App.I amplitude/current stratification

- **Ticket:** 1781012109.1288.14a764a8
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT in `data/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65

## Question
Does the high S07e all-three App.I RF score persist uniformly after stratifying by event amplitude and by pre-label current/run-rate family, or is it explained by amplitude correlation or rate-dependent pulse quality?

## Raw Reproduction First
The parent App.I control population is recomputed first from raw ROOT with baseline median samples 0-3, `A>1000` ADC, CFD20 times, B2 selected, and at least two downstream staves selected.

| quantity                                     | report_value | reproduced | delta | tolerance | pass |
| -------------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| parent control events, B2 and >=2 downstream |              | 10156      |       |           | True |
| parent clean events, D_t<3 ns                |              | 2155       |       |           | True |
| parent gross events, documented D_t>50 ns    |              | 74         |       |           | True |
| parent gross events, guarded D_t>51 ns       | 72           | 72         | 0     | 0         | True |
| S07g all-three control events                |              | 3774       |       |           | True |
| S07g all-three guarded gross events          |              | 22         |       |           | True |

The guarded `D_t>51 ns` count reproduces the documented App.I **72 gross events** exactly before the all-three restriction and stratum audit. The all-three subset keeps 3774 control events and 22 guarded gross events.

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
Labels remain the App.I timing extremes: clean if `D_t<3 ns`, gross if `D_t>51 ns`; intermediate events are excluded from the classifier benchmark. All benchmark rows have B4, B6, and B8 selected, so missing-stave topology is constant.

- **Traditional:** pre-registered curvature-only score `|C_t|`; no `D_t`, no amplitude, no topology.
- **Amplitude control:** run-held-out RF using only absolute log amplitudes (`B2/B4/B6/B8` plus event maximum).
- **ML:** random forest over amplitude-normalized waveform shapes for B2/B4/B6/B8 and downstream aggregate shape summaries. It excludes run id, event id, `D_t`, `C_t`, absolute amplitudes, present flags, and missing-stave slots.
- **Strata:** event-maximum-amplitude tertiles from the full all-three control population before clean/gross filtering, and run families fixed in the config from pre-label all-three rates: `low_all_three_rate_edge, mid_all_three_rate, high_all_three_rate`.
- **Uncertainty:** leave-one-run-out predictions with run-block bootstrap 95% CIs. Sparse strata with one class or too few resampled mixed-class blocks report `NaN` intervals rather than hiding the limitation.

## Overall Head-to-Head
| method                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier      | notes                                                                                                          |
| -------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ---------- | -------------------------------------------------------------------------------------------------------------- |
| curvature-only traditional | 1        | 1              | 1               | 1                 | 1         | 1          | 0.00399976 | Pre-registered \|C_t\| only; all benchmark rows have B4/B6/B8 selected.                                        |
| shape-only RF              | 0.992778 | 0.980488       | 1               | 0.92781           | 0.766222  | 1          | 0.0074835  | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; normalized shape only; 143 features. |
| amplitude-only RF control  | 0.779282 | 0.71446        | 0.882241        | 0.249153          | 0.106297  | 0.345305   | 0.0326235  | Absolute log-amplitude controls only; 5 features.                                                              |

At fixed 95% clean efficiency, mean gross rejection over held-out runs with gross examples is:

| method                     | gross_rejection |
| -------------------------- | --------------- |
| curvature-only traditional | 1               |
| shape-only RF              | 0.96            |

## Amplitude Strata
| stratum_type      | stratum            | method                       | n_events | n_clean | n_gross | n_runs | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision |
| ----------------- | ------------------ | ---------------------------- | -------- | ------- | ------- | ------ | -------- | -------------- | --------------- | ----------------- |
| amplitude_stratum | high_event_max_amp | curvature-only traditional   | 169      | 159     | 10      | 7      | 1        | 1              | 1               | 1                 |
| amplitude_stratum | high_event_max_amp | amplitude-only RF control    | 169      | 159     | 10      | 7      | 0.738994 | 0.643519       | 0.90705         | 0.225735          |
| amplitude_stratum | high_event_max_amp | shape-only RF                | 169      | 159     | 10      | 7      | 1        | 1              | 1               | 1                 |
| amplitude_stratum | high_event_max_amp | shape RF shuffled-label null | 169      | 159     | 10      | 7      | 0.416352 | 0.150862       | 0.725352        | 0.0594119         |
| amplitude_stratum | low_event_max_amp  | curvature-only traditional   | 273      | 269     | 4       | 7      | 1        | 1              | 1               | 1                 |
| amplitude_stratum | low_event_max_amp  | amplitude-only RF control    | 273      | 269     | 4       | 7      | 0.639405 | 0.424709       | 0.81663         | 0.027291          |
| amplitude_stratum | low_event_max_amp  | shape-only RF                | 273      | 269     | 4       | 7      | 0.991636 | 0.968262       | 1               | 0.826923          |
| amplitude_stratum | low_event_max_amp  | shape RF shuffled-label null | 273      | 269     | 4       | 7      | 0.761152 | 0.639352       | 0.91583         | 0.0694198         |
| amplitude_stratum | mid_event_max_amp  | curvature-only traditional   | 159      | 151     | 8       | 7      | 1        | 1              | 1               | 1                 |
| amplitude_stratum | mid_event_max_amp  | amplitude-only RF control    | 159      | 151     | 8       | 7      | 0.814156 | 0.722222       | 0.960526        | 0.480394          |
| amplitude_stratum | mid_event_max_amp  | shape-only RF                | 159      | 151     | 8       | 7      | 0.98096  | 0.940038       | 1               | 0.881705          |
| amplitude_stratum | mid_event_max_amp  | shape RF shuffled-label null | 159      | 151     | 8       | 7      | 0.518212 | 0.251456       | 0.691044        | 0.0638285         |

## Current/Run-Family Strata
| stratum_type       | stratum                 | method                       | n_events | n_clean | n_gross | n_runs | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision |
| ------------------ | ----------------------- | ---------------------------- | -------- | ------- | ------- | ------ | -------- | -------------- | --------------- | ----------------- |
| current_run_family | high_all_three_rate     | curvature-only traditional   | 431      | 416     | 15      | 3      | 1        | 1              | 1               | 1                 |
| current_run_family | high_all_three_rate     | amplitude-only RF control    | 431      | 416     | 15      | 3      | 0.771715 | 0.689824       | 0.894057        | 0.297125          |
| current_run_family | high_all_three_rate     | shape-only RF                | 431      | 416     | 15      | 3      | 0.999359 | 0.998475       | 1               | 0.985965          |
| current_run_family | high_all_three_rate     | shape RF shuffled-label null | 431      | 416     | 15      | 3      | 0.565224 | 0.317829       | 0.990991        | 0.0514968         |
| current_run_family | low_all_three_rate_edge | curvature-only traditional   | 13       | 13      | 0       | 2      |          |                |                 |                   |
| current_run_family | low_all_three_rate_edge | amplitude-only RF control    | 13       | 13      | 0       | 2      |          |                |                 |                   |
| current_run_family | low_all_three_rate_edge | shape-only RF                | 13       | 13      | 0       | 2      |          |                |                 |                   |
| current_run_family | low_all_three_rate_edge | shape RF shuffled-label null | 13       | 13      | 0       | 2      |          |                |                 |                   |
| current_run_family | mid_all_three_rate      | curvature-only traditional   | 157      | 150     | 7       | 2      | 1        | 1              | 1               | 1                 |
| current_run_family | mid_all_three_rate      | amplitude-only RF control    | 157      | 150     | 7       | 2      | 0.798095 | 0.798095       | 0.947368        | 0.194116          |
| current_run_family | mid_all_three_rate      | shape-only RF                | 157      | 150     | 7       | 2      | 0.982857 | 0.978495       | 1               | 0.835775          |
| current_run_family | mid_all_three_rate      | shape RF shuffled-label null | 157      | 150     | 7       | 2      | 0.495238 | 0.184211       | 0.587097        | 0.0574865         |

## Leakage Hunt
| probe                                  | roc_auc  | average_precision | notes                                                                       |
| -------------------------------------- | -------- | ----------------- | --------------------------------------------------------------------------- |
| missing-stave topology                 |          |                   | Removed by construction: n_downstream unique=[3].                           |
| curvature separation audit             | 1        | 1                 | Perfect because max clean \|C_t\|=5.436 ns and min gross \|C_t\|=51.995 ns. |
| absolute-amplitude-only RF             | 0.779282 | 0.249153          | Log amplitudes only; excluded from main RF.                                 |
| shape RF with shuffled training labels | 0.53203  | 0.0451046         | Null/leakage sanity check under the same run-held-out folds.                |
| leaky D_t score                        | 1        | 1                 | Forbidden label-defining ceiling; reported only to quantify self-reference. |
| forbidden feature audit                |          |                   | Forbidden columns in main RF: [].                                           |

The overall shape RF remains high (`ROC AUC=0.993`), but curvature-only is still perfect (`ROC AUC=1.000`) and the amplitude-only control is non-trivial (`ROC AUC=0.779`). The too-good result is explained by the target geometry rather than software leakage: max clean `|C_t|` is 5.436 ns and min gross `|C_t|` is 51.995 ns. The shuffled-label control is near chance overall; sparse stratum nulls are reported explicitly rather than interpreted.

## Verdict
S07g does not turn the App.I RF into an independent timing truth. The shape score remains high in the populated amplitude and run-family strata, but the conventional curvature score separates the same weak labels perfectly wherever both classes are present. The amplitude-only control confirms that part of the RF ranking is amplitude-correlated, while the run-family table shows the sparse edge families are not strong enough to support a standalone current claim.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python reports/1781012109.1288.14a764a8__s07g_appi_amplitude_current_stratification/s07g_appi_amplitude_current_stratification.py --config reports/1781012109.1288.14a764a8__s07g_appi_amplitude_current_stratification/s07g_config.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `scoreboard.csv`, `stratified_scoreboard.csv`, `run_family_metadata.csv`, `leakage_checks.csv`, `heldout_fixed_efficiency.csv`, `oof_predictions.csv`, `run_counts.csv`, and `input_sha256.csv`.
