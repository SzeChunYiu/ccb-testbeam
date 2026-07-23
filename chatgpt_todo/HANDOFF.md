# Latest Handoff

## Session

- **UTC:** 2026-07-23T03:04:06Z
- **Task:** AUD-AMP-007 (VALIDATED tooling increment; real-data work BLOCKED)
- **Initial remote main:** `c4d3a15d89a6c2d03fcf0795472d980fbd149c6d`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed defect

`tools/audit/validate_amplitude_evidence_map.py` required traceable evidence references, but `tools/audit/amplitude_convention_audit.py` retained an independent weaker loader. Direct CLI or programmatic auditor invocation could still authorize a hash-bound record with no artifact identifying the schema, producer code, pedestal study, commit, or report supporting the convention.

## Work pushed directly to main

`tools/audit/amplitude_convention_audit.py` is now v3.0.0 and uses the shared `validate_payload` gate for both CLI evidence-map loading and direct `audit(...)` calls. The authorization path now requires:

- canonical lowercase hexadecimal SHA-256 keys;
- `ABSOLUTE` or `NET` convention;
- an accepted evidence-basis category;
- a non-empty `evidence_reference`;
- optional embedded-digest equality.

Normalized evidence is retained in each table record, and `physics_evidence_reference` is exposed explicitly.

Added `tests/test_amplitude_evidence_integration.py`. Updated the existing hash-bound, physics-baseline, baseline-acceptance, and convention-anchor tests so accepted synthetic records contain traceable references.

Immutable session record:

- `chatgpt_todo/archive/2026-07-23T030406Z_AUD-AMP-007_INTEGRATED_EVIDENCE_VALIDATION.md`

## Validation

A direct clone was attempted and failed because the runtime could not resolve `github.com`. The implementation and affected tests were reconstructed exactly in a local temporary tree and executed before connector writes:

```text
python -m py_compile tools/audit/amplitude_convention_audit.py tests/test_amplitude_evidence_integration.py
python -m pytest \
  tests/test_hash_bound_amplitude_evidence.py \
  tests/test_amplitude_evidence_integration.py \
  tests/test_amplitude_convention_anchor_gate.py \
  tests/test_amplitude_baseline_acceptance_gate.py \
  tests/test_amplitude_physics_baseline_gate.py -q
17 passed in 0.14s
```

## Main progression

- `c4d3a15d89a6c2d03fcf0795472d980fbd149c6d` — initial remote main.
- `29f3e0e45044c796ec109344894d2c78956ba1ee` — `fix(audit): enforce traceable evidence validation in auditor`.
- `8ce6c67911ff56bc6a8e20378219b2ce1b3541e7` — `test(audit): enforce evidence-reference integration`.
- `622cdd9a09f70eec8414c1048b6232d097a4fb7d` — `test(audit): require traceable hash-bound evidence`.
- `ad81ecad0ef73f6dc581c1688c4c3a8d325ce5df` — `test(audit): add traceable physics evidence references`.
- `91c48247025aeec0711ad98cdab02228cf8e0804` — `test(audit): add traceable baseline evidence references`.
- `be97bfae90ea97a3c3fdc3f548c6b0710f31632c` — `test(audit): add traceable convention evidence references`.
- `b3b8b7e3707a4d3159181cb8a161fad7b584c997` — `docs(audit): archive integrated evidence validation`.
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- No real pulse table or real evidence map was available.
- No amplitude convention, stopping count, stopping fraction, event CSV, DeltaE-E plot, calibration, or detector-performance result was regenerated.
- Historical A-002 outputs remain quarantined.
- The complete repository test suite and GitHub CI were not run.
- `SESSION_LOG.md` was not replaced because safe append semantics were unavailable; the immutable archive preserves the session record.

## Acceptance status

- Integrated evidence-reference authorization gate: VALIDATED by focused synthetic regression.
- Real-table amplitude convention: BLOCKED on exact table bytes and independently reviewable evidence.
- A-002 regenerated outputs: BLOCKED.

## Next action

Create a real evidence map for the exact A-002 input using its lowercase SHA-256 and an immutable `evidence_reference`. Run `validate_amplitude_evidence_map.py`, then run `amplitude_convention_audit.py` without `--max-rows`. Review every parser error, ambiguity, malformed/nonfinite warning, baseline-schema state, and physics-acceptance state before regenerating the quarantined A-002 JSON, CSV, and DeltaE-E figure.
