# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T224320Z`
- **Task:** `AUD-MERGE-001`
- **Unit:** PR #868 current-main mapping and single-stave status synchronization
- **Initial remote `main`:** `1e99395ee2bdf0907f82782e5b2b0b2680a3c90f`
- **Validated evidence head:** `2dcbbdc86450707c0d6d8c1d3fe5ccc0c57e5fa1`
- **Coordination/archive head before handoff:** `18ed01724728cf722473a54d815fb1acbae910d2`
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or stale-PR merge
- **Acceptance:** **COMPLETE** for this integration/documentation unit

## Start-of-run review and concurrency

Authenticated GitHub reads inspected recent `main` history, repository metadata,
open PRs, PR #868 and its file inventory, the successful PR workflow job, current
single-stave C++ implementation, three validation scripts and tests, the MC
validation workflow, canonical Geant4 results, `KNOWN_ISSUES.md`, and the
repository-local coordination system.

A concurrent `AUD-WIKI-001` session was actively working on the exact MV3 public
WIKI gate. This run did not duplicate or alter that candidate and selected the
independent `BLK-MERGE-001` integration question.

## PR #868 disposition

PR #868 remains closed, unmerged, and non-mergeable. Its head is
`7992aa318b6f13b5f4bcbd828ad97996075fed4b`.

The validated technical implementation is already represented on current main:

### Exact blob matches

- multiseed RNG analyzer: `a92d79b593cc7de6b1d6a34a2733fb9148331b55`
- event comparator: `c4e379f209ee1513b2b33c08e91903bda744c892`
- photon comparator: `849456e492f55af63cfdf8e030fa9980f69dd4c0`
- multiseed tests: `bd9f3a5d76ba76fe8c0a9dbe0a5998c661b77f69`
- event-comparator tests: `cdcf8d7c58997ade812ab2c48f458d98a287238b`
- photon-comparator tests: `deb1e85189c96ffc4c427a6051ec67edba1ce5ce`

### Current-main semantic supersets

- requested/effective/forced thread fields and CLI are present;
- current numeric parsing is stricter than the PR version;
- master-owned RNG seeding is configured before run-manager construction;
- worker `BeginOfRunAction` does not reseed;
- requested/effective/`G4FORCENUMBEROFTHREADS` provenance is recorded;
- the MC validation workflow covers all six exact-matched scripts/tests and the
  broader non-integration unit suite.

The PR branch is therefore not needed as a transport mechanism and must not be
merged over current coordination or later scientific changes. `BLK-MERGE-001` is
resolved by the file-level mapping and retained CI/runtime evidence.

## PR validation evidence

- GitHub Actions run: `29861328983`
- job: `88738491575`
- conclusion: success
- recorded tests: `147 passed, 1 skipped in 41.64s`
- completed stages: lint, unit tests, artifact upload, result enforcement

## Confirmed documentation flaw

The former `geant4/single_stave/KNOWN_ISSUES.md` contradicted itself:

- the opening update said photon collection and overlap testing were resolved;
- the body still had `Open issue A` and `Open issue B`;
- the final status said `photon-collection readout IN_PROGRESS`;
- exact 1T/48T and four-seed evidence was absent.

The exact former text failed the new validator with status 1, `FLAWED`, and 19
findings: 12 missing current-status tokens, four missing seed means, and three
stale resolved-issue narratives.

## Correction delivered

Updated:

- `geant4/single_stave/KNOWN_ISSUES.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this handoff

Added:

- `tools/audit/validate_single_stave_known_issues.py`
- `tests/test_validate_single_stave_known_issues.py`
- `docs/validation/single_stave_known_issues_audit.md`
- `docs/validation/single_stave_known_issues_validation.json`
- `docs/validation/single_stave_known_issues.svg`
- `chatgpt_todo/archive/2026-07-24T224320Z_AUD-MERGE-001_PR868_MAIN_MAPPING.md`

Policy:

`KNOWN_ISSUES_MUST_MATCH_REPOSITORY_RECORDED_G4_VALIDATION`

The corrected document records:

- Geant4 11.2.2 / GCC 12.3.0 / `hpua40`;
- 100 MeV protons and 500 events per run;
- 27/27 event branches exact equal for same-seed 1T/48T;
- 1,170,091 photon records with all six stored fields exact equal;
- seed means 177.1, 178.0, 179.5, and 178.5 PE/event;
- cross-seed mean 178.3 PE/event and seed-mean RSE 0.48%.

It explicitly states that this is not a detector calibration and retains
`BLK-G4-SP-001`.

## Validation commands and results

```text
python -m py_compile \
  tools/audit/validate_single_stave_known_issues.py \
  tests/test_validate_single_stave_known_issues.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_single_stave_known_issues.py -q

5 passed in 0.05s
```

Additional checks:

- exact former-text negative control: `FLAWED`, 19 findings, status 1;
- corrected direct validation: `VALIDATED`, zero issues;
- validation JSON parse: PASS;
- SVG XML parse: PASS;
- maximum changed Python line lengths: 97 and 93 characters.

## Direct-main commit sequence

- `f3c68c77098274ba77934021cd84ebcc70edbae2` — synchronize status document;
- `d7b50b5baa36445b950474feafb37858c6367cae` — fail-closed validator;
- `745931d565a985288bb06c3629a02702b993082a` — focused tests;
- `57e4d30fd654a1d467b456756a72ef303f0bfed9` — validation JSON;
- `01294ceb2f0151f2af36dece2e0af25f6645e493` — audit report;
- `2dcbbdc86450707c0d6d8c1d3fe5ccc0c57e5fa1` — visual evidence;
- `e4be24e39e2c2c881b5e16f3a41bd74e5407ffd7` — active-task completion;
- `18ed01724728cf722473a54d815fb1acbae910d2` — immutable archive.

The connector returned successful direct-main commit SHAs rather than
conventional textual `git push` stdout. A post-write recent-history read must
confirm this handoff commit and the sequence on remote `main`; that confirmation
is reported to the user with the resulting remote head.

## Scientific boundary

This unit validates repository integration and documentation consistency. It
does not independently rerun Geant4, inspect the original ROOT files, validate
PE/MeV transfer, establish beam-data closure, validate stopping power, or quantify
model/material/detector systematics. The 0.48% RSE covers the four recorded seed
means only.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were not
replaced because their current contents are shared long-lived records and the
connector exposes whole-file replacement rather than a byte-safe append/patch.
Another scheduled session was concurrently updating coordination. Reconstructing
or replacing those files risked lost updates. The complete append-equivalent
record is preserved in the immutable archive and this handoff; the aggregate
`BLK-MERGE-001` section may remain stale until a byte-safe coordination update.

## Next exact action

Publish the validated 24,023-byte root-WIKI MV3 candidate recorded by the prior
`AUD-WIKI-001` handoff through a byte-safe complete-file write, then require zero
findings from the new MV3 validator, the existing front-door gates, and the WIKI
internal-link check against remote-equivalent bytes.
