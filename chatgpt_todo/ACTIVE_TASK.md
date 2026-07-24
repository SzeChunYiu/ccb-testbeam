# Active Task

- **Task ID:** AUD-LEDGER-001 / CL-023 and CL-024 MV6 PCA reconstruction unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T140810Z
- **Initial remote main SHA:** `c9c432f5b96eae0fd11550be7833f18221019b1a`
- **Scope completed in this unit:** reconstructed malformed `CL-023` and `CL-024` from the tracked MV6 synthetic-waveform producer, exact summary JSON, historical report, and producing commit; refreshed cumulative ledger-width evidence.
- **Confirmed defects:** both rows had 37 rather than 43 columns, so late fields were shifted and withheld; they published superseded fractions `0.89` and `0.997` and cited a noncanonical producer/result path.
- **Source reconstruction:** first three MV6 explained-variance ratios sum to `0.7254602133437841`; the first eight sum to `0.821883926913117`. The producer subtracts the pedestal, peak-normalizes each synthetic waveform, fits ten PCA components, uses seed 42, and processed 87,555 charged B-arm MC tracks from 220,000 scanned events.
- **Implemented files:** corrected `docs/claim_ledger.csv`; added `tools/audit/validate_mv6_pca_claim_rows.py`, focused tests, and Markdown/JSON/SVG validation evidence; refreshed the ledger schema Markdown/JSON/SVG evidence.
- **Validation:** changed Python files compiled; focused suite returned `7 passed in 1.39s`; JSON and SVG parsed; exact pre-change ledger SHA-256 matched; corrected ledger blob is `d33180f144cca10a6e310b3e89b5ab1d065d7e66`.
- **Evidence policy:** `MV6_PCA_CLAIMS_MUST_MATCH_TRACKED_SYNTHETIC_WAVEFORM_OUTPUT` plus `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.
- **Cumulative ledger state:** `10/26` exact-width claim rows and `16/26` withheld malformed rows. The schema validator remains intentionally `FLAWED`/status 1 until all rows are reconstructed.
- **Scientific boundary:** these are deterministic synthetic-waveform MC outputs, not beam-data PCA, uncertainty, data/MC transfer, or detector-performance claims. Chapter 6 still contains unsupported PCA-spectrum and physical-interpretation statements and requires a separate correction.
- **Remaining work:** repair the next source-backed malformed ledger rows; synchronize Chapter 6 with the tracked MV6 representation contract; execute `AUD-ANOM-001` matched data/MC closure.
- **Status:** VALIDATED for this CL-023/CL-024 reconstruction unit; ledger-wide `AUD-LEDGER-001` and `AUD-ANOM-001` remain PARTIAL.
