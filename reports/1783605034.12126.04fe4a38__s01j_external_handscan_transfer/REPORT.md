# S01j q-template atom transfer to real external hand-scan

**Ticket:** `1783605034.12126.04fe4a38`  
**Worker:** `testbeam-laptop-1`  
**Date:** 2026-07-11

## Abstract

This study tests whether the q-template support atom that transferred in S01i's injected-truth panel also transfers to a small externally adjudicated real-waveform gallery. Raw ROOT reproduction is performed before loading the labels. The held-out unit is acquisition run, and uncertainty is a nonparametric run-block bootstrap over the hand-scan runs.

The benchmark winner is **mlp** with ROC AUC **0.9882** [0.9722, 0.9997] and AP **0.9719** [0.9326, 0.9990]. The strongest traditional comparator is **traditional_train_selected_score** with ROC AUC **0.9352** [0.9067, 0.9582].

## Raw ROOT Reproduction

| quantity                                         |   expected |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| selected B-stave pulses with amplitude >1000 ADC |     640737 |       640737 |       0 |           0 | True   |

The selected-pulse count is reproduced directly from `data/root/root/hrdb_run_*.root` by pedestal-subtracting HRDv even B-stave channels and applying the 1000 ADC amplitude threshold. The reproduced count is computed before the hand-scan table is opened.

## External Hand-Scan Target

The labelled target is `consensus_target_any` from `reports/1781011449.1304.37c054cc__p09b_manual_waveform_gallery_adjudication/adjudication_labels.csv`. Positive labels denote delayed peak or other hand-scan target morphology. The gallery contains only real raw waveforms selected by earlier P09 rankers; it is not synthetic injection truth and not independent beamline particle truth.

|   run |   n |   positives |   positive_fraction |   mean_q_template_rmse |   mean_late_fraction |
|------:|----:|------------:|--------------------:|-----------------------:|---------------------:|
|    42 |  64 |          12 |            0.1875   |               1.13453  |             0.161485 |
|    57 |  64 |          16 |            0.25     |               1.13871  |             0.195271 |
|    64 |  64 |          12 |            0.1875   |               0.882613 |             0.16009  |
|    65 |  64 |          21 |            0.328125 |               0.992475 |             0.214428 |

Let \(y_i \in \{0,1\}\) be the consensus target label for labelled waveform \(i\). The run-held-out score \(s_m(x_i)\) for method \(m\) is evaluated by ROC AUC

\[\mathrm{AUC}_m = P(s_m(x^+) > s_m(x^-)) + \tfrac{1}{2}P(s_m(x^+) = s_m(x^-)),\]

with confidence intervals from resampling labelled acquisition runs with replacement.

## Splitting and Leakage Controls

All methods use leave-one-run-out folds over the hand-scan runs. Run id, event id, event order, reviewer labels, consensus labels, and reviewer-derived measurements are excluded from learned features. The traditional score is selected using only non-held-out runs. Neural models see either the normalized 18-sample waveform alone or the waveform plus a small atom gate; neither receives the held-out labels during training.

For labelled rows \(i\) in held-out run \(r\), every trainable estimator is fit on \(\{j: r_j \ne r\}\) only. The reported predictions are therefore out-of-run scores for all 256 labelled rows. The bootstrap samples the four run blocks with replacement and recomputes AUC/AP on the concatenated sampled blocks; pulse-random intervals are intentionally not used because they would condition on the acquisition run.

## Methods

- **traditional_train_selected_score:** a transparent train-run-selected scorecard over P09/q-template/rubric-independent detector-quality scalars, with sign selected on training runs only.
- **ridge:** ridge linear classifier on scalar waveform, q-template, detector-quality, and one-hot method/stave/taxon inputs.
- **gradient_boosted_trees:** histogram gradient-boosted trees on the same tabular inputs.
- **mlp:** two-layer tabular neural network on the same inputs.
- **1d_cnn:** compact convolutional network on the normalized 18-sample waveform.
- **atom_gated_cnn_new:** the new architecture, a waveform CNN concatenated with q-template/late-peak/baseline/saturation atom gates.

The ridge objective is

\[\min_w \sum_i (y_i - w^T z_i)^2 + \alpha\lVert w\rVert_2^2,\]

where \(z_i\) is the fold-standardized tabular feature vector. The MLP and boosted-tree models use the same \(z_i\) and optimize held-out probability scores. The 1D-CNN maps normalized waveform samples \(x_i(t)\) through two convolutional layers and a global max-pool. The new architecture augments this latent waveform vector \(h_i\) with atom gates \(a_i=(q_{bad}, late, baseline, saturation, ...)\),

\[s_i = \sigma\{g([h_i, a_i])\},\]

so it directly tests whether q-template and neighbouring support atoms improve transfer beyond waveform shape alone.

## Head-to-Head Benchmark

| method                           | family           |   n |   positives |   roc_auc |   average_precision |   auc_ci_low |   auc_ci_high |   ap_ci_low |   ap_ci_high |
|:---------------------------------|:-----------------|----:|------------:|----------:|--------------------:|-------------:|--------------:|------------:|-------------:|
| mlp                              | nn               | 256 |          61 |  0.98823  |            0.971942 |     0.972249 |      0.999717 |    0.932641 |     0.998951 |
| gradient_boosted_trees           | ml               | 256 |          61 |  0.985876 |            0.964473 |     0.972249 |      0.9975   |    0.939371 |     0.99073  |
| ridge                            | ml               | 256 |          61 |  0.985288 |            0.963274 |     0.979988 |      0.994497 |    0.952798 |     0.983806 |
| atom_gated_cnn_new               | new_architecture | 256 |          61 |  0.98243  |            0.947518 |     0.964274 |      0.996429 |    0.895536 |     0.987094 |
| 1d_cnn                           | nn               | 256 |          61 |  0.944851 |            0.916615 |     0.897608 |      0.993929 |    0.84807  |     0.981091 |
| traditional_train_selected_score | traditional      | 256 |          61 |  0.935183 |            0.869312 |     0.906674 |      0.958214 |    0.842036 |     0.898346 |

## Per-Run Metrics

| method                           |   run |   n |   positives |   roc_auc |   average_precision |
|:---------------------------------|------:|----:|------------:|----------:|--------------------:|
| 1d_cnn                           |    42 |  64 |          12 |  0.995192 |            0.97907  |
| 1d_cnn                           |    57 |  64 |          16 |  0.992187 |            0.982955 |
| 1d_cnn                           |    64 |  64 |          12 |  0.873397 |            0.803593 |
| 1d_cnn                           |    65 |  64 |          21 |  0.922481 |            0.923953 |
| atom_gated_cnn_new               |    42 |  64 |          12 |  0.995192 |            0.97907  |
| atom_gated_cnn_new               |    57 |  64 |          16 |  0.997396 |            0.993056 |
| atom_gated_cnn_new               |    64 |  64 |          12 |  0.953526 |            0.869035 |
| atom_gated_cnn_new               |    65 |  64 |          21 |  0.986711 |            0.972588 |
| gradient_boosted_trees           |    42 |  64 |          12 |  0.995192 |            0.97907  |
| gradient_boosted_trees           |    57 |  64 |          16 |  0.998698 |            0.996324 |
| gradient_boosted_trees           |    64 |  64 |          12 |  0.969551 |            0.925926 |
| gradient_boosted_trees           |    65 |  64 |          21 |  0.972315 |            0.949032 |
| mlp                              |    42 |  64 |          12 |  1        |            1        |
| mlp                              |    57 |  64 |          16 |  1        |            1        |
| mlp                              |    64 |  64 |          12 |  0.963141 |            0.906486 |
| mlp                              |    65 |  64 |          21 |  0.982281 |            0.971815 |
| ridge                            |    42 |  64 |          12 |  0.99359  |            0.979167 |
| ridge                            |    57 |  64 |          16 |  0.998698 |            0.996324 |
| ridge                            |    64 |  64 |          12 |  0.983974 |            0.946789 |
| ridge                            |    65 |  64 |          21 |  0.984496 |            0.97404  |
| traditional_train_selected_score |    42 |  64 |          12 |  0.967949 |            0.907769 |
| traditional_train_selected_score |    57 |  64 |          16 |  0.953125 |            0.901448 |
| traditional_train_selected_score |    64 |  64 |          12 |  0.886218 |            0.829259 |
| traditional_train_selected_score |    65 |  64 |          21 |  0.939092 |            0.898015 |

## Traditional Fold Choices

|   heldout_run | traditional_choice    |
|--------------:|:----------------------|
|            42 | post_peak_min sign +1 |
|            57 | post_peak_min sign +1 |
|            64 | post_peak_min sign +1 |
|            65 | post_peak_min sign +1 |

## q-template Transfer Diagnostics

| contrast                              |     value |
|:--------------------------------------|----------:|
| target_rate_top_q_quartile_minus_rest | -0.276042 |
| target_rate_atom_gated_top_decile     |  1        |
| heldout_positive_fraction             |  0.238281 |

The first contrast is a direct descriptive q-template enrichment check. The second asks whether the atom-gated CNN's most confident decile is enriched in consensus positives. These diagnostics are not used to choose the winner; they are reported to separate classifier performance from the narrower q-template-transfer question.

## Systematics and Caveats

- The hand-scan set is small and deliberately enriched by previous traditional/ML rankers, so absolute rates do not estimate full-dataset prevalence.
- The target is autonomous hand-style morphology adjudication, not independent human review or particle truth.
- Because only four runs carry labels, run-block intervals are coarse; they are still preferable to pulse-level bootstrap intervals for acquisition-transfer claims.
- The `taxon` feature is a prior gallery source label and may encode selection-context information; the report therefore treats this as a transfer triage result rather than a deployable classifier.
- Strong performance by q-template or atom-gated methods supports detector-quality transfer, not injection realism by itself.

## Verdict

`result.json` names **mlp** as the winner. The q-template atom transfer is summarized as `handscan_support_transfer_seen`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s01j_1783605034_12126_04fe4a38_external_handscan_transfer.py --config configs/s01j_1783605034_12126_04fe4a38_external_handscan_transfer.yaml
```
