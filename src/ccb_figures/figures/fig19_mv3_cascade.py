"""
Figure 19 — MV3 Downstream Impact: The Problem Cascade (Chapter 9, 12).

NEW FIGURE — shows how MV3 stopping-depth failure cascades through
every other MV study, quantifying sensitivity where known.

Core conclusion: MV3 geometry failure affects PID, range-energy
(qualitative only), pile-up multiplicity (possibly fortuitous),
timing (assumed insensitive — not verified).
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

from ..config import PALETTE, save_pub, new_fig


def build() -> str:
    fig, ax = new_fig(11, 5.5)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7)
    ax.axis("off")

    ax.text(6.5, 6.7, "MV3 Downstream Impact: The Problem Cascade",
            ha="center", fontsize=10, fontweight="bold", color=PALETTE["neutral_black"])

    # Root cause
    root = FancyBboxPatch((4.0, 5.5), 5.0, 0.8, boxstyle="round,pad=0.1",
                          facecolor=PALETTE["fail_red"], edgecolor="none", alpha=0.85)
    ax.add_patch(root)
    ax.text(6.5, 5.9, "MV3: Missing inter-stave dead material in GEANT4",
            ha="center", fontsize=8, fontweight="bold", color="white")

    # Cascade arrows and affected studies
    impacts = [
        (0.5, 3.8, "MV1: PID", "B2 → less affected\nSensitivity unquantified",
         "⚠️"),
        (3.2, 3.8, "MV2: Range-Energy", "Qualitative only until\ngeometry fixed",
         "⚠️"),
        (6.0, 3.8, "MV4: Timing", "Assumed insensitive\nNOT verified by variation",
         "? "),
        (8.8, 3.8, "MV5: Pile-up", "Multiplicity may be affected\n"
         "Agreement possibly fortuitous",
         "⚠️"),
        (1.8, 1.5, "MV3c: Geometry Audit", "PR #8: review-gated\n"
         "Not merged, not built, not run",
         "⛔"),
        (5.5, 1.5, "MV3b: Material Budget", "~0.1–0.5 g/cm²/pair\n"
         "FR-4 + polymer, not Al",
         "CORRECTED"),
        (9.2, 1.5, "B8 Acceptance", "5–10% on tracks\nentering B8",
         "? "),
    ]

    for x, y, title, detail, icon in impacts:
        # Card
        ax.add_patch(FancyBboxPatch((x, y), 2.8, 1.5,
                    boxstyle="round,pad=0.1",
                    facecolor=PALETTE["bg_light"],
                    edgecolor=PALETTE["tension_orange"] if icon == "⚠️"
                    else PALETTE["fail_red"] if icon == "⛔"
                    else PALETTE["neutral_light"],
                    lw=1))
        ax.text(x + 1.4, y + 1.2, icon, ha="center", fontsize=11)
        ax.text(x + 1.4, y + 0.7, title, ha="center", fontsize=7.5, fontweight="bold")
        ax.text(x + 1.4, y + 0.05, detail, ha="center", fontsize=5.8,
                color=PALETTE["neutral_dark"])

    # Arrows from root
    for x in [2.0, 4.5, 7.5, 10.0]:
        ax.annotate("", xy=(x, 5.4), xytext=(6.5 - (x - 6.5) * 0.3, 5.4),
                    arrowprops=dict(arrowstyle="->", color=PALETTE["fail_red"],
                                    lw=1.2, alpha=0.5))

    # Summary box
    ax.text(6.5, 0.2,
            "MV3 is the highest-priority unresolved item. Until GEANT4 geometry is fixed "
            "and new MC produced, all Tier 2 validations carry unquantified MV3 sensitivity.",
            ha="center", fontsize=6.5, color=PALETTE["fail_red"], fontweight="bold")

    name = "19_mv3_cascade"
    save_pub(fig, name)
    return name
