"""
Figure 11 — Timing Chain Schematic (Chapter 5).

NEW FIGURE — replaces the text description of the 3-step chain
with a clear visual schematic.

Core conclusion: CFD20 seed → template phase refinement →
amplitude timewalk correction = σ₆₈ 0.72 ns (B6).
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

from ..config import PALETTE, save_pub, new_fig


def build() -> str:
    fig, ax = new_fig(12, 4.5)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 6)
    ax.axis("off")

    ax.text(8, 5.7, "Timing Extraction Chain: CFD20 → Template Phase → Timewalk Correction",
            ha="center", fontsize=10, fontweight="bold", color=PALETTE["neutral_black"])

    # Three steps
    steps = [
        (1.5, 2.5, 3.2, 2.2, PALETTE["b4"],
         "Step 1\nCFD20 Seed",
         "Constant-fraction\ndiscriminator at 20%\nof peak amplitude\n\nLinear interpolation\nbetween straddling\nsamples",
         "→ t_CFD"),
        (6.5, 2.5, 3.2, 2.2, PALETTE["b6"],
         "Step 2\nTemplate Phase",
         "Amplitude-adaptive\ntemplate per stave\n& log-amplitude bin\n\nMinimises SSR\nquality: q_template",
         "→ t_CFD + φ"),
        (11.5, 2.5, 3.2, 2.2, PALETTE["b8"],
         "Step 3\nTimewalk Correction",
         "t_corrected = t_CFD\n− B/amplitude\n\nB fitted per stave\nB2-blind calibration\n(terminal deuteron)",
         "→ σ₆₈ = 0.72 ns"),
    ]

    for x, y, w, h, color, title, body, result in steps:
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                             facecolor=color, edgecolor="white", lw=1, alpha=0.9)
        ax.add_patch(box)
        ax.text(x + w / 2, y + h - 0.35, title, ha="center", fontsize=8,
                fontweight="bold", color="white")
        ax.text(x + w / 2, y + h / 2 - 0.1, body, ha="center", fontsize=6.5,
                color="white", alpha=0.95)
        ax.text(x + w / 2, y + 0.15, result, ha="center", fontsize=6,
                color="#FFD700", fontweight="bold")

    # Arrows between steps
    for x1, x2 in [(4.7, 6.5), (9.7, 11.5)]:
        ax.annotate("", xy=(x2, 3.6), xytext=(x1, 3.6),
                    arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_mid"], lw=2))

    # Waveform mini-example (bottom)
    ax.text(8, 1.2, "18-sample waveform → 3 timing estimators → single corrected time",
            ha="center", fontsize=7, color=PALETTE["neutral_mid"], fontstyle="italic")

    # Resolution annotation
    ax.text(14.7, 5.3, "Best: B6\nσ₆₈ = 0.72 ns\nCombined:\n0.55 ns",
            fontsize=7, color=PALETTE["b6"], fontweight="bold", ha="right", va="top")

    name = "11_timing_chain"
    save_pub(fig, name)
    return name
