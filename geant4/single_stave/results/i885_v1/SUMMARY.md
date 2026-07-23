# Issue #885 -- single-stave proton/deuteron campaign (v1, partial)

Status: **PARTIAL (14/72 total files; 7/20 independent main-grid energy points).**

Main-grid coverage: **PARTIAL (14/40 main-grid files)**.

Coverage by species:

- proton: 2, 5, 8, 12, 20 MeV, two seeds each;
- deuteron: 2, 5 MeV, two seeds each;
- attenuation/timing: no committed files.

> **Audit warning:** the P5/P5b calibration fits and the fit values in `i885_fits.json` are not accepted calibration results. They fit per-seed rows while displaying seed-averaged points, report seed-file counts as `n`, and include deuteron fits with only two independent energies. See `AUDIT_INVALIDATION.md` and `docs/validation/i885_campaign_acceptance_audit.md`.

## Campaign (`slurm/points_i885_campaign.csv`, 72 files)

- particles: proton, deuteron;
- main grid: 2, 5, 8, 12, 20, 30, 50, 80, 120, 150 MeV at `hit_x_cm = 0`;
- attenuation/timing: 30 and 80 MeV at 5, 10, 30, and 45 cm from the +x readout;
- two seeds (101, 102) × 500 events/file;
- readout SiPM at +x (`kStaveHalfX = 25 cm`).

## Seed-averaged partial simulation summaries

| species | KE (MeV) | raw edep (MeV) | Birks-visible (MeV) | quench vis/raw | track len (mm) | SiPM pe |
|---|---:|---:|---:|---:|---:|---:|
| deuteron | 2 | 1.972 | 0.303 | 0.154 | 0.045 | 3.6 |
| deuteron | 5 | 4.986 | 1.207 | 0.242 | 0.208 | 14.0 |
| proton | 2 | 1.984 | 0.438 | 0.221 | 0.071 | 5.2 |
| proton | 5 | 4.991 | 1.689 | 0.338 | 0.343 | 20.0 |
| proton | 8 | 7.989 | 3.304 | 0.414 | 0.787 | 38.4 |
| proton | 12 | 11.996 | 5.802 | 0.484 | 1.626 | 67.6 |
| proton | 20 | 19.959 | 11.412 | 0.572 | 4.061 | 131.5 |

At the shared 2 MeV point, the repository-recorded simulation gives a lower visible/raw ratio for the deuteron than for the proton (0.154 versus 0.221). This is a partial simulation comparison, not a real-data calibration or a completed campaign conclusion.

## Calibration-fit status

The following legacy values are retained in `i885_fits.json` for provenance but are **FLAWED / quarantined**:

- proton SiPM fit: 10 seed files but 5 independent energies;
- deuteron SiPM fit: 4 seed files but 2 independent energies;
- proton Birks-visible fit: 10 seed files but 5 independent energies;
- deuteron Birks-visible fit: 4 seed files but 2 independent energies.

A corrected generator must seed-average before fitting, record `n_files` and `n_energy_points`, set `fit_basis = "seed_averaged_unique_energy"`, and refuse a linear fit below three independent energies.

## Plots

P1–P4 and P8 are partial simulation diagnostics. P5/P5b fit overlays are quarantined. P6/P7 have no committed attenuation/timing coverage in this bundle.

## Regenerate and validate

```bash
# GCC/12.3.0 + Geant4/11.2.2 + SciPy-bundle, from geant4/single_stave/
python3 ../../scripts/single_stave/plot_i885_campaign.py \
  --indir <ccb-runs/i885_v1> \
  --outdir results/i885_v1 \
  --expected 72 \
  --summary

cd ../..
python tools/audit/validate_i885_campaign_results.py \
  --manifest geant4/single_stave/slurm/points_i885_campaign.csv \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --summary geant4/single_stave/results/i885_v1/SUMMARY.md \
  --output docs/validation/i885_campaign_acceptance_validation.json
```

Do not publish regenerated calibration-fit claims until the validator exits successfully with zero issues.
