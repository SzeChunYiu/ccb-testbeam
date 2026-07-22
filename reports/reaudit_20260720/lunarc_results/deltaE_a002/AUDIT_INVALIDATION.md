# A-002 stopping-profile invalidation

## Status

**FLAWED — rerun required.**

The event-number collision result in `result.json` remains internally consistent:

- 385,984 distinct physical `(run, evt)` keys;
- 73,098 `eventno` values span more than one physical event;
- 146,196 physical events participate in those collisions (about 38%).

However, the committed stopping distribution and `DE-01_deltaE_E_data.png` are not valid physical-event summaries.

## Confirmed defect

The bridge declared `(source_file_id, run, evt)` as the physical event key, but built its wide table with:

```python
index=["run", "evt", "eventno"]
```

Therefore, any physical `(run, evt)` carrying more than one `eventno` value was split into multiple output rows. The inconsistency is visible without access to the raw table:

- declared physical events: **385,984**;
- stopping-bin total: **632,939**;
- excess rows: **246,955**.

A mutually exclusive stopping classification must sum exactly to the number of physical events. Since it does not, the published stopping counts, fractions, event CSV row count, and density plot cannot be interpreted as event-level results.

## Code correction

`scripts/single_stave/deltaE_E_data_bridge.py` was corrected on `main` to:

- aggregate hits by `(run, evt, stave)`;
- exclude `eventno` from the event-table key;
- retain `eventno` only for collision diagnostics;
- assert that the wide-table row count equals the physical composite-key count;
- assert that stopping-bin counts sum exactly to the physical-event count;
- report how many physical events contain multiple `eventno` values.

Regression coverage is in `tests/test_deltae_data_bridge_composite_key.py`.

## Required rerun

Regenerate, from the original pulse table:

- `result.json`;
- `deltaE_E_events_data.csv`;
- `DE-01_deltaE_E_data.png`.

Before promoting the replacement result, verify:

1. output key uniqueness on `(source_file_id, run, evt)`;
2. output row count equals `n_events_composite_key`;
3. stopping-bin total equals `n_events_composite_key`;
4. no `eventno` column participates in event identity;
5. input path, byte size, SHA-256, code commit, environment, and exact command are recorded.

The approximately 38% eventno-collision conclusion may be retained, but the stopping profile and ΔE–E density must remain quarantined until the corrected rerun is complete.
