# Active Task

## AUD-G4-001 — Multithreaded RNG seeding audit

- **Status:** PARTIAL
- **Priority:** P0
- **Session:** 2026-07-21T08:00Z
- **Base commit:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **Area:** `geant4/single_stave`

### Problem

`main.cc` seeds the master CLHEP engine before constructing the Geant4 run manager, which is the correct point for MT event-seed generation. `RunAction::BeginOfRunAction` then reset every thread-local engine to the same configured seed. This can interfere with Geant4's centrally assigned per-event seeds, introduce correlated worker streams, and make results depend on thread scheduling.

### Current change

- Removed the worker/master reseed from `RunAction::BeginOfRunAction`.
- Documented the required master-before-run-manager seed placement in `main.cc`.

### Acceptance criteria

- [x] No CLHEP reseeding occurs inside `BeginOfRunAction`.
- [x] Master engine is seeded before run-manager construction.
- [ ] Build succeeds with the repository's supported Geant4 version.
- [ ] Same seed gives identical event-keyed output for 1 and N threads after sorting by event ID.
- [ ] Different seeds produce statistically independent output.
- [ ] Event IDs are unique and complete in merged ROOT output.
- [ ] Validation plots and quantitative comparison are committed.

### Required validation commands

Adapt executable/configuration names to the repository build instructions:

```bash
cmake -S geant4/single_stave -B build/single_stave
cmake --build build/single_stave -j

# Run the same seed with one and multiple threads.
# Capture exact commands and environment in HANDOFF.md.

python scripts/compare_single_stave_mt_reproducibility.py \
  --single-thread one.root --multi-thread many.root \
  --output docs/figures/g4_mt_rng_reproducibility.png
```

The comparison script/plot remains a follow-up task because this connector session cannot execute the Geant4 build or access generated ROOT outputs.
