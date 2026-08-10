# GAP-01: Krakau MC Stopping-Depth Material Budget Fix

> **Current authority (2026-08 audit): HISTORICAL / NONAUTHORISING.** The geometry edit and the numerical comparisons below are retained as legacy simulation diagnostics. The earlier label `IMPLEMENTED + VALIDATED` is superseded: this run predates closure of the current scattering-source, external-executable/input, stopping-table, weighting, selection-matching, and detector-response provenance gates (#1182, #1178, #1179, #1058; CL-021). Its χ² values therefore must not be used as validated evidence that material budget is or is not the dominant cause of the DATA↔MC discrepancy. The report remains useful as a conditional mechanism study under its historical generator/configuration.

## Historical status: IMPLEMENTED + VALIDATED at the time (now superseded)

## What was done

### 1. Geometry investigation
The Krakau test-beam geometry is defined by `hibeam_g4_geobuilder` (external repo,
`src/krakow.cxx`), producing `krakow_109_8-38deg_4-71deg.root`. The hibeam_g4
`WasaDetectorConstruction` imports this `.root` via VGM — it does NOT build geometry in C++.

MV3c audited the geobuilder source and confirmed:
- **Present**: CD2 target, Mylar window, Al beam pipe, trigger scintillators (since 2026-01-26)
- **Absent (the GAP-01 primary gap)**: inter-stave dead material between scintillator bars
  (bars placed back-to-back with zero gap in both HRDStack1/HRDStack2)

### 2. Material added (`build_krakow_gap01.C`)
The geometry is modified **in-place** on the existing TGeoManager (all env-configurable):

- **Inter-stave dead material**: thin FR-4-equivalent slabs (Z_eff~8, ρ=1.85 g/cm²)
  inserted between consecutive Sci_bar layers. Bars are shrunk by deadThk/2 in z
  to create the gap. Default: 0.162 cm/gap → 0.30 g/cm² per gap.
  - B-arm (4 bars, 3 gaps): 0.90 g/cm² total
  - A-arm (8 bars, 7 gaps): 2.10 g/cm² total
- **Upstream absorber** (optional, configurable): Al slab placed before each arm
  entrance face, rotated to match the arm orientation (RotateY). Default: OFF (0 cm).
  Enable via `GAP01_ABS_THK_CM` env var.

Parameters: `GAP01_DEAD_THK_CM`, `GAP01_DEAD_DENSITY`, `GAP01_ABS_THK_CM`,
`GAP01_ABS_MATERIAL` (all env-overridable).

### 3. Build
hibeam_g4 rebuilt from source on LUNARC against:
- conda env `hibeam_env` (ROOT 6.34.10, Geant4 11.2.2, CLHEP 2.4.6.2)
- VGM 5.3.1 (rebuilt from source)
- Modified ScatteringGenerator.cc (CSFile + DEdxFile support, from billy host fork)

### 4. Validation MC
100k events with the GAP-01 geometry (inter-stave dead material only, no absorber),
190 MeV p+CD2 scattering source, Threads 1.

## Results (MV3 v3 stopping-depth, threshold-corrected)

| Stave | MC OLD (1M) | MC GAP-01 (100k, inter-stave) | Data |
|-------|-------------|-------------------------------|------|
| B2    | 0.470       | 0.475                         | 0.876|
| B4    | 0.182       | 0.179                         | 0.063|
| B6    | 0.125       | 0.166                         | 0.039|
| B8    | 0.223       | 0.181                         | 0.023|

| Config | χ²/ndf | vs OLD |
|--------|--------|--------|
| OLD MC (no fix) | 68,269 | — |
| Inter-stave only (0.9 g/cm² B-arm) | 66,369 | 1.03× improvement |
| Inter-stave + 10 g/cm² Al absorber | 221,380 | 0.31× (WORSE) |

## Key finding

**Historical conditional finding:** under this exact legacy source/configuration, the inter-stave dead-material variation produced only a marginal numerical χ² change (1.03×), while the tested 10 g/cm² uniform Al absorber made that legacy discrepancy metric worse. Because the current source/selection/response/provenance chain is not closed, this does **not** establish a project-level conclusion that the real DATA↔MC discrepancy is not primarily a material-budget issue.

Within the historical fixture, the data stopping distribution was sharply peaked at B2 (87.6%) while the MC distribution remained broad under the tested material variations. Surviving mechanisms to retest after source/runtime closure include:
1. p+CD2 source-energy/angular-model differences;
2. energy-loss/straggling/multiple-scattering and actual upstream material;
3. DATA trigger/reconstruction/selection versus MC acceptance mismatch;
4. detector-response and digitization differences absent from truth-level comparisons.

**Current recommendation:** retain the GAP-01 scan as a conditional material-sensitivity study, but do not rank material versus source/selection/response explanations until the same current, content-bound MC population is propagated through matched reconstruction with nuisance/systematic variations.

## Files
- `geant4/configs/build_krakow_gap01.C` — geometry modification macro (env-configurable)
- `geant4/configs/krakow_gap01.config` — hibeam_g4 config for GAP-01 geometry
- `geant4/configs/run_gap01_100k.mac` — 100k-event validation macro
- `geant4/jobs/gap01_validation.sbatch` — Slurm job script
- `scripts/gap01_mv3_validate.py` — MV3 before/after validation + plot
