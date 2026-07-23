# Active Task

- **Task ID:** AUD-G4-019
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T230825Z
- **Initial remote main SHA:** `eec220db6807d3d3615d92c6d39d4fb2e18e4335`
- **Validated implementation/evidence head:** `807febe85c35b537c53a5acdf1795ee9a67d7cb2`
- **Scope:** bind canonical stopping-power simulation rows, byte count, and SHA-256 to one exact in-memory input snapshot and make invalid UTF-8 a controlled input failure.
- **Confirmed defect:** validator v1.1.0 parsed with `read_text()`, then later re-read the path for `stat()` and SHA-256; a replaced path could produce rows from bytes A with provenance from bytes B. Invalid UTF-8 escaped as an uncaught decoder exception.
- **Validated change:** validator v1.2.0 reads exact bytes once, decodes/parses and derives size/hash from that byte string, records `SINGLE_READ_EXACT_BYTES`, and maps invalid UTF-8 to status-2 `SimulationTableError`.
- **Commands:** focused `py_compile`; existing plus new validator pytest; exact former-algorithm negative control; JSON/SVG parse; Git-blob and line-length checks.
- **Validation:** `19 passed in 2.01s`; former algorithm produced `2 failed`; changed Python lines are at most 94 characters; committed implementation blob matches validated local blob `6a57b93d...`.
- **Evidence:** `docs/validation/stopping_power_sim_snapshot_audit.md`, `stopping_power_sim_snapshot_validation.json`, and `stopping_power_sim_snapshot.svg`.
- **Boundary:** parser/provenance integrity is validated synthetically, but no real export, accepted projectile-loss observable, uncertainty budget, or stopping-power closure was produced.
- **Status:** COMPLETE for `AUD-G4-019`; accepted stopping-power physics closure remains PARTIAL/BLOCKED.
