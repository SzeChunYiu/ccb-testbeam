# Latest Handoff

## Session

- **UTC:** 2026-07-22T09:01:34Z
- **Task:** AUD-DELTAE-001 (PARTIAL)
- **Initial remote main:** `59739b65e8b8002984196a6d924f39c4eec75a7b`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed scientific and engineering finding

The A-002 report declares 385,984 physical `(run, evt)` events, but its mutually exclusive stopping bins total 632,939. The 246,955-row excess is caused by `scripts/single_stave/deltaE_E_data_bridge.py` retaining `eventno` in both the aggregation and pivot indices while declaring `(source_file_id, run, evt)` as the physical key.

The approximately 38% eventno-only collision diagnostic is computed from unique `(eventno, run, evt)` relations and remains internally consistent. The stopping profile, generated event CSV cardinality, and `DE-01_deltaE_E_data.png` are not valid event-level outputs and are quarantined pending rerun.

## Work pushed directly to main

- Corrected the bridge to aggregate hits by `(run, evt, stave)` and emit exactly one row per physical composite key.
- Removed `eventno` from event identity while preserving it for collision diagnostics.
- Added explicit output-row and stopping-bin cardinality invariants.
- Added `physical_events_with_multiple_eventno_values` and `stopping_distribution_total` diagnostics.
- Added `tests/test_deltae_data_bridge_composite_key.py`.
- Added `reports/reaudit_20260720/lunarc_results/deltaE_a002/AUDIT_INVALIDATION.md`.
- Updated the A-002 report with a prominent FLAWED/quarantine banner.
- Added `AUD-DELTAE-001` to `chatgpt_todo/BACKLOG.md` and refreshed `ACTIVE_TASK.md`.
- Added immutable session record `chatgpt_todo/archive/2026-07-22T090134Z_AUD-DELTAE-001_CARDINALITY.md`.

## Validation

Executed exact temporary copies of the corrected bridge and regression test:

```text
python -m pytest /tmp/a002fix/tests/test_deltae_data_bridge_composite_key.py -q
2 passed in 2.65s
```

The synthetic fixture reproduces the old failure mode by assigning two eventno values to one physical `(run, evt)` event. The corrected bridge emits one row, excludes eventno from the key, and enforces that stopping bins sum to the physical-event count.

## Main progression

- `59739b65e8b8002984196a6d924f39c4eec75a7b` — initial remote main
- `6c64480723e51da421a2f840922746606b477062` — `fix(deltae): enforce one row per physical composite event`
- `52c64cb40e0937add38b1774a5b1d30f3ecdc2aa` — `test(deltae): catch eventno-induced composite-key row splitting`
- `efe7771dc9b0a0052ecf66c04690b1ea732f04da` — `docs(deltae): invalidate split-row A-002 stopping profile`
- `0cef39853312e8d8252bde7b704a6b0f1fe09829` — `docs(audit): track A-002 cardinality rerun`
- `e5b1a1dce78bdb17b18aa81c3452bb5d5ffdad2d` — `docs(audit): claim A-002 cardinality correction`
- `85d83b7a9cc452c234c0afec1e288d55ba2073e9` — `docs(audit): archive A-002 cardinality defect`
- `b37cdd79bf4a96444eb76ba696e1d6c73b62c812` — `docs(deltae): quarantine invalid A-002 stopping outputs`
- `1a7dff49d69ef8c49fb427236ebb17efd75bdbe8` — `docs(deltae): correct invalidation code path`
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- No real pulse table was available in this execution environment.
- The corrected bridge was validated on synthetic data only.
- The original A-002 `result.json`, CSV, and figure were preserved for provenance and explicitly invalidated rather than silently overwritten.
- No replacement stopping counts, fractions, or ΔE–E density are claimed.
- Corrected real-table regeneration remains `BLOCKED_COMPUTE`.

## Acceptance status

- Root-cause diagnosis: VALIDATED.
- Composite-key code correction: VALIDATED on synthetic regression.
- Eventno-collision conclusion: retained as repository-recorded real-data evidence.
- Historical stopping profile/CSV/plot: FLAWED and quarantined.
- Corrected real-data artifacts: BLOCKED.

## Next action

Run the corrected bridge against the original pulse table. Record input path, byte size, SHA-256, code SHA, environment, and exact command. Require uniqueness of `(source_file_id, run, evt)`, output row count equal to `n_events_composite_key`, and stopping-bin total equal to the same count before replacing the quarantined JSON, CSV, and figure.
