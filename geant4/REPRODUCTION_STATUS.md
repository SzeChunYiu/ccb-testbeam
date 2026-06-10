# GEANT4 simulation — BUILT & RUN (CCB / Krakow test beam)

**Status (2026-06-10): SUCCESS.** The colleague's HIBEAM `hibeam_g4` GEANT4 sim was reproduced
(built from the official GitHub source) and run on billy, producing truth-labelled events.

## How (the key was the environment)
Build/run the OFFICIAL GitHub source (`HIBEAM-NNBAR/hibeam_g4`) in the **conda env `nnbar_env`**
(its compiler + ROOT 6.32 + GEANT4 11.2.2 + VGM 5.4.0). See `setup_and_run.sh`. The earlier
failures were entirely environment: the **system gcc-13** rejected GEANT4's `G4VAnalysisManager`
struct/class tag (cascading 1000s of errors), and the **system ROOT 6.24** crashed at runtime
(`libCling` mismatch). With `nnbar_env` it builds with 0 errors and runs cleanly.
Run: `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root` → truth tree `hibeam`.

## Truth output (tree `hibeam`)
Per event: primary (PDG, Ekin, momentum) + per-detector hits TARGET / ProtoTPC / **Sci_bar**
(the scintillator staves) with `LayerID` (depth), `PDG` (true particle), `EDep`, time, position,
momentum. This is the **truth the data lacks**: per-stave energy AND particle identity.

## First sim-vs-data comparison (30k events) — see `results/sim_vs_data.png`
- **Range-telescope confirmed:** Sci_bar hits fall with depth (layer 0→7), as the data's
  B2≫B4>B6>B8.
- **PID truth (new!):** deuterons stop early (layers 0–1: d-fraction ≈0.38) while protons dominate
  deep layers (layers 4–7: p-fraction ≈0.9). This is the ΔE–E proton/deuteron separation that the
  data could only infer at sample level — now per-event truth (enables S15 PID).
- **Quantitative gap to resolve:** the simulated penetration falls more gently than the data's
  selected-pulse counts (data drops ~40× B2→B4; sim ~1.3× layer0→1). Expected, because the data's
  `A>1000 ADC` selection keeps stopping/Bragg-peak pulses, and the Sci_bar `LayerID`↔B-stave
  mapping + exact geometry/energy still need pinning. This is the next study (for the workers).

## For the workers
The truth output is at `/home/billy/ccb-geant4/output_30k.root` (read-only, jail-visible).
Workers should USE it (not rebuild the sim): supervised p/d PID, energy-scale validation vs the
data-driven S14 calibration, and reconciling the penetration/selection mapping.
