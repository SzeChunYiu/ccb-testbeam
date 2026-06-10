# S10h: late-sample residual taxonomy for 20pct last-above inflation

- **Ticket:** `1781028280.1036.7e527107`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** all ML predictions are leave-one-run-out; intervals bootstrap held-out runs.

## Reproduction first

The raw ROOT S10c/S10d pipeline was rerun before taxonomy. It reproduced the 20% smooth
template crossing at **101.865 ns**, the empirical
last-above value at **119.030 ns**, and the
empirical-minus-template inflation at **17.165 ns**.

| quantity                                          |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S10d live20 template smooth crossing ns           |       101.865  |     101.865  |       0 |        0.05 | True   |
| S10d live20 empirical last-above ns               |       119.03   |     119.03   |       0 |        0.05 | True   |
| S10d live20 empirical-minus-template inflation ns |        17.1648 |      17.1648 |       0 |        0.05 | True   |

## Traditional taxonomy

Each selected B-stack pulse was attached to the smooth 20% crossing from its run-held-out
stave template. The rule taxonomy uses only pulse shape, amplitude, downstream topology, and
baseline/noise summaries; it does not use current labels to assign classes.

- final_sample_censored_tail: 89.8% of positive inflation, mean inflation 28.58 ns, pulse fraction 72.6%, final-sample censored 100.0%.
- high_amplitude_late_tail: 6.5% of positive inflation, mean inflation 29.92 ns, pulse fraction 5.0%, final-sample censored 100.0%.
- late_rebound_peak: 1.9% of positive inflation, mean inflation 16.03 ns, pulse fraction 2.8%, final-sample censored 0.0%.
- baseline_noise_residual: 0.9% of positive inflation, mean inflation 24.24 ns, pulse fraction 0.9%, final-sample censored 0.0%.

Current/run stratification shows the largest high-current excesses in:

- final_sample_censored_tail: high-low fraction +0.1575 [+0.0672, +0.2288], mean inflation high-low -0.35 ns.
- high_amplitude_late_tail: high-low fraction +0.0085 [-0.0078, +0.0252], mean inflation high-low -0.77 ns.
- broad_slow_tail: high-low fraction +0.0002 [-0.0001, +0.0012], mean inflation high-low +2.09 ns.

The dominant explanation is not a new smooth-tail crossing. Most positive inflation is carried
by pulses whose late samples remain or rebound above 20% after the template crossing, especially
final-sample-censored and high-amplitude late-tail classes.

## ML classifier

The ML method is a leave-one-run-out standardized L2 logistic classifier for
`inflation20_ns > 10.0 ns`. Features are waveform-shape,
amplitude, stave, downstream-topology, and residual-shape summaries; run, current, event ids,
live20, and the direct inflation target are excluded.

Mean run-held-out AUC is **0.998** [0.997, 0.999].
The top 10% ML-risk pulses have mean inflation **32.33 ns**
[31.54, 34.12] and carry **14.0%**
of positive inflation [8.1%, 20.2%].

## Leakage review

Leakage flags: **0**.

| check                    |    value |   threshold | flag   | note                                                                                                |
|:-------------------------|---------:|------------:|:-------|:----------------------------------------------------------------------------------------------------|
| ml_split_by_run          | 1        |     1       | False  | Every ML prediction is made for a held-out run.                                                     |
| forbidden_feature_count  | 0        |     0       | False  | No run/event/current/direct-target columns in feature matrix.                                       |
| run_heldout_auc          | 0.998113 |     0.985   | False  | High AUC is expected because the target is late waveform shape; flag only with row-split advantage. |
| random_row_split_auc     | 0.998611 |     1.09811 | False  | Large row-split advantage would suggest run or event leakage.                                       |
| shuffled_target_loro_auc | 0.433693 |     0.6     | False  | Shuffled labels should not predict true held-out inflation labels.                                  |
| ml_score_current_auc     | 0.604949 |     0.9     | False  | Flags if the ML score nearly identifies current group.                                              |

## Conclusion

The S10d 20% empirical last-above inflation is pulse-shape driven. A smooth template crossing
near 101.9 ns coexists with per-pulse late residual structure that keeps discrete samples above
20% until about 119.0 ns on average. The rule taxonomy assigns most positive inflation to
final-sample-censored, high-amplitude late-tail, broad slow-tail, and late-rebound classes.
The run-held-out ML classifier independently isolates the same high-inflation population without
run/current/event-id features, and the leakage audit has zero flags.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`,
`taxonomy_summary.csv`, `current_taxonomy_contrast.csv`, `taxonomy_strata_by_run.csv`,
`ml_fold_diagnostics.csv`, `ml_summary.csv`, `ml_leakage_checks.csv`, `ml_feature_manifest.csv`,
and `ml_scores.csv.gz` are in this folder.
