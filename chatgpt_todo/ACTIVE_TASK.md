# Active Task

## AUD-G4-001 — Multithreaded RNG seeding and ensemble audit

- **Status:** PARTIAL
- **Priority:** P0
- **Session:** 2026-07-21T13:00Z
- **Base commit:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Area:** `geant4/single_stave`

### Problem

The original code correctly seeded the master CLHEP engine before creating the Geant4 run manager, but then reset each thread-local engine in `RunAction::BeginOfRunAction`. This could interfere with Geant4's centrally assigned event seeds. The repository also lacked explicit requested/effective thread provenance and reproducible validators for event trees, photon trees, and multiseed ensembles.

### Implemented changes

- Removed worker/master reseeding from `BeginOfRunAction`.
- Added explicit requested, effective, and environment-forced thread provenance.
- Added event-keyed ROOT reproducibility validation with JSON/PDF output.
- Added exact canonical photon-multiset validation with JSON/PDF output.
- Added `scripts/analyze_single_stave_multiseed_rng.py` and synthetic tests.
- The multiseed validator checks comparable physics provenance, complete event IDs, unique seeds within each effective-thread group, exact duplicate streams across different seeds, event-indexed Pearson/Fisher-z correlations, robust seed-mean outliers, thread-group effects, seed coverage, and machine-readable/visual outputs.

### Acceptance criteria

- [x] No CLHEP reseeding occurs inside `BeginOfRunAction`.
- [x] Master engine is seeded before run-manager construction.
- [x] Requested/effective/forced thread provenance is represented in code and metadata.
- [x] Event-tree validator and synthetic tests are implemented.
- [x] Photon-tree validator and synthetic tests are implemented.
- [x] Multiseed ensemble validator and synthetic tests are implemented.
- [ ] Python test modules and lint pass in the repository environment.
- [ ] Build succeeds with supported Geant4 11.2.2.
- [ ] Same seed gives identical event-keyed and photon-multiset output for 1 and N effective threads.
- [ ] Forced-thread provenance is verified at runtime.
- [ ] At least four unique seeds per effective-thread group are generated.
- [ ] No exact duplicate stream occurs across different seeds.
- [ ] Cross-seed event-indexed correlations stay within preregistered Fisher-z threshold.
- [ ] Seed means show no unexplained robust outliers.
- [ ] Thread-group mean effects stay within preregistered threshold.
- [ ] Approximately 178 PE/event is regenerated with uncertainty and provenance.
- [ ] JSON and PDF validation artifacts are committed or published according to repository artifact policy.

### Required multiseed command

Create a JSON manifest containing each ROOT file, metadata sidecar, and stable label, then run:

```bash
python scripts/analyze_single_stave_multiseed_rng.py \
  --manifest configs/g4_multiseed_manifest.json \
  --output-json results/g4_multiseed_rng.json \
  --output-pdf docs/figures/g4_multiseed_rng.pdf \
  --minimum-seeds-per-thread 4 \
  --max-thread-effect-z 3 \
  --max-seed-outlier-z 4 \
  --max-cross-seed-correlation-z 4
```

Thresholds are diagnostics rather than universal proofs of independence. Any change must be preregistered and justified before looking at final ensemble results.

### Current blocker

This connector session can edit and push GitHub content but does not expose a checked-out Geant4/ROOT runtime or generated LUNARC outputs. Static implementation is committed; runtime acceptance remains open.
