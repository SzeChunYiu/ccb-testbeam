# Study report: S07d - injected two-pulse timing-corruption target

- **Ticket:** 1781006037.1502.693f2c73
- **Worker:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` waveforms in `data/root/root`
- **Runs:** Sample II analysis runs 58, 59, 60, 61, 62, 63, 65

## Question
Can the App.I waveform-shape classifier be benchmarked against an independent injected two-pulse timing-corruption target, so the direct `D_t` baseline is no longer label-defining?

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

- **Traditional:** inside each training fold, choose the best signed one-dimensional conventional score from post-injection `D_t`, `|C_t|`, downstream shape summaries, and a fold-local two-pulse matched-template residual. The chosen score is standardized on the training runs and applied to the held-out run.
- **ML:** random forest on amplitude-normalized waveform shape only: B2 shape plus downstream aggregate shape means/stds. It excludes `D_t`, `C_t`, run, event id, pair id, injected delay/scale/target, absolute amplitudes, present flags, and the analytic matched-template score. Probabilities are cross-fold isotonic calibrated.

Traditional fold choices:

| heldout_run | candidate                  | sign | train_auc | train_median | train_iqr | n_train | n_test |
| ----------- | -------------------------- | ---- | --------- | ------------ | --------- | ------- | ------ |
| 58          | max_downstream_peak_sample | 1    | 0.620799  | 6            | 4         | 4236    | 74     |
| 59          | max_downstream_peak_sample | 1    | 0.618779  | 7            | 4         | 3480    | 830    |
| 60          | max_downstream_peak_sample | 1    | 0.61785   | 7            | 4         | 3454    | 856    |
| 61          | max_downstream_peak_sample | 1    | 0.627707  | 6            | 3         | 3096    | 1214   |
| 62          | max_downstream_peak_sample | 1    | 0.619187  | 7            | 4         | 3470    | 840    |
| 63          | max_downstream_peak_sample | 1    | 0.618564  | 7            | 4         | 3922    | 388    |
| 65          | max_downstream_peak_sample | 1    | 0.621816  | 6            | 4         | 4202    | 108    |

RF scan:

| n_estimators | max_depth | min_samples_leaf | roc_auc  | average_precision | brier    |
| ------------ | --------- | ---------------- | -------- | ----------------- | -------- |
| 500          | 7         | 10               | 0.854413 | 0.868368          | 0.159375 |
| 400          | 5         | 15               | 0.822431 | 0.841944          | 0.173623 |
| 300          | 4         | 20               | 0.80186  | 0.822802          | 0.182457 |
| 200          | 3         | 30               | 0.78073  | 0.801445          | 0.189125 |

## Head-to-head
| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                   |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| traditional fold-selected timing/template | 0.615554 | 0.605378       | 0.630506        | 0.580895          | 0.573647  | 0.591947   | 0.239654 | 0.235215     | 0.244489      | Fold-local best signed score from D_t, |C_t|, downstream shape summaries, and matched-template residual.                                                |
| direct D_t/curvature cross-check          | 0.509564 | 0.500211       | 0.520668        | 0.556127          | 0.549546  | 0.564812   | 0.243235 | 0.242155     | 0.244742      | Not label-defining here; label is injected truth, not D_t.                                                                                              |
| shape-only RF                             | 0.854413 | 0.829646       | 0.880155        | 0.868368          | 0.844317  | 0.894737   | 0.159375 | 0.142435     | 0.176542      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 10}; excludes timing, run, pair id, injection params, amplitudes, topology flags. |

The direct timing cross-check is no longer tautological: `D_t` is measured after corruption, while the label is the known injected copy. In this injection setting it is near chance, which confirms that the target is not a disguised `D_t` threshold. RF minus traditional AUC is 0.239; RF minus direct `D_t`/curvature AUC is 0.345.

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
The independent injected target removes the S07b self-reference problem. On this target, the fold-selected traditional timing/template score reaches ROC AUC 0.616 [0.605, 0.631], while the shape-only RF reaches ROC AUC 0.854 [0.830, 0.880]. The RF is therefore a sensitive waveform-shape detector for this injected two-pulse corruption, but the result should be interpreted as injection-recovery evidence, not as a measured beam pile-up rate.

## Reproducibility
Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python reports/1781006037.1502.693f2c73__s07d_injected_timing_corruption/s07d_injected_timing_corruption.py --config reports/1781006037.1502.693f2c73__s07d_injected_timing_corruption/s07d_config.json
```

Key artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `scoreboard.csv`, `traditional_fold_choices.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

## Follow-up tickets
- S07e: run the same injected two-pulse target with all-three-downstream events only and a pre-registered curvature-only comparator; expected information gain: separates waveform shape from missing-stave topology.
- S11b: replace the matched-template residual with a full constrained two-pulse fit and report chi2/ndf; expected information gain: tests whether a traditional fit can match the RF without black-box features.
