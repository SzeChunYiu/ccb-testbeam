# Chapter 11: Open Questions and Future Work
> **REVIEW_STATUS: EDITORIAL_REVIEWED** (AI role-separated nature-reviewer-style lenses; not independent human peer review). Scope: readability/structure only. Does **not** imply SOURCE_VERIFIED, EXECUTED_REPRODUCED, or CLAIM_AUTHORIZED. Open factual blockers remain tracked in GitHub issues / claim ledger. Contract: `docs/contracts/REVIEW_STATUS_TAXONOMY.json` / `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md`.


## Abstract

The CCB test-beam analysis programme has addressed the primary physics goals of timing resolution characterisation and pile-up rate determination, with Monte Carlo validation providing truth-bridged assessment of every major claim. This chapter catalogues the open questions that remain, ranked by severity from blocking (must fix before publication) to low (completeness items). Each gap is traceable to a specific study and includes a concrete action plan for resolution.

---

## 1. Blocking Issues

### GAP-01: Stopping-Depth Monte Carlo Failure (BLOCKING)

**Severity:** Blocks quantitative MC-based acceptance corrections.

**Source:** MV3 stopping-depth profile comparison (chi^2/ndf = 68,269).

**Finding:** The GEANT4 geometry overestimates the fraction of particles reaching deep staves (B6, B8) by a factor of 10. The root cause is missing upstream material budget: the target support structure, beam window, trigger scintillators, and inter-stave absorber layers, estimated at 8-10 g/cm^2 total.

**Action:** Update the GEANT4 geometry file with full material specification including all passive elements between the target and the B-stack entrance. Regenerate the 1M-event Monte Carlo sample. Rerun MV3 with the updated geometry. Target: reduce chi^2/ndf below 5 (qualitative agreement) or below 2 (quantitative agreement).

**Impact if unresolved:** All quantitative stopping-depth claims from Monte Carlo are unreliable. B8 trigger efficiency calibration cannot be MC-anchored. The PSTAR range-energy method (Chapter 7) cannot be validated for deep-stopping particles.

---

## 2. High-Impact Issues

### GAP-02: Timewalk Monte Carlo Tension (HIGH)

**Severity:** Prevents reporting of timewalk-corrected sigma_68 with MC validation.

**Source:** MV4 timing comparison (pull = 2.68 sigma for timewalk-corrected resolution).

**Finding:** The digitizer CFD model uses B/sqrt(ADC) instead of the physically correct B/amplitude parametrisation, producing an inverted timewalk correction in the Monte Carlo.

**Action:** Code fix in `src/ccb_mc_validation/digitizer/pipeline.py` or the CFD stage: replace the B/sqrt(ADC) term with B/amplitude. Rerun MV4 with the corrected digitizer. Expected result: timewalk-corrected pull < 2 sigma.

**Impact if unresolved:** Timewalk-corrected sigma_68 cannot be reported as MC-validated. The raw timing (pull = 1.05 sigma) already passes, so the uncorrected timing resolution is validated.

### GAP-03: Digitizer Gain Uncertainty (HIGH)

**Severity:** Dominant systematic for deuteron fraction and energy-dependent quantities.

**Source:** MV0 digitizer calibration (245.6 plus or minus 73.7 ADC/MeV, 30% systematic).

**Finding:** The gain calibration uses a single calibration point (Sample II B2 median). The uncertainty arises from single-point calibration (15%), digitizer model approximations (10%), and missing forced-trigger pedestal data (10%).

**Action:** (1) Acquire forced-trigger pedestal data in the next beam run (reduces baseline uncertainty to 5%). (2) Perform per-stave gain calibration using duplicate-readout or GEANT4 truth per stave. (3) Include Birks quenching in the digitizer model to correct for high-dE/dx light suppression. Target: reduce gain uncertainty to 10-15%.

**Impact if unresolved:** 30% energy-scale uncertainty propagates into all ADC-to-MeV conversions.

---

## 3. Medium-Impact Issues

### GAP-04: Two-Pulse ML Failure Rate (MEDIUM)

**Severity:** Gates ML adoption for production two-pulse recovery.

**Source:** S11 two-pulse decomposition comparison.

**Finding:** ML achieves better time RMS (9-11 ns vs 13-18 ns for template fit) but higher failure rate (0.295 vs 0.168). No truth-labelled overlay Monte Carlo exists to characterise ML failure modes.

**Action:** Extend MV5 to generate truth-labelled overlapping waveforms by superposing digitised single-particle pulses with known time separations and amplitudes. Train and evaluate ML models on this labelled dataset. Characterise failure modes as a function of time separation, amplitude ratio, and particle species.

**Impact if unresolved:** ML two-pulse recovery cannot be adopted for production. Conventional template fit remains the default.

### GAP-05: Two-Ended Timing Projection (MEDIUM)

**Severity:** The sqrt(2) projection for two-ended timing improvement is unvalidated.

**Source:** S05d two-ended covariance study.

**Finding:** The one-ended timing resolution is dominated by position-dependent WLS propagation delay (0-5.9 ns variation). Two-ended readout averages the two end times, cancelling the position dependence to first order and projecting a sqrt(2) improvement. This projection assumes uncorrelated end measurements.

**Action:** Measure the correlation between the two ends using A/B stack coincidence events (where the same particle crosses both stacks, providing an independent position constraint) or dedicated split-readout channels in a future beam test.

**Impact if unresolved:** The two-ended timing projection remains an upper-bound estimate rather than a validated value.

---

## 4. Low-Impact Issues

### GAP-06: CFD/OF Parameter Scan (LOW)

**Finding:** CFD fraction (20%) and optimal filter window were chosen heuristically. No systematic grid search exists.

**Action:** Parameter sweep: CFD fraction 10-50% in 5% steps, OF window 3-18 samples. Confirm 20% is near-optimal.

### GAP-07: Gaussian-Core Fit Quality (LOW)

**Finding:** Gaussian-core fits to residual distributions do not report chi^2/ndf.

**Action:** Add chi^2/ndf and tail fraction to all timing residual fit reports.

### GAP-08: Absolute TOF Scale (LOW)

**Finding:** No independent time-of-flight reference (TPC, trigger scintillator cross-check) exists.

**Action:** Cross-check TOF against TPC track length divided by expected velocity, or against trigger scintillator coincidence timing.

### GAP-09: Stave-to-Stave Calibration (LOW)

**Finding:** MV0 gain is calibrated on B2 only; inter-stave variation (plus or minus 10%) is assumed, not measured.

**Action:** Measure per-stave gain using duplicate-readout or GEANT4 truth per stave.

---

## 5. Dependency Graph

The open questions form a dependency graph:

- GAP-01 (geometry update) is independent and can be addressed in parallel with all other gaps.
- GAP-02 (timewalk fix) depends on the digitizer code change but not on new data or MC.
- GAP-03 (gain uncertainty) depends on new beam data (forced-trigger pedestal) and is gated by the next beam run.
- GAP-04 (ML failure rate) depends on MV5 extension and can be addressed with existing simulation infrastructure.
- GAP-05 (two-ended timing) depends on new beam data with split-readout configuration.

The blocking and high-impact items (GAP-01, GAP-02, GAP-03) must be resolved before the analysis can be considered publication-ready. The medium and low items are completeness issues that do not affect the validity of the existing physics claims.

## 6. Recommended Next Actions

In priority order, the recommended sequence of actions to close the remaining open questions is:

1. **Fix MV4 timewalk (GAP-02) — immediate, code change only.** This is the highest-return action: a one-line change from B/sqrt(ADC) to B/amplitude in the digitizer CFD stage resolves the only remaining tension in the timing validation programme. No new data or MC production required. Estimated effort: 1 day.

2. **Update GEANT4 geometry (GAP-01) — requires MC regeneration.** Add the missing material budget (target support, beam window, trigger paddles, inter-stave absorbers) to the GEANT4 geometry file. Regenerate the 1M-event sample. Rerun MV3. Estimated effort: 2-4 weeks (geometry update, validation, MC production on LUNARC).

3. **Extend MV5 for truth-labelled overlay (GAP-04) — simulation only.** Generate synthetic overlapping waveforms by superposing digitised single-particle pulses with known time separations and amplitudes. Train and evaluate ML models on this labelled dataset. Characterise failure modes. Estimated effort: 1-2 weeks.

4. **Acquire forced-trigger pedestal data (GAP-03) — requires new beam run.** Include forced-trigger runs in the next CCB beam time. This reduces the gain uncertainty from 30% to 10-15%. Combined with per-stave calibration, this is the single most impactful data-taking improvement. Estimated effort: 1 day of beam time.

5. **Perform CFD/OF parameter scans (GAP-06) — completeness.** Systematic grid search over CFD fraction (10-50%) and OF window (3-18 samples). Confirm 20% is near-optimal. Estimated effort: 1-2 days.

6. **Add chi^2/ndf to timing fits (GAP-07) — reporting completeness.** Add goodness-of-fit metrics to all timing residual reports. Estimated effort: 0.5 days.

7. **Cross-check absolute TOF (GAP-08) — completeness.** Use TPC track length or trigger scintillator coincidence to validate the absolute time-of-flight scale. Estimated effort: 1-2 days.

8. **Measure stave-to-stave gain variation (GAP-09) — completeness.** Use duplicate-readout or GEANT4 truth per stave to calibrate inter-stave gain differences. Estimated effort: 2-3 days.

9. **Validate two-ended timing projection (GAP-05) — requires new beam run.** Instrument both ends of selected WLS fibres and measure the correlation between the two end times. Replace the sqrt(2) projection with a measured factor. Estimated effort: 1-2 days of beam time plus analysis.

## 7. Publication Readiness Assessment

The analysis programme currently meets the following publication-readiness criteria:

- **Reproducibility:** The selected-pulse table is reproduced with exact fidelity (S00, SHA256-verified). The digitizer configuration is version-controlled. The pipeline is executable on LUNARC with SLURM job scripts.
- **MC validation:** Every physics claim carries an explicit MC validation verdict (MV0-MV6). Where the MC fails (MV3 stopping-depth, MV4 timewalk), the root cause is diagnosed and documented.
- **Methodological rigour:** The three leakage controls (target shuffle, LORO, event-block shuffle) are defined, applied, and documented. The CORRECTED studies are published as negative findings.
- **Systematic uncertainties:** Quantified for all major physics quantities. The dominant systematics (digitizer gain 30%, stopping-depth model 5%) are acknowledged and their resolutions planned.

The outstanding items before submission to a peer-reviewed journal are: GAP-01 (geometry update, blocking for MC acceptance corrections), GAP-02 (timewalk fix, high, code-only), and GAP-03 (gain uncertainty, high, requires new beam data). Chapters 2-10, which document the current state of the analysis with explicit caveats for the open gaps, are suitable for internal collaboration review and pre-submission circulation.

## 8. Summary of Closed Findings

For completeness, the following analysis threads are considered fully closed with no remaining open questions:

- **S00 data gate:** The 640,737 selected-pulse count is reproduced exactly (SHA256-verified). No further work needed.
- **MV1 PID ceiling:** AUC = 0.986 at MC truth level. Data-only PID is benchmarked against this ceiling. No further work needed.
- **MV5 pile-up validation:** R_max = 3.05 MHz validated to 0.2% agreement with MC. The original 4.22 MHz is confirmed as an error. No further work needed.
- **MV6 anomaly identification:** C12 nuclear recoils identified (55% of anomalies, 0.32% of tracks). Impact on physics quantified as negligible (0.1% systematic). No further work needed.
- **S10 pile-up rate:** The effective live-time tau_eff = 124.79 ns is measured and MC-validated. No further work needed.
- **S18 A-stack reproduction:** The A1-A3 residual width of 1.39 ns reproduces the analysis note's 1.43 ns. No further work needed.
- **Sample I/II trigger split:** The deuteron enrichment (73.5% vs 48.4%) is MC-confirmed. The trigger mimicry algorithm reproduces the Matthias effect. All supervisor deliverables (deltaE-E per sample, per-stave per-species energy spectra, stopping-depth distributions, data/MC comparison with KS tests) are complete. No further work needed.

## 9. Gap Closure Timeline

The following timeline represents the recommended sequence and estimated effort for closing the remaining open questions, assuming one full-time-equivalent analyst with LUNARC cluster access:

| Priority | Gap | Estimated Effort | Dependencies | Earliest Completion |
|----------|-----|-----------------|--------------|---------------------|
| 1 | GAP-02 (timewalk fix) | 1 day | None (code change only) | Immediate |
| 2 | GAP-04 (ML failure rate) | 1-2 weeks | MV5 extension | 2 weeks |
| 3 | GAP-01 (geometry update) | 2-4 weeks | MC regeneration on LUNARC | 4-6 weeks |
| 4 | GAP-03 (gain uncertainty) | Requires new beam run | Next CCB beam time | 3-6 months |
| 5 | GAP-05 (two-ended timing) | Requires new beam run | Split-readout hardware | 6-12 months |
| 6 | GAP-06 through GAP-09 (completeness) | 1-2 weeks each | None | 1-2 months |

## 10. Risk Assessment Matrix

Each gap is assessed on two axes: scientific impact if unresolved (1-5, where 5 means a major physics claim is unvalidated) and difficulty of resolution (1-5, where 5 means new hardware or beam time):

| Gap | Impact | Difficulty | Risk Level | Mitigation |
|-----|--------|------------|------------|------------|
| GAP-01 | 5 (MC acceptance corrections unreliable) | 4 (geometry rebuild + MC production) | CRITICAL | Flag all MC-dependent depth claims as preliminary |
| GAP-02 | 3 (timewalk-corrected timing unvalidated) | 1 (code change only) | MODERATE | Raw timing already passes MC validation |
| GAP-03 | 4 (energy scale systematic dominates) | 5 (requires beam time) | HIGH | Propagate 30% systematic through all energy-dependent quantities |
| GAP-04 | 2 (ML two-pulse not adopted) | 3 (simulation study) | LOW | Template fit is the recommended default |
| GAP-05 | 2 (two-ended projection unvalidated) | 5 (requires hardware) | LOW | Report sqrt(2) as upper-bound estimate |

## 11. Publication Strategy

The analysis programme is suitable for submission to a peer-reviewed journal upon resolution of GAP-01 and GAP-02. The recommended publication strategy is:

**Target journal:** Nuclear Instruments and Methods in Physics Research, Section A (NIM-A). This journal specialises in detector physics, test-beam analysis, and instrumentation methods — the core contributions of this work.

**Alternative journals:** Journal of Instrumentation (JINST) for open-access publication with a focus on detector commissioning methodology; Physical Review Accelerators and Beams (PRAB) if the emphasis is on the ESS operational implications.

**Main findings for the cover letter:**
1. A one-ended WLS fibre readout timing study whose historical 540 ps combined value is withheld as source-absent (CL-004/CL-005); the defensible timing statement on the located 8×16 raw product is the format-limited B4–B6 pair residual of 8.7 ns (CL-1320-001), with the one-ended configuration's cost/simplicity advantage independent of any validated resolution number.
2. Validated pile-up tolerance of 3.05 MHz, correcting a 4.22 MHz error in the original analysis note that arose from an incorrect effective live-time assumption.
3. Systematic Monte Carlo validation programme (MV0-MV6) providing truth-bridged assessment of every physics claim.
4. Methodological finding: rigorous leakage controls (target shuffle, LORO, event-block shuffle) are essential for evaluating machine learning in detector physics — 230+ studies, multiple corrected claims.
5. Complete, reproducible analysis pipeline with SHA256-verified data provenance and version-controlled configuration.

**Suggested referees:** Experts in scintillator detector timing, GEANT4 simulation validation, and machine learning for particle physics (specific names to be provided by the collaboration).

## 12. Future Beam Test Wishlist

Based on the open questions and systematic limitations identified in this analysis, the following measurements should be prioritised in the next CCB beam run:

1. **Forced-trigger pedestal data (highest priority):** Acquire events with no beam to measure the true ADC baseline distribution. This reduces the digitizer gain systematic from 30% to 10-15% and anchors the absolute energy scale.

2. **Per-stave gain calibration:** Use a beam of known energy (e.g., 190 MeV protons at normal incidence) to calibrate the relative gain of each stave. Alternatively, use cosmic muons (minimum-ionising, approximately 2 MeV/cm) to provide an absolute energy reference independent of the beam.

3. **Two-ended readout validation:** Instrument both ends of selected WLS fibres to measure the correlation between end times and validate the sqrt(2) projection. This requires only a fibre splitter and a second SiPM channel.

4. **Beam energy scan:** Vary the proton energy (e.g., 100, 150, 190, 230 MeV) to map the range-energy relation and calibrate the Birks constant via stopping particles of known incident energy.

5. **Low-rate runs for pile-up baseline:** Acquire data at very low beam current (< 0.1 nA) to measure the single-particle pulse shape with negligible pile-up contamination, providing a clean template for the two-pulse decomposition algorithm.

6. **Beam spot position scan:** Move the beam spot across the stave surface to map the position-dependent light collection efficiency and validate the WLS attenuation model.

## 13. Potential PhD Thesis Structure

This analysis programme provides sufficient material for a doctoral thesis structured as follows:

- **Chapter 1:** Introduction — HIBEAM/NNBAR physics motivation, ESS facility, detector requirements
- **Chapter 2:** The CCB Test-Beam Experiment — beamline, detector, data acquisition
- **Chapter 3:** Data Pipeline and Monte Carlo Digitizer — raw data processing, truth-bridged validation framework
- **Chapter 4:** Timing Resolution — CFD, timewalk correction, multi-stave combination, B2 covariance
- **Chapter 5:** Pile-up Characterisation — effective live-time, rate limits, two-pulse recovery
- **Chapter 6:** Pulse Shape and Machine Learning — dimensionality reduction, leakage controls, ML landscape
- **Chapter 7:** Energy Calibration — digitizer gain, Birks quenching, range-energy method
- **Chapter 8:** Particle Identification — deltaE-E method, stopping-depth PID, MC truth ceiling
- **Chapter 9:** Anomaly Discovery and Identification — C12 nuclear recoils, unsupervised clustering
- **Chapter 10:** Monte Carlo Validation Programme — systematic truth-bridged assessment
- **Chapter 11:** Conclusions and Outlook — summary of findings, open questions, future work

The thesis would contribute three original results to the field: (i) the validated timing and pile-up performance of one-ended WLS+SiPM readout for large-area scintillator detectors, (ii) the methodological framework for leakage-controlled ML evaluation in detector physics, and (iii) the complete, reproducible analysis pipeline with Monte Carlo truth bridging.

---

## Status Table with Closure Criteria (Thesis Upgrade Addition)

> **Every open question must have a falsifiable closure criterion, not a vague discussion.**

### Open Questions: Severity-Ranked with Closure Criteria

| ID | Question | Severity | Closure criterion | Current status |
|---|---|---|---|---|
| GAP-01 | MV3 geometry: missing material | **BLOCKING** | GEANT4 geometry fix → new MC → MV3 rerun → χ²/ndf < 10 | Not started |
| GAP-02 | MV4 corrected timing tension | **HIGH** | Toy digitizer B/√ADC → B/A → rerun → pull < 2σ | MV4b diagnosed; fix pending |
| GAP-03 | Digitizer gain 30% systematic | **HIGH** | Per-stave gain calibration → systematic < 10% | Not started |
| GAP-04 | PCA variance inconsistent | **HIGH** | Canonical rerun → single value → all docs updated | Not started |
| GAP-05 | Data weak-label PID AUC not separated | **HIGH** | Evaluate HGB on data weak labels → report purity-efficiency matrix | Not started |
| GAP-06 | Covariance-aware timing pending | **HIGH** | Compute full covariance estimator → update combined σ | Not started |
| GAP-07 | τeff cross-checks not done | **MEDIUM** | 2+ independent methods agree within 5 ns | Not started |
| GAP-08 | Censoring systematic not propagated | **MEDIUM** | Tail extrapolation or MC full-window simulation → propagated | Not started |
| GAP-09 | ML timing not production-ready | **MEDIUM** | All leakage controls passed → LORO CI excludes zero | Not started |
| GAP-10 | Forced-pedestal truth missing | **MEDIUM** | Dedicated forced-trigger run → pedestal truth validation | Requires new data |

### Closure Criteria Checklist

A gap is CLOSED only when:
1. A specific study produces a quantitative result
2. The result is documented in a REPORT.md
3. The claim ledger is updated
4. All affected chapters are updated
5. The gap is removed from this list

**Current fully-closed gaps:** 0 of 10.

---

## Chapter Verdict — Established / Open / Next

### Established
✅ Ten high-impact open questions catalogued with severity and closure criteria.
✅ Two blocking issues identified: MV3 geometry and MV4 digitizer.
✅ All open questions have falsifiable tests, not vague discussion.

### Open
⚠️ No gaps are fully closed — this document is a work plan, not a completion report.
⚠️ Some gaps require new experimental data (forced-trigger).

### Next Studies
🔬 Prioritize GAP-01 (MV3 geometry) — blocks multiple downstream claims.
🔬 Prioritize GAP-02 (MV4 digitizer) — prevents MC-validated timing claim.
🔬 Batch GAP-04 through GAP-09 as a single analysis sprint using existing data.
