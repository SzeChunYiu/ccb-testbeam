# Ticket #2397 / P09: anomaly and glitch detection

- **Study ID:** P09
- **Ticket:** #2397, P09: Anomaly/glitch detection
- **Author worker:** testbeam-laptop-3
- **Date:** 2026-08-16
- **Depends on:** S00 raw selected-pulse gate; P09a rare waveform anomaly taxonomy; P09b curated waveform-gallery adjudication
- **Input checksum manifest:** `input_sha256.csv`
- **Git commit:** 1bea179d8e1aaf6679c3774c24256f780ed28675

## 0. Question

Does a learned waveform anomaly detector improve review-triage precision for rare/pathological B-stack pulses over a strong transparent outlier baseline, when all methods are evaluated on the same curated review rows and split by acquisition run?

The pre-registered primary endpoint is leave-one-run-out average precision for `consensus_curated_any` in the frozen P09b gallery.  Secondary endpoints are ROC AUC, top-25% flagged-set precision, top-50% flagged-set precision, Brier score, and run-block bootstrap 95% confidence intervals.

## 1. Reproduction from raw ROOT

The raw files are read from `/home/billy/ccb-data/data/extracted/root/root` for the configured S00/P09 run set `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 64, 58, 59, 60, 61, 62, 63, 65]`.  For every configured `hrdb_run_*.root`, branch `h101/HRDv` is reshaped to `(event, channel, sample)` with 18 samples.  The S00/P09 B-stack gate is

`b_ec = median(x_ec0, x_ec1, x_ec2, x_ec3)`

and

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`

for even B-stack channels B2, B4, B6, and B8.  This gate is run before loading review labels or training any model.

| quantity                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00/P09 B-stack selected pulses |         640737 |       640737 |       0 |           0 | True   |

The per-run counts are written to `reproduction_counts_by_run.csv`; their sum is 640737.

## 2. Review target and split

The benchmark target is the frozen P09b autonomous curated-gallery label `consensus_curated_any`.  It is a review-triage label, not particle truth and not an externally blinded human panel.  The table has 256 rows over runs 42, 57, 64, 65.  Every model is trained in leave-one-run-out folds: rows from the held-out run are absent from model fitting and calibration.

## 3. Methods

**Traditional baseline.** `traditional_shape_outlier` is the P09a robust-template outlier score.  It combines train-run amplitude/stave template residuals, peak sample, late fraction, baseline excursion, saturation count, duplicate-channel timing span, secondary peak, and undershoot.  It is intentionally transparent and is the adoption baseline.

**Ridge.** `ridge_logistic` is an L2-penalized logistic classifier on scalar waveform and frozen P09a score features, standardized inside each train fold and class-balanced.  It is the ridge-style linear comparator requested by the ticket.

**Gradient-boosted trees.** `gradient_boosted_trees` is a histogram gradient-boosted tree classifier with shallow leaves and L2 regularization.

**MLP.** `mlp` is a compact two-hidden-layer perceptron on the same scalar features.

**1D-CNN.** `one_dimensional_cnn` sees only the normalized 18-sample waveform and uses two one-dimensional convolution layers followed by global average pooling.

**New architecture.** `hybrid_review_fusion_new` is a stacked review-fusion model.  It combines the transparent anomaly scores, boosted-tree score, and CNN waveform evidence through a regularized ridge-logistic stacking head fit only inside each train fold.

For a method score `s_m(x_i)` and binary review target `y_i`, the average precision is

`AP_m = sum_n (R_n - R_(n-1)) P_n`

over the precision-recall staircase sorted by `s_m`.  The fixed-budget flagged precision is

`P_m(k) = (1/k) sum over i in Top_k(s_m) of y_i`.

Uncertainty intervals are percentile 95% intervals from 2000 bootstrap resamples of acquisition runs.  Run resampling keeps all rows within sampled runs together.

## 4. Head-to-head benchmark

| method                    |   average_precision |   ap_ci_low |   ap_ci_high |   roc_auc |   auc_ci_low |   auc_ci_high |   top25_precision |   top25_ci_low |   top25_ci_high |   brier |
|:--------------------------|--------------------:|------------:|-------------:|----------:|-------------:|--------------:|------------------:|---------------:|----------------:|--------:|
| ridge_logistic            |              0.9992 |      0.9985 |       0.9997 |    0.9748 |       0.9581 |        0.9893 |            1      |         1      |               1 | 0.05321 |
| mlp                       |              0.9989 |      0.9985 |       0.9998 |    0.9647 |       0.9559 |        0.9904 |            1      |         1      |               1 | 0.02681 |
| gradient_boosted_trees    |              0.9967 |      0.9907 |       1      |    0.9166 |       0.7702 |        1      |            1      |         1      |               1 | 0.01832 |
| traditional_shape_outlier |              0.9914 |      0.9856 |       0.9959 |    0.7686 |       0.6581 |        0.8673 |            1      |         1      |               1 | 0.03125 |
| hybrid_review_fusion_new  |              0.9911 |      0.9828 |       1      |    0.811  |       0.5827 |        0.998  |            1      |         1      |               1 | 0.1478  |
| one_dimensional_cnn       |              0.9816 |      0.9677 |       0.994  |    0.5892 |       0.4748 |        0.7578 |            0.9844 |         0.9531 |               1 | 0.2013  |

Winner by the pre-registered primary metric: **ridge_logistic**, with AP 0.9992 [0.9985, 0.9997].  The strong traditional baseline has AP 0.9914 [0.9856, 0.9959].  The winner-minus-traditional AP delta is 0.0078.

## 5. Run-held-out stability

| method                    |   run |   n |   positives |   roc_auc |   average_precision |   top25_precision |   top50_precision |     brier |
|:--------------------------|------:|----:|------------:|----------:|--------------------:|------------------:|------------------:|----------:|
| gradient_boosted_trees    |    42 |  64 |          61 |    1      |              1      |            1      |            1      | 0.006384  |
| gradient_boosted_trees    |    57 |  64 |          63 |    1      |              1      |            1      |            1      | 0.0002165 |
| gradient_boosted_trees    |    64 |  64 |          62 |    0.8387 |              0.9945 |            1      |            1      | 0.03096   |
| gradient_boosted_trees    |    65 |  64 |          62 |    0.7137 |              0.9868 |            1      |            0.9688 | 0.03572   |
| hybrid_review_fusion_new  |    42 |  64 |          61 |    1      |              1      |            1      |            1      | 0.06796   |
| hybrid_review_fusion_new  |    57 |  64 |          63 |    1      |              1      |            1      |            1      | 0.2128    |
| hybrid_review_fusion_new  |    64 |  64 |          62 |    0.5484 |              0.9816 |            1      |            1      | 0.07998   |
| hybrid_review_fusion_new  |    65 |  64 |          62 |    0.7097 |              0.9865 |            1      |            0.9688 | 0.2304    |
| mlp                       |    42 |  64 |          61 |    0.9891 |              0.9995 |            1      |            1      | 0.03817   |
| mlp                       |    57 |  64 |          63 |    1      |              1      |            1      |            1      | 0.01049   |
| mlp                       |    64 |  64 |          62 |    0.9758 |              0.9992 |            1      |            1      | 0.02335   |
| mlp                       |    65 |  64 |          62 |    0.9516 |              0.9984 |            1      |            1      | 0.03524   |
| one_dimensional_cnn       |    42 |  64 |          61 |    0.4863 |              0.9624 |            0.9375 |            0.9688 | 0.2057    |
| one_dimensional_cnn       |    57 |  64 |          63 |    0.9048 |              0.9985 |            1      |            1      | 0.1631    |
| one_dimensional_cnn       |    64 |  64 |          62 |    0.5081 |              0.9791 |            1      |            0.9688 | 0.199     |
| one_dimensional_cnn       |    65 |  64 |          62 |    0.4597 |              0.9762 |            1      |            0.9688 | 0.2375    |
| ridge_logistic            |    42 |  64 |          61 |    0.9727 |              0.9987 |            1      |            1      | 0.05938   |
| ridge_logistic            |    57 |  64 |          63 |    0.9841 |              0.9998 |            1      |            1      | 0.03901   |
| ridge_logistic            |    64 |  64 |          62 |    0.9919 |              0.9997 |            1      |            1      | 0.03923   |
| ridge_logistic            |    65 |  64 |          62 |    0.9516 |              0.9984 |            1      |            1      | 0.07522   |
| traditional_shape_outlier |    42 |  64 |          61 |    0.7978 |              0.9895 |            1      |            1      | 0.04688   |
| traditional_shape_outlier |    57 |  64 |          63 |    0.7302 |              0.9951 |            1      |            1      | 0.01562   |
| traditional_shape_outlier |    64 |  64 |          62 |    0.9113 |              0.997  |            1      |            1      | 0.03125   |
| traditional_shape_outlier |    65 |  64 |          62 |    0.6129 |              0.983  |            1      |            0.9688 | 0.03125   |

## 6. Feature and systematic diagnostics

The ridge permutation diagnostic on the full review table identifies which scalar summaries carry the curated-review target.  This is not used to tune the winner after evaluation; it is an interpretability diagnostic.

| feature                 |   ap_importance_mean |   ap_importance_std |
|:------------------------|---------------------:|--------------------:|
| late_fraction           |            0.001748  |           0.001303  |
| wf_late_frac            |            0.001748  |           0.001303  |
| post_peak_min           |            0.001555  |           0.002317  |
| wf_width50              |            0.001441  |           0.0009424 |
| traditional_score       |            0.0007187 |           0.0007451 |
| baseline_mad            |            0.0006515 |           0.0006969 |
| saturation_count        |            0.0005198 |           0.0006933 |
| timing_span_dup         |            0.0003607 |           0.0002391 |
| isolation_anomaly_score |            0.0002708 |           0.0001998 |
| wf_tail_min             |            0.0001844 |           0.000308  |
| wf_width35              |            9.87e-05  |           0.000137  |
| secondary_peak          |            6.979e-05 |           0.0001033 |
| wf_secondary_peak       |            6.979e-05 |           0.0001033 |
| ae_recon_mse            |            6.777e-05 |           5.999e-05 |
| pca_recon_mse           |            1.243e-05 |           2.771e-05 |

Systematic caveats:

- The curated label is a morphology review target, not beam-particle truth.
- The review table is small and enriched by P09a ranking; absolute population prevalence cannot be inferred from the gallery.
- Leave-one-run-out protects against direct same-run leakage, but the four-run gallery gives wide run-block intervals.
- The hybrid stack is more complex than the traditional baseline; its adoption is justified only for triage ranking, not autonomous veto decisions.
- ROOT reproduction uses the B-stack selected-pulse count as the raw-data anchor; the review benchmark reuses frozen P09b gallery labels because no new manual review panel was run in this session.

## 7. Falsification

The falsification test was fixed before model ranking: an ML/NN method is not promoted unless its average precision exceeds the traditional baseline and its run-bootstrap interval is not obviously compatible with a large loss against the baseline.  A leakage alarm would be raised if any train/test run overlap appears, if identifier columns enter the feature matrix, or if a method reaches exactly perfect AP/AUC on every held-out run.

The observed train/test run overlap is zero by construction.  Identifier columns (`run`, event ids, stave, labels, waveform string) are excluded from scalar feature matrices.  No method has perfect by-run AP/AUC across all runs; the result is therefore not rejected by the predeclared leakage guard.

## 8. Provenance manifest

Machine-readable provenance is in `manifest.json`; the headline winner and all CIs are in `result.json`.  Input hashes are in `input_sha256.csv`.  Commands:

`uv run --with numpy --with pandas --with scikit-learn --with uproot --with torch --with tabulate python scripts/ticket_2397_p09_anomaly_glitch_detection.py`

## 9. Findings and next steps

The benchmark supports **ridge_logistic** as the best available review-triage ranker for the current curated gallery.  It beats the transparent baseline on AP while preserving run-held-out evaluation.  The result should be treated as a triage result: it can prioritize waveform examples for review, but it should not be used as a physics veto without an independently sampled review set.

No new follow-up ticket is appended by this worker.  The highest-value next measurement is already represented by the existing P09 follow-up family: obtain an independently sampled, event-keyed manual review panel so flagged-set precision can be measured without enrichment from the original P09a selectors.

## 10. Output artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_counts_by_run.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_run_metrics.csv`, `method_bootstrap_ci.csv`, `heldout_predictions.csv`, and `feature_importance.csv`.
