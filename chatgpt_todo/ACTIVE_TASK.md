# Active Task

- **Task ID:** `AUD-DELTAE-004`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T021210Z`
- **Initial remote main SHA:** `303da4b0d96b703de002d53abd98f0ca9c964250`
- **Scope:** diagnose and correct the Python/pandas-version-dependent provenance-identifier
  failure in the strict A-002 DeltaE-E CSV regression without weakening content-addressing.
- **Observed failure:** repository CI under Python 3.11 / pandas 3.0.5 loaded an all-digit
  40-character Git commit token as an integer, while the test expected the exact string.
- **Scientific risk:** an untyped CSV reader can change identifier type and can irreversibly erase
  leading zeros, making provenance ambiguous even when the authoritative JSON remains exact.
- **Policy:** `DELTAE_CSV_IDENTIFIERS_MUST_USE_AN_EXPLICIT_TEXT_READER_CONTRACT`.
- **Remediation:** added `docs/contracts/deltae_event_csv_reader.json`, integrated its nine text
  dtypes into the strict bundle regression, and added focused all-digit/leading-zero coverage.
- **Evidence:**
  - `docs/validation/deltae_csv_reader_contract_validation.json`
  - `docs/validation/deltae_csv_reader_contract.svg`
  - `docs/validation/deltae_csv_reader_contract_audit.md`
  - `chatgpt_todo/archive/2026-07-26T021210Z_AUD-DELTAE-004_CSV_READER_CONTRACT.md`
- **Validation:** Python compilation passed; focused pytest returned `3 passed in 0.03s`; the JSON
  and SVG parsed; renderer/test lines are at most 89/85 characters. Exact CI pandas 3.0.5 behavior
  remains bound to run `30181818642`, job `89739575939`.
- **Focused acceptance:** `VALIDATED / COMPLETE`.
- **Repository integration:** `PARTIAL`; no push-triggered workflow result was visible through the
  available connector, so repository-wide CI success is not claimed.
- **Next action:** run the exact full repository gate on the current integration head and audit all
  downstream DeltaE CSV consumers for explicit reader-contract use.
- **Scientific boundary:** no exact A-002 pulse table was processed and no amplitude convention,
  polarity, stopping fraction, DeltaE-E PID, calibration, uncertainty, or detector-performance
  result is authorized.
- **Status:** `COMPLETE`
