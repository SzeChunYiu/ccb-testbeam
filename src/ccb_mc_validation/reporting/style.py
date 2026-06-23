"""Matplotlib styling helpers for MC validation figures."""

from __future__ import annotations

from typing import Final

import matplotlib as mpl

# Paul Tol bright scheme — colorblind-safe.
COLORBLIND_PALETTE: Final[tuple[str, ...]] = (
    "#4477AA",
    "#EE6677",
    "#228833",
    "#CCBB44",
    "#66CCEE",
    "#AA3377",
    "#BBBBBB",
)


def apply_scientific_style(*, font_size: float = 10.0) -> None:
    """Apply publication-oriented matplotlib rcParams with a colorblind palette."""
    mpl.rcParams.update(
        {
            "figure.dpi": 100,
            "savefig.dpi": 160,
            "font.size": font_size,
            "axes.titlesize": font_size + 1,
            "axes.labelsize": font_size,
            "xtick.labelsize": font_size - 1,
            "ytick.labelsize": font_size - 1,
            "legend.fontsize": font_size - 1,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": "--",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.prop_cycle": mpl.cycler(color=list(COLORBLIND_PALETTE)),
            "lines.linewidth": 1.6,
            "lines.markersize": 5.0,
            "figure.constrained_layout.use": True,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
        }
    )
