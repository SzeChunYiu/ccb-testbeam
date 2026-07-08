# P09e: delayed-peak external timing closure

**Ticket:** `1781099176.1077.49f23306`

## Abstract
P09d showed that late-gated delayed B2 peaks can be recovered against the odd duplicate-channel consistency target. This study asks the harder external question: does the recovered B2 time close against an independent same-event B4/B6/B8 timing reference? I rebuilt the selected B-stack pulse table from raw ROOT, selected delayed B2 candidates using only B2 waveform morphology, and compared a strong train-run template offset with ridge regression, gradient-boosted trees, an MLP, a compact 1D-CNN, and a new late-gated CNN. Every prediction is leave-one-run-out: the held-out run is absent from the training sample, and uncertainty intervals are run-block bootstraps over the held-out runs.

## Reproduction first
The raw ROOT scan used the S00/P09a gate: B2/B4/B6/B8 even channels, baseline median over samples 0-3, and amplitude > 1000 ADC. Same-event B4/B6/B8 CFD20 crossings were computed in the same pass to define the external timing reference.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

Per-run reproduction counts and all raw ROOT sha256 hashes are written to `reproduction_counts_by_run.csv` and `input_sha256.csv`.

## Delayed-peak definition
A candidate is eligible for the recovery benchmark when

`stave == B2` and `peak_sample >= 13` and `late_fraction >= 0.32` and `secondary_peak <= 0.60`, with at least one finite selected B4/B6/B8 reference crossing, excluding saturated two-sample plateaus.

This definition is deliberately close to the P09b delayed-peak morphology but is applied to the full raw selected-pulse table rather than only to the 256-row gallery.

## Target and metrics
For delayed B2 pulse `i`, the external timing target is `t_i^ext = median({t_i^B4, t_i^B6, t_i^B8})` over selected downstream staves with finite CFD20 crossings in the same event. A method predicts `\hat t_i` from the B2 normalized waveform and scalar morphology only; the downstream reference is never passed as a feature.

The main scalar loss is

`L_i = |hat_t_i - t_i^ext| / 1.00`.

Reported columns include timing sigma68, timing MAE, mean external closure loss `L`, the rate of good recoveries satisfying `|dt| <= 1.50` samples, and a preregistered recover-vs-veto utility `U = good_rate - 0.55 * mean(min(L,4))`. The veto action has `U = 0` because it keeps no delayed pulse measurement.

## Methods
The traditional baseline is a late-template external offset refit: in the training runs, delayed and near-delayed B2 pulses are binned by peak-position class; the median offset `median(t^ext - t^B2)` is then applied to the held-out run with B2-level fallback. This is a strong non-ML method because it uses the known late-peak coordinate directly while preserving run isolation.

The ML/NN methods share the same feature tensor: 18 normalized B2 waveform samples plus amplitude, peak, late/early area fractions, width, baseline diagnostics, secondary peak, undershoot, CFD20, and duplicate-span quality. The duplicate-span quality is retained only as a B2 waveform quality covariate; the odd duplicate target is not used. Ridge is linear in standardized features; gradient-boosted trees use histogram boosting; the MLP is a two-layer ReLU regressor; the 1D-CNN convolves over waveform samples and appends scalar features; the new architecture is a late-gated CNN whose latent channels are multiplicatively gated by samples 12-17 and the peak coordinate before the final regressor.

## Candidate counts
|   run | stave   |   delayed_candidates |   selected_pulses |
|------:|:--------|---------------------:|------------------:|
|    42 | B2      |                   41 |             16977 |
|    42 | B4      |                    0 |               711 |
|    42 | B6      |                    0 |               307 |
|    42 | B8      |                    0 |               117 |
|    57 | B2      |                   49 |             12774 |
|    57 | B4      |                    0 |               656 |
|    57 | B6      |                    0 |               273 |
|    57 | B8      |                    0 |               130 |
|    64 | B2      |                   61 |             11907 |
|    64 | B4      |                    0 |              1689 |
|    64 | B6      |                    0 |               763 |
|    64 | B8      |                    0 |               271 |
|    65 | B2      |                   55 |             11768 |
|    65 | B4      |                    0 |               842 |
|    65 | B6      |                    0 |               323 |
|    65 | B8      |                    0 |               105 |

## Fold audit
|   test_run |   n_train_sampled |   n_train_delayed_candidates |   n_test_delayed_candidates | test_run_in_train   | cnn_1d_device   | late_gated_cnn_new_device   |
|-----------:|------------------:|-----------------------------:|----------------------------:|:--------------------|:----------------|:----------------------------|
|         42 |             34620 |                         1180 |                          41 | False               | cpu             | cpu                         |
|         57 |             34692 |                         1172 |                          49 | False               | cpu             | cpu                         |
|         64 |             33637 |                         1160 |                          61 | False               | cpu             | cpu                         |
|         65 |             34498 |                         1166 |                          55 | False               | cpu             | cpu                         |

## Head-to-head benchmark
| method                    |   n_eval |   time_res68_samples | time_res68_samples_ci95   |   time_mae_samples | time_mae_samples_ci95   |   external_closure_loss | external_closure_loss_ci95   |   composite_loss | composite_loss_ci95   |   good_recovery_rate | good_recovery_rate_ci95   |   recover_utility_vs_veto0 | recover_utility_vs_veto0_ci95   |
|:--------------------------|---------:|---------------------:|:--------------------------|-------------------:|:------------------------|------------------------:|:-----------------------------|-----------------:|:----------------------|---------------------:|:--------------------------|---------------------------:|:--------------------------------|
| traditional_late_template |      206 |             0.231267 | [0.189, 0.307]            |           1.10777  | [0.798, 1.45]           |                1.10777  | [0.798, 1.45]                |         1.10777  | [0.798, 1.45]         |             0.893204 | [0.849, 0.929]            |                   0.573126 | [0.433, 0.684]                  |
| ridge                     |      206 |             1.12858  | [0.569, 1.9]              |           1.22074  | [0.98, 1.52]            |                1.22074  | [0.98, 1.52]                 |         1.22074  | [0.98, 1.52]          |             0.747573 | [0.657, 0.806]            |                   0.151188 | [-0.0682, 0.314]                |
| gradient_boosted_trees    |      206 |             0.291256 | [0.25, 0.322]             |           0.505255 | [0.393, 0.622]          |                0.505255 | [0.393, 0.622]               |         0.505255 | [0.393, 0.622]        |             0.951456 | [0.935, 0.97]             |                   0.714917 | [0.661, 0.762]                  |
| mlp                       |      206 |             0.456954 | [0.423, 0.509]            |           0.887321 | [0.687, 1.04]           |                0.887321 | [0.687, 1.04]                |         0.887321 | [0.687, 1.04]         |             0.927184 | [0.885, 0.964]            |                   0.479483 | [0.397, 0.603]                  |
| cnn_1d                    |      206 |             0.564114 | [0.538, 0.623]            |           0.666147 | [0.543, 0.807]          |                0.666147 | [0.543, 0.807]               |         0.666147 | [0.543, 0.807]        |             0.92233  | [0.876, 0.957]            |                   0.607271 | [0.519, 0.684]                  |
| late_gated_cnn_new        |      206 |             0.470197 | [0.419, 0.593]            |           0.642172 | [0.512, 0.791]          |                0.642172 | [0.512, 0.791]               |         0.642172 | [0.512, 0.791]        |             0.917476 | [0.89, 0.941]             |                   0.613782 | [0.518, 0.678]                  |

## Leakage checks
| check                                   |   value | pass   | note                                                                          |
|:----------------------------------------|--------:|:-------|:------------------------------------------------------------------------------|
| raw_reproduction_before_modeling        |  640737 | True   | script raises before model training if this is false                          |
| leave_one_run_train_test_overlap        |       0 | True   | run identifier is used only for splitting and bootstrap blocks                |
| identifier_columns_absent_from_features |       0 | True   | run, eventno, evt, event_index, channel, and stave are not in SCALAR_FEATURES |
| all_methods_same_eval_rows              |       1 | True   | head-to-head methods must score the same delayed candidates                   |
| finite_predictions                      |       1 | True   | NaN predictions would invalidate recovery scoring                             |

## Systematics and caveats
- The B4/B6/B8 reference is external to the B2 recovery waveform, but it is still a same-event detector observable rather than beam-truth time.
- The delayed-candidate definition intentionally rejects strong secondary peaks to avoid turning the study into a pile-up benchmark; this can remove real late pile-up cases.
- B4/B6/B8 references exist only when a downstream stave also passes the selected-pulse gate, so this is a topology-supported closure test rather than a fully inclusive delayed-peak census.
- Training includes delayed B2 candidates from other runs. That is required for a recovery refit, but run-wise non-stationarity remains a systematic; the reported intervals therefore bootstrap whole held-out runs.
- The gallery labels are not used as training labels. P09b/P09c motivate the morphology, while this study scores against independent downstream timing closure in the raw ROOT table.

## Verdict
The winner by mean external closure loss is **gradient_boosted_trees** with `L = 0.505` (95% run-bootstrap CI [0.393, 0.622]) and good-recovery rate 0.951 (CI [0.935, 0.97]). Its recover-vs-veto utility is 0.715 (CI [0.661, 0.762]), so the preregistered action decision is **recover** for this candidate set. This directly tests whether P09d-style recovery transfers from duplicate-channel consistency to downstream timing closure.

## Provenance
Runtime was 549.2 s on `billy` with Python `3.7.6`. The manifest records input, code, command, seed, and output hashes.
