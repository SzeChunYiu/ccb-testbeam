# S01d: selected-pulse table rebuild from S00c checked selector

- Ticket: `1781028640.1299.266407ae`
- Worker: `testbeam-laptop-4`
- Inputs: raw B-stack ROOT under `data/root/root`; no Monte Carlo.
- Reference: S01b selected-table manifest in `reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest`.

## Result

The raw `HRDv` scan reproduced the S00/S01b selected-pulse table exactly: **640,737 rows**, count delta **0**, gzip sha match `True`, and decompressed CSV sha match `True`.

| Check | Reference | Rebuilt | Pass |
|---|---:|---:|---|
| data rows | 640737 | 640737 | True |
| gzip sha256 | `648c32d0109f` | `648c32d0109f` | True |
| content sha256 | `6b5b965babbf` | `6b5b965babbf` | True |
| run/stave counts | S01b table | rebuilt table | True |

The match depends on preserving the S01b gzip header timestamp and original filename; `table_hash_comparison.csv` records both the byte hash and the decompressed-content hash.

## Reproduction Gate

The selector is the S00c checked rule: B2/B4/B6/B8 even channels, median baseline from samples 0-3, and `max(waveform - baseline) > 1000 ADC`. All configured S00/S01b count checks passed with zero tolerance.

| quantity                                      |   expected |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses                 |     640737 |       640737 |       0 |           0 | True   |
| sample_i_calib events with selected pulse     |     239559 |       239559 |       0 |           0 | True   |
| sample_i_calib selected pulses                |     248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis events with selected pulse  |     243133 |       243133 |       0 |           0 | True   |
| sample_i_analysis selected pulses             |     252266 |       252266 |       0 |           0 | True   |
| sample_i_analysis B2 selected pulses          |     241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4 selected pulses          |       6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6 selected pulses          |       3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8 selected pulses          |       1299 |         1299 |       0 |           0 | True   |
| sample_ii_calib events with selected pulse    |      12103 |        12103 |       0 |           0 | True   |
| sample_ii_calib selected pulses               |      14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis events with selected pulse |      89807 |        89807 |       0 |           0 | True   |
| sample_ii_analysis selected pulses            |     125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2 selected pulses         |      88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4 selected pulses         |      21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6 selected pulses         |      11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8 selected pulses         |       4506 |         4506 |       0 |           0 | True   |

## Held-Out Methods

Held-out runs were `57,65`. CIs bootstrap held-out runs, not rows.

| Method | Held-out accuracy [95% CI] | Notes |
|---|---:|---|
| Traditional median-first-four gate | 1.000000 [1.000000, 1.000000] | Production rule; exact by definition. |
| Dynamic-range comparator | 0.818108 [0.736509, 0.900812] | Strong alternate threshold semantics. |
| ML logistic raw summaries | 0.980009 [0.979603, 0.980410] | GroupKFold by run; excludes `median_amp`, run, evt, and labels. |

ML is not a production replacement here. The deterministic selector is the table definition, so the correct outcome is a tie or ML loss against the exact rule.

## Leakage Audit

The honest ML score is high because waveform maxima, minima, and pretrigger summaries approximate the same threshold algebra, so leakage checks were run explicitly. Train/test run overlap is zero; the leaky `median_amp` sentinel reaches the expected near-perfect score; shuffled-label training falls to 0.201 accuracy.

| check                                      |    value | pass   | notes                                                                                           |
|:-------------------------------------------|---------:|:-------|:------------------------------------------------------------------------------------------------|
| train_test_run_overlap                     | 0        | True   | Split is by run; heldout runs are 57,65.                                                        |
| honest_feature_excludes_threshold_variable | 1        | True   | Honest ML features exclude median_amp, run, evt, event order, and labels.                       |
| leaky_sentinel_accuracy                    | 0.996862 | True   | Including median_amp should nearly reproduce the deterministic threshold; ROC AUC was 0.999980. |
| shuffled_label_accuracy                    | 0.2013   | True   | Randomized training labels should not reproduce the gate.                                       |

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `s00_selected_b_pulses.csv.gz`, `table_hash_comparison.csv`, `run_stave_count_comparison.csv`, `count_match_table.csv`, `heldout_benchmark.csv`, `heldout_benchmark_by_run.csv`, `ml_group_cv_scan.csv`, `leakage_checks.csv`, and `ml_sample_by_run.csv` are in this report directory.

Runtime: 552.9 s on `billy`.
