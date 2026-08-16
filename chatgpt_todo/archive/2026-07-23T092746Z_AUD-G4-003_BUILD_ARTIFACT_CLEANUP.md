# Immutable Session Record — AUD-G4-003

## Session

- **UTC:** 2026-07-23T09:27:46Z
- **Task:** AUD-G4-003 (repository hygiene COMPLETE; PR #888 scientific source review PARTIAL)
- **Initial remote main:** `3ecefa27002e370f57001399d27a88244e0aa523`
- **Concurrent main incorporated:** `aea19386b7d2f25e5a0b5d64bb585f3fe0f1a2ef` (PR #889)
- **Validated cleanup on remote main:** `c7cdd653c5fef08b1e70cb33db9c574f7e7e0de9`
- **Commit message:** `fix(repo): remove tracked Geant4 build artifacts`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Canonical destination:** `main`

## Start-of-run review

- Confirmed admin/push access and `main` as the default branch.
- Attempted a direct clone; DNS resolution of `github.com` failed, so authenticated GitHub connector reads/writes were used.
- Read the current handoff, active task, backlog, master index, blocker register, code-result map, study ledger, session-log tail, current history, PR #868 status, and merged PR #888 metadata/files/CI.
- PR #868 remains closed and unmerged; it was not modified.
- A concurrent PR #889 merged after the run began. The cleanup was rebuilt on its exact main commit before pushing, preserving all concurrent source changes.

## Independent PR #888 finding

PR #888 changed 71 files. Exactly 66 were added below `geant4/single_stave/build/`, including:

- `CMakeCache.txt` and generated CMake/Make files;
- compiler-identification executables and ABI probes;
- `.o`, `.o.d`, dependency, and linker-command files;
- the linked `ccb_stave_sim` executable;
- copied `macros/` and `optical/` runtime assets;
- a generated `proton_smoke.root.meta.json` sidecar.

The cache embedded absolute LUNARC worktree, compiler, Python, Geant4, Qt, and library paths. `geant4/single_stave/CMakeLists.txt` explicitly copies source `macros/` and `optical/` directories into the binary directory, confirming those copies are generated build products rather than canonical source. The source and build copies of `proton_point.mac` had the same Git blob SHA before cleanup.

PR #888 workflow run `29994419166` completed successfully, but its only job installed Python and ran unit tests. It did not independently establish a clean Geant4 build or runtime physics validation.

## Validated change

Remote-main commit `c7cdd653c5fef08b1e70cb33db9c574f7e7e0de9`:

- removed the complete tracked `geant4/single_stave/build/` tree;
- added `geant4/**/build/` to `.gitignore`;
- added `tests/test_no_tracked_geant4_build_artifacts.py`, which inspects the Git index with `:(glob)geant4/**/build/**` and fails if any generated build path is tracked.

No PR #888 or PR #889 scientific source file was reverted.

## Validation

Executed locally in a synthetic Git checkout:

```text
python -m py_compile tests/test_no_tracked_geant4_build_artifacts.py
python -m pytest tests/test_no_tracked_geant4_build_artifacts.py -q
```

The regression first failed as designed with a tracked `geant4/demo/build/CMakeCache.txt`. After removing that path and adding the ignore rule, it returned:

```text
1 passed in 0.03s
```

`git check-ignore -v geant4/demo/build/CMakeCache.txt` matched `geant4/**/build/`.

Before advancing `main`, the candidate commit was inspected by SHA:

- `.gitignore` contained the new rule;
- the new regression file matched the validated local copy;
- `geant4/single_stave/build/CMakeCache.txt` returned 404;
- `geant4/single_stave/src/SteppingAction.cc` remained present with the merged PR #888 source change.

GitHub `update_ref` returned `success=true`. A subsequent remote history query confirmed `c7cdd653c5fef08b1e70cb33db9c574f7e7e0de9` at the head of `main` before coordination writes.

## Scientific boundary

- No Geant4 executable was run in this session.
- No CTest, ROOT analysis, detector simulation, plot, table, calibration, or numerical detector-performance result was generated or changed.
- Removing environment-specific build products neither validates nor invalidates the source-level claims in PR #888 or PR #889.
- The four PR #888 fixes and four PR #889 fixes remain PARTIAL until reviewed against primary Geant4/software documentation and exercised in a clean build with retained logs and immutable outputs.
- Historical A-002 outputs remain quarantined under `BLK-AMP-001`.

## Repository-local records

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/CODE_RESULT_MAP.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/STUDY_REVIEW_LEDGER.md`
- `chatgpt_todo/SESSION_LOG.md`
- `chatgpt_todo/HANDOFF.md`

Added immutable record:

- `chatgpt_todo/archive/2026-07-23T092746Z_AUD-G4-003_BUILD_ARTIFACT_CLEANUP.md`

## Acceptance status

- Removal of 66 tracked generated build files: COMPLETE.
- Future Geant4 build-tree ignore rule: COMPLETE.
- Git-index recurrence regression: COMPLETE and synthetically validated.
- Validated cleanup on remote `main`: CONFIRMED at `c7cdd653c5fef08b1e70cb33db9c574f7e7e0de9`.
- Independent scientific review of PR #888/#889 source changes: PARTIAL.
- PR #868: closed and unmerged.

## Next action

Review one PR #888/#889 source-level claim at a time. Start with Birks visible-energy semantics in `SteppingAction.cc`: verify the Geant4 API contract and material/Birks configuration, add a focused regression or clean-build runtime check, and preserve exact compiler/Geant4 versions, commands, logs, seeds, event counts, and output hashes before promoting any physics interpretation.
