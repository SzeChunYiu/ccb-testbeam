# S16g: tagged random-trigger rerun without quiet selection

- **Ticket:** 1781014767.1817.342d2609
- **Worker:** testbeam-laptop-1
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16g_1781014767_1817_342d2609.json`

## Question

Rerun S16e after tagged random-trigger ROOT was expected to be present, without using a quiet-event amplitude-selected proxy. The target claim is direct adaptive-pedestal zero-bias on true no-pulse samples.

## Raw reproduction first

Raw B-stack ROOT from `h101/HRDv` reproduces **640,737** selected B-stave pulses with `A > 1000` ADC, matching the expected **640,737** exactly before any model fit.

The tagged-random audit found **0** `TRIGGER != 1` entries, **0** filename tag matches, and **0** tag-like branches across the configured B-stack raw ROOT files. The primary tagged-random gate therefore **failed**.

## Fallback method

Because no true tagged random/forced B-stack no-pulse sample is visible in this mirror, the head-to-head below is a fallback pedestal-closure benchmark on beam-trigger pre-trigger samples. It uses no quiet-event amplitude selection. Each row predicts one held-out pre-trigger sample using the other three pre-trigger samples and, for ML only, post-trigger waveform samples relative to the three-sample seed. Evaluation is leave-one-run-out over `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]` with run-block bootstrap CIs.

Traditional methods are median3, mean3, an adaptive positivity-constrained pedestal with the target sample excluded, and a train-run stratified offset by stave, target sample, and pre-trigger spread. ML is a ridge regressor with run-held-out training. Run id, event ids, target ADC, amplitude, and peak sample are excluded from ML features.

## Held-out benchmark

| Method | Records | Runs | MAE ADC | Mean bias ADC | Timing-shift tail frac |
|---|---:|---:|---:|---:|---:|
| traditional_mean3 | 320900 | 33 | 207.79 [172.49, 235.79] | 0.00 [-2.51, 2.34] | 0.1030 [0.0808, 0.1236] |
| traditional_median3 | 320900 | 33 | 211.03 [176.36, 238.90] | -35.04 [-40.01, -30.12] | 0.0000 [0.0000, 0.0000] |
| traditional_run_train_stratified_offset | 320900 | 33 | 238.05 [209.68, 261.56] | -0.16 [-6.62, 6.93] | 0.2890 [0.2708, 0.3056] |
| traditional_adaptive_pc_excluding_target | 320900 | 33 | 265.91 [226.91, 311.41] | -242.32 [-285.97, -210.23] | 0.0782 [0.0649, 0.0924] |
| ml_ridge_waveform_no_target | 320900 | 33 | 279.69 [251.60, 304.25] | 0.09 [-3.13, 4.43] | 0.5557 [0.5151, 0.6014] |
| ml_shuffled_target_control | 320900 | 33 | 461.03 [429.63, 494.42] | -0.11 [-40.80, 44.71] | 0.8075 [0.7898, 0.8250] |

The lowest-MAE traditional row is `traditional_mean3`: MAE 207.79 [172.49, 235.79] ADC and mean bias 0.00 [-2.51, 2.34] ADC. The train-run stratified traditional offset has MAE 238.05 [209.68, 261.56] ADC and mean bias -0.16 [-6.62, 6.93] ADC. The adaptive estimator remains biased: MAE 265.91 [226.91, 311.41] ADC and mean bias -242.32 [-285.97, -210.23] ADC. The ML ridge row has MAE 279.69 [251.60, 304.25] ADC and mean bias 0.09 [-3.13, 4.43] ADC.

## Leakage checks

| Check | Aggregate value | Passing folds | All pass |
|---|---:|---:|---|
| ml_shuffled_target_worse_than_real | 181.6 | 33/33 | yes |
| train_heldout_run_overlap | 0 | 33/33 | yes |
| ml_feature_forbidden_column_overlap | 0 | 1/1 | yes |
| tagged_random_gate_has_candidates | 0 | 0/1 | no |

The ML result is not promoted as tagged-random truth. Its shuffled-target control is worse on average, and the feature list excludes run, event identifiers, target ADC, amplitude, and peak sample.

## Conclusion

This rerun does not confirm adaptive pedestal zero-bias on true no-pulse samples because the tagged random-trigger ROOT is still absent from the visible data mirror. On the no-quiet-selection fallback, adaptive pedestal bias is -242.32 [-285.97, -210.23] ADC. The run-trained traditional offset and ML ridge reduce mean bias, but neither is direct random-trigger validation.

## Follow-up tickets

- S16h: add or mirror the actual forced/random HRD pedestal ROOT files, then rerun this script without entering the fallback path.
- S16i: compare adaptive-pedestal bias before and after any future tagged-random ingest using identical input hashes and leave-one-run-out scoring.
