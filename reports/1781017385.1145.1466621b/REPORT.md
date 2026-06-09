# P01d: run-family leakage sentinels for waveform probes

**Ticket:** `1781017385.1145.1466621b`

## Reproduction first
Raw B-stack ROOT from `data/root/root` was scanned before any modelling. The P01/S00 gate (B2/B4/B6/B8, median baseline samples 0-3, amplitude >1000 ADC) reproduced **640737** selected pulses versus expected **640737**.

## Method
The target is `stave_index`, matching the P01c leakage battery. Each fold holds out one whole run family, trains only on the other families, and scores on capped held-out run/stave cells. CIs are 95% run-block bootstrap intervals over held-out runs; `sample_ii_calib` is a one-run family, so its CI is necessarily degenerate.

Traditional is residualized hand-shape summaries plus PCA-6, with log-amplitude and selected multiplicity linearly regressed out using train rows only. ML is a masked-denoising AE-6 latent with the same residualization. No Monte Carlo was used.

## Main run-family probes
| heldout_family     | method                            | value | ci_low | ci_high | train_rows | heldout_rows | heldout_runs |
| ------------------ | --------------------------------- | ----- | ------ | ------- | ---------- | ------------ | ------------ |
| sample_i_calib     | traditional residual hand+PCA-6   | 0.256 | 0.248  | 0.266   | 39867      | 18190        | 11           |
| sample_i_calib     | ML residual masked-denoising AE-6 | 0.295 | 0.276  | 0.317   | 39867      | 18190        | 11           |
| sample_i_analysis  | traditional residual hand+PCA-6   | 0.303 | 0.294  | 0.312   | 37832      | 20225        | 14           |
| sample_i_analysis  | ML residual masked-denoising AE-6 | 0.300 | 0.282  | 0.321   | 37832      | 20225        | 14           |
| sample_ii_analysis | traditional residual hand+PCA-6   | 0.278 | 0.271  | 0.285   | 40786      | 17271        | 7            |
| sample_ii_analysis | ML residual masked-denoising AE-6 | 0.254 | 0.241  | 0.265   | 40786      | 17271        | 7            |
| sample_ii_calib    | traditional residual hand+PCA-6   | 0.268 | 0.268  | 0.268   | 55686      | 2371         | 1            |
| sample_ii_calib    | ML residual masked-denoising AE-6 | 0.255 | 0.255  | 0.255   | 55686      | 2371         | 1            |

## Shuffle gates
| heldout_family     | traditional_value | ml_value | ml_minus_traditional | traditional_shuffle_p95 | ml_shuffle_p95 | accepted_ml_gain | heldout_runs                                             |
| ------------------ | ----------------- | -------- | -------------------- | ----------------------- | -------------- | ---------------- | -------------------------------------------------------- |
| sample_i_calib     | 0.256             | 0.295    | 0.038                | 0.282                   | 0.299          | False            | [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42]             |
| sample_i_analysis  | 0.303             | 0.300    | -0.002               | 0.309                   | 0.325          | False            | [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57] |
| sample_ii_analysis | 0.278             | 0.254    | -0.024               | 0.280                   | 0.309          | False            | [58, 59, 60, 61, 62, 63, 65]                             |
| sample_ii_calib    | 0.268             | 0.255    | -0.013               | 0.326                   | 0.305          | False            | [64]                                                     |

A waveform representation gain is accepted only if the AE score is above the traditional score and above its within-family label-shuffle p95 by the configured margin of `0.030`.

## Leakage hunt
| heldout_family     | method                       | value | ci_low | ci_high | heldout_rows |
| ------------------ | ---------------------------- | ----- | ------ | ------- | ------------ |
| sample_i_calib     | proxy amplitude+multiplicity | 0.637 | 0.627  | 0.645   | 18190        |
| sample_i_calib     | event-order leakage probe    | 0.250 | 0.245  | 0.255   | 18190        |
| sample_i_analysis  | proxy amplitude+multiplicity | 0.628 | 0.621  | 0.634   | 20225        |
| sample_i_analysis  | event-order leakage probe    | 0.253 | 0.246  | 0.260   | 20225        |
| sample_ii_analysis | proxy amplitude+multiplicity | 0.639 | 0.607  | 0.663   | 17271        |
| sample_ii_analysis | event-order leakage probe    | 0.248 | 0.245  | 0.252   | 17271        |
| sample_ii_calib    | proxy amplitude+multiplicity | 0.681 | 0.681  | 0.681   | 2371         |
| sample_ii_calib    | event-order leakage probe    | 0.249 | 0.249  | 0.249   | 2371         |

| heldout_family     | check                               | value  | pass  | note                                                                          |
| ------------------ | ----------------------------------- | ------ | ----- | ----------------------------------------------------------------------------- |
| sample_i_calib     | train_heldout_run_overlap           | 0.000  | True  | must be zero                                                                  |
| sample_i_calib     | duplicate_key_overlap_train_heldout | 0.000  | True  | run-heldout split makes overlap impossible unless duplicated metadata exists  |
| sample_i_calib     | ml_shuffle_p95_margin_gate          | -0.004 | False | ML score must exceed label-shuffle p95 by margin 0.030                        |
| sample_i_calib     | traditional_shuffle_p95_margin_gate | -0.025 | False | traditional score must exceed label-shuffle p95 by margin 0.030               |
| sample_i_calib     | proxy_near_best_main                | -0.343 | False | fails if amplitude/multiplicity proxy is within margin of the best main score |
| sample_i_calib     | event_order_near_best_main          | 0.045  | True  | fails if event-order probe is within margin of the best main score            |
| sample_i_calib     | too_good_leakage_hunt_triggered     | 0.295  | True  | triggered=False                                                               |
| sample_i_calib     | accepted_ml_gain                    | 0.038  | False | accepted only if ML beats traditional and ML clears shuffle p95 plus margin   |
| sample_i_analysis  | train_heldout_run_overlap           | 0.000  | True  | must be zero                                                                  |
| sample_i_analysis  | duplicate_key_overlap_train_heldout | 0.000  | True  | run-heldout split makes overlap impossible unless duplicated metadata exists  |
| sample_i_analysis  | ml_shuffle_p95_margin_gate          | -0.024 | False | ML score must exceed label-shuffle p95 by margin 0.030                        |
| sample_i_analysis  | traditional_shuffle_p95_margin_gate | -0.007 | False | traditional score must exceed label-shuffle p95 by margin 0.030               |
| sample_i_analysis  | proxy_near_best_main                | -0.326 | False | fails if amplitude/multiplicity proxy is within margin of the best main score |
| sample_i_analysis  | event_order_near_best_main          | 0.050  | True  | fails if event-order probe is within margin of the best main score            |
| sample_i_analysis  | too_good_leakage_hunt_triggered     | 0.303  | True  | triggered=False                                                               |
| sample_i_analysis  | accepted_ml_gain                    | -0.002 | False | accepted only if ML beats traditional and ML clears shuffle p95 plus margin   |
| sample_ii_analysis | train_heldout_run_overlap           | 0.000  | True  | must be zero                                                                  |
| sample_ii_analysis | duplicate_key_overlap_train_heldout | 0.000  | True  | run-heldout split makes overlap impossible unless duplicated metadata exists  |
| sample_ii_analysis | ml_shuffle_p95_margin_gate          | -0.055 | False | ML score must exceed label-shuffle p95 by margin 0.030                        |
| sample_ii_analysis | traditional_shuffle_p95_margin_gate | -0.001 | False | traditional score must exceed label-shuffle p95 by margin 0.030               |
| sample_ii_analysis | proxy_near_best_main                | -0.360 | False | fails if amplitude/multiplicity proxy is within margin of the best main score |
| sample_ii_analysis | event_order_near_best_main          | 0.030  | True  | fails if event-order probe is within margin of the best main score            |
| sample_ii_analysis | too_good_leakage_hunt_triggered     | 0.278  | True  | triggered=False                                                               |
| sample_ii_analysis | accepted_ml_gain                    | -0.024 | False | accepted only if ML beats traditional and ML clears shuffle p95 plus margin   |
| sample_ii_calib    | train_heldout_run_overlap           | 0.000  | True  | must be zero                                                                  |
| sample_ii_calib    | duplicate_key_overlap_train_heldout | 0.000  | True  | run-heldout split makes overlap impossible unless duplicated metadata exists  |
| sample_ii_calib    | ml_shuffle_p95_margin_gate          | -0.050 | False | ML score must exceed label-shuffle p95 by margin 0.030                        |
| sample_ii_calib    | traditional_shuffle_p95_margin_gate | -0.059 | False | traditional score must exceed label-shuffle p95 by margin 0.030               |
| sample_ii_calib    | proxy_near_best_main                | -0.414 | False | fails if amplitude/multiplicity proxy is within margin of the best main score |
| sample_ii_calib    | event_order_near_best_main          | 0.019  | False | fails if event-order probe is within margin of the best main score            |
| sample_ii_calib    | too_good_leakage_hunt_triggered     | 0.268  | True  | triggered=False                                                               |
| sample_ii_calib    | accepted_ml_gain                    | -0.013 | False | accepted only if ML beats traditional and ML clears shuffle p95 plus margin   |

## Held-out run breakdown
| heldout_family    | method                            | run | heldout_rows | balanced_accuracy |
| ----------------- | --------------------------------- | --- | ------------ | ----------------- |
| sample_i_analysis | ML residual masked-denoising AE-6 | 44  | 854          | 0.256             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 45  | 1978         | 0.284             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 46  | 687          | 0.252             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 47  | 860          | 0.261             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 48  | 1656         | 0.263             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 49  | 1736         | 0.249             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 50  | 1829         | 0.321             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 51  | 1240         | 0.361             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 52  | 959          | 0.391             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 53  | 1675         | 0.324             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 54  | 1647         | 0.334             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 55  | 1352         | 0.335             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 56  | 1993         | 0.335             |
| sample_i_analysis | ML residual masked-denoising AE-6 | 57  | 1759         | 0.260             |
| sample_i_analysis | event-order leakage probe         | 44  | 854          | 0.236             |
| sample_i_analysis | event-order leakage probe         | 45  | 1978         | 0.237             |
| sample_i_analysis | event-order leakage probe         | 46  | 687          | 0.257             |
| sample_i_analysis | event-order leakage probe         | 47  | 860          | 0.260             |
| sample_i_analysis | event-order leakage probe         | 48  | 1656         | 0.271             |
| sample_i_analysis | event-order leakage probe         | 49  | 1736         | 0.243             |
| sample_i_analysis | event-order leakage probe         | 50  | 1829         | 0.269             |
| sample_i_analysis | event-order leakage probe         | 51  | 1240         | 0.269             |
| sample_i_analysis | event-order leakage probe         | 52  | 959          | 0.245             |
| sample_i_analysis | event-order leakage probe         | 53  | 1675         | 0.259             |
| sample_i_analysis | event-order leakage probe         | 54  | 1647         | 0.251             |
| sample_i_analysis | event-order leakage probe         | 55  | 1352         | 0.242             |
| sample_i_analysis | event-order leakage probe         | 56  | 1993         | 0.239             |
| sample_i_analysis | event-order leakage probe         | 57  | 1759         | 0.253             |
| sample_i_analysis | proxy amplitude+multiplicity      | 44  | 854          | 0.600             |
| sample_i_analysis | proxy amplitude+multiplicity      | 45  | 1978         | 0.640             |
| sample_i_analysis | proxy amplitude+multiplicity      | 46  | 687          | 0.585             |
| sample_i_analysis | proxy amplitude+multiplicity      | 47  | 860          | 0.544             |
| sample_i_analysis | proxy amplitude+multiplicity      | 48  | 1656         | 0.634             |
| sample_i_analysis | proxy amplitude+multiplicity      | 49  | 1736         | 0.638             |
| sample_i_analysis | proxy amplitude+multiplicity      | 50  | 1829         | 0.620             |
| sample_i_analysis | proxy amplitude+multiplicity      | 51  | 1240         | 0.627             |
| sample_i_analysis | proxy amplitude+multiplicity      | 52  | 959          | 0.638             |
| sample_i_analysis | proxy amplitude+multiplicity      | 53  | 1675         | 0.627             |
| sample_i_analysis | proxy amplitude+multiplicity      | 54  | 1647         | 0.615             |
| sample_i_analysis | proxy amplitude+multiplicity      | 55  | 1352         | 0.625             |
| sample_i_analysis | proxy amplitude+multiplicity      | 56  | 1993         | 0.634             |
| sample_i_analysis | proxy amplitude+multiplicity      | 57  | 1759         | 0.631             |
| sample_i_analysis | traditional residual hand+PCA-6   | 44  | 854          | 0.333             |
| sample_i_analysis | traditional residual hand+PCA-6   | 45  | 1978         | 0.275             |
| sample_i_analysis | traditional residual hand+PCA-6   | 46  | 687          | 0.135             |
| sample_i_analysis | traditional residual hand+PCA-6   | 47  | 860          | 0.291             |
| sample_i_analysis | traditional residual hand+PCA-6   | 48  | 1656         | 0.296             |
| sample_i_analysis | traditional residual hand+PCA-6   | 49  | 1736         | 0.291             |

## Verdict
No AE-over-traditional gain was accepted after the family-local shuffle p95 plus margin gate. Leakage/proxy flags were raised for: sample_i_calib:ml_shuffle_p95_margin_gate, sample_i_calib:traditional_shuffle_p95_margin_gate, sample_i_calib:proxy_near_best_main, sample_i_analysis:ml_shuffle_p95_margin_gate, sample_i_analysis:traditional_shuffle_p95_margin_gate, sample_i_analysis:proxy_near_best_main, sample_ii_analysis:ml_shuffle_p95_margin_gate, sample_ii_analysis:traditional_shuffle_p95_margin_gate, sample_ii_analysis:proxy_near_best_main, sample_ii_calib:ml_shuffle_p95_margin_gate, sample_ii_calib:traditional_shuffle_p95_margin_gate, sample_ii_calib:proxy_near_best_main, sample_ii_calib:event_order_near_best_main.

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_counts_by_run.csv`, `family_probe_metrics.csv`, `shuffle_nulls.csv`, `leakage_checks.csv`, `family_splits.csv`, and `heldout_by_run_metrics.csv`.
