# AUD-AMP-002 — amplitude contract reconciliation

## Session

- UTC: 2026-07-22T22:04:00Z
- Repository: `SzeChunYiu/ccb-testbeam`
- Base remote main: `8d4b1d45defb7dcdbb505489a3f09f381efc0274`
- Write target: `main`

## Confirmed contradiction

`docs/contracts/PULSE_TABLE_CONTRACT.md` stated that the historical 19-table scan could classify bare `amplitude_adc` by a raw median threshold and used that classification to endorse subtraction for MV3 inputs.

The current accepted auditor, `tools/audit/amplitude_convention_audit.py` v2.6.0, does the opposite: every median-only label is recorded as `RAW_MEDIAN_HEURISTIC`, marked `UNANCHORED`, and makes the run non-accepting. The current handoff also records that historical labels overlap the former thresholds, so raw median is not an identifying observable.

## Change

The correction section of `docs/contracts/PULSE_TABLE_CONTRACT.md` now:

- preserves the historical `17 ABSOLUTE / 2 NET` split as repository-recorded heuristic evidence only;
- states that raw median does not uniquely identify physical convention;
- prohibits use of that split to authorize subtraction or non-subtraction;
- requires explicit schema, producer-code evidence, or independently reviewed pedestal evidence;
- requires exact input hashing before a legacy table is used;
- keeps the versioned `peak_height_adc` and `peak_code_adc` schema as the long-term resolution.

## Validation

Reviewed together:

- `docs/contracts/PULSE_TABLE_CONTRACT.md` before editing;
- `tools/audit/amplitude_convention_audit.py` v2.6.0;
- `chatgpt_todo/ACTIVE_TASK.md` and `HANDOFF.md` from the preceding session.

This was a documentation consistency correction. No raw table, simulation, numerical result, plot, CSV, or ROOT file was changed or regenerated.

## Evidence boundary

- The historical 19-table corpus was not rerun.
- The exact A-002 source table was not available.
- No table convention is promoted by this change.
- Historical A-002 stopping outputs remain quarantined.

## Main commits

- `abc2c3b7df32adf5fb1bb47aece44472fcac8ff2` — `docs(contract): reject median-only amplitude conventions`
- `072919af41ac6e029e121450839af9bcf1ce3b4b` — `docs(audit): claim amplitude contract reconciliation`

## Next action

Run the current auditor over the exact A-002 table and historical corpus without prefix sampling. Resolve every unanchored record using schema metadata, producer code, or a uniquely identified pedestal-level field with a reviewed physical relationship to the amplitude column. Commit the provenance JSON before regenerating A-002 outputs.