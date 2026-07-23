# Issue #885 — single-stave proton/deuteron calibration campaign (v1)

Status: **PARTIAL (12/72 files: proton 2-20 MeV + deuteron 2 MeV)** — proton KE-scan + cross-species Birks comparison plotted; the full
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

## Physics validation (completed subset: proton 2-20 MeV + deuteron 2 MeV)

Seed-averaged per-config means (500 ev/seed, 2 seeds):

| species | KE (MeV) | raw edep (MeV) | Birks-visible (MeV) | quench vis/raw | track len (mm) | SiPM pe (readout) |
|---------|---------:|---------------:|--------------------:|---------------:|---------------:|------------------:|
| deuteron| 2        | 1.972          | 0.303               | 0.154          | 0.045          | 3.6               |
| proton  | 2        | 1.984          | 0.438               | 0.221          | 0.071          | 5.2               |
| proton  | 5        | 4.991          | 1.689               | 0.339          | 0.343          | 20.0              |
| proton  | 8        | 7.989          | 3.304               | 0.413          | 0.786          | 38.4              |
| proton  | 12       | 11.996         | 5.802               | 0.483          | 1.626          | 67.6              |
| proton  | 20       | 19.959         | 11.412              | 0.572          | 4.061          | 131.5             |

At 2 MeV the **deuteron is quenched more strongly than the proton** (0.154 vs
0.221, d/p = 0.70): its ~half-velocity, higher-dE/dx Bragg deposit suppresses
more scintillation, and its track is shorter (0.045 vs 0.071 mm). This is the
physical reason separate p/d calibration curves are required. Proton quench
weakens monotonically with energy (0.221 -> 0.572 over 2-20 MeV) as dE/dx falls.

Fits (this subset): proton SiPM calibration **7.12 pe/MeV, R^2 = 0.993** (10
files, 5 energies); Birks-visible vs KE **0.619 MeV/MeV, R^2 = 0.992**. Deuteron
calibration needs more energies (only 2 MeV landed so far).

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
