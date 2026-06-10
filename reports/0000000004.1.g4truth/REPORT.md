# S17a: hibeam_g4 GEANT4 truth bridge feasibility and schema audit

- **Ticket ID:** `0000000004.1.g4truth`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Depends on:** S14/S15 weak-label energy/PID findings and program-audit ticket `0000000001.1.audit01`
- **Input checksums:** see `input_sha256.csv`
- **Git commit at execution:** `878ce92758857e3bb1f49867c10133dd8651d6bc`
- **Code/config:** `scripts/s17a_0000000004_1_g4truth_schema_validation.py`; external hibeam source `/home/billy/HIBEAM/Detector_simulation/hibeam_g4-main`

## 0. Question

Can the colleague-supplied `hibeam_g4` GEANT4 setup be built on this machine and run with the provided Krakow geometry/configuration to produce event-level truth for energy and particle identity, and does the resulting truth tree plausibly address the S14/S15 gap where data-only charge/depth labels are weak rather than true p/d labels?

## 1. Reproduction and feasibility gate

This ticket is not a raw CCB HRD reproduction study. The reproduction gate is therefore the exact external recipe in the ticket: build `hibeam_g4`, run the provided `krakow.config` and `run_krakow.mac`, and obtain `output_krakow.root` with `WriteTree 1`.

| Quantity | Expected | Observed | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| CMake configure | success | success | 0 | exact | yes |
| CMake build target `hibeam_g4` | success | success | 0 | exact | yes |
| Provided macro reaches `/run/beamOn 1000000` | yes | no | blocked | exact | no |
| Provided macro writes `output_krakow.root` | yes | no | missing output | exact | no |
| Patched no-`CSFile` smoke run writes ROOT | diagnostic only | 100000 entries | not a production replacement | n/a | yes |

The build is feasible, but the exact provided run macro is not compatible with the current hibeam source. The macro contains
`/ElGen/CSFile sigma_pd_cm_190.txt`; `ScatteringGenerator::DefineCommands()` registers only `/ElGen/E`, `/ElGen/TargetThickness`, and `/ElGen/Beamspot`. GEANT4 therefore reports `COMMAND NOT FOUND </ElGen/CSFile sigma_pd_cm_190.txt>`, interrupts the batch before `beamOn`, and writes no `output_krakow.root`. The process exits with status 0, so the log content, not only the shell exit status, is the decisive feasibility evidence.

## 2. Build method

The successful build used:

```bash
source /home/billy/anaconda3/etc/profile.d/conda.sh
conda activate nnbar_env
source /home/billy/nnbar/simulation/GEANT4_Packages/install/geant4-11.2.2/bin/geant4.sh
export VGM_INSTALL=/home/billy/nnbar/simulation/GEANT4_Packages/install/vgm
cmake -S reports/0000000004.1.g4truth/hibeam_g4-main \
  -B reports/0000000004.1.g4truth/build \
  -DVGM_DIR=/home/billy/nnbar/simulation/GEANT4_Packages/install/vgm/lib/VGM-5.4.0 \
  -DGeant4_DIR=/home/billy/nnbar/simulation/GEANT4_Packages/install/geant4-11.2.2/lib/cmake/Geant4
cmake --build reports/0000000004.1.g4truth/build --parallel 4
```

Two local build adaptations were required, both kept inside this ticket directory. First, CMake had to point at the installed VGM config rather than the VGM build-tree config, because the build-tree `VGMConfig.cmake` points at a missing installed `VGMTargets.cmake`. Second, the upstream `CMakeLists.txt` attempts to copy `${PROJECT_SOURCE_DIR}/../hibeam_g4_build/README.md`; that sibling README is absent under `/home/billy/HIBEAM/Detector_simulation`. I used a local symlinked source sandbox plus a placeholder sibling README in the ticket scratch area, without modifying the external source tree.

The configuration warning about RPATH ordering between system and conda libraries did not prevent linking or execution. GEANT4 version was `geant4-11-02-patch-02` and VGM reported version `5.4`.

## 3. Exact run failure

The exact requested command was executed from the staged run directory:

```bash
../build/hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root
```

It loaded the ROOT geometry and initialized physics, then failed before event generation:

| Run kind | Processed events | Wall time | Max RSS | `COMMAND NOT FOUND` | ROOT output |
|---|---:|---:|---:|---:|---|
| provided macro, 1M requested | 0 | 0:14.92 | 681508 kB | true | absent |
| patched no-`CSFile`, 100k | 100000 | 0:45.05 | 706312 kB | false | present |

The source-level cause is deterministic. The scattering generator constructor loads only `dedx_p_in_CD2.txt` from the working directory; it does not expose a cross-section file property. The current event generator samples the center-of-mass angle as

```text
theta3cm = pi * U(0,1)
```

and then applies two-body kinematics for a proton plus deuteron final state. Thus the supplied `sigma_pd_cm_190.txt` table is not merely missing from the working directory; it has no registered macro command in this revision.

## 4. Truth tree schema from patched smoke run

To document the available output schema, I ran a diagnostic macro that removed the unsupported `CSFile` line and changed `/run/beamOn 1000000` to `/run/beamOn 100000`. This is **not** a production truth sample because it omits the p-d differential cross-section weighting. It is a schema and plumbing test.

The patched ROOT file contains one TTree, `hibeam`, with 62 jagged vector branches. The branch groups are:

| Group | Branch pattern | Meaning |
|---|---|---|
| Primary | `PrimaryTrackID`, `PrimaryPDG`, `PrimaryEkin`, `PrimaryTime`, `PrimaryPos*`, `PrimaryMom*`, `PrimaryWeight` | generator-level primary proton/deuteron truth |
| TARGET | `TARGET_*` | sensitive hits in the target volume |
| ProtoTPC | `ProtoTPC_*` | sensitive hits in the prototype TPC volume |
| Sci_bar | `Sci_bar_*` | scintillator-bar truth hits |

Every detector group stores track id, layer ids, PDG code, deposited energy, time, track length, local/global position, and momentum. The full branch table is in `truth_schema.csv`.

Primary truth in the 100k patched run:

| PDG | Particle | Count | Mean Ekin MeV | Median Ekin MeV | 5%-95% Ekin MeV |
|---:|---|---:|---:|---:|---:|
| 2212 | proton | 100000 | 104.535 | 104.752 | 20.351 to 188.498 |
| 1000010020 | deuteron | 100000 | 85.027 | 84.817 | 1.063 to 169.193 |

The energy complement is physically plausible for two-body p-d scattering after the simple target energy-loss model: protons carry the higher mean kinetic energy, while deuterons retain the higher ionization density per hit in scintillator.

## 5. Scintillator validation against S14/S15 questions

The data-driven S14/S15 state before this ticket was: raw HRD pulse selection and depth ordering are reliable internal observables, but absolute energy and p/d PID remain weak-label or proxy claims. The program audit explicitly identifies GEANT4 truth as the missing bridge.

The patched GEANT4 smoke run supports the direction of that bridge, but not its production use:

| Metric | Value | 95% CI | Interpretation |
|---|---:|---:|---|
| `hibeam` tree entries | 100000 | n/a | one recorded truth row per generated event in patched run |
| `Sci_bar` truth hits | 126574 | n/a | scintillator truth support for 24.004% of tree entries |
| deuteron minus proton hit Edep | +16.237 MeV | [16.063, 16.412] | deuteron hits are more ionising per scintillator crossing |
| deuteron minus proton event total Edep | -13.245 MeV | [-14.115, -12.424] | proton-tagged events deposit more total scintillator energy because they produce more hits |

Layer-resolved truth shows the same caution. For `Sci_bar_LayerID1=1`, proton hits have mean Edep 17.05 MeV and deuteron hits 34.98 MeV. For `Sci_bar_LayerID1=2`, proton hits have mean Edep 26.64 MeV and deuteron hits 32.41 MeV, but deuteron statistics there are much smaller (651 hits versus 30462 in layer 1). This is qualitatively consistent with the S14/S15 picture: D-like tracks are high-ionization and terminal, while proton-like tracks penetrate further and accumulate more total stack energy. It also explains why total charge alone is not a clean p/d truth label.

## 6. Equations and interpretation

For a particle species \(s\) in the scintillator truth tree, the hit-level deposited-energy mean is

```text
mean_hit_Edep(s) = (1 / N_hits,s) * sum_i Edep_i,s .
```

The event-level total for species \(s\) is

```text
Edep_event(e,s) = sum_{i in event e, PDG_i=s} Edep_i ,
mean_event_Edep(s) = (1 / N_events,s) * sum_e Edep_event(e,s).
```

The bootstrap intervals in `validation_metrics.csv` resample the species-specific hit or event arrays with replacement using seed `1700041`. They intentionally do not include material, angular, or geometry systematics. The statistical precision is therefore not the limiting uncertainty; the dominant uncertainty is whether the generator samples the right p-d angular distribution and whether the geometry/material response maps to the actual HRD stack.

## 7. Systematics and caveats

- The exact ticket macro does not run because `/ElGen/CSFile` is not registered.
- The patched smoke run ignores `sigma_pd_cm_190.txt`; it samples scattering angle uniformly and must not be used as a p-d rate or angular truth sample.
- GEANT4 warns that material `Mylar` has fractional masses summing to 1.378, not 1.0. That is a material-model systematic large enough to block precision energy claims.
- `Use built-in Birks saturation` is disabled in the printed EM parameters. No Birks, optical-photon, light-collection, or ADC response is validated against HRD waveforms.
- The Krakow geometry exposes `Sci_bar_LayerID1` values 1 and 2 in this output, not the full B2/B4/B6/B8 naming convention used by the data-only HRD reports.
- The run does not align simulated events to raw CCB runs, currents, trigger conditions, or selected-pulse support.

## 8. Verdict

`hibeam_g4` can be built on this machine, and a no-`CSFile` diagnostic run produces a usable truth schema with primary PDG/energy and per-detector hit truth. The exact provided production macro, however, is currently blocked by a source/macro interface mismatch. Therefore S17a does **not** deliver a production GEANT4 truth file for S14/S15. It delivers a precise build/run recipe, the failure mode, the truth schema, and a limited smoke-run validation showing that per-hit deuteron ionization is higher while event-total energy is topology-dependent.

The next scientific step is to restore or document cross-section-file support in `ScatteringGenerator`, rerun the unmodified 1M macro, and only then compare p/d truth against the S14/S15 charge-depth action bands.

## 9. Reproducibility

From the repository root:

```bash
git checkout -B work-0000000004.1.g4truth origin/main
mkdir -p reports/0000000004.1.g4truth/build reports/0000000004.1.g4truth/run reports/0000000004.1.g4truth/logs
ln -s /home/billy/HIBEAM/Detector_simulation/hibeam_g4-main reports/0000000004.1.g4truth/hibeam_g4-main
mkdir -p reports/0000000004.1.g4truth/hibeam_g4_build
printf 'Local placeholder for hibeam_g4 CMake configure_file. Original sibling README was absent on this machine.\n' > reports/0000000004.1.g4truth/hibeam_g4_build/README.md
cp /home/billy/ccb-geant4/krakow.config /home/billy/ccb-geant4/run_krakow.mac /home/billy/ccb-geant4/krakow_109_8-38deg_4-71deg.root /home/billy/ccb-geant4/sigma_pd_cm_190.txt /home/billy/ccb-geant4/dedx_p_in_CD2.txt /home/billy/ccb-geant4/krakow.geoconf reports/0000000004.1.g4truth/run/
source /home/billy/anaconda3/etc/profile.d/conda.sh
conda activate nnbar_env
source /home/billy/nnbar/simulation/GEANT4_Packages/install/geant4-11.2.2/bin/geant4.sh
export VGM_INSTALL=/home/billy/nnbar/simulation/GEANT4_Packages/install/vgm
cmake -S reports/0000000004.1.g4truth/hibeam_g4-main -B reports/0000000004.1.g4truth/build -DVGM_DIR=/home/billy/nnbar/simulation/GEANT4_Packages/install/vgm/lib/VGM-5.4.0 -DGeant4_DIR=/home/billy/nnbar/simulation/GEANT4_Packages/install/geant4-11.2.2/lib/cmake/Geant4
cmake --build reports/0000000004.1.g4truth/build --parallel 4
cd reports/0000000004.1.g4truth/run
../build/hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root
sed '/\/ElGen\/CSFile/d; s#/run/beamOn 1000000#/run/beamOn 100000#' run_krakow.mac > run_krakow_no_csfile_100k.mac
../build/hibeam_g4 -c krakow.config -m run_krakow_no_csfile_100k.mac output_krakow_no_csfile_100k.root
cd ../../..
python scripts/s17a_0000000004_1_g4truth_schema_validation.py --root reports/0000000004.1.g4truth/run/output_krakow_no_csfile_100k.root --report-dir reports/0000000004.1.g4truth --original-log reports/0000000004.1.g4truth/logs/hibeam_run.full.log --patched-log reports/0000000004.1.g4truth/logs/hibeam_run_no_csfile_100k.full.log
```

Committed artifacts:

- `REPORT.md`
- `result.json`
- `manifest.json`
- `input_sha256.csv`
- `truth_schema.csv`
- `primary_truth_summary.csv`
- `sci_bar_pid_summary.csv`
- `sci_bar_layer_pid_summary.csv`
- `event_pid_edep_summary.csv`
- `validation_metrics.csv`
- `run_feasibility.csv`
- `validation_metadata.json`
- `logs/cmake_configure.log`
- `logs/cmake_build.log`
