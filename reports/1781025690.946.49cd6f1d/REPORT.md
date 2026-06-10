# S11d: constrained two-pulse fit comparator on all-three injected benchmark

- **Ticket:** `1781025690.946.49cd6f1d`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Target:** S07f all-three injected truth, Sample-II analysis runs, B2+B4+B6+B8 selected, `A>1000` ADC.
- **Split:** leave-one-run-out; intervals are run-block bootstrap 95% CIs.

## Raw-ROOT Reproduction First

| quantity                                | report_value | reproduced | delta        | tolerance | pass |
| --------------------------------------- | ------------ | ---------- | ------------ | --------- | ---- |
| parent App.I guarded gross D_t>51 ns    | 72           | 72         | 0            | 0         | True |
| parent App.I documented gross D_t>50 ns |              | 74         |              |           | True |
| all-three control events                | 3774         | 3774       | 0            | 0         | True |
| all-three clean events D_t<3 ns         |              | 579        |              |           | True |
| all-three guarded gross D_t>51 ns       | 22           | 22         | 0            | 0         | True |
| all-three S07e shape RF ROC AUC         | 0.992778     | 0.994426   | 0.00164861   | 0.002     | True |
| S07f traditional injected ROC AUC       | 0.605954     | 0.605954   | -3.7261e-07  | 0.002     | True |
| S07f shape-only RF injected ROC AUC     | 0.822118     | 0.822118   | -4.78575e-07 | 0.002     | True |

The S07f target was regenerated before the new fit. It reproduces the prior traditional AUC **0.605954** and shape-only RF AUC **0.822118**, within the configured tolerance.

| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                       |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| traditional fold-selected timing/template | 0.605954 | 0.598605       | 0.618069        | 0.570681          | 0.561867  | 0.583083   | 0.239508 | 0.237077     | 0.241699      | Fold-local best signed timing, curvature, shape-summary, or matched-template score.                                                                         |
| direct D_t/curvature cross-check          | 0.530522 | 0.51749        | 0.537119        | 0.581449          | 0.566058  | 0.597987   | 0.24422  | 0.240807     | 0.247804      | Not label-defining here; target is injected two-pulse truth.                                                                                                |
| all-three shape-only RF                   | 0.822118 | 0.80083        | 0.844361        | 0.83589           | 0.81471   | 0.860373   | 0.177242 | 0.164769     | 0.190468      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, run/event ids, injection params, amplitudes, and topology flags. |

## Target Counts

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 9         | 9        | 18    |
| 59  | 93        | 93       | 186   |
| 60  | 129       | 129      | 258   |
| 61  | 176       | 176      | 352   |
| 62  | 111       | 111      | 222   |
| 63  | 57        | 57       | 114   |
| 65  | 4         | 4        | 8     |

## Methods

Traditional method: train-run-only median templates for B4/B6/B8 feed a bounded one-pulse versus two-pulse least-squares fit on each downstream stave. This replaces the S07d fold-selected traditional proxy for the head-to-head claim. The held-out score is selected inside each training fold from fit outputs only: `secondary_fraction`, `secondary_amp_norm`, delay, `chi2/ndf`, two-pulse SSE, and fractional SSE improvement.

ML method: the S07f shape-only RF on B2 and downstream aggregate normalized waveform features, with timing, run/event ids, pair ids, injection parameters, amplitudes, topology flags, and fit outputs excluded.

Fit-output fold choices:

| heldout_run | candidate            | sign | train_auc | train_median | train_iqr | n_train | n_test |
| ----------- | -------------------- | ---- | --------- | ------------ | --------- | ------- | ------ |
| 58          | frac_sse_improvement | 1    | 0.607629  | 0.46869      | 0.738699  | 1140    | 18     |
| 59          | frac_sse_improvement | 1    | 0.604032  | 0.470814     | 0.731985  | 972     | 186    |
| 60          | frac_sse_improvement | 1    | 0.60263   | 0.458436     | 0.734061  | 900     | 258    |
| 61          | frac_sse_improvement | 1    | 0.622496  | 0.466038     | 0.742642  | 806     | 352    |
| 62          | frac_sse_improvement | 1    | 0.613319  | 0.46967      | 0.741311  | 936     | 222    |
| 63          | frac_sse_improvement | 1    | 0.609748  | 0.4679       | 0.744578  | 1044    | 114    |
| 65          | frac_sse_improvement | 1    | 0.61092   | 0.474937     | 0.74189   | 1150    | 8      |

Fit-output summary:

| class     | n   | valid_fraction | median_secondary_fraction | median_secondary_amp_norm | median_delay_samples | median_chi2_ndf | median_frac_sse_improvement |
| --------- | --- | -------------- | ------------------------- | ------------------------- | -------------------- | --------------- | --------------------------- |
| raw_clean | 579 | 0.614853       | 0.0787813                 | 0.0836907                 | 5                    | 0.0177819       | 0.18484                     |
| injected  | 579 | 0.740933       | 0.193294                  | 0.232977                  | 4                    | 0.0148847       | 0.539219                    |

RF scan:

| n_estimators | max_depth | min_samples_leaf | roc_auc  | average_precision | brier    |
| ------------ | --------- | ---------------- | -------- | ----------------- | -------- |
| 500          | 7         | 8                | 0.821774 | 0.83481           | 0.175043 |
| 400          | 5         | 15               | 0.794658 | 0.811703          | 0.185905 |
| 300          | 4         | 20               | 0.776676 | 0.794122          | 0.194116 |

## Head-to-Head

| method                           | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                              |
| -------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| bounded two-pulse fit outputs    | 0.607549 | 0.593121       | 0.622313        | 0.632821          | 0.599228  | 0.654399   | 0.239429 | 0.234688     | 0.246842      | Fold-local score selected from constrained-fit outputs only: secondary fraction/amplitude, delay, chi2/ndf, SSE, and fractional SSE improvement.                   |
| direct D_t/curvature cross-check | 0.530522 | 0.515176       | 0.537398        | 0.581449          | 0.565437  | 0.597185   | 0.24422  | 0.241128     | 0.247745      | Diagnostic only; label is injected truth, not a D_t tail threshold.                                                                                                |
| shape-only RF                    | 0.821774 | 0.798902       | 0.846064        | 0.83481           | 0.814542  | 0.861304   | 0.175043 | 0.161193     | 0.1898        | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, ids, injection parameters, amplitudes, topology flags, and fit outputs. |

## Leakage Hunt

| probe                                  | roc_auc  | average_precision | notes                                                 |
| -------------------------------------- | -------- | ----------------- | ----------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same for clean/injected pairs; should be chance.      |
| topology-only RF                       | 0.5      | 0.5               | Constant all-three topology; should be chance.        |
| absolute-amplitude-only RF             | 0.564989 | 0.57132           | Excluded from main RF; injection changes peak height. |
| shape RF with shuffled training labels | 0.490514 | 0.478764          | Null/leakage sanity check.                            |
| per-stave slot shape RF                | 0.851986 | 0.856799          | Permissive shape representation; not main claim.      |
| pair split violations                  | 0        |                   | Must be 0.                                            |
| forbidden main RF columns              | 0        |                   | None.                                                 |

Pair ids are split by run, pair split violations are zero, the main RF contains no forbidden columns, and the shuffled-label RF remains near chance. The amplitude-only probe is kept out of the main method because the injection can change peak height.

## Finding

The full bounded fit improves interpretability but does not close the S07f RF gap. On the same all-three injected target, fit-output-only scoring reaches ROC AUC **0.608** [0.593, 0.622], while the shape-only RF reaches **0.822** [0.799, 0.846]. The RF advantage is **0.214** AUC.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11d_1781025690_946_49cd6f1d_constrained_all_three_fit.py --config configs/s11d_1781025690_946_49cd6f1d_constrained_all_three_fit.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07f_reproduction_scoreboard.csv`, `scoreboard.csv`, `two_pulse_fit_oof.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.
