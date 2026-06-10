# S16i: pre/post tagged-random ingest adaptive pedestal comparison

- **Ticket:** `1781034306.1188.0470572e`
- **Author:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `dcbb6a346363e6d1f5ea625254f62bffc9757d69`
- **Config:** `configs/s16i_1781034306_1188_0470572e_prepost_tagged_random_ingest.json`

## Abstract

S16i tests whether an apparent adaptive-pedestal zero-bias change can be
attributed to a new tagged-random/no-pulse ingest rather than to method changes.
The answer in this workspace is negative: the current B-stack raw ROOT hashes
match the pre-ingest S16g benchmark exactly, the current ROOT/archive audit
finds `0` strict forced/random ROOT/archive candidates, and direct non-beam
B-stack rows remain `0`.  The direct tagged-random pedestal endpoint is
therefore not statistically identifiable.  Under the byte-identical fallback
Sample-II leave-one-run-out proxy benchmark, the method ranking is unchanged
and the proxy winner remains **gradient_boosted_trees**.

## 1. Reproduction Gate

For run \(r\), B-stack stave \(c\in\{B2,B4,B6,B8\}\), and sample \(t\),
the raw-ROOT count uses

\[
p_{irc} = \operatorname{median}(x_{irc0},x_{irc1},x_{irc2},x_{irc3}),
\qquad
A_{irc} = \max_t(x_{irct} - p_{irc}).
\]

Selected pulses satisfy \(A_{irc}>1000\) ADC and are read directly from
`h101/HRDv` in `data/root/root/hrdb_run_NNNN.root`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The total selected B-stave pulse count reproduces exactly: `640737`.

## 2. Pre/Post Ingest Control

The primary S16i control is byte identity.  If the pre-ingest and current raw
ROOT hashes match, a downstream score change cannot be caused by tagged-random
data ingest.

| quantity                                     |   value |
|:---------------------------------------------|--------:|
| raw ROOT run hashes compared                 |      33 |
| raw ROOT run hashes matching pre-ingest S16g |      33 |
| strict forced/random ROOT/archive candidates |       0 |
| direct non-beam B-stack rows                 |       0 |

All compared run hashes match; the input population is unchanged.  The current
ROOT trigger audit is:

| stack   |   files |   entries |   non_beam_trigger_entries |   files_with_tag_like_branch |
|:--------|--------:|----------:|---------------------------:|-----------------------------:|
| hrda    |      57 |   1652508 |                          0 |                            0 |
| hrdb    |      53 |   1649802 |                          0 |                            0 |

The strict file/archive candidate table has no direct ROOT/archive hit:

_No rows._

## 3. Adaptive-Pedestal Context

The original S16 adaptive-pedestal validation used a leave-one-pretrigger-sample
target because tagged-random truth was unavailable.  For held-out runs 57 and
65, with the held-out sample excluded from each estimator, the adaptive
positivity-constrained pedestal was biased downward:

| method             | mean_bias_95ci_adc         | mae_95ci_adc            |
|:-------------------|:---------------------------|:------------------------|
| ml_hgbr_calibrated | -8.74 [-14.17, -2.61]      | 48.88 [43.82, 55.29]    |
| mean3              | -14.79 [-38.34, 11.42]     | 260.70 [236.25, 287.99] |
| median3            | -51.19 [-80.36, -20.93]    | 273.64 [244.24, 302.67] |
| adaptive_pc        | -310.69 [-347.59, -277.34] | 341.04 [300.45, 373.27] |

This is a pre-ingest physics-event proxy result, not a tagged-random electronics
pedestal result.  Since S16i finds no post-ingest tagged-random rows, the true
pre/post adaptive-pedestal bias difference
\[
\Delta b = b_\mathrm{post,tagged} - b_\mathrm{pre,tagged}
\]
is undefined rather than zero.  What is identifiable is the input-control
statement: no tagged-random ingest is visible in the current mirror.

## 4. Traditional and ML/NN Benchmark

For continuity, S16i carries forward the frozen S16g Sample-II leave-one-run-out
benchmark only because both raw inputs and benchmark artifacts are byte
controlled.  The proxy target is the post-veto timing-tail fraction
\[
\Pr(|r_i-m_{p(i)}|>5\,\mathrm{ns}\mid \mathrm{kept}),
\qquad
r_i=(t_a-x_a/v)-(t_b-x_b/v),
\]
with pair centers \(m_p\) fit on training runs only.

The strong traditional method is the pre-trigger empirical quantile envelope.
The ML/NN set is ridge, gradient-boosted trees, MLP, 1D-CNN, and the
pair-symmetric `siamese_cnn_meta` architecture.  All scalers, thresholds,
models, and pair centers are train-fold objects; held-out runs are never used
for fitting.

| method                 | efficiency_95ci         | tail_capture_95ci       | post_veto_tail_95ci     | sigma68_after_ns_95ci   | auc_95ci             | ap_95ci              |
|:-----------------------|:------------------------|:------------------------|:------------------------|:------------------------|:---------------------|:---------------------|
| traditional_quantile   | 0.8997 [0.8807, 0.9175] | 0.3161 [0.2415, 0.4227] | 0.0115 [0.0071, 0.0147] | 1.565 [1.517, 1.608]    | 0.701 [0.656, 0.763] | 0.051 [0.034, 0.085] |
| ridge                  | 0.8995 [0.8893, 0.9111] | 0.4885 [0.3547, 0.6658] | 0.0086 [0.0044, 0.0120] | 1.561 [1.520, 1.618]    | 0.732 [0.646, 0.835] | 0.149 [0.074, 0.273] |
| gradient_boosted_trees | 0.8965 [0.8862, 0.9054] | 0.5172 [0.4019, 0.6161] | 0.0082 [0.0049, 0.0108] | 1.626 [1.570, 1.669]    | 0.747 [0.686, 0.793] | 0.248 [0.147, 0.346] |
| mlp                    | 0.8985 [0.8842, 0.9118] | 0.4828 [0.4070, 0.6206] | 0.0087 [0.0053, 0.0114] | 1.646 [1.584, 1.699]    | 0.712 [0.652, 0.793] | 0.248 [0.149, 0.361] |
| 1d_cnn                 | 0.9067 [0.8816, 0.9348] | 0.5115 [0.3976, 0.6294] | 0.0082 [0.0041, 0.0113] | 1.606 [1.545, 1.682]    | 0.722 [0.658, 0.791] | 0.322 [0.202, 0.481] |
| siamese_cnn_meta       | 0.8983 [0.8822, 0.9126] | 0.5115 [0.3865, 0.6500] | 0.0083 [0.0046, 0.0116] | 1.607 [1.558, 1.670]    | 0.742 [0.661, 0.808] | 0.309 [0.209, 0.433] |

The direct tagged-random winner is **none** because there are no tagged-random
truth rows.  The proxy continuity winner is **gradient_boosted_trees**,
with held-out post-veto tail fraction
`0.0082`
[`0.0049`,
`0.0108`].

## 5. Leakage and Validity Checks

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

The key leakage control is run-level splitting.  The artifact-control checks
also require that the S16g head-to-head, fold-metric, leakage, and result files
used here are hashed in `artifact_sha256.csv`.

## 6. Systematics and Caveats

- Absence in the mounted mirror is not proof that the original DAQ never
  recorded forced/random pedestal triggers.
- The direct post-ingest adaptive-pedestal bias is not estimable until true
  tagged-random/no-pulse B-stack rows exist.
- The S16g proxy winner is a timing-tail-veto winner, not an electronics
  pedestal-truth winner.
- Identical hashes make the data-ingest explanation falsifiable here: no
  observed score or bias change can be attributed to a new ingest in this
  workspace state.
- Pair residuals are not independent at the event level; the inherited CIs use
  the S16g run/event bootstrap rather than naive row bootstrap.

## 7. Conclusion

S16i isolates the causal question requested by the ticket.  There is no visible
post-ingest tagged-random sample: current raw ROOT hashes are identical to the
S16g pre-ingest hashes, strict forced/random candidates are `0`, and direct
non-beam B-stack rows are `0`.  Therefore the direct adaptive-pedestal
pre/post tagged-random comparison is blocked, not won by any method.  Under the
unchanged LORO proxy benchmark, **gradient_boosted_trees** remains the
best method among the traditional quantile baseline, ridge, gradient-boosted
trees, MLP, 1D-CNN, and `siamese_cnn_meta`.

No novel follow-up ticket is appended from this run.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16i_1781034306_1188_0470572e_prepost_tagged_random_ingest.py \
  --config configs/s16i_1781034306_1188_0470572e_prepost_tagged_random_ingest.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `artifact_sha256.csv`, `hash_comparison.csv`,
`reproduction_match_table.csv`, `root_trigger_branch_audit.csv`,
`file_archive_inventory.csv`, `direct_nonbeam_entries.csv`,
`prepost_summary.csv`, `method_continuity.csv`, and
`pedestal_preingest_context.csv`.
