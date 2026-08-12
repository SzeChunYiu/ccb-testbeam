# ADR-0005: Split geometry / physics / optical config digests

**Status:** accepted  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 08  
**Issues:** #986

## Context

`DetectorConstruction` previously hashed a flat concatenation that (a) omitted
`kCoatingThk`, `kSensorThk`, and `far_end_mode`, and (b) mixed Birks / optical
knobs into the "geometry" digest.

## Decision

Emit three versioned digests:

1. `geometry_hash` / `ccb-geometry-config/1` — mass geometry extents, coating
   and sensor thickness, fibre radii, `far_end_mode`, material identity labels.
2. `physics_hash` / `ccb-physics-config/1` — Birks `kB` (mm/MeV).
3. `optical_hash` / `ccb-optical-config/1` — optical interface model, WLS/Y11
   yield knobs, TiO2 finish parameters, attenuation form, strict-optical flag.

Serialization uses named fields, scientific float formatting, and an explicit
schema version prefix.

## Consequences

- Changing only Birks no longer mutates the geometry digest.
- Changing `far_end_mode` / coating / sensor thickness mutates geometry.
- Digitizer digest remains owned by #977 and is out of scope here.
