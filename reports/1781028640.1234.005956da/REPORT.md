# S00d: S00c selector-count guard in CI

Ticket `1781028640.1234.005956da` asked to put the S00c raw selector-count regression on the pre-merge path so semantic drift in the median-first-four and dynamic-range selectors blocks merges.

## Reproduction First
The first operation in this ticket-specific run scanned the raw B-stack ROOT files under `data/root/root` and recomputed the S00c anchors from `HRDv` before any model benchmark:

| quantity                   |   expected |   reproduced |   delta |   tolerance | pass   |
|:---------------------------|-----------:|-------------:|--------:|------------:|:-------|
| median_first_four_selected |     640737 |       640737 |       0 |           0 | yes    |
| dynamic_range_selected     |     706373 |       706373 |       0 |           0 | yes    |
| dynamic_only               |      65636 |        65636 |       0 |           0 | yes    |
| median_only                |          0 |            0 |       0 |           0 | yes    |

The guard uses zero tolerance. Any nonzero delta in `median_first_four_selected`, `dynamic_range_selected`, `dynamic_only`, or `median_only` raises before report success.

## CI Wiring
- Guard script: `scripts/s00d_1781028640_1234_005956da_ci_premerge.py --guard-only`
- Workflow: `.github/workflows/s00c-selector-count-regression.yml` (present)
- Data path override for runners: `TESTBEAM_RAW_ROOT_DIR`

The guard-only mode intentionally performs just the raw ROOT count scan and exact anchor comparison; it does not rely on ML to pass.

## Traditional And ML Cross-Check
For continuity with S00c, the ticket also reran the full S00c benchmark with this ticket id. Whole-run bootstrap intervals summarize run-to-run stability:

| quantity                   |   observed_total |   run_bootstrap_ci_low |   run_bootstrap_ci_high |
|:---------------------------|-----------------:|-----------------------:|------------------------:|
| median_first_four_selected |           640737 |               526512   |                762928   |
| dynamic_range_selected     |           706373 |               591330   |                829247   |
| dynamic_only               |            65636 |                52951.6 |                 79561.6 |
| median_only                |                0 |                    0   |                     0   |

Held-out benchmark:

| method                              |   accuracy |   accuracy_ci_low |   accuracy_ci_high |   false_positive |   false_negative | notes                                                   |
|:------------------------------------|-----------:|------------------:|-------------------:|-----------------:|-----------------:|:--------------------------------------------------------|
| traditional median-first-four gate  |   1        |          1        |           1        |                0 |                0 | deterministic raw selector definition                   |
| dynamic-range selector              |   0.985446 |          0.984998 |           0.985866 |             4058 |                0 | intentional semantic-change comparator                  |
| ML logistic honest raw summaries    |   0.99773  |          0.99754  |           0.997898 |              554 |               79 | run-group CV selected C=10.0                            |
| ML leakage sentinel with median_amp |   0.999788 |          0.999731 |           0.999839 |               59 |                0 | contains a direct monotone transform of the target rule |

Held-out run-block accuracy intervals resample the two held-out runs as blocks:

| method                              |   n_heldout_runs |   mean_run_accuracy |   run_bootstrap_ci_low |   run_bootstrap_ci_high |   min_run_accuracy |   max_run_accuracy |
|:------------------------------------|-----------------:|--------------------:|-----------------------:|------------------------:|-------------------:|-------------------:|
| ML leakage sentinel with median_amp |                2 |            0.999795 |               0.999733 |                0.999856 |           0.999733 |           0.999856 |
| ML logistic honest raw summaries    |                2 |            0.997731 |               0.997716 |                0.997746 |           0.997716 |           0.997746 |
| dynamic-range selector              |                2 |            0.984602 |               0.976354 |                0.99285  |           0.976354 |           0.99285  |
| traditional median-first-four gate  |                2 |            1        |               1        |                1        |           1        |           1        |

The traditional median-first-four gate exactly reproduces the anchor on held-out records: accuracy `1.000000` with false positives `0` and false negatives `0`. The honest ML logistic model reaches `0.997730` accuracy with CI `[0.997540, 0.997898]`, but it is not used as the merge guard.

## Leakage Hunt
The deliberately leaky sentinel includes `median_amp`, a direct selector-rule feature, and reaches `0.999788` accuracy. That near-perfect result is treated as leakage evidence, not a valid generalization claim. The CI path therefore uses the deterministic raw-count guard only.
