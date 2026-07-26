# Active Task

- **Task ID:** `AUD-DELTAE-008`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T052912Z`
- **Initial remote main SHA:** `ed3633055695184bd5ef68ab90bb6951e81d9354`
- **Scope:** prevent the canonical DeltaE event-table writer from silently treating arbitrary Parquet
  serialization failures as permission to publish a different CSV artifact, overwriting a validated
  input path, or leaving stale alternate-format tables that can be mistaken for current output.
- **Policy:** `DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT`.
- **Repository facts under review:** `_deltaE_E_core._write_table()` catches every exception from
  `DataFrame.to_parquet()` and falls back to `to_csv()`; output candidates are not compared with the
  exact input snapshots; publication is not atomic and an old alternate format is not reconciled.
- **Files in scope:** `scripts/single_stave/deltaE_E.py`, focused tests/audit tooling, validation
  JSON/SVG/Markdown, and matching coordination records.
- **Validation plan:** reproduce broad-exception fallback and input-alias behavior with deterministic
  controls; implement explicit engine-unavailable fallback only; use same-directory temporary files,
  flush/fsync, and `os.replace`; preserve previous final files on failure; remove only the stale
  alternate table after successful publication; record output policy in result/manifest contracts;
  run focused pytest, syntax, JSON/SVG, line-length, and exact-source audit checks.
- **Scientific boundary:** this is artifact-integrity engineering. It does not authorize an A-002
  amplitude convention, pulse polarity, stopping distribution, DeltaE-E PID result, calibration,
  uncertainty budget, or detector-performance claim.
- **Status:** `ACTIVE`
