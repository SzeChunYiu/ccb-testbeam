# Active Task

- **Task ID:** `AUD-DELTAE-006`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T043100Z`
- **Initial remote main SHA:** `a29cc75dc403a9af2e804e55a53e8b037efd8942`
- **Scope:** bind canonical DeltaE Parquet rows, byte count, and SHA-256 to one exact immutable input
  snapshot before event-key validation, selection, data/MC joins, statistics, plotting, or manifest
  publication.
- **Policy:** `DELTAE_PARQUET_ROWS_AND_PROVENANCE_MUST_SHARE_ONE_BYTE_SNAPSHOT`.
- **Implementation:** `.parquet` and `.pq` paths are read once as bytes and parsed through
  `pandas.read_parquet(io.BytesIO(raw))`; the same retained bytes supply manifest size and SHA-256.
  Result and manifest reader contracts publish `SINGLE_READ_EXACT_BYTES`. CSV lossless-key behavior
  and the established numerical/plotting core remain unchanged.
- **Validation:** exact proposed files compiled; focused regression returned `7 passed in 0.04s`;
  exact former blob returned `FLAWED` with seven findings; exact current source returned `VALIDATED`
  with zero findings; deterministic path replacement changed the former manifest digest but not the
  current one; JSON and SVG parsing and line-length checks passed.
- **Evidence:**
  - `docs/validation/deltae_parquet_snapshot_validation.json`
  - `docs/validation/deltae_parquet_snapshot.svg`
  - `docs/validation/deltae_parquet_snapshot_audit.md`
  - `chatgpt_todo/archive/2026-07-26T043100Z_AUD-DELTAE-006_PARQUET_SNAPSHOT.md`
- **Focused acceptance:** canonical Parquet reader/provenance boundary `VALIDATED / COMPLETE`.
- **Scientific boundary:** no exact A-002 table, amplitude convention, polarity, stopping fraction,
  DeltaE-E PID, uncertainty, calibration, or detector-performance result is authorized.
- **Next action:** resolve `AUD-DELTAE-001`, `AUD-DELTAE-002`, and `BLK-AMP-001`, then run an immutable
  content-addressed production table through the strict reader and full scientific validation gate.
- **Status:** `COMPLETE`
