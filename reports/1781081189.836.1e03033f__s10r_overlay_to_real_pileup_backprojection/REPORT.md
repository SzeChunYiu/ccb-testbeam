# S10r: Overlay-to-real pileup backprojection

- **Ticket:** `1781081189.836.1e03033f`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** `data/root/root`
- **Output:** `reports/1781081189.836.1e03033f__s10r_overlay_to_real_pileup_backprojection`
- **Winner:** `random_filter_1d_cnn`

## Abstract

This study asks whether overlay-trained two-pulse scores backproject onto measured high-current pulse atoms rather than merely ranking methods on synthetic overlays. The analysis first reproduces the raw selected-pulse number from ROOT, then builds a source-run split overlay benchmark and compares a strong traditional template-fit score with ridge, gradient-boosted trees, dense MLP, 1D convolutional random-filter features, and a hybrid template-residual stack. The trained scores are then applied to real high-current runs and matched low-current control runs.

## Raw ROOT Reproduction

The raw gate passed exactly: `640737` selected B-stave pulses versus `640737` registered pulses. The sample-II B-stave counts are reproduced in `reproduction_match_table.csv`.

## Methods

Let \(x_i \in \mathbb{R}^{18}\) be a baseline-subtracted B-stave waveform. The traditional score is

\[
s_{fit}(x)=\frac{\mathrm{SSE}_1(x)-\mathrm{SSE}_2(x)}{\max(\mathrm{SSE}_1(x),1)} ,
\]

where the one-pulse and two-pulse hypotheses are bounded least-squares template fits over the configured delay and amplitude-ratio grids. The ridge model is a linear classifier on normalized waveform and summary features. The boosted-tree model uses histogram gradient boosting on the same feature vector. The MLP is a dense neural classifier. The 1D-CNN surrogate applies fixed random zero-mean convolutional filters to the waveform and trains an MLP on max/mean/std pooled filter responses. The hybrid architecture appends the traditional fit probability to those convolutional features and trains a gradient-boosted stacker.

Training runs were `[58, 59, 60, 61, 62]`; held-out overlay runs were `[63, 65]`. Bootstrap CIs resample source runs, then events within sampled runs. Real backprojection compares high-current runs `[63, 65]` against low-current controls `[44, 45, 46, 47, 48]` with thresholds selected on train overlays by F1.

## Overlay Benchmark

| Method | AP | AP 95% CI | ROC AUC | AUC 95% CI | Brier |
|---|---:|---:|---:|---:|---:|
| gradient_boosted_trees | 0.862 | [0.836, 0.888] | 0.841 | [0.817, 0.865] | 0.164 |
| random_filter_1d_cnn | 0.854 | [0.823, 0.877] | 0.820 | [0.787, 0.846] | 0.171 |
| hybrid_template_residual_stack | 0.846 | [0.805, 0.878] | 0.827 | [0.792, 0.858] | 0.170 |
| ridge_linear_classifier | 0.829 | [0.799, 0.863] | 0.814 | [0.782, 0.843] | 0.195 |
| mlp_dense_waveform | 0.818 | [0.785, 0.853] | 0.807 | [0.776, 0.834] | 0.181 |
| traditional_template_delta_sse | 0.770 | [0.738, 0.804] | 0.725 | [0.693, 0.760] | 0.437 |

## Held-Out Run Split

| Run | Method | AP | ROC AUC | score gap |
|---:|---|---:|---:|---:|
| 63 | traditional_template_delta_sse | 0.772 | 0.734 | 0.141 |
| 63 | ridge_linear_classifier | 0.821 | 0.804 | 0.148 |
| 63 | gradient_boosted_trees | 0.866 | 0.843 | 0.397 |
| 63 | mlp_dense_waveform | 0.823 | 0.807 | 0.275 |
| 63 | random_filter_1d_cnn | 0.862 | 0.830 | 0.350 |
| 63 | hybrid_template_residual_stack | 0.861 | 0.840 | 0.329 |
| 65 | traditional_template_delta_sse | 0.768 | 0.715 | 0.109 |
| 65 | ridge_linear_classifier | 0.839 | 0.823 | 0.150 |
| 65 | gradient_boosted_trees | 0.859 | 0.839 | 0.392 |
| 65 | mlp_dense_waveform | 0.815 | 0.807 | 0.270 |
| 65 | random_filter_1d_cnn | 0.845 | 0.811 | 0.325 |
| 65 | hybrid_template_residual_stack | 0.832 | 0.816 | 0.309 |

## Real Backprojection

| Method | high-minus-low candidate rate | 95% CI | support Jaccard | 95% CI | high candidate rate |
|---|---:|---:|---:|---:|---:|
| traditional_template_delta_sse | 0.029 | [-0.011, 0.066] | 0.882 | [0.000, 0.903] | 0.938 |
| ridge_linear_classifier | -0.164 | [-0.258, -0.092] | 0.857 | [0.000, 0.889] | 0.309 |
| gradient_boosted_trees | -0.137 | [-0.211, -0.094] | 0.609 | [0.000, 0.684] | 0.115 |
| mlp_dense_waveform | -0.142 | [-0.216, -0.089] | 0.727 | [0.000, 0.842] | 0.333 |
| random_filter_1d_cnn | -0.030 | [-0.086, 0.008] | 0.667 | [0.000, 0.800] | 0.121 |
| hybrid_template_residual_stack | -0.083 | [-0.149, -0.045] | 0.750 | [0.000, 0.769] | 0.101 |

The winner is `random_filter_1d_cnn` under the preregistered joint ranking criterion: held-out overlay AP plus 0.25 times the real high-minus-low candidate-rate delta. Its real delta is near zero with a confidence interval crossing zero, so this is a conservative overlay-ranking result with partial real support, not evidence for a calibrated positive physics rate.

## Systematics and Caveats

Dominant systematics are overlay realism, threshold selection, current-dependent baseline excursions, saturation-adjacent pulse shapes, and the fact that real high-current candidates have no direct pulse-overlap truth label. The run bootstrap only covers between-run fluctuations for the configured runs; it does not cover unobserved detector states. The fixed-filter 1D-CNN is deliberately lightweight and should be interpreted as a convolutional feature neural baseline, not a fully optimized deep CNN. Backprojection support is summarized by amplitude bin, peak phase, and stave; finer topology could lower the Jaccard values.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s10r_1781081189_836_1e03033f_overlay_to_real_backprojection.py --config configs/s10r_1781081189_836_1e03033f_overlay_to_real_backprojection.json
```

Runtime was `229.79` s. Detailed outputs include `overlay_model_metrics.csv`, `overlay_model_metrics_by_run.csv`, `real_backprojection_metrics.csv`, `real_backprojection_bootstrap_ci.csv`, `stress_event_table.csv`, `real_event_scores.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.
