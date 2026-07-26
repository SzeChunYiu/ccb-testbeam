# Active Task

- **Task ID:** `AUD-LEDGER-002`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T080450Z`
- **Initial remote main SHA:** `f28b166c836b3055b2ff1e110c15767ba075e72b`
- **Scope:** prevent the canonical claim-ledger schema validator from overwriting the ledger or publishing truncated validation artifacts when JSON/SVG destinations alias inputs, each other, or fail during replacement.
- **Policy:** `CLAIM_LEDGER_VALIDATION_OUTPUTS_MUST_BE_DISTINCT_AND_ATOMIC`.
- **Implementation:** validator v1.1.0 rejects resolved-path, symlink, hard-link, and JSON/SVG pairwise aliases; publishes strict UTF-8 through a unique same-directory temporary file with flush, `fsync`, and `os.replace`; cleans temporary files; preserves prior outputs on replacement failure; returns controlled status 2; and records publication provenance.
- **Validation:** existing schema tests plus focused output-safety regressions returned `19 passed in 0.08s`; former direct-write algorithm reconstruction destructively overwrote its input; current direct/symlink aliases failed closed; injected replacement failure preserved the previous output; JSON and SVG parsed; maximum changed Python line length was 96. Ruff was unavailable and was not claimed.
- **Evidence:**
  - `docs/validation/claim_ledger_output_safety_validation.json`
  - `docs/validation/claim_ledger_output_safety.svg`
  - `docs/validation/claim_ledger_output_safety_audit.md`
  - `chatgpt_todo/archive/2026-07-26T080450Z_AUD-LEDGER-002_OUTPUT_SAFETY.md`
- **Core delivery through:** `f90de3e39283187c53d053ced5d5c3059c6ffc4b`.
- **Focused acceptance:** output-publication remediation `VALIDATED / COMPLETE`.
- **Repository acceptance:** claim-level scientific audit remains `PARTIAL`; this task does not close `AUD-LEDGER-001`.
- **Scientific boundary:** no claim value, uncertainty, source, simulation, calibration, or detector-performance result is authorized by this task.
- **Status:** `COMPLETE`
