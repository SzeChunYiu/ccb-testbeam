# Active Task

- **Task ID:** AUD-WIKI-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T090650Z
- **First observed remote main SHA:** `0f0e79031777faa203c086860d6a163d10c838ae`
- **Accepted latest-main base after concurrent P07e completion:** `5e7f9c96ac604eef63be356da0131fc492b5173d`
- **Scope completed in this unit:** corrected the linked academic executive-summary front door so Rmax, effective live-time truth type, MV4 raw timing status, C12 truth scope, P04p duplicate-readout selection, and P07e saturation recovery match exact-width canonical claim state and existing source-backed audits.
- **Implemented files:** corrected `docs/academic_chapters/01_executive_summary.md`; added `tools/audit/validate_executive_summary_claims.py` v1.0.0, focused tests, Markdown audit, machine-readable JSON, and accessible SVG evidence.
- **Validation:** `py_compile` passed; focused pytest returned `5 passed in 0.03s`; corrected summary validated with zero issues against an exact 43-column extraction of `CL-007`, `CL-010`, `CL-011`, `CL-015`, and `CL-016`; JSON and SVG parsed; changed Python lines are at most 96 characters; committed source/test blobs match locally validated bytes.
- **Scientific decisions:** Rmax is withheld under S-STAT-003; MV4 raw status is `VALIDATED`, not `PASS`; C12 remains truth-labelled MC only; no canonical P04p winner is named; P07e saturation correction remains withheld because external duplicate closure is worse than raw.
- **Public wording removed:** `ML wins (confirmed)`, established `Rmax ≈ 3.05 MHz`, and empirical-sounding C12 wording.
- **Evidence policy:** `EXECUTIVE_SUMMARY_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`.
- **Scientific boundary:** no raw ROOT data, waveform extraction, model refit, bootstrap regeneration, Rmax physics derivation, C12 data identification, calibration, or detector-performance result was generated.
- **Remaining work:** synchronize the root `WIKI.md` Rmax and P04p/P07e wording; continue source-backed reconstruction of the 19 malformed ledger rows; resolve S-STAT-003 and the P04p/P07e validation blockers before changing their statuses.
- **Status:** COMPLETE for the executive-summary chapter correction; `AUD-WIKI-001` remains PARTIAL repository-wide.
