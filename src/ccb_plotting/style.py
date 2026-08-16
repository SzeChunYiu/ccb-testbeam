"""One restrained, journal-sized visual language for CCB figures.

The defaults follow common journal artwork constraints: exact column widths,
small but legible typography, vector-safe fonts, thin axes, and colour-blind-safe
encodings.  Plot-specific modules may change geometry, never the evidence state.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import matplotlib as mpl

MM_PER_INCH = 25.4
SINGLE_COLUMN_MM = 89.0
DOUBLE_COLUMN_MM = 183.0
MAX_HEIGHT_MM = 170.0

# Okabe-Ito palette.  Black is deliberately first so colour is never the only cue.
OKABE_ITO = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "grey": "#6B6B6B",
    "light_grey": "#D8D8D8",
}

PAPER_RCPARAMS: dict[str, object] = {
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Liberation Sans"],
    "font.size": 7.0,
    "axes.titlesize": 7.5,
    "axes.titleweight": "normal",
    "axes.labelsize": 7.0,
    "axes.linewidth": 0.6,
    "axes.edgecolor": "#262626",
    "axes.labelcolor": "#262626",
    "axes.facecolor": "white",
    "axes.grid": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.labelsize": 6.0,
    "ytick.labelsize": 6.0,
    "xtick.color": "#262626",
    "ytick.color": "#262626",
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "xtick.minor.width": 0.4,
    "ytick.minor.width": 0.4,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "legend.fontsize": 5.8,
    "legend.frameon": False,
    "legend.handlelength": 1.5,
    "legend.handletextpad": 0.45,
    "legend.borderaxespad": 0.25,
    "lines.linewidth": 0.9,
    "lines.markersize": 3.4,
    "patch.linewidth": 0.6,
    "figure.facecolor": "white",
    "figure.dpi": 120,
    "figure.constrained_layout.use": True,
    "savefig.dpi": 600,
    "savefig.facecolor": "white",
    "savefig.transparent": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "svg.hashsalt": "ccb-paper-grade-v1",
    "mathtext.default": "regular",
}


def mm_to_inches(value_mm: float) -> float:
    """Convert millimetres to inches after validating the dimension."""
    value = float(value_mm)
    if not 0.0 < value <= MAX_HEIGHT_MM * 2:
        raise ValueError(f"invalid figure dimension {value_mm!r} mm")
    return value / MM_PER_INCH


def figure_size(*, column: str = "single", height_mm: float = 55.0) -> tuple[float, float]:
    """Return an exact journal canvas size in inches."""
    widths = {"single": SINGLE_COLUMN_MM, "double": DOUBLE_COLUMN_MM}
    try:
        width_mm = widths[column]
    except KeyError as exc:
        raise ValueError(f"column must be one of {sorted(widths)}, got {column!r}") from exc
    if not 20.0 <= float(height_mm) <= MAX_HEIGHT_MM:
        raise ValueError(f"height_mm must be in [20, {MAX_HEIGHT_MM}], got {height_mm}")
    return mm_to_inches(width_mm), mm_to_inches(float(height_mm))


def apply_paper_style() -> None:
    """Apply the project-wide paper style to the active Matplotlib process."""
    mpl.rcParams.update(PAPER_RCPARAMS)


@contextmanager
def paper_style() -> Iterator[None]:
    """Apply the paper style without leaking rcParams to caller code."""
    with mpl.rc_context(PAPER_RCPARAMS):
        yield


def light_axis_grid(axis: object, *, which: str = "y") -> None:
    """Add only the sparse reference grid needed to read quantitative values."""
    grid_axis = getattr(axis, f"{which}axis")
    grid_axis.grid(True, color=OKABE_ITO["light_grey"], linewidth=0.45, alpha=0.7)
    axis.set_axisbelow(True)
