# Physics Audit — Complete Findings and Corrections

**Date:** 2026-07-01
**Scope:** Every .md file in docs/, reports/, and root-level documentation
**Principle:** Every claim must be traceable to measured data or validated simulation. No proxy materials with different physical properties. No uncalibrated models presented as calibrated results. No untested assumptions stated as fact.

---

## CRITICAL (Must Fix Before Publication)

### C1. MV3 Structural Failure Not Propagated to Other MV Verdicts

**Finding:** MV3 shows the simulation's stopping profile is wrong by a factor of 10 (B8: 22% MC vs 2% data, chi2/ndf = 68,269). Yet MV1 (PID AUC=0.986), MV2 (range-energy), MV4 (timing), and MV5 (pile-up) are all marked PASS using the same simulation. A simulation that puts the wrong particle species at the wrong depths with the wrong energies cannot simultaneously produce valid PID, energy, timing, and pile-up results — unless those studies are demonstrably insensitive to the stopping-depth error.

**Correction:** Every MV study that PASSED must include an explicit caveat about MV3 sensitivity:
- MV1 (PID): "PID separates species by dE/dx and range. The stopping-depth error means MC places protons too deep (B8 overpopulated), but p/d separation at B2 (where deuterons stop) may be less affected. Verified: the AUC=0.986 uses features from all layers; sensitivity to MV3 error not quantified."
- MV4 (timing): "Timing resolution depends on waveform shape and digitizer model, not on stopping fractions. MV3 error is not expected to affect timing — but this is an assumption, not verified by varying the geometry."
- MV5 (pile-up): "Pile-up rate depends on particle multiplicity per event. MV3 error in stopping fractions could affect multiplicity estimates. The 0.2% agreement may be fortuitous cancellation."

**Files to fix:** FINDINGS_SYNTHESIS.md, PROJECT_REPORT.md, docs/SYSTEMATIC_UNCERTAINTIES.md, WIKI.md

### C2. Timing Independence Assumption Untested

**Finding:** All per-stave resolution numbers (B4=1.45 ns, B6=0.72 ns, B8=0.93 ns) and the combined 3-stave sigma (0.54-0.56 ns) are derived from variance decomposition that assumes independent stave errors. This assumption is untested for downstream staves (B4/B6/B8). If errors are positively correlated (common clock jitter, shared pickup), the decomposition UNDERestimates individual stave resolution. The combined sigma inherits this assumption twice (once for per-stave resolution, once for inverse-variance weighting).

**Correction:** Every timing resolution number must carry the caveat: "Derived under the assumption of independent stave errors. If stave errors are correlated, the true per-stave resolution is larger and the combined resolution is correspondingly affected. The independence assumption has been validated for B4/B6/B8 pairs (fitted covariance = -0.127 ns^2, consistent with shared true event time and conservative by ~0.07 ns), but not for all correlation sources."

**Files to fix:** WIKI.md, docs/05_timing_resolution.md, FINDINGS_SYNTHESIS.md, PROJECT_REPORT.md

### C3. Two-Ended Projection in Headline Tables Without Qualifier

**Finding:** The two-ended readout sigma ~0.6-1.0 ns appears in the headline table of docs/00_overview.md without any qualifier that it is a theoretical projection. The actual hardware has only one-ended readout. The projection assumes (a) both ends have identical resolution, (b) errors are uncorrelated. Neither assumption is verified.

**Correction:** Every appearance of this number must include: "[projected, not measured — assumes identical two-end resolution and uncorrelated errors]"

**Files to fix:** docs/00_overview.md, WIKI.md, FINDINGS_SYNTHESIS.md

### C4. Al Proxy for Low-Z Materials (FIXED in commit 9caf23b)

**Finding:** MV3b used aluminum as a proxy for optical wrapping, beam windows, and inter-stave dead material. Al (Z=13) has very different stopping power from the actual low-Z materials. Fixed in commit 9caf23b.

**Status:** ✅ CORRECTED. Verify no remnants remain.

---

## HIGH (Should Fix Before Publication)

### H1. Deuteron/Proton Energy Medians from Uncalibrated Model

**Finding:** docs/01_setup_and_detector.md quotes "Deuteron-like: median ≈ 15.8 MeV" and "Proton-like: median ≈ 69.3 MeV" from a 2-parameter power-law fit to 4 CSDA points. These are presented with 0.1 MeV precision but are explicitly "not per-event truth" and have unquantified systematic uncertainties from geometry, Birks quenching, and relative gains.

**Correction:** Add explicit caveat: "These are sample-level characterizations from an analytic range model (2-parameter power-law fit to 4 NIST PSTAR CSDA points), NOT measurements. Dominant systematic uncertainties (geometry, Birks quenching, relative gains) are unquantified. Use for qualitative interpretation only. Absolute per-event energy is not available from waveform data alone."

**Files to fix:** docs/01_setup_and_detector.md, WIKI.md, FINDINGS_SYNTHESIS.md

### H2. MV4 Timing from Toy Digitizer with Unphysical Timewalk

**Finding:** The MV4 corrected-path timing (sigma68 = 1.770 ns) was produced by a toy digitizer model with B = -23.00 ns*sqrt(ADC) — a dimensionally inconsistent coefficient with the wrong sign. MV4b diagnosed this and proposed the fix (1/A form), but the fix has not been run in the full production chain. The MV4 "PASS (raw) / TENSION (corrected)" verdicts should not be treated as final.

**Correction:** Update MV4 status to "PASS (raw, insensitive to timewalk) / TENSION (corrected, known model artifact per MV4b — fix identified but not yet run in production)."

**Files to fix:** docs/09_open_questions.md, FINDINGS_SYNTHESIS.md, WIKI.md

### H3. MV0 Gain 92 +/- 28 ADC/MeV — 30% Uncertainty and KS Mismatch

**Finding:** The gain is labeled "PRODUCTION (v2)" but has a KS shape mismatch of 0.158 (KS-optimal is 60 ADC/MeV with KS=0.119), unresolved inter-stave variation (B6=64, B8=78 ADC/MeV), and uses digitizer card nominal values (tau_rise=2.5 ns, tau_decay=42 ns) rather than measured scintillator+WLS+SiPM response. The +/- 30% uncertainty dominates the deuteron-fraction systematic budget.

**Correction:** Relabel as "PRELIMINARY — 30% systematic uncertainty. Shape mismatch (KS=0.158) indicates the median-matching approach may not be valid. Inter-stave variation unresolved. Requires forced-trigger pedestal data and per-stave calibration for production use."

**Files to fix:** FINDINGS_SYNTHESIS.md, PROJECT_REPORT.md, WIKI.md, docs/SYSTEMATIC_UNCERTAINTIES.md

### H4. Data PID AUC ~0.985 from Weak Labels, Not Species Truth

**Finding:** The data PID AUC ~0.985 quoted alongside MC truth AUC 0.986 comes from P08b, which uses weak labels constructed from charge-scale features correlated with the input. This is a leakage-safe proxy, not species truth. Presenting it as comparable to the MC truth AUC is misleading.

**Correction:** Add explicit qualifier: "Data PID: AUC ~0.985 (weak-label proxy from charge-scale features; NOT species truth. MC truth ceiling: AUC = 0.986 with species labels. Data reaches near the ceiling, but this is a weak-label stress test, not an independent PID measurement.)"

**Files to fix:** FINDINGS_SYNTHESIS.md, PROJECT_REPORT.md, WIKI.md

### H5. MV5 R_max "0.2% Agreement" is Circular

**Finding:** The MV5 "confirmation" of R_max computes tau_eff from the same analytical model used to derive the data-corrected R_max. The MC and data both use the same tau_eff -> R_max conversion. The 0.2% agreement is self-consistency, not independent validation.

**Correction:** Rephrase: "MV5: The MC digitizer reproduces the same waveform live-time (124.8 ns) as measured in data. This confirms the digitizer's pulse-shape model is consistent with data — it does NOT provide an independent measurement of R_max. The pile-up rate limit of ~3.05 MHz is supported by both data-driven measurement and MC self-consistency, but no truly independent cross-check exists."

**Files to fix:** FINDINGS_SYNTHESIS.md, docs/09_open_questions.md, WIKI.md

---

## MEDIUM (Should Document Before Publication)

### M1. Gaussian-Core Fits Lack chi2/ndf

**Finding:** All per-stave timing resolution numbers are based on Gaussian-core fits whose goodness-of-fit is unknown. A poor fit means the quoted sigma is not a valid characterization.

**Correction:** Add to all timing tables: "chi2/ndf for Gaussian-core fits not reported — goodness unknown. sigma68 (robust, non-parametric) is the recommended metric."

### M2. CFD Fraction Unscanned, Ridge Alpha Fixed

**Finding:** CFD20 was chosen without scanning (10-50% range never tested). Ridge regression alpha=10 is fixed without cross-validation. These are arbitrary choices that affect quoted performance.

**Correction:** Document as "conditional on CFD20 and alpha=10 — not optimized."

### M3. MV6 Anomaly Fraction Discrepancy: 4% vs 0.32%

**Finding:** MV6 verdict text says "~4% anomaly corresponds to C12" but MC finds only 0.32% (12.5x smaller). The factor-of-12 discrepancy is not explained in the verdict.

**Correction:** Clarify: "The ~4% is the unsupervised cluster size in data. MC identifies 0.32% as C12 recoils. The discrepancy may reflect (a) the unsupervised cluster includes non-C12 anomalies, (b) the MC may underproduce C12 recoils, or (c) both. The 0.32% is the MC-calibrated C12 fraction."

### M4. TOF Reference Energy Changed Without Justification

**Finding:** TOF reference energy changed from 100 MeV to 40 MeV between analysis notes with no physical justification.

**Correction:** Document the rationale or flag as an unresolved systematic.

### M5. B2 Timewalk Set to Zero by Fiat

**Finding:** B2 timewalk correction is set to zero ("B2-blind") to avoid circularity, but B2 almost certainly has real amplitude-dependent timewalk. The bias this introduces in B2-containing residuals is not quantified.

**Correction:** Quantify the maximum plausible B2 timewalk and its effect on B2-containing residuals.

### M6. "Pile-up Score" is 77% Current-Independent Baseline

**Finding:** Only ~9.2% of the ML pile-up score at 20 nA is genuine beam pile-up. Any number quoted as "pile-up fraction" without subtracting the baseline is inflated.

**Correction:** Audit all pile-up fraction numbers to ensure they are baseline-subtracted.

---

## LOW (Improve Before Publication)

### L1. Adaptive Pedestal Bias is By-Design

**Finding:** The adaptive pedestal's -311 ADC bias is presented as a failure, but it is designed to be a conservative lower bound.

**Correction:** Clarify that the bias direction is built into the algorithm.

### L2. Small-Sample ML Claims (72 events)

**Finding:** App. I classifier trained on 72 positive examples. AUC 0.958 is statistically fragile.

**Correction:** Add bootstrap CI and small-sample caveat.

### L3. MV3 chi2/ndf Uncertainty Model Undescribed

**Finding:** chi2/ndf = 68,269 is quoted without describing the uncertainty model used to compute it.

**Correction:** Document the uncertainty model (Poisson errors per bin? Systematic errors included?).

---

## Files Requiring Changes (Priority Order)

1. **FINDINGS_SYNTHESIS.md** — C1, C2, C3, H1, H2, H3, H4, H5
2. **WIKI.md** — C2, C3, H1, H3, H4
3. **docs/00_overview.md** — C3
4. **docs/05_timing_resolution.md** — C2, M1
5. **docs/01_setup_and_detector.md** — H1
6. **PROJECT_REPORT.md** — C1, H3, H4
7. **docs/SYSTEMATIC_UNCERTAINTIES.md** — C1, H3
8. **docs/09_open_questions.md** — H2, H5
9. **docs/06_pileup.md** — M6
10. **docs/04_timing_calibration.md** — M4, M5
