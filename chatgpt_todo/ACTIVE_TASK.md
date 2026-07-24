# Active Task

- **Task ID:** AUD-WIKI-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T103118Z
- **Initial remote main SHA:** `c254e767bbc225d98f9c839d50251c511ca69a98`
- **Scope completed in this unit:** rewrote the complete root `WIKI.md` to enforce the v1.2.0 exact-width canonical claim gate for Rmax, effective live-time, P04p duplicate-readout model selection, and P07e saturation recovery.
- **Public corrections:** numerical Rmax is withheld pending `S-STAT-003`; `3.0448717948717947 MHz` is superseded history only; duplicate-readout and saturation-recovery statements are separated and `GATED`; no production model or correction is authorized; MV5 Rmax is `BLOCKED`.
- **Canonical bindings:** `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, and `CL-016`, each required to have exactly 43 columns before interpretation.
- **Implemented files:** updated `WIKI.md`; added `tests/test_wiki_claim_front_door_current.py`; added Markdown, JSON, and SVG validation evidence.
- **Validation:** corrected WIKI is `21368` bytes with SHA-256 `baaa9dbd3585870c7d9c0807493e9afce81f9767f3be68d581502d62496c59d4` and committed Git blob `9d8110893adeae482b2439c4187b53f94174a55e`; validator v1.2.0 returned `VALIDATED` with zero issues; integration regression returned `2 passed`; stale Rmax mutation failed closed; focused internal-link check passed for 16 existing targets; JSON and SVG parsed.
- **Evidence policy:** `WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`.
- **Scientific boundary:** no detector data, simulation, fit, Rmax calculation, uncertainty interval, model training, calibration, or detector-performance result was generated.
- **Remaining work:** continue mapping and reviewing the remaining material WIKI claims and repair the 19 malformed claim-ledger rows; resolve `S-STAT-003`, `BLK-P04P-001`, and `BLK-P07E-001` before restoring or authorizing their claims.
- **Status:** PARTIAL at repository-wide scope; the root-front-door remediation unit is VALIDATED and complete.
