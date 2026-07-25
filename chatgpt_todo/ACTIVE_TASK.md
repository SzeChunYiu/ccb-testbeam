# Active Task

- **Task ID:** AUD-DELTAE-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T042815Z
- **Initial remote main SHA:** `86c6e086d3716ab3ac10481fae92f1a316adf2d3`
- **Validated implementation/evidence head:** `2606d00c377746b991c12824911f89012357d739`
- **Scope completed:** added a fail-closed, content-addressed and transactional rerun entry point around `scripts/single_stave/deltaE_E_data_bridge.py` without replacing the already validated composite-key and signed-polarity transformation.
- **Repository evidence:** bridge blob `7f50ce667a6cde07e94717d0187831da4d8459ac`; focused bridge-test blob `3b59a793f5d67e6a0d3c7117c42ec41ad7b84a90`; strict runner blob `76f7ffda2c2af92b400ca61f2f12c2b34fff7dba`; strict test blob `796ccc908d54246881b3774fba5a7853e8201b03`.
- **Correction:** expected input SHA-256 plus before/after identity, clean expected repository commit, exact script/command/runtime provenance, unique physical-key and finite-output checks, provenance-bearing JSON/CSV/SVG, output containment protection, explicit overwrite, and staged complete-bundle replacement with rollback.
- **Validation:** focused py_compile passed; focused pytest returned `9 passed in 1.79s`; JSON and SVG parsed; changed Python lines are at most 97 characters; synthetic fixture produced 2 event rows, 2 unique composite keys, and stopping total 2; committed source blobs were re-read from `main`.
- **Evidence:** `docs/validation/deltae_strict_rerun_audit.md`, `deltae_strict_rerun_validation.json`, `deltae_strict_rerun.svg`, and immutable archive `chatgpt_todo/archive/2026-07-25T042815Z_AUD-DELTAE-001_STRICT_RERUN.md`.
- **Scientific boundary:** exact A-002 bytes and convention/polarity evidence were unavailable; no production rerun, accepted stopping distribution, uncertainty budget, ΔE-E PID result, or detector-performance claim is made.
- **Status:** PARTIAL — validated software/provenance progress is on `main`; completion requires the exact evidence-authorized A-002 rerun and independent scientific closure.
