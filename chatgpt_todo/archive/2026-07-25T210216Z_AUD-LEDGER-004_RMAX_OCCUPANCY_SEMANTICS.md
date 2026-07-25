# AUD-LEDGER-004 — Data-side Rmax occupancy semantics

- **Session stamp:** `2026-07-25T210216Z`
- **Initial remote main:** `5f4847036ab6d3ee8fb268f9ed96abc36852bbc4`
- **Owner:** scheduled scientific-review session
- **Status:** `VALIDATED` audit gate; scientific claim `BLOCKED`
- **Policy:** `OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`

## Reviewed repository state

- `docs/claim_ledger.csv` blob `83238de4b244b741bd2227986455edf04bff3265`
- `scripts/studies/data_side_real_beam.py` blob
  `22a86dd5c5c8fa9f993e501abd426791034ac16c`
- `reports/studies/data_side/REPORT.md` blob
  `daf9ba94b66eac6988f748597fa0fae799f6aea4`
- existing Rmax quarantine validator and its MV5 evidence contract
- exact `CL-011` S10b estimand and its data-only boundary
- repository history, open PR state, and PR #868 disposition

## Confirmed defect

The data-side study measured 640,737 selected B-stave pulses over 584,602 composite
`(run,eventno)` keys, giving mean selected multiplicity `1.0960225931488432`. This is a
descriptive selected-pulse multiplicity. It does not measure run exposure, event-arrival
rate, trigger live time, luminosity, or a maximum acceptable pile-up mean.

The producer nevertheless assigned `mu_max=0.38`, assumed `tau_eff=130 ns`, calculated
`2.923076923076923 MHz`, called it data-derived, and said measured occupancy grounded the
convention. The `CL-010` row then published `2.92 MHz`, added unsupported `0.10` and
`0.20 MHz` components, changed status to `DONE_DATA_ONLY`, pointed to the data-side study,
and removed blocker `S-STAT-003`.

The exact S10b `CL-011` estimand is `124.79018394263471 ns`. Applying the same legacy
`0.38` convention gives `3.045111305987686 MHz`; this remains a model sensitivity rather
than an empirical absolute rate. The former 130 ns choice is lower by
`0.12203438291076338 MHz` or `4.007550813357915%`.

## Delivered files

- `tools/audit/audit_data_side_rmax_semantics.py`
- `tests/test_audit_data_side_rmax_semantics.py`
- `tools/audit/render_data_side_rmax_semantics_evidence.py`
- `docs/validation/data_side_rmax_semantics_validation.json`
- `docs/validation/data_side_rmax_semantics.svg`
- `docs/validation/data_side_rmax_semantics_audit.md`
- this immutable archive

## Validation

```text
python -m py_compile \
  tools/audit/audit_data_side_rmax_semantics.py \
  tests/test_audit_data_side_rmax_semantics.py \
  tools/audit/render_data_side_rmax_semantics_evidence.py

pytest -q tests/test_audit_data_side_rmax_semantics.py
6 passed in 0.03s
```

- current-like executable fixture: `FLAWED`, 34 findings
- corrected contract fixture: `VALIDATED`, zero findings
- exact-tau mutation: rejected
- duplicate `CL-010`: controlled input error
- invalid UTF-8: controlled status 2
- destructive output alias: rejected
- JSON parse: PASS
- SVG XML parse: PASS
- maximum changed Python line length: 93

## Acceptance boundary

No raw ROOT data were rerun. No absolute event rate, exposure, luminosity, pile-up
acceptance criterion, recovery ceiling, calibration, or detector-performance result was
produced. A later unit must remediate the producer, report, figure metadata, and `CL-010`
row together and require both Rmax validators to return zero findings.

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate matrices
were not replaced because only whole-file replacement was available while complete
append-only bytes were paged or truncated. This archive preserves the append-equivalent
record without overwriting unrelated provenance.
