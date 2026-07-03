# CCB Test-Beam — Study Gap Analysis & Open Questions

> **A systematic audit of what's missing, what's unresolved, and what should be studied next.**
> For the complete analysis narrative, see [`WIKI.md`](WIKI.md).

**Last updated:** 2026-07-01 (corrected 2026-07-03 following External Review 2026-07-02 — several 2026-07-01 gap closures reopened/withdrawn, see §7)
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

#### GAP-01: Stopping-Depth Profile — Structural MC Failure
- **Severity:** ⛔ **BLOCKING** (prevents quantitative MC-based acceptance corrections)
- **Source:** [MV3 Stopping-Depth Profile](reports/mv3_stopping_depth/REPORT.md), MV3 v3
- **Finding:** χ²/ndf = 68,269. MC overestimates B8 penetration by 10× relative to data.
- **Root cause:** not established (corrected 2026-07-03). MV3b's toy estimate (~8–10 g/cm² of missing upstream material) was retracted in its own errata (realistic inter-stave estimate 0.1–0.5 g/cm²/pair); co-factors include track-basis vs event-basis counting, species exclusion (24% of charged tracks), no Birks quenching in the threshold, gain uncertainty, and an unvalidated LayerID→stave mapping.
- **MV3b diagnosis:** toy estimate retracted in its own errata; the real missing amount is unknown — a beamline material audit is required.
- **Action:** Audit real beamline material → update GEANT4 geometry → new MC production run → rerun MV3 with a nuisance scan.
- **Impact if unresolved:** All quantitative stopping-depth claims from MC are unreliable. B8 trigger efficiency calibration cannot be MC-anchored.

#### GAP-02: Timewalk Correction — MC Tension
- **Severity:** 🔶 **HIGH** (2.68σ pull, but raw timing passes)
- **Source:** [MV4 Timing Resolution](reports/mv4_timing_study/REPORT.md), MV4b
- **Finding:** Raw timing passes (pull = −1.05σ), but timewalk-corrected σ₆₈ shows +2.68σ tension.
- **Root cause:** Toy digitizer uses B/√ADC with negative B — physically inverted timewalk. MV4b diagnosed; correct form is B/amplitude.
- **Action:** Switch toy digitizer timewalk parametrization from B/√ADC → B/amplitude → rerun MV4.
- **Impact if unresolved:** Timewalk-corrected σ₆₈ comparison with MC cannot be reported at face value.

### 2.2 High-Impact Open Questions

#### GAP-03: Digitizer Gain — ±30% Uncertainty
- **Severity:** ⚠️ **HIGH** (dominant systematic for deuteron fraction)
- **Source:** [MV0 Digitizer Calibration](reports/mv0_digitizer/REPORT.md), MV0 v2
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
- **Action:** Measure correlation between two ends using dedicated split-readout channels → replace √2 with measured factor. *(Corrected 2026-07-03: A/B stack coincidences cannot serve here — the two stacks are independent arms measuring different particles of a kinematically-correlated pd pair, so A–B timing carries the pair kinematic spread plus the shared event T0, not a same-particle two-end correlation; experiment-owner setup facts.)*
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
- **Action:** Cross-check TOF against TPC track length / expected velocity, or against trigger scintillator coincidence. *(Note 2026-07-03: the TPC sits in front of Stack A only, and each arm has its own trigger scintillators — a TPC-based check applies to the A arm; per-arm trigger-to-stack timing applies within one arm; experiment-owner setup facts.)*

#### GAP-09: Stave-to-Stave Calibration Extrapolation
- **Severity:** **LOW** (assumed ±10% from single-stave calibration point)
- **Finding:** MV0 gain is calibrated on B2 only; ±10% stave-to-stave variation is assumed, not measured.
- **Action:** Measure per-stave gain using duplicate-readout or GEANT4 truth per stave.

---

## 3. Methodology Verification

### 3.1 Timing Independence Assumption

**Claim:** Multi-stave timing uses σ_comb² = Σ σ_i² / N (independent errors).

**Reality:** S05c shows B2-containing pairs are far more correlated than downstream pairs (the quantitative covariance values ~1042/~16 ns² were withdrawn 2026-07-03 — closure script numerically invalid). The independence assumption **fails for B2**; residual downstream covariance is unmeasured.

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

**Verdict:** ⚠️ **Partially verified.** The 10% tail-crossing method is well-defined and bootstrap CIs are given. (Correction 2026-07-03: MV5 does *not* provide independent confirmation — it used the data-measured τ_eff as an input and was retracted as a validation.) Alternative measurement methods are not cross-checked against each other. **Recommendation:** Add at least one alternative τ_eff measurement method as a cross-check.

### 3.6 Pile-up Censoring

**Claim:** Pile-up rate from live-time measurement.

**Check:** S10h, S10i note that "72.6% of pulses show positive inflation at live20" — the final-sample window is heavily censored.

**Verdict:** ⚠️ **Caveat acknowledged but not resolved.** The censoring is documented but the impact on R_max is not fully propagated. **Recommendation:** Quantify the systematic from acquisition-window bounds on R_max.

---

## 4. Genuinely Missing Studies

### 4.1 Multi-Stave Event Reconstruction with Covariance

> **Note (2026-07-03):** the 2026-07-01 "closure" of this item (fitted covariance = −0.127 ns²) was withdrawn — the closure script was numerically invalid. This study is genuinely missing again; the listing below stands.

**What's missing:** Current B4+B6+B8 combination assumes zero covariance. S05c showed B2 covariance is large; residual downstream covariance may be non-zero.

**Why it matters:** The combined σ ≈ 0.54 ns may be optimistic if downstream covariance is non-negligible.

**Proposed study:** Fit full 3×3 covariance matrix for B4/B6/B8 → compute optimal weighted combination → compare with independence-assumed σ.

### 4.2 Two-Ended Readout Correlation Measurement

> **Note (2026-07-03):** the 2026-07-01 partial closure (bounded [0.39, 0.85] ns) was withdrawn — the script measured nothing and its algebra was inverted (correct form σ√((1+ρ)/2); honest worst case ρ→1 = no improvement). This study is genuinely missing again; the listing below stands.

**What's missing:** The √2 projection assumes uncorrelated ends. No measurement of actual end-to-end correlation exists.

**Why it matters:** If ends are positively correlated (common-mode noise, temperature), the √2 factor overestimates the improvement. If anti-correlated (differential sensing), it underestimates.

**Proposed study:** Use dedicated split-readout channels → measure end-to-end correlation → compute actual improvement factor. *(Corrected 2026-07-03: the earlier proposal to use A/B stack coincidence events is withdrawn — an A·B coincidence pairs different particles (a kinematically-correlated pd pair sharing the event T0), so it cannot measure same-stave end-to-end correlation; experiment-owner setup facts.)*

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

**Why it matters:** The A-stack is an independent detector arm at the conjugate angle measuring **different particles** (experiment-owner setup facts, 2026-07-03). Full reproduction is an independent **methodology** check — it strengthens every B-stack methods claim, though it cannot cross-check the same particles.

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

> **Note (2026-07-03):** the items below that were marked closed in the §7 Gap Closure Log
> (GAP-02 rerun, GAP-05 two-ended correlation, multi-stave covariance) are open again after the
> external review withdrew those closures — this list is again correct as written.

### Immediate (Can Be Done Now, No New Data)

| Priority | Action | Effort |
|---|---|---|
| 0 | **Enforce the confirmation-partition policy** ([`docs/CONFIRMATION_PARTITION.md`](docs/CONFIRMATION_PARTITION.md)): runs 64 and 12–30 are reserved; any sub-0.3 ns timing claim (absolute or delta — all S03-family gains, incl. the falsified S03k 1.107 ns) requires a one-shot preregistered confirmation there before publication, using the shared estimators in `src/ccb_mc_validation/statistics/estimators.py` and consulting the program-level FDR census (`scripts/stats01_program_fdr.py`) | Low (policy landed 2026-07-03) |
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
| **GAP-02** (MV4b timewalk) | 3338707 | ⚠️ REOPENED 2026-07-03 | MV4 rerun never happened; MV4b misquoted MV4's pulls | `reports/mv4b_timewalk_1782911012/` |
| **GAP-05** (Two-ended correlation) | 3338704 | ⛔ WITHDRAWN 2026-07-03 | Script measured nothing; algebra inverted — correct form σ√((1+ρ)/2); honest worst case ρ→1 = no improvement | `reports/two_ended_correlation_1782911012/` |
| **GAP-06** (CFD/OF scan) | 3338703 | ⚠️ FRAMEWORK READY | CFD20 + OF9 confirmed as defaults; needs S02 data for full scan | `reports/cfd_of_scan_1782911012/` |
| **Missing Study #1** (Multi-stave covariance) | — | ⛔ WITHDRAWN 2026-07-03 | Closure script numerically invalid; −0.127 ns² untraceable | `reports/multistave_covariance_1782911275/` |
| **GAP-07** (χ²/ndf) | 3338706 | ⚠️ FRAMEWORK DEFINED | Reporting standards specified; needs code change to S02 script | `reports/gap_closure_quick_1782911012/` |
| **GAP-08** (TOF scale) | 3338706 | ⚠️ BLOCKED | Requires TPC track reconstruction | `reports/gap_closure_quick_1782911012/` |
| **Methodology §3.5** (τ_eff cross-check) | 3338706 | ⚠️ STILL OPEN | MV5 retracted as validation (2026-07-03) — no independent confirmation exists; data-only alternative still needed | `reports/gap_closure_quick_1782911012/` |

### Still Requiring Action

| Gap | Action | Effort |
|-----|--------|--------|
| GAP-01 (MV3 geometry) | Update GEANT4 geometry + new MC production | High (code + compute) |
| GAP-03 (MV0 forced-trigger) | Acquire forced-trigger data in next beam run | High (beam time) |
| GAP-04 (MC overlay study) | MV5 extension with truth-labelled overlaps | Medium (code + compute) |
| GAP-06 full closure | Run CFD/OF parameter scan with actual S02 timing data | Low (compute only) |
| GAP-07 full closure | Add χ²/ndf and tail fraction to S02 script output | Low (code change) |
| GAP-05 full closure | Measure two-ended correlation from split-readout data | Medium (requires data) |
