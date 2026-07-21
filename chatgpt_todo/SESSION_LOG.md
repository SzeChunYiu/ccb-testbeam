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

- Base: `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- Branch: `chatgpt/AUD-G4-001-mt-rng-seeding`
- PR: `#868` (draft, mergeable at inspection time).
- Reviewed `AppConfig.hh`, `AppConfig.cc`, `main.cc`, `RunAction.cc`, PR #868, and the existing handoff.
- Found that worker count was not a declared CLI input and was absent from metadata, making the planned 1-thread versus N-thread validation incompletely reproducible.
- Added `--threads N`, positive-value validation, stdout reporting, pre-initialization `G4MTRunManager::SetNumberOfThreads`, and metadata field `threads_requested`.
- Preserved sequential-build compatibility with `#ifdef G4MULTITHREADED`.
- Static checks completed: configuration flow, initialization ordering, input validation, and provenance propagation.
- Runtime checks not run: connector environment has no checked-out Geant4/ROOT build or LUNARC outputs.
- Required next action: compile with Geant4 11.2.2, run same-seed 1-thread and 4-thread jobs, verify event IDs and event-keyed fields, compare photon distributions, and regenerate the approximately 178 PE/event result.

## 2026-07-21T10:00Z — AUD-G4-001

- Base: `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- Branch: `chatgpt/AUD-G4-001-mt-rng-seeding`
- PR: `#868` (draft, mergeable at start of session).
- Found that metadata still recorded only `threads_requested`, although `G4FORCENUMBEROFTHREADS` can override `SetNumberOfThreads`.
- Added effective-thread capture, exact override environment provenance, mismatch warning, and sidecar persistence.
- Runtime checks not run: no checked-out Geant4 11.2.2/ROOT environment or generated ROOT data.

## 2026-07-21T11:00Z — AUD-G4-001

- Added `scripts/compare_single_stave_mt_reproducibility.py` for event-ID integrity, event-key sorting, schema validation, branch comparison, provenance validation, JSON, and PDF diagnostics.
- Fixed string-branch comparison so NumPy `equal_nan=True` is not incorrectly applied to nonnumeric arrays.
- Added synthetic uproot regression tests.
- Checks not run: Python tests, ruff, Geant4 build, simulation, and real ROOT validation.

## 2026-07-21T12:00Z — AUD-G4-001 / AUD-G4-003

- Found that photon rows have no persistent photon ID, so ROOT row position is not a valid cross-thread identity.
- Added `scripts/compare_single_stave_photon_trees.py` with schema/domain/foreign-key validation, canonical multiset comparison, aggregate metrics, JSON, and PDF output.
- Added synthetic tests for reordered identical populations, invalid domains, changed values, and missing rows.
- Checks not run: pytest, ruff, Geant4 build, real ROOT event/photon validation, forced-thread run, multiseed ensemble, or approximately 178 PE/event regeneration.

## 2026-07-21T13:00Z — AUD-G4-001 / AUD-G4-004

- Base: `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- Branch: `chatgpt/AUD-G4-001-mt-rng-seeding`
- PR: `#868` (draft, mergeable at start of session).
- Reviewed the active task, backlog, prior event/photon validators, synthetic-test style, PR state, and visualization matrix.
- Identified that exact same-seed equality alone cannot reveal duplicated streams across different seeds or quantify seed/thread stability.
- Added `scripts/analyze_single_stave_multiseed_rng.py`, a manifest-driven ensemble validator.
- The validator requires complete event IDs and comparable physics provenance; tracks requested/effective/forced thread provenance; requires unique seeds within each effective-thread group; hashes complete selected event streams; detects exact stream duplication across different seeds; calculates per-run mean, standard deviation, SEM, extrema, robust seed-mean z scores, event-indexed cross-seed Pearson correlations with Fisher-z significance, seed coverage, and thread-group mean effects.
- Added JSON summary and PDF pages showing run means with within-run SEM and robust seed-level outlier diagnostics.
- Added synthetic tests for a passing two-thread-group ensemble, exact duplicate streams across different seeds, duplicate seeds within a thread group, insufficient seed coverage, JSON output, and PDF generation.
- During static review, corrected the experimental design so the same seeds may be reused across thread configurations for paired reproducibility; uniqueness is enforced within each effective-thread group rather than globally.
- Added an explicit caveat that these diagnostics do not prove full RNG independence and that thresholds must be preregistered.
- Commits added: `7dfecc4`, `a311a67`, `82a6d02`, `fbfa1af`, plus coordination updates.
- Static validation performed: Python syntax was parsed before upload; manifest/schema flow, event sorting, provenance gates, exact hash fields, duplicate detection, threshold gates, exit status, JSON/PDF paths, and synthetic failure cases were reviewed.
- Checks not executed: pytest, ruff, Geant4 compilation, real multiseed runs, actual correlations, thread effects, and optical-yield regeneration. No runtime success is claimed.
- Required next action: run all three validator test modules and lint, generate at least four seeds for one-thread and four-thread configurations, execute the event/photon/multiseed validators, inspect multiplicity effects and preregistered thresholds, then regenerate the approximately 178 PE/event claim with uncertainty.
