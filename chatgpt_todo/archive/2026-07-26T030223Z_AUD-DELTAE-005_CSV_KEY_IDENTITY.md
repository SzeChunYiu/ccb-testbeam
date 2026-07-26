# AUD-DELTAE-005 — CSV composite-key identity

- **Session:** `2026-07-26T030223Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `f1a615d5b591b63c91b03124d243daf8372b61cd`
- **Task status:** `PARTIAL`
- **Focused audit gate:** `VALIDATED`
- **Production reader contract:** `FLAWED`
- **Policy:** `DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`

## Repository review

Reviewed recent `main` history, open PR #933, closed PR #868, current CI status,
`chatgpt_todo/` coordination records, the DeltaE CSV reader contract, canonical
`deltaE_E.py`, strict bridge tests, and the Cluster A data-side consumer.

The current source blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414`
defines the composite key as `(source_file_id, run_id, event_id)` but reads CSV
with default `pandas.read_csv(path)` inference.

## Demonstrated result

For exact source identifiers `001` and `1` with equal run/event tokens:

- default inferred distinct composite keys: `1`;
- lossless-text distinct composite keys: `2`;
- default false data/MC matches: `1`;
- lossless-text false matches: `0`.

The current-like executable contract returned `FLAWED` with five findings. A
corrected strict-UTF-8/text-key fixture returned `VALIDATED` with zero findings.

## Files added

- `tools/audit/audit_deltae_csv_key_identity.py`
- `tests/test_audit_deltae_csv_key_identity.py`
- `tools/audit/render_deltae_csv_key_identity_evidence.py`
- `docs/validation/deltae_csv_key_identity_validation.json`
- `docs/validation/deltae_csv_key_identity.svg`
- `docs/validation/deltae_csv_key_identity_audit.md`

## Validation

```text
python -m py_compile \
  tools/audit/audit_deltae_csv_key_identity.py \
  tests/test_audit_deltae_csv_key_identity.py \
  tools/audit/render_deltae_csv_key_identity_evidence.py
pytest -q tests/test_audit_deltae_csv_key_identity.py
6 passed in 0.09s
```

JSON and SVG parsing passed. Maximum changed Python line length: 100.

## Acceptance boundary

The audit tooling and evidence are validated. The canonical reader was not
modified in this unit. A follow-up must implement single-read strict UTF-8 and
text dtypes for all three key columns, add direct integration tests, and require
the exact current source to produce zero findings.

No ROOT or A-002 production data were processed. No physics result is authorized.
Repository-wide pytest/ruff, ROOT processing, link inventory, and GitHub Actions
were not run.

`SESSION_LOG.md` was not appended because the available connector permits
whole-file replacement while the complete append-only bytes are exposed only in
paged or truncated views. Reconstructing it partially could erase provenance.
This immutable record and `HANDOFF.md` preserve the append-equivalent session.
