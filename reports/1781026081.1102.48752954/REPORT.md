# Study report: S11d - amplitude-binned constrained templates for S07d

- **Ticket:** 1781026081.1102.48752954
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input:** raw B-stack `HRDv` waveforms in `data/root/root`
- **Runs:** Sample II analysis runs 58, 59, 60, 61, 62, 63, 65

## Question
Does a stronger traditional comparator, using amplitude-binned constrained two-pulse templates with pre-registered secondary-fraction thresholds, explain the remaining RF advantage on the S07d injected timing-corruption target?

## Raw reproduction first
Before injection, the script re-scans raw ROOT with the S07b App.I selection: B2 selected, at least two selected downstream staves, median baseline samples 0-3, `A>1000` ADC, CFD20 times, and Sample II analysis runs.

| quantity                              | report_value | reproduced | delta | tolerance | pass |
| ------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| control events, B2 and >=2 downstream |              | 10156      |       |           | True |
| clean events, D_t<3 ns                |              | 2155       |       |           | True |
| gross events, documented D_t>50 ns    |              | 74         |       |           | True |
| gross events, guarded D_t>51 ns       | 72           | 72         | 0     | 0         | True |

The guarded App.I gross-tail count reproduces the prior **72 events** exactly. This is used only as a raw-ROOT gate; the benchmark label below is injected truth, not a `D_t` threshold.

## Injected target
The injected dataset starts from the raw clean App.I sideband (`D_t<3 ns`). Each clean event is paired with one synthetic copy where a selected downstream waveform receives a delayed, scaled copy of itself. Delays are 2-6 samples and scales are 0.12-0.38. All features and timings are recomputed after injection.

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 37        | 37       | 74    |
| 59  | 415       | 415      | 830   |
| 60  | 428       | 428      | 856   |
| 61  | 607       | 607      | 1214  |
| 62  | 420       | 420      | 840   |
| 63  | 194       | 194      | 388   |
| 65  | 54        | 54       | 108   |

## Methods
Evaluation is leave-one-run-held-out across runs 58, 59, 60, 61, 62, 63, 65. Metrics are computed from out-of-fold predictions; intervals are run-block bootstrap 95% CIs.

- **Traditional:** in each training fold, build raw-clean amplitude-quantile template libraries per stave, fit delayed secondary fractions with coefficient constrained to [0, 0.45], and choose a decision threshold from the fixed grid [0.08, 0.12, 0.16, 0.2, 0.24, 0.28] using training runs only.
- **ML:** random forest on amplitude-normalized waveform shape only: B2 shape plus downstream aggregate shape means/stds. It excludes `D_t`, `C_t`, run, event id, pair id, injected delay/scale/target, absolute amplitudes, present flags, and the analytic matched-template score. Probabilities are cross-fold isotonic calibrated.

Traditional threshold choices:

| heldout_run | threshold | train_balanced_accuracy | train_auc | n_train | n_test | n_template_bins | n_fallback_bins | median_train_secondary_fraction |
| ----------- | --------- | ----------------------- | --------- | ------- | ------ | --------------- | --------------- | ------------------------------- |
| 58          | 0.16      | 0.584986                | 0.587133  | 4236    | 74     | 12              | 0               | 0.135332                        |
| 59          | 0.16      | 0.57931                 | 0.583057  | 3480    | 830    | 12              | 0               | 0.130934                        |
| 60          | 0.16      | 0.580776                | 0.581635  | 3454    | 856    | 12              | 0               | 0.132769                        |
| 61          | 0.2       | 0.586886                | 0.592343  | 3096    | 1214   | 12              | 0               | 0.146468                        |
| 62          | 0.12      | 0.584726                | 0.587166  | 3470    | 840    | 12              | 0               | 0.136383                        |
| 63          | 0.12      | 0.582356                | 0.586768  | 3922    | 388    | 12              | 0               | 0.134835                        |
| 65          | 0.16      | 0.58377                 | 0.586235  | 4202    | 108    | 12              | 0               | 0.13464                         |

RF scan:

| n_estimators | max_depth | min_samples_leaf | roc_auc  | average_precision | brier    |
| ------------ | --------- | ---------------- | -------- | ----------------- | -------- |
| 500          | 7         | 10               | 0.854413 | 0.868368          | 0.159375 |
| 400          | 5         | 15               | 0.822431 | 0.841944          | 0.173623 |
| 300          | 4         | 20               | 0.80186  | 0.822802          | 0.182457 |
| 200          | 3         | 30               | 0.78073  | 0.801445          | 0.189125 |

## Head-to-head
| method                                | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                   |
| ------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| amplitude-binned constrained template | 0.581647 | 0.57154        | 0.590992        | 0.553964          | 0.545712  | 0.566787   | 0.244431 | 0.242311     | 0.246297      | Fold-local amplitude-binned constrained two-pulse template score; thresholds chosen from a fixed grid on training runs.                                 |
| direct D_t/curvature cross-check      | 0.509564 | 0.500211       | 0.520668        | 0.556127          | 0.549546  | 0.564812   | 0.243235 | 0.242155     | 0.244742      | Not label-defining here; label is injected truth, not D_t.                                                                                              |
| shape-only RF                         | 0.854413 | 0.829646       | 0.880155        | 0.868368          | 0.844317  | 0.894737   | 0.159375 | 0.142435     | 0.176542      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 10}; excludes timing, run, pair id, injection params, amplitudes, topology flags. |

The direct timing cross-check is no longer tautological: `D_t` is measured after corruption, while the label is the known injected copy. In this injection setting it is near chance, which confirms that the target is not a disguised `D_t` threshold. RF minus traditional AUC is 0.273; RF minus direct `D_t`/curvature AUC is 0.345.

## Leakage hunt
| probe                                  | roc_auc  | average_precision | notes                                                                    |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------------ |
| pre-injection D_t                      | 0.5      | 0.5               | Same value for raw/injected pair; should be near chance.                 |
| topology-only RF                       | 0.501324 | 0.501163          | Selected-stave flags and downstream multiplicity only.                   |
| absolute-amplitude-only RF             | 0.595767 | 0.613553          | Excluded from main RF; injection can raise peak amplitude.               |
| shape RF with shuffled training labels | 0.499019 | 0.507182          | Null/leakage sanity check.                                               |
| per-stave slot shape RF                | 0.869289 | 0.882503          | More permissive representation including present flags; not main claim.  |
| pair split violations                  | 0        |                   | Count of pair ids appearing in both train and held-out folds; must be 0. |
| forbidden main RF columns              | 0        |                   | None.                                                                    |

The pair split check confirms that paired raw/injected variants are always held out together by run. The pre-injection `D_t` score is near chance, so the injected label is not just selecting the original App.I timing tail. The shuffled-label and topology-only probes stay near chance. The amplitude-only probe is reported because injection changes peak height; it is excluded from the main RF.

## Verdict
The raw reproduction gate passes before the injected benchmark. The amplitude-binned constrained template score reaches ROC AUC 0.582 [0.572, 0.591], while the shape-only RF reaches ROC AUC 0.854 [0.830, 0.880]. The stronger template fit reduces the comparator gap only if its AUC approaches the RF; otherwise the remaining RF advantage is not just the unbinned-template mismatch tested here.

## Reproducibility
Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s11d_1781026081_1102_48752954_amplitude_binned_s07d_templates.py --config configs/s11d_1781026081_1102_48752954_amplitude_binned_s07d_templates.json
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `scoreboard.csv`, `traditional_threshold_choices.csv`, `template_support_by_fold.csv`, `template_fit_scores.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.
