# Active Task

- **Task ID:** AUD-AMP-006
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T02:05:18Z
- **Base main SHA:** `5e00ec10368a893d3ae4d92398f18dc777e4f044`
- **Scope:** require every hash-bound amplitude-convention record to identify the actual schema, producer-code, or reviewed pedestal artifact supporting the physics convention.
- **Finding:** v2.9.0 of `amplitude_convention_audit.py` can accept an evidence record containing only `convention` and `evidence_basis`; the record need not identify a reviewable source. Its loader also accepts noncanonical 64-character digest keys.
- **Change:** added `tools/audit/validate_amplitude_evidence_map.py` v1.0.0, which requires canonical lowercase hexadecimal SHA-256 keys, accepted convention/basis values, a non-empty `evidence_reference`, and a matching optional embedded digest.
- **Validation:** `python -m py_compile` passed and focused pytest returned `7 passed in 0.06s` on exact local files.
- **Boundary:** the new tool is currently a standalone preflight validator; direct convention-auditor invocation does not yet import it. No real evidence map or pulse table was available.
- **Status:** PARTIAL — standalone traceability gate and regression tests validated; integration into the main auditor and real A-002 evidence remain open.
