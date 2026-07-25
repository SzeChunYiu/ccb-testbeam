# GAP-01: Krakau MC Stopping-Depth Material Budget Fix

## Status: IMPLEMENTED + VALIDATED (χ² improvement modest; root cause is broader than material alone)

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

**The inter-stave dead material (the MV3b primary gap) has been added but produces only
a marginal χ² improvement (1.03×).** A scan of upstream absorber thickness shows that
adding 10 g/cm² Al makes the χ² WORSE — the absorber shifts protons from B8 to B4/B6
instead of concentrating them at B2 as the data requires.

**The data-MC discrepancy is NOT primarily a material-budget issue.** The data's stopping
distribution is sharply peaked at B2 (87.6%), while the MC produces a broad distribution
regardless of how much uniform material is added. This points to additional physics issues:
1. The p+CD2 scattering energy spectrum may be too broad (too many high-energy protons)
2. Energy-loss straggling or multiple-scattering effects in the upstream material
3. Data selection biases (trigger efficiency, geometric acceptance) not modeled in MC

**Recommendation**: The material budget fix is necessary but not sufficient. The next
investigation should focus on the scattering cross-section model (sigma_pd_cm_190.txt)
and the data-MC selection matching, not further material budget additions.

## Files
- `geant4/configs/build_krakow_gap01.C` — geometry modification macro (env-configurable)
- `geant4/configs/krakow_gap01.config` — hibeam_g4 config for GAP-01 geometry
- `geant4/configs/run_gap01_100k.mac` — 100k-event validation macro
- `geant4/jobs/gap01_validation.sbatch` — Slurm job script
- `scripts/gap01_mv3_validate.py` — MV3 before/after validation + plot
