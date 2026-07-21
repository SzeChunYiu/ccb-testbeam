# Latest Handoff

## Session

- **UTC:** 2026-07-21T17:00Z
- **Tasks:** `AUD-G4-001` and `AUD-G4-002`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base commit:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Head at start:** `cc7b379fba133e15c2101e7aaf6f1bc0e1dc249b`
- **Status:** PARTIAL. Python unit tests passed at the start head. Lint has now been added to CI. Real Geant4/ROOT validation and regeneration of the optical-yield claim remain blocked.

## Evidence inspected

- PR #868 metadata and current branch changes.
- `MC Validation CI` run `29846207091`, run number `209`.
- Result: `status=completed`, `conclusion=success` at commit `cc7b379fba133e15c2101e7aaf6f1bc0e1dc249b`.
- `.github/workflows/mc_validation_ci.yml`.
- `pyproject.toml`, confirming ruff is included in the `dev` dependency set and configured for Python 3.9 compatibility.
- Commit `d51159fc3c41a70c804c5da329b20041617dd506`, whose message reports overlap-free optical collection and approximately 178 detected PE/event.
- `geant4/single_stave/KNOWN_ISSUES.md`.
- Existing `BLOCKERS.md`, `ACTIVE_TASK.md`, `BACKLOG.md`, `SESSION_LOG.md`, and prior handoff.

## Findings

### 1. Python unit-test blocker resolved for the starting head

The corrected workflow run completed successfully. This closes the pytest recheck required after the two synthetic-fixture fixes. It does not validate Geant4 compilation or real ROOT outputs.

### 2. CI trigger and lint gap

The workflow paths covered package source, tests, configuration, and the workflow itself, but not the three standalone RNG validator scripts. A script-only change could therefore avoid CI. The workflow also installed ruff but did not execute it.

Implemented:

- trigger coverage for:
  - `scripts/compare_single_stave_mt_reproducibility.py`;
  - `scripts/compare_single_stave_photon_trees.py`;
  - `scripts/analyze_single_stave_multiseed_rng.py`;
- a targeted ruff step for those scripts and their tests.

Commit: `c3fb8822d4db4a9c76602ec8321096a30903f98e`.

### 3. Internal contradiction in the optical-collection note

`KNOWN_ISSUES.md` said issues A/B were resolved at the top, but later sections still called them open and the final status said photon collection remained in progress. This made current status ambiguous to both users and AI sessions.

The document now labels the defects as historical, explains the implemented fixes, and separates prior LUNARC observations from current-branch validation still required.

Commit: `1e098d6523783adf5023843e5fed5926ca3d390e`.

### 4. Ambiguous PE-per-MeV denominator

The note reported:

- mean detected readout PE: approximately 178/event;
- mean deposited energy: approximately 16.8 MeV/event;
- ratio: approximately 10.6 PE/MeV.

The arithmetic is `178 / 16.8 ≈ 10.6`, so the denominator is deposited energy, not the 100 MeV incident proton kinetic energy. The revised text now states `PE/MeV deposited` explicitly and warns that this is not yet a calibrated detector response.

### 5. Optical claim lacks sufficient provenance and uncertainty

The repository records the values approximately 585 arrivals/event and 178 detected PE/event, but the reviewed note does not provide:

- exact output ROOT path and hash;
- exact metadata sidecar and hash;
- event count;
- seed;
- requested/effective/forced thread counts;
- complete command/configuration;
- mean spread, standard error, confidence interval, or seed-to-seed uncertainty;
- current-branch regeneration.

Therefore the claim remains a preliminary prior observation, not a validated current result.

Created `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md` with stable claim IDs `CLM-G4-001` through `CLM-G4-008`, evidence states, missing evidence, and required validation.

Commit: `28886b8805a2367b4cbf4c3b9fd16f241c8f24b8`.

## Files changed in this run

- `.github/workflows/mc_validation_ci.yml`
- `geant4/single_stave/KNOWN_ISSUES.md`
- `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/SESSION_LOG.md`
- `chatgpt_todo/HANDOFF.md`

## Validation performed

- Confirmed the prior CI run completed successfully.
- Confirmed ruff is installed by `.[dev]` and repository lint rules exist.
- Verified the new workflow paths exactly match the three validator scripts.
- Verified the ruff step names all three validator tests.
- Recomputed the documented ratio: `178 / 16.8 = 10.595...`, consistent with approximately 10.6 PE/MeV deposited.
- Cross-checked the contradictory resolved/open/in-progress wording in the prior known-issues document.
- Confirmed no raw data, ROOT files, generated physics artifacts, secrets, or unrelated files were modified.

## Evidence classification

- **Observed:** workflow run `29846207091` succeeded at the starting head.
- **Observed repository fact:** commit `d51159f...` and the known-issues note report approximately 585 arrivals/event and 178 detected PE/event.
- **Derived:** approximately 10.6 PE/MeV deposited from the two reported means.
- **Implemented:** CI path/lint coverage, reconciled documentation, and the claim-evidence matrix.
- **Not validated:** the optical values on the current branch, their uncertainty, thread invariance, multiseed stability, or agreement with real detector data.

## Blockers

- `BLK-CI-001`: pytest portion closed; the latest head must now pass the newly added ruff and pytest steps.
- `BLK-G4-001`: open. No supported Geant4 11.2.2/ROOT/LUNARC runtime or generated optical outputs are available in this session.

## Required next actions

1. Inspect the workflow run for the latest branch head and require both ruff and pytest to pass.
2. If lint fails, use the exact diagnostics and make only demonstrated formatting/import/upgrade fixes.
3. In a supported Geant4 11.2.2 environment, build and retain full logs.
4. Generate same-seed 1-thread, 4-thread, and forced-thread optical outputs.
5. Run the event-tree and photon-tree validators.
6. Generate at least four independent seeds per effective-thread group and run the multiseed validator using preregistered thresholds.
7. Locate or regenerate the exact optical configuration behind the historical 178 PE/event result.
8. Report event-level and seed-level uncertainty, complete provenance, ROOT/metadata hashes, and all required plots.
9. Update `CLAIM_EVIDENCE_MATRIX.md` and `VISUALIZATION_MATRIX.md` with actual artifact paths and verdicts.

## Acceptance decision

Keep PR #868 in draft. Do not merge until the latest Python CI passes and the Geant4/ROOT runtime acceptance criteria are satisfied. The 178 PE/event and 10.6 PE/MeV-deposited values must remain preliminary until regeneration with uncertainty and complete provenance.
