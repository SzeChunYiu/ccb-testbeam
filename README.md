# CCB Test-Beam Analysis

> **Analysis of the CCB test-beam data: 190 MeV protons on CD₂ target, measured by HRD scintillator range stacks.**
>
> Physics goals: **same-particle timing resolution** and **pile-up characterization**.

> [!WARNING]
> **Repository-wide scientific revalidation is in progress under #1594.** Historical `PASS`/`VALIDATED` labels, attractive plots, successful reproduction, and Monte-Carlo closure are not sufficient by themselves to authorize detector-performance claims. Read [`docs/SCIENTIFIC_AUDIT_STATUS.md`](docs/SCIENTIFIC_AUDIT_STATUS.md) before using any result. Every consequential number, equation, method, figure, and public claim is being re-audited from physics and provenance first principles.

[![Studies](https://img.shields.io/badge/studies-~230-blue)](studies/STUDIES.md)
[![MC Validations](https://img.shields.io/badge/MC%20validations-6-green)](studies/MC_VALIDATION_PROGRAM.md)
[![Python](https://img.shields.io/badge/python->=3.11-3776AB)](pyproject.toml)
[![Status](https://img.shields.io/badge/status-global%20revalidation-orange)](docs/SCIENTIFIC_AUDIT_STATUS.md)

---

## Quick Start

| You want to... | Read this |
|---|---|
| **Know what can currently be trusted** | → **[`docs/SCIENTIFIC_AUDIT_STATUS.md`](docs/SCIENTIFIC_AUDIT_STATUS.md)** — global revalidation rules and blockers |
| **Follow the master scientific audit** | → **GitHub issue #1594** + `chatgpt_todo/REDO_QUEUE.csv` |
| **Understand the whole project** | → [`WIKI.md`](WIKI.md) — comprehensive but currently under line-by-line reconciliation (#1598) |
| **Canonical one-screen dashboard** | → [`reports/PROJECT_DASHBOARD.md`](reports/PROJECT_DASHBOARD.md) — claim states; still subject to global revalidation |
| **See what's missing / what to do next** | → [`STUDY_GAPS.md`](STUDY_GAPS.md) and `chatgpt_todo/REDO_QUEUE.csv` |
| **Browse all ~230 studies** | → [`studies/STUDIES.md`](studies/STUDIES.md) |
| **Understand methodology rules** | → [`docs/REPORT_STANDARD.md`](docs/REPORT_STANDARD.md) and `chatgpt_todo/SCIENTIFIC_REVIEW_PROTOCOL.md` |

## Scientific status

**Do not interpret the table below as a list of measured detector properties.** Evidence classes are part of the result. `MC_METHOD_CLOSURE` and `SIMULATION_RESULT` describe simulation-domain performance; `GATED`/`BLOCKED`/`FLAWED`/`SUPERSEDED` do not authorize current detector claims.

| Claim | Value | Evidence class | Current interpretation |
|---|---|---|---|
| Selected B-stack pulses (S00 gate) | **640,737** | DATA_MEASUREMENT | **GATED** — independent raw-data contract reconstruction is a P0 task (#1603) |
| Combined timing σ₆₈ (4-sensor) | **0.089 ns** | MC_METHOD_CLOSURE | simulation-method closure only; **not beam detector timing** |
| PID p-vs-d AUC | **0.898** | SIMULATION_RESULT | realistic MC-chain result; data transfer under #1606/#1608 |
| ADC digitizer gain | **119.17 ADC/MeV** | SIMULATION_RESULT | simulation calibration, not a measured detector calibration |
| Birks kB | **0.0156 cm/MeV** | SIMULATION_RESULT | simulation/model fit pending reference and nuisance audit |
| Digitizer-domain rate criterion | **0.605 MHz** | SIMULATION_RESULT | simulation-domain criterion; canonical detector `Rmax` remains unresolved |
| Detector timing resolution (data) | withheld | BLOCKED/GATED | rebuild from validated waveform primitives under #1603/#1605 |
| Canonical detector pile-up rate limit | withheld | BLOCKED | quantity definition and quality criterion under #1607 |
| Legacy Rmax = 3.044 MHz | — | SUPERSEDED | historical only; do not use |
| MV0 gain proxy | **92 ADC/MeV with 28 ADC/MeV heuristic envelope** | DATA_MC_PROXY | GATED; envelope is not a confidence interval |
| Truth-level PID ceiling | **0.986** | TRUTH_LEVEL_MC_ONLY | not beam-data PID performance |
| C12 anomaly identity | — | TRUTH_LEVEL_MC_ONLY | MC species composition cannot identify the beam-data anomaly |
| Legacy stopping-depth χ²/ndf | ≈ **6.8×10⁴** | FLAWED/TENSION diagnostic | invalid as closure until geometry/selection/generator/systematics are rebuilt |

The exhaustive numerical/equation/figure census is being built under #1610. Where historical prose conflicts with the audit ledgers or canonical evidence state, **the audited evidence state wins**.

## Current repair order

1. **#1603:** raw ROOT identity, waveform polarity/pedestal/amplitude semantics, channel map, event keys, trigger and selection anchors.
2. **#1604:** detector/electronics/SiPM/WLS calibration and nuisance covariance.
3. **#1608:** geometry, generator, Geant4/digitizer assumptions and data/MC transfer.
4. **#1609:** statistical inference, covariance, leakage, multiplicity and untouched validation.
5. **#1605–#1607:** rerun timing; energy/stopping/ΔE–E/PID/anomaly; pile-up/rate/saturation from validated primitives.
6. **#1597/#1601/#1613:** regenerate scientific figures from audited machine-readable evidence.
7. **#1598/#1611:** reconcile WIKI/README/dashboard/publication material and enforce the publication evidence gate.

An upstream failure automatically reopens every dependent study, figure, and public statement.

## Repository Layout

```
ccb-testbeam/
├── docs/SCIENTIFIC_AUDIT_STATUS.md ← read first during global revalidation
├── WIKI.md              ← illustrated wiki; currently under #1598 reconciliation
├── STUDY_GAPS.md         ← gap analysis
├── PROJECT_REPORT.md     ← historical/project status; audit before publication use
├── FINDINGS_SYNTHESIS.md ← historical synthesis; supersession warnings apply
├── README.md             ← you are here
├── DATA.md               ← data locations and integrity
├── chatgpt_todo/         ← machine-readable audit ledgers and redo queue
├── docs/                 ← methodology, references, figures, contracts
├── studies/              ← research programme
├── reports/              ← per-study reports and generated evidence
├── scripts/              ← analysis code
├── configs/              ← run configs and analysis choices
├── geant4/               ← Geant4 simulation code and jobs
└── tests/                ← regression and audit tests
```

## Getting Started (Development)

```bash
git clone https://github.com/SzeChunYiu/ccb-testbeam.git
cd ccb-testbeam
pip install -e ".[dev]"
pytest tests/ -q
```

Do **not** use an old expected headline value as a rerun acceptance target. Reruns must validate inputs/definitions first and report the result they actually obtain.

## Data

Raw data lives outside git and multiple repository paths/lineages have historically been referenced. Exact raw-file inventory, hashes, schema, archive identity, event counts and lineage are therefore part of P0 audit #1603; do not infer authorization merely from a path appearing in prose.

## Status

**Global scientific revalidation in progress; not peer-reviewed.** Scientific closure requires the evidence and adversarial-review gates in [`docs/SCIENTIFIC_AUDIT_STATUS.md`](docs/SCIENTIFIC_AUDIT_STATUS.md) and `chatgpt_todo/SCIENTIFIC_REVIEW_PROTOCOL.md`.