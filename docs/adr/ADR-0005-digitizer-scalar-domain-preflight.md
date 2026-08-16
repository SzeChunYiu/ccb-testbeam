# ADR-0005: Digitizer scalar domain preflight before event 0

**Status:** accepted  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 05  
**Issues:** #1080

## Context

`DigitizerPipeline.from_config` previously accepted `n_samples=0`,
`sample_spacing_ns=0`, negative `transport_sigma_ns`, and non-finite floats,
which can yield empty/degenerate yet finite-looking waveforms.

## Decision

1. Centralize domain checks in
   `ccb_mc_validation.response.digitizer_domains.preflight_digitizer_config`.
2. Invoke preflight from `DigitizerPipeline.from_config` **before** returning a
   runnable pipeline (and therefore before event-0 RNG use).
3. Classify accepted zeros where intentional (`noise_rms=0`,
   `transport_sigma=0`) as `VALID_CONTROL`; reject nonphysical zeros
   (`n_samples`, `sample_spacing_ns`) as `INVALID_INPUT`.
4. Persist requested/effective/classification metadata for provenance (#1078
   follow-up).

## Consequences

- Invalid configs fail closed with `DigitizerDomainError` / exit code 2.
- Production configs in `configs/mc_validation/digitizer.yaml` remain valid.
