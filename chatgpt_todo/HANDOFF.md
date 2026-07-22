# Latest Handoff

## Session

- **UTC:** 2026-07-22T18:04:00Z
- **Task:** AUD-AMP-001 (PARTIAL)
- **Initial remote main:** `df73792f871073cf716c137ee0810717395a5abf`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed scientific-method finding

The historical 19-table amplitude audit is internally incompatible with the current raw-median thresholds. It labels several tables `ABSOLUTE` at medians 3096.5, 3122, 3191, and 3419 ADC, while version 2.5.0 labels medians at or below 3500 ADC as `NET`. Another historical table at 3803.5 ADC lies in the current `AMBIGUOUS` interval. Therefore, the raw `amplitude_adc` median does not uniquely identify physical convention.

A legacy column named only `amplitude_adc` must not be accepted as absolute-code or net-amplitude evidence without an independent pedestal-level anchor or separately documented schema provenance.

## Work pushed directly to main

`tools/audit/amplitude_convention_audit.py` is now version 2.6.0 and:

- records `convention_evidence=PEDESTAL_ANCHORED` only when exactly one pedestal-level column is available;
- records `RAW_MEDIAN_HEURISTIC` otherwise;
- records `convention_acceptance=UNANCHORED` for median-only labels;
- emits `UNANCHORED_AMPLITUDE_CONVENTION`;
- leaves `subtract_baseline_correct` null for unanchored labels, including apparent NET labels;
- aggregates `n_unanchored_conventions`;
- returns nonzero whenever any classified table is unanchored;
- preserves provenance hashes, complete-table default, prefix rejection, malformed/nonfinite rejection, ambiguity, explicit skips, and parser-error retention.

Added `tests/test_amplitude_convention_anchor_gate.py`.

Immutable session record:

- `chatgpt_todo/archive/2026-07-22T180400Z_AUD-AMP-001_UNANCHORED_CONVENTIONS.md`

## Validation

Exact reconstructed source and focused tests were executed before GitHub writes:

```text
python -m py_compile /tmp/amp26/tools/audit/amplitude_convention_audit.py /tmp/amp26/tests/test_amplitude_convention_anchor_gate.py
python -m pytest /tmp/amp26/tests -q
3 passed in 0.08s
```

The regression verifies that unanchored low-median and high-median labels both fail, while a table with one unique pedestal-level column can pass.

A direct clone attempt failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and writes were used.

## Main progression

- `df73792f871073cf716c137ee0810717395a5abf` — initial remote main.
- `c3f3f6ee6438f61474e8569cdfcd85f34509349e` — `fix(audit): reject unanchored amplitude conventions`.
- `a55a273d8780f62983f6894259f07334009fe249` — `test(audit): cover unanchored amplitude convention gate`.
- `e2236f45c001551f457d47850f0b17bd9a46b4d6` — `docs(audit): archive unanchored convention gate`.
- `9c5bfe45f5d7998205701c0a88d21498f7b1afae` — `docs(audit): record unanchored convention task`.
- This handoff update is the final session commit and must be verified as remote `main`.

## Evidence boundary and blockers

- No real pulse table was available.
- The prior 17 ABSOLUTE / 2 NET corpus result was not rerun and is now explicitly treated as repository-recorded heuristic output rather than accepted convention evidence.
- The exact amplitude and baseline schema of the A-002 source table remain unknown.
- Historical A-002 stopping outputs remain quarantined.
- No corrected stopping counts, fractions, CSV, or figure are claimed.
- The focused new test passed against the exact pushed source content; the complete repository test suite and CI were not run in this connector-only environment.

## Acceptance status

- Unanchored convention gate: VALIDATED on focused synthetic regression.
- Raw-median convention labels without pedestal anchor: NON-ACCEPTING by design.
- Historical corpus classification: requires rerun and independent anchors.
- A-002 source-table convention/schema: BLOCKED pending exact-table measurement.
- Corrected A-002 real-data artifacts: BLOCKED.

## Next action

Run version 2.6.0 over the exact A-002 source table and the prior corpus without `--max-rows`. For every unanchored record, obtain an explicit pedestal-level field, a schema contract, or producer-code evidence before accepting a convention. Commit the generated JSON with input hashes. Only then pass the measured convention explicitly to `scripts/single_stave/deltaE_E_data_bridge.py` and regenerate the quarantined A-002 JSON, CSV, and figure under the composite-key and stopping-bin cardinality invariants.
