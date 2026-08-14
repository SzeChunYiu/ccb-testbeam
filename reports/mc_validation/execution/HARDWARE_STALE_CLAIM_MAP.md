# Hardware Stale-Claim Map (Issue #1296)

Documents resolved hardware narrative conflicts and stale claims vs evidence. See `GMM_3330_HARDWARE_EVIDENCE_REPORT.md` for full evidence sweep results.

## Conflict Resolutions

| Path | Anchor | Old Stale Claim | New Text/Status | Evidence |
|------|--------|-----------------|-----------------|----------|
| docs/academic_chapters/02_experimental_setup.md | ~Line 19 | "approximately 22.5 cm" range for 5cm thick stave | QUARANTINED: superseded by #796 clarification (2.0 cm thickness). 22.5 cm applies to non-existent 5cm geometry. | Issue #796 DESIGN_SPEC: 2.0 cm thickness |
| docs/academic_chapters/02_experimental_setup.md | BC-408 references | "BC-408, density 1.032 g/cm³" material | QUARANTINED: #796 specifies extruded polystyrene (no specific brand). BC-408 remains UNKNOWN_EXTERNAL legacy material reference. | Issue #796 DESIGN_SPEC: extruded polystyrene |
| docs/academic_chapters/02_experimental_setup.md | ~Line 87 | "two Kuraray Y-11 wavelength-shifting fibres" (implies two-ended readout) | QUARANTINED: #796/#987 confirm one-fibre one-end readout for CCB beam-test. Two-fibre language reserved for full concept design. | Issue #796 DESIGN_SPEC + #987: one-fibre one-end |
| geant4/configs/krakow.geoconf | All geometry params | 109 cm, -38°, +71.5°, 8 B bars, 4 A bars | SIM_CONFIG status: these are Geant4 configuration values, not survey-grade metrology. | `docs/stave-geometry.md` DESIGN_SPEC |
| docs/academic_chapters/02_experimental_setup.md | "approximately one-metre" bars | ~1 m stave length | RESOLVED: #796 confirms 50 cm design spec. ~1 m narrative remains UNKNOWN_EXTERNAL (legacy description). | Issue #796 DESIGN_SPEC: 50 cm length |

## Evidence Classes for Key Quantities

| Quantity | Value | Evidence Class | Source | Claim ID |
|----------|-------|----------------|--------|-----------|
| Stave thickness | 2.0 cm | DESIGN_SPEC | Issue #796 clarification | P-006 |
| Stave length | 50 cm | DESIGN_SPEC | Issue #796 clarification | P-006 |
| Stave width | 5.18 cm | DESIGN_SPEC | Issue #796 clarification | P-006 |
| Hole diameter | 2.0 mm | DESIGN_SPEC | Issue #796 clarification | P-006 |
| Fibre separation | 2.0 cm | DESIGN_SPEC | Issue #796 clarification | P-006 |
| Fibre diameter | 1.8 mm | DESIGN_SPEC | Issue #796 clarification | P-006 |
| Geometry distance | 109 cm | SIM_CONFIG | `geant4/configs/krakow.geoconf` | P-004 |
| B stack angle | -38° | SIM_CONFIG | `geant4/configs/krakow.geoconf` | P-004 |
| A stack angle | +71.5° | SIM_CONFIG | `geant4/configs/krakow.geoconf` | P-004 |
| Beam energy | 190 MeV | UNKNOWN_EXTERNAL | No source-bound record found | P-002 |
| Target thickness | 2.3 mm CD₂ | UNKNOWN_EXTERNAL | No source-bound record found | P-003 |
| Readout scheme | One-fibre one-end | DESIGN_SPEC | Issue #796/#987 clarification | P-006 |

## UNKNOWN_EXTERNAL Categories (No Primary Collaboration Artifacts)

1. Primary CAD/build sheets
2. Assembly drawings with scale
3. Photos with scale/build annotations
4. Manufacturer spec sheets (Y-11 grade/lot, SiPM operating point)
5. SiPM carrier board records
6. Fibre end treatment records
7. CD2 target hardware record
8. Beam energy hardware record (190 MeV)
9. Trigger scintillator hardware
10. Survey/layout notes (109cm, -38deg, +71.5deg)

## Quarantine Guidance

All references to superseded 5cm geometry, BC-408 material specification, or two-fibre readout must carry quarantining qualifiers (DESIGN_SPEC, UNKNOWN_EXTERNAL, or legacy narrative markers) to prevent promotion to publication claims. The hardware BOM (`publication/tables/hardware_bom.csv`) is the canonical source for evidence class per quantity.
