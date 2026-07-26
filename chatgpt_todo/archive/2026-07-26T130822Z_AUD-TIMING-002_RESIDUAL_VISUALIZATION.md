# AUD-TIMING-002 — Real-data CFD residual visualization audit

## Session identity

- **Stamp:** `2026-07-26T130822Z`
- **Owner:** scheduled scientific-review session
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `0f7a8e50960d01156ea87cac435f6e25925cd1d9`
- **Reviewed PR:** #939, open and unmerged
- **Reviewed PR head:** `ce81f22ef57c5db0b658737c0d9ced4c7fc69949`
- **Reviewed source blob:** `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`
- **Reviewed result blob:** `debc5c45d84a210f8425bab5c9f87d8b61fd279b`
- **Policy:** `REAL_DATA_CFD_RESIDUAL_PLOTS_MUST_COVER_THE_REPORTED_DISTRIBUTION`

## Repository and concurrency review

At run start, `main` was the confirmed head above and had no attached combined status checks. The required coordination files were read before task selection. `AUD-TIMING-001` had already audited the PR's event-identity defect, so this run did not duplicate it. PR #868 was rechecked and remained closed, non-mergeable, unmerged, and untouched.

No concurrent `main` commit appeared before the focused audit writes. All delivered changes used sequential direct writes to `main`; no branch, pull request, force-push, or history rewrite was used.

## Confirmed visualization defect

The PR source constructs uncentered B6-B8 residual vector `v`, calls

```python
ax.hist(v, bins=80, range=(-10, 10), ...)
```

and labels the plot with `sigma68(v)` calculated from the full vector. Values outside `[-10,10] ns` are omitted by the histogram but retained by the label statistic.

The exact PR result records for the plotted methods are:

| sample | method | n | median (ns) | sigma68 (ns) |
|---|---|---:|---:|---:|
| Sample II | CFD10 | 1888 | 59.60530122976422 | 0.8985129399585929 |
| Sample II | CFD20 | 1888 | 63.55902020874973 | 15.433838062158472 |
| task runs | CFD10 | 675 | -31.827483483483483 | 3.5480843306636647 |
| task runs | CFD20 | 675 | -28.576323232323233 | 6.72995931053074 |

The reused metric defines `sigma68 = (q84-q16)/2`. Since `q16 <= median <= q84`, conservative bounds are `q16 >= median-2*sigma68` and `q84 <= median+2*sigma68`.

| sample | method | q16 lower bound (ns) | q84 upper bound (ns) | guaranteed consequence |
|---|---|---:|---:|---|
| Sample II | CFD10 | 57.80827534984704 | 61.40232710968141 | at least 84% above +10 ns |
| Sample II | CFD20 | 32.691344084432785 | 94.42669633306667 | at least 84% above +10 ns |
| task runs | CFD10 | -38.923652144810816 | -24.731314822156154 | at least 84% below -10 ns |
| task runs | CFD20 | -42.03624185338471 | -15.116404611261753 | at least 84% below -10 ns |

This result needs no Gaussian assumption and no raw residual vector. The current PNGs display, at most, remote tail subsets while attaching full-distribution labels. The audit does not assert that the numerical widths are false; it establishes that the figures cannot visually validate them.

## Better method and acceptance criteria

Before residual figures are scientific evidence, the producer must:

1. resolve `AUD-TIMING-001` by using `(run,event_id)` consistently;
2. center residuals on a documented location estimator before a fixed deviation plot, or choose a range that covers the full vector;
3. record total/displayed/underflow/overflow counts;
4. state whether the axis is raw residual, centered deviation, or calibrated delay;
5. overlay the exact median, q16, q84, and tail threshold used by reported metrics;
6. provide a full-range view plus an optional centered core inset;
7. regenerate from immutable ROOT inputs with paths, bytes, SHA-256, tree/entry counts, code commit, command, environment, seeds, output hashes, and limitations.

## Delivered files

- `tools/audit/audit_real_data_cfd_residual_visualization.py`
- `tests/test_audit_real_data_cfd_residual_visualization.py`
- `tools/audit/render_real_data_cfd_residual_visualization_evidence.py`
- `docs/validation/fixtures/pr939_real_data_cfd_timing_relevant.py`
- `docs/validation/fixtures/pr939_real_data_cfd_timing_result_subset.json`
- `docs/validation/real_data_cfd_residual_visualization_validation.json`
- `docs/validation/real_data_cfd_residual_visualization.svg`
- `docs/validation/real_data_cfd_residual_visualization_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this immutable archive record
- matching `chatgpt_todo/HANDOFF.md`

The fixtures are explicitly connector-inspected relevant copies, not a complete PR checkout or raw-data artifact.

## Validation

```text
python -m py_compile \
  tools/audit/audit_real_data_cfd_residual_visualization.py \
  tests/test_audit_real_data_cfd_residual_visualization.py \
  tools/audit/render_real_data_cfd_residual_visualization_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_real_data_cfd_residual_visualization.py

6 passed in 0.08s
```

Environment: Python 3.13.5, pytest 9.0.2.

The current fixture returned `FLAWED` with six findings. Median-centered and dynamic-range fixtures returned `VALIDATED` with zero findings. Duplicate method records, invalid UTF-8, and output aliases fail closed. Injected JSON replacement failure preserved the prior file and removed the temporary file. JSON and SVG parsing passed. Changed Python lines are at most 100 characters.

Implementation identity after delivery:

- auditor blob `41d92f8ceae38517bae28a65dc329769294f6a31`;
- focused-test blob `d684d4182a1f1bd4fb734acdcb79c949b8c48029`.

## Direct-main sequence before handoff

- `c85c249dabfe7bae3280bf886a6639db1f7f6877` — audit gate;
- `68e98a44608cb3c9f872f6e9b2af982957092f45` — focused regressions;
- `10d7ce773d6ecf5eed40d9361f7e5fdfe6b11d6b` — evidence renderer;
- `b02405ea9126c49d4130a9b28b2d199b4eef955a` — inspected source fixture;
- `a3f774d5f85904b42fde992c8ac19f97f86c02b9` — inspected result fixture;
- `0761e353958c80f3ff018ec82cf1c879f445ba3d` — validation JSON;
- `5a331ed835b378547fd92dbc999d104c157d7743` — SVG evidence;
- `963ef9175debe6258f264442c9cc9c55f8a86e71` — audit report;
- `70dcad8c9aa0d38f561d03ee411947b478efeb6e` — active-task completion.

GitHub contents writes returned successful direct-main commit SHAs rather than a conventional terminal `git push` transcript.

## Scientific and delivery boundary

The audit implementation and evidence are `VALIDATED / COMPLETE`. PR #939 residual visualization and broader timing acceptance remain `FLAWED / PARTIAL`. PR #939 must not be merged on the basis of the existing residual figures, and the prior event-identity blocker remains unresolved.

No ROOT bytes were reprocessed. No channel mapping, pedestal subtraction, CFD bias, in-time selection efficiency, bootstrap coverage, equal/independent-stave assumption, single-stave resolution, canonical `CL-002` claim, or detector-performance quantity was validated or changed.

Repository-wide pytest/ruff, the PR producer, full raw-data rerun, complete documentation/link inventory, and GitHub Actions were not run and are not claimed as passing.

`SESSION_LOG.md` was reviewed but not replaced in this run because the connector provides paged/truncated reads and whole-file replacement writes. A manual reconstruction could erase append-only provenance. This archive and the current handoff preserve the complete append-equivalent record without claiming that mandatory append succeeded.
