"""
Figure 06 — Stopping-Depth Profile MV3 FAIL (Chapter 9).

Core conclusion: MC overestimates B8 penetration by factor 10×,
χ²/ndf = 68,269 — traced to missing inter-stave dead material in GEANT4.

Archetype: quantitative grid (left: bar comparison, right: ratio).
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, despine, add_verdict_stamp
from ..data import get_mc


def build() -> str:
    mc = get_mc()

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), facecolor="white")

    staves = mc.mv3_staves
    mc_frac = mc.mv3_mc_fractions
    data_frac = mc.mv3_data_fractions

    # ── Panel (a): Side-by-side bar ──────────────────────────────
    ax = axes[0]
    despine(ax)
    x = np.arange(len(staves))
    width = 0.32
    ax.bar(x - width / 2, mc_frac, width, label="MC (GEANT4)",
           color=PALETTE["mc"], edgecolor="white", linewidth=0.3, alpha=0.85)
    ax.bar(x + width / 2, data_frac, width, label="Data",
           color=PALETTE["data"], edgecolor="white", linewidth=0.3, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(staves, fontsize=8)
    ax.set_ylabel("Fraction of Pulses (%)", fontweight="bold", fontsize=7.5)
    ax.set_title("Stopping-Depth Profile", fontsize=8, fontweight="bold")
    ax.legend(fontsize=7, handlelength=1.2)
    ax.yaxis.grid(True, alpha=0.2)

    # ── Panel (b): Data/MC ratio ─────────────────────────────────
    ax2 = axes[1]
    despine(ax2)
    ratios = [d / m if m > 0 else 0 for d, m in zip(data_frac, mc_frac)]
    bar_colors = [
        PALETTE["tension_orange"] if 0.5 < r < 2 else PALETTE["fail_red"]
        for r in ratios
    ]
    ax2.bar(staves, ratios, color=bar_colors, edgecolor="white",
            linewidth=0.3, width=0.5, alpha=0.9)
    ax2.axhline(y=1.0, color=PALETTE["neutral_mid"], linestyle="--",
                linewidth=0.8, alpha=0.6)
    ax2.set_ylabel("Data / MC Ratio", fontweight="bold", fontsize=7.5)
    ax2.set_title("Data/MC Ratio", fontsize=8, fontweight="bold")
    ax2.set_ylim(0, max(ratios) * 1.35)
    ax2.yaxis.grid(True, alpha=0.2)

    # B8 failure annotation
    ax2.annotate(f"B8: {ratios[3]:.2f}×\n(MC 10× too many\nat B8)",
                 xy=(3, ratios[3]), xytext=(3.3, ratios[3] + 0.4),
                 fontsize=7, ha="center", color=PALETTE["fail_red"], fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color=PALETTE["fail_red"], lw=1.2))

    add_verdict_stamp(ax2, "FAIL")
    ax2.text(0.5, 0.88, f"χ²/ndf = {mc.mv3_chi2ndf:,.0f}",
             transform=ax2.transAxes, ha="center", fontsize=7,
             color=PALETTE["fail_red"], fontweight="bold")

    fig.suptitle("MV3: Stopping-Depth Profile — STRUCTURAL FAIL",
                 fontweight="bold", fontsize=10, y=1.02, color=PALETTE["fail_red"])

    plt.tight_layout(pad=1.5)
    name = "06_stopping_depth"
    save_pub(fig, name)
    return name
