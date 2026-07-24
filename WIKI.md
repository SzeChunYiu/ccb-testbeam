# CCB Test-Beam Analysis — Unified Illustrated Wiki

> **A self-contained guide to the CCB test-beam analysis, written for readers with and without prior knowledge of particle physics instrumentation.**
>
> Every study has a **descriptive name** and a **hyperlink** to its full report. Every claim is traceable to source. Uncertainty coverage is tracked in the canonical claim ledger; entries marked `CI_MISSING_BLOCKING` remain incomplete.
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
| **SUPERSEDED** | Retained only as correction history; not an accepted current result |

### Canonical Results Table

| Claim | Current value | Stat. unc. | Syst. unc. | Truth type | Status |
|---|---|---|---|---|---|
| Selected B-stack pulses | 640,737 | — | — | data_count | **VALIDATED** |
| B6 single-stave σ₆₈ | 0.68–0.75 ns | 0.02 | 0.05 | data + digitized MC | **VALIDATED** |
| Combined 3-stave σ (B4+B6+B8) | 0.54–0.56 ns | 0.02 | 0.08 | data_only | **DONE_DATA_ONLY** |
| Pair covariance | −0.127 ns² | — | — | data_only | **DONE_DATA_ONLY** |
| Rmax (pile-up tolerance) | Withheld pending S-STAT-003 | — | — | derived model conflicted | **BLOCKED** |
| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | data + MC self-consistent | **VALIDATED** |
| Digitizer gain (MV0 v2) | 92 ± 28 ADC/MeV | 14 | 28 | digitized MC | **VALIDATED** |
| p/d PID AUC | 0.9860 | — | — | MC truth only | **TRUTH_LEVEL_MC_ONLY** |
| C12-like anomaly fraction in truth-labelled MC | 283 / 87,555 tracks (0.32%) | — | — | MC truth only | **TRUTH_LEVEL_MC_ONLY** |
| MV3 B8 data/MC | data 2.3% / MC 22.3% | — | — | MC vs data | **FAIL** |
| MV4 raw timing pull | −1.05σ | — | — | digitized MC | **VALIDATED** |
| MV4 corrected timing pull | +2.68σ | — | — | digitized MC | **TENSION** |
| ML timing | Diagnostic only | — | — | data_only | **GATED** |
| Duplicate-readout model | No production model selected | — | — | data external duplicate readout | **GATED** |
| Saturation-recovery model | External held-out closure is worse than raw | — | — | data external duplicate readout | **GATED** |

Rmax is withheld pending S-STAT-003. No production duplicate-readout or saturation correction is authorized.

### Corrected Values (Historical Context Only)

| Old value | New canonical value | Reason |
|---|---|---|
| 4.22 MHz | Superseded; accepted replacement withheld pending S-STAT-003 | Former rate and later replacement use unresolved criteria |
| 3.0448717948717947 MHz | Superseded history only; do not use as an accepted result | Derived from the recorded 0.38 duty factor, not a validated occupancy-quality threshold |
| ~246 ADC/MeV | 92 ± 28 ADC/MeV | MV0 v2 recalibration |
| 706,373 pulses | 640,737 pulses | S00 median selector gate |
| PCA 3 PCs 89%, 8 PCs 99.7% | Needs canonical rerun | Variance normalization inconsistent |

### What This Project Does NOT Claim

1. **No final event-aligned truth in real beam data**
2. **No final absolute per-event energy calibration from waveform alone** (30% syst.)
3. **No final B8 acceptance correction** (MV3 geometry FAIL)
4. **No production ML timing replacement** (transfer/leakage controls pending)
5. **No forced-pedestal truth in current data**
6. **No accepted numerical Rmax until S-STAT-003 resolves the criterion**
7. **No production duplicate-readout or saturation correction**

### Executive Verdict

The analysis does **not** find that machine learning should fully replace traditional methods. Traditional physics-anchored approaches remain superior for timewalk correction, pile-up rate estimation, and energy calibration. Duplicate-readout model selection is still gated because the coverage interval crosses the eligibility threshold. Saturation recovery is also gated because external held-out duplicate closure is worse than raw and producer-byte provenance is incomplete. The most important finding is methodological: **most apparent ML advantages fail or remain unresolved after leakage, uncertainty, provenance, and transfer controls**.

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
| MC raw timing pull | −1.05σ | **VALIDATED** |
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

> **Claim-governance update (2026-07-24).** τeff remains validated; numerical Rmax is withheld pending S-STAT-003. See [Full chapter](docs/academic_chapters/05_pileup_analysis.md).

### Key Results

| Observable | Value | Status |
|---|---|---|
| Rmax (pile-up tolerance) | Withheld pending S-STAT-003 | **BLOCKED** |
| τeff (effective live-time) | 124.79 ns | **VALIDATED** (corrected from 90 ns) |
| Two-pulse ML recovery | Lower RMS, higher failure | **GATED** (operating curve pending) |

### Rmax Status

The effective live-time estimate remains `124.79 ns`, but the accepted occupancy-quality threshold is unresolved. The recorded `0.38` value is a beam duty factor, not a justified reconstruction-quality threshold, and the MV5 summary records no recovery-failure-ceiling crossing. Numerical Rmax values are therefore withheld until S-STAT-003 preregisters and validates the criterion, derivation, and uncertainty treatment.

The historical value `3.0448717948717947 MHz` is retained only in the superseded table above. It must not be cited as an accepted pile-up tolerance or as a validated lower bound.

### Critical Open Issues

1. **Canonical Rmax criterion unresolved** — S-STAT-003 must define the measurand and threshold
2. **τeff cross-checks needed** — at least 2 independent methods (threshold scan, exponential fit)
3. **Censoring systematic** — 180 ns window truncates ~23% of pulse tail; not propagated to any future Rmax
4. **ML score calibration** — classifier output not mapped to physical overlap probability
5. **MC overlay truth** — two-pulse recovery not validated with truth-labelled overlaps

### Next Study Priority
🔬 S-STAT-003: Resolve canonical Rmax definition and uncertainty model
🔬 S-PU-001: Measure τeff by alternative methods → confirm robustness
🔬 Quantify censoring systematic before restoring any numerical Rmax

**[Full chapter:](docs/academic_chapters/05_pileup_analysis.md)**

## 6. Pulse Shape & Machine Learning

> **Claim-governance update (2026-07-24).** PCA variance remains superseded; P04p and P07e production decisions remain gated. See [Full chapter](docs/academic_chapters/06_pulse_shape_ml.md).

### ML Verdict Matrix

| Domain | Traditional | ML | Verdict |
|---|---|---|---|
| Timewalk correction | Analytic A₀+B/A | MLP/CNN | **Traditional wins** (ML fails LORO) |
| Duplicate readout | Amplitude correlation | Harm-veto models | **GATED** — coverage-uncertainty rule and transfer validation unresolved |
| Saturation recovery | Raw/clip-aware observables | Ratio-transfer model | **GATED** — external held-out closure is worse than raw; producer bytes unbound |
| Pile-up recovery | Template deconvolution | CNN | **GATED** |
| PID | ΔE-E/range | HGB | **ML informative** (MC-truth only) |

### Key Corrections

1. **PCA variance: SUPERSEDED.** Wiki (89% / 99.7%) and corrected chapter differ. Needs canonical rerun.
2. **AE superiority: CORRECTED.** Original claim was leakage (train-test contamination).
3. **Duplicate readout: GATED.** The reported GBT point estimate barely clears the coverage threshold, but its run-bootstrap interval crosses the gate; a lower-bound rule changes the eligible model.
4. **Saturation recovery: GATED.** Pseudo-saturation closure is synthetic, while external held-out duplicate closure degrades from raw `0.120794` to ML `0.176358` charge res68.
5. **No production duplicate-readout or saturation correction is authorized.**

**[Full chapter:](docs/academic_chapters/06_pulse_shape_ml.md)**

---

## 7. Amplitude, Charge & Energy Calibration

> **Claim-governance update (2026-07-24).** Gain correction remains documented; P04p and P07e are separated and gated. See [Full chapter](docs/academic_chapters/07_energy_calibration.md).

### Key Results

| Observable | Value | Status |
|---|---|---|
| Digitizer gain | 92 ± 28 ADC/MeV | **VALIDATED** (MV0 v2, corrected from ~246 ADC/MeV) |
| KS mismatch (MV0 v2) | 0.158 | **TENSION** (inter-stave variation unresolved) |
| Absolute energy uncertainty | ~35% | Structural limitation |
| ML duplicate-readout | No canonical production winner | **GATED** — selection interval crosses the coverage gate |
| ML saturation recovery | External held-out closure worse than raw | **GATED** — producer bytes and transfer validation incomplete |

### What Is NOT Claimed
- **No absolute per-event energy calibration** (35% systematic)
- **No per-stave gain measurement** (±10% assumed, not measured)
- **No Birks constant calibration** (kB = 0.10–0.15 mm/MeV unverified for this scintillator)
- **No production duplicate-readout model or saturation correction**

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
| C12-like anomaly fraction in truth-labelled MC | 283 / 87,555 tracks (0.32%) | **TRUTH_LEVEL_MC_ONLY** (MV6; transfer to data unvalidated) |

### Required Studies (Not Yet Done)

- Anomaly detection efficiency (synthetic injection)
- False-positive rate (data sideband validation)
- Species composition of anomaly cluster

### Veto Impact
No data-veto performance is claimed. Efficiency, false-positive rate, and retained-event fraction require the preregistered matched data/MC closure and independent data sidebands.

**[Full chapter:](docs/academic_chapters/09_anomaly_id.md)**

---

## 10. Monte Carlo Validation

> **Claim-governance update (2026-07-24).** Full MV0–MV6 validation matrix retained; MV5 numerical Rmax is withheld. See [Full chapter](docs/academic_chapters/10_mc_validation.md).

### Validation Matrix

| Study | Observable | Verdict | Action |
|---|---|---|---|
| MV0 v2 | Digitizer gain | **VALIDATED** | Reduce systematic |
| MV1 | p/d PID | **TRUTH_LEVEL_MC_ONLY** | Data transfer needed |
| MV3 | Stopping depth | **FAIL** (χ²/ndf = 68,269) | **GEANT4 fix** |
| MV4 raw | Timing | **VALIDATED** (−1.05σ) | Accept |
| MV4 corrected | Timing | **TENSION** (+2.68σ) | **Digitizer fix** |
| MV5 | Pile-up Rmax | **BLOCKED** | Resolve S-STAT-003 before restoring a value |
| MV6 | C12-like anomaly in truth-labelled MC | **TRUTH_LEVEL_MC_ONLY** | Matched data/MC closure and efficiency study |

### Two Blocking Issues

1. **MV3: Structural GEANT4 failure** — missing 8–10 g/cm²; blocks acceptance corrections
2. **MV5: Canonical Rmax criterion unresolved** — numerical value and uncertainty are withheld pending S-STAT-003

**[Full chapter:](docs/academic_chapters/10_mc_validation.md)**

## 11. Open Questions & Next Steps

> **Thesis-grade update (2026-07-14).** All gaps now have closure criteria. See [Full chapter](docs/academic_chapters/11_open_questions.md).

### Blocking Issues

| Gap | Issue | Action |
|---|---|---|
| GAP-01 | MV3 geometry FAIL (χ²/ndf = 68,269) | GEANT4 fix → new MC → rerun MV3 |
| GAP-06 | Combined timing assumes independence | Covariance-aware estimator |
| S-STAT-003 | Numerical Rmax criterion unresolved | Preregister criterion, derivation, uncertainty, and closure |

### High-Priority Issues

| Gap | Issue | Action |
|---|---|---|
| GAP-02 | MV4 corrected timing TENSION | Digitizer timewalk fix |
| GAP-03 | Gain 30% systematic | Per-stave calibration |
| GAP-04 | PCA variance inconsistent | Canonical rerun |
| GAP-05 | PID weak-label not separated | Data evaluation |
| GAP-09 | ML timing not production | Full leakage controls |
| BLK-P04P-001 | Duplicate-readout selection uncertainty | Preregister coverage rule and validate transfer |
| BLK-P07E-001 | Saturation producer provenance and external closure | Recover bytes and validate new runs/staves |

### Closure Criteria
A gap is CLOSED only when: study produces quantitative result → REPORT.md written → claim ledger updated → chapters updated → gap removed from list.

**Current fully-closed gaps:** 0 of 10 catalogued.

**[Full chapter:](docs/academic_chapters/11_open_questions.md)** | **[STUDY_GAPS.md](STUDY_GAPS.md)**

---

## 12. Methodology Appendix

> **Thesis-grade update (2026-07-14).** Build/lint checks and reproducibility checklist documented. See [Full chapter](docs/academic_chapters/12_methodology_appendix.md).

### Build/Lint Checks

| Check | Script | Severity |
|---|---|---|
| Superseded-value scan | `scripts/audit_claim_superseded.py` | **Blocking** |
| Claim ledger completeness | `scripts/check_claim_ledger_complete.py` | **Blocking** |
| Broken link checker | `scripts/broken_link_checker.py` | High |
| Figure source data checker | `scripts/check_figure_source_data.py` | High |
| ML leakage control checker | `scripts/check_ml_leakage_controls.py` | High |

### CI Pipeline
```yaml
name: Thesis QA
on: [push, pull_request]
jobs:
  audit: [superseded scan, link check, claim check]
```

### Reproducibility
Every chapter must be reproducible from: command + config + seed + output table + manifest + figures + report.

**[Full chapter:](docs/academic_chapters/12_methodology_appendix.md)** | **[CLAIM_CHECKLIST_INTEGRATION.md](docs/CLAIM_CHECKLIST_INTEGRATION.md)**

---

## Study Catalogue

> **Thesis-grade update (2026-07-14).** See [Full chapter](docs/academic_chapters/11_open_questions.md) for the complete study catalogue.

### Study Categories

| Category | Count | Status |
|---|---|---|
| Data-driven studies | ~230 | Various completion states |
| MC validations (MV0-MV6) | 7 | 3 VALIDATED, 1 TENSION, 1 FAIL, 1 BLOCKED, 1 TRUTH_LEVEL_MC_ONLY |
| Diagnostic studies (MV3b, MV4b) | 2 | Root causes identified |
| GEANT4 simulation studies | ~10 | G4-01 through G4-08 |

See [`STUDY_GAPS.md`](STUDY_GAPS.md) for the full gap inventory with dependency graph.
