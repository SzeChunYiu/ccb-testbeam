# Active Task

- **Task ID:** AUD-WIKI-002
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-24T033502Z
- **Initial remote main SHA:** `e8b01b4414d2a797c5f97fe3ee98f88e99ad254a`
- **Validated code/test/evidence head:** `57dee4451352b27fc191cbc36805a2d0316600ff`
- **Scope:** audit the public WIKI front door against canonical claim-ledger status, truth-type, and uncertainty provenance.
- **Confirmed defects:** MV4 raw timing is labelled `PASS` three times although `PASS` is outside the WIKI legend and ledger claim `CL-007` is `VALIDATED`; effective live-time is labelled `data_only` although `CL-011` is `data_mc_self_consistent`; the front matter says every number has uncertainty although the ledger contains `CI_MISSING_BLOCKING` fields.
- **Validated work:** added a fail-closed validator, five focused tests, a Markdown audit, machine-readable JSON, and labelled SVG evidence. Exact cited WIKI lines plus exact ledger rows produced status `FLAWED`, process status 1, and eight issues.
- **Validation:** `py_compile`; `5 passed in 0.03s`; JSON and SVG parsed; maximum Python line lengths 91 and 92 characters.
- **Boundary:** no WIKI remediation, timing recalculation, pile-up recalculation, uncertainty completion, data processing, or simulation was performed.
- **Status:** PARTIAL. Correct the complete current `WIKI.md`, run the validator on full exact files, and require `VALIDATED` before completing this task.
