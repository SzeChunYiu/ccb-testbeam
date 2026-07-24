# Active Task

- **Task ID:** AUD-LEDGER-001 / CL-025 and CL-026 governance-blocker reconstruction unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T150603Z
- **Initial remote main SHA:** `818246402ae7665bbd7ea699825ea3dbb4f68b04`
- **Scope completed in this unit:** reconstructed malformed `CL-025` and `CL-026` from the exact systematic-uncertainty source document and its introducing commit; added a fail-closed validator, focused tests, machine-readable evidence, visual evidence, and refreshed cumulative row-width evidence.
- **Confirmed defects:** `CL-025` had 37 rather than 43 columns and `CL-026` had 35 rather than 43, so status, truth type, source, blocker, and notes were shifted and withheld.
- **Source-backed result:** no forced-trigger zero-signal events exist in the current dataset, so no independent pedestal-truth value or uncertainty is authorized; the existing uncertainty inventory and simple quadrature summary do not constitute claim-specific reproducible propagation.
- **Implemented files:** corrected `docs/claim_ledger.csv`; added `tools/audit/validate_pedestal_systematics_claim_rows.py`, focused tests, and Markdown/JSON/SVG evidence; refreshed cumulative schema Markdown/JSON/SVG evidence.
- **Validation:** changed Python files compiled; focused suite returned `7 passed in 0.70s`; exact corrected ledger and source returned `VALIDATED` with zero issues; JSON and SVG parsed; changed Python lines were at most 99 characters.
- **Evidence policy:** `BLOCKED_GOVERNANCE_CLAIMS_REQUIRE_EXACT_WIDTH_AND_SOURCE_EVIDENCE` plus `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.
- **Cumulative ledger state:** `12/26` exact-width claim rows and `14/26` withheld malformed rows. The schema validator remains intentionally `FLAWED`/status 1 until all rows are reconstructed.
- **Scientific boundary:** this unit creates no pedestal measurement, uncertainty budget, detector-performance result, data reprocessing, or simulation output. `CL-025` and `CL-026` remain `BLOCKED`.
- **Remaining work:** reconstruct the next source-backed malformed ledger rows; acquire immutable forced-trigger data for `BLK-PED-001`; implement claim-specific hash-bound nuisance propagation and coverage validation for `BLK-SYST-001`; complete `AUD-ANOM-001` matched data/MC closure.
- **Status:** VALIDATED for this two-row reconstruction unit; ledger-wide `AUD-LEDGER-001` remains PARTIAL.
