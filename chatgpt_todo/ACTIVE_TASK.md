# Active Task

- **Task ID:** AUD-LEDGER-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T042917Z
- **Initial observed remote main SHA:** `6a0268b46cc7c848096019ea466b73901df1605b`
- **Latest base main SHA before writes:** `ef5a2167934f414e7cf064c210ddd22bb401ce20`
- **Scope:** establish a fail-closed, exact-byte validator for the canonical 43-column claim-ledger schema; measure every current row width; produce machine-readable and visual evidence; do not guess missing field placement.
- **Assumptions:** a width-mismatched CSV row cannot safely authorize interpretation of positional late fields; source-backed reconstruction of each malformed row is a separate required step.
- **Files:** `docs/claim_ledger.csv`; new `tools/audit/validate_claim_ledger_schema.py`; new focused tests and `docs/validation/claim_ledger_schema_*` evidence; relevant `chatgpt_todo/` ledgers and handoff.
- **Validation plan:** exact Git-blob reconstruction; `py_compile`; focused pytest; exact-ledger validator run; JSON parse; SVG XML parse; changed-file line-length scan; remote-main commit verification.
- **Measured current state:** header width 43; 26 data rows; only `CL-007` and `CL-011` are exact-width; 24 rows have 35--40 columns.
- **Status:** ACTIVE.
