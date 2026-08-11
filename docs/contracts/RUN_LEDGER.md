# Run ledger (`ccb-run-ledger/1`) — issue #962

**Canonical Sample II calibration run: 64** (not 61).

## Evidence

- Newer report / `docs/02_data_and_runs.md` and `configs/s00_reproduction.yaml`
  define `sample_ii_calib: [64]` with run 61 in analysis.
- Older 54-page B-stack timing note used run 61; that role is recorded as
  `SUPERSEDED` on run 61 in `configs/daq/run_ledger.yaml`.

## Enforcement

`ccb_mc_validation.daq.run_ledger` loads the YAML ledger, rejects calibration∩
validation overlaps, and asserts the Sample II calibration decision.
