# P12f Externalized Frozen Harm-Ledger Policy Validation

- **Ticket:** `1781191863.1669.616c1405`
- **Worker:** `testbeam-laptop-4`
- **Frozen policy source:** `reports/1781062454.713.242b3d71__p12e_cross_consumer_pulse_atom_harm_ledger/heldout_consumer_predictions.csv.gz`
- **Support/raw-count source:** `reports/1781145765.1768.59211878__p12d_frozen_action_matrix_consumer_calibration`
- **P12e artifact present:** `True`.
- **Fixed acceptance coverage:** `0.9`.
- **Raw ROOT source:** `/home/billy/ccb-data/extracted/root/root`
- **Raw reproduction:** `640737` selected B-stave pulses versus expected `640737`; pass = `True`.
- **Held-out run blocks:** `58, 59, 60, 61, 62, 63, 65`.

## Scientific Question

The study tests whether a frozen P12 harm-ledger accept/reject policy remains useful when evaluated on externalized consumer evidence rather than on the same internal charge/timing atoms that produced the policy.  The external consumers are P04 downstream charge closure, S02 external atom handoff tail rejection, and S03 external shape-constrained timing closure.  The null is that the frozen policy ordering is no better than a run-shuffled association between policy quality and downstream consumer evidence.

## Methods

Let `m` index a frozen method and `r` a held-out run.  The P12e prediction table supplies a harm score for every selected consumer pulse.  At fixed acceptance coverage `q=0.9`, the policy accepts the `q` fraction with the lowest predicted harm and rejects the remainder.  The P12e policy loss is `L_{mr} = H^acc_{mr} + (1 - G^rej_{mr})`, where `H^acc_{mr}` is the accepted-pulse mean consumer harm and `G^rej_{mr}` is the fraction of total consumer harm captured by the rejected tail.  External evidence supplies P04 fractional charge width `C_{mr}`, P04 catastrophic bias rate `K_{mr}`, S02 tail-label Brier score `B_{mr}`, S02 fixed-clean tail rejection `T_{mr}`, S03 timing width `S_{mr}`, and S03 >5 ns tail fraction `U_{mr}`.  Lower is better except for `T_{mr}`; the validation score is

`V_{mr} = L_{mr} + C_{mr} + K_{mr} + B_{mr} + (1 - T_{mr}) + 0.25 S_{mr} + U_{mr}`.

The factor 0.25 keeps the nanosecond timing width on the same rough numerical scale as the fractional charge and probability losses without erasing the physical units in component tables.  The run-block estimate is `bar V_m = |R|^-1 sum_r V_{mr}`.  Bootstrap confidence intervals resample the complete run labels `r` with replacement.  Shuffled-policy sentinels keep each method's P12e fixed-coverage score fixed but randomly permute method labels for the external consumer components within each run before recomputing `bar V_m`.

The benchmark panel is the frozen P12e prediction panel: a strong traditional atom-action rule, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new action-prior residual CNN architecture.  No method is refit in P12f.

## Benchmark Summary

| method | family | n_runs | external_validation_score | external_validation_score_ci95 | p12_primary_score_mean | p04_res68_abs_frac_mean | s02_brier_mean | s03_sigma68_ns_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | ml | 7 | 1.792 | [1.665, 1.916] | 0.7634 | 0.2291 | 0.0434 | 1.777 |
| ridge | ml | 7 | 1.865 | [1.662, 2.06] | 0.7881 | 0.2192 | 0.05388 | 1.86 |
| action_prior_residual_cnn_new_arch | new_architecture | 7 | 2.187 | [1.965, 2.474] | 0.8296 | 0.2236 | 0.1537 | 1.776 |
| 1d_cnn | nn | 7 | 2.358 | [2.16, 2.609] | 1.015 | 0.2235 | 0.1484 | 1.76 |
| mlp | nn | 7 | 2.869 | [2.791, 2.946] | 0.7537 | 0.3709 | 0.06185 | 2.001 |
| traditional_frozen_harm_ledger | traditional | 7 | 3.244 | [3.172, 3.306] | 0.7659 | 0.2522 | 0.754 | 1.741 |

## Per-Run Externalized Evidence

| run | method | p12_primary_score | p04_res68_abs_frac | p04_catastrophic_rate | s02_brier | s02_tail_rejection | s03_sigma68_ns | external_validation_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | 1d_cnn | 0.9028 | 0.2341 | 0.2361 | 0.0719 | 0.8571 | 1.465 | 1.998 |
| 58 | action_prior_residual_cnn_new_arch | 0.5237 | 0.2377 | 0.2917 | 0.1369 | 0.6714 | 1.224 | 1.854 |
| 58 | gradient_boosted_trees | 0.4544 | 0.2659 | 0.3472 | 0.02501 | 1 | 1.454 | 1.514 |
| 58 | mlp | 0.4461 | 0.371 | 0.4861 | 0.03696 | 0.4 | 2.571 | 2.684 |
| 58 | ridge | 0.4721 | 0.2274 | 0.3056 | 0.02685 | 0.9857 | 1.712 | 1.503 |
| 58 | traditional_frozen_harm_ledger | 0.4507 | 0.3211 | 0.4167 | 0.7813 | 0.2857 | 1.313 | 3.056 |
| 59 | 1d_cnn | 1.068 | 0.2333 | 0.2777 | 0.1825 | 0.9311 | 1.916 | 2.364 |
| 59 | action_prior_residual_cnn_new_arch | 0.9291 | 0.238 | 0.2977 | 0.1301 | 0.938 | 1.846 | 2.164 |
| 59 | gradient_boosted_trees | 0.8701 | 0.225 | 0.271 | 0.02835 | 1 | 1.703 | 1.866 |
| 59 | mlp | 0.8587 | 0.3867 | 0.4579 | 0.0511 | 0.3375 | 2.105 | 2.993 |
| 59 | ridge | 0.8936 | 0.2357 | 0.3017 | 0.04965 | 0.9656 | 1.936 | 2.049 |
| 59 | traditional_frozen_harm_ledger | 0.877 | 0.2346 | 0.2884 | 0.7544 | 0.3306 | 1.939 | 3.359 |
| 60 | 1d_cnn | 1.103 | 0.2171 | 0.2207 | 0.1364 | 0.6839 | 1.696 | 2.462 |
| 60 | action_prior_residual_cnn_new_arch | 0.9663 | 0.2115 | 0.217 | 0.1973 | 0.7045 | 1.799 | 2.394 |
| 60 | gradient_boosted_trees | 0.912 | 0.219 | 0.217 | 0.03135 | 0.9987 | 1.742 | 1.873 |
| 60 | mlp | 0.9026 | 0.3862 | 0.5461 | 0.05121 | 0.3587 | 1.766 | 3.008 |
| 60 | ridge | 0.9268 | 0.2207 | 0.2394 | 0.06003 | 0.9484 | 1.9 | 2.022 |
| 60 | traditional_frozen_harm_ledger | 0.9128 | 0.2454 | 0.3105 | 0.7293 | 0.3742 | 1.629 | 3.275 |
| 61 | 1d_cnn | 1.076 | 0.2006 | 0.2022 | 0.2817 | 0.4526 | 2.591 | 3.016 |
| 61 | action_prior_residual_cnn_new_arch | 0.9376 | 0.1931 | 0.1957 | 0.3091 | 0.4039 | 2.646 | 2.947 |
| 61 | gradient_boosted_trees | 0.879 | 0.1987 | 0.1968 | 0.1356 | 1 | 2.55 | 2.091 |
| 61 | mlp | 0.8691 | 0.3237 | 0.4465 | 0.1526 | 0.4711 | 2.17 | 2.89 |
| 61 | ridge | 0.8999 | 0.1975 | 0.2076 | 0.1198 | 0.9026 | 2.682 | 2.247 |
| 61 | traditional_frozen_harm_ledger | 0.8815 | 0.2126 | 0.2324 | 0.6187 | 0.3632 | 2.629 | 3.304 |
| 62 | 1d_cnn | 1.079 | 0.1945 | 0.1992 | 0.1812 | 0.7321 | 1.728 | 2.383 |
| 62 | action_prior_residual_cnn_new_arch | 0.9337 | 0.1974 | 0.1955 | 0.07811 | 0.9158 | 1.76 | 1.958 |
| 62 | gradient_boosted_trees | 0.8786 | 0.201 | 0.208 | 0.01919 | 1 | 1.636 | 1.742 |
| 62 | mlp | 0.8677 | 0.3316 | 0.4499 | 0.04457 | 0.2283 | 1.58 | 2.894 |
| 62 | ridge | 0.8959 | 0.1949 | 0.2193 | 0.04438 | 0.9796 | 1.746 | 1.845 |
| 62 | traditional_frozen_harm_ledger | 0.8817 | 0.2109 | 0.2105 | 0.7621 | 0.3457 | 1.72 | 3.183 |
| 63 | 1d_cnn | 0.9841 | 0.2275 | 0.2877 | 0.08446 | 0.9446 | 1.766 | 2.134 |
| 63 | action_prior_residual_cnn_new_arch | 0.82 | 0.2247 | 0.2849 | 0.07116 | 0.9197 | 1.848 | 1.974 |
| 63 | gradient_boosted_trees | 0.748 | 0.2282 | 0.2932 | 0.02135 | 1 | 1.878 | 1.783 |
| 63 | mlp | 0.7396 | 0.4102 | 0.5315 | 0.02813 | 0.3213 | 1.65 | 2.831 |
| 63 | ridge | 0.7885 | 0.2321 | 0.2904 | 0.04435 | 0.9723 | 1.842 | 1.889 |
| 63 | traditional_frozen_harm_ledger | 0.7551 | 0.2251 | 0.2986 | 0.7889 | 0.338 | 1.812 | 3.236 |
| 65 | 1d_cnn | 0.893 | 0.2576 | 0.3492 | 0.1005 | 0.7377 | 1.157 | 2.152 |
| 65 | action_prior_residual_cnn_new_arch | 0.6969 | 0.2631 | 0.381 | 0.1531 | 0.8033 | 1.31 | 2.018 |
| 65 | gradient_boosted_trees | 0.6019 | 0.2662 | 0.3968 | 0.04302 | 1 | 1.473 | 1.676 |
| 65 | mlp | 0.592 | 0.3867 | 0.5397 | 0.06834 | 0.3443 | 2.162 | 2.783 |
| 65 | ridge | 0.6399 | 0.226 | 0.2857 | 0.03213 | 0.9836 | 1.206 | 1.502 |
| 65 | traditional_frozen_harm_ledger | 0.6025 | 0.316 | 0.4444 | 0.8437 | 0.1967 | 1.142 | 3.295 |

## Shuffled-Policy Sentinels

| method | shuffled_mean | shuffled_ci95 | real_minus_shuffled |
| --- | --- | --- | --- |
| gradient_boosted_trees | 2.327 | [1.947, 2.745] | -0.5348 |
| ridge | 2.355 | [1.968, 2.784] | -0.4898 |
| 1d_cnn | 2.579 | [2.213, 2.996] | -0.2204 |
| action_prior_residual_cnn_new_arch | 2.398 | [2.029, 2.824] | -0.2106 |
| mlp | 2.318 | [1.936, 2.749] | 0.5516 |
| traditional_frozen_harm_ledger | 2.329 | [1.93, 2.772] | 0.9153 |

## Systematics and Caveats

- The P12e artifact has pulse-level frozen predictions but no standalone `result.json`, `method_metrics.csv`, or raw-count ledger; P12f therefore uses P12e for the fixed-coverage policy scores and the P12d support bundle only for raw ROOT reproduction and predecessor metadata.
- The validation is artifact-level and run-blocked.  It reconstructs the fixed-coverage P12e accept/reject decision from pulse predictions, but it cannot join P04/S02/S03 row-level consumers because those files expose different row populations and summary granularities.
- P04, S02, and S03 measure different physical losses.  The composite score is an operational decision metric; component tables should be inspected before promoting any single physics claim.
- The external artifacts were produced by prior tickets with their own modeling choices.  P12f treats them as frozen consumer evidence and does not tune their thresholds or refit their models.
- Missing external entries are not silently used for ranking; all six benchmark methods have seven run blocks after method-name harmonization.

## Conclusion

The winner is `gradient_boosted_trees` with external validation score `1.79212` and run-block 95% CI `[1.6652638047947361, 1.9155776531833093]`.  This validates the frozen policy only as an externalized consumer-risk ordering, not as a detector-truth label.
