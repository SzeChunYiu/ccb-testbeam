# P09d: delayed-peak recovery refit

**Ticket:** `1781032068.1433.5cef09d4`

## Abstract
P09b/P09c found that delayed-peak gallery calls survive blinded morphology review. This study tests whether those pulses should be vetoed or recovered. I rebuilt the selected B-stack pulse table from raw ROOT, selected delayed-peak candidates using only waveform morphology, and compared a late-template traditional refit with ridge regression, gradient-boosted trees, an MLP, a compact 1D-CNN, and a new late-gated CNN. Every prediction is leave-one-run-out: the held-out run is absent from the training sample, and uncertainty intervals are run-block bootstraps over the held-out runs.

## Reproduction first
The raw ROOT scan used the S00/P09a gate: B2/B4/B6/B8 even channels, baseline median over samples 0-3, and amplitude > 1000 ADC. The duplicate odd channel was read in the same pass but was not used for selecting pulses.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

Per-run reproduction counts and all raw ROOT sha256 hashes are written to `reproduction_counts_by_run.csv` and `input_sha256.csv`.

## Delayed-peak definition
A candidate is eligible for the recovery benchmark when

`peak_sample >= 13` and `late_fraction >= 0.32` and `secondary_peak <= 0.60`, with finite duplicate-channel timing and positive duplicate charge, excluding saturated two-sample plateaus.

This definition is deliberately close to the P09b delayed-peak morphology but is applied to the full raw selected-pulse table rather than only to the 256-row gallery.

## Target and metrics
For pulse `i`, the recovery target is the duplicate-channel pair `(t_i^dup, q_i^dup)`, where `t_i^dup` is the CFD20 crossing of the odd-channel normalized waveform and `q_i^dup = log(1 + A_i^dup)` is the log positive duplicate amplitude. A method predicts `\hat y_i = (\hat t_i, \hat q_i)` from the even-channel normalized waveform and scalar morphology only.

The main scalar loss is

`L_i = sqrt(((hat_t_i - t_i^dup)/1.00)^2 + ((hat_q_i - q_i^dup)/0.25)^2)`.

Reported columns include timing sigma68, timing MAE, log-charge MAE, mean `L`, the rate of good recoveries satisfying `|dt| <= 1.50` samples and `|dq| <= 0.35`, and a preregistered recover-vs-veto utility `U = good_rate - 0.55 * mean(min(L,4))`. The veto action has `U = 0` because it keeps no delayed pulse measurement.

## Methods
The traditional baseline is a late-template offset refit: in the training runs, delayed and near-delayed pulses are binned by stave and peak-position class; the median offsets `median(t^dup - t^even)` and `median(q^dup - q^even)` are then applied to the held-out run with stave-level fallbacks. This is a strong non-ML method because it uses the known late-peak coordinate directly while preserving run isolation.

The ML/NN methods share the same feature tensor: 18 normalized waveform samples plus amplitude, peak, late/early area fractions, width, baseline diagnostics, secondary peak, undershoot, CFD20, and duplicate-span quality. Ridge is linear in standardized features; gradient-boosted trees use histogram boosting; the MLP is a two-layer ReLU regressor; the 1D-CNN convolves over waveform samples and appends scalar features; the new architecture is a late-gated CNN whose latent channels are multiplicatively gated by samples 12-17 and the peak coordinate before the final regressor.

## Candidate counts
|   run | stave   |   delayed_candidates |   selected_pulses |
|------:|:--------|---------------------:|------------------:|
|    42 | B2      |                    9 |             16977 |
|    42 | B4      |                    0 |               711 |
|    42 | B6      |                    0 |               307 |
|    42 | B8      |                    0 |               117 |
|    57 | B2      |                    3 |             12774 |
|    57 | B4      |                    0 |               656 |
|    57 | B6      |                    0 |               273 |
|    57 | B8      |                    0 |               130 |
|    64 | B2      |                    4 |             11907 |
|    64 | B4      |                    0 |              1689 |
|    64 | B6      |                    0 |               763 |
|    64 | B8      |                    0 |               271 |
|    65 | B2      |                    2 |             11768 |
|    65 | B4      |                    0 |               842 |
|    65 | B6      |                    0 |               323 |
|    65 | B8      |                    0 |               105 |

## Fold audit
|   test_run |   n_train_sampled |   n_train_delayed_candidates |   n_test_delayed_candidates | test_run_in_train   | cnn_1d_device   | late_gated_cnn_new_device   |
|-----------:|------------------:|-----------------------------:|----------------------------:|:--------------------|:----------------|:----------------------------|
|         42 |             30266 |                          149 |                           9 | False               | cpu             | cpu                         |
|         57 |             30357 |                          155 |                           3 | False               | cpu             | cpu                         |
|         64 |             30540 |                          154 |                           4 | False               | cpu             | cpu                         |
|         65 |             30799 |                          156 |                           2 | False               | cpu             | cpu                         |

## Head-to-head benchmark
| method                    |   n_eval |   time_res68_samples | time_res68_samples_ci95   |   time_mae_samples | time_mae_samples_ci95   |   charge_mae_log | charge_mae_log_ci95   |   composite_loss | composite_loss_ci95   |   good_recovery_rate | good_recovery_rate_ci95   |   recover_utility_vs_veto0 | recover_utility_vs_veto0_ci95   |
|:--------------------------|---------:|---------------------:|:--------------------------|-------------------:|:------------------------|-----------------:|:----------------------|-----------------:|:----------------------|---------------------:|:--------------------------|---------------------------:|:--------------------------------|
| traditional_late_template |       18 |             7.77903  | [6.22, 9.89]              |           5.98543  | [5.31, 7.25]            |         0.466015 | [0.297, 0.735]        |         6.52238  | [5.69, 8.33]          |            0.0555556 | [0, 0.1]                  |                  -1.94529  | [-2.2, -1.8]                    |
| ridge                     |       18 |             3.54703  | [2.28, 4.62]              |           2.94125  | [2.1, 3.47]             |         0.340435 | [0.312, 0.4]          |         3.40326  | [2.6, 3.92]           |            0.111111  | [0, 0.286]                |                  -1.57197  | [-1.85, -1.13]                  |
| gradient_boosted_trees    |       18 |             0.278512 | [0.0883, 0.84]            |           0.339648 | [0.185, 0.59]           |         0.206373 | [0.125, 0.247]        |         0.981385 | [0.714, 1.06]         |            0.833333  | [0.6, 1]                  |                   0.293572 | [0.0724, 0.538]                 |
| mlp                       |       18 |             1.20419  | [0.668, 2.15]             |           1.01706  | [0.565, 1.59]           |         0.174515 | [0.114, 0.208]        |         1.40879  | [0.895, 2.05]         |            0.666667  | [0.333, 0.889]            |                  -0.105679 | [-0.741, 0.341]                 |
| cnn_1d                    |       18 |             1.61524  | [0.662, 2.71]             |           1.39466  | [0.866, 2.23]           |         0.273103 | [0.187, 0.323]        |         1.89731  | [1.54, 2.52]          |            0.5       | [0.154, 0.645]            |                  -0.499175 | [-1.17, -0.21]                  |
| late_gated_cnn_new        |       18 |             2.47089  | [0.733, 3.43]             |           1.68653  | [1.14, 2.91]            |         0.283574 | [0.23, 0.318]         |         2.29398  | [1.87, 3.18]          |            0.444444  | [0.111, 0.621]            |                  -0.740412 | [-1.61, -0.353]                 |

## Leakage checks
| check                                   |   value | pass   | note                                                                          |
|:----------------------------------------|--------:|:-------|:------------------------------------------------------------------------------|
| raw_reproduction_before_modeling        |  640737 | True   | script raises before model training if this is false                          |
| leave_one_run_train_test_overlap        |       0 | True   | run identifier is used only for splitting and bootstrap blocks                |
| identifier_columns_absent_from_features |       0 | True   | run, eventno, evt, event_index, channel, and stave are not in SCALAR_FEATURES |
| all_methods_same_eval_rows              |       1 | True   | head-to-head methods must score the same delayed candidates                   |
| finite_predictions                      |       1 | True   | NaN predictions would invalidate recovery scoring                             |

## Systematics and caveats
- The duplicate channel is a data-derived proxy target, not an external truth label. It tests consistency of the paired readout and is appropriate for recovery quality, but it cannot prove absolute particle timing.
- The delayed-candidate definition intentionally rejects strong secondary peaks to avoid turning the study into a pile-up benchmark; this can remove real late pile-up cases.
- Training includes delayed candidates from other runs. That is required for a recovery refit, but run-wise non-stationarity remains a systematic; the reported intervals therefore bootstrap whole held-out runs.
- The gallery labels are not used as training labels. P09b/P09c motivate the morphology, while this study scores against duplicate-channel measurements in the raw ROOT table.
- The utility parameter penalizes large residuals after clipping. I report the raw timing and charge errors so the conclusion does not depend only on that scalar utility.

## Verdict
The winner by mean composite recovery loss is **gradient_boosted_trees** with `L = 0.981` (95% run-bootstrap CI [0.714, 1.06]) and good-recovery rate 0.833 (CI [0.6, 1]). Its recover-vs-veto utility is 0.294 (CI [0.0724, 0.538]), so the preregistered action decision is **recover** for this candidate set. The result supports treating delayed peaks as recoverable morphology when a late-aware model is available, with the caveat that the duplicate-channel target is a consistency standard rather than an external clock.

## Provenance
Runtime was 200.7 s on `billy` with Python `3.7.6`. The manifest records input, code, command, seed, and output hashes.
