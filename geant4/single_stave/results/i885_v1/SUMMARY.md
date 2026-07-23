# Issue #885 -- single-stave proton/deuteron campaign (v1, partial)

Status: **PARTIAL (14/72 total files; 7/20 independent main-grid energy points).**

Main-grid coverage: **PARTIAL (14/40 main-grid files)**.

Coverage by species:

- proton: 2, 5, 8, 12, 20 MeV, two seeds each;
- deuteron: 2, 5 MeV, two seeds each;
- attenuation/timing: no committed files.

> **Calibration status:** the legacy per-seed fits have been replaced by a seed-averaged refit. No linear calibration is accepted from the current partial bundle. Deuteron fits are skipped because only two independent energies exist. Proton linear models are retained only as rejected diagnostics because their weighted goodness-of-fit tests fail.

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

`i885_fits.json` now separates accepted fits, rejected model diagnostics, and insufficient-coverage skips:

- accepted calibration fits: **none**;
- deuteron SiPM and Birks-visible fits: skipped at 2 independent energies, below the preregistered minimum of 3;
- proton SiPM linear diagnostic: 5 independent energies, residual dof = 3, reduced chi-square = 357.99, goodness-of-fit p = 1.62 x 10^-232;
- proton Birks-visible linear diagnostic: 5 independent energies, residual dof = 3, reduced chi-square = 33391.66, p below double-precision range.

The proton values reject a straight-line response under the recorded statistical-uncertainty model. They are not calibration constants. A nonlinear or restricted-range model must be specified and validated after wider campaign coverage; model choice must not be selected solely to improve fit quality on this partial sample.

## Plots

P1-P4 and P8 are partial simulation diagnostics. `P5_seed_averaged_calibration.svg` shows seed-averaged independent-energy points and the rejected proton linear diagnostics. It is explicitly labelled as Geant4 simulation output, not detector data. The canonical SVG is generated deterministically from the fit JSON and point CSV by `render_i885_refit_svg.py`; its SHA-256 is `725b592d9d217f43cf8624ca7682575a35cf5f4f1ec06d9ea7266a7a4f8a3332`. P6/P7 have no committed attenuation/timing coverage in this bundle.

## Regenerate and validate

```bash
python scripts/single_stave/refit_i885_campaign.py \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --output-json geant4/single_stave/results/i885_v1/i885_fits.json \
  --output-svg /tmp/i885_refit_matplotlib_preview.svg \
  --output-points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv

python scripts/single_stave/render_i885_refit_svg.py \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv \
  --output geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg

python -m pytest \
  tests/test_refit_i885_campaign.py \
  tests/test_render_i885_refit_svg.py -q

python tools/audit/validate_i885_campaign_results.py \
  --manifest geant4/single_stave/slurm/points_i885_campaign.csv \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --summary geant4/single_stave/results/i885_v1/SUMMARY.md \
  --output docs/validation/i885_campaign_acceptance_validation.json
```

Do not publish a calibration function until campaign coverage, model specification, residual diagnostics, uncertainty treatment, and independent validation are complete.
