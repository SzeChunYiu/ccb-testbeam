# ccb-testbeam

Analysis of the **CCB test-beam** data: 190 MeV protons on a CD₂ target, recorded by the
HRD scintillator range stacks at the Cyclotron Centre Bronowice (Centrum Cyklotronowe
Bronowice, Kraków). The physics goals are **same-particle timing resolution** and
**pile-up characterisation** of the scintillator staves, carried out **data-driven (no
Monte Carlo)**.

This repository holds the **code, documentation, study plans, and results**. The raw data
(~6.4 GB) lives outside git — see [`DATA.md`](DATA.md).

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
