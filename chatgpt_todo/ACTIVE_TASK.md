# Active Task

- **Task ID:** `AUD-RMAX-001`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T200250Z`
- **Initial remote main SHA:** `9c576de392c4f81aaea369b4612e16841eeef730`
- **Policy:** `RMAX_CHECK_MUST_VALIDATE_CLAIM_STATE_AND_NEVER_INFER_RATE_FROM_OCCUPANCY`.
- **Scope:** audit and remediate `scripts/check_rmax_formula.py` so the Thesis QA gate validates the canonical ledger and public WIKI state, uses the exact CL-011 live-time estimand, distinguishes arithmetic sensitivities from empirical rates, exits zero only for a scientifically consistent blocked claim, and fails closed on malformed inputs or stale overclaim wording.
- **Inputs inspected:** `scripts/check_rmax_formula.py`, `.github/workflows/thesis_qa.yml`, `WIKI.md`, `docs/claim_ledger.csv`, `tools/audit/audit_data_side_rmax_semantics.py`, recent main history, PR #868, and repository coordination files.
- **Confirmed defects:** the current checker prints `PASS` then exits `1`; it does not read WIKI or the claim ledger; it calls 3.05 MHz “measured (occupancy)” despite the exposure/rate-identifiability blocker; current WIKI still says `Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz)`.
- **Validation plan:** add direct CLI/unit regressions; reproduce stale/current and corrected fixtures; verify exact arithmetic, strict UTF-8 input handling, unique canonical claim rows, atomic JSON publication, and deterministic SVG/JSON evidence.
- **Scientific boundary:** no absolute Rmax, event-arrival rate, live exposure, pile-up ceiling, calibration, or detector-performance quantity will be accepted by this task.
- **Status:** `ACTIVE`
