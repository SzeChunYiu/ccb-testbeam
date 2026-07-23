# Issue #885 campaign acceptance audit

Status: **FLAWED for published coverage and calibration-fit acceptance; PARTIAL but usable for the listed per-file simulation summaries.**

This audit evaluates the committed partial result bundle against the committed 72-file campaign manifest. It does not rerun Geant4 and does not alter the underlying per-file means.

## Inputs and provenance

Validated with:

```bash
python tools/audit/validate_i885_campaign_results.py \
  --manifest geant4/single_stave/slurm/points_i885_campaign.csv \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --summary geant4/single_stave/results/i885_v1/SUMMARY.md \
  --output docs/validation/i885_campaign_acceptance_validation.json
```

The validator records byte size and SHA-256 for every input. The reconstructed files used for this run matched the current Git blob IDs:

| input | Git blob |
|---|---|
| campaign manifest | `15c4bb9ac99c1742e35225687ddcdf4341cae451` |
| per-config CSV | `d38a42b0696d106d1f15068f8d81ed76f91b1040` |
| fits JSON | `49bf41b359fbab42e4c583acacba7df2aac401c8` |
| pre-correction summary | `3ea2a10f0751a3a7bcbc3db79c6a9d73bd956ca4` |

## Measured coverage

The manifest contains 72 files in total:

- 40 main-grid files: two particles × ten energies × two seeds at `hit_x_cm = 0`;
- 32 attenuation/timing files: two particles × two energies × four positions × two seeds.

The committed result CSV contains 14 files, all on the main grid:

- proton: 2, 5, 8, 12, and 20 MeV, two seeds each — 10 files / 5 independent energies;
- deuteron: 2 and 5 MeV, two seeds each — 4 files / 2 independent energies;
- attenuation/timing: no committed files.

Therefore the correct current labels are:

- total campaign: `14/72` files;
- main grid: `14/40` files;
- independent main-grid energy points: `7/20`;
- species coverage must be listed separately because the two species do not cover the same energies.

The former summary text `14/72 main-grid files` used the total campaign count as the main-grid denominator. Its collapsed phrase `deuteron, proton @ 2-20 MeV` also implied common coverage that is not present.

## Calibration-fit independence defect

The committed fit records count seed files as observations:

| fit family | species | reported `n` | seed files | independent energies |
|---|---:|---:|---:|---:|
| SiPM pe vs KE | proton | 10 | 10 | 5 |
| SiPM pe vs KE | deuteron | 4 | 4 | 2 |
| Birks-visible energy vs KE | proton | 10 | 10 | 5 |
| Birks-visible energy vs KE | deuteron | 4 | 4 | 2 |

The plotting code displays seed-averaged points but fits the unaveraged per-seed rows. Repeating the same kinetic-energy coordinate for two seeds does not create two independent calibration energies. The fit metadata must distinguish contributing files from independent energy points and must declare the fit basis.

For the deuteron subset, only two distinct kinetic energies are present. A straight line has two fitted parameters, so a two-energy fit has zero residual degrees of freedom after seed averaging. Its near-unity or unity R² cannot validate linear calibration. The current deuteron slopes may remain as descriptive two-point secants, but they must not be presented as validated calibration fits.

For the proton subset, five independent energies are present. A linear fit can be computed, but acceptance still requires seed-averaged input, explicit independent-point counts, residual diagnostics, and a stated validity range. The observed nonlinear Birks response means a high global R² alone is not evidence that one linear calibration is physically adequate over the full planned 2–150 MeV range.

## Acceptance criteria for regeneration

A corrected generator/result bundle must:

1. derive total and main-grid denominators from the campaign manifest;
2. report exact per-species energy lists and attenuation coverage;
3. seed-average before fitting;
4. record `fit_basis = "seed_averaged_unique_energy"`;
5. record both `n_files` and `n_energy_points`;
6. set legacy `n` equal to the independent energy-point count;
7. refuse a linear calibration fit with fewer than three independent energies;
8. report the fitted energy range, residuals, uncertainty method, and limitations;
9. rerun this validator and obtain `status = VALIDATED` with zero issues.

## Validation result

The exact pre-correction bundle returned:

```text
i885 campaign validation: status=FLAWED issues=20 warnings=1
exit status: 1
```

After correcting only the summary coverage wording, the bundle returned:

```text
i885 campaign validation: status=FLAWED issues=18 warnings=1
exit status: 1
```

The remaining 18 issues are fit-provenance/independence defects across four fit records. The incomplete campaign itself is a warning, not an error. Per-file simulation means remain repository-recorded partial simulation outputs; the published calibration-fit claims are quarantined pending regeneration.
