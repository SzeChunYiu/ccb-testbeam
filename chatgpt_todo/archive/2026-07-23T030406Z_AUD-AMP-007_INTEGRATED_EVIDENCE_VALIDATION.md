# AUD-AMP-007 — Integrated evidence-reference validation

## Session

- UTC: 2026-07-23T03:04:06Z
- Initial remote main: `c4d3a15d89a6c2d03fcf0795472d980fbd149c6d`
- Task state: VALIDATED tooling increment; real-table validation remains BLOCKED.

## Confirmed defect

`tools/audit/validate_amplitude_evidence_map.py` required a non-empty `evidence_reference`, but `tools/audit/amplitude_convention_audit.py` used a separate weaker loader. Direct CLI or programmatic auditor invocation could therefore authorize an evidence record containing only a table hash, convention, and evidence-basis category.

## Correction

- Updated `amplitude_convention_audit.py` to v3.0.0.
- Both CLI loading and direct `audit(...)` calls now invoke the shared `validate_payload` function.
- Canonical lowercase SHA-256 syntax, accepted convention, accepted basis, non-empty evidence reference, and optional embedded-digest equality are now enforced in the authorization path itself.
- Normalized evidence is retained in output, including `physics_evidence_reference`.
- Added focused integration tests and updated prior hash-bound evidence fixtures to include traceable references.

## Validation

Executed on exact local reconstructions of the committed implementation and affected tests:

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

A direct clone was attempted and failed with `Could not resolve host: github.com`; authenticated GitHub connector writes were used.

## Main commits

- `29f3e0e45044c796ec109344894d2c78956ba1ee` — `fix(audit): enforce traceable evidence validation in auditor`
- `8ce6c67911ff56bc6a8e20378219b2ce1b3541e7` — `test(audit): enforce evidence-reference integration`
- `622cdd9a09f70eec8414c1048b6232d097a4fb7d` — `test(audit): require traceable hash-bound evidence`
- `ad81ecad0ef73f6dc581c1688c4c3a8d325ce5df` — `test(audit): add traceable physics evidence references`
- `91c48247025aeec0711ad98cdab02228cf8e0804` — `test(audit): add traceable baseline evidence references`
- `be97bfae90ea97a3c3fdc3f548c6b0710f31632c` — `test(audit): add traceable convention evidence references`

## Evidence boundary

No real pulse table or real evidence map was available. No amplitude convention, stopping count, stopping fraction, event CSV, DeltaE-E plot, calibration, or detector-performance result was regenerated. Historical A-002 outputs remain quarantined.
