"""
Figure 15 — MC Validation Master Synthesis (Chapter 9).

NEW FIGURE — single-panel master overview of all 6 MV studies
with verdicts, pull values, MV3 sensitivity, and status.

Core conclusion: MV1/MV2/MV5/MV6 PASS, MV0 PRELIMINARY,
MV3 STRUCTURAL FAIL, MV4 PASS/TENSION.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig , despine
from ..data import get_mc


def build() -> str:
    mc = get_mc()

    fig, ax = new_fig(11, 4.5)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 8)
    ax.axis("off")

    ax.text(5.5, 7.7, "MC Validation Master Synthesis (MV0–MV6)",
            ha="center", fontsize=11, fontweight="bold", color=PALETTE["neutral_black"])

    # Study cards
    studies = [
        (0.5, 5.0, "MV0", "Digitizer\nGain", "92 ± 28 ADC/MeV",
         "PRELIMINARY", "30% systematic", "KS=0.158",
         PALETTE["preliminary_grey"]),
        (2.5, 5.0, "MV1", "PID", "AUC = 0.986",
         "PASS", "Data within 0.5%", "of MC ceiling",
         PALETTE["pass_green"]),
        (4.5, 5.0, "MV2", "Range-\nEnergy", "p: 23, d: 89 MeV",
         "PASS", "d in layers 0-1", "p in layers 4-7",
         PALETTE["pass_green"]),
        (6.5, 5.0, "MV3", "Stopping\nDepth", "χ²/ndf=68,269",
         "FAIL", "B8: 10× mismatch", "Missing dead material",
         PALETTE["fail_red"]),
        (8.5, 5.0, "MV4", "Timing", "pull=−1.05σ/+2.68σ",
         "TENSION", "Raw PASS", "Corrected = digitizer",
         PALETTE["tension_orange"]),
        (0.5, 1.5, "MV5", "Pile-up", "R_max=3.044 MHz",
         "PASS", "0.2% agreement", "Self-consistency",
         PALETTE["pass_green"]),
        (3.0, 1.5, "MV6", "C12\nAnomaly", "0.32% C12",
         "PASS", "55% of early-peak", "MC-calibrated",
         PALETTE["pass_green"]),
        (5.5, 1.5, "MV3b", "Material\nBudget", "~0.1-0.5 g/cm²",
         "CORRECTED", "FR-4/PCB/polymer", "Not Al (errata)",
         PALETTE["neutral_mid"]),
        (8.0, 1.5, "MV4b", "Physical\nTimewalk", "B = τ·V_th > 0",
         "RESOLVED", "1/A form fixes it", "Needs re-run",
         PALETTE["tension_orange"]),
    ]

    for x, y, mv, topic, key, verdict, line1, line2, color in studies:
        # Card background
        ax.add_patch(plt.Rectangle((x, y), 2.1, 2.5, facecolor=PALETTE["bg_light"],
                                   edgecolor=PALETTE["neutral_light"], linewidth=0.8,
                                   zorder=0))
        # Verdict stripe
        ax.add_patch(plt.Rectangle((x, y + 2.15), 2.1, 0.35, facecolor=color,
                                   edgecolor="none", alpha=0.85, zorder=1))
        ax.text(x + 1.05, y + 2.33, verdict, ha="center", fontsize=7,
                fontweight="bold", color="white", zorder=2)

        # Content
        ax.text(x + 1.05, y + 1.7, f"{mv}: {topic}", ha="center", fontsize=7.5,
                fontweight="bold", color=PALETTE["neutral_black"])
        ax.text(x + 1.05, y + 1.1, key, ha="center", fontsize=8,
                fontweight="bold", color=PALETTE["b2"])
        ax.text(x + 1.05, y + 0.55, f"{line1}  ·  {line2}",
                ha="center", fontsize=5.5, color=PALETTE["neutral_mid"])

    # Legend
    ax.text(5.5, 0.3,
            "MV3 (FAIL) = highest priority  |  MV0 (PRELIMINARY) = needs forced-trigger pedestal  |  "
            "MV4 (TENSION) = 1/A fix applied, needs re-run",
            ha="center", fontsize=6, color=PALETTE["neutral_mid"])

    name = "15_mc_synthesis"
    save_pub(fig, name)
    return name
