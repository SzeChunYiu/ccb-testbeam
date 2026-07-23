# Latest Handoff

## Session

- **UTC:** 2026-07-23T14:23:31Z
- **Task:** `AUD-I885-002`
- **Initial remote main:** `27993fce7556e65decf8c760ac6f3a9d2928e0c7`
- **Final pre-handoff main:** `e6dd97da2d50cc81e9f49f8dab7cb2c8395fa6eb`
- **Validated numerical/result head:** `84e901c0f0e649b2a635b4ff567b2ce4464c9690`
- **Validated canonical-visual head:** `5c025154300ec7779d7d03cc944e922ebfdd9dff`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** COMPLETE for seed-independence correction, partial-bundle regeneration, global-linear-model testing, focused tests, byte-reproducible visual evidence, coordination records, and direct-to-main delivery; PARTIAL / BLOCKED for a scientifically accepted detector calibration.

## Start-of-run and concurrent-work review

- System Git clone/fetch failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and direct writes were used.
- Fetched current `main`, recent history, PR #868, the issue #885 campaign manifest, plotter, validator, tests, partial result bundle, summary/invalidation, and mandatory `chatgpt_todo/` records.
- Work started from remote main `27993fce7556e65decf8c760ac6f3a9d2928e0c7`; recent history was rechecked repeatedly and no overlapping concurrent change was observed during the direct-write sequence.
- No task branch, pull request, force-push, history rewrite, raw-source-data change, or unrelated deletion was used.
- PR #868 remains closed, not merged, and non-mergeable; it was not modified.

## Scientific reconstruction

The issue #885 manifest specifies 72 simulation files:

- 40 main-grid files: two particles × ten energies × two seeds;
- 32 attenuation/timing files: two particles × two energies × four positions × two seeds.

The committed partial bundle contains 14 files / 7,000 simulated events:

- proton: 2, 5, 8, 12, 20 MeV, two seeds each — ten files / five independent energies;
- deuteron: 2, 5 MeV, two seeds each — four files / two independent energies;
- attenuation/timing: no committed files.

Exact analysis input:

- `geant4/single_stave/results/i885_v1/i885_per_config.csv`
- 3,698 bytes
- SHA-256 `1a712157f1cba06f9d3b3847217c381c31bdc581337612c92b02ccc82a1691d4`.

## Confirmed defects

1. The former P5/P5b plotter displayed seed-averaged points but fitted unaveraged per-seed rows.
2. Legacy fit `n` counted files rather than independent energy settings.
3. The deuteron line used four files but only two energies; after seed averaging a two-parameter line has zero residual degrees of freedom.
4. Fit records lacked residual degrees of freedom, chi-square, p-value, coefficient uncertainty, range, and explicit statistical assumptions.
5. High R-squared values masked severe failure of the global proton straight-line model relative to the recorded statistical uncertainties.
6. The initially committed compact SVG was visually reviewed but lacked an explicit committed canonical renderer, so its exact bytes were not reproducible from the documented refit command alone.

## Validated implementation

Added `scripts/single_stave/refit_i885_campaign.py` v1.0.0. It:

- validates required columns, finite values, positive event counts, nonnegative SEMs, and unique `(particle, energy_MeV, hit_x_cm, seed)` rows;
- forms exactly one point per particle and energy;
- combines propagated within-file SEM and between-seed SEM in quadrature;
- refuses a line below three independent energies;
- performs weighted least squares when uncertainties are finite and positive;
- records coefficient covariance and uncertainty, fit range, residual dof, chi-square, reduced chi-square, p-value, R-squared, RMSE, maximum residual, file count, energy count, fit basis, and assumptions;
- accepts a line only when the preregistered goodness-of-fit p-value is at least 0.01;
- separates accepted `fits`, `fit_rejections`, and insufficient-coverage `fit_skips`;
- records exact input path, size, and SHA-256.

Added `scripts/single_stave/render_i885_refit_svg.py` v1.0.0 as the canonical visual renderer. It consumes the regenerated fit JSON and point CSV, fails closed if an accepted calibration is present or required rejection/skip/point records are invalid, and generates the committed compact SVG deterministically.

Focused tests:

- `tests/test_refit_i885_campaign.py` — six cases;
- `tests/test_render_i885_refit_svg.py` — three cases.

Regenerated/corrected:

- `geant4/single_stave/results/i885_v1/i885_fits.json`
- `geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv`
- `geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg`
- `geant4/single_stave/results/i885_v1/SUMMARY.md`
- `geant4/single_stave/results/i885_v1/AUDIT_INVALIDATION.md`
- `docs/validation/i885_seed_averaged_refit_audit.md`
- `docs/validation/i885_seed_averaged_refit_validation.json`
- `docs/validation/i885_seed_averaged_visual_validation.json`.

## Quantitative result

| response | species | files | energies | residual dof | reduced chi-square | p-value | status |
|---|---|---:|---:|---:|---:|---:|---|
| SiPM pe vs kinetic energy | proton | 10 | 5 | 3 | 357.9873 | `1.6218e-232` | LINEAR_MODEL_REJECTED |
| Birks-visible vs kinetic energy | proton | 10 | 5 | 3 | 33391.6587 | below double-precision range | LINEAR_MODEL_REJECTED |
| SiPM pe vs kinetic energy | deuteron | 4 | 2 | 0 | — | — | SKIPPED_INSUFFICIENT_ENERGY_POINTS |
| Birks-visible vs kinetic energy | deuteron | 4 | 2 | 0 | — | — | SKIPPED_INSUFFICIENT_ENERGY_POINTS |

`i885_fits.json` has an empty accepted `fits` object. The proton SiPM R-squared remains 0.9868 and the Birks-visible R-squared 0.9422, demonstrating that R-squared alone cannot authorize calibration.

The rejection is conditional on independent Gaussian combined uncertainties and no systematic/model term. It rejects the stated global linear/statistical model; it does not identify a replacement model.

## Reproducible validation

```text
python -m py_compile \
  scripts/single_stave/refit_i885_campaign.py \
  scripts/single_stave/render_i885_refit_svg.py \
  tests/test_refit_i885_campaign.py \
  tests/test_render_i885_refit_svg.py

python -m pytest \
  tests/test_refit_i885_campaign.py \
  tests/test_render_i885_refit_svg.py -q

9 passed in 1.04s

python scripts/single_stave/refit_i885_campaign.py \
  --observed geant4/single_stave/results/i885_v1/i885_per_config.csv \
  --output-json geant4/single_stave/results/i885_v1/i885_fits.json \
  --output-svg /tmp/i885_refit_matplotlib_preview.svg \
  --output-points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv

i885 refit: status=PARTIAL accepted=0 rejected=2 skipped=2

python scripts/single_stave/render_i885_refit_svg.py \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv \
  --output /tmp/i885_canonical.svg

cmp /tmp/i885_canonical.svg \
  geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg
```

Validation results:

- byte-for-byte canonical SVG equality: PASS;
- repeated renderer output: deterministic;
- SVG SHA-256: `725b592d9d217f43cf8624ca7682575a35cf5f4f1ec06d9ea7266a7a4f8a3332`;
- SVG size: 7,259 bytes;
- JSON and XML parse: PASS;
- visual inspection: axes, units, point/error meaning, fit rejection, deuteron skip, provenance, and `not detector data` are explicit;
- marker shape and line style supplement visual distinctions;
- all four focused Python files have maximum line length no greater than 100 characters;
- renderer local Git blob `a01999fc040880f1596b8d7bf71ce0d880ec4924` and test blob `60710780598e4c13ed39f3971d9925087c0a1b03` match GitHub.

Not run: full repository pytest, ruff, Geant4/CTest, ROOT/raw simulation regeneration, or GitHub Actions. No broader CI or detector-performance result is claimed.

## Direct-to-main commits

Numerical implementation, tests, results, and initial evidence:

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

Initial coordination and archive:

- `24e5a831db33bfe21e511052fa187e39e8b16b58` — `docs(audit): claim issue 885 seed-averaged refit task`
- `31290cb1bb4dbd4e2ab6d64531d57faed85f6562` — `docs(audit): track issue 885 model-validation backlog`
- `0d26d13bcee8a9453017534076a6d6647258b445` — `docs(audit): index issue 885 seed-averaged refit`
- `943efa17da1e4488cb8a80d0d974a8d353c35f2f` — `docs(audit): map issue 885 seed-averaged diagnostics`
- `c4077f74c6e70ec6e53e18ea18116159fe6bb536` — `docs(audit): classify issue 885 linear-model rejection`
- `9993651fadeda62f741c3cb91c05ee656d78de95` — `docs(audit): register issue 885 model-rejection visual`
- `47c4a5254962f543bf3af560f11fbd6269594a81` — `docs(audit): record issue 885 model rejection study`
- `024f3f977111f2e8a836c36fdb1af746052d1601` — `docs(audit): refine issue 885 calibration blocker`
- `b2d092c14d975babfee2f34bdf33f6c69576dde8` — `docs(audit): archive issue 885 seed-averaged refit`
- `50ee0c149331e5d23fdef4d7176b5c7de278e044` — `docs(audit): hand off issue 885 seed-averaged refit`.

Canonical visual reproducibility correction:

- `2a48931e93784658226c0f3f3d6adc61802cbe1e` — `feat(i885): render deterministic seed-averaged audit SVG`
- `4401c4d227fa2da63965fcb5a8d8e5b24568e63d` — `test(i885): cover deterministic audit SVG renderer`
- `45c1a6faf5a76bf144d97371f7b68cbee09bd42e` — `docs(validation): make issue 885 visual byte-reproducible`
- `c4810d0e0ae15d46429def445b47959520f5215b` — `docs(validation): record issue 885 visual reproducibility`
- `ca42994c23cc5c6c4790a5fa3430bc615ea5babf` — `docs(i885): document canonical deterministic visual renderer`
- `a8d5eeb7faffaa8ea9625606900bce9a57014195` — `docs(audit): bind issue 885 visual to canonical renderer`
- `5c025154300ec7779d7d03cc944e922ebfdd9dff` — `docs(audit): archive issue 885 visual reproducibility`
- `e6dd97da2d50cc81e9f49f8dab7cb2c8395fa6eb` — `docs(audit): finalize issue 885 refit validation state`.

Every GitHub contents write returned a successful commit SHA on `main`; remote history was checked throughout. No force-push or history rewrite occurred. This handoff update is the final direct-main write for the session and its commit is verified after creation.

## Repository-local records

Updated:

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `MASTER_INDEX.md`
- `CODE_RESULT_MAP.md`
- `STUDY_REVIEW_LEDGER.md`
- `CLAIM_EVIDENCE_MATRIX.md`
- `VISUALIZATION_MATRIX.md`
- `BLOCKERS.md`
- `HANDOFF.md`.

Immutable provenance:

- `archive/2026-07-23T142331Z_AUD-I885-002_SEED_AVERAGED_REFIT.md`
- `archive/2026-07-23T150122Z_AUD-I885-002_VISUAL_REPRODUCIBILITY.md`.

`SESSION_LOG.md` was not overwritten because the connector provides complete-file replacement but no append primitive and the long append-only file was returned in separately truncated responses. Reconstructing it through a replacement write would risk altering prior provenance. The two immutable archive entries contain the complete session and supplemental validation records.

## Acceptance and next action

- Seed-independence correction: COMPLETE.
- Focused numerical and visual regression: COMPLETE (`9 passed`).
- Partial-bundle JSON/CSV/SVG regeneration: COMPLETE.
- Canonical visual byte reproducibility: COMPLETE.
- Global proton straight-line response: REJECTED under the stated uncertainty model.
- Deuteron line: BLOCKED by only two independent energies.
- Accepted detector calibration: BLOCKED under `BLK-I885-001` / `AUD-I885-003`.

Next: complete the campaign or freeze an independent validation subset, preregister physically plausible saturation/quenching/nonlinear models and restricted energy ranges, compare them on held-out or newly generated energies, quantify seed/run/systematic uncertainty and coverage, and perform real-data closure before accepting calibration constants.
