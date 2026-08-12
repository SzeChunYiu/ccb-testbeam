# CCB test-beam paper: open atomic tasks and AI-session handoff

**Date:** 2026-08-12  
**Manuscript:** `chatgpt_todo/PAPER_DRAFT_CCB_TESTBEAM_20260812.md`  
**Evidence map:** `chatgpt_todo/PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md`

This queue is designed for later AI sessions to execute without inventing missing data or silently changing the paper's measurands. It extends, rather than replaces, `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md` and `chatgpt_todo/AI_SESSION_PICKUP_GUIDE_20260808.md`.

## Session contract

Before taking any paper atom:

1. Read `ATOMIC_RESEARCH_PROTOCOL.md`, `AI_SESSION_PICKUP_GUIDE_20260808.md`, this file, and the evidence matrix.
2. Pull latest `main` and record exact commit, submodule SHAs, dirty state and relevant issue state.
3. Re-check the canonical claim ledger. A closed GitHub issue is not sufficient to promote a claim if a later ADR or claim gate blocks it.
4. State the exact estimand before writing code. Examples: `sigma68(Δt_B4B6)` on a declared waveform schema, or `median[(Ereco-Edep)/Edep]` on held-out optical MC.
5. Bind raw inputs by path, bytes and SHA-256. If the data host is required, do not replace measured data with toy data to satisfy the task.
6. Use composite event identifiers. Never join cross-run data on `eventno` alone.
7. Keep DATA, MC truth, digitised MC and optical-model outputs separate until an explicit response transform is validated.
8. Run the four review passes from the project protocol: detector/physics, adversarial mechanism, statistics/validation, claims/provenance.
9. Update the result file first, then the claim ledger/evidence matrix, then manuscript wording. Never hand-edit a plot number into the paper.
10. If a task remains blocked, leave a falsifiable child atom instead of converting the blocker into an assumption.

## Priority map

`P0` atoms block a central manuscript performance statement or risk a wrong claim. `P1` atoms substantially strengthen the paper. `P2` atoms improve interpretation/documentation but do not block the core topology paper.

---

## PAPER-A01 [P0] Authoritative CCB stave and test-beam hardware record

**Question:** What hardware was physically installed, and which parts of the current source-bound geometry are simulation choices rather than measured construction facts?

**Why:** The repository contains a stale ~100×10×1 cm BC-408 narrative that conflicts with issue #796 and the current 50×5.18×2.0 cm extruded-polystyrene model. The paper cannot carry both.

**Required inputs:**

- issue #796/#797 supervisor comments;
- photos/CAD/build sheets/run log if present;
- channel map, SiPM carrier-board record, fibre grade and end treatment;
- target/stack survey or beam-line configuration note.

**Procedure:**

1. Build a hardware BOM table: component, installed value, evidence artifact, date, uncertainty/status.
2. Separate `MEASURED`, `DESIGN_SPEC`, `SIM_CONFIG`, and `UNKNOWN` fields.
3. Reconcile physical B-layer thickness. Issue #796 initially says "5 cm thickness" in its body, while the later hardware clarification says 2.0 cm along the particle path. Resolve from primary hardware evidence.
4. Verify which stack is called A/B in the run log and geometry, including angles.
5. Verify the one-fibre/one-end channel mapping to DAQ channels.

**Outputs:** `result.json`, `hardware_bom.csv`, source-hash manifest, proposed corrections to stale docs, regenerated Figure 1/2 metadata.

**Acceptance:** no conflicting dimensions/material names remain in publication surfaces; every exact hardware number has a primary source.

---

## PAPER-A02 [P0] Raw waveform product lineage and publication data manifest

**Question:** Which immutable waveform product authorises timing, amplitude and saturation results?

**Parent context:** #952/#953/#993/#1149 family.

**Known sources:** located real beam ROOT files under `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/`; historical 18-sample selected product used by S00/S03. The located raw product is 8×16 samples; the historical timing product declares 8×18.

**Procedure:**

1. On the data host, regenerate the complete content-addressed raw manifest using the current verified-stream consumer.
2. Identify exact 18-sample producer inputs, executable/source revision and output hashes.
3. For shared immutable events, compare all eight channels and all preserved sample words stage by stage.
4. Test candidate mechanisms for the extra two samples: true trailing samples, padding/constants, duplicated boundaries, circular-buffer reconstruction, cross-event words, separate acquisition mode.
5. If no reversible transform exists, version the two schemas separately and state which paper plots use which product.
6. Build a publication data manifest with per-run event counts, file SHA-256 and DAQ schema.

**Acceptance:** every timing/amplitude paper figure names a waveform schema and source hash; no implicit 16↔18 equivalence remains.

---

## PAPER-A03 [P0] Run inventory and trigger semantics closure

**Question:** What exactly changed between Sample I and Sample II at hardware level, and which runs belong to calibration versus analysis?

**Known config:** Sample-I calibration 31-37,39-42; Sample-I analysis 44-57; Sample-II calibration 64; Sample-II analysis 58-63,65.

**Procedure:**

1. Bind the run log and DAQ trigger configuration for every run 31-65.
2. Record beam species/energy, target, trigger counters/logical condition, thresholds, prescales and DAQ changes.
3. Explain excluded/missing runs 38 and 43 and the calibration role of run 64.
4. Compare data trigger semantics with `MC_TRIGGER_PROXY`; do not tune a proxy until hardware truth is known.
5. Create a table ready for the manuscript.

**Outputs:** `run_inventory.csv`, `trigger_contract.json`, Table 1 source file.

**Acceptance:** the words "coincidence" and "B-only" are backed by a hardware/run-log artifact rather than inherited prose.

---

## PAPER-A04 [P0] Production inter-stave timing resolution

**Question:** What timing resolution is identifiable from an authorising waveform product for stable single-component B-stave pulses?

**Do not start from a desired sub-ns number.** Issue #1059 shows that global-maximum CFD can retarget different pulse components as the fraction changes.

**Estimands:**

- pair residual central width `sigma68(Δt_ij)`;
- robust RMS and core fit width as secondary metrics;
- run-to-run spread;
- single-stave resolution only under a justified covariance model.

**Procedure:**

1. Use only the waveform product authorised by PAPER-A02.
2. Define pulse polarity, baseline, saturation, in-window peak and stable-component class before timing optimisation.
3. Compare leading edge, global CFD, prompt-component CFD/template and, if justified, matched-filter/OF timing.
4. For CFD, emit crossing/component diagnostics and reject or model component-switch events.
5. Fit time-walk correction on calibration runs only. Candidate form `t_corr=t_raw-c0-c1/A` is allowed only if residual closure supports it; compare alternatives without data snooping on held-out runs.
6. Apply geometry/particle TOF correction with uncertainty.
7. Evaluate B4-B6, B6-B8 and any other same-particle pair with enough clean events.
8. Report `sigma68`, RMS, Gaussian-core sigma if meaningful, tail fraction, bootstrap CI and per-run LORO spread.
9. Infer single-stave sigma only from an overconstrained covariance model or justified symmetry; do not divide a pair width by sqrt(2) by default.
10. Make residual-vs-amplitude and residual-vs-run closure plots.

**Required figures:** final Figure 6 plus appendix estimator comparisons.

**Acceptance:** stable pulse component, held-out correction closure, waveform schema, covariance assumptions and uncertainty are all explicit. If these fail, paper continues to report the format-limited negative result only.

---

## PAPER-A05 [P0] Production amplitude ΔE-E data plot

**Question:** What does the real B2/B4 amplitude topology show after current polarity, baseline, event-key and saturation rules?

**Procedure:**

1. Rebuild the selected pulse/event table from authorising data.
2. Assert uniqueness of `(file_id, run, event, stave)` before pivoting.
3. Produce B4 versus B2 amplitude for all relevant run families and separate Sample I/II panels.
4. Mark saturation explicitly. Repeat with saturated B2 events excluded as a sensitivity panel.
5. Report event count, Pearson and rank correlation with run-block bootstrap intervals.
6. Add B2/B4 marginals and conditional B4 distributions in B2 quantiles.
7. Extend to the B2/B4/B6/B8 stopping-depth vector; report how often the deepest selected stave is B2/B4/B6/B8.

**Acceptance:** figure can be regenerated from a result file; no `eventno`-only join; axes remain ADC unless PAPER-A09 provides a validated response.

---

## PAPER-A06 [P0] CCB material budget and data-matched MC closure

**Question:** Can the MC reproduce the B-stack stopping population once real passive material and the data-matched four-channel readout are included?

**Procedure:**

1. Start from the current geometry/systematics programme, not the historical 11.12 g/cm² value as an answer.
2. Bind all material components that a particle traverses before and between B layers.
3. Validate geometry overlaps and survey placement.
4. Propagate event weights and report effective sample size.
5. Map eight physical MC layers to the four analysed data channels without information leakage.
6. Apply the same trigger-proxy status, amplitude/threshold/saturation response and event selection as data once those components are validated.
7. Compare stopping-depth distribution, B2/B4 correlation, first-layer high-signal fraction and marginal shapes.
8. Scan material budget within source-bound uncertainty and report whether the sign of the B2-B4 correlation is robust.

**Acceptance:** either quantitative closure with uncertainty or an explicit, localized model discrepancy. Do not hide a discrepancy through a fitted arbitrary energy scale.

---

## PAPER-A07 [P0] Stage-resolved optical efficiency and light transport

**Question:** Where are photons lost between scintillation production and primary SiPM avalanches?

**Current block:** `ADR-WLS-FLUORESCENCE-YIELD-UNVERIFIED.md` disables absolute light-yield authorisation.

**Required counters per event:**

- deposited and visible energy;
- generated scintillation photons;
- photons entering each fibre region;
- WLS absorptions;
- WLS re-emissions;
- sensor-surface incidents by fibre/end;
- primary photon-triggered avalanches before crosstalk/afterpulse;
- final avalanches/charge after correlated noise.

**Procedure:**

1. Bind optical tables and exact Geant4/ccb-sipm-core revisions.
2. Replace or parameterise the unit WLS fluorescence-yield assumption using a source-bound measurement/literature contract. If only a bounded prior is defensible, propagate it as a nuisance rather than fixing it silently.
3. Scan hit position along the 50 cm stave and transverse position relative to both fibres.
4. Fit attenuation only over a range where the chosen model is justified; compare single/double exponential if data warrant.
5. Report stage ratios with binomial/weighted uncertainty where applicable, plus covariance when ratios share denominators.
6. Compare the physical F1+x channel to the other simulated control ends/fibre to quantify the information lost by one-fibre/one-end readout.

**Acceptance:** Figure 10 and a table that separates capture, transport and PDE efficiencies. `authorising_absolute_light_yield_claims=true` only if its source contract is satisfied.

---

## PAPER-A08 [P0] SiPM operating point, coupling and electronics response

**Question:** What S13360-3050CS response model corresponds to the CCB hardware?

**Open physics from ADR:** recovery law, charge-domain impulse normalisation, illumination footprint/coupler, correlated-noise distributions.

**Procedure:**

1. Locate/log bias voltage, temperature, front-end circuit, shaping/integration convention and any LED/dark calibration.
2. Bind PDE versus wavelength at the actual overvoltage, not a generic datasheet maximum.
3. Measure or source-bind gain and single-photoelectron charge in the charge domain.
4. Validate saturation/recovery using the actual illuminated-cell footprint.
5. Treat crosstalk/afterpulse parameters as nuisance models unless measured at the CCB operating point.
6. Produce a detector-response transfer function from primary photons/avalanches to the exact data observable (peak ADC or integrated charge).

**Acceptance:** optical MC can be converted into a data-like observable without phenomenological PE units or hidden peak-normalisation dependence.

---

## PAPER-A09 [P0] Held-out energy reconstruction and resolution

**Question:** What energy resolution follows from the simulated one-stave response, and what can be transferred to data?

**Primary estimand:** reconstruct Geant4 deposited energy `Edep` from a data-like signal. Incident kinetic energy is a different estimand and must be reported separately.

**Procedure:**

1. Ingest the existing calibration ROOT files (`/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid/` on fs10) or an immutable mirrored dataset.
2. Split events before fitting. Use energy-point and species holdout designs that test interpolation and transfer.
3. Establish baselines: linear PE/charge response, monotonic spline, physically motivated saturation inverse if needed. ML may be compared only after the simple baseline.
4. Reconstruct held-out Edep event by event.
5. Report median bias, `sigma68((Ereco-Edep)/Edep)`, RMS, tail fraction and coverage versus Edep, species and position.
6. Propagate PAPER-A07/A08 nuisance parameters. Show statistical-only and total model envelopes separately.
7. Test whether one common p/d calibration is sufficient. Species-specific tuning must be justified by a physical response difference rather than by truth-label convenience.
8. If fitting `sigma_E/E = a/sqrt(E) ⊕ b/E ⊕ c`, do so only after demonstrating that the energy grid identifies all retained terms.
9. After a validated data response exists, repeat with digitised MC and compare data distributions. Do not use the heuristic 92±28 ADC/MeV as the final calibration.

**Acceptance:** Figure 11 and Table 2 are generated from held-out predictions; all calibration/validation splits and nuisance scans are recorded.

---

## PAPER-A10 [P1] Quantify segmentation loss for ΔE-E/PID

**Question:** How much information is lost by reading only B2/B4/B6/B8 instead of the full physical B stack?

**Procedure:**

1. Use truth MC with all eight layers as the reference observable space.
2. Compare simple physics-motivated classifiers/estimators using 8 layers versus the data-matched four layers.
3. Metrics: p/d separation AUC or another preregistered metric, stopping-depth resolution, incident-energy resolution, calibration transfer.
4. Keep train/test split by run-family/MC production block to avoid leakage.
5. Prefer transparent baselines: dE/dx sequence likelihood, range/depth rule, linear/logistic model. ML is secondary.

**Acceptance:** one figure/table can support the manuscript statement that sparse segmentation limits classical ΔE-E, instead of leaving it qualitative.

---

## PAPER-A11 [P1] Citation and reference verification

**Procedure derived from `nature-ref-verifier`:**

1. Extract every reference from the final manuscript.
2. Resolve DOI where present and compare title, author list/order, year, journal, volume and pages/article number against publisher/Crossref/official source.
3. Mark `VERIFIED`, `CHECK`, `NEEDS_FIX`, `UNVERIFIABLE`.
4. For manufacturer pages, record access date and distinguish representative values from guaranteed specifications.
5. No citation is allowed to support a claim outside its documented scope.

**Current checked set:** seven references in the draft have been checked against official publisher/arXiv/Geant4/manufacturer sources. Repeat after any bibliography expansion.

---

## PAPER-A12 [P1] Documentation and stale-claim cleanup

**Question:** Which repository narrative files can mislead the next paper-writing session?

**Known conflicts to fix after the evidence gates settle:**

- stale BC-408 / ~100 cm stave description in `docs/academic_chapters/02_experimental_setup.md`;
- 540 ps / 0.68-0.75 ns timing language in `docs/academic_chapters/04_timing_analysis.md` unless relabelled historical/non-authorising;
- analytical `0.56%` total efficiency and assumed WLS/PDE values in `docs/stave_sim/STAVE_SIM_ENERGY_MODEL.md` unless clearly marked obsolete/non-authorising;
- any plot/caption using 246 ADC/MeV or presenting the gated 92±28 ADC/MeV proxy as a precision calibration;
- trigger wording that omits `MC_TRIGGER_PROXY`.

**Acceptance:** wiki/docs point to the claim ledger and the paper evidence matrix as the current publication truth surface.

---

## PAPER-A13 [P1] Final figure registry and publication package

1. Populate `paper/plot_crosswalk.csv` and `visualization/PLOT_MANIFEST.csv` with Figures 1-11.
2. Every quantitative figure reads a result file dynamically.
3. Embed result/config/input hashes in a sidecar or caption metadata.
4. Separate `ILLUSTRATIVE` schematics from quantitative figures.
5. Compile the LaTeX manuscript only after claim statuses in the evidence matrix are `GREEN` or explicitly framed limitations.

---

## PAPER-A14 [P2] Data release / Hugging Face mirror

The Hugging Face connector returned upstream HTTP 502 errors for dataset discovery on 2026-08-12, and web search did not identify a public HIBEAM/NNBAR CCB test-beam dataset. This is **not evidence that no dataset exists**.

**Known data locations from repository reports:**

- beam ROOT: `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/`;
- optical calibration MC: `/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid/` plus report artifacts.

**If a Hugging Face dataset is intended:**

1. obtain the exact dataset repository ID from the collaboration or data host;
2. verify that it contains the same files by SHA-256 before using it as a mirror;
3. publish dataset card fields: provenance, run selection, schema, detector mapping, licence/access policy, checksums, known 16/18-sample distinction;
4. never infer equivalence from file names alone.

---

## Suggested execution order

The critical chain is:

`A01/A02/A03` → `A04/A05` → `A06` → `A07/A08` → `A09` → `A10` → `A11/A12/A13`.

A05 can proceed in parallel with A04 after A02 establishes the authorising amplitude product. A07 and A08 should run in parallel but merge only at a defined primary-avalanche/charge boundary. A14 is independent unless the Hugging Face mirror becomes the publication data source.

## Manuscript promotion rule

Promote the draft from `chatgpt_todo/` into `paper/` only when:

- no reviewer `BLOCK` remains on the central claims;
- unresolved limitations are intentionally part of the paper's conclusion rather than hidden missing work;
- Figures 1-11 have an explicit `GREEN`, `YELLOW-as-limitation`, or removed status;
- the claim ledger agrees with the manuscript;
- references pass A11;
- a final humanization pass changes style only, not evidence or claim strength.
