# ADR: Runs 59–65 attenuation fits are non-authorising (#1033)

## Status
NONAUTHORISING pending identifiability contract.

## Context
Observed ADC-versus-position slopes mix optical attenuation with deposited
energy/species, Birks, trigger mixture, WLS transport, SiPM PDE/saturation,
electronics gain/baseline, and beam-spot changes. A single-exponential fit is
not identifiable as attenuation length without separating those nuisances.

## Decision
Any producer that emits an attenuation length / light-collection claim from
runs 59–65 must set:

- `attenuation_identifiability_status = UNRESOLVED`
- `authorising_attenuation_claims = false`

Fail closed: refuse `authorising=true` exports until a versioned
identifiability ledger binds held-out positions and nuisance controls.

## Related
Blocked on #987 (fibre count), #991 (stave length), #1008/#1079 (quenching),
#1010 (electronics).
