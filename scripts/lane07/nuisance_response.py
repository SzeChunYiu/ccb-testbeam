"""Nuisance-sweep response summaries (issues #984/#985).

Fail-closed: do not promote a global linear slope as the systematic derivative
when curvature, saturation, or missing nominal locality make it misleading.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def parse_value_replicate(raw: str) -> Tuple[str, Optional[int]]:
    """Parse knob labels with optional replicate encoding.

    Accepts main AF-036 / #984 form ``0.6__rep=<seed>`` and legacy ``0.6__r2``.
    """
    if "__rep=" in raw:
        base, rep = raw.rsplit("__rep=", 1)
        try:
            return base, int(rep)
        except ValueError:
            return raw, None
    if "__r" in raw:
        base, rep = raw.rsplit("__r", 1)
        try:
            return base, int(rep)
        except ValueError:
            return raw, None
    return raw, None


def choose_nominal_index(xs: np.ndarray, *, preferred: Optional[float] = None) -> int:
    """Pick nominal index: preferred value if present, else median grid point."""
    xs = np.asarray(xs, dtype=float)
    if xs.size == 0:
        raise ValueError("empty grid")
    if preferred is not None and np.isfinite(preferred):
        i = int(np.argmin(np.abs(xs - preferred)))
        if abs(float(xs[i]) - preferred) <= 1e-12 * max(1.0, abs(preferred)):
            return i
        # tolerate soft match within 1% relative for float grids
        if abs(float(xs[i]) - preferred) <= 0.01 * max(1.0, abs(preferred)):
            return i
    order = np.argsort(xs)
    mid = order[len(order) // 2]
    return int(mid)


def local_finite_difference(
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    nominal_index: int,
    unsaturated: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Local left/right finite differences about the nominal operating point."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    n = xs.size
    if unsaturated is None:
        unsaturated = np.ones(n, dtype=bool)
    else:
        unsaturated = np.asarray(unsaturated, dtype=bool)

    out: Dict[str, Any] = {
        "estimand": "local_finite_difference_about_nominal",
        "nominal_index": int(nominal_index),
        "nominal_x": float(xs[nominal_index]) if n else float("nan"),
        "nominal_y": float(ys[nominal_index]) if n else float("nan"),
        "status": "OK",
        "reason": "",
    }
    if n < 2 or not np.isfinite(xs[nominal_index]) or not np.isfinite(ys[nominal_index]):
        out["status"] = "UNAVAILABLE"
        out["reason"] = "need_finite_nominal_and_neighbors"
        return out
    if not unsaturated[nominal_index]:
        out["status"] = "BLOCKED"
        out["reason"] = "nominal_point_adc_saturated"
        out["local_slope"] = None
        out["asymmetric_excursions"] = None
        return out

    order = np.argsort(xs)
    pos = int(np.where(order == nominal_index)[0][0])
    left = right = None
    for j in range(pos - 1, -1, -1):
        idx = int(order[j])
        if unsaturated[idx] and np.isfinite(xs[idx]) and np.isfinite(ys[idx]):
            left = idx
            break
    for j in range(pos + 1, n):
        idx = int(order[j])
        if unsaturated[idx] and np.isfinite(xs[idx]) and np.isfinite(ys[idx]):
            right = idx
            break

    slopes = []
    if left is not None:
        dx = float(xs[nominal_index] - xs[left])
        if dx != 0:
            slopes.append(("left", float((ys[nominal_index] - ys[left]) / dx), left))
    if right is not None:
        dx = float(xs[right] - xs[nominal_index])
        if dx != 0:
            slopes.append(("right", float((ys[right] - ys[nominal_index]) / dx), right))

    if not slopes:
        out["status"] = "UNAVAILABLE"
        out["reason"] = "no_unsaturated_neighbors"
        out["local_slope"] = None
        out["asymmetric_excursions"] = None
        return out

    local_slope = float(np.mean([s[1] for s in slopes]))
    asym = {
        "delta_y_left": float(ys[nominal_index] - ys[left]) if left is not None else None,
        "delta_y_right": float(ys[right] - ys[nominal_index]) if right is not None else None,
        "x_left": float(xs[left]) if left is not None else None,
        "x_right": float(xs[right]) if right is not None else None,
        "slope_left": next((s[1] for s in slopes if s[0] == "left"), None),
        "slope_right": next((s[1] for s in slopes if s[0] == "right"), None),
    }
    out["local_slope"] = local_slope
    out["asymmetric_excursions"] = asym
    x0, y0 = float(xs[nominal_index]), float(ys[nominal_index])
    out["local_elasticity"] = (
        float(local_slope * x0 / y0) if abs(y0) > 1e-9 else float("nan")
    )
    return out


def global_linear_diagnostic(
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    unsaturated: Optional[np.ndarray] = None,
    local_slope: Optional[float] = None,
) -> Dict[str, Any]:
    """Non-authorising global linear fit + curvature / mismatch flags (#985)."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if unsaturated is None:
        m = np.isfinite(xs) & np.isfinite(ys)
    else:
        m = np.asarray(unsaturated, dtype=bool) & np.isfinite(xs) & np.isfinite(ys)
    out: Dict[str, Any] = {
        "estimand": "global_linear_NONAUTHORISING",
        "authorising": False,
        "status": "OK",
    }
    if m.sum() < 2 or float(np.ptp(xs[m])) <= 0:
        out["status"] = "UNAVAILABLE"
        out["reason"] = "insufficient_unsaturated_points"
        return out
    slope, intercept = np.polyfit(xs[m], ys[m], 1)
    yhat = slope * xs[m] + intercept
    ss_res = float(np.sum((ys[m] - yhat) ** 2))
    ss_tot = float(np.sum((ys[m] - np.mean(ys[m])) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    # Quadratic curvature diagnostic on unsaturated points.
    curvature_flag = False
    if m.sum() >= 3:
        coef = np.polyfit(xs[m], ys[m], 2)
        # Compare quadratic improvement vs linear residual scale.
        yhat2 = coef[0] * xs[m] ** 2 + coef[1] * xs[m] + coef[2]
        ss_res2 = float(np.sum((ys[m] - yhat2) ** 2))
        if ss_res > 0 and (ss_res - ss_res2) / ss_res > 0.2:
            curvature_flag = True
        # Also flag if |a|*range^2 is large vs |slope|*range
        span = float(np.ptp(xs[m]))
        if abs(coef[0]) * span * span > 0.25 * abs(slope) * span:
            curvature_flag = True
    mismatch = False
    if local_slope is not None and np.isfinite(local_slope) and abs(local_slope) > 1e-12:
        if abs(slope - local_slope) / max(abs(local_slope), 1e-12) > 0.5:
            mismatch = True
    elif local_slope is not None and np.isfinite(local_slope):
        if abs(slope - local_slope) > 1e-6:
            mismatch = True

    misleading = bool(curvature_flag or mismatch or (np.isfinite(r2) and r2 < 0.85))
    out.update(
        {
            "slope": float(slope),
            "intercept": float(intercept),
            "r2": float(r2) if np.isfinite(r2) else None,
            "curvature_flag": curvature_flag,
            "local_global_mismatch": mismatch,
            "global_linear_misleading": misleading,
            "n_points_used": int(m.sum()),
        }
    )
    if misleading:
        out["status"] = "NONAUTHORISING_MISLEADING"
        out["reason"] = "curvature_or_mismatch_or_poor_r2"
    return out


def summarize_numeric_response(
    values: Sequence[str],
    ys: Sequence[float],
    frac_clipped: Sequence[float],
    *,
    preferred_nominal: Optional[float] = 1.0,
    clip_frac_threshold: float = 0.5,
) -> Dict[str, Any]:
    """Full #985 response summary for one observable vs numeric knob."""
    parsed = [parse_value_replicate(v) for v in values]
    # Aggregate replicates by value: mean of ys for same value string.
    buckets: Dict[str, List[Tuple[float, float]]] = {}
    for (vstr, _rep), y, fc in zip(parsed, ys, frac_clipped):
        buckets.setdefault(vstr, []).append((float(y), float(fc)))
    vstrs = sorted(buckets.keys(), key=lambda s: float(s))
    xs = np.array([float(v) for v in vstrs], dtype=float)
    y_mean = np.array([np.mean([t[0] for t in buckets[v]]) for v in vstrs], dtype=float)
    fc_mean = np.array([np.mean([t[1] for t in buckets[v]]) for v in vstrs], dtype=float)
    unsaturated = fc_mean < clip_frac_threshold
    try:
        nom_i = choose_nominal_index(xs, preferred=preferred_nominal)
    except ValueError:
        return {"status": "UNAVAILABLE", "reason": "empty_grid"}
    local = local_finite_difference(xs, y_mean, nominal_index=nom_i, unsaturated=unsaturated)
    glob = global_linear_diagnostic(
        xs,
        y_mean,
        unsaturated=unsaturated,
        local_slope=local.get("local_slope"),
    )
    return {
        "values": vstrs,
        "x": xs.tolist(),
        "y_mean": y_mean.tolist(),
        "frac_clipped_mean": fc_mean.tolist(),
        "unsaturated_mask": unsaturated.tolist(),
        "n_replicates_per_value": {v: len(buckets[v]) for v in vstrs},
        "local": local,
        "global_linear_diagnostic": glob,
        "authorising_summary": "local_finite_difference",
    }


def paired_replicate_effects(
    values: Sequence[str],
    ys: Sequence[float],
    *,
    preferred_nominal: Optional[float] = 1.0,
) -> Dict[str, Any]:
    """Seed-paired differences from nominal when replicates are present (#984)."""
    rows = []
    for v, y in zip(values, ys):
        vstr, rep = parse_value_replicate(v)
        rows.append((vstr, rep, float(y)))
    reps = {r for _, r, _ in rows if r is not None}
    if not reps:
        return {
            "status": "UNAVAILABLE",
            "reason": "no_replicate_encoding_in_labels",
            "authorising": False,
        }
    # Build value->nominal
    vstrs = sorted({v for v, _, _ in rows}, key=lambda s: float(s))
    xs = np.array([float(v) for v in vstrs], dtype=float)
    nom_i = choose_nominal_index(xs, preferred=preferred_nominal)
    nom_v = vstrs[nom_i]
    effects = []
    for rep in sorted(reps):
        by_v = {v: y for v, r, y in rows if r == rep}
        if nom_v not in by_v:
            continue
        y0 = by_v[nom_v]
        for v, y in by_v.items():
            if v == nom_v:
                continue
            effects.append(
                {
                    "replicate": int(rep),
                    "value": v,
                    "delta_y": float(y - y0),
                    "x": float(v),
                    "x0": float(nom_v),
                }
            )
    if not effects:
        return {"status": "UNAVAILABLE", "reason": "missing_nominal_in_replicates"}
    # Between-seed variance of effects at each x
    from collections import defaultdict

    by_x: Dict[float, List[float]] = defaultdict(list)
    for e in effects:
        by_x[e["x"]].append(e["delta_y"])
    between = {
        str(x): {
            "mean_delta": float(np.mean(ds)),
            "std_delta": float(np.std(ds, ddof=1)) if len(ds) > 1 else float("nan"),
            "n_replicates": len(ds),
        }
        for x, ds in sorted(by_x.items())
    }
    return {
        "status": "OK",
        "nominal_value": nom_v,
        "effects": effects,
        "between_seed": between,
        "n_replicates": len(reps),
    }
