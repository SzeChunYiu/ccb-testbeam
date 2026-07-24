# AUD-MERGE-001 — PR #868 current-main mapping and status synchronization

## Session identity

- Session stamp: `2026-07-24T224320Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `1e99395ee2bdf0907f82782e5b2b0b2680a3c90f`
- Core evidence head before coordination: `2dcbbdc86450707c0d6d8c1d3fe5ccc0c57e5fa1`
- Task: `AUD-MERGE-001`
- Related blocker: `BLK-MERGE-001`

## Start-of-run and concurrency review

The session inspected recent `main` history, current coordination files, open PRs,
PR #868, its changed-file inventory, its successful Actions job, the current MC
validation workflow, single-stave configuration/RNG/provenance code, validation
scripts/tests, `KNOWN_ISSUES.md`, and the canonical runtime result record.

A concurrent `AUD-WIKI-001` session was actively staging an MV3 WIKI
synchronization gate. This task deliberately avoided modifying its WIKI candidate
or validator and selected the independent PR #868 integration blocker instead.

## PR #868 state and CI

- PR state: closed
- Merged: false
- Mergeable: false
- Head: `7992aa318b6f13b5f4bcbd828ad97996075fed4b`
- GitHub Actions run: `29861328983`
- Job: `88738491575`
- Conclusion: success
- Recorded focused result: `147 passed, 1 skipped in 41.64s`
- The job completed lint, unit-test, artifact-upload, and enforcement steps.

No stale branch merge was attempted.

## Current-main implementation map

### Exact Git blob matches

| Path | PR #868 blob = current-main blob |
|---|---|
| `scripts/analyze_single_stave_multiseed_rng.py` | `a92d79b593cc7de6b1d6a34a2733fb9148331b55` |
| `scripts/compare_single_stave_mt_reproducibility.py` | `c4e379f209ee1513b2b33c08e91903bda744c892` |
| `scripts/compare_single_stave_photon_trees.py` | `849456e492f55af63cfdf8e030fa9980f69dd4c0` |
| `tests/test_analyze_single_stave_multiseed_rng.py` | `bd9f3a5d76ba76fe8c0a9dbe0a5998c661b77f69` |
| `tests/test_compare_single_stave_mt_reproducibility.py` | `cdcf8d7c58997ade812ab2c48f458d98a287238b` |
| `tests/test_compare_single_stave_photon_trees.py` | `deb1e85189c96ffc4c427a6051ec67edba1ce5ce` |

### Current-main semantic supersets

- `AppConfig.hh` retains requested/effective/forced thread fields.
- `AppConfig.cc` retains `--threads`, provenance description, and positivity
  checks, and additionally uses checked finite numeric parsing.
- `main.cc` seeds the master before run-manager construction, sets requested
  threads, reads the effective count, records `G4FORCENUMBEROFTHREADS`, and warns
  on overrides.
- `RunAction.cc` does not reseed workers and records requested/effective/forced
  thread provenance in the metadata sidecar; current main also has stronger JSON
  escaping.
- `.github/workflows/mc_validation_ci.yml` lints all three exact-matched scripts
  and tests and runs the broader non-integration test suite.

The validated technical implementation from PR #868 is therefore represented on
current `main`. The former PR coordination files are stale and superseded and
must not be transported over current coordination.

## Confirmed documentation defect

The pre-change `geant4/single_stave/KNOWN_ISSUES.md` simultaneously said the
photon-collection and overlap-test issues were resolved and labelled them as
`Open issue A`, `Open issue B`, and `photon-collection readout IN_PROGRESS`.
It omitted the exact 1T/48T and four-seed evidence recorded later in
`docs/validation/G4_VALIDATION_RESULTS.md`.

The exact former bytes failed the new validator:

- exit status: `1`
- status: `FLAWED`
- findings: `19`
- classes: 12 missing current-status tokens, 4 missing seed means, 3 stale
  resolved-issue narratives

## Correction and evidence

Updated:

- `geant4/single_stave/KNOWN_ISSUES.md`
- `chatgpt_todo/ACTIVE_TASK.md`

Added:

- `tools/audit/validate_single_stave_known_issues.py`
- `tests/test_validate_single_stave_known_issues.py`
- `docs/validation/single_stave_known_issues_audit.md`
- `docs/validation/single_stave_known_issues_validation.json`
- `docs/validation/single_stave_known_issues.svg`
- this immutable archive record

The corrected document reports the exact repository-recorded facts:

- Geant4 11.2.2 / GCC 12.3.0 / `hpua40`
- 500 events per run
- 27/27 event branches exact equal
- 1,170,091 photon records and all six fields exact equal
- seed means 177.1, 178.0, 179.5, 178.5 PE/event
- cross-seed mean 178.3 PE/event and seed-mean RSE 0.48%

It explicitly states that this is not a detector calibration and keeps
`BLK-G4-SP-001` open.

## Exact validation

```text
python -m py_compile \
  tools/audit/validate_single_stave_known_issues.py \
  tests/test_validate_single_stave_known_issues.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_single_stave_known_issues.py -q

5 passed in 0.05s
```

Additional checks:

- exact former-text negative control: status 1, `FLAWED`, 19 findings
- corrected direct validation: `VALIDATED`, zero issues
- validation JSON parse: PASS
- SVG XML parse: PASS
- maximum Python line lengths: validator 97, tests 93

The validation was executed on exact local reconstructions of the repository
files. The connector-only environment did not independently execute Geant4 or
open the original ROOT files.

## Direct-main commits

- `f3c68c77098274ba77934021cd84ebcc70edbae2` — synchronize status document
- `d7b50b5baa36445b950474feafb37858c6367cae` — validator
- `745931d565a985288bb06c3629a02702b993082a` — focused tests
- `57e4d30fd654a1d467b456756a72ef303f0bfed9` — validation JSON
- `01294ceb2f0151f2af36dece2e0af25f6645e493` — audit report
- `2dcbbdc86450707c0d6d8c1d3fe5ccc0c57e5fa1` — visual evidence
- `e4be24e39e2c2c881b5e16f3a41bd74e5407ffd7` — active-task completion

The GitHub contents connector returned successful commit SHAs rather than
conventional textual `git push` output. Final remote-head confirmation is recorded
in `chatgpt_todo/HANDOFF.md` after the final coordination commit.

## Scientific boundary

This task validates code integration and documentation consistency. It does not
independently reproduce the LUNARC runtime, validate PE/MeV transfer, establish
beam-data closure, validate stopping power, or quantify detector/model
systematics. The 0.48% RSE covers only the four recorded seed means.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, and `BLOCKERS.md` were not replaced during this
connector-only session because their current contents are long-lived shared
coordination records and GitHub's contents action performs whole-file
replacement. Reconstructing or replacing them while another scheduled session
was active risked lost updates. The complete append-equivalent record is retained
here and in the latest handoff. `BLK-MERGE-001` is resolved by this evidence even
if its aggregate section remains stale until a byte-safe coordination update.
