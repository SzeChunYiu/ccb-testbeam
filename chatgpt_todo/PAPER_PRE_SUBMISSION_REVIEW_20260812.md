# CCB test-beam manuscript: simulated pre-submission review

**Date:** 2026-08-12  
**Draft under review:** `chatgpt_todo/PAPER_DRAFT_CCB_TESTBEAM_20260812.md`  
**Evidence matrix:** `chatgpt_todo/PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md`  
**Open analyses:** `chatgpt_todo/PAPER_OPEN_ATOMS_20260812.md`

## Review protocol

This is an internal, role-separated scientific review. It is not human peer review. The `nature-reviewer` workflow normally prefers mutually blind reviewers; this environment does not provide isolated reviewer contexts, so mutual blindness cannot be guaranteed. To reduce cross-role contamination, each report below uses a fixed remit, identifies the evidence it inspected, records the strongest alternative explanation, and gives an independent vote before the synthesis.

Three core reviewer roles are used:

- **Reviewer R1, detector and test-beam instrumentation:** experimental particle physicist with scintillator range-telescope, DAQ, timing and beam-test experience. Focus: what was physically measured, hardware configuration, trigger semantics and timing observability.
- **Reviewer R2, scintillator optics, Geant4 and SiPM response:** detector-simulation physicist with Geant4 optical processes, WLS fibres and SiPM digitisation experience. Focus: model fidelity, optical-stage identifiability and energy reconstruction.
- **Reviewer R3, statistics, reconstruction and claims:** statistical physicist/reconstruction reviewer. Focus: estimands, sample splitting, covariance, uncertainty, data/MC comparability, leakage and whether the manuscript verbs match the evidence.

A fourth synthesis lens, **claims/provenance editor**, checks that no result is promoted above the canonical claim ledger or later ADRs.

---

# Review cycle 1

## R1: detector and test-beam instrumentation

### Overall assessment

**Vote: MAJOR REVISION / BLOCK central detector-performance claims; ACCEPT the topology result and evidence-bounded paper structure.**

The draft has a defensible experimental story: the B-stack selected population changes strongly between the coincidence-like and B-only run families, and the paper no longer hides the fact that only four readout channels are available for the analysed B stack. The stave description also follows the newer hardware clarification rather than the stale ~1 m BC-408 narrative. Those are substantial improvements over the older documentation.

The paper is not yet ready to publish a detector timing resolution or an absolute range-stack energy resolution. The current raw waveform product is demonstrably unable to support the former, and the channel/trigger/material contracts are not yet strong enough for the latter.

### Evidence inspected

- issue #796 and #797 hardware/readout clarification;
- `docs/stave-geometry.md`;
- `geant4/configs/krakow.geoconf`;
- `configs/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.yaml`;
- `reports/SAMPLE_I_II_DATA_MC_REPORT.md` with its later `MC_TRIGGER_PROXY` gate;
- `reports/studies/data_side/REPORT.md`;
- issue #993 waveform-lineage discussion;
- issue #1059 CFD component-selection ambiguity;
- current evidence matrix.

### Major comments

1. **Hardware truth still needs one publication-grade source.** The current 50 × 5.18 × 2.0 cm stave is well supported by the supervisor clarification and source-bound geometry, but issue #796 initially contains a conflicting "5 cm thickness" phrase and an older academic chapter contains a much larger BC-408 bar. The manuscript is right not to average these descriptions. PAPER-A01 must resolve the installed hardware from a drawing, build record, photograph with dimensions, or other primary collaboration record.

2. **Trigger names must remain operational, not causal.** The data run families may be called coincidence and B-only when a run log proves that hardware condition. The MC split is currently only a first-layer charged-hit proxy. The draft correctly uses `MC_TRIGGER_PROXY`; this label should appear in every MC selection caption and table.

3. **The timing negative result is publishable; a sub-ns number is not.** The 8×16 raw data show a ~38 ns B4-B6 residual with multimodal/boundary peak positions. That result supports the statement that this waveform product is unsuitable for a precision-resolution measurement. It does not support an intrinsic 38 ns resolution. The draft handles this correctly.

4. **A future timing result needs an explicitly timed pulse.** Issue #1059 is not a small algorithmic detail. A global-maximum CFD can move from an early component to a later component as the fraction changes. Any final timing method must declare whether it times the prompt component, largest component, or a track-associated component. Optimising a fraction against residual width without component identity is unacceptable.

5. **Selected-pulse fractions are not detector efficiencies.** Sample-I B2 occupancy and saturation are properties of the selected population. The manuscript mostly uses this language correctly. Keep "fraction of selected pulses" and "selected-event topology" in plots and captions.

### Strongest alternative explanation

The Sample-I/Sample-II depth contrast could partly arise from trigger thresholds, waveform selection and B2 saturation rather than only from a different p/d mixture. The current MC truth gives a physically plausible species explanation, but the hardware-trigger response and identical data/MC selection are not yet closed.

### Falsifier

Reconstruct the full run/trigger contract from primary DAQ records, then apply a digitised trigger/selection response to MC. If the depth contrast remains after matching thresholds, saturation and the four-channel data view, the species/stopping interpretation becomes much stronger.

### Minor comments

- Prefer "source-bound configuration" to "geometry" when quoting the 109 cm parameter unless survey information is available.
- State the physical layer count and readout-channel count in the same paragraph whenever segmentation is discussed.
- A photograph of one stave/end board would materially improve the setup section if publication permissions permit.

---

## R2: scintillator optics, Geant4 and SiPM response

### Overall assessment

**Vote: MAJOR REVISION / BLOCK absolute optical-efficiency and detector energy-resolution claims; ACCEPT the optical MC as a model study.**

The draft makes the crucial distinction that the order-10 PE/MeV result is a property of the implemented optical hypothesis, not a calibrated detector measurement. That distinction must survive every abstract, caption and conclusion edit. The later WLS and SiPM ADRs supersede the older language that called this an absolute calibration.

The simulation programme is scientifically useful because it separates CCB event transport from single-stave optical transport. The next publication-level step is to expose stage-by-stage photon losses and to bind the WLS/SiPM nuisance parameters, not to fit one global efficiency.

### Evidence inspected

- `geant4/single_stave/` design as documented in `docs/stave-geometry.md`;
- issue #796 optical campaign summary;
- `docs/stave_sim/STAVE_SIM_ENERGY_MODEL.md`;
- `docs/adr/ADR-WLS-FLUORESCENCE-YIELD-UNVERIFIED.md`;
- `docs/adr/ADR-SIPM-PHYSICS-BLOCKED-WAVEA-LANE01.md`;
- `reports/1781181864.166832.35d806b2__s21_geant4_source_review/REPORT.md`;
- current SiPM provenance/status work on main;
- evidence matrix/open atoms.

### Major comments

1. **Do not publish the old 0.56% total efficiency.** It is assembled from an estimated WLS capture fraction and a generic PDE value. The later project gates correctly make absolute light yield non-authorising. The manuscript should use stage ratios once they exist.

2. **The Geant4 WLS default is a physics assumption, not Y-11 quantum-efficiency data.** A one-secondary re-emission default can make an internally reproducible optical chain while still biasing absolute PE yield. PAPER-A07 must source-bind or nuisance-scan the fluorescence yield.

3. **PDE must be operating-point specific.** The Hamamatsu product page can support sensor geometry and spectral-response context. It cannot, by itself, establish the CCB PDE at the actual overvoltage and temperature. The paper correctly avoids quoting a detector PDE. Keep that discipline.

4. **PE must have a charge-domain definition.** The SiPM ADR records that peak-normalised kernels can make `pe` phenomenological rather than an avalanche-charge unit. Energy reconstruction should preferably use primary avalanche count or an independently calibrated charge observable before moving to ADC peak amplitude.

5. **The optical campaign widths are not yet an energy-resolution curve.** The reported 8.9-20.8% values come from selected campaign points and an older summary. A publication result needs an event-level residual definition, a train/validation split and nuisance propagation. PAPER-A09 is correctly written around `Edep`, not incident kinetic energy, as the first estimand.

6. **Position dependence matters because only one end is read out.** With no two-ended charge asymmetry, attenuation is a direct energy nuisance. A position scan along the 50 cm stave is required before treating one common PE/MeV slope as position independent.

### Strongest alternative explanation

An apparent stable ~10 PE/MeV slope across the limited campaign grid could result from compensating assumptions: unit WLS re-emission, chosen optical surfaces, generic PDE and a particular coupling footprint. A global agreement in PE/MeV does not separately validate any one of these mechanisms.

### Falsifier

Record photon counts at each causal boundary, then vary one source-bound nuisance at a time. If different parameter combinations reproduce the same final PE yield but predict different WLS-absorption, sensor-incidence or position dependence, those intermediate observables identify which models are degenerate and what bench measurement is needed.

### Minor comments

- Keep Geant4 truth EDep, visible energy after quenching and sensor response as separate columns in the final table.
- A full optical efficiency should never be multiplied from marginal means if event-by-event correlations make that product differ from the ratio of totals.
- Document whether quoted uncertainties on PE campaign points are event spreads, standard errors or fit uncertainties before using the `±` notation in the final paper.

---

## R3: statistics, reconstruction and claims

### Overall assessment

**Vote: MAJOR REVISION / ACCEPT manuscript logic, BLOCK quantitative submission until uncertainty and held-out analyses are added.**

The manuscript is unusually careful about truth type and non-identifiability, which is appropriate here. The remaining statistical problem is not lack of sample size. It is that several useful numbers are fixed outputs without publication-grade uncertainty, and some historical analyses mix calibration, selection and evaluation populations.

### Evidence inspected

- `docs/claim_ledger.csv`;
- data-side ΔE-E and timing report;
- sample transfer configuration;
- S21 source review and later weighted-estimand context;
- issue #1059;
- evidence matrix/open atoms;
- manuscript references and claim wording.

### Major comments

1. **The ΔE-E correlations need grouped uncertainty.** `corr=+0.221` in 33,966 selected events is a useful point estimate. Final reporting should include a run-block bootstrap or other dependence-aware interval. An IID standard error would be too optimistic if event conditions vary across runs.

2. **The data/MC correlation sign is diagnostic, not a scalar goodness-of-fit.** The data are ADC amplitudes and the MC values are truth EDep with different selection. The manuscript correctly places them in separate panels. Do not report `Δcorr=0.754` as a calibrated discrepancy until the response and selection match.

3. **Weighted MC must propagate weights through the estimand.** The old CCB generator attaches angular cross-section weights. Any production MC histogram, correlation, fit or classifier must declare its weight treatment and effective sample size.

4. **Timing needs covariance-aware inference.** A pair residual does not identify two individual stave variances without additional assumptions or multiple overconstrained pairs. Avoid the default `sigma_pair/sqrt(2)` conversion. The manuscript explicitly says this; keep it.

5. **Calibration must be separated from validation.** The run config already distinguishes calibration/analysis populations. The final timing and energy-response fits should preserve that separation and report performance only on held-out runs/energy points.

6. **Energy resolution requires a single unambiguous denominator.** Start with `(Ereco-Edep)/Edep` for the single-stave optical MC. Incident kinetic energy and full-stack reconstructed energy are separate tasks. Do not combine them in one "energy resolution" number.

7. **Avoid significance language before the uncertainty model exists.** The current draft generally uses "different" or "diagnostic" rather than claiming a statistically significant MC disagreement. That is the right level.

### Strongest alternative explanation

Several apparent method improvements can be explained by selection and calibration leakage: choosing pulse classes, correction forms or nuisance settings using the same runs/energy points on which performance is reported. A large sample cannot cure this bias.

### Falsifier

Freeze estimator/selection/calibration on the declared calibration population, then evaluate once on held-out run blocks and held-out MC energy/species points. If the improvement transfers with dependence-aware intervals and nuisance scans, it is a robust performance result.

### Minor comments

- Every table should include `n_events` and, for data, `n_runs`.
- For saturation-masked ΔE-E sensitivity, report both retained fraction and change in topology metric.
- If a response curve is non-Gaussian, use `sigma68` plus tail fraction rather than only a Gaussian sigma.

---

# Cycle-1 synthesis

## Points of agreement

All three reviewers agree on four conclusions.

1. **The beam-data topology result is the current strongest empirical result.** The Sample-I/Sample-II depth and amplitude differences are suitable for the core results section once run/trigger provenance and grouped uncertainties are tightened.
2. **The timing section should presently be a method plus negative result.** A detector timing resolution remains blocked; the ~38 ns raw residual is a format limitation, while historical sub-ns values are simulation/toy or non-authorising diagnostics.
3. **The optical campaign belongs in the paper as model-dependent MC.** It gives useful scale and design insight but not a measured absolute efficiency.
4. **The missing energy-resolution result is tractable from existing MC.** PAPER-A09 is a high-value next analysis because the raw calibration ntuples already exist and the estimand can be defined cleanly as held-out reconstruction of Geant4 deposited energy.

## Required revision to the paper's central claim

The paper should not be framed as a complete detector characterisation. Its defensible central argument is:

> The CCB beam data demonstrate the stopping-versus-penetrating topology of the sparsely read out B range stack, while a layered Geant4 response programme identifies the additional waveform, passive-material and optical/electronics constraints required before timing and absolute energy performance can be quoted.

This wording matches the current evidence and gives the remaining analyses a coherent purpose.

## Cycle-1 decision

**Not submission-ready as a quantitative detector-performance paper.**  
**Manuscript structure and evidence discipline are ready for collaboration circulation.**

Submission would be scientifically premature if it included a detector timing resolution, absolute light-collection efficiency, or detector energy resolution before the corresponding P0 atoms close. A narrower topology-and-model-validation paper could be submitted sooner if the collaboration intentionally removes those blocked performance claims rather than leaving placeholders.

---

# Editorial revision pass using `humanizer`

The draft was checked against the requested humanization rules with the constraint that scientific meaning and claim strength cannot change. The technical manuscript uses a neutral voice, so the correct human style is plain and precise rather than conversational.

The following patterns are prohibited in the final text:

- inflated phrases such as "groundbreaking", "pivotal", "crucial demonstration" or claims that the work "underscores" a broad significance;
- vague attribution such as "experts believe" or "studies show" without a named source;
- `-ing` clauses used to imply a causal conclusion that the data do not establish;
- synonym cycling for the same detector object;
- decorative rule-of-three lists when two or four actual items exist;
- chatbot artifacts such as "this highlights" or "it is important to note";
- em/en-dash punctuation as a stylistic crutch in new prose;
- passive constructions that hide who selected, fitted or simulated an observable when naming the actor improves reproducibility.

### Concrete wording decisions retained for the final manuscript

- Use **"model-dependent optical response"**, not "light-yield calibration", for the current PE/MeV campaign.
- Use **"format-limited timing residual"**, not "timing resolution", for the 8×16 raw result.
- Use **"selected-pulse fraction"**, not "efficiency", for the B2/B4/B6/B8 data counts.
- Use **"source-bound configuration"**, not "measured geometry", for the 109 cm / arm-angle values until survey evidence exists.
- Use **"diagnostic data/MC topology difference"**, not "MC failure at N sigma", for the present B2-B4 correlation-sign difference.
- Avoid the phrase "limitations strengthen the paper". State directly which design or calibration action follows from each limitation.

No factual number, citation or uncertainty is added by the humanization pass.

---

# Review cycle 2: readiness after evidence-bounded revision

Cycle 2 evaluates the manuscript as it is now intended to read: blocked detector-performance claims are withheld; the existing optical numbers are explicitly model-dependent; the timing section reports a negative data-format result; the core empirical claim is the trigger-dependent stopping topology.

## R1 second vote

**ACCEPT WITH REQUIRED PRE-SUBMISSION EVIDENCE for the topology paper; BLOCK any added detector timing number until PAPER-A02/A04 close.**

The narrative no longer depends on the old sub-ns timing claim. The main remaining experimental requirement is publication-grade hardware/run provenance and a regenerated current ΔE-E/depth figure from the authorising data product.

## R2 second vote

**ACCEPT WITH REQUIRED PRE-SUBMISSION EVIDENCE for a model-study optical section; BLOCK the words "absolute efficiency" or "detector energy resolution" until PAPER-A07/A08/A09 close.**

The paper can show the existing PE/MeV campaign points if every caption states the model status and the later ADR gate. A stronger paper should complete the stage-efficiency and held-out energy-reconstruction studies before submission.

## R3 second vote

**ACCEPT WITH REQUIRED PRE-SUBMISSION EVIDENCE after grouped uncertainty is added to the main data figures.**

The central claims are now appropriately bounded. The remaining statistical requirements are executable rather than conceptual: run-block intervals, weighted MC estimands, held-out reconstruction and explicit counts/selection flow.

## Synthesis second vote

**TEXT/ARGUMENT: READY FOR COLLABORATION REVIEW.**  
**SCIENTIFIC NUMERICAL PACKAGE: NOT YET READY FOR JOURNAL SUBMISSION.**

The manuscript can become submission-ready in either of two scientifically coherent ways:

- **Full performance route:** complete PAPER-A01 to A09, then publish topology, timing, optical transport and held-out energy resolution as a unified detector-characterisation paper.
- **Narrow route:** complete A01/A02/A03/A05/A06, keep timing as the format-limited negative result and optical response explicitly simulation-only, and remove any promise of a measured detector timing/energy resolution from title/abstract/conclusions.

The full route is preferred because it directly matches the requested paper outline and uses already available simulation infrastructure. The review should be rerun after the P0 result files exist. "Ready to publish" should mean the reviewers no longer need to qualify central numerical claims with a BLOCK, not merely that the prose is polished.

---

# Author checklist before final reviewer loop

- [ ] PAPER-A01 hardware BOM and source record complete.
- [ ] PAPER-A02 authorising waveform/data manifest complete.
- [ ] PAPER-A03 trigger/run inventory complete.
- [ ] PAPER-A04 either produces an authorising timing result or the paper intentionally retains the negative-result-only timing section.
- [ ] PAPER-A05 current ΔE-E/depth data result with run-block uncertainty complete.
- [ ] PAPER-A06 data-matched, weighted MC material/selection closure complete or residual mismatch quantified.
- [ ] PAPER-A07/A08 optical/SiPM chain either calibrated enough for absolute response or explicitly remains model-dependent.
- [ ] PAPER-A09 held-out Edep reconstruction and resolution complete.
- [ ] Figure registry regenerates every quantitative number from result files.
- [ ] Claim ledger agrees with manuscript wording/status.
- [ ] Final reference verifier reports no `NEEDS_FIX` entries.
- [ ] Final humanization pass changes style only and preserves all evidence qualifiers.
