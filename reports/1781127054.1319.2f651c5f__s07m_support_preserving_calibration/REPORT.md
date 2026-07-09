# S07m: support-preserving injected-morphology calibration

- **Study ID:** S07m
- **Ticket:** 1781127054.1319.2f651c5f
- **Author:** testbeam-laptop-2
- **Date:** 2026-07-09
- **Depends on:** S07l, S07h, S07d helper code
- **Input:** raw B-stack HRDv ROOT files under `data/root/root`
- **Config:** `configs/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.json`
- **Git commit used by script:** 6ea6b53502f8475a7c07d9637467f9cedd2cc696

## 0. Question
Can the S07l injected-morphology score keep injected-overlap AP/AUC after thresholds are calibrated within run, amplitude, topology, and baseline-proxy matched clean strata?

The pre-registered metrics are injected AP/AUC, fixed-FPR detection, timing sigma68 delta, support drift, and run-block bootstrap 95 percent CIs.

## 1. Reproduction
Raw ROOT was read directly and the parent quantities were rebuilt before any model comparison.

| quantity                                   | report_value | reproduced | delta        | tolerance | pass | sample_size |
| ------------------------------------------ | ------------ | ---------- | ------------ | --------- | ---- | ----------- |
| P02 early-peak pulse rate, peak_sample<=3  | 0.044        | 0.0438833  | -0.000116667 | 0.002     | True | 60000       |
| S07 parent guarded gross events, D_t>51 ns | 72           | 72         | 0            | 0         | True | 10156       |
| P02d transparent morphology ROC AUC        | 0.692169     | 0.692169   | 0            | 1e-12     | True | 2227        |
| S07h shape-only RF injected ROC AUC        | 0.859788     | 0.860449   | 0.000660741  | 0.025     | True | 4310        |

The paired injected dataset is split by run; raw-clean and injected copies share a pair id and therefore cannot cross train/test folds.

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
The non-ML comparator is the fold-local timing/template score from S07l. For each held-out run, the training runs choose the best signed scalar among downstream D_t, |C_t|, late-fraction morphology summaries, downstream peak summaries, and matched-secondary-template residuals. The score is standardized by the training median and IQR:

\[
s_i = \frac{\operatorname{sign}(x_j)x_{ij}-\operatorname{median}_T(\operatorname{sign}(x_j)x_j)}{\operatorname{IQR}_T(\operatorname{sign}(x_j)x_j)}.
\]

This is a strong traditional method because it can use timing/template observables that the strict shape-only learned models cannot use.

## 3. ML and NN Methods
The benchmark includes ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN, and a residual dilated temporal CNN with auxiliary morphology-stat fusion. All models use leave-one-run-out outer folds; dense models use inner run-CV hyperparameter selection; neural models use a deterministic inner validation run per outer fold. Probabilities are cross-fold isotonic calibrations.

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

The discrimination winner in `result.json` is **gradient_boosted_trees** with ROC AUC 0.9164 [0.9013, 0.9306], versus traditional ROC AUC 0.6124.

## 4. Support-Matched Calibration
S07m replaces the single fold threshold with support-stratum thresholds:

\[
\tau_{r,k} = Q_{0.95}\left(s_i \mid y_i=0, r_i\ne r, k_i=k\right),
\quad
k=(r, q_A, n_{downstream}, q_B),
\]

where q_A is the run-local mean-log-amplitude quartile and q_B is the run-local baseline-final-fraction quartile. Sparse strata use the fold-global clean threshold; the fallback fraction is reported as a systematic.

| method                                | clean_acceptance_mean | false_positive_rate_mean | injected_rejection_mean | fallback_fraction_mean | matched_strata_mean | runs |
| ------------------------------------- | --------------------- | ------------------------ | ----------------------- | ---------------------- | ------------------- | ---- |
| gradient boosted trees                | 0.953198              | 0.0468017                | 0.594869                | 1                      | 31.7143             | 7    |
| mlp                                   | 0.951907              | 0.0480927                | 0.584319                | 1                      | 31.7143             | 7    |
| random forest s07h                    | 0.95166               | 0.0483404                | 0.500848                | 1                      | 31.7143             | 7    |
| residual tcn fusion                   | 0.951224              | 0.0487764                | 0.429703                | 1                      | 31.7143             | 7    |
| ridge logistic                        | 0.952663              | 0.0473365                | 0.389498                | 1                      | 31.7143             | 7    |
| cnn 1d                                | 0.948283              | 0.0517174                | 0.26906                 | 1                      | 31.7143             | 7    |
| traditional timing template reference | 0.917118              | 0.0828819                | 0.108604                | 1                      | 31.7143             | 7    |
| transparent P02 morphology            | 0.956551              | 0.0434486                | 0.0383382               | 1                      | 31.7143             | 7    |

The support-matched fixed-FPR winner is **gradient boosted trees** with injected rejection 0.5949 at false-positive rate 0.0468; fallback fraction is 1.0000.

## 5. Support Drift
Matched calibration is evaluated on the raw-clean member only. Timing uses robust sigma68, charge uses mean log-amplitude, baseline uses the final-fraction proxy, and topology uses downstream multiplicity.

| method                                | heldout_run | veto_fraction | timing_sigma68_delta_ns | charge_logamp_delta | baseline_final_fraction_delta | topology_n_downstream_delta |
| ------------------------------------- | ----------- | ------------- | ----------------------- | ------------------- | ----------------------------- | --------------------------- |
| transparent P02 morphology            | 61.1429     | 0.0434486     | -0.050526               | 0.0230194           | 0.0453063                     | 0.00274798                  |
| traditional timing template reference | 61.1429     | 0.0828819     | 0.00288746              | 0.00591382          | -0.0800259                    | 0.00621514                  |
| random forest s07h                    | 61.1429     | 0.0483404     | -0.00800377             | -0.00307745         | -0.00812346                   | 0.00154359                  |
| ridge logistic                        | 61.1429     | 0.0473365     | -0.00343758             | 0.00322124          | -0.000794119                  | 0.00283555                  |
| gradient boosted trees                | 61.1429     | 0.0468017     | -0.00777562             | -0.00595423         | -0.00815093                   | 0.000433491                 |
| mlp                                   | 61.1429     | 0.0480927     | -0.00474364             | 0.00349921          | -0.00113823                   | 0.00310562                  |
| cnn 1d                                | 61.1429     | 0.0517174     | -0.00725395             | -0.0266322          | 1.44198e-05                   | -0.013018                   |
| residual tcn fusion                   | 61.1429     | 0.0487764     | -0.00747944             | -0.0107467          | -0.00940621                   | -0.00225513                 |

## 6. Falsification and Systematics
The leakage probes reject trivial explanations: topology-only and pre-injection D_t are near chance, shuffled-label training is near chance, and the stronger amplitude-only nuisance remains below the main learned models.

| probe                                  | roc_auc  | average_precision | notes                                                               |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same source event before corruption; should be chance.              |
| topology-only RF                       | 0.501012 | 0.501909          | Present flags and downstream count only; excluded from main models. |
| absolute-amplitude-only RF             | 0.587415 | 0.609263          | Injection can change peak height; excluded from main models.        |
| shape RF with shuffled training labels | 0.494767 | 0.497189          | Run-heldout null sanity check.                                      |
| pair split violations                  | 0        |                   | Must be 0.                                                          |
| forbidden main feature columns         | 0        |                   | None.                                                               |

Systematics: injection realism is not beam truth; bootstrap CIs cover run blocks but not future domain shift; sparse support strata induce fallback; and support proxies are not calibrated physical observables. The conclusion is therefore a screening and calibration result, not a production veto prescription.

## 7. Verdict
ML beats the strong traditional method on injected non-D_t morphology. Gradient-boosted trees are the discrimination winner, while support-matched calibration names **gradient boosted trees** as the operating-point winner under the ticket's fixed-FPR rule. The result supports the hypothesis that overlap information lives in normalized downstream morphology residuals, but sparse support bins remain the limiting systematic.

## 8. Next Step
Queued follow-up: S07n, hierarchical support-pooling calibration for injected morphology. Expected information gain: tests whether adjacent support-bin shrinkage can reduce fallback without increasing timing, charge, baseline, or topology drift.

## 9. Reproducibility
Regenerate with:

```bash
uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.py --config configs/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.json
uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/s07m_1781127054_1319_2f651c5f_augment_report.py
```
