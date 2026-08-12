# ADR-WAVE-B-LANE02: Explicit Geant4 neutron tracking-time cut (#1091)

**Status:** accepted (provenance pin; sensitivity claims BLOCKED)
**Date:** 2026-08-12
**Lane:** Wave B Lane 02
**Issues:** #1091

## Context

QGSP_BIC registers `G4NeutronTrackingCut` with a documented **10 µs** default
(Geant4 Physics List Guide). The single-stave executable previously inherited
that boundary silently and emitted contradictory run-metadata fields.

## Decision

1. Require `--neutron-timecut-policy-id` on every `ccb_stave_sim` invocation;
   unset policy aborts before event 0 (#1091 fail-closed).
2. Resolve the policy against `configs/transport/neutron_timecut_registry.json`
   via the in-binary mirror (`NeutronTimecutPolicy`).
3. After `Initialize()`, apply the Geant4 UI command
   `/physics_engine/neutron/timeLimit <value> microsecond` so the cut is
   explicit in transport, not merely named in metadata.
4. Run sidecars record `neutron_tracking_time_cut_configured=true`,
   `neutron_timecut_policy_id`, numeric `neutron_time_cut_us`, and policy
   status. Delayed-neutron negligibility claims remain **BLOCKED** per
   ADR-0013 until a registered sensitivity digest exists.

## Consequences

- Software provenance is honest; no invented cut values.
- Physics sensitivity for late neutrons remains BLOCKED.
- Does not auto-close #1091.
