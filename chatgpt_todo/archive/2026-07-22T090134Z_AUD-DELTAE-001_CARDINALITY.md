# AUD-DELTAE-001 — A-002 event-cardinality correction

- **UTC:** 2026-07-22T09:01:34Z
- **Initial main:** `59739b65e8b8002984196a6d924f39c4eec75a7b`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed finding

The A-002 report and `result.json` declare 385,984 physical `(run, evt)` events, but the stopping counts sum to 632,939. The 246,955-row excess is caused by retaining `eventno` in the aggregation and pivot indices despite declaring `(source_file_id, run, evt)` as the physical key.

The approximately 38% eventno-collision diagnostic is computed independently from unique `(eventno, run, evt)` relations and remains internally consistent. The stopping profile, event CSV row count, and ΔE–E density are invalid until rerun.

## Code change

`scripts/single_stave/deltaE_E_data_bridge.py` now:

- aggregates by `(run, evt, stave)`;
- excludes `eventno` from event identity;
- reports physical keys with multiple eventno values;
- asserts one output row per physical composite key;
- asserts stopping-bin totals equal the physical-event count.

Added `tests/test_deltae_data_bridge_composite_key.py`.

## Validation

```text
python -m pytest /tmp/a002fix/tests/test_deltae_data_bridge_composite_key.py -q
2 passed in 2.65s
```

The tests reproduce the old split-row condition with one `(run, evt)` carrying two eventno values and verify that exactly one physical row is emitted.

## Scientific status

- eventno-only collision conclusion: retained as repository-recorded real-data evidence;
- stopping counts/fractions: FLAWED;
- `deltaE_E_events_data.csv`: FLAWED until regenerated;
- `DE-01_deltaE_E_data.png`: FLAWED until regenerated;
- corrected real-table outputs: BLOCKED_COMPUTE.

## Required rerun

Run the corrected bridge on the original pulse table, record source path/size/SHA-256, code SHA, environment and exact command, and verify key uniqueness, row-count equality and stopping-bin closure before replacing the quarantined outputs.
