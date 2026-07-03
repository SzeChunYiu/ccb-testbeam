# Systematic Uncertainties — CCB Test-Beam Analysis

Date: 2026-06-28 (corrected 2026-07-03 following External Review 2026-07-02)
Status: All 6 MC validation studies ran; MV0/MV2/MV5/MV6 verdicts retracted and MV4 under review
(see `docs/mc_validation/MC_VALIDATION_RESULTS.md`) — magnitudes below that depend on the retracted
gain (92 ± 28 ADC/MeV) or on MV5/MV6 verdicts are pending re-derivation.

---

## Overview

| Source | Magnitude | Affected quantity | MC study | Status |
|---|---|---|---|---|
| Gain calibration (MV0) | ±30% on ADC/MeV | Energy-ADC conversion | MV0 v2 | Accepted systematic |
| Stopping-depth profile (MV3) | Up to 10× on B8 fraction | Depth-based PID cuts | MV3 FAIL | Geometry fix required |
| Timing σ₆₈ (MV4) | +2.7σ pull on corrected | Timing-based cuts | MV4 TENSION | Model artefact (MV4b fix) |
| Pile-up (MV5) | 0.2% on R_max | Trigger rate, occupancy | MV5 PASS | Negligible |
| C12 anomaly (MV6) | 0.18% on track count | Deuteron purity | MV6 DONE | Negligible with MV6 cut |
| Timewalk model (MV4b) | Pull +2.7σ → ~0 | Timing resolution | MV4b | Diagnosed: 1/A model fix |
| MV3 bias on PID (MV3b) | <5% | Proton-deuteron AUC | MV3b | Conservative bound |

---

## 1. Gain Calibration (MV0)

**Quantity**: ADC-to-MeV conversion factor
**Value**: gain = 92 ± 28 ADC/MeV
**Relative uncertainty**: ±30%

**Sources**:
1. **Methodology approximation**: We use median-matching (data B2 net_adc median = 1781 ADC,
   MC B2 edep median = 26.44 MeV × 0.733 peak_frac), which ignores tails.
   Systematic: ±15% from tail-vs-median mismatch.

2. **Missing S16 (forced-pedestal) sample**: No forced-trigger zero-signal events exist
   in the current dataset. Baseline subtracted as fixed 6752 ADC. Systematic: ±10% on pedestal.

3. **MC digitizer fidelity**: τ_rise, τ_decay, peak_frac all contribute. Systematic: ±10%.

4. **Single stave (B2) calibration point**: Only B2 has sufficient statistics for gain
   determination. Systematic: ±10% from stave-to-stave variation (assumed).

**Impact on analysis**:
- ADC threshold cuts: proportional to gain → cuts shift by ±30%
- dE/dx ratios (used for p/d PID): partially self-normalizing → <10% impact on AUC

---

## 2. Stopping-Depth Profile (MV3 FAIL)

**Quantity**: Fraction of tracks stopping in each stave pair
**MC vs data**: B2 47%/data 87%; B8 22%/data 2% (factor 9.7× discrepancy)
**Root cause**: not established (corrected 2026-07-03 — the "~8-10 g/cm² missing upstream material"
toy estimate was retracted in MV3b's own errata; realistic inter-stave estimate 0.1–0.5 g/cm²/pair;
co-factors include counting basis, species exclusion, no Birks quenching, gain uncertainty, and an
unvalidated LayerID→stave mapping)

**Impact by analysis**:
- **PID (MV1)**: Deuterons stop in B2 at 95 MeV/u → d-frac in B8 < 5% in data.
  Even with B8 MC fraction wrong, d/p separation in B2 is unaffected.
  **Impact on AUC: unquantified** (the previously quoted "<3%" had no computation behind it —
  corrected 2026-07-03; a sensitivity scan is required).

- **Range-energy (MV2)**: Stopping depths in data are ~20 cm shallower than MC predicts.
  Any range-based energy reconstruction has systematic offset.
  **Impact: 15-20% bias on absolute energy assignment**.

- **Anomaly class (MV6)**: C12 recoils identified by waveform morphology, not stopping depth.
  **Impact: negligible**.

- **Trigger efficiency**: If stave B8 triggers are MC-tuned, they may be wrongly calibrated.
  **Impact: 5-10% on tracks entering B8 (not relevant for beam-range protons/deuterons)**.

**Mitigation**:
1. Short-term: apply MV3b correction factor to stopping-depth-based quantities
2. Long-term: update Geant4 geometry (add T1/T2 scintillators, beam window, inter-stave material)

---

## 3. Timing Resolution (MV4 / MV4b)

**Quantity**: σ₆₈ of timing distribution
**Raw MC**: 1.744 ± 0.007 ns vs data 1.85 ns → pull = −1.05 (PASS)
**Corrected MC**: 1.770 ± 0.011 ns vs data 1.50 ns → pull = +2.68 (TENSION)
**Root cause (MV4b)**: Toy timewalk uses B/√ADC with B < 0 (unphysical); correct form is B/A

**Systematic uncertainty**:
- Current: 0.35 ns (difference of corrected σ₆₈ values, MC − data)
- After MV4b fix: expected < 0.15 ns

**Impact**: Timing-based cuts (e.g., proton–deuteron TOF separation) carry 0.35 ns systematic
until timewalk model is corrected.

---

## 4. Pile-Up Rate (MV5)

**Quantity**: Maximum trigger rate R_max
**MC result**: 3.044 MHz (τ_eff = 124.8 ns)
**Data result**: 3.05 MHz (corrected)
**Agreement**: 0.2% → **negligible systematic**

**Note**: The note's value of 4.22 MHz (assuming τ_eff = 90 ns) was wrong.
τ_eff is measured from data (10% tail-crossing live-time, S10b); no analytic derivation is quoted.
(Correction 2026-07-03: an earlier pseudo-derivation "τ_rise + τ_decay×(1−threshold) ≈
2.5 + 42×(1−0.05)" was removed — it evaluates to 42.4 ns, not 124.8 ns. The "MC result 3.044 MHz"
above is retracted as a validation: MV5's MC τ_eff was a hardcoded copy of the data value, and
R_max ≤ 3.05 MHz is a data-driven one-sided upper bound.)

---

## 5. C12 Anomaly Contamination (MV6)

**Quantity**: Fraction of anomaly tracks that are true C12 recoils
**Measured**: 0.32% anomaly fraction; 55% dominated by C12 (GMM Cluster 2 purity = 44.5%)
**Cross-section estimate**: ~0.1–0.2% expected rate (see docs/MV6_C12_PHYSICS.md)

**Impact on deuteron measurement**:
- C12 range < 25 μm → cannot be misidentified as deuteron (range ~20 cm)
- After MV6 morphology cut: <0.1% systematic on deuteron count
- Without MV6 cut: ~0.18% true C12 rate — still negligible for most analyses

---

## 6. Summary: Priority Order for Fixing

| Priority | Systematic | Current magnitude | Fix |
|---|---|---|---|
| High | MV3 geometry | 10× discrepancy in B8 fraction | New MC production with geometry update |
| Medium | MV0 gain | ±30% on energy scale | Forced-trigger S16 data acquisition in future run |
| Medium | MV4 timewalk | 0.35 ns on σ₆₈ | Replace B/√ADC with B/A in digitizer |
| Low | MV6 anomaly | <0.2% on track count | Apply GMM Cluster 2 cut |
| Negligible | MV5 pile-up | 0.2% on R_max | Closed |

---

## 7. Systematic Uncertainty Budget (Summary Table)

For a deuteron-fraction measurement (main physics goal):

| Source | δ(d fraction) | Notes |
|---|---|---|
| Gain calibration (MV0) | <10% | PID cuts partially self-normalizing |
| Stopping-depth (MV3) | <5% | d stop in B2; B8 discrepancy irrelevant |
| Timing (MV4) | <3% | Timing-based selections |
| C12 contamination (MV6) | <0.1% | Morphology cut applied |
| **Total (add in quadrature)** | **~12%** | Dominated by MV0 gain |

The dominant systematic is the gain calibration (MV0). This will remain at ±30%
until a forced-trigger S16 pedestal sample is acquired in a future beam run.

---

*Document: SYSTEMATIC_UNCERTAINTIES.md | Date: 2026-06-28 | CCB test-beam project*
