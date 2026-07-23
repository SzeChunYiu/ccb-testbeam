# AUD-I885-002 — seed-averaged response refit and linear-model test

- **Session stamp:** 2026-07-23T14:23:31Z
- **Owner:** scheduled ChatGPT audit session
- **Initial remote main:** `27993fce7556e65decf8c760ac6f3a9d2928e0c7`
- **Implementation/evidence head before this archive:** `024f3f977111f2e8a836c36fdb1af746052d1601`
- **Status:** COMPLETE for the independence correction, partial-bundle regeneration, focused validation, model rejection, visual evidence, and direct-to-main delivery; PARTIAL / BLOCKED for an accepted detector calibration.

## Area reviewed

Issue #885 single-stave proton/deuteron partial Geant4 campaign:

- `scripts/single_stave/plot_i885_campaign.py`
- `tools/audit/validate_i885_campaign_results.py`
- `geant4/single_stave/slurm/points_i885_campaign.csv`
- `geant4/single_stave/results/i885_v1/{i885_per_config.csv,i885_fits.json,SUMMARY.md,AUDIT_INVALIDATION.md}`
- prior P5/P5b fit and coverage claims
- relevant tests, validation documents, recent main history, PR #868 metadata, and repository-local audit ledgers.

## Confirmed defects

1. The legacy plotter displayed seed-averaged points but fitted per-seed rows.
2. Legacy fit `n` counted files rather than independent energies.
3. The deuteron line used four seed files but only two distinct energies, leaving zero residual degrees of freedom after seed averaging.
4. R-squared alone was used without residual or goodness-of-fit diagnostics and concealed severe disagreement of the proton response with a single line relative to recorded statistical errors.

## Implementation

Added `scripts/single_stave/refit_i885_campaign.py` v1.0.0. It:

- validates required columns, finite values, positive event counts, nonnegative SEMs, and unique `(particle, energy_MeV, hit_x_cm, seed)` configurations;
- forms one point per particle and energy;
- combines propagated per-file SEM and between-seed SEM in quadrature;
- refuses a line below three independent energies;
- performs weighted least squares when all combined uncertainties are finite and positive;
- records coefficient covariance, slope/intercept uncertainty, range, residual dof, chi-square, reduced chi-square, p-value, R-squared, RMSE, maximum residual, file count, independent-energy count, assumptions, and fit basis;
- accepts a line only for goodness-of-fit `p >= 0.01`;
- separates `fits`, `fit_rejections`, and `fit_skips`;
- writes input path, byte size, and SHA-256;
- emits a deterministic, explicitly simulation-only SVG and a seed-averaged-point CSV.

Added `tests/test_refit_i885_campaign.py` with six cases covering independent-energy counts, two-energy skipping, energy-mean rather than seed-row weighting, nonlinear rejection, duplicate-key rejection, and traceable CLI outputs.

## Exact input and sample

- `geant4/single_stave/results/i885_v1/i885_per_config.csv`
- SHA-256: `1a712157f1cba06f9d3b3847217c381c31bdc581337612c92b02ccc82a1691d4`
- bytes: 3,698
- 14 files / 7,000 simulated events
- proton: five energies, two seeds each
- deuteron: two energies, two seeds each
- no attenuation/timing files in the committed bundle.

No random seed was introduced by the postprocessor.

## Measured results

No line is accepted.

| response | species | files | energies | residual dof | reduced chi-square | p-value | state |
|---|---|---:|---:|---:|---:|---:|---|
| SiPM pe vs KE | proton | 10 | 5 | 3 | 357.9873 | `1.6218e-232` | LINEAR_MODEL_REJECTED |
| Birks-visible vs KE | proton | 10 | 5 | 3 | 33391.6587 | below double-precision range | LINEAR_MODEL_REJECTED |
| SiPM pe vs KE | deuteron | 4 | 2 | 0 | — | — | SKIPPED_INSUFFICIENT_ENERGY_POINTS |
| Birks-visible vs KE | deuteron | 4 | 2 | 0 | — | — | SKIPPED_INSUFFICIENT_ENERGY_POINTS |

The proton SiPM R-squared is still 0.9868 and the Birks-visible R-squared is 0.9422. This demonstrates why R-squared is not an acceptance criterion for a response model.

The rejection is conditional on independent Gaussian seed-averaged uncertainties and no systematic/model term. It does not identify a replacement model.

## Commands and validation

```bash
python -m py_compile \
  scripts/single_stave/refit_i885_campaign.py \
  tests/test_refit_i885_campaign.py

python -m pytest tests/test_refit_i885_campaign.py -q
# 6 passed

python scripts/single_stave/refit_i885_campaign.py \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --output-json geant4/single_stave/results/i885_v1/i885_fits.json \
  --output-svg geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg \
  --output-points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv
# status=PARTIAL accepted=0 rejected=2 skipped=2
```

Additional checks:

- Python changed-file line length no greater than 100 characters;
- result JSON parsed;
- SVG parsed and visually inspected;
- repeated SVG generation was deterministic in the validation environment;
- reconstructed input and relevant source blobs were compared with GitHub blob identities.

The full repository suite, ruff, Geant4, ROOT processing, CTest, and GitHub Actions were not run. No broader CI success is claimed.

## Artifacts and documentation

- `geant4/single_stave/results/i885_v1/i885_fits.json`
- `geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv`
- `geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg`
- `geant4/single_stave/results/i885_v1/SUMMARY.md`
- `geant4/single_stave/results/i885_v1/AUDIT_INVALIDATION.md`
- `docs/validation/i885_seed_averaged_refit_audit.md`
- `docs/validation/i885_seed_averaged_refit_validation.json`

Relevant backlog, master-index, code-result, study, claim, visualization, blocker, active-task, and handoff records were updated.

## Direct-to-main commit sequence before archive

1. `5e88f2e0ef668e3decd0b5f3befed8a455dbfd0a` — `feat(i885): seed-average and validate calibration refits`
2. `6a0e81de1f48b6c3cb31228a65efbd4a6a91839a` — `test(i885): cover seed-averaged calibration refits`
3. `bacb74854150686c707baf339b60952c3c293691` — `data(i885): replace legacy fits with seed-averaged diagnostics`
4. `9eceb957d181584501bf5038512b7f5559d29282` — `data(i885): record seed-averaged calibration points`
5. `b5ab119cc1b4ec8346c5bbc8abb64aa6293c3ce9` — `docs(validation): record seed-averaged issue 885 refit audit`
6. `612adfcfcc0f028421e17753679372a806d5593e` — `docs(validation): add issue 885 refit validation record`
7. `3390495253c3f529efa7a0ff5c0718a5e16ea948` — `docs(i885): report rejected seed-averaged linear models`
8. `163dfb0c0c64b279cc6ee5c75d025645d254835d` — `fix(i885): stabilize compact SVG output`
9. `68891d39418950368af9421da558b36de415587b` — `docs(i885): visualize seed-averaged calibration rejection`
10. `84e901c0f0e649b2a635b4ff567b2ce4464c9690` — `docs(i885): supersede invalid per-seed calibration fits`
11. `24e5a831db33bfe21e511052fa187e39e8b16b58` — `docs(audit): claim issue 885 seed-averaged refit task`
12. `31290cb1bb4dbd4e2ab6d64531d57faed85f6562` — `docs(audit): track issue 885 model-validation backlog`
13. `0d26d13bcee8a9453017534076a6d6647258b445` — `docs(audit): index issue 885 seed-averaged refit`
14. `943efa17da1e4488cb8a80d0d974a8d353c35f2f` — `docs(audit): map issue 885 seed-averaged diagnostics`
15. `c4077f74c6e70ec6e53e18ea18116159fe6bb536` — `docs(audit): classify issue 885 linear-model rejection`
16. `9993651fadeda62f741c3cb91c05ee656d78de95` — `docs(audit): register issue 885 model-rejection visual`
17. `47c4a5254962f543bf3af560f11fbd6269594a81` — `docs(audit): record issue 885 model rejection study`
18. `024f3f977111f2e8a836c36fdb1af746052d1601` — `docs(audit): refine issue 885 calibration blocker`

All were written directly to `main` without force-push or history rewrite.

## Blockers and next action

`BLK-I885-001` remains open for scientific calibration acceptance. Complete the campaign or freeze an independent validation subset; preregister physically plausible nonlinear/saturation/quenching models and restricted ranges; compare them on held-out or newly generated energies; quantify statistical and systematic coverage and seed/run stability; then perform real-data closure before accepting calibration constants.

PR #868 remains closed, unmerged, and non-mergeable. It was not modified.

`SESSION_LOG.md` was not replaced because the connector exposes complete-file replacement but not a safe append primitive, and the long file was returned in truncated chunks. Replacing it from incomplete bytes would violate append-only provenance. This immutable archive is the complete session record; `HANDOFF.md` records the remote-final SHA and delivery confirmation.
