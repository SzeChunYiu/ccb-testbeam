# Active Task

- **Task ID:** `AUD-DELTAE-005`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T040516Z`
- **Initial remote main SHA:** `87e81a490dd9889901fbfb18604685bc2e437d27`
- **Scope:** remediate the canonical `deltaE_E.py` CSV boundary so the exact composite event key
  `(source_file_id, run_id, event_id)` survives parsing and input provenance is bound to the bytes
  actually parsed.
- **Policy:** `DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`.
- **Implementation:** CSV-like inputs are read once as bytes, decoded strict UTF-8, and all three key
  columns are parsed as pandas strings. Same-snapshot byte count and SHA-256 are reused in the
  manifest. The established 761-line numerical core is retained by exact Git blob.
- **Validation:** exact front-door compilation passed; isolated boundary regression returned
  `4 passed in 0.03s`; AST-equivalent reader audit returned all required checks true; JSON and SVG
  parsing passed. The committed exact-source and full CLI regressions were not locally executed
  because the networkless container could not materialize the retained core.
- **Evidence:**
  - `docs/validation/deltae_csv_key_identity_validation.json`
  - `docs/validation/deltae_csv_key_identity.svg`
  - `docs/validation/deltae_csv_key_identity_audit.md`
  - `chatgpt_todo/archive/2026-07-26T040516Z_AUD-DELTAE-005_CSV_KEY_REMEDIATION.md`
- **Focused acceptance:** canonical CSV reader and provenance boundary `VALIDATED / COMPLETE`.
- **Scientific boundary:** no exact A-002 table, amplitude convention, polarity, stopping fraction,
  DeltaE-E PID, uncertainty, calibration, or detector-performance result is authorized.
- **Next action:** resolve `AUD-DELTAE-001`, `AUD-DELTAE-002`, and `BLK-AMP-001`, then run an immutable
  content-addressed production table through the strict reader and full scientific validation gate.
- **Status:** `COMPLETE`
