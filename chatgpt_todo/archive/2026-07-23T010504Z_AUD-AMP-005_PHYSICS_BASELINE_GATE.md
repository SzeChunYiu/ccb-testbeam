# AUD-AMP-005 — Physics Baseline Execution Gate

## Session

- UTC: 2026-07-23T01:05:04Z
- Initial remote main: `947df912016b97d7d21160c1f4e8f2b075c4cbda`
- Target: direct to `main`
- Scope: reconcile hash-bound amplitude convention evidence with the pedestal data actually required to execute the authorized physics transformation.

## Confirmed defect

Version 2.8.0 set `physics_acceptance=ACCEPTABLE` whenever a SHA-256 keyed evidence record existed. For evidence authorizing `ABSOLUTE`, that could happen even when the table had no unique pedestal-level column or incomplete pedestal values. The final gate also counted unresolved baselines from the heuristic convention rather than the evidence-authorized physics convention. Conversely, incomplete optional pedestal diagnostics could incorrectly block a hash-bound `NET` convention, even though no subtraction is required.

## Correction

Version 2.9.0 separates convention authorization from transformation executability:

- hash-bound `NET` evidence is accepted without requiring an optional pedestal diagnostic and sets `physics_subtract_baseline_correct=false`;
- hash-bound `ABSOLUTE` evidence requires exactly one pedestal-level column and complete finite pedestal coverage for every finite amplitude row;
- missing or multiple pedestal candidates produce `BASELINE_SCHEMA_UNRESOLVED` and `HASH_BOUND_ABSOLUTE_WITHOUT_UNIQUE_BASELINE`;
- incomplete pedestal values produce `BASELINE_DATA_INVALID` and `HASH_BOUND_ABSOLUTE_WITH_INVALID_BASELINE_DATA`;
- `n_nonaccepted_physics_conventions` counts every classified table whose physics state is not `ACCEPTABLE` and is part of the process exit gate;
- the legacy `n_invalid_baseline_data_tables` aggregate now follows physics acceptance, so optional incomplete pedestal diagnostics do not reject an accepted `NET` convention.

## Validation

Exact local reconstruction commands:

```text
python -m py_compile tools/audit/amplitude_convention_audit.py tests/test_amplitude_physics_baseline_gate.py
python -m pytest tests/test_amplitude_physics_baseline_gate.py -q
```

Result:

```text
3 passed in 0.04s
```

Regression cases:

1. Hash-bound `ABSOLUTE` without a pedestal column is non-accepting.
2. Hash-bound `ABSOLUTE` with incomplete pedestal values is non-accepting.
3. Hash-bound `NET` remains accepting when an optional pedestal diagnostic is incomplete.

## Files

- `tools/audit/amplitude_convention_audit.py`
- `tests/test_amplitude_physics_baseline_gate.py`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`
- this immutable record

## Evidence boundary

No real pulse table or A-002 source input was available. No convention assignment, stopping count, stopping fraction, event CSV, plot, calibration, or scientific numerical result was regenerated. Historical A-002 outputs remain quarantined. A direct clone failed because the runtime could not resolve `github.com`; authenticated GitHub connector writes were used.
