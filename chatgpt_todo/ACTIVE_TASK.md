# Active Task

- **Task ID:** AUD-WIKI-004
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T102318Z
- **Initial remote main SHA:** `dcd30497d7e83a35d686b8835aefdb2537fbcf02`
- **Scope:** audit exact public binding of canonical `CL-011` S10b live10 in the
  root WIKI after the ledger and Chapter 5 corrections.
- **Confirmed defect:** both WIKI claim sites retain rounded `124.79 ns`,
  `VALIDATED`, and/or stale uncertainty/truth semantics; the canonical table
  still publishes unsupported `0.5` and `1.0` components.
- **Delivered:** location-bound fail-closed validator, seven focused tests,
  machine-readable validation, visual evidence, audit report, immutable
  archive, and reproducible handoff.
- **Validation:** `7 passed in 1.63s`; current exact excerpts are `FLAWED` with
  24 findings; corrected fixture is `VALIDATED` with zero findings; JSON and SVG
  parse; maximum changed Python line length is 95.
- **Evidence:** `docs/validation/wiki_tau_eff_public_binding_audit.md`,
  `wiki_tau_eff_public_binding_validation.json`, and
  `wiki_tau_eff_public_binding.svg`.
- **Scientific boundary:** no ROOT reprocessing, fit rerun, new uncertainty,
  universal dead time, accepted Rmax, calibration, or performance result.
- **Status:** PARTIAL. The gate is validated; root `WIKI.md` remediation remains
  open and must pass this gate plus existing WIKI and link checks.
