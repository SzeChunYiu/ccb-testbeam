# Active Task

- **Task ID:** AUD-LEDGER-001 / CL-019 through CL-021 legacy MV3 reconstruction unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T173757Z
- **Initial remote main SHA:** `1e44fd19a02c33377e727bd5d85be7a8aa96b587`
- **Scope completed in this unit:** reconstructed malformed `CL-019`, `CL-020`, and `CL-021` from the exact tracked legacy MV3 v3 report and current fail-closed remediation; added a validator, focused tests, machine-readable evidence, visual evidence, and refreshed cumulative row-width evidence.
- **Confirmed defects:** row widths were 38, 38, and 36 rather than 43; former rows cited untracked producer/result paths; rounded fractions omitted exact per-stave counts; the report exposed only the label `chi2/ndf = 68269.4` without chi-square, ndf, p-value, bin variances, or covariance.
- **Source-backed result:** fixed rounded B8 fractions are MC `0.223` from 249484 thresholded tracks and data `0.023` from 306745 selected events. The rounded outputs identify 249 and 307 possible integer numerators respectively, so exact binomial intervals cannot be reconstructed.
- **Implemented files:** corrected `docs/claim_ledger.csv`; added `tools/audit/validate_mv3_legacy_claim_rows.py`, `tools/audit/render_mv3_legacy_claim_evidence.py`, focused tests, and Markdown/JSON/SVG evidence; refreshed cumulative schema Markdown/JSON/SVG evidence.
- **Validation:** changed Python files compiled; focused suite returned `7 passed in 1.05s`; the exact corrected ledger/report/current-source contract returned `VALIDATED` with zero issues; JSON and SVG parsed; committed Python blobs match the locally validated Git blobs; changed Python lines meet the repository 100-character convention.
- **Evidence policy:** `LEGACY_MV3_PROFILE_REQUIRES_EXACT_COUNTS_AND_FAIL_CLOSED_RERUN` plus `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.
- **Cumulative ledger state:** `19/26` exact-width claim rows and `7/26` withheld malformed rows. The schema validator remains intentionally `FLAWED`/status 1 until all rows are reconstructed.
- **Scientific boundary:** this unit performs no ROOT rerun, beam-data processing, exact stopping-count recovery, uncertainty calculation, profile goodness-of-fit reconstruction, detector-response closure, or accepted stopping-profile measurement. `CL-019` and `CL-020` remain `GATED`; `CL-021` is `FLAWED`; all are blocked under `BLK-MV3-LEGACY-001`.
- **Remaining work:** rerun MV3 from immutable inputs with explicit Sample I/II labels and per-layer masks; retain exact counts and a preregistered statistic/uncertainty model; reconstruct the seven remaining malformed timing rows; complete repository-wide inventory and anomaly closure.
- **Status:** VALIDATED for this three-row reconstruction unit; ledger-wide `AUD-LEDGER-001` remains PARTIAL.
