# Response to Matthias re: MV3c Geometry PR — Inter-Stave Dead Layers

**Date:** 2026-07-01
**Re:** HIBEAM-NNBAR/hibeam_g4_geobuilder#8

---

## TL;DR

You are right — 2 mm aluminum equivalent between every stave pair is not realistic. The 2.51 g/cm2/pair value in PR #8 is a **toy-model starting point**, not a calibrated number. I agree it should be revised downward. The actual value should be determined by scanning the parameter against data. The PR was opened as a review-gated draft precisely because it has not been built or run yet.

## Where the Numbers Come From

### The 2.51 g/cm2/pair (inter-stave dead material)

This comes from MV3b's analytic toy model, which diagnosed MV3's stopping-depth failure (chi2/ndf = 68,269) as a missing-material problem. MV3b estimated:

- Known missing components (beam window, T1/T2, air, etc.): ~1.08 g/cm2
- Required total to match data: ~11.12 g/cm2
- Unexplained deficit: ~10.03 g/cm2
- Divided across 4 stave pairs (B2-B4, B4-B6, B6-B8, plus one more): ~2.51 g/cm2/pair

**Important caveat (documented in MV3c addendum):** MV3b's toy model uses a continuum-slowing-down calculation whose "zero material" baseline (100% B8) does NOT match the actual Geant4 simulation's baseline (B2=47%, B4=18%, B6=13%, B8=22%). This means the 11.12 g/cm2 is a **toy-model self-consistent estimate**, not a value extracted directly from the real simulation. The true required material is likely lower.

### The 2 mm Al placeholder (NOT inter-stave)

MV3b's component table listed "B2 light guides + wrap" as a separate line item using "2mm Al" as a placeholder for that specific component. This was a rough proxy for light-guide material around the B2 stave, not for the inter-stave dead layers. The Al proxy convention was reused in PR #8 for the inter-stave layers, which is misleading — I will update the PR to use a different, clearly labeled proxy material.

## What PR #8 Actually Does

The PR adds a configurable `interstaveDeadMat_areal_gcm2` parameter (default 2.51 g/cm2/pair, implemented as thin Al-proxy layers between HRDBar volumes). Key points:

1. **Al is a placeholder** — explicitly labeled as a proxy for generic structural/connector material, not a claim about composition
2. **Setting the parameter to 0 recovers the original geometry exactly**
3. **The value is meant to be scanned** — the PR description says: "The 2.51 g/cm2/pair default is a first candidate to start that scan from, not a predicted final answer"
4. **The PR is review-gated** — opened for discussion, not pushed to main; nothing changes unless a maintainer merges it

## What I Think the Real Value Should Be

Based on the MV3c source audit findings:

- The trigger scintillators (T1/T2) were likely already present in the simulation (added to source in Jan 2026), meaning MV3b overestimated the missing component
- The CD2 target and Mylar beam window are also confirmed present in the geometry source
- The inter-stave dead material is confirmed absent — but the amount needed is almost certainly less than 2.51 g/cm2/pair

A realistic starting point might be **0.1-0.5 g/cm2/pair** (e.g., ~0.5 mm of PCB + connector material), which should be determined by:

1. Actually building the geometry with the patch
2. Running a parameter scan from 0 to ~3 g/cm2/pair in small steps
3. Finding the value that brings simulated B8 fraction within 2 sigma of data (2.3%)

## What's Needed to Resolve This

1. **Merge or iterate PR #8** — with a corrected, more realistic default value
2. **Rebuild the .root geometry file** on LUNARC (requires ROOT + VGM toolchain)
3. **Re-run MV3 production** against the new geometry
4. **Scan `interstaveDeadMat_areal_gcm2`** to find the calibrated value

This is tracked as GAP-01 in STUDY_GAPS.md.

## Summary

| Item | MV3b Claim | MV3c Finding |
|---|---|---|
| T1/T2 trigger scintillators | "Not in MC" | **Present in source** since 2026-01-26 |
| CD2 target | Implicitly missing | **Present in source** |
| Mylar beam window | "Not in MC" | **Present in source** (not Al as assumed) |
| Inter-stave dead material | ~10 g/cm2 deficit | **Confirmed absent**; amount needed likely < MV3b estimate |
| PR #8 default value | 2.51 g/cm2/pair | Should be revised to ~0.1-0.5 g/cm2/pair; actual value from scan |

I will update the PR description to clarify these points and revise the default value. Thanks for catching this — the 2.51 g/cm2/pair was indeed too high as a starting assumption.
