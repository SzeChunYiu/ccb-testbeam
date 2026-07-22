# AUD-AMP-001 — unresolved absolute-baseline acceptance gate

## Session

- UTC: 2026-07-22T17:01:05Z
- Initial remote `main`: `9033b4a0b8b69914451e5c44e8b4f7d6a3b8c78b`
- Repository: `SzeChunYiu/ccb-testbeam`
- Write target: direct to `main`

## Confirmed defect

Version 2.4.0 distinguished pedestal-level columns from dispersion columns, but the command-line acceptance gate did not fail when an `ABSOLUTE` table had no unique pedestal-level column. Such a table could therefore produce `subtract_baseline_correct=null` and a baseline warning while the process still exited zero.

For absolute-code amplitudes, the physically relevant net height requires a uniquely identified pedestal level. Missing or ambiguous pedestal provenance is unresolved evidence and must not pass the audit gate.

## Implementation

`tools/audit/amplitude_convention_audit.py` is now version 2.5.0 and records:

- `baseline_resolution=RESOLVED` for an absolute table with exactly one pedestal-level candidate;
- `baseline_resolution=MISSING` for an absolute table with no pedestal-level candidate;
- `baseline_resolution=AMBIGUOUS` for an absolute table with multiple pedestal-level candidates;
- `baseline_resolution=NOT_REQUIRED` for a net-amplitude table.

The aggregate JSON now includes `n_unresolved_absolute_baselines`, and the command returns nonzero whenever this count is positive.

## Regression evidence

Added `tests/test_amplitude_baseline_acceptance_gate.py` covering:

1. missing and multiple pedestal-level candidates both fail the aggregate gate;
2. one unique pedestal-level column passes;
3. a net-amplitude table does not require a pedestal column.

Executed on exact reconstructed source content before the GitHub write:

```text
python -m py_compile /tmp/ampgate/tools/audit/amplitude_convention_audit.py /tmp/ampgate/tests/test_amplitude_baseline_acceptance_gate.py
python -m pytest /tmp/ampgate/tests -q
3 passed in 0.07s
```

The direct local clone attempt failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and writes were used.

## Commits

- `e86c3a83baa16fadff1f9a72931884e9c1acd1a9` — `fix(audit): fail unresolved absolute-baseline gates`
- `6b85438abeb8e07df19e7ddfb6953aa8e8df4317` — `test(audit): cover unresolved absolute-baseline gates`
- `ef3bea361f15636f99547317406f12224d117c5f` — `docs(audit): record unresolved baseline acceptance task`

## Evidence boundary

No real pulse table was accessed. The prior amplitude-table corpus, the exact A-002 source table, corrected stopping counts, CSV, and figure were not regenerated. Historical A-002 outputs remain quarantined.

## Next action

Run version 2.5.0 over the exact A-002 source table and prior corpus without `--max-rows`. Review every error, ambiguous convention, malformed/nonfinite warning, and unresolved absolute baseline. Only an absolute table with one measured pedestal-level field may be passed to baseline subtraction in the A-002 regeneration.
