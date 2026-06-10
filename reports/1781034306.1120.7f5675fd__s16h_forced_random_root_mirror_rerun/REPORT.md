# S16h: forced/random HRD pedestal ROOT mirror and non-fallback S16g rerun gate

- **Ticket:** `1781034306.1120.7f5675fd`
- **Author:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `7207c1c707c2a8f6e70750b6d75bbb0502af363b`
- **Config:** `configs/s16h_1781034306_1120_7f5675fd_forced_random_root_mirror_rerun.json`

## Abstract

This ticket asked to add or mirror the actual forced/random HRD pedestal ROOT
files and rerun S16g without the pre-trigger fallback. I treated the requested
ROOT sample as a hard prerequisite rather than silently substituting the older
quiet-proxy benchmark. The mounted data were rescanned from raw `h101/HRDv`,
the three available raw archive zips were inventoried member-by-member, and the
ROOT trigger metadata were inspected for direct non-beam B-stack rows. The raw
selected-pulse anchor reproduces exactly (`640737` B-stave pulses), but no
forced/random/pedestal ROOT source and no `TRIGGER != 1` B-stack rows are
visible. Therefore the non-fallback S16g truth rerun is blocked in this
workspace state. For continuity only, the prior run-held-out S16g proxy
benchmark is summarized and clearly labeled as proxy context.

## 1. Reproduction Gate

For run \(r\), B-stack stave channel \(c\in\{B2,B4,B6,B8\}\), and sample
\(t\), the pedestal and amplitude are

\[
p_{irc} = \operatorname{median}(x_{irc0},x_{irc1},x_{irc2},x_{irc3}),
\qquad
A_{irc} = \max_t(x_{irct} - p_{irc}).
\]

The selected-pulse count is \(\sum_{irc}\mathbf{1}[A_{irc}>1000]\), read
directly from `data/root/root/hrdb_run_NNNN.root`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Acquisition and Mirror Audit

The acquisition predicate required either a strict forced/random/pedestal/no-
pulse token in a ROOT/archive path or direct ROOT metadata rows with
`TRIGGER != 1`. This is intentionally conservative: generic trigger wording is
not enough to create a no-pulse truth label.

| quantity | value |
|---|---:|
| filesystem/archive rows audited | 438 |
| filesystem forced/random token hits | 0 |
| strict filesystem ROOT/archive candidates | 0 |
| raw zip members audited | 217 |
| strict raw-archive ROOT/archive candidates | 0 |
| direct non-beam B-stack rows | 0 |

ROOT trigger summary:

| stack   |   files |   entries |   non_beam_trigger_entries |   files_with_tag_like_branch |
|:--------|--------:|----------:|---------------------------:|-----------------------------:|
| hrda    |      57 |   1652508 |                          0 |                            0 |
| hrdb    |      53 |   1649802 |                          0 |                            0 |

The complete inventories are `file_archive_inventory.csv`,
`raw_archive_member_inventory.csv`, `root_trigger_branch_audit.csv`, and
`direct_nonbeam_entries.csv`.

## 3. Non-Fallback S16g Rerun Gate

A direct S16g pedestal benchmark needs labels

\[
y_i = \mathbf{1}[\mathrm{event}\ i\ \mathrm{is\ forced/random/no\ pulse}],
\]

or an equivalent non-beam trigger value. In this mounted mirror,

\[
\sum_i \mathbf{1}[\mathrm{TRIGGER}_i \ne 1] = 0.
\]

Consequently the direct estimator residuals, confidence intervals, and winner
are not statistically defined. The script did not enter the pre-trigger
fallback path. The machine-readable direct result is
`direct_s16g_nonfallback.status = blocked_missing_truth_root` in `result.json`.

## 4. Method Identifiability

The requested method families are all recorded below. For the direct endpoint,
ML/NN methods are not "beaten"; they are unidentifiable because there are zero
positive truth rows.

| method                             | family           | direct_truth_status              | direct_metric                   |   direct_value |   direct_ci_low |   direct_ci_high | proxy_context_metric           |   proxy_context_value |   proxy_context_ci_low |   proxy_context_ci_high |
|:-----------------------------------|:-----------------|:---------------------------------|:--------------------------------|---------------:|----------------:|-----------------:|:-------------------------------|----------------------:|-----------------------:|------------------------:|
| deterministic_source_trigger_audit | traditional      | not_identifiable_zero_truth_rows | forced/random pedestal residual |            nan |             nan |              nan | post-veto timing-tail fraction |             nan       |              nan       |               nan       |
| ridge                              | ml               | not_identifiable_zero_truth_rows | forced/random pedestal residual |            nan |             nan |              nan | post-veto timing-tail fraction |               0.00863 |                0.00445 |                 0.01196 |
| gradient_boosted_trees             | ml               | not_identifiable_zero_truth_rows | forced/random pedestal residual |            nan |             nan |              nan | post-veto timing-tail fraction |               0.00818 |                0.00495 |                 0.01084 |
| mlp                                | ml               | not_identifiable_zero_truth_rows | forced/random pedestal residual |            nan |             nan |              nan | post-veto timing-tail fraction |               0.00874 |                0.00528 |                 0.01143 |
| 1d_cnn                             | nn               | not_identifiable_zero_truth_rows | forced/random pedestal residual |            nan |             nan |              nan | post-veto timing-tail fraction |               0.00818 |                0.00406 |                 0.01130 |
| siamese_cnn_meta                   | new_architecture | not_identifiable_zero_truth_rows | forced/random pedestal residual |            nan |             nan |              nan | post-veto timing-tail fraction |               0.00826 |                0.00456 |                 0.01158 |

## 5. Proxy Context Only

The following table is copied from the prior S16g proxy benchmark
`reports/1781033528.1397.05213c6c__s16g_forced_random_truth_benchmark`. It used leave-one-run-out splits by
Sample-II run with run/event bootstrap CIs and compared a strong traditional
quantile veto against ridge, gradient-boosted trees, MLP, 1D-CNN, and the
pair-symmetric `siamese_cnn_meta` architecture. It is not a direct electronics
pedestal truth result.

| method                 | efficiency_95ci         | tail_capture_95ci       | post_veto_tail_95ci     | sigma68_after_ns_95ci   | auc_95ci             | ap_95ci              |
|:-----------------------|:------------------------|:------------------------|:------------------------|:------------------------|:---------------------|:---------------------|
| gradient_boosted_trees | 0.8965 [0.8862, 0.9054] | 0.5172 [0.4019, 0.6161] | 0.0082 [0.0049, 0.0108] | 1.626 [1.570, 1.669]    | 0.747 [0.686, 0.793] | 0.248 [0.147, 0.346] |
| cnn1d                  | 0.9067 [0.8816, 0.9348] | 0.5115 [0.3976, 0.6294] | 0.0082 [0.0041, 0.0113] | 1.606 [1.545, 1.682]    | 0.722 [0.658, 0.791] | 0.322 [0.202, 0.481] |
| siamese_cnn_meta       | 0.8983 [0.8822, 0.9126] | 0.5115 [0.3865, 0.6500] | 0.0083 [0.0046, 0.0116] | 1.607 [1.558, 1.670]    | 0.742 [0.661, 0.808] | 0.309 [0.209, 0.433] |
| ridge                  | 0.8995 [0.8893, 0.9111] | 0.4885 [0.3547, 0.6658] | 0.0086 [0.0044, 0.0120] | 1.561 [1.520, 1.618]    | 0.732 [0.646, 0.835] | 0.149 [0.074, 0.273] |
| mlp                    | 0.8985 [0.8842, 0.9118] | 0.4828 [0.4070, 0.6206] | 0.0087 [0.0053, 0.0114] | 1.646 [1.584, 1.699]    | 0.712 [0.652, 0.793] | 0.248 [0.149, 0.361] |
| traditional_quantile   | 0.8997 [0.8807, 0.9175] | 0.3161 [0.2415, 0.4227] | 0.0115 [0.0071, 0.0147] | 1.565 [1.517, 1.608]    | 0.701 [0.656, 0.763] | 0.051 [0.034, 0.085] |

Proxy-context winner: **gradient_boosted_trees**, by lowest
held-out post-veto proxy tail fraction subject to the fixed efficiency rule.
Direct-truth winner: **none_no_direct_truth_root**.

## 6. Leakage Checks

| check                                                               | value                | pass   |
|:--------------------------------------------------------------------|:---------------------|:-------|
| loro_runs_match_config                                              | 58,59,60,61,62,63,65 | True   |
| train_heldout_event_id_overlap_max                                  | 0                    | True   |
| features_exclude_run_event_residual_labels                          | nan                  | True   |
| all_predictions_finite                                              | 137520               | True   |
| one_row_per_method_fold_shuffled_state                              | 84                   | True   |
| cnn1d_actual_tail_capture_ge_shuffled_proxy_median                  | 0.49122807017543857  | True   |
| gradient_boosted_trees_actual_tail_capture_ge_shuffled_proxy_median | 0.40350877192982454  | True   |
| mlp_actual_tail_capture_ge_shuffled_proxy_median                    | 0.34782608695652173  | True   |
| ridge_actual_tail_capture_ge_shuffled_proxy_median                  | 0.3684210526315789   | True   |
| siamese_cnn_meta_actual_tail_capture_ge_shuffled_proxy_median       | 0.30434782608695654  | True   |
| traditional_quantile_actual_tail_capture_ge_shuffled_proxy_median   | 0.19298245614035087  | True   |

## 7. Systematics and Caveats

- The result is an absence-in-mounted-mirrors statement. It does not prove the
  DAQ never recorded forced/random pedestal triggers.
- The available `h101` ROOT files appear beam-trigger only. If filtering
  occurred before `root.zip` production, it is upstream of the visible data.
- The raw count reproduction verifies the audited B-stack population but cannot
  manufacture no-pulse truth labels.
- Proxy timing-tail labels are useful diagnostics but are not electronics
  pedestal truth; this report keeps them separate from the blocked direct
  endpoint.
- The accidental appended ticket id recorded for this run is
  `1781112571.447.099f56ef`; no additional follow-up was appended
  by this script.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781034306_1120_7f5675fd_forced_random_root_mirror_rerun.py \
  --config configs/s16h_1781034306_1120_7f5675fd_forced_random_root_mirror_rerun.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `reproduction_match_table.csv`,
`root_trigger_branch_audit.csv`, `file_archive_inventory.csv`,
`raw_archive_member_inventory.csv`, `direct_nonbeam_entries.csv`,
`direct_method_identifiability.csv`, and `proxy_context_benchmark.csv`.
