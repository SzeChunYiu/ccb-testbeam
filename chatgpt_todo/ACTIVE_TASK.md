# Active Task

- **Task ID:** AUD-DELTAE-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T042815Z
- **Initial remote main SHA:** `86c6e086d3716ab3ac10481fae92f1a316adf2d3`
- **Scope:** add a fail-closed, content-addressed rerun entry point around `scripts/single_stave/deltaE_E_data_bridge.py` without changing the already validated composite-key and signed-polarity transformation.
- **Repository evidence:** bridge blob `7f50ce667a6cde07e94717d0187831da4d8459ac`; focused test blob `3b59a793f5d67e6a0d3c7117c42ec41ad7b84a90`; backlog tasks `AUD-DELTAE-001`/`AUD-DELTAE-002`; blocker `BLK-AMP-001`.
- **Confirmed engineering gap:** the current `main()` uses hard-coded paths, rereads the input through pandas without exact-byte provenance, writes JSON/CSV/PNG directly, omits command/runtime/code hashes, and cannot safely support the required immutable A-002 rerun bundle.
- **Planned files:** strict runner, focused synthetic tests, validation JSON/Markdown/SVG, matching backlog/index/blocker/handoff/session records, and immutable archive.
- **Validation plan:** py_compile; focused pytest covering input hash mismatch, before/after replacement, output aliases, atomic preservation, metadata propagation, and synthetic bridge integration; JSON parse; SVG XML parse; changed Python line-length check; remote blob reread.
- **Scientific boundary:** exact A-002 bytes and polarity evidence are unavailable, so this run cannot regenerate or accept the physical stopping distribution or ΔE–E result.
- **Status:** ACTIVE
