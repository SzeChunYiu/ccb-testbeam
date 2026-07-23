# AUD-AMP-008 — Immutable evidence-reference gate

## Session

- UTC: 2026-07-23T04:05:33Z
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `62a3389b5cbe26cdd56f6089a9e3d1f264629017`
- Write target: direct to `main`
- Status: VALIDATED tooling increment; real-data amplitude convention remains BLOCKED

## Confirmed defect

The amplitude evidence-map gate bound each convention assertion to the exact input-table SHA-256 and required a non-empty `evidence_reference`, but the referenced supporting artifact itself was not immutable. A reference could name a mutable path, branch, or otherwise changed document while continuing to authorize physics use for the table. Hash-binding the input protects table identity; it does not preserve the exact schema, producer-code, or pedestal-evidence bytes used to justify the convention.

## Changes

`tools/audit/validate_amplitude_evidence_map.py` is now version 1.1.0. Every accepted record must include canonical lowercase hexadecimal `evidence_reference_sha256` in addition to:

- the exact input-table SHA-256 map key;
- `ABSOLUTE` or `NET` convention;
- an accepted evidence basis;
- a non-empty human-readable `evidence_reference`;
- optional embedded input digest equality.

The normalized record retains both the input digest and the supporting-artifact digest. Because `amplitude_convention_audit.py` imports the shared `validate_payload` function for both CLI and programmatic maps, missing or malformed supporting-artifact digests fail closed on every authorization path.

Updated regression fixtures:

- `tests/test_validate_amplitude_evidence_map.py`
- `tests/test_hash_bound_amplitude_evidence.py`
- `tests/test_amplitude_evidence_integration.py`
- `tests/test_amplitude_convention_anchor_gate.py`
- `tests/test_amplitude_baseline_acceptance_gate.py`
- `tests/test_amplitude_physics_baseline_gate.py`

The new tests explicitly cover missing, uppercase, nonhexadecimal, and wrong-length supporting-artifact digests, plus direct auditor rejection of an unbound reference.

## Validation

A direct clone was attempted and failed:

```text
git clone --depth 1 https://github.com/SzeChunYiu/ccb-testbeam.git /tmp/ccb-testbeam
fatal: unable to access 'https://github.com/SzeChunYiu/ccb-testbeam.git/': Could not resolve host: github.com
```

Exact copies of the updated validator logic and its focused digest tests were reconstructed locally and run:

```text
python -m py_compile tools/audit/validate_amplitude_evidence_map.py tests/test_validate_amplitude_evidence_map.py
python -m pytest tests/test_validate_amplitude_evidence_map.py -q
5 passed in 0.05s
```

The complete affected auditor suite and repository-wide CI were not available in this runtime. All updated fixture files were written through GitHub's contents API with their current blob SHAs; no force push or history rewrite was used.

## Main progression

- `e75c5ab60d5a7dc7ab51ff6c764e062a7162547d` — `fix(audit): bind amplitude evidence references to immutable bytes`
- `da8377d6ddfec256fc6610f4fbff8b51d921d2fb` — `test(audit): require immutable evidence-reference digests`
- `fa0e235aa58b1bef7b692c35d76b7765a3529a4f` — `test(audit): bind hash-bound evidence references to bytes`
- `cf2ac2873ce1dbcfefdc270ac07ead99ee322914` — `test(audit): enforce immutable evidence references in integration`
- `714b905f29853d9d27852ba9211703e413afd5d6` — `test(audit): bind convention-anchor evidence artifacts`
- `8afeeead6c4662971e68d1c885e3ec0d04ae2375` — `test(audit): bind baseline evidence artifacts`
- `2cf21c07d2cd79eb354a5514d28d4b2fb8c3e3ff` — `test(audit): bind physics evidence artifacts`

## Scientific boundary

No real pulse table, real evidence artifact, ROOT file, stopping count, stopping fraction, event CSV, DeltaE-E figure, calibration, or detector-performance result was generated or changed. Historical A-002 outputs remain quarantined. The exact A-002 amplitude convention remains unresolved until both the table bytes and the cited evidence bytes are available and hashed.

## Next action

Create the real A-002 evidence record with both the exact table SHA-256 and the exact supporting-artifact SHA-256. Validate the map, run the complete amplitude auditor without prefix sampling, review all parser/ambiguity/data-quality states, and only then regenerate the quarantined A-002 scientific outputs.
