# Audit status for issue #885 partial campaign results

Status: **PARTIAL simulation output; coverage summary and calibration fits are not accepted.**

The committed per-config CSV contains 14 valid-looking main-grid files, but the current summary and fit metadata fail the independent campaign validator:

```bash
python tools/audit/validate_i885_campaign_results.py \
  --manifest geant4/single_stave/slurm/points_i885_campaign.csv \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --summary geant4/single_stave/results/i885_v1/SUMMARY.md \
  --output docs/validation/i885_campaign_acceptance_validation.json
```

Measured state:

- 14/72 total campaign files;
- 14/40 main-grid files;
- proton coverage: 2, 5, 8, 12, 20 MeV;
- deuteron coverage: 2, 5 MeV;
- no committed attenuation/timing files;
- proton fits use 10 seed files but only 5 independent energies;
- deuteron fits use 4 seed files but only 2 independent energies.

The deuteron R² values are not calibration-validation evidence because a seed-averaged line through two distinct energies has zero residual degrees of freedom. All P5/P5b fit lines, slopes, intercepts, R² values, and associated calibration wording are quarantined until the generator seed-averages the data, records independent-point counts, requires at least three energies, and regenerates the result bundle.

The per-file means and the direct 2 MeV proton/deuteron quench comparison remain repository-recorded simulation outputs, subject to the wider simulation and detector-model limitations. They are not real-data calibration results.
