# S07n: hierarchical support-pooling calibration for injected morphology

- **Study ID:** S07n
- **Ticket:** 1783600624.24816.324219c6
- **Author:** testbeam-laptop-2
- **Date:** 2026-07-11
- **Depends on:** S07h (`reports/1781015838.1407.0539203d`) and S07d helper code
- **Input:** raw B-stack `HRDv` ROOT files under `data/root/root`
- **Config:** `configs/s07n_1783600624_24816_324219c6_hierarchical_support_pooling.json`
- **Git commit used by script:** 022cedd84ba0617d3bd7d486f8a072a8aee9dcfa

## 0. Question
Can hierarchical pooling across adjacent run, amplitude, topology, and baseline support strata reduce sparse-stratum fallback while preserving injected AP/AUC and keeping timing, charge, baseline, topology, saturation, and pile-up drift within the S07m support-drift bounds?

Pre-registered ticket text: can hierarchical pooling across adjacent run/amplitude/topology/baseline support strata reduce sparse-stratum fallback while preserving injected AP/AUC and keeping timing/charge/baseline/topology drift within S07m bounds? Expected information gain: distinguishes true morphology signal from sparse-bin threshold noise and gives a deployment-ready calibration rule if fallback collapses without drift. The benchmark still names a method-family winner against a strong traditional timing/template comparator on identical leave-one-run-out folds.

## 1. Reproduction Gate
The script starts from raw ROOT, rebuilds the S07h/P02d inputs, and refuses to continue unless the parent numbers match. The parent S07h RF AUC is also rerun on the same raw-derived injected rows as a continuity check.

| quantity                                   | report_value | reproduced | delta        | tolerance | pass | sample_size |
| ------------------------------------------ | ------------ | ---------- | ------------ | --------- | ---- | ----------- |
| P02 early-peak pulse rate, peak_sample<=3  | 0.044        | 0.0438833  | -0.000116667 | 0.002     | True | 60000       |
| S07 parent guarded gross events, D_t>51 ns | 72           | 72         | 0            | 0         | True | 10156       |
| P02d transparent morphology ROC AUC        | 0.692169     | 0.692169   | 0            | 1e-12     | True | 2227        |
| S07h shape-only RF injected ROC AUC        | 0.859788     | 0.860449   | 0.000660741  | 0.025     | True | 4310        |

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
| gradient_boosted_trees                | 0.916447 | 0.901277       | 0.930591        | 0.920581          | 0.906789  | 0.937246   | 0.119092 | 0.106295     | 0.135304      | Histogram gradient-boosted trees on strict normalized morphology features.                                     |
| mlp                                   | 0.901606 | 0.887334       | 0.920805        | 0.902297          | 0.889944  | 0.920769   | 0.133493 | 0.116141     | 0.153385      | Small early-stopped dense neural network on strict normalized morphology features.                             |
| random_forest_s07h                    | 0.860449 | 0.835842       | 0.883307        | 0.873343          | 0.84956   | 0.89833    | 0.155261 | 0.141299     | 0.170874      | S07h random-forest continuity model; best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}. |
| ridge_logistic                        | 0.818442 | 0.804553       | 0.832063        | 0.819922          | 0.801299  | 0.844218   | 0.175527 | 0.166401     | 0.186047      | L2-regularized logistic regression on strict normalized morphology features.                                   |
| residual_tcn_fusion                   | 0.800683 | 0.776011       | 0.823295        | 0.791862          | 0.766227  | 0.818456   | 0.179515 | 0.165365     | 0.193224      | New residual dilated temporal CNN with non-sample morphology-stat fusion.                                      |
| cnn_1d                                | 0.676587 | 0.664617       | 0.688959        | 0.688667          | 0.673879  | 0.70602    | 0.220603 | 0.215914     | 0.22664       | Small 1D-CNN over B2/downstream mean/downstream std normalized waveforms.                                      |
| traditional timing/template reference | 0.612406 | 0.603512       | 0.625993        | 0.577832          | 0.571537  | 0.587535   | 0.240167 | 0.237256     | 0.24239       | Strong fold-local timing/template score; primary traditional comparator.                                       |
| transparent P02 morphology            | 0.527618 | 0.520403       | 0.536934        | 0.510367          | 0.506478  | 0.515632   | 0.248646 | 0.247891     | 0.249415      | Train-fold-selected transparent P02 morphology cuts/scores only.                                               |

Winner recorded in `result.json`: **gradient_boosted_trees**, ROC AUC **0.9164** with 95 percent run-block CI **[0.9013, 0.9306]**. The traditional timing/template reference reaches ROC AUC **0.6124** [0.6035, 0.6260].

## 4. Operating-Point Benchmark
Thresholds are determined without the held-out run. For score \(s\), the fixed-clean-efficiency gate sets \(\tau_r=Q_{0.95}(s_i:y_i=0,i\notin r)\); clean rows with \(s>\tau_r\) are false positives, injected rows with \(s>\tau_r\) are true detections. The fixed-FPR gate uses the same 95th clean percentile because the pre-registered FPR is 0.05.

| method                                | mode                      | clean_acceptance_mean | false_positive_rate_mean | injected_rejection_mean | runs |
| ------------------------------------- | ------------------------- | --------------------- | ------------------------ | ----------------------- | ---- |
| gradient_boosted_trees                | fixed_clean_efficiency    | 0.953198              | 0.0468017                | 0.594869                | 7    |
| mlp                                   | fixed_clean_efficiency    | 0.951907              | 0.0480927                | 0.584319                | 7    |
| random_forest_s07h                    | fixed_clean_efficiency    | 0.95166               | 0.0483404                | 0.500848                | 7    |
| residual_tcn_fusion                   | fixed_clean_efficiency    | 0.951224              | 0.0487764                | 0.429703                | 7    |
| ridge_logistic                        | fixed_clean_efficiency    | 0.952663              | 0.0473365                | 0.389498                | 7    |
| cnn_1d                                | fixed_clean_efficiency    | 0.948283              | 0.0517174                | 0.26906                 | 7    |
| traditional timing/template reference | fixed_clean_efficiency    | 0.917118              | 0.0828819                | 0.108604                | 7    |
| transparent P02 morphology            | fixed_clean_efficiency    | 0.956551              | 0.0434486                | 0.0383382               | 7    |
| gradient_boosted_trees                | fixed_false_positive_rate | 0.953198              | 0.0468017                | 0.594869                | 7    |
| mlp                                   | fixed_false_positive_rate | 0.951907              | 0.0480927                | 0.584319                | 7    |
| random_forest_s07h                    | fixed_false_positive_rate | 0.95166               | 0.0483404                | 0.500848                | 7    |
| residual_tcn_fusion                   | fixed_false_positive_rate | 0.951224              | 0.0487764                | 0.429703                | 7    |
| ridge_logistic                        | fixed_false_positive_rate | 0.952663              | 0.0473365                | 0.389498                | 7    |
| cnn_1d                                | fixed_false_positive_rate | 0.948283              | 0.0517174                | 0.26906                 | 7    |
| traditional timing/template reference | fixed_false_positive_rate | 0.917118              | 0.0828819                | 0.108604                | 7    |
| transparent P02 morphology            | fixed_false_positive_rate | 0.956551              | 0.0434486                | 0.0383382               | 7    |

## 5. Real-Support Drift
Support drift is measured only on the raw-clean member of each pair, using held-out thresholds. Timing is the robust \(\sigma_{68}\) of post-reconstruction downstream `D_t`; charge uses the mean log-amplitude proxy across selected B staves; baseline uses final-sample fraction; saturation uses a top-decile log-amplitude proxy; pile-up uses mean `D_t`; topology uses downstream multiplicity. These are support diagnostics, not independent beam truth labels.

| method                                | veto_fraction | timing_sigma68_delta_ns | charge_logamp_delta | baseline_final_fraction_delta | saturation_logamp_top10_delta | pileup_dt_mean_delta_ns | topology_n_downstream_delta |
| ------------------------------------- | ------------- | ----------------------- | ------------------- | ----------------------------- | ----------------------------- | ----------------------- | --------------------------- |
| transparent P02 morphology            | 0.0434486     | -0.050526               | 0.0230194           | 0.0453063                     | 0.0081987                     | 0.0455456               | 0.00274798                  |
| traditional timing/template reference | 0.0828819     | 0.00288746              | 0.00591382          | -0.0800259                    | 0.0067963                     | -0.0129244              | 0.00621514                  |
| random_forest_s07h                    | 0.0483404     | -0.00800377             | -0.00307745         | -0.00812346                   | -0.0018819                    | -0.00489204             | 0.00154359                  |
| ridge_logistic                        | 0.0473365     | -0.00343758             | 0.00322124          | -0.000794119                  | 0.00110609                    | -0.00111582             | 0.00283555                  |
| gradient_boosted_trees                | 0.0468017     | -0.00777562             | -0.00595423         | -0.00815093                   | 0.000359153                   | 0.00585275              | 0.000433491                 |
| mlp                                   | 0.0480927     | -0.00474364             | 0.00349921          | -0.00113823                   | 0.000220811                   | -0.00466454             | 0.00310562                  |
| cnn_1d                                | 0.0517174     | -0.00725395             | -0.0266322          | 1.44198e-05                   | -0.00189269                   | 0.00860645              | -0.013018                   |
| residual_tcn_fusion                   | 0.0487764     | -0.00747944             | -0.0107467          | -0.00940621                   | -0.0028383                    | 0.00575348              | -0.00225513                 |

## 6. Hierarchical Support-Pooling Calibration
For each held-out row, S07n replaces one global threshold with a support-local threshold. The exact clean stratum is amplitude quantile, downstream topology, and baseline-final-fraction quantile. Because exact strata can be sparse, the calibration backs off through a fixed hierarchy:

\[
\mathcal P_i =
\begin{cases}
\mathrm{adjacent\ run}\cap a_i\cap t_i\cap b_i, & n\ge n_{\min}\\
a_i\cap t_i\cap b_i, & n\ge n_{\min}\\
a_i\cap t_i, & n\ge n_{\min}\\
a_i, & n\ge n_{\min}\\
\mathrm{all\ training\ clean}, & \mathrm{otherwise}.
\end{cases}
\]

The per-row threshold is \(\tau_i=Q_{0.95}(s_j:j\in\mathcal P_i,y_j=0)\), computed only from training runs. The table reports whether pooling collapses sparse exact-stratum fallback while retaining injected rejection and clean false-positive control.

| method                                | pool_level                         | n_rows | n_clean | n_injected | mean_pool_clean | clean_false_positive_rate | injected_rejection | exact_stratum_available_fraction |
| ------------------------------------- | ---------------------------------- | ------ | ------- | ---------- | --------------- | ------------------------- | ------------------ | -------------------------------- |
| transparent P02 morphology            | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.0724495                 | 0.077193           | 1                                |
| transparent P02 morphology            | amp_only                           | 6      | 0       | 6          | 426             |                           | 0                  | 0                                |
| transparent P02 morphology            | amp_topology                       | 126    | 52      | 74         | 428.77          | 0.403846                  | 0.324324           | 0                                |
| transparent P02 morphology            | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.0945946                 | 0.1625             | 1                                |
| transparent P02 morphology            | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0812065                 | 0.0886311          | 0.969374                         |
| traditional timing/template reference | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.0576639                 | 0.123308           | 1                                |
| traditional timing/template reference | amp_only                           | 6      | 0       | 6          | 426             |                           | 0                  | 0                                |
| traditional timing/template reference | amp_topology                       | 126    | 52      | 74         | 428.77          | 0.346154                  | 0.337838           | 0                                |
| traditional timing/template reference | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.108108                  | 0.275              | 1                                |
| traditional timing/template reference | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0663573                 | 0.135963           | 0.969374                         |
| random_forest_s07h                    | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.0660424                 | 0.553885           | 1                                |
| random_forest_s07h                    | amp_only                           | 6      | 0       | 6          | 426             |                           | 0.166667           | 0                                |
| random_forest_s07h                    | amp_topology                       | 126    | 52      | 74         | 428.77          | 0.0384615                 | 0.5                | 0                                |
| random_forest_s07h                    | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.027027                  | 0.3625             | 1                                |
| random_forest_s07h                    | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0640371                 | 0.543852           | 0.969374                         |
| ridge_logistic                        | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.0660424                 | 0.418546           | 1                                |
| ridge_logistic                        | amp_only                           | 6      | 0       | 6          | 426             |                           | 0                  | 0                                |
| ridge_logistic                        | amp_topology                       | 126    | 52      | 74         | 428.77          | 0                         | 0.5                | 0                                |
| ridge_logistic                        | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.0540541                 | 0.3625             | 1                                |
| ridge_logistic                        | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0640371                 | 0.418097           | 0.969374                         |
| gradient_boosted_trees                | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.073928                  | 0.688221           | 1                                |
| gradient_boosted_trees                | amp_only                           | 6      | 0       | 6          | 426             |                           | 0.833333           | 0                                |
| gradient_boosted_trees                | amp_topology                       | 126    | 52      | 74         | 428.77          | 0.0769231                 | 0.513514           | 0                                |
| gradient_boosted_trees                | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.0540541                 | 0.5                | 1                                |
| gradient_boosted_trees                | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0733179                 | 0.675638           | 0.969374                         |
| mlp                                   | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.0837851                 | 0.634586           | 1                                |
| mlp                                   | amp_only                           | 6      | 0       | 6          | 426             |                           | 0.166667           | 0                                |
| mlp                                   | amp_topology                       | 126    | 52      | 74         | 428.77          | 0.0769231                 | 0.554054           | 0                                |
| mlp                                   | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.0675676                 | 0.4875             | 1                                |
| mlp                                   | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0830626                 | 0.625058           | 0.969374                         |
| cnn_1d                                | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.0660424                 | 0.283208           | 1                                |
| cnn_1d                                | amp_only                           | 6      | 0       | 6          | 426             |                           | 0                  | 0                                |
| cnn_1d                                | amp_topology                       | 126    | 52      | 74         | 428.77          | 0.0576923                 | 0.310811           | 0                                |
| cnn_1d                                | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.108108                  | 0.25               | 1                                |
| cnn_1d                                | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0672854                 | 0.282135           | 0.969374                         |
| residual_tcn_fusion                   | adjacent_run_amp_topology_baseline | 4024   | 2029    | 1995       | 134.996         | 0.0625924                 | 0.406015           | 1                                |
| residual_tcn_fusion                   | amp_only                           | 6      | 0       | 6          | 426             |                           | 0                  | 0                                |
| residual_tcn_fusion                   | amp_topology                       | 126    | 52      | 74         | 428.77          | 0.0576923                 | 0.378378           | 0                                |
| residual_tcn_fusion                   | any_run_amp_topology_baseline      | 154    | 74      | 80         | 97.1169         | 0.108108                  | 0.35               | 1                                |
| residual_tcn_fusion                   | all_hierarchical                   | 4310   | 2155    | 2155       | 142.635         | 0.0640371                 | 0.401856           | 0.969374                         |

## 7. Falsification and Leakage Checks
The falsification criterion was pre-registered before running this ticket: a model is not useful if its run-held-out injected AUC/AP gain is matched by amplitude-only, topology-only, shuffled-label, or leakage probes, or if a fixed operating point imposes large support drift. Multiple model families were tested; the conclusion names a point-estimate winner but does not promote the gate for production adoption.

| probe                                  | roc_auc  | average_precision | notes                                                               |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same source event before corruption; should be chance.              |
| topology-only RF                       | 0.501012 | 0.501909          | Present flags and downstream count only; excluded from main models. |
| absolute-amplitude-only RF             | 0.587415 | 0.609263          | Injection can change peak height; excluded from main models.        |
| shape RF with shuffled training labels | 0.494767 | 0.497189          | Run-heldout null sanity check.                                      |
| pair split violations                  | 0        |                   | Must be 0.                                                          |
| forbidden main feature columns         | 0        |                   | None.                                                               |

The strongest nuisance probe is amplitude-only because injection can alter peak height. It is not part of the main feature set. Pair split violations and forbidden main columns are both required to be zero.

## 8. Systematics and Caveats
- **Benchmark fairness:** the traditional timing/template score is strong and receives timing/template handles excluded from the shape-only learned models. This makes the learned win, if present, harder to obtain.
- **Data leakage:** all splits are by run; paired injected/raw rows are never split across train/test; model features exclude identifiers and label-defining timing variables.
- **Metric misuse:** ROC AUC and AP describe injected closure detection, not a measured beam pile-up rate. Support-drift rows are diagnostics over raw-clean events.
- **Pooling interpretation:** hierarchical pooling is a threshold calibration study, not a new detector label; adjacent-run pooling still excludes the held-out run and therefore tests deployable calibration rather than in-run tuning.
- **Post-hoc selection:** model grids, operating points, and primary metrics are in the config. Because several methods are compared, the winner is a screening winner with bootstrap CIs rather than a deployment claim.
- **Systematics not covered by bootstrap:** future run-domain shift, artificial injection realism, missing real-current truth labels, and the use of support proxies for charge/baseline/saturation are outside the run-block CI.

## 9. Findings and Next Step
The strongest conclusion is that waveform-shape learning remains useful on independent injected truth, but operating-point use is not automatically safe. The benchmark winner is **gradient_boosted_trees**, while the support-drift and hierarchical-pooling tables should be treated as gatekeepers for any downstream use. Hypothesis: injected overlap morphology is concentrated in downstream normalized temporal residuals, not in topology or original timing-tail labels; production use needs support-aware calibration rather than a pure high-score veto.

One follow-up is queued in `result.json`: S07o should validate the S07n hierarchical support-pooling gate on non-injected real-current control windows with blinded manual waveform adjudication. Expected information gain: separates injected-closure utility from real-current waveform-pathology transfer.

## 10. Reproducibility
Regenerate all artifacts with:

```bash
uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/s07n_1783600624_24816_324219c6_hierarchical_support_pooling.py --config configs/s07n_1783600624_24816_324219c6_hierarchical_support_pooling.json
```

Key artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `method_summary.csv`, `operating_point_summary.csv`, `support_drift_by_run.csv`, `hierarchical_pooling_summary.csv`, `hierarchical_pooling_by_row.csv`, `leakage_checks.csv`, `hyperparameter_cv.csv`, `oof_predictions.csv`, and figures `fig_method_auc.png`, `fig_post_injection_dt.png`, `fig_winner_score.png`, `fig_reliability.png`.
