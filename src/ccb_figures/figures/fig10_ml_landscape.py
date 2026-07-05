"""
Figure 10 — ML Performance Landscape (Chapters 7, 10).

Core conclusion: ML wins where truth is independent and information is
in waveform shape; ties/loses where analytic models are already optimal;
most ML "wins" fail leakage controls.

Archetype: asymmetric mixed-modality figure.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig
from ..data import get_ml_landscape


def build() -> str:
    ml = get_ml_landscape()

    fig, ax = new_fig(9.5, 5.5)
    ax.set_xlim(0, 1)
    ax.set_ylim(-1, len(ml.domains))
    ax.axis("off")

    # Title
    ax.text(0.5, len(ml.domains) + 0.3,
            "ML Performance Landscape: Where ML Wins, Ties, or Loses",
            ha="center", fontsize=10, fontweight="bold",
            color=PALETTE["neutral_black"])

    # Category labels (left)
    cats = [
        (len(ml.domains) - 0.5, len(ml.domains), "✅ ML Wins",
         "Truth independent of input,\ninformation in waveform shape",
         PALETTE["pass_green"]),
        (4.5, len(ml.domains) - 1, "Tie/Loss",
         "Analytic physics model\nalready near-optimal",
         PALETTE["traditional"]),
        (1.5, 3, "❌ ML Loses / Leakage",
         "Self-referential labels or\nfailed cross-validation",
         PALETTE["fail_red"]),
    ]
    for mid, y, title, sub, color in cats:
        ax.text(0.02, mid, title, fontsize=7.5, fontweight="bold",
                color=color, va="center")
        ax.text(0.02, mid - 0.35, sub, fontsize=6, color=PALETTE["neutral_mid"], va="top")

    # Row bars
    y_positions = list(range(len(ml.domains)))
    for i, (domain, verdict, detail, color) in enumerate(
        zip(ml.domains, ml.verdicts, ml.details, ml.colors)
    ):
        y = len(ml.domains) - 1 - i
        # Background stripe
        if i % 2 == 0:
            ax.axhspan(y - 0.4, y + 0.4, facecolor=PALETTE["bg_light"], alpha=0.5, zorder=0)
        # Color block
        ax.barh(y, 0.82, left=0.15, height=0.65, color=color,
                edgecolor="white", linewidth=0.3, alpha=0.85, zorder=1)
        # Domain name
        ax.text(0.16, y, domain.replace("\n", " "), fontsize=7,
                fontweight="bold", color="white", va="center", zorder=2)
        # Verdict + detail
        ax.text(0.56, y + 0.15, f"{verdict}  —  {detail}",
                fontsize=7, color=PALETTE["neutral_dark"], va="center")
        # Separator line
        ax.text(0.555, y - 0.15, "─" * 55, fontsize=3,
                color=PALETTE["neutral_light"], va="center")

    # Bottom legend
    legend_y = -0.5
    legend_items = [
        (PALETTE["pass_green"], "ML Wins — independent truth, shape signal"),
        (PALETTE["tension_orange"], "ML Wins partially — higher failure rate"),
        (PALETTE["traditional"], "Tie/Loss — analytic already optimal"),
        (PALETTE["fail_red"], "Leakage / CORRECTED"),
    ]
    for i, (color, label) in enumerate(legend_items):
        x = 0.15 + i * 2.1
        ax.add_patch(plt.Rectangle((x, legend_y), 0.15, 0.15,
                                   facecolor=color, edgecolor="none", alpha=0.85))
        ax.text(x + 0.22, legend_y + 0.07, label, fontsize=6.5,
                color=PALETTE["neutral_dark"], va="center")

    name = "10_ml_landscape"
    save_pub(fig, name)
    return name
