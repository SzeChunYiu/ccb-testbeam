"""
Figure 16 — Leakage Controls: The Three Gates (Chapter 10).

NEW FIGURE — diagram showing the three mandatory leakage controls
and which ML claims they invalidated.

Core conclusion: Target shuffle, LORO, event-block shuffle —
most apparent ML wins fail at least one.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

from ..config import PALETTE, save_pub, new_fig


def build() -> str:
    fig, ax = new_fig(10.5, 4.8)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")

    ax.text(6, 5.7, "ML Leakage Controls: Three Mandatory Gates",
            ha="center", fontsize=10, fontweight="bold", color=PALETTE["neutral_black"])

    # Three gate cards
    gates = [
        (0.3, 2.0, 3.2, 2.8, PALETTE["b2"],
         "Gate 1\nTarget Shuffle",
         "Randomly permute labels\nacross all events",
         "Catches: self-referential\nlabels, data leakage",
         "Caught: data-only PID\n(AUC ~1.0 = self-ref.)"),
        (4.5, 2.0, 3.2, 2.8, PALETTE["b6"],
         "Gate 2\nLeave-One-Run-Out",
         "Train on runs 31–57,\ntest on runs 58–65",
         "Catches: run-specific\nsignals, calibration drift",
         "Caught: representation\nsuperiority claims"),
        (8.7, 2.0, 3.2, 2.8, PALETTE["b8"],
         "Gate 3\nEvent-Block Shuffle",
         "Shuffle in blocks\nof events",
         "Catches: within-run temporal\nleakage, waveform correlations",
         "Caught: CNN timing\nimprovements"),
    ]

    for x, y, w, h, color, title, method, catches, caught in gates:
        FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                       facecolor=PALETTE["bg_light"],
                       edgecolor=color, lw=1.5, alpha=0.95).set_zorder(0)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                       facecolor=PALETTE["bg_light"],
                       edgecolor=color, lw=1.5, alpha=0.95))
        ax.text(x + w / 2, y + h - 0.35, title, ha="center",
                fontsize=8, fontweight="bold", color=color)
        ax.text(x + w / 2, y + h - 1.0, method, ha="center",
                fontsize=6.5, color=PALETTE["neutral_dark"])
        ax.text(x + w / 2, y + h - 1.7, catches, ha="center",
                fontsize=6.5, color=PALETTE["neutral_mid"])
        # Caught box
        FancyBboxPatch((x + 0.15, y + 0.08), w - 0.3, 0.7,
                       boxstyle="round,pad=0.08",
                       facecolor=PALETTE["fail_red"], edgecolor="none",
                       alpha=0.15).set_zorder(0)
        ax.add_patch(FancyBboxPatch((x + 0.15, y + 0.08), w - 0.3, 0.7,
                       boxstyle="round,pad=0.08",
                       facecolor=PALETTE["fail_red"], edgecolor="none",
                       alpha=0.15))
        ax.text(x + w / 2, y + 0.45, caught, ha="center",
                fontsize=6, color=PALETTE["fail_red"], fontweight="bold")

    # Pass criterion
    ax.text(6, 1.1,
            "Pass criterion: beat strongest traditional baseline on ALL three controls "
            "with CI excluding zero",
            ha="center", fontsize=7, fontweight="bold", color=PALETTE["pass_green"])

    # Arrow between gates
    for x1, x2 in [(3.5, 4.5), (7.7, 8.7)]:
        ax.annotate("", xy=(x2, 3.4), xytext=(x1, 3.4),
                    arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_light"], lw=1.5))

    name = "16_leakage_controls"
    save_pub(fig, name)
    return name
