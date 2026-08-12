# ADR-986: Separated canonical config digests

## Status

**ACCEPTED for geometry/physics split; optical/digitizer digests available**

## Context

The previous geometry hash concatenated unlabeled floats, omitted geometry-
changing fields (`far_end_mode`, coating/sensor thickness), and included Birks.

## Decision

1. `geometry_config_sha256`: named fields + units + schema version; includes
   coating/sensor/far_end; excludes Birks.
2. `physics_config_sha256`: Birks, production cut, optical interface model.
3. Python mirrors the contract in
   `ccb_mc_validation.provenance.canonical_config_digests`.
4. Run metadata writes both digests. Optical table digests remain per-table in
   the sidecar; a rolled-up optical digest helper exists for consumers (#977
   digitizer digest is produced by the digitizer pipeline).

## Consequences

Geometry-identical / physics-different runs no longer collide on geometry
identity. Schema-version bumps deliberately change the digest namespace.
