# ADR-SIPM-PDE-SOURCE-UNIFIED
Status: ACCEPTED
Date: 2026-08-11
Issues: #981

## Decision

One PDE source of truth for both the legacy diagnostic PE path and
ccb-sipm-core ADC path: `geant4/single_stave/optical/sipm_pde.csv`
(loaded via `OpticalTables`, hashed in run metadata).

Extrapolation policy: **zero outside the tabulated wavelength range**,
matching `ResponseSimulator::photon_detection_efficiency`. Endpoint clamping
in `OpticalCurve::Interp` is bypassed by an explicit out-of-range check in
`SteppingAction::PdeAt`.

## Consequences

- Editing the CSV changes both branches.
- Out-of-range (e.g. broadband Cerenkov tails beyond the table) yield PDE=0
  on both paths.
- Core embedded RepresentativeS13360 PDE knots are overwritten at integration
  time by the CSV contents.
