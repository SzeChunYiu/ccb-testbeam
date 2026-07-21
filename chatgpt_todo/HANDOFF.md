# Latest Handoff

## Session

- **UTC:** 2026-07-21T08:00Z
- **Task:** `AUD-G4-001`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **Status:** PARTIAL — code correction committed to branch; runtime validation still required.

## Area reviewed

Recent single-stave Geant4 optical-simulation changes, especially PR #867 (`SetNtupleMerging(true)`) and the random-number initialization path in:

- `geant4/single_stave/src/main.cc`
- `geant4/single_stave/src/RunAction.cc`

## Finding

The code seeded CLHEP before constructing the run manager in `main.cc`, then reapplied the identical seed in every `RunAction::BeginOfRunAction`. Geant4 MT pre-generates event seeds on the master and assigns them independently of worker scheduling. Reseeding inside the worker run action can overwrite that state and create correlated streams or thread-count-dependent results.

### Evidence classification

- **Repository fact:** identical configured seed was applied before run-manager construction and again in `BeginOfRunAction`.
- **Official design fact:** Geant4 MT uses master-generated seeds associated with events to provide reproducibility independent of thread scheduling.
- **Inference requiring runtime confirmation:** the redundant worker reseed may have biased or correlated earlier MT optical-calibration samples. Existing physics results are not declared invalid yet; affected outputs must be regenerated and compared.

## Changes

1. Removed `CLHEP::HepRandom::setTheSeed` from `RunAction::BeginOfRunAction`.
2. Removed the now-unused `Randomize.hh` include from `RunAction.cc`.
3. Clarified in `main.cc` that the seed must be set before run-manager construction.
4. Created the initial `chatgpt_todo` coordination protocol and active task record.

## Commits on task branch

- `bbeb4bf733cb8cc9e41aac1765b54d8768746947` — `fix(g4): preserve Geant4 MT event seeding`
- `d2129cfbf5be0ac141bce08915b4abe7f23bc293` — `docs(g4): explain master-before-run-manager seeding`
- `e0ff48efedc8fe82bf1223ecdc435a8665a980a7` — `chore(chatgpt_todo): establish audit coordination protocol`
- `bb4664b20a51ae5c362ceda5bf6caf6d9ed5eb54` — `chore(chatgpt_todo): claim MT RNG audit task`

GitHub contents writes update the remote task branch directly. A pull request should be opened after the remaining coordination files are added.

## Validation not executed

This session had GitHub repository access but no checked-out build environment, Geant4 runtime, ROOT files, or LUNARC data access. Therefore it did **not** claim:

- successful compilation;
- runtime correctness;
- identical one-thread/multi-thread event output;
- absence of bias in previous calibration outputs;
- regenerated optical-photon or calibration results.

## Required next validation

1. Build with the repository-supported Geant4 11.2.2 environment.
2. Run identical configuration/seed with 1 and at least 4 worker threads.
3. Sort event ntuples by event ID and compare all deterministic fields event-by-event.
4. Verify complete, unique event IDs in the merged ROOT file.
5. Run multiple seeds and compare photon yield, arrival-time, wavelength, path-length, and detected-PE distributions.
6. Regenerate the claimed `178 PE/event` sample if it used the old worker reseeding.
7. Produce:
   - event-by-event absolute-difference plot;
   - event-ID completeness/duplication plot;
   - one-thread versus multi-thread distribution overlays with ratio panels;
   - seed-to-seed correlation/ensemble summary.
8. Record commands, Geant4/ROOT/compiler versions, thread counts, seed values, event counts, hashes, quantitative differences, and plot paths.

## Acceptance decision

Do not merge until compilation and thread-count reproducibility checks pass. If outputs differ after sorting by event ID, inspect run-manager type, macro thread commands, event seeding, and any nondeterministic output ordering before accepting the fix.
