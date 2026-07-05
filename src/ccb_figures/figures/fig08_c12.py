"""
Figure 08 — C12 Anomaly Discovery (Chapters 7, 9, MV6).

Core conclusion: Unsupervised learning found ~4% early-peak cluster;
MC truth identifies 0.32% as C12 nuclear recoils (55% of MC early-peak class).
Factor-12.5 discrepancy under investigation.

Archetype: image plate + quant.
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, despine
from ..data import get_mc, make_c12_waveform


def build() -> str:
    mc = get_mc()
    rng = np.random.default_rng(42)
    t_ns, normal, c12 = make_c12_waveform(rng)

    fig = plt.figure(figsize=(10, 6), facecolor="white")
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.35,
                          height_ratios=[1, 0.7])

    # ── Panel (a): Normal proton waveform ─────────────────────────
    ax = fig.add_subplot(gs[0, 0])
    despine(ax)
    ax.plot(t_ns, normal, "o-", color=PALETTE["proton"], markersize=3.5,
            linewidth=1.5, label="Normal proton")
    ax.fill_between(t_ns, 0, normal, alpha=0.15, color=PALETTE["proton"])
    ax.axvline(x=55, color=PALETTE["proton"], linestyle="--", linewidth=0.6, alpha=0.4)
    ax.set_xlabel("Time (ns)", fontsize=7)
    ax.set_ylabel("ADC (norm.)", fontsize=7)
    ax.set_title("Normal Proton Pulse", fontsize=8, fontweight="bold")
    ax.set_xlim(0, 175)
    ax.yaxis.grid(True, alpha=0.2)

    # ── Panel (b): C12 recoil waveform ───────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    despine(ax2)
    ax2.plot(t_ns, c12, "s-", color=PALETTE["fail_red"], markersize=3.5,
             linewidth=1.5, label="C12 recoil")
    ax2.fill_between(t_ns, 0, c12, alpha=0.15, color=PALETTE["fail_red"])
    ax2.axvline(x=15, color=PALETTE["fail_red"], linestyle="--", linewidth=0.6, alpha=0.4)
    ax2.set_xlabel("Time (ns)", fontsize=7)
    ax2.set_ylabel("ADC (norm.)", fontsize=7)
    ax2.set_title("C12 Nuclear Recoil (Anomaly)", fontsize=8, fontweight="bold")
    ax2.set_xlim(0, 175)
    ax2.yaxis.grid(True, alpha=0.2)

    # ── Panel (c): Discovery chain diagram ───────────────────────
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.set_xlim(0, 10)
    ax3.set_ylim(0, 10)
    ax3.axis("off")
    ax3.set_title("Discovery Chain", fontsize=8, fontweight="bold", pad=8)

    steps = [
        (5, 9.0, "PCA + GMM", "~4% cluster", PALETTE["ml"]),
        (5, 7.0, "Morphology cut", "Early peak, near-zero area", PALETTE["neutral_mid"]),
        (5, 5.0, "MV6 MC truth", "C12: 0.32% (55% of MC class)", PALETTE["mc"]),
        (5, 3.0, "Physics mechanism", "C12 recoil in CD₂ target", PALETTE["b2"]),
        (5, 1.0, "Systematic impact", "<0.1% on deuteron count", PALETTE["pass_green"]),
    ]
    for i, (x, y, label, detail, color) in enumerate(steps):
        ax3.text(x, y, f"{label}: {detail}", ha="center", fontsize=7,
                 fontweight="bold" if i < 2 else "normal", color=color)
        if i < len(steps) - 1:
            ax3.annotate("", xy=(x, y - 1.3), xytext=(x, y - 0.6),
                        arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_light"], lw=1.2))

    # ── Panel (d): Composition bar (bottom row, spans 3 cols) ────
    ax4 = fig.add_subplot(gs[1, :])
    despine(ax4)

    composition = [
        ("C12 recoils", mc.mv6_c12_mc_fraction, PALETTE["fail_red"]),
        ("Proton", 15.0, PALETTE["proton"]),
        ("Electron", 13.0, PALETTE["accent_teal"]),
        ("Alpha", 9.0, PALETTE["deuteron"]),
        ("Heavy ion", 7.0, PALETTE["ml"]),
        ("Other", 100 - mc.mv6_c12_mc_fraction - 15 - 13 - 9 - 7, PALETTE["neutral_light"]),
    ]

    left = 0
    for label, pct, color in composition:
        if pct > 0.5:
            ax4.barh(0, pct, left=left, color=color, edgecolor="white",
                     linewidth=0.3, height=0.5, label=label)
            if pct > 5:
                ax4.text(left + pct / 2, 0, f"{label}\n{pct:.1f}%",
                         ha="center", va="center", fontsize=6, fontweight="bold",
                         color="white" if pct > 10 else PALETTE["neutral_dark"])
            left += pct

    ax4.set_ylim(-0.5, 0.5)
    ax4.set_xlim(0, 100)
    ax4.set_xlabel("MC Early-Peak Class Composition (%)", fontsize=7)
    ax4.set_yticks([])
    ax4.xaxis.grid(True, alpha=0.2)

    fig.suptitle("MV6: C12 Nuclear Recoil Anomaly Discovery",
                 fontweight="bold", fontsize=10, y=1.01)

    name = "08_c12_anomaly"
    save_pub(fig, name)
    return name
