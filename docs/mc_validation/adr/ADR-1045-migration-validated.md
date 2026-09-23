# ADR-1045: Trigger evidence_state MIGRATION_VALIDATED (MC-side migration only)

**Status:** accepted (2026-08-17)
**Issue:** #1045 (`ARU-TRIGGER-MIMIC-001`)
**Supersedes:** [ADR-0002](../ADR-0002-trigger-hardware-proxy-blocked.md) decision item 2, in part (evidence_state / hardware_definition_status only)
**Contract:** `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json` (schema 1.1.0)

## Context

ADR-0002 blocked the trigger-hardware atom because the real T1/T2 trigger
scintillators were absent from MC geometry and no source-bound electronics
model existed. #1045 phases 1B–4 delivered the missing MC-side evidence on the
authorising corrected-source chain (CL-021 satisfied: the 1M v3 run reproduces
the authorising two-arm sample exactly, 554/1M — a geometry-only delta):

- **Phase 2 (v3 geometry)**: the REAL baseline trigger counters
  (`Trig_stack_1` B arm −38.0° / `Trig_stack_2` A arm +71.5°, r = 99 cm)
  instrumented by splitting the shared `Trig_bar` into
  `T1_trigger_log`/`T2_trigger_log` with dedicated SD branches — zero invented
  geometry (receipt `research/trigger_migration_study/phase2_geometry_receipt.json`,
  v3 sha256 `657661c8…`, 8/8 builder gates). Earlier v1 (unrotated slabs,
  grazing incidence) and v2 (r = 30 cm, sign-flipped antipodal placement, 0/554)
  attempts are RETRACTED with root causes recorded in the receipt.
- **Phase 3 (scan)**: hardware pass count nearly flat in threshold 0.5–5 MeV
  (361 → 355 @ 15 ns window, reference 360 @ 1.0 MeV); two-arm proxy count
  rises with coincidence window (386 @ 5 ns → 554 @ 15 ns → 557 @ 30 ns).
- **Phase 4 (corrected per-event joint matrix)**: at 1.0 MeV / 15 ns —
  both = 165, proxy-only = 389, hardware-only = 195, proxy total = 554;
  two-arm retention 0.2978 ± 0.0194, consistent with the independent
  ray-projection prediction 0.289, and threshold-insensitive (0.2978 @ 0.5 MeV
  → 0.2942 @ 5 MeV) — the migration loss is geometric. The hardware sample is
  NOT a subset of the proxy sample. Supersedes the aggregate-join matrix
  (256/298/0), which assumed a false subset relation; see
  `research/trigger_migration_study/phase4/JOINT_MATRIX_CORRECTION.md`.

## Decision

1. `evidence_state` moves `BLOCKED` → **`MIGRATION_VALIDATED`** and
   `hardware_definition_status` → **`GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED`**.
2. The new label **`MC_TRIGGER_MIGRATION`** authorizes MC-side migration
   statements only (evidence class `MC_METHOD_CLOSURE`; registered as
   `paper/figures.yaml` TRIG-MIGRATION / TRIG-SCAN). These quantify the
   proxy → instrumented-hardware-response migration on the authorising MC and
   validate no real trigger.
3. ADR-0002 items 1, 3, 4 REMAIN IN FORCE: real-data hardware-trigger claims
   stay forbidden; production Sample I/II membership keeps the
   `MC_TRIGGER_PROXY` classifier; no future `sample_membership_hardware_model`
   channel is overwritten by the proxy.
4. Electronics (discriminator threshold provenance, pulse shapes, dead time,
   multiplicity logic) remain unbound; the 0.5–5 MeV scan thresholds are
   study parameters, not source-bound hardware settings.

## Consequences

- Paper figures/tables may state the quantified proxy → hardware-response
  migration on the authorising MC, labelled as MC migration (not beam data).
- The validator (`tools/audit/validate_trigger_hardware_schema.py`) now pins
  the study block: artifacts must exist and headline numbers must reproduce
  from the committed report.
- Closure of the REAL trigger atom still requires the ADR-0002 closure list:
  source-bound electronics schema; held-out real-trigger acceptance closure
  with preregistered tolerance; energy/angle/multiplicity migration axes
  (species dimension delivered).

## Rejection criteria (unchanged from ADR-0002)

Scanning `coinc_ns` alone does not close the real-trigger atom. Invented
thresholds/materials without hardware provenance are rejected.
