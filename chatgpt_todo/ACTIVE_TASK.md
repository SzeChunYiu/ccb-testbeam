# Active Task

- **Task ID:** AUD-LEDGER-001 / CL-013 and CL-014 MV0 source reconstruction unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T160450Z
- **Initial remote main SHA:** `9e1ccc57fee369293be0f090141831e0f65216b8`
- **Scope completed in this unit:** reconstructed malformed `CL-013` and `CL-014` from the tracked MV0 report, calibration JSON, producer path, and introducing commit; added a fail-closed validator, focused tests, machine-readable evidence, visual evidence, and refreshed cumulative row-width evidence.
- **Confirmed defects:** `CL-013` had 38 rather than 43 columns and `CL-014` had 37 rather than 43; their late fields were withheld. The former records cited wrong/nonexistent source paths, represented the 30% heuristic gain range as statistical plus systematic uncertainty, and supplied unsupported KS count/p-value semantics.
- **Source-backed result:** the report records a B2 median-matching gain of 92 ADC/MeV with a heuristic 30% systematic envelope, not a confidence interval; the fixed KS statistic is 0.1577 at gain 92 and 0.1188 at the scan optimum gain 60, with 579424 B2 data pulses and 321130 MC B2-hit tracks.
- **Implemented files:** corrected `docs/claim_ledger.csv`; added `tools/audit/validate_mv0_claim_rows.py`, focused tests, and Markdown/JSON/SVG evidence; refreshed cumulative schema Markdown/JSON/SVG evidence.
- **Validation:** changed Python files compiled; focused suite returned `5 passed in 0.03s`; the exact reconstructed ledger and sources returned `VALIDATED` with zero issues; JSON and SVG parsed; changed Python lines met the repository 100-character convention.
- **Evidence policy:** `MV0_CLAIMS_REQUIRE_EXACT_WIDTH_AND_SOURCE_BACKED_LIMITATIONS` plus `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.
- **Cumulative ledger state:** `14/26` exact-width claim rows and `12/26` withheld malformed rows. The schema validator remains intentionally `FLAWED`/status 1 until all rows are reconstructed.
- **Scientific boundary:** this unit creates no calibration rerun, confidence interval, selection closure, detector-performance result, data reprocessing, or simulation output. `CL-013` is `GATED`; `CL-014` records source-backed `TENSION`; both remain constrained by `BLK-MV0-001`.
- **Remaining work:** reconstruct the next source-backed malformed ledger rows; recover exact MV0 producer/input provenance and selection closure; preregister an uncertainty and alternative-model validation plan; complete `AUD-ANOM-001` matched data/MC closure.
- **Status:** VALIDATED for this two-row reconstruction unit; ledger-wide `AUD-LEDGER-001` remains PARTIAL.
