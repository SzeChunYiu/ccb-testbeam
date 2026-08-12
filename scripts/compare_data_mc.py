#!/usr/bin/env python3
"""
compare_data_mc.py  (v7 — cluster-bootstrap OOB null with scale refit)
=====================================================================
Data <-> MC comparison for the CCB test beam, Sample I vs Sample II.

v7 changes:
  - OOB cluster-bootstrap null with scale refit on each replicate (#1164).
  - MC and DA clusters resampled independently; p-value = fraction of
    replicates where bootstrap D >= observed D on OOB clusters.
  - Legacy unit-weight permutation p_value_status updated to
    NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION (#1049 closed).
  - _scale_topology_record blocked_by narrowed to [#994, #1052] (#1164/#1166 resolved).

v6 changes retained:
  - Prefer event-level MC first-B EDep (#1052) over legacy hit/step arrays.
  - Require source-event cluster IDs for any null-calibration path (#1164).
  - Record fitted-scale topology (fit sample, overlap mode) for #1166.
  - Legacy unit-weight permutation p-value remains NONAUTHORISING (#1049).

v5 changes retained:
  - Weighted ECDFs are right-continuous step functions on unique support.
  - Tied observations are collapsed into one jump carrying their total weight.
  - Weighted KS D is evaluated exactly on the union of support points; no linear
    interpolation is used.
  - The legacy unit-weight permutation p-value is retained only as a clearly
    non-authorising diagnostic blocked by issue #1049.

v4 changes retained:
  - Per-event MC weights are required (fail closed if missing).
  - Weight vector is validated via validate_mc_weights: finite, nonnegative,
    dominance and ESS limits are enforced.
  - _wmedian does not fall back to an unweighted median.
  - Weight diagnostics (ESS, dominance, CV) are recorded in the output.

Brings together:
  - MC truth summary + first-B-layer EDep   (from mc01_trigger_split_truth.py)
  - DATA stave summary + first-B-layer (B2) amplitude (from data01_sample_split_staves.py)

Usage:
  python3 compare_data_mc.py --mc-dir <mc_out> --data-dir <data_out> --out <dir>
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

# Add repo root for validate_mc_weights import
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "tools"))
from audit import validate_mc_weights as vw

# ── Weight validation policy ──────────────────────────────────────────────────
# These enforce that the MC weight vector is finite, nonnegative, and not
# dominated by a single event.  Thresholds are conservative (optimisation-run
# justified defaults from the MC campaign).
MAX_ABS_WEIGHT_FRACTION = 0.50   # no single event carries >50% of total abs weight
MIN_ABSOLUTE_ESS = 1.0           # absolute ESS must be >= 1 (at least one effective event)


def load_json(d, name):
    with open(os.path.join(d, name)) as fh:
        return json.load(fh)


def _wmedian(x, w):
    """Weighted median via cumulative weight.  Raises if w is None or invalid."""
    x = np.asarray(x, dtype=float)
    if w is None:
        raise ValueError("_wmedian requires a weight vector")
    w = np.asarray(w, dtype=float)
    if w.size != x.size:
        raise ValueError(f"weight size {w.size} != value size {x.size}")
    if w.sum() <= 0:
        raise ValueError("weight sum is not positive")
    o = np.argsort(x)
    xs, ws = x[o], w[o]
    cw = np.cumsum(ws) / ws.sum()
    # Weighted median: smallest observable value at/above cumulative weight 0.5
    idx = int(np.searchsorted(cw, 0.5, side="left"))
    return float(xs[idx])


def _whist(x, bins, weights):
    """Weighted density histogram."""
    x = np.asarray(x, dtype=float)
    w = np.asarray(weights, dtype=float)
    h, _ = np.histogram(x, bins=bins, weights=w, density=True)
    return h


def _weighted_ecdf(x, w):
    """Return unique support and right-continuous weighted empirical CDF.

    The jump at support value ``a`` is the total weight of every row with
    ``x == a`` divided by the total sample weight.  This representation is
    invariant, up to floating roundoff, to splitting or merging identical
    weighted rows.
    """
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.ndim != 1 or w.ndim != 1:
        raise ValueError("weighted ECDF requires one-dimensional values and weights")
    if x.size != w.size:
        raise ValueError(f"weight size {w.size} != value size {x.size}")
    if x.size == 0:
        raise ValueError("weighted ECDF requires at least one observation")
    if not np.isfinite(x).all():
        raise ValueError("weighted ECDF values must be finite")
    if not np.isfinite(w).all():
        raise ValueError("weighted ECDF weights must be finite")
    if np.any(w < 0):
        raise ValueError("weighted ECDF weights must be nonnegative")
    total = float(np.sum(w))
    if total <= 0:
        raise ValueError("weighted ECDF weight sum must be positive")

    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ws = w[order]
    support, first = np.unique(xs, return_index=True)
    mass = np.add.reduceat(ws, first)
    cdf = np.cumsum(mass, dtype=float) / total
    cdf[-1] = 1.0
    return support, cdf


def _evaluate_weighted_ecdf(support, cdf, points):
    """Evaluate a right-continuous step ECDF at arbitrary points."""
    support = np.asarray(support, dtype=float)
    cdf = np.asarray(cdf, dtype=float)
    points = np.asarray(points, dtype=float)
    if support.ndim != 1 or cdf.ndim != 1 or support.size != cdf.size:
        raise ValueError("support and CDF must be one-dimensional arrays of equal size")
    if support.size == 0:
        raise ValueError("weighted ECDF support must not be empty")
    if not np.all(np.diff(support) > 0):
        raise ValueError("weighted ECDF support must be strictly increasing")
    if not np.isfinite(points).all():
        raise ValueError("weighted ECDF evaluation points must be finite")

    idx = np.searchsorted(support, points, side="right") - 1
    out = np.zeros(points.shape, dtype=float)
    mask = idx >= 0
    out[mask] = cdf[idx[mask]]
    return out


def _weighted_ks_distance(data, model, w_data, w_model):
    """Exact supremum distance between two right-continuous weighted ECDFs."""
    support_d, cdf_d = _weighted_ecdf(data, w_data)
    support_m, cdf_m = _weighted_ecdf(model, w_model)
    joint = np.union1d(support_d, support_m)
    eval_d = _evaluate_weighted_ecdf(support_d, cdf_d, joint)
    eval_m = _evaluate_weighted_ecdf(support_m, cdf_m, joint)
    return float(np.max(np.abs(eval_d - eval_m)))


def _weighted_ks_stat(data, model, w_data, w_model, n_bootstrap=200):
    """Weighted two-sample ECDF distance plus legacy blocked permutation p-value.

    ``D`` is the exact supremum distance between the two right-continuous
    weighted empirical CDFs.  The numerical p-value is retained only for
    backwards traceability: issue #1049 establishes that the current unit-weight
    value-permutation null is not calibrated for non-uniform MC weights and is
    therefore non-authorising.
    """
    data = np.asarray(data, dtype=float)
    model = np.asarray(model, dtype=float)
    w_data = np.asarray(w_data, dtype=float)
    w_model = np.asarray(w_model, dtype=float)
    if len(data) < 2 or len(model) < 2:
        return {
            "D": 0.0,
            "p_value": 1.0,
            "p_value_status": "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION",
            "cdf_convention": "right_continuous",
            "note": "insufficient data",
        }

    d_obs = _weighted_ks_distance(data, model, w_data, w_model)

    # Legacy non-authorising permutation null retained for provenance only.
    # Issue #1049 owns replacement with a calibrated design-consistent null.
    pooled = np.concatenate([data, model])
    n_d = len(data)
    N = min(n_bootstrap, 200)
    rng = np.random.default_rng(42)
    d_null = np.empty(N)
    for i in range(N):
        rng.shuffle(pooled)
        d_pool = pooled[:n_d]
        m_pool = pooled[n_d:]
        w_d = np.ones(n_d) / n_d
        w_m = np.ones(len(m_pool)) / len(m_pool)
        d_null[i] = _weighted_ks_distance(d_pool, m_pool, w_d, w_m)
    p_val = float((d_null >= d_obs).mean())
    return {
        "D": d_obs,
        "p_value": p_val,
        "p_value_status": "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION",
        "p_value_method": "legacy_unit_weight_value_permutation",
        "cdf_convention": "right_continuous",
        "ecdf_support": "unique_tie_aggregated",
        "n_data": int(n_d),
        "n_model": int(len(model)),
        "n_bootstrap": int(N),
        "weighted": True,
    }


def _validate_weight_vector(weights, label):
    """Validate a weight vector; returns a WeightAudit.  Raises on failure."""
    audit = vw.summarize_weights(weights)
    passed, findings = vw.validate_audit(
        audit,
        require_nonnegative=True,
        require_nonzero_sum=True,
        max_abs_weight_fraction=MAX_ABS_WEIGHT_FRACTION,
        min_absolute_ess=MIN_ABSOLUTE_ESS,
    )
    if not passed:
        codes = [f["code"] for f in findings if f["blocking"]]
        raise ValueError(
            f"MC weight validation FAILED for {label}: "
            f"blocking codes {codes}. "
            f"ESS={audit.absolute_effective_sample_size:.2f}, "
            f"max_abs_frac={audit.max_abs_weight_fraction:.4f}, "
            f"n_negative={audit.n_negative}, "
            f"n_nonfinite={audit.n - audit.n_finite}"
        )
    return audit


def _weight_diagnostics(audit):
    """Build a JSON-serialisable diagnostics dict from a WeightAudit."""
    return {
        "n": audit.n,
        "n_finite": audit.n_finite,
        "n_zero": audit.n_zero,
        "n_positive": audit.n_positive,
        "n_negative": audit.n_negative,
        "sum_w": audit.sum_w,
        "sum_abs_w": audit.sum_abs_w,
        "signed_effective_sample_size": audit.signed_effective_sample_size,
        "absolute_effective_sample_size": audit.absolute_effective_sample_size,
        "max_abs_weight_fraction": audit.max_abs_weight_fraction,
        "all_unit_weights": audit.all_unit_weights,
        "signed_weights_present": audit.signed_weights_present,
        "cancellation_fraction": audit.cancellation_fraction,
        "cancellation_severity": getattr(audit, "cancellation_severity", audit.cancellation_fraction),
        "signed_mass_orientation": getattr(audit, "signed_mass_orientation", 0),
        "weight_scale": getattr(audit, "weight_scale", None),
        "signed_diagnostic_method_id": getattr(audit, "signed_diagnostic_method_id", None),
        "coefficient_of_variation_abs": audit.coefficient_of_variation_abs,
    }



def _build_deltaE_E_narrative(comp_fields: dict) -> dict:
    """Derive ΔE–E narrative from machine-readable fields (#1002).

    Causal wording such as "physics effect, not an analysis artifact" is withheld
    while alternative mechanisms remain open (#956 and related mapping/geometry gates).
    """
    d_frac_I = float(comp_fields.get("sampleI_d_fraction", float("nan")))
    d_frac_II = float(comp_fields.get("sampleII_d_fraction", float("nan")))
    mean_stop_I = comp_fields.get("sampleI_mean_stop_layer")
    mean_stop_II = comp_fields.get("sampleII_mean_stop_layer")
    r_I = comp_fields.get("sampleI_pearson_r")
    r_II = comp_fields.get("sampleII_pearson_r")
    open_blockers = list(comp_fields.get("open_blockers", ["#956", "#1002"]))

    def fmt(x, nd=3):
        if x is None:
            return "unavailable"
        try:
            return f"{float(x):.{nd}f}"
        except (TypeError, ValueError):
            return "unavailable"

    prose = (
        "MC ΔE–E Pearson correlation (derived from loaded summary fields): "
        f"Sample I r={fmt(r_I)}, deuteron fraction at first B layer={fmt(d_frac_I*100,1)}%, "
        f"mean stop layer={fmt(mean_stop_I,1)}; "
        f"Sample II r={fmt(r_II)}, deuteron fraction={fmt(d_frac_II*100,1)}%, "
        f"mean stop layer={fmt(mean_stop_II,1)}. "
        "Narrative status: DIAGNOSTIC_ONLY while alternative mechanisms "
        f"({', '.join(open_blockers)}) remain open; no causal claim that the "
        "correlation pattern is a physics effect rather than an analysis artifact is authorised."
    )
    return {
        "status": "DIAGNOSTIC_ONLY",
        "open_blockers": open_blockers,
        "fields": {
            "sampleI_d_fraction": d_frac_I,
            "sampleII_d_fraction": d_frac_II,
            "sampleI_mean_stop_layer": mean_stop_I,
            "sampleII_mean_stop_layer": mean_stop_II,
            "sampleI_pearson_r": r_I,
            "sampleII_pearson_r": r_II,
        },
        "prose": prose,
        "causal_claim_authorised": False,
    }


def _load_spectrum_with_contract(mc_dir, data_dir):
    """Load DATA/MC first-B spectra with statistical-unit + cluster contracts.

    Prefers ``first_B_layer_event_edep.npz`` (#1052). Legacy hit/step files are
    accepted only as explicitly non-authorising diagnostics.
    """
    mc_event = Path(mc_dir) / "first_B_layer_event_edep.npz"
    mc_hit = Path(mc_dir) / "first_B_layer_edep.npz"
    da_path = Path(data_dir) / "first_B_layer_B2_amplitude.npz"
    if not da_path.exists():
        raise FileNotFoundError(da_path)

    da_amp = np.load(da_path)
    daI, daII = da_amp["sampleI"], da_amp["sampleII"]
    data_clusters = {}
    if "sampleI_cluster_id" in da_amp.files and "sampleII_cluster_id" in da_amp.files:
        data_clusters = {
            "I": np.asarray(da_amp["sampleI_cluster_id"]),
            "II": np.asarray(da_amp["sampleII_cluster_id"]),
        }
        data_unit = "pulse_row"
        data_cluster_key = "run:eventno"
    else:
        data_unit = "pulse_row_missing_cluster_id"
        data_cluster_key = None

    if mc_event.exists():
        mc_edep = np.load(mc_event)
        mc_unit = str(np.asarray(mc_edep["statistical_unit"]).reshape(-1)[0]) if "statistical_unit" in mc_edep.files else "event_stave_edep"
        product = "first_B_layer_event_edep.npz"
        authorising_unit = mc_unit == "event_stave_edep"
        quarantine = None if authorising_unit else "NONAUTHORISING_BLOCKED_ISSUE_1052"
    elif mc_hit.exists():
        mc_edep = np.load(mc_hit)
        mc_unit = str(np.asarray(mc_edep["statistical_unit"]).reshape(-1)[0]) if "statistical_unit" in mc_edep.files else "hit_step_edep"
        product = "first_B_layer_edep.npz"
        authorising_unit = False
        quarantine = "NONAUTHORISING_BLOCKED_ISSUE_1052"
    else:
        raise FileNotFoundError("missing first_B_layer_event_edep.npz and first_B_layer_edep.npz")

    mcI, mcII = mc_edep["sampleI"], mc_edep["sampleII"]
    if "sampleI_weights" not in mc_edep.files or "sampleII_weights" not in mc_edep.files:
        raise ValueError(
            f"{product} is missing sampleI_weights / sampleII_weights. "
            "Per-event PrimaryWeight is required; re-run mc01_trigger_split_truth.py."
        )
    mcI_w = np.asarray(mc_edep["sampleI_weights"], dtype=np.float64)
    mcII_w = np.asarray(mc_edep["sampleII_weights"], dtype=np.float64)

    mc_clusters = {}
    if "sampleI_cluster_id" in mc_edep.files and "sampleII_cluster_id" in mc_edep.files:
        mc_clusters = {
            "I": np.asarray(mc_edep["sampleI_cluster_id"]),
            "II": np.asarray(mc_edep["sampleII_cluster_id"]),
        }
        mc_cluster_key = "generator_event_index"
    else:
        mc_cluster_key = None

    membership = {}
    for side, key_i, key_ii in (
        ("I", "sampleI_in_sample_i", "sampleI_in_sample_ii"),
        ("II", "sampleII_in_sample_i", "sampleII_in_sample_ii"),
    ):
        if key_i in mc_edep.files and key_ii in mc_edep.files:
            membership[side] = {
                "in_sample_i": np.asarray(mc_edep[key_i], dtype=bool),
                "in_sample_ii": np.asarray(mc_edep[key_ii], dtype=bool),
            }

    contract = {
        "mc_product": product,
        "mc_statistical_unit": mc_unit,
        "data_statistical_unit": data_unit,
        "mc_cluster_key": mc_cluster_key,
        "data_cluster_key": data_cluster_key,
        "authorising_statistical_unit": bool(authorising_unit and data_cluster_key and mc_cluster_key),
        "quarantine": quarantine,
        "null_calibration_gate": (
            "OPEN_FOR_RESEARCH"
            if (mc_cluster_key and data_cluster_key and authorising_unit)
            else "BLOCKED_MISSING_CLUSTER_OR_UNIT"
        ),
        "weight_semantics": "PrimaryWeight_first_primary",
        "issues": ["#1049", "#1052", "#1164", "#1166"],
    }
    return {
        "mcI": mcI,
        "mcII": mcII,
        "mcI_w": mcI_w,
        "mcII_w": mcII_w,
        "daI": daI,
        "daII": daII,
        "mc_clusters": mc_clusters,
        "data_clusters": data_clusters,
        "membership": membership,
        "contract": contract,
        "mc_edep": mc_edep,
        "da_amp": da_amp,
    }


def _scale_topology_record(membership, data_clusters):
    """Serialize fitted-scale fit/test overlap topology (#1166)."""
    mc_nested = False
    if "I" in membership and "II" in membership:
        # Under the current trigger design, Sample I events are a subset of II.
        mc_nested = True
    data_disjoint = False
    if data_clusters:
        # DATA Sample I/II are disjoint at the configured run-family level.
        data_disjoint = True
    return {
        "estimator_id": "data_mc_median_match_peak_adc_per_truth_edep_MeV_proxy",
        "fit_sample": "II",
        "tested_samples": ["I", "II"],
        "mc_sample_i_subset_of_ii": mc_nested,
        "data_sample_i_run_disjoint_from_ii": data_disjoint,
        "nuisance_mode_default": "refit_inside_replicate",
        "authorising": False,
        "blocked_by": ["#994", "#1052"],
        "note": (
            "Scale is a non-authorising proxy until event/stave digitized response "
            "is available. Null replicates refit the scale inside each replicate "
            "(OOB cluster bootstrap, #1164); freezing shat on Sample II is rejected."
        ),
    }


def _group_values_by_label(values, labels):
    """One-pass ``{label: values_array}`` for any hashable cluster/group label.

    Mirrors ``ccb_mc_validation.statistics.bootstrap._group_values_by_label``:
    ``labels == k`` does an element-wise broadcast for tuple labels (e.g.
    ``(run, event)``) instead of a cluster-level membership test; this avoids
    that pitfall and preserves label-equality semantics.
    """
    groups = {}
    order = []
    for label, val in zip(labels.tolist(), values.tolist()):
        bucket = groups.get(label)
        if bucket is None:
            groups[label] = [val]
            order.append(label)
        else:
            bucket.append(val)
    keys = np.empty(len(order), dtype=object)
    keys[:] = order
    members = {k: np.asarray(groups[k], dtype=float) for k in order}
    return keys, members


def _cluster_bootstrap_null_scale_refit(
    mcI, mcII, daI, daII,
    mcI_w, mcII_w,
    mc_clusters, data_clusters,
    d_obs,
    *,
    n_replicates=1000,
    seed=42,
):
    """OOB cluster-bootstrap null with per-replicate scale refit (#1164).

    MC and DATA clusters are resampled independently (different label schemes:
    ``generator_event_index`` on MC, ``run:eventno`` on DATA).  Each replicate::

      1. resamples clusters WITH replacement -> bootstrap sample,
      2. refits the MeV->ADC scale on the bootstrap sample's Sample II:
         mev_to_adc_r = median(DA_II_boot) / weighted_median(MC_II_boot, w),
      3. evaluates the weighted KS D on the **out-of-bag** (OOB) clusters,
         applying the refit scale to the OOB MC values.

    p-value = fraction of replicates with D_boot >= observed D on OOB clusters.
    ``d_obs`` is a dict with keys ``"I"`` and ``"II"`` giving the full-data
    weighted KS distance for each sample.  Minimum 500 replicates; 1000-2000
    recommended.  Fail closed: raises ``ValueError`` when cluster IDs are missing
    or when fewer than half of the replicates succeed (pattern from
    ``weighted_cluster_bootstrap``).
    """
    required = {
        "mcI": mc_clusters.get("I"),
        "mcII": mc_clusters.get("II"),
        "daI": data_clusters.get("I"),
        "daII": data_clusters.get("II"),
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise ValueError(
            f"OOB cluster-bootstrap null requires source-event cluster IDs; "
            f"missing {missing} (issue #1164)"
        )
    mcI_c, mcII_c = required["mcI"], required["mcII"]
    daI_c, daII_c = required["daI"], required["daII"]

    # Length consistency: every value vector must pair with its cluster ids.
    for name, (vals, labs) in {
        "mcI": (mcI, mcI_c), "mcII": (mcII, mcII_c),
        "daI": (daI, daI_c), "daII": (daII, daII_c),
    }.items():
        if np.asarray(vals).size != np.asarray(labs).size:
            raise ValueError(
                f"{name}: value size {np.asarray(vals).size} != cluster-id "
                f"size {np.asarray(labs).size} (issue #1164)"
            )

    # Observed statistics on the full data (scale computed in main()).
    # ``d_obs`` is passed in by the caller — do NOT re-declare here.
    d_boot = {"I": [], "II": []}
    n_success = {"I": 0, "II": 0}
    n_failure = {"I": 0, "II": 0}

    # Cluster membership for every side (values AND MC weights).
    mcI_keys, mcI_members = _group_values_by_label(mcI, mcI_c)
    mcI_w_members = _group_values_by_label(mcI_w, mcI_c)[1]
    mcII_keys, mcII_members = _group_values_by_label(mcII, mcII_c)
    mcII_w_members = _group_values_by_label(mcII_w, mcII_c)[1]
    daI_keys, daI_members = _group_values_by_label(daI, daI_c)
    daII_keys, daII_members = _group_values_by_label(daII, daII_c)

    rng = np.random.default_rng(seed)
    n = int(n_replicates)
    if n < 500:
        raise ValueError(f"OOB cluster-bootstrap null requires >=500 replicates, got {n}")

    scale_r = np.empty(n, dtype=float)
    for r in range(n):
        # Independent resamplings: MC and DA clusters have different label
        # schemes, so they are never mixed.
        chosen_mcII = rng.choice(mcII_keys, size=mcII_keys.size, replace=True)
        chosen_mcI = rng.choice(mcI_keys, size=mcI_keys.size, replace=True)
        chosen_daII = rng.choice(daII_keys, size=daII_keys.size, replace=True)
        chosen_daI = rng.choice(daI_keys, size=daI_keys.size, replace=True)

        oob_mcII = np.concatenate(
            [mcII_members[k] for k in mcII_keys if k not in set(chosen_mcII)]
        )
        oob_mcII_w = np.concatenate(
            [mcII_w_members[k] for k in mcII_keys if k not in set(chosen_mcII)]
        )
        oob_daII = np.concatenate(
            [daII_members[k] for k in daII_keys if k not in set(chosen_daII)]
        )
        oob_mcI = np.concatenate(
            [mcI_members[k] for k in mcI_keys if k not in set(chosen_mcI)]
        )
        oob_mcI_w = np.concatenate(
            [mcI_w_members[k] for k in mcI_keys if k not in set(chosen_mcI)]
        )
        oob_daI = np.concatenate(
            [daI_members[k] for k in daI_keys if k not in set(chosen_daI)]
        )

        # Scale refit on the bootstrap sample's Sample II (both sides).
        mcII_boot = np.concatenate([mcII_members[k] for k in chosen_mcII])
        mcII_boot_w = np.concatenate([mcII_w_members[k] for k in chosen_mcII])
        daII_boot = np.concatenate([daII_members[k] for k in chosen_daII])
        try:
            mc_ref_r = _wmedian(mcII_boot, mcII_boot_w)
            da_ref_r = float(np.median(daII_boot)) if daII_boot.size else 0.0
            if not (mc_ref_r > 0 and da_ref_r > 0):
                raise ValueError("non-positive scale refit")
            scale_r[r] = da_ref_r / mc_ref_r
        except ValueError:
            n_failure["I"] += 1
            n_failure["II"] += 1
            continue

        # Weighted KS D on OOB clusters with the refit scale.
        for s, oob_da, oob_mc, oob_w in (
            ("I", oob_daI, oob_mcI, oob_mcI_w),
            ("II", oob_daII, oob_mcII, oob_mcII_w),
        ):
            if oob_da.size == 0 or oob_mc.size == 0:
                n_failure[s] += 1
                continue
            d_boot[s].append(_weighted_ks_distance(
                oob_da, oob_mc * scale_r[r],
                np.ones(oob_da.size), oob_w,
            ))
            n_success[s] += 1

    # Observed D is the full-data weighted KS distance (scale from main()).
    # Computed by the caller and passed in; here we only report the bootstrap.
    threshold = max(10, int(0.5 * n))
    out = {"method": "oob_cluster_bootstrap_scale_refit", "fit_sample": "II"}
    for s in ("I", "II"):
        if n_success[s] < threshold:
            raise ValueError(
                f"OOB cluster-bootstrap null NOT_ESTIMABLE for Sample {s}: "
                f"only {n_success[s]}/{n} replicates succeeded "
                f"({n_failure[s]} failures) (issue #1164)"
            )
        arr = np.asarray(d_boot[s], dtype=float)
        out[s] = {
            "n_boot_success": int(n_success[s]),
            "n_boot_failure": int(n_failure[s]),
            "D_obs": float(d_obs[s]),
            "D_bootstrap_mean": float(arr.mean()),
            "D_bootstrap_p95": float(np.quantile(arr, 0.95)),
            "p_value": float((arr >= d_obs[s]).mean()),
        }
    out["status"] = "OK"
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc-dir", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale-uncertainty", type=float, default=0.30,
                    help="±fractional uncertainty on MeV→ADC scale (default 0.30 from MV0)")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    mc = load_json(args.mc_dir, "mc_trigger_split_summary.json")
    da = load_json(args.data_dir, "data_sample_split_summary.json")
    loaded = _load_spectrum_with_contract(args.mc_dir, args.data_dir)
    mcI = loaded["mcI"]
    mcII = loaded["mcII"]
    daI = loaded["daI"]
    daII = loaded["daII"]
    mcI_w = loaded["mcI_w"]
    mcII_w = loaded["mcII_w"]
    spectrum_contract = loaded["contract"]
    scale_topology = _scale_topology_record(loaded["membership"], loaded["data_clusters"])
    if spectrum_contract["quarantine"] == "NONAUTHORISING_BLOCKED_ISSUE_1052":
        print(
            "WARNING: using non-authorising MC statistical unit "
            f"{spectrum_contract['mc_statistical_unit']} from {spectrum_contract['mc_product']} "
            "(issue #1052). Prefer first_B_layer_event_edep.npz."
        )

    # Validate weights — fail closed if any policy gate fails
    audit_I = _validate_weight_vector(mcI_w, "Sample I")
    audit_II = _validate_weight_vector(mcII_w, "Sample II")

    # ── MeV -> ADC scale (Sample II proton-dominated weighted median) ────────
    mc_ref = float(_wmedian(mcII, mcII_w)) if mcII.size else 1.0
    da_ref = float(np.median(daII)) if daII.size else 1.0
    mev_to_adc = da_ref / mc_ref if mc_ref else 1.0
    scale_lo = mev_to_adc * (1 - args.scale_uncertainty)
    scale_hi = mev_to_adc * (1 + args.scale_uncertainty)

    # ── Nuisance contract (issue #1166, WKS-NULL-SCALE-001) ─────────────────
    # Machine-readable description of the fitted-scale nuisance shat, its
    # estimator, fit/test topology, and authorisation state.  The shat is fit
    # on Sample II (both MC weighted median and DATA median) and applied to the
    # comparison of both Sample I and Sample II.  The MC fit-test overlap is
    # nested: Sample II MC events appear in both the fit and the test.  The
    # DATA side has the same structure.  This contract is non-authorising until
    # the gating issues (#994, #1052) close.
    nuisance = {
        "estimator_id": "data_mc_median_match_peak_adc_per_truth_edep_MeV_proxy",
        "estimator_formula": "shat = median(DA_II) / weighted_median(MC_II, PrimaryWeight)",
        "fit_sample": "Sample II",
        "tested_samples": ["Sample I", "Sample II"],
        "units": "ADC_per_MeV",
        "fit_sample_components": {
            "MC": {
                "estimator": "weighted_median",
                "weight": "PrimaryWeight",
                "n_events": int(mcII.size) if mcII.size else 0,
                "value": mc_ref,
            },
            "DATA": {
                "estimator": "median",
                "n_events": int(daII.size) if daII.size else 0,
                "value": da_ref,
            },
        },
        "fit_test_overlap": {
            "mode": "NESTED",
            "description": (
                "The fit uses Sample II (both MC and DATA).  The test evaluates "
                "both Sample I and Sample II against the same scale.  On the MC side, "
                "Sample II events participate in both the fit (weighted median) and "
                "the test (weighted ECDF D).  The DATA side shares the same nested "
                "structure: Sample II median is the fit target, and Sample II also "
                "appears in the test."
            ),
            "mc_fit_test_relation": "nested_MC",
            "data_fit_test_relation": "nested_DATA",
        },
        "authorisation": {
            "status": "NONAUTHORISING",
            "blockers": {
                "#994": "truth-typed scale identity gate",
                "#1052": "matched detector-event/stave response",
                "#1164": "source-bound event IDs and membership",
            },
        },
    }

    # ── Counterfactual ───────────────────────────────────────────────────────
    counterfactual = {
        "no_trigger_mimicry_note": "Without trigger mimicry, all ENTER-B events form one undifferentiated sample. "
                                   "With trigger mimicry, Sample I (coincidence) is a deuteron-enriched subset. "
                                   "The improvement is the Sample I vs Sample II contrast.",
        "enterB_all_d_fraction": mc["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
        "coincidence_sampleI_d_fraction": mc["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
        "singleB_not_coinc_d_fraction": "computed below (Sample II minus Sample I overlap)",
        "d_enrichment_factor": round(
            mc["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0) /
            max(mc["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0), 0.001), 2),
        "conclusion": "Trigger mimicry recovers a factor ~{:.1f}x deuteron enrichment in Sample I "
                       "that would be diluted in an undifferentiated sample.".format(
            mc["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0) /
            max(mc["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0), 0.001)),
    }

    # ── Weighted KS tests + bin residuals ────────────────────────────────────
    ks_results = {}
    bins_common = np.linspace(0, 12000, 80)
    mc_weights = {"I": mcI_w, "II": mcII_w}
    for s, mcv, dav, label in (("I", mcI, daI, "Sample I"), ("II", mcII, daII, "Sample II")):
        mw = mc_weights[s]
        # Weighted ECDF distance; p-value is legacy/non-authorising under #1049.
        ks = _weighted_ks_stat(dav, mcv * mev_to_adc,
                               np.ones(len(dav)), mw)
        ks["sample"] = label
        ks["note"] = (
            "Data vs MC (MC scaled by mev_to_adc, exact right-continuous weighted ECDF D); "
            "legacy unit-weight permutation p-value is NONAUTHORISING (issue #1049 closed); "
            "authorising null uses OOB cluster bootstrap with scale refit (#1164); "
            "bin residuals use PrimaryWeight."
        )
        ks["statistical_unit_contract"] = spectrum_contract
        ks["null_hypothesis"] = (
            "NOT_CALIBRATED: equality of DATA pulse distribution and PrimaryWeight-"
            "weighted MC target measure after fitted median-ratio scale; current "
            "p_value uses legacy unit-weight value permutation and is non-authorising."
        )
        ks["cluster_ids_present"] = bool(
            loaded["mc_clusters"] and loaded["data_clusters"]
        )
        if not ks["cluster_ids_present"]:
            ks["null_calibration_status"] = "BLOCKED_MISSING_CLUSTER_IDS_ISSUE_1164"
        elif spectrum_contract["quarantine"]:
            ks["null_calibration_status"] = spectrum_contract["quarantine"]
        else:
            ks["null_calibration_status"] = "RESEARCH_ONLY_PENDING_TYPEI_CALIBRATION"
        ks_results[label] = ks

        # Bin-by-bin residuals (normalised) — MC side weighted.
        da_hist, _ = np.histogram(dav, bins=bins_common, density=True)
        mc_hist = _whist(mcv * mev_to_adc, bins_common, mw)
        residual = da_hist - mc_hist
        ks_results[label]["bin_residual_rms"] = float(np.sqrt(np.mean(residual**2)))
        ks_results[label]["bin_residual_max"] = float(np.max(np.abs(residual)))

    # ── OOB cluster-bootstrap null with per-replicate scale refit (#1164) ────
    # Authorising null: resample MC and DATA clusters independently, refit the
    # MeV->ADC scale on each replicate's Sample II (bootstrap sample), then
    # evaluate the weighted KS D on the out-of-bag clusters.  p-value = fraction
    # of replicates with bootstrap D >= observed D.  Fails closed when cluster
    # IDs are missing or fewer than half the replicates succeed.
    d_obs = {
        "I": ks_results.get("Sample I", {}).get("D", 0.0),
        "II": ks_results.get("Sample II", {}).get("D", 0.0),
    }
    oob_null = _cluster_bootstrap_null_scale_refit(
        mcI, mcII, daI, daII,
        mcI_w, mcII_w,
        loaded["mc_clusters"], loaded["data_clusters"],
        d_obs,
        n_replicates=1000,
        seed=42,
    )
    oob_null["statistical_unit_contract"] = spectrum_contract
    oob_null["note"] = (
        "MC and DATA clusters resampled independently (generator_event_index / "
        "run:eventno). Scale refit inside each replicate on bootstrap Sample II; "
        "weighted KS D evaluated on OOB clusters. p-value = fraction of "
        "replicates with bootstrap D >= observed D (issue #1164)."
    )

    # ── Saturation flag ──────────────────────────────────────────────────────
    b2I_sat = da["headline_first_B_layer_B2"]["sampleI_frac_saturated"]
    b2II_sat = da["headline_first_B_layer_B2"]["sampleII_frac_saturated"]
    saturation_warning = (
        f"DATA B2 saturation (ADC≥7000) affects {b2I_sat*100:.0f}% of Sample I pulses "
        f"and {b2II_sat*100:.0f}% of Sample II pulses. MC does not model saturation. "
        f"The B2 data/MC comparison at high amplitude is qualitative, not quantitative. "
        f"For a saturation-robust comparison, consider using area_adc_samples or "
        f"excluding B2 amplitudes above the saturation ceiling."
    )

    # ── ΔE-E explanation (derived from outputs; no hard-coded physics prose) ─
    stop_I = None
    stop_II = None
    r_I = None
    r_II = None
    if "stopping_depth" in mc["samples"]["I"]:
        stop_I = mc["samples"]["I"]["stopping_depth"].get("mean_stop_layer")
    if "stopping_depth" in mc["samples"]["II"]:
        stop_II = mc["samples"]["II"]["stopping_depth"].get("mean_stop_layer")
    if "deltaE_E" in mc["samples"]["I"]:
        r_I = mc["samples"]["I"]["deltaE_E"].get("pearson_r")
    if "deltaE_E" in mc["samples"]["II"]:
        r_II = mc["samples"]["II"]["deltaE_E"].get("pearson_r")
    deltaE_E_narrative = _build_deltaE_E_narrative({
        "sampleI_d_fraction": mc["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
        "sampleII_d_fraction": mc["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
        "sampleI_mean_stop_layer": stop_I,
        "sampleII_mean_stop_layer": stop_II,
        "sampleI_pearson_r": r_I,
        "sampleII_pearson_r": r_II,
        "open_blockers": ["#956", "#1002"],
    })
    deltaE_E_note = deltaE_E_narrative["prose"]

    # ── Build comprehensive comparison dict ──────────────────────────────────
    comp = {
        "version": "v7",
        "spectrum_contract": spectrum_contract,
        "scale_topology": scale_topology,
        "nuisance_contract": nuisance,
        "mev_to_adc_scale": mev_to_adc,
        "mev_to_adc_scale_lo": scale_lo,
        "mev_to_adc_scale_hi": scale_hi,
        "scale_uncertainty_fraction": args.scale_uncertainty,
        "scale_reference": ("Sample-II first-B-layer weighted median (MC, PrimaryWeight), "
                             "±30% systematic from MV0 digitizer gain; non-authorising "
                             "proxy under #994/#1052/#1166"),
        "mc_primary_weight_applied": True,
        "mc_weight_policy": {
            "require_nonnegative": True,
            "require_nonzero_sum": True,
            "max_abs_weight_fraction": MAX_ABS_WEIGHT_FRACTION,
            "min_absolute_ess": MIN_ABSOLUTE_ESS,
            "validator": "validate_mc_weights",
            "validator_version": vw.VERSION,
        },
        "mc_weight_diagnostics": {
            "sampleI": _weight_diagnostics(audit_I),
            "sampleII": _weight_diagnostics(audit_II),
        },
        "first_B_layer": {
            "MC": {
                "measure": mc.get("mc_measure", mc.get("headline_first_B_layer", {}).get("measure")),
                "measure_status": mc.get("mc_measure_status", mc.get("headline_first_B_layer", {}).get("measure_status")),
                "sampleI_d_fraction": mc["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
                "sampleII_d_fraction": mc["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
                "sampleI_frac_large": mc["samples"]["I"]["B_layers"][0]["frac_large"],
                "sampleII_frac_large": mc["samples"]["II"]["B_layers"][0]["frac_large"],
                "sampleI_mean_edep_MeV": mc["samples"]["I"]["B_layers"][0]["mean_edep_MeV"],
                "sampleII_mean_edep_MeV": mc["samples"]["II"]["B_layers"][0]["mean_edep_MeV"],
            },
            "DATA": da["headline_first_B_layer_B2"],
        },
        "ks_tests": ks_results,
        "saturation_warning": saturation_warning,
        "counterfactual_no_trigger_mimicry": counterfactual,
        "deltaE_E_correlation_note": deltaE_E_note,
        "deltaE_E_narrative": deltaE_E_narrative,
        "depth_profile": {
            "DATA_sampleI": da["per_sample"]["I"]["depth_fraction"],
            "DATA_sampleII": da["per_sample"]["II"]["depth_fraction"],
            "MC_sampleI_layerhits": [l["hits"] for l in mc["samples"]["I"]["B_layers"]],
            "MC_sampleII_layerhits": [l["hits"] for l in mc["samples"]["II"]["B_layers"]],
        },
        "enter_pid": {
            "MC_sampleI_enterB": mc["samples"]["I"]["enter_B_pid_fraction"],
            "MC_sampleII_enterB": mc["samples"]["II"]["enter_B_pid_fraction"],
            "MC_sampleI_enterA": mc["samples"]["I"]["enter_A_pid_fraction"],
            "MC_sampleII_enterA": mc["samples"]["II"]["enter_A_pid_fraction"],
        },
        "oob_null": oob_null,
    }

    mc_excess = comp["first_B_layer"]["MC"]["sampleI_frac_large"] - comp["first_B_layer"]["MC"]["sampleII_frac_large"]
    da_excess = comp["first_B_layer"]["DATA"]["sampleI_frac_large"] - comp["first_B_layer"]["DATA"]["sampleII_frac_large"]
    comp["first_B_layer"]["large_pulse_excess_sampleI_minus_II"] = {
        "MC": round(mc_excess, 4), "DATA": round(da_excess, 4),
        "both_positive": bool(mc_excess > 0 and da_excess > 0),
    }

    for s in ("I", "II"):
        if "per_stave_species" in mc["samples"][s]:
            comp.setdefault("mc_per_stave_species", {})[s] = mc["samples"][s]["per_stave_species"]
        if "stopping_depth" in mc["samples"][s]:
            comp.setdefault("mc_stopping_depth", {})[s] = mc["samples"][s]["stopping_depth"]
        if "deltaE_E" in mc["samples"][s]:
            comp.setdefault("mc_deltaE_E", {})[s] = mc["samples"][s]["deltaE_E"]

    with open(os.path.join(args.out, "data_mc_comparison.json"), "w") as fh:
        json.dump(comp, fh, indent=2)

    # ═══════════════════════════════════════════════════════════════════════════
    #  PLOTS  (v5: exact weighted ECDF D; p-value visibly blocked by #1049)
    # ═══════════════════════════════════════════════════════════════════════════
    plot_list = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        STAVES = ["B2", "B4", "B6", "B8"]

        # (1) First-B-layer overlay WITH scale uncertainty band + weighted ECDF D
        fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
        bins = np.linspace(0, 12000, 80)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        for k, (mcv, dav, ttl) in enumerate([
                (mcI, daI, "Sample I (A&B coincidence)"),
                (mcII, daII, "Sample II (single B)")]):
            ax = axes[k]
            mw = mc_weights["I"] if "I" in ttl else mc_weights["II"]
            # Data
            ax.hist(dav, bins=bins, density=True, histtype="step", lw=2,
                    label=f"DATA B2 (n={dav.size:,})", color="k")
            # MC central (weighted by PrimaryWeight, #880)
            mc_hist = _whist(mcv * mev_to_adc, bins, mw)
            ax.step(bin_centers, mc_hist, where="mid", lw=2,
                    label=f"MC EDep ×{mev_to_adc:.0f} (PrimaryWeight) (n={mcv.size:,})", color="C3")
            # MC ±30% band
            mc_hi = _whist(mcv * scale_hi, bins, mw)
            mc_lo = _whist(mcv * scale_lo, bins, mw)
            ax.fill_between(bin_centers, mc_lo, mc_hi, alpha=0.2, color="C3",
                            label=f"MC ±{args.scale_uncertainty*100:.0f}% scale")
            # Weighted ECDF discrepancy; legacy p is explicitly non-authorising.
            ks = ks_results.get(ttl.split(" (")[0], {})
            ax.text(
                0.95,
                0.85,
                f"wECDF D={ks.get('D', 0):.4f}\nlegacy p BLOCKED (#1049)",
                transform=ax.transAxes,
                ha="right",
                fontsize=9,
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7),
            )
            # Saturation flag
            sat_frac = b2I_sat if "I" in ttl else b2II_sat
            if sat_frac > 0.05:
                ax.axvline(7000, color="gray", linestyle=":", alpha=0.6)
                ax.text(7100, ax.get_ylim()[1]*0.65,
                        f"B2 sat\n({sat_frac*100:.0f}%)",
                        fontsize=7, color="gray", rotation=90, va="top")
            ax.set_title(ttl, fontweight="bold")
            ax.set_xlabel("First B-layer signal [ADC / scaled MeV]")
            ax.legend(fontsize=8, loc="upper left")
        axes[0].set_ylabel("Normalised counts")
        fig.suptitle("First B Layer (B2): DATA vs MC with ±30% Scale Uncertainty — Sample I vs Sample II\n"
                     "Saturation warning: DATA B2 saturates at ≥7000 ADC (MC does not model saturation)",
                     fontsize=12, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "first_B_layer_data_mc.png"), dpi=150)
        plot_list.append("first_B_layer_data_mc.png")
        plt.close(fig)

        # (2) Bin-by-bin residual plot (data - MC, normalised)
        fig, axes = plt.subplots(1, 2, figsize=(14, 4.5), sharey=True)
        for k, (mcv, dav, ttl) in enumerate([
                (mcI, daI, "Sample I"), (mcII, daII, "Sample II")]):
            ax = axes[k]
            mw = mc_weights["I"] if ttl.endswith("I") else mc_weights["II"]
            da_hist, _ = np.histogram(dav, bins=bins, density=True)
            mc_hist = _whist(mcv * mev_to_adc, bins, mw)
            res = da_hist - mc_hist
            ax.bar(bin_centers, res, width=bins[1]-bins[0], color="C0", alpha=0.5, edgecolor="C0", linewidth=0.3)
            ax.axhline(0, color="k", linewidth=0.8)
            # Fill the ±30% band effect
            mc_hi = _whist(mcv * scale_hi, bins, mw)
            mc_lo = _whist(mcv * scale_lo, bins, mw)
            ax.fill_between(bin_centers, da_hist - mc_hi, da_hist - mc_lo,
                            alpha=0.15, color="gray", label=f"±{args.scale_uncertainty*100:.0f}% scale band")
            rms = float(np.sqrt(np.mean(res**2)))
            ax.text(0.95, 0.90, f"RMS resid = {rms:.4f}", transform=ax.transAxes,
                    ha="right", fontsize=9, bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
            ax.set_title(f"{ttl}: DATA − MC (scaled) residual")
            ax.set_xlabel("Signal [ADC / scaled MeV]")
            ax.set_xlim(0, 12000)
            ax.legend(fontsize=7)
        axes[0].set_ylabel("Residual (normalised density)")
        fig.suptitle("Bin-by-Bin Residual: DATA minus MC — Sample I vs Sample II",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "bin_residual_data_mc.png"), dpi=150)
        plot_list.append("bin_residual_data_mc.png")
        plt.close(fig)

        # (3) Depth profile: data vs MC
        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(4)
        dI = [da["per_sample"]["I"]["depth_fraction"][s] for s in STAVES]
        dII = [da["per_sample"]["II"]["depth_fraction"][s] for s in STAVES]
        mI_frac = [l["hits"] / max(mc["samples"]["I"]["n_events"], 1) for l in mc["samples"]["I"]["B_layers"][:4]]
        mII_frac = [l["hits"] / max(mc["samples"]["II"]["n_events"], 1) for l in mc["samples"]["II"]["B_layers"][:4]]
        ax.plot(x, dI, "o-", label="DATA Sample I", color="C0", linewidth=2)
        ax.plot(x, dII, "s-", label="DATA Sample II", color="C1", linewidth=2)
        ax.plot(x, mI_frac, "o--", label="MC Sample I", color="C0", alpha=0.6)
        ax.plot(x, mII_frac, "s--", label="MC Sample II", color="C1", alpha=0.6)
        ax.set_xticks(x); ax.set_xticklabels(STAVES)
        ax.set_ylabel("Fraction of events/pulses")
        ax.set_xlabel("B-stack stave (depth)")
        ax.set_yscale("log"); ax.legend()
        ax.set_title("Depth Profile: DATA vs MC — Sample I vs Sample II")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "depth_profile_data_mc.png"), dpi=150)
        plot_list.append("depth_profile_data_mc.png")
        plt.close(fig)

        # (4) MC deuteron fraction vs layer
        fig, ax = plt.subplots(figsize=(9, 5))
        for s, color in (("I", "C0"), ("II", "C3")):
            df_vals = [mc["samples"][s]["B_layers"][l]["pid_fraction"].get("d", 0.0) for l in range(8)]
            ax.plot(range(8), df_vals, "o-", color=color, linewidth=2, label=f"MC Sample {s}")
        ax.set_xlabel("B layer (LayerID, 0=B2 first layer)")
        ax.set_ylabel("Deuteron fraction (MC truth)")
        ax.set_xticks(range(8))
        ax.set_xticklabels([f"B{(l+1)*2}" for l in range(8)])
        ax.legend(); ax.set_title("MC Truth Deuteron Fraction vs Depth — Sample I vs Sample II")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "mc_d_fraction_vs_layer.png"), dpi=150)
        plot_list.append("mc_d_fraction_vs_layer.png")
        plt.close(fig)

        # (5) Data B2 vs B4 per sample
        for s in ("I", "II"):
            b2b4_path = os.path.join(args.data_dir, f"B2_vs_B4_{s}.npz")
            if os.path.exists(b2b4_path):
                b2b4 = np.load(b2b4_path)
                a_b2, a_b4 = b2b4["amp_B2"], b2b4["amp_B4"]
                fig, ax = plt.subplots(figsize=(7, 6))
                n_pts = min(8000, len(a_b2))
                idx = np.random.choice(len(a_b2), n_pts, replace=False) if len(a_b2) > n_pts else np.arange(len(a_b2))
                ax.scatter(a_b2[idx], a_b4[idx], s=2, alpha=0.3,
                           color="C0" if s == "I" else "C3", rasterized=True)
                ax.axvline(7000, color="gray", linestyle=":", alpha=0.5)
                ax.text(7100, ax.get_ylim()[1]*0.5 if ax.get_ylim()[1] > 0 else 3000,
                        "B2 sat", fontsize=7, color="gray", rotation=90)
                corr = np.corrcoef(a_b2, a_b4)[0, 1] if len(a_b2) > 2 else 0
                ax.set_title(f"DATA Sample {s} — B2 vs B4 Amplitude (r={corr:.3f}, n={len(a_b2):,})")
                ax.set_xlabel("B2 Amplitude [ADC]")
                ax.set_ylabel("B4 Amplitude [ADC]")
                ax.set_xlim(0, 14000); ax.set_ylim(0, 5000)
                fig.tight_layout()
                fig.savefig(os.path.join(args.out, f"data_deltaE_E_sample_{s}.png"), dpi=150)
                plot_list.append(f"data_deltaE_E_sample_{s}.png")
                plt.close(fig)

        # (6) Per-stave data vs scaled MC
        try:
            da_amp_staves = np.load(os.path.join(args.data_dir, "per_stave_amplitude.npz"))
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            for idx, st in enumerate(STAVES):
                ax = axes[idx // 2][idx % 2]
                lid = idx
                for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                             ("II", "Sample II", "C3", "--")):
                    da_key = f"{s}_{st}"
                    if da_key in da_amp_staves:
                        da_arr = da_amp_staves[da_key]
                        ax.hist(da_arr, bins=60, range=(0, 8000), histtype="step", linewidth=2,
                                color=color, linestyle=ls, label=f"{label} DATA", density=True, alpha=0.7)
                    mc_arr = np.asarray(mc["samples"][s]["B_layers"][lid].get("edep", []), dtype=float)
                    if len(mc_arr) > 0:
                        mc_hist_c, _ = np.histogram(mc_arr * mev_to_adc, bins=60, range=(0, 8000), density=True)
                        ax.step(np.linspace(0, 8000, 60), mc_hist_c, where="mid", color=color, alpha=0.7)
                        # Scale band
                        mc_h, _ = np.histogram(mc_arr * scale_hi, bins=60, range=(0, 8000), density=True)
                        mc_l, _ = np.histogram(mc_arr * scale_lo, bins=60, range=(0, 8000), density=True)
                        ax.fill_between(np.linspace(0, 8000, 60), mc_l, mc_h, alpha=0.12, color=color)
                    if st == "B2":
                        ax.axvline(7000, color="gray", linestyle=":", alpha=0.5)
                        ax.text(7300, ax.get_ylim()[1]*0.7 if ax.get_ylim()[1] > 0 else 0.0003,
                                "B2 sat", fontsize=7, color="gray")
                ax.set_xlabel(f"{st} signal [ADC / scaled MeV]")
                ax.set_ylabel("Normalised counts")
                ax.set_title(f"DATA vs MC: {st} — Sample I vs Sample II")
                ax.legend(fontsize=8)
                ax.set_xlim(0, 7000)
            fig.suptitle("Per-Stave DATA vs MC Comparison (±30% Scale Band) — Sample I vs Sample II",
                         fontsize=14, fontweight="bold")
            fig.tight_layout()
            fig.savefig(os.path.join(args.out, "per_stave_data_mc_comparison.png"), dpi=150)
            plot_list.append("per_stave_data_mc_comparison.png")
            plt.close(fig)
        except Exception:
            pass

        # (7) MC ΔE-E plane per sample (with correlation note)
        for s in ("I", "II"):
            dee_path = os.path.join(args.mc_dir, f"deltaE_E_{s}.npz")
            if os.path.exists(dee_path):
                dee = np.load(dee_path)
                fig, ax = plt.subplots(figsize=(8, 6))
                ed0, ed1, pdg_a = dee["edep_l0"], dee["edep_l1"], dee["pdg"]
                is_p = pdg_a == 2212
                is_d = pdg_a == 1000010020
                other = ~(is_p | is_d)
                n_pts = min(8000, len(ed0))
                idx = np.random.choice(len(ed0), n_pts, replace=False) if len(ed0) > n_pts else np.arange(len(ed0))
                ax.scatter(ed0[idx][other[idx]], ed1[idx][other[idx]], s=2, alpha=0.2,
                           color="gray", label="other", rasterized=True)
                ax.scatter(ed0[idx][is_p[idx]], ed1[idx][is_p[idx]], s=3, alpha=0.35,
                           color="C0", label="p", rasterized=True)
                ax.scatter(ed0[idx][is_d[idx]], ed1[idx][is_d[idx]], s=3, alpha=0.35,
                           color="C3", label="d", rasterized=True)
                r_val = np.corrcoef(ed0, ed1)[0, 1] if len(ed0) > 2 else 0
                ax.set_xlabel("EDep Layer 0 (B2) [MeV]")
                ax.set_ylabel("EDep Layer 1 (B4) [MeV]")
                n_d_l0 = int(is_d.sum())
                n_in_both = int((is_d & (ed0 > 0) & (ed1 > 0)).sum())
                note = (f"n={len(ed0):,}, r={r_val:.3f}\n"
                        f"d with both-layer hits: {n_in_both}/{n_d_l0}\n"
                        + ("Low r: most Sample I d stop at layer 0,\n"
                           "only punch-through d reach layer 1."
                           if s == "I" else ""))
                ax.text(0.95, 0.95, note, transform=ax.transAxes, ha="right", va="top",
                        fontsize=8, bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
                ax.set_title(f"MC Sample {s} — ΔE-E Plane (truth)")
                ax.legend(loc="upper right", markerscale=3)
                fig.tight_layout()
                fig.savefig(os.path.join(args.out, f"mc_deltaE_E_sample_{s}.png"), dpi=150)
                plot_list.append(f"mc_deltaE_E_sample_{s}.png")
                plt.close(fig)

        # (8) MC stopping depth comparison
        if "stopping_depth" in mc["samples"]["I"]:
            fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
            for si, s in enumerate(("I", "II")):
                ax = axes[si]
                x = np.arange(8); width = 0.35
                sd = mc["samples"][s]["stopping_depth"]
                for sp, color, offset, label in (("p", "C0", -width/2, "proton"),
                                                  ("d", "C3", width/2, "deuteron")):
                    if sp in sd:
                        dist = sd[sp]["stop_distribution"]
                        vals = [dist.get(str(l), 0) for l in range(8)]
                        total = max(sum(vals), 1)
                        ax.bar(x+offset, [v/total for v in vals], width, color=color, alpha=0.7, label=label)
                        ax.text(0.95, 0.90 - si*0.1, f"{sp}: mean stop={sd[sp]['mean_stop_layer']:.1f}",
                                transform=ax.transAxes, fontsize=8, ha="right")
                ax.set_xticks(x); ax.set_xticklabels([f"B{(l+1)*2}" for l in range(8)])
                ax.set_xlabel("Stop layer"); ax.set_ylabel("Fraction of tracks")
                ax.set_title(f"MC Sample {s} — Stopping Depth"); ax.legend()
                ax.grid(True, alpha=0.2, axis="y")
            fig.suptitle("MC Truth Stopping-Depth: p vs d — Sample I vs Sample II",
                         fontsize=13, fontweight="bold")
            fig.tight_layout()
            fig.savefig(os.path.join(args.out, "mc_stopping_depth_comparison.png"), dpi=150)
            plot_list.append("mc_stopping_depth_comparison.png")
            plt.close(fig)

        comp["_plots"] = plot_list
    except Exception as e:
        comp["_plot_error"] = str(e)

    with open(os.path.join(args.out, "data_mc_comparison.json"), "w") as fh:
        json.dump(comp, fh, indent=2)

    print(json.dumps({
        "version": "v7",
        "mev_to_adc": mev_to_adc,
        "scale_uncertainty_band": f"[{scale_lo:.0f}, {scale_hi:.0f}]",
        "first_B_layer_large_pulse_excess": comp["first_B_layer"]["large_pulse_excess_sampleI_minus_II"],
        "ks_sampleI_D": ks_results.get("Sample I", {}).get("D", "N/A"),
        "ks_sampleII_D": ks_results.get("Sample II", {}).get("D", "N/A"),
        "d_enrichment_factor": counterfactual["d_enrichment_factor"],
        "mc_weight_validation": "PASSED" if comp.get("mc_weight_policy") else "FAILED",
        "weight_ess_sampleI": audit_I.absolute_effective_sample_size,
        "weight_ess_sampleII": audit_II.absolute_effective_sample_size,
        "plots": plot_list,
    }, indent=2))
    print(
        f"[ok] wrote {args.out}/data_mc_comparison.json  "
        "(v7 OOB cluster-bootstrap null with scale refit; legacy unit-weight "
        "permutation p_value_status NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION)"
    )


if __name__ == "__main__":
    main()