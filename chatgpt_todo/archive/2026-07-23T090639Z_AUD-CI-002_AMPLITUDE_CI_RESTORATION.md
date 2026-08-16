# AUD-CI-002 — Amplitude audit current-main CI restoration

## Session identity

- UTC: `2026-07-23T09:06:39Z`
- Owner: scheduled ChatGPT audit session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `345d82d1daccbe1d8eafcf525ab51fd19ab20832`
- Task state: COMPLETE

## Start-of-run review

- Confirmed repository admin/push access and default branch `main`.
- Inspected current recent history, PR #868, all open pull requests returned by GitHub search, current commit status, `ACTIVE_TASK.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, `CODE_RESULT_MAP.md`, `HANDOFF.md`, and recent `SESSION_LOG.md` entries.
- Direct clone attempt failed with `Could not resolve host: github.com`; authenticated GitHub connector reads/writes were used.
- PR #868 was confirmed closed and not merged. It was not reopened or merged.

## Confirmed defects

### Stale regression assertion

Production code emits `AMPLITUDE_CONVENTION_WITHOUT_BASELINE_LEVEL`, but `tests/test_amplitude_convention_audit.py` still asserted the superseded `ABSOLUTE_WITHOUT_BASELINE_LEVEL` name.

### Invalid-baseline aggregate undercount

`n_invalid_baseline_data_tables` counted only rows whose evidence-gated `physics_acceptance` was `BASELINE_DATA_INVALID`. A table without accepted evidence can still have incomplete pedestal values and an unconditional `convention_acceptance=BASELINE_DATA_INVALID`; the old aggregate omitted it. The repaired expression counts non-NET rows with that convention-level state, preserving the rule that hash-authorized NET processing does not require optional pedestal diagnostics.

## Validated transport

- PR: `#884`
- Base SHA: `345d82d1daccbe69b98c94ada34d48b5b7f84024e` was not used; actual PR base was `345d82d1daccbe1d8eafcf525ab51fd19ab20832`.
- Head: `9750d0fddc626a76f0c954fa09065db05ac83f32`
- Changed files: exactly two
  - `tools/audit/amplitude_convention_audit.py`
  - `tests/test_amplitude_convention_audit.py`
- Diff size: four additions, two deletions.
- Workflow: MC Validation CI run `29993563323`
- Job: `89161772967`
- Workflow/job conclusion: success.
- Merge method: squash.
- GitHub merge result: `merged=true`, `message="Pull Request successfully merged"`.
- Remote-main merge commit: `4f857f508160bbbe059d936866b426a45788c9bd`.
- Post-merge verification: recent commit search returned the merge commit as remote-main head; both changed main files were re-read and contained the exact reviewed changes.

## Coordination commits

- `f95b28c9ec764ebfe0a9c3983d69b5aa138a6ebb` — `docs(audit): record amplitude CI restoration task`
- `92cb21bfe54ad0fb165eac3d5265559dc2137a7e` — `docs(audit): close amplitude CI restoration backlog item`
- `a1b83fd8ea275b369830d36c2b39f84af3fb5166` — `docs(audit): index restored amplitude CI gate`
- `8d7e741eb4312af216dbf034b061b74fc7d8374c` — `docs(audit): map amplitude CI repair to audit outputs`
- `05b9f00430827e8c06220d3560014b86154ccd59` — `docs(audit): record resolved amplitude CI blocker`

## Validation boundary

- The successful workflow validates the repository Python unit-test gate exercised by that workflow on the PR merge ref.
- No raw detector data, pulse table, ROOT output, Geant4 simulation, figure, calibration, stopping distribution, or detector-performance result was generated or changed.
- No real amplitude convention, pedestal-subtraction authorization, or pulse polarity is inferred.
- `BLK-AMP-001` remains open and historical A-002 outputs remain quarantined.

## Next action

Continue the independent scientific audit with a non-overlapping item-level study/code review. For A-002 specifically, obtain the exact table and immutable convention/polarity evidence before any output regeneration.
