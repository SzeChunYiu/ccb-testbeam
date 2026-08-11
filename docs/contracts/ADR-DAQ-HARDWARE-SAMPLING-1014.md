# ADR: DAQ digitizer identity vs 100 MS/s sampling — issue #1014

**Status:** BLOCKED  
**Date:** 2026-08-11  
**Lane:** Wave A / Lane 08

## Context

`docs/academic_chapters/02_experimental_setup.md` names the HRD waveform
digitizer as a **CAEN V1742** while stating native analysis sampling of
**100 MS/s (10 ns/sample)**. CAEN's catalogue separates:

| Family | Model example | Native sampling | Bits |
|---|---|---|---|
| 742 | V1742 / VX1742 | up to **5 GS/s** (DRS4 SCA) | 12 |
| 724 | V1724 / VX1724 | **100 MS/s** flash ADC | 14 |

The chapter currently combines a 742-family model name with a 724-family rate
unless an explicit firmware/decimation/repacking transform is documented. This
also contaminates ADC-range worlds in #1073 (12-bit 4095 vs 14-bit 16383 vs
empirical 7000).

## Decision

**Do not invent hardware.** Until crate inventory, firmware, and unpacker
evidence recover one source-bound digitizer+transform contract:

1. Public/authorising claims that assert "V1742 native 100 MS/s" remain **BLOCKED**.
2. Timing/MC code must not treat 10 ns as proven V1742-native aperture.
3. Chapter 2 wording is marked contradictory pending forensic recovery.
4. Related saturation semantics stay under the #1073 fail-closed registry.

## Consequences

- No silent choice of V1724 vs V1742 in code defaults.
- ADR status stays BLOCKED until hardware/firmware evidence lands.
- Downstream #1009/#1010 schemas consume this ADR rather than chapter prose.
