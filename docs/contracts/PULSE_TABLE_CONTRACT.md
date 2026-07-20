# Pulse table contract (v1) — resolves P0 A-001

**Problem (A-001, CONFIRMED):** the canonical S00 pulse table stores an
amplitude that is **already baseline-subtracted**, but MV0/MV3 code paths treat
it as an absolute ADC code and subtract `baseline_adc` **again**. Any calibration
or stopping comparison built on the double-subtracted value is wrong. The
`92 ADC/MeV` (a.k.a. `92 ± 28`) gain and every MV3 threshold derived from it must
be re-derived from this explicit contract.

## Canonical definition (v1)

For each `(run, evt, stave)` the selected-pulse table stores:

| column | definition | units | notes |
|---|---|---|---|
| `run` | run id | — | part of the composite key |
| `evt` | event id within the run | — | NOT globally unique; never key on `evt` alone |
| `stave` | instrumented channel id | — | maps via the geometry/readout contract |
| `baseline_adc` | pre-pulse baseline level | ADC code | raw, NOT subtracted from amplitude below |
| `peak_height_adc` | `max(waveform - baseline)` over the window | ADC counts | **baseline ALREADY removed** |
| `peak_code_adc` | `max(waveform)` (absolute) | ADC code | optional; absolute peak sample |
| `saturation` | hardware saturation flag | bool | propagate downstream |

**Invariant:** `peak_height_adc` is the amplitude. **Do NOT** compute
`peak_height_adc - baseline_adc` — that is the A-001 bug. If a consumer needs an
absolute-code peak it must use `peak_code_adc`.

## Deprecation of the ambiguous name

The bare column name `amplitude_adc` is **ambiguous** (is it net or absolute?) and
is the root of A-001. Producers must emit `peak_height_adc` (net) and, where
available, `peak_code_adc` (absolute). `tools/audit/validate_pulse_schema.py`
flags `AMBIGUOUS_AMPLITUDE_ADC` when `amplitude_adc` appears without an explicit
`peak_height_adc`/`peak_code_adc`, and `AMPLITUDE_SCHEMA_DOUBLE_SUBTRACTION`
(via `tools/audit/audit_repository.py`) flags code that subtracts `baseline_adc`
from an amplitude column.

## Versioning & provenance

- `schema_version` MUST be written into the table metadata and any manifest.
- The producer (`scripts/01_build_pulse_table_from_root.py`) and every consumer
  (MV0 gain, MV3 stopping, digitizer) must record `schema_version` and the table
  sha256.
- Changing this contract is a new `schema_version`; downstream results are
  invalidated until re-run.

## Required actions (status)

| action | status | blocker |
|---|---|---|
| Publish this contract | **DONE** (this file) | — |
| `validate_pulse_schema.py` enforces it in CI | **READY** | wire into a CI gate |
| Regenerate the pulse table under v1 | **BLOCKED_COMPUTE** | needs raw ROOT + LUNARC |
| Re-derive 92 ADC/MeV gain (MV0) | **BLOCKED_COMPUTE** | depends on regenerated table |
| Re-run MV3 thresholds | **BLOCKED_COMPUTE** | depends on MV0 |
