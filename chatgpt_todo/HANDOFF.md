# Latest Handoff

## Session

- **UTC:** 2026-07-23T01:05:04Z
- **Task:** AUD-AMP-005 (PARTIAL)
- **Initial remote main:** `947df912016b97d7d21160c1f4e8f2b075c4cbda`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed scientific/provenance defect

`tools/audit/amplitude_convention_audit.py` v2.8.0 treated the existence of a hash-bound evidence record as sufficient for `physics_acceptance=ACCEPTABLE`. For evidence authorizing `ABSOLUTE`, this could pass even when the table lacked a unique pedestal-level column or had incomplete pedestal values, so the required subtraction could not be executed reproducibly. The aggregate gate also followed the heuristic convention rather than the evidence-authorized physics convention. Conversely, incomplete optional pedestal diagnostics could incorrectly reject a hash-bound `NET` table even though no subtraction is required.

## Work pushed directly to main

Version 2.9.0 makes the execution gate convention-specific:

- hash-bound `NET` evidence is accepted without requiring optional pedestal diagnostics and sets `physics_subtract_baseline_correct=false`;
- hash-bound `ABSOLUTE` evidence requires exactly one pedestal-level column;
- every finite amplitude row must have a finite pedestal value before `ABSOLUTE` is accepted;
- unresolved schema produces `BASELINE_SCHEMA_UNRESOLVED` and `HASH_BOUND_ABSOLUTE_WITHOUT_UNIQUE_BASELINE`;
- incomplete data produces `BASELINE_DATA_INVALID` and `HASH_BOUND_ABSOLUTE_WITH_INVALID_BASELINE_DATA`;
- `n_nonaccepted_physics_conventions` counts every classified table not in the `ACCEPTABLE` physics state and is included in the CLI failure gate;
- `n_invalid_baseline_data_tables` now follows physics acceptance, so optional incomplete pedestal diagnostics do not falsely reject an accepted `NET` convention.

Added regression coverage:

- `tests/test_amplitude_physics_baseline_gate.py`

Immutable session record:

- `chatgpt_todo/archive/2026-07-23T010504Z_AUD-AMP-005_PHYSICS_BASELINE_GATE.md`

## Validation

Executed on exact local reconstructions:

```text
python -m py_compile tools/audit/amplitude_convention_audit.py tests/test_amplitude_physics_baseline_gate.py
python -m pytest tests/test_amplitude_physics_baseline_gate.py -q
3 passed in 0.04s
```

The focused regression covers missing pedestal schema for hash-bound `ABSOLUTE`, incomplete pedestal data for hash-bound `ABSOLUTE`, and an accepted hash-bound `NET` table with incomplete optional pedestal diagnostics.

## Main progression

- `947df912016b97d7d21160c1f4e8f2b075c4cbda` — initial remote main.
- `926b24f56b696249c94ecadd193131f433efbf97` — `fix(audit): gate absolute evidence on executable pedestal data`.
- `138f763679f172feab45c3598ff6c46902bd19cc` — `test(audit): cover physics pedestal acceptance gate`.
- `2eeb00b660fa181b60a6381327de9880a0ac7eda` — `docs(audit): archive physics baseline execution gate`.
- `3e75fc9e77624044586fd28c922fa7e6f30fb746` — `docs(audit): claim physics baseline execution gate`.
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- No real pulse table or exact A-002 source table was available.
- The historical amplitude corpus was not rerun.
- No amplitude convention, stopping count, stopping fraction, event CSV, DeltaE-E plot, calibration, or scientific numerical result was regenerated.
- Historical A-002 outputs remain quarantined.
- A direct clone failed because this runtime could not resolve `github.com`; authenticated connector writes were used.
- The complete repository test suite and CI were not run.
- `SESSION_LOG.md` was not replaced because safe append semantics were unavailable; the immutable archive preserves the complete run.

## Acceptance status

- Physics baseline execution gate: VALIDATED by focused synthetic regression.
- Real-table amplitude convention: BLOCKED on exact data access and reviewed evidence.
- A-002 regenerated outputs: BLOCKED.

## Next action

Hash the exact A-002 table and trace its producer/schema provenance. For an `ABSOLUTE` evidence record, require one unique pedestal-level column and complete finite pedestal coverage before passing the convention to `scripts/single_stave/deltaE_E_data_bridge.py`. Run v2.9.0 without `--max-rows`, review every non-acceptable physics state and malformed-value warning, and regenerate the quarantined outputs only after all gates pass.
