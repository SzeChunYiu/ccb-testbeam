# ADR-0010: Separate geometry_hash and physics_hash

**Status:** accepted  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 05  
**Issues:** #986

## Context

The single-stave `geometry_hash` mixed Birks `kB` into a geometry digest and
omitted geometry-changing fields (`kCoatingThk`, `kSensorThk`, `far_end_mode`).

## Decision

1. `geometry_hash` schema `geometry_v2`: named fields + units for stave/fibre/
   coating/sensor extents and `far_end_mode` — **no Birks**.
2. `physics_hash` schema `physics_v1`: `birks_kB_mm_per_MeV` +
   `optical_interface_model`.
3. Run metadata records both digests.
4. Full optical-table / digitizer digests remain owned by related provenance
   issues; this ADR closes the overloaded geometry digest defect.

## Consequences

- Changing only Birks changes `physics_hash`, not `geometry_hash`.
- Changing far-end mode or coating thickness changes `geometry_hash`.
