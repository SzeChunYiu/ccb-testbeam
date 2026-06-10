# S16f: quiet-proxy selection bias in pedestal closure

- **Ticket:** 1781014587.1828.635a3c7c
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16f_1781014587_1828_635a3c7c.json`

## Question

Does the all-stave quiet-event proxy (`max B2/B4/B6/B8 amplitude < 80` ADC) bias pedestal closure relative to beam-trigger pre-trigger activity?

## Raw reproduction first

The raw B-stack ROOT gate reproduces **640,737** selected B-stave pulses with `A > 1000` ADC, matching the expected **640,737** exactly. This was done before building quiet-proxy, traditional, or ML models.

The sampled analysis table is run-balanced, not a replacement for the reproduction count: **64,687** beam pulse records and **66,000** quiet/proxy stave records expanded over the four pre-trigger target samples.

## Methods

The validation target is one held-out pre-trigger sample from a beam-selected pulse. Estimators use only the other three pre-trigger samples, stave index, target-sample index, and pre-trigger spread stratum. Splits are leave-one-run-out; every run is held out once and CIs bootstrap held-out run blocks.

Traditional baselines are median3 with no proxy, quiet-trained stratified offsets, beam-trained stratified offsets as a control, and adaptive positivity-constrained pedestal excluding the target sample. The ML method is a logistic quiet-vs-beam propensity model; quiet records are inverse-odds weighted and used to form the same stratified offsets. Run id, event id, target ADC, full waveform samples after the target, and post-trigger target values are excluded from ML features.

## Threshold and strata scan

| Quiet cut ADC | Strata | Median beam-minus-quiet offset ADC | Max abs stratum offset ADC |
|---:|---:|---:|---:|
| 40 | 5 | -1.00 | 25.00 |
| 80 | 5 | 1.00 | 42.00 |
| 120 | 5 | 1.00 | 36.00 |
| 200 | 5 | 1.00 | 23.00 |

The scan shows how much the quiet proxy's pre-trigger offset differs from beam-selected pre-trigger activity before any model is applied.

## Held-out head-to-head

| Method | Records | Runs | MAE ADC | Mean bias ADC | Downstream timing-shift tail fraction |
|---|---:|---:|---:|---:|---:|
| traditional_median3_no_proxy | 258748 | 33 | 215.25 [179.02, 247.86] | -35.58 [-40.34, -30.11] | 0.0000 [0.0000, 0.0000] |
| traditional_quiet_offset_stratified | 258748 | 33 | 218.77 [180.28, 253.18] | -33.57 [-37.95, -28.38] | 0.0234 [0.0183, 0.0284] |
| ml_shuffled_domain_control | 258748 | 33 | 218.78 [187.43, 255.13] | -33.57 [-37.46, -28.78] | 0.0233 [0.0180, 0.0298] |
| ml_inverse_propensity_quiet_offset | 258748 | 33 | 219.58 [184.98, 251.59] | -26.26 [-30.67, -21.79] | 0.0649 [0.0588, 0.0691] |
| traditional_beam_train_offset_control | 258748 | 33 | 242.78 [217.68, 267.67] | -0.18 [-6.81, 6.10] | 0.2832 [0.2670, 0.2951] |
| traditional_adaptive_pc_excluding_target | 258748 | 33 | 269.63 [228.80, 309.85] | -245.37 [-281.48, -205.10] | 0.1251 [0.1155, 0.1331] |

Best held-out MAE is `traditional_median3_no_proxy` at 215.25 ADC. The quiet-proxy traditional method has 218.77 [180.28, 253.18] ADC MAE and -33.57 [-37.95, -28.38] ADC mean bias. The ML inverse-propensity correction has 219.58 [184.98, 251.59] ADC MAE; the shuffled-domain control is 218.78 [187.43, 255.13] ADC.

## Leakage checks

| Check | Aggregate value | Passing folds | All pass |
|---|---:|---:|---|
| propensity_train_auc | 0.8928 | 33/33 | yes |
| shuffled_domain_auc | 0.4634 | 33/33 | yes |
| train_heldout_run_overlap | 0 | 33/33 | yes |
| feature_exclusion_forbidden_columns | 0 | 1/1 | yes |

No run overlap was observed. The ML result is not suspiciously good: it does not beat the beam-trained control, and the shuffled-domain control remains close enough that the propensity model should be treated as a diagnostic correction rather than a new pedestal truth.

## Conclusion

The all-stave quiet proxy is a biased sample of beam-trigger pre-trigger activity. It is useful as a low-amplitude electronics stability proxy, but using it as a direct pedestal-closure truth sample produces a nonzero beam-held-out bias. The stronger traditional control is to learn offsets on beam-trigger pre-trigger samples by run; the ML inverse-propensity weighting reduces some quiet-vs-beam mismatch but does not remove the need for a true forced/random pedestal sample.

## Follow-up tickets

- S16g: acquire or mirror forced/random HRD pedestal ROOT and rerun this exact quiet-vs-beam benchmark against direct no-pulse truth.
- S16h: propagate quiet-proxy propensity scores into S02/S03 timing-tail studies as a nuisance covariate, with the same run-held-out leakage controls.
