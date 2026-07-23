# Latest Handoff

## Session

- **UTC:** 2026-07-23T13:21:12Z
- **Task:** `AUD-I885-001`
- **Initial remote main:** `2986da32c6b01d6f3f1b6ec90231ab5eeee436b1`
- **Validated implementation/evidence head:** `467c007cd3526a762258a7f1d3f00563a37db8a8`
- **Coordination/archive head before this handoff:** `036079211edcd6021e9fdf73c603ca57908776b7`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** COMPLETE for independent validation, coverage correction, quarantine, focused tests, and audit evidence; PARTIAL / BLOCKED for regenerated and scientifically accepted calibration curves.

## Start-of-run review

- Direct clone failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and writes were used.
- Inspected current main history, merged PR #898, issue #885, open PRs, commit status, campaign plotter, manifest, partial CSV, fit JSON, summary, generated-result descriptions, and all mandatory `chatgpt_todo/` ledgers.
- The session based its work on main commit `2986da32c6b01d6f3f1b6ec90231ab5eeee436b1`; no concurrent main change appeared during the direct-write sequence.
- No branch, PR, force-push, history rewrite, or unrelated-file replacement was used.
- PR #868 remains closed/unmerged and was not modified.
- No status checks were attached to the initial or delivered heads; no GitHub Actions success is claimed.

## Scientific reconstruction and confirmed defects

The issue #885 manifest defines 72 files:

- 40 main-grid files: two particles × ten energies × two seeds at `hit_x_cm = 0`;
- 32 attenuation/timing files: two particles × two energies × four positions × two seeds.

The committed partial result contains 14 files / 7,000 events, all on the main grid:

- proton: 2, 5, 8, 12, 20 MeV, two seeds each — 10 files / 5 independent energies;
- deuteron: 2, 5 MeV, two seeds each — 4 files / 2 independent energies;
- attenuation/timing: no committed configurations.

Confirmed defects:

1. `SUMMARY.md` reported `14/72 main-grid files`; 72 is the total campaign, while the main-grid denominator is 40.
2. `Covered: deuteron, proton @ 2-20 MeV` collapsed unequal species coverage.
3. `plot_i885_campaign.py` plots seed-averaged points but computes P5/P5b fits from the unaveraged per-seed rows.
4. `i885_fits.json` reports `n=10` for five independent proton energies and `n=4` for two independent deuteron energies.
5. A straight line through two deuteron energy points has zero residual degrees of freedom after seed averaging; its near-unity R² cannot validate a calibration.
6. P6/P7 have no committed attenuation/timing coverage in the current bundle.

The listed per-file simulation means remain partial repository-recorded simulation outputs. Calibration slopes, intercepts, R² values, P5/P5b overlays, and completed/shared-coverage wording are quarantined.

## Validated implementation

Added `tools/audit/validate_i885_campaign_results.py` v1.0.0. It:

- strictly parses the campaign manifest and observed result CSV;
- checks unique configuration keys and observed-manifest membership;
- derives total/main coverage and exact per-species energy lists;
- audits summary numerator/denominator/species wording;
- audits fit basis, file count, independent-energy count, legacy `n`, and minimum independent energies;
- records exact paths, byte sizes, and SHA-256 for every input;
- treats incomplete campaign coverage as a warning but returns nonzero for acceptance defects.

Added `tests/test_validate_i885_campaign_results.py` covering the current failure modes, a valid partial campaign, an out-of-manifest configuration, and CLI provenance/status.

Corrected and added:

- `geant4/single_stave/results/i885_v1/SUMMARY.md`
- `geant4/single_stave/results/i885_v1/AUDIT_INVALIDATION.md`
- `docs/validation/i885_campaign_acceptance_audit.md`
- `docs/validation/i885_campaign_acceptance_validation.json`
- `docs/validation/i885_campaign_acceptance.svg`

The SVG is explicitly a synthetic repository-audit schematic, not detector data, and communicates differences using text/shapes in addition to color.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/validate_i885_campaign_results.py \
  tests/test_validate_i885_campaign_results.py

python -m pytest tests/test_validate_i885_campaign_results.py -q
4 passed in 0.60s
```

Exact reconstructed inputs matched Git blobs:

- manifest `15c4bb9ac99c1742e35225687ddcdf4341cae451`;
- per-config CSV `d38a42b0696d106d1f15068f8d81ed76f91b1040`;
- fit JSON `49bf41b359fbab42e4c583acacba7df2aac401c8`;
- pre-correction summary `3ea2a10f0751a3a7bcbc3db79c6a9d73bd956ca4`.

Measured validator results:

```text
pre-correction bundle: status=FLAWED issues=20 warnings=1 exit=1
corrected-summary bundle: status=FLAWED issues=18 warnings=1 exit=1
```

The summary correction removed the two coverage issues. The remaining 18 issues are fit-independence/provenance defects across four fit records. JSON parsed, SVG parsed as XML, and changed Python lines were within 100 characters.

No Geant4 executable, ROOT file, real data, simulation rerun, accepted calibration, or detector-performance output was generated. Full repository pytest, ruff, CTest, and GitHub Actions were not run.

## Direct-to-main commits

Implementation and validation evidence:

- `189d785e068d9fec85796fdfb097bd2a3dc1fcea` — `feat(audit): validate issue 885 campaign acceptance`
- `583fa57c9277262dcc72de0f1fa749b1419a3a5d` — `test(audit): cover issue 885 campaign acceptance`
- `6945bbb4e314e3e57c8b181ba79468258c3ca7aa` — `docs(validation): record issue 885 campaign audit`
- `1a66794b9a3ac3163a5efa3f4aeee2f9d0ebf02c` — `docs(i885): correct partial coverage and quarantine fits`
- `a90a326c7f94ca210836aad0594fac59905db1f6` — `docs(i885): quarantine partial calibration fits`
- `52f9f38b8dd733fd17e7993b4a918473f48d9a0d` — `docs(validation): add issue 885 campaign record`
- `467c007cd3526a762258a7f1d3f00563a37db8a8` — `docs(validation): visualize issue 885 acceptance gate`

Coordination and provenance:

- `c40abd2a5d9e5b932950059d71247c796034a9cf` — `docs(audit): claim issue 885 campaign acceptance task`
- `c4bcd928b8c720086db9eb7ec73f664f4be300ce` — `docs(audit): track issue 885 calibration acceptance`
- `c65dd3b8d9f29a9efa1ae3205e57f721cb2bece7` — `docs(audit): index issue 885 campaign defects`
- `61adf3403838c24971fe382e4e1dcf876f983c58` — `docs(audit): map issue 885 result dependencies`
- `9a7960c9c3cc728c2f729a2f93a3ada0dd11e096` — `docs(audit): record issue 885 study review`
- `84385fdbf983080f2706cec1c289300c9a5a9341` — `docs(audit): classify issue 885 calibration claims`
- `8088a19e37114f09bfd926b7fa7a5e90c9d741fb` — `docs(audit): register issue 885 visual evidence`
- `8a0e148bcbb9cb646c2d62f101ff47d7a995313f` — `docs(audit): block unvalidated issue 885 calibration`
- `036079211edcd6021e9fdf73c603ca57908776b7` — `docs(audit): archive issue 885 campaign acceptance`

Every write returned a successful direct-main commit SHA. Remote history confirmed the commits consecutively. `SESSION_LOG.md` was not overwritten because the connector has no safe append primitive and replacing an append-only file from partial retrieval could destroy prior records. The complete immutable session entry is retained at:

`chatgpt_todo/archive/2026-07-23T132112Z_AUD-I885-001_CAMPAIGN_ACCEPTANCE.md`

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

## Acceptance and next action

- Independent validator and focused regression: COMPLETE (`4 passed`).
- Coverage reconstruction and corrected public summary: COMPLETE.
- Calibration-fit quarantine and visual evidence: COMPLETE.
- Direct-to-main delivery: COMPLETE.
- Corrected plotter/fits/P5/P5b regeneration: PARTIAL / BLOCKED under `BLK-I885-001`.

Next: modify `plot_i885_campaign.py` so all coverage is manifest-derived, fit inputs are seed-averaged unique energies, `n_files` and `n_energy_points` are distinct, fewer than three energies do not generate an accepted line, and fit range/residual/uncertainty diagnostics are retained. Regenerate P5/P5b and `i885_fits.json` from declared inputs and require zero validator issues before publishing calibration claims.
