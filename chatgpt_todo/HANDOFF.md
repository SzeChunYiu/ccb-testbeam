# Latest Handoff

## Session

- **UTC:** 2026-07-21T09:00Z
- **Task:** `AUD-G4-001`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Status:** PARTIAL — static seeding and thread-configuration corrections are pushed; compilation and runtime validation remain mandatory.

## Area reviewed

Single-stave Geant4 optical simulation execution and provenance path:

- `geant4/single_stave/include/AppConfig.hh`
- `geant4/single_stave/src/AppConfig.cc`
- `geant4/single_stave/src/main.cc`
- `geant4/single_stave/src/RunAction.cc`
- recent merged PR #867 (`SetNtupleMerging(true)`)

## Findings

### F1 — worker-level RNG reseeding

The code seeded CLHEP before constructing the run manager in `main.cc`, then reapplied the identical seed in every `RunAction::BeginOfRunAction`. Geant4 MT pre-generates event-associated seeds on the master. The worker reseed could interfere with that state and create correlated streams or thread-count-dependent results.

### F2 — thread count was an undeclared execution input

The executable exposed no `--threads` configuration and did not record the requested thread count in its metadata. Therefore the required 1-thread versus N-thread reproducibility experiment could depend on machine defaults or environment variables and could not be reconstructed solely from the command line plus metadata.

### Evidence classification

- **Repository facts:** duplicate seeding existed; the CLI had no thread-count option; metadata did not record thread count.
- **Official Geant4 design facts:** the master generates event-associated seeds before worker processing; worker count is configured on the MT run manager before initialization.
- **Inference requiring runtime confirmation:** previous optical-calibration outputs may differ after correcting seed ownership. No existing physics claim is declared invalid without rerunning it.

## Changes pushed

1. Removed `CLHEP::HepRandom::setTheSeed` from `RunAction::BeginOfRunAction`.
2. Kept the single master seed before run-manager construction.
3. Added `AppConfig::n_threads`, defaulting to one worker for a conservative reproducible default.
4. Added `--threads N` parsing, usage text, validation (`N > 0`), and `Describe()` output.
5. In MT builds, dynamically obtain `G4MTRunManager` and call `SetNumberOfThreads(cfg.n_threads)` before `Initialize()`.
6. Added `threads_requested` to the metadata sidecar.
7. Updated the repository-local audit handoff.

## New commits in this session

- `c1f1fb3239afa7de2926a641952fae0c4f25d932` — `feat(g4): make worker thread count explicit in run config`
- `2b34468ca75a04bf626b831239f839198403f1dd` — `feat(g4): parse and report explicit worker thread count`
- `05b7ad7988534fcbdbb052e5c9d2708c049e5ad4` — `feat(g4): configure MT workers before initialization`
- `7572b1413a1f6c8e24a1a1b40d26850c5b9391b6` — `feat(g4): record requested thread count in run metadata`

## Static validation performed

- Confirmed the new thread setting occurs after run-manager construction but before `Initialize()`, when worker creation is configured.
- Confirmed sequential builds remain guarded by `#ifdef G4MULTITHREADED` and do not require `G4MTRunManager`.
- Confirmed invalid zero or negative thread counts are rejected during argument parsing.
- Confirmed the declared thread count is included in stdout configuration and metadata provenance.

## Validation not executed

This connector session did not provide a checked-out compiler environment, Geant4 11.2.2 runtime, ROOT files, or LUNARC data. It therefore does **not** claim:

- compilation success;
- runtime success;
- actual worker count equal to the requested count under all environments (for example, `G4FORCENUMBEROFTHREADS` can override it);
- identical event-keyed outputs for one and multiple threads;
- independence across different seeds;
- regenerated optical-photon yields or calibration results.

## Required runtime commands

Use a Geant4 11.2.2 environment and record compiler, ROOT, CLHEP, and build options:

```bash
cmake -S geant4/single_stave -B build/single_stave
cmake --build build/single_stave -j

build/single_stave/ccb_single_stave \
  --particle proton --energy 100 --nevents 1000 \
  --threads 1 --seed 20260721 --mode optical \
  --output mt_rng_t1.root

build/single_stave/ccb_single_stave \
  --particle proton --energy 100 --nevents 1000 \
  --threads 4 --seed 20260721 --mode optical \
  --output mt_rng_t4.root
```

Also run at least four distinct seeds for an ensemble comparison. Explicitly unset or record `G4FORCENUMBEROFTHREADS`.

## Required quantitative checks and plots

1. Metadata: `threads_requested`, seed, event count, geometry hash, commit, and optical-table hashes must match the intended configuration.
2. Event IDs: exactly `0..N-1`, no duplicates or omissions, for both outputs.
3. Event-keyed deterministic comparison after sorting by event ID.
4. Distribution overlays and ratio panels for deposited energy, generated scintillation photons, arrivals, detected photons, and saturated PE.
5. Per-photon wavelength, arrival-time, and path-length comparisons.
6. Seed-ensemble means, variances, confidence intervals, and cross-seed correlations.
7. Regenerate the recent approximately 178 PE/event result and quantify any change with uncertainty.

## Acceptance decision

Keep PR #868 in draft. Do not merge until the supported build passes and the thread-count reproducibility, merged-row integrity, and optical-result regeneration criteria are satisfied. If environment override variables change the actual worker count, add an explicit actual-thread-count field or startup assertion before declaring the provenance contract complete.
