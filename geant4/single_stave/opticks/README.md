# CCB Opticks GPU optical-photon bridge (optional production path)

Integrates Opticks GPU optical-photon transport into the CCB single-stave Geant4
sim as an OPTIONAL path behind a flag. The CPU Geant4 reference is untouched
(ctest 9/9 PASS). The Opticks build is referenced out-of-tree by path/env
(`$SPIKE` / `OPTICKS_PREFIX`); no Opticks source is vendored into this repo.

## What is here

| file | role |
|------|------|
| `CCBSensorIdentifier.h` | Annotates the 4 SiPM discs (`Sensor_F1/2_PlusX/MinusX`) as Opticks sensors by volume name + copyNo. Fixes the spike's `hit_total=0` gap at ingestion (GDML round-trip drops G4 SD status, and the default `U4SensorIdentifierDefault` only matches `PMT`). |
| `ccb_opticks_gpu.cc` | Bridge: `SetSensorIdentifier` + `G4CXOpticks::SetGeometry` (GDML->CSGFoundry, sensor-annotated) + per-event `setInputPhoton` (explicit scintillation gensteps from the sim's proton Edep) + `simulate` + `gatherHit`. |
| `build_bridge.sh` | Builds the bridge by injecting the two canonical repo sources into the configured Opticks g4cx build tree (how Opticks' own tests build). |
| `opticks_parity.py` | GPU-vs-CPU parity diagnostic plot + SUMMARY. |
| `run_opticks_parity.sh` | End-to-end driver (CPU ref -> GPU capture -> bridge -> plot). |

## Residuals (issue spec) -> status

1. **GDML export** — DONE in the sim, not here: `ccb_stave_sim --dump-gdml FILE`
   writes the production geometry after Initialize and exits (booleans + TiO2
   preserved). Ctest-guarded (`ccb_stave_gdml_export`).
2. **SiPM sensor annotation** — DONE/PROVEN: the ingested CSGFoundry reports
   `sensor_count = 4` with all four SiPM names and a populated `sensor_id` array.
3. **Explicit scintillation gensteps from proton Edep** — capture DONE in the sim
   (`--gpu-optical` / `CCB_GPU_OPTICAL=1`, ~1.49e5 photons/event, lambda ~454 nm
   in band, ctest-guarded `ccb_stave_gpu_optical_capture`); upload DONE in the
   bridge (Opticks `INPUT_PHOTON` genstep, 148720 photons dispatched).
4. **`--gpu-optical` flag (env `CCB_GPU_OPTICAL=1`), default OFF** — DONE.
5. **Parity diagnostic** — DONE as a diagnostic; see PARTIAL note below.

## PARTIAL: the last-mile device->host hit gather

On the A40, geometry ingestion, sensor annotation, and genstep upload all work
and the propagation launch is dispatched. The photon/hit component GATHER
returns null in the standalone `G4CXOpticks`/`CSGOptiXSMTest` invocation --
crucially for BOTH the input-photon bridge AND the spike's own torch, i.e. an
Opticks EventMode/component-save pipeline configuration point, NOT a sensor or
geometry defect. Resolving it needs the full Opticks event-save pipeline (the
in-tree `G4CXOpticks` Geant4 integration path) rather than the standalone test
binary. This is left documented rather than hacked.

The CPU reference distributions (per-sensor arrivals, wavelength/time/path) are
produced from a clean `--optical-out` run and plotted in
`figures/opticks/opticks_gpu_vs_cpu_parity.png` with the GPU status annotated.
