# CCB Test-Beam Analysis

> **Analysis of the CCB test-beam data: 190 MeV protons on CD₂ target, measured by HRD scintillator range stacks.**
>
> Physics goals: **same-particle timing resolution** and **pile-up characterization**.

[![Studies](https://img.shields.io/badge/studies-~230-blue)](studies/STUDIES.md)
[![MC Validations](https://img.shields.io/badge/MC%20validations-6-green)](studies/MC_VALIDATION_PROGRAM.md)
[![Python](https://img.shields.io/badge/python-3.11-3776AB)](pyproject.toml)
[![Status](https://img.shields.io/badge/status-research%20in%20progress-yellow)](WIKI.md)

---

## Quick Start

| You want to... | Read this |
|---|---|
| **Understand the whole project** | → **[`WIKI.md`](WIKI.md)** — illustrated, comprehensive, self-contained |
| **See the key results** | → [WIKI.md §1 Executive Summary](WIKI.md#1-executive-summary) |
| **See what's missing / what to do next** | → **[`STUDY_GAPS.md`](STUDY_GAPS.md)** — gap analysis & open questions |
| **Get the one-page status** | → [`PROJECT_REPORT.md`](PROJECT_REPORT.md) |
| **Read the publication narrative** | → [`FINDINGS_SYNTHESIS.md`](FINDINGS_SYNTHESIS.md) |
| **Browse all ~230 studies** | → [`studies/STUDIES.md`](studies/STUDIES.md) |
| **Understand the methodology** | → [`docs/REPORT_STANDARD.md`](docs/REPORT_STANDARD.md) |
| **Look up terms** | → [`docs/glossary.md`](docs/glossary.md) |

## Headline Results

**2026-07-03:** an external review found the MC-validation layer unsound; see [`EXTERNAL_REVIEW_2026-07-02.md`](EXTERNAL_REVIEW_2026-07-02.md) and the corrections throughout this repo.

| Measurement | Value | Confidence |
|---|---|---|
| Selected pulses | **640,737** (exact reproduction) | ✅ |
| Best timing (B6) | **σ(core) ≈ 0.68–0.75 ns** (external-note Gaussian-core decomposition; not σ₆₈, not MC-validated) | ⚠️ Under review |
| Combined 3-stave (B4+B6+B8) | **σ₆₈ ≈ 0.54–0.56 ns** | ⚠️ Under review (covariance validation withdrawn) |
| Pile-up tolerance | **R_max ≤ 3.05 MHz** (one-sided upper bound; censoring-aware estimators suggest ≈2.1 MHz or lower) | ⚠️ Data-only (MV5 was self-referential, not an independent validation) |
| Proton/deuteron PID | **AUC = 0.986** (MC truth ceiling; data reaches it only via weak-label proxies, not species truth) | ⚠️ Qualitative MC support |
| Anomaly identity | **C12 nuclear recoils** (0.32%) | ⛔ Withdrawn (MV6 ran with invalidated gain, no quenching, no threshold; 12× data/MC rate mismatch unresolved) |

## Repository Layout

```
ccb-testbeam/
├── WIKI.md              ← 🌟 START HERE: complete illustrated wiki
├── STUDY_GAPS.md         ← what's missing, what to do next
├── PROJECT_REPORT.md     ← one-page status report
├── FINDINGS_SYNTHESIS.md ← publication narrative across all studies
├── README.md             ← you are here
├── DATA.md               ← data locations and integrity
├── docs/                 ← modular documentation (setup, methods, etc.)
│   ├── figures/          ← all generated figures
│   ├── mc_validation/    ← MC validation details
│   └── glossary.md       ← terminology reference
├── studies/              ← the research programme
│   ├── STUDIES.md         ← master prioritized study list
│   └── STUDY_TEMPLATE.md  ← required report format
├── reports/              ← per-study reports (one directory per study)
├── scripts/              ← analysis & ML code
├── configs/              ← run configs, cut definitions
├── notebooks/            ← Jupyter notebooks
├── geant4/               ← GEANT4 simulation code & jobs
├── fleet/                ← agent fleet orchestration
└── src/                  ← Python package source
```

## Getting Started (Development)

```bash
# Clone
git clone https://github.com/SzeChunYiu/ccb-testbeam.git
cd ccb-testbeam

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -q

# Reproduce the data anchor
python scripts/01_build_pulse_table_from_root.py
```

## Data

Raw data (~6.4 GB, 110 ROOT files) lives outside git. See [`DATA.md`](DATA.md) for locations (LUNARC `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/`).

## Status

**Research in progress.** All results preliminary, not yet peer-reviewed. The project follows strict reproducibility and methodology rules — see [`docs/REPORT_STANDARD.md`](docs/REPORT_STANDARD.md).
