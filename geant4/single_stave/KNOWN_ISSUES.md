# Single-stave sim — verified state (LUNARC, 2026-07-20/21)

> **UPDATE:** issues A & B below are RESOLVED (commit on feat/g4-optical-collection).
> Boolean-subtracted holes + world-daughter protruding fibres + external sensors +
> outer-only TiO2 reflector -> **overlap-free** (all volumes CheckOverlaps OK) and
> **photon collection works**: 100 MeV p -> arrival_readout mean 585, detected PE
> mean 178 (~10.6 PE/MeV). Geometry-report is now GEOMETRY_SELFCHECK and the ctest
> fails on Geant4's real 'Overlap is detected'.

# Single-stave sim — verified state & known issues (LUNARC run, 2026-07-20)

Findings from the first real runs on Geant4 11.2.2 (cosmos3, 100 MeV protons).

## Verified working

| Aspect | Evidence |
|---|---|
| Build | 100% compile, `ccb_stave_sim` links (after the proton/deuteron cast fix, #861) |
| ctests | 3/3 pass (geometry smoke, proton smoke, geometry-report) |
| Charged-particle physics / geometry | `edep_scint = 16.8 MeV` mean for 100 MeV p over 2.0 cm polystyrene — matches dE/dx ≈ 8 MeV/cm; confirms the 2 cm **normal** path length (the audit's key geometry concern) |
| Scintillation generation | after the distinct-material fix (this commit): `n_scint_generated ≈ 148k`/event (~10k/MeV yield). **Was 0** because the fibre core and scintillator shared the NIST `G4_POLYSTYRENE` singleton, so `BuildFibreCore()` clobbered the scintillation MPT with the WLS table. |
| Provenance | `<output>.meta.json` records git commit, geometry hash, seed, config, and all 7 optical-table sha256 |

## Open issue A — zero photon collection (P0 for optical calibration)

`arrival_readout = 0`, `detected_readout = 0` despite 148k photons/event
generated. Two root causes:

1. **Sensor/scintillator overlap.** The 4 endcap sensors are placed at
   `x = ±(kFibreHalfX + …) ≈ ±24.9 cm`, **inside** the ±25 cm scintillator box —
   Geant4 `CheckOverlaps` reports "Overlap is detected for volume
   Sensor_F1_PlusX with Scintillator". The degenerate geometry around the
   sensors prevents clean boundary-crossing detection.
2. **Fibre ends are buried inside the bar.** Fibres/holes are nested daughters
   of the scintillator (`kFibreHalfX = 24.9 < kStaveHalfX = 25`), so a photon
   reaching the fibre end exits into scintillator, not into an external sensor.

### Required fix (geometry-hierarchy refactor)
Per the blueprint's "Boolean subtraction of holes … is preferable":
- Bore the two holes as a `G4SubtractionSolid` **out of** the scintillator solid
  (so the scintillator genuinely excludes the hole channels).
- Place the fibre stack (gap → outer/inner clad → core) as **world** daughters,
  length **> bar** (e.g. half-length 26 cm), passing through the holes and
  **protruding ±1 cm** beyond the bar faces.
- Place the readout sensors on the **protruding fibre ends, in the world**
  (x ≈ ±26 cm), so `SteppingAction` sees a clean core→sensor boundary crossing.
- Re-verify WLS coupling (blue scint → Y-11 absorption → green re-emission →
  attenuation → sensor) produces nonzero detected PE, and that
  `generated ≥ arrival ≥ detected` holds per event.

## Open issue B — geometry-report false PASS

`PrintGeometryReport()` emits `OVERLAP_CHECK_PASS` from an **internal
constants** check; it does **not** reflect Geant4's real `CheckOverlaps`, which
found the sensor overlap. The report (and the `ccb_stave_geometry_smoke` ctest)
must parse Geant4's actual overlap output (the `/geometry/test/run` result and
the `G4PVPlacement` surface-check warnings) and fail on any detected overlap.

## Status
CCB-796-RUN: **build + charged-physics + scintillation-generation VERIFIED**;
**photon-collection readout IN_PROGRESS** (issues A/B above). The optical
calibration plots require issue A resolved first.
