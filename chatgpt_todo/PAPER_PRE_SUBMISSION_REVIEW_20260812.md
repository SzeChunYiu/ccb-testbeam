# CCB test-beam manuscript: simulated pre-submission review

**Date:** 2026-08-12  
**Draft:** `chatgpt_todo/PAPER_DRAFT_CCB_TESTBEAM_20260812.md`  
**Evidence matrix:** `chatgpt_todo/PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md`  
**Open tasks:** `chatgpt_todo/PAPER_OPEN_ATOMS_20260812.md`

## Change log (2026-08-12, issue #956)

PAPER-A05 primary producer `scripts/single_stave/paper_956_deltaE_E_publication.py` regenerated Figures 7–8 and segmentation/B2–B4 diagnostics under `reports/paper_956_deltaE_E_20260812T103800Z/` with SHA-256 provenance. Manuscript Section 7.3, evidence rows P-027–P-033, claim ledger CL-028–CL-031, and checklist items above were updated. MC species-colour panels and beam-energy sensitivity remain open.

---

This is an internal role-separated scientific review, not independent human peer review. The requested `nature-reviewer` workflow prefers mutually blind reviewers. This environment does not provide isolated contexts, so mutual blindness cannot be guaranteed. I therefore use fixed reviewer remits, force each reviewer to state the strongest alternative explanation and falsifier, and retain mistakes found by later passes in the audit record.

The four lenses are:

1. **R1 detector/test-beam instrumentation:** scintillator telescope, DAQ, trigger and timing observability.
2. **R2 Geant4/optics/SiPM:** transport, optical stages, detector response and energy reconstruction.
3. **R3 statistics/reconstruction:** estimands, uncertainty, held-out validation, weights and covariance.
4. **R4 adversarial claims editor:** checks definitions against supervisor issues, claim ledger, ADRs and stale documentation.

---

# Cycle 1: draft-level review

## R1 detector/test-beam instrumentation

**Vote: MAJOR REVISION; ACCEPT stopping-topology result, BLOCK detector timing/absolute energy performance.**

The draft has enough beam data to support a paper, but the strongest measured result is narrower than several historical project summaries suggested. Sample I and Sample II have visibly different selected depth/amplitude populations. The four B readout channels also make the detector limitation easy to explain. PAPER-A02 / #993 now closes waveform lineage as **DISTINCT_SCHEMAS**: the located 8×16 LUNARC raw product authorises format-limited timing only; historical 18-sample sub-ns values remain non-authorising.

### Major points

- The current 50 × 5.18 × 2.0 cm stave description is preferable to the older ~1 m BC-408 narrative, but PAPER-A01 must bind a primary collaboration hardware record because issue #796 itself contains an earlier conflicting `5cm thickness` phrase.
- Data trigger names need a run-log/hardware source. The MC selection must remain labelled `MC_TRIGGER_PROXY`; first-layer hit logic is not a validated simulation of the trigger counter/electronics.
- The ~38 ns B4-B6 result from the located 8×16 LUNARC raw product is publishable only as evidence that the waveform representation is sampling/window limited. It is not the detector timing resolution. Historical 18-sample sub-ns timing values remain non-authorising for this product (#993 DISTINCT_SCHEMAS).
- Issue #1059 changes the timing measurand for multi-component pulses: global-maximum CFD can retarget a later pulse as the fraction changes. Lane 05 closes the software contract with `first_local_peak` component binding, deterministic fraction-transition controls, and fail-closed selector identifiability limits (#1277/#1278). Physical component identity and authorising beam-data timing remain blocked until PAPER-A04 closes on the authorising 8×16 schema; the ~38 ns format-limited residual is the only publishable beam-data timing statement today.
- Pulse fractions are selected-population quantities, not particle efficiencies.

**Strongest alternative explanation:** the Sample-I/Sample-II depth difference could be amplified by trigger thresholds, B2 saturation and analysis selection rather than caused only by a different p/d mixture.

**Falsifier:** bind hardware trigger semantics and apply the same threshold/saturation/four-readout response to weighted MC. Test whether the depth contrast and truth-species interpretation survive.

---

## R2 Geant4, scintillator optics and SiPM response

**Vote: MAJOR REVISION; ACCEPT optical MC as a model study, BLOCK absolute light efficiency and detector energy resolution.**

The standalone single-stave simulation is useful and already supplies a response scale, but later ADRs correctly prevent the existing ~10 PE/MeV result from being treated as an absolute calibration.

### Major points

- Do not publish the old analytical 0.56% scintillation-photon-to-PE efficiency. It combines an estimated WLS capture fraction and generic PDE assumptions that later project gates supersede.
- The Geant4 Y-11 model contains absorption/emission/timing information but lacks a source-bound fluorescence-yield/multiplicity contract. The current unit-secondary default is a hypothesis. Issue #1088 is therefore a physics blocker even though a fail-closed software contract has been implemented.
- Hamamatsu product data can support sensor geometry and spectral context, not the CCB PDE at an unknown overvoltage/temperature.
- `pe` must be tied to a physical primary-avalanche or charge definition before it becomes an absolute calibration unit; peak-normalised impulse models can otherwise make it phenomenological.
- The campaign-reported 8.9-20.8% spreads are not yet a publication energy-resolution curve. PAPER-A09 must define an event-level residual, freeze a calibration, validate on held-out events/points and propagate optical/SiPM nuisance parameters.
- Position dependence is likely material for one-ended readout and needs an explicit scan along the 50 cm stave.

**Strongest alternative explanation:** different combinations of WLS yield, attenuation, coupling, PDE and gain can reproduce the same mean PE/MeV at a few calibration points while predicting different variance, position dependence and saturation.

**Falsifier:** instrument stage counters and compare parameter hypotheses at fixed incoming photon histories. Use intermediate observables, not only the final mean signal.

---

## R3 statistics and reconstruction

**Vote: MAJOR REVISION; ACCEPT evidence discipline, BLOCK quantitative submission without grouped uncertainty and held-out analyses.**

The project has large event samples, but sample size is not the main statistical issue. The relevant risks are selection/calibration leakage, unpropagated event weights, shared-run dependence and ambiguous resolution denominators.

### Major points

- Report dependence-aware intervals using run-block bootstrap or another grouped method for data topology/correlation summaries. Treating all pulses as IID would understate run-to-run uncertainty.
- Propagate MC event weights through every plotted estimand and report `Σw`, `Σw²` and effective sample size.
- A pair timing width does not identify individual stave resolutions without a covariance model. Do not divide by `sqrt(2)` automatically.
- Keep calibration and validation populations separated. The current run configuration already provides a natural split; final timing/energy response should preserve it.
- For single-stave energy resolution, start with `(Ereco-Edep)/Edep`. Incident kinetic energy and full-stack incident-energy reconstruction are separate estimands.
- Do not convert the B2/B4 data-MC difference into an `N sigma` discrepancy until response and selection are matched.

**Strongest alternative explanation:** apparent reconstruction gains can come from choosing pulse classes, correction forms or nuisance parameters on the same population used for performance reporting.

**Falsifier:** freeze selection/estimator/calibration on declared training runs or MC points, then evaluate exactly once on held-out groups with nuisance scans.

---

# Cycle 1 adversarial claims audit: reviewer miss and correction

The first three reviews initially failed to challenge a definition inherited from the first manuscript draft: that draft treated a B2-versus-B4 amplitude plot as the ΔE-E observable. A subsequent issue-level audit by R4 found direct supervisor instructions in **issue #618** that reject this definition.

The required definitions are:

### DATA

`ΔE = amplitude(B2)`  
`E = amplitude(B4) + amplitude(B6) + amplitude(B8)`

### DATA-matched MC

`ΔE = Edep(B2)`  
`E = Edep(B4) + Edep(B6) + Edep(B8)`

### Full MC truth

`ΔE = Edep(first B layer / B2 analogue)`  
`E = sum of Edep in all downstream physical B-stack layers available in MC`

Issue #618 explicitly states that **B2 versus B4 alone must not be called ΔE-E**. Issue #879 independently explains why the sparse alternating-layer readout can change the apparent pointing direction when the stopping-power rise falls in a missing stave.

This was a scientifically material review failure because observable definition precedes plotting/statistics. The manuscript, evidence matrix and open-task queue were rewritten after this finding. The existing B2-B4 `n=33,966, corr=+0.221` data result is retained only as a two-channel response diagnostic. The truth-MC `corr=-0.533` value is treated the same way.

**Process lesson:** reviewer passes must begin by checking the supervisor/analysis-contract issues for observable definitions, not only by judging the prose and result files.

---

# Cycle 2: review of the corrected scientific argument

## R1 second pass

**Vote: ACCEPT WITH REQUIRED PRE-SUBMISSION EVIDENCE for the topology/sparse-range paper; BLOCK any intrinsic timing number until PAPER-A04 closes on the authorising 8×16 schema (#993 now DISTINCT_SCHEMAS).**

The corrected manuscript now has a clear experimental core. It reports the selected stopping-versus-penetrating topology, separates physical layers from readout channels and does not claim a detector timing resolution from the 8×16 data. Remaining experimental requirements are the publication hardware/run contract and regeneration of the proper downstream-sum ΔE-E plot from the authorising data product.

## R2 second pass

**Vote: ACCEPT WITH REQUIRED PRE-SUBMISSION EVIDENCE for a model-dependent optical section; BLOCK absolute efficiency and detector energy resolution until #1088/PAPER-A07/A08/A09 close.**

The optical section now uses the existing PE campaign as a declared model prediction and explicitly separates WLS fluorescence yield, transport, sensor PDE, avalanche count and electronics response. This is publishable as simulation methodology. A stronger full-performance paper should add stage efficiencies and held-out energy reconstruction before submission.

## R3 second pass

**Vote: ACCEPT WITH REQUIRED PRE-SUBMISSION EVIDENCE after grouped uncertainty and weighted MC are added to the central figures.**

The corrected ΔE-E definition removes the largest observable-definition error. Final paper figures still need run-block uncertainty, counts/selection flow and weighted-MC metadata. The B2-B4 diagnostic can remain in an appendix or model-validation subsection if clearly labelled.

## R4 second pass

**Vote: ACCEPT manuscript claim structure; BLOCK promotion of any old stale value not present in the evidence matrix.**

The following phrases/values are prohibited unless new evidence changes their status:

- ~0.54 ns or ~0.68-0.75 ns described as measured beam-data detector timing resolution;
- ~10 PE/MeV described as measured absolute light yield;
- 0.56% described as detector photon-to-PE efficiency;
- 246 ADC/MeV as a production conversion;
- 92±28 ADC/MeV described as precision calibration;
- MC trigger described as validated hardware-trigger reproduction;
- B2 versus B4 described as ΔE-E;
- 16- and 18-sample waveform products described as equivalent — **removed**; #993 closes them as distinct schemas with quarantined cross-schema timing transfer.

---

# Humanization/editorial pass

The requested `humanizer` workflow was applied as an editorial constraint, not as a source of scientific content. The revised manuscript uses a neutral technical voice and avoids changing evidence strength for style.

Rules retained in the current draft:

- use **model-dependent optical response**, not `light-yield calibration`, for current PE/MeV numbers;
- use **format-limited timing residual**, not `timing resolution`, for the raw 8×16 result;
- use **selected-pulse fraction**, not `efficiency`, for B-stack counts;
- use **source-bound configuration**, not `measured geometry`, for unsurveyed geometry parameters;
- use **two-channel B2-B4 diagnostic**, not `ΔE-E`, for the +0.221/-0.533 correlation result;
- keep the same detector term instead of synonym cycling;
- avoid promotional phrases, vague attribution and generic "this highlights/underscores" prose;
- do not add citations, numbers or causal claims during style editing.

---

# Synthesis and publication decision

## What is already strong enough to write as a paper result

1. The beam-data selected B-stack topology differs strongly between the Sample-I and Sample-II analysis populations.
2. The sparse four-readout configuration is an experimentally important limitation and motivates the correct downstream-sum ΔE-E definition plus an eight-vs-four-layer MC study.
3. The located 8×16 waveform product demonstrably fails to support a precision detector timing measurement; that negative result and the methodological reason are reportable.
4. The single-stave optical simulation supplies a reproducible model response of order 10 detected PE/MeV at selected p/d points, provided it is labelled model-dependent.
5. Existing MC infrastructure is sufficient to perform a clean held-out deposited-energy reconstruction study once the response/nuisance contract is frozen.

## What still blocks a full detector-characterisation submission

- authoritative hardware/run and waveform provenance: PAPER-A01/A02/A03;
- physically defined production timing: PAPER-A04 remains open for authorising beam-data performance; #1059 software binding and negative ~38 ns format-limited result are reportable; #993 blocks real-data fraction-transition product;
- proper issue-#618 ΔE-E data/MC figures with grouped uncertainty and weights: PAPER-A05;
- passive-material/data-matched MC closure: PAPER-A06;
- WLS/SiPM stage calibration, including reopened #1088: PAPER-A07/A08;
- held-out Edep energy resolution: **initial MC_MODEL_DEPENDENT closure delivered** (PAPER-A09 / `reports/paper_a09_heldout_edep_reconstruction/`); optical/SiPM nuisance envelope still blocked.

## Decision

**TEXT AND SCIENTIFIC ARGUMENT: READY FOR COLLABORATION REVIEW.**  
**FULL NUMERICAL DETECTOR-PERFORMANCE PACKAGE: NOT YET READY FOR JOURNAL SUBMISSION.**

There are two viable publication scopes:

- **Full performance route:** close PAPER-A01-A09 and publish topology, proper ΔE-E, timing, optical response and held-out energy resolution together.
- **Narrow evidence-bounded route:** close A01/A02/A03/A05/A06, retain timing as the format-limited negative result, keep optical response explicitly simulation-only, and omit measured detector timing/absolute energy-performance claims.

The full route best matches the requested outline. The reviewer loop should be rerun after the P0 result files exist; "ready to publish" means no central numerical claim in the abstract or conclusions still carries a reviewer `BLOCK`.

## Final checklist for the next reviewer loop

- [ ] hardware BOM/source record complete;
- [x] 8×16/8×18 waveform lineage resolved as **distinct schemas** (`reports/studies/paper_a02_waveform_lineage/`; LUNARC raw authorising, 18-sample historical/non-authorising);
- [ ] run/trigger hardware table complete;
- [ ] production timing closes or is intentionally withheld;
- [x] issue-#618 proper DATA ΔE-E regenerated with uncertainty (`reports/paper_956_deltaE_E_20260812T103800Z/`, 2026-08-12);
- [x] full and data-matched MC ΔE-E regenerated with weights/ESS (same bundle; species-colour panels pending);
- [ ] material/selection response closure quantified;
- [ ] WLS fluorescence-yield and SiPM response status updated;
- [ ] held-out Edep reconstruction/resolution complete;
- [ ] every quantitative figure generated from tracked result files;
- [ ] claim ledger and wiki agree with manuscript wording;
- [ ] final bibliography passes reference verification;
- [ ] final humanization pass changes style only.
