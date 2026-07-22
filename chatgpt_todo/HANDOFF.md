# Latest Handoff

## Session

- **UTC:** 2026-07-22T10:03:23Z
- **Task:** AUD-DELTAE-001 (PARTIAL)
- **Initial remote main:** `e44083917882ca5bd6375211a0bb74a3b6d73a37`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed scientific and engineering finding

The A-002 bridge had two independent hazards:

1. `eventno` was part of the aggregation/pivot index, so one physical `(run, evt)` could become multiple rows. This made the historical stopping bins total 632,939 while the report declared 385,984 physical events.
2. The corrected bridge still silently fell back to legacy `amplitude_adc`. A concurrent empirical audit on `main` measured that this name has table-dependent semantics: 17 of 19 inspected tables contain an ABSOLUTE peak code and two timing tables contain an already-NET value. Applying the 200 ADC stopping threshold directly to an absolute code near the pedestal would make populated layers pass spuriously; subtracting baseline from a net table would double-subtract.

The exact convention of the A-002 source table `reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz` was not measured in this session and was not present in the inspected 19-table listing.

## Work pushed directly to main

`scripts/single_stave/deltaE_E_data_bridge.py` now:

- emits one row per `(source_file_id, run, evt)`;
- excludes `eventno` from physical identity and retains it only for collision diagnostics;
- enforces output-row and stopping-bin cardinality invariants;
- accepts explicit net-height columns (`median_amp_adc`, `peak_height_adc`, `net_adc`) as NET;
- refuses to infer semantics for `amplitude_adc`;
- requires `amplitude_convention='absolute'` or `'net'` when legacy `amplitude_adc` is selected;
- requires `baseline_adc` and applies `abs(amplitude_adc - baseline_adc)` for ABSOLUTE input;
- uses NET input unchanged;
- records amplitude source column, convention, transform, and explicit-selection state in result metadata;
- rejects multiple explicit amplitude fields unless one is selected.

Regression coverage in `tests/test_deltae_data_bridge_composite_key.py` now exercises composite-key integrity, convention-free rejection, absolute conversion, net pass-through, missing-baseline rejection, and multiple-column ambiguity.

Immutable session record:

- `chatgpt_todo/archive/2026-07-22T100323Z_AUD-DELTAE-001_AMPLITUDE_CONVENTION.md`

## Validation

Exact temporary copies of the final code and tests were executed:

```text
python -m pytest /tmp/test_deltae.py -q
6 passed in 0.37s
```

The unrelated spreadsheet-runtime warmup emitted an error after Python startup, but pytest exited 0 and all six target tests passed.

## Main progression

- `e44083917882ca5bd6375211a0bb74a3b6d73a37` — initial remote main; concurrent real-table amplitude-convention correction.
- `88c9349a5c2a9022f7c7714a634fa4a2c89b78d8` — `fix(deltae): reject ambiguous amplitude fallback`.
- `4b700bc0ab9ead04d14b88704102930ac74800d4` — `test(deltae): gate ambiguous amplitude semantics`.
- `f7a509c303140239f0c5494cd87a3c3fcdb320b7` — `fix(deltae): transform measured amplitude conventions`.
- `b8d9eb0a5d49e8dfa0e5d4bb56e7d7c0d83bb28d` — `test(deltae): cover absolute and net amplitude conventions`.
- `22d037b14126a30a3c58b08d3bb18d836398042a` — `docs(audit): archive A-002 amplitude convention gate`.
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- No real A-002 pulse table was available.
- The source table's amplitude convention was not measured here.
- The bridge correction is validated on synthetic fixtures only.
- Historical A-002 stopping counts, CSV cardinality, and `DE-01_deltaE_E_data.png` remain FLAWED and quarantined.
- No replacement stopping counts, fractions, or ΔE–E density are claimed.
- Real-table regeneration remains `BLOCKED_COMPUTE`.

## Acceptance status

- Composite-key root cause and code correction: VALIDATED on synthetic regression.
- Table-dependent amplitude-semantics hazard: VALIDATED against repository-recorded empirical audit evidence.
- Convention-aware transform implementation: VALIDATED on synthetic regression.
- A-002 source-table convention: BLOCKED pending measurement.
- Corrected real-data JSON/CSV/figure: BLOCKED.

## Next action

Hash and inspect the exact A-002 pulse table. Measure whether its legacy `amplitude_adc` is ABSOLUTE or NET using baseline-relative distributions and `tools/audit/amplitude_convention_audit.py`. Prefer an explicit net-height field. If legacy `amplitude_adc` must be used, pass the measured convention explicitly. Then rerun the bridge and require unique composite keys, output row count equal to `n_events_composite_key`, and stopping-bin total equal to that same physical-event count before replacing quarantined outputs.
