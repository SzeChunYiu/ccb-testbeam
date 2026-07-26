# Active Task

- **Task ID:** `AUD-DELTAE-005`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T030223Z`
- **Initial remote main SHA:** `f1a615d5b591b63c91b03124d243daf8372b61cd`
- **Scope:** audit whether the canonical `deltaE_E.py` CSV reader preserves the exact
  composite event key `(source_file_id, run_id, event_id)` before uniqueness checks and joins.
- **Policy:** `DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`.
- **Confirmed defect:** the current CSV branch uses default `pandas.read_csv(path)` inference.
  Exact source tokens `001` and `1` collapsed into one parsed key and produced one false data/MC
  inner-join match in the deterministic control. Lossless text parsing retained two keys and zero
  false matches.
- **Evidence:**
  - `docs/validation/deltae_csv_key_identity_validation.json`
  - `docs/validation/deltae_csv_key_identity.svg`
  - `docs/validation/deltae_csv_key_identity_audit.md`
  - `chatgpt_todo/archive/2026-07-26T030223Z_AUD-DELTAE-005_CSV_KEY_IDENTITY.md`
- **Validation:** compilation passed; focused pytest returned `6 passed in 0.09s`; JSON and SVG
  parsing passed; changed Python lines are at most 100 characters.
- **Focused acceptance:** audit tooling and evidence `VALIDATED`.
- **Production reader:** `FLAWED`; five findings remain and the canonical source was deliberately
  not modified in this audit unit.
- **Next action:** implement single-read strict UTF-8 and text dtypes for all three composite-key
  columns in `deltaE_E.py`, add direct reader/CLI regressions, and require this audit to return zero
  findings before a CSV-backed production rerun.
- **Scientific boundary:** no exact A-002 pulse table was processed and no amplitude convention,
  polarity, stopping fraction, DeltaE-E PID, calibration, uncertainty, or detector-performance
  result is authorized.
- **Status:** `PARTIAL`
