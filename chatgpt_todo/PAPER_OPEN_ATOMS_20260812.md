# CCB test-beam paper: open atomic tasks and AI-session handoff

**Date:** 2026-08-12  
**Manuscript:** `chatgpt_todo/PAPER_DRAFT_CCB_TESTBEAM_20260812.md`  
**Evidence matrix:** `chatgpt_todo/PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md`  
**Review:** `chatgpt_todo/PAPER_PRE_SUBMISSION_REVIEW_20260812.md`

This queue extends `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md` and `AI_SESSION_PICKUP_GUIDE_20260808.md`. It does not replace the concurrently active SiPM/provenance lane in `ACTIVE_TASK.md`.

## Session contract

Before taking an atom:

1. Read the atomic research protocol, AI pickup guide, paper draft, evidence matrix and this queue.
2. Pull latest `main`; record exact superproject/submodule SHAs and dirty state.
3. Search open and closed issues before creating a new one. Closed software-remediation issues can still leave a physics atom blocked; #993 and #1088 were reopened for this reason.
4. Define the estimand before coding. Do not optimise an undefined physical quantity.
5. Bind raw inputs by immutable path/file identity, byte count and SHA-256.
6. Use composite event identities. Never join cross-run samples on `eventno` alone.
7. Keep DATA, truth MC, digitised MC and optical-model outputs separate until a validated response transform connects them.
8. Run four passes on every result: detector/physics, adversarial mechanism, statistics/validation, claims/provenance.
9. Update result files and claim status before changing manuscript numbers.
10. If external evidence is absent, terminate as `BLOCKED_EXTERNAL` with a falsifiable missing-input contract rather than inventing a parameter.

## Priority chain

`A01/A02/A03` → `A04/A05` → `A06` → `A07/A08` → `A09` → `A10` → `A11/A12/A13`.

A05 can proceed in parallel with A04 once A02 identifies the authorising amplitude waveform/product. A07 and A08 can proceed in parallel but must meet at an explicit primary-avalanche/charge boundary.

---

## PAPER-A01 [P0] Authoritative hardware/BOM and CCB layout

**Question:** What was physically installed, and which values are only simulation configuration?

**Known conflict:** issue #796 begins with a conflicting `5cm thickness` phrase; later hardware clarification and current source-bound model give 50 × 5.18 × 2.0 cm extruded polystyrene. An older academic chapter describes a ~1 m BC-408 stave.

**Required work:**

- locate CAD/build sheet/photo/channel map/fibre record/SiPM board record/target record;
- build `hardware_bom.csv` with fields `quantity,value,unit,evidence_path,evidence_sha,status={MEASURED,DESIGN_SPEC,SIM_CONFIG,UNKNOWN}`;
- verify B/A naming and physical angles from run/hardware record;
- verify one-fibre/one-end channel mapping;
- reconcile all stale narrative dimensions/material names.

**Acceptance:** every exact hardware number in the paper has a primary collaboration source or is explicitly labelled in `paper/hardware_bom.csv` with status `MEASURED`, `DESIGN_SPEC`, `SIM_CONFIG`, or `UNKNOWN_EXTERNAL`.

---

## PAPER-A02 [P0] Publication waveform/data lineage

**Parent:** reopened #993 plus #952/#953/#1149 lineage work.

**Question:** Which immutable waveform product authorises amplitude and timing figures, and what is the relationship between 8×16 raw and 8×18 historical timing products?

**Procedure:**

1. On data host regenerate complete raw manifest for all paper runs with current verified-stream primitives.
2. Identify exact 18-sample producer, source revision and output hashes.
3. For common immutable events compare all 8×16 preserved words stage by stage and analyse the two disputed 18-sample positions separately.
4. Falsify padding, duplicated boundary words, circular-buffer reconstruction, cross-event contamination and separate acquisition-mode hypotheses.
5. If no exact transform is demonstrated, version products as distinct schemas and quarantine cross-schema timing transfer.
6. Create a result-lineage table mapping every paper data figure to source file/schema/hash.

**Acceptance:** #993 scientific criteria **pass** as DISTINCT_SCHEMAS (`reports/studies/paper_a02_waveform_lineage/`). LUNARC 8×16 raw is authorising; 18-sample timing stays historical/non-authorising.

---

## PAPER-A03 [P0] Run inventory and trigger hardware contract

**Current analysis grouping:**

- Sample-I calibration: 31-37,39-42
- Sample-I analysis: 44-57
- Sample-II calibration: 64
- Sample-II analysis: 58-63,65

**Question:** What exact hardware trigger, threshold/prescale and DAQ state defines each run?

**Outputs:** `run_inventory.csv`, `trigger_contract.json`, publication Table 1.

**Acceptance:** data words "coincidence" and "B-only" are backed by run/DAQ evidence. MC remains `MC_TRIGGER_PROXY` until hardware response is modelled.

---

## PAPER-A04 [P0] Production inter-stave timing

**Parents:** #993 closed DISTINCT_SCHEMAS; #1059 closed (software binding + format-limited negative result).

**Status (2026-08-12):** Lane 05 delivers deterministic two-pulse fraction-transition controls (`scripts/cfd_fraction_transition.py`), component-assignment diagnostics in `scripts/real_data_cfd_timing.py`, saturation/recovery selector sensitivity tests (#1277/#1278), clean single-pulse controls, and leave-one-run-out template validation (#1061). Real-data CFD fraction-transition study may proceed only on authorising **8×16** LUNARC schema (#993 closed DISTINCT_SCHEMAS); 18-sample historical timing remains non-authorising. Same-sample minimum `sigma68` is exploratory only (#1062).

**Primary estimands:** pair residual `sigma68(Δt_ij)`, RMS/core/tail, run spread; single-stave variance only through justified covariance inference.

**Procedure:**

1. Use only the authorising waveform schema from A02.
2. Freeze polarity, baseline, saturation, pulse-window and stable-component selection before optimiser tuning.
3. Compare leading-edge, global CFD, prompt-component CFD/template and other justified estimators.
4. CFD diagnostics must report crossing bracket, peak/component identity and fraction-switch population.
5. Fit time-walk only on calibration runs; validate on held-out runs with residual mean/width versus amplitude.
6. Apply TOF correction with geometry/particle uncertainty.
7. Analyse multiple pairs where possible to identify covariance, not default to `sigma_pair/sqrt(2)`.
8. Report grouped bootstrap intervals and LORO/run dependence.

**Acceptance:** every timing result identifies the physical pulse component and source waveform. If not, keep the present ~38 ns 8×16 result only as `FORMAT-LIMITED / NOT DETECTOR RESOLUTION`.

---

## PAPER-A05 [P0] **Correct production amplitude ΔE-E**

**Status (2026-08-12):** **#956 closed (primary).** Producer `scripts/single_stave/paper_956_deltaE_E_publication.py`; bundle `reports/paper_956_deltaE_E_20260812T103800Z/` (LUNARC mirror). Section 7 and P-027–P-033 updated. Remaining follow-ups: species-colour MC panels, beam-energy sensitivity scan.

### Data definition

`ΔE_data = amplitude(B2)`  
`E_data = amplitude(B4) + amplitude(B6) + amplitude(B8)`

### Data-matched MC definition

`ΔE_MC_4 = Edep(B2)`  
`E_MC_4 = Edep(B4) + Edep(B6) + Edep(B8)`

### Full MC truth definition

`ΔE_MC = Edep(first B layer / B2 analogue)`  
`E_MC = sum(Edep in every downstream physical B-stack layer available in MC)`

**Procedure:**

1. Rebuild event table from authorising data product; assert uniqueness of `(file_id,run,event,stave)`.
2. Produce Sample-I and Sample-II data hexbin/density panels with identical axes.
3. Mark B2 saturation and repeat with saturated B2 events removed/flagged.
4. Report event/run counts, median/16-84% ranges, rank/Pearson or preregistered topology statistics with run-block bootstrap intervals.
5. Produce full-MC and four-readout MC panels separately for proton, deuteron, p+d colour-coded and all species.
6. Propagate MC weights and report `Σw`, `Σw²`, ESS.
7. Keep the existing B2-B4 `n=33,966, corr=+0.221` result only as a **two-channel diagnostic** with its own grouped uncertainty. It is not ΔE-E.
8. Produce deepest-active/reach distributions using explicit threshold-comparison semantics and link existing threshold/stopping-proxy issues where relevant.

**Acceptance:** Figure 7/8 implement issue #618 exactly and are regenerated from result files, with DATA axes labelled ADC amplitude proxies.

---

## PAPER-A06 [P0] Material budget and data-matched MC closure

**Question:** Does the stopping/ΔE-E topology close when real passive material, event weights, trigger proxy and four-readout response are treated consistently?

**Procedure:**

- bind all material before/between B layers from hardware evidence;
- run overlap/survey checks and staged material nuisance scans;
- map eight physical MC layers to the four data readouts without pretending missing layers are zero energy;
- use correct ΔE-E definitions from A05;
- compare stopping/reach distributions, proper downstream-sum ΔE-E, B2 saturation/high-signal fraction and secondary B2-B4 diagnostic;
- report weighted goodness-of-fit and ESS where identifiable;
- do not fit an arbitrary energy scale merely to conceal a geometry/selection discrepancy.

**Acceptance:** quantitative closure with uncertainty, or a localised residual discrepancy that remains explicit in the paper.

---

## PAPER-A07 [P0] Stage-resolved optical efficiency

**Parent:** reopened #1088 plus related optical/provenance atoms.

**Question:** Where are photons lost between scintillation production and primary avalanches?

**Required per-event counters:**

- `Edep`, visible/quenching output;
- generated scintillation photons;
- photons entering fibre regions;
- WLS absorption interactions;
- WLS emitted secondaries;
- sensor incidents per fibre/end;
- primary photon-triggered avalanches;
- final avalanches/charge after correlated noise.

**Procedure:**

1. Bind exact Geant4 optical tables and submodule revisions.
2. Resolve #1088 with a source-bound fluorescence-yield/multiplicity model or explicit bounded nuisance. Software fail-closed labelling alone is not physics closure.
3. Scan hit position along 50 cm and transverse position relative to fibres.
4. Quantify capture, transport and PDE ratios with uncertainty/covariance.
5. Compare physical F1+x to simulated unused fibre/ends.

**Acceptance:** stage table/Figure 10; absolute light-yield language remains blocked unless #1088 physics contract authorises it.

---

## PAPER-A08 [P0] CCB SiPM operating point/coupling/electronics transfer

**Question:** What response maps sensor photons or primary avalanches to the beam-data observable?

**Need:** bias/temperature, PDE at operating point, coupling footprint, gain/single-avalanche charge, recovery, saturation, correlated noise, front-end shaping and digitiser convention.

**Acceptance:** a charge-domain, provenance-bound transfer to the exact paper data observable. Generic datasheet PDE maxima and phenomenological peak-normalised `pe` units are not sufficient.

---

## PAPER-A09 [P0] Held-out deposited-energy reconstruction and resolution

**Question:** What is the single-stave resolution for reconstructing Geant4 deposited energy from the simulated detector response?

**Raw MC location known from issue #796:** `/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid/` plus tracked report artifacts.

**Primary residual:**

`r = (Ereco - Edep) / Edep`

**Procedure:**

1. Bind/mirror calibration ntuples by SHA-256.
2. Split before fitting; test held-out energy points/species/position.
3. Start with transparent response models (linear/monotonic/saturation inverse). ML is secondary.
4. Report median bias, `sigma68`, RMS, tail fraction and coverage versus Edep.
5. Propagate A07/A08 nuisance parameters; separate statistical spread from model envelope.
6. Test one common proton/deuteron calibration before allowing species-dependent calibration.
7. Do not use 92±28 ADC/MeV as the final response and never resurrect 246 ADC/MeV.

**Acceptance:** Figure 11/Table 2 from frozen held-out predictions. **Status (2026-08-12):** initial closure delivered in `reports/paper_a09_heldout_edep_reconstruction/` on the five-point SHA-256-bound grid; optical/SiPM nuisance envelope remains blocked pending A07/A08.

---

## PAPER-A10 [P1] Quantify segmentation loss: eight physical layers vs four readouts

**Question:** How much dE/dx/PID/range information is lost because alternating physical B layers are missing from the analysed readout?

**Motivation:** issue #879 reports that apparent ΔE-E pointing direction can change with which alternating stave set is observed.

**Procedure:**

- compare full eight-layer MC with data-matched B2/B4/B6/B8 view;
- shift the readout phase (odd/even physical layers) as a controlled ablation;
- scan small source-bound incident-energy/material variations;
- compare proper downstream-sum ΔE-E topology, stopping-depth accuracy and simple p/d separation;
- use transparent physics baselines before ML.

**Acceptance:** quantify, rather than merely state, why sparse segmentation limits the beam-test ΔE-E observable.

---

## PAPER-A11 [P1] Final reference verification

Apply `nature-ref-verifier` after the bibliography is frozen: DOI resolvability, title, authors/order, year, journal, volume/pages/article number, and source scope. Manufacturer values require access date and `representative/specification` language where applicable.

---

## PAPER-A12 [P1] Wiki/documentation stale-claim cleanup

Audit and correct at least:

- stale ~1 m BC-408 setup description;
- historical sub-ns timing wording that reads like beam-data performance;
- old analytical 0.56% optical efficiency;
- any 246 ADC/MeV production text or precision interpretation of 92±28;
- trigger prose that drops `MC_TRIGGER_PROXY`;
- any page that calls B2-versus-B4 the canonical ΔE-E plot;
- WIKI status rows that conflict with the current claim ledger.

The wiki should link the claim ledger and paper evidence matrix as current publication truth surfaces.

---

## PAPER-A13 [P1] Figure registry and LaTeX publication package

- Populate the plot/table crosswalks for Figures 1-11.
- Every quantitative figure reads a result file dynamically.
- Store config/input/result hashes and selection/uncertainty metadata.
- Keep `ILLUSTRATIVE` schematics separate from quantitative results.
- Promote the manuscript from `chatgpt_todo/` to `paper/` only after central reviewer BLOCKs are resolved or intentionally removed from the paper scope.

---

## PAPER-A14 [P2] Publication data mirror / Hugging Face

The Hugging Face connector returned upstream 502 errors during dataset discovery on 2026-08-12, and the supplementary web search did not identify a CCB/HIBEAM public dataset repository. This is not evidence that none exists.

Known source locations:

- beam ROOT: `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/`
- optical calibration MC: `/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid/`

If a Hub dataset is intended, obtain the exact repository ID from the collaboration/data host, then prove every mirrored file by SHA-256. The dataset card must document provenance, run selection, waveform schema, detector mapping, licence/access policy and the unresolved/resolved 16/18-sample distinction.

## Promotion rule

The full performance paper becomes submission-ready only when the reviewer loop has no unresolved `BLOCK` on a numerical claim that remains in the abstract/conclusions. A narrower topology/model paper may proceed with timing and absolute optical/energy performance explicitly withheld, but the correct ΔE-E definition from issue #618 is mandatory in either scope.
