# Figure Gallery — CCB Test-Beam Analysis

All publication figures are in the `reports/` directory. Use these for paper drafts.
Format: PNG, 150 dpi (for embedded figures).

---

## MV0 — Digitizer Gain Calibration

Directory: `reports/mv0_calibration_1782677847/`

| Figure | Description |
|---|---|
| `mv0_adc_vs_edep_scatter.png` | Scatter plot: data net_adc vs MC edep (B2 protons); gain slope = 92 ADC/MeV shown |
| `mv0_adc_spectrum_data.png` | Data B2 net_adc distribution; median = 1781 ADC marked |
| `mv0_edep_spectrum_mc.png` | MC B2 edep distribution; median × peak_frac = 1781 ADC |
| `mv0_gain_calibration_summary.png` | Combined: data/MC overlay after gain application |

**Key number**: gain = 92 ± 28 ADC/MeV (v2 corrected; v1 was 246 ADC/MeV — wrong ADC convention)

---

## MV3 — Stopping-Depth Profile (FAIL)

Directory: `reports/mv3_stopping_v3_1782679272/`

| Figure | Description |
|---|---|
| `mv3_stop_frac.png` | Bar chart: MC vs data stave hit fractions (B2/B4/B6/B8); shows 10× B8 discrepancy |

**Key number**: χ²/ndf = 68,269 (catastrophic FAIL); B8 MC=22.3% vs data=2.3%

---

## MV4 — Timing Resolution

Directory: `reports/mv4_timing_1782678162/`

| Figure | Description |
|---|---|
| `mv4_sigma68_comparison.png` | σ₆₈ MC vs data (raw and corrected) |
| `mv4_timing_distribution.png` | Timing residual distribution overlays |
| `mv4_timewalk_correction.png` | Timewalk ΔT vs ADC amplitude |
| `mv4_sigma68_vs_amplitude.png` | Amplitude-dependent σ₆₈ |
| `mv4_pull_summary.png` | Pull values (raw PASS, corrected TENSION) |

**Key number**: σ₆₈_raw = 1.744 ns (PASS pull=−1.05); corrected pull=+2.68 (TENSION — MV4b shows model artefact)

---

## MV4b — Physical Timewalk Model

Directory: `reports/mv4b_timewalk_model/`

| Figure | Description |
|---|---|
| `mv4b_timewalk_model.png` | Physical (1/A) vs toy (1/√A) timewalk curves — shows toy B<0 is unphysical |
| `mv4b_timing_residuals.png` | σ₆₈ distributions: raw / physical 1/A / toy 1/√A corrections |
| `mv4b_sigma68_vs_adc.png` | Amplitude-dependent σ₆₈ for each correction model |

**Key finding**: Toy timewalk with B<0 over-corrects; physical 1/A form resolves tension

---

## MV5 — Pile-Up Rate

Directory: `reports/mv5_pileup_1782678353/`

| Figure | Description |
|---|---|
| `mv5_rmax_comparison.png` | R_max MC vs data comparison (3.044 vs 3.05 MHz) |
| `mv5_deadtime_model.png` | Dead-time fraction vs trigger rate |

**Key number**: R_max = 3.044 MHz (0.2% agreement with data) — PASS

---

## MV6 — Anomaly Species Identification

Directory: `reports/mv6_representation_1782678362/`

| Figure | Description |
|---|---|
| `mv6_pca_clusters.png` | PCA scatter with GMM clusters coloured; Cluster 2 = C12 anomaly |

**Key number**: 0.32% anomaly fraction; C12 recoils = 55% of anomaly class

---

## MV3b — Upstream Material Budget

Directory: `reports/mv3b_material_budget/`

| Figure | Description |
|---|---|
| `mv3b_range_curve.png` | Proton CSDA range vs energy in BC-408; stave positions marked |
| `mv3b_material_scan.png` | B8 fraction vs upstream material; required=~8 g/cm²; known components |

**Key finding**: ~8 g/cm² additional upstream material needed; inter-stave dead material is dominant

---

## MC Synthesis

Directory: `reports/mc_validation_synthesis/`

| Figure | Description |
|---|---|
| `mv9_master_synthesis.png` | Master overview: all 6 MV verdicts, pull values, status |

---

## Data Analysis Studies (S* / P*)

See `reports/SUMMARY.md` for the full list of ~230 data-driven studies.
Key figures are in study-specific subdirectories under `reports/`.

---

## Figure Production

All figures are reproducible by running the corresponding script:

| Study | Script | Output dir |
|---|---|---|
| MV0 | `scripts/mv0_calibrate_from_data.py` | `reports/mv0_calibration_*/` |
| MV3 | `scripts/mv3_stopping_v3.py` | `reports/mv3_stopping_v3_*/` |
| MV4 | `scripts/mv4_timing_study.py` | `reports/mv4_timing_*/` |
| MV4b | `scripts/mv4b_timewalk_model.py` | `reports/mv4b_timewalk_model/` |
| MV5 | `scripts/mv5_pileup_study.py` | `reports/mv5_pileup_*/` |
| MV6 | `scripts/mv6_representation_study.py` | `reports/mv6_representation_*/` |
| MV3b | `scripts/mv3b_material_budget.py` | `reports/mv3b_material_budget/` |

Python environment: `/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3`

SLURM jobs for compute-intensive runs: see `geant4/jobs/mv*.sbatch`

---

*Figure gallery | Date: 2026-06-28 | CCB test-beam project*
