# Latest Handoff

## Session

- **UTC:** 2026-07-21T10:00Z
- **Task:** `AUD-G4-001`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Status:** PARTIAL — static RNG ownership and complete requested/effective thread provenance corrections are pushed; compilation and runtime validation remain mandatory.

## Area reviewed

Single-stave Geant4 optical simulation execution and provenance path:

- `geant4/single_stave/include/AppConfig.hh`
- `geant4/single_stave/src/AppConfig.cc`
- `geant4/single_stave/src/main.cc`
- `geant4/single_stave/src/RunAction.cc`
- recent merged PR #867 (`SetNtupleMerging(true)`)
- Geant4 MT design documentation and release notes

## Findings

### F1 — worker-level RNG reseeding

The code seeded CLHEP before constructing the run manager in `main.cc`, then reapplied the identical seed in every `RunAction::BeginOfRunAction`. Geant4 MT pre-generates event-associated seeds on the master. The worker reseed could interfere with that state and create correlated streams or thread-count-dependent results.

### F2 — thread count was an undeclared execution input

The executable exposed no `--threads` configuration and did not record the requested thread count in its metadata. Therefore the required 1-thread versus N-thread reproducibility experiment could depend on machine defaults or environment variables and could not be reconstructed solely from the command line plus metadata.

### F3 — requested threads were not necessarily effective threads

The first correction recorded only `threads_requested`. Geant4 documents `G4FORCENUMBEROFTHREADS` as an override that can force the worker count regardless of `SetNumberOfThreads`. Therefore metadata could still report four requested workers while the run actually used a different count. Geant4 11 exposes `G4RunManager::GetNumberOfThreads()` and `G4MTRunManager::GetNumberOfThreads()` for reading the configured effective value.

## Evidence classification

- **Repository facts:** duplicate seeding existed; the original CLI had no thread-count option; the first correction persisted only the requested count.
- **Official Geant4 design facts:** the master generates event-associated seeds before worker processing; worker count is configured before initialization; `G4FORCENUMBEROFTHREADS` can override programmatic thread requests; the run manager exposes the configured number of threads.
- **Inference requiring runtime confirmation:** previous optical-calibration outputs may differ after correcting seed ownership. No existing physics claim is declared invalid without rerunning it.

## Changes pushed

1. Removed `CLHEP::HepRandom::setTheSeed` from `RunAction::BeginOfRunAction`.
2. Kept the single master seed before run-manager construction.
3. Added `AppConfig::n_threads`, defaulting to one worker.
4. Added `--threads N` parsing, usage, validation (`N > 0`), and reporting.
5. Configure `G4MTRunManager` before `Initialize()`.
6. Added `n_threads_effective`, populated by reading the run manager after applying the request.
7. Capture `G4FORCENUMBEROFTHREADS` exactly when present.
8. Emit a startup warning when requested and effective counts differ.
9. Persist `threads_requested`, `threads_effective`, and `G4FORCENUMBEROFTHREADS` in the metadata sidecar and stdout configuration.
10. Preserved sequential-build compatibility through the base run-manager `GetNumberOfThreads()` interface and MT guards.

## New commits in this session

- `f1a64d0c4ac9bda5371907763cc73cd5bf75ad5f` — `fix(g4): distinguish requested and effective thread counts`
- `b1ac470c0d6f16d0201cd4ede00d99c33130abe8` — `fix(g4): record effective worker count after overrides`
- `7c7ae619ff2014ffcb5e5dcaf1991986ac27f8f7` — `fix(g4): expose effective thread provenance in run description`
- `fd4589e01fe20ac9273f10c2bd04f938ddce8ab9` — `fix(g4): persist effective worker and override provenance`

## Static validation performed

- Confirmed thread configuration and effective-count capture occur before actions are constructed, so every copied `AppConfig` receives the finalized provenance.
- Confirmed `GetNumberOfThreads()` is available on the Geant4 11 base run manager and overridden by the MT run manager.
- Confirmed sequential builds report an effective count through the base interface without referencing `G4MTRunManager` outside MT guards.
- Confirmed the override environment variable is read without altering it.
- Confirmed requested/effective mismatch is visible at startup and in metadata.
- Confirmed invalid zero or negative requests remain rejected.

## Validation not executed

This connector session did not provide a checked-out compiler environment, Geant4 11.2.2 runtime, ROOT files, or LUNARC data. It therefore does **not** claim:

- compilation success;
- runtime success;
- the exact behavior of the override in the repository's supported Geant4 build;
- identical event-keyed outputs for one and multiple threads;
- independence across different seeds;
- regenerated optical-photon yields or calibration results.

## Required runtime commands

Use a Geant4 11.2.2 environment and record compiler, ROOT, CLHEP, and build options:

```bash
cmake -S geant4/single_stave -B build/single_stave
cmake --build build/single_stave -j

unset G4FORCENUMBEROFTHREADS
build/single_stave/ccb_single_stave \
  --particle proton --energy 100 --nevents 1000 \
  --threads 1 --seed 20260721 --mode optical \
  --output mt_rng_t1.root

build/single_stave/ccb_single_stave \
  --particle proton --energy 100 --nevents 1000 \
  --threads 4 --seed 20260721 --mode optical \
  --output mt_rng_t4.root

G4FORCENUMBEROFTHREADS=2 \
build/single_stave/ccb_single_stave \
  --particle proton --energy 100 --nevents 1000 \
  --threads 4 --seed 20260721 --mode optical \
  --output mt_rng_requested4_forced2.root
```

The third run must report and persist `threads_requested=4`, `threads_effective=2`, and `G4FORCENUMBEROFTHREADS=2`. Also run at least four distinct seeds for an ensemble comparison.

## Required quantitative checks and plots

1. Metadata: requested/effective threads, override value, seed, event count, geometry hash, commit, and optical-table hashes must match the intended configuration.
2. Event IDs: exactly `0..N-1`, no duplicates or omissions, for every output.
3. Event-keyed deterministic comparison after sorting by event ID.
4. Distribution overlays and ratio panels for deposited energy, generated scintillation photons, arrivals, detected photons, and saturated PE.
5. Per-photon wavelength, arrival-time, and path-length comparisons.
6. Seed-ensemble means, variances, confidence intervals, and cross-seed correlations.
7. Regenerate the recent approximately 178 PE/event result and quantify any change with uncertainty.
8. Add a provenance table comparing requested, forced, effective, and observed worker settings for all validation runs.

## Acceptance decision

Keep PR #868 in draft. Do not merge until the supported build passes, the override-provenance test succeeds, and thread-count reproducibility, merged-row integrity, and optical-result regeneration criteria are satisfied.
