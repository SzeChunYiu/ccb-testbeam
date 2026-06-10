# GEANT4 simulation — reproduction status (CCB / Krakow test beam)

This folder holds the GEANT4 setup for the CCB test beam, provided by a colleague (the HIBEAM
`hibeam_g4` framework). Goal: generate **truth-labelled** events (particle type p/d, true energy,
hit positions/times) to compare against the real beam data — the one thing the data-only analysis
cannot provide (energy scale, p-vs-d PID, real pile-up truth).

## What's here
- `configs/krakow.config`, `configs/krakow.geoconf` — detector/geometry config (Wasa geometry,
  detectors TARGET, ProtoTPC, Sci_bar).
- `macros/run_krakow.mac` — 190 MeV protons, 2.3 mm CD₂ target, 10 mm beamspot, p-d elastic
  generator (`/ElGen`) using `sigma_pd_cm_190.txt`, `beamOn 1000000`, `WriteTree 1` (truth tree).
- `data/dedx_p_in_CD2.txt` — proton dE/dx (stopping power) in CD₂.
- `data/sigma_pd_cm_190.txt` — p-d elastic differential cross-section at 190 MeV.
- `geometry/krakow_109_8-38deg_4-71deg.root` — the test-setup geometry (TGeo).
- `setup_and_run.sh` — the build+run recipe (env, cmake, make, run).
- `readme_krakow_hg4.txt` — the colleague's original instructions.

## Reproduction attempt on this machine (2026-06-10) — HONEST STATUS

**Local stack available:** GEANT4 11.2.2, ROOT 6.24/02, VGM 5.4.0, Arrow/Parquet 19, cmake 3.28 —
plus a prebuilt `hibeam_g4` binary at
`/home/billy/nnbar/simulation/HIBEAM/Detector_simulation/hibeam_g4_build/hibeam_g4`.

**Result: the sim could NOT be cleanly built or run on this laptop — it needs the stack the
colleague built `hibeam_g4` against (most likely LUNARC).** Two blocking incompatibilities:

1. **Rebuilding `hibeam_g4-main` from source fails (~1356 compile errors).** cmake configures fine
   (finds GEANT4, ROOT, VGM, Arrow, Parquet), but compilation collides with this machine's **very
   new Arrow 19** and current GEANT4/ROOT headers: e.g. `operator<<` ambiguity between CLHEP and
   `arrow::`, `arrow::Status/Result/DataType` not found in scope, `G4VAnalysisManager not declared`,
   incomplete `TPCTrackManager`/`TString`/`G4Track`. The source was written for an **older Arrow**.
   Porting it to Arrow 19 is a real task, not a quick fix.

2. **The prebuilt binary is an older `hibeam_g4` version** that does not match the colleague's 2026
   `krakow.config`/macro: it parses the config and **loads the Krakow geometry ("Activating geometry
   Wasa")** but reports "unknown parsing" on several config lines and then aborts in event generation
   (`std::logic_error: basic_string null`) — its generator predates the `/ElGen` p-d elastic
   generator the macro uses. ROOT 6.24 also throws `TList` errors reading the geometry (writer
   version skew).

## How to actually run it (recommended)
Run on the **matching stack** — the LUNARC environment where `hibeam_g4` was built — using
`setup_and_run.sh` (adjust the GEANT4/ROOT/VGM/Arrow paths). That produces `output_krakow.root`
with the truth tree. Then compare to the data-driven results (energy ordering per stave, ΔE–E
proton/deuteron separation, penetration/topology).

Alternatively, port `hibeam_g4-main` to Arrow 19 on this laptop (fix the `arrow::` namespace and
GEANT4/CLHEP includes across `src/`), then `setup_and_run.sh` builds and runs locally.

## Near-term science without the full transport (already in flight)
The **dE/dx table is directly usable now**: ticket **S14g** anchors the energy calibration with the
real `dedx_p_in_CD2.txt` proton stopping power (replacing the empirical power-law range model), and
`sigma_pd_cm_190.txt` informs the p/d mix for PID (S15). These give a first simulation-input-vs-data
comparison while the full GEANT4 transport awaits the matching stack.
