# S11b: constrained two-pulse template fit for S07d

- **Ticket:** 1781012659.1188.131c30d5
- **Worker:** testbeam-laptop-4
- **Input:** raw B-stack `HRDv` waveforms in `data/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65

## Question
Can a full constrained two-pulse template fit replace the S07d fold-local matched-template residual and close the gap to the shape-only RF on the same injected two-pulse target?

## Raw Reproduction First
The script re-scans raw ROOT before any injection using the S07d App.I gate: B2 selected, at least two downstream staves selected, median baseline samples 0-3, `A>1000` ADC, CFD20 timing, and Sample II analysis runs.

| quantity                              | report_value | reproduced | delta | tolerance | pass |
| ------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| control events, B2 and >=2 downstream |              | 10156      |       |           | True |
| clean events, D_t<3 ns                |              | 2155       |       |           | True |
| gross events, documented D_t>50 ns    |              | 74         |       |           | True |
| gross events, guarded D_t>51 ns       | 72           | 72         | 0     | 0         | True |

The guarded `D_t>51 ns` count reproduces the prior **72 events** exactly.

## Target And Split
The benchmark uses the S07d injected-truth dataset: each raw clean `D_t<3 ns` event is paired with one delayed/scaled downstream self-overlay. Evaluation is leave-one-run-held-out; intervals are run-block bootstrap 95% CIs.

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
- **Traditional:** for each held-out run, templates are built from training-run raw-clean events only. A one-pulse fit and constrained two-pulse fit are solved on each selected downstream stave; the best constrained hypothesis reports `chi2/ndf`, fitted secondary amplitude, secondary fraction, and delay. The scoring candidate is selected inside the training fold from conventional timing/shape summaries plus those fit outputs, replacing S07d's matched-template residual.
- **ML:** random forest on the same S07d strict shape columns (`b2_shape_*`, `ds_shape_*`), excluding timing, run, event id, pair id, injection parameters, absolute amplitudes, stave-present flags, and two-pulse fit outputs. Probabilities are cross-fold isotonic calibrated.

Constrained-fit fold choices:

| heldout_run | candidate                  | sign | train_auc | train_median | train_iqr | n_train | n_test |
| ----------- | -------------------------- | ---- | --------- | ------------ | --------- | ------- | ------ |
| 58          | max_downstream_peak_sample | 1    | 0.620799  | 6            | 4         | 4236    | 74     |
| 59          | max_downstream_peak_sample | 1    | 0.618779  | 7            | 4         | 3480    | 830    |
| 60          | max_downstream_peak_sample | 1    | 0.61785   | 7            | 4         | 3454    | 856    |
| 61          | max_downstream_peak_sample | 1    | 0.627707  | 6            | 3         | 3096    | 1214   |
| 62          | max_downstream_peak_sample | 1    | 0.619187  | 7            | 4         | 3470    | 840    |
| 63          | max_downstream_peak_sample | 1    | 0.618564  | 7            | 4         | 3922    | 388    |
| 65          | max_downstream_peak_sample | 1    | 0.621816  | 6            | 4         | 4202    | 108    |

Fit-output summary:

| class     | n    | valid_fraction | median_secondary_fraction | median_secondary_amp_norm | median_delay_samples | median_chi2_ndf | median_frac_sse_improvement |
| --------- | ---- | -------------- | ------------------------- | ------------------------- | -------------------- | --------------- | --------------------------- |
| raw_clean | 2155 | 0.596752       | 0.101026                  | 0.105473                  | 5                    | 0.0400476       | 0.246881                    |
| injected  | 2155 | 0.67703        | 0.182746                  | 0.20994                   | 5                    | 0.0397241       | 0.506534                    |

RF scan:

| n_estimators | max_depth | min_samples_leaf | roc_auc  | average_precision | brier    |
| ------------ | --------- | ---------------- | -------- | ----------------- | -------- |
| 500          | 7         | 10               | 0.856356 | 0.870166          | 0.157867 |
| 400          | 5         | 15               | 0.822342 | 0.842268          | 0.174012 |
| 300          | 4         | 20               | 0.799977 | 0.821242          | 0.182669 |
| 200          | 3         | 30               | 0.778435 | 0.797885          | 0.190003 |

## Head-to-head
| method                             | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                                    |
| ---------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| constrained two-pulse template fit | 0.615554 | 0.606474       | 0.631356        | 0.580895          | 0.572865  | 0.592255   | 0.239654 | 0.235156     | 0.245079      | Fold-local score selected from conventional timing/shape summaries plus chi2/ndf, fitted secondary amplitude/fraction, delay, and SSE improvement.                       |
| direct D_t/curvature cross-check   | 0.509564 | 0.500609       | 0.520059        | 0.556127          | 0.549693  | 0.563716   | 0.243235 | 0.242174     | 0.244611      | Not label-defining here; label is injected truth, not D_t.                                                                                                               |
| shape-only RF                      | 0.856356 | 0.833619       | 0.882368        | 0.870166          | 0.847104  | 0.895898   | 0.157867 | 0.142077     | 0.173698      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 10}; excludes timing, run, pair id, injection params, amplitudes, topology flags, and fit outputs. |

## Leakage Hunt
| probe                                  | roc_auc  | average_precision | notes                                                                    |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------------ |
| pre-injection D_t                      | 0.5      | 0.5               | Same value for raw/injected pair; should be near chance.                 |
| topology-only RF                       | 0.50105  | 0.500887          | Selected-stave flags and downstream multiplicity only.                   |
| absolute-amplitude-only RF             | 0.595156 | 0.613307          | Excluded from main RF; injection can raise peak amplitude.               |
| shape RF with shuffled training labels | 0.523814 | 0.525181          | Null/leakage sanity check.                                               |
| pair split violations                  | 0        |                   | Count of pair ids appearing in both train and held-out folds; must be 0. |
| forbidden main RF columns              | 0        |                   | None.                                                                    |

Pair ids are split by run, so raw/injected pairs cannot cross train/test. The ML result is strong but matches the prior S07d pattern: pre-injection `D_t`, topology-only RF, and shuffled-label RF remain near chance; absolute-amplitude-only RF is reported as a known injection side effect and is excluded from the main RF.

## Verdict
The full constrained two-pulse fit is a stronger and more interpretable traditional replacement than the old matched residual because it exposes `chi2/ndf`, secondary amplitude, and delay per event. On this S07d target it reaches ROC AUC 0.616 [0.606, 0.631], while the shape-only RF reaches 0.856 [0.834, 0.882]. The fit does not close the black-box feature gap; the RF advantage is 0.241 AUC.

## Reproducibility
Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s11b_1781012659_s07d_two_pulse_fit.py --config configs/s11b_1781012659_s07d_two_pulse_fit.json
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `two_pulse_fit_oof.csv`, `scoreboard.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

## Follow-up Tickets
- S11d: fit the S07d injected target with asymmetric amplitude-binned templates and pre-register secondary-fraction thresholds; expected information gain: tests whether template mismatch, not ML capacity, explains the remaining RF advantage.
- P05b: calibrate CNN or MLP two-pulse abstention on S07d-style run-held-out injections using chi2/ndf and secondary-amplitude sidebands; expected information gain: turns high-AUC detection into an operational recovery rule.
