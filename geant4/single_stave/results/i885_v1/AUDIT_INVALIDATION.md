# Audit status for issue #885 partial campaign results

Status: **PARTIAL simulation output; no calibration function is accepted.**

The original P5/P5b fits were invalid because repeated seed files were treated as independent energy points and deuteron lines were fit through only two independent energies. Those legacy fit records have been superseded by `scripts/single_stave/refit_i885_campaign.py` and are no longer present in `i885_fits.json`.

Current measured state:

- 14/72 total campaign files;
- 14/40 main-grid files;
- proton coverage: 2, 5, 8, 12, 20 MeV, two seeds each;
- deuteron coverage: 2, 5 MeV, two seeds each;
- no committed attenuation/timing files;
- every fit input is seed-averaged to one point per energy;
- deuteron fits are skipped because two energies leave zero residual degrees of freedom;
- proton linear diagnostics are rejected by weighted goodness-of-fit tests.

For the proton SiPM response, the seed-averaged five-point line has reduced χ² = 357.99 for 3 residual degrees of freedom and p = 1.62 × 10⁻²³². For the proton Birks-visible response, reduced χ² = 33391.66 and the p-value underflows double precision. These results are evidence against a single straight-line response under the recorded uncertainty model, not accepted calibration constants.

`i885_fits.json` therefore contains an empty `fits` object, rejected proton diagnostics under `fit_rejections`, and deuteron coverage failures under `fit_skips`. `P5_seed_averaged_calibration.svg` displays the same state with explicit simulation-only labelling.

The per-file means and direct 2 MeV proton/deuteron quench comparison remain repository-recorded simulation outputs subject to detector-model, physics-list, optical-transport, and incomplete-coverage limitations. They are not real-data calibration results.
