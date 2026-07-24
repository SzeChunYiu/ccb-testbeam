# Active Task

- **Task ID:** AUD-G4-021
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-24T020230Z
- **Initial remote main SHA:** `cdaf032c13f9967ad2a02c420987058b8a57a61b`
- **Scope:** audit whether the canonical stopping-power report can overwrite its simulation/reference inputs or leave a partial report when writing fails.
- **Confirmed source risk under review:** `run_compare()` writes directly with `out_path.open("w")` after reading the inputs, without an explicit output/input alias rejection or atomic temporary-file replacement.
- **Files:** `scripts/single_stave/compare_stopping_power.py`, new source-audit tool/tests, validation Markdown/JSON/SVG, and mandatory `chatgpt_todo/` ledgers.
- **Validation plan:** AST-based exact-pattern audit; synthetic vulnerable/fixed controls; focused `py_compile` and pytest; JSON and SVG parsing; line-length scan; exact current-source blob and limitations recorded.
- **Boundary:** this session can validate the software/provenance defect and remediation specification. It does not validate a real Geant4 export or accepted stopping-power closure.
- **Status:** ACTIVE
