# ADR: Y-11 fluorescence yield defaults to one re-emission (#1088)

## Status
UNVERIFIED / NONAUTHORISING for absolute light-yield / ADC calibration.

## Context
Geant4 WLS processes default each absorption to one re-emitted photon unless an
explicit fluorescence-yield spectrum/contract is supplied. Absolute PE/ADC
comparisons that treat that default as measured Y-11 quantum efficiency are
scientifically unsupported.

Executable metadata on `main` already records:

- `wls_fluorescence_model = geant4_default_one_secondary`
- `wls_fluorescence_status = ASSUMPTION_UNIT_YIELD`

## Decision
Python and analysis gates must keep:

- `authorising_absolute_light_yield_claims = false`

while status is `ASSUMPTION_UNIT_YIELD` (or any non-`MEASURED_YIELD_SPECTRUM` /
`SOURCE_BOUND_YIELD` token). Do not invent a numeric yield.

## Consequences
Light-collection / absolute ADC calibration claims remain diagnostic-only until a
source-bound yield spectrum is configured and provenance-promoted.
