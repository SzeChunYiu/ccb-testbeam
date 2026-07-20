# CCB single-stave optical simulation (issue #796)

A from-scratch Geant4 application that replaces the merged prototype
`scripts/stave_sim.cc`. It fixes every defect catalogued in
`audit/KNOWN_CODE_DEFECTS.md` and follows
`starter_code/single_stave/GEANT4_IMPLEMENTATION_BLUEPRINT.md`.

## What was wrong with the prototype, and how this fixes it

| Prototype defect | Fix in this app |
|---|---|
| Primary traversed the 50 cm long axis, not the 2 cm thickness | `PrimaryGeneratorAction` launches at `z = -half_z-1mm`, direction `+z` → crosses the 2.0 cm normal thickness |
| `G4Tubs` fibres unrotated → axis along thickness, extend outside mother | Fibres rotated `rotateY(90°)` to lie along `x`; contained in the bar; overlap-checked |
| Photons counted by energy deposit in fibre (≈ always 0) | `TrackingAction` counts generated photons by creator process; `SteppingAction` counts boundary crossings into **named sensor volumes** and applies PDE after recording raw arrivals |
| `BeamOn` loop overwrote earlier energy points | One immutable config per invocation → one output file; provenance sidecar |
| No holes/cladding, no TiO2 surface, no PDE curve, no Birks knob | Explicit hole/gap → outer/inner cladding → core; TiO2 border optical surface; wavelength-dependent PDE table; configurable Birks `kB` |
| Qt5/ICU build failure | CMake builds headless by default; vis is an optional `-DCCB_ENABLE_VIS=ON` target |
| No seed/geometry/optical-table provenance | Seed, geometry hash, and per-table sha256 written to `<output>.meta.json` |

## Layout

```
include/  src/       C++ (AppConfig, DetectorConstruction, PhysicsList,
                     PrimaryGeneratorAction, RunAction, EventAction,
                     SteppingAction, TrackingAction, ActionInitialization,
                     OpticalTables, DetectorMessenger, main)
macros/              geometry_check, vis, proton_point, deuteron_point
optical/             versioned CSV tables (each has a provenance header)
slurm/               build.sh, submit_calibration.sh, points_example.csv
tests/               check_geometry_report.py + offline pytest
CMakeLists.txt       headless-by-default build + 3 ctests
```

## Build & test (LUNARC, needs Geant4 + optical physics)

```bash
module load Geant4            # or: source <g4-install>/bin/geant4.sh
cd geant4/single_stave
bash slurm/build.sh build     # cmake + build + ctest
```

Three ctests: geometry/overlap smoke (`OVERLAP_CHECK_PASS`), a 5-event proton
run, and the Python geometry-report assertions.

## Run a calibration point

```bash
build/ccb_stave_sim --mode optical --particle proton --energy 100 \
    --nevents 2000 --seed 1 --hit-x 0 --hit-y 0 \
    --optical-dir build/optical --output stave_p100.root
```

Grid over many points on SLURM:

```bash
sbatch --array=0-$(( $(grep -cvE '^\s*(#|$)' slurm/points_example.csv) - 1 )) \
       slurm/submit_calibration.sh build slurm/points_example.csv out/
```

## Two simulation modes

* `--mode optical` — full optical transport, keeps per-photon wavelength/time in
  the `photons` ntuple. Used to derive the response kernel. Run each point until
  the bootstrap uncertainty on mean detected PE is below the pre-registered
  threshold (analysis-side loop, not a blind photon count).
* `--mode fast` — optical detail suppressed; the analysis layer applies a
  pre-derived response kernel to large full-detector samples. Validate the
  kernel against held-out `optical` points.

## Outputs

`events` ntuple (per event): quenched + raw Edep, scintillator track length,
entry/exit, generated scintillation/WLS/Cerenkov photon counts, and per-channel
arrival / detected PE / saturated PE for all four conceptual channels
(readout = fibre 1, +x end; the other three are simulation controls). In
`optical` mode a `photons` ntuple stores `(event, sensor, wavelength_nm,
time_ns, path_len_mm, detected)`. `<output>.meta.json` records the git commit,
geometry hash, seed, config, and every optical-table sha256.

Analyze with `scripts/single_stave/analyze_single_stave.py`.

## Parameter provenance & status

Optical tables and detector parameters are **representative literature/datasheet
priors**, each labelled in its CSV header (see
`research/DETECTOR_PARAMETERS.md`). PDE overvoltage, optical coupling, far-end
termination, and the exact TiO2 reflectivity are `UNKNOWN_EXTERNAL` pending the
run hardware settings — they are exposed as run-time systematics
(`--pde-scale`, `--coupling`, `--far-end`, `--reflectivity-scale`) so a scan
brackets them rather than a single invented number being asserted as truth.
