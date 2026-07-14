# Figures — Regeneration Guide

> **Last updated:** 2026-07-14
> **Status:** Figure regeneration pending — most figures are PNG at 150 dpi and need paper-grade upgrade.

## Quick Start

To regenerate all figures:
```bash
python scripts/regenerate_all_figures.py --config configs/figure_regeneration.yaml
```

## Per-Figure Regeneration

| Figure | Script | Output | Current status |
|---|---|---|---|
| FIG-GL-001 (S00 gate) | `scripts/s00_selector.py` | `docs/figures/s00_gate.pdf` | Needs redraw (150 dpi → vector) |
| FIG-TIM-001 (timing summary) | `scripts/mv4_timing_study.py --plot` | `docs/figures/03_timing_resolution.pdf` | Needs multi-panel rebuild |
| FIG-TIM-006 (ML sweep) | `scripts/ml_timing_benchmark.py --plot` | `docs/figures/ml_architecture_sweep.pdf` | Needs creation |
| FIG-TIM-010 (MC timing) | `scripts/mv4_timing_study.py --mc-plot` | `docs/figures/04_mc_vs_data.pdf` | Add ratio/pull panels |
| FIG-PU-003 (Rmax) | `scripts/mv5_pileup_study.py --plot` | `docs/figures/rmax_comparison.pdf` | Add tau_eff methods |
| FIG-PS-001 (PCA) | `scripts/mv6_pca_canonical_rerun.py --plot` | `docs/figures/05_pca_vs_ae.pdf` | Regenerate with canonical PCA |
| FIG-EN-001 (gain) | `scripts/mv0_calibration.py --plot` | `docs/figures/mv0_adc_vs_edep.pdf` | Add per-stave panels |
| FIG-PID-001 (PID AUC) | `scripts/mv1_pid.py --plot` | `docs/figures/07_pid_auc.pdf` | Add ROC/PR/confusion |
| FIG-AN-001 (C12) | `scripts/mv6_anomaly.py --plot` | `docs/figures/08_c12_anomaly.pdf` | Add cluster/species/veto |
| FIG-MC-001 (synthesis) | `scripts/mv9_synthesis.py --plot` | `docs/figures/mv9_synthesis.pdf` | Paper dashboard (no emoji) |
| FIG-SYS-001 (systematics) | `scripts/plot_systematics.py` | `docs/figures/09_systematic_budget.pdf` | Waterfall + correlation |

## Paper-Grade Requirements

Every thesis figure must have:
- [ ] Vector export (PDF or SVG)
- [ ] PNG at 300 dpi (draft) or 600 dpi (final)
- [ ] Source data as CSV or JSON in same directory
- [ ] Conclusion-bearing caption
- [ ] Units on all axes
- [ ] Sample size N shown
- [ ] Uncertainty (error bars / CI bands / shaded systematics)
- [ ] Colorblind-safe palette
- [ ] No decorative 3D, heavy gradients, or emoji

## Source Data Convention

For every figure `docs/figures/<name>.pdf`, store source data as:
```
docs/figures/<name>_source.csv   (tabulated values)
docs/figures/<name>_source.json  (structured metadata)
```

See `docs/figure_registry.csv` for complete inventory.
