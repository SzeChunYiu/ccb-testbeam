# Issue #885 — single-stave proton/deuteron calibration campaign (v1)

Status: **PARTIAL** — proton main KE-scan plotted from completed files; the full
72-point array (job 3408050) is still draining on LUNARC. Plots in this directory
are regenerated from whatever has landed; re-run the plotter (below) once the
array finishes for the complete picture.

## Campaign design (`slurm/points_i885_campaign.csv`, 72 points)

| axis | values |
|------|--------|
| particles | proton, deuteron |
| KE (main scan, hit_x = 0) | 2, 5, 8, 12, 20, 30, 50, 80, 120, 150 MeV |
| attenuation/timing | 30, 80 MeV at entry 5/10/30/45 cm from +x readout end |
| seeds per point | 2 (101, 102) |
| events per point | 500 (optical transport) |

Geometry (DetectorConstruction.hh): stave x in [-25,+25] cm (kStaveHalfX=25 cm),
**readout SiPM at +x end** (kReadout = Sensor_F1_PlusX). "distance d from readout"
maps to hit_x = 25 - d, i.e. {5,10,30,45} cm -> hit_x {20,15,-5,-20}. The main
KE-scan points (hit_x=0) sit 25 cm from the readout and double as the x=0
attenuation reference.

No C++ changes were needed: origin/main already records Birks-visible
(`edep_scint_MeV` via G4EmSaturation), raw (`edep_scint_raw_MeV`), track length,
entry/exit, scint/WLS/Cerenkov photon counts and per-sensor arrival/detected/pe.

## Submission

- Job: `sbatch --array=0-71%12 slurm/submit_calibration.sh build/ points.csv out/`
  -> Slurm array **3408050**, capped at 12 concurrent tasks (4 CPUs each) to be
  polite on the shared hep pool.
- Output dir: `/projects/hep/fs10/shared/nnbar/billy/ccb-runs/i885_v1/`
  (one `stave_<part>_<E>MeV_x<hx>_s<seed>.root` + `.meta.json` per point).

## Physics validation (proton, completed subset)

| KE (MeV) | raw edep (MeV) | Birks-visible (MeV) | quench vis/raw | track len (mm) | SiPM pe (readout) |
|----------|---------------:|--------------------:|---------------:|---------------:|------------------:|
| 2        | 1.984          | 0.438               | 0.221          | 0.071          | 5.2               |
| 5        | 4.992          | 1.690               | 0.339          | 0.344          | 19.7              |
| 12       | 11.996         | 5.800               | 0.483          | 1.625          | 67.5              |

Birks suppression weakens with energy (higher-E -> lower dE/dx -> less quench),
exactly as expected. Proton SiPM calibration (pe_sat_readout vs KE): linear,
**6.26 pe/MeV, R² = 0.992** (8 files, low-E). Birks-visible vs KE: 0.540 MeV/MeV.

## Plots (this directory)

- `P1_KE_vs_Birks_visible_light.png` — KE vs Birks-quenched light produced
- `P2_KE_vs_scint_photons.png` — KE vs scintillation photons generated
- `P3_raw_edep_vs_Birks_light.png` — deposited energy vs Birks-visible light (linearity)
- `P4_KE_vs_SiPM_pe.png` — KE vs SiPM-collected photoelectrons (readout)
- `P5_calibration_pe_vs_KE.png` — SiPM pe vs KE calibration, linear fit per particle
- `P5b_calibration_Birks_vs_KE.png` — Birks-visible light vs KE calibration
- `P6_attenuation.png` — pe vs distance from readout (needs 30/80 MeV attenuation points)
- `P7_timing_vs_distance.png` — mean photon arrival time vs distance (needs photons tree)
- `P8_track_length_vs_KE.png` — scintillator track length vs KE (stopping proxy)
- `i885_per_config.csv` — per-config means + SEM; `i885_fits.json` — fit parameters

## Regenerate / scale

```bash
# from geant4/single_stave/, with GCC/12.3.0 + Geant4/11.2.2 + SciPy-bundle loaded
python3 ../../scripts/single_stave/plot_i885_campaign.py \
    --indir /projects/hep/fs10/shared/nnbar/billy/ccb-runs/i885_v1 \
    --outdir results/i885_v1 --expected 72
```

Rebuild the grid (e.g. more seeds / energies / events):
```bash
CCB_I885_NEVENTS=1000 CCB_I885_SEEDS=101,102,103 \
  python3 slurm/make_i885_campaign.py --out slurm/points_i885_campaign.csv
```

## Build note

`bash slurm/build.sh` reports a ctest "failure" for test 4
(`ccb_stave_birks_visible_regression`) because that test needs uproot in the
build-time python, which is not on LUNARC's default path. The `ccb_stave_sim`
binary itself builds and links cleanly; geometry + proton smoke tests pass.
