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
- Reviewed `.github/workflows/mc_validation_ci.yml` and found that failing pytest output was available only in the large job log, with no downloadable focused diagnostic artifact.
- Added deterministic CI diagnostics: pytest output is now tee'd to `pytest.log`, the pytest exit status is preserved through `PIPESTATUS`, and `actions/upload-artifact@v4` uploads the log even on failure.
- Commit: `18dfa7b72c7b532244b266993b3176e66714bcff` — `ci: preserve pytest diagnostics for audit failures`.
- Updated `BLOCKERS.md` in commit `27c91a811320f3a9edf521e95a80c4a9e18a74cd`.
- Validation performed: reviewed YAML trigger coverage, bash pipeline exit behavior, artifact execution under `if: always()`, artifact naming, missing-file failure behavior, and retention.
- Validation pending: the next workflow run must complete and its artifact must be downloaded and inspected. No Python-test success is claimed.
- Geant4/ROOT/LUNARC runtime blocker remains open.
