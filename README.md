# CCB Test-Beam Analysis

> **Analysis of the CCB test-beam data: 190 MeV protons on CD₂ target, measured by HRD scintillator range stacks.**
>
> Physics goals: **same-particle timing resolution** and **pile-up characterization**.

[![Studies](https://img.shields.io/badge/studies-~230-blue)](studies/STUDIES.md)
[![MC Validations](https://img.shields.io/badge/MC%20validations-6-green)](studies/MC_VALIDATION_PROGRAM.md)
[![Python](https://img.shields.io/badge/python->=3.11-3776AB)](pyproject.toml)
[![Status](https://img.shields.io/badge/status-research%20in%20progress-yellow)](WIKI.md)

---

## Quick Start

| You want to... | Read this |
|---|---|
| **Understand the whole project** | → **[`WIKI.md`](WIKI.md)** — illustrated, comprehensive, self-contained |
| **Canonical one-screen dashboard** | → **[`reports/PROJECT_DASHBOARD.md`](reports/PROJECT_DASHBOARD.md)** — proven vs BLOCKED at a glance |
| **See the key results** | → [WIKI.md §1 Executive Summary](WIKI.md#1-executive-summary) |
| **See what's missing / what to do next** | → **[`STUDY_GAPS.md`](STUDY_GAPS.md)** — gap analysis & open questions |
| **Get the one-page status** | → [`PROJECT_REPORT.md`](PROJECT_REPORT.md) |
| **Read the publication narrative** | → [`FINDINGS_SYNTHESIS.md`](FINDINGS_SYNTHESIS.md) |
| **Browse all ~230 studies** | → [`studies/STUDIES.md`](studies/STUDIES.md) |
| **Understand the methodology** | → [`docs/REPORT_STANDARD.md`](docs/REPORT_STANDARD.md) |
| **Look up terms** | → [`docs/glossary.md`](docs/glossary.md) |

## Headline Results

> **All results are preliminary and study-scoped, not peer-reviewed.**
> Canonical entry point: [`reports/PROJECT_DASHBOARD.md`](reports/PROJECT_DASHBOARD.md).
> Machine-readable public authority: [`docs/contracts/PUBLIC_CLAIM_AUTHORITY.json`](docs/contracts/PUBLIC_CLAIM_AUTHORITY.json).
> The row-by-row claim ledger is [`docs/claim_ledger.csv`](docs/claim_ledger.csv); this
> section mirrors [`reports/studies/clusterE/claims_table.csv`](reports/studies/clusterE/claims_table.csv)
> and must not advertise a stronger status than the ledger.

**MC method closure proven; detector-performance transfer to beam data remains gated.**
The full analysis chain — timing, ΔE-E PID, ADC/Birks energy calibration, and pile-up —
is demonstrated end-to-end on the Krakow 1M-event Geant4 Monte Carlo (clusters A–D +
Opticks, all merged on `origin/main`). Raw beam ROOT files are **located on LUNARC at `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/`** (2026-07-25; see `reports/studies/data_side/REPORT.md`), but the **canonical archive not yet populated** at `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam-data/` (`DATA.md`). Located
waveforms are 16-sample; detector-resolution claims remain gated by format/lineage
(#952/#962) and bench calibration. Public headlines are governed by
`docs/contracts/PUBLIC_CLAIM_AUTHORITY.json` + `docs/claim_ledger.csv`.

| Claim | Value | Evidence class | Status | Source |
|---|---|---|---|---|
| Selected B-stack pulses (S00 gate) | **640,737** | DATA_MEASUREMENT | 🔒 GATED | CL-001 |
| Combined timing σ₆₈ (4-sensor, MC) | **0.089 ns** | MC_METHOD_CLOSURE | ✅ PASS | clusterB #918 |
| PID p-vs-d AUC (realistic chain, MC) | **0.898** | SIMULATION_RESULT | ✅ PASS | clusterA #921 |
| ADC calibration (digitizer gain, MC) | **119.17 ADC/MeV** | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| Birks kB (per-track dE/dx, MC) | **0.0156 cm/MeV** | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| Digitizer-domain Rmax (0% gate, MC) | **0.605 MHz** | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| Opticks GPU/CPU parity | 0 GPU hits / 4592 CPU; CPU ctest 9/9 | SIMULATION_RESULT | 🟡 PARTIAL | opticks #920 |
| Detector timing resolution (data) | withheld | BLOCKED_DATA | ⛔ BLOCKED | CL-002..006 |
| Canonical pile-up Rmax | withheld | BLOCKED | ⛔ BLOCKED | CL-010 (S-STAT-003) |
| Legacy Rmax = 3.044 MHz | SUPERSEDED | SUPERSEDED | 🚫 SUPERSEDED | CL-012 (do not use) |
| ADC gain (data/MC proxy, MV0) | **92 ADC/MeV** (heuristic ±30% envelope) | DATA_MC_PROXY | 🟡 GATED | CL-013 |
| PID on beam data | deferred | BLOCKED_DATA | ⛔ BLOCKED | format/lineage gates #952/#962 |
| Stopping-depth data/MC | χ²/ndf ≈ 6.8e4 — FAIL | MC_DIAGNOSTIC | 🟠 TENSION | CL-021 |

**Read the statuses literally.** The ±30% MV0 envelope is a heuristic, **not a
confidence interval**. The data anomaly near 4% is **not** identified as C12
(CL-022). The systematic budget is incomplete (CL-026). For the publication narrative
see [`docs/PUBLICATION_NARRATIVE.md`](docs/PUBLICATION_NARRATIVE.md); for the
synthesis figures see [`reports/PROJECT_DASHBOARD.md`](reports/PROJECT_DASHBOARD.md).


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
