# DAQ event-key contract (`daq-event-key/1`) — issue #961

**Status:** `PROVISIONAL_PENDING_PIPELINE_DOMAIN_CLOSURE`  
**Canonical key:** `(run, EVENTNO)`

## Decision

Use `(run, EVENTNO)` as the repository-level DAQ event identity for joins and
bootstrap clustering. `EVT` alone is forbidden: inventory evidence shows wrap at
16383 with heavy within-run duplication. `EVENTNO` is unique within inspected
raw ROOT runs but resets across runs, so `run` is mandatory.

## Why not closed

Exact key-set/domain closure across raw → ucesb → sorted → parquet (#957/#953)
is still outstanding. This contract prevents silent EVT/eventno misuse while
keeping the forensic gap explicit.

## Machine API

`ccb_mc_validation.daq.event_key_contract.validate_join_keys`.
