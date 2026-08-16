# Chapter 12: Methodology Appendix — Reproducibility, Leakage Controls, and Reporting Standards
> **REVIEW_STATUS: EDITORIAL_REVIEWED** (AI role-separated nature-reviewer-style lenses; not independent human peer review). Scope: readability/structure only. Does **not** imply SOURCE_VERIFIED, EXECUTED_REPRODUCED, or CLAIM_AUTHORIZED. Open factual blockers remain tracked in GitHub issues / claim ledger. Contract: `docs/contracts/REVIEW_STATUS_TAXONOMY.json` / `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md`.


## Abstract

The CCB test-beam analysis programme enforces a set of methodological standards designed to ensure reproducibility, prevent machine learning leakage, and maintain traceability from raw data to physics claims. This appendix documents the reporting standard, the three leakage controls, the reproducibility protocol, the study registry system, and the terminology conventions used throughout the analysis.

---

## 1. Reporting Standard

### 1.1 Reproduce-first principle

Every physics claim in this analysis must be reproducible from raw data. The reproduce-first principle means that:

1. The analysis pipeline starts from the raw ROOT files (110 files, SHA256 checksums verified by Study S00), not from intermediate data products.
2. Every selection cut, calibration parameter, and analysis choice is documented in version-controlled configuration files (YAML or JSON) under `configs/`.
3. Every study produces a self-contained report directory under `reports/<study_id>/REPORT.md` that includes: the study motivation and hypothesis, the input data and selection criteria, the analysis method and code version (git commit hash), the results with statistical and systematic uncertainties, and the MC validation verdict where applicable.

### 1.2 Strong traditional baseline

Every machine learning result must be compared against a strong traditional baseline, not a degraded or naive one. The traditional baseline must be the best available physics-anchored method for the task:

- For timing: analytic timewalk correction (f(A) = A_0 + B/A), evaluated under LORO cross-validation.
- For pile-up: Poisson rate model with measured tau_eff.
- For PID: single-cut deltaE threshold and logistic regression on energy deposition features.
- For energy: PSTAR range-energy lookup table.

A machine learning method that beats a weak baseline but loses to the strong baseline is not a win. The strong baseline is the standard that any ML method must surpass to be considered for adoption.

### 1.3 Statistical rigour

All reported quantities must include uncertainty estimates:

- Statistical uncertainties: bootstrap 68% confidence intervals with N_bootstrap = 1000 resamples.
- Systematic uncertainties: itemised by source with magnitude and correlation assumptions.
- Model selection: Bayesian Information Criterion for GMM components; 5-fold cross-validation for classifier hyperparameters; LORO cross-validation for run-dependent effects.
- Significance thresholds: 95% bootstrap CI excluding zero for claiming a difference; two-sided tests unless the hypothesis is directional by physics (e.g., "ML improves timing resolution").

---

## 2. Leakage Controls

### 2.1 Target shuffle (null-hypothesis test)

The regression or classification target is randomly permuted while keeping input features fixed. The model is trained on shuffled data and evaluated on unshuffled held-out data. A model passes if its performance on shuffled data is indistinguishable from a constant baseline predictor (p > 0.05, two-sided, 100 shuffles). This detects spurious learning from input feature correlations that are independent of the target.

### 2.2 Leave-one-run-out cross-validation

The model is trained on all runs except one and evaluated on the held-out run, repeating for each run. The performance metrics are averaged over runs with the standard deviation across runs as the uncertainty. This detects run-specific learning (baseline shifts, calibration drift, pulse shape template variations).

### 2.3 Event-block shuffle

Events are grouped into blocks of B = 200 consecutive events within a run. Blocks — not individual events — are randomly assigned to training (80%) and test (20%) sets. This detects short-range temporal correlations (beam intensity drift, detector temperature variation within a run).

### 2.4 Leakage verdict taxonomy

- **Passed:** The model's performance survives all three controls with the performance change within the bootstrap uncertainty.
- **Gated:** The model passes in-fold but has not been evaluated under one or more controls. The result is reported but explicitly labelled as "not yet validated."
- **CORRECTED:** The model fails one or more controls. The apparent win is retracted. The corrected finding is published as a negative result.

---

## 3. Reproducibility Protocol

### 3.1 Data provenance

The raw data integrity is verified by SHA256 checksums recorded in Study S00:

| File | SHA256 |
|---|---|
| `CCB Data.zip` | 01365d81479efbfc6fe4f975ee460be1db554ae21891ec7fa594ed8906e009eb |
| `CCB Data/root.zip` | 19ba847cfbeb46d2944cf8d5c304afb52da6fcad991d1d402a6fd3e9a432efc1 |
| `CCB Data/sorted-b.zip` | f77835459bb1d797b8da74e6ac2fc88eab2402dd84b29965dc4f1dadcee1db94 |

The selected-pulse table is reproduced with exact fidelity (640,737 pulses, zero-delta from the original analysis note) by running `scripts/01_build_pulse_table_from_root.py`.

### 3.2 Code versioning

All analysis code is version-controlled in the repository `SzeChunYiu/ccb-testbeam` on GitHub. Each study report records the git commit hash at the time of execution. The MC validation pipeline is invoked through a unified CLI (`ccb-mc-validation`) that resolves study dependencies, manages random seeds, and writes a machine-readable manifest.

### 3.3 Configuration management

All analysis parameters (selection cuts, calibration constants, model hyperparameters) are stored in version-controlled YAML or JSON configuration files under `configs/`. No hardcoded numbers appear in analysis scripts. Each configuration file is named with its study identifier and a timestamp, e.g., `configs/mc_validation/base.yaml`.

---

## 4. Study Registry

The complete catalogue of studies is maintained in `studies/STUDIES.md`. Each study entry includes:

- **Study ID:** A unique identifier (S00-S18 for data studies, P01-P13 for pulse shape and ML studies, MV0-MV6 for MC validation).
- **Status:** Completed, in progress, gated, or CORRECTED.
- **Dependencies:** Other studies that must be completed before this study can be executed.
- **Output:** Path to the report directory under `reports/`.
- **Key findings:** One-line summary of the main result.
- **MC verdict:** PASS, TENSION, FAIL, or N/A.

The study registry is the single source of truth for the status of the analysis programme and is updated with each completed study.

---

## 5. Terminology Conventions

### 5.1 Detector elements

- **Stave:** A single scintillator bar with WLS fibre and SiPM readout. Designated by stack (A or B) and number (e.g., B2, B4).
- **Layer:** Used interchangeably with stave in the Monte Carlo context (Sci_bar_LayerID).
- **Stack:** A group of staves forming a range telescope. A-stack (4 staves, +71.5 degrees) and B-stack (8 staves, -38 degrees).

### 5.2 Waveform quantities

- **ADC sample:** A single 10 ns digitised voltage measurement. Waveforms have 18 samples indexed 0-17.
- **Baseline:** The median of ADC samples 0-3 (pre-trigger region).
- **Amplitude A:** Maximum baseline-subtracted ADC value (pulse height).
- **CFD time:** Constant-fraction discriminator time at 20% of peak amplitude.
- **sigma_68:** Half-width of the central 68% interval of a distribution. Equivalent to sigma for a Gaussian.

### 5.3 Physics quantities

- **EDep:** Energy deposited in a scintillator stave, in MeV (MC) or ADC-equivalent (data).
- **dE/dx:** Specific energy loss, in MeV/cm or MeV mm^2/g.
- **tau_eff:** Effective waveform live-time, the time for the pulse template to fall to 10% of peak.
- **R_max:** Maximum tolerable beam rate before pile-up distortions exceed threshold.
- **Birks constant k_B:** Parameter governing scintillation light yield saturation at high dE/dx.

### 5.4 Machine learning terms

- **HGB:** Histogram Gradient Boosting (scikit-learn implementation).
- **MLP:** Multi-Layer Perceptron (feedforward neural network).
- **CNN:** Convolutional Neural Network (1D convolution over waveform samples).
- **GMM:** Gaussian Mixture Model (unsupervised clustering).
- **PCA:** Principal Component Analysis (linear dimensionality reduction).
- **AE:** Autoencoder (nonlinear dimensionality reduction via neural network).
- **LORO:** Leave-One-Run-Out cross-validation.
- **BIC:** Bayesian Information Criterion (model selection).

---

## 6. Figure and Table Standards

All figures in this analysis programme adhere to the following standards:

- **Resolution:** 300 DPI PNG for publication.
- **Style:** Clean white surface, colorblind-safe categorical palette (validated for adjacent pairwise DeltaE >= 12), no chartjunk, no dark grid backgrounds.
- **Axis labels:** All axes labelled with quantity and units. Font: sans-serif, 9-11 pt.
- **Error bars:** 68% confidence intervals unless otherwise stated. Bootstrap-derived where applicable.
- **Legends:** Present for all figures with 2 or more series. Placed inside the plot area where possible to maximise data-ink ratio.
- **Colour:** Categorical palette in fixed order: blue (#2a78d6), aqua (#1baf7a), yellow (#eda100), green (#008300), violet (#4a3aa7), red (#e34948). Never recycled. Never a rainbow colormap.
- **No emoji:** Academic-grade notation only. Greek letters, mathematical symbols, and Unicode subscripts/superscripts are acceptable.

All figures are regenerated from source by `scripts/generate_publication_figures.py` and version-controlled alongside the analysis code.

## 7. Code Repository Structure

The complete analysis codebase is organised as follows:

```
ccb-testbeam/
├── WIKI.md                    # Project wiki (this document)
├── FINDINGS_SYNTHESIS.md      # Publication narrative
├── STUDY_GAPS.md              # Gap analysis and open questions
├── docs/
│   ├── academic_chapters/     # Academic-format chapter files (Ch 1-12)
│   └── figures/               # Publication-quality figures (300 DPI PNG)
├── scripts/                   # Analysis scripts (Python)
│   ├── 01_build_pulse_table_from_root.py  # ROOT -> pulse table
│   ├── mc01_trigger_split_truth.py        # MC trigger-split truth
│   ├── data01_sample_split_staves.py      # Data sample split
│   ├── compare_data_mc.py                 # Data/MC comparison
│   ├── mv1_mv2_truth_pid_energy.py        # MV1/MV2 truth PID
│   ├── mv3_stopping_depth.py              # MV3 stopping-depth
│   ├── mv4_timing_study.py                # MV4 timing
│   ├── mv5_pileup_study.py                # MV5 pile-up
│   ├── mv6_representation_study.py        # MV6 representation
│   └── generate_publication_figures.py    # Figure generation
├── src/                       # Python package source
│   └── ccb_mc_validation/     # MC validation framework
│       ├── digitizer/         # MV0 digitizer (pipeline, Birks, sampling, electronics)
│       ├── io/                # ROOT I/O (truth tree reader)
│       ├── studies/           # Per-study modules (MV1-MV6)
│       └── statistics/        # Bootstrap, KS test, confidence intervals
├── configs/                   # YAML/JSON configuration files
│   └── mc_validation/         # MC validation configurations
├── geant4/                    # GEANT4 simulation
│   ├── configs/               # Geometry and beam configuration
│   ├── macros/                # GEANT4 macro files
│   ├── jobs/                  # SLURM job scripts
│   └── data/                  # MC ROOT output (not in git)
├── reports/                   # Per-study report directories
├── studies/                   # Study registry and templates
└── tests/                     # Unit tests (pytest)
```

All paths are relative to the repository root. The canonical copy of the repository is on GitHub at `SzeChunYiu/ccb-testbeam`, with a working copy on the LUNARC cluster at `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/`.

## 8. Software Versions

The analysis was developed and executed with the following software versions:

| Package | Version | Purpose |
|---|---|---|
| Python | 3.11.14 | Core language |
| NumPy | 1.24+ | Numerical arrays |
| SciPy | 1.11+ | Statistical tests, interpolation |
| pandas | 1.5+ | Data frames, CSV I/O |
| scikit-learn | 1.3+ | ML classifiers, regressors, GMM |
| uproot | 5.0+ | ROOT file I/O |
| Matplotlib | 3.7+ | Figure generation |
| PyTorch | 2.0+ | Autoencoder, neural network models |
| GEANT4 | 11.2.2 | Monte Carlo simulation |
| ROOT | 6.32 | MC truth tree I/O |
| VGM | 5.4.0 | Virtual Geometry Model |

The conda environment `hibeam_env` at `/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/` provides the Python environment for all analysis scripts. The conda environment `nnbar_env` provides the GEANT4 compilation and execution environment. Both environments are version-locked and documented in their respective `environment.yml` files.

## 9. Continuous Integration and Testing

### 9.1 GitHub Actions workflows

The repository includes two CI/CD workflows under `.github/workflows/`:

**`mc_validation_ci.yml`** — Triggered on every push to `main` and on pull requests. This workflow: (1) checks out the repository, (2) sets up Python 3.11 with the `hibeam_env` conda environment, (3) runs `pytest tests/ -q` to execute the unit test suite, (4) runs `python scripts/mc_validation/verify_wiki_publication.py` to validate that all figures referenced in the wiki are present in `docs/figures/` and that all study references resolve to valid report directories, and (5) fails the build if any assertion fails or any figure is missing.

**`s00c-selector-count-regression.yml`** — Triggered on pushes that modify `scripts/01_build_pulse_table_from_root.py` or `configs/s00_reproduction.yaml`. This workflow: (1) downloads the S00 raw ROOT files from the LUNARC data archive (requires LUNARC SSH key as a GitHub secret), (2) runs the reconstruction script, (3) asserts that the output pulse table contains exactly 640,737 rows and that the SHA256 checksum of the output matches the golden reference recorded in Study S00. This is a regression test that prevents accidental changes to the selection pipeline from silently altering the pulse count.

### 9.2 Test suite structure

The test suite under `tests/` uses pytest with the following organisation:

- `tests/test_root_truth_records.py` — Tests for the ROOT truth tree reader (`src/ccb_mc_validation/io/root_truth.py`): verifies that the expected branches are present, that the data types match the schema, and that corrupted files raise appropriate exceptions.
- `tests/test_digitizer_pipeline.py` — Tests for the MV0 digitizer pipeline: verifies that each stage (Birks, scintillation, transport, sampling, electronics) produces output with the correct shape and physical bounds (e.g., amplitudes non-negative, time within 0-180 ns).
- `tests/test_statistics.py` — Tests for the statistical utilities: bootstrap confidence interval coverage, KS test calibration against known distributions, and BIC model selection on synthetic GMM data.
- `tests/fixtures/` — Small synthetic ROOT files and CSV tables used as test inputs.

The test coverage target is >80% for the `src/` package. Coverage is measured with `pytest-cov` and reported in the CI output.

### 9.3 Code style guide

All Python code in the repository follows these conventions:

- **Formatting:** `ruff format` with line length 100 characters.
- **Linting:** `ruff check` with the default rule set plus `flake8-bugbear` (B) and `pyupgrade` (UP) rules.
- **Type hints:** All public functions and methods must have complete type annotations using Python 3.10+ syntax (e.g., `list[dict[str, float]]` rather than `List[Dict[str, float]]`). Type checking is performed by `mypy --strict` in CI.
- **Docstrings:** NumPy docstring format (triple-quoted string with `Parameters`, `Returns`, `Raises` sections). Every public function must have a docstring describing its purpose, inputs, outputs, and side effects.
- **Imports:** Standard library first, then third-party packages, then local modules. Absolute imports preferred over relative imports for clarity.
- **Naming:** `snake_case` for functions, methods, and variables; `PascalCase` for classes; `UPPER_CASE` for module-level constants.

### 9.4 Release procedure

Releases follow semantic versioning (`MAJOR.MINOR.PATCH`):

- **MAJOR** version increment: breaking changes to the analysis pipeline that change physics results (e.g., new baseline algorithm, new selection threshold).
- **MINOR** version increment: new features or studies added without breaking existing results (e.g., new MV study, new figure).
- **PATCH** version increment: bug fixes, documentation updates, CI improvements.

Each release is tagged with `git tag -a vX.Y.Z -m "Release vX.Y.Z: summary"` and pushed to GitHub. The release notes are auto-generated from the commit messages since the previous tag using `git log --oneline vX.Y.Z-1..HEAD`.

---

## 10. Mathematical Notation

All equations across the 12 academic chapters use a consistent notation. The following table defines every symbol used:

| Symbol | Definition | Units | First Use |
|--------|-----------|-------|-----------|
| sigma_68 | Half-width of central 68% interval of a distribution | ns, MeV, ADC | Ch 1 |
| A | Pulse amplitude (maximum baseline-subtracted ADC) | ADC | Ch 1 |
| A_0 | Asymptotic CFD offset in timewalk correction | ns | Ch 1 |
| B | Timewalk amplitude coefficient | ns * ADC or ns * ADC^(1/2) | Ch 1 |
| t_CFD | Constant-fraction discriminator arrival time | ns | Ch 1 |
| t_corrected | Timewalk-corrected arrival time | ns | Ch 1 |
| tau_eff | Effective waveform live-time | ns | Ch 1 |
| tau_rise | Scintillator rise time | ns | Ch 2 |
| tau_decay | Scintillator decay time (fast component) | ns | Ch 2 |
| R_max | Maximum tolerable beam rate | MHz | Ch 1 |
| D | Beam duty factor | dimensionless | Ch 1 |
| R | Beam rate | particles/s | Ch 5 |
| mu | Mean occupancy (Poisson parameter) | dimensionless | Ch 5 |
| k_B | Birks constant | mm/MeV | Ch 2 |
| dE/dx | Specific energy loss | MeV/cm | Ch 2 |
| dL/dx | Scintillation light yield per unit path | MeV-equivalent/cm | Ch 7 |
| beta | Particle velocity in units of c | dimensionless | Ch 2 |
| gamma | Lorentz factor | dimensionless | Ch 2 |
| T_p | Proton kinetic energy | MeV | Ch 2 |
| m_p | Proton rest mass (938.272 MeV/c^2) | MeV/c^2 | Ch 2 |
| m_d | Deuteron rest mass (1875.613 MeV/c^2) | MeV/c^2 | Ch 2 |
| theta | Scattering angle | degrees or rad | Ch 2 |
| epsilon_WLS | WLS fibre collection efficiency | dimensionless | Ch 7 |
| epsilon_SiPM | SiPM photon detection efficiency | dimensionless | Ch 7 |
| G | Digitizer gain | ADC/MeV | Ch 7 |
| q_Birks | Birks quenching factor | dimensionless | Ch 7 |
| chi^2 | Chi-squared statistic | dimensionless | Ch 3 |
| ndf | Number of degrees of freedom | dimensionless | Ch 3 |
| AUC | Area under ROC curve | dimensionless | Ch 8 |
| D | KS test statistic | dimensionless | Ch 3 |
| lambda_j | PCA eigenvalue | ADC^2 | Ch 6 |
| pi_k | GMM mixture weight | dimensionless | Ch 6 |
| mu_k | GMM component mean | PCA-space units | Ch 6 |
| Sigma_k | GMM component covariance matrix | PCA-space units^2 | Ch 6 |
| gamma_ik | GMM responsibility (posterior) | dimensionless | Ch 6 |
| BIC | Bayesian Information Criterion | dimensionless | Ch 6 |
| N | Number of data points | dimensionless | Ch 6 |
| K | Number of GMM components | dimensionless | Ch 6 |
| d | Latent dimension | dimensionless | Ch 6 |
| z_i | PCA embedding vector | dimensionless | Ch 6 |
| w_i | Waveform vector (18 samples) | ADC | Ch 6 |
| w_bar | Mean waveform vector | ADC | Ch 6 |
| Sigma | Covariance matrix (18x18) | ADC^2 | Ch 6 |
| V | Eigenvector matrix | dimensionless | Ch 6 |
| Lambda | Eigenvalue diagonal matrix | ADC^2 | Ch 6 |
| T | Kinetic energy | MeV | Ch 2 |
| R | Range (CSDA) | cm | Ch 7 |
| alpha, beta | PSTAR power-law fit parameters | cm/MeV^beta, dimensionless | Ch 7 |
| sigma_noise | Electronic noise RMS | ADC | Ch 3 |
| sigma_transport | WLS fibre Gaussian time dispersion | ns | Ch 3 |

All symbols are defined on first use in their respective chapters and used consistently throughout. Greek letters are rendered in Unicode (e.g., sigma for sigma, tau for tau). Mathematical operators follow standard physics notation: mean values denoted by angle brackets or overbars, uncertainties denoted by plus/minus, and statistical estimators denoted by hats where needed.

---

## Reproducibility Checklist (Thesis Upgrade Addition)

> **Every chapter must be reproducible from a command list and artifact list.**

### Per-Chapter Artifact Requirements

| Chapter | Command artifact | Data artifact | Config artifact | Seed |
|---|---|---|---|---|
| Executive Summary | (synthesis only) | `docs/claim_ledger.csv` | — | — |
| Experimental Setup | `scripts/plot_geometry.py` | `krakow_109_8-38deg_4-71deg.root` | `configs/geometry.yaml` | — |
| Data Pipeline | `scripts/01_build_pulse_table_from_root.py` | Raw ROOT files | `configs/s00_reproduction.yaml` | 20260601 |
| Timing | `scripts/mv4_timing_study.py` | Pulse table | `configs/mv4_timing.yaml` | 20260601 |
| Pile-up | `scripts/mv5_pileup_study.py` | Pulse table | `configs/mv5_pileup.yaml` | 20260601 |
| Pulse Shape ML | `scripts/mv6_pca_canonical_rerun.py` | Pulse table | `configs/mv6_pca.yaml` | 20260601 |
| Energy Calibration | `scripts/mv0_calibration.py` | MC digitized waveforms | `configs/mv0_calibration.yaml` | 20260601 |
| PID | `scripts/mv1_pid.py` | MC digitized waveforms | `configs/mv1_pid.yaml` | 20260601 |
| Anomaly ID | `scripts/mv6_anomaly.py` | Pulse table | `configs/mv6_anomaly.yaml` | 20260601 |
| MC Validation | (synthesis only) | MV0–MV6 results | — | — |
| Open Questions | (synthesis only) | STUDY_GAPS.md | — | — |
| Methodology | (this appendix) | CLAIM_CHECKLIST_INTEGRATION.md | — | — |

---

## Methodology Rules Enforcement (Thesis Upgrade Addition)

### Build/Lint Check Summary

| Check | Script | CI status | Severity |
|---|---|---|---|
| Superseded-value scan | `scripts/audit_claim_superseded.py` | Required | **Blocking** |
| Claim ledger completeness | `scripts/check_claim_ledger_complete.py` | Required | **Blocking** |
| Broken link checker | `scripts/broken_link_checker.py` | Required | High |
| Figure source data checker | `scripts/check_figure_source_data.py` | Required | High |
| ML claim leakage control checker | `scripts/check_ml_leakage_controls.py` | Required | High |
| MC truth-type checker | `scripts/check_mc_truth_type.py` | Required | Medium |
| Plot style checker | `scripts/check_plot_style.py` | Recommended | Medium |
| Table uncertainty checker | `scripts/check_table_uncertainty.py` | Recommended | Medium |

### CI Pipeline

```yaml
name: Thesis QA
on: [push, pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python scripts/audit_claim_superseded.py
      - run: python scripts/broken_link_checker.py
```

---

## Chapter Verdict — Established / Open / Next

### Established
✅ Twelve academic chapters follow the thesis architecture standard.
✅ Claim ledger and figure registry provide cross-chapter auditability.
✅ Build/lint checks are specified for automated enforcement.

### Open
⚠️ CI pipeline not yet operational on GitHub Actions.
⚠️ Some lint scripts are specified but not yet implemented.
⚠️ Plot regeneration (vector + source data) not yet completed.

### Next Studies
🔬 Implement remaining CI/lint scripts.
🔬 Enable GitHub Actions CI pipeline with all 8 checks.
🔬 Regenerate all figures to paper-grade standards (PDF/SVG vector + 300+ dpi PNG).
🔬 Build figures/README.md with per-figure regeneration instructions.
