# AUD-PULSE-001 — Pulse-schema provenance hardening

## Session

- UTC: 2026-07-22T08:06:55Z
- Initial remote main: `bcd5762ec8fc10a911e32e60a0b91b0d6fbd6d0c`
- Task: `AUD-PULSE-001`
- Write target: direct to `main`

## Repository evidence reviewed

- `tools/audit/validate_pulse_schema.py`
- `tests/test_audit_tools.py`
- `reports/reaudit_20260720/lunarc_results/pulse_schema_a001/REPORT.md`
- `reports/reaudit_20260720/lunarc_results/pulse_schema_a001/validation.json`
- commit `bcd5762ec8fc10a911e32e60a0b91b0d6fbd6d0c`

## Confirmed reproducibility gap

The A-001 result established that a real timing pulse table contains an ambiguous `amplitude_adc` field, but the committed validation JSON used abbreviated paths and did not include an immutable digest or byte size for the input table. A future reviewer could not prove which exact compressed table bytes were validated.

## Engineering change

`tools/audit/validate_pulse_schema.py` now records:

- exact CLI input path;
- input byte size;
- SHA-256 digest streamed in 1 MiB blocks;
- validator repository path;
- validator version `1.1.0`.

The loader help text now explicitly includes compressed CSV inputs. Existing validation semantics and exit codes remain unchanged.

## Regression test

Added `tests/test_pulse_schema_provenance.py`. It creates a gzip-compressed CSV pulse table, executes the validator, and verifies row count, path, byte size, SHA-256 digest, tool path, and tool version.

Exact temporary-copy validation:

```text
python -m pytest /tmp/exact_a001/tests/test_pulse_schema_provenance.py -q
1 passed in 0.07s
```

This session did not rerun the validator on the repository's real pulse tables because those large report inputs were not available in the local execution container. The A-001 scientific finding remains repository-recorded evidence; the new provenance fields will apply when the real validation is rerun.

## Main commits

- `0a480e51d4c0f744b47f86af67bd6c19f379822b` — `fix(audit): record pulse-table input provenance`
- `35e4b5787d25deae0a0db697e8fb6d25c4b14320` — `test(audit): cover compressed pulse-table provenance`

## Acceptance

- Validator provenance implementation: VALIDATED on synthetic compressed CSV.
- Real A-001 artifact regeneration with hashes: BLOCKED_COMPUTE / NOT RUN.
- MV0/MV3 numerical re-derivation after schema-v1 table regeneration: BLOCKED_COMPUTE.

## Next action

Rerun `validate_pulse_schema.py` against each real pulse table with full, non-abbreviated paths and commit the generated JSON containing SHA-256 provenance. Then regenerate schema-v1 pulse tables and re-derive all affected amplitude-dependent MV0/MV3 results.
