"""
Figure 02 — Analysis Pipeline (Chapter 3).

Core conclusion: 110 ROOT files → 640,737 selected B-stack pulses →
3 analysis branches with MC truth bridge.

Archetype: schematic-led composite.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

from ..config import PALETTE, save_pub, new_fig
from ..data import get_expt


def build() -> str:
    expt = get_expt()

    fig, ax = new_fig(13.5, 5.5)
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 7)
    ax.axis("off")

    # ── Title ─────────────────────────────────────────────────────
    ax.text(8.5, 6.7, "Analysis Pipeline: 110 ROOT files → 640,737 pulses → 3 branches",
            ha="center", fontsize=10, fontweight="bold", color=PALETTE["neutral_black"])

    # ── Stage 1: Raw Data ─────────────────────────────────────────
    FancyBboxPatch((0.8, 4.0), 3.5, 1.6, boxstyle="round,pad=0.15",
                   facecolor=PALETTE["neutral_dark"], edgecolor="none", alpha=0.85).set_zorder(1)
    ax.add_patch(FancyBboxPatch((0.8, 4.0), 3.5, 1.6, boxstyle="round,pad=0.15",
                   facecolor=PALETTE["neutral_dark"], edgecolor="none", alpha=0.85))
    ax.text(2.55, 5.1, "Raw ROOT Files", ha="center", fontsize=8,
            fontweight="bold", color="white")
    ax.text(2.55, 4.5, f"{expt.raw_files} files, ~{expt.raw_size_mb} MB\n"
            f"hrdb_run_NNNN.root", ha="center", fontsize=6.5, color="#D0D0D0")

    # ── Stage 2: Selection Gate ───────────────────────────────────
    ax.annotate("", xy=(5.5, 4.8), xytext=(4.3, 4.8),
                arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_mid"], lw=2))
    FancyBboxPatch((5.5, 4.0), 3.5, 1.6, boxstyle="round,pad=0.15",
                   facecolor=PALETTE["b4"], edgecolor="none", alpha=0.85).set_zorder(1)
    ax.add_patch(FancyBboxPatch((5.5, 4.0), 3.5, 1.6, boxstyle="round,pad=0.15",
                   facecolor=PALETTE["b4"], edgecolor="none", alpha=0.85))
    ax.text(7.25, 5.1, "Pulse Table (S00)", ha="center", fontsize=8,
            fontweight="bold", color="white")
    ax.text(7.25, 4.5, f"{expt.selected_pulses:,} selected pulses\n"
            f"baseline: median(ADC[0:3])\nA > 1000 ADC threshold",
            ha="center", fontsize=6.5, color="#E0E0E0")

    # ── Stage 3: Analysis Branches ────────────────────────────────
    branches = [
        (2.0, 1.2, 2.2, 0.9, PALETTE["fail_red"], "Timing\nCFD20 → Timewalk → σ₆₈"),
        (5.0, 1.2, 2.2, 0.9, PALETTE["deuteron"], "Pile-up\nLive-time → R → Excess"),
        (8.0, 1.2, 2.2, 0.9, PALETTE["ml"], "PID\nΔE-E → HGB → AUC=0.986"),
    ]
    for x, y, w, h, color, label in branches:
        FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                       facecolor=color, edgecolor=PALETTE["neutral_dark"],
                       lw=1, alpha=0.8).set_zorder(1)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                       facecolor=color, edgecolor=PALETTE["neutral_dark"],
                       lw=1, alpha=0.8))
        ax.text(x + w/2, y + h/2, label, ha="center", va="center",
                fontsize=6.5, color="white", fontweight="bold")

    # Branch arrows
    for xc in [3.1, 6.1, 9.1]:
        ax.annotate("", xy=(xc, 2.1), xytext=(xc, 3.9),
                    arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_mid"], lw=1.2))

    # ── Main pipeline arrow ───────────────────────────────────────
    ax.annotate("", xy=(10.2, 4.8), xytext=(9.0, 4.8),
                arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_mid"], lw=2))

    # ── Stage 4: Main results ─────────────────────────────────────
    results_box = FancyBboxPatch((10.2, 3.8), 5.5, 2.6, boxstyle="round,pad=0.15",
                                 facecolor=PALETTE["bg_light"],
                                 edgecolor=PALETTE["neutral_light"], lw=1.2)
    ax.add_patch(results_box)
    ax.text(12.95, 6.1, "Key Results", ha="center", fontsize=8, fontweight="bold",
            color=PALETTE["neutral_black"])
    results = [
        "σ₆₈(B6) = 0.72 ns  |  σ₆₈(B4+B6+B8) = 0.55 ns",
        "R_max = 3.05 MHz  |  τ_eff = 124.8 ns",
        "PID AUC = 0.986  |  C12 anomaly: 0.32%",
    ]
    for i, r in enumerate(results):
        ax.text(10.6, 5.5 - i * 0.45, r, fontsize=7, color=PALETTE["neutral_dark"])

    # ── MC Validation Pipeline ────────────────────────────────────
    ax.text(1.0, 0.5, "MC Validation (MV0–MV6): GEANT4 truth bridge",
            fontsize=7.5, fontweight="bold", color=PALETTE["ml"])
    mc_items = [
        ("MV0", "Gain", "⚠️"),
        ("MV1", "PID", "✅"),
        ("MV2", "Range", "✅"),
        ("MV3", "Stop", "⛔"),
        ("MV4", "Timing", "✅/🔶"),
        ("MV5", "Pile-up", "✅"),
        ("MV6", "C12", "✅"),
    ]
    for i, (mv, topic, verdict) in enumerate(mc_items):
        x0 = 1.0 + i * 1.55
        FancyBboxPatch((x0, 0.05), 1.35, 0.55, boxstyle="round,pad=0.05",
                       facecolor=PALETTE["ml"], edgecolor="none", alpha=0.6).set_zorder(1)
        ax.add_patch(FancyBboxPatch((x0, 0.05), 1.35, 0.55, boxstyle="round,pad=0.05",
                       facecolor=PALETTE["ml"], edgecolor="none", alpha=0.6))
        ax.text(x0 + 0.675, 0.42, f"{mv}: {topic}", ha="center", fontsize=6, color="white")
        ax.text(x0 + 0.675, 0.15, verdict, ha="center", fontsize=7)

    plt.tight_layout(pad=0.8)
    name = "02_analysis_pipeline"
    save_pub(fig, name)
    return name
