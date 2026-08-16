# ADC saturation-world registry — issue #1073

**Status:** `BLOCKED_HARDWARE_EVIDENCE`  
**Parent:** #1014

## Worlds

| ID | Claim | Ceiling | Problem |
|---|---|---|---|
| A | S00 "14-bit V1742" | 16383 | Contradicts catalogue 12-bit V1742 |
| B | CAEN V1742 catalogue | 4095 | Incompatible with observed/project values >4095 without a transform |
| C | MC/chapter ~7000 | 7000 | Parametric/empirical; not proven hardware clip |

## Rule

`authorising_saturation_threshold()` **raises**. Diagnostic flags may use a named
world only when marked `authorising=False`.

Machine API: `ccb_mc_validation.daq.adc_saturation_registry`.

## S00 field-level authorization boundary

The canonical pulse-table column historically named `saturation` does **not**
become a hardware-censoring fact merely because the table itself passes its
count/selection gates. `ccb_mc_validation.daq.s00_saturation_field` defines the
field as `DIAGNOSTIC_ONLY_ADC_WORLD_UNRESOLVED` while this registry is blocked.
The legacy `peak_code_adc >= 16383` map may be reproduced only as explicitly
named World-A diagnostic semantics with `authorising=false`.

This is a field-level distinction: an S00 artifact can remain valid for a
separate, demonstrated selection/count contract while its saturation-dependent
claims are blocked. A consumer that needs physical clipping/censoring semantics
must call the authorising API and fail closed until the native→stored transfer,
rails, polarity, over-range behavior and any repacking/calibration are source
bound.

## Known integration gap (P0)

As of the audit at `main@896c6c0bca2fa0d5fdf50a5d33840e4b8ab75b60`,
`scripts/01_build_pulse_table_from_root.py` still computes and serializes
`waveforms.max(axis=-1) >= 16383` under the plain column name `saturation`, and
its canonical manifest has no saturation field-authorization record. Therefore
#1073 is **OPEN/PARTIAL**, not scientifically complete. Producer/schema migration
and downstream consumer audit are separate child atoms; no choice among 4095,
7000, or 16383 is authorized by this document.
