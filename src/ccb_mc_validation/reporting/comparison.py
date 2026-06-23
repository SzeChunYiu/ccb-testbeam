"""Ratio and pull panels for MC-vs-data overlays."""

from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes


def ratio_panel(
    ax: Axes,
    x: np.ndarray,
    numerator: np.ndarray,
    denominator: np.ndarray,
    *,
    label: str = "ratio",
    unity_band: float = 0.05,
) -> None:
    """Plot ``numerator / denominator`` with a shaded unity band."""
    x_arr = np.asarray(x, dtype=float)
    num = np.asarray(numerator, dtype=float)
    den = np.asarray(denominator, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(den > 0, num / den, np.nan)

    ax.axhspan(1.0 - unity_band, 1.0 + unity_band, color="#CCCCCC", alpha=0.35, zorder=0)
    ax.axhline(1.0, color="black", linewidth=0.8, linestyle="--")
    ax.plot(x_arr, ratio, marker="o", label=label)
    ax.set_ylabel("ratio")
    ax.legend(loc="best")


def pull_panel(
    ax: Axes,
    x: np.ndarray,
    observed: np.ndarray,
    expected: np.ndarray,
    uncertainty: np.ndarray,
    *,
    label: str = "pull",
) -> None:
    """Plot standardized residuals ``(observed - expected) / uncertainty``."""
    x_arr = np.asarray(x, dtype=float)
    obs = np.asarray(observed, dtype=float)
    exp = np.asarray(expected, dtype=float)
    unc = np.asarray(uncertainty, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        pull = np.where(unc > 0, (obs - exp) / unc, np.nan)

    ax.axhline(0.0, color="black", linewidth=0.8, linestyle="--")
    ax.axhspan(-1.0, 1.0, color="#CCCCCC", alpha=0.25, zorder=0)
    ax.plot(x_arr, pull, marker="o", label=label)
    ax.set_ylabel("pull")
    ax.legend(loc="best")
