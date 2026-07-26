# Active Task

- **Task ID:** `AUD-DELTAE-005`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T030223Z`
- **Initial remote main SHA:** `f1a615d5b591b63c91b03124d243daf8372b61cd`
- **Scope:** audit whether the canonical `deltaE_E.py` CSV reader preserves the exact
  composite event key `(source_file_id, run_id, event_id)` before uniqueness checks and joins.
- **Observed risk:** `read_table()` currently delegates CSV input to default `pandas.read_csv`
  inference. Exact text identifiers such as `001` and `1` can collapse to the same numeric value,
  creating false duplicate keys or false data/MC matches.
- **Policy:** `DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`.
- **Files under review:** `scripts/single_stave/deltaE_E.py`, CSV reader contracts, DeltaE tests,
  downstream Cluster A data-side reader, CI evidence, and the mandatory `chatgpt_todo/` records.
- **Validation plan:** add a fail-closed source auditor, executable synthetic controls, focused
  regressions, atomic machine-readable output, SVG evidence, and a content-addressed handoff.
- **Scientific boundary:** software/event-identity validation only; no A-002 amplitude, stopping,
  PID, calibration, uncertainty, or detector-performance claim is authorized.
- **Status:** `ACTIVE`
