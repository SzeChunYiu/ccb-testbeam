# Latest Handoff

## Session

- **UTC:** 2026-07-22T12:08:38Z
- **Task:** AUD-AMP-001 (PARTIAL)
- **Initial remote main:** `8bff3f834c9da713996d946de1b16f3777e433a4`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed engineering finding

Version 2.0.0 of `tools/audit/amplitude_convention_audit.py` classified only the first 40,000 rows by default. A physical convention could therefore change when the same table rows were reordered. Prefix order is not a detector property, so the default introduced hidden file-order dependence into a scientific classification.

A focused regression demonstrates the failure mode: the prefix `[100, 200]` is classified NET, while the complete table `[100, 200, 6700, 6800, 6900]` has a median in the ABSOLUTE band.

## Work pushed directly to main

The auditor is now version 2.1.0 and:

- evaluates the complete amplitude column by default;
- keeps `--max-rows N` only as an explicit prefix diagnostic;
- labels bounded scans `PREFIX_SAMPLE`;
- records `input_truncated`, `max_rows_requested`, and aggregate `n_partial`;
- emits `PREFIX_SAMPLE_ROW_ORDER_DEPENDENT` for every bounded scan;
- returns nonzero whenever any classified table is partial;
- preserves the existing provenance, ambiguity, baseline, skip, and read-error diagnostics.

Regression coverage was expanded in `tests/test_amplitude_convention_audit.py`.

Immutable session record:

- `chatgpt_todo/archive/2026-07-22T120838Z_AUD-AMP-001_FULL_TABLE_CLASSIFICATION.md`

## Validation

Exact temporary copies were syntax checked and executed:

```text
python -m py_compile /tmp/ccb_audit/tools/audit/amplitude_convention_audit.py /tmp/ccb_audit/tests/test_amplitude_convention_audit.py
python -m pytest /tmp/ccb_audit/tests/test_amplitude_convention_audit.py -q
7 passed in 0.19s
```

## Main progression

- `8bff3f834c9da713996d946de1b16f3777e433a4` — initial remote main.
- `3013c1eeba50de2c9df437da4d5b8ccf79ee0304` — `fix(audit): remove implicit prefix bias from amplitude classification`.
- `a1ce2a1d1908876e684eaf68673c2894759af652` — `test(audit): cover full-table amplitude classification`.
- `b443dd3e28291a232927df0332dde5d7eb79c544` — `docs(audit): archive full-table amplitude classification fix`.
- `2c19900c15d2fd6ee21ee072923b217a0bceda7f` — `docs(audit): record full-table amplitude audit task`.
- This handoff update is the final session commit and must be verified as remote `main`.

## Evidence boundary and blockers

- No real pulse table was available in this execution environment.
- The prior repository-recorded 17 ABSOLUTE / 2 NET result was not rerun with version 2.1.0.
- The exact convention of `reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz` remains unmeasured here.
- Historical A-002 stopping outputs remain quarantined.
- No corrected stopping counts, fractions, CSV, or plot are claimed.

## Acceptance status

- Full-table default and partial-mode rejection: VALIDATED on synthetic regression.
- Provenance/error/ambiguity handling: VALIDATED on synthetic regression.
- Prior 19-table corpus classification: repository-recorded only; rerun required with version 2.1.0 and no `--max-rows`.
- A-002 source-table convention: BLOCKED pending exact-table measurement.
- Corrected A-002 real-data artifacts: BLOCKED.

## Next action

Run version 2.1.0 against the exact A-002 source table and the prior 19-table corpus without `--max-rows`, commit the full-table JSON outputs, and review every error or AMBIGUOUS record. Only then pass the measured convention explicitly to `scripts/single_stave/deltaE_E_data_bridge.py` and regenerate the quarantined A-002 JSON, CSV, and figure while enforcing composite-key and stopping-bin cardinality invariants.
