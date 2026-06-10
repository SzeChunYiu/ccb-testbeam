# S07l: injected morphology operating-point support audit

- **Study ID:** S07l
- **Ticket:** 1781039488.1142.659b28c4
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Depends on:** S07h (`reports/1781015838.1407.0539203d`) and S07d helper code
- **Input:** raw B-stack `HRDv` ROOT files under `data/root/root`
- **Config:** `configs/s07l_1781039488_1142_659b28c4_operating_point_support.json`
- **Git commit used by script:** 1bbc67bdfcfb3d61d423d4ca04ac5a0d908ccf3c

## 0. Question
Can the S07h injected non-`D_t` morphology detector be run at fixed clean efficiency / fixed false-positive rate without large support drift, and which model family wins against a strong traditional timing/template comparator on identical leave-one-run-out folds?

Pre-registered ticket text: can the S07h injected non-`D_t` morphology RF be operated at fixed efficiency or fixed false-positive rate without distorting real timing, charge, baseline, saturation, pile-up, or topology support. Metrics are injected AP/AUC, fixed-efficiency FPR, real-data support drift, timing sigma68/tail delta, charge-bias delta, and ML-minus-traditional utility with run-block bootstrap 95 percent CIs.

## 1. Reproduction Gate
The script starts from raw ROOT, rebuilds the S07h/P02d inputs, and refuses to continue unless the parent numbers match. The parent S07h RF AUC is also rerun on the same raw-derived injected rows as a continuity check.

| quantity                                   | report_value | reproduced | delta        | tolerance | pass | sample_size |
| ------------------------------------------ | ------------ | ---------- | ------------ | --------- | ---- | ----------- |
| P02 early-peak pulse rate, peak_sample<=3  | 0.044        | 0.0438833  | -0.000116667 | 0.002     | True | 60000       |
| S07 parent guarded gross events, D_t>51 ns | 72           | 72         | 0            | 0         | True | 10156       |
| P02d transparent morphology ROC AUC        | 0.692169     | 0.692169   | 0            | 1e-12     | True | 2227        |
| S07h shape-only RF injected ROC AUC        | 0.859788     | 0.860185   | 0.000397069  | 0.025     | True | 4310        |

The reproduced dataset contains paired raw-clean and injected rows. Raw and injected members share a `pair_id` and are split together because the outer fold is the run.

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 37        | 37       | 74    |
| 59  | 415       | 415      | 830   |
| 60  | 428       | 428      | 856   |
| 61  | 607       | 607      | 1214  |
| 62  | 420       | 420      | 840   |
| 63  | 194       | 194      | 388   |
| 65  | 54        | 54       | 108   |

## 2. Traditional Method
The strong traditional comparator is the S07d/S07h fold-selected timing/template score. For each held-out run, training runs choose a signed one-dimensional score from downstream `D_t`, `|C_t|`, late-fraction summaries, downstream peak/shape summaries, and a fold-local matched-secondary-template residual. The selected score is centered and scaled by the training interquartile range before applying to the held-out run:

\[
s_{i,r} = \frac{\operatorname{sign}(j_r)x_{ij_r}-\operatorname{median}_{k\in T_r}(\operatorname{sign}(j_r)x_{kj_r})}{\operatorname{IQR}_{k\in T_r}(\operatorname{sign}(j_r)x_{kj_r})}.
\]

This is a deliberately strong baseline because it can use timing/template observables that the neural shape models do not receive. It is not a strawman P02 early-peak cut.

## 3. ML and Neural Methods
All learned models use the same outer leave-one-run-out split. Dense ML methods receive strict S07h morphology features: normalized B2 shape plus downstream mean/std normalized-shape summaries, excluding run, event id, pair id, injection target/delay/scale, absolute amplitudes, selected-present flags, `D_t`, and `C_t`. The 1D-CNN receives three channels over 18 samples: B2 normalized shape, downstream mean normalized shape, and downstream normalized-shape standard deviation. The new architecture, `residual_tcn_fusion`, adds dilated residual temporal convolutions and fuses non-sample morphology summaries after the temporal block.

For the dense models, hyperparameters are chosen by inner leave-one-run-out CV on the outer training runs. For the neural models, one deterministic run-held-out inner validation run per outer fold selects channel width and dropout from the configured two-point grid; models are intentionally small CPU models. Probabilities are cross-fold isotonic calibrations:

\[
\hat p_i = g_{-r(i)}(s_i),\qquad g_{-r}=\arg\min_{g\;\mathrm{isotonic}}\sum_{i\notin r}(y_i-g(s_i))^2.
\]

The resulting benchmark table is:

| method                                | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                          |
| ------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | -------------------------------------------------------------------------------------------------------------- |
| gradient_boosted_trees                | 0.916447 | 0.902933       | 0.931006        | 0.920581          | 0.904409  | 0.937268   | 0.119092 | 0.105847     | 0.136793      | Histogram gradient-boosted trees on strict normalized morphology features.                                     |
| mlp                                   | 0.902995 | 0.874067       | 0.929625        | 0.908207          | 0.882607  | 0.931389   | 0.128761 | 0.105351     | 0.152466      | Small early-stopped dense neural network on strict normalized morphology features.                             |
| random_forest_s07h                    | 0.860185 | 0.840719       | 0.881292        | 0.874182          | 0.850854  | 0.895774   | 0.155377 | 0.141227     | 0.171268      | S07h random-forest continuity model; best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}. |
| ridge_logistic                        | 0.818442 | 0.804267       | 0.832404        | 0.819922          | 0.799597  | 0.842511   | 0.175527 | 0.166305     | 0.18592       | L2-regularized logistic regression on strict normalized morphology features.                                   |
| residual_tcn_fusion                   | 0.787019 | 0.759413       | 0.813725        | 0.782797          | 0.752027  | 0.813627   | 0.185323 | 0.172305     | 0.197604      | New residual dilated temporal CNN with non-sample morphology-stat fusion.                                      |
| cnn_1d                                | 0.689399 | 0.670779       | 0.707426        | 0.70015           | 0.674773  | 0.722472   | 0.217962 | 0.211036     | 0.22505       | Small 1D-CNN over B2/downstream mean/downstream std normalized waveforms.                                      |
| traditional timing/template reference | 0.612406 | 0.603955       | 0.627405        | 0.577832          | 0.571238  | 0.586359   | 0.240167 | 0.23741      | 0.242476      | Strong fold-local timing/template score; primary traditional comparator.                                       |
| transparent P02 morphology            | 0.527618 | 0.520173       | 0.536852        | 0.510367          | 0.506473  | 0.515948   | 0.248646 | 0.247926     | 0.249467      | Train-fold-selected transparent P02 morphology cuts/scores only.                                               |

Winner recorded in `result.json`: **gradient_boosted_trees**, ROC AUC **0.9164** with 95 percent run-block CI **[0.9029, 0.9310]**. The traditional timing/template reference reaches ROC AUC **0.6124** [0.6040, 0.6274].

## 4. Operating-Point Benchmark
Thresholds are determined without the held-out run. For score \(s\), the fixed-clean-efficiency gate sets \(\tau_r=Q_{0.95}(s_i:y_i=0,i\notin r)\); clean rows with \(s>\tau_r\) are false positives, injected rows with \(s>\tau_r\) are true detections. The fixed-FPR gate uses the same 95th clean percentile because the pre-registered FPR is 0.05.

| method                                | mode                      | clean_acceptance_mean | false_positive_rate_mean | injected_rejection_mean | runs |
| ------------------------------------- | ------------------------- | --------------------- | ------------------------ | ----------------------- | ---- |
| mlp                                   | fixed_clean_efficiency    | 0.951006              | 0.0489941                | 0.623795                | 7    |
| gradient_boosted_trees                | fixed_clean_efficiency    | 0.953198              | 0.0468017                | 0.594869                | 7    |
| random_forest_s07h                    | fixed_clean_efficiency    | 0.947937              | 0.0520626                | 0.497237                | 7    |
| residual_tcn_fusion                   | fixed_clean_efficiency    | 0.944013              | 0.0559869                | 0.425016                | 7    |
| ridge_logistic                        | fixed_clean_efficiency    | 0.952663              | 0.0473365                | 0.389498                | 7    |
| cnn_1d                                | fixed_clean_efficiency    | 0.952698              | 0.0473019                | 0.283418                | 7    |
| traditional timing/template reference | fixed_clean_efficiency    | 0.917118              | 0.0828819                | 0.108604                | 7    |
| transparent P02 morphology            | fixed_clean_efficiency    | 0.956551              | 0.0434486                | 0.0383382               | 7    |
| mlp                                   | fixed_false_positive_rate | 0.951006              | 0.0489941                | 0.623795                | 7    |
| gradient_boosted_trees                | fixed_false_positive_rate | 0.953198              | 0.0468017                | 0.594869                | 7    |
| random_forest_s07h                    | fixed_false_positive_rate | 0.947937              | 0.0520626                | 0.497237                | 7    |
| residual_tcn_fusion                   | fixed_false_positive_rate | 0.944013              | 0.0559869                | 0.425016                | 7    |
| ridge_logistic                        | fixed_false_positive_rate | 0.952663              | 0.0473365                | 0.389498                | 7    |
| cnn_1d                                | fixed_false_positive_rate | 0.952698              | 0.0473019                | 0.283418                | 7    |
| traditional timing/template reference | fixed_false_positive_rate | 0.917118              | 0.0828819                | 0.108604                | 7    |
| transparent P02 morphology            | fixed_false_positive_rate | 0.956551              | 0.0434486                | 0.0383382               | 7    |

## 5. Real-Support Drift
Support drift is measured only on the raw-clean member of each pair, using held-out thresholds. Timing is the robust \(\sigma_{68}\) of post-reconstruction downstream `D_t`; charge uses the mean log-amplitude proxy across selected B staves; baseline uses final-sample fraction; saturation uses a top-decile log-amplitude proxy; pile-up uses mean `D_t`; topology uses downstream multiplicity. These are support diagnostics, not independent beam truth labels.

| method                                | veto_fraction | timing_sigma68_delta_ns | charge_logamp_delta | baseline_final_fraction_delta | saturation_logamp_top10_delta | pileup_dt_mean_delta_ns | topology_n_downstream_delta |
| ------------------------------------- | ------------- | ----------------------- | ------------------- | ----------------------------- | ----------------------------- | ----------------------- | --------------------------- |
| transparent P02 morphology            | 0.0434486     | -0.050526               | 0.0230194           | 0.0453063                     | 0.0081987                     | 0.0455456               | 0.00274798                  |
| traditional timing/template reference | 0.0828819     | 0.00288746              | 0.00591382          | -0.0800259                    | 0.0067963                     | -0.0129244              | 0.00621514                  |
| random_forest_s07h                    | 0.0520626     | -0.00743918             | -0.00409681         | -0.00821327                   | -0.00150056                   | -0.00437955             | 0.001127                    |
| ridge_logistic                        | 0.0473365     | -0.00343758             | 0.00322124          | -0.000794119                  | 0.00110609                    | -0.00111582             | 0.00283555                  |
| gradient_boosted_trees                | 0.0468017     | -0.00777562             | -0.00595423         | -0.00815093                   | 0.000359153                   | 0.00585275              | 0.000433491                 |
| mlp                                   | 0.0489941     | -0.016339               | -0.00113459         | -0.00265058                   | -0.000676529                  | 0.00737335              | 0.00148512                  |
| cnn_1d                                | 0.0473019     | -0.00575417             | -0.0236474          | -0.00151943                   | -0.00106581                   | 0.00789215              | -0.0115227                  |
| residual_tcn_fusion                   | 0.0559869     | -0.0142698              | -0.00742259         | -0.00903266                   | -0.0016756                    | 0.00865197              | -0.00142553                 |

## 6. Falsification and Leakage Checks
The falsification criterion was pre-registered before running this ticket: a model is not useful if its run-held-out injected AUC/AP gain is matched by amplitude-only, topology-only, shuffled-label, or leakage probes, or if a fixed operating point imposes large support drift. Multiple model families were tested; the conclusion names a point-estimate winner but does not promote the gate for production adoption.

| probe                                  | roc_auc  | average_precision | notes                                                               |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same source event before corruption; should be chance.              |
| topology-only RF                       | 0.501066 | 0.501262          | Present flags and downstream count only; excluded from main models. |
| absolute-amplitude-only RF             | 0.587159 | 0.609659          | Injection can change peak height; excluded from main models.        |
| shape RF with shuffled training labels | 0.509618 | 0.50543           | Run-heldout null sanity check.                                      |
| pair split violations                  | 0        |                   | Must be 0.                                                          |
| forbidden main feature columns         | 0        |                   | None.                                                               |

The strongest nuisance probe is amplitude-only because injection can alter peak height. It is not part of the main feature set. Pair split violations and forbidden main columns are both required to be zero.

## 7. Systematics and Caveats
- **Benchmark fairness:** the traditional timing/template score is strong and receives timing/template handles excluded from the shape-only learned models. This makes the learned win, if present, harder to obtain.
- **Data leakage:** all splits are by run; paired injected/raw rows are never split across train/test; model features exclude identifiers and label-defining timing variables.
- **Metric misuse:** ROC AUC and AP describe injected closure detection, not a measured beam pile-up rate. Support-drift rows are diagnostics over raw-clean events.
- **Post-hoc selection:** model grids, operating points, and primary metrics are in the config. Because several methods are compared, the winner is a screening winner with bootstrap CIs rather than a deployment claim.
- **Systematics not covered by bootstrap:** future run-domain shift, artificial injection realism, missing real-current truth labels, and the use of support proxies for charge/baseline/saturation are outside the run-block CI.

## 8. Findings and Next Step
The strongest conclusion is that waveform-shape learning remains useful on independent injected truth, but operating-point use is not automatically safe. The benchmark winner is **gradient_boosted_trees**, while the support-drift table should be treated as the gatekeeper for any downstream use. Hypothesis: injected overlap morphology is concentrated in downstream normalized temporal residuals, not in topology or original timing-tail labels; a production gate would need support-preserving calibration rather than a pure high-score veto.

One follow-up is queued in `result.json`: S07m should test support-preserving score calibration by matching clean rows in run, amplitude, topology, and baseline-proxy strata before applying any injected-morphology threshold. Expected information gain: separates true injected-overlap sensitivity from threshold-induced population distortion.

## 9. Reproducibility
Regenerate all artifacts with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with torch python scripts/s07l_1781039488_1142_659b28c4_operating_point_support.py --config configs/s07l_1781039488_1142_659b28c4_operating_point_support.json
```

Key artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `method_summary.csv`, `operating_point_summary.csv`, `support_drift_by_run.csv`, `leakage_checks.csv`, `hyperparameter_cv.csv`, `oof_predictions.csv`, and figures `fig_method_auc.png`, `fig_post_injection_dt.png`, `fig_winner_score.png`, `fig_reliability.png`.
