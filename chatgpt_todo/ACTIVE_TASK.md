# Active Task

- **Task ID:** `AUD-LEDGER-002`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T080450Z`
- **Initial remote main SHA:** `f28b166c836b3055b2ff1e110c15767ba075e72b`
- **Scope:** prevent the canonical claim-ledger schema validator from overwriting the ledger or publishing truncated validation artifacts when JSON/SVG destinations alias inputs, each other, or fail during replacement.
- **Policy:** `CLAIM_LEDGER_VALIDATION_OUTPUTS_MUST_BE_DISTINCT_AND_ATOMIC`.
- **Repository facts under review:** validator v1.0.0 Git blob `1961e63756b734db30a4a9a8037a756c291afe25` writes JSON and SVG directly to requested final paths and performs no output-alias check.
- **Files:** `tools/audit/validate_claim_ledger_schema.py`; focused output-safety tests; deterministic JSON/SVG evidence; audit report; coordination records.
- **Validation plan:** preserve existing schema behavior; reproduce the former destructive direct-write algorithm on a synthetic ledger; reject direct/symlink/hard-link aliases; inject `os.replace` failure; verify previous-output preservation, temporary cleanup, controlled status 2, compilation, focused pytest, JSON parse, SVG parse, and line-length limits.
- **Scientific boundary:** software/provenance validation only; no claim value, uncertainty, source, simulation, calibration, or detector-performance result is authorized by this task.
- **Status:** `ACTIVE`
