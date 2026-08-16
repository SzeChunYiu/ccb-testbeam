# Real-data CFD residual-visualization audit

## Scope

This focused audit reviews the residual-histogram evidence in open PR #939. Remote
`main` was `0f7a8e50960d01156ea87cac435f6e25925cd1d9` at run start. The reviewed PR head is
`ce81f22ef57c5db0b658737c0d9ced4c7fc69949`.

Reviewed artifacts:

- `scripts/real_data_cfd_timing.py`, Git blob
  `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`;
- `reports/real_data_cfd_timing/result.json`, Git blob
  `debc5c45d84a210f8425bab5c9f87d8b61fd279b`;
- the existing event-identity audit for the same PR;
- the reused `scripts/s02_timing_pickoff.py` definitions of `sigma68`, bootstrap,
  core fitting, and residual metrics.

Policy:

`REAL_DATA_CFD_RESIDUAL_PLOTS_MUST_COVER_THE_REPORTED_DISTRIBUTION`

The version-controlled fixtures retain the exact relevant source and result records
observed through the connector. They are deliberately labelled as relevant copies,
not as full PR checkout or raw ROOT evidence.

## Confirmed visualization defect

The residual plotting path passes the uncentered residual vector `v` to
`ax.hist(...)` with a fixed visible range of `[-10, 10] ns`. The legend reports
`sigma68(v)` from the full vector. Values outside the range are silently omitted by
the histogram, so the plotted support and the labelled statistic are different.

The result bundle reports the following medians and robust widths for the two methods
actually plotted:

| sample | method | n | median (ns) | sigma68 (ns) |
|---|---|---:|---:|---:|
| Sample II | CFD10 | 1888 | 59.60530122976422 | 0.8985129399585929 |
| Sample II | CFD20 | 1888 | 63.55902020874973 | 15.433838062158472 |
| task runs | CFD10 | 675 | -31.827483483483483 | 3.5480843306636647 |
| task runs | CFD20 | 675 | -28.576323232323233 | 6.72995931053074 |

Every median is outside the fixed display window.

## Conservative coverage calculation

The reused metric defines:

`σ68 = (q84 - q16) / 2`.

Because `q16 <= median <= q84`:

- `q16 >= median - 2*σ68`;
- `q84 <= median + 2*σ68`.

The exact result records therefore imply:

| sample | method | conservative q16 lower bound (ns) | conservative q84 upper bound (ns) | consequence |
|---|---|---:|---:|---|
| Sample II | CFD10 | 57.80827534984704 | 61.40232710968141 | q16 is above +10 ns |
| Sample II | CFD20 | 32.691344084432785 | 94.42669633306667 | q16 is above +10 ns |
| task runs | CFD10 | -38.923652144810816 | -24.731314822156154 | q84 is below -10 ns |
| task runs | CFD20 | -42.03624185338471 | -15.116404611261753 | q84 is below -10 ns |

Thus, for every plotted distribution, at least 84% of events are guaranteed to lie
outside the displayed histogram window from the reported median and sigma68 alone.
No assumption about Gaussianity or access to the raw residual vector is needed.

The fixed-window PNGs therefore cannot visually demonstrate the labelled robust
widths. They show, at most, a remote tail subset while using full-distribution labels.
This is a visualization/provenance defect; it does not establish that the numerical
widths themselves are false.

## Better method

Before the residual figures can support a scientific timing claim, the producer should:

1. use collision-safe `(run, event_id)` keys as required by `AUD-TIMING-001`;
2. center each residual vector on a documented estimator, preferably its median, before
   a fixed deviation-window plot, or choose a data-driven range covering the full vector;
3. record total, displayed, underflow, and overflow counts for each method;
4. state whether axes show raw residual, median-centered deviation, or calibrated delay;
5. overlay the exact median, q16, q84, and tail definition used by the table;
6. regenerate both residual PNGs from immutable ROOT inputs and retain source/result/
   figure hashes plus the exact generation command.

A useful two-panel alternative is a full-range histogram for completeness plus a
median-centered core inset. The full-range panel exposes offsets and tails; the inset
can display the sub-nanosecond core without silently removing most events.

## Audit result

The current contract returns `FLAWED` with six findings:

- one fixed uncentered `[-10, 10] ns` histogram finding;
- four findings that at least 84% of the labelled distributions are guaranteed outside
  the visible window;
- one finding that the legend statistic and histogram use different support.

Machine-readable and visual evidence:

- `docs/validation/real_data_cfd_residual_visualization_validation.json`;
- `docs/validation/real_data_cfd_residual_visualization.svg`.

The SVG is software/visualization evidence, not detector timing data.

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

The current relevant fixture returned exit status 1 (`FLAWED`) with six findings. A
median-centered fixture and a dynamic-range fixture both returned `VALIDATED` with
zero findings. Duplicate method records, invalid UTF-8, and input/output aliases fail
closed. Injected JSON replacement failure preserves the prior file and removes the
temporary file. JSON and SVG parsing passed. Changed Python lines are at most 100
characters.

Local validation environment: Python 3.13.5, pytest 9.0.2.

## Scientific and delivery boundary

This audit does not reprocess ROOT bytes and does not validate event identity, the
empirical channel map, baseline subtraction, first-crossing CFD, in-time selection,
bootstrap coverage, single-stave `pair/sqrt(2)` interpretation, timing resolution, or
canonical claim `CL-002`.

PR #939 remains open, non-mergeable, and without attached status checks. The PR must
not be merged on the basis of the existing residual figures. The event-identity defect
from `AUD-TIMING-001` also remains unresolved in the PR source.
