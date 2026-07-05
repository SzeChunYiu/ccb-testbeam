"""
Figure 14 — Pedestal & Energy Scale (Chapter 8).

NEW FIGURE — compares adaptive vs learned pedestal methods,
saturation recovery, and gain calibration status.

Core conclusion: ML pedestal reduces MAE 341→49 ADC but proxy-validated only;
gain 92±28 ADC/MeV is PRELIMINARY (30% systematic).
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, despine, add_verdict_stamp
from ..data import get_pedestal


def build() -> str:
    pe = get_pedestal()

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), facecolor="white")

    # ── Panel (a): Pedestal methods ──────────────────────────────
    ax = axes[0]
    despine(ax)

    methods = ["Adaptive\n(legacy)", "HGBR\n(learned)"]
    mae_values = [pe.adaptive_mae, pe.learned_mae]
    colors = [PALETTE["fail_red"], PALETTE["pass_green"]]
    bars = ax.bar(np.arange(2), mae_values, color=colors, edgecolor="white",
                  linewidth=0.3, width=0.5, alpha=0.85)
    for bar, val in zip(bars, mae_values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                f"{val} ADC", ha="center", fontsize=7.5, fontweight="bold")
    ax.set_xticks(np.arange(2))
    ax.set_xticklabels(methods, fontsize=6.5)
    ax.set_ylabel("MAE vs pretrigger-median (ADC)", fontweight="bold", fontsize=7)
    ax.set_title("Pedestal Accuracy", fontsize=8, fontweight="bold")
    ax.yaxis.grid(True, alpha=0.2)

    ax.text(0.5, 0.05, f"Bias: {pe.adaptive_bias} ADC (by design)",
            transform=ax.transAxes, ha="center", fontsize=6, color=PALETTE["neutral_mid"])
    add_verdict_stamp(ax, "PRELIMINARY")

    # ── Panel (b): Saturation recovery ───────────────────────────
    ax2 = axes[1]
    despine(ax2)

    cats = ["Template\n(baseline)", "ML\n(rising edge)"]
    ml_lo, ml_hi = pe.ml_sat_res68
    trad_lo, trad_hi = pe.trad_sat_res68

    x2 = np.arange(2)
    bars2 = ax2.bar(x2, [trad_lo, ml_lo], color=[PALETTE["traditional"], PALETTE["ml"]],
                    edgecolor="white", linewidth=0.3, width=0.5, alpha=0.85)
    # Range
    ax2.vlines(0, trad_lo, trad_hi, color=PALETTE["neutral_dark"], linewidth=1.5)
    ax2.vlines(1, ml_lo, ml_hi, color=PALETTE["neutral_dark"], linewidth=1.5)

    for bar, (lo, hi), label in zip(bars2,
                                     [(trad_lo, trad_hi), (ml_lo, ml_hi)],
                                     [f"{trad_lo:.3f}–{trad_hi:.3f}",
                                      f"{ml_lo:.3f}–{ml_hi:.3f}"]):
        ax2.text(bar.get_x() + bar.get_width() / 2, hi + 0.01,
                 label, ha="center", fontsize=7, fontweight="bold")

    ax2.set_xticks(x2)
    ax2.set_xticklabels(cats, fontsize=6.5)
    ax2.set_ylabel("res68", fontweight="bold", fontsize=7)
    ax2.set_title("Saturation Recovery", fontsize=8, fontweight="bold")
    ax2.yaxis.grid(True, alpha=0.2)

    ax2.text(0.5, 0.05, f"3–7× improvement\n{pe.saturation_fraction:.0%} of B2 saturated",
             transform=ax2.transAxes, ha="center", fontsize=6, color=PALETTE["neutral_mid"])

    # ── Panel (c): Energy scale limitation ───────────────────────
    ax3 = axes[2]
    despine(ax3)

    edeps = [pe.proton_edep, pe.deuteron_edep]
    particles = ["Proton", "Deuteron"]
    colors3 = [PALETTE["proton"], PALETTE["deuteron"]]
    bars3 = ax3.bar(np.arange(2), edeps, color=colors3, edgecolor="white",
                    linewidth=0.3, width=0.45, alpha=0.85)
    for bar, val in zip(bars3, edeps):
        ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                 f"{val:.0f} MeV", ha="center", fontsize=7.5, fontweight="bold")
    ax3.set_xticks(np.arange(2))
    ax3.set_xticklabels(particles, fontsize=7)
    ax3.set_ylabel("edep_tot (MeV)", fontweight="bold", fontsize=7)
    ax3.set_title("GEANT4 Truth Energy (MV2)", fontsize=8, fontweight="bold")
    ax3.yaxis.grid(True, alpha=0.2)

    ax3.text(0.5, 0.05,
             "Per-event energy structurally\nunreachable from waveform alone\n"
             "Birks lookup = best held-out method",
             transform=ax3.transAxes, ha="center", fontsize=6, color=PALETTE["neutral_mid"])

    fig.suptitle("Pedestal, Saturation Recovery & Energy Scale",
                 fontweight="bold", fontsize=10, y=1.02)

    plt.tight_layout(pad=1.5)
    name = "14_pedestal_energy"
    save_pub(fig, name)
    return name
