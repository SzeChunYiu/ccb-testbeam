# AUD-AMP-004 — Hash-bound amplitude convention evidence

## Session

- UTC: 2026-07-23T00:10:19Z
- Initial remote main: `b72a9061ce1411e64521e6c71ef099c4c92e15d6`
- Task state: PARTIAL
- Write target: direct to `main`

## Confirmed flaw

Version 2.7.0 treated the coexistence of a complete, uniquely named pedestal column with bare `amplitude_adc` as sufficient to label the convention acceptable. Column coexistence is only a diagnostic: it does not prove whether `amplitude_adc` stores an absolute peak code or an already baseline-subtracted height. The pulse-table contract requires explicit schema metadata, producer-code provenance, or independently reviewed evidence.

## Implementation

`tools/audit/amplitude_convention_audit.py` v2.8.0 adds `--evidence-map`. The map is keyed by the exact input SHA-256 and permits only `ABSOLUTE` or `NET` conventions supported by one of:

- `EXPLICIT_SCHEMA_METADATA`
- `PRODUCER_CODE_PROVENANCE`
- `INDEPENDENTLY_REVIEWED_PEDESTAL_EVIDENCE`

The audit keeps median and pedestal diagnostics as heuristic fields but separates them from physics acceptance:

- `physics_convention`
- `physics_convention_evidence`
- `physics_acceptance`
- `physics_subtract_baseline_correct`

Without an exact hash-bound evidence record, the CLI emits `NO_HASH_BOUND_CONVENTION_EVIDENCE`, increments `n_unverified_conventions`, and exits nonzero. Evidence does not transfer after any byte-level file change.

## Validation

Executed locally on exact reconstructed files:

```text
python -m py_compile tools/audit/amplitude_convention_audit.py tests/test_hash_bound_amplitude_evidence.py
python -m pytest tests -q
11 passed in 0.09s
```

Coverage includes missing evidence, exact accepted evidence, file mutation invalidation, invalid evidence bases, pedestal-only diagnostics, and net/absolute evidence paths.

## Commits before handoff

- `39d7a4ab509a8213954bd677907410ea5b0d0dae` — `fix(audit): require hash-bound amplitude convention evidence`
- `5c2a07f580920d0728a998716e4af885bf65de0f` — `test(audit): cover hash-bound amplitude evidence`
- `275b543e536d6ef6f5555dd19f0a9ccc1a236048` — `test(audit): require evidence beyond pedestal coexistence`
- `063ba946d6b6fb9a6a6b1db1bd04a0f2e5ca036e` — `test(audit): gate physics use on hash-bound evidence`

## Evidence boundary

No real pulse table was available. No historical corpus classification, A-002 convention, stopping counts, fractions, event CSV, or DeltaE-E figure was regenerated. Historical A-002 outputs remain quarantined.

## Next action

Create a reviewed evidence map for the exact A-002 table only after hashing the file and tracing its producer/schema provenance. Run v2.8.0 without `--max-rows`; do not pass a convention to downstream physics code unless `physics_acceptance=ACCEPTABLE` and all malformed, nonfinite, ambiguity, and baseline-quality gates pass.
