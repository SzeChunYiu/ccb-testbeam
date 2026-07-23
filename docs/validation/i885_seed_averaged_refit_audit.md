# Issue #885 seed-averaged calibration refit audit

## Question

Can the committed partial issue #885 simulation bundle support the published straight-line proton/deuteron calibration curves after correcting the seed-independence defect?

## Inputs

- `geant4/single_stave/results/i885_v1/i885_per_config.csv`
- 14 configuration files, 7,000 simulated events
- proton energies: 2, 5, 8, 12, 20 MeV, two seeds each
- deuteron energies: 2, 5 MeV, two seeds each
- exact input SHA-256: `1a712157f1cba06f9d3b3847217c381c31bdc581337612c92b02ccc82a1691d4`

## Method

`scripts/single_stave/refit_i885_campaign.py` v1.0.0 forms exactly one point per particle and energy. The point value is the mean of per-file means. Its displayed uncertainty is the quadrature sum of:

1. the propagated per-file standard errors, and
2. the standard error of the seed-to-seed means.

A weighted straight line is attempted only with at least three independent energies. The fit retains residual degrees of freedom, chi-square, reduced chi-square, goodness-of-fit p-value, RMSE, maximum absolute residual, range, coefficient covariance, file count, and independent-energy count. A line is placed in the accepted `fits` object only when the chi-square goodness-of-fit p-value is at least 0.01. This threshold was specified in code before examining the generated result in this run.

The p-value assumes independent Gaussian seed-averaged uncertainties and contains no model or systematic term. Rejection therefore establishes incompatibility with this stated linear/statistical model; it does not select a replacement response model.

`scripts/single_stave/render_i885_refit_svg.py` v1.0.0 is the canonical renderer for the committed SVG. It reads the regenerated fit JSON and seed-averaged-point CSV, refuses to render a bundle containing an accepted calibration fit, requires both rejected proton diagnostics and both deuteron coverage skips, and emits deterministic compact SVG. The renderer output was verified byte-for-byte against the committed `P5_seed_averaged_calibration.svg` (SHA-256 `725b592d9d217f43cf8624ca7682575a35cf5f4f1ec06d9ea7266a7a4f8a3332`).

## Results

| response | species | files | independent energies | residual dof | reduced chi-square | p-value | status |
|---|---|---:|---:|---:|---:|---:|---|
| SiPM pe vs KE | proton | 10 | 5 | 3 | 357.99 | 1.62 x 10^-232 | linear model rejected |
| Birks-visible vs KE | proton | 10 | 5 | 3 | 33391.66 | below double-precision range | linear model rejected |
| SiPM pe vs KE | deuteron | 4 | 2 | 0 | - | - | skipped: insufficient energies |
| Birks-visible vs KE | deuteron | 4 | 2 | 0 | - | - | skipped: insufficient energies |

No calibration fit is accepted. High R-squared alone would have hidden the proton model failure: the seed-averaged SiPM diagnostic still has R-squared = 0.9868 while its weighted goodness-of-fit p-value is approximately 10^-232.

## Reproduce

```bash
python -m py_compile \
  scripts/single_stave/refit_i885_campaign.py \
  scripts/single_stave/render_i885_refit_svg.py \
  tests/test_refit_i885_campaign.py \
  tests/test_render_i885_refit_svg.py

python -m pytest \
  tests/test_refit_i885_campaign.py \
  tests/test_render_i885_refit_svg.py -q

python scripts/single_stave/refit_i885_campaign.py \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --output-json geant4/single_stave/results/i885_v1/i885_fits.json \
  --output-svg /tmp/i885_refit_matplotlib_preview.svg \
  --output-points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv

python scripts/single_stave/render_i885_refit_svg.py \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv \
  --output geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg
```

Focused results:

- refit suite: `6 passed`;
- deterministic renderer suite: `3 passed`;
- renderer output matched the committed SVG byte-for-byte.

## Interpretation and next method comparison

A single global line is unsuitable for the current proton response under the recorded statistical errors. Plausible next comparisons include a physically motivated saturation/quenching response, monotonic spline used only for interpolation, or preregistered restricted-energy linear ranges. They must be compared using residual structure, held-out or newly generated energies, uncertainty coverage, robustness to seeds, and eventual data/MC closure. The current partial sample must not be used to choose and validate the same model.

The visual output is repository-recorded Geant4 simulation evidence, not detector data. No real-data calibration or detector-performance claim follows from this audit.
