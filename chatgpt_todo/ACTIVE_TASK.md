# Active Task

- **Task ID:** AUD-WIKI-002
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T041806Z
- **Initial remote main SHA:** `c9ff3196a1c5a4441119e6b19b592db1a8b5763b`
- **Scope:** remediate the public WIKI front door against canonical claim-ledger status, truth-type, and uncertainty provenance, then run the exact-file validator.
- **Completed work:** replaced all three raw-MV4 `PASS` labels with `VALIDATED`; aligned effective live-time to `data + MC self-consistent`; replaced the blanket uncertainty-completeness claim; restored `CL-007` and `CL-011` to the 43-column ledger schema; fixed duplicate summary-row truth checking; added focused tests and Markdown/JSON/SVG evidence.
- **Validation:** `py_compile`; `5 passed in 0.03s`; exact corrected WIKI plus bound ledger rows returned `VALIDATED` with zero issues; focused WIKI check found all 16 verified internal targets valid.
- **Scientific boundary:** no timing pull, live-time, pile-up rate, confidence interval, data, simulation, or detector-performance value was recalculated.
- **Remaining separate defect:** 24 of 26 claim-ledger rows still do not match the 43-column header and are tracked under `AUD-LEDGER-001` / `BLK-LEDGER-001`.
- **Status:** COMPLETE.
