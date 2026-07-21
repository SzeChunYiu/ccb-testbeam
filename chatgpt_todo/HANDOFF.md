# Latest Handoff

## Session

- **UTC:** 2026-07-21T11:00Z
- **Task:** `AUD-G4-001`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Status:** PARTIAL — static RNG/thread-provenance fixes and a reproducible ROOT comparison tool are pushed; compilation and real Geant4 output validation remain mandatory.

## Area reviewed

Single-stave Geant4 optical simulation execution, provenance, and validation path:

- `geant4/single_stave/include/AppConfig.hh`
- `geant4/single_stave/src/AppConfig.cc`
- `geant4/single_stave/src/main.cc`
- `geant4/single_stave/src/RunAction.cc`
- `scripts/compare_single_stave_mt_reproducibility.py`
- `tests/test_compare_single_stave_mt_reproducibility.py`
- merged PR #867 (`SetNtupleMerging(true)`)
- Geant4 MT design and thread-control documentation

## Findings

### F1 — worker-level RNG reseeding

The code seeded CLHEP before constructing the run manager in `main.cc`, then reapplied the identical seed in every `RunAction::BeginOfRunAction`. Geant4 MT pre-generates event-associated seeds on the master. The worker reseed could interfere with that state and create correlated streams or thread-count-dependent results.

### F2 — thread count was an undeclared execution input

The executable exposed no `--threads` configuration and did not record the requested thread count in metadata. A one-thread versus N-thread reproducibility experiment could therefore depend on hidden machine defaults or environment variables.

### F3 — requested threads were not necessarily effective threads

Recording only `threads_requested` was insufficient because `G4FORCENUMBEROFTHREADS` can override `SetNumberOfThreads`. Provenance could otherwise claim four workers while the run manager configured another count.

### F4 — the required quantitative validator did not exist

The handoff referenced `scripts/compare_single_stave_mt_reproducibility.py`, but no such script existed. Without a version-controlled validator, event ordering, branch schemas, duplicate or missing event IDs, metadata mismatches, numerical differences, and requested visual evidence would have been checked manually and inconsistently.

## Evidence classification

- **Repository facts:** duplicate seeding existed; thread count was initially undeclared; effective thread count and override were initially absent; the required comparison script was absent.
- **Official Geant4 design facts:** the master generates event-associated seeds; worker count is configured before initialization; `G4FORCENUMBEROFTHREADS` can override the programmatic request; the run manager exposes its configured thread count.
- **Static implementation evidence:** the new validator sorts by event ID, requires complete/unique IDs, compares branch schemas and all common branches, separates thread provenance from physics provenance, writes JSON, and generates diagnostic PDF pages.
- **Inference requiring runtime confirmation:** previous optical-calibration outputs may change after correcting RNG ownership. No physics claim is declared invalid until rerun.

## Changes pushed

1. Removed `CLHEP::HepRandom::setTheSeed` from `RunAction::BeginOfRunAction`.
2. Kept master seeding before run-manager construction.
3. Added validated `--threads N`, defaulting to one.
4. Configured `G4MTRunManager` before `Initialize()`.
5. Added requested, effective, and environment-forced thread provenance.
6. Added mismatch warnings and metadata persistence.
7. Added `scripts/compare_single_stave_mt_reproducibility.py`.
8. The validator:
   - loads two ROOT `events` trees through uproot;
   - validates integer event IDs are exactly `0..N-1`, complete, and unique;
   - sorts rows by event ID before comparison;
   - requires matching branch schemas;
   - compares numeric branches with configurable `rtol`/`atol` and nonnumeric branches exactly;
   - requires matching physics provenance, including optical-table hashes;
   - reports thread provenance without requiring it to match;
   - writes a machine-readable JSON result;
   - creates a PDF summary, distributions, ratio panels, and event-keyed difference plots;
   - exits nonzero on failed acceptance criteria.
9. Added synthetic ROOT regression tests covering reordered-identical events, string branches, duplicate/missing IDs, and a numeric mismatch.

## Commits added in this session

- `1067d6a28e3c5ee95e52dc5f63b8d3c9b4f78e99` — `feat(g4): add MT ROOT reproducibility validator`
- `ea30cc30313d45a122a6ddc31215b342ec42c3c8` — `fix(g4): make MT validator type-safe`
- `fc801dfe7fb8aec0dc3f0068baf39a08199975af` — `test(g4): cover MT ROOT reproducibility validator`

## Static validation performed

- Reviewed the complete comparison logic and corrected `equal_nan=True` handling so string branches such as `particle` are compared safely.
- Confirmed event rows are aligned by stable sort on `event`, not file row order.
- Confirmed the metadata gate requires geometry, seed, particle, energy, event count, physics settings, and optical-table provenance to match.
- Confirmed requested/effective/forced thread values are reported but may differ by design.
- Confirmed failed structural or numerical checks return exit code 1.
- Confirmed synthetic tests exercise both pass and fail paths and create nonempty PDF output when run in the repository development environment.

## Validation not executed

The execution environment could not clone GitHub directly and did not expose a checked-out Geant4 11.2.2/ROOT build or generated ROOT files. Therefore this session does **not** claim:

- Python tests passed;
- lint passed;
- Geant4 compilation succeeded;
- the simulation ran successfully;
- one-thread and multithread event histories match;
- merged event/photon rows are complete;
- distinct seeds are independent;
- the approximately 178 PE/event result was reproduced.

## Required runtime commands

Use the supported Geant4 11.2.2 environment and record compiler, ROOT, CLHEP, CMake options, commit, optical-table hashes, and environment variables:

```bash
python -m pytest tests/test_compare_single_stave_mt_reproducibility.py -q
ruff check scripts/compare_single_stave_mt_reproducibility.py \
  tests/test_compare_single_stave_mt_reproducibility.py

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

python scripts/compare_single_stave_mt_reproducibility.py \
  --reference mt_rng_t1.root \
  --candidate mt_rng_t4.root \
  --reference-meta mt_rng_t1.root.meta.json \
  --candidate-meta mt_rng_t4.root.meta.json \
  --output-json results/g4_mt_rng_t1_vs_t4.json \
  --output-pdf docs/figures/g4_mt_rng_t1_vs_t4.pdf

G4FORCENUMBEROFTHREADS=2 \
build/single_stave/ccb_single_stave \
  --particle proton --energy 100 --nevents 1000 \
  --threads 4 --seed 20260721 --mode optical \
  --output mt_rng_requested4_forced2.root
```

The override run must report and persist `threads_requested=4`, `threads_effective=2`, and `G4FORCENUMBEROFTHREADS=2`.

## Required remaining checks and plots

1. Run the new validator with exact tolerance first (`rtol=0`, `atol=0`). Any relaxation must be scientifically justified and recorded.
2. Validate the `photons` tree separately: row count, event foreign keys, sensor values, wavelength, arrival time, path length, and detection flag.
3. Run at least four distinct seeds and add an ensemble-level independence and uncertainty analysis.
4. Regenerate the approximately 178 PE/event result and quantify any change with uncertainty.
5. Produce a requested/forced/effective thread-provenance table for every validation run.
6. Commit the JSON summaries, reasonably sized PDFs, commands, and interpretation when repository artifact policy permits.

## Acceptance decision

Keep PR #868 in draft. Do not merge until the Python tests and lint pass, the supported Geant4 build succeeds, override provenance is confirmed, event and photon integrity pass, one-versus-many-thread reproducibility is quantified, and the optical result is regenerated.