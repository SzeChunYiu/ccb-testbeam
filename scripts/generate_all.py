#!/usr/bin/env python3
"""
CCB Test-Beam — Publication Figure Generator.

Generates all 20 publication-quality figures for the CCB Test-Beam wiki.
Nature-grade: Arial, clean spines, white background, SVG+PDF+300dpi PNG.

Usage:
    python generate_all.py           # generate all 20 figures
    python generate_all.py 01 05 10  # generate specific figures by number

Output: docs/figures/*.{png,svg,pdf}
"""

import sys
import time
from pathlib import Path

# Ensure the repo-root src/ package is importable when this script is run
# directly. NOTE: this launcher is DEPRECATED for headline/publication figures
# — use the canonical, sha256-gated registry driver instead:
#     python -m tools.figure_registry.builder --registry paper/figures.yaml --out paper/figures
# (scripts/ lives one level below the repo root, so the package dir is
# <repo>/src, i.e. parent.parent / "src" — NOT parent / "src".)
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "src"))

from ccb_figures.figures import (  # noqa: E402
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

# Ordered registry: (number, module, chapter, description)
REGISTRY: list[tuple[str, object, str, str]] = [
    ("01", fig01_setup, "Ch. 1–2", "Experimental Setup Schematic"),
    ("02", fig02_pipeline, "Ch. 3", "Analysis Pipeline"),
    ("03", fig03_timing, "Ch. 5", "Per-Stave Timing Resolution"),
    ("04", fig04_mc_vs_data, "Ch. 9", "MC vs Data: Key Comparisons"),
    ("05", fig05_pca_vs_ae, "Ch. 7", "PCA vs Autoencoder"),
    ("06", fig06_stopping, "Ch. 9", "Stopping-Depth Profile (MV3 FAIL)"),
    ("07", fig07_pid, "Ch. 9", "PID Performance (MV1)"),
    ("08", fig08_c12, "Ch. 7/9", "C12 Anomaly Discovery"),
    ("09", fig09_systematics, "Ch. 11", "Systematic Uncertainty Budget"),
    ("10", fig10_ml_landscape, "Ch. 7/10", "ML Performance Landscape"),
    ("11", fig11_timing_chain, "Ch. 5", "Timing Chain Schematic"),
    ("12", fig12_b2_covariance, "Ch. 5", "B2 Covariance Problem"),
    ("13", fig13_pileup, "Ch. 6", "Pile-up Rate Model & Excess"),
    ("14", fig14_pedestal, "Ch. 8", "Pedestal & Energy Scale"),
    ("15", fig15_mc_synthesis, "Ch. 9", "MC Validation Master Synthesis"),
    ("16", fig16_leakage_controls, "Ch. 10", "ML Leakage Controls"),
    ("17", fig17_study_coverage, "Ch. 3", "Study Coverage Map"),
    ("18", fig18_timewalk, "Ch. 5", "Analytic vs ML Timewalk"),
    ("19", fig19_mv3_cascade, "Ch. 9", "MV3 Downstream Impact Cascade"),
    ("20", fig20_key_results, "Ch. 12", "Key Results Dashboard"),
]


def main() -> int:
    # Figure selection
    if len(sys.argv) > 1:
        selected = set(sys.argv[1:])
        targets = [(n, m, c, d) for n, m, c, d in REGISTRY if n in selected]
        if not targets:
            print(f"No figures matched: {sys.argv[1:]}")
            print(f"Available: {[n for n, _, _, _ in REGISTRY]}")
            return 1
    else:
        targets = REGISTRY

    print(f"Generating {len(targets)} CCB Test-Beam publication figures...")
    print("Output: docs/figures/*.{png,svg,pdf}\n")

    ok = 0
    fail = 0
    t0 = time.monotonic()

    for num, module, chapter, description in targets:
        try:
            start = time.monotonic()
            name = module.build()
            elapsed = time.monotonic() - start
            print(f"  ✓ Fig {num:>2s}  {name:<35s}  {chapter:<8s}  {elapsed:.1f}s  {description}")
            ok += 1
        except Exception as e:
            print(f"  ✗ Fig {num:>2s}  {chapter}  {description}  —  {e}")
            fail += 1

    total = time.monotonic() - t0
    print(f"\n{'─'*70}")
    print(f"Done: {ok} figures in {total:.1f}s ({fail} failed)")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
