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
