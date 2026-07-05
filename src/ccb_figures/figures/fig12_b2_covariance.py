"""
Figure 12 — B2 Covariance Problem (Chapter 5).

NEW FIGURE — visualises the 65× larger B2 pair variance vs
downstream pairs, tracing to terminal deuteron topology.

Core conclusion: B2-containing pairs have ~1042 ns² variance vs
~16 ns² for downstream pairs — B2 must be excluded.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig, despine
from ..data import get_timing


def build() -> str:
    td = get_timing()

    fig, ax = new_fig(7, 4.2)
    despine(ax)

    pairs = ["B2–B4", "B2–B6", "B2–B8",
             "B4–B6", "B4–B8", "B6–B8"]
    variances = [
        td.b2_pair_variance, td.b2_pair_variance, td.b2_pair_variance,
        td.downstream_pair_variance, td.downstream_pair_variance, td.downstream_pair_variance,
    ]
    colors = [
        PALETTE["fail_red"], PALETTE["fail_red"], PALETTE["fail_red"],
        PALETTE["pass_green"], PALETTE["pass_green"], PALETTE["pass_green"],
    ]

    x = np.arange(len(pairs))
    bars = ax.bar(x, variances, color=colors, edgecolor="white",
                  linewidth=0.3, width=0.6, alpha=0.85)

    # Annotate
    for bar, val in zip(bars, variances):
        label = f"{val:.0f} ns²" if val > 100 else f"{val:.0f}"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                label, ha="center", fontsize=7, fontweight="bold")

    # Separator
    ax.axvline(x=2.5, color=PALETTE["neutral_mid"], linestyle="--",
               linewidth=0.8, alpha=0.4)

    # Region labels
    ax.text(1, max(variances) * 0.92, "Terminal deuteron\nB2 pairs\n~65× larger",
            ha="center", fontsize=7, color=PALETTE["fail_red"], fontweight="bold")
    ax.text(4, max(variances) * 0.25, "Clean downstream\npairs\n~16 ns²",
            ha="center", fontsize=7, color=PALETTE["pass_green"], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(pairs, fontsize=7)
    ax.set_ylabel("Pairwise Timing Variance (ns²)", fontweight="bold", fontsize=7.5)
    ax.set_ylim(0, max(variances) * 1.18)
    ax.yaxis.grid(True, alpha=0.2)

    ax.set_title("B2 Covariance Anomaly: Terminal Deuteron Topology",
                 fontweight="bold", fontsize=9, pad=12)

    # Independence note
    ax.text(0.98, 0.05,
            f"Fitted pairwise covariance (B4/B6/B8): {td.pairwise_covariance:.3f} ns²\n"
            "Independence assumption validated & conservative",
            transform=ax.transAxes, ha="right", fontsize=6.5,
            color=PALETTE["neutral_mid"])

    plt.tight_layout(pad=0.8)
    name = "12_b2_covariance"
    save_pub(fig, name)
    return name
