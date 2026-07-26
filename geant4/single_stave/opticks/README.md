# CCB Opticks GPU optical-photon bridge (optional production path)

Integrates Opticks GPU optical-photon transport into the CCB single-stave Geant4
sim as an OPTIONAL path behind a flag. The CPU Geant4 reference is untouched
(ctest 9/9 PASS). The Opticks build is referenced out-of-tree by path/env
(`$SPIKE` / `OPTICKS_PREFIX`); no Opticks source is vendored into this repo.

## What is here

| file | role |
|------|------|
| `CCBSensorIdentifier.h` | Annotates the 4 SiPM discs (`Sensor_F1/2_PlusX/MinusX`) as Opticks sensors by volume name + copyNo. |
| `ccb_setGeometry.cc` | **Gather-fix layer 1.** Sensor-annotated GDML -> CSGFoundry ingest. Installs `CCBSensorIdentifier` BEFORE `G4CXOpticks::SetGeometry`, so the cached CSGFoundry reports `sensor_count=4` (the generic `G4CXOpticks_setGeometry_Test` uses the default PMT-prefix identifier and yields `sensor_count=0`). |
| `ccb_opticks_gpu.cc` | Bridge: `SetSensorIdentifier` + `SetGeometry` + per-event `setInputPhoton` + `simulate` + `gatherHit`. Uses `EventMode=HitPhoton` (layer-2 fix) so the photon array is gathered (hits are derived on host from it). |
| `build_bridge.sh` | Builds the bridge + `ccb_setGeometry` by injecting the canonical repo sources into the configured Opticks g4cx build tree. |
| `opticks_parity.py` | GPU-vs-CPU parity diagnostic plot + SUMMARY. |
| `run_opticks_parity.sh` | End-to-end driver. Dumps the GPU GDML with `CCB_GPU_GEOM=1` (injects EFFICIENCY detect surfaces on the SiPMs), ingests via `ccb_setGeometry`, runs the bridge, plots. |

## Root cause of the "GATHER returns null / hit_total=0" symptom (3 layers)

The Opticks integration agent (#920) reported the GPU transport works (4.6M
photons/s, geometry ingests, photons propagate) but the photon/hit GATHER
returns null, and attributed it to an "EventMode/component-save pipeline
configuration point." Investigation on gpua40 (live artifacts, not commit log)
shows the symptom has **three** stacked layers, two of which are now fixed:

### Layer 1 — sensor annotation NEVER applied at ingest (FIXED)
The standalone `G4CXOpticks_setGeometry_Test` ingests with the DEFAULT
`U4SensorIdentifierDefault`, which matches the `"PMT"` volume-name prefix. CCB
SiPMs are named `Sensor_F1/2_PlusX/MinusX`, so **zero** sensors are recognised:
the cached CSGFoundry reported `sensor_count=0` (verified in the spike's
`logs/ingest.log`), no sensor boundary surfaces are created, and although
transport runs no photon can ever be attributed to a sensor. `ccb_setGeometry`
fixes this — verified `sensor_count=4` with all four SiPM names and a populated
`sensor_id` array.

### Layer 2 — Minimal EventMode does not gather the photon array (FIXED)
`QEvt::gatherHit` derives hits on HOST from the gathered photon array
(`count_if_sphoton` over `evt->photon`), and returns null when there is no
photon array. The default `Minimal` EventMode gathers `HitComp` only (no
photon). `SEventConfig::Initialize_Comp_Simulate_` also RE-DERIVES the
gather/save masks from EventMode during `QSim::init`, so the bridge's explicit
`SetGatherComp` was overridden. Fix: `SetEventMode("HitPhoton")` (or
`OPTICKS_EVENT_MODE=HitPhoton`) — verified the photon array (148674/event) is
now gathered.

### Layer 3 — device-side SURFACE_DETECT not applied (OPEN)
With sensors annotated + photon gathered, `num_hit` is still 0. The SiPM
boundaries lack a detect surface, so `DetectorConstruction` now attaches an
EFFICIENCY=1.0 skin surface (gated behind `CCB_GPU_GEOM` so the CPU path is
bit-for-bit unchanged — verified `SIPM_ARRIVALS total=2276` without the flag).
Per the Opticks GPU-kernel analysis (`qsim::propagate_at_surface`,
`U4SurfaceArray::addSurface`: `detect = EFFICIENCY`), this is the correct
detection configuration that survives the GDML round-trip and produces
SURFACE_DETECT (default HitMask `"SD"`). The boundary texture confirms
`detect=1.0` on all four sensor boundaries. **Nonetheless `num_hit` stays 0**
even for photons generated directly inside a SiPM volume, i.e. the device is
not flagging photons SURFACE_DETECT despite `detect>0` in the texture. This
remaining gap is a device-side detection-application issue (needs Opticks
kernel-level debugging, e.g. `qsim.h:1677` `propagate_at_surface` /
`qbnd.h fill_state` printf), not a sensor/geometry/EventMode configuration
point. Status is therefore still PARTIAL, not VALIDATED.

## Residuals (issue spec) -> status

1. **GDML export** — DONE: `ccb_stave_sim --dump-gdml FILE` (ctest-guarded).
2. **SiPM sensor annotation** — DONE/VERIFIED via `ccb_setGeometry`
   (`sensor_count=4`). The prior "sensor_count=4" claim was stale: the generic
   ingest produced `sensor_count=0`.
3. **Explicit scintillation gensteps** — DONE: `--gpu-optical` /
   `CCB_GPU_OPTICAL=1` (~1.49e5 photons/event); bridge `INPUT_PHOTON` genstep.
4. **`--gpu-optical` flag, default OFF** — DONE.
5. **Parity diagnostic** — DONE as a diagnostic; see PARTIAL note above.

The CPU reference distributions (per-sensor arrivals, wavelength/time/path) are
produced from a clean `--optical-out` run and plotted in
`figures/opticks/opticks_gpu_vs_cpu_parity.png` with the GPU status annotated.
