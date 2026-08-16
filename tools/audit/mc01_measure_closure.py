"""Measure-closure helpers for mc01_trigger_split_truth (issue #1050).

Keeps weighted and unweighted representations role-separated so authorising
scalars/figures cannot silently mix measures.
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np


MEASURE_PRIMARY_WEIGHT = "PrimaryWeight"
MEASURE_UNWEIGHTED = "unweighted_generated_rows"
MEASURE_STATUS_AUTHORISING = "AUTHORISING_WEIGHTED_PREDICTION"
MEASURE_STATUS_DIAGNOSTIC = "LEGACY_UNWEIGHTED_PROPOSAL_DIAGNOSTIC"


def weight_diagnostics(weights) -> dict[str, float | int]:
    w = np.asarray(weights, dtype=float)
    if w.size == 0:
        return {
            "n": 0,
            "sum_w": 0.0,
            "sum_w2": 0.0,
            "ess": 0.0,
            "max_weight_fraction": 0.0,
        }
    sw = float(np.sum(w))
    s2 = float(np.sum(w * w))
    ess = float(sw * sw / s2) if s2 > 0.0 else 0.0
    max_frac = float(np.max(np.abs(w)) / abs(sw)) if sw != 0.0 else 0.0
    return {
        "n": int(w.size),
        "sum_w": sw,
        "sum_w2": s2,
        "ess": ess,
        "max_weight_fraction": max_frac,
    }


def layer_summary_from_counts(
    *,
    edep,
    edep_w,
    pid_counts: Mapping[str, int],
    pid_w: Mapping[str, float],
    wsum: float,
    large_mev: float,
    apply_weight: bool,
) -> dict[str, Any]:
    """Build one layer summary with a single declared measure."""
    e = np.asarray(edep, dtype=float)
    ew = np.asarray(edep_w, dtype=float) if len(edep_w) else np.ones_like(e)
    if ew.size != e.size:
        ew = np.ones_like(e)

    unweighted_pid = {}
    tot = sum(pid_counts.values()) or 1
    for k, v in sorted(pid_counts.items(), key=lambda kv: -kv[1]):
        unweighted_pid[k] = round(v / tot, 4)

    weighted_pid = {}
    wtot = sum(pid_w.values()) or 1.0
    for k, v in sorted(pid_w.items(), key=lambda kv: -kv[1]):
        weighted_pid[k] = round(v / wtot, 4)

    def _wmean(x, w):
        if x.size == 0:
            return 0.0
        sw = float(np.sum(w))
        if not np.isfinite(sw) or sw <= 0:
            return float(np.mean(x))
        return float(np.sum(w * x) / sw)

    def _wfrac(x, w, thr):
        if x.size == 0:
            return 0.0
        sw = float(np.sum(w))
        if not np.isfinite(sw) or sw <= 0:
            return float(np.mean(x > thr))
        return float(np.sum(w[x > thr]) / sw)

    unweighted = {
        "mean_edep_MeV": float(e.mean()) if e.size else 0.0,
        "median_edep_MeV": float(np.median(e)) if e.size else 0.0,
        "frac_large": float((e > large_mev).mean()) if e.size else 0.0,
        "pid_fraction": unweighted_pid,
    }
    weighted = {
        "mean_edep_MeV": _wmean(e, ew),
        "frac_large": _wfrac(e, ew, large_mev),
        "pid_fraction": weighted_pid,
        "weighted_sum_event_weight": float(wsum),
    }

    if apply_weight:
        return {
            "measure": MEASURE_PRIMARY_WEIGHT,
            "hits": int(e.size),
            "mean_edep_MeV": weighted["mean_edep_MeV"],
            "frac_large": weighted["frac_large"],
            "pid_fraction": weighted["pid_fraction"],
            "weighted_sum_event_weight": weighted["weighted_sum_event_weight"],
            "weight_diagnostics": weight_diagnostics(ew),
            "unweighted_diagnostic": unweighted,
        }
    return {
        "measure": MEASURE_UNWEIGHTED,
        "hits": int(e.size),
        "mean_edep_MeV": unweighted["mean_edep_MeV"],
        "frac_large": unweighted["frac_large"],
        "pid_fraction": unweighted["pid_fraction"],
        "weighted_sum_event_weight": float(wsum),
        "weight_diagnostics": weight_diagnostics(np.ones_like(e)),
        "unweighted_diagnostic": unweighted,
    }


def build_headline_first_b_layer(l0_I: Mapping[str, Any], l0_II: Mapping[str, Any], *, apply_weight: bool) -> dict[str, Any]:
    measure = MEASURE_PRIMARY_WEIGHT if apply_weight else MEASURE_UNWEIGHTED
    status = MEASURE_STATUS_AUTHORISING if apply_weight else MEASURE_STATUS_DIAGNOSTIC
    headline = {
        "measure": measure,
        "measure_status": status,
        "sampleI_d_fraction": l0_I["pid_fraction"].get("d", 0.0),
        "sampleII_d_fraction": l0_II["pid_fraction"].get("d", 0.0),
        "sampleI_frac_large": l0_I["frac_large"],
        "sampleII_frac_large": l0_II["frac_large"],
        "sampleI_mean_edep_MeV": l0_I["mean_edep_MeV"],
        "sampleII_mean_edep_MeV": l0_II["mean_edep_MeV"],
        "sampleI_weight_diagnostics": l0_I.get("weight_diagnostics", {}),
        "sampleII_weight_diagnostics": l0_II.get("weight_diagnostics", {}),
    }
    if apply_weight:
        headline["unweighted_diagnostic"] = {
            "sampleI_d_fraction": l0_I.get("unweighted_diagnostic", {}).get("pid_fraction", {}).get("d", 0.0),
            "sampleII_d_fraction": l0_II.get("unweighted_diagnostic", {}).get("pid_fraction", {}).get("d", 0.0),
            "sampleI_frac_large": l0_I.get("unweighted_diagnostic", {}).get("frac_large", 0.0),
            "sampleII_frac_large": l0_II.get("unweighted_diagnostic", {}).get("frac_large", 0.0),
            "sampleI_mean_edep_MeV": l0_I.get("unweighted_diagnostic", {}).get("mean_edep_MeV", 0.0),
            "sampleII_mean_edep_MeV": l0_II.get("unweighted_diagnostic", {}).get("mean_edep_MeV", 0.0),
        }
    return headline


def choose_scatter_indices(n: int, n_pts: int, weights, *, seed: int) -> np.ndarray:
    """Deterministic subsample; weight-proportional when weights are nontrivial."""
    if n <= 0:
        return np.asarray([], dtype=int)
    n_pts = min(int(n_pts), int(n))
    rng = np.random.default_rng(seed)
    w = np.asarray(weights, dtype=float)
    if w.size != n or not np.all(np.isfinite(w)) or not np.any(w > 0):
        return rng.choice(n, n_pts, replace=False)
    p = np.clip(w, 0.0, None)
    s = float(p.sum())
    if s <= 0.0:
        return rng.choice(n, n_pts, replace=False)
    p = p / s
    return rng.choice(n, n_pts, replace=False, p=p)
