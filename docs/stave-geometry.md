# CCB single-stave geometry (issue #892)

This note documents the single-stave optical geometry implemented in
`geant4/single_stave/src/DetectorConstruction.cc` and
`geant4/single_stave/include/DetectorConstruction.hh`. Every number below is read
from those source files; the figures in `figures/geometry/` are generated from
the same constants by `figures/geometry/make_stave_drawing.py` (re-run after any
geometry change).

## Coordinate convention

| axis | meaning | extent |
|------|---------|--------|
| x | stave / fibre length | +-25 cm (50 cm) |
| y | width | +-2.59 cm (5.18 cm) |
| z | **normal thickness** | +-1.0 cm (2.0 cm) |

The primary enters at `(hit_x, hit_y, z = -half_z - eps)` travelling `+z`, so it
crosses the **2.0 cm normal thickness** (not the 50 cm long axis). Fibres run
along `x`; a `G4Tubs` is rotated +90 deg about `y` to lie on `x`.

## Volumes and dimensions (half-lengths)

| constant | value | role |
|----------|-------|------|
| `kStaveHalfX` | 25.0 cm | scintillator bar half-length |
| `kStaveHalfY` | 2.59 cm | bar half-width |
| `kStaveHalfZ` | 1.0 cm | bar half-thickness (normal path = 2.0 cm) |
| `kCoatingThk` | 0.25 mm | TiO2 reflective shell thickness |
| `kHoleRadius` | 1.0 mm | hole drilled through the scintillator |
| `kFibreRadius` | 0.90 mm | fibre outer-cladding outer radius |
| `kFibreHalfX` | 26.0 cm | fibre half-length (protrudes 1 cm per face) |
| `kFibreSep` | 2.0 cm | fibre centre-to-centre (y = +-1.0 cm) |
| `kSensorThk` | 0.10 mm | endcap SiPM disc thickness |

Two fibre channels at `y = +-1.0 cm`, each a concentric stack:

| layer | radius | material | n |
|-------|--------|----------|---|
| WLS core | `0.94 * kFibreRadius` = 0.846 mm | Y-11 doped polystyrene (`CCB_Y11Core`) | 1.59 |
| inner cladding | `0.97 * kFibreRadius` = 0.873 mm | PMMA (`CCB_FibreInnerClad`) | 1.49 |
| outer cladding | `1.00 * kFibreRadius` = 0.900 mm | fluorinated PMMA (`CCB_FibreOuterClad`) | 1.42 |
| optical gap | `kHoleRadius` = 1.000 mm | air (`G4_AIR`) | 1.00 |

Annular thicknesses: inner cladding 27 µm, outer cladding 27 µm, air gap 100 µm.

## Materials and optical properties

- **Scintillator** `CCB_Scintillator`: polystyrene (C8H8)n, 1.06 g/cm3, n = 1.59.
  Scintillation yield 10000/MeV, fast time constant 2.4 ns; Birks kB configurable
  (default 0.126 mm/MeV). Emission/absorption from the versioned optical tables.
- **WLS core** `CCB_Y11Core`: polystyrene host, 1.05 g/cm3, n = 1.59, with the
  Y-11 WLS absorption/emission spectra and an 8.5 ns WLS time constant. (Distinct
  material instance from the scintillator so the WLS and scintillation MPTs do
  not clobber one another.)
- **TiO2 coating**: modelled as a `dielectric_metal`, `unified`,
  `groundfrontpainted` border surface on the scintillator/coating boundary. It
  covers the **outer faces only**; the fibre-hole walls stay open
  (scintillator/air) so scintillation photons can cross into the fibres.
- **Optical gap / world**: air, n = 1.00.

## Optical readout chain

1. Energy deposit in the polystyrene scintillator -> scintillation photons
   (blue/UV, Birks-quenched).
2. Photons cross the open hole wall (scintillator n=1.59 -> air n=1.00) into the
   fibre outer cladding, then the PMMA inner cladding, and are absorbed in the
   Y-11 core (WLS uptake).
3. The Y-11 dye re-emits at a longer (green) wavelength. The descending
   refractive-index stack (core 1.59 > inner clad 1.49 > outer clad 1.42 > air
   1.00) traps the re-emitted photons by total internal reflection and guides
   them along `x`.
4. Fibres protrude 1 cm past each bar face; endcap SiPM discs
   (`kSensorThk = 0.10 mm`, radius = `kFibreRadius`) sit just beyond the
   protruding ends. Four channels are instrumented: F1+x (the **physical
   readout**), F1-x, F2+x, F2-x (controls).

## Figures (`figures/geometry/`)

- `fig_stave_crosssection_yz.png` - normal-incidence cross section (the y-z
  plane a primary sees); the diagnostic view of the two fibre channels and the
  full core/cladding/gap stack with dimensions and refractive indices.
- `fig_stave_longitudinal_xy.png` - top-down (x-y) longitudinal view showing the
  50 cm bar, both fibres protruding 1 cm per face, and the four SiPM sensors.
- `fig_fibre_radial_stack.png` - single fibre radial stack to scale, with the
  cladding annular thicknesses.
- `fig_stave_raytracer_3d.jpeg` - Geant4 `RayTracer` 3D render (headless, CPU).
  Produced via `macros/vis_raytracer.mac` (build with `-DCCB_ENABLE_VIS=ON`).
  Note: at stave scale the sub-mm cladding is not resolvable in this 3D shot.
- `ccb_stave_geometry.wrl` - VRML 2.0 export of the **exact** Geant4 geometry
  (`macros/vis_vrml2.mac`); open in any VRML viewer to inspect interactively.
- `ccb_stave_geometry.svg` - vector version of the cross section.

## Reproducing

```bash
# Schematics (headless, needs numpy + matplotlib):
python figures/geometry/make_stave_drawing.py

# Geant4 renders (build the sim with visualization):
cmake -DCCB_ENABLE_VIS=ON <repo>/geant4/single_stave && cmake --build .
ccb_stave_sim --macro macros/vis_raytracer.mac --optical-dir optical --output /tmp/x.root
ccb_stave_sim --macro macros/vis_vrml2.mac   --optical-dir optical --output /tmp/x.root
```
