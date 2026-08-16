# Real-data CFD timing event-identity audit

## Scope

This focused audit reviews the event-pairing contract in open PR #939. Remote `main`
was `a8c446732e9a73d6880b313939868162ec4e2d74` before this audit wrote files. The reviewed source is
`scripts/real_data_cfd_timing.py`, head
`ce81f22ef57c5db0b658737c0d9ced4c7fc69949`, Git blob
`ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`.

Policy:

`REAL_DATA_CFD_EVENTS_MUST_USE_RUN_AND_EVENT_ID_TOGETHER`

The review concerns software identity and provenance. It does not validate the raw ROOT bytes,
channel map, waveform calibration, CFD estimator, in-time selection efficiency, timing resolution,
or canonical claim `CL-002`.

## Confirmed source-contract defect

`load_waveforms` retains both `run` and `event_id` for every selected pulse. The same source later:

1. pivots aligned peak samples with `index="event_id"` in `select_in_time`;
2. reapplies accepted keys with `df["event_id"].isin(keep)`;
3. pivots corrected pair times with `index="event_id"` in `pair_analysis`;
4. repeats an event-id-only pivot in the residual plotting path.

For multi-run inputs, `EVENTNO` must therefore be treated as run-local unless exact data provenance
proves global uniqueness. Dropping `run` permits two failure modes:

- a stave pulse from one run can be paired with a different stave pulse from another run when their
  run-local event numbers coincide;
- two legitimate complete pairs with the same run-local event number can make `pandas.pivot` abort
  because the event-id/stave coordinates are duplicated.

## Independent behavioral controls

The audit uses two synthetic controls.

### False cross-run pair

Input rows:

| run | event_id | stave |
|---:|---:|---|
| 58 | 7 | B6 |
| 59 | 7 | B8 |

The current event-id-only contract creates one apparent B6–B8 pair and selects both rows. The
composite `(run, event_id)` contract creates zero pairs and selects zero rows.

### Duplicate run-local event number

Two complete B6–B8 pairs are supplied, one in run 58 and one in run 59, both with `event_id=9`.
The current event-id-only pivot raises `ValueError`; the composite contract retains two valid pairs.

These controls establish the software failure mode. They do not prove that either collision occurred
in the retained production sample because the exact per-run `EVENTNO` values were unavailable here.

## Audit result

The connector-inspected relevant source copy returns `FLAWED` with six findings:

- three `RUN_DROPPED_FROM_PIVOT_KEY` findings;
- one `RUN_DROPPED_FROM_SELECTION_FILTER` finding;
- `SYNTHETIC_FALSE_CROSS_RUN_PAIR`;
- `RUN_LOCAL_EVENT_ID_COLLISION_CAN_ABORT`.

Machine-readable evidence:

- `docs/validation/real_data_cfd_event_identity_validation.json`
- `docs/validation/real_data_cfd_event_identity.svg`

The SVG is synthetic software/provenance evidence, not detector timing data.

## Required remediation before scientific acceptance

The producer should:

1. define one canonical event key, `EVENT_KEY = ["run", "event_id"]`;
2. use that key in every selection, pivot, merge, residual, plot, count, and output table;
3. reject duplicate `(run, event_id, stave)` rows before pivoting;
4. report per-run input paths, byte counts, SHA-256 hashes, tree name, entry counts, and exact key
   cardinalities before and after every selection;
5. regenerate all JSON, Markdown, and figures from immutable ROOT bytes;
6. rerun the timing analysis and compare event counts and widths against the current artifacts;
7. keep the single-stave `pair/sqrt(2)` interpretation conditional on equal, independent stave
   resolutions and negligible correlated jitter.

Until then, the reported 1,888 selected pairs and 0.899 ns pair width are not independently
content-addressed against a collision-safe event key. This audit does not assert that the numerical
values are false; it establishes that the current source cannot prove their event identity.

## Validation

```text
python -m py_compile \
  tools/audit/audit_real_data_cfd_event_identity.py \
  tests/test_audit_real_data_cfd_event_identity.py \
  tools/audit/render_real_data_cfd_event_identity_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_real_data_cfd_event_identity.py

6 passed in 0.06s
```

The expected current-like audit exit was 1 (`FLAWED`). A corrected composite-key fixture returned
`VALIDATED` with zero findings. Invalid UTF-8 and source/output aliasing failed closed. Injected
replacement failure preserved the prior JSON and left no temporary file. JSON and SVG parsing
passed. Changed Python lines are at most 99 characters.

Local validation environment: Python 3.13.5, pandas 2.2.3, pytest 9.0.2.

## Limitations

The execution container could not resolve `github.com`, so the complete PR checkout and raw ROOT
files were not available. The local audit input is explicitly labelled
`CONNECTOR_INSPECTED_EXACT_RELEVANT_SOURCE_COPY`; the exact PR head and full source Git blob are
recorded separately. PR #939 had no attached commit status checks at inspection time and remains
open. No merge is authorized by this audit.
