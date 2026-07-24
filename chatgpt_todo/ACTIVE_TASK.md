# Active Task

- **Task ID:** AUD-LEDGER-001 / CL-017 and CL-018 legacy MV1 PID reconstruction unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T170218Z
- **Initial remote main SHA:** `86fb70f4408a9bb5c0bb6dc24c016a9428e1dd0b`
- **Scope completed in this unit:** reconstructed malformed `CL-017` and `CL-018` from the exact tracked legacy MV1 producer, fixed truth-MC summary, introducing commit, and current group-disjoint remediation; added a fail-closed validator, focused tests, machine-readable evidence, visual split evidence, and refreshed cumulative row-width evidence.
- **Confirmed defects:** both rows had 38 rather than 43 columns and cited nonexistent source paths. The fixed 0.9859658513538254 AUC and 0.9644090769970706 purity are from a row-index parity split with no event ID, no explicit HGB seed, no environment/input manifest, and no uncertainty or purity counts.
- **Source-backed result:** 400369 charged tracks contain 150130 protons and 146842 deuterons; the binary p/d sample is 296972 tracks. These are fixed truth-MC outputs, not beam-data performance.
- **Implemented files:** corrected `docs/claim_ledger.csv`; added `tools/audit/validate_mv1_legacy_claim_rows.py`, `tools/audit/render_mv1_split_leakage_evidence.py`, focused tests, and Markdown/JSON/SVG evidence; refreshed cumulative schema Markdown/JSON/SVG evidence.
- **Validation:** changed Python files compiled; focused suite returned `6 passed in 0.82s`; the exact corrected ledger/source/output contract returned `VALIDATED` with zero issues; JSON and SVG parsed; changed Python lines meet the repository 100-character convention.
- **Evidence policy:** `LEGACY_MV1_PID_OUTPUTS_REQUIRE_GROUP_DISJOINT_RERUN_AND_UNCERTAINTY` plus `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.
- **Cumulative ledger state:** `16/26` exact-width claim rows and `10/26` withheld malformed rows. The schema validator remains intentionally `FLAWED`/status 1 until all rows are reconstructed.
- **Scientific boundary:** this unit performs no ROOT rerun, beam-data processing, uncertainty calculation, detector-response closure, or accepted PID-performance measurement. `CL-017` and `CL-018` remain `GATED` under `BLK-MV1-001`.
- **Remaining work:** rerun MV1 with immutable event groups and content-addressed provenance; quantify AUC and operating-point uncertainty and split/seed sensitivity; correct Chapter 8's unconditional truth-ceiling wording; reconstruct the next source-backed malformed ledger rows; complete `AUD-ANOM-001` matched data/MC closure.
- **Status:** VALIDATED for this two-row reconstruction unit; ledger-wide `AUD-LEDGER-001` remains PARTIAL.
