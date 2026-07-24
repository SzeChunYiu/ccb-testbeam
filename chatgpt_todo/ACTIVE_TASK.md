# Active Task

- **Task ID:** AUD-LEDGER-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T061758Z
- **Initial remote main SHA for this unit:** `72fccaa8f4d6c00665c60fd0a94884c87cdd544b`
- **Scope completed in this unit:** reconstructed paired Rmax rows `CL-010` and `CL-012` from the MV5 report, summary JSON, implementation, academic chapter, producing commit, and tracked figure; identified incompatible definitions; withheld the canonical rate; repaired `FIG-PU-003`; added a fail-closed validator, focused regressions, JSON evidence, and accessible SVG evidence.
- **Implemented files:** `tools/audit/validate_claim_ledger_cl010.py` v1.0.0; `tests/test_validate_claim_ledger_cl010.py`; `docs/validation/claim_ledger_cl010_{audit.md,validation.json,svg}`; corrected `docs/claim_ledger.csv`, `docs/figure_registry.csv`, and cumulative schema evidence.
- **Validation:** `py_compile` passed; focused pytest returned `6 passed in 0.04s`; source-faithful fixture validation returned `VALIDATED` with zero issues; JSON and SVG parsed; changed Python lines were at most 92 characters. Repository facts were checked through authenticated GitHub blobs because a complete checkout was unavailable.
- **Measured current state:** 26 ledger rows; `CL-001`, `CL-007`, `CL-010`, `CL-011`, and `CL-012` are exact-width; 21 rows remain width-mismatched and their late fields remain `WITHHELD`; cumulative schema status remains `FLAWED` by design.
- **Scientific finding:** `3.0448717948717947 MHz` is `(1/124.8 ns) × 0.38`, where `0.38` is the recorded beam duty factor; the chapter separately derives `3.20 MHz` from `mu_max=0.1` and four staves before calling `3.05 MHz` a rounding; the MV5 recovery-ceiling crossing is null because the maximum failure fraction is `0.03475 < 0.17`.
- **Scientific boundary:** no accepted Rmax value, uncertainty, data result, or simulation result was produced. `CL-010` is `BLOCKED`, `CL-012` is `SUPERSEDED`, and public WIKI/chapter language remains to be synchronized after `S-STAT-003` defines the rate criterion.
- **Remaining work:** reconstruct each of the 21 malformed rows from source evidence, resolve `S-STAT-003`, synchronize WIKI/chapter Rmax language, require 26/26 exact rows, then rerun claim, link, table, and figure checks.
- **Status:** PARTIAL.
