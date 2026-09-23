# ADR-0002: Hardware-trigger response remains BLOCKED (no invented trigger)

**Status:** accepted (fail-closed); decision item 2 superseded IN PART on 2026-08-17 by [ADR-1045](adr/ADR-1045-migration-validated.md) — `evidence_state` → `MIGRATION_VALIDATED` (MC-side migration study only), `hardware_definition_status` → `GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED`. Items 1, 3, 4 remain fully in force: no invented hardware parameters, `MC_TRIGGER_PROXY` labelling for production Sample I/II membership, and no overwrite of a future `sample_membership_hardware_model` channel. Real-data hardware-trigger claims remain forbidden.  
**Date:** 2026-08-11  
**Issue:** #1045 (`ARU-TRIGGER-MIMIC-001`)  
**Contract:** `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json`

## Context

Sample I / Sample II are defined by real CCB hardware-trigger run populations.
The repository currently classifies MC events with an HRD first-stack-layer
charged-hit proxy (`ENTER A/B` + coincidence window). The real trigger
scintillators are not in the MC geometry, and no source-bound
threshold/discriminator/coincidence electronics model exists.

## Decision

1. **Do not invent** hardware trigger geometry, material, thresholds, or
   discriminator timing parameters to force a “hardware” claim.
2. Until a source-bound model or held-out proxy closure exists, the trigger
   response atom remains **`BLOCKED`** with
   `hardware_definition_status = UNKNOWN_EXTERNAL`.
3. All quantitative outputs that use the current first-layer coincidence MUST
   be labelled **`MC_TRIGGER_PROXY`** / **`DIAGNOSTIC_ONLY`**. Statements such
   as “hardware-trigger reproduction” or unqualified “confirmed against real
   data” via this proxy are forbidden.
4. The existing HRD-first-layer classifier remains available as a **diagnostic
   proxy** only; it must not overwrite a future
   `sample_membership_hardware_model` channel.

## Consequences

- Positive: prevents false closure of DATA↔MC Sample I/II claims (#618/#956).
- Negative: Sample-mixture / p/d fraction claims that need the real trigger stay
  blocked until geometry/electronics evidence lands (#844/#962) or a
  preregistered proxy-validation study closes the migration matrix.

## Rejection criteria

Scanning only `coinc_ns` around the first-HRD-layer proxy does **not** close
this ADR. Invented thresholds/materials without hardware provenance are
rejected.

## Governance note (#1218)

Scientific PRs that touch this atom must use non-closing references (`Refs`)
unless a ledgered completion/successor-transfer intent is validated. Merging
implementation leaves does not auto-complete the research universe.
