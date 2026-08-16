# CCB single-stave optical simulation (issue #796)

A from-scratch Geant4 application that replaces the merged prototype
`scripts/stave_sim.cc`. It implements the repaired geometry, optical transport,
provenance, and test infrastructure described in
`starter_code/single_stave/GEANT4_IMPLEMENTATION_BLUEPRINT.md`. Remaining
analysis and detector-validation boundaries are documented below rather than
being treated as completed physics validation.

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
tests/               geometry, Birks, far-end, arrival, and ADC checks
CMakeLists.txt       headless-by-default build + CTest registration
```

## Build & test (LUNARC, needs Geant4 + optical physics)

```bash
module load Geant4            # or: source <g4-install>/bin/geant4.sh
cd geant4/single_stave
bash slurm/build.sh build     # cmake + build + ctest
```

CTest covers geometry/overlap, a small proton run, the geometry-report parser,
Birks visible-energy behavior, WLS profile configuration, far-end modes, SiPM
boundary arrivals, and SiPM ADC output. Some tests skip when optional Python
ROOT dependencies are unavailable; inspect the complete CTest output rather
than reporting only the process exit code.

## Run a calibration point

```bash
build/ccb_stave_sim --mode optical --particle proton --energy 100 \
    --nevents 2000 --seed 1 --hit-x 0 --hit-y 0 \
    --optical-dir build/optical --output stave_p100.root
```

Optical tables are **strict by default** (#978/#980): missing/malformed/unit-invalid
CSVs abort before event 0. Development-only permissive fallback is
`--allow-optical-fallback` (sets `authorising=false`). Production SLURM
(`slurm/submit_calibration.sh`) also passes `--strict-optical` explicitly.

Grid over many points on SLURM:

```bash
sbatch --array=0-$(( $(grep -cvE '^\s*(#|$)' slurm/points_example.csv) - 1 )) \
       slurm/submit_calibration.sh build slurm/points_example.csv out/
```

## Simulation modes

* `--mode optical` — full optical transport, with per-photon wavelength/time in
  the `photons` ntuple. Run each point until its preregistered statistical and
  stability criteria are met; a fixed event count alone is not acceptance.
* `--mode fast` — **not implemented**. The CLI rejects this option. A future
  response-kernel path requires held-out optical closure, uncertainty coverage,
  and a measured speedup before it can be enabled or used for physics.

## Outputs and analysis contract

The `events` ntuple stores quenched and raw Edep, scintillator track length,
entry/exit coordinates, generated scintillation/WLS/Cerenkov photon counts, and
per-channel arrival, detected-PE, saturated-PE, and ADC values for four
conceptual channels. The physical readout is fibre 1, +x; the other three are
simulation controls. In optical mode the `photons` ntuple stores `(event,
sensor, wavelength_nm, time_ns, path_len_mm, detected)`. `<output>.meta.json`
records the git commit, geometry hash, seed, configuration, and every optical
input-table SHA-256.

The current producer and `scripts/single_stave/analyze_single_stave.py` use
different branch names and units. First read
`scripts/single_stave/EVENT_CONTRACT.md` and run the explicit converter:

```bash
python scripts/single_stave/adapt_geant4_events.py \
  --input stave_p100.root --tree events \
  --run-id proton_100MeV_seed1 \
  --output stave_p100.normalized.parquet
```

Analyzer version 2.0.0 preserves the scintillation, WLS, and Cerenkov counters,
verifies their exact total, and uses `n_optical_generated_total` for arrival
bounds and collection-efficiency plots. This establishes schema/bookkeeping
compatibility for normalized inputs. Scientific acceptance still requires an
end-to-end execution on immutable real ROOT bytes with row-count and hash
closure plus review of all generated diagnostics.

## Parameter provenance & status

Optical tables and detector parameters are **representative literature/datasheet
priors**, each labelled in its CSV header (see
`research/DETECTOR_PARAMETERS.md` and `optical/optical_constants_ledger.conf`). PDE overvoltage, optical coupling, far-end
termination, and the exact TiO2 reflectivity are `UNKNOWN_EXTERNAL` pending the
run hardware settings — they are exposed as run-time systematics
(`--pde-scale`, `--coupling`, `--far-end`, `--reflectivity-scale`) so a scan
brackets them rather than a single invented number being asserted as truth.
