"""
CCB Testbeam — Figure Configuration & Nature-Grade rcParams.

Applies the Nature Figure Making contract:
- Arial sans-serif, editable SVG text
- Clean white background, left+bottom spines only
- Publication-grade DPI and export helper
- CCB-specific physics palette
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path("docs/figures")
DPI_PUB = 300  # minimum for publication
FORMATS = ("png", "svg", "pdf")

# ---------------------------------------------------------------------------
# rcParams — apply once at import time
# ---------------------------------------------------------------------------
mpl.rcParams.update({
    # Typography
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,

    # Editable text in vector output
    "svg.fonttype": "none",
    "pdf.fonttype": 42,

    # Clean spines
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "axes.edgecolor": "#4D4D4D",

    # Grid — sparse, light
    "axes.grid": False,
    "grid.alpha": 0.15,
    "grid.color": "#B0B0B0",

    # Legend
    "legend.frameon": False,
    "legend.edgecolor": "none",
    "legend.handlelength": 1.5,
    "legend.handletextpad": 0.5,
    "legend.borderpad": 0.3,

    # Figure
    "figure.facecolor": "white",
    "figure.dpi": DPI_PUB,
    "savefig.dpi": DPI_PUB,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
    "savefig.transparent": False,
})


# ---------------------------------------------------------------------------
# CCB Physics Palette
#
# Semantic: one neutral family, one detector channel family,
# one MC/data distinction, one verdict color set.
# ---------------------------------------------------------------------------
PALETTE = {
    # Detector staves — cool sequential (B2 → B8, closer to beam → farther)
    "b2": "#0F4D92",
    "b4": "#3775BA",
    "b6": "#5BA3D9",
    "b8": "#8ECAE6",

    # Stacks
    "b_stack": "#0F4D92",
    "a_stack": "#8BCF8B",
    "combined": "#9A4D8E",

    # Data vs MC
    "data": "#0F4D92",
    "mc": "#B64342",

    # Particle species
    "proton": "#3775BA",
    "deuteron": "#E28E2C",

    # ML methods
    "ml": "#9A4D8E",
    "traditional": "#7884B4",
    "analytic": "#484878",

    # Verdict colors
    "pass_green": "#2E9E44",
    "tension_orange": "#E28E2C",
    "fail_red": "#E53935",
    "preliminary_grey": "#767676",

    # Neutrals
    "neutral_light": "#E8E8E8",
    "neutral_mid": "#A0A0A0",
    "neutral_dark": "#4D4D4D",
    "neutral_black": "#272727",

    # Accents for annotations
    "accent_gold": "#D4A017",
    "accent_teal": "#42949E",

    # Background tints for panel grouping
    "bg_light": "#F5F5F5",
}


def save_pub(fig: plt.Figure, name: str, dpi: int = DPI_PUB) -> None:
    """Save in all publication formats with editable text."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for fmt in FORMATS:
        path = OUTPUT_DIR / f"{name}.{fmt}"
        if fmt == "png":
            fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
        else:
            fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def new_fig(width: float, height: float) -> tuple[plt.Figure, plt.Axes]:
    """Create a clean single-panel figure."""
    fig, ax = plt.subplots(figsize=(width, height), facecolor="white")
    ax.set_facecolor("white")
    return fig, ax


def despine(ax: plt.Axes) -> None:
    """Remove top/right spines (belt-and-suspenders with rcParams)."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def add_verdict_stamp(
    ax: plt.Axes,
    verdict: str,
    x: float = 0.98,
    y: float = 0.02,
    ha: str = "right",
) -> None:
    """Add a small verdict badge to a panel."""
    color_map = {
        "PASS": PALETTE["pass_green"],
        "TENSION": PALETTE["tension_orange"],
        "FAIL": PALETTE["fail_red"],
        "PRELIMINARY": PALETTE["preliminary_grey"],
    }
    ax.text(
        x, y, verdict,
        transform=ax.transAxes, ha=ha, va="bottom",
        fontsize=6.5, fontweight="bold",
        color=color_map.get(verdict, PALETTE["neutral_dark"]),
        bbox=dict(
            boxstyle="round,pad=0.25", facecolor="white",
            edgecolor=color_map.get(verdict, PALETTE["neutral_mid"]),
            linewidth=0.6, alpha=0.9,
        ),
    )
