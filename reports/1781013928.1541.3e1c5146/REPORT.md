# S16f: forced/random pedestal truth validation

- **Ticket:** 1781013928.1541.3e1c5146
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16f_1781013928_1541_3e1c5146.json`

## Question

Once non-beam HRD pedestal entries are available, does the S16 adaptive pedestal lowering remain biased relative to true forced/random no-pulse samples?

## Raw reproduction first

The raw B-stack ROOT reproduction gives **640,737** selected B-stave pulses with `A > 1000` ADC, matching the expected **640,737**. The direct forced/random audit finds **0** `TRIGGER != 1` entries and **0** forced/random/pedestal filename hits across **110** raw ROOT files.

## Direct truth gate

No acquired forced/random no-pulse HRD entries are present in this mirror. Therefore the requested direct electronics-pedestal comparison is **not estimable** from the available raw ROOT, and neither the traditional nor ML method below is claimed as direct forced/random truth.

## Held-out proxy benchmark

As a fallback sanity check only, quiet B-stack events with event maximum below `80` ADC were split by run. Runs `57, 65` are held out; bootstrap intervals resample held-out runs.

| Method | Records | MAE ADC | Mean bias ADC |
|---|---:|---:|---:|
| traditional_adaptive_pc_excluding_target | 807336 | 18.19 [14.61, 23.87] | -9.42 [-15.21, -5.83] |
| ml_pretrigger_extra_trees_calibrated | 807336 | 18.24 [17.20, 20.01] | -1.10 [-2.01, -0.48] |
| traditional_mean4_pre | 807336 | 19.65 [16.47, 24.38] | 5.16 [1.61, 11.61] |
| traditional_median4_plus_train_offset | 807336 | 20.04 [16.75, 25.68] | 3.34 [-0.12, 9.20] |
| traditional_median4_pre | 807336 | 20.14 [16.74, 25.93] | 5.32 [1.78, 11.12] |

The best proxy method is `traditional_adaptive_pc_excluding_target` with MAE 18.19 ADC and mean bias -9.42 ADC. This is a proxy for electronics stability, not evidence that S16 lowering is unbiased on forced/random triggers.

## Leakage checks

| Check | Metric | Value | Interpretation |
|---|---|---:|---|
| shuffled_training_target | mae_adc | 84.67 | negative control; should be much worse than the real ML model |
| intentional_target_feature_oracle | mae_adc | 2.73 | positive control; direct target leakage would make the error suspiciously small |
| real_feature_exclusion | n_excluded_leakage_columns | 4.00 | real features exclude run, eventno, evt, and target_adc; split is by run |

## Conclusion

The requested S16f direct forced/random pedestal validation is blocked: this data mirror contains no non-beam HRD ROOT entries or forced/random/pedestal filename hits. The quiet-proxy benchmark remains compatible with prior S16d behavior, but it must not be treated as acquired forced/random electronics truth.
