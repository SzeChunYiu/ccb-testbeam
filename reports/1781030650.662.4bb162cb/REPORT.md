# S16j: pretrigger hidden-mode stability audit

- **Ticket:** `1781030650.662.4bb162cb`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Depends on:** S16e/S16f/S16i and raw B-stack ROOT runs 44-57.
- **Config:** `configs/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.json`

## 0. Question

Does the pretrigger-only hidden-mode/tail-risk signal reported in the S16 family remain stable when each run is held out, or is it a quiet-proxy/run-sampling artifact? The preregistered primary benchmark is held-out ROC AUC for the S16i 20% tail-risk label, with AP and calibration ECE as secondary metrics. The label is a nuisance proxy, not forced/random pedestal truth.

## 1. Reproduction

Raw `h101/HRDv` was rescanned through the S10/S16 event builder before any model fit. The S16i pretrigger-only ML AUC scale is reproduced by rerunning the same tail-risk label with a run-held-out ridge/logistic pretrigger probe on the raw-derived table.

| quantity                                      |   report_value |     reproduced |        delta |   tolerance | pass   |
|:----------------------------------------------|---------------:|---------------:|-------------:|------------:|:-------|
| S10/S16 selected B-stave pulses in runs 44-57 |  252266        | 252266         |  0           |      0      | True   |
| low_2nA multi_stave_per_selected_event        |       0.0156   |      0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event        |       0.0041   |      0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event         |       0.0231   |      0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event      |       0.0268   |      0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event      |       0.0085   |      0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event       |       0.0334   |      0.0334141 |  1.41048e-05 |      0.0015 | True   |
| S16i reproduced ML tail AUC                   |       0.695784 |      0.690055  | -0.00572864  |      0.03   | True   |

The relevant prior ML AUC was 0.695784; this run reproduces 0.690055, a delta of -0.005729, inside the tolerance of 0.030.

## 2. Traditional Method

The strong non-ML comparator is a frozen train-run table. In each held-out fold, training events define quantile bins in pretrigger RMS, absolute slope, maximum excursion, adaptive lowering, amplitude, stave, and run-family/current group. A cell score is

$$\hat p_c = (n_{c,1} + \alpha)/(n_c + 2\alpha),\quad \alpha=0,$$

with fallback to stave by pretrigger-risk group and then to the global training prevalence when a cell has fewer than the configured minimum `traditional_min_cell_n=20` events. Its held-out AUC is 0.955 [0.951, 0.959], AP 0.971 [0.961, 0.980], and ECE 0.024 [0.015, 0.037].

No chi-square fit is used; the full run distribution is reported in `fold_metrics.csv` and visualized in `fig_run_stability_auc.png`.

## 3. ML and NN Methods

All ML/NN rows use the same held-out runs and exclude run id, event number, and post-trigger samples. Ridge/logistic, boosted trees, and MLP use pretrigger summaries plus stave; the 1D-CNN uses the four pretrigger samples; the hybrid residual CNN is the new architecture, combining the 1D pretrigger convolution with standardized residual/tabular pretrigger summaries and stave index. Each model is Platt-calibrated on training-run scores before scoring the held-out run.

Runtime caveat: the MLP and NN rows are lightweight probes with capped training rows/iterations; the MLP raised non-convergence warnings at the configured 10-iteration cap. They are included to test whether neural capacity obviously changes the conclusion, not as fully tuned production classifiers.

| method                               |      n |   mean_fold_auc |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |       ece |   ece_ci_low |   ece_ci_high |     brier |   brier_ci_low |   brier_ci_high |   mean_quiet_probability_shift |   timing_tail_odds_ratio_top_score |   charge_bias_delta_top_score |   run_auc_sd |
|:-------------------------------------|-------:|----------------:|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|----------:|-------------:|--------------:|----------:|---------------:|----------------:|-------------------------------:|-----------------------------------:|------------------------------:|-------------:|
| traditional_frozen_pretrigger_tables | 243133 |        0.955316 |  0.955316 |         0.951401 |          0.959479 |            0.970895 |                   0.960536 |                    0.980426 | 0.0244815 |    0.0151378 |     0.0366994 | 0.0452395 |      0.0329589 |       0.0601178 |                     -0.597717  |                          34.0572   |                      0.440176 |   0.00775093 |
| gradient_boosted_trees               | 243133 |        0.713385 |  0.713385 |         0.687109 |          0.741355 |            0.837061 |                   0.774068 |                    0.895618 | 0.122443  |    0.0900278 |     0.155787  | 0.158165  |      0.114023  |       0.204874  |                     -0.673779  |                           4.53962  |                      0.556184 |   0.0511715  |
| ridge_logistic                       | 243133 |        0.690055 |  0.690055 |         0.672278 |          0.709065 |            0.840865 |                   0.785674 |                    0.899361 | 0.13849   |    0.108712  |     0.169034  | 0.166614  |      0.119501  |       0.206267  |                     -0.577956  |                           3.78679  |                      0.499061 |   0.0368929  |
| mlp_tabular                          | 243133 |        0.626133 |  0.626133 |         0.589521 |          0.664722 |            0.793747 |                   0.725508 |                    0.859971 | 0.139922  |    0.109553  |     0.171692  | 0.169549  |      0.122432  |       0.21395   |                     -0.545981  |                           2.33055  |                      0.891909 |   0.0761675  |
| hybrid_residual_cnn                  | 243133 |        0.529577 |  0.529577 |         0.49545  |          0.557518 |            0.74135  |                   0.676564 |                    0.807185 | 0.153373  |    0.120539  |     0.182135  | 0.185045  |      0.142788  |       0.228554  |                     -0.254672  |                           0.946675 |                     -0.324195 |   0.0607599  |
| cnn1d_pretrigger                     | 243133 |        0.505282 |  0.505282 |         0.455006 |          0.562306 |            0.732321 |                   0.658936 |                    0.801223 | 0.159603  |    0.127836  |     0.190212  | 0.191555  |      0.149289  |       0.23242   |                     -0.0871603 |                           1.15412  |                     -1.36673  |   0.11128    |

Sentinel checks using only run family or only amplitude/stave are:

| sentinel                      |   roc_auc |   average_precision |
|:------------------------------|----------:|--------------------:|
| amplitude_stave_only_sentinel |  0.979285 |            0.988905 |
| run_family_only_sentinel      |  0.5      |            0.744566 |

## 4. Head-to-Head Benchmark

Winner by preregistered held-out ROC AUC is `traditional_frozen_pretrigger_tables` with AUC 0.955 [0.951, 0.959] and AP 0.971 [0.961, 0.980]. Compared with the traditional table, the AUC difference is +0.000. The result is not promoted as detector truth because all labels are derived from beam-trigger tail behavior rather than external forced/random pedestal truth.

## 5. Falsification

Pre-registration from the ticket: held-out AUC/AP, calibration ECE, mean quiet-probability shift, timing-tail odds ratio, charge-bias delta, and run-family bootstrap 95% CIs. A stability claim would be falsified if the best ML/NN row failed to beat the traditional comparator, if run-held-out CIs included chance performance, or if sentinels matched the best model. Here the amplitude/stave-only sentinel is at least as strong as the main winner, so the independence part of the hidden-mode claim is falsified even though the raw pretrigger AUC scale reproduces. Multiple models are reported without post-hoc pruning; the winner is descriptive and should be confirmed by a fresh ticket before use as a nuisance handle.

## 6. Threats to Validity

- **Benchmark/selection:** the traditional table is intentionally strong and includes run-family, stave, amplitude, and pretrigger strata; ML wins only if it exceeds this comparator on identical held-out rows.
- **Data leakage:** splits are by run; run id and event ids are excluded. Current/run-family appears only in the traditional table and sentinel, not the main ML feature set.
- **Metric misuse:** AUC/AP rank a proxy tail label. ECE/Brier check calibration, and charge residual plus timing-tail odds expose nuisance coupling beyond rank metrics.
- **Post-hoc selection:** all model families and the 20% tail-risk target are fixed in config before scoring.

## 7. Provenance Manifest

`manifest.json` lists input hashes, command, git commit, Python version, seeds, config, and output hashes.

## 8. Findings and Next Steps

The S16-family pretrigger AUC scale is reproduced from raw ROOT within tolerance. The best held-out row is `traditional_frozen_pretrigger_tables` with AUC 0.955, versus the traditional frozen table at 0.955. However, the amplitude/stave-only sentinel reaches AUC 0.979, so the hidden-mode stability claim is not independent of ordinary amplitude/stave composition. The signal should be treated as a nuisance proxy, not hidden physics truth, until an external target confirms it.

Hypothesis: the pretrigger signal is a real electronics/run-condition nuisance visible in raw pretrigger samples, but it is not an independent hidden physics mode. It should be used as a nuisance diagnostic only if future forced/random pedestal truth or an independently blinded tail label confirms comparable run/stave stability.

Proposed follow-up ticket: S16k: confirm S16j hidden-mode scores on independent forced/random or blinded pedestal truth

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.py --config configs/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `fold_metrics.csv`, `stability_by_run.csv`, `sentinel_metrics.csv`, `heldout_predictions_sample.csv`, and figures.
