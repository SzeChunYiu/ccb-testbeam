# Active Task

- **Task ID:** `AUD-FIG-006-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T192823Z`
- **Initial remote main SHA:** `cbc5ef1cc194ae976ffb05a0f7a2305ec8428088`
- **Policy:** `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`.
- **Delivered:** complete per-entry managed-output inventory; previous-report reconciliation; non-PASS, failure, removed-ID, and kind/suffix-change cleanup; safe registry IDs and prior-report path validation; symlink/nonregular-target rejection; report-publication rollback; direct lifecycle regressions; JSON/SVG evidence; detailed audit; immutable archive.
- **Deterministic results:** PASS-to-BLOCKED `2 -> 0` files; PASS-to-FAIL `2 -> 0`; removed ID `2 -> 0`; obsolete kind/suffix artifact `1 -> 0`; injected report failure restored prior PNG/CSV/report exactly; unsafe external path and `../ESCAPE` ID rejected.
- **Validation:** Python compilation passed; focused lifecycle pytest `9 passed in 0.81s`; reconstructed figure-registry suite `37 passed in 1.16s`; exact-source stale audit `VALIDATED` with zero findings; strict JSON and SVG parsing passed; maximum changed Python line length 96.
- **Remote blobs:** builder `6f2b8066799f045fe8c3a05549139c871a2ef27e`; registry `c64bf734b244a114ea7d5f259b32421cd59aaa25`; lifecycle tests `38591487747c3881052a5c30932afda1d0997fc5`.
- **Concurrent work:** merges `fa5b063...` and `81470c3...` were inspected and did not touch figure-registry files. Their Rmax script wording/exit semantics require a separate urgent audit.
- **Scientific boundary:** no paper figure, central value, uncertainty, calibration, timing, PID, stopping profile, pile-up rate, or detector-performance quantity was regenerated or accepted.
- **Unrun:** repository-wide pytest/ruff, complete shipped-registry build, paper build, link inventory, GitHub Actions.
- **Archive:** `chatgpt_todo/archive/2026-07-26T192823Z_AUD-FIG-006-R1_STALE_ARTIFACT_REMEDIATION.md`.
- **Acceptance:** focused software/provenance remediation `VALIDATED / COMPLETE`.
- **Next:** run the complete shipped registry and paper build in a full checkout; separately audit `check_rmax_formula.py` against the exposure/rate-identifiability contract.
- **Status:** `COMPLETE`
