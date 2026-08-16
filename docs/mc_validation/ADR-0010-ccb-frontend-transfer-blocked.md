# ADR-0010: CCB front-end transfer function remains BLOCKED

**Status:** BLOCKED  
**Date:** 2026-08-11  
**Issues:** #1010 (parent), #1067 (fail-closed measured impulse), #1068 (charge/peak units)

## Context

`ccb-sipm-core` labels its default electronics impulse as
`ASSUMPTION_GENERIC_CRRC_NOT_MEASURED`. Timing, pile-up, CFD/template phase,
saturation recovery, and waveform-shape MC closure are sensitive to the real
CCB front-end transfer function and noise covariance.

Issue #1010 requires a measured or identified CCB response
(`BENCH_MEASURED` or `DATA_FIT` on calibration runs with held-out closure).
No such measurement is bound in this repository at the time of this ADR.

## Decision

1. Do **not** invent a numerical front-end impulse, shaping time, undershoot,
   recovery pole, or noise covariance and label it as CCB-measured.
2. Production / publication paths that claim detector timing, pile-up
   resolvability, or waveform morphology **fail closed** unless the electronics
   response provenance is an authorized measured/identified class.
3. `ASSUMPTION_GENERIC_CRRC_NOT_MEASURED` and the MV0 parametric white-noise
   gain/noise/clip path remain available only for software development and
   explicitly labelled diagnostic proxies; they cannot authorize detector-
   performance claims.
4. Closure of this ADR requires binding a channel-identified impulse (or
   hierarchical `DATA_FIT` with held-out waveform residual closure) into
   `ModelConfig.measured_impulse_*` with fail-closed digest/runtime binding
   from #1067/#1068, then re-running the adversarial suite in #1010.

## Consequences

- Waveform/timing MC plots must record `electronics_response_authority=BLOCKED`
  (or an authorized digest) in provenance.
- Claim-ledger / study gates must refuse to promote generic-CRRC outputs to
  detector-performance evidence.
- Lane 09 Wave B therefore ships the fail-closed authority gate and this ADR
  rather than a fabricated transfer function.
