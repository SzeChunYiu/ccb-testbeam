# Latest Handoff

## Session

- **UTC:** 2026-07-21T15:00Z
- **Task:** `AUD-G4-001` — persistent CI failure diagnosis and observability
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base commit:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Head before this run:** `6feea8707c9abff6142f1745c3e5d8d01774af24`
- **Status:** PARTIAL — the first synthetic fixture defect was fixed, but the next CI run still failed. The exact remaining pytest traceback was inaccessible because the connector truncated the large workflow log. Focused pytest-log artifact support is now committed so the next run can be diagnosed without guessing.

## Work selected

The highest-priority dependency-resolved work remained `AUD-G4-001`: obtain executable evidence for the new event, photon, and multiseed validators. The recheck CI run failed, so this session did not add more scientific analysis code. It improved CI observability while preserving pytest's true exit status.

## Evidence inspected

- PR `#868` metadata and complete changed-file list.
- Recheck workflow run `29836848008`, workflow `MC Validation CI`.
- Recheck job `88655291248`, name `test`.
- Step results:
  - checkout: success;
  - Python setup: success;
  - package installation: success;
  - unit tests: failure.
- Retrieved workflow job log through the GitHub connector.
- Inspected `.github/workflows/mc_validation_ci.yml`.
- Inspected the three new validator test modules and the multiseed validator implementation.
- Inspected current `ACTIVE_TASK.md`, `BACKLOG.md`, `BLOCKERS.md`, `SESSION_LOG.md`, and prior handoff.

## Observed problem

The job log contains the pytest failure detail, but the connector response was truncated before the failure summary and traceback. The workflow did not publish a smaller diagnostic artifact. Therefore, the remaining test defect could not be identified with sufficient evidence. No speculative code change was made.

## Change committed

### CI diagnostics

Commit:

- `18dfa7b72c7b532244b266993b3176e66714bcff` — `ci: preserve pytest diagnostics for audit failures`

Workflow behavior now:

```yaml
- name: Run unit tests
  shell: bash
  run: |
    set +e
    pytest tests/ -q --ignore=tests/integration 2>&1 | tee pytest.log
    status=${PIPESTATUS[0]}
    exit "$status"
- name: Upload pytest diagnostics
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: pytest-log-${{ github.run_id }}-${{ github.run_attempt }}
    path: pytest.log
    if-no-files-found: error
    retention-days: 14
```

This preserves the pytest exit status while making the complete focused test output downloadable after both successful and failed runs.

### Coordination updates

- `27c91a811320f3a9edf521e95a80c4a9e18a74cd` — record the persistent CI blocker and diagnostic strategy in `BLOCKERS.md`.
- `e7bfdfd5950838d0fd0421c008fbfb4c0e8532aa` — append this session to `SESSION_LOG.md`.
- This handoff update records the latest state and next exact actions.

## Validation performed

- Confirmed workflow path triggers include tests, configuration, package metadata, and the workflow itself.
- Confirmed `PIPESTATUS[0]` captures pytest's status rather than `tee`'s status.
- Confirmed the artifact step uses `if: always()` and therefore runs after a failing pytest step.
- Confirmed the artifact name is unique by workflow run and attempt.
- Confirmed missing `pytest.log` is itself treated as an error rather than silently ignored.
- Confirmed retention is limited to 14 days.
- Confirmed no raw detector data, ROOT outputs, generated physics plots, credentials, or unrelated files were modified.

## Evidence classification

- **Observed:** workflow run `29836848008` and job `88655291248` failed in the unit-test step after successful environment setup.
- **Observed limitation:** connector log output was truncated before the pytest traceback.
- **Implemented and statically reviewed:** focused pytest artifact upload with preserved failure status.
- **Pending runtime evidence:** next workflow run and downloadable `pytest-log-*` artifact.
- **Not evaluated:** validator correctness on real Geant4 ROOT files, one-thread/four-thread equality, photon multiset equality, forced-thread provenance, multiseed independence diagnostics, and the approximately 178 PE/event claim.

## Required next actions

1. Inspect the workflow run triggered by commit `18dfa7b72c7b532244b266993b3176e66714bcff` or the latest coordination head.
2. Fetch its workflow artifacts and download `pytest-log-<run>-<attempt>`.
3. Read the exact pytest failure and traceback.
4. Fix only the demonstrated defect; add a regression assertion if the defect is not already covered.
5. Require a subsequent successful CI conclusion before marking Python validation complete.
6. Add or verify a dedicated ruff step for the three validator scripts and tests.
7. In a supported Geant4 11.2.2/ROOT environment, build and generate same-seed one-thread, four-thread, and forced-thread outputs.
8. Run the event and photon validators.
9. Generate at least four unique seeds per effective-thread group and run the multiseed validator with preregistered thresholds.
10. Regenerate the approximately 178 PE/event result with uncertainty and full provenance.

## Artifact retrieval procedure

After the next workflow run completes:

1. Fetch workflow runs for the latest PR head.
2. Fetch artifacts for the run.
3. Select the artifact named `pytest-log-<run-id>-<run-attempt>`.
4. Download and inspect `pytest.log`.
5. Record the exact failing test, exception type, traceback, environment, and proposed fix in this handoff and `BLOCKERS.md`.

## Blockers

- `BLK-CI-001`: unit tests still fail; focused artifact support is pushed and the next run must be inspected.
- `BLK-G4-001`: no supported Geant4/ROOT/LUNARC runtime or generated optical outputs are available in this audit environment.

## Acceptance decision

Keep PR `#868` in draft. Do not merge until:

- all validator unit tests and lint pass;
- supported Geant4 compilation succeeds;
- same-seed event and photon reproducibility is demonstrated across effective thread counts;
- forced-thread provenance is verified;
- the multiseed ensemble is evaluated without unexplained failures;
- the approximately 178 PE/event result is regenerated with uncertainty and complete provenance.
