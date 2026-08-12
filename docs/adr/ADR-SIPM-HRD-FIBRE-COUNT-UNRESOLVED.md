# ADR: HRD stave fibre-count hardware contradiction (#987)

## Status
UNRESOLVED / NONAUTHORISING for light-collection claims.

## Context
Chapter 2 describes one Y-11 fibre per BC-408 bar. Executable Geant4 geometry
implements two fibre channels at y=±1 cm with four end sensors and only F1+x
labelled as the physical readout. Number/placement of fibres changes collection
efficiency, position dependence, timing, and SiPM coupling.

## Decision
Do not invent a hardware winner. Record:

- `hrd_fibre_count_status = UNRESOLVED_HARDWARE_CONTRADICTION`
- `authorising_light_collection_claims = false`

until a machine-readable hardware ledger cites MEASURED/CAD/BUILD_DOC evidence
and Geant4/chapter text are regenerated from that single source.

## Consequences
Runs 59–65 attenuation / light-collection analyses (#1033) remain diagnostic-only.
