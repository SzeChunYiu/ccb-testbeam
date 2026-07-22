# Latest Handoff

## Session

- **UTC:** 2026-07-22T23:07:00Z
- **Task:** AUD-AMP-003 (PARTIAL)
- **Initial remote main:** `c6b86c9a5253887b709c235766687a69ee322bc2`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed numerical/provenance defect

`tools/audit/amplitude_convention_audit.py` v2.6.0 treated one uniquely named pedestal-level column as sufficient evidence for an accepted amplitude convention. It did not require the column to contain usable finite pedestal values for the finite amplitude rows. An empty, malformed, or nonfinite `baseline_adc` column could therefore produce `convention_acceptance=ACCEPTABLE` and a subtraction decision despite having no valid pedestal data.

## Work pushed directly to main

Version 2.7.0 now:

- records `finite_amplitude_baseline_pairs`;
- records `finite_amplitude_rows_without_finite_baseline`;
- records `baseline_pair_coverage`;
- requires complete finite pedestal coverage for all finite amplitudes used in classification;
- sets `baseline_data_quality=INCOMPLETE` when coverage is incomplete;
- sets `convention_acceptance=BASELINE_DATA_INVALID`;
- withholds `subtract_baseline_correct`;
- emits `INCOMPLETE_BASELINE_FOR_FINITE_AMPLITUDES`;
- increments `n_invalid_baseline_data_tables` and returns nonzero.

Added `tests/test_amplitude_baseline_data_quality.py` covering empty, partial, and complete pedestal coverage.

Immutable session record:

- `chatgpt_todo/archive/2026-07-22T230700Z_AUD-AMP-003_BASELINE_DATA_QUALITY.md`

## Validation

Executed on exact temporary copies:

```text
python -m py_compile tools/audit/amplitude_convention_audit.py tests/test_amplitude_baseline_data_quality.py
python -m pytest tests/test_amplitude_baseline_data_quality.py -q
3 passed in 0.08s
```

Both target commands exited successfully. An unrelated spreadsheet-runtime warmup error was emitted after Python startup and did not affect the focused validation.

## Main progression

- `c6b86c9a5253887b709c235766687a69ee322bc2` — initial remote main.
- `1de58024d3a78525a299789c446e375e6cdd3f35` — `fix(audit): reject incomplete pedestal data`.
- `8fd5b6ff4bbd544b4da0baf0acff205ec2ebe3cb` — `test(audit): cover incomplete pedestal data gates`.
- `394a98bf45a64a398a3d3bb3d3eb62c13d5d215d` — `docs(audit): claim pedestal data-quality gate`.
- `450ced817fc44d11168f047018e7077388aec529` — `docs(audit): archive pedestal data-quality gate`.
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- No real pulse table or exact A-002 source table was available.
- The historical amplitude corpus was not rerun.
- No convention assignment, stopping count, stopping fraction, event CSV, DeltaE-E plot, calibration, or scientific numerical result was regenerated.
- Historical A-002 outputs remain quarantined.
- The complete repository test suite and CI were not run.
- `SESSION_LOG.md` was not replaced because the connector does not provide safe append semantics for the long append-only file; the immutable archive contains the complete session record.

## Acceptance status

- Baseline data-quality gate: VALIDATED by focused synthetic regression.
- Real-table amplitude convention: BLOCKED on exact data access and provenance.
- A-002 regenerated outputs: BLOCKED.

## Next action

Run v2.7.0 against the exact A-002 source table and historical corpus without `--max-rows`. Require complete finite pedestal coverage for any pedestal-anchored convention, review every unanchored, ambiguous, malformed, nonfinite, or incomplete-baseline record, and commit the provenance JSON before passing an explicit convention to `scripts/single_stave/deltaE_E_data_bridge.py`.
