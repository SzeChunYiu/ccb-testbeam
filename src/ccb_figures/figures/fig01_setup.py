"""
Figure 01 — Experimental Setup Schematic (Chapter 1/2).

Core conclusion: 190 MeV protons on CD₂ at CCB Kraków with
A/B HRD stacks ~100 cm downstream, capturing 18-sample waveforms.

Archetype: schematic-led composite.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

from ..config import PALETTE, save_pub, new_fig
from ..data import get_expt


def build() -> str:
    """Generate figure and return the base filename."""
    expt = get_expt()

    fig, ax = new_fig(11.5, 4.8)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 6.5)
    ax.axis("off")

    # ── Title ─────────────────────────────────────────────────────
    ax.text(7.5, 6.25, "CCB Test-Beam: 190 MeV protons → CD₂ target → HRD stacks",
            ha="center", fontsize=10, fontweight="bold", color=PALETTE["neutral_black"])

    # ── Beam line ─────────────────────────────────────────────────
    ax.annotate("", xy=(14, 3.5), xytext=(0.3, 3.5),
                arrowprops=dict(arrowstyle="->", color=PALETTE["fail_red"], lw=2.5))
    ax.text(7.2, 4.35, "190 MeV protons", ha="center", fontsize=8,
            fontweight="bold", color=PALETTE["fail_red"])

    # ── Target ────────────────────────────────────────────────────
    target = Rectangle((2.5, 2.6), 1.0, 1.8, facecolor=PALETTE["deuteron"],
                       edgecolor=PALETTE["neutral_dark"], lw=1.5, alpha=0.85)
    ax.add_patch(target)
    ax.text(3.0, 3.5, "CD₂\nTarget", ha="center", va="center",
            fontsize=7.5, fontweight="bold", color="white")
    ax.text(3.0, 2.3, "2.3 mm", ha="center", fontsize=6, color=PALETTE["neutral_mid"])

    # ── Trigger scintillators ─────────────────────────────────────
    trig = Rectangle((4.3, 2.8), 0.8, 1.4, facecolor=PALETTE["accent_teal"],
                     edgecolor=PALETTE["neutral_dark"], lw=1, alpha=0.7)
    ax.add_patch(trig)
    ax.text(4.7, 3.5, "Trigger\nScint.", ha="center", va="center", fontsize=6.5)

    # ── TPC ───────────────────────────────────────────────────────
    tpc = Rectangle((5.8, 2.3), 1.4, 2.4, facecolor=PALETTE["ml"],
                    edgecolor=PALETTE["neutral_dark"], lw=1.2, alpha=0.55)
    ax.add_patch(tpc)
    ax.text(6.5, 3.5, "TPC\n(tracking)", ha="center", va="center", fontsize=7, color="white")

    # ── A-Stack ───────────────────────────────────────────────────
    a_stack = Rectangle((8.3, 1.8), 1.8, 3.4, facecolor=PALETTE["a_stack"],
                        edgecolor=PALETTE["neutral_dark"], lw=1.8, alpha=0.65)
    ax.add_patch(a_stack)
    ax.text(9.2, 4.95, "A-Stack (HRD)", ha="center", fontsize=8, fontweight="bold")
    ax.text(9.2, 3.5, "A1  A3\n~100 cm", ha="center", fontsize=7)
    ax.text(9.2, 2.05, "Cross-check", ha="center", fontsize=6,
            color=PALETTE["neutral_mid"], fontstyle="italic")

    # ── B-Stack ───────────────────────────────────────────────────
    b_stack = Rectangle((10.9, 1.8), 1.8, 3.4, facecolor=PALETTE["b_stack"],
                        edgecolor=PALETTE["neutral_dark"], lw=1.8, alpha=0.75)
    ax.add_patch(b_stack)
    ax.text(11.8, 4.95, "B-Stack (HRD)", ha="center", fontsize=8,
            fontweight="bold", color="white")
    ax.text(11.8, 3.5, "B2 B4 B6 B8\n~100 cm", ha="center", fontsize=7, color="white")
    ax.text(11.8, 2.05, "★ Primary analysis", ha="center", fontsize=6.5,
            color="#FFD700", fontweight="bold")

    # ── Distance annotations ──────────────────────────────────────
    ax.annotate("", xy=(8.3, 5.6), xytext=(3.5, 5.6),
                arrowprops=dict(arrowstyle="<->", color=PALETTE["neutral_mid"], lw=1))
    ax.text(5.9, 5.8, "~100 cm", ha="center", fontsize=7, color=PALETTE["neutral_mid"])

    # ── Waveform callout ──────────────────────────────────────────
    ax.annotate("18-sample\nwaveform\n10 ns/sample",
                xy=(12.7, 1.3), xytext=(12.7, 0.3),
                fontsize=6.5, ha="center", color=PALETTE["b_stack"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["b_stack"], lw=1.2))

    # ── Bottom metadata ───────────────────────────────────────────
    ax.text(0.3, 0.3,
            f"Beam: {expt.beam_energy} MeV protons | "
            f"Target: {expt.target_thickness} mm {expt.target} | "
            f"Facility: CCB Kraków",
            fontsize=6.5, color=PALETTE["neutral_mid"])

    # ── Stave spacing inset ───────────────────────────────────────
    ax.text(13.8, 5.8, f"Stave spacing:\n{expt.stave_spacing} cm\n"
            f"(MC: {expt.stave_spacing_mc} cm)",
            fontsize=6, color=PALETTE["neutral_mid"], ha="right", va="top")

    plt.tight_layout(pad=0.8)
    name = "01_experimental_setup"
    save_pub(fig, name)
    return name
