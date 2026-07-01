# MV3b: Upstream Material Budget Estimation

Generated: 2026-06-28 | **Corrected: 2026-07-01** (see Errata section)
Study: MV3b — diagnostic follow-up to MV3 structural FAIL
Input: MV3 SLURM result (chi2/ndf=68,269)

---

## Executive Summary

MV3 found a catastrophic MC-data stopping-depth discrepancy:
- MC B8 fraction: **22.3%** (protons penetrate far into the detector)
- Data B8 fraction: **2.3%** (protons stop mostly in B2)
- chi2/ndf = **68,269** (catastrophic FAIL)

This study analytically estimates the upstream material thickness needed to
reconcile MC with data, and identifies the physical components responsible.

**Important caveat (2026-07-01):** This is an analytic toy model, not a direct
fit to the Geant4 simulation. The toy model baseline (0 g/cm2 added -> 100% B8)
does NOT match the actual Geant4 simulation baseline (22.3% B8 at 0 g/cm2 added,
because the real simulation already includes the CD2 target, Mylar window,
trigger scintillators, and beam pipe). The 11.12 g/cm2 estimate is a toy-model
self-consistent number, not a calibrated value from the real simulation. See Errata.

---

## 1. Analytical Method

Using the Bethe-Bloch CSDA range formula (Barkas approximation, calibrated to NIST PSTAR):

    R_plastic(E) = 0.00220 * E^1.750 / rho_plastic  [cm, E in MeV]

Parameters: rho_plastic = 1.03 g/cm3 (BC-408), beam E0 = 190.0 MeV.

A Monte Carlo (n=50,000 tracks) propagates protons through the B-arm geometry
with variable upstream material added before B2.

---

## 2. Material Scan Result

| Extra upstream material | B8 fraction | B2 fraction |
|---|---|---|
| 0.0 g/cm2 (toy model baseline, no upstream material) | 100.0% | 0.0% |
| 11.1 g/cm2 (toy model matched to data) | 1.7% | 0.0% |
| **Actual Geant4 simulation (MV3, 0 added)** | **22.3%** | **47.0%** |
| **Data** | **2.3%** | **87.6%** |

Toy model estimate of extra material needed: **11.12 g/cm2** (toy-model self-consistent).

The toy model baseline does NOT match the real simulation because the real
simulation already contains the CD2 target, Mylar window, trigger scintillators,
and beam pipe — all of which are absent from the toy model's "zero added material"
starting point. This means the toy model overestimates how much additional material
is needed. The real required amount is lower than 11.12 g/cm2.

---

## 3. Material Budget Components (Corrected)

| Component | Areal density [g/cm2] | In current MC? |
|---|---|---|
| CD2 target (0.23 cm, rho=1.01 g/cm3) | 0.232 | **Present** (MV3c audit) |
| Mylar beam window (100 um, rho=1.39 g/cm3) | 0.014 | **Present** (MV3c audit) |
| Beam pipe wall (Al, 5 mm, rho=2.70 g/cm3) | 1.35 | **Present** (MV3c audit) |
| T1 trigger scintillator (PSci, 1 cm, rho=1.032 g/cm3) | 1.032 | **Present in source** (since 2026-01-26) |
| T2 trigger scintillator (PSci, 1 cm, rho=1.032 g/cm3) | 1.032 | **Present in source** (since 2026-01-26) |
| Air gap (~50 cm, rho=0.00129 g/cm3) | ~0.001 | Negligible |
| B2 optical coupling / ESR wrapping | ~0.05-0.10 | Not in MC (thin polymer reflective film) |
| **Subtotal (confirmed present)** | **~3.7** | Most items already in source |
| **Inter-stave dead material** | **Unknown** | **Confirmed absent** (MV3c) |

### Correction of Previous Erroneous Claims

The original version of this report contained physically incorrect claims:

1. **"B2 light guides/wrapping (2 mm Al)"** — This was wrong. Light guides and
   optical wrappings are not made of aluminum. The actual components are:
   - WLS fiber readout (polystyrene core, acrylic cladding)
   - ESR (Enhanced Specular Reflector) film wrapping (polymer multilayer, ~65 um thick)
   - Optical coupling compound (silicone or epoxy, sub-mm thickness)
   
   Aluminum (Z=13, rho=2.70 g/cm3) would completely block the scintillation light
   and defeat the purpose of the detector. The correct areal density of optical
   wrapping around B2 is approximately 0.05-0.10 g/cm2, not 0.280 g/cm2.

2. **"Beam exit window (0.5 mm Al)"** — The MV3c source audit found the actual
   material is Mylar (100 um, rho=1.39 g/cm3), not aluminum. Areal density:
   0.014 g/cm2, not 0.135 g/cm2.

3. **"2 mm Al" as a generic proxy for inter-stave dead material** — Using aluminum
   as a placeholder for unknown structural/connector materials is physically
   misleading because:
   - Al has very different stopping power (dE/dx scales approximately with Z/A)
     from the actual low-Z organic materials (FR-4 PCB: epoxy/glass composite,
     optical wrapping: polymer film, connectors: copper alloy + plastic housing)
   - Using an Al proxy overestimates the areal density needed because higher-Z
     materials stop protons more efficiently per g/cm2
   - The correct approach is to model actual detector materials (FR-4, polymer,
     copper trace equivalent) or explicitly state that any proxy value is a
     stopping-power-equivalent thickness, not a physical thickness of aluminum

### Interpretation (Corrected)

The MV3c source audit found that most items previously listed as "not in current MC"
are actually present in the geometry-builder source. The confirmed-absent component
is the inter-stave dead material (PCB boards, connectors, optical wrapping between
consecutive scintillator bars).

The amount of inter-stave material needed **cannot be reliably estimated from this
toy model** because:
1. The toy model baseline does not match the real simulation
2. The toy model uses continuum slowing-down without the actual Geant4 geometry
3. Most of the "missing" material in the original estimate was actually already present

The only way to get a calibrated number is to add realistic inter-stave material
to the actual Geant4 geometry and re-run the simulation, scanning the added areal
density until the simulated stopping fractions match data.

---

## 4. Geometry Fix Recommendation (Revised)

1. **Verify the .root geometry file provenance** — confirm whether the production
   file includes the trigger scintillators (added to source 2026-01-26)
2. **Add inter-stave dead material** with realistic composition:
   - FR-4 PCB substrate + copper trace equivalent for readout boards
   - Polymer reflective film for optical wrapping between staves
   - Starting estimate: ~0.1-0.5 g/cm2 per stave pair (based on typical
     scintillator detector construction, not the toy-model 2.51 g/cm2)
3. **Re-run MV3** against the updated geometry
4. **Scan the inter-stave areal density** from 0 to ~3 g/cm2/pair to find the
   calibrated value that brings simulated B8 fraction within 2 sigma of data (2.3%)

The candidate fix is PR #8 at HIBEAM-NNBAR/hibeam_g4_geobuilder (review-gated,
not merged, not built, not run).

---

## 5. References

- MV3 report: reports/mv3_stopping_v3_1782679272/REPORT.md
- MV3c geometry audit: reports/mv3c_geometry_source_audit/REPORT.md
- PR #8: https://github.com/HIBEAM-NNBAR/hibeam_g4_geobuilder/pull/8
- NIST PSTAR: https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html

---

## 6. Errata (2026-07-01)

| Original Claim | Correction | Reason |
|---|---|---|
| "B2 light guides/wrapping (2 mm Al)" | B2 optical coupling/wrapping, ~0.05-0.10 g/cm2 (polymer/ESR film) | Light guides are optical elements; Al would block light completely |
| "Beam exit window (0.5 mm Al)" | Mylar window, 100 um, 0.014 g/cm2 | MV3c audit found actual material is Mylar |
| Toy model "0.0 g/cm2" row shown as equivalent to MC | Added actual Geant4 simulation row for comparison | Toy model baseline differs from real simulation baseline |
| "11.12 g/cm2 required" as a calibrated number | Labeled as toy-model self-consistent estimate | Most components already present per MV3c |
| 2.51 g/cm2/pair as PR #8 default | Should be revised to ~0.1-0.5 g/cm2/pair as starting point, with a scan to find the calibrated value | Original derived from toy model, not from real simulation |

**Principle:** All material claims must be based on actual detector construction
materials, not convenient proxies with different physical properties. When the
exact material is unknown, the uncertainty must be stated explicitly with a
physically motivated range, not a precise-looking number from an uncalibrated model.
