# Active Task

- **Task ID:** AUD-LEDGER-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T042917Z
- **Initial observed remote main SHA:** `6a0268b46cc7c848096019ea466b73901df1605b`
- **Latest base main SHA before writes:** `ef5a2167934f414e7cf064c210ddd22bb401ce20`
- **Scope completed in this unit:** established a fail-closed, exact-byte validator for the canonical 43-column claim-ledger schema; measured every current row; produced machine-readable and accessible visual evidence without guessing missing field placement.
- **Implemented files:** `tools/audit/validate_claim_ledger_schema.py` v1.0.0; `tests/test_validate_claim_ledger_schema.py`; `docs/validation/claim_ledger_schema_{audit.md,validation.json,svg}`.
- **Validation:** exact ledger Git blob matched; `py_compile` passed; focused pytest returned `9 passed in 0.04s`; exact current ledger correctly returned process status 1 / `FLAWED`; JSON and SVG parsed; changed Python lines were at most 91 characters; remote implementation/test/SVG blobs matched locally validated files.
- **Measured current state:** header width 43; 26 data rows; only `CL-007` and `CL-011` are exact-width; 24 rows have 35--40 columns; malformed-row positional field interpretation is explicitly `WITHHELD`.
- **Scientific boundary:** no claim value, truth classification, uncertainty, source path, calibration, data result, simulation result, or detector-performance metric was recalculated or promoted.
- **Remaining work:** reconstruct each of the 24 malformed rows from its reports/scripts/data/configuration/history to all 43 fields; preserve intended nonempty values and caveats; require 26/26 exact rows; rerun WIKI, claim, link, and figure/source checks.
- **Status:** PARTIAL.
