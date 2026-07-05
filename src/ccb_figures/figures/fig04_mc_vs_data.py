"""
Figure 04 — MC vs Data: Key Comparisons (Chapter 9).

Core conclusion: MC validates timing raw (PASS, pull=-1.05σ), corrected
shows tension (+2.68σ, digitizer artifact), pile-up self-consistent.

Archetype: quantitative grid (2×2).
"""

import matplotlib.pyplot as plt
import numpy as np

from ..config import PALETTE, save_pub, despine, add_verdict_stamp
from ..data import get_mc


def build() -> str:
    mc = get_mc()

    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5), facecolor="white")
    fig.subplots_adjust(hspace=0.4, wspace=0.35)

    # ── Panel (a): σ₆₈ raw ──────────────────────────────────────
    ax = axes[0, 0]
    despine(ax)
    d = [mc.mv4_raw_mc[0], mc.mv4_raw_data]
    e = [mc.mv4_raw_mc[1], 0.10]  # data error assumed 0.10 ns
    bars = ax.bar(["MC (GEANT4)", "Data"], d, yerr=e,
                  color=[PALETTE["mc"], PALETTE["data"]],
                  edgecolor="white", linewidth=0.5, width=0.5,
                  capsize=4, alpha=0.85)
    for bar, val in zip(bars, d):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.3f}", ha="center", fontsize=7.5, fontweight="bold")
    ax.set_ylabel("σ₆₈ (ns)", fontweight="bold", fontsize=7.5)
    ax.set_title("Raw Timing (no correction)", fontsize=8, fontweight="bold")
    add_verdict_stamp(ax, "PASS")
    ax.text(0.5, 0.88, f"pull = {mc.mv4_raw_pull:+.2f}σ", transform=ax.transAxes,
            ha="center", fontsize=7, color=PALETTE["pass_green"], fontweight="bold")

    # ── Panel (b): σ₆₈ timewalk-corrected ────────────────────────
    ax = axes[0, 1]
    despine(ax)
    d = [mc.mv4_corrected_mc[0], mc.mv4_corrected_data]
    e = [mc.mv4_corrected_mc[1], 0.10]
    bars = ax.bar(["MC (GEANT4)", "Data"], d, yerr=e,
                  color=[PALETTE["mc"], PALETTE["data"]],
                  edgecolor="white", linewidth=0.5, width=0.5,
                  capsize=4, alpha=0.85)
    for bar, val in zip(bars, d):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.3f}", ha="center", fontsize=7.5, fontweight="bold")
    ax.set_ylabel("σ₆₈ (ns)", fontweight="bold", fontsize=7.5)
    ax.set_title("Timewalk-Corrected Timing", fontsize=8, fontweight="bold")
    add_verdict_stamp(ax, "TENSION")
    ax.text(0.5, 0.88, f"pull = {mc.mv4_corrected_pull:+.2f}σ", transform=ax.transAxes,
            ha="center", fontsize=7, color=PALETTE["tension_orange"], fontweight="bold")

    # ── Panel (c): R_max ──────────────────────────────────────────
    ax = axes[1, 0]
    despine(ax)
    d = [mc.mv5_rmax_mc, mc.mv5_rmax_data]
    bars = ax.bar(["MC (GEANT4)", "Data"], d,
                  color=[PALETTE["mc"], PALETTE["data"]],
                  edgecolor="white", linewidth=0.5, width=0.5, alpha=0.85)
    for bar, val in zip(bars, d):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.3f}", ha="center", fontsize=7.5, fontweight="bold")
    ax.set_ylabel("R_max (MHz)", fontweight="bold", fontsize=7.5)
    ax.set_title("Pile-up Rate Limit", fontsize=8, fontweight="bold")
    add_verdict_stamp(ax, "PASS")
    ax.text(0.5, 0.88, "0.2% agreement", transform=ax.transAxes,
            ha="center", fontsize=7, color=PALETTE["pass_green"], fontweight="bold")

    # ── Panel (d): τ_eff ──────────────────────────────────────────
    ax = axes[1, 1]
    despine(ax)
    d = [mc.mv5_taueff_mc, mc.mv5_taueff_data]
    bars = ax.bar(["MC (GEANT4)", "Data"], d,
                  color=[PALETTE["mc"], PALETTE["data"]],
                  edgecolor="white", linewidth=0.5, width=0.5, alpha=0.85)
    for bar, val in zip(bars, d):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.2f}", ha="center", fontsize=7.5, fontweight="bold")
    ax.set_ylabel("τ_eff (ns)", fontweight="bold", fontsize=7.5)
    ax.set_title("Effective Live-Time", fontsize=8, fontweight="bold")
    add_verdict_stamp(ax, "PASS")
    ax.text(0.5, 0.88, "< 0.01%", transform=ax.transAxes,
            ha="center", fontsize=7, color=PALETTE["pass_green"], fontweight="bold")

    fig.suptitle("MC Validation: Key Comparisons", fontweight="bold", fontsize=10, y=1.01)

    name = "04_mc_vs_data"
    save_pub(fig, name)
    return name
