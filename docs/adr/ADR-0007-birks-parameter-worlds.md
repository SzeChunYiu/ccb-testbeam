# ADR-0007: Birks kB parameter worlds must be explicit

**Status:** accepted (fail-closed config); physical kB choice **BLOCKED** pending material/#1000 + calibration  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 05  
**Issues:** #1079 (related #1008, #979, #994)

## Context

Three incompatible quenching parameter states coexisted:

| World | Effective kB | Location |
|---|---|---|
| H1 | 0 (no quenching) | Chapter-10 MV0 prose after scan |
| H2 | 0.008 cm/MeV (= 0.08 mm/MeV) | Python `birks_quench` default when pipeline omitted kB |
| H3 | 0.126 mm/MeV (= 0.0126 cm/MeV) | Geant4 `AppConfig` / material ionisation |

A cm↔mm unit slip is a factor-of-ten error in the Birks argument.

## Decision

1. `DigitizerPipeline` stores `birks_kB_cm_per_MeV: float | None`.
2. `apply_birks=True` **requires** an explicit unit-tagged config key:
   `birks_kB_cm_per_MeV` or `birks_kB_mm_per_MeV` (converted ×0.1).
3. Unlabelled `kB` / `birks_kB` keys are rejected.
4. The algebraic helper may keep `0.008` only for low-level unit tests; it is
   **not** a production response identity.
5. Choosing among H1/H2/H3/H4 remains a scientific decision; this ADR only
   removes the silent mismatch.

## Consequences

- Cross-path Python↔Geant4 comparisons must declare a common unit-tagged kB.
- No invented “true” scintillator kB is published here.
