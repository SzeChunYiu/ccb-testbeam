# Phase 2 Status — Truth-Trigger Volume Addition

**Date**: 2026-08-16
**Status**: IMPLEMENTATION COMPLETE — AWAITING LUNARC EXECUTION

## Completed

1. **GDML Patch Script**: `scripts/trigger_phase2/patch_gdml_trigger_volumes.py`
   - Adds T1 (A-arm) and T2 (B-arm) trigger volumes to GDML
   - Uses existing PSci material
   - Proper positioning and rotation for each arm

2. **Trigger Sensitive Detector**: C++ class for recording trigger response
   - `TriggerSensitiveDetector.hh` — Header file
   - `TriggerSensitiveDetector.cc` — Implementation
   - Records EDep, earliest time, and hit count per event

3. **Documentation**:
   - `patch_detector_construction.md` — Instructions for modifying detector construction
   - `PLAN.md` — Full implementation plan
   - `STATUS.md` — This file

4. **Test Script**: `test_phase2_simulation.sh`
   - Patches GDML
   - Copies files
   - Recompiles
   - Submits 50k event test simulation

## Blocking

Phase 2 requires LUNARC execution of `test_phase2_simulation.sh`:
- Patch the GDML file (requires write access to shared directory)
- Recompile HIBEAM simulation (requires build environment)
- Run 50k event simulation (requires Geant4 runtime)

## Geometry Specifications Confirmed

| Parameter | T1 (A-arm) | T2 (B-arm) |
|-----------|------------|------------|
| Material | PSci (polystyrene) | PSci (polystyrene) |
| Size (cm) | 10×10×1 (L×W×T) | 15×15×1 (L×W×T) |
| Angle | 71.5° from beam | -38° from beam |
| Position | ~30 cm upstream of HRD | ~30 cm upstream of HRD |
| Purpose | A-arm trigger for Sample I | B-arm trigger for Sample II |

## Decision: Option A — Direct GDML Modification

Chose Option A (modify base GDML directly) because:
- Fastest approach (6-8h vs 8-16h for other options)
- GDML file is accessible and well-structured
- Geometry is shared among all users anyway
- Minimal impact on existing code

## Next Steps

1. Execute `test_phase2_simulation.sh` on LUNARC
2. Verify T1/T2 volumes appear in geometry
3. Verify sensitive detectors register successfully
4. Analyze 50k event output for trigger response
5. Proceed to Phase 3 (Threshold/Coincidence SCAN)

## Commit

- Commit hash: `a223b807`
- Branch: `fix/1045-trigger-migration`
- Files: 6 added, 502 insertions

---
**Issue**: #1045 (P0)
**Phase**: 2/6
**Created**: 2026-08-16

---

## v3 Geometry — AUTHORITATIVE (2026-08-17)

**v2 RETRACTED**: the rotated r=30 slab design gave two-arm & T1&T2 = **0/554** on 1M
(job 3506988). Root cause: sign-flipped antipodal placement — `t_pos = -30*u_arm`
placed both counters on the opposite side of the target from both arms.

**v3 design**: the baseline geometry ALREADY contains the real T1/T2 counters as
passive `Trig_stack_1/2` volumes (PSci bars, r=99 cm, on the B/A arm axes). v3
instruments them — split shared `Trig_bar` into `T1_trigger_log` (stack_1, B arm,
−38.0°) / `T2_trigger_log` (stack_2, A arm, +71.5°); zero invented geometry.
Builder: `scripts/trigger_phase2/make_t1t2_v3.py` (8/8 gates PASS).
Geometry sha256 `657661c8…` → `phase2_geometry_receipt.json`.

**Validation chain**:
- 10k (job 3507011): 96 branches / 36 T1/T2 branches; T1∧T2=4, all annihilations;
  hits at r=99 on the arm axes.
- 1M (job 3507013): two-arm = **554 exactly** (geometry-only change proven);
  T1∧T2@0.5 MeV = 361; two-arm & T1∧T2 = **165/554 = 0.2978** vs independent
  ray-projection prediction 0.289.

**Phase 3/4 on v3 1M** (jobs 3507014/3507018): threshold scan flat (361→355 over
0.5–5 MeV); **Phase 4 corrected via per-event joint matrix** — the aggregate
matrix's "both=256 / hardware_only=0" was an artifact of joining two scans by
aggregate arithmetic (see `phase4/JOINT_MATRIX_CORRECTION.md`). Corrected:
**both=165, proxy_only=389, hardware_only=195; retention 29.8%**, threshold-
insensitive, A-arm counter geometric bottleneck. Hardware sample ⊄ proxy sample
(54% of hardware triggers lie outside the two-arm definition).
