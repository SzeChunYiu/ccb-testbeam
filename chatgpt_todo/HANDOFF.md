# Latest Handoff

## Session

- **UTC:** 2026-07-21T14:00Z
- **Task:** `AUD-G4-001` — CI triage for MT reproducibility validation
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base commit:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Current pushed head:** `5d2bde29d29f4b763fde9089963b5179d76d41a4`
- **Status:** PARTIAL — a demonstrated synthetic-test fixture defect was fixed and documented. A new CI run is still required before Python validation can be marked successful. Geant4/ROOT runtime acceptance remains blocked.

## Work selected

The previous handoff required executing the new validator tests. The latest GitHub Actions run provided the first runtime evidence, and it failed. This run therefore prioritized exact CI diagnosis rather than adding more unexecuted analysis code.

## Repository and CI evidence inspected

- PR `#868`, head before this run: `412726c5e70b828019f006b85592561506092a05`
- GitHub Actions workflow: `MC Validation CI`
- Workflow run: `29832957171`
- Job: `88641969815` (`test`)
- Failed step: `Run unit tests`
- Successful prior steps: checkout, Python setup, package installation
- `tests/test_compare_single_stave_mt_reproducibility.py`
- `scripts/compare_single_stave_mt_reproducibility.py`
- Existing `ACTIVE_TASK.md`, `BACKLOG.md`, `SESSION_LOG.md`, and prior handoff

## Confirmed defect

The helper `write_run` in `tests/test_compare_single_stave_mt_reproducibility.py` created three per-event branches:

- `event`
- `edep_scint_MeV`
- `n_scint_generated`

The passing row-order-invariance test constructed:

- reference rows with event order `[0, 1, 2]` and energy values `[1, 2, 3]`;
- candidate rows with event order `[2, 0, 1]` and energy values `[3, 1, 2]`.

However, the helper always wrote `n_scint_generated=[10,20,30]`, independent of the supplied row values. After sorting by event ID, the candidate branch became `[20,30,10]`, while the reference remained `[10,20,30]`. The validator was therefore correct to reject the candidate: the two synthetic event tables were not identical.

This is a test-fixture defect, not evidence of a validator defect and not evidence about Geant4 MT reproducibility.

## Fix committed

Commit:

- `a39f507a8ce17a580a5b08c0bfd3a98da3776751` — `test(g4): keep reordered synthetic event branches aligned`

Change:

```python
numeric = np.asarray(values, dtype=np.float64)
...
"edep_scint_MeV": numeric,
"n_scint_generated": (numeric * 10).astype(np.int32),
```

All synthetic per-event branches now remain attached to the same row when event rows are permuted. An explanatory comment was added to prevent the same fixture-design error from recurring.

Coordination commits:

- `9ad30ce871cd3b778aaa1be1f1a7125e951df1c8` — record the CI diagnosis and fix in `SESSION_LOG.md`
- `5d2bde29d29f4b763fde9089963b5179d76d41a4` — create `chatgpt_todo/BLOCKERS.md` with exact CI and runtime blockers

## Evidence classification

- **Observed:** Actions run `29832957171` completed with failure in the unit-test step.
- **Proven by static reconstruction:** the pass fixture contained a genuine event-keyed mismatch in `n_scint_generated`.
- **Implemented:** the fixture now derives both numeric branches from the same row-aligned values.
- **Pending:** a new Actions run must confirm whether this was the only failing test.
- **Not evaluated:** real Geant4 output, one-thread/four-thread equality, photon multiset equality, multiseed independence diagnostics, and optical yield.

## Validation performed this run

- Inspected the exact CI run, job, and failed step.
- Confirmed checkout and dependency installation completed before the failure.
- Reconstructed reference and candidate branch contents before and after event-ID sorting.
- Confirmed the existing validator should fail the old fixture.
- Reviewed the replacement helper for row alignment, dtype stability, and preservation of the intentional numeric-mismatch test.
- Confirmed no raw data, ROOT outputs, generated PDFs, secrets, or unrelated files were changed.

## Validation not yet complete

- No new successful CI conclusion is available yet.
- Direct local pytest and ruff execution were not available through the GitHub connector session.
- Geant4 11.2.2 compilation was not performed.
- No real ROOT files were generated or compared.
- The approximately 178 PE/event claim was not regenerated.

## Required next actions

1. Inspect the next `MC Validation CI` run on a head containing `a39f507a...`.
2. If it fails, read the exact failing traceback and fix only the demonstrated defect.
3. When unit tests pass, run or add a dedicated lint check for the three validator scripts and tests.
4. Build `geant4/single_stave` with supported Geant4 11.2.2.
5. Generate same-seed one-thread and four-thread optical outputs, plus the forced-thread provenance case.
6. Run the event-tree and photon-tree validators.
7. Generate at least four unique seeds per effective-thread group and run the multiseed validator with preregistered thresholds.
8. Regenerate the approximately 178 PE/event result with uncertainty and full provenance.
9. Update affected study, claim, figure, table, and wiki records only after runtime evidence exists.

## Commands for the next execution environment

```bash
python -m pytest \
  tests/test_compare_single_stave_mt_reproducibility.py \
  tests/test_compare_single_stave_photon_trees.py \
  tests/test_analyze_single_stave_multiseed_rng.py \
  -q

ruff check \
  scripts/compare_single_stave_mt_reproducibility.py \
  scripts/compare_single_stave_photon_trees.py \
  scripts/analyze_single_stave_multiseed_rng.py \
  tests/test_compare_single_stave_mt_reproducibility.py \
  tests/test_compare_single_stave_photon_trees.py \
  tests/test_analyze_single_stave_multiseed_rng.py
```

## Blockers

See `chatgpt_todo/BLOCKERS.md`:

- `BLK-CI-001`: fix pushed; successful CI recheck pending.
- `BLK-G4-001`: no supported Geant4/ROOT/LUNARC runtime in this audit session.

## Acceptance decision

Keep PR `#868` in draft. Do not merge until:

- the validator unit tests and lint pass;
- supported Geant4 compilation succeeds;
- same-seed event and photon reproducibility is demonstrated across effective thread counts;
- forced-thread provenance is verified;
- the multiseed ensemble is evaluated without unexplained failures;
- the approximately 178 PE/event result is regenerated with uncertainty and complete provenance.
