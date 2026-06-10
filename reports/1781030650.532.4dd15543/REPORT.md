# S10l: asymmetric-template failure atom map

- **Ticket:** `1781030650.532.4dd15543`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT files under `data/root/root`
- **Split:** train source runs `[58, 59, 60, 61, 62]`; held-out source runs `[63, 65]`
- **Primary metric:** held-out constituent time RMS on injected positive two-pulse events, with held-out-source-run bootstrap 95% CIs.
- **Winner:** `hist_gradient_boosted_trees` with time RMS `7.27` ns.

## 0. Question

When the S10f amplitude-binned/asymmetric traditional two-pulse fit does not push the operational resolvable delay below about 60 ns, which atomic axes explain the failure: amplitude ratio, pulse separation, saturation boundary, baseline excursion, peak-sample phase, or residual tail shape? The preregistered comparison is a strong asymmetric template fit versus ridge, gradient-boosted trees, MLP, 1D-CNN, and a new attention waveform encoder on identical held-out source runs.

## 1. Reproduction gate

The raw ROOT selected-pulse count gate passed exactly.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S10 injection ML AP handle was independently rerun from raw ROOT.

| quantity                      |   report_value |   reproduced |        delta |   tolerance | pass   |   best_C |      auc |     brier |
|:------------------------------|---------------:|-------------:|-------------:|------------:|:-------|---------:|---------:|----------:|
| S10 low_2nA injection ML AP   |          0.982 |     0.981989 | -1.12387e-05 |       0.006 | True   |       10 | 0.986246 | 0.0345569 |
| S10 high_20nA injection ML AP |          0.968 |     0.971862 |  0.00386215  |       0.006 | True   |       10 | 0.965324 | 0.0658963 |

The S10f failure statement reproduced: under the stricter S10l per-event good-recovery diagnostic, the traditional asymmetric template fit still does not establish a stable sub-60 ns recovery. This is the failure S10l decomposes.

| quantity                                                |   report_value |   reproduced |   delta |   tolerance | pass   |   diagnostic_delay_ns |   boundary_ns |
|:--------------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|----------------------:|--------------:|
| S10f traditional sub-60 ns stable-recovery failure flag |              1 |            1 |       0 |           0 | True   |                   nan |            60 |

## 2. Traditional method

The traditional baseline is the S10f/S11c amplitude-binned asymmetric empirical-template fit. For stave \(s\), amplitude bin \(a\), and tail class \(h\), a train-run-only normalized template is

\[
T_{sah}(j) = \operatorname{median}_k \left[ \frac{w_k(j + \hat t_k - t_0)}{\max_j w_k(j)} \right],
\]

where \(\hat t_k\) is CFD20 phase and \(t_0=5\) samples. The two-pulse model is

\[
y(j)=A_1 T_p(j-t_1)+A_2 T_q(j-t_1-\Delta)+b+\epsilon_j,
\]

with \(p,q\) selected from nearby amplitude/tail templates, \(\Delta\) scanned over the configured separation grid, and \((A_1,A_2,b)\) solved by constrained least squares. A recovery is labeled bad when the fit fails, max constituent timing error exceeds 10.0 ns, or total-charge bias exceeds 0.20.

## 3. ML and NN methods

All ML/NN models use only waveform-derived features and stave one-hot labels; source run and event id are excluded. Ridge uses logistic regression with L2 penalty plus ridge regression. Gradient-boosted trees use histogram gradient boosting. MLP uses one hidden classifier and a two-layer regressor. The 1D-CNN is a small convolutional multi-task network. The new architecture is a gated attention encoder over the 18 samples, sharing a classifier and four regression heads. Regression targets are \(t_1/12, t_2/12, A_1/A_{max}, A_2/A_{max}\); regression loss is applied to positive injected events.

## 4. Head-to-head benchmark

| Method | family | AP | time RMS ns, 95% CI | charge res68, 95% CI | charge bias | failure rate |
|---|---|---:|---:|---:|---:|---:|
| amplitude_binned_asymmetric_template_fit | traditional | 0.701 | 17.52 [17.31, 17.74] | 0.116 [0.114, 0.117] | -0.001 | 0.020 |
| ridge_logistic_plus_ridge_regression | ml | 0.835 | 8.55 [8.48, 8.62] | 0.072 [0.069, 0.074] | -0.017 | 0.308 |
| hist_gradient_boosted_trees | ml | 0.884 | 7.27 [6.86, 7.64] | 0.061 [0.055, 0.067] | -0.010 | 0.273 |
| compact_mlp_classifier_regressor | ml | 0.842 | 9.10 [9.05, 9.15] | 0.073 [0.067, 0.077] | -0.002 | 0.322 |
| one_dimensional_cnn | nn | 0.788 | 10.86 [10.69, 11.01] | 0.079 [0.074, 0.085] | -0.042 | 0.418 |
| attention_waveform_encoder | new_architecture | 0.810 | 11.34 [11.33, 11.35] | 0.089 [0.084, 0.090] | -0.047 | 0.293 |

The winner by the preregistered primary metric is **hist_gradient_boosted_trees**. The bootstrap unit is held-out source run, so the CIs include run-to-run movement but remain limited by having only two held-out runs.

## 5. Failure atom map

| Axis | Level | n | traditional failure rate, 95% CI | bad-recovery odds ratio, 95% CI | time RMS ns | charge res68 |
|---|---|---:|---:|---:|---:|---:|
| amplitude_ratio | 0.25 | 150 | 0.800 [0.747, 0.853] | 2.20 [1.65, 3.16] | 21.38 | 0.164 |
| separation_ns | 20 | 74 | 0.797 [0.656, 0.905] | 1.93 [0.94, 4.59] | 16.70 | 0.107 |
| residual_tail_shape | slow_tail | 154 | 0.773 [0.756, 0.792] | 1.81 [1.78, 1.88] | 20.32 | 0.168 |
| baseline_excursion | 50-80 | 98 | 0.765 [0.760, 0.771] | 1.62 [1.44, 1.81] | 18.76 | 0.129 |
| saturation_boundary | below_saturation_proxy | 558 | 0.686 [0.669, 0.703] | 1.36 [1.15, 1.67] | 17.57 | 0.120 |
| peak_sample_phase | edge | 401 | 0.698 [0.692, 0.705] | 1.26 [1.13, 1.40] | 16.46 | 0.131 |
| peak_sample_phase | nominal | 26 | 0.731 [0.667, 0.786] | 1.23 [0.97, 1.54] | 23.34 | 0.128 |
| separation_ns | 30-40 | 130 | 0.715 [0.662, 0.774] | 1.22 [0.81, 1.92] | 15.25 | 0.112 |
| baseline_excursion | ge80 | 75 | 0.720 [0.639, 0.795] | 1.22 [0.86, 1.77] | 18.71 | 0.181 |
| amplitude_ratio | 0.50 | 142 | 0.711 [0.701, 0.720] | 1.19 [1.16, 1.22] | 18.09 | 0.113 |

The strongest atoms are high-odds strata, not causal proof. They localize where the traditional model loses recoverability and motivate targeted controls.

## 6. Risk-coverage

Risk-coverage AUC is the area under good-recovery fraction versus retained coverage after sorting by each method's confidence score. It is reported on held-out positives only.

| Method | risk-coverage AUC, 95% CI | ML-minus-traditional |
|---|---:|---:|
| amplitude_binned_asymmetric_template_fit | 0.404 [0.365, 0.442] | +0.000 |
| ridge_logistic_plus_ridge_regression | 0.632 [0.600, 0.663] | +0.228 |
| hist_gradient_boosted_trees | 0.778 [0.770, 0.788] | +0.375 |
| compact_mlp_classifier_regressor | 0.648 [0.647, 0.648] | +0.244 |
| one_dimensional_cnn | 0.333 [0.333, 0.334] | -0.071 |
| attention_waveform_encoder | 0.371 [0.365, 0.380] | -0.033 |

## 7. Held-out run split

| Run | Method | AP | time RMS ns | charge res68 | failure rate |
|---:|---|---:|---:|---:|---:|
| 63 | amplitude_binned_asymmetric_template_fit | 0.710 | 17.31 | 0.117 | 0.027 |
| 63 | ridge_logistic_plus_ridge_regression | 0.816 | 8.62 | 0.074 | 0.307 |
| 63 | hist_gradient_boosted_trees | 0.887 | 6.86 | 0.067 | 0.283 |
| 63 | compact_mlp_classifier_regressor | 0.824 | 9.05 | 0.077 | 0.313 |
| 63 | one_dimensional_cnn | 0.777 | 11.01 | 0.083 | 0.407 |
| 63 | attention_waveform_encoder | 0.795 | 11.33 | 0.090 | 0.290 |
| 65 | amplitude_binned_asymmetric_template_fit | 0.695 | 17.74 | 0.114 | 0.013 |
| 65 | ridge_logistic_plus_ridge_regression | 0.854 | 8.48 | 0.069 | 0.310 |
| 65 | hist_gradient_boosted_trees | 0.882 | 7.64 | 0.055 | 0.263 |
| 65 | compact_mlp_classifier_regressor | 0.863 | 9.15 | 0.067 | 0.330 |
| 65 | one_dimensional_cnn | 0.796 | 10.69 | 0.074 | 0.430 |
| 65 | attention_waveform_encoder | 0.822 | 11.35 | 0.083 | 0.297 |

## 8. Falsification and leakage checks

The falsification criterion was fixed before reading the result: if the traditional asymmetric template fit won the held-out time-RMS benchmark, the claimed need for ML/NN recovery would be rejected; if any leakage sentinel fired, the benchmark would be treated as invalid. Leakage flags observed: **0**.

| check                                                                   |     value | pass   |
|:------------------------------------------------------------------------|----------:|:-------|
| train_heldout_source_run_overlap                                        |  0        | True   |
| event_id_overlap                                                        |  0        | True   |
| amplitude_binned_asymmetric_template_fit_too_good_time_rms_lt_3ns       | 17.5247   | True   |
| amplitude_binned_asymmetric_template_fit_too_good_detection_ap_gt_0p995 |  0.701093 | True   |
| ridge_logistic_plus_ridge_regression_too_good_time_rms_lt_3ns           |  8.55046  | True   |
| ridge_logistic_plus_ridge_regression_too_good_detection_ap_gt_0p995     |  0.835357 | True   |
| hist_gradient_boosted_trees_too_good_time_rms_lt_3ns                    |  7.26719  | True   |
| hist_gradient_boosted_trees_too_good_detection_ap_gt_0p995              |  0.8841   | True   |
| compact_mlp_classifier_regressor_too_good_time_rms_lt_3ns               |  9.10109  | True   |
| compact_mlp_classifier_regressor_too_good_detection_ap_gt_0p995         |  0.842111 | True   |
| one_dimensional_cnn_too_good_time_rms_lt_3ns                            | 10.8583   | True   |
| one_dimensional_cnn_too_good_detection_ap_gt_0p995                      |  0.787786 | True   |
| attention_waveform_encoder_too_good_time_rms_lt_3ns                     | 11.3382   | True   |
| attention_waveform_encoder_too_good_detection_ap_gt_0p995               |  0.809682 | True   |
| mean_train_run_cv_ap_finite                                             |  0.864983 | True   |

## 9. Systematics and caveats

The benchmark is data-driven but synthetic: empirical templates and real residuals come from raw ROOT, while the second pulse is injected. This isolates recovery mechanics but may understate real high-current pathologies such as unresolved electronics saturation, trigger coupling, and pile-up topologies not represented by the injection generator. The saturation boundary is a proxy based on total injected amplitude, not a digitizer truth flag. The attention encoder is included as an architectural stress test, not as a production model. With only runs 63 and 65 held out, run-bootstrap CIs are honest but coarse.

## 10. Provenance

Artifacts are machine-readable in `result.json`, `manifest.json`, `head_to_head_overall.csv`, `failure_atom_map.csv`, `risk_coverage.csv`, `heldout_by_run.csv`, and `injected_events_with_predictions.csv`. Input checksums are in `input_sha256.csv`; output checksums are in `manifest.json`.

Reproduce with:

```bash
/home/billy/anaconda3/bin/python scripts/s10l_1781030650_532_4dd15543_failure_atom_map.py --config configs/s10l_1781030650_532_4dd15543_failure_atom_map.json
```

Runtime for this run: 228.92 s.
