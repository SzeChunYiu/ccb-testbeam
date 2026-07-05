"""CCB Testbeam — Publication figure modules.

Each module has a build() -> str function that generates the figure
and returns its base filename (without extension).

Figures 01–10: Redesigned existing wiki figures (improved to Nature-grade)
Figures 11–20: New figures filling chapter gaps
"""

from . import (
    fig01_setup,
    fig02_pipeline,
    fig03_timing,
    fig04_mc_vs_data,
    fig05_pca_vs_ae,
    fig06_stopping,
    fig07_pid,
    fig08_c12,
    fig09_systematics,
    fig10_ml_landscape,
    fig11_timing_chain,
    fig12_b2_covariance,
    fig13_pileup,
    fig14_pedestal,
    fig15_mc_synthesis,
    fig16_leakage_controls,
    fig17_study_coverage,
    fig18_timewalk,
    fig19_mv3_cascade,
    fig20_key_results,
)

__all__ = [
    "fig01_setup",
    "fig02_pipeline",
    "fig03_timing",
    "fig04_mc_vs_data",
    "fig05_pca_vs_ae",
    "fig06_stopping",
    "fig07_pid",
    "fig08_c12",
    "fig09_systematics",
    "fig10_ml_landscape",
    "fig11_timing_chain",
    "fig12_b2_covariance",
    "fig13_pileup",
    "fig14_pedestal",
    "fig15_mc_synthesis",
    "fig16_leakage_controls",
    "fig17_study_coverage",
    "fig18_timewalk",
    "fig19_mv3_cascade",
    "fig20_key_results",
]
