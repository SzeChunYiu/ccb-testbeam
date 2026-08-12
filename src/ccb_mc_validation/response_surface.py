"""Local / asymmetric nuisance response summaries (#985).

A single unweighted global ``np.polyfit(..., 1)`` across a saturated or
nonlinear sweep is not a generally meaningful systematic derivative.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np

CONTRACT_VERSION = "2026.0-waveB-lane03-response-surface-v1"


def _as_float_arrays(
    xs: Sequence[float],
    ys: Sequence[float],
    frac_clipped: Optional[Sequence[float]] = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if frac_clipped is None:
        c = np.zeros_like(x)
    else:
        c = np.asarray(frac_clipped, dtype=np.float64)
    return x, y, c


def summarize_nuisance_sweep(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    frac_clipped: Optional[Sequence[float]] = None,
    clip_frac_threshold: float = 0.5,
    nominal_x: Optional[float] = None,
) -> dict[str, Any]:
    """Summarize a one-knob sweep without forcing a global linear slope.

    Returns local finite-difference elasticity near the nominal operating
    point (median x by default), asymmetric unsaturated excursions, curvature
    diagnostics, and an explicit flag when a global linear fit would be
    misleading.
    """
    x, y, clip = _as_float_arrays(xs, ys, frac_clipped)
    m = np.isfinite(x) & np.isfinite(y)
    x, y, clip = x[m], y[m], clip[m]
    out: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "n_points": int(len(x)),
        "points": [
            {"x": float(xi), "y": float(yi), "frac_clipped": float(ci)}
            for xi, yi, ci in zip(x, y, clip)
        ],
    }
    if len(x) < 2 or float(np.ptp(x)) <= 0:
        out.update(
            {
                "status": "INSUFFICIENT_POINTS",
                "global_linear_misleading": True,
                "local_slope": float("nan"),
                "local_elasticity": float("nan"),
            }
        )
        return out

    # Saturated ADC regions must not determine optical/ADC sensitivity slopes.
    unsaturated = clip < float(clip_frac_threshold)
    x_u, y_u = x[unsaturated], y[unsaturated]
    n_sat = int((~unsaturated).sum())
    out["n_saturated_points"] = n_sat
    out["n_unsaturated_points"] = int(unsaturated.sum())

    if nominal_x is None:
        nominal_x = float(np.median(x_u)) if len(x_u) else float(np.median(x))
    out["nominal_x"] = float(nominal_x)

    # Local finite difference: nearest unsaturated neighbours bracketing nominal.
    local_slope = float("nan")
    local_elast = float("nan")
    if len(x_u) >= 2:
        order = np.argsort(x_u)
        xu, yu = x_u[order], y_u[order]
        # Find bracket around nominal.
        hi = int(np.searchsorted(xu, nominal_x, side="left"))
        lo = hi - 1
        if lo < 0:
            lo, hi = 0, 1
        elif hi >= len(xu):
            lo, hi = len(xu) - 2, len(xu) - 1
        dx = float(xu[hi] - xu[lo])
        if abs(dx) > 0:
            local_slope = float((yu[hi] - yu[lo]) / dx)
            y0 = float(yu[lo] + (yu[hi] - yu[lo]) * (nominal_x - xu[lo]) / dx)
            if abs(y0) > 1e-12 and abs(nominal_x) > 1e-12:
                local_elast = float(local_slope * nominal_x / y0)
            out["local_bracket"] = {
                "x_lo": float(xu[lo]),
                "x_hi": float(xu[hi]),
                "y_lo": float(yu[lo]),
                "y_hi": float(yu[hi]),
                "y_at_nominal_interp": y0,
            }
    out["local_slope"] = local_slope
    out["local_elasticity"] = local_elast

    # Asymmetric unsaturated excursions from nominal.
    if len(x_u):
        # Interpolate y at nominal among unsaturated if possible; else nearest.
        y_nom = float(np.interp(nominal_x, x_u[np.argsort(x_u)], y_u[np.argsort(x_u)]))
        below = x_u < nominal_x
        above = x_u > nominal_x
        out["asymmetric_excursion"] = {
            "y_nominal": y_nom,
            "delta_y_min_below": float(np.min(y_u[below]) - y_nom) if below.any() else float("nan"),
            "delta_y_max_above": float(np.max(y_u[above]) - y_nom) if above.any() else float("nan"),
        }
    else:
        out["asymmetric_excursion"] = {
            "y_nominal": float("nan"),
            "delta_y_min_below": float("nan"),
            "delta_y_max_above": float("nan"),
        }

    # Curvature / linearity diagnostic on unsaturated points.
    global_linear_misleading = False
    reasons: list[str] = []
    if n_sat > 0:
        global_linear_misleading = True
        reasons.append("saturated_points_present")
    if len(x_u) >= 3:
        # Compare residual of degree-1 vs degree-2 poly on unsaturated points.
        coeff1 = np.polyfit(x_u, y_u, 1)
        resid1 = y_u - np.polyval(coeff1, x_u)
        ss1 = float(np.sum(resid1**2))
        coeff2 = np.polyfit(x_u, y_u, 2)
        resid2 = y_u - np.polyval(coeff2, x_u)
        ss2 = float(np.sum(resid2**2))
        out["global_linear_fit_unsaturated"] = {
            "slope": float(coeff1[0]),
            "intercept": float(coeff1[1]),
            "ss_residual": ss1,
        }
        out["quadratic_ss_residual"] = ss2
        # Materially better quadratic => global linear summary misleading.
        if ss1 > 0 and (ss1 - ss2) / ss1 > 0.2:
            global_linear_misleading = True
            reasons.append("quadratic_improves_residual_>20pct")
        # Non-monotonic check.
        order = np.argsort(x_u)
        dy = np.diff(y_u[order])
        if len(dy) >= 2 and np.any(dy > 0) and np.any(dy < 0):
            global_linear_misleading = True
            reasons.append("non_monotonic_unsaturated_response")
    elif len(x_u) < 2:
        global_linear_misleading = True
        reasons.append("fewer_than_2_unsaturated_points")

    out["global_linear_misleading"] = global_linear_misleading
    out["misleading_reasons"] = reasons
    out["status"] = "OK"
    # Systematic budgets should use local/asymmetric response, not global elasticity.
    out["recommended_elasticity"] = local_elast
    out["recommended_slope"] = local_slope
    return out
