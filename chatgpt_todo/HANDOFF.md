# Latest Handoff

## Session

- **UTC:** 2026-07-22T08:06:55Z
- **Task:** AUD-PULSE-001 (PARTIAL)
- **Initial remote main:** `bcd5762ec8fc10a911e32e60a0b91b0d6fbd6d0c`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Scientific and engineering finding

The real-table A-001 result confirmed an ambiguous `amplitude_adc` schema, but its committed validation JSON used abbreviated paths and omitted immutable input hashes and byte sizes. The exact compressed table bytes could therefore not be independently identified from the artifact alone.

## Work pushed directly to main

- Updated `tools/audit/validate_pulse_schema.py` to emit exact input path, byte size, streamed SHA-256 digest, validator path, and tool version `1.1.0`.
- Added `tests/test_pulse_schema_provenance.py` covering gzip-compressed CSV loading and all new provenance fields.
- Added immutable session record `chatgpt_todo/archive/2026-07-22T080655Z_AUD-PULSE-001_PROVENANCE.md`.
- Updated `chatgpt_todo/ACTIVE_TASK.md`.

## Validation

Executed exact temporary copies of the committed validator and regression test:

```text
python -m pytest /tmp/exact_a001/tests/test_pulse_schema_provenance.py -q
1 passed in 0.07s
```

The test verifies row count, input path, file size, SHA-256 digest, tool path, and version for a gzip-compressed pulse table.

## Main progression

- `bcd5762ec8fc10a911e32e60a0b91b0d6fbd6d0c` — initial remote main
- `0a480e51d4c0f744b47f86af67bd6c19f379822b` — `fix(audit): record pulse-table input provenance`
- `35e4b5787d25deae0a0db697e8fb6d25c4b14320` — `test(audit): cover compressed pulse-table provenance`
- `e5fa6d3812d77c9dbd3e5b58ac86d3c101279098` — `docs(audit): archive pulse-schema provenance hardening`
- `1148a2c8dada2718598030e5a028321c79470d2a` — `docs(audit): claim pulse-schema provenance task`
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- The code path was validated only with a synthetic compressed CSV.
- This session did not access or rerun the real timing or matched pulse tables.
- No raw ROOT input, schema-v1 table, MV0 gain, MV3 threshold, figure, or numerical scientific result was regenerated.
- The existing A-001 finding remains repository-recorded real-table evidence.
- Real artifact regeneration with full paths and SHA-256 provenance remains `BLOCKED_COMPUTE`.

## Acceptance status

- Provenance implementation: VALIDATED.
- Compressed-CSV regression: VALIDATED.
- Real A-001 validation artifact regeneration: BLOCKED.
- Affected MV0/MV3 re-derivation: BLOCKED.

## Next action

Run the updated validator against every real pulse table, using full paths and schema tags, and commit the generated JSON reports with immutable input hashes. Then regenerate schema-v1 pulse tables and re-derive every amplitude-dependent MV0/MV3 result before restoring any affected scientific claim.
