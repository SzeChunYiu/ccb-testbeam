# CCB test-beam paper evidence and figure matrix

**Date:** 2026-08-12  
**Purpose:** bind every manuscript claim to a measured result, source/configuration record, model-dependent MC result, external primary source or explicit blocker. This file is a publication truth surface; when it conflicts with older narrative text, `paper/hardware_bom.csv`, the canonical claim ledger and later ADRs win.

## Evidence classes

- `DATA_MEASURED`: result calculated from real beam data for a declared selected population. Does not imply absolute detector calibration.
- `SOURCE_BOUND_CONFIG`: exact value in configuration/source. Not automatically survey/metrology truth.
- `DESIGN_SPEC`: collaboration hardware clarification or build specification with primary-source path recorded in `paper/hardware_bom.csv`. Not automatically survey/metrology truth.
- `MC_TRUTH`: Geant4 particle/energy-deposit observable before detector response.
- `MC_MODEL_DEPENDENT`: numerical detector-response prediction under declared but incompletely calibrated assumptions.
- `GATED`: useful result exists but claim promotion is blocked by a named provenance/calibration/systematic condition.
- `BLOCKED`: required evidence/identifiability is absent.
- `EXTERNAL_PRIMARY`: peer-reviewed primary paper, official toolkit documentation or manufacturer technical source.

## Claim matrix

| ID | Claim / object | Status | Primary evidence | Publication rule / remaining action |
|---|---|---|---|---|
| P-001 | HIBEAM/NNBAR annihilation-detector motivation | EXTERNAL_PRIMARY | Yiu et al. 2022; Dunne et al. 2022 | use only claims supported by those papers |
| P-002 | simulation/configuration beam energy 190 MeV | SOURCE_BOUND_CONFIG | reviewed run macro in S21 source review | bind run log before calling it measured beam energy |
| P-003 | simulation/configuration target 2.3 mm CD2 | SOURCE_BOUND_CONFIG | S21 source review | bind hardware/target record before metrology claim |
| P-004 | nominal 109 geometry parameter, arms about -38°/+71.5°, 8/4 bars | SOURCE_BOUND_CONFIG | `geant4/configs/krakow.geoconf` | label source-bound configuration, not survey |
| P-005 | compact CCB Geant4 geometry omits some real passive/support/electronics material | AUDIT / GATED | S21 source review | material-budget closure required for quantitative stopping |
| P-006 | B stave is extruded polystyrene, 50 × 5.18 × 2.0 cm | DESIGN_SPEC | issue #796; `paper/hardware_bom.csv`; `docs/stave_sim/STAVE_SIM_ENERGY_MODEL.md` | legacy BC-408/~1 m prose remains `UNKNOWN_EXTERNAL`; do not resolve by Geant4 alone |
| P-007 | two 2.0 mm holes, two 1.8 mm Y-11 fibres, 2 cm separation | DESIGN_SPEC | issue #796; `paper/hardware_bom.csv`; `docs/stave-geometry.md` | fibre grade/lot and construction record still absent |
| P-008 | only one fibre at one end was read out in beam test | DESIGN_SPEC | issues #796/#797; `paper/hardware_bom.csv` | retain in setup and every optical interpretation |
| P-009 | source-bound sensor is S13360-3050CS | DESIGN_SPEC | issue #796; `paper/hardware_bom.csv` | operating point, bias and coupling are separate claims |
| P-010 | S13360-3050CS 3×3 mm², 50 µm pitch, 3600 pixels | EXTERNAL_PRIMARY | Hamamatsu official data | safe manufacturer specification |
| P-011 | Y-11 representative 476 nm emission, 430 nm absorption, >3.5 m attenuation | EXTERNAL_PRIMARY | Kuraray official technical data | representative, not installed-fibre calibration |
| P-012 | Geant4 provides scintillation/absorption/boundary/WLS optical processes | EXTERNAL_PRIMARY | Geant4 manuals/papers | no detector-calibration inference from toolkit semantics |
| P-013 | historical CCB angular distributions require explicit event-weight treatment | GATED/AUDIT | S21 source review and later weight work | final MC figure must bind exact revision, Σw, Σw², ESS |
| P-014 | Sample-I calibration runs 31-37,39-42; analysis 44-57 | SOURCE_BOUND_CONFIG | S03e config | verify against run log/hardware trigger record |
| P-015 | Sample-II calibration 64; analysis 58-63,65 | SOURCE_BOUND_CONFIG | S03e config | same |
| P-016 | MC Sample I/II uses first-layer charged-hit proxy | GATED | current header of `SAMPLE_I_II_DATA_MC_REPORT.md` | show `MC_TRIGGER_PROXY` in every figure/table |
| P-017 | historical S00 selected B-pulse count is 640,737 | GATED | claim ledger / S03e config | source-lineage status must be stated; do not call efficiency |
| P-018 | Sample-II selected counts 125,096 total; B2 88,213, B4 21,229, B6 11,148, B8 4,506 | selected-population count | S03e config | regenerate from authorising product for final table |
| P-019 | Sample-I B2 historical selected population: n=241,422, mean 6090 ADC, saturation fraction 0.417 | DATA_MEASURED in historical selection | `SAMPLE_I_II_DATA_MC_REPORT.md` | final current producer must revalidate baseline/polarity/saturation rules |
| P-020 | Sample-II B2 historical mean 3663 ADC, saturation fraction 0.061 | DATA_MEASURED in historical selection | same | same |
| P-021 | trigger-proxy MC gives deuteron-enriched first B layer for Sample I and more penetrating Sample II | MC_TRUTH + proxy gate | `SAMPLE_I_II_DATA_MC_REPORT.md` | not hardware trigger efficiency |
| P-022 | located LUNARC beam ROOT waveform product is 8×16 samples (128 HRDv words/event) | DATA provenance / immutable manifest | `reports/studies/paper_a02_waveform_lineage/manifest.json`; #993 closed DISTINCT | authorising schema `hrd_raw_8x16_v1` for paper amplitude + format-limited timing |
| P-023 | historical timing product/config declares 8×18 at 10 ns on different laptop mounts | DISTINCT_SCHEMA / non-authorising for LUNARC raw | `configs/s00_reproduction.yaml`; S00a sorted-b manifest; #993 | quarantine cross-schema timing transfer; 18-sample timing historical only |
| P-024 | raw 8×16 B4-B6 central width ~38.0 ns for n=5207 | DATA_MEASURED / NON-PERFORMANCE | data-side report | caption `FORMAT-LIMITED; NOT DETECTOR RESOLUTION` |
| P-025 | historical sub-ns timing numbers are not authorising beam-data detector resolutions | GATED/BLOCKED | claim ledger; #993; #1059; `~38 ns` format-limited B4-B6 residual | keep historical/toy/MC only if clearly labelled; no invented sub-ns resolutions |
| P-026 | global-maximum CFD can switch physical pulse component as fraction changes | confirmed algorithmic ambiguity (software bound) | #1059; `scripts/cfd_fraction_transition.py`; `first_local_peak` producer default; lane05 synthetic tests | production timing must define target component; real-data fraction scan on authorising 8×16 schema only (#993 DISTINCT); same-sample sigma minimum is exploratory only (#1062) |
| P-027 | **Correct DATA ΔE-E definition:** ΔE=A(B2); E=A(B4)+A(B6)+A(B8) | DATA_MEASURED | issue #618; `reports/paper_956_deltaE_E_20260812T103800Z/` | regenerated 2026-08-12; composite key; axes remain ADC proxies |
| P-028 | **Correct data-matched MC ΔE-E:** ΔE=Edep(B2); E=Edep(B4)+Edep(B6)+Edep(B8) | MC_TRUTH + MC_TRIGGER_PROXY | issue #618; paper_956 run | PrimaryWeight: Sample I ESS=23,099; Sample II ESS=102,463 |
| P-029 | full MC ΔE-E residual E should include every downstream physical B layer available | MC_TRUTH + MC_TRIGGER_PROXY | issue #618; paper_956 run | full vs 4-readout panels side by side; r flips sign Sample I |
| P-030 | B2-vs-B4 alone is **not** the CCB ΔE-E analogue | explicit supervisor correction | issue #618 | composite-key diagnostic n=25,423, r=+0.151 |
| P-031 | composite-key B2-B4 diagnostic n=25,423, corr +0.151 | DATA_MEASURED diagnostic | `paper_956_deltaE_E_20260812T103800Z` | supersedes eventno-only 33,966/0.221 for production use |
| P-032 | historical B2-B4 truth-MC diagnostic corr -0.533 | MC_TRUTH diagnostic (legacy) | data-side report | retained as legacy two-layer reference only |
| P-033 | sparse alternating-layer readout can flip apparent ΔE-E pointing direction when stopping rise falls in missing stave | segmentation interpretation | issue #879; `fig_segmentation_readout_phase` | 1/3/5/7 vs 0/2/4/6 phase panels produced |
| P-034 | composite event key required; event-number-only joins are unsafe across runs | confirmed historical analysis flaw | #797 closing context / corrected producers | final producer asserts uniqueness before pivot |
| P-035 | optical campaign gives about 8.7-11.0 detected PE/MeV at selected p/d points | MC_MODEL_DEPENDENT | issue #796 campaign / calibration artifacts | never call measured light yield |
| P-036 | campaign relative spreads about 8.9-20.8% at selected points | MC_MODEL_DEPENDENT | same | define event-level resolution denominator before publication use |
| P-037 | current Geant4 Y-11 fluorescence yield/multiplicity is not source-bound | BLOCKED for absolute optical response | ADR + reopened #1088 | #1088 must close physics acceptance or remain BLOCKED_EXTERNAL |
| P-038 | absolute light-yield authorisation remains false under current WLS assumption | BLOCKED | `ADR-WLS-FLUORESCENCE-YIELD-UNVERIFIED.md` | no total collection-efficiency claim |
| P-039 | SiPM recovery law, charge normalisation, coupling footprint and correlated-noise parameters lack full CCB operating-point validation | BLOCKED | `ADR-SIPM-PHYSICS-BLOCKED-WAVEA-LANE01.md` | PAPER-A08 |
| P-040 | old analytical 0.56% total efficiency is non-authorising | SUPERSEDED FOR CLAIMS | `STAVE_SIM_ENERGY_MODEL.md` vs later ADRs | do not publish as detector efficiency |
| P-041 | heuristic ~92 ADC/MeV with ~28 ADC/MeV envelope is not precision calibration | GATED | claim ledger | do not relabel data axes in MeV |
| P-042 | historical ~246 ADC/MeV conversion is obsolete | SUPERSEDED | paper outline / later gain work | remove from production figures |
| P-043 | single-stave Edep reconstruction evaluated on held-out optical MC grid | MC_MODEL_DEPENDENT | `reports/paper_a09_heldout_edep_reconstruction/result.json`; SHA-256-bound grid at `ccb_calib_grid/` | pooled linear PE→Edep on train runs (d70,p100,p140); held-out d110+p60: median bias +10.1%, σ68 8.9%, RMS 17.8%, tail 15%; nuisance envelope NOT_EVALUATED |
| P-044 | full-stack incident-energy resolution is not yet calibrated in data | BLOCKED | material + per-channel response + trigger/selection gaps | PAPER-A06/A08/A09 full-stack extension |

## Required figures

### Figure 1: CCB layout

**Status:** `YELLOW`. Generate from source-bound configuration now; replace/supplement with an authoritative mechanical drawing or photo if PAPER-A01 finds one. Caption must distinguish configuration from metrology.

### Figure 2: stave geometry/readout

**Status:** `GREEN` as a source-bound schematic. Reuse `figures/geometry/` and mark one-fibre/one-end physical readout.

### Figure 3: data depth profile, Sample I vs II

**Status:** `YELLOW`. Existing result establishes topology; final plot must regenerate from the authorising product and carry current selection/saturation status plus counts.

### Figure 4: weighted MC depth profile/truth composition

**Status:** `YELLOW`. Bind production revision, weights/ESS, layer mapping and `MC_TRIGGER_PROXY`.

### Figure 5: raw timing residual

**Status:** `GREEN` only as a negative/format-limited result on `hrd_raw_8x16_v1`. Caption: `8×16 LUNARC raw; 10 ns nominal sampling; NOT DETECTOR RESOLUTION`.

### Figure 6: production timing/time-walk closure

**Status:** `RED`. Blocked by PAPER-A04 and #1059 on the authorising 8×16 schema; 18-sample historical timing explicitly non-authorising (#993 DISTINCT).

### Figure 7: **proper data amplitude ΔE-E**

**Status:** `YELLOW/GREEN`. Regenerated 2026-08-12 in `reports/paper_956_deltaE_E_20260812T103800Z/` (issue #956). Composite key, Sample I/II separate panels, identical axes, B2 saturation marked, run-block bootstrap in `tables/sample_summary.json`.

### Figure 8: **proper MC ΔE-E**

**Status:** `YELLOW`. Regenerated 2026-08-12: four-readout and full-downstream panels per sample with PrimaryWeight (Σw, ESS in manifest). Species-colour panels remain a follow-up; `MC_TRIGGER_PROXY` labelled.

### Figure 9: single-stave Edep → detected PE

**Status:** `YELLOW`. Existing campaign can be plotted with `MODEL-DEPENDENT OPTICAL MC; ABSOLUTE LIGHT YIELD NOT AUTHORISED`.

### Figure 10: optical-stage efficiencies

**Status:** `RED`. Requires PAPER-A07/A08 and reopened #1088.

### Figure 11: held-out energy-reconstruction resolution

**Status:** `YELLOW` (model-dependent MC closure on deposited energy; nuisance envelope pending A07/A08). Primary estimand \(r=(E_{\mathrm{reco}}-E_{\mathrm{dep}})/E_{\mathrm{dep}}\) with run-held-out split. Source: `reports/paper_a09_heldout_edep_reconstruction/`, figure `docs/figures/paper/edep_reconstruction_heldout.png`. Caption must state `MODEL-DEPENDENT OPTICAL MC; NOT BEAM-DATA CALIBRATION`.

## Unsafe/stale text that must not return

1. `docs/academic_chapters/02_experimental_setup.md` legacy BC-408 / ~1 m / ~10×1 cm prose — retained only as `UNKNOWN_EXTERNAL` rows in `paper/hardware_bom.csv` unless primary hardware evidence overturns the #796 design spec.
2. Any sub-ns timing value described as a measured beam-data detector resolution under current #993/#1059 status.
3. `~10 PE/MeV` described as measured absolute light yield.
4. analytical `0.56%` total optical efficiency described as detector efficiency.
5. 246 ADC/MeV in production interpretation; 92±28 ADC/MeV described as precision calibration.
6. MC trigger described as validated hardware trigger reproduction.
7. ADC and Geant4 truth EDep placed on a common numerical energy axis without validated response.
8. 16- and 18-sample waveform products described as equivalent without #993 closure.
9. **B2 versus B4 called ΔE-E.** The current contract is ΔE=B2 and residual E=sum of downstream B4+B6+B8 in data.

## Reference verification status

The current seven external references were checked against official publisher/arXiv/Geant4/manufacturer sources on 2026-08-12. Repeat the `nature-ref-verifier` workflow after any bibliography expansion. Manufacturer values must remain labelled representative/specification values rather than detector calibrations.
