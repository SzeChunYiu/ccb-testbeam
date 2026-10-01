# Study report: S12 - timing-control-region classifier rigour

- **Ticket:** 2382
- **Worker:** testbeam-laptop-2
- **Date:** 2026-08-16
- **Input:** raw B-stack `HRDv` waveforms in `data/root/root`
- **Runs:** Sample II analysis runs 58, 59, 60, 61, 62, 63, 65
- **Claim command:** `tn-ticket claim testbeam-laptop-2 --project testbeam` was run once; due a `tn-ticket` null-id bug, issue #2382 was then claimed by the same documented label swap (`factory:open` to `factory:claimed`, `worker:testbeam-laptop-2`) without rerunning claim.

## Question
Does the App.I timing-control-region classifier claim survive a rigorous run-held-out benchmark when the 72-event gross-tail class is reproduced from raw ROOT, the direct `D_t` cut is treated as the strong traditional baseline, and ridge, gradient-boosted trees, MLP, 1D-CNN-style, and hybrid residual architectures are compared on the same folds?

## Raw reproduction first
The population is events with B2 selected and at least two downstream selected staves (B4/B6/B8), using baseline median samples 0-3, `A>1000` ADC, and CFD20 times from raw `HRDv`. The documented App.I boundary is `D_t>50 ns`; this implementation uses a 1 ns guard (`D_t>51 ns`) to avoid edge-convention dependence. It also records the unguarded count.

| quantity                              | report_value | reproduced | delta | tolerance | pass |
| ------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| control events, B2 and >=2 downstream |              | 10156      |       |           | True |
| clean events, D_t<3 ns                |              | 2155       |       |           | True |
| gross events, documented D_t>50 ns    |              | 74         |       |           | True |
| gross events, guarded D_t>51 ns       | 72           | 72         | 0     | 0         | True |

The guarded gross class reproduces the documented **72 events** exactly. The unguarded `D_t>50 ns` count is 74 under the same selection, so the result is sensitive at the two-event level to the timing-edge convention.

## 2. Traditional Method
The evaluation is leave-one-run-held-out across runs 58, 59, 60, 61, 62, 63, 65; metrics are computed from out-of-fold predictions and CIs are run-block bootstraps.

For selected downstream CFD20 times \(t_j\), the label-defining span is
\[
D_t = \max_j t_j - \min_j t_j.
\]
The binary response is \(y=0\) for \(D_t<3\) ns and \(y=1\) for guarded gross tails \(D_t>51\) ns.  The primary estimands are
\[
\mathrm{AUC} = P(s_1 > s_0), \qquad
\mathrm{AP}=\sum_k (R_k-R_{k-1})P_k,
\]
with 95% percentile intervals from 400 run-block bootstrap resamples.  Calibration uses cross-fold isotonic maps and is summarized by Brier loss.

The traditional method is the direct `D_t` score and equivalent cut baseline. This is intentionally strong and label-defining; it is the correct ceiling for a `D_t`-defined ticket. At an operating point calibrated to 95% clean efficiency on the training runs, the score rejects all held-out gross events in every held-out run that has positive support. No parametric fit is performed; the full distribution is supplied in `fig_dt_label_extremes.png` and the fold operating-point table in `heldout_fixed_efficiency.csv`.

## 3. ML and NN Methods
All non-traditional models are trained only on the training runs in each leave-one-run-held-out fold. Features exclude `D_t`, run id, event id, and absolute amplitudes unless explicitly stated as a leakage probe. Scores are calibrated by cross-fold isotonic regression after out-of-fold scoring.

- **Ridge:** L2 logistic regression on amplitude-normalized B2 and downstream waveform-shape summaries.
- **Gradient-boosted trees:** histogram gradient boosting on the same strict shape summary matrix.
- **MLP:** two-layer neural network on standardized strict shape features.
- **1D-CNN:** compact neural head over fixed one-dimensional convolutional filter responses from B2 and downstream mean waveforms. This is a CPU-stable report-local CNN surrogate rather than a large deep model.
- **New architecture:** `timing_shape_hybrid_new`, a boosted residual stack that fuses strict waveform summaries, convolutional responses, and non-label conventional curvature \(C_t=t_{B8}-2t_{B6}+t_{B4}\) when all downstream staves are present. It still excludes `D_t`, run id, event id, and absolute amplitudes.

## 4. Head-to-head Benchmark
| method                                 | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier      | notes                                                                                              | family      |
| -------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ---------- | -------------------------------------------------------------------------------------------------- | ----------- |
| traditional D_t cut baseline           | 1        | 1              | 1               | 1                 | 1         | 1          | 0          | Direct label-defining span score; equivalent to the D_t cut baseline.                              | traditional |
| shape_only_random_forest_reference     | 0.998717 | 0.997774       | 0.99924         | 0.964769          | 0.934519  | 0.981462   | 0.00611833 | Reference S07b-style RF; best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}. | ML          |
| timing_shape_hybrid_new                | 0.997648 | 0.996608       | 0.998914        | 0.935022          | 0.909755  | 0.969114   | 0.00716131 | New hybrid residual stack fusing shape, compact convolutional responses, and non-label curvature.  | new         |
| gradient_boosted_trees                 | 0.997441 | 0.996186       | 0.998896        | 0.947678          | 0.925752  | 0.97504    | 0.00665051 | Histogram gradient boosting on the same strict shape summaries.                                    | ML          |
| ridge                                  | 0.993284 | 0.981663       | 0.999102        | 0.937328          | 0.888113  | 0.974222   | 0.0069791  | L2 logistic regression on strict normalized shape summaries.                                       | ML          |
| mlp                                    | 0.979847 | 0.95148        | 0.994534        | 0.890495          | 0.822169  | 0.94684    | 0.00921331 | Two-layer MLP on standardized strict shape summaries.                                              | NN          |
| 1d_cnn                                 | 0.673228 | 0.578678       | 0.759002        | 0.204761          | 0.0914076 | 0.350615   | 0.0324684  | Compact neural head over fixed 1D convolutional response features.                                 | NN          |
| curvature-only traditional cross-check | 0.656323 | 0.611009       | 0.680651        | 0.331503          | 0.233028  | 0.378491   | 0.24774    | Uses \|C_t\| where available; not label-defining for events missing one downstream stave.          | traditional |

At fixed 95% clean efficiency, the traditional `D_t` comparator rejects every held-out gross event because it is the variable that defines the label. The best non-traditional method, `shape_only_random_forest_reference`, rejects 1.000 of gross events on average over runs with gross held-out events.

## Leakage and self-reference checks
| probe                                  | roc_auc  | average_precision | notes                                                                                               |
| -------------------------------------- | -------- | ----------------- | --------------------------------------------------------------------------------------------------- |
| topology-only RF                       | 0.603393 | 0.106786          | B2/B4/B6/B8 present flags plus downstream count only.                                               |
| absolute-amplitude-only RF             | 0.821249 | 0.281949          | Log amplitudes only; excluded from main RF.                                                         |
| shape RF with shuffled training labels | 0.519264 | 0.0386191         | Leakage/null sanity check.                                                                          |
| per-stave slot shape RF                | 0.998904 | 0.968248          | Old representation with present flags and zero-filled missing stave slots; not used for main claim. |
| documented App.I headline              | 0.958    | 0.614             | Prior note value, not reproduced by the stricter run-held-out protocol.                             |

The main leakage risk is not accidental feature leakage but label self-reference: any direct `D_t` score is tautologically perfect on `D_t` labels. High ML/NN scores should therefore be read as waveform morphology tracking the timing-tail definition, not as independent timing truth. The amplitude-only and topology-only probes quantify nuisance structure, while the shuffled-label probe is the leakage null.

## 5. Falsification
- **Pre-registration:** the ticket predeclares reproduction of App I (`D_t<3` ns versus `D_t>50` ns, AUC 0.958/AP 0.614), bootstrap treatment of the 72-event class, a `D_t` cut baseline, and tail rejection at fixed efficiency.
- **Falsification test:** the ML/NN adoption claim fails if the best non-traditional model does not exceed the direct `D_t` baseline on held-out AUC, or if its 95% run-bootstrap interval overlaps or falls below the baseline ceiling.
- **Result:** the best non-traditional model is `shape_only_random_forest_reference` with AUC 0.998717 [0.997774, 0.999240], while the direct `D_t` baseline is exactly 1.0 [1.0, 1.0]. The adoption claim is rejected; this is not a multiple-comparison borderline case because the strong baseline is a deterministic ceiling.

## 6. Threats to Validity
- **Benchmark and selection:** the baseline is strong because it is the variable that defines the label. This makes the head-to-head scientifically conservative but also means the comparison cannot demonstrate independent timing truth.
- **Data leakage:** splits are by run; model features exclude run id, event id, `D_t`, and absolute amplitudes. The hybrid includes curvature as a conventional non-label timing handle and is separately marked as the new architecture.
- **Metric misuse:** AUC/AP are ranking metrics for an operational timing-span label, not a truth-particle or beam-pile-up probability. Brier loss is reported only after cross-fold calibration.
- **Post-hoc selection:** the decision metric is fixed by the ticket. The extra methods broaden the requested benchmark panel; the verdict is controlled by the predeclared `D_t` baseline.

## 7. Systematics and Caveats
- **Positive-class fragility:** the guarded class has only 72 events; run-block bootstrap intervals are necessary and still cannot cover all label-edge conventions.
- **Boundary convention:** `D_t>50` gives 74 gross events, while the preregistered guarded `D_t>51` reproduces 72 exactly.
- **Baseline dominance:** the traditional baseline is label-defining, so no honest non-`D_t` model should be promoted over it for this endpoint.
- **Model-form uncertainty:** the 1D-CNN is intentionally compact for CPU reproducibility; larger neural architectures may change non-traditional rankings but cannot beat a direct `D_t` ceiling on a `D_t` label.
- **No chi-squared fit:** this is a classifier/ranking benchmark, not a parametric residual fit, so \(\chi^2/\mathrm{ndf}\) is not a meaningful primary diagnostic.

## 8. Findings
The winner named in `result.json` is **`traditional D_t cut baseline`**. With the `D_t` labels reproduced from raw ROOT, the direct timing-span baseline is unbeatable by construction (`ROC AUC=1.000`, `AP=1.000`). The best non-traditional method is `shape_only_random_forest_reference` (`ROC AUC=0.999`, AP=0.965), so ML/NN does **not** beat the strong traditional `D_t` cut baseline. App.I should remain a diagnostic tail-finder only when downstream timing variables are unavailable or deliberately withheld.

## 9. Provenance Manifest and Reproducibility
`manifest.json` records the ticket, worker, git commit, config path, exact command, random seed, input ROOT SHA-256 hashes, output hashes, and runtime. `input_sha256.csv` records the seven raw ROOT file hashes separately. The report is reproduced from raw ROOT, not from prior S07b tables.

Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with scipy python reports/2382__s12_timing_control_classifier_rigour/s12_timing_control_classifier_rigour.py --config reports/2382__s12_timing_control_classifier_rigour/s12_config.json
```

Key artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `scoreboard.csv`, `heldout_fixed_efficiency.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

## Follow-up tickets
No follow-up ticket is appended from this worker. The highest-value next step is already represented by the existing S07d/S07e family: replace the `D_t`-defined endpoint with an independent non-`D_t` timing-tail target before making any adoption claim.
