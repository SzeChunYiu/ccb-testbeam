# ADR-SIPM-OPERATING-POINT-H1 — Overvoltage/temperature overrides
Status: ACCEPTED (fail-closed interim)
Date: 2026-08-11
Issues: #1072
Related: #976 #977 #981 #1066 #1071

## Decision

Until a source-bound overvoltage/temperature response surface exists, the
production Geant4 ↔ ccb-sipm-core integration treats the representative
S13360-3050CS operating point (3 V, 25 C) as **immutable provenance**.

`CCB_SIPM_OVERVOLTAGE_V` / `CCB_SIPM_TEMPERATURE_C` may only be set to the
profile values (idempotent). Any other value aborts before event 0.

## Rejected alternatives (for now)

- H2 separable scalar corrections — requires measured local slopes.
- H3 joint response surface — requires calibrated PDE/G/DCR/XT/AP(Vov,T).
- H4 discrete measured profiles — requires additional validated profiles.

## Consequences

- No OV/T systematic grid may claim a physics change via these env vars.
- Metadata continues to record the fixed profile OV/T.
- Revisit when device-specific surfaces are bound (#987 / calibration plan).
