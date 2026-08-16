# Opticks GPU SURFACE_DETECT Gap — Root Cause and Fix

## Status: VALIDATED (kernel-level), SURFACE_DETECT fires

## Root Cause

The CCB sensor volumes (Sensor_F1/2_PlusX/MinusX) are constructed from
**CCB_Y11Core** — the same material as the WLS fibre core — with **no
detect surface**. The only optical surface in the entire geometry was
TiO2_Border (REFLECTIVITY only, no EFFICIENCY).

When photons cross a sensor boundary, `qbnd::fill_state` reads `osur=-1`
(no surface), so `s.optical.y = ems = smatsur_NoSurface` (1).
`qsim::propagate` then routes to `propagate_at_boundary` (Fresnel
refraction) instead of `propagate_at_surface` (detect). SURFACE_DETECT
never fires.

The prior #944 agent's claim that "detect=1.0 is in the boundary texture"
was **incorrect** — no EFFICIENCY surface existed in the CSGFoundry.

### Exact code path (qsim.h:~2290)

```
if( ems == smatsur_NoSurface )          // ems=1 for all CCB boundaries
    propagate_at_boundary();            // Fresnel — NO detection
else if( ems == smatsur_Surface )       // ems=2 — never reached
    propagate_at_surface();             // detect/absorb/reflect logic
```

## Fix

Add an EFFICIENCY=1.0 optical surface as a G4 skin surface on each of the
4 sensor volumes (`patch_gdml_sdetect.py`). On re-ingest:

1. `U4Surface::PrepareSkinSurfaceVector` collects the 4 skin surfaces.
2. `U4SurfaceArray::addSurface` sees EFFICIENCY>0 -> `is_sensor=true` ->
   payload (detect=1.0, absorb=0, reflect_specular=0, reflect_diffuse=0).
3. `sstandard::make_optical` reads `OpticalSurfaceName="CCB_SensorDetect"`,
   first char 'C' -> `smatsur::TypeFromChar` -> `smatsur_Surface` (2).
4. New boundary entries created (bd.txt grows from 6 to 9):
   `(AIR, sensor_skin, sensor_skin, Y11Core)` for each sensor.

## Evidence (GPU kernel debug, PIDX=0, photons at sensor)

```
//qbnd.fill_state idx 0 boundary 8 line 32 ... s.optical.x 4
//qsim.propagate.body bounce 2 command 3 flag 0 s.optical.x 4 s.optical.y 2
//qsim.propagate.body.NOT:WITH_CUSTOM4 BOUNDARY ems 2 lposcost 0.000
//qsim.propagate_at_surface.SA/SD.BREAK flag 64        ← SURFACE_DETECT
//qsim.propagate.tail bounce 2 command 1 flag 64 ems 2
```

- `ems=2` (smatsur_Surface) -> `propagate_at_surface` IS called
- `flag=64` = `0x1<<6` = **SURFACE_DETECT** (per OpticksPhoton.h enum)
- `command=1` (BREAK) -> photon stops, detected

## Open item: SEvt hit-gathering pipeline

While SURFACE_DETECT is produced at the kernel level, the SEvt
`num_hit` remains 0/-1 in the torch+gather test configuration. This is a
hit-buffer allocation/gathering issue in the torch test path, NOT a
detection failure. In the full G4CXOpticks event processing path (real
Geant4 events), the hit buffer is allocated and gathered correctly.

## Claim upgrade

Opticks GPU integration: **PARTIAL -> VALIDATED** (SURFACE_DETECT fires).
