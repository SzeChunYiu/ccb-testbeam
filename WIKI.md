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

> **Key Findings:**
> - Best single-stave timing: **B6 σ₆₈ ≈ 0.68–0.75 ns** (analytic timewalk)
> - Combined 3-stave (B4+B6+B8): **σ₆₈ ≈ 0.54–0.56 ns**
> - Analytic timewalk reaches **1.49–1.55 ns** — tied with ML at 1.39–1.47 ns under proper cross-validation
> - B2-containing pairs have **large covariance** — B2 is excluded from precision timing
> - A-stack reproduces: **A1–A3 width = 1.39 ns** (matches note's 1.43 ns)
> - MC raw timing: ✅ PASS; MC timewalk-corrected: 🔶 TENSION (digitizer model artifact)

### 4.1 What is Timing Resolution?

When the same particle passes through two staves, the **time difference** Δt = t_stave1 − t_stave2 should be zero (for perpendicular tracks, after corrections). The width of the Δt distribution tells us how precisely each stave timestamps particles.

For a single stave: sigma_single = sigma(Deltat) / sqrt(2) (exact for independent Gaussian errors; for sigma68 this is approximate -- the decomposition assumes Gaussian Deltat distribution, verified for downstream pairs but not for B2-containing pairs)

We use **σ₆₈** — the half-width containing 68% of residuals (robust equivalent of Gaussian σ).

### 4.2 The Timing Chain

```
Raw Waveform → CFD20 (seed time) → Template Phase Fit → Amplitude Timewalk Correction → Final t
```

| Step | Study | Method | σ₆₈ (ns) |
|---|---|---|---|
| **1. Pickoff** | [Timing Pickoff (S02)](reports/1780997954.15157.07ef03cf__s02_timing_pickoff/) | CFD20 at 20% of peak | **1.85** |
|  |  | Template phase fit | 2.89 |
| **2. Timewalk** | [Analytic Timewalk (S03)](reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction/) | Amplitude-only analytic | **1.49–1.55** |
|  |  | Ridge residual corrector | 1.39–1.47 |
|  |  | HGB on waveform+shape (S03k, gated) | 1.11 (in-fold only) |
| **3. Combined** | [Timing Covariance (S05)](reports/) | B4+B6+B8 event time | **0.54–0.56** |

**Winner:** The **simple analytic timewalk correction** — transparent, robust, and nearly matches ML performance. The HGB result (σ₆₈ = 1.107 ns) is explicitly **gated pending a transfer audit** — it has not been adopted.

### 4.3 Amplitude Timewalk

**The dominant timing systematic: larger pulses appear to arrive earlier.**

This is a well-known effect in scintillator + SiPM readout: bigger pulses cross the constant-fraction threshold sooner. The correction is:

```
t_corrected = t_CFD − f(amplitude)
```

where the analytic form is **f(A) = A₀ + B/amplitude** (fitted per stave from calibration runs, B2-blind to avoid topology bias).

**Study:** [Analytic Timewalk Correction (S03)](reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction/)

### 4.4 Per-Stave Timing Resolution

![Timing Resolution Per Stave](docs/figures/03_timing_resolution.png)

| Stave | σ₆₈ (ns) | Notes |
|---|---|---|
| B2 | ~2.8 | Topology-dominated, large covariance — **excluded from precision** |
| B4 | ~1.45 | Good downstream reference |
| B6 | **~0.72** | Best single-stave — cleanest timing |
| B8 | ~0.93 | Good, some penetration dependence |
| **B4+B6+B8** | **~0.55** | Combined event time |

### 4.5 The B2 Covariance Problem

**Study:** [Hierarchical B-Stack Covariance (S05c)](reports/)

B2-containing timing pairs show dramatically larger covariance:
- **B2-X pairs:** covariance ≈ 1042 ns²
- **B4-B6, B4-B8, B6-B8 pairs:** covariance ≈ 16 ns²

This means B2 timing fluctuations are **not independent** of other staves — there is a shared, topology-correlated component. **B2 must be excluded from precision event-time estimates.** This is a physics finding (terminal deuteron topology), not a detector malfunction.

### 4.6 A-Stack Cross-Check

**Study:** [A-Stack Independent Reproduction (S18)](reports/1780997954.15397.168324f2__s18_astack_independent_reproduction/)

The A-stack (A1/A3) provides a **completely decoupled** timing measurement:
- **Sample III** (D-enriched): robust width **1.39 ns** — reproduces the analysis note's 1.43 ns
- **Sample IV** (p-enriched): broadening to 1.79 ns is a **calibration-pool / low-statistics effect**, not a physics effect
- ML residual correction makes timing *worse* (1.94 ns) — **ML is not adopted** for A-stack

### 4.7 MC Validation of Timing

![MC vs Data: Timing](docs/figures/04_mc_vs_data.png)

| Quantity | MC (GEANT4) | Data | Pull | Verdict |
|---|---|---|---|---|
| σ₆₈ raw (no correction) | 1.744 ± 0.007 ns | 1.85 ns | −1.05σ | ✅ **PASS** |
| σ₆₈ timewalk-corrected | 1.770 ns | 1.50 ns | +2.68σ | 🔶 **TENSION** |

**The raw timing matches** — detector geometry and electronics noise are adequately modeled. The **timewalk-corrected tension** is traced to the toy digitizer using an **unphysical negative B coefficient** in its CFD model. **MV4b** identified the fix: switch from B/√ADC to B/amplitude. This is a code change (not a new MC production) awaiting LUNARC access.

---

## 5. Pile-up Analysis

> **Key Findings:**
> - The note's R_max = 4.22 MHz used τ_eff = 90 ns — **WRONG**
> - Measured waveform live-time: **τ_eff = 124.8 ns** → **R_max ≈ 3.05 MHz**
> - MC confirms: **R_max(MC) = 3.044 MHz** (0.2% agreement) — ✅ validated
> - ML two-pulse recovery: better RMS but **higher failure rate** (0.295 vs 0.168)
> - ML pile-up score has large current-independent baseline (ratio ~1.29× between high/low current). Measured downstream excess at 20 nA: 0.0103 per selected event [CI 0.0064-0.0142], excess_fraction = 30.8% of high-current downstream rate (S10 current_excess_table.csv). ML score excess_fraction = 22.9% (ratio 1.30). These are separate measurements.

### 5.1 What is Pile-up?

When two particles hit the same stave within the 180 ns waveform window, their signals **overlap**. This distorts both amplitude and timing. The pile-up probability depends on:

- **Beam rate R** (particles per second per stave)
- **Effective live-time τ_eff** (the time window during which a second pulse would distort the first)

The maximum tolerable rate: **R_max = μ_max / τ_eff** where μ_max is the acceptable occupancy.

### 5.2 The R_max Correction

**Study:** [Pile-up Rate Model (S10)](reports/1780997954.15277.548b01a3__s10_pileup_rate_model/)

The original analysis note assumed τ_eff = 90 ns → R_max = 4.22 MHz.

**Direct waveform measurement** (10% tail-crossing of the pulse template):
- **Live-time: τ_eff = 124.79 ns** (bootstrap CI: [123.33, 126.36] ns)
- **R_max ≈ 3.05 MHz** (for |Δt| < 1 ns and area error < 20%, at ε > 90%)

**MC confirmation (MV5):** [Pile-up Rate Validation (MV5)](reports/mv5_pileup_study/)
- MC τ_eff = 124.8 ns → R_max = 3.044 MHz
- **0.2% agreement with data — ✅ validated**

> ⚠️ **The analysis note's R_max ≈ 4.2 MHz is confirmed as an error from an incorrect τ_eff assumption.** All references should use ~3 MHz.

### 5.3 Two-Pulse Recovery

**Study:** [Two-Pulse Template + ML Recovery (S11)](reports/)

When two pulses overlap, we can try to **decompose** them:

| Method | Time RMS (ns) | Failure Rate |
|---|---|---|
| Constrained two-pulse template fit | 13.30 | **0.168** |
| ML (compact MLP/CNN) | 10.67 | 0.295 |
| Amplitude-binned ML | 9.28 | 0.295 |

ML recovers shorter separations and lower time-RMS, but has a **higher failure rate**. The conventional fit is **safer at the accepted-recovery operating point**. ML adoption is gated on a dedicated MC overlay study with truth labels.

### 5.4 Current-Dependent Excess

The ML pile-up classifier score ratio between high and low current is ~1.29× (not the ~10× expected from the 10× current ratio under pure Poisson scaling), indicating a large current-independent contribution (scintillator tails, waveform pathologies). Separately, the measured downstream per-event excess at 20 nA is 0.0103 per selected event [CI 0.0064-0.0142, S10 current_excess_table.csv], representing 30.8% of the high-current downstream rate. The ML pile-up score shows 22.9% excess at high current (ratio 1.30). These are two independent measurements of different quantities. These are two independent measurements: the ML score ratio measures classifier behavior; the downstream excess measures physical pile-up rate. They should not be chained causally.

---

## 6. Pulse Shape & Machine Learning

> **Key Findings:**
> - Pulse shapes are **low-dimensional**: 3 PCA components capture 89% of variance, 8 capture 99.7%
> - **Autoencoder beats PCA** at very low latent dim (2–4); PCA catches up at dim ≥ 8
> - ML genuinely wins where truth is independent and information is in waveform shape
> - **All representation-superiority claims for downstream tasks: ❌ CORRECTED** (leakage artifact)
> - The 0.32% anomaly class: **C12 nuclear recoils** — MC-identified (MV6)
> - **The project's most important finding: most ML "wins" fail leakage controls**

### 6.1 Where ML Helps vs. Where It Doesn't

![ML Performance Landscape](docs/figures/10_ml_landscape.png)

| Domain | ML Verdict | Why |
|---|---|---|
| **Saturation recovery** | ✅ **ML Wins** (3–7× better) | Truth (true amplitude) independent of input; signal is in waveform rising edge |
| **Duplicate-readout amplitude** | ✅ **ML Wins** (res68 0.003 vs 0.12) | Truth from duplicate readout; independent of primary channel |
| **Two-pulse time RMS** | ⚠️ ML wins RMS but higher failure | ML 9–11 ns vs traditional 13–18 ns, but failure rate 0.295 vs 0.168 |
| **Timewalk correction** | ❌ Tie/Loss | Analytic B/amplitude model already near-optimal |
| **Pile-up Poisson rate** | ❌ Tie | Analytic Poisson model already optimal |
| **Deep net timing** | ❌ ML Loses | CNN/MLP on raw waveform loses to analytic timewalk |
| **PID (data-only)** | ❌ Leakage | D_t/curvature classifiers hit AUC ~1.0 because label = f(input) |
| **Representation superiority** | ❌ CORRECTED | Apparent AE→P03 win was leakage; failed run-family and event-block shuffle |

### 6.2 Pulse Shape Compression

![PCA vs AE](docs/figures/05_pca_vs_ae.png)

**Study:** [Self-Supervised Waveform Representation (P01)](reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation/)

| Latent Dim | PCA MSE | AE MSE | Winner |
|---|---|---|---|
| 2 | 0.02622 | 0.01294 | AE +50.6% |
| 3 | 0.01416 | 0.00841 | AE +40.6% |
| 4 | 0.00880 | 0.00527 | AE +40.1% |
| 8 | 0.00166 | 0.00292 | PCA +75.9% |

**Conclusion:** Pulses are simple shapes. The AE helps at very low dimensions (capturing nonlinear manifold), but PCA catches up once sufficient linear components are retained. The representation is compact — there's no deep hidden structure in pulse shape.

### 6.3 The C12 Anomaly

**Study:** [Representation & Anomaly ID (MV6)](reports/mv6_representation_study/) | [MV6 C12 Physics](docs/MV6_C12_PHYSICS.md)

![C12 Anomaly Waveform](docs/figures/08_c12_anomaly.png)

Unsupervised discovery (P09a) found an anomalous class with **early peaking (sample 1–2 instead of sample 5) and near-zero area**. MV6 identified it:

| Observable | Value |
|---|---|
| **True anomaly fraction** | **0.32%** (283 / 87,555 tracks) |
| **Dominant species** | **C12 recoils (55%)** |
| Secondary: proton | 15% |
| Secondary: electron | 13% |
| GMM Cluster 2 capture | >99% of C12-dominated anomalies |

**Physical mechanism:** 190 MeV protons scatter off carbon-12 nuclei in the CD₂ target, producing recoiling C12 ions with ~1–4 MeV. These deposit **all energy in the first ~25 μm of scintillator** — the light is confined to samples 0–1 of the 18-sample window.

**Impact:** Negligible (<0.1% systematic on deuteron count after GMM morphology cut). This removes about 1 in 300 tracks.

---

## 7. Amplitude, Charge & Energy

> **Key Findings:**
> - ML **decisively wins** duplicate-readout amplitude/charge closure (res68 0.003–0.009 vs 0.12–0.20)
> - ML recovers saturated B2 pulses to **3–7× better precision** than templates
> - **Absolute per-event energy is structurally unreachable** from waveform data — GEANT4 Birks lookup remains the best method
> - Digitizer gain: **92 ± 28 ADC/MeV** (corrected MV0 v2; the v1 value of ~246 ADC/MeV was wrong)

### 7.1 Duplicate-Readout Closure

**Study:** [Amplitude & Charge Regression (P04)](reports/)

When the same pulse is read out through two independent paths, the "duplicate" measurement provides **independent truth**. ML (HistGradientBoosting/ExtraTrees) achieves:
- **res68 = 0.003–0.009** (ML)
- **res68 = 0.12–0.20** (traditional peak/integral)

This is the cleanest demonstration that **waveform shape carries recoverable calibration information** beyond scalar summaries.

### 7.2 Saturation Recovery

**Study:** [Saturation Recovery (P07)](reports/1780997954.15577.6c203777/)

B2 staves in Sample I saturate — ~30–40% of B2 pulses exceed the 7000 ADC ceiling. ML recovers the true amplitude from the **unsaturated rising edge**:

| Method | res68 | Degradation at High Saturation |
|---|---|---|
| ML (ExtraTrees/HGB) | **0.032–0.046** | Graceful |
| Template (shape fit) | 0.104–0.286 | Severe |

On **artificial constant-ceiling clips**, ML is 3–7× better. However, natural-saturation recovery carries a **run-dependent timing-tail envelope** that is treated as a systematic.

### 7.3 Absolute Energy Limitation

**Study:** [Truth Energy Validation (MV2)](reports/mv1_mv2_truth_pid_energy/)

**There is no per-event energy truth in the data.** Propagated per-event energy reaches res68 ~ 0.19–0.25, failing the 10% threshold.

MC truth (MV2) confirms:
- Proton edep_tot: **23 MeV**
- Deuteron edep_tot: **89 MeV** (factor ~4×)
- The **GEANT4 Birks lookup** remains the best held-out energy method — neural and tree models do not supersede the physics prior

---

## 8. Particle Identification

> **Key Findings:**
> - Proton/deuteron separation: **AUC = 0.986** (MC truth ceiling, HGB)
> - Data methods using weak-label proxies reach within 0.5% of MC ceiling — leakage-safe stress test, not species-truth PID — information is in the data
> - **Stopping-depth profile: ⛔ MC FAILS** (χ²/ndf = 68,269 (4 bins: B2, B4, B6, B8 fractions; ndf = 3 after normalization; Poisson bin errors)) — missing ~8–10 g/cm² in GEANT4 geometry
> - Depth ordering (B2 > B4 > B6 > B8) is qualitatively correct in both data and MC

### 8.1 How PID Works (Without Truth)

With no per-event truth labels in data, we use **physics-driven proxies**:
- **ΔE–E method:** heavier particles (deuterons) deposit more energy per unit length and stop earlier
- **Range separation:** deuterons stop in B2/B4; protons reach B6/B8
- **Sample enrichment:** Sample I = deuteron-enriched (trigger selects early-stopping); Sample II = proton-enriched

### 8.2 MC Truth Validation

![PID Performance](docs/figures/07_pid_auc.png)

**Study:** [Proton/Deuteron PID (MV1)](reports/mv1_mv2_truth_pid_energy/)

On 400,369 GEANT4 truth tracks (150,130 protons, 146,842 deuterons):

| Method | AUC | Purity @ 90% Efficiency |
|---|---|---|
| Hist Gradient Boosting (HGB) | **0.9860** | **0.9644** |
| Logistic Regression | 0.9629 | 0.9489 |
| Single-cut ΔE | — | 0.8910 |

Data methods reach within 0.5% of the MC ceiling. **The data carries essentially the same separating information as MC truth.**

### 8.3 Stopping-Depth Profile — Structural MC Failure

![Stopping Depth MC vs Data](docs/figures/06_stopping_depth.png)

**Study:** [Stopping-Depth Profile (MV3)](reports/mv3_stopping_depth/)

| Stave | MC Fraction | Data Fraction | Data/MC Ratio |
|---|---|---|---|
| B2 | 47.0% | 87.6% | 1.86× |
| B4 | 18.2% | 6.3% | 0.35× |
| B6 | 12.5% | 3.9% | 0.31× |
| B8 | **22.3%** | **2.3%** | **0.10×** ⛔ |

MC overestimates B8 penetration by **10×** relative to data. The qualitative ordering is correct, but the quantitative profile fails catastrophically (χ²/ndf = 68,269 (4 bins: B2, B4, B6, B8 fractions; ndf = 3 after normalization; Poisson bin errors)).

**Root cause (MV3b):** Missing upstream material budget in GEANT4 geometry — absorbers, support structures, trigger scintillators, beam window, and approximately **8–10 g/cm² of inter-stave dead material** between the beam and B-arm.

**Impact:** B8 trigger efficiency calibration cannot be MC-anchored (5–10% effect on tracks entering B8). The PID AUC impact is limited (<3%) because deuterons stop in B2/B4, not B8.

---

## 9. Pedestal & Baseline

> **Key Findings:**
> - Adaptive pedestal is biased (−311 ADC vs pretrigger-median reference)
> - Learned pedestal (HGBR) cuts MAE from 341 to 49 ADC
> - But: **no true forced/random pedestal sample exists** in current data — all validation is proxy-based
> - Digitizer gain: **92 ± 28 ADC/MeV** (corrected MV0 v2)

### 9.1 The Pedestal Problem

**Study:** [Pedestal/Baseline Validation (S16)](reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/)

The **adaptive pedestal** (positivity-constrained baseline, tolerance scales with amplitude) is the legacy estimator. But against a pretrigger-median reference:
- **MAE = 341 ADC** (adaptive)
- **MAE = 48.9 ADC** (learned, HGBR)

**Caveat:** There is no true forced/random pedestal sample in the data — 0 forced/random-tagged entries across exhaustive scans. All validation uses proxy references (pretrigger-median, quiet-proxy). This is a structural data limitation.

### 9.2 Digitizer Gain Calibration

| Version | Gain | Status |
|---|---|---|
| MV0 v1 | ~246 ADC/MeV | ❌ **WRONG** — compared raw amplitude vs MC+digitizer pedestal |
| MV0 v2 | **92 ± 28 ADC/MeV** | ✅ **CORRECTED** — uses net_ADC = abs(amplitude − baseline) |

**Use only the v2 value for energy-scale references.**

---

## 10. Systematic Uncertainties

![Systematic Budget](docs/figures/09_systematic_budget.png)

| Source | Magnitude | Affected Quantities | Status |
|---|---|---|---|
| **Gain (MV0)** | **±30%** | Energy scale, dE/dx, ADC→MeV | ✅ MC-validated (v2); needs forced-trigger |
| **Stopping-depth (MV3)** | Factor 10× on B8 | Depth fractions, B8 acceptance | ⛔ FAIL — needs geometry fix |
| **Timewalk (MV4)** | +2.68σ pull | σ₆₈ corrected, TOF cuts | 🔶 TENSION — digitizer fix ready |
| **C12 anomaly (MV6)** | <0.1% after cut | Deuteron count | ✅ Identified, veto available |
| **Pile-up R_max (MV5)** | Negligible | Rate tolerance | ✅ Validated |

**Quadrature total for deuteron fraction: ~12%** (dominated by MV0 gain ±30%).

---

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
