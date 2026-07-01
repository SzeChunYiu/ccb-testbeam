# Response to Matthias re: MV3c Geometry PR - Inter-Stave Dead Layers

**Date:** 2026-07-01
**Re:** HIBEAM-NNBAR/hibeam_g4_geobuilder#8

---

## TL;DR

You are completely right — 2 mm aluminum between staves makes no physical sense.
Light guides are optical elements, not metal. I made an error by using "Al" as a
placeholder proxy without checking whether the proxy material itself was physically
appropriate. I have corrected the MV3b report with proper material estimates and an
errata section documenting what was wrong. The PR #8 default value should be revised
to a realistic starting point (~0.1-0.5 g/cm2/pair based on actual scintillator
detector construction materials: FR-4 PCB, polymer wrapping, connector material),
and the actual value must be determined by scanning the parameter against data.

## Where the "2 mm Al" Came From (and Why It Was Wrong)

The MV3b analytical toy model tried to estimate how much upstream material would
be needed to bring the simulated B8 stopping fraction from its current value down
to the data value (2.3%). In building a component budget, I used aluminum (rho=2.70
g/cm3) as a generic placeholder for "structural material" in several places:

1. **"B2 light guides/wrapping (2 mm Al)"** — This was the worst offender. Light
   guides in scintillator detectors are optical elements: wavelength-shifting fibers
   (polystyrene core, acrylic cladding), ESR (Enhanced Specular Reflector) polymer
   film wrapping, and optical coupling compound (silicone or epoxy). Aluminum would
   block 100% of the scintillation light — a detector built this way would not work
   at all. The actual B2 optical wrapping is approximately 0.05-0.10 g/cm2.

2. **"Beam exit window (0.5 mm Al)"** — The MV3c source audit (reading the actual
   geometry-builder source code) found the window is Mylar (100 um, rho=1.39 g/cm3),
   not aluminum. Areal density: 0.014 g/cm2, not 0.135 g/cm2.

3. **Inter-stave dead material proxy** — Using Al as a proxy for unknown material
   between staves is physically inappropriate because Al (Z=13) has very different
   stopping power from the actual low-Z materials (FR-4 PCB: epoxy/glass composite,
   rho~1.8; polymer wrapping; plastic connector housings). Higher-Z materials stop
   protons more efficiently per g/cm2, so an Al proxy overestimates the areal density
   actually needed.

## What I Simulated vs What I Compared To

The MV3b analytic model used a simple Bethe-Bloch continuum-slowing-down calculation:

- Beam: 190 MeV protons
- Target: 0.15 g/cm2 CD2 (fixed in the model)
- Variable upstream material added before B2, ranging from 0 to 15 g/cm2
- 50,000 tracks, CSDA range formula calibrated to NIST PSTAR
- Measured B8 fraction (fraction of tracks with range exceeding B8 depth)

This was compared to the data B8 fraction of 2.3% from the MV3 SLURM production
run, which processed the GEANT4 simulation of 190 MeV protons through the krakow
geometry and digitized the resulting energy deposits through the MV0 digitizer.

**The critical error:** I compared the toy model at "0 g/cm2 added" (which gives
100% B8 because there is NO upstream material at all in the toy model baseline)
against the data B8 fraction. But the actual GEANT4 simulation at "0 g/cm2 added"
already gives 22.3% B8 — because the real geometry already includes the CD2 target,
Mylar window, trigger scintillators, and beam pipe. The toy model baseline is a
completely different physical situation from the simulation baseline.

This means:
1. The toy model is a useful qualitative diagnostic (confirms material deficit is
   the right explanation), but
2. The specific number 11.12 g/cm2 is NOT a calibrated prediction — it is the toy
   model's self-consistent answer to "how much material would this toy model need
   to match data," not "how much material does the real simulation need"
3. The 2.51 g/cm2/pair default in PR #8 inherits this problem

## Corrected Material Budget

| Component | Areal density [g/cm2] | Source |
|---|---|---|
| CD2 target | 0.232 | Present in geometry source (MV3c audit) |
| Mylar beam window | 0.014 | Present in geometry source |
| Beam pipe (Al, 5 mm wall) | 1.35 | Present in geometry source |
| T1 trigger scintillator (PSci, 1 cm) | 1.032 | In source since 2026-01-26 |
| T2 trigger scintillator (PSci, 1 cm) | 1.032 | In source since 2026-01-26 |
| B2 optical coupling/wrapping | ~0.05-0.10 | Estimated from typical construction |
| **Inter-stave dead material** | **Unknown** | Confirmed absent; needs scan |

Most of the material is already present. The inter-stave dead material is the
primary missing component, but the amount needed is almost certainly far less
than the toy model's 2.51 g/cm2/pair estimate.

## What Should Happen Next

1. Revise the PR default to a physically realistic starting point (~0.1-0.5 g/cm2/pair
   based on FR-4 PCB + connector + wrapping material)
2. Use the actual low-Z material composition, not Al proxy
3. Build the geometry, run MV3, scan the parameter from 0 to ~3 g/cm2/pair
4. The calibrated value is whatever makes simulated B8 fraction match 2.3% (data)

The MV3b report has been updated with full errata documenting all corrections.

## Does This Pattern Appear Elsewhere?

I am now auditing all claims throughout the wiki and reports for similar issues —
any claim that uses a physically inappropriate proxy, any number presented as
calibrated when it came from an uncalibrated model, and any assumption not grounded
in the actual detector construction. The principle going forward is:

**Every material claim must be based on the actual detector as built. No
convenient proxies with different physics. When the exact value is unknown,
state the uncertainty and give a physically motivated range, not a
precise-looking number from an uncalibrated model.**
