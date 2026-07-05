"""
Figure 17 — Study Coverage Map (Chapter 3, all chapters).

NEW FIGURE — grid showing all ~230 studies mapped to chapters,
MV validations, and status (pass/tension/fail/preliminary).

Core conclusion: Full coverage of timing, pile-up, PID, energy,
ML methodology, systematics; MV3 is the critical gap.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig


def build() -> str:
    fig, ax = new_fig(11.5, 5.5)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(6, 8.7, "Study Coverage Map: ~230 Studies Across 13 Chapters",
            ha="center", fontsize=10, fontweight="bold", color=PALETTE["neutral_black"])

    # Chapter rows
    chapters = [
        ("Ch. 1–2: Intro & Setup", 8.0, 12, 0, "#0F4D92"),
        ("Ch. 3: Data Pipeline (S00–S01)", 7.2, 5, 0, "#3775BA"),
        ("Ch. 4: Pulse Reconstruction (S16)", 6.4, 8, 0, "#5BA3D9"),
        ("Ch. 5: Timing (S02–S05, MV4)", 5.6, 35, 6, "#8ECAE6"),
        ("Ch. 6: Pile-up (S10, MV5)", 4.8, 18, 3, "#42949E"),
        ("Ch. 7: Pulse Shape & ML (P01–P09)", 4.0, 40, 8, "#9A4D8E"),
        ("Ch. 8: Amplitude/Energy (MV0, MV2)", 3.2, 20, 3, "#B64342"),
        ("Ch. 9: MC Validation (MV0–MV6)", 2.4, 6, 1, "#E28E2C"),
        ("Ch. 10: ML Methodology (S07)", 1.6, 12, 2, "#7884B4"),
        ("Ch. 11: Systematics", 0.8, 5, 2, "#484878"),
    ]

    for label, y, total, issues, color in chapters:
        ax.text(0.3, y, label, fontsize=6.5, fontweight="bold",
                color=color, va="center")
        # Count bar
        bar_width = total / 40 * 7  # scale to max 40
        ax.add_patch(plt.Rectangle((3.0, y - 0.2), bar_width, 0.4,
                                   facecolor=color, edgecolor="none", alpha=0.7))
        ax.text(3.0 + bar_width + 0.15, y, f"{total} studies",
                fontsize=6, color=PALETTE["neutral_mid"], va="center")
        if issues > 0:
            ax.text(6.5, y, f"{issues} open items",
                    fontsize=5.5, color=PALETTE["fail_red"], va="center",
                    fontstyle="italic")

    # Status legend
    legend_items = [
        (PALETTE["pass_green"], "✅ PASS — 5 MV studies"),
        (PALETTE["tension_orange"], "🔶 TENSION — MV4 corrected"),
        (PALETTE["fail_red"], "⛔ FAIL — MV3 geometry"),
        (PALETTE["preliminary_grey"], "⚠️ PRELIMINARY — MV0 gain"),
    ]
    for i, (color, label) in enumerate(legend_items):
        ax.text(8.0, 8.0 - i * 0.35, label, fontsize=6.5, color=color)

    # Critical gap callout
    ax.add_patch(plt.Rectangle((7.8, 0.3), 4.0, 1.6,
                               facecolor=PALETTE["fail_red"], edgecolor="none",
                               alpha=0.08))
    ax.text(9.8, 1.5, "Critical Gap", fontsize=7, fontweight="bold",
            color=PALETTE["fail_red"], ha="center")
    ax.text(9.8, 1.0, "MV3: Missing inter-stave dead\nmaterial in GEANT4 geometry\n"
            "PR #8 open — needs merge,\nbuild, and new MC production",
            fontsize=5.5, color=PALETTE["neutral_dark"], ha="center")

    ax.text(9.8, 0.4, "230 studies · 13 chapters · 6 MV validations",
            ha="center", fontsize=6, color=PALETTE["neutral_mid"])

    name = "17_study_coverage"
    save_pub(fig, name)
    return name
