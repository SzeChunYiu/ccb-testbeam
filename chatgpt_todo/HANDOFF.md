# Latest Handoff

## Session

- **UTC:** 2026-07-23T14:23:31Z
- **Task:** `AUD-I885-002`
- **Initial remote main:** `27993fce7556e65decf8c760ac6f3a9d2928e0c7`
- **Validated implementation/evidence head:** `84e901c0f0e649b2a635b4ff567b2ce4464c9690`
- **Coordination/archive head before this handoff:** `b2d092c14d975babfee2f34bdf33f6c69576dde8`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** COMPLETE for seed-independence correction, partial-bundle regeneration, focused tests, model rejection, visual evidence, and direct-to-main delivery; PARTIAL / BLOCKED for an accepted proton/deuteron detector calibration.

## Start-of-run review

- Direct clone/fetch through system Git failed because the runtime could not resolve `github.com`; authenticated GitHub connector reads and direct writes were used.
- Fetched latest `main`, recent history, PR #868, the issue #885 manifest, partial result CSV, legacy fit JSON, plotter, existing validator/tests, summary/invalidation, and mandatory `chatgpt_todo/` records.
- Work was based on remote main `27993fce7556e65decf8c760ac6f3a9d2928e0c7`. Main was rechecked during the write sequence; no overlapping concurrent change was observed.
- No branch, pull request, force-push, history rewrite, source-data modification, or unrelated-file deletion was used.
- PR #868 is still closed, unmerged, and non-mergeable; it was not modified.

## Scientific reconstruction

The manifest specifies 72 simulation files:

- 40 main-grid files: two particles × ten energies × two seeds;
- 32 attenuation/timing files: two particles × two energies × four positions × two seeds.

The committed partial bundle contains 14 files / 7,000 simulated events:

- proton: 2, 5, 8, 12, 20 MeV, two seeds each — 10 files / five independent energies;
- deuteron: 2, 5 MeV, two seeds each — four files / two independent energies;
- no committed attenuation/timing configurations.

Exact analysis input:

- path: `geant4/single_stave/results/i885_v1/i885_per_config.csv`
- bytes: 3,698
- SHA-256: `1a712157f1cba06f9d3b3847217c381c31bdc581337612c92b02ccc82a1691d4`.

## Confirmed defects

1. The former P5/P5b plotter displayed seed-averaged points but performed regressions on unaveraged seed rows.
2. Legacy fit `n` counted files rather than independent energies.
3. The deuteron line used four files but only two energies; after seed averaging a two-parameter line has zero residual degrees of freedom.
4. Fit records did not retain residual degrees of freedom, chi-square, p-value, coefficient uncertainty, range, or an explicit statistical model.
5. High R-squared values masked severe failure of the global proton straight-line model relative to the recorded statistical errors.

## Validated implementation

Added `scripts/single_stave/refit_i885_campaign.py` v1.0.0. It:

- strictly validates columns, finite values, positive event counts, nonnegative SEMs, and unique `(particle, energy_MeV, hit_x_cm, seed)` rows;
- forms exactly one point per particle and energy;
- combines propagated within-file SEM and between-seed SEM in quadrature;
- refuses a line below three independent energies;
- performs weighted least squares when combined uncertainties are finite and positive;
- records slope/intercept covariance and uncertainties, range, residual dof, chi-square, reduced chi-square, p-value, R-squared, RMSE, maximum residual, file count, energy count, fit basis, and assumptions;
- accepts a line only when the preregistered goodness-of-fit p-value is at least 0.01;
- separates accepted `fits`, `fit_rejections`, and insufficient-coverage `fit_skips`;
- records exact input path, byte size, and SHA-256;
- emits a deterministic, explicitly simulation-only SVG plus the seed-averaged-point CSV.

Added `tests/test_refit_i885_campaign.py` with focused coverage for:

- independent-energy versus file counts;
- deuteron skip at two energies;
- fitting energy means rather than weighting energies by seed-row count;
- nonlinear-model rejection;
- duplicate configuration rejection;
- traceable CLI JSON/SVG/CSV outputs.

Regenerated/corrected:

- `geant4/single_stave/results/i885_v1/i885_fits.json`
- `geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv`
- `geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg`
- `geant4/single_stave/results/i885_v1/SUMMARY.md`
- `geant4/single_stave/results/i885_v1/AUDIT_INVALIDATION.md`
- `docs/validation/i885_seed_averaged_refit_audit.md`
- `docs/validation/i885_seed_averaged_refit_validation.json`.

The accepted `fits` object is empty. Legacy coefficients no longer appear as accepted calibration records.

## Quantitative result

| response | species | files | independent energies | residual dof | reduced chi-square | goodness-of-fit p | status |
|---|---|---:|---:|---:|---:|---:|---|
| SiPM pe vs kinetic energy | proton | 10 | 5 | 3 | 357.9873 | `1.6218e-232` | LINEAR_MODEL_REJECTED |
| Birks-visible vs kinetic energy | proton | 10 | 5 | 3 | 33391.6587 | below double-precision range | LINEAR_MODEL_REJECTED |
| SiPM pe vs kinetic energy | deuteron | 4 | 2 | 0 | — | — | SKIPPED_INSUFFICIENT_ENERGY_POINTS |
| Birks-visible vs kinetic energy | deuteron | 4 | 2 | 0 | — | — | SKIPPED_INSUFFICIENT_ENERGY_POINTS |

The proton SiPM diagnostic still has R-squared 0.9868 and the Birks-visible diagnostic R-squared 0.9422. These values demonstrate that R-squared alone cannot authorize calibration.

The rejection is conditional on independent Gaussian combined uncertainties and no systematic/model term. It is evidence against the stated global linear model, not proof of a particular nonlinear replacement.

## Reproducible validation

```text
python -m py_compile \
  scripts/single_stave/refit_i885_campaign.py \
  tests/test_refit_i885_campaign.py

python -m pytest tests/test_refit_i885_campaign.py -q
6 passed

python scripts/single_stave/refit_i885_campaign.py \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --output-json geant4/single_stave/results/i885_v1/i885_fits.json \
  --output-svg geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg \
  --output-points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv

i885 refit: status=PARTIAL accepted=0 rejected=2 skipped=2
```

Additional checks completed:

- generated JSON parsed;
- SVG parsed and was visually inspected;
- the plot states axes, units, provenance, uncertainty meaning, model rejection, deuteron skip, and `not detector data`;
- marker shape and line style supplement visual distinctions;
- repeated SVG generation was deterministic in the validation environment;
- changed Python lines were no longer than 100 characters;
- reconstructed relevant Git blobs matched the GitHub content identities used for review.

Not run:

- full repository pytest;
- ruff;
- Geant4 compilation/CTest;
- ROOT or raw simulation regeneration;
- GitHub Actions.

No broader CI or detector-performance result is claimed.

## Direct-to-main commits

Implementation, tests, results, and evidence:

- `5e88f2e0ef668e3decd0b5f3befed8a455dbfd0a` — `feat(i885): seed-average and validate calibration refits`
- `6a0e81de1f48b6c3cb31228a65efbd4a6a91839a` — `test(i885): cover seed-averaged calibration refits`
- `bacb74854150686c707baf339b60952c3c293691` — `data(i885): replace legacy fits with seed-averaged diagnostics`
- `9eceb957d181584501bf5038512b7f5559d29282` — `data(i885): record seed-averaged calibration points`
- `b5ab119cc1b4ec8346c5bbc8abb64aa6293c3ce9` — `docs(validation): record seed-averaged issue 885 refit audit`
- `612adfcfcc0f028421e17753679372a806d5593e` — `docs(validation): add issue 885 refit validation record`
- `3390495253c3f529efa7a0ff5c0718a5e16ea948` — `docs(i885): report rejected seed-averaged linear models`
- `163dfb0c0c64b279cc6ee5c75d025645d254835d` — `fix(i885): stabilize compact SVG output`
- `68891d39418950368af9421da558b36de415587b` — `docs(i885): visualize seed-averaged calibration rejection`
- `84e901c0f0e649b2a635b4ff567b2ce4464c9690` — `docs(i885): supersede invalid per-seed calibration fits`.

Coordination and provenance:

- `24e5a831db33bfe21e511052fa187e39e8b16b58` — `docs(audit): claim issue 885 seed-averaged refit task`
- `31290cb1bb4dbd4e2ab6d64531d57faed85f6562` — `docs(audit): track issue 885 model-validation backlog`
- `0d26d13bcee8a9453017534076a6d6647258b445` — `docs(audit): index issue 885 seed-averaged refit`
- `943efa17da1e4488cb8a80d0d974a8d353c35f2f` — `docs(audit): map issue 885 seed-averaged diagnostics`
- `c4077f74c6e70ec6e53e18ea18116159fe6bb536` — `docs(audit): classify issue 885 linear-model rejection`
- `9993651fadeda62f741c3cb91c05ee656d78de95` — `docs(audit): register issue 885 model-rejection visual`
- `47c4a5254962f543bf3af560f11fbd6269594a81` — `docs(audit): record issue 885 model rejection study`
- `024f3f977111f2e8a836c36fdb1af746052d1601` — `docs(audit): refine issue 885 calibration blocker`
- `b2d092c14d975babfee2f34bdf33f6c69576dde8` — `docs(audit): archive issue 885 seed-averaged refit`.

All writes returned successful direct-main commit SHAs. Remote history was checked throughout the sequence. No force-push or history rewrite occurred.

## Updated repository-local records

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `MASTER_INDEX.md`
- `CODE_RESULT_MAP.md`
- `STUDY_REVIEW_LEDGER.md`
- `CLAIM_EVIDENCE_MATRIX.md`
- `VISUALIZATION_MATRIX.md`
- `BLOCKERS.md`
- `HANDOFF.md`
- immutable archive `archive/2026-07-23T142331Z_AUD-I885-002_SEED_AVERAGED_REFIT.md`.

`SESSION_LOG.md` was not replaced because the connector lacks a safe append operation and returned the long append-only file in truncated chunks. Reconstructing and replacing it from incomplete bytes could destroy prior provenance. The immutable archive above contains the complete session entry.

## Acceptance and next action

- Seed-independence correction and focused regression: COMPLETE (`6 passed`).
- Partial-bundle fit/point/visual regeneration: COMPLETE.
- Global proton linear model: REJECTED under the stated statistical model.
- Deuteron calibration fit: BLOCKED by only two independent energies.
- Direct-to-main delivery: COMPLETE through the coordination/archive head above; this handoff commit follows directly on `main`.
- Accepted calibration function and detector interpretation: BLOCKED under `BLK-I885-001` / `AUD-I885-003`.

Next: complete the campaign or freeze an independent validation subset, preregister physical nonlinear/saturation/quenching models and restricted energy ranges, compare them using held-out or newly generated energies, quantify seed/run/systematic uncertainty and coverage, and perform real-data closure before accepting calibration constants.
