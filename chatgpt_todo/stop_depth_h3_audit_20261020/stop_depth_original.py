"""H3 stopping-depth estimands (issue #1047 / ARU-MC01-STOPWGT-001).

Separates termination probabilities from the stop-layer distribution
conditional on stopping. Weighted and unweighted fields share the same
conditioning; unavailable estimands carry an explicit status/reason
instead of silent NaN.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

import numpy as np

TERMINATIONS = ("stop", "escape", "censored")


def _as_float_array(x: Iterable[Any]) -> np.ndarray:
    return np.asarray(list(x), dtype=float)


def _as_str_array(x: Iterable[Any]) -> np.ndarray:
    return np.asarray([str(v) for v in x], dtype=object)


def _validate_weights(weights: np.ndarray) -> None:
    if weights.size == 0:
        return
    if not np.all(np.isfinite(weights)):
        raise ValueError("event weights must be finite (#880 / #1047)")
    if np.any(weights < 0.0):
        raise ValueError("event weights must be non-negative (#880 / #1047)")


def summarize_stop_depth_h3(
    *,
    termination: Sequence[Any],
    stop_layer: Sequence[Any],
    weights: Sequence[Any] | None = None,
    n_layers: int = 8,
    species: str | None = None,
) -> dict[str, Any]:
    """Return explicit H3 summaries for one species (or a pre-filtered set).

    Parameters
    ----------
    termination
        Per-track labels in {stop, escape, censored}.
    stop_layer
        Finite only when termination == "stop"; other values are ignored.
    weights
        Per-track event weights. Defaults to ones. Invalid weights fail closed.
    n_layers
        Number of B layers in the depth histogram.
    species
        Optional label recorded in the output for provenance.
    """
    if n_layers < 1:
        raise ValueError(f"n_layers must be >= 1, got {n_layers}")

    term = _as_str_array(termination)
    layers = _as_float_array(stop_layer)
    if layers.size != term.size:
        raise ValueError(
            f"stop_layer length {layers.size} != termination length {term.size}"
        )

    if weights is None:
        ww = np.ones(term.size, dtype=float)
    else:
        ww = _as_float_array(weights)
        if ww.size != term.size:
            raise ValueError(
                f"weights length {ww.size} != termination length {term.size}"
            )
    _validate_weights(ww)

    unknown = sorted({t for t in term if t not in TERMINATIONS})
    if unknown:
        raise ValueError(f"unknown termination labels: {unknown}")

    out: dict[str, Any] = {
        "estimand": "H3_termination_plus_conditional_stop_depth",
        "conditioning": {
            "termination_probs": "unconditional over species tracks",
            "stop_depth": "conditional on termination==stop",
        },
        "n_layers": int(n_layers),
        "n_tracks": int(term.size),
        "species": species,
    }

    term_prob_w: dict[str, float] = {}
    term_count: dict[str, int] = {}
    sw_all = float(ww.sum()) if ww.size else 0.0
    for label in TERMINATIONS:
        mask = term == label
        term_count[label] = int(mask.sum())
        if ww.size == 0 or sw_all <= 0.0:
            term_prob_w[label] = 0.0
        else:
            term_prob_w[label] = float(ww[mask].sum() / sw_all)

    out["termination_count"] = term_count
    out["termination_prob_weighted"] = term_prob_w
    out["termination_prob_unweighted"] = {
        label: (term_count[label] / term.size if term.size else 0.0)
        for label in TERMINATIONS
    }
    out["weight_sum_all"] = sw_all
    out["sum_w2_all"] = float(np.sum(ww * ww)) if ww.size else 0.0

    stop_mask = term == "stop"
    stop_layers = layers[stop_mask]
    stop_w = ww[stop_mask]
    n_stop = int(stop_mask.sum())
    out["n_stop"] = n_stop
    out["weight_sum_stop"] = float(stop_w.sum()) if stop_w.size else 0.0
    out["sum_w2_stop"] = float(np.sum(stop_w * stop_w)) if stop_w.size else 0.0

    stop_dist_u: dict[int, int] = {int(l): 0 for l in range(n_layers)}
    finite_stop = stop_layers[np.isfinite(stop_layers)]
    for l in finite_stop.astype(int):
        if 0 <= l < n_layers:
            stop_dist_u[int(l)] += 1
    out["stop_distribution_unweighted"] = stop_dist_u
    if n_stop > 0 and finite_stop.size > 0:
        out["mean_stop_layer_unweighted"] = float(finite_stop.mean())
        out["median_stop_layer_unweighted"] = float(np.median(finite_stop))
        out["mean_stop_layer_unweighted_status"] = "ok"
    else:
        out["mean_stop_layer_unweighted"] = None
        out["median_stop_layer_unweighted"] = None
        out["mean_stop_layer_unweighted_status"] = "unavailable"
        out["mean_stop_layer_unweighted_reason"] = "no_stopping_tracks"

    stop_dist_w: dict[int, float] = {int(l): 0.0 for l in range(n_layers)}
    sw_stop = float(stop_w.sum()) if stop_w.size else 0.0
    if n_stop == 0 or sw_stop <= 0.0:
        out["stop_distribution_weighted"] = stop_dist_w
        out["mean_stop_layer_weighted"] = None
        out["mean_stop_layer_weighted_status"] = "unavailable"
        out["mean_stop_layer_weighted_reason"] = (
            "no_stopping_tracks" if n_stop == 0 else "non_positive_stop_weight_sum"
        )
    else:
        finite = np.isfinite(stop_layers)
        if not np.all(finite):
            raise ValueError(
                "stop_layer must be finite for every termination==stop track"
            )
        for l in range(n_layers):
            stop_dist_w[int(l)] = float(np.sum(stop_w[stop_layers == l]) / sw_stop)
        out["stop_distribution_weighted"] = stop_dist_w
        out["mean_stop_layer_weighted"] = float(np.sum(stop_w * stop_layers) / sw_stop)
        out["mean_stop_layer_weighted_status"] = "ok"

    out["termination_prob_weighted_sum"] = float(sum(term_prob_w.values()))
    out["stop_distribution_weighted_sum"] = float(sum(stop_dist_w.values()))
    return out


def summarize_stop_depth_by_species(
    tracks: Mapping[str, Sequence[Any]],
    *,
    species_pdg: Mapping[str, int],
    n_layers: int = 8,
) -> dict[str, dict[str, Any]]:
    """Apply H3 per species using pdg / termination / stop_layer / weight columns."""
    pdg = _as_float_array(tracks["pdg"])
    term = _as_str_array(tracks["termination"])
    stop = _as_float_array(tracks["stop_layer"])
    ww = _as_float_array(tracks.get("weight", np.ones(pdg.size)))
    if not (pdg.size == term.size == stop.size == ww.size):
        raise ValueError("track column length mismatch for stop-depth H3 summary")

    out: dict[str, dict[str, Any]] = {}
    for sp_name, sp_pdg in species_pdg.items():
        mask = pdg == float(sp_pdg)
        out[sp_name] = summarize_stop_depth_h3(
            termination=term[mask],
            stop_layer=stop[mask],
            weights=ww[mask],
            n_layers=n_layers,
            species=sp_name,
        )
    return out
