# Active Task

- **Task ID:** `AUD-TIMING-003-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T190253Z`
- **Initial remote main SHA:** `be97e1a1e77de3bba6305f28802d1c876d2d1605`
- **Trigger:** PR #939 merged after current-main audits had demonstrated event-identity, residual-visualization, and individual-stave-inference defects.
- **Policy:** `REAL_DATA_CFD_REQUIRES_COMPOSITE_EVENT_KEYS_AND_PAIR_ONLY_INFERENCE`.
- **Delivered:** collision-safe `(run,event_id)` contract; duplicate stave-row rejection; pair-only inference denial; median-centered full/core residual diagnostics with quantiles and tail counts; nonfinite JSON safeguards; atomic text publication; legacy report/result quarantine; eight regressions; JSON/SVG evidence; detailed audit; immutable archive.
- **Deterministic results:** event-ID-only control identifies one value while the composite key preserves two events and residuals `[1.0,1.0]`; synthetic full-range underflow/overflow `0/0`, core underflow/overflow `1/1`; individual-stave authorization `false`.
- **Validation:** Python compilation passed; focused pytest `8 passed in 0.05s`; evidence `VALIDATED` with zero findings; strict JSON and SVG parsing passed; maximum changed Python line length 95.
- **Scientific boundary:** no ROOT file or beam event was processed; historical PR #939 metrics and PNGs are quarantined, not revalidated; a content-addressed rerun is required.
- **Unrun:** repository-wide pytest/ruff, producer execution, ROOT hashing, figure regeneration, link inventory, GitHub Actions.
- **Archive:** `chatgpt_todo/archive/2026-07-26T190253Z_AUD-TIMING-003-R1_CFD_PRODUCTION_SAFEGUARDS.md`.
- **Acceptance:** software remediation `VALIDATED / COMPLETE`; production physics result `PAIR_ONLY_PENDING_CONTENT_ADDRESSED_RERUN`.
- **Next:** execute producer v2.0.0 on immutable LUNARC ROOT bytes, review composite-key closure and regenerated diagnostics, then consider pair-level scientific acceptance; do not infer individual staves without validated deconvolution.
- **Status:** `COMPLETE`
