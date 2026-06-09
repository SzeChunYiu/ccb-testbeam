# Study report: S07b - timing-control classifier calibration with D_t labels

- **Ticket:** 1781000790.531071.5a66741c
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` waveforms in `data/root/root`
- **Runs:** Sample II analysis runs 58, 59, 60, 61, 62, 63, 65

## Question
Does the App.I waveform classifier still beat a direct `D_t`/curvature baseline once the tiny gross timing-tail class is reproduced from raw ROOT, evaluated with run-held-out folds, calibrated, and bootstrapped?

## Raw reproduction first
The population is events with B2 selected and at least two downstream selected staves (B4/B6/B8), using baseline median samples 0-3, `A>1000` ADC, and CFD20 times from raw `HRDv`. The documented App.I boundary is `D_t>50 ns`; this implementation uses a 1 ns guard (`D_t>51 ns`) to avoid edge-convention dependence. It also records the unguarded count.

| quantity                              | report_value | reproduced | delta | tolerance | pass |
| ------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| control events, B2 and >=2 downstream |              | 10156      |       |           | True |
| clean events, D_t<3 ns                |              | 2155       |       |           | True |
| gross events, documented D_t>50 ns    |              | 74         |       |           | True |
| gross events, guarded D_t>51 ns       | 72           | 72         | 0     | 0         | True |

The guarded gross class reproduces the documented **72 events** exactly. The unguarded `D_t>50 ns` count is 74 under the same selection, so the result is sensitive at the two-event level to the timing-edge convention.

## Methods
The evaluation is leave-one-run-held-out across runs 58, 59, 60, 61, 62, 63, 65; metrics are computed from out-of-fold predictions and CIs are run-block bootstraps.

- **Traditional:** `D_t` plus curvature score, `max(D_t, |C_t|)`, where `C_t=t_B8-2t_B6+t_B4` when all three downstream staves exist. This is intentionally a strong conventional comparator and is label-defining because the labels are `D_t` extremes.
- **ML:** random forest on amplitude-normalized waveform-shape features only: B2 shape plus downstream shape means/stds. It excludes `D_t`, `C_t`, run id, event id, absolute amplitudes, present flags, and zero-filled missing-stave slots. Probabilities are cross-fold isotonic calibrated.

## Head-to-head
| method                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier      | notes                                                                                                                                                                      |
| -------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| traditional D_t/curvature  | 1        | 1              | 1               | 1                 | 1         | 1          | 0          | Label-defining timing-span comparator; leakage ceiling.                                                                                                                    |
| curvature-only cross-check | 0.656323 | 0.613988       | 0.680933        | 0.331503          | 0.244475  | 0.378647   | 0.24774    | Independent only for all-three-downstream events; missing curvature imputed.                                                                                               |
| shape-only RF              | 0.998717 | 0.997793       | 0.999252        | 0.964769          | 0.923685  | 0.980435   | 0.00611833 | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; strict aggregate shape; excludes D_t, C_t, run id, event id, absolute amplitudes, present flags. |

At fixed 95% clean efficiency, the traditional `D_t` comparator rejects every held-out gross event because it is the variable that defines the label. The RF rejects 1.000 of gross events on average over runs with gross held-out events.

## Leakage and self-reference checks
| probe                                  | roc_auc  | average_precision | notes                                                                                               |
| -------------------------------------- | -------- | ----------------- | --------------------------------------------------------------------------------------------------- |
| topology-only RF                       | 0.603393 | 0.106786          | B2/B4/B6/B8 present flags plus downstream count only.                                               |
| absolute-amplitude-only RF             | 0.821249 | 0.281949          | Log amplitudes only; excluded from main RF.                                                         |
| shape RF with shuffled training labels | 0.519264 | 0.0386191         | Leakage/null sanity check.                                                                          |
| per-stave slot shape RF                | 0.998904 | 0.968248          | Old representation with present flags and zero-filled missing stave slots; not used for main claim. |
| documented App.I headline              | 0.958    | 0.614             | Prior note value, not reproduced by the stricter run-held-out protocol.                             |

The RF is checked against topology-only, amplitude-only, shuffled-label, and per-stave slot probes. The main leakage risk is not accidental feature leakage but label self-reference: any direct `D_t` score is tautologically perfect on `D_t` labels. A high shape score should therefore be read as waveform morphology tracking the timing-tail definition, not as independent truth.

## Verdict
No. With the `D_t` labels reproduced from raw ROOT, a direct timing-span baseline is unbeatable by construction (`ROC AUC=1.000`, `AP=1.000`). The shape-only RF is useful as a non-timing ranking proxy (`ROC AUC=0.999`, AP=0.965), but it does **not** beat the strong traditional `D_t`/curvature baseline. The safer interpretation is that App.I can be used as a diagnostic tail-finder only when downstream timing variables are unavailable or deliberately withheld.

## Reproducibility
Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with scipy --with pyyaml python reports/1781000790.531071.5a66741c__s07b_timing_control_classifier/s07b_timing_control_classifier.py --config reports/1781000790.531071.5a66741c__s07b_timing_control_classifier/s07b_config.json
```

Key artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `scoreboard.csv`, `heldout_fixed_efficiency.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

## Follow-up tickets
- S07d: redo App.I with an independent non-`D_t` target, e.g. injected two-pulse timing corruption, so the conventional timing baseline is not label-defining.
- S07e: repeat timing-control RF with all-three-downstream events only and a pre-registered curvature-only baseline to separate shape information from missing-stave topology.
