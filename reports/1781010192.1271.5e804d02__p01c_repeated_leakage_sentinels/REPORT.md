# P01c: repeated leakage sentinels for waveform probes

**Ticket:** 1781010192.1271.5e804d02

## Reproduction first
The script read raw B-stack ROOT files from `data/root/root` before
any model fitting. The P01/S00 selection reproduced
**640,737** selected B-stave pulses
versus the expected **640,737**.

## Official run-heldout benchmark
Held-out runs are `42, 57, 64, 65`. Training and
held-out samples are balanced by `(run, stave)` with at most
1500 pulses per cell. CIs are 95% held-out run-block bootstraps.

| method                            | value | ci_low | ci_high | macro_f1 | train_rows | heldout_rows |
| --------------------------------- | ----- | ------ | ------- | -------- | ---------- | ------------ |
| traditional residual PCA+hand     | 0.331 | 0.304  | 0.349   | 0.312    | 82118      | 11998        |
| ML residual masked-denoising AE-4 | 0.235 | 0.221  | 0.246   | 0.211    | 82118      | 11998        |
| proxy amplitude+topology          | 0.668 | 0.637  | 0.680   | 0.622    | 82118      | 11998        |
| leakage target topology mask      | 0.829 | 0.805  | 0.849   | 0.733    | 82118      | 11998        |

The traditional method is a ridge residualization against log-amplitude and
selected-stave multiplicity followed by hand-shape features plus PCA-4. The ML
method is a masked-denoising AE-4 trained only on training runs, followed by
the same balanced linear probe.

## Repeated leakage battery
Each row summarizes 10 shuffled-label seeds for a permutation
mode. The acceptance rule compares the real ML score against the worst
95th-percentile shuffled score plus a 0.02 margin.

| base_method                       | shuffle_mode        | mean  | p95   | max   | count |
| --------------------------------- | ------------------- | ----- | ----- | ----- | ----- |
| ML residual masked-denoising AE-4 | global              | 0.268 | 0.307 | 0.313 | 10    |
| ML residual masked-denoising AE-4 | within_run          | 0.239 | 0.246 | 0.248 | 10    |
| ML residual masked-denoising AE-4 | within_run_topology | 0.260 | 0.264 | 0.264 | 10    |
| ML residual masked-denoising AE-4 | within_topology     | 0.256 | 0.262 | 0.262 | 10    |
| traditional residual PCA+hand     | global              | 0.250 | 0.273 | 0.273 | 10    |
| traditional residual PCA+hand     | within_run          | 0.255 | 0.267 | 0.269 | 10    |
| traditional residual PCA+hand     | within_run_topology | 0.329 | 0.333 | 0.333 | 10    |
| traditional residual PCA+hand     | within_topology     | 0.333 | 0.339 | 0.339 | 10    |

The battery also writes per-heldout-run and per-topology shuffle strata to
`shuffle_summary.csv` and the raw seed-level rows to `repeated_shuffle_battery.csv`.

## Random-row comparison
Random-row splits are not accepted as physics evidence; they are leakage
sentinels for row/order/composition shortcuts.

| method                                             | value | ci_low | ci_high | macro_f1 | train_rows | heldout_rows |
| -------------------------------------------------- | ----- | ------ | ------- | -------- | ---------- | ------------ |
| traditional residual PCA+hand random-row split     | 0.378 | 0.371  | 0.385   | 0.364    | 70587      | 23529        |
| ML residual masked-denoising AE-4 random-row split | 0.276 | 0.270  | 0.282   | 0.268    | 70587      | 23529        |

## Pass/fail rule
| rule                                              | value | detail                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ml_ci_beats_traditional_ci                        | False | ML low 0.221 > traditional high 0.349                                                                                                                                                                                                                                                                                        |
| ml_overall_above_repeated_shuffle_p95_plus_margin | False | ML 0.235; shuffle p95 max 0.307; margin 0.02                                                                                                                                                                                                                                                                                 |
| random_row_gain_not_suspicious                    | True  | random-row 0.276 - run-heldout 0.235 <= 0.05                                                                                                                                                                                                                                                                                 |
| ml_above_shuffle_in_every_run_and_topology        | False | heldout_run=42 real 0.242 <= shuffle p95 0.297+0.02; heldout_run=57 real 0.239 <= shuffle p95 0.305+0.02; heldout_run=64 real 0.228 <= shuffle p95 0.313+0.02; heldout_run=65 real 0.214 <= shuffle p95 0.341+0.02; topology=quad real 0.288 <= shuffle p95 0.301+0.02; topology=single real 0.318 <= shuffle p95 0.317+0.02 |

Decision: **FAIL** for accepting a waveform representation improvement.
The result does not pass the pre-registered leakage battery, so the correct
interpretation is that P01-style waveform probes still require repeated
shuffle/permutation controls before any claimed improvement is accepted.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `reproduction_counts_by_run.csv`,
`run_heldout_benchmark.csv`, `random_row_benchmark.csv`,
`real_by_stratum.csv`, `repeated_shuffle_battery.csv`, `shuffle_summary.csv`,
`leakage_pass_rules.csv`, and `ae_training_loss.csv` are in this report
directory. No Monte Carlo was used.
