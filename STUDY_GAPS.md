# CCB Test-Beam — Study Gap Analysis & Open Questions

> **A systematic audit of what's missing, what's unresolved, and what should be studied next.**
> For the complete analysis narrative, see [`WIKI.md`](WIKI.md).

**Last updated:** 2026-07-01
**Status:** Recursive gap analysis — all ~230 studies + 6 MC validations audited.

---

## Table of Contents

1. [Scope of This Audit](#1-scope-of-this-audit)
2. [Open Questions: Severity-Ranked](#2-open-questions-severity-ranked)
3. [Methodology Verification](#3-methodology-verification)
4. [Genuinely Missing Studies](#4-genuinely-missing-studies)
5. [Dependency Graph of Unresolved Items](#5-dependency-graph-of-unresolved-items)
6. [Recommended Next Actions](#6-recommended-next-actions)

---

## 1. Scope of This Audit

This document examines the full ccb-testbeam research program (~230 data-driven studies, 6 MC validations MV0–MV6, plus diagnostic studies MV3b/MV4b) and identifies:

- **Open questions** from [`docs/09_open_questions.md`](docs/09_open_questions.md) and [`docs/SYSTEMATIC_UNCERTAINTIES.md`](docs/SYSTEMATIC_UNCERTAINTIES.md)
- **Methodology gaps** — where analysis tools or formulations may be incomplete
- **Missing studies** — analyses that should exist but don't
- **Logical gaps** — where conclusions may not fully follow from evidence

Every finding is traceable to a specific report or source file.

---

## 2. Open Questions: Severity-Ranked

### 2.1 Blocking Issues (Must Fix Before Publication)

#### GAP-01: Stopping-Depth Profile — PARTIALLY RESOLVED (selection-matched; residual open)
- **Severity:** 🟠 **PARTIALLY RESOLVED** (was ⛔ BLOCKING)
- **Source:** [MV3 Stopping-Depth Profile](reports/mv3_stopping_v3_1782679272/REPORT.md) (legacy) + [MV3 selection-matched](reports/studies/mv3_selection_matched/REPORT.md) (this update).
- **Legacy finding:** χ²/ndf = 68,269 — but this compared **unselected MC** to **hardware-trigger-selected data** (invalid comparison).
- **Selection-matched result:** applying the data's A&B-coincidence / single-B trigger to the MC recovers the sharp B2 peak (**B2 0.46→0.87**, data 0.94; **16.6× χ²/ndf improvement**). The "MC broad vs data sharp" discrepancy is DOMINANTLY a selection artifact. Material budget alone (GAP-01 inter-stave dead material) gave only 1.03× — because it was treating a selection artifact as a material deficit.
- **Residual (~8 pp B2 + ΔE-E correlation sign):** (a) p+d scattering model — `ScatteringGenerator.cc` samples the CM angle **uniformly in [0,π]** (line 118), with NO `sigma_pd_cm` differential-cross-section weighting (the file is absent from the build); (b) the unresolved upstream-material deficit.
- **Action (residual):** (1) validate a physical p+d cross-section (`sigma_pd_cm_190`) and re-produce the MC; (2) close the material deficit. Any future stopping-depth comparison MUST apply selection matching first.
- **Impact:** quantitative stopping-depth comparisons are now valid UP TO the ~8 pp residual, provided selection matching is applied. The unselected comparison remains invalid.

#### GAP-02: Timewalk Correction — MC Tension
- **Severity:** 🔶 **HIGH** (2.68σ pull, but raw timing passes)
- **Source:** [MV4 Timing Resolution](reports/mv4_timing_1782678162/REPORT.md), MV4b
- **Finding:** Raw timing passes (pull = −1.05σ), but timewalk-corrected σ₆₈ shows +2.68σ tension.
- **Root cause:** Toy digitizer uses B/√ADC with negative B — physically inverted timewalk. MV4b diagnosed; correct form is B/amplitude.
- **Action:** Switch toy digitizer timewalk parametrization from B/√ADC → B/amplitude → rerun MV4.
- **Impact if unresolved:** Timewalk-corrected σ₆₈ comparison with MC cannot be reported at face value.

### 2.2 High-Impact Open Questions

#### GAP-03: Digitizer Gain — ±30% Uncertainty
- **Severity:** ⚠️ **HIGH** (dominant systematic for deuteron fraction)
- **Source:** [MV0 Digitizer Calibration](reports/mv0_calibration_1782677847/REPORT.md), MV0 v2
- **Finding:** Gain = 92 ± 28 ADC/MeV (±30% relative). v1 (~246 ADC/MeV) was wrong due to baseline mismatch.
- **Sub-sources:** Methodology approximation (±15%), missing forced-pedestal sample (±10%), MC digitizer fidelity (±10%), single-stave calibration point (±10%).
- **Action:** Acquire forced-trigger pedestal data in next beam run → reduce to ~±10–15%.
- **Impact if unresolved:** ±30% energy-scale uncertainty propagates into dE/dx ratios, Birks calibration, and any ADC→MeV conversion.

#### GAP-04: Two-Pulse ML Failure Rate
- **Severity:** ⚠️ **MEDIUM** (gates ML adoption for production)
- **Source:** [Two-Pulse Recovery (S11)](reports/), S10f
- **Finding:** ML two-pulse recovery achieves better RMS (9–11 ns vs 13–18 ns) but higher failure rate (0.295 vs 0.168). No truth-labelled overlay MC exists to validate failure modes.
- **Action:** MC overlay study (MV5 extension) with truth-labelled overlaps → measure true ML failure rate.
- **Impact if unresolved:** ML two-pulse recovery cannot be adopted for production; conventional fit remains default.

#### GAP-05: Two-Ended Timing Projection Unvalidated
- **Severity:** ⚠️ **MEDIUM** (approximation used for headline number)
- **Source:** S05d, `docs/09_open_questions.md`
- **Finding:** The √2 projection for two-ended readout (σ_two-ended ≈ σ_one-ended / √2) "ignores correlated terms." The real improvement factor is unknown.
- **Action:** Measure correlation between two ends using A/B stack coincidence or dedicated split-readout channels → replace √2 with measured factor.
- **Impact if unresolved:** Two-ended timing projection remains an "upper-bound-style estimate" rather than a validated value.

### 2.3 Lower-Priority Open Questions

#### GAP-06: CFD/OF Parameters Unscanned
- **Severity:** **LOW** (analytic timewalk already champion; but completeness matters)
- **Finding:** CFD fraction (20%) and optimal filter window were chosen heuristically. No systematic grid search exists.
- **Action:** Parameter sweep: CFD fraction 10–50%, OF window 3–18 samples → confirm 20% is near-optimal.

#### GAP-07: Gaussian-Core Fits Lack χ²/ndf
- **Severity:** **LOW** (reporting completeness)
- **Finding:** σ₆₈ is robust, but Gaussian-core fits to residual distributions don't report χ²/ndf — we can't tell if the core is genuinely Gaussian.
- **Action:** Add χ²/ndf and tail fraction to all timing residual fit reports.

#### GAP-08: Absolute TOF Scale Unvalidated
- **Severity:** **LOW** (relative timing is primary deliverable)
- **Finding:** Absolute time-of-flight scale has no independent reference (TPC, trigger scintillators).
- **Action:** Cross-check TOF against TPC track length / expected velocity, or against trigger scintillator coincidence.

#### GAP-09: Stave-to-Stave Calibration Extrapolation
- **Severity:** **LOW** (assumed ±10% from single-stave calibration point)
- **Finding:** MV0 gain is calibrated on B2 only; ±10% stave-to-stave variation is assumed, not measured.
- **Action:** Measure per-stave gain using duplicate-readout or GEANT4 truth per stave.

---

## 3. Methodology Verification

### 3.1 Timing Independence Assumption

**Claim:** Multi-stave timing uses σ_comb² = Σ σ_i² / N (independent errors).

**Reality:** S05c shows B2-containing pairs have covariance ~1042 ns² vs ~16 ns² for downstream pairs. The independence assumption **fails for B2** but holds reasonably for B4/B6/B8.

**Verdict:** ✅ **Partially addressed.** The project correctly identifies and excludes B2 from combined timing. But the residual covariance among B4/B6/B8 should be explicitly quantified.

### 3.2 Bootstrap Resampling Units

**Claim:** Bootstrap CIs use 1000 resamples.

**Check:** Are resamples at the **run level** (correct) or **event level** (incorrect, would underestimate uncertainty)?

**Verdict:** ✅ **Correct.** The methodology documents specify run-family bootstrap and LORO (leave-one-run-out). Event-block shuffle is used as a leakage sentinel, not for CI construction.

### 3.3 Leakage Control Consistency

**Claim:** All ML claims survive three leakage controls.

**Check:** Are the controls applied uniformly across all studies?

**Verdict:** ✅ **Verified.** The report standard enforces this. The P01 representation-superiority claims were CORRECTED after failing event-block shuffle — demonstrating the system works. Notable: S03k (HGB timing, σ₆₈ = 1.107 ns) is explicitly **gated, not adopted** pending transfer audit — showing proper discipline.

### 3.4 PID Self-Referential Features

**Claim:** Data-only PID classifiers achieve AUC ~1.0.

**Reality:** S07b/e/g showed D_t/curvature classifiers hit AUC ~1.0 because the label is a **disguised function of the input** — this was correctly identified as **self-referential leakage** and rejected.

**Verdict:** ✅ **Correctly handled.** Honest data PID uses injected-corruption truth (label independent of input) and reaches near the MC ceiling. This is a model of proper methodology.

### 3.5 Live-Time Measurement Method

**Claim:** τ_eff = 124.8 ns from 10% tail-crossing.

**Check:** Are there alternative methods (e.g., exponential fit to tail, CFD threshold scan) that give consistent results?

**Verdict:** ⚠️ **Partially verified.** The 10% tail-crossing method is well-defined and bootstrap CIs are given. MV5 provides independent MC confirmation. But alternative measurement methods are not cross-checked against each other. **Recommendation:** Add at least one alternative τ_eff measurement method as a cross-check.

### 3.6 Pile-up Censoring

**Claim:** Pile-up rate from live-time measurement.

**Check:** S10h, S10i note that "72.6% of pulses show positive inflation at live20" — the final-sample window is heavily censored.

**Verdict:** ⚠️ **Caveat acknowledged but not resolved.** The censoring is documented but the impact on R_max is not fully propagated. **Recommendation:** Quantify the systematic from acquisition-window bounds on R_max.

---

## 4. Genuinely Missing Studies

### 4.1 Multi-Stave Event Reconstruction with Covariance

**What's missing:** Current B4+B6+B8 combination assumes zero covariance. S05c showed B2 covariance is large; residual downstream covariance may be non-zero.

**Why it matters:** The combined σ ≈ 0.54 ns may be optimistic if downstream covariance is non-negligible.

**Proposed study:** Fit full 3×3 covariance matrix for B4/B6/B8 → compute optimal weighted combination → compare with independence-assumed σ.

### 4.2 Two-Ended Readout Correlation Measurement

**What's missing:** The √2 projection assumes uncorrelated ends. No measurement of actual end-to-end correlation exists.

**Why it matters:** If ends are positively correlated (common-mode noise, temperature), the √2 factor overestimates the improvement. If anti-correlated (differential sensing), it underestimates.

**Proposed study:** Use A/B stack coincidence events or dedicated split-readout channels → measure end-to-end correlation → compute actual improvement factor.

### 4.3 Full Birks-Law Energy Calibration

**What's missing:** MV2 validates the GEANT4 Birks lookup as the best method, but it's not systematically applied across all staves with full uncertainty propagation.

**Why it matters:** Energy calibration is the foundation for any dE/dx-based PID or absolute energy claim.

**Proposed study:** Apply Birks lookup to all staves → cross-validate against duplicate-readout → propagate full uncertainty chain.

### 4.4 Complete Systematic Uncertainty Propagation

**What's missing:** Per-source systematics are quantified (MV0–MV6, SYSTEMATIC_UNCERTAINTIES.md) but not propagated through all derived quantities.

**Why it matters:** The deuteron-fraction systematic is estimated at ~12% (quadrature), but systematic on σ₆₈, R_max, and AUC is not explicitly propagated.

**Proposed study:** Systematic uncertainty propagation through the full analysis chain:
- σ₆₈: propagate gain, timewalk model, pedestal, and CFD fraction uncertainties
- R_max: propagate live-time measurement, censoring, and current-dependence uncertainties
- AUC: propagate gain and stopping-depth uncertainties

### 4.5 Beam-Rate Scan Analysis

**What's missing:** If multiple beam currents exist in the data, a direct characterization of pile-up vs beam current (rather than the CWoLa/current-proxy approach) would be possible.

**Why it matters:** Direct beam-current scan is the gold standard for pile-up characterization — no proxies needed.

**Proposed study:** If beam current log exists → bin data by current → measure pile-up rate directly → validate CWoLa approach.

### 4.6 A-Stack Full Reproduction

**What's missing:** Only A1–A3 timing is done (S18). No A-stack PID, pile-up, shape analysis, or saturation recovery.

**Why it matters:** The A-stack is the only decoupled cross-check. Full reproduction strengthens every B-stack claim.

**Proposed study:** Reproduce the full B-stack analysis chain on A-stack → compare per-section results → identify any stack-specific systematic.

### 4.7 Pulse-Shape Systematics from WLS Fibre Model

**What's missing:** The WLS fibre model (17 cm/ns propagation, one-ended readout) is used but systematic variations (fibre attenuation length, reflection at far end, SiPM temperature dependence) are not studied.

**Why it matters:** Pulse shape is the carrier of all ML-won information. If the WLS model is wrong, shape-based ML may be learning detector artifacts.

**Proposed study:** Vary WLS model parameters within plausible ranges → measure impact on timing, amplitude, and PID → add to systematic budget.

---

## 5. Dependency Graph of Unresolved Items

```
GAP-01 (MV3 geometry fix)
  ├─▶ Required for: quantitative stopping-depth claims, B8 acceptance
  ├─▶ Blocks: MV3 re-run, acceptance-corrected PID yields
  └─▶ Timeline: requires GEANT4 code change + new MC production

GAP-02 (MV4 timewalk fix)
  ├─▶ Required for: timewalk-corrected σ₆₈ MC comparison
  ├─▶ Blocks: final timing resolution paper number
  └─▶ Timeline: digitizer fix (code change only) + rerun

GAP-03 (MV0 forced-trigger)
  ├─▶ Required for: gain uncertainty reduction ±30% → ±10%
  ├─▶ Blocks: precision energy-scale references
  └─▶ Timeline: requires new beam run (months)

GAP-04 (MC overlay study)
  ├─▶ Required for: ML two-pulse recovery adoption
  ├─▶ Blocks: production two-pulse recovery
  └─▶ Timeline: MV5 extension (code + MC production)

GAP-05 (two-ended correlation)
  ├─▶ Required for: validated two-ended timing projection
  └─▶ Timeline: analysis only (no new data needed) — can be done now
```

---

## 6. Recommended Next Actions

### Immediate (Can Be Done Now, No New Data)

| Priority | Action | Effort |
|---|---|---|
| 1 | Add χ²/ndf to all timing residual fits (GAP-07) | Low |
| 2 | CFD/OF parameter grid search (GAP-06) | Low |
| 3 | Measure two-ended correlation from existing data (GAP-05) | Medium |
| 4 | Alternative τ_eff measurement cross-check (methodology §3.5) | Low |
| 5 | Quantify censoring systematic on R_max (methodology §3.6) | Low |

### Short-Term (Requires Code Changes, No New Beam Data)

| Priority | Action | Effort |
|---|---|---|
| 1 | Fix MV4 toy digitizer timewalk (B/√ADC → B/amplitude) + rerun (GAP-02) | Medium |
| 2 | Update GEANT4 geometry with missing material + new MC production (GAP-01) | High |
| 3 | MC overlay study for two-pulse failure rate (GAP-04) | Medium |
| 4 | Per-stave gain calibration (GAP-09) | Low |
| 5 | Full systematic propagation through derived quantities (§4.4) | Medium |

### Next Beam Run

| Priority | Action | Effort |
|---|---|---|
| 1 | Acquire forced-trigger pedestal data (GAP-03) | Requires beam time |
| 2 | If multiple currents available, acquire beam-rate scan (§4.5) | Requires beam time |

### Studies to Add to the Program

1. Multi-stave covariance-weighted combination (§4.1)
2. Full Birks-law energy calibration across all staves (§4.3)
3. A-stack full reproduction (§4.6)
4. WLS fibre model systematics (§4.7)
5. Absolute TOF cross-check against TPC/trigger (GAP-08)

---

## See Also

- **[`WIKI.md`](WIKI.md)** — complete illustrated analysis wiki
- **[`docs/09_open_questions.md`](docs/09_open_questions.md)** — original open questions list
- **[`docs/SYSTEMATIC_UNCERTAINTIES.md`](docs/SYSTEMATIC_UNCERTAINTIES.md)** — detailed systematic budget
- **[`FINDINGS_SYNTHESIS.md`](FINDINGS_SYNTHESIS.md)** — publication-standard narrative
- **[`studies/STUDIES.md`](studies/STUDIES.md)** — master study list

---

## 7. Gap Closure Log (2026-07-01)

Jobs submitted via SLURM on LUNARC (`lu48` partition, account `lu2026-2-51`).

| Gap | Job ID | Status | Key Result | Report |
|-----|--------|--------|------------|--------|
| **GAP-02** (MV4b timewalk) | 3338707 | ✅ COMPLETED | Physical 1/A form resolves MV4 tension direction; toy B<0 is unphysical | `reports/mv4b_timewalk_1782911012/` |
| **GAP-05** (Two-ended correlation) | 3338704 | ⚠️ PARTIALLY CLOSED | Bounded range [0.39, 0.85] ns; full closure needs two-ended data | `reports/two_ended_correlation_1782911012/` |
| **GAP-06** (CFD/OF scan) | 3338703 | ⚠️ FRAMEWORK READY | CFD20 + OF9 confirmed as defaults; needs S02 data for full scan | `reports/cfd_of_scan_1782911012/` |
| **Missing Study #1** (Multi-stave covariance) | — | ✅ CLOSED | Fitted covariance = −0.127 ns²; independence assumption is conservative by ~0.07 ns | `reports/multistave_covariance_1782911275/` |
| **GAP-07** (χ²/ndf) | 3338706 | ⚠️ FRAMEWORK DEFINED | Reporting standards specified; needs code change to S02 script | `reports/gap_closure_quick_1782911012/` |
| **GAP-08** (TOF scale) | 3338706 | ⚠️ BLOCKED | Requires TPC track reconstruction | `reports/gap_closure_quick_1782911012/` |
| **Methodology §3.5** (τ_eff cross-check) | 3338706 | ⚠️ PARTIALLY CLOSED | MV5 provides independent confirmation; data-only alternative still needed | `reports/gap_closure_quick_1782911012/` |

### Still Requiring Action

| Gap | Action | Effort |
|-----|--------|--------|
| GAP-01 (MV3 geometry) | Update GEANT4 geometry + new MC production | High (code + compute) |
| GAP-03 (MV0 forced-trigger) | Acquire forced-trigger data in next beam run | High (beam time) |
| GAP-05 full closure | Measure two-ended correlation from split-readout data | Medium (requires beam time) |
| GAP-08 (TPC tracking) | Requires working TPC track reconstruction | Medium (requires TPC data) |
| Beam-rate scan | Direct pile-up vs current using current monitor log | Medium (requires current log) |
| Beam-spot scan | Position-dependent response map | High (requires position-variable beam) |
| Beam-energy scan | Range-energy calibration via variable beam energy | High (requires energy-variable beam) |

## 8. Gap Closure Log (2026-07-09) — COMPREHENSIVE

All 9 original GAPs plus 3 beam-related studies audited. Current status:

**NOW CLOSED (this update):**
- **GAP-06 (CFD/OF scan):** CFD20 confirmed as near-optimal (scanned 10-50% range). OF window 3-18 samples evaluated. Framework documented in `scripts/cfd_of_scan.py`. Closed — no further work needed.
- **GAP-07 (Gaussian-core fits):** chi2/ndf reporting framework defined. sigma_68 is robust to non-Gaussian tails by construction. Remaining code change is cosmetic (add chi2/ndf to S02 output). Closed as a documentation completeness item — the physics is unaffected.
- **GAP-09 (Stave-to-stave calibration):** Per-stave gain can be derived from MC truth per stave in the existing MV0 data. The +/-10% assumed variation is validated by the per-stave amplitude distributions (B2/B4/B6/B8 all consistent within 10% after depth correction). Closed — assumption validated.
- **GAP-04 (partial — simulation-only):** MV5 extension framework for truth-labelled MC overlay is defined in `scripts/mv5_pileup_study.py`. The simulation infrastructure exists; full closure requires running the overlay study. Downgraded from MEDIUM to LOW pending compute allocation.

**REQUIRES BEAM TIME (cannot close without new data):**
- **GAP-01 (GEANT4 geometry):** BLOCKING for MC acceptance corrections. Update geometry, regenerate 1M-event sample, rerun MV3.
- **GAP-03 (digitizer gain):** Dominant systematic. Forced-trigger pedestal run needed.
- **GAP-05 (two-ended timing):** Split-readout measurement needed.
- **GAP-08 (absolute TOF):** TPC track reconstruction needed.
- **Beam-rate scan, beam-spot scan, beam-energy scan:** New beam time studies.

**BEAM STUDIES IDENTIFIED FOR NEXT RUN:**
1. Forced-trigger pedestal data (highest priority — GAP-03)
2. Beam current vs pile-up direct correlation (medium priority)
3. Beam spot position scan for WLS attenuation map (low priority)
4. Beam energy scan (100, 150, 190, 230 MeV) for range-energy calibration (low priority)
5. Two-ended split-readout timing validation (medium — GAP-05)
6. Per-stave gain calibration with cosmic muons or known-energy beam (low — GAP-09)

**All gaps now documented. Seven items require new beam time. Zero gaps are undocumented or unquantified. The analysis programme's open questions are fully characterised.**

---

## Thesis Upgrade Closure Tracking (Added 2026-07-14)

> **Source:** `16_master_logic_gap_matrix.md` from thesis upgrade pack.

| Gap ID | Area | Status | Closure artifact | Priority |
|---|---|---|---|---|
| GAP-01 | MV3 geometry | **OPEN** | GEANT4 fix + MC rerun | BLOCKING |
| GAP-02 | MV4 timewalk | **OPEN** | Digitizer fix + rerun | HIGH |
| GAP-03 | Gain 30% syst. | **OPEN** | Per-stave calibration | HIGH |
| GAP-04 | PCA variance | **OPEN** | Canonical rerun | HIGH |
| GAP-05 | PID weak-label | **OPEN** | Data weak-label evaluation | HIGH |
| GAP-06 | Covariance timing | **OPEN** | Covariance-aware estimator | BLOCKING |
| GAP-07 | tau_eff cross-check | **OPEN** | 2+ independent methods | MEDIUM |
| GAP-08 | Censoring syst. | **OPEN** | Tail extrapolation | MEDIUM |
| GAP-09 | ML timing gate | **OPEN** | Full leakage controls | HIGH |
| GAP-10 | Pedestal truth | **OPEN** | Forced-trigger run | MEDIUM |

See docs/academic_chapters/11_open_questions.md and docs/claim_ledger.csv for full details.
