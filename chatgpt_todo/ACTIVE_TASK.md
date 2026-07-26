# Active Task

- **Task ID:** `AUD-DELTAE-008`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T052912Z`
- **Initial remote main SHA:** `ed3633055695184bd5ef68ab90bb6951e81d9354`
- **Scope:** prevent the canonical DeltaE event-table writer from silently treating arbitrary Parquet
  serialization failures as permission to publish a different CSV artifact, overwriting a validated
  input path, or leaving stale alternate-format tables that can be mistaken for current output.
- **Policy:** `DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT`.
- **Implementation:** both event-table output candidates are checked against retained exact input
  snapshots; stale alternate formats fail closed; completed same-directory temporary artifacts are
  fsynced and published with `os.replace`; failed temporaries are removed; CSV-gzip fallback is
  permitted only for a recognized missing Parquet engine; result and manifest metadata record the
  output contract.
- **Validation:** syntax passed; focused tests returned `14 passed in 0.05s`; exact-source audit
  returned `VALIDATED` with zero findings; arbitrary failure, engine-only fallback, prior-final
  preservation, direct/symlink alias, stale alternate, replacement failure, malformed source,
  invalid UTF-8, atomic audit JSON, JSON/SVG parsing, and line-length controls passed.
- **Evidence:**
  - `docs/validation/deltae_table_output_contract_validation.json`
  - `docs/validation/deltae_table_output_contract.svg`
  - `docs/validation/deltae_table_output_contract_audit.md`
  - `chatgpt_todo/archive/2026-07-26T052912Z_AUD-DELTAE-008_TABLE_OUTPUT_INTEGRITY.md`
- **Focused acceptance:** event-table output boundary `VALIDATED / COMPLETE`.
- **Scientific boundary:** no exact A-002 table, amplitude convention, pulse polarity, stopping
  fraction, DeltaE-E PID, uncertainty, calibration, or detector-performance result is authorized.
- **Next action:** resolve `AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and
  `BLK-AMP-001`, then run the content-addressed production table through the full scientific gate.
- **Status:** `COMPLETE`
