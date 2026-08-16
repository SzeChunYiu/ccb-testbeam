# Phase 1B: Baseline Rebuild on an Authorising MC — REQUIRED

**Issue**: #1045 (P0)
**Date**: 2026-08-16 (re-scoped 2026-08-16)
**Status**: REQUIRED — Phase 1 baseline rests on a NONAUTHORISING MC
**Supersedes**: the earlier `PHASE1B_TRUNCATED_DATA_NOTICE.md`, whose
diagnosis (ccb_data 128-word truncation biasing Phase 1) was wrong.

## Corrected diagnosis

`scripts/trigger_baseline_characterization.py` reads **only MC truth
branches** (primary PDG, kinematics, Sci_bar truth hits) from
`output_krakow_1M.root`. The Geant4 MC never consumes the ccb_data staged
waveforms, so the #952 128-word truncation **could not have biased the
Phase 1 numbers**. A "re-run on corrected staging" would be incoherent:
the data staging is not an input to this MC.

The real defect is **MC provenance**: per `geant4/REPRODUCTION_STATUS.md`,
`output_krakow_1M.root` (2026-07-09) is a product of the **superseded
uniform-source generator** and is **NONAUTHORISING** — legacy products "may
be inspected as historical truth-level diagnostics" but "must not be used to
claim validated proton/deuteron PID, stopping-depth performance, penetration
closure, energy calibration, detector efficiency, or DATA↔MC agreement".

## Impact

- ε_HRD[deuteron] = 45.6% and ε_HRD[proton] = 0.4% are **HISTORICAL
  DIAGNOSTICS** of that specific non-authorising MC. They are retained as a
  schema/pipeline shakedown, not as baseline measurements.
- Any migration matrix M = ε_truth / ε_HRD built on this denominator is
  non-authorising by construction. Phase 3/4 must not consume it as if it
  were a validated baseline.
- The deuteron-fraction observation (Sample I 99.3% deuteron) is likewise
  conditional on the historical generator.

## Required action: Phase 1B (re-scoped)

Rebuild the baseline on an **authorising corrected-source MC** — the CL-021
chain, not a data-staging re-run:

1. **Pinned corrected-source build**: extend `geant4/setup_and_run.sh` to
   (a) clone/verify a pinned `HIBEAM-NNBAR/hibeam_g4` commit (prove
   commit/tree, fail closed on drift), and (b) install
   `geant4/src_patch/ScatteringGenerator.{hh,cc}` — the current harness does
   NOT install the src_patch, which is exactly why the June build produced a
   superseded-source MC.
2. **Authorising run**: 1,000,000 events, provenance bound to one immutable
   manifest (compiler/build/run-manager/thread/seed/event-count), per the
   7-item authorising contract in `geant4/REPRODUCTION_STATUS.md`.
3. **Re-run** `scripts/trigger_baseline_characterization.py` on the new MC
   and diff ε_HRD vs the historical values; the delta is the source-model
   systematic, quoted alongside every downstream migration number.

## Blocking

- CL-021 (cross-section support / sampled source uncertainty) remains gated;
  #1058 (dedx parser origin) and #1178/#1179 stay open per the contract.
- Phase 3 must not start on the historical denominator; Phase 2 execution
  (geometry + sensitive detectors) is independent and may proceed in
  parallel — its output is reusable against the corrected MC.

## Updated phase sequence

| Phase | Name | Status |
|-------|------|--------|
| 1 | Baseline HRD Proxy Characterization | ⚠️ COMPLETE as historical diagnostic (non-authorising MC) |
| 1B | Baseline on Authorising Corrected-Source MC | 🔥 **REQUIRED** (CL-021 chain) |
| 2 | Truth-Trigger Volume Addition | Implementation complete (parallel-safe) |
| 3 | Threshold/Coincidence SCAN | Blocked on 1B for the denominator |
| 4 | Migration Matrix Analysis | Awaiting 3 |
| 5 | MC Regeneration (conditional) | Awaiting 4 |
| 6 | Contract Bump | Awaiting 5 |

---
**Created**: 2026-08-16 · **Re-scoped**: 2026-08-16
**Issue**: #1045 (P0)
**Severity**: P0 — no authorising migration matrix until the denominator is an authorising MC
