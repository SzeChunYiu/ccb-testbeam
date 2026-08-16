#!/usr/bin/env python3
"""Deterministic robustness diagnostics for the first-local CFD selector.

This module studies the *software selector* under bounded waveform perturbations.
It does not encode a measured CCB noise model and does not authorize a physical
pulse-component identity (#1059).
"""
from __future__ import annotations

import numpy as np

import digital_cfd

STABILITY_PROFILE = "first_local_peak_linf_sufficient_radius_v1"
STABILITY_STATUS = "DETERMINISTIC_SOFTWARE_BOUND_NONAUTHORISING"


def _failed_predicate_radius(
    y: np.ndarray,
    index: int,
    *,
    floor: float,
    alpha: float,
) -> float:
    """Largest sufficient radius keeping one current eligibility failure true.

    A candidate is ineligible when at least one of the three selector predicates
    fails.  Under an arbitrary additive perturbation with ``||delta||_inf < eps``:

    * a floor deficit ``floor-y[k]`` can shrink by at most ``(1+alpha)*eps``;
    * either neighbour-order deficit can shrink by at most ``2*eps``.

    Keeping *any one* failed predicate false is enough to keep the candidate
    ineligible, hence the maximum of the available per-predicate certificates.
    """
    failures: list[float] = []
    value = float(y[index])
    if value < floor:
        failures.append((floor - value) / (1.0 + alpha))
    if value < float(y[index - 1]):
        failures.append((float(y[index - 1]) - value) / 2.0)
    if value < float(y[index + 1]):
        failures.append((float(y[index + 1]) - value) / 2.0)
    if not failures:
        return 0.0
    return float(max(failures))


def _argmax_identity_radius(y: np.ndarray, index: int) -> float:
    """Sufficient L-infinity radius preserving a unique argmax index."""
    if y.size <= 1:
        return float("inf")
    value = float(y[index])
    others = np.delete(y, index)
    second = float(np.max(others))
    gap = value - second
    return float(max(0.0, gap / 2.0))


def first_local_peak_linf_stability_diagnostics(
    waveforms: np.ndarray,
    *,
    min_prominence_frac: float = digital_cfd.FIRST_LOCAL_PEAK_DEFAULT_FLOOR_FRAC,
) -> dict[str, object]:
    """Return a sufficient exact-selected-index L-infinity robustness radius.

    The selector is the named non-authorising profile implemented by
    :func:`digital_cfd.first_local_peak_diagnostics`.  For each waveform this
    function returns ``identity_radius_adc`` such that every arbitrary additive
    sample-wise perturbation satisfying

    ``||delta||_inf < identity_radius_adc``

    is guaranteed to preserve the selected sample index under the same selector
    law.  The bound is sufficient, not necessary; a zero radius means only that
    this certificate cannot guarantee robustness (for example, a plateau).

    The output units are the waveform amplitude units (ADC-like analysis units
    in the current real-data producer).  No stochastic probability or detector
    calibration is inferred from this deterministic bound.
    """
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")

    selector = digital_cfd.first_local_peak_diagnostics(
        wave,
        min_prominence_frac=min_prominence_frac,
    )
    alpha = float(selector["global_fraction_floor"])
    selected = np.asarray(selector["selected_peak_indices"], dtype=int)
    global_indices = np.asarray(selector["global_peak_indices"], dtype=int)
    global_amplitudes = np.asarray(selector["global_amplitudes"], dtype=float)
    floors = np.asarray(selector["selection_floors"], dtype=float)
    selection_statuses = np.asarray(selector["statuses"], dtype=object)

    n = wave.shape[0]
    identity_radius = np.zeros(n, dtype=float)
    selected_floor_radius = np.full(n, np.nan, dtype=float)
    selected_left_radius = np.full(n, np.nan, dtype=float)
    selected_right_radius = np.full(n, np.nan, dtype=float)
    earlier_exclusion_radius = np.full(n, np.nan, dtype=float)
    interior_exclusion_radius = np.full(n, np.nan, dtype=float)
    argmax_radius = np.full(n, np.nan, dtype=float)
    certificate_status = np.full(n, "INVALID_SELECTOR_STATE", dtype=object)

    for i in range(n):
        y = wave[i]
        j = int(selected[i])
        global_amp = float(global_amplitudes[i])
        floor = float(floors[i])
        if (
            j < 0
            or not np.isfinite(global_amp)
            or global_amp <= 0.0
            or not np.all(np.isfinite(y))
        ):
            continue

        status = str(selection_statuses[i])
        if status == digital_cfd.SELECT_LOCAL_ABOVE_GLOBAL_FLOOR:
            if not (0 < j < y.size - 1):
                continue
            selected_floor_radius[i] = max(
                0.0,
                (float(y[j]) - floor) / (1.0 + alpha),
            )
            selected_left_radius[i] = max(
                0.0,
                (float(y[j]) - float(y[j - 1])) / 2.0,
            )
            selected_right_radius[i] = max(
                0.0,
                (float(y[j]) - float(y[j + 1])) / 2.0,
            )

            earlier: list[float] = []
            for k in range(1, j):
                earlier.append(
                    _failed_predicate_radius(y, k, floor=floor, alpha=alpha)
                )
            earlier_exclusion_radius[i] = (
                float(min(earlier)) if earlier else float("inf")
            )
            identity_radius[i] = float(
                min(
                    selected_floor_radius[i],
                    selected_left_radius[i],
                    selected_right_radius[i],
                    earlier_exclusion_radius[i],
                )
            )
            certificate_status[i] = "LOCAL_SELECTED_SUFFICIENT_RADIUS"
            continue

        if status == digital_cfd.SELECT_FALLBACK_GLOBAL:
            interior: list[float] = []
            for k in range(1, max(1, y.size - 1)):
                if k >= y.size - 1:
                    break
                interior.append(
                    _failed_predicate_radius(y, k, floor=floor, alpha=alpha)
                )
            interior_exclusion_radius[i] = (
                float(min(interior)) if interior else float("inf")
            )
            g = int(global_indices[i])
            if g < 0:
                continue
            argmax_radius[i] = _argmax_identity_radius(y, g)
            identity_radius[i] = float(
                min(interior_exclusion_radius[i], argmax_radius[i])
            )
            certificate_status[i] = "FALLBACK_GLOBAL_SUFFICIENT_RADIUS"

    return {
        "profile_id": STABILITY_PROFILE,
        "evidence_status": STABILITY_STATUS,
        "authorising_component_identity": False,
        "norm": "L_INFINITY_ADDITIVE_SAMPLE_PERTURBATION",
        "strict_inequality": True,
        "global_fraction_floor": alpha,
        "selected_peak_indices": selected,
        "selection_statuses": selection_statuses,
        "identity_radius_adc": identity_radius,
        "selected_floor_radius_adc": selected_floor_radius,
        "selected_left_radius_adc": selected_left_radius,
        "selected_right_radius_adc": selected_right_radius,
        "earlier_exclusion_radius_adc": earlier_exclusion_radius,
        "interior_exclusion_radius_adc": interior_exclusion_radius,
        "argmax_radius_adc": argmax_radius,
        "certificate_statuses": certificate_status,
    }
