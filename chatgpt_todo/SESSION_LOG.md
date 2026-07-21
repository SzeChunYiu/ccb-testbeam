# Session Log

## 2026-07-21T08:00Z — AUD-G4-001

- Base: `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- Branch: `chatgpt/AUD-G4-001-mt-rng-seeding`
- Reviewed recent commits #861–#867, PR #867, `README.md`, `geant4/single_stave/src/main.cc`, and `RunAction.cc`.
- Found redundant per-worker reseeding in `BeginOfRunAction` after correct master seeding before run-manager construction.
- Removed worker reseed and documented Geant4 MT seed ownership.
- Initialized `chatgpt_todo` coordination files, task, backlog, master index, and handoff.
- External evidence: Geant4 11.2 MT documentation states that the master pre-generates event-associated seeds for reproducibility independent of worker configuration.
- Runtime checks not run: no local compiler, Geant4 environment, ROOT output, or LUNARC data exposed through the GitHub connector.
- Required next action: compile and perform 1-thread versus N-thread event-keyed reproducibility and merged-row validation before merge.

## 2026-07-21T09:00Z — AUD-G4-001

- Added explicit `--threads N` configuration, validation, startup reporting, run-manager configuration, and metadata provenance.
- Preserved sequential-build compatibility.
- Runtime validation remained unavailable.

## 2026-07-21T10:00Z — AUD-G4-001

- Added requested, effective, and `G4FORCENUMBEROFTHREADS` provenance.
- Added mismatch warning and sidecar persistence.

## 2026-07-21T11:00Z — AUD-G4-001

- Added event-tree integrity and event-keyed ROOT reproducibility validator with JSON/PDF output.
- Added synthetic uproot regression tests and type-safe string comparison.

## 2026-07-21T12:00Z — AUD-G4-001 / AUD-G4-003

- Added photon-tree schema, domain, foreign-key, canonical multiset, JSON, and PDF validation.
- Added synthetic photon tests.

## 2026-07-21T13:00Z — AUD-G4-001 / AUD-G4-004

- Added manifest-driven multiseed RNG ensemble validator and synthetic tests.
- Added exact stream hashing, seed coverage, duplicate detection, robust seed-mean diagnostics, cross-seed correlation diagnostics, and thread-group effects.
- Clarified that same seeds may be paired across thread groups but must be unique within each group.

## 2026-07-21T14:00Z — AUD-G4-001 CI triage

- Inspected Actions run `29832957171`, job `88641969815`.
- Found and fixed a row-alignment defect in the reordered-identical synthetic event fixture.
- Commit: `a39f507a8ce17a580a5b08c0bfd3a98da3776751`.
- CI success remained pending.

## 2026-07-21T15:00Z — AUD-G4-001 CI observability

- Inspected PR `#868` head `6feea8707c9abff6142f1745c3e5d8d01774af24`.
- Observed Actions run `29836848008` completed with failure in job `88655291248`, step `Run unit tests`; checkout, Python setup, and dependency installation passed.
- Retrieved the workflow log, but the connector truncated the response before the pytest failure summary. No remaining test defect was guessed or claimed.
- Added focused `pytest.log` artifact upload while preserving the pytest exit status.
- Commit: `18dfa7b72c7b532244b266993b3176e66714bcff`.
- Geant4/ROOT/LUNARC runtime blocker remained open.

## 2026-07-21T16:00Z — AUD-G4-001 CI artifact diagnosis

- Inspected Actions run `29841567992`, job `88671487198`.
- Downloaded artifact `pytest-log-29841567992-1` (ID `8499645299`, SHA-256 `4419acfc79abc323e0b2e2b5825885739aa84bb48135399a14e5cd41d3f41dac`).
- Exact result: `1 failed, 146 passed, 1 skipped in 42.40s`.
- Fixed the duplicate-seed fixture's accidental duplicate manifest labels.
- Commit: `64a5c171de07506ed18326240618a456714d5593`.

## 2026-07-21T17:00Z — AUD-G4-001 / AUD-G4-002 claim and CI audit

- Observed `MC Validation CI` run `29846207091` completed successfully at head `cc7b379fba133e15c2101e7aaf6f1bc0e1dc249b`; the Python unit-test gate is therefore satisfied for that head.
- Reviewed `.github/workflows/mc_validation_ci.yml` and found that changes limited to the three RNG validator scripts did not trigger the workflow and no dedicated ruff step existed.
- Added all three validator script paths to push/PR triggers and added a targeted ruff check for the scripts and their tests.
- Commit: `c3fb8822d4db4a9c76602ec8321096a30903f98e`.
- Audited commit `d51159fc3c41a70c804c5da329b20041617dd506` and `geant4/single_stave/KNOWN_ISSUES.md` for the reported 585 arrivals/event and 178 PE/event result.
- Found contradictory status language: the header marked issues A/B resolved while lower sections still called them open and the final status said photon collection was in progress.
- Found denominator ambiguity in the reported `10.6 PE/MeV`: it is `178 / 16.8 MeV deposited`, not `178 / 100 MeV incident`.
- Rewrote the note to separate prior observations, derived quantities, resolved historical defects, and validation still required.
- Commit: `1e098d6523783adf5023843e5fed5926ca3d390e`.
- Created `CLAIM_EVIDENCE_MATRIX.md` mapping the optical claims to current evidence, missing provenance, and required validation.
- Commit: `28886b8805a2367b4cbf4c3b9fd16f241c8f24b8`.
- Closed the pytest portion of `BLK-CI-001`, retained the new lint recheck, and kept the Geant4/ROOT runtime blocker open.
- Commit: `1f8649aa6fb5a4329de5bbee3e02a87045d020d0`.
- No new 178 PE/event value, uncertainty, or real-data agreement is claimed. The exact output file, sample size, seed/thread provenance, and ROOT hash remain unavailable.

## 2026-07-21T18:00Z — AUD-G4-001 CI diagnostics gate

- Inspected `MC Validation CI` run `29850745641`, run number `216`, job `88702685351`, at PR head `9bfc1284915ac1cd471b5ae7a9cb11cc424660bd`.
- Observed checkout, Python setup, and dependency installation succeed; `Lint RNG validation code` failed; pytest was skipped; the pytest-only artifact upload also failed because no `pytest.log` was created.
- Identified a CI observability defect: one failed check prevented the independent check from running and removed the focused diagnostics needed for evidence-based repair.
- Updated the workflow so ruff and pytest always execute, write `ruff.log` and `pytest.log`, expose their actual statuses, upload both logs in one `validation-logs-*` artifact, and fail only in a final aggregate gate.
- Workflow commit: `68e0f3b24cd146699bbb5f2173665fee244e5e93`.
- Updated `BLOCKERS.md` with the exact run/job, failure sequence, diagnostic design flaw, and next acceptance condition.
- Direct local clone and execution remained unavailable because the container could not resolve `github.com`; no lint finding was guessed or modified.
