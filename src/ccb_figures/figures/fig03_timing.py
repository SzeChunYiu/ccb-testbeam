"""
Figure 03 — Per-Stave Timing Resolution (Chapter 5).

Core conclusion: B6 achieves σ₆₈=0.72 ns, combined B4+B6+B8 hits 0.55 ns,
B2 excluded due to terminal deuteron topology.

Archetype: quantitative grid.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig, despine
from ..data import get_timing


def build() -> str:
    td = get_timing()

    fig, ax = new_fig(8, 4.5)
    despine(ax)

    staves = td.staves
    values = td.sigma68
    colors = [PALETTE["b2"], PALETTE["b4"], PALETTE["b6"],
              PALETTE["b8"], PALETTE["combined"]]

    x = np.arange(len(staves))
    bars = ax.bar(x, values, color=colors, edgecolor="white", linewidth=0.5,
                  width=0.65, alpha=0.9)

    # Value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.06,
                f"{val:.2f}", ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=PALETTE["neutral_dark"])

    # Unit label
    ax.text(0.99, 0.95, "ns (σ₆₈)", transform=ax.transAxes, ha="right",
            fontsize=7, color=PALETTE["neutral_mid"], fontstyle="italic")

    # B2 annotation
    ax.annotate("Excluded:\nterminal deuteron\ncovariance ~65× larger",
                xy=(0, values[0]), xytext=(0.7, values[0] + 0.6),
                fontsize=6.5, ha="center", color=PALETTE["fail_red"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["fail_red"], lw=1))

    # Combined annotation
    ax.annotate("B4+B6+B8\ncombined\nevent time",
                xy=(4, values[4]), xytext=(4.8, values[4] + 0.4),
                fontsize=6.5, ha="center", color=PALETTE["combined"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["combined"], lw=1))

    ax.set_xticks(x)
    ax.set_xticklabels(staves, fontsize=8)
    ax.set_ylabel("σ₆₈ (ns)", fontweight="bold", fontsize=8)
    ax.set_ylim(0, max(values) * 1.35)
    ax.yaxis.grid(True, alpha=0.2)

    # Title strip
    ax.set_title("Per-Stave Timing Resolution", fontweight="bold", fontsize=9, pad=12)

    plt.tight_layout(pad=0.8)
    name = "03_timing_resolution"
    save_pub(fig, name)
    return name
