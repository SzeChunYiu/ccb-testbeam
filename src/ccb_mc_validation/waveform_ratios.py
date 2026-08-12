"""Versioned waveform late/peak-to-area ratio contract (#1100).

Never project a nonpositive signed area onto a small positive epsilon. Invalid
denominators become NaN (typed invalid) rather than O(10^6) artifacts.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import numpy as np

CONTRACT_VERSION = "2026.0-waveB-lane03-waveform-ratio-v1"
AREA_EPS = 1e-3  # relative to typical |area|; not an absolute physics constant


def signed_area_validity(
    area_signed: np.ndarray,
    *,
    area_eps: float = AREA_EPS,
    area_scale: Optional[float] = None,
) -> np.ndarray:
    """Boolean mask: signed-area denominator is physically usable."""
    area_signed = np.asarray(area_signed, dtype=np.float64)
    if area_scale is None:
        finite = area_signed[np.isfinite(area_signed)]
        area_scale = float(np.median(np.abs(finite))) if finite.size else 1.0
    return np.abs(area_signed) > float(area_eps) * max(1.0, float(area_scale))


def late_and_peak_ratios(
    waveforms: np.ndarray,
    *,
    late_start: int = 12,
    area_eps: float = AREA_EPS,
    normalize_by: Optional[np.ndarray] = None,
) -> dict[str, np.ndarray]:
    """Compute versioned late-fraction / peak-to-area features.

    Parameters
    ----------
    waveforms:
        Shape (n, n_samples). If ``normalize_by`` is given, features are
        computed on ``waveforms / normalize_by[:, None]``.
    late_start:
        First sample index of the late window (inclusive).
    """
    w = np.asarray(waveforms, dtype=np.float64)
    if w.ndim != 2:
        raise ValueError(f"waveforms must be 2-D, got shape {w.shape}")
    if normalize_by is not None:
        amp = np.asarray(normalize_by, dtype=np.float64)
        if amp.shape != (w.shape[0],):
            raise ValueError("normalize_by must have shape (n_pulses,)")
        # Fail closed on non-positive amplitude for amplitude-normalised ratios.
        bad_amp = ~(np.isfinite(amp) & (np.abs(amp) > 0.0))
        norm = np.full_like(w, np.nan)
        good = ~bad_amp
        norm[good] = w[good] / amp[good, None]
    else:
        norm = w

    area_signed = np.nansum(norm, axis=1)
    area_positive = np.nansum(np.maximum(norm, 0.0), axis=1)
    area_abs = np.nansum(np.abs(norm), axis=1)
    tail_signed = np.nansum(norm[:, late_start:], axis=1)
    tail_positive = np.nansum(np.maximum(norm[:, late_start:], 0.0), axis=1)
    tail_abs = np.nansum(np.abs(norm[:, late_start:]), axis=1)

    ok = signed_area_validity(area_signed, area_eps=area_eps)
    late_signed = np.full(len(norm), np.nan, dtype=np.float64)
    peak_to_area = np.full(len(norm), np.nan, dtype=np.float64)
    late_signed[ok] = tail_signed[ok] / area_signed[ok]
    peak_to_area[ok] = 1.0 / area_signed[ok]

    # Positive / abs fractions: defined when denominator > 0; else NaN.
    late_positive = np.full(len(norm), np.nan, dtype=np.float64)
    late_abs = np.full(len(norm), np.nan, dtype=np.float64)
    pos_ok = area_positive > 0.0
    abs_ok = area_abs > 0.0
    late_positive[pos_ok] = tail_positive[pos_ok] / area_positive[pos_ok]
    late_abs[abs_ok] = tail_abs[abs_ok] / area_abs[abs_ok]

    return {
        "contract_version": np.array([CONTRACT_VERSION] * len(norm), dtype=object),
        "area_signed": area_signed,
        "area_positive": area_positive,
        "area_abs": area_abs,
        "denominator_valid_signed": ok.astype(bool),
        "late_signed_fraction_v1": late_signed,
        "peak_to_area_signed_v1": peak_to_area,
        "late_positive_fraction_v1": late_positive,
        "late_abs_fraction_v1": late_abs,
    }


def assert_no_epsilon_projection(area: np.ndarray, ratio: np.ndarray) -> None:
    """Adversarial check: nonpositive area must not yield a finite fabricated ratio."""
    area = np.asarray(area, dtype=np.float64)
    ratio = np.asarray(ratio, dtype=np.float64)
    bad = (area <= 0) & np.isfinite(ratio) & (np.abs(ratio) > 1e3)
    if np.any(bad):
        raise AssertionError(
            "epsilon-projection pathology detected: nonpositive area produced "
            f"|ratio|>1e3 at indices {np.where(bad)[0][:10]}"
        )
