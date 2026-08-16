# ADR-0004: Production DAQ digitizer requires measured transfer function

**Status:** accepted (gate); physical closure **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 06  
**Issues:** #1009 (related #952, #993, #977, #885)

## Context

Geant4 `EventAction` runs `ccb::sipm::ResponseSimulator`, obtains
`result.waveform.adc`, then discards the waveform and persists only
`peak_raw - baseline`. The core internal grid (`sample_dt_ns ≈ 0.5`) is not
the HRD DAQ observation grid. Historical `s17c_*_digitized_g4_waveform_bridge`
configs and `ccb_mc_validation.digitizer` use an **18-sample / 10 ns**
parametric model that is not lineage for the forensic **8×16** HRD product.

## Decision

1. **Do not invent** sample intervals, clocks, apertures, trigger-phase models,
   or electronics impulse responses for production data/MC waveform claims.
2. Publish a versioned `daq_digitizer_registry.json`
   (`schema_version: 2026.0-waveB-lane06`) under `configs/transport/`.
3. **Fail closed** via
   `ccb_mc_validation.transport.authorize_production_daq_digitizer`:
   missing `daq_digitizer_schema_id`, non-`APPROVED` status, or missing
   `measured_transfer_function.evidence_digest` → `StudyBlockedError`.
4. Mark parametric 18-sample bridges as `LEGACY_PARAMETRIC_STUDY` only.
5. Keep internal high-resolution SiPM response grids distinct from the DAQ
   observation grid; never rename one as the other.
6. Promote a schema to `APPROVED` only after measured transfer-function
   evidence and the resolved #952/#993 waveform contract are digest-bound.

## Current registry state

| schema_id | status | notes |
|---|---|---|
| `hyp_hrd_8x16_nominal_10ns_unmeasured` | **BLOCKED** | 8×16 nominal description without measured TF |

No `APPROVED` production schema exists yet.

## Consequences

- Production waveform persistence / DAQ-sampled MC comparison remains
  **BLOCKED** until measured TF + authorised schema land.
- Scalar `adc_*` peak diagnostics may continue as non-authorizing diagnostics.
- Callers cannot override `n_channels` / `samples_per_channel` /
  `sample_interval_ns` against an approved measured schema.

## Alternatives considered

1. **Downsample every 20th 0.5 ns sample to fake 10 ns** — rejected; not an
   ADC aperture/clock/phase model.
2. **Authorize the 18-sample parametric bridge as production** — rejected;
   contradicts #993 lineage rules for the 16-sample product.
3. **Invent a CR-RC prior as the HRD transfer function** — rejected by this
   ADR and the Wave B lane charter.
