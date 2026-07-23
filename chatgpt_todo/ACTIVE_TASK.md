# Active Task

- **Task ID:** AUD-G4-009
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T15:02:28Z
- **Initial observed main SHA:** `e6dd97da2d50cc81e9f49f8dab7cb2c8395fa6eb`
- **Latest main before writes:** `abb8a34ec47b6d62fae2ec07b837b71d2077bece`
- **Implementation/evidence head:** `28345eb2417fdbd87d595984a82a513cfa26af2e`
- **Scope:** audit simulation-event CSV ingestion used before the PSTAR deposited-energy diagnostic; prevent malformed rows, ambiguous aliases, unsupported particles, and mixed raw/quenched semantics from being silently omitted or misinterpreted.
- **Confirmed defect:** current `compare_stopping_power.py` silently continues past rows with missing particle, energy, deposit, or nonpositive/missing track length and chooses the first populated alias. A synthetic three-row table with a missing middle-row energy returned two usable rows with no failure.
- **Validated change:** added `validate_stopping_power_sim_table.py` v1.0.0, 17 focused tests, Markdown/JSON evidence, and a deterministic synthetic SVG. The preflight validates every noncomment row, exact alias occupancy, finite physical values, consistent deposit semantics, and input byte/SHA-256 provenance.
- **Commands:** `python -m py_compile tools/audit/validate_stopping_power_sim_table.py tests/test_validate_stopping_power_sim_table.py`; `python -m pytest tests/test_validate_stopping_power_sim_table.py -q`; JSON/XML parsing and changed-file line-length scan.
- **Validation:** `17 passed in 1.31s`; JSON/SVG parse passed; changed Python lines are at most 100 characters; local tool/test SHA-256 values are recorded in the session archive.
- **Boundary:** this is a standalone preflight. The legacy comparison CLI does not invoke it automatically, and no real event CSV, Geant4 run, PSTAR closure, calibration, or detector-performance claim was validated.
- **Status:** PARTIAL — validator, tests, provenance output, and visual evidence are validated on `main`; remaining acceptance requires canonical CLI integration plus validation on real exported event tables.
