"""
Figure 18 — Analytic vs ML Timewalk: Head-to-Head (Chapter 5).

NEW FIGURE — visual comparison of analytic B/A vs ML timewalk correction,
showing they are statistically tied under LORO.

Core conclusion: Analytic timewalk (σ₆₈ = 1.49–1.55 ns) is statistically
tied with ML (1.39–1.47 ns) under leave-one-run-out CV.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig, despine
from ..data import get_timing


def build() -> str:
    td = get_timing()

    fig, ax = new_fig(7, 4.2)
    despine(ax)

    methods = ["CFD20\n(raw seed)", "Analytic\nB/A", "ML\n(Ridge)", "ML\n(HGB, gated)"]
    sigma_values = [2.8, (td.analytic_sigma68[0] + td.analytic_sigma68[1]) / 2,
                    (td.ml_sigma68[0] + td.ml_sigma68[1]) / 2, 1.11]
    ranges = [(2.5, 3.5),
              (td.analytic_sigma68[0], td.analytic_sigma68[1]),
              (td.ml_sigma68[0], td.ml_sigma68[1]),
              (1.05, 1.17)]
    colors = [PALETTE["neutral_mid"], PALETTE["analytic"],
              PALETTE["ml"], PALETTE["fail_red"]]
    statuses = ["", "Production\ncandidate", "Tied with\nanalytic (LORO)", "Not adopted\n(transfer audit)"]

    x = np.arange(len(methods))
    for i, (val, (lo, hi), color) in enumerate(zip(sigma_values, ranges, colors)):
        ax.bar(i, val, color=color, edgecolor="white", linewidth=0.3,
               width=0.55, alpha=0.85)
        ax.vlines(i, lo, hi, color=PALETTE["neutral_dark"], linewidth=1.8)

    # Labels
    for i, (val, (lo, hi), status) in enumerate(zip(sigma_values, ranges, statuses)):
        ax.text(i, hi + 0.08, f"{val:.2f}", ha="center", fontsize=8, fontweight="bold")
        if status:
            ax.text(i, lo - 0.18, status, ha="center", fontsize=6,
                    color=PALETTE["neutral_mid"], fontstyle="italic")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=7)
    ax.set_ylabel("σ₆₈ (ns)  lower = better", fontweight="bold", fontsize=7.5)
    ax.set_ylim(0, max(r[1] for r in ranges) * 1.25)
    ax.yaxis.grid(True, alpha=0.2)

    ax.set_title("Timewalk Correction: Analytic vs ML",
                 fontweight="bold", fontsize=9, pad=12)

    # Key insight
    ax.text(0.98, 0.05,
            "Analytic B/A tied with ML under proper CV — preferred for transparency\n"
            "HGB gated: in-fold only, needs transfer audit",
            transform=ax.transAxes, ha="right", fontsize=6.5,
            color=PALETTE["neutral_mid"])

    plt.tight_layout(pad=0.8)
    name = "18_timewalk_head_to_head"
    save_pub(fig, name)
    return name
