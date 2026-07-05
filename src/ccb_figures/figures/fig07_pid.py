"""
Figure 07 — PID Performance (Chapter 9, MV1).

Core conclusion: HGB reaches AUC=0.986 (MC truth ceiling), data-based
methods within 0.5% using weak-label proxies only.

Archetype: quantitative grid.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, new_fig, despine
from ..data import get_mc


def build() -> str:
    mc = get_mc()

    fig, ax = new_fig(7, 4.2)
    despine(ax)

    methods = ["ΔE Single-cut", "Logistic\nRegression", "HGB\n(MC Truth)"]
    aucs = [mc.mv1_purity_cut, mc.mv1_auc_lr, mc.mv1_auc_hgb]
    purities = [mc.mv1_purity_cut, mc.mv1_purity_lr, mc.mv1_purity_hgb]

    x = np.arange(len(methods))
    width = 0.30

    bars_auc = ax.bar(x - width / 2, aucs, width, label="AUC",
                      color=PALETTE["b6"], edgecolor="white", linewidth=0.3, alpha=0.85)
    bars_pur = ax.bar(x + width / 2, purities, width, label="Purity @ 90% eff.",
                      color=PALETTE["a_stack"], edgecolor="white", linewidth=0.3, alpha=0.85)

    for bar, val in zip(bars_auc, aucs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.006,
                f"{val:.4f}", ha="center", fontsize=7, fontweight="bold")
    for bar, val in zip(bars_pur, purities):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.006,
                f"{val:.4f}", ha="center", fontsize=7, fontweight="bold")

    # MC ceiling line
    ax.axhline(y=mc.mv1_auc_hgb, color=PALETTE["mc"], linestyle="--",
               linewidth=1, alpha=0.5)
    ax.text(2.4, mc.mv1_auc_hgb + 0.004, "MC truth ceiling",
            fontsize=6.5, color=PALETTE["mc"], ha="center")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=7)
    ax.set_ylabel("Score", fontweight="bold", fontsize=7.5)
    ax.legend(loc="lower right", fontsize=7, handlelength=1.2)
    ax.set_ylim(0.82, 1.01)
    ax.yaxis.grid(True, alpha=0.2)

    ax.set_title("Proton/Deuteron PID: MC Truth Validation (MV1)",
                 fontweight="bold", fontsize=9, pad=12)

    plt.tight_layout(pad=0.8)
    name = "07_pid_auc"
    save_pub(fig, name)
    return name
