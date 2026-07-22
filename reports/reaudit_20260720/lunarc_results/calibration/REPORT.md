# Single-stave optical calibration — Edep → PE (#796, CCB-796-CALIB, DONE)

Full deposited-energy → detected-photoelectron calibration from the working
single-stave Geant4 sim on LUNARC (Geant4 11.2.2). This is the #796 optical
calibration deliverable: it required the optical readout to actually work
(#866) — before that, PE was 0.

## Run
- Executable: `geant4/single_stave` at merged main (optical readout + ntuple merge).
- Mode: `--mode optical`, 200 events/point, seeds 1–5.
- Grid: proton {60, 100, 140} MeV, deuteron {70, 110} MeV — spanning the empirical
  stave-entry spectra (`../entry_energies/`: proton ~7–159 MeV, deuteron ~50–128 MeV).
- Analysis: `scripts/single_stave/analyze_calibration_grid.py` (pooled + per-point).

## Result (`result.json`, `calibration_source.csv` = 1000 events, `G4CAL-01_edep_vs_pe.png`)

| species | KE [MeV] | E_dep [MeV] | detected PE | yield [PE/MeV] | resolution |
|---|--:|--:|--:|--:|--:|
| proton | 60 | 28.67 | 282.4 ± 25.2 | 9.85 | 0.089 |
| proton | 100 | 16.22 | 176.6 ± 16.5 | 10.89 | 0.093 |
| proton | 140 | 12.69 | 139.5 ± 29.0 | 10.99 | 0.208 |
| deuteron | 70 | 49.68 | 431.6 ± 62.4 | 8.69 | 0.145 |
| deuteron | 110 | 28.58 | 275.5 ± 47.5 | 9.64 | 0.172 |

- **Light yield ≈ 10 PE/MeV** (pooled 10.1; species/energy spread 8.7–11.0) — a
  realistic WLS-fibre single-stave yield.
- Physics is correct: **lower-energy protons deposit MORE** (higher dE/dx toward
  the Bragg peak: 60 MeV → 28.7 MeV vs 140 MeV → 12.7 MeV over the 2 cm), and
  **deuterons deposit more than protons at similar KE** (heavier, slower).
- Resolution 9–21% (PE-statistics dominated; the 140 MeV proton tail widens it).

## Status
CCB-796-RUN, CCB-796-ENTRY, CCB-796-OPTICAL, **CCB-796-CALIB — all DONE**. The
single-stave optical calibration chain (geometry → Edep → scintillation → WLS →
collection → PE → light yield/resolution) is validated end-to-end on real
Geant4. Figures G4CAL-01 (Edep→PE, committed) and G4CAL-02 (PE vs KE) on fs10;
regenerate with the analysis script over the grid outputs.

## Reproduce
```bash
ssh lunarc; module load GCC/12.3.0 Geant4/11.2.2
git clone --depth 1 --branch main https://github.com/SzeChunYiu/ccb-testbeam /tmp/ccb
cd /tmp/ccb/geant4/single_stave && bash slurm/build.sh build
for E in 60 100 140; do ./build/ccb_stave_sim --mode optical --particle proton --energy $E \
  --nevents 200 --optical-dir build/optical --output out/proton_$E.root; done
python scripts/single_stave/analyze_calibration_grid.py   # edit GRID/OUT paths
```
