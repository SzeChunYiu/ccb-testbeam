# Latest Handoff

## Session

- **UTC:** 2026-07-23T04:05:33Z
- **Task:** AUD-AMP-008 (VALIDATED tooling increment; real-data work BLOCKED)
- **Initial remote main:** `62a3389b5cbe26cdd56f6089a9e3d1f264629017`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed defect

Amplitude convention evidence was bound to the exact input-table SHA-256 and required a non-empty reference string, but the supporting artifact named by that string was not itself immutable. A mutable producer-code path, schema document, or pedestal report could change while an old authorization record continued to permit physics use.

## Work pushed directly to main

`tools/audit/validate_amplitude_evidence_map.py` is now v1.1.0. Each evidence record must now include canonical lowercase hexadecimal `evidence_reference_sha256` in addition to the exact input digest, convention, accepted evidence basis, and human-readable `evidence_reference`.

Because `tools/audit/amplitude_convention_audit.py` uses the shared `validate_payload` function for CLI and programmatic evidence maps, missing or malformed supporting-artifact digests fail closed in both paths.

Updated regression fixtures:

- `tests/test_validate_amplitude_evidence_map.py`
- `tests/test_hash_bound_amplitude_evidence.py`
- `tests/test_amplitude_evidence_integration.py`
- `tests/test_amplitude_convention_anchor_gate.py`
- `tests/test_amplitude_baseline_acceptance_gate.py`
- `tests/test_amplitude_physics_baseline_gate.py`

Immutable session record:

- `chatgpt_todo/archive/2026-07-23T040533Z_AUD-AMP-008_IMMUTABLE_EVIDENCE_REFERENCE.md`

## Validation

A direct clone was attempted and failed because the runtime could not resolve `github.com`.

Exact copies of the updated validator logic and focused supporting-digest tests were reconstructed locally:

```text
python -m py_compile tools/audit/validate_amplitude_evidence_map.py tests/test_validate_amplitude_evidence_map.py
python -m pytest tests/test_validate_amplitude_evidence_map.py -q
5 passed in 0.05s
```

The complete affected auditor suite and repository-wide CI were not available in this runtime. No success beyond the focused validator gate is claimed.

## Main progression

- `62a3389b5cbe26cdd56f6089a9e3d1f264629017` — initial remote main.
- `e75c5ab60d5a7dc7ab51ff6c764e062a7162547d` — `fix(audit): bind amplitude evidence references to immutable bytes`.
- `da8377d6ddfec256fc6610f4fbff8b51d921d2fb` — `test(audit): require immutable evidence-reference digests`.
- `fa0e235aa58b1bef7b692c35d76b7765a3529a4f` — `test(audit): bind hash-bound evidence references to bytes`.
- `cf2ac2873ce1dbcfefdc270ac07ead99ee322914` — `test(audit): enforce immutable evidence references in integration`.
- `714b905f29853d9d27852ba9211703e413afd5d6` — `test(audit): bind convention-anchor evidence artifacts`.
- `8afeeead6c4662971e68d1c885e3ec0d04ae2375` — `test(audit): bind baseline evidence artifacts`.
- `2cf21c07d2cd79eb354a5514d28d4b2fb8c3e3ff` — `test(audit): bind physics evidence artifacts`.
- `9bf409ddd6d5b09c7f3188016fcab5901cc55904` — `docs(audit): archive immutable evidence-reference gate`.
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- No real pulse table or real evidence artifact was available.
- No amplitude convention, stopping count, stopping fraction, event CSV, DeltaE-E plot, calibration, or detector-performance result was regenerated.
- Historical A-002 outputs remain quarantined.
- The exact A-002 convention remains unresolved.
- `SESSION_LOG.md` was not replaced because safe append semantics were unavailable; the immutable archive preserves the complete run.

## Acceptance status

- Input-table hash binding: VALIDATED previously.
- Evidence-reference presence: VALIDATED previously.
- Supporting-artifact byte binding: VALIDATED by focused synthetic regression in this session.
- Real-table amplitude convention: BLOCKED on exact table bytes and exact supporting evidence bytes.
- A-002 regenerated outputs: BLOCKED.

## Next action

Create a real A-002 evidence map containing both the exact table SHA-256 and the exact supporting-artifact SHA-256. Run `validate_amplitude_evidence_map.py`, then run `amplitude_convention_audit.py` without `--max-rows`. Review every parser error, ambiguity, malformed/nonfinite warning, baseline-schema state, and physics-acceptance state before regenerating the quarantined A-002 JSON, CSV, and DeltaE-E figure.
