# Active Task

- **Task ID:** `AUD-DELTAE-004`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T021210Z`
- **Initial remote main SHA:** `303da4b0d96b703de002d53abd98f0ca9c964250`
- **Scope:** diagnose and correct the Python/pandas-version-dependent provenance-identifier
  failure in the strict A-002 DeltaE-E CSV regression without weakening content-addressing.
- **Observed failure:** repository CI under Python 3.11 / pandas 3.0.5 loaded an all-digit
  40-character Git commit token as an integer, while the test expected the exact string.
- **Scientific risk:** an untyped CSV reader can change identifier type and can erase leading
  zeros, making a provenance column ambiguous even when the authoritative JSON remains exact.
- **Policy:** `DELTAE_CSV_IDENTIFIERS_MUST_USE_AN_EXPLICIT_TEXT_READER_CONTRACT`.
- **Files in scope:**
  - `tests/test_deltae_data_bridge_strict.py`
  - `docs/contracts/deltae_event_csv_reader.json`
  - focused compatibility regression and validation evidence under `tests/`, `tools/audit/`,
    `docs/validation/`, and `chatgpt_todo/archive/`
- **Validation plan:** compile changed Python, run focused synthetic identifier tests locally,
  require the exact repository-wide GitHub Actions gate to pass or document every remaining
  failure, parse JSON/SVG evidence, and verify remote `main` contains the delivery commit.
- **Acceptance boundary:** this unit may establish a stable CSV reader contract and restore the
  provenance regression across pandas versions. It does not authorize A-002 amplitude semantics,
  stopping fractions, DeltaE-E PID, calibration, or detector performance.
- **Status:** `ACTIVE`
