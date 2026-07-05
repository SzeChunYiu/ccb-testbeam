# B-M9 — Close or bound the GEANT4 LayerID → physical-stave mapping

- Generated: 2026-07-05 (investigation over LUNARC GEANT4 geometry + SD source + analysis mapping code + prior audits).
- Reviewer origin: M9 ("the LayerID→stave mapping (paired vs odd) is under review yet underlies S21/S23/MV3 per-stave assignments").
- Verdict: **PARTIAL SIGN-OFF.** LayerID *semantics and depth ordering* are geometry-verified and signed off; the *grouping of 8 GEANT4 bars into the 4 data staves* (paired vs odd/even) cannot be resolved from the simulation alone and is **carried as mapping-conditional** — but the conditional touches only the small deep-stave (B4/B6/B8) MC fractions, not the headline numbers.

## Evidence (verified, not assumed)

**Geometry** — direct inspection of the deployed geometry file
`geant4/data/krakow_109_8-38deg_4-71deg.root` (TGeoManager):
- B-stack = node `Sci_stack1_1` (parent copyNo 1, the ang1=−38° arm) contains **8 `Sci_bar` daughters, copyNo 0…7**, at local z = −7,−5,−3,−1,+1,+3,+5,+7 cm.
- Each `Sci_bar` is a `TGeoBBox` 2 cm thick (dZ=1.0 cm) of material PSci; the stack is **8 contiguous, zero-gap 2 cm bars = 16 cm** deep.
- A-stack = `Sci_stack2_2` (parent copyNo 2, ang2=71.5°): 4 `Sci_bar` + `Trig_bar`.
- The `hibeam_g4_geobuilder` source (`krakow.cxx::Build()`, cross-checked in `reports/mv3c_geometry_source_audit/`) places bars by `bar_posz=(i+0.5)*bar_t − stack_t`, `bar_t=2 cm`, contiguous → loop index **i = copyNo = LayerID**, **i=0 = entrance bar nearest the target (most upstream)**, i=7 deepest.

**Sensitive detector** — `HIBEAM_Detector/hibeam_g4-main/src/SamplingD.cc` (`Sample_Det::ProcessHits`, lines 58/60/85–87): `LayerID = currentPhysical->GetCopyNo()` (the Sci_bar depth index 0…7); `LayerID1 = GetCopyNumber(1)` (stack id: **1 = B-stack, 2 = A-stack**). Matches `src/ccb_mc_validation/constants.py` (`B_ARM=1, A_ARM=2, NB_LAYERS=8, NA_LAYERS=4`).

**Analysis mapping** — `scripts/mc02_build_mc_pulse_table.py::stave_index_of` (and the `MAPPINGS` in `mv3_stopping_v4_diagnostics.py`, mc03, s21, s23):
- **paired** (default): `idx = layer//2` → `{0,1}→B2, {2,3}→B4, {4,5}→B6, {6,7}→B8` (each stave = sum of two adjacent 2 cm bars = 4 cm).
- **odd/even_read**: keep only alternate bars, discard the other half's energy (`{0}→B2,{2}→B4,{4}→B6,{6}→B8`).
- **Every variant agrees LayerID 0 → B2 (upstream, most-occupied) with monotonically increasing depth to B8, and 4 cm stave pitch.** The ambiguity is *energy grouping only* (is the in-between bar's energy collected or discarded), never ordering.

## What is SIGNED OFF (geometry-verified, mapping-INVARIANT)

- `LayerID = copyNo = bar depth index`, **0 = upstream entrance (→B2), 7 = deepest (→B8)**; monotonic, no interleaving.
- `LayerID1 = 1` selects the B range-stack (8 bars); `= 2` the A-stack (4 bars).
- B-arm = 8 contiguous 2 cm PSci bars (16 cm), no in-sim gaps/dead layers.
- **B2 fraction (~0.87), B2-vs-rest, total B-arm occupancy, and the depth ordering are mapping-invariant** — identical to ≲0.3% across paired/even/odd in the χ² grid (`reports/phase2_geometry_1783108797/grid_table.md`), and the most-occupied MC stave (B2 = LayerID 0) matches the data ordering (data stopping fractions B2=0.876, B4=0.063, B6=0.039, B8=0.023). Report these **unconditionally**.
- **Definitive dictionary (paired, the adopted default):** `{LayerID 0,1→B2; 2,3→B4; 4,5→B6; 6,7→B8}` for LayerID1==1; A-arm `{0→A1,1→A2,2→A3,3→A4}` for LayerID1==2.

## What is CARRIED AS MAPPING-CONDITIONAL

- The **individual deep-stave MC fractions B4, B6, B8** and everything built on them: S21 per-stave deuteron fractions + penetration-depth tail, S23 per-stave MC occupancy shares, MV3 B4/B6/B8 stopping-depth profile. These move at the few-percent level between paired and even/odd (grid examples: B6 0.038→0.023, B8 0.036→0.049; B4 ~0.055 both). **DATA per-stave fractions are unaffected — only the MC shares move** (already flagged in the S23 report caveat).

## Why not a full sign-off

The simulation contains **8 physically undifferentiated, fully-active bars** and carries **no "read/unread" or "stave" attribute**; it cannot distinguish "4 thick ~4 cm staves double-instrumented" (→ paired conserves all deposited energy) from "8 separate 2 cm blocks with only alternate ones read out" (→ odd/even, unread-bar energy genuinely lost). This is a **hardware fact about the real detector**, not something derivable from the sim geometry. The data-side docs are themselves internally inconsistent on the pitch (`docs/01_setup_and_detector.md`: "d = 4 cm newer vs ~2 cm older — discrepancy to resolve (S00)"). The earlier claim that "MV3 v4 closed the mapping → paired stands" is **overstated**: paired is only the marginal *best-χ²* variant, and the best χ²/ndf is still ~554 (a fit that fails on missing upstream material regardless of mapping) and is entangled with the unknown gain and trigger/basis axes — a data-driven best fit, not an independent geometry validation (and picking a mapping by data-χ² is mildly circular for a data/MC comparison).

## Recommendation (adopted)

1. **Adopt `paired` as the default** — physically consistent with the contiguous fully-active 8-bar stack the geobuilder actually built (pair-centres at z=−6,−2,+2,+6 cm = 4 cm pitch).
2. **Report B2 fraction, B2-vs-rest, total occupancy, and depth ordering as geometry-certain (mapping-invariant).**
3. **Report B4/B6/B8 fractions (and S21/S23/MV3 quantities derived from them) with the paired↔odd/even spread carried as an explicit mapping systematic**, not as decision-grade. Data-side per-stave numbers are unaffected.

## Source locations (LUNARC, absolute)
- Geometry: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/krakow_109_8-38deg_4-71deg.root`
- SD LayerID write: `.../HIBEAM_Detector/hibeam_g4-main/src/SamplingD.cc:58,60,85-87`
- Constants: `.../ccb-testbeam/src/ccb_mc_validation/constants.py:5-7`
- Mapping code: `.../ccb-testbeam/scripts/mc02_build_mc_pulse_table.py:52-53,142-155`; `scripts/mv3_stopping_v4_diagnostics.py:18-21,51-54`
- χ² grid: `.../ccb-testbeam/reports/phase2_geometry_1783108797/grid_table.md`
- Prior geobuilder audit: `.../ccb-testbeam/reports/mv3c_geometry_source_audit/REPORT.md`
