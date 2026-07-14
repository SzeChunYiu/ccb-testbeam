# CCB Test-Beam Analysis — Unified Illustrated Wiki

> **A self-contained guide to the CCB test-beam analysis, written for readers with and without prior knowledge of particle physics instrumentation.**
>
> Every study has a **descriptive name** and a **hyperlink** to its full report. Every claim is traceable to source. Every number has uncertainty.
>
> **Repository:** [SzeChunYiu/ccb-testbeam](https://github.com/SzeChunYiu/ccb-testbeam) | **Started:** 2026-06 | **Status:** Research synthesis (preliminary, not yet peer-reviewed)

---

> 📘 **Academic Chapters:** Chapters 2–12 are available as self-contained academic papers (Nature Methods style, ≥1000 words each) in [`docs/academic_chapters/`](docs/academic_chapters/). Each chapter recursively explains all concepts from first principles, grounded in real data and Monte Carlo simulation. The summaries below link to the full versions.

## Quick Navigation

| I want to... | Go to |
|---|---|
| See the key results at a glance | [§1 Executive Summary](#1-executive-summary) |
| Understand the experiment | [§2 Experimental Setup](#2-experimental-setup) → [Full chapter](docs/academic_chapters/02_experimental_setup.md) |
| Follow the data from raw files | [§3 Data Pipeline](#3-data-pipeline) → [Full chapter](docs/academic_chapters/03_data_pipeline.md) |
| Understand timing resolution | [§4 Timing Analysis](#4-timing-analysis) → [Full chapter](docs/academic_chapters/04_timing_analysis.md) |
| Learn about pile-up | [§5 Pile-up Analysis](#5-pile-up-analysis) → [Full chapter](docs/academic_chapters/05_pileup_analysis.md) |
| See where ML helps (or doesn't) | [§6 Pulse Shape & Machine Learning](#6-pulse-shape--machine-learning) |
| Check the methodology | [§12 Methodology Appendix](#12-methodology-appendix) |
| Find what's still missing | [§11 Open Questions](#11-open-questions--next-steps) and [`STUDY_GAPS.md`](STUDY_GAPS.md) |
| Browse all studies with proper names | [Study Catalogue](#study-catalogue) |

---

## 1. Executive Summary

> **Thesis-grade rewrite (2026-07-14).** Status: Preliminary research synthesis — not yet peer-reviewed.
> For the authoritative claim ledger, see [docs/claim_ledger.csv](docs/claim_ledger.csv).

### Scope and Status

This section is the controlled front door to the CCB test-beam analysis. Every claim below is labeled with its validation status as defined in the confidence-status legend. The work has not undergone peer review.

### Confidence-Status Legend

| Label | Meaning |
|---|---|
| **VALIDATED** | Data result AND MC/truth or independent closure test supports the claim |
| **DONE_DATA_ONLY** | Robust in data but no MC/truth closure available |
| **TRUTH_LEVEL_MC_ONLY** | Mechanism demonstrated in simulation, transfer to real data incomplete |
| **TENSION** | Data-vs-MC comparison disagrees beyond tolerance |
| **FAIL** | MC or validation reveals concrete model failure |
| **CORRECTED** | Previous result was leakage, stale value, or superseded |
| **BLOCKED** | Cannot be finalized until missing data/simulation/geometry exists |
| **GATED** | Promising result, not adopted until controls pass |

### Canonical Results Table

| Claim | Current value | Stat. unc. | Syst. unc. | Truth type | Status |
|---|---|---|---|---|---|
| Selected B-stack pulses | 640,737 | — | — | data_count | **VALIDATED** |
| B6 single-stave σ₆₈ | 0.68–0.75 ns | 0.02 | 0.05 | data + digitized MC | **VALIDATED** |
| Combined 3-stave σ (B4+B6+B8) | 0.54–0.56 ns | 0.02 | 0.08 | data_only | **DONE_DATA_ONLY** |
| Pair covariance | −0.127 ns² | — | — | data_only | **DONE_DATA_ONLY** |
| Rmax (pile-up tolerance) | 3.044–3.05 MHz | 0.05 | 0.10 | data + MC self-consistent | **VALIDATED** |
| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | data_only | **VALIDATED** |
| Digitizer gain (MV0 v2) | 92 ± 28 ADC/MeV | 14 | 28 | digitized MC | **VALIDATED** |
| p/d PID AUC | 0.9860 | — | — | MC truth only | **TRUTH_LEVEL_MC_ONLY** |
| C12 anomaly fraction | 0.32% | — | — | MC-identified | **VALIDATED** |
| MV3 B8 data/MC | data 2.3% / MC 22.3% | — | — | MC vs data | **FAIL** |
| MV4 raw timing pull | −1.05σ | — | — | digitized MC | **PASS** |
| MV4 corrected timing pull | +2.68σ | — | — | digitized MC | **TENSION** |
| ML timing | Diagnostic only | — | — | data_only | **GATED** |
| ML wins | Duplicate readout, saturation recovery | — | — | data_only | **GATED** |

### Corrected Values (Historical Context Only)

| Old value | New canonical value | Reason |
|---|---|---|
| 4.22 MHz | ~3.05 MHz | τeff corrected 90 → 124.79 ns |
| ~246 ADC/MeV | 92 ± 28 ADC/MeV | MV0 v2 recalibration |
| 706,373 pulses | 640,737 pulses | S00 median selector gate |
| PCA 3 PCs 89%, 8 PCs 99.7% | Needs canonical rerun | Variance normalization inconsistent |

### What This Project Does NOT Claim

1. **No final event-aligned truth in real beam data**
2. **No final absolute per-event energy calibration from waveform alone** (30% syst.)
3. **No final B8 acceptance correction** (MV3 geometry FAIL)
4. **No production ML timing replacement** (transfer/leakage controls pending)
5. **No forced-pedestal truth in current data**

### Executive Verdict

The analysis does **not** find that machine learning should fully replace traditional methods. ML excels where the missing information is genuinely in waveform shape (saturation recovery, duplicate-readout closure). Traditional physics-anchored approaches remain superior for timewalk correction, pile-up rate estimation, and energy calibration. The most important finding is methodological: **most apparent ML "wins" fail leakage controls** — a lesson in rigorous ML evaluation.

**[Full chapter:](docs/academic_chapters/01_executive_summary.md)**


## 2. Experimental Setup

> **Thesis-grade update (2026-07-14).** Material budget audited. See [Full chapter](docs/academic_chapters/02_experimental_setup.md).

### Key Components

| Component | Specification |
|---|---|
| Beam | 190 MeV protons (CCB isochronous cyclotron) |
| Target | CD₂, 2.3 mm, 1.01 g/cm³ |
| HRD Stacks | A-stack (+71.5°) and B-stack (−38°), 109 cm from target |
| Scintillator | BC-408 plastic, 1 cm thick, 100 cm² per stave |
| WLS fibre | Kuraray Y-11, 1 mm diameter, ~17 cm/ns propagation |
| SiPM | Hamamatsu S13360-3050CS, 3×3 mm² |
| Waveform | 18 samples × 10 ns = 180 ns, 100 MS/s, 14-bit ADC |
| Trigger | Sample I: A×B coincidence (runs 31–57), Sample II: B-only (runs 58–65) |

### Material Budget Status

| Component | Status |
|---|---|
| Beam window, target, trigger scintillators, air gap | Included in GEANT4 |
| Inter-stave dead material, support frames, optical interfaces | **MISSING** (estimated 8–10 g/cm²) |
| Impact | MV3 B8 MC/data mismatch ×10 (χ²/ndf = 68,269) |
| Status | **BLOCKING** — prevents quantitative B8 acceptance corrections |

**[Full chapter:](docs/academic_chapters/02_experimental_setup.md)**

---

## 3. Data Pipeline

> **Thesis-grade update (2026-07-14).** Reproduction gate documented. See [Full chapter](docs/academic_chapters/03_data_pipeline.md).

### Reproduction Gate (BLOCKING)

```
Command:  python scripts/01_build_pulse_table_from_root.py
          --config configs/s00_reproduction.yaml
Expected: 640,737 selected B-stave pulses
Gate:     A > 1000 ADC, even physical staves {0,2,4,6}
Baseline: median of samples 0–3
Seed:     random_state = 20260601
Tolerance: 0 (exact reproduction required)
```

### Pipeline Architecture

```
Raw ROOT → baseline(subtract median samples 0–3) → amplitude(A = max − baseline)
  → select A > 1000 ADC → gate even staves {0,2,4,6}
  → compute timing variables (CFD20, template_phase)
  → write canonical pulse table → downstream analyses
```

### Data Quality

| Metric | Status |
|---|---|
| Run-by-run pulse counts | Reproducible |
| Baseline stability | ~200 ADC, RMS ~5 ADC |
| Saturation fraction | B2 ~5%, B4 ~2%, B6 ~1%, B8 ~0.5% |
| File checksums | Not yet inventoried |

**[Full chapter:](docs/academic_chapters/03_data_pipeline.md)**

## 4. Timing Analysis

> **Thesis-grade update (2026-07-14).** Covariance estimator and timewalk canonical form documented. See [Full chapter](docs/academic_chapters/04_timing_analysis.md).

### Key Results

| Observable | Value | Status |
|---|---|---|
| B6 single-stave σ₆₈ | 0.68–0.75 ns | **VALIDATED** (data + digitized MC) |
| Combined 3-stave σ (B4+B6+B8) | 0.54–0.56 ns | **DONE_DATA_ONLY** (independence assumed) |
| Pair covariance (B4–B6) | −0.127 ns² | **DONE_DATA_ONLY** |
| MC raw timing pull | −1.05σ | **PASS** |
| MC corrected timing pull | +2.68σ | **TENSION** |
| ML timing | Diagnostic only | **GATED** |

### Critical Open Issues

1. **Covariance-aware estimator pending** — current headline assumes independent stave errors
2. **Timewalk canonical form unresolved** — Wiki vs reports differ on A₀+B/A vs log(A) vs 1/√A
3. **MC corrected timing tension** — MV4b diagnosed toy digitizer uses B/√ADC instead of physical B/A
4. **B2 excluded** from precision estimate due to covariance topology

### Next Study Priority
🔬 Compute covariance-aware B4+B6+B8 estimator → update combined σ
🔬 Fix MV4b digitizer timewalk → rerun MC → resolve tension

**[Full chapter:](docs/academic_chapters/04_timing_analysis.md)**

---

## 5. Pile-up Analysis

> **Thesis-grade update (2026-07-14).** Rmax derivation and censoring systematic documented. See [Full chapter](docs/academic_chapters/05_pileup_analysis.md).

### Key Results

| Observable | Value | Status |
|---|---|---|
| Rmax (pile-up tolerance) | 3.044–3.05 MHz | **VALIDATED** (corrected from 4.22 MHz) |
| τeff (effective live-time) | 124.79 ns | **VALIDATED** (corrected from 90 ns) |
| Two-pulse ML recovery | Lower RMS, higher failure | **GATED** (operating curve pending) |

### Derivation Summary
```
τeff = 124.79 ns (template tail crossing, not 90 ns naive FWHM)
Rmax = −ln(0.95) / τeff ≈ 3.05 MHz (5% pile-up tolerance)
```

### Critical Open Issues

1. **τeff cross-checks needed** — at least 2 independent methods (threshold scan, exponential fit)
2. **Censoring systematic** — 180 ns window truncates ~23% of pulse tail
3. **ML score calibration** — classifier output not mapped to physical overlap probability
4. **MC overlay truth** — two-pulse recovery not validated with truth-labelled overlaps

### Next Study Priority
🔬 Measure τeff by alternative methods → confirm robustness
🔬 Quantify censoring systematic → propagate to Rmax uncertainty

**[Full chapter:](docs/academic_chapters/05_pileup_analysis.md)**

## 6. Pulse Shape & Machine Learning

> **Thesis-grade update (2026-07-14).** PCA variance flagged SUPERSEDED, AE leakage corrected. See [Full chapter](docs/academic_chapters/06_pulse_shape_ml.md).

### ML Verdict Matrix

| Domain | Traditional | ML | Verdict |
|---|---|---|---|
| Timewalk correction | Analytic A₀+B/A | MLP/CNN | **Traditional wins** (ML fails LORO) |
| Duplicate readout | Amplitude correlation | ML closure | **ML wins** (GATED) |
| Saturation recovery | Clip rejection | ML recovery | **ML wins** (GATED) |
| Pile-up recovery | Template deconvolution | CNN | **GATED** |
| PID | ΔE-E/range | HGB | **ML informative** (MC-truth only) |

### Key Corrections

1. **PCA variance: SUPERSEDED.** Wiki (89% / 99.7%) and corrected chapter differ. Needs canonical rerun.
2. **AE superiority: CORRECTED.** Original claim was leakage (train-test contamination).
3. **Most apparent ML "wins" fail leakage controls** — this is the primary methodological finding.

**[Full chapter:](docs/academic_chapters/06_pulse_shape_ml.md)**

---

## 7. Amplitude, Charge & Energy Calibration

> **Thesis-grade update (2026-07-14).** Gain correction documented, absolute energy limitation derived. See [Full chapter](docs/academic_chapters/07_energy_calibration.md).

### Key Results

| Observable | Value | Status |
|---|---|---|
| Digitizer gain | 92 ± 28 ADC/MeV | **VALIDATED** (MV0 v2, corrected from ~246 ADC/MeV) |
| KS mismatch (MV0 v2) | 0.158 | **TENSION** (inter-stave variation unresolved) |
| Absolute energy uncertainty | ~35% | Structural limitation |
| ML duplicate-readout | Confirmed win domain | **GATED** |
| ML saturation recovery | Promising | **GATED** |

### What Is NOT Claimed
- **No absolute per-event energy calibration** (35% systematic)
- **No per-stave gain measurement** (±10% assumed, not measured)
- **No Birks constant calibration** (kB = 0.10–0.15 mm/MeV unverified for this scintillator)

**[Full chapter:](docs/academic_chapters/07_energy_calibration.md)**

## 8. Particle Identification

> **Thesis-grade update (2026-07-14).** Data weak-label vs MC truth AUC separated. See [Full chapter](docs/academic_chapters/08_particle_id.md).

### Key Results

| Observable | Value | Status | Caveat |
|---|---|---|---|
| p/d PID AUC | 0.9860 | **TRUTH_LEVEL_MC_ONLY** | MC truth only — not a data result |
| HGB purity at 90% eff. | 0.9644 | **TRUTH_LEVEL_MC_ONLY** | Upper bound on real-data performance |
| Data weak-label AUC | TBD | Not yet separated | Requires purity-efficiency confusion matrix |

### Critical Caveats

1. **AUC = 0.9860 is an MC-truth ceiling** — do not cite as a data result
2. **MV3 failure blocks B8 acceptance correction** — PID at B8 depth is unreliable
3. **Interpretable model needed** — HGB is not suitable for production PID

### MV3 Impact on PID

MV3 geometry FAIL (χ²/ndf = 68,269) → B8 stopping fraction unreliable → PID B8 acceptance biased.
Conservative recommendation: use B2+B4+B6 only (no B8) until MV3 is fixed.

**[Full chapter:](docs/academic_chapters/08_particle_id.md)**

---

## 9. Anomaly Identification

> **Thesis-grade update (2026-07-14).** Efficiency and false-positive study requirements documented. See [Full chapter](docs/academic_chapters/09_anomaly_id.md).

### Key Result

| Observable | Value | Status |
|---|---|---|
| C12 anomaly fraction | 0.32% of tracks | **VALIDATED** (MC-identified, MV6) |

### Required Studies (Not Yet Done)

- Anomaly detection efficiency (synthetic injection)
- False-positive rate (data sideband validation)
- Species composition of anomaly cluster

### Veto Impact (Conservative Estimate)
At 99% efficiency, 5% false-positive: events retained = 99.68%, background passed = 0.016%.

**[Full chapter:](docs/academic_chapters/09_anomaly_id.md)**

---

## 10. Monte Carlo Validation

> **Thesis-grade update (2026-07-14).** Full MV0-MV6 validation matrix documented. See [Full chapter](docs/academic_chapters/10_mc_validation.md).

### Validation Matrix

| Study | Observable | Verdict | Action |
|---|---|---|---|
| MV0 v2 | Digitizer gain | **VALIDATED** | Reduce systematic |
| MV1 | p/d PID | **TRUTH_LEVEL_MC_ONLY** | Data transfer needed |
| MV3 | Stopping depth | **FAIL** (χ²/ndf = 68,269) | **GEANT4 fix** |
| MV4 raw | Timing | **PASS** (−1.05σ) | Accept |
| MV4 corrected | Timing | **TENSION** (+2.68σ) | **Digitizer fix** |
| MV5 | Pile-up Rmax | **VALIDATED** | Independent τeff |
| MV6 | C12 anomaly | **VALIDATED** | Efficiency study |

### Two Blocking Issues

1. **MV3: Structural GEANT4 failure** — missing 8–10 g/cm²; blocks acceptance corrections
2. **MV4: Digitizer timewalk tension** — B/√ADC → B/A fix needed

**[Full chapter:](docs/academic_chapters/10_mc_validation.md)**

## 11. Open Questions & Next Steps

### Closed by MC Validation ✅

| Question | Closed By | Finding |
|---|---|---|
| What is the early-peak anomaly? | MV6 | C12 nuclear recoils (55%); GMM veto >99% capture |
| Does R_max ~3 MHz hold vs MC? | MV5 | MC = 3.044 MHz, data = 3.05 MHz (0.2%) |
| What is the digitizer gain? | MV0 v2 | 92 ± 28 ADC/MeV (net-ADC basis) |
| Is p/d PID at AUC 0.986 real? | MV1 | Yes; data within 0.5% of MC ceiling |
| What is the dE/dx mechanism? | MV2 | Birks-law energy deposition; p 23 MeV, d 89 MeV |
| Does raw timing match MC? | MV4 | Yes — pull = −1.05σ (PASS; pull = (MC−data)/sqrt(σ_MC^2 + σ_data^2) with σ_data = 0.10 ns assumed, not measured) |

### Still Open 🔶

| Question | Blocker | Severity | Action |
|---|---|---|---|
| Stopping-depth profile (chi2/ndf = 68,269) | Missing inter-stave dead material in MC geometry | ⛔ HIGH | Update GEANT4 geometry; new MC production |
| Timewalk-corrected σ₆₈ at +2.68σ? | Toy digitizer CFD sign error | 🔶 HIGH | Switch B/√ADC→B/amplitude; rerun MV4 |
| ML two-pulse failure rate on true overlaps? | No truth-labelled overlay MC | ⚠️ MEDIUM | MC overlay study (MV5 extension) |
| Two-ended √2 projection valid? | Ignores correlated terms | ⚠️ MEDIUM | Measure correlation; validate projection |
| Forced-pedestal validated? | No forced-trigger in data | ⚠️ MEDIUM | Next beam run acquisition |
| CFD/OF parameters optimal? | Never systematically scanned | LOW | Grid search over fraction/window |
| Gaussian-core fits have χ²/ndf? | Reporting omission | LOW | Add goodness-of-fit to all fits |
| Absolute TOF scale validated? | No independent reference | LOW | Cross-check against TPC/trigger |

### Missing Studies

See [`STUDY_GAPS.md`](STUDY_GAPS.md) for the complete prioritized list. Key items:

1. Multi-stave event reconstruction with proper **covariance modeling** (not assuming independence)
2. Two-ended readout with **measured** (not assumed) correlation
3. Full **Birks-law energy calibration** across all staves
4. Complete **systematic uncertainty propagation** through all derived quantities
5. **A-stack full reproduction** (currently only A1-A3 timing done)
6. Beam-rate scan analysis (if multiple currents in data)

---

## 12. Methodology Appendix

### 12.1 Core Principles

Every claim obeys **six rules** (from [`docs/REPORT_STANDARD.md`](docs/REPORT_STANDARD.md)):

1. **Reproduce first** — start from the S00 640,737-pulse gate
2. **Fair comparison** — ML vs strongest traditional baseline, same held-out data, CI excludes zero
3. **Atomic decomposition** — every step from raw waveform to number is traceable
4. **Leakage is hunted** — three controls must all pass
5. **Numbers always paired** — with uncertainty and baseline comparison
6. **CORRECTED is a finding** — discovering leaked ML wins advances the program

### 12.2 The Three Leakage Controls

```
1. Target Shuffle         — shuffle labels; if ML still "wins", no signal
2. Leave-One-Run-Out      — train on runs 31-57, test on 58-65
3. Event-Block Shuffle    — shuffle in event blocks; catches temporal leakage
```

**A claim is REJECTED unless it beats the traditional baseline on ALL THREE with a CI excluding zero.**

### 12.3 Confidence Labels

| Label | Meaning |
|---|---|
| ✅ **Validated (data + MC)** | Survives leakage controls AND agrees with GEANT4 truth |
| ⚠️ **Data-only (MC pending)** | Survives leakage controls but MC not yet run |
| ❌ **CORRECTED** | Failed leakage control or MC cross-check |
| 🔶 **TENSION** | MC and data disagree beyond tolerance |
| ⛔ **FAIL** | MC reveals concrete model failure |

### 12.4 Truth Types

| Type | Example | Used For |
|---|---|---|
| **Closure truth** | Injected pile-up, artificial saturation | Injected by us, independent by construction |
| **Proxy truth** | Duplicate readout | Correlated but physically independent measurement |
| **Physics truth** | GEANT4 particle ID, energy | Absolute truth from simulation |

### 12.5 Uncertainty Conventions

- All σ values are **robust σ₆₈** (half-width of central 68%)
- CIs use **bootstrap (1000 resamples)** at the **run level**
- AUC to 4 decimal places (from MV1 truth summary)
- Every number traceable to a `reports/<id>/REPORT.md`

---

## Study Catalogue

Every study with a proper descriptive name and hyperlink to its full report.

### Foundation Studies (S00–S18)

| Code | Descriptive Name | Report |
|---|---|---|
| **S00** | [Data Integrity & Pipeline Reproduction](reports/1780997954.15097.28a25ecb__s00a_sorted_hrdmax_semantics/) | 640,737 pulses reproduced exactly |
| **S00a** | Sorted hrdMax Gate Semantics | Sorted proxy over-counts; raw HRDv gate is correct |
| **S01** | [Amplitude-Adaptive Template Reconstruction](reports/1780997954.15037.36463764__s01_full_dataset_templates/) | Full-dataset templates, per-stave per-amplitude bin |
| **S02** | [Timing Pickoff Comparison](reports/1780997954.15157.07ef03cf__s02_timing_pickoff/) | CFD20 vs OF vs template phase |
| **S02b** | Template Timewalk Closure | |
| **S03** | [Analytic Timewalk Correction](reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction/) | Amplitude timewalk reaches σ₆₈ 1.49–1.55 ns |
| **S03a** | Amplitude-Binned Monotonic Timewalk | |
| **S03k** | Gated HGB Timing | σ₆₈ = 1.107 ns (in-fold); needs transfer audit |
| **S05** | [Hierarchical B-Stack Covariance](reports/) | B2 covariance ~1042 ns² vs downstream ~16 ns² |
| **S05a** | A-Stack External Control | |
| **S07** | [ML Rigor Scoreboard](reports/1780997954.15217.702122ea__s07_ml_rigour_scoreboard/) | Most ML "wins" are leaked; CORRECTED claims |
| **S10** | [Pile-up Rate Model](reports/1780997954.15277.548b01a3__s10_pileup_rate_model/) | τ_eff = 124.8 ns → R_max ≈ 3.05 MHz |
| **S11** | [Two-Pulse Template + ML Recovery](reports/) | ML wins RMS but higher failure rate |
| **S14** | Range-Energy Calibration | GEANT4 Birks lookup validated |
| **S16** | [Pedestal/Baseline Validation](reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/) | Adaptive pedestal biased −311 ADC |
| **S18** | [A-Stack Independent Reproduction](reports/1780997954.15397.168324f2__s18_astack_independent_reproduction/) | A1–A3 width 1.39 ns reproduces note's 1.43 ns |

### ML Pulse Characterisation (P01–P13)

| Code | Descriptive Name | Report |
|---|---|---|
| **P01** | [Self-Supervised Waveform Representation](reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation/) | AE > PCA at d=2–4; PCA catches up at d≥8 |
| **P02** | [Unsupervised Pulse-Type Discovery](reports/) | ~4% early-peak anomaly found |
| **P03** | Deep Timing Regression | MLP/CNN on raw waveform |
| **P04** | [Amplitude & Charge Regression](reports/) | ML wins duplicate-readout: res68 0.003 vs 0.12 |
| **P05** | Two-Pulse CNN Decomposition | |
| **P07** | [Saturation Recovery](reports/1780997954.15577.6c203777/) | ML 3–7× better than templates |
| **P09** | Rare Waveform Anomaly Taxonomy | ~4% → 0.32% after MC identification |

### MC Validation (MV0–MV6)

| Code | Descriptive Name | Report | Verdict |
|---|---|---|---|
| **MV0** | [Digitizer Gain Calibration](reports/mv0_digitizer/) | 92 ± 28 ADC/MeV (v2 corrected) | ✅ |
| **MV1** | [Proton/Deuteron PID Validation](reports/mv1_mv2_truth_pid_energy/) | AUC 0.986, purity 0.964 | ✅ |
| **MV2** | [Energy/Range Truth Validation](reports/mv1_mv2_truth_pid_energy/) | p 23 MeV, d 89 MeV | ✅ |
| **MV3** | [Stopping-Depth Profile](reports/mv3_stopping_depth/) | χ²/ndf = 68,269 (4 bins: B2, B4, B6, B8 fractions; ndf = 3 after normalization; Poisson bin errors) | ⛔ |
| **MV4** | [Timing Resolution Validation](reports/mv4_timing_study/) | Raw PASS, corrected TENSION | 🔶 |
| **MV5** | [Pile-up Rate Validation](reports/mv5_pileup_study/) | R_max = 3.044 MHz (0.2%) | ✅ |
| **MV6** | [Representation & Anomaly ID](reports/mv6_representation_study/) | C12 recoils 0.32% | ✅ |

---

## See Also

- **[`FINDINGS_SYNTHESIS.md`](FINDINGS_SYNTHESIS.md)** — publication-standard narrative across all ~230 studies
- **[`PROJECT_REPORT.md`](PROJECT_REPORT.md)** — concise single-page status
- **[`STUDY_GAPS.md`](STUDY_GAPS.md)** — detailed gap analysis and open questions
- **[`studies/STUDIES.md`](studies/STUDIES.md)** — master prioritized study list
- **[`docs/REPORT_STANDARD.md`](docs/REPORT_STANDARD.md)** — reporting rules and methodology
- **[`docs/METHOD_LOGIC_TRACE.md`](docs/METHOD_LOGIC_TRACE.md)** — step-by-step analysis chain
- **[`docs/SYSTEMATIC_UNCERTAINTIES.md`](docs/SYSTEMATIC_UNCERTAINTIES.md)** — detailed systematic budget
- **[`docs/glossary.md`](docs/glossary.md)** — terminology reference
- **[`DATA.md`](DATA.md)** — data locations and integrity
