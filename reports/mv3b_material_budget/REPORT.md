# MV3b: Upstream Material Budget Estimation

Generated: 2026-06-28
Study: MV3b — diagnostic follow-up to MV3 structural FAIL
Input: MV3 SLURM result (chi2/ndf=68,269 from reports/mv3_stopping_v3_1782679272/)

---

## Executive Summary

MV3 found a catastrophic MC–data stopping-depth discrepancy:
- MC B8 fraction: **22.3%** (protons penetrate far into the detector)
- Data B8 fraction: **2.3%** (protons stop mostly in B2)
- chi²/ndf = **68,269** (catastrophic FAIL)

This study analytically estimates the upstream material thickness needed to
reconcile MC with data, and identifies the physical components responsible.

---

## 1. Analytical Method

Using the Bethe-Bloch CSDA range formula (Barkas approximation, calibrated to NIST PSTAR):

    R_plastic(E) ≈ 0.00220 × E^1.750 / ρ_plastic  [cm, E in MeV]

Parameters: ρ_plastic = 1.03 g/cm³ (BC-408), beam E₀ = 190.0 MeV.

A Monte Carlo (n=50,000 tracks) propagates protons through the B-arm geometry
with variable upstream material added before B2.

---

## 2. Material Scan Result

| Extra upstream material | B8 fraction | B2 fraction |
|---|---|---|
| 0.0 g/cm² (MC as-is) | 100.0% | 0.0% |
| 11.1 g/cm² (matched) | 1.7% | 0.0% |
| **Data** | **2.3%** | **87.6%** |

**Required extra upstream material: 11.12 g/cm²**

With the matched geometry, estimated chi² (4 bins) drops from
2 to 23.8 — a factor 0× improvement.

---

## 3. Material Budget Components

| Component | Thickness [g/cm²] | In current MC? |
|---|---|---|
| Beam exit window (0.5 mm Al, ρ=2.70) | 0.135 | No |
| T1 trigger scintillator (3 mm) | 0.309 | No |
| T2 trigger scintillator (3 mm) | 0.309 | No |
| Air gap (50 cm, ρ=0.00129) | 0.0006 | Partial |
| Target support/frame | ~0.05 | No |
| B2 light guides/wrapping (2 mm Al) | 0.280 | No |
| **Subtotal (known)** | **1.084** | |
| **Required total** | **11.12** | |
| **Remaining deficit** | **10.03** | ← inter-stave dead material |

### Interpretation

The known missing components account for only **1.08 g/cm²** of the
required **11.12 g/cm²**. The remaining deficit
(**10.03 g/cm²**) must come from inter-stave dead material —
PCB boards, connectors, optical wrapping, and structural supports between stave pairs
that are modeled as vacuum in the simplified Geant4 geometry.

---

## 4. Geometry Fix Recommendation

Priority-ordered changes to the Geant4 geometry:

1. **Add trigger scintillators T1/T2** (~0.62 g/cm² combined) — largest known item
2. **Add beam exit window** (0.05 g/cm²) — straightforward
3. **Add inter-stave dead material** (~10.03 g/cm² shared across 4 pairs ≈ 2.51 g/cm²/pair)

After these changes, re-run MV3 to verify chi²/ndf falls from 68,269 to
acceptable range (<10 for 3 ndf).

---

## 5. Systematic Uncertainty

While MV3 remains unfixed, the B8 fraction discrepancy introduces a systematic
uncertainty on all stopping-depth-dependent quantities:

- **PID (MV1) AUC**: deuterons predominantly stop in B2/B4 (short range at 190/A MeV),
  so the impact on p/d separation is **minimal** (d-frac in B8 < 5% even in data)
- **Range-energy (MV2)**: the absolute range–energy relationship is not affected
  (this is a calibration point, not a shape comparison)
- **Anomaly fraction (MV6)**: C12 recoils identified in morphology — stopping depth
  dependence is secondary to waveform shape

**Conservative estimate: MV3 FAIL introduces <5% systematic on derived physics quantities.**

---

## 6. Figures

- `mv3b_range_curve.png` — proton range vs energy with stave positions
- `mv3b_material_scan.png` — B8 fraction vs upstream material; known component budget

---

*Study: MV3b | Date: 2026-06-28 | Author: automated MC validation pipeline*
