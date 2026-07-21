# Latest Handoff

## Session

- **UTC:** 2026-07-21T16:00Z
- **Task:** `AUD-G4-001` — diagnose second CI failure from focused pytest artifact
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base commit:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Head before this run:** `7ef6b1997e0a0a937a60d74633fefcef1189a2ab`
- **Status:** PARTIAL — the diagnostic artifact exposed one exact remaining synthetic-test defect. The fixture has been corrected and a CI recheck is required. Real Geant4/ROOT validation remains blocked.

## Work selected

The highest-priority dependency-resolved task remained `AUD-G4-001`: obtain executable evidence for the event, photon, and multiseed validators. The focused pytest artifact introduced in the prior session was available, so this run downloaded and inspected it before changing code.

## Evidence inspected

- PR `#868` metadata at head `7ef6b1997e0a0a937a60d74633fefcef1189a2ab`.
- `MC Validation CI` run `29841567992`.
- Job `88671487198`, name `test`.
- Step conclusions:
  - checkout: success;
  - Python setup: success;
  - package installation: success;
  - unit tests: failure;
  - pytest diagnostic artifact upload: success.
- Artifact `pytest-log-29841567992-1`:
  - artifact ID `8499645299`;
  - size 1523 bytes as a ZIP archive;
  - digest `sha256:4419acfc79abc323e0b2e2b5825885739aa84bb48135399a14e5cd41d3f41dac`;
  - contained `pytest.log` with the complete focused output.
- `tests/test_analyze_single_stave_multiseed_rng.py`.
- Current `BLOCKERS.md`, `SESSION_LOG.md`, and prior handoff.

## Exact observed test result

```text
1 failed, 146 passed, 1 skipped in 42.40s
```

Failing test:

```text
tests/test_analyze_single_stave_multiseed_rng.py::test_rejects_duplicate_seed_within_thread_group
```

Exception:

```text
ValueError: manifest labels must be unique
```

The exception occurred in `scripts/analyze_single_stave_multiseed_rng.py::build_summary()` before the intended duplicate-seed-within-effective-thread-group diagnostic was evaluated.

## Root cause

The test deliberately constructs two runs with the same configured seed and effective thread count:

```python
(101, 1, 0.0),
(101, 1, 0.1),
```

However, the synthetic `build_manifest()` helper generated labels only from seed and thread count:

```python
"label": f"s{seed}-t{threads}"
```

Both intentional duplicate-seed rows therefore received the same manifest label. Unique labels and unique seeds are separate invariants:

- manifest labels must always be unique so runs can be addressed unambiguously;
- configured seeds must be unique within an effective-thread group for the multiseed acceptance check.

The fixture accidentally violated the label invariant before reaching the seed invariant it was intended to test. The production validator behaved correctly by rejecting ambiguous labels.

## Change committed

Commit:

- `64a5c171de07506ed18326240618a456714d5593` — `test(g4): keep duplicate-seed fixture labels unique`

The helper now includes the row index:

```python
rows.append(
    {
        "root": str(root),
        "meta": str(meta),
        "label": f"run{index}-s{seed}-t{threads}",
    }
)
```

This keeps every synthetic run label unique while preserving the duplicated seed and thread count required by `test_rejects_duplicate_seed_within_thread_group`.

## Coordination updates

- `BLOCKERS.md` now records the exact workflow, job, artifact, digest, pytest summary, traceback, root cause, fix, and recheck gate.
- `SESSION_LOG.md` includes an append-only record of this run.
- This handoff replaces the prior artifact-retrieval instructions with the observed result and next acceptance step.

## Validation performed

- Confirmed the downloaded ZIP contained exactly one `pytest.log` file.
- Read the complete focused pytest output rather than relying on truncated workflow logs.
- Confirmed only one test failed and 146 passed, with one skipped.
- Traced the exception to the production label-uniqueness guard.
- Confirmed the production guard is scientifically and operationally valid: ambiguous labels would corrupt run-to-array mappings and diagnostics.
- Confirmed the intended duplicate seed/thread values remain unchanged after the fixture fix.
- Confirmed existing tests that pair the same seeds across different thread groups still receive unique labels.
- Confirmed no raw detector data, ROOT outputs, generated physics plots, credentials, or unrelated source files were modified.

## Evidence classification

- **Observed:** workflow run `29841567992` failed only in the unit-test step and successfully uploaded the pytest artifact.
- **Observed:** artifact output reported `1 failed, 146 passed, 1 skipped in 42.40s`.
- **Observed:** the remaining failure was caused by duplicate synthetic labels, not by a demonstrated production multiseed-analysis error.
- **Implemented and statically reviewed:** unique index-prefixed labels in the synthetic manifest helper.
- **Pending runtime evidence:** a successful CI recheck after commit `64a5c171de07506ed18326240618a456714d5593` and subsequent coordination commits.
- **Not evaluated:** correctness on real Geant4 ROOT files, one-thread/four-thread equality, photon multiset equality, forced-thread provenance, multiseed independence diagnostics, and the approximately 178 PE/event claim.

## Required next actions

1. Inspect the `MC Validation CI` run for the latest PR head.
2. Require the unit-test job to complete successfully.
3. If it fails, download the new `pytest-log-*` artifact and fix only the demonstrated defect.
4. Add or verify a dedicated ruff step for the three validator scripts and test modules.
5. In a supported Geant4 11.2.2/ROOT environment, build the single-stave simulation.
6. Generate same-seed one-thread, four-thread, and forced-thread outputs.
7. Run the event-tree and photon-tree validators.
8. Generate at least four unique seeds per effective-thread group and run the multiseed validator with preregistered thresholds.
9. Regenerate the approximately 178 PE/event result with uncertainty and complete provenance.
10. Update the claim-evidence and visualization matrices with the actual outputs and quantitative results.

## Blockers

- `BLK-CI-001`: second fixture defect fixed; successful CI recheck is still required.
- `BLK-G4-001`: no supported Geant4/ROOT/LUNARC runtime or generated optical outputs are available in this audit environment.

## Acceptance decision

Keep PR `#868` in draft. Do not merge until:

- all validator unit tests and lint pass;
- supported Geant4 compilation succeeds;
- same-seed event and photon reproducibility is demonstrated across effective thread counts;
- forced-thread provenance is verified;
- the multiseed ensemble is evaluated without unexplained failures;
- the approximately 178 PE/event result is regenerated with uncertainty and complete provenance.
