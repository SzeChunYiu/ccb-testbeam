# Latest Handoff

## Session

- **UTC:** 2026-07-22T22:04:00Z
- **Task:** AUD-AMP-002 (PARTIAL)
- **Initial remote main:** `8d4b1d45defb7dcdbb505489a3f09f381efc0274`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed evidence-governance finding

The authoritative pulse-table contract still stated that a raw `amplitude_adc` median could classify a legacy table and used the historical `17 ABSOLUTE / 2 NET` split to endorse subtraction for MV3 inputs.

That statement contradicted the current accepted implementation. `tools/audit/amplitude_convention_audit.py` v2.6.0 records every median-only label as `RAW_MEDIAN_HEURISTIC`, marks it `UNANCHORED`, leaves subtraction correctness unresolved, and returns nonzero. The preceding audit also established that historical labels overlap the former raw-median thresholds. Raw median is therefore not an identifying observable for physical amplitude convention.

## Work pushed directly to main

Updated `docs/contracts/PULSE_TABLE_CONTRACT.md` so it now:

- retains the historical 19-table scan only as heuristic evidence that the ambiguous column name carries inconsistent semantics;
- explicitly states that the `17 ABSOLUTE / 2 NET` split is not an accepted convention determination;
- prohibits downstream subtraction decisions based on that split;
- requires explicit schema metadata, producer-code evidence, or independently reviewed pedestal evidence;
- requires exact input hashing before a legacy table is used;
- preserves `peak_height_adc` and `peak_code_adc` under a versioned schema as the long-term resolution.

Updated `chatgpt_todo/ACTIVE_TASK.md` for AUD-AMP-002.

Immutable session record:

- `chatgpt_todo/archive/2026-07-22T220400Z_AUD-AMP-002_CONTRACT_RECONCILIATION.md`

## Validation

Cross-checked the corrected contract against:

- `tools/audit/amplitude_convention_audit.py` v2.6.0;
- the preceding `ACTIVE_TASK.md` and `HANDOFF.md` evidence boundary;
- the contract's historical correction text.

This was a bounded documentation consistency correction. No raw table, simulation, numerical result, plot, CSV, or ROOT file was modified or regenerated.

## Main progression

- `8d4b1d45defb7dcdbb505489a3f09f381efc0274` — initial remote main.
- `abc2c3b7df32adf5fb1bb47aece44472fcac8ff2` — `docs(contract): reject median-only amplitude conventions`.
- `072919af41ac6e029e121450839af9bcf1ce3b4b` — `docs(audit): claim amplitude contract reconciliation`.
- `08d415c07fd469e3913481166f44581e9a40fa57` — `docs(audit): archive amplitude contract reconciliation`.
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- The historical 19-table corpus was not rerun.
- The exact A-002 source table was not available.
- No legacy table convention is promoted by this documentation correction.
- Historical A-002 stopping counts, fractions, CSV, and figure remain quarantined.
- The complete repository test suite and CI were not run; the changed scientific artifact is documentation only.
- `SESSION_LOG.md` was not replaced because safe append semantics were unavailable through the connector; the immutable archive contains the full session record.

## Acceptance status

- Contract/implementation consistency: VALIDATED by direct source comparison.
- Median-only convention labels: NON-ACCEPTING.
- Historical 17/2 corpus classification: heuristic repository record requiring rerun and independent anchors.
- A-002 source convention and corrected outputs: BLOCKED.

## Next action

Run the current amplitude auditor over the exact A-002 source table and historical corpus without `--max-rows`. Resolve every unanchored record using schema metadata, producer code, or one uniquely identified pedestal-level field with a reviewed physical relationship to the amplitude column. Commit the generated JSON with exact paths, byte sizes, and SHA-256 values before passing a convention to `scripts/single_stave/deltaE_E_data_bridge.py` and regenerating the quarantined A-002 outputs.