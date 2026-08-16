"""H3 stopping-depth estimands (issue #1047).

Separates termination mechanism from conditional stop-layer depth.
Does not invent physics: unavailable estimands are explicitly statused.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence

import numpy as np

TERMINATIONS = ("stop", "escape", "censored")


def _as_float_array(x: Sequence[Any]) -> np.ndarray:
    return np.asarray(x, dtype=float)


def _weight_diagnostics(w: np.ndarray) -> Dict[str, float]:
    w = np.asarray(w, dtype=float)
    finite = np.isfinite(w)
    ww = w[finite]
    sw = float(ww.sum()) if ww.size else 0.0
    sw2 = float(np.sum(ww * ww)) if ww.size else 0.0
    ess = float((sw * sw) / sw2) if sw2 > 0 else 0.0
    return {
        "sum_w": sw,
        "sum_w2": sw2,
        "n_tracks": int(w.size),
        "n_finite_weights": int(finite.sum()),
        "ess": ess,
    }


def summarize_stopping_h3(
    termination: Sequence[Any],
    stop_layer: Sequence[Any],
    weights: Sequence[Any],
    *,
    n_layers: int,
    species_mask: Optional[Sequence[bool]] = None,
) -> Dict[str, Any]:
    """Return explicit H3 summaries for one species (or all tracks).

    Estimands
    ---------
    - ``termination_probability_weighted``: P_w(stop|s), P_w(escape|s), P_w(censored|s)
      with denominator = all finite weights in the species mask.
    - ``stop_distribution_weighted`` / ``mean_stop_layer_weighted``: conditional on
      ``termination == \"stop\"`` only (H1), never mixing escape/censored into the
      depth denominator.
    """
    term = np.asarray(list(termination), dtype=object)
    layers = _as_float_array(stop_layer)
    w = _as_float_array(weights)
    if term.size != layers.size or term.size != w.size:
        raise ValueError("termination/stop_layer/weights length mismatch")

    if species_mask is None:
        mask = np.ones(term.size, dtype=bool)
    else:
        mask = np.asarray(species_mask, dtype=bool)
        if mask.size != term.size:
            raise ValueError("species_mask length mismatch")

    term_s = term[mask]
    layers_s = layers[mask]
    w_s = w[mask]

    out: Dict[str, Any] = {
        "estimand": "H3_termination_plus_conditional_depth",
        "conditioning": {
            "termination_probs": "all_species_tracks",
            "stop_depth": "termination==stop",
        },
        "n_layers": int(n_layers),
    }

    # Weight validity: fail-closed on non-finite / negative weights.
    bad_w = (~np.isfinite(w_s)) | (w_s < 0)
    if bad_w.any():
        out.update(
            {
                "status": "BLOCKED",
                "reason": "nonfinite_or_negative_weights",
                "termination_probability_weighted": None,
                "stop_distribution_weighted": None,
                "mean_stop_layer_weighted": None,
                "diagnostics": _weight_diagnostics(w_s),
            }
        )
        return out

    sw_all = float(w_s.sum()) if w_s.size else 0.0
    term_probs: Dict[str, float] = {}
    if sw_all <= 0 or w_s.size == 0:
        for tname in TERMINATIONS:
            term_probs[tname] = float("nan")
        term_status = "UNAVAILABLE"
        term_reason = "empty_or_zero_weight_species"
    else:
        for tname in TERMINATIONS:
            m = term_s == tname
            term_probs[tname] = float(w_s[m].sum() / sw_all)
        # Any unexpected termination labels are kept out of the three-way sum;
        # report residual mass so we do not silently drop weight.
        known = np.isin(term_s, list(TERMINATIONS))
        residual = float(w_s[~known].sum() / sw_all) if (~known).any() else 0.0
        term_probs["other"] = residual
        s3 = sum(term_probs[t] for t in TERMINATIONS)
        if not np.isfinite(s3) or abs(s3 + residual - 1.0) > 1e-9:
            term_status = "BLOCKED"
            term_reason = "termination_probs_not_normalized"
        else:
            term_status = "OK"
            term_reason = ""

    out["termination_probability_weighted"] = term_probs
    out["termination_status"] = term_status
    out["termination_reason"] = term_reason
    out["diagnostics_all"] = _weight_diagnostics(w_s)

    # Conditional stop-depth (H1) — stopping tracks only.
    stop_m = term_s == "stop"
    layers_stop = layers_s[stop_m]
    w_stop = w_s[stop_m]
    diag_stop = _weight_diagnostics(w_stop)
    out["diagnostics_stop"] = diag_stop

    finite_layer = np.isfinite(layers_stop)
    if stop_m.sum() == 0 or diag_stop["sum_w"] <= 0:
        out["stop_depth_status"] = "UNAVAILABLE"
        out["stop_depth_reason"] = "no_stopping_tracks"
        out["stop_distribution_weighted"] = None
        out["mean_stop_layer_weighted"] = None
        return out

    if not finite_layer.all():
        out["stop_depth_status"] = "BLOCKED"
        out["stop_depth_reason"] = "nonfinite_stop_layer_among_stops"
        out["stop_distribution_weighted"] = None
        out["mean_stop_layer_weighted"] = None
        return out

    sw = float(w_stop.sum())
    stop_dist = {int(ll): float(np.sum(w_stop[layers_stop == ll]) / sw) for ll in range(n_layers)}
    mass = float(sum(stop_dist.values()))
    if abs(mass - 1.0) > 1e-9:
        out["stop_depth_status"] = "BLOCKED"
        out["stop_depth_reason"] = "conditional_depth_not_normalized"
        out["stop_distribution_weighted"] = stop_dist
        out["mean_stop_layer_weighted"] = None
        return out

    mean = float(np.sum(w_stop * layers_stop) / sw)
    if not np.isfinite(mean):
        out["stop_depth_status"] = "BLOCKED"
        out["stop_depth_reason"] = "nonfinite_conditional_mean"
        out["stop_distribution_weighted"] = stop_dist
        out["mean_stop_layer_weighted"] = None
        return out

    out["stop_depth_status"] = "OK"
    out["stop_depth_reason"] = ""
    out["stop_distribution_weighted"] = stop_dist
    out["mean_stop_layer_weighted"] = mean
    out["status"] = "OK" if term_status == "OK" else term_status
    if term_status != "OK":
        out["reason"] = term_reason
    return out


def duplicate_weight_invariance(
    termination: Sequence[Any],
    stop_layer: Sequence[Any],
    weights: Sequence[Any],
    *,
    n_layers: int,
) -> Dict[str, Any]:
    """Duplicate each track with half weight; summaries must match (invariance)."""
    term = list(termination)
    layers = list(stop_layer)
    w = list(weights)
    term2, layers2, w2 = [], [], []
    for t, L, wi in zip(term, layers, w):
        term2.extend([t, t])
        layers2.extend([L, L])
        w2.extend([0.5 * float(wi), 0.5 * float(wi)])
    a = summarize_stopping_h3(term, layers, w, n_layers=n_layers)
    b = summarize_stopping_h3(term2, layers2, w2, n_layers=n_layers)
    return {"a": a, "b": b}
