# Immutable session record — AUD-I885-001

## Session identity

- UTC stamp: `2026-07-23T13:21:12Z`
- Owner: scheduled ChatGPT audit session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `2986da32c6b01d6f3f1b6ec90231ab5eeee436b1`
- Validated implementation/evidence head: `467c007cd3526a762258a7f1d3f00563a37db8a8`
- Coordination head before archive: `8a0e148bcbb9cb646c2d62f101ff47d7a995313f`
- Task: `AUD-I885-001`
- Status: COMPLETE for validator, focused tests, coverage correction, quarantine, evidence, and direct-to-main delivery; PARTIAL for corrected generator and accepted calibration.

## Start-of-run review

A direct clone was attempted but failed with `Could not resolve host: github.com`. Repository inspection and direct-to-main writes used the authenticated GitHub connector. Current main history, issue #885, merged PR #898, open PRs, commit status, campaign manifest, plotter, result CSV, fit JSON, summary, figures, and mandatory `chatgpt_todo/` files were inspected. No task branch, pull request, force-push, or history rewrite was used. No status checks were attached to the initial main commit.

## Scientific reconstruction

Issue #885 requests proton and deuteron simulation at ten kinetic energies, plus attenuation/timing scans at two energies and four entry distances. The committed manifest contains:

- 40 main-grid files: 2 particles × 10 energies × 2 seeds at `hit_x_cm = 0`;
- 32 attenuation/timing files: 2 particles × 2 energies × 4 positions × 2 seeds;
- 72 total files and 36,000 planned events at 500 events/file.

The committed partial CSV contains 14 files and 7,000 events, all on the main grid:

- proton: 2, 5, 8, 12, 20 MeV, two seeds each — 10 files / 5 independent energies;
- deuteron: 2, 5 MeV, two seeds each — 4 files / 2 independent energies;
- attenuation/timing: zero committed files.

## Confirmed defects

1. The original summary stated `14/72 main-grid files`; 72 is the total-campaign denominator, while the main grid contains 40 files.
2. The summary phrase `deuteron, proton @ 2-20 MeV` collapsed unequal coverage and falsely implied that both species cover the same range.
3. `plot_i885_campaign.py` displays seed-averaged fit points but calls `linfit` on the raw per-seed rows.
4. `i885_fits.json` reports `n=10` for five independent proton energies and `n=4` for two independent deuteron energies.
5. A line fitted to two seed-averaged deuteron energies has two parameters and zero residual degrees of freedom. Its near-unity R² cannot validate a calibration.
6. P6/P7 attenuation/timing claims have no committed configurations in the current result bundle.

The partial per-file simulation means were not invalidated. The calibration slopes, intercepts, R² values, P5/P5b overlays, and completed-coverage wording were quarantined.

## Work delivered

Added `tools/audit/validate_i885_campaign_results.py` v1.0.0. It strictly parses the manifest and observed CSV, verifies unique keys and observed-manifest membership, derives main-grid coverage and per-species energies, audits summary coverage, audits fit independence/provenance, records input paths/sizes/SHA-256, treats partial coverage as a warning, and fails on scientific acceptance defects.

Added `tests/test_validate_i885_campaign_results.py` with four focused tests covering current-style defects, a valid partial campaign, an out-of-manifest configuration, and CLI provenance/nonzero status.

Corrected `geant4/single_stave/results/i885_v1/SUMMARY.md` to report 14/72 total files, 14/40 main-grid files, 7/20 independent energy points, exact per-species coverage, zero attenuation/timing coverage, and the calibration quarantine.

Added:

- `geant4/single_stave/results/i885_v1/AUDIT_INVALIDATION.md`
- `docs/validation/i885_campaign_acceptance_audit.md`
- `docs/validation/i885_campaign_acceptance_validation.json`
- `docs/validation/i885_campaign_acceptance.svg`

The SVG is explicitly a synthetic repository-audit schematic, not detector data. It uses labels and shapes in addition to color.

## Validation commands and results

```text
python -m py_compile \
  tools/audit/validate_i885_campaign_results.py \
  tests/test_validate_i885_campaign_results.py

python -m pytest tests/test_validate_i885_campaign_results.py -q
4 passed in 0.60s
```

Exact reconstructed current-main inputs matched Git blob IDs:

- manifest: `15c4bb9ac99c1742e35225687ddcdf4341cae451`
- per-config CSV: `d38a42b0696d106d1f15068f8d81ed76f91b1040`
- fits JSON: `49bf41b359fbab42e4c583acacba7df2aac401c8`
- pre-correction summary: `3ea2a10f0751a3a7bcbc3db79c6a9d73bd956ca4`

Validator results:

```text
pre-correction bundle: status=FLAWED issues=20 warnings=1 exit=1
corrected-summary bundle: status=FLAWED issues=18 warnings=1 exit=1
```

The two removed issues were the wrong main-grid denominator and collapsed species coverage. The remaining issues are fit independence/provenance defects. Validation JSON parsed successfully, SVG parsed as XML, and changed Python lines were checked to remain within 100 characters.

No Geant4 executable, ROOT output, real data, simulation rerun, calibration, or detector-performance result was generated. Full repository pytest, ruff, CTest, and GitHub Actions were not run.

## Direct-to-main commits

- `189d785e068d9fec85796fdfb097bd2a3dc1fcea` — `feat(audit): validate issue 885 campaign acceptance`
- `583fa57c9277262dcc72de0f1fa749b1419a3a5d` — `test(audit): cover issue 885 campaign acceptance`
- `6945bbb4e314e3e57c8b181ba79468258c3ca7aa` — `docs(validation): record issue 885 campaign audit`
- `1a66794b9a3ac3163a5efa3f4aeee2f9d0ebf02c` — `docs(i885): correct partial coverage and quarantine fits`
- `a90a326c7f94ca210836aad0594fac59905db1f6` — `docs(i885): quarantine partial calibration fits`
- `52f9f38b8dd733fd17e7993b4a918473f48d9a0d` — `docs(validation): add issue 885 campaign record`
- `467c007cd3526a762258a7f1d3f00563a37db8a8` — `docs(validation): visualize issue 885 acceptance gate`
- `c40abd2a5d9e5b932950059d71247c796034a9cf` — `docs(audit): claim issue 885 campaign acceptance task`
- `c4bcd928b8c720086db9eb7ec73f664f4be300ce` — `docs(audit): track issue 885 calibration acceptance`
- `c65dd3b8d9f29a9efa1ae3205e57f721cb2bece7` — `docs(audit): index issue 885 campaign defects`
- `61adf3403838c24971fe382e4e1dcf876f983c58` — `docs(audit): map issue 885 result dependencies`
- `9a7960c9c3cc728c2f729a2f93a3ada0dd11e096` — `docs(audit): record issue 885 study review`
- `84385fdbf983080f2706cec1c289300c9a5a9341` — `docs(audit): classify issue 885 calibration claims`
- `8088a19e37114f09bfd926b7fa7a5e90c9d741fb` — `docs(audit): register issue 885 visual evidence`
- `8a0e148bcbb9cb646c2d62f101ff47d7a995313f` — `docs(audit): block unvalidated issue 885 calibration`

Every write returned a successful commit SHA directly on `main`. Remote history confirmed the sequence. The append-only `SESSION_LOG.md` was not overwritten because the connector has no append primitive and partial replacement would risk destroying historical entries; this immutable archive is the complete session record.

## Remaining blocker and next action

`BLK-I885-001` remains open. Correct `plot_i885_campaign.py` so coverage is manifest-derived, fit inputs are seed-averaged independent energies, fit metadata records file and energy counts plus range/residual/uncertainty information, and fewer than three energies do not produce an accepted line. Regenerate P5/P5b and `i885_fits.json` from declared inputs, rerun the independent validator, and require zero issues before publishing calibration claims.
