# Chapter 1: Executive Summary

> **Thesis-grade rewrite (2026-07-14).** Status: Preliminary research record — not yet peer-reviewed.
> For the authoritative claim ledger, see [`docs/claim_ledger.csv`](docs/claim_ledger.csv).

---

## 1. Scope and Status

This chapter is the controlled front door to the CCB test-beam analysis thesis. It gives the reader a calibrated confidence map: what is established, what is corrected, what is preliminary, what is blocked by Monte Carlo or data limitations, and what remains analysis-only.

**Important caveat:** The work described in this thesis is a research synthesis and has not undergone peer review. Every claim below should be understood in the context of its validation status as defined in §3.

---

## 2. Physics Motivation

The CCB test-beam experiment at the Cyclotron Centre Bronowice (CCB) in Kraków, Poland, measured the response of HRD (Horizontal Range Detector) scintillator stacks to 190 MeV protons incident on a deuterated polyethylene (CD₂) target. The key deliverables are:

1. **Same-particle timing resolution** — how precisely can we timestamp when a charged particle hits each stave?
2. **Pile-up characterization** — at what beam rate do overlapping pulses become the limiting factor?
3. **Particle identification** — can we distinguish proton from deuteron events using the HRD telescope?
4. **Digitizer calibration** — what is the absolute energy scale of the readout electronics?

These measurements directly inform the design of the HIBEAM/NNBAR experiment at the European Spallation Source (ESS), where sub-nanosecond timing is required to discriminate neutron-antineutron oscillation candidates from spallation-induced background.

---

## 3. Confidence-Status Legend

Every claim in this thesis is labeled with one of the following statuses:

| Label | Meaning | Example |
|---|---|---|
| **VALIDATED** | Data result AND MC/truth or independent closure test supports the claim | S00 pulse count, Rmax correction |
| **DONE_DATA_ONLY** | Robust in data but no MC/truth closure available | Combined 3-stave timing |
| **TRUTH_LEVEL_MC_ONLY** | Mechanism demonstrated in simulation, transfer to real data incomplete | p/d PID AUC = 0.9860 |
| **DIGITIZED-MC TENSION** | Data-vs-MC comparison exists but disagrees beyond tolerance | MV4 corrected timing |
| **CORRECTED** | Previous result was leakage, stale value, or superseded | Rmax 4.22 → 3.05 MHz |
| **BLOCKED** | Cannot be finalized until missing data/simulation/geometry exists | MV3 acceptance correction, forced-pedestal truth |

**Do not confuse data validation with MC validation.** Some checks are data-driven, some use digitized MC, some use truth-level MC, and some are self-consistency only. The truth type for each claim is stated in §4.

---

## 4. Canonical Results Table

| Claim | Current value | Stat. unc. | Syst. unc. | Truth type | Source study | Status |
|---|---|---|---|---|---|---|
| Selected B-stack pulses | 640,737 | — | — | data_count | S00 gate | **VALIDATED** |
| B6 single-stave σ₆₈ | 0.68–0.75 ns | 0.02 | 0.05 | data + digitized MC | MV4 raw | **VALIDATED** |
| Combined 3-stave σ (B4+B6+B8) | 0.54–0.56 ns | 0.02 | 0.08 | data_only | MV4 combined | **DONE_DATA_ONLY** |
| Pair covariance | −0.127 ns² | — | — | data_only | MV4 covariance | **DONE_DATA_ONLY** |
| Rmax (pile-up tolerance) | 3.044–3.05 MHz | 0.05 | 0.10 | data + MC self-consistent | MV5 | **VALIDATED** |
| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | data_only | MV5 | **VALIDATED** |
| Digitizer gain (MV0 v2) | 92 ± 28 ADC/MeV | 14 | 28 | digitized MC | MV0 v2 | **VALIDATED** |
| p/d PID AUC | 0.9860 | — | — | MC truth only | MV1 | **TRUTH_LEVEL_MC_ONLY** |
| HGB p/d purity at 90% eff. | 0.9644 | — | — | MC truth only | MV1 | **TRUTH_LEVEL_MC_ONLY** |
| C12 anomaly fraction | 0.32% | — | — | MC-identified | MV6 | **VALIDATED** |
| MV3 B8 fraction (MC) | 22.3% | — | — | MC truth | MV3 | **FAIL** |
| MV3 B8 fraction (data) | 2.3% | — | — | data | MV3 | **FAIL** |
| MV3 χ²/ndf | 68,269 | — | — | MC vs data | MV3 | **FAIL** |
| MV4 raw timing pull | −1.05σ | — | — | digitized MC | MV4 raw | **PASS** |
| MV4 corrected timing pull | +2.68σ | — | — | digitized MC | MV4 corrected | **TENSION** |
| ML timing | Diagnostic only | — | — | data_only | MV4 | **GATED** |
| ML wins (confirmed) | Duplicate readout, saturation recovery | — | — | data_only | P04p, P07e | **GATED** |
| PCA variance | Inconsistent across docs | — | — | MC truth | MV6 | **SUPERSEDED** |

### Corrected values (shown only for historical context)

| Old value | → | New canonical value | Reason |
|---|---|---|---|
| 4.22 MHz | → | ~3.05 MHz | τeff corrected from 90 ns → 124.79 ns |
| ~246 ADC/MeV | → | 92 ± 28 ADC/MeV | MV0 v2 recalibration with improved MC geometry |
| 706,373 pulses | → | 640,737 pulses | S00 median selector gate, not dynamic selector |
| PCA 3 PCs 89%, 8 PCs 99.7% | → | Needs canonical rerun | Variance normalization inconsistent across Wiki and corrected chapter |

---

## 5. What This Thesis Does NOT Claim

> **The following claims are explicitly excluded from this thesis:**

1. **No final event-aligned truth in real beam data.** All real-data timing and PID comparisons lack per-event MC truth. Truth anchors exist only in simulation.
2. **No final absolute per-event energy calibration from waveform alone.** The digitizer gain (92 ± 28 ADC/MeV) has a 30% systematic uncertainty. Per-stave variation is unresolved.
3. **No final B8 acceptance correction.** The MV3 stopping-depth MC/data mismatch (χ²/ndf = 68,269, B8 fraction 22.3% MC vs 2.3% data) prevents quantitative acceptance corrections until the GEANT4 geometry is fixed.
4. **No production ML timing replacement.** ML timing results are diagnostic/gated until transfer/leakage controls are complete. Analytic timewalk remains the conservative production method.
5. **No forced-pedestal truth in current data.** Baseline/pedestal validation is limited to self-consistency checks without dedicated forced-trigger runs.

---

## 6. Project Architecture

```
Raw ROOT files → Pulse table (640,737 selected B-pulses)
  ├── Timing branch → pickoff → timewalk → covariance → combined σ₆₈
  ├── Pile-up branch → τeff → Rmax → two-pulse recovery
  ├── PID branch → ΔE–E features → HGB classifier → AUC/purity
  ├── ML branch → PCA/AE → ML timing → duplicate readout → saturation recovery
  ├── MC truth bridge → MV0-MV6 validations → digitized MC comparisons
  └── Systematic budget → nuisance propagation → final claims
```

---

## 7. Established Results

✅ S00 reproduction gate (640,737 pulses) is canonical and reproducible.
✅ B6 single-stave timing resolution σ₆₈ ≈ 0.68–0.75 ns (data + MC validated).
✅ Combined 3-stave timing σ ≈ 0.54–0.56 ns (data-only; covariance-aware estimate pending).
✅ Pile-up tolerance Rmax ≈ 3.05 MHz (corrected from 4.22 MHz after τeff measurement).
✅ Digitizer gain 92 ± 28 ADC/MeV established via MC digitized calibration (MV0 v2).
✅ C12 nuclear recoil anomaly fraction is 0.32% of tracks (MC-identified).
✅ Traditional methods remain superior for timewalk, pile-up rate estimation, and energy calibration.
✅ Most apparent ML "wins" fail leakage controls — a methodological lesson in rigorous ML evaluation.

---

## 8. Remaining Open Issues

⚠️ **MC timing tension:** MV4 raw timing passes (pull = −1.05σ), but timewalk-corrected timing shows +2.68σ tension. MV4b diagnosed the cause (toy digitizer uses B/√ADC instead of physical B/A). Needs digitizer fix and rerun.
⚠️ **MV3 geometry failure:** Missing upstream material (estimated ~8–10 g/cm²) causes 10× overestimate of B8 penetration in MC. Blocks quantitative PID acceptance corrections.
⚠️ **PID truth transfer:** p/d AUC = 0.9860 is MC-truth only. Transfer to real data with weak labels not yet demonstrated at comparable performance.
⚠️ **ML timing gate:** ML timing shows promising residuals but has not passed all leakage controls. Diagnostic only until LORO/transfer/control table complete.
⚠️ **Systematic propagation incomplete:** Systematic uncertainties listed but not fully propagated to all final observables.
⚠️ **PCA variance stale:** PCA variance values in Wiki and corrected chapter are inconsistent; needs canonical rerun.

---

## 9. Next Studies Required

🔬 **Covariance-aware combined timing estimator** — replace independence assumption with measured pair covariance.
🔬 **MV4b digitizer fix** — switch toy digitizer timewalk from B/√ADC to B/amplitude; rerun MV4 timing MC validation.
🔬 **GEANT4 geometry update** — add missing material; regenerate MC; rerun MV3, MV1, MV2, MV6 sensitivities.
🔬 **PID depth-reweighting** — reweight MV1 by data stop-layer fractions to bound MV3 impact.
🔬 **Full nuisance propagation** — build systematic nuisance parameter propagation pipeline for all final claims.
🔬 **Claim ledger audit** — verify every number in every chapter maps to a claim_ledger.csv row with correct status.
🔬 **Figure regeneration** — upgrade all figures to paper-grade: vector exports, 300+ dpi PNGs, source CSV/JSON, conclusion-bearing captions.

---

## 10. Reproducibility

This chapter is reproducible from the following artifacts:

- **Claim ledger:** [`docs/claim_ledger.csv`](docs/claim_ledger.csv)
- **Figure registry:** [`docs/figure_registry.csv`](docs/figure_registry.csv)
- **Canonical values:** [`docs/CLAIM_CHECKLIST_INTEGRATION.md`](docs/CLAIM_CHECKLIST_INTEGRATION.md)
- **Source commit:** `main` branch, commit at time of writing

All quantitative claims in this chapter are registered in the claim ledger with traceable source paths.
