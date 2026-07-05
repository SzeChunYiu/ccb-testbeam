# CCB Test-Beam Analysis — Unified Illustrated Wiki

> **A self-contained guide to the CCB test-beam analysis, written for readers with and without prior knowledge of particle physics instrumentation.**
>
> Every study has a **descriptive name** and a **hyperlink** to its full report. Claims are traceable to source, and numbers carry uncertainties where the source artifact provides them; where a source publishes no uncertainty (or a claim is under review), that gap is flagged inline rather than papered over.
>
> **Repository:** [SzeChunYiu/ccb-testbeam](https://github.com/SzeChunYiu/ccb-testbeam) | **Started:** 2026-06 | **Status:** Research synthesis (preliminary, not yet peer-reviewed)
>
> **Correction 2026-07-03:** an external review ([`EXTERNAL_REVIEW_2026-07-02.md`](EXTERNAL_REVIEW_2026-07-02.md)) found the MC-validation layer unsound; corrections are applied throughout this wiki.
>
> **Update 2026-07-03 (post-review reruns):** three honest reruns landed the same day: **S21** confirms the Sample-I deuteron-enrichment hypothesis at truth level ([§8.4](#84-trigger-truth-deuteron-enrichment-s21--confirmed)); **MV4** was rerun with a rising-edge CFD and physical timewalk sign, verdict REVIEW ([§4.7](#47-mc-validation-of-timing-mv4-honest-rerun)); **MV2** was rerun after the momentum-unit fix and now reports MeV-scale energies ([§7.3](#73-absolute-energy-limitation)).
>
> **Update 2026-07-04 (post-review program complete):** the full correction program (Phases 0–4 + statistics hardening) is done. Headlines: **MV3's stopping-depth discrepancy is strongly indicated (pending `Trig_bar` simulation) to be the unsimulated two-arm coincidence trigger, not missing material** — re-graded FAIL → TENSION, χ²/ndf 68,269 → 625 ([§8.3](#83-stopping-depth-profile--fail-re-graded-tension-root-cause-the-trigger)); the Sample-I deuteron enrichment is confirmed at truth level and **consistent in data** (S23, run-set differences not yet separated, [§8.5](#85-data-side-sample-iii-closure-s23--consistent-in-data)); per-stave timing vs amplitude is measured (S22, [§4.8](#48-timing-resolution-vs-amplitude-s22)); the honest truth-labelled two-pulse benchmark replaces the rigged S11a table and the first independent MC live-time exists (MC03/S24, [§5.2–5.3](#52-the-r_max-correction)); **C12 recoils are ruled out** as the early-peak class (MV6b, [§6.3](#63-the-early-peak-anomaly-c12-ruled-out)); MV7 pedestal validation ran on zero-signal MC ([§9](#9-pedestal--baseline)); a program-level FDR census covers all delta-CI claims ([§12.5](#125-uncertainty-conventions)). Synthesis: `FINDINGS_SYNTHESIS.md` "Post-review program (2026-07-03/04)".

---

## Quick Navigation

| I want to... | Go to |
|---|---|
| See the key results at a glance | [§1 Executive Summary](#1-executive-summary) |
| Understand the experiment | [§2 Experimental Setup](#2-experimental-setup) |
| Follow the data from raw files | [§3 Data Pipeline](#3-data-pipeline) |
| Understand timing resolution | [§4 Timing Analysis](#4-timing-analysis) |
| Learn about pile-up | [§5 Pile-up Analysis](#5-pile-up-analysis) |
| See where ML helps (or doesn't) | [§6 Pulse Shape & Machine Learning](#6-pulse-shape--machine-learning) |
| Check the methodology | [§12 Methodology Appendix](#12-methodology-appendix) |
| Find what's still missing | [§11 Open Questions](#11-open-questions--next-steps) and [`STUDY_GAPS.md`](STUDY_GAPS.md) |
| Browse all studies with proper names | [Study Catalogue](#study-catalogue) |

---

## 1. Executive Summary

### What is this project?

This project analyzes data from a **test-beam experiment** at the **Cyclotron Centre Bronowice (CCB)** in Kraków, Poland. A beam of **190 MeV protons** struck a **deuterated polyethylene (CD₂) target**, and the resulting charged particles were measured by **HRD scintillator range stacks** — detectors that stop particles in successive layers ("staves") to measure their energy and type.

Each scintillator stave records a **180-nanosecond waveform** (18 samples, one every 10 ns). From these waveforms we extract **pulse amplitude**, **arrival time**, and **pulse shape**. The physics goals are:

1. **Same-particle timing resolution** — how precisely can we timestamp when a particle hits each stave?
2. **Pile-up characterization** — how often do overlapping pulses degrade our measurements, and at what beam rate does this become the limiting factor?

The analysis is **data-driven** (no per-event Monte Carlo truth), but uses **GEANT4 Monte Carlo simulations** as a "truth bridge" to validate key findings.

### Key Results at a Glance

| Measurement | Value | Confidence |
|---|---|---|
| Selected B-stack pulses | **640,737** (exact reproduction) | ✅ Validated (S00) |
| Best single-stave timing (B6) | **σ(core) ≈ 0.68–0.75 ns** (external-note Gaussian-core decomposition; not σ₆₈, not MC-validated) | ⚠️ Under review |
| Combined 3-stave (B4+B6+B8) | **σ ≈ 0.54-0.56 ns** | ⚠️ Under review (covariance validation withdrawn 2026-07-03; assumes independent stave errors — unmeasured) |
| Pile-up tolerance R_max | **≤ 3.05 MHz** (one-sided upper bound, corrected from 4.22 MHz; censoring-aware estimators suggest ≈2.1 MHz or lower) | ⚠️ Data-driven bound; first independent MC live-time disagrees by +8% (MC03: 134.99 vs 124.79 ns) — the excess, if real, **tightens the bound rather than validating it** |
| Proton/deuteron PID | **AUC = 0.986** (MC truth ceiling; data reaches it only via weak-label proxies, not species truth) | ⚠️ MC truth ceiling only; the data side uses weak-label proxies, not species truth (MV1, rerun 2026-07-03) |
| Sample-I deuteron enrichment (B2) | truth: **ratio 1.519 [1.510, 1.528]** (exclusive 1.912); data: **f(A>5000) ratio 3.45 [3.41, 3.50]** | ✅ Confirmed at truth level (S21); **consistent in data** (S23, 2026-07-03; run-set differences not yet separated); MC under-predicts the contrast (DR 0.738, z = −99 statistics-only; systematics from disjoint run-sets/beam conditions not included) |
| MV3 stopping-depth discrepancy | root cause = **unsimulated two-arm coincidence trigger**; χ²/ndf 68,269 → **625 (109×)** with trigger proxy + event basis + species-inclusive + gain 60 | 🔶 Re-graded FAIL → TENSION (Phase 2, 2026-07-03); missing-material narrative falsified |
| MC timing (MV4 honest rerun) | MC pair-equivalent **2.087 ± 0.009 ns**, between data raw 2.993 ns and corrected 1.50 ns | ⚠️ REVIEW — unmatched comparison; matched per-stave rerun pending |
| Per-stave timing vs amplitude (S22) | downstream per-stave σ ≈ **0.85–1.1 ns** at high amplitude; raw curves follow 1/A better than 1/√A | ✅ Measured (2026-07-03); B2 saturation-excluded |
| Two-pulse recovery (honest benchmark) | trad wins at matched 80% coverage; ML wins at full coverage (0.011 vs 0.048); σ68 trad 0.64 / ML 0.89 ns | ✅ Truth-labelled (MC03/S24, 2026-07-04; replaces the rigged S11a table) |
| Anomaly class identity | **NOT C12 recoils** — 0/1,656 quenched C12 records pass A>1000 at any gain | ✅ Ruled out (MV6b, 2026-07-04); class must be instrumental/trigger-phase — data-side question |
| Digitizer gain | **≈ 60–80 ADC/MeV, dominated by trigger/quenching modelling — no precision value yet** (v1 246 and v2 92 ± 28 both retracted; 297 = explicit placeholder) | ⚠️ Trigger-consistent scan optimum ~60 (unquenched); quenched re-scan pending (~70–80 expected) |
| ML wins domains | Duplicate-readout, saturation recovery | ⚠️ Data-only |

> **Global note on the confidence intervals in this table.** Sub-0.1 ns and sub-percent CIs quoted
> above (and throughout this wiki) are **statistics-only**. Where the same quantity carries a
> %-level data–MC discrepancy (e.g. the MC τ_eff CI ±0.025 ns against a +8% data offset; the S23
> double ratios with z = −99), the systematic difference dominates and the statistics-only CI does
> **not** bound the physical value. Treat those CIs as internal-precision figures, not uncertainties
> on the physics.
>
> **Grade key (words + number make the verdict; the emoji is a mnemonic only).**
> **G1 Validated** (truth + data, no dominant unquantified systematic) · **G2 Confirmatory/negative**
> (a clean exclusion or truth ceiling) · **G3 Indicated / consistent** (directional; a dominant
> systematic or confound is unseparated) · **G4 Under review / bound** (provisional, or a one-sided
> bound) · **G5 Retracted / corrected**. A consolidated per-headline grade table is in
> [`PROJECT_REPORT.md` §5.1](PROJECT_REPORT.md); there is **no single fully-validated primary
> physics result yet** — the cleanest results are the negative/confirmatory ones (C12 exclusion, PID
> truth ceiling).

### Executive Verdict

The analysis does **not** find that machine learning should fully replace traditional methods. ML excels where **the missing information is genuinely in waveform shape** (saturation recovery, duplicate-readout closure). Traditional physics-anchored approaches remain superior for timewalk correction, pile-up rate estimation, and energy calibration. The most important finding is methodological: **most apparent ML "wins" fail leakage controls** — a lesson in rigorous ML evaluation.

---

## 2. Experimental Setup

### The Beamline

```
                         ┌──────────────┐
  190 MeV protons ──────▶│  CD₂ Target  │──────▶ scattered charged particles
                         └──────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼                       ▼
             ┌────────────┐          ┌────────────┐
             │  Trigger   │          │    TPC     │
             │ Scintillators│         │ (tracking) │
             └────────────┘          └────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  ┌───────────┐          ┌───────────┐
  │  A-Stack  │          │  B-Stack  │  ★ Primary analysis
  │  A1 A3... │          │ B2 B4 B6 B8│
  │  ~100 cm  │          │  ~100 cm  │
  └───────────┘          └───────────┘
```

> **Authoritative setup (experiment-owner setup facts, 2026-07-03; diagram source: `drawing_ccb_setup`):**
> Stack A and Stack B are **two independent detector arms at conjugate angles**, each ~100 cm from
> the CD₂ target and each behind its **own trigger scintillators**, with the **TPC in front of
> Stack A only**. The arms measure **different particles** — pd-elastic scattering sends the proton
> into one arm and the kinematically-correlated deuteron into the other. An A·B coincidence
> therefore tags a correlated **pair** sharing the event T0, never the same particle twice.
> The triggers define the samples: **Sample I = A AND B trigger coincidence** (MC mimic: a charged
> particle entering the first A layer and the first B layer within 15 ns); **Sample II = B trigger
> only** (A ignored). In MC, Sample I is a **subset** of Sample II (inclusive); in data, Samples I
> and II are **disjoint run sets** taken with different trigger configurations. The ASCII sketch
> above is schematic only.

### Detector Details

| Component | Specification |
|---|---|
| **Beam** | Proton, kinetic energy T_p = 190 MeV |
| **Target** | Deuterated polyethylene (CD₂) |
| **HRD Stacks** | Two scintillator range telescopes (A and B) |
| **Distance from target** | ~100 cm |
| **Primary staves** | B2, B4, B6, B8 (even channels only) |
| **Independent-arm staves** | A1, A3 (Stack A — independent arm at the conjugate angle, measures different particles) |
| **Waveform** | 18 samples × 10 ns spacing = 180 ns window |
| **Readout** | One-ended wavelength-shifting (WLS) fibre → SiPM |
| **WLS propagation** | ~17 cm/ns |

### How the Detector Works

The HRD stacks function as a **ΔE–E / range telescope**:

1. A charged particle enters B2 (the most upstream stave), depositing energy
2. It continues through B4 → B6 → B8, slowing down at each layer
3. **Heavier particles** (deuterons) stop earlier (B2/B4); **lighter particles** (protons) penetrate deeper (B6/B8)
4. Each stave records an **18-sample waveform** capturing the scintillation light pulse
5. From each waveform we extract: **amplitude** (ADC), **arrival time** (ns), and **pulse shape** features

This is **not** an imaging detector — we get time and amplitude, not spatial position within a stave.

### Data Samples

| Sample | Stack | Description | Enrichment |
|---|---|---|---|
| **Sample I** | B | A·B trigger-coincidence runs; topology-heavy | D-enriched in upstream B staves: **confirmed at truth level** (S21: B2 ratio 1.519 [1.510, 1.528]; [§8.4](#84-trigger-truth-deuteron-enrichment-s21--confirmed)) and **consistent in data** (S23: B2 f(A>5000) ratio 3.45 [3.41, 3.50]; run-set differences not yet separated; [§8.5](#85-data-side-sample-iii-closure-s23--consistent-in-data)) |
| **Sample II** | B | B-trigger-only runs; penetrating | p-enriched relative to Sample I (S21 truth: f_p rises from 0.40 in B2 to 0.87 in B8) |
| **Sample III** | A | A-arm data from the Sample I runs | Independent arm — different particles |
| **Sample IV** | A | A-arm data from the Sample II runs | Low statistics (A not in the trigger) |

> **Key insight (corrected 2026-07-03, experiment-owner setup facts):** The "Sample I vs II" split reflects trigger configuration, not a beam change: **Sample I = A AND B trigger coincidence** (MC mimic: charged particle entering the first A and first B layer within 15 ns); **Sample II = B trigger only** (A ignored). In MC, Sample I is a **subset** of Sample II (inclusive flags in `src/ccb_mc_validation/io/root_truth.py`; the legacy `sample_label` was exclusive). In data, Samples I and II are **disjoint run sets** with different trigger configurations — every MC-vs-data sample comparison must state this asymmetry. The deuteron enrichment of Sample I in the B stack — previously a hypothesis after the earlier GEANT4 "confirmation" ran on retracted machinery — is now **confirmed at truth level by S21** (trigger-mimicked truth study, 2026-07-03): B2 deuteron-fraction ratio I/II = 1.519 [1.510, 1.528], and 91.2% of Sample-I events are a deuteron-into-B, proton-into-A pair — the direct signature of the kinematically-correlated pd-elastic pair the coincidence tags. It is **consistent in data by S23** (Sample-I B2 high-amplitude fraction ratio 3.45 [3.41, 3.50]), though the data Samples I/II are disjoint run sets so run-set/beam differences are not yet separated from the trigger. See [§8.4](#84-trigger-truth-deuteron-enrichment-s21--confirmed) and [§8.5](#85-data-side-sample-iii-closure-s23--consistent-in-data).

---

## 3. Data Pipeline

### End-to-End Flow

```
┌──────────────┐     ┌────────────────┐     ┌──────────────────┐
│  Raw ROOT    │────▶│  Pulse Table   │────▶│  Analysis        │
│  Files (110) │     │  640,737 pulses│     │  Branches        │
│  ~810 MB     │     │  CSV format    │     │                  │
└──────────────┘     └────────────────┘     └──────────────────┘
                                                     │
              ┌──────────────────────────────────────┤
              ▼                     ▼                ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐
    │  Timing Branch  │  │  Pile-up Branch │  │  PID Branch  │
    │  CFD → Timewalk │  │  Live-time → R  │  │  ΔE-E → AUC  │
    │  → Residuals    │  │  → Two-pulse    │  │  → GEANT4    │
    └─────────────────┘  └─────────────────┘  └──────────────┘
```

### Step 1: Raw ROOT → Pulse Table

**Study:** [Data Integrity & Pipeline Reproduction (S00)](reports/1780997954.15097.28a25ecb__s00a_sorted_hrdmax_semantics/)

The script `scripts/01_build_pulse_table_from_root.py` reads 110 ROOT files and produces a selected-pulse table:

1. Read `HRDv` tree from each ROOT file
2. Use **even B-stack staves** only: B2, B4, B6, B8
3. Compute **baseline** = median of ADC samples 0–3
4. Select pulses with **amplitude A > 1000 ADC**

**Result:** Exactly **640,737 selected B-stave pulse records** — reproduced with zero delta from the original analysis note.

### Step 2: Pulse Table → Analysis Branches

The selected-pulse table contains per-pulse columns:
- `run`, `event`, `stave` — identifiers
- `amplitude`, `baseline`, `peak_sample` — basic quantities
- `cfd_time`, `template_phase`, `q_template` — reconstructed timing and shape quality

All downstream analysis scripts read from this table and produce results in `reports/<id>/REPORT.md`.

### Step 3: MC Validation Pipeline

**Study:** [Digitizer Calibration (MV0)](reports/mv0_digitizer/)

The GEANT4 Monte Carlo produces **truth-level** particle data (PDG code, energy, position, time) but no waveforms. The **MV0 digitizer** converts MC truth into synthetic 18-sample ADC waveforms by modeling:

- Scintillator rise/decay (BC-408)
- WLS/fibre transit smearing
- 10 ns sampling
- Electronics noise + baseline
- Saturation clipping

This lets the same analysis pipeline run on MC data **with truth labels attached**, enabling direct data-vs-MC comparisons with known answers.

> ⚠️ **Known defect (External Review 2026-07-02, C1) — fixed by the Phase 1 overhaul:** the old shared-library digitizer's hit time cancelled exactly in the sampling code (waveforms bit-identical for t0 = 0/50/55 ns) and it diffed a peak-normalized kernel instead of integrating it. MC-validation studies that used it inherit this defect. The Phase 1 replacement is the config-driven, per-stave **mc02** pipeline (data-tuned tail decays, unit-tested; [MC02](reports/mc02_pulse_table_1783107862/), Birks and A-arm variants in [Phase 4](reports/phase4_1783180742/)). The gain remains a placeholder (§9.2); truth-level studies such as S21 bypass the digitizer entirely.

---

## 4. Timing Analysis

> **Key Findings:**
> - Best single-stave timing: **B6 σ(core) ≈ 0.68–0.75 ns** (external-note Gaussian-core decomposition; not σ₆₈, not MC-validated — under review 2026-07-03)
> - Combined 3-stave (B4+B6+B8): **σ₆₈ ≈ 0.54–0.56 ns** (under review — covariance validation withdrawn 2026-07-03)
> - Analytic timewalk reaches **1.49–1.55 ns** — tied with ML at 1.39–1.47 ns under proper cross-validation
> - B2-containing pairs have **large covariance** — B2 is excluded from precision timing
> - A-stack reproduces: **A1–A3 width = 1.39 ns** (matches note's 1.43 ns) — independent-arm methodology check on different particles (2026-07-03)
> - MC timing (MV4 honest rerun 2026-07-03): MC pair-equivalent σ₆₈ = **2.087 ± 0.009 ns**, between the data raw (2.993 ns) and corrected (1.50 ns) anchors — **REVIEW**; matched per-stave comparison pending Phase 1 digitizer
> - Resolution vs amplitude (S22, 2026-07-03): raw curves follow **1/A** better than 1/√A; downstream per-stave σ ≈ **0.85–1.1 ns at high amplitude**; B2 saturation-excluded (§4.8)

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

> ⚠️ **Anchor caveat (External Review 2026-07-02, P3):** the 1.85 ns "CFD20" value above is the anchor the analysis note carried forward, but the S02 head-to-head benchmark's raw CFD20 pair-difference σ₆₈ is **2.993 ns** (`head_to_head_benchmark.csv`, row `cfd20_reference`) — the 1.85 ns figure includes ML-ridge correction. The MV4 rerun (§4.7) uses 2.993 ns as the raw anchor.

### 4.3 Amplitude Timewalk

**The dominant timing systematic: larger pulses appear to arrive earlier.**

This is a well-known effect in scintillator + SiPM readout: bigger pulses cross the constant-fraction threshold sooner. The correction is:

```
t_corrected = t_CFD − f(amplitude)
```

where the analytic form is **f(A) = A₀ + B/amplitude** (fitted per stave from calibration runs, B2-blind to avoid topology bias).

**Study:** [Analytic Timewalk Correction (S03)](reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction/)

### 4.4 Per-Stave Timing Resolution

![Per-stave timing resolution; hatched bars are under review](docs/figures/03_timing_resolution.png)

*Figure: per-stave timing resolution. Solid bars are quoted S03 ranges (error bars = half-width of the quoted range, not fitted CIs); hatched bars are under review since 2026-07-03 — B6 is the external note's Gaussian-core σ (not σ₆₈), and the B4+B6+B8 combination assumes independent stave errors after its covariance validation was withdrawn.*

| Stave | σ₆₈ (ns) | Notes |
|---|---|---|
| B2 | ~2.8 | Topology-dominated, large covariance — **excluded from precision** |
| B4 | ~1.45 | Good downstream reference |
| B6 | **~0.72** | Best single-stave — cleanest timing (Gaussian-core value, not σ₆₈; under review 2026-07-03) |
| B8 | ~0.93 | Good, some penetration dependence |
| **B4+B6+B8** | **~0.55** | Combined event time (under review — covariance validation withdrawn 2026-07-03) |

### 4.5 The B2 Covariance Problem

**Study:** [Hierarchical B-Stack Covariance (S05c)](reports/)

B2-containing timing pairs show dramatically larger covariance:
- **B2-X pairs:** covariance ≈ 1042 ns²
- **B4-B6, B4-B8, B6-B8 pairs:** covariance ≈ 16 ns²

> ⚠️ **Correction (2026-07-03):** the quantitative covariance values above come from a closure script that was numerically invalid (off-diagonals exceed the diagonals — an impossible covariance matrix); they are withdrawn as measurements. The residual inter-stave covariance is unmeasured. The qualitative finding (B2 pairs are far more correlated than downstream pairs) stands.

This means B2 timing fluctuations are **not independent** of other staves — there is a shared, topology-correlated component. **B2 must be excluded from precision event-time estimates.** This is a physics finding (terminal deuteron topology), not a detector malfunction.

### 4.6 A-Stack Independent-Arm Check

**Study:** [A-Stack Independent Reproduction (S18)](reports/1780997954.15397.168324f2__s18_astack_independent_reproduction/)

> **Interpretation corrected 2026-07-03 (experiment-owner setup facts):** the A-stack is an
> **independent detector arm at the conjugate angle** — it measures **different particles** than the
> B-stack (pd-elastic sends the proton into one arm, the correlated deuteron into the other). Its
> timing results therefore check the **methodology** (calibration chain, timewalk, width extraction)
> on an independent detector; they are *not* a cross-check of the same particles, and any A–B
> coincidence timing carries the pd-pair kinematic spread plus the shared event T0.

The A-stack (A1/A3) provides an analysis-decoupled timing measurement on the independent arm:
- **Sample III** (A-arm data, coincidence-trigger runs): robust width **1.39 ns** — reproduces the analysis note's 1.43 ns
- **Sample IV** (A-arm data, B-trigger-only runs): broadening to 1.79 ns is a **calibration-pool / low-statistics effect**, not a physics effect
- ML residual correction makes timing *worse* (1.94 ns) — **ML is not adopted** for A-stack

### 4.7 MC Validation of Timing (MV4 honest rerun)

**Study:** [Timing Resolution Validation, honest rerun (MV4)](reports/mv4_timing_1783077795/) — 2026-07-03

The rerun replaces the invalidated 2026-07-01 comparison. Two code fixes landed first, both confirming the external review's diagnoses:

1. **Rising-edge CFD.** The old CFD scanned forward from sample 0 and, at the 250-ADC selection, its 20% threshold sat at ~1σ of noise — roughly half of low-amplitude "crossings" were noise, not signal. The rerun constrains the CFD to the last below-to-above crossing before the peak, eliminating the noise-crossing pathology.
2. **Physical timewalk sign.** With the MV4b functional-form fix (B/amplitude instead of B/√amplitude) and the rising-edge CFD, the fitted timewalk coefficient is **B = +39.6 ns·ADC** — the physically expected positive leading-edge sign. The earlier "unphysical negative B" was an artifact of the noise crossings.

| Stage | MC single-trace σ₆₈ (ns) | MC pair-equivalent σ₆₈ (ns) | Data pair-difference σ₆₈ (ns) | MC/data ratio |
|---|---|---|---|---|
| raw CFD20 | 1.476 ± 0.007 | 2.087 ± 0.009 | 2.993 (S02) | 0.697 ± 0.003 |
| timewalk-corrected | 1.481 ± 0.009 | 2.094 ± 0.012 | 1.50 (S03) | 1.396 ± 0.008 |

![MV4 honest rerun: MC pair-equivalent timing vs the data raw and corrected anchors](docs/figures/04_mc_vs_data.png)

*Figure: MV4 honest rerun (2026-07-03). (a) MC pair-equivalent σ₆₈ (single-trace × √2, assuming independent stave errors) against the data pair-difference anchors; MC error bars are bootstrap. (b) MC/data ratio; the dashed line marks equality. The data σ₆₈ uncertainty is unmeasured, so **no pull is computed** — the ratio quantifies agreement scale only and is not a hypothesis test. Source: [`reports/mv4_timing_1783077795/mv4_summary.json`](reports/mv4_timing_1783077795/mv4_summary.json).*

**Verdict: REVIEW.** The MC pair-equivalent value (2.087 ns) falls between the data raw (2.993 ns) and corrected (1.50 ns) anchors, so the toy digitizer is in the right regime but the comparison is still not matched: merged-track MC waveforms vs per-stave data pulses, unmatched selection, and a retracted gain (the gain here only sets the toy's amplitude/noise scale — no ADC/MeV claim). The MC timewalk correction yields no improvement (1.00×) because the rising-edge CFD has already removed the amplitude-dependent noise bias that dominates the data correction. A matched per-stave rerun awaits the Phase 1 digitizer overhaul.

### 4.8 Timing Resolution vs Amplitude (S22)

**Study:** [Per-Stave Timing vs Amplitude (S22)](reports/s22_timing_vs_amplitude_1783108999/) — 2026-07-03

S22 measures σ₆₈ vs the min-pair amplitude for every downstream pair, per sample, with
per-(pair, run) centering (so cable-delay offsets are removed before pooling — the review's P9
fix) and event-level within-run bootstrap errors:

- **Scaling law:** the raw curves follow σ(A) = √(c² + k²(1000/A)²) — a **1/A** timewalk-style
  law — better than 1/√A in the high-lever pairs (B4–B6: χ²/ndf 0.32–0.87 vs 1.25–3.71), and tie
  where the constant floor dominates (B6–B8).
- **Per-stave resolution at high amplitude:** ≈ **0.85–1.1 ns** for the downstream staves
  (σ_pair/√2, cross-checked with a three-pair triangle decomposition).
- **B2 is saturation-excluded:** 30–40% of selected B2 pulses sit above ~7000 ADC where the
  amplitude (hence the CFD threshold and the timewalk feature) is compressed; B2 curves are
  flagged and excluded from headline per-stave claims.
- The amp-only timewalk correction is fitted two-stage (downstream betas first, B2 frozen out)
  and evaluated leave-one-run-out. Caveats: the √2 conversion assumes independent equal-variance
  stave errors; the runs are the same as earlier S02/S03 work (no fresh confirmation partition).

![S22 — pair-difference σ₆₈ vs amplitude with the 1/A fit overlay](docs/figures/31_s22_timing_vs_amplitude.png)

*Figure 31: per-bin pair-difference σ₆₈ vs min-pair amplitude for the downstream pairs (raw CFD20, per-run-centred), Sample I and II, with the fitted 1/A timewalk law **σ(A) = √(c² + k²(1000/A)²)** overlaid; error bars = 200-bootstrap 95% CI; each fit's χ²/ndf is annotated. Source: [`reports/s22_timing_vs_amplitude_1783108999/`](reports/s22_timing_vs_amplitude_1783108999/) (s22_curves.csv per-bin points, s22_summary.json fits). Regenerated by `scripts/generate_postreview_figures.py`.*

---

## 5. Pile-up Analysis

> **Key Findings:**
> - The note's R_max = 4.22 MHz used τ_eff = 90 ns — **WRONG**
> - Measured waveform live-time: **τ_eff = 124.8 ns** → **R_max ≤ 3.05 MHz** (one-sided upper bound; censoring-aware estimators — KM 151.6 ns, IPCW 179.1 ns — suggest ≈2.1 MHz or lower)
> - ⛔ The "MC confirms R_max" claim is retracted (2026-07-03): MV5's "MC τ_eff" was a hardcoded copy of the data value. **Update 2026-07-04:** the first independent MC live-time (MC03) gives **134.99 ns vs data 124.79 ns (+8%, B2-driven)** — an honest disagreement, not a confirmation
> - Two-pulse recovery, honest truth-labelled benchmark (MC03/S24, 2026-07-04, replaces the rigged S11a table): **traditional wins at matched 80% coverage; ML wins at full coverage** (failure 0.011 vs 0.048); common-subset dt σ68 trad 0.64 vs ML 0.89 ns (§5.3)
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
- **R_max ≤ 3.05 MHz** (one-sided upper bound; for |Δt| < 1 ns and area error < 20%, at ε > 90%)

**MC confirmation (MV5): ⛔ RETRACTED as validation (2026-07-03); slot refilled by MC03 (2026-07-04).** [Pile-up Rate Validation (MV5)](reports/mv5_pileup_study/) | [MC03 overlay + independent τ_eff](reports/mc03_overlay_1783180480/)
- MV5 used the data-measured τ_eff as an input (the "MC τ_eff = 124.8 ns" was a hardcoded copy); at the time no independent MC live-time measurement existed.
- **The first honest MC live-time now exists (MC03, 2026-07-04):** the S10b 10% tail-crossing estimator on digitized MC single pulses (per-stave data-tuned tail decays) gives **τ_eff = 134.99 ns [134.96, 135.01]** (statistics only; the +8% / +10.2 ns offset from data 124.79 ns is the dominant, systematic, difference) **vs data 124.79 ns (Δ = +10.2 ns, +8%, driven by B2: 141.35 ns)**. This is an honest disagreement — MC pulses are clean by construction while the data value includes real pathologies — and it fills the validation slot left by the retracted MV5.
- R_max = 0.380/τ_eff is quoted as **one bound plus an estimator band: R_max ≤ 3.05 MHz (censoring-aware estimators — KM 151.6 ns, IPCW 179.1 ns — suggest ≈2.1 MHz or lower)**. The +8% MC live-time excess, if real, would push τ_eff up and **tighten this bound rather than validate it**.

> ⚠️ **The analysis note's R_max ≈ 4.2 MHz is an error from an incorrect τ_eff assumption; that correction stands, but as an upper bound.** All references should use R_max ≤ 3.05 MHz.

![MC03 first independent MC live-time vs data — a +8% disagreement](docs/figures/27_mc_taueff_vs_data.png)

*Figure 27: per-stave MC τ_eff (points, error bars = bootstrap 95% CI, 300 resamples; n_aligned = 6,000 per stave) and the pooled MC value **134.99 ns [134.96, 135.01]** vs the data **124.79 ns** (band = the S10 waveform-bootstrap CI [123.3, 126.4]) — an honest **+8% (+10.2 ns)** disagreement, B2-driven, replacing the retracted MV5 "MC confirms R_max". Source: [`reports/mc03_overlay_1783180480/result.json`](reports/mc03_overlay_1783180480/result.json). Regenerated by `scripts/generate_postreview_figures.py`.*

![R_max is a one-sided upper bound, not 4.22 MHz](docs/figures/09_rmax_correction.png)

*Figure 09 (rebuilt): (a) τ_eff estimators — the note's assumed 90 ns is an error; the 10%-crossing data value is 124.8 ns, and censoring-aware Kaplan–Meier / IPCW give 151.6 / 179.1 ns. (b) the resulting R_max = μ_max/τ_eff: the note's **4.22 MHz is retracted as a value**; the data 10%-crossing gives the one-sided bound **R_max ≤ 3.05 MHz**, and the censoring-aware estimators imply **≈2.1 MHz or lower**. No error bars (derived point values). Sources: S10 τ estimators; MC τ_eff from [`reports/mc03_overlay_1783180480/`](reports/mc03_overlay_1783180480/). Regenerated by `scripts/generate_postreview_figures.py`.*

### 5.3 Two-Pulse Recovery — honest truth-labelled benchmark (MC03/S24)

**Study:** [Honest Two-Pulse Benchmark (MC03/S24)](reports/mc03_overlay_1783180480/) — 2026-07-04. It replaces the retracted S11a comparison (review P8: injection grid == fit hypothesis grid, injected waveforms from the fit's own templates, per-method failure definitions at unmatched coverage). **The S11a numbers — time RMS 10.67 vs 13.30 ns and failure rates 0.295 vs 0.168 — are retired and must not be cited.**

The honest benchmark uses 600,000 truth-labelled overlay records at 0.5/1.5/3 MHz (continuous injected dt, digitized pairs of real truth hit groups, one failure definition for both methods, detection thresholds set by the same 10%-FPR procedure):

| Comparison | Template fit | Compact ML |
|---|---|---|
| Failure at **matched 80% coverage** | **≤ 0.0001** (all rates) | 0.0001–0.0002 |
| Failure at **full coverage** | 0.047–0.049 | **0.011** |
| dt σ₆₈ on the common accepted subset | **0.64 ns** | 0.89 ns |
| Detection ROC AUC | 0.980 | **0.997** |

**Reading:** at a matched, abstaining operating point the **traditional fit wins**; if full coverage is required, **ML wins** (it fails 4× less often when forced to answer). Caveats: the fit template shares the kernel *family* with the generator (not the injection sample); trigger phase is fixed at 50 ns; single-stave overlays only; amplitudes on the placeholder gain scale.

![Honest two-pulse risk-coverage — split verdict](docs/figures/30_twopulse_riskcoverage.png)

*Figure 30: (a) risk (failure rate on the answered subset) vs coverage for the template fit and compact ML (bold = 0.5 MHz; faint = 1.5 / 3.0 MHz), with the matched 80%-coverage line; (b) at 0.5 MHz — failure @ full coverage (trad 0.047 vs ML 0.011), failure @ 80% coverage (trad 0.000 vs ML 1.1×10⁻⁴), and common-subset Δt σ₆₈ (trad 0.646 vs ML 0.893 ns); bars scaled per metric with true values annotated. 600,000 truth-labelled overlays; the retired S11a 0.295/0.168 table is not shown. Source: [`reports/mc03_overlay_1783180480/`](reports/mc03_overlay_1783180480/) (risk_coverage_curves.csv, result.json). Regenerated by `scripts/generate_postreview_figures.py`.*

### 5.4 Current-Dependent Excess

The ML pile-up classifier score ratio between high and low current is ~1.29× (not the ~10× expected from the 10× current ratio under pure Poisson scaling), indicating a large current-independent contribution (scintillator tails, waveform pathologies). Separately, the measured downstream per-event excess at 20 nA is 0.0103 per selected event [CI 0.0064-0.0142, S10 current_excess_table.csv], representing 30.8% of the high-current downstream rate. The ML pile-up score shows 22.9% excess at high current (ratio 1.30). These are two independent measurements of different quantities. These are two independent measurements: the ML score ratio measures classifier behavior; the downstream excess measures physical pile-up rate. They should not be chained causally.

---

## 6. Pulse Shape & Machine Learning

> **Key Findings:**
> - Pulse shapes are **low-dimensional**: 3 PCA components capture 89% of variance, 8 capture 99.7%
> - **Autoencoder beats PCA** at very low latent dim (2–4); PCA catches up at dim ≥ 8
> - ML genuinely wins where truth is independent and information is in waveform shape
> - **All representation-superiority claims for downstream tasks: ❌ CORRECTED** (leakage artifact)
> - ✅ The C12-recoil hypothesis for the anomaly class is **ruled out** (MV6b, 2026-07-04): with physical Birks quenching, 0 of 1,656 C12 records pass A>1000 at any gain — the 4.4% early-peak class must be **instrumental or trigger-phase-related** (data-side question, P02/P09 leads)
> - **The project's most important finding: most ML "wins" fail leakage controls**

### 6.1 Where ML Helps vs. Where It Doesn't

![ML performance landscape: verdicts per domain after leakage controls](docs/figures/10_ml_landscape.png)

*Figure: ML verdicts per domain after leakage controls. Two-pulse recovery is a split verdict per the honest truth-labelled benchmark (MC03/S24, 2026-07-04): traditional at matched coverage, ML at full coverage — superseding the S11 headline table (§5.3).*

| Domain | ML Verdict | Why |
|---|---|---|
| **Saturation recovery** | ✅ **ML Wins** (3–7× better) | Truth (true amplitude) independent of input; signal is in waveform rising edge |
| **Duplicate-readout amplitude** | ✅ **ML Wins** (res68 0.003 vs 0.12) | Truth from duplicate readout; independent of primary channel |
| **Two-pulse recovery** | ⚠️ Split verdict (truth-labelled, MC03/S24) | Traditional wins at matched 80% coverage; ML wins at full coverage (0.011 vs 0.048) and on detection AUC; σ68 trad 0.64 vs ML 0.89 ns (§5.3; the S11a 0.295/0.168 table is retired) |
| **Timewalk correction** | ❌ Tie/Loss | Analytic B/amplitude model already near-optimal |
| **Pile-up Poisson rate** | ❌ Tie | Analytic Poisson model already optimal |
| **Deep net timing** | ❌ ML Loses | CNN/MLP on raw waveform loses to analytic timewalk |
| **PID (data-only)** | ❌ Leakage | D_t/curvature classifiers hit AUC ~1.0 because label = f(input) |
| **Representation superiority** | ❌ CORRECTED | Apparent AE→P03 win was leakage; failed run-family and event-block shuffle |

### 6.2 Pulse Shape Compression

![Reconstruction MSE vs latent dimension for PCA and autoencoder](docs/figures/05_pca_vs_ae.png)

*Figure: waveform reconstruction MSE (normalized ADC², log scale) vs latent dimension. The autoencoder wins at d ≤ 4; PCA overtakes at d = 8. Values from the P01 report table below (no per-point uncertainties were published).*

**Study:** [Self-Supervised Waveform Representation (P01)](reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation/)

| Latent Dim | PCA MSE | AE MSE | Winner |
|---|---|---|---|
| 2 | 0.02622 | 0.01294 | AE +50.6% |
| 3 | 0.01416 | 0.00841 | AE +40.6% |
| 4 | 0.00880 | 0.00527 | AE +40.1% |
| 8 | 0.00166 | 0.00292 | PCA +75.9% |

**Conclusion:** Pulses are simple shapes. The AE helps at very low dimensions (capturing nonlinear manifold), but PCA catches up once sufficient linear components are retained. The representation is compact — there's no deep hidden structure in pulse shape.

### 6.3 The Early-Peak Anomaly: C12 Ruled Out

**Studies:** [MV6b honest redo with Birks quenching](reports/mv6b_anomaly_quenching_1783180742/) — 2026-07-04 | retracted original: [Representation & Anomaly ID (MV6)](reports/mv6_representation_study/)

![MV6b: C12 recoils cannot be the data's 4.4% early-peak class](docs/figures/26_mv6b_c12_ruled_out.png)

*Figure 26: (a) early-peak (peak_sample ≤ 3) fraction of A>1000 pulses — **0.000%** in both the quenched (Birks ON) and unquenched MC tables, against the data's **4.4%**; (b) C12-dominant records passing A>1000 at gain 297: **0/1,656** quenched vs 3/1,656 unquenched (0/1,656 at every gain 60–297). Bars are exact counts/fractions (no error bars). Source: [`reports/phase4_1783180742/REPORT.md`](reports/phase4_1783180742/REPORT.md) (quenched twin `reports/mv6b_anomaly_quenching_1783180742/`). PNG/SVG/PDF regenerated by `scripts/generate_postreview_figures.py`.*

Unsupervised discovery (P09a) found an anomalous class with **early peaking and near-zero area** (~4.4% of selected data pulses, peak at sample ≤3). MV6 attributed it to C12 nuclear recoils; that run was retracted 2026-07-03 (invalidated gain 246, no Birks quenching, no amplitude threshold, per-track whole-arm waveforms, mismatched denominators — External Review 2026-07-02).

**MV6b (2026-07-04) settles the question with physical Birks quenching.** Comparing a quenched digitized MC pulse table against its unquenched twin (identical card/seeds/noise) under the data taxonomy (A > 1000 net ADC, early-peak = `peak_sample ≤ 3`):

| Quantity | Quenched (Birks ON) | Unquenched twin | Data |
|---|---|---|---|
| C12 records passing A>1000 (any gain, 60–297) | **0 / 1,656** | 0–3 / 1,656 | — |
| MC early-peak fraction (every configuration) | 0.000% | 0.000% | **4.4%** |
| Heavy-ion share of the gain-60 selection | 0% | 13.8% | — |

**Verdict: C12 recoils are ruled out as the data's 4.4% early-peak class** — their light (few-MeV recoil, quench factor ~60–100) sits at the noise floor, at every gain hypothesis. Since the MC's species content cannot reach A>1000 with early peaks at all, the class **cannot be a species/scintillation effect**: it must be **instrumental** (baseline/noise/bipolar artifacts, per the P02/P09 leads) **or trigger-phase-related**, neither of which the MC models. The question is reopened as a **data-side** investigation.

**Legacy corrections that still stand:** in-situ p+C recoils in the scintillator are the only kinematically possible C12 source (target recoils cannot cross ~1 m of air); the GMM Cluster-2 veto (discarding 16.7% of tracks to remove a 0.32% class) remains not recommended.

---

## 7. Amplitude, Charge & Energy

> **Key Findings:**
> - ML **decisively wins** duplicate-readout amplitude/charge closure (res68 0.003–0.009 vs 0.12–0.20)
> - ML recovers saturated B2 pulses to **3–7× better precision** than templates
> - **Absolute per-event energy is structurally unreachable** from waveform data — GEANT4 Birks lookup remains the best method
> - Digitizer gain: **≈ 60–80 ADC/MeV, dominated by trigger/quenching modelling — no precision value yet** (v1 ~246 and v2 92 ± 28 both retracted 2026-07-03; Phase-2 trigger-consistent scan prefers ~60 unquenched, quenched re-scan pending)

### 7.1 Duplicate-Readout Closure

**Study:** [Amplitude & Charge Regression (P04)](reports/)

When the same pulse is read out through two independent paths, the "duplicate" measurement provides **independent truth**. ML (HistGradientBoosting/ExtraTrees) achieves:
- **res68 = 0.003–0.009** (ML)
- **res68 = 0.12–0.20** (traditional peak/integral)

This is the cleanest demonstration that **waveform shape carries recoverable calibration information** beyond scalar summaries.

> **FDR status (P04):** the P04/P04c–e duplicate-readout wins have **no machine-readable delta-CI in the STATS01 FDR census** — they are among the 6 prose-only bold wins outside the BH census ([§12.5](#125-uncertainty-conventions)). They are **reported, not yet FDR-certified**; treat the res68 gap as indicative until a machine-readable delta-CI is run through the census.

### 7.2 Saturation Recovery

**Study:** [Saturation Recovery (P07)](reports/P07_saturation_recovery/)

B2 staves in Sample I saturate — ~30–40% of B2 pulses exceed the 7000 ADC ceiling. ML recovers the true amplitude from the **unsaturated rising edge**:

| Method | res68 | Degradation at High Saturation |
|---|---|---|
| ML (ExtraTrees/HGB) | **0.032–0.046** | Graceful |
| Template (shape fit) | 0.104–0.286 | Severe |

On **artificial constant-ceiling clips**, ML is 3–7× better. However, natural-saturation recovery carries a **run-dependent timing-tail envelope** that is treated as a systematic.

> **FDR status (P07):** like P04, the P07 saturation-recovery win has **no machine-readable delta-CI in the STATS01 FDR census** (a prose-only bold win, [§12.5](#125-uncertainty-conventions)). It is **reported, not yet FDR-certified**.

### 7.3 Absolute Energy Limitation

**Study:** [Truth Energy Validation, rerun (MV2)](reports/mv1_mv2_truth_pid_energy_1783077795/) — 2026-07-03

**There is no per-event energy truth in the data.** Propagated per-event energy reaches res68 ~ 0.19–0.25, failing the 10% threshold.

MC truth (MV2 rerun after the momentum-unit fix, 400,369 tracks):
- The eV-scale ekin corruption (GeV/MeV momentum-unit error, review item C3) is fixed: entry kinetic energies are now MeV-scale (mean proton ekin 99.4 MeV, deuteron 79.7 MeV).
- Proton edep_tot median: **101.1 MeV**; deuteron: **73.4 MeV** — the same artifact values as before the rerun (the previously quoted 23/89 MeV were untraceable). Deuterons stop early because pd-elastic kinematics gives them ~105 MeV with roughly half a proton's range; forward protons (~150 MeV) penetrate deep or punch through.
- New containment flag (edep_tot ≥ 0.8·ekin): **proton 0.70, deuteron 0.84** — a large proton punch-through fraction, consistent with the range picture above. Stop-layer vs ekin tables are now physically ordered for contained tracks.
- The **GEANT4 Birks lookup** remains the best held-out energy method — neural and tree models do not supersede the physics prior.
- Caveat: MV2 runs on the untriggered MC population (Phase 2: the MV3 discrepancy is the unsimulated trigger, not geometry); absolute penetration-depth quantities inherit that selection bias.

---

## 8. Particle Identification

> **Key Findings:**
> - Proton/deuteron separation: **AUC = 0.986** (MC truth ceiling, HGB; rerun 2026-07-03)
> - Data methods using weak-label proxies reach within 0.5% of MC ceiling — leakage-safe stress test, not species-truth PID — information is in the data
> - **Sample-I deuteron enrichment: ✅ CONFIRMED at truth level (S21, 2026-07-03)** — B2 ratio 1.519 [1.510, 1.528]; enrichment fades with depth (B4 1.40, B6 ~1.0, B8 inverted at 0.43)
> - **…and CONSISTENT in data (S23, 2026-07-03; run-set differences not yet separated)** — Sample-I B2 high-amplitude fraction ratio 3.45 [3.41, 3.50]; trigger mimicking moves MC toward the data (KS 0.192 → 0.131; occupancy χ² 624k → 20k)
> - **Stopping-depth profile: 🔶 re-graded FAIL → TENSION (Phase 2, 2026-07-03)** — the χ²/ndf = 68,269 is **strongly indicated (pending `Trig_bar` simulation)** to be the **unsimulated two-arm coincidence trigger**, not geometry; trigger proxy + event basis + species-inclusive + gain 60 → **625 (109×)**; missing-material narrative falsified (~0.13 g/cm² air missing vs ≥10.5 needed)
> - Depth ordering (B2 > B4 > B6 > B8) is qualitatively correct in both data and MC

### 8.1 How PID Works (Without Truth)

With no per-event truth labels in data, we use **physics-driven proxies**:
- **ΔE–E method:** heavier particles (deuterons) deposit more energy per unit length and stop earlier
- **Range separation:** deuterons stop in B2/B4; protons reach B6/B8
- **Sample enrichment (confirmed at truth level 2026-07-03):** Sample I (A·B trigger coincidence) is deuteron-enriched in the upstream B staves — S21 measures a B2 deuteron-fraction ratio of 1.519 [1.510, 1.528] over Sample II, driven by the coincidence tagging kinematically-correlated pd-elastic pairs (91.2% of Sample-I events are d-into-B, p-into-A). See §8.4.

### 8.2 MC Truth Validation

![PID classifier performance on GEANT4 truth](docs/figures/07_pid_auc.png)

*Figure: AUC and purity at 90% efficiency per method on GEANT4 truth (MV1 rerun 2026-07-03). The single hard cut has no AUC (it is one operating point). Source: [`reports/mv1_mv2_truth_pid_energy_1783077795/mv1_mv2_truth_summary.json`](reports/mv1_mv2_truth_pid_energy_1783077795/mv1_mv2_truth_summary.json).*

**Study:** [Proton/Deuteron PID, rerun (MV1)](reports/mv1_mv2_truth_pid_energy_1783077795/) — 2026-07-03

On 400,369 GEANT4 truth tracks (150,130 protons, 146,842 deuterons); the rerun after the unit fix reproduces the original PID numbers:

| Method | AUC | Purity @ 90% Efficiency |
|---|---|---|
| Hist Gradient Boosting (HGB) | **0.9860** | **0.9644** |
| Logistic Regression | 0.9629 | 0.9489 |
| Single-cut ΔE | — | 0.8910 |

Data methods reach within 0.5% of the MC ceiling — but **only via weak-label proxies, not species truth**: AUC = 0.986 is an MC truth ceiling, and the data side is a leakage-safe stress test showing the separating information is present, not a species-truth PID validation.

### 8.3 Stopping-Depth Profile — FAIL Re-graded TENSION (root cause: the trigger)

![Hero: the trigger, not missing material, is the MV3 root cause — χ²/ndf ladder and stave-fraction profiles](docs/figures/25_mv3_trigger_rootcause.png)

*Figure 25 (program hero): (a) MV3 stopping-depth agreement **χ²/ndf** (log scale) across hypotheses — the published untriggered reference (**68,269**) collapses **×22 to 3,047** once the truth-level A·B coincidence trigger is required, then to **555** at the best grid point (gain 60, event basis, species-inclusive); the odd/even LayerID mappings score worse and are disfavoured. (b) Per-stave selected-pulse fractions (log scale): untriggered MC over-predicts deep-stave **B8 penetration ×10**, while the trigger-proxy MC tracks the data. No error bars — these are exact χ²/ndf and population fractions over the full grid (n = 306,745 data pulses; 1,000,000 MC events). Source: [`reports/phase2_geometry_1783108797/mv3v4_grid.json`](reports/phase2_geometry_1783108797/mv3v4_grid.json) (untriggered reference χ²/ndf = 68,269 from the MV3 report). Regenerated by `scripts/generate_postreview_figures.py`.*

![Stopping-depth profile: MC vs data and their ratio](docs/figures/06_stopping_depth.png)

*Figure: (a) fraction of selected pulses per stave, untriggered MC vs data; (b) data/MC ratio (log scale, dashed line = agreement). The untriggered MC overpredicts B8 penetration by ×10; the Phase-2 trigger proxy removes almost all of the discrepancy (table below).*

**Studies:** [Phase 2 geometry audit + MV3 v4 diagnostics](reports/phase2_geometry_1783108797/) — 2026-07-03 | original: [Stopping-Depth Profile (MV3)](reports/mv3_stopping_depth/)

The published comparison (untriggered MC, species-filtered, gain 92) gave χ²/ndf = 68,269:

| Stave | MC Fraction (untriggered) | MC Fraction (trigger proxy, gain 60) | Data Fraction |
|---|---|---|---|
| B2 | 47.0% | **87.1%** | 87.6% |
| B4 | 18.2% | 5.5% | 6.3% |
| B6 | 12.5% | 3.8% | 3.9% |
| B8 | 22.3% | 3.6% | 2.3% |

**Root cause strongly indicated (Phase 2, 2026-07-03), pending `Trig_bar` simulation: the
unsimulated two-arm coincidence trigger.** (The truth-level A-arm coincidence is a *proxy*, not a
simulated trigger; the residual is still large, so the cause is directionally compelling but not yet
established — see the `Trig_bar` scoring work item below.)
The geometry audit (direct volume dump of the production file) **falsified** the missing-material
narrative: every named upstream component (vacuum window, trigger scintillators, TPC hull) is
already in the production geometry; only **~0.13 g/cm² of air** is genuinely missing, while the
B2 deficit would require **≥10.5 g/cm²** of upstream material — a factor ≥13 more than physically
exists (air 0.13 + wrapping ≲0.5 + ESR ≲0.1 ≈ ≲0.8 g/cm²). Instead, requiring a truth-level
A-arm coincidence — the Sample-I trigger the data was actually recorded with — collapses χ²/ndf
from 68,269 to 3,141, and with event basis + species-inclusive counting + gain 60 to **625
(a 109× reduction; best grid point 555; vs the C2-corrected data profile 88,542 → 1,061)**.

**The physics:** the coincidence keeps deuteron-into-B events (the conjugate ~85 MeV proton
reaches Stack A) and vetoes deep-proton events (the conjugate ~37 MeV deuteron dies in the TPC
hull). Untriggered MC contains both populations; the data does not. The odd-layer mapping
hypothesis (review P4) is disfavored — both unread-bar variants score worse — so the `paired`
LayerID→stave mapping stands.

**Impact:** MV3 is re-graded **FAIL → TENSION**; **no new GEANT4 production is needed**, and
geobuilder PR #8 (inter-stave Al proxy, ~10× the realistic wrapping budget) should be closed or
reworked, not merged. The residual χ²/ndf ~600–1,100 (≲1% absolute per-stave deviations) is
attributed to the crude A-HRD proxy, no Birks quenching in the threshold model, data-B2 pile-up,
and the phase-locked peak_frac. **Next MC-side work item: score the `Trig_bar` volumes as
sensitive detectors and emit a real per-event Sample-I/Sample-II trigger flag.**

### 8.4 Trigger-Truth Deuteron Enrichment (S21) — CONFIRMED

**Study:** [Sample I vs II Trigger-Truth Comparison (S21)](reports/s21_sample12_trigger_truth_1783077969/) — 2026-07-03

**Sample I is deuteron-enriched in the upstream B staves — confirmed at truth level.** On 1,000,000 GEANT4 events with the trigger mimic (Sample I = charged particle entering the first A layer and first B layer within 15 ns, n = 64,762 events; Sample II = entering B, inclusive, n = 237,098), the B2 deuteron fraction is 0.675 [0.672, 0.678] in Sample I vs 0.444 [0.443, 0.446] in Sample II:

| Stave | f_d Sample I | f_d Sample II | Ratio I/II (95% CI) | Ratio I/(II\I) (95% CI) |
|---|---|---|---|---|
| B2 | 0.675 | 0.444 | **1.519 [1.510, 1.528]** | **1.912 [1.898, 1.925]** |
| B4 | 0.304 | 0.216 | 1.404 [1.365, 1.444] | 1.450 [1.409, 1.492] |
| B6 | 0.011 | 0.011 | 1.003 [0.795, 1.264] | 1.003 [0.795, 1.265] |
| B8 | 0.002 | 0.005 | 0.427 [0.228, 0.799] | 0.411 [0.219, 0.770] |

![S21 deuteron enrichment: fractions, ratios, and energy deposits per stave](docs/figures/24_s21_denrichment.png)

*Figure: S21 trigger-truth result. (a) Truth deuteron fraction of charged B-arm tracks per stave with 95% binomial CIs; (b) Sample I/II enrichment ratio (log scale) for the inclusive (I ⊂ II) and exclusive (I vs II\I) definitions, with 95% CIs — enrichment fades with depth and inverts at B8; (c) median per-stave energy deposit in Sample I, whiskers = 16–84% quantile span. Source: [`reports/s21_sample12_trigger_truth_1783077969/s21_summary.json`](reports/s21_sample12_trigger_truth_1783077969/s21_summary.json); full multi-panel overview in [`docs/figures/s21_overview.png`](docs/figures/s21_overview.png) (copy of the report artifact).*

**Mechanism.** The enrichment is exactly the pd-elastic pair-tagging predicted by the setup facts (§2): in Sample I, 91.2% of events have a deuteron entering B and a proton entering A (the conjugate 8.0% are p-into-B, d-into-A). The enrichment fades with depth — strong in B2/B4, absent in B6 (ratio 1.00 [0.80, 1.26]), inverted in B8 (0.43 [0.23, 0.80]) — because the tagged ~105 MeV deuterons stop in the first two staves, leaving deep staves proton-dominated in both samples.

**Energy separation.** In Sample-I B2, the deuteron energy-deposit median is **70.5 MeV (σ₆₈ 16.4)** vs **24.6 MeV (σ₆₈ 11.9)** for protons — the ΔE separation that drives the PID of §8.1–8.2.

**Caveats (from the S21 report):**
- Truth level only: EDep proxies the pulse amplitude — no digitizer, threshold, saturation, or Birks quenching. Data-facing amplitudes will differ.
- The LayerID→stave mapping ({0,1}→B2 … {6,7}→B8) is a repo convention under review; per-LayerID tables in the report allow re-derivation under alternative mappings, and the enrichment holds per-LayerID (f_d = 0.735/0.752 in layers 0/1 of Sample I vs 0.484/0.447 in Sample II).
- S21's absolute per-stave fractions come from the untriggered-MC population and inherit the MV3 comparison bias (Phase 2 root cause: the unsimulated trigger, not missing material — §8.3); the I/II enrichment **ratios** (same geometry, same bias) are more robust than any absolute fraction.
- Inclusive definitions make Sample I a subset of Sample II, so the inclusive ratio's binomial errors are positively correlated; the exclusive I vs II\I comparison (disjoint events) is reported alongside and is stronger (1.912 at B2).
- In data, Samples I and II are disjoint run sets with different trigger configurations — this MC comparison mimics the trigger logic, not the run-set split.

### 8.5 Data-Side Sample I/II Closure (S23) — Consistent in Data

**Study:** [Sample I vs II Data-Side Closure and Data–MC Comparison (S23)](reports/s23_sample12_data_mc_1783108675/) — 2026-07-03

S23 closes the loop the S21 caveats left open: does the enrichment survive in the *data* (with
digitization, thresholds and saturation), and does trigger-mimicked MC move toward the data?

1. **The signature is in the data:** the Sample-I B2 spectrum is markedly harder —
   f(A>5000) = 0.710 [0.708, 0.711] (Sample I) vs 0.206 [0.203, 0.208] (Sample II), **ratio
   3.45 [3.41, 3.50]**; B2 medians 6542 vs 3350 ADC; B2 occupancy share 0.957 vs 0.705.
2. **Trigger mimicking moves MC toward the data:** for data Sample I, the B2 shape distance
   falls KS 0.192 (untriggered) → 0.131 (Sample-I mimic) and the occupancy χ² falls
   623,875 → 20,421; the matched mimic is the closest MC variant. The claim is the *direction*
   of improvement, not agreement — absolute χ² stays far from statistical
   (trigger-unselected occupancy weights + unmodelled beam conditions).
3. **Double ratios (gain- and geometry-robust):** B2 occupancy DR = **0.738 [0.733, 0.742]
   (z vs 1: −99)** — MC under-predicts the between-sample contrast, exactly what a missing
   trigger simulation produces (Phase 2, §8.3). The z = −99 is **statistics-only significance;
   systematics from the disjoint run-sets and beam conditions are not included**, so it measures
   internal precision, not the physical MC–data disagreement. MC high-amplitude thresholds are
   quantile-matched and shape metrics median-scaled so the placeholder gain cancels to first
   order.

**Caveats:** disjoint data run sets vs inclusive MC mimics (the exclusive II\I MC variant is
reported alongside); beam/rate differences between run sets are not modelled; B2 saturation
leaves a tail-shape systematic in the KS distance.

![S23 — the Sample-I enrichment is confirmed in the data](docs/figures/32_s23_data_enrichment.png)

*Figure 32: (a) data fraction of pulses with A > 5000 ADC, Sample I vs II per stave — the B2 Sample-I/II high-amplitude ratio is **3.45 [3.41, 3.50]**; (b) data/MC double ratios (data I/II)/(MC I/II): the occupancy DR per stave is everywhere < 1 (MC under-predicts the between-sample contrast — the missing trigger simulation) and the B2 high-amplitude DR is **1.67 [1.64, 1.70]**. Error bars = 95% bootstrap CI; n = 640,737 data / 458,712 MC rows. Source: [`reports/s23_sample12_data_mc_1783108675/s23_summary.json`](reports/s23_sample12_data_mc_1783108675/s23_summary.json). Regenerated by `scripts/generate_postreview_figures.py`.*

---

## 9. Pedestal & Baseline

> **Key Findings:**
> - Adaptive pedestal is biased (341 ADC (MAE) vs pretrigger-median reference)
> - Learned pedestal (HGBR) cuts MAE from 341 to 49 ADC
> - But: **no true forced/random pedestal sample exists** in current data — all validation is proxy-based
> - **MV7 (2026-07-03): zero-signal MC closure** — adaptive MAE 3.48 ADC, learned 1.50 ADC (MC-level lower bounds; the data side stays proxy-only)
> - Digitizer gain: **≈ 60–80 ADC/MeV, no precision value yet** (v1/v2 retracted 2026-07-03; trigger-consistent scan ~60, quenched re-scan pending)

### 9.1 The Pedestal Problem

**Study:** [Pedestal/Baseline Validation (S16)](reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/)

The **adaptive pedestal** (positivity-constrained baseline, tolerance scales with amplitude) is the legacy estimator. But against a pretrigger-median reference:
- **MAE = 341 ADC** (adaptive)
- **MAE = 48.9 ADC** (learned, HGBR)

**Caveat:** There is no true forced/random pedestal sample in the data — 0 forced/random-tagged entries across exhaustive scans. All validation uses proxy references (pretrigger-median, quiet-proxy). This is a structural data limitation.

**MV7 — zero-signal MC validation (2026-07-03).** [MC02 pulse table + MV7](reports/mc02_pulse_table_1783107862/): on 100,000 zero-signal MC records (white-Gaussian noise + uniform pedestal jitter [6737, 7029] ADC), the adaptive estimator (median of samples 0–3) reaches **MAE 3.48 ADC** and the learned ridge estimator **MAE 1.50 ADC** against absolute truth. This closes the MC side of the forced-pedestal question; the MAEs are lower bounds (correlated noise, drift and signal contamination are not modelled), and the data side remains proxy-only until a forced-trigger sample exists.

### 9.2 Digitizer Gain Calibration

| Version | Gain | Status |
|---|---|---|
| MV0 v1 | ~246 ADC/MeV | ❌ **RETRACTED** — compared raw amplitude vs MC+digitizer pedestal |
| MV0 v2 | 92 ± 28 ADC/MeV | ⛔ **RETRACTED (2026-07-03)** — its anchor was \|net − pedestal\| of an already baseline-subtracted amplitude (a folded garbage variable); true B2 net median = 5752 ADC, not 1781; unreproducible from any committed script; MC anchor circular with the MV3-failed geometry |

![Digitizer gain: an honest 60–80 band, not a number](docs/figures/28_gain_honest_band.png)

*Figure 28: (a) gain number-line — both published values (v1 ~246, v2 92 ± 28) are **retracted** (red ×); the trigger-consistent band **≈ 60–80 ADC/MeV** (green) is the current best statement, with 297 carried only as a placeholder. (b) the trigger-consistent MV3 stopping-depth χ²/ndf scan (track/inclusive/paired) is monotonic with a minimum at **gain 60 (χ²/ndf 555)**. No error bars (χ²/ndf point values). Source: [`reports/phase2_geometry_1783108797/mv3v4_grid.json`](reports/phase2_geometry_1783108797/mv3v4_grid.json); retractions per External Review 2026-07-02. Regenerated by `scripts/generate_postreview_figures.py`.*

**Neither retracted value is valid. The current best statement (2026-07-04): gain ≈ 60–80 ADC/MeV, dominated by trigger/quenching modelling — no precision value yet.** The Phase-2 trigger-consistent scan prefers **~60** (unquenched threshold model; the scan is monotonic: 60 → χ²/ndf 625, 92 → 3,613, 300 → 7,017, and without the trigger the gain scan is flat — gain cannot rescue an untriggered comparison). With Birks quenching on, the preferred gain is expected to rise to **~70–80**; that re-scan is pending. The **297 ADC/MeV** in the mc02 digitizer card is the C2-corrected data-side anchor (true B2 net median 5752 ADC over the trigger-unselected MC edep anchor) and is carried as an **explicit placeholder only**. The hardware pedestal ~6752 ADC statement stands (it is the `baseline_adc` column). (External Review 2026-07-02; Phase 2 2026-07-03)

---

## 10. Systematic Uncertainties

![MC-validation status chart after the external review and reruns](docs/figures/09_systematic_budget.png)

*Figure: MC-validation status after the 2026-07-02 external review and the 2026-07-03 reruns. This replaces the previous "systematic budget" bar chart: with the gain retracted, honest magnitudes cannot be drawn for most sources, so status is shown instead of fabricated percentages.*

| Source | Magnitude | Affected Quantities | Status |
|---|---|---|---|
| **Gain (MV0/Phase 2)** | ≈ 60–80 ADC/MeV range, no precision value (v1/v2 retracted) | Energy scale, dE/dx, ADC→MeV | ⚠️ Trigger-consistent scan ~60 (unquenched); quenched re-scan pending (~70–80 expected); 297 = placeholder |
| **Stopping-depth (MV3)** | residual χ²/ndf ~600–1,100 (≲1% per stave) after the trigger proxy | Depth fractions, B8 acceptance | 🔶 TENSION (re-graded 2026-07-03) — root cause = unsimulated trigger; closes further with the `Trig_bar` trigger flag |
| **Timewalk (MV4)** | MC/data ratio 0.70 (raw) / 1.40 (corrected); no pull (data σ unmeasured) | σ₆₈ corrected, TOF cuts | ⚠️ REVIEW — honest rerun 2026-07-03; matched per-stave rerun pending Phase 1 digitizer |
| **Early-peak anomaly (MV6b)** | 4.4% data class; MC 0.000% | Anomaly veto design | ✅ C12 ruled out (2026-07-04) — instrumental/trigger-phase, data-side investigation; veto not recommended (discards 16.7% of tracks) |
| **Pile-up R_max (MV5/MC03)** | One-sided bound; MC live-time +8% high | Rate tolerance | ⚠️ Data-driven bound; independent MC τ_eff 134.99 vs 124.79 ns — honest disagreement to reconcile |

**Quadrature total for deuteron fraction: ~12%** (pre-review value, dominated by the now-retracted MV0 gain ±30%; to be recomputed once a valid gain exists).

### 10.1 Program-Level Multiplicity Control (STATS01)

The external review flagged ~238 adaptive studies on one dataset with no multiplicity
control. STATS01 applies a per-family Benjamini–Hochberg correction (q = 0.05) over every
delta-with-CI claim in the artifacts.

![Program-level FDR census: multiplicity control is necessary, not sufficient](docs/figures/29_fdr_census.png)

*Figure 29: (a) per-family BH census — nominal (CI-excludes-zero) vs BH-surviving delta-with-CI claim counts across **1,948 claims in 152 studies** (representation 372/372, amplitude-charge 419/462, pedestal 225/231, timing 200/221, pileup 129/131, pid 17/18); (b) of the 17 scoreboard "bold wins", **11 survive BH, 6 are prose/derived-only, 0 fail** — and the callout shows **S03k survives BH yet was falsified** by the S03p/S03r feature-leakage null grids. Counts; BH q = 0.05 within family; the normal-approximation p-values make survivor counts an upper bound on trustworthy wins. Source: [`reports/stats01_program_fdr_20260703_220116/REPORT.md`](reports/stats01_program_fdr_20260703_220116/REPORT.md). Regenerated by `scripts/generate_postreview_figures.py`.*

**A BH-surviving claim is necessary, not sufficient:** multiplicity control does not repair
dependent-residual bootstraps, feature leakage, or unfair baselines (the S03k lesson).

---

## 11. Open Questions & Next Steps

### Closed by MC Validation ✅

_(Corrected 2026-07-03: R_max, digitizer gain, and anomaly species moved back to "Still Open" following the external review. Updated 2026-07-04: the post-review program closed the rows below.)_

| Question | Closed By | Finding |
|---|---|---|
| Is p/d PID at AUC 0.986 real? | MV1 (rerun 2026-07-03) | Yes as an MC truth ceiling; data within 0.5% via weak-label proxies, not species truth |
| Is Sample I deuteron-enriched in the B stack? | S21 + S23 (2026-07-03) | Yes — truth level (B2 ratio 1.519 [1.510, 1.528], exclusive 1.912; 91.2% d\|p pd-elastic pairs) **and data** (B2 f(A>5000) ratio 3.45 [3.41, 3.50]) |
| Is the p/d range-energy mechanism quantitative? | MV2 rerun (2026-07-03) | MeV-scale ekin after the momentum-unit fix; containment p 0.70 / d 0.84; Birks lookup remains best |
| What caused the MV3 stopping-depth FAIL? | Phase 2 (2026-07-03) | The unsimulated two-arm coincidence trigger; material narrative falsified; χ²/ndf 68,269 → 625 (109×); re-graded TENSION |
| Is the early-peak anomaly class C12 recoils? | MV6b (2026-07-04) | **No — ruled out** (0/1,656 quenched C12 records pass A>1000 at any gain); class is instrumental/trigger-phase, data-side |
| ML two-pulse failure rate on true overlaps? | MC03/S24 (2026-07-04) | Trad wins at matched 80% coverage; ML wins at full coverage (0.011 vs 0.048); σ68 trad 0.64 vs ML 0.89 ns |
| Zero-signal pedestal model validated? | MV7 (2026-07-03, MC level) | Adaptive MAE 3.48 / learned 1.50 ADC vs absolute truth (lower bounds; data side stays proxy-only) |

### Still Open 🔶

| Question | Blocker | Severity | Action |
|---|---|---|---|
| Residual MV3 tension (χ²/ndf ~600–1,100) | Truth-level A-HRD proxy is crude vs the real paddle coincidence; no quenching in the threshold model | 🔶 MEDIUM | **Score `Trig_bar` volumes → real per-event trigger flag** (supersedes the geometry-production plan) |
| Does MC timing match data in a matched comparison? | MV4 honest rerun is REVIEW: CFD noise-crossing and timewalk-sign pathologies fixed, but MC is still merged-track vs per-stave data with unmatched selection | 🔶 MEDIUM | Matched per-stave MV4 rerun on the Phase 1 digitizer (data selection applied, measured σ_data) |
| Why is the MC live-time +8% above data? | MC03 τ_eff 134.99 vs 124.79 ns, B2-driven; MC pulses clean by construction vs data pathologies | 🔶 MEDIUM | Data-matched selection/pathology model on the MC side; per-stave reconciliation |
| What is the precision digitizer gain? | Trigger-consistent optimum ~60 fitted unquenched; the quenched table has zero A>1000 rows at gain 60 | ⚠️ HIGH | **Quenched trigger-consistent gain re-scan** (~70–80 expected), then re-anchor on a geometry-robust observable |
| What instrumental mechanism makes the 4.4% early-peak class? | Species origin ruled out (MV6b); MC models neither trigger phase nor DAQ artifacts | 🔶 HIGH | **Data-side investigation** (P02 morphology, P09 taxonomy; baseline/noise/bipolar + trigger-phase hypotheses) |
| Does the S21 enrichment survive digitization end-to-end in MC? | S23 confirms the data side and the mimic direction; a fully digitized truth-labelled S21 selection replay is still pending | ⚠️ LOW | Rerun S21 selection on the mc02 digitized pulse table with the real trigger flag |
| Two-ended √2 projection valid? | Ignores correlated terms | ⚠️ MEDIUM | Measure correlation; validate projection |
| Forced-pedestal validated on data? | No forced-trigger in data (MV7 closes the MC side) | ⚠️ MEDIUM | Next beam run acquisition |
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
- CIs use **run-level bootstrap**; resample counts vary by study (typically 300–1000 — the blanket "1000 resamples" claim was corrected by the 2026-07-02 external review, which also flagged that pair-residual bootstraps under-cover by ~√1.5)
- AUC to 4 decimal places (from MV1 truth summary)
- Every number traceable to a `reports/<id>/REPORT.md`
- **Multiplicity control (2026-07-03):** a program-level Benjamini–Hochberg census over all 1,948 delta-CI claims exists ([STATS01](reports/stats01_program_fdr_20260703_220116/)); of the 17 scoreboard bold wins, 11 survive BH, 0 fail, 6 rest on prose only. BH survival is necessary, not sufficient (S03k survives BH yet is leakage-falsified). Sub-0.3 ns timing claims additionally require the reserved **confirmation partition** (runs 64, 12–30; [`docs/CONFIRMATION_PARTITION.md`](docs/CONFIRMATION_PARTITION.md)) and the shared estimators module (`src/ccb_mc_validation/statistics/estimators.py`). **That partition is defined but not yet used** — so any sub-0.3 ns timing claim is not yet confirmed on held-out data.

---

## Study Catalogue

Every study with a proper descriptive name and hyperlink to its full report.

### Foundation Studies (S00–S21)

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
| **S05** | [Hierarchical B-Stack Covariance](reports/) | B2 pairs far more correlated than downstream pairs (quantitative covariance values ~1042/~16 ns² withdrawn 2026-07-03 — closure script numerically invalid) |
| **S05a** | A-Stack Independent-Arm Control (formerly "External Control"; the A arm measures different particles — experiment-owner setup facts, 2026-07-03) | |
| **S07** | [ML Rigor Scoreboard](reports/1780997954.15217.702122ea__s07_ml_rigour_scoreboard/) | Most ML "wins" are leaked; CORRECTED claims |
| **S10** | [Pile-up Rate Model](reports/1780997954.15277.548b01a3__s10_pileup_rate_model/) | τ_eff = 124.8 ns → R_max ≤ 3.05 MHz (one-sided bound) |
| **S11** | [Two-Pulse Template + ML Recovery](reports/) | RETIRED — rigged benchmark (review P8); replaced by the honest truth-labelled S24 (below) |
| **S14** | Range-Energy Calibration | GEANT4 Birks lookup validated |
| **S16** | [Pedestal/Baseline Validation](reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/) | Adaptive pedestal biased 341 ADC (MAE) |
| **S18** | [A-Stack Independent Reproduction](reports/1780997954.15397.168324f2__s18_astack_independent_reproduction/) | A1–A3 width 1.39 ns reproduces note's 1.43 ns |
| **S21** | [Sample I vs II Trigger-Truth Comparison](reports/s21_sample12_trigger_truth_1783077969/) | Sample-I d-enrichment CONFIRMED at truth level: B2 ratio 1.519 [1.510, 1.528]; pd-pair tagging (91.2% d\|p) |
| **S22** | [Per-Stave Timing vs Amplitude](reports/s22_timing_vs_amplitude_1783108999/) | 1/A beats 1/√A raw; downstream per-stave ≈0.85–1.1 ns at high amplitude; B2 saturation-excluded |
| **S23** | [Sample I vs II Data-Side Closure + Data–MC](reports/s23_sample12_data_mc_1783108675/) | d-enrichment consistent in data (B2 f(A>5000) ratio 3.45 [3.41, 3.50]; run-set differences not yet separated); trigger mimic moves MC toward data (KS 0.192→0.131); DR 0.738 (z=−99, statistics-only) |
| **S24** | [Honest Two-Pulse Benchmark (MC03)](reports/mc03_overlay_1783180480/) | Truth-labelled: trad wins at matched 80% coverage; ML wins at full coverage (0.011 vs 0.048); σ68 trad 0.64 / ML 0.89 ns; independent MC τ_eff 134.99 vs data 124.79 ns |

### ML Pulse Characterisation (P01–P13)

| Code | Descriptive Name | Report |
|---|---|---|
| **P01** | [Self-Supervised Waveform Representation](reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation/) | AE > PCA at d=2–4; PCA catches up at d≥8 |
| **P02** | [Unsupervised Pulse-Type Discovery](reports/) | ~4% early-peak anomaly found |
| **P03** | Deep Timing Regression | MLP/CNN on raw waveform |
| **P04** | [Amplitude & Charge Regression](reports/) | ML wins duplicate-readout: res68 0.003 vs 0.12 |
| **P05** | Two-Pulse CNN Decomposition | |
| **P07** | [Saturation Recovery](reports/P07_saturation_recovery/) | ML 3–7× better than templates |
| **P09** | Rare Waveform Anomaly Taxonomy | ~4% early-peak class in data; MC identification retracted 2026-07-03 (species open) |

### MC Validation (MV0–MV7) and Post-Review Program (2026-07-03/04)

| Code | Descriptive Name | Report | Verdict |
|---|---|---|---|
| **MV0** | [Digitizer Gain Calibration](reports/mv0_digitizer/) | v1 and v2 both retracted 2026-07-03; current best statement: gain ≈ 60–80 ADC/MeV (trigger/quenching-dominated), no precision value | ⛔ retracted / ⚠️ range only |
| **MV1** | [Proton/Deuteron PID Validation](reports/mv1_mv2_truth_pid_energy_1783077795/) | AUC 0.986, purity 0.964 (rerun 2026-07-03) | ✅ |
| **MV2** | [Energy/Range Truth Validation](reports/mv1_mv2_truth_pid_energy_1783077795/) | Rerun 2026-07-03 after unit fix: MeV-scale ekin; containment p 0.70 / d 0.84; medians p 101.1 / d 73.4 MeV | ✅ (geometry caveat) |
| **MV3 v4** | [Stopping-Depth Profile + Phase-2 Diagnostics](reports/phase2_geometry_1783108797/) | Root cause = unsimulated trigger; χ²/ndf 68,269 → 625 (109×); material narrative falsified; next: `Trig_bar` trigger flag | 🔶 TENSION (re-graded from FAIL) |
| **MV4** | [Timing Resolution Validation](reports/mv4_timing_1783077795/) | Honest rerun 2026-07-03: rising-edge CFD, timewalk B = +39.6 ns·ADC (physical); MC pair-equiv 2.087 ns between data 2.993 (raw) and 1.50 (corrected); matched per-stave rerun pending | ⚠️ REVIEW |
| **MV5** | [Pile-up Rate Validation](reports/mv5_pileup_study/) | Retracted as validation 2026-07-03 (MC τ_eff was hardcoded copy of data); slot refilled by MC03's independent τ_eff (134.99 vs 124.79 ns, +8%) | ⛔ → 🔶 (honest disagreement) |
| **MV6** | [Representation & Anomaly ID](reports/mv6_representation_study/) | Retracted 2026-07-03 (C12 attribution unsupported); superseded by MV6b | ⛔ |
| **MV6b** | [Anomaly Taxonomy with Birks Quenching](reports/mv6b_anomaly_quenching_1783180742/) | C12 RULED OUT: 0/1,656 quenched C12 records pass A>1000 at any gain; early-peak class is instrumental/trigger-phase (data-side) | ✅ exclusion |
| **MV7** | [Zero-Signal Pedestal Validation](reports/mc02_pulse_table_1783107862/) | Adaptive MAE 3.48 ADC, learned 1.50 ADC vs absolute truth on zero-signal MC (lower bounds) | ✅ (MC level) |
| **MC02** | [Digitized MC Pulse Table (Phase 1)](reports/mc02_pulse_table_1783107862/) | 1M events → 518,247 rows; per-stave data-tuned τ_decay; Birks + A-arm variants ([Phase 4](reports/phase4_1783180742/)) | ✅ built (gain placeholder) |
| **MC03** | [Truth-Labelled Overlays + Independent τ_eff](reports/mc03_overlay_1783180480/) | 600k overlay records at 0.5/1.5/3 MHz; honest S24 benchmark; MC τ_eff 134.99 ns vs data 124.79 (+8%) | ✅ built / 🔶 τ_eff disagreement |
| **STATS01** | [Program-Level FDR Census](reports/stats01_program_fdr_20260703_220116/) | 1,948 delta-CI claims; 11/17 bold wins survive BH, 0 fail, 6 prose-only; S03k survives BH yet leakage-falsified | ✅ census |

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
