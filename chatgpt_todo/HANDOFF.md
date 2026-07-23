# Latest Handoff

## Session

- **UTC:** 2026-07-23T00:10:19Z
- **Task:** AUD-AMP-004 (PARTIAL)
- **Initial remote main:** `b72a9061ce1411e64521e6c71ef099c4c92e15d6`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed scientific/provenance defect

`tools/audit/amplitude_convention_audit.py` v2.7.0 treated the coexistence of a complete, uniquely named pedestal column with bare `amplitude_adc` as sufficient for an accepted amplitude convention. That is not identifying evidence: an absolute peak code and an already baseline-subtracted height may both coexist with a pedestal diagnostic. The repository contract requires explicit schema metadata, producer-code provenance, or independently reviewed evidence.

## Work pushed directly to main

Version 2.8.0 adds an optional `--evidence-map` keyed by the exact input SHA-256. Accepted records must specify `ABSOLUTE` or `NET` and one of:

- `EXPLICIT_SCHEMA_METADATA`
- `PRODUCER_CODE_PROVENANCE`
- `INDEPENDENTLY_REVIEWED_PEDESTAL_EVIDENCE`

The JSON now separates heuristic diagnostics from physics authorization:

- `heuristic_convention`
- `physics_convention`
- `physics_convention_evidence`
- `physics_acceptance`
- `physics_subtract_baseline_correct`

Without exact hash-bound evidence, the CLI emits `NO_HASH_BOUND_CONVENTION_EVIDENCE`, increments `n_unverified_conventions`, and exits nonzero. A changed file hash invalidates the evidence automatically.

Added and updated regression coverage:

- `tests/test_hash_bound_amplitude_evidence.py`
- `tests/test_amplitude_convention_anchor_gate.py`
- `tests/test_amplitude_baseline_acceptance_gate.py`

Immutable session record:

- `chatgpt_todo/archive/2026-07-23T001019Z_AUD-AMP-004_HASH_BOUND_EVIDENCE.md`

## Validation

Executed on exact local reconstructions:

```text
python -m py_compile tools/audit/amplitude_convention_audit.py tests/test_hash_bound_amplitude_evidence.py
python -m pytest tests -q
11 passed in 0.09s
```

The focused suite covers missing evidence, exact accepted evidence, mutation invalidation, invalid evidence bases, pedestal-only diagnostics, unresolved baselines, and net/absolute evidence paths.

## Main progression

- `b72a9061ce1411e64521e6c71ef099c4c92e15d6` — initial remote main.
- `39d7a4ab509a8213954bd677907410ea5b0d0dae` — `fix(audit): require hash-bound amplitude convention evidence`.
- `5c2a07f580920d0728a998716e4af885bf65de0f` — `test(audit): cover hash-bound amplitude evidence`.
- `275b543e536d6ef6f5555dd19f0a9ccc1a236048` — `test(audit): require evidence beyond pedestal coexistence`.
- `063ba946d6b6fb9a6a6b1db1bd04a0f2e5ca036e` — `test(audit): gate physics use on hash-bound evidence`.
- `62037cf3031b8c308b649e28924864ebc353d69a` — `docs(audit): archive hash-bound convention evidence gate`.
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

- Hash-bound convention-evidence gate: VALIDATED by focused synthetic regression.
- Real-table amplitude convention: BLOCKED on exact data access and reviewed evidence.
- A-002 regenerated outputs: BLOCKED.

## Next action

Hash the exact A-002 table, trace its producer/schema provenance, and create a reviewed evidence-map entry only if the convention is demonstrated. Run v2.8.0 without `--max-rows`. Do not pass a convention to `scripts/single_stave/deltaE_E_data_bridge.py` unless `physics_acceptance=ACCEPTABLE` and every malformed, nonfinite, ambiguity, and baseline-quality gate passes.
