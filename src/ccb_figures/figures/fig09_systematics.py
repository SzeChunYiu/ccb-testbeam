"""
Figure 09 — Systematic Uncertainty Budget (Chapter 11).

Core conclusion: Gain ±30% dominates, quadrature total ~12% on
deuteron fraction; MV3 geometry failure is largest unresolved item.

Archetype: quantitative grid (horizontal bar).
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig, despine
from ..data import get_systematic


def build() -> str:
    sd = get_systematic()

    fig, ax = new_fig(8.5, 4)
    despine(ax)

    sources = sd.sources
    magnitudes = sd.magnitudes_pct
    colors = [
        PALETTE["fail_red"],
        PALETTE["tension_orange"],
        PALETTE["deuteron"],
        PALETTE["pass_green"],
        PALETTE["accent_teal"],
    ]

    y_pos = range(len(sources))
    bars = ax.barh(y_pos, magnitudes, color=colors, edgecolor="white",
                   linewidth=0.3, height=0.6, alpha=0.85)

    for bar, mag in zip(bars, magnitudes):
        if mag > 0.5:
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{mag:.1f}%", va="center", fontsize=8, fontweight="bold",
                    color=PALETTE["neutral_dark"])
        else:
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"{mag:.1f}%", va="center", fontsize=7, color=PALETTE["neutral_mid"])

    ax.set_yticks(y_pos)
    ax.set_yticklabels(sources, fontsize=6.5)

    ax.set_xlabel("Systematic on Deuteron Fraction (%)", fontweight="bold", fontsize=7.5)
    ax.set_xlim(0, max(magnitudes) * 1.6)
    ax.xaxis.grid(True, alpha=0.2)
    ax.invert_yaxis()

    # Quadrature sum
    ax.text(0.97, 0.08,
            f"Quadrature total: ~{sd.quadrature_total:.0f}%\n"
            f"Dominant: MV0 gain ({sd.gain_raw_pct:.0f}% raw, "
            f"<{sd.magnitudes_pct[0]:.0f}% on d-fraction)\n"
            f"Gated: MV3 geometry fix (HIGH priority)",
            transform=ax.transAxes, ha="right", fontsize=6.5,
            color=PALETTE["neutral_dark"],
            bbox=dict(boxstyle="round,pad=0.4", facecolor=PALETTE["bg_light"],
                      edgecolor=PALETTE["neutral_light"], linewidth=0.6))

    ax.set_title("Systematic Uncertainty Budget", fontweight="bold", fontsize=9, pad=12)

    plt.tight_layout(pad=0.8)
    name = "09_systematic_budget"
    save_pub(fig, name)
    return name
