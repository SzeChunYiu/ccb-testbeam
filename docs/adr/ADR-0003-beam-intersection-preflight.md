# ADR-0003: Geometry-aware beam / primary intersection preflight

**Status:** accepted  
**Date:** 2026-08-11  
**Lane:** Wave A Lane 03  
**Issues:** #999 (depends on registry in ADR-0002 / #986/#991/#992)

## Context

`AppConfig::ParseArgs()` accepted any finite `hit_x`, `hit_y`, `theta`, `phi`.
Primaries can be launched that never enter the scintillator (θ≥90°, hit outside
the face, large tilt that exits before entry). Empty results can be misread as
detector inefficiency or response systematics.

## Decision

1. After geometry extents are known, run an analytical AABB ray intersection
   of the configured primary against the scintillator box.
2. **Python:** `ccb_mc_validation.geometry.beam_intersection` loads extents from
   the **selected** geometry profile (same registry as ADR-0002) — no duplicate
   hard-coded limits in AppConfig.
3. **C++ single-stave:** preflight in `main` uses `DetectorConstruction`
   half-extents (the executable geometry source), not a second copy in
   `AppConfig`.
4. Default mode `calibration` requires intersection with the intended **-z**
   entry face and θ < 90°.
5. Intentional miss studies must set `allow_miss` / `--allow-miss`.
6. Predicted entry/exit and path length are returned for run metadata.

## Consequences

- Calibration/systematic campaigns fail closed on miss geometries.
- Extents always come from the approved geometry source for that path
  (profile registry or DetectorConstruction).

## Tests

- Central normal incidence → pass
- Hit just inside / outside x,y edge
- θ = 89°, 90°, 91°
- Large-angle trajectory that misses the box
- `allow_miss=True` accepts an intentional miss
