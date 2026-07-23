# AUD-AMP-006 — Amplitude evidence-reference gate

## Session

- UTC: 2026-07-23T02:05:18Z
- Initial remote main: `5e00ec10368a893d3ae4d92398f18dc777e4f044`
- Write target: direct to `main`
- Scope: make hash-bound amplitude-convention evidence traceable to an explicit review artifact or producer source.

## Confirmed defect

`tools/audit/amplitude_convention_audit.py` v2.9.0 validates the input-table SHA-256, convention, and evidence-basis category, but an evidence record containing only `convention` and `evidence_basis` can still authorize physics use. Such a record does not identify the schema metadata, producer code, pedestal study, commit, or report that supports the convention. The loader also accepts any 64-character key, including non-hexadecimal or uppercase values.

This means hash binding protects table identity but does not by itself make the scientific assertion reviewable or reproducible.

## Work completed

Added `tools/audit/validate_amplitude_evidence_map.py` v1.0.0. It fail-closes unless every record has:

- a canonical lowercase hexadecimal 64-character SHA-256 key;
- `convention` equal to `ABSOLUTE` or `NET`;
- an accepted evidence basis;
- a non-empty `evidence_reference` identifying the supporting artifact/source;
- an optional embedded `sha256` that exactly matches the map key.

The validator emits a normalized JSON report when `--output` is supplied and inserts the canonical digest into each normalized record.

Added `tests/test_validate_amplitude_evidence_map.py` covering valid normalization, missing references, malformed digest keys, mismatched embedded hashes, and invalid evidence bases.

## Validation

Executed on exact local files before GitHub writes:

```text
python -m py_compile tools/audit/validate_amplitude_evidence_map.py tests/test_validate_amplitude_evidence_map.py
python -m pytest tests/test_validate_amplitude_evidence_map.py -q
7 passed in 0.06s
```

## Commits

- `20f06b94f7f7e5dc26c9d42acaf9ffee6641cb28` — `feat(audit): validate traceable amplitude evidence maps`
- `a2f9091daf19263d87c514d84aa2e0d385bad27c` — `test(audit): cover traceable amplitude evidence maps`
- This archive commit follows those commits on `main`.

## Evidence boundary

- No real pulse table or evidence map was available.
- The validator is a standalone preflight gate; v2.9.0 of the convention auditor has not yet imported it directly.
- No amplitude convention, stopping count, stopping fraction, CSV, plot, calibration, or detector-performance result was regenerated.
- Historical A-002 outputs remain quarantined.
- Direct cloning failed because the runtime could not resolve `github.com`; authenticated connector reads/writes were used.

## Next action

Integrate `validate_payload` into `amplitude_convention_audit.py` so direct auditor invocation cannot bypass the traceability requirement. Then create a real evidence map for the exact A-002 input, with `evidence_reference` pointing to immutable schema/producer/review evidence, run both validators, and regenerate A-002 only after every physics gate passes.
