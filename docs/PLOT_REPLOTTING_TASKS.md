# Plot Replotting Tasks — Thesis-Grade Upgrade

> **Source:** Plot scientific audit (2026-07-14)
> **Grades:** A (thesis-ready), B (minor fixes), C (needs rebuild), D (inadequate), F (unsafe)

## Critical Priority (Blocking)

| ID | Figure | Grade | Action |
|---|---|---|---|
| 10 | Systematic uncertainty budget | **F** | Replace entirely. Current plot conflates input gain uncertainty with propagated deuteron-fraction uncertainty. Build two-level plot: input systematics + propagated output waterfall. |
| 08 | C12 anomaly waveform | **D** | Replace mocked waveform with real MV6 class-median ± IQR waveforms. Add species composition, peak-sample histogram, veto efficiency panel. |
| 07 | PID AUC/purity | **D+** | Replace grouped bars with: ROC curve + CI bands, PR/purity-efficiency curve, confusion matrix, SHAP/feature sensitivity, MV3 stress test (B2/B4/B6 only vs all layers). |
| 05 | ML performance landscape | **D** | Replace unreadable infographic with evidence matrix heatmap (method × task × metric). Show baseline, ML, delta, CI, leakage status. |
| 04 | MC validation comparisons | **C−** | Split timing and pile-up panels. Add pull plots, ratio panels, dependency caveats. |
| 03 | Per-stave timing resolution | **C−** | Split per-stave and combined estimators. Add CI bands, covariance caveat annotation. |

## High Priority

| ID | Figure | Grade | Action |
|---|---|---|---|
| 06 | PCA vs AE compression | **C** | Add PCA scree plot with uncertainty, reconstruction examples, corrected variance values. |
| 01 | Experimental setup | **C** | Replace cartoon schematic with vector detector geometry diagram. Add material budget overlay. |
| 02 | Analysis pipeline | **C** | Replace simple flowchart with reproducibility/truth-provenance graph. |
| 11 | WLS/SiPM plots | **D** | Replace analytic curves with datasheet/measured curves. Add overvoltage and temperature caveats. |

## Medium Priority

| ID | Figure | Grade | Action |
|---|---|---|---|
| 12 | Beamline ASCII | **D+** | Replace with formal vector diagram. |
| 13 | Pipeline ASCII | **D+** | Replace with formal vector diagram. |

## Paper-Grade Requirements (All Figures)

- [ ] Vector export (PDF/SVG)
- [ ] PNG at 300 dpi (draft) / 600 dpi (final)
- [ ] Source CSV/JSON data
- [ ] Conclusion-bearing caption
- [ ] Units on all axes
- [ ] N and selection gate shown
- [ ] Uncertainty (error bars / CI bands / shaded systematics)
- [ ] Colorblind-safe palette
- [ ] No mock/fake data presented as evidence
- [ ] No emoji in plot areas
- [ ] Figure registry entry updated
