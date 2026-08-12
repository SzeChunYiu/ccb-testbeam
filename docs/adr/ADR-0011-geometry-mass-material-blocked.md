# ADR-0011: Mass-geometry material tables remain BLOCKED from geometry digest

**Status:** accepted (BLOCKED scope)  
**Date:** 2026-08-12  
**Lane:** LUNARC campaign lane 03  
**Issues:** #986

## Context

GEOMETRY_DIGEST_V2 (#986) now canonicalizes named mass-geometry extents
(coating/sensor thickness, fibre radii, `far_end_mode`) and excludes Birks and
optical response knobs from `geometry_hash`.

The Geant4 solids still depend on full material property tables (refractive
index curves, absorption lengths, Birks host coupling). Those tables are not
fully serialized into the geometry digest namespace.

## Decision

1. `geometry_hash` remains authoritative for **solid extents and placement
   identity** only (see `docs/contracts/GEOMETRY_DIGEST_V2.json`).
2. Material **density tables and wavelength-dependent optical properties** are
   **BLOCKED** from the geometry digest until a separate optical/material table
   digest contract is accepted (#978–#980 family).
3. Run metadata must record `physics_hash` and `optical_hash` alongside
   `geometry_hash`; consumers must not treat geometry digest alone as complete
   mass+optical provenance.
4. When geometry-changing fields are unknown to the digest serializer, fail
   closed (raise / abort) rather than emit a partial digest.

## Consequences

- Same `geometry_hash` with different optical-table SHA256s is expected and
  must partition caches by `optical_hash` + table hashes.
- Closing #986 for digest canonicalization does not claim closure of optical
  table provenance.
