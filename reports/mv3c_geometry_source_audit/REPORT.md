# MV3c: Geometry-Builder Source Audit and Candidate Fix

Generated: 2026-07-01
Study: MV3c — follow-up to MV3 (structural FAIL) and MV3b (analytic material-budget diagnosis)
Author: session follow-up (no LUNARC access; source-code audit + patch proposed for review as HIBEAM-NNBAR/hibeam_g4_geobuilder#8)

---

## 0. Motivation

MV3b (`reports/mv3b_material_budget/REPORT.md`) diagnosed MV3's structural stopping-depth
FAIL (chi2/ndf = 68,269) as a missing-upstream-material problem and produced a *component
budget* table listing candidate missing items (beam exit window, T1/T2 trigger scintillators,
air gap, target support, B2 light guides) as "not in current MC", with a combined known
deficit of only 1.08 g/cm2 against a required 11.12 g/cm2 — leaving a 10.03 g/cm2 unexplained
gap attributed to unmodeled "inter-stave dead material".

MV3b's own table was built analytically, without reading the actual Geant4 geometry-builder
source. This follow-up study reads that source directly to check which of MV3b's "not in
current MC" assumptions are still true, and to prepare a first candidate code fix for the
part that is confirmed genuinely missing.

## 1. Where the krakow geometry actually comes from

`geant4/configs/krakow.config` (this repo) sets:

```
Geometry_Namefile krakow_109_8-38deg_4-71deg.root
```

The Geant4 application (`hibeam_g4`, `src/WasaDetectorConstruction.cc::Construct()`) does
**not** build geometry in C++. It imports a pre-built ROOT/VGM geometry file by name:

```cpp
const std::string nameGeometry = Par.GetString("Geometry_Namefile");
gGeoManager->Import(nameGeometry.c_str());
...
RootGM::Factory rtFactory;      // Import geometry from Root to VGM
Geant4GM::Factory g4Factory;    // Export VGM geometry to Geant4
```

The `.root` geometry file itself is produced by a separate tool, `hibeam_g4_geobuilder`
(referenced in `geant4/configs/krakow.config`'s own comment: "Works with HIBEAM model
created using hibeam_g4_geobuilder"), specifically `src/krakow.cxx` / `include/krakow.hh`
in that repository (`HIBEAM-NNBAR/hibeam_g4_geobuilder`, a private-but-accessible GitHub
org repo, cloned locally to `~/Desktop/projects/_scratch/hibeam_g4_geobuilder` for this
audit). This is the actual source of the CCB/Krakow geometry MV3 is checking against.

## 2. What the geometry-builder source actually contains

Reading `src/krakow.cxx::Build()` directly (not assuming from MV3b's component list):

| Component | MV3b assumption | Actual source finding |
|---|---|---|
| CD2 target | "not in current MC" (implicit — MV3b's table only lists it as a required addition) | **Present**: `TARGET = MakeTube("TARGET", CD2, r=0-2.93cm, halfThickness=0.23/2 cm)` — a 2.3 mm CD2 tube at z=0 |
| Beam exit window | "Aluminium foil, ~0.1mm, No [not in current MC]" | **Present, but Mylar not Al**: `Window = MakeTube("Window", Mylar, r=0-5.0cm, halfThickness=0.01cm)` — a 100 um Mylar window at z=-5cm, upstream of the target |
| Beam pipe | (not listed by MV3b) | **Present**: `PIPE = MakeTube("PIPE", Al, r=4.5-5.0cm, halfThickness=24.99cm)` — 5mm-thick Al pipe wall at z=-30cm |
| T1/T2 trigger scintillators | "3mm PSci, No [not in current MC]" | **Present in source since commit `ced58bf` ("Added trigger scintillators to Krakow model."), dated 2026-01-26** — two `trigSci` volumes (PSci, 1cm thick each, i.e. thicker than MV3b assumed) per stack side, placed at `distTrig = distance - 10cm`, staggered in x/y with a small overlap region (a two-paddle coincidence-style trigger) |
| Air gap | "Air 50cm: 0.000645 g/cm2 (Partial)" | Not an explicit volume; implicit in whatever medium fills the world/mother volume. Numerically negligible either way (MV3b's own number, ~0.0006 g/cm2, confirms this is not a material candidate) |
| Inter-stave dead material (PCB, connectors, optical wrapping between consecutive scintillator-bar layers) | "~10.03 g/cm2 deficit, attributed here" | **Confirmed absent.** The bar-placement loop places `HRDBar` (PSci) volumes back-to-back with zero gap (`bar_posz = (i+0.5)*bar_t - stack_t`, i.e. contiguous, `bar_t=2cm` pitch, no intervening volume) inside a `Vacuum`-filled `HRDStack1`/`HRDStack2` mother box. There is no dead-material volume of any kind between bars in the current source. |

## 3. Interpretation — this revises, but does not overturn, MV3b's conclusion

**Important caveat that could not be resolved from this Mac:** commit `ced58bf` (adding the
trigger scintillators) is dated 2026-01-26, well before the MV0-MV6 production runs
(2026-06-25 through 2026-06-28, per `docs/mc_validation/MC_VALIDATION_RESULTS.md`'s SLURM job
IDs). *If* the specific file `krakow_109_8-38deg_4-71deg.root` used by the production runs was
(re)built from the geometry-builder source at or after that commit, the trigger scintillators
(and the CD2 target, and the Mylar window) were already present in the simulated geometry that
produced MV3's chi2/ndf = 68,269 — meaning MV3b's "T1/T2 not in current MC" line item was not
correct for that run, and the true "known component" subtotal is higher than the 1.08 g/cm2
MV3b computed (roughly 1.08 + ~1-2 g/cm2 of PSci trigger material, depending on how much of the
two-paddle overlap geometry a given track actually crosses). *If*, instead, the `.root` file
predates that commit and was never regenerated, MV3b's original assumption holds exactly as
written.

This cannot be settled without either (a) LUNARC access to inspect the actual deployed
`.root` file's build provenance, or (b) simply regenerating the geometry file fresh from the
current `hibeam_g4_geobuilder` `main` branch before the next MV3 production run, which
sidesteps the ambiguity entirely and is the recommended action regardless of which case is
true.

**What does not change:** the inter-stave dead-material gap is confirmed absent from the
geometry-builder source under either interpretation above — it is a separate, independently
verified finding, not something that depends on the file-provenance question. This remains the
best-supported candidate explanation for the bulk of MV3's discrepancy, consistent with MV3b's
own headline conclusion.

## 4. Candidate fix prepared (not yet built or run)

A patch implementing the inter-stave dead-material fix has been written and committed to a
local branch of `hibeam_g4_geobuilder`:

- Location: `~/Desktop/projects/_scratch/hibeam_g4_geobuilder` (branch
  `fix/mv3-interstave-dead-material`, commit `4714ddd`)
- **Pushed and opened for review (2026-07-01):**
  [HIBEAM-NNBAR/hibeam_g4_geobuilder#8](https://github.com/HIBEAM-NNBAR/hibeam_g4_geobuilder/pull/8).
  Opening a pull request (rather than pushing directly to `main`) keeps this reversible and
  review-gated: nothing in the shared collaboration repository changes unless a maintainer
  reviews and merges it. The PR description states plainly that the change is not built,
  not run, and not verified.
- **Not compiled or run**: building `hibeam_g4_geobuilder` requires ROOT + VGM (the same
  `nnbar_env` conda environment documented in `geant4/REPRODUCTION_STATUS.md`), which is not
  set up on this Mac. The change was verified for **geometric self-consistency only**, by
  reproducing the exact placement arithmetic in Python and confirming zero gaps and zero
  overlaps between consecutive bar/dead-layer volumes for both the config-driven
  `nBars1=8, nBars2=4` (krakow.geoconf) and the hardcoded-default `nBars1=7, nBars2=3` cases.

### What the patch does

Adds a single named, tunable constant `Krakow::interstaveDeadMat_areal_gcm2` (default 2.51
g/cm2, MV3b's own "per pair" share of the diagnosed deficit) and inserts a thin Al-proxy
`DeadLayer` volume between every consecutive pair of `HRDBar` layers in both `HRDStack1` and
`HRDStack2`. Al is used as an explicit, clearly-labeled placeholder/proxy for "generic
structural/connector material", not a claim about the true detailed composition — consistent
with how MV3b itself modeled comparable known items (e.g. "B2 light guides+wrap" as 2mm Al).
Setting the constant to 0 recovers the original (pre-patch) geometry exactly. Stack
half-thickness and the `dist1`/`dist2` offsets are updated so the stack's entrance face (the
first bar surface nearest the target) stays at the same `distance` as before; only the total
stack depth grows.

### Recommended next step (requires LUNARC)

1. **Done (2026-07-01):** [PR #8](https://github.com/HIBEAM-NNBAR/hibeam_g4_geobuilder/pull/8) is open against `HIBEAM-NNBAR/hibeam_g4_geobuilder`, awaiting maintainer review.
2. Once reviewed/merged, rebuild the `.root` geometry file with the current `main` (to also resolve the file-
   provenance ambiguity in Section 3) plus this patch.
3. Re-run MV3 (`geant4/jobs/mv3_stopping_v3.sbatch` or its successor) against the new geometry.
4. This is exactly the falsifying test already specified in `docs/09_open_questions.md`: scan
   `interstaveDeadMat_areal_gcm2` and identify the value that brings the simulated
   B8/B6/B4/B2 stopping fractions within 2 sigma of the data fractions
   (B2=0.876, B4=0.063, B6=0.039, B8=0.023). The 2.51 g/cm2/pair default is a first candidate
   to start that scan from, not a predicted final answer.

## 5. Summary

| Item | Status |
|---|---|
| CD2 target, beam window, beam pipe | Present in geometry-builder source (contra part of MV3b's assumption list) |
| T1/T2 trigger scintillators | Present in source since 2026-01-26; file-provenance relative to the June 2026 production run is unresolved |
| Inter-stave dead material | Confirmed absent from source; MV3b's leading candidate for the ~10 g/cm2 deficit stands |
| Candidate code fix | Written, self-consistency-verified, [PR #8](https://github.com/HIBEAM-NNBAR/hibeam_g4_geobuilder/pull/8) open for review; not built, not run, not merged |
| MV3 status | Unchanged: STRUCTURAL FAIL, still requires a new Geant4 production run to close |
