"""
Figure 13 — Pile-up Rate Model & Current-Dependent Excess (Chapter 6).

NEW FIGURE — visualises τ_eff measurement, Poisson R_max model,
and current-dependent excess at 20 nA.

Core conclusion: τ_eff = 124.79 ns → R_max = 3.05 MHz;
30.8% downstream excess at high current.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, despine
from ..data import get_pileup


def build() -> str:
    pd_ = get_pileup()

    fig = plt.figure(figsize=(10.5, 5.5), facecolor="white")
    gs = fig.add_gridspec(2, 2, hspace=0.4, wspace=0.35)

    # ── Panel (a): τ_eff measurement ──────────────────────────────
    ax = fig.add_subplot(gs[0, 0])
    despine(ax)

    x_labels = ["Note\n(incorrect)", "Measured\n(data)", "MC\n(MV5)"]
    values = [pd_.tau_eff_incorrect, pd_.tau_eff, 124.8]
    colors = [PALETTE["fail_red"], PALETTE["data"], PALETTE["mc"]]
    x = np.arange(3)
    bars = ax.bar(x, values, color=colors, edgecolor="white",
                  linewidth=0.3, width=0.5, alpha=0.85)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.1f}", ha="center", fontsize=7.5, fontweight="bold")

    # CI on measured
    ax.errorbar(1, pd_.tau_eff,
                yerr=[[pd_.tau_eff - pd_.tau_eff_ci[0]],
                      [pd_.tau_eff_ci[1] - pd_.tau_eff]],
                fmt="none", color=PALETTE["neutral_dark"], capsize=3, linewidth=1)
    ax.text(1, pd_.tau_eff - 6,
            f"[{pd_.tau_eff_ci[0]:.1f}, {pd_.tau_eff_ci[1]:.1f}]",
            ha="center", fontsize=6, color=PALETTE["neutral_mid"])

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=6.5)
    ax.set_ylabel("τ_eff (ns)", fontweight="bold", fontsize=7.5)
    ax.set_title("Effective Live-Time τ_eff", fontsize=8, fontweight="bold")
    ax.yaxis.grid(True, alpha=0.2)

    # ── Panel (b): R_max comparison ───────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    despine(ax2)

    r_values = [pd_.r_max_incorrect, pd_.r_max]
    labels_r = ["Note (incorrect)", "Corrected"]
    colors_r = [PALETTE["fail_red"], PALETTE["pass_green"]]
    bars2 = ax2.bar(np.arange(2), r_values, color=colors_r, edgecolor="white",
                    linewidth=0.3, width=0.45, alpha=0.85)
    for bar, val in zip(bars2, r_values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                f"{val:.2f} MHz", ha="center", fontsize=7.5, fontweight="bold")
    ax2.set_xticks(np.arange(2))
    ax2.set_xticklabels(labels_r, fontsize=7)
    ax2.set_ylabel("R_max (MHz)", fontweight="bold", fontsize=7.5)
    ax2.set_title("Rate Limit: τ = 90 → τ = 124.8 ns", fontsize=8, fontweight="bold")
    ax2.yaxis.grid(True, alpha=0.2)

    # Arrow showing the correction
    ax2.annotate("−1.17 MHz\n(incorrect τ)",
                 xy=(1, pd_.r_max), xytext=(0.5, pd_.r_max_incorrect + 0.15),
                 fontsize=6.5, ha="center", color=PALETTE["fail_red"],
                 arrowprops=dict(arrowstyle="->", color=PALETTE["fail_red"], lw=1))

    # ── Panel (c): Current-dependent excess (bottom row, spans 2) ──
    ax3 = fig.add_subplot(gs[1, :])
    despine(ax3)

    metrics = [
        ("Downstream\nper event", 0.0231, 0.0334, 0.0103, (0.0064, 0.0142), "30.8%"),
        ("Multi-stave\nper event", 0.0156, 0.0268, 0.0112, (0.0080, 0.0145), "41.9%"),
        ("Three-stave\nper event", 0.0041, 0.0085, 0.0044, (0.0027, 0.0061), "51.8%"),
        ("ML classifier\nscore", 0.1213, 0.1574, 0.0360, None, "22.9%"),
    ]

    x3 = np.arange(len(metrics))
    width3 = 0.25
    ax3.bar(x3 - width3, [m[1] for m in metrics], width3,
            label="Low current (2 nA)", color=PALETTE["b6"],
            edgecolor="white", linewidth=0.3, alpha=0.85)
    ax3.bar(x3, [m[2] for m in metrics], width3,
            label="High current (20 nA)", color=PALETTE["deuteron"],
            edgecolor="white", linewidth=0.3, alpha=0.85)
    ax3.bar(x3 + width3, [m[3] for m in metrics], width3,
            label="Excess (Δ)", color=PALETTE["fail_red"],
            edgecolor="white", linewidth=0.3, alpha=0.85)

    for i, m in enumerate(metrics):
        ax3.text(i + width3, m[3] + 0.001, m[5],
                 ha="center", fontsize=6.5, fontweight="bold", color=PALETTE["fail_red"])

    ax3.set_xticks(x3)
    ax3.set_xticklabels([m[0] for m in metrics], fontsize=6.5)
    ax3.set_ylabel("Rate / Score", fontweight="bold", fontsize=7.5)
    ax3.set_title("Current-Dependent Excess: 2 nA → 20 nA", fontsize=8, fontweight="bold")
    ax3.legend(fontsize=6.5, ncol=3, loc="upper left", handlelength=1)
    ax3.yaxis.grid(True, alpha=0.2)

    ax3.text(0.98, 0.08,
             f"Downstream excess: {pd_.downstream_excess:.4f} "
             f"[{pd_.downstream_excess_ci[0]:.4f}, {pd_.downstream_excess_ci[1]:.4f}] per event\n"
             f"ML score ratio: {pd_.ml_score_ratio:.2f} — independent measurement",
             transform=ax3.transAxes, ha="right", fontsize=6.5, color=PALETTE["neutral_mid"])

    fig.suptitle("Pile-up Characterization: τ_eff → R_max → Current Excess",
                 fontweight="bold", fontsize=10, y=1.01)

    name = "13_pileup_rate"
    save_pub(fig, name)
    return name
