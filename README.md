# ccb-testbeam

Analysis of the **CCB test-beam** data: 190 MeV protons on a CD₂ target, recorded by the
HRD scintillator range stacks at the Cyclotron Centre Bronowice (Centrum Cyklotronowe
Bronowice, Kraków). The physics goals are **same-particle timing resolution** and
**pile-up characterisation** of the scintillator staves, carried out **data-driven (no
Monte Carlo)**.

This repository holds the **code, documentation, study plans, and results**. The raw data
(~6.4 GB) lives outside git — see [`DATA.md`](DATA.md).

> **Start here:** [`PROJECT_REPORT.md`](PROJECT_REPORT.md) is the single human-readable status
> report — the science, results so far (with numbers), current blockers, and what's next, all in
> one place.

> Status: research in progress. Results here are **not yet peer-reviewed**; treat all
> numbers as preliminary.

## At a glance

| Item | Value |
|---|---|
| Beam | proton, T_p = 190 MeV |
| Target | deuterated polyethylene (CD₂) |
| Detector | HRD scintillator range stacks A & B (ΔE–E / range telescope) + TPC + trigger scints |
| Analysed staves | B-stack: B2, B4, B6, B8 (main); A-stack: A1, A3 (cross-check) |
| Waveform | 18 samples @ 10 ns, one-ended WLS-fibre readout |
| Selected pulses | ~640,737 (B-stack, A > 1000 ADC) |
| Headline timing | downstream single-stave ≈ 0.68–1.0 ns (B6 best); combined 3-stave ≈ 0.54 ns; two-ended projection ≈ 0.6–1.0 ns |
| Pile-up tolerance | R_max ≈ 4.2 MHz (|Δt|<1 ns & area<20% at >90% eff, τ_eff=90 ns) |

## Findings so far

Each study reproduces a report number first, then benchmarks a strong **traditional** method
head-to-head against an **ML** method (split by run, bootstrap CIs). One row per completed study;
full write-ups in `reports/<study>/REPORT.md`, live scoreboard in `reports/SUMMARY.md`.

| Study | Question | Headline finding | ML vs traditional |
|---|---|---|---|
| **S00** | Can we rebuild the selected-pulse table from raw ROOT? | **640,737** pulses reproduced **exactly** (zero delta, all per-stave counts) | threshold is exact; ML adds nothing (correct) |
| **S00a** | Is sorted `hrdMax` a valid count proxy? | No — it over-counts; the gate must stay pinned to raw `HRDv` | — |
| **S01** | Amplitude-adaptive template & `q_template` on all 640k pulses | Pulse shape is low-dim; AE reconstructs far better than the median template | **ML wins** (recon MSE 0.0021 vs 0.044) |
| **S02** | Best timing pickoff (CFD/OF/template)? | Single-stave σ68 from same-particle residuals | **ML wins**: ridge-on-CFD20 **1.85 ns** vs template **2.89 ns** (Δ≈1.04 ns) |
| **S07** | Are the ML classifiers calibrated & fairly benchmarked? | Low-current/topology signal is real, not a strawman | **ML wins**: ROC AUC **0.77** vs 0.50 (p≈0.001) |
| **S10** | Pile-up rate model & current-dependent excess | Poisson **R_max ≈ 4.2 MHz** reproduced; downstream high−low excess CI excludes zero | tie — ML score is diagnostic, not production-superior |
| **S16** | Is the adaptive pedestal unbiased? | Adaptive pedestal is badly biased (−311 ADC); a learned pedestal fixes it | **ML wins**: MAE **49** vs **341 ADC** |
| **S18** | Independent A-stack reproduction (Sample III/IV) | A1–A3 robust width **1.39 ns** reproduces the note's 1.43 ns | tie (ML Δ not significant, p≈0.52) |
| **P02** | Unsupervised pulse-type discovery | Found a ~4% early-peak/low-area anomalous class with no labels | **AE beats PCA 40–51%** at low latent dim |
| **P07** | Recover saturated high-amplitude B2 pulses | Recover true amplitude from the unsaturated rising edge | **ML wins**: ~4% error vs template 10–29% (3–7×) |

_Recurring theme: ML clearly helps where the signal is in **waveform shape** (timing, saturation,
pedestal, representation); it ties the analytic method where the physics is already a clean
closed-form model (pile-up Poisson rate, A-stack residual width). Every ML "win" is checked for
leakage (split by run; see `fleet/LESSONS.md`)._ The fleet runs autonomously — see
[`fleet/FLEET_STANDARD.md`](fleet/FLEET_STANDARD.md).

## Repository layout

```
ccb-testbeam/
├── README.md            ← you are here
├── DATA.md              ← where the raw/extracted data lives + manifest
├── docs/                ← the documentation, broken into focused modules
│   ├── 00_overview.md
│   ├── 01_setup_and_detector.md
│   ├── 02_data_and_runs.md
│   ├── 03_pulse_reconstruction.md
│   ├── 04_timing_calibration.md
│   ├── 05_timing_resolution.md
│   ├── 06_pileup.md
│   ├── 07_ml_methods.md
│   ├── 08_astack.md
│   ├── 09_open_questions.md
│   ├── glossary.md
│   └── references.md
├── studies/             ← the research programme
│   ├── STUDIES.md        ← master, prioritised list of everything we can study
│   └── STUDY_TEMPLATE.md ← required report format for every study
├── reports/             ← agent / human study write-ups land here (one dir per study)
├── scripts/             ← analysis & ML code
├── configs/             ← run configs, cut definitions, calibration constants
└── fleet/
    └── ORCHESTRATION.md  ← how the codex/tn-ticket agent fleet runs this project
```

## Provenance

This repo was bootstrapped from two analysis notes:
- `bstack_pulse_timing_report_v41_ccb_corrected.pdf` (54 pp, B-stack only, "v41")
- `bstack_astack_report_with_timing_label_pileup_ml.pdf` (122 pp, B+A stack + ML appendices, 2026-06-07)

The `docs/` modules are a structured, maintainable decomposition of those notes. Where the
two notes disagree numerically (e.g. run splits, per-stave resolutions), `docs/` follows the
**newer 122-page report** and flags the difference.

## How the work gets done

Studies are defined in [`studies/STUDIES.md`](studies/STUDIES.md), turned into tickets on the
`tn-ticket` queue (`project:testbeam`), and worked by a fleet of codex agents (local laptop +
LUNARC). See [`fleet/ORCHESTRATION.md`](fleet/ORCHESTRATION.md). Every study produces a report
in `reports/` following [`studies/STUDY_TEMPLATE.md`](studies/STUDY_TEMPLATE.md).
