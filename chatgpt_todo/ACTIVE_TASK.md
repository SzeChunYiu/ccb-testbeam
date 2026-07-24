# Active Task

- **Task ID:** AUD-LEDGER-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T050822Z
- **Initial remote main SHA for this unit:** `1c982d65a0b742c3b6d4f78201cfed37fa3094c4`
- **Scope completed in this unit:** reconstructed `CL-001` from the canonical S00 configuration, implementation, report, exact count table, manifest, producing commit, generated-data contract, and committed diagnostic figure; repaired stale `FIG-GL-001` paths; added a source-chain validator, focused regressions, JSON evidence, and accessible SVG evidence.
- **Implemented files:** `tools/audit/validate_claim_ledger_cl001.py` v1.0.0; `tests/test_validate_claim_ledger_cl001.py`; `docs/validation/claim_ledger_cl001_{audit.md,validation.json,svg}`; corrected `docs/claim_ledger.csv`, `docs/figure_registry.csv`, and cumulative schema evidence.
- **Validation:** exact evidence files were reconstructed from authenticated repository reads; `py_compile` passed; focused pytest returned `5 passed`; CL-001 validator returned `VALIDATED` with zero issues; count `640737`, 33 configured runs, delta 0, tolerance 0; JSON and SVG parsed; changed Python lines were at most 96 characters.
- **Measured current state:** 26 ledger rows; `CL-001`, `CL-007`, and `CL-011` are exact-width; 23 rows remain width-mismatched and their late fields remain `WITHHELD`; cumulative schema status remains `FLAWED` by design.
- **Scientific boundary:** no raw ROOT file, generated pulse table, count, uncertainty, calibration, simulation, or detector-performance result was regenerated. The exact-count claim is scoped to fixed repository-declared inputs and algorithm; the selected-pulse CSV remains intentionally untracked.
- **Remaining work:** reconstruct each of the 23 malformed rows from source evidence, preserve uncertainty caveats and unresolved fields explicitly, require 26/26 exact rows, then rerun WIKI, claim, link, table, and figure checks.
- **Status:** PARTIAL.
