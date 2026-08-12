# ADR-0012: Constant v_WLS = 17 cm/ns is a BLOCKED timing hypothesis

**Status:** accepted (BLOCKED physics claim)  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 09  
**Issues:** #1032

## Context

Chapter prose and timing notes use a single effective fibre speed
`v_WLS = 17 cm/ns` (`c / n_eff` with `n_eff≈1.76`) for one-ended B-stave
position→time corrections. No CCB measurement freezes that constant; WLS
fluorescence delay, modal dispersion, reflections, and SiPM/electronics response
are conflated into one number (Kodama et al. PTEP 2024 show multi-ns emission
structure and distance-dependent broadening for Y-11).

## Decision

1. Treat `v_WLS=17 cm/ns` as named hypothesis
   `wls_effective_speed_17cm_per_ns_H1`, not detector truth.
2. Authorising timing corrections that apply this constant must fail closed
   (`authorising=false`) until a measured/optical-transport model is bound.
3. Diagnostic/exploratory use may retain the constant if explicitly labelled
   `NONAUTHORISING_WLS_SPEED_HYPOTHESIS`.
4. No invented multi-mechanism model is promoted in this ADR.

## Consequences

- Documentation and study scripts must not promote absolute WLS-corrected times
  as measured without #1032 closure.
- No auto-close of #1032.
