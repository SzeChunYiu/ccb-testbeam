"""Versioned raw-waveform pedestal/amplitude selector (Issue #1109).

The S00 pipeline historically embedded a *single* pedestal estimator inline in
``scripts/01_build_pulse_table_from_root.py``: ``pedestal = median(w[0:4])``
(the "first-four median" gate). Issue #1109 establishes that this gate can
censor genuine pulses before timing/topology analysis: when an early/recovery/
bipolar waveform raises or lowers the first four samples, ``A4 = max(w) - b4``
is biased low and a real pulse can fall under the selection cut.

This module makes the selector *versioned and self-describing*:

- ``S00_selector_v1`` is the historical first-four-median gate, frozen and
  immutable, so downstream count reproduction is never silently changed.
- Candidate estimators carry an explicit :class:`PedestalValidity` state and a
  declared validity domain, so a waveform class is never silently censored —
  it is either accepted as valid or explicitly classified into a failure state
  (``EARLY_ACTIVE``, ``RECOVERY_CONTAMINATED``, ``BIPOLAR_OR_POLARITY_UNKNOWN``,
  ``JAGGED``, ``SATURATED``, ``NO_PEDESTAL_IDENTIFIABLE``).

Design contract (acceptance criteria from the issue):

1. Hardware evidence decides whether samples 0-3 are quiet; this module only
   *classifies* waveform shape and exposes the states, it does not fabricate
   hardware evidence.
2. Every record rejected by one selector but accepted by another is
   decomposable by mechanism (H1-H8) via :func:`classify_pedestal_validity`.
3. Estimators are pure functions over a waveform array, so they are testable
   against known-answer fixtures without raw ROOT data.
4. The historical selector is preserved as one exact mathematical map under
   ``v1``; candidate estimators are additive and never replace it in the
   canonical count path until a migration decision is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from numbers import Integral
from typing import Iterable

import numpy as np


S00_SELECTOR_V1_ID = "v1_first_four_median"
S00_SELECTOR_V1_BASELINE_INDICES = (0, 1, 2, 3)


class SelectorInputError(ValueError):
    """Controlled failure for inputs outside a named selector's valid domain."""


def _validate_v1_baseline_indices(
    baseline_indices: Iterable[int] | None,
) -> tuple[int, int, int, int]:
    """Return the frozen v1 baseline tuple or reject any semantic mutation.

    The optional argument is retained only for backwards-compatible call sites.
    It is an assertion of the named model identity, not a free selector
    parameter. Alternate baseline windows require a separately versioned model.
    Only true integral index values are accepted: booleans and numerically equal
    floating-point aliases are rejected so type coercion cannot bypass the
    semantic identity check.
    """
    if baseline_indices is None:
        return S00_SELECTOR_V1_BASELINE_INDICES
    try:
        raw_indices = tuple(baseline_indices)
    except TypeError as exc:
        raise SelectorInputError(
            "v1 baseline indices must be exactly (0, 1, 2, 3)"
        ) from exc
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral)
        for value in raw_indices
    ):
        raise SelectorInputError(
            "v1 baseline indices must be integral values exactly (0, 1, 2, 3)"
        )
    indices = tuple(int(value) for value in raw_indices)
    if indices != S00_SELECTOR_V1_BASELINE_INDICES:
        raise SelectorInputError(
            f"{S00_SELECTOR_V1_ID} is frozen to baseline indices "
            f"{S00_SELECTOR_V1_BASELINE_INDICES}; got {indices!r}. "
            "Use a separately versioned selector for another baseline window."
        )
    return S00_SELECTOR_V1_BASELINE_INDICES


def _validate_v1_waveforms(waveforms: np.ndarray, *, scalar: bool) -> np.ndarray:
    """Validate the closed numerical domain of the historical v1 map."""
    wave = np.asarray(waveforms, dtype=float)
    if scalar and wave.ndim != 1:
        raise SelectorInputError(
            f"{S00_SELECTOR_V1_ID} scalar input must be 1-D; got shape {wave.shape}"
        )
    if not scalar and wave.ndim < 1:
        raise SelectorInputError(
            f"{S00_SELECTOR_V1_ID} batched input needs a sample axis; got {wave.shape}"
        )
    if wave.shape[-1] < len(S00_SELECTOR_V1_BASELINE_INDICES):
        raise SelectorInputError(
            f"{S00_SELECTOR_V1_ID} needs at least four samples; got shape {wave.shape}"
        )
    if not np.isfinite(wave).all():
        raise SelectorInputError(
            f"{S00_SELECTOR_V1_ID} requires finite waveform samples"
        )
    return wave


class PedestalValidity(Enum):
    """Validity state of the pedestal region (first samples) of one waveform.

    These are the seven states Issue #1109 requires. ``QUIET_VALID`` is the only
    state in which the first-four pedestal estimate is trusted without further
    hardware evidence. Every other state is a *censoring diagnosis*: the
    waveform class is identified so the migration analysis can decompose
    selector discrepancies by mechanism instead of silently dropping records.
    """

    QUIET_VALID = "QUIET_VALID"
    """Samples 0-3 are quiet; the first-four pedestal is valid (H0 baseline)."""

    EARLY_ACTIVE = "EARLY_ACTIVE"
    """H1: an early pulse (samples 0-3) raises the pedestal, biasing A4 low."""

    RECOVERY_CONTAMINATED = "RECOVERY_CONTAMINATED"
    """H2: prior-pulse recovery / baseline relaxation contaminates the window."""

    BIPOLAR_OR_POLARITY_UNKNOWN = "BIPOLAR_OR_POLARITY_UNKNOWN"
    """H3: negative/bipolar pulse makes the polarity of the pedestal ambiguous."""

    JAGGED = "JAGGED"
    """H4: a single jagged/dropout ADC sample distorts the four-sample median."""

    SATURATED = "SATURATED"
    """H6: upper (or lower) saturation clips the waveform, capping computed A."""

    NO_PEDESTAL_IDENTIFIABLE = "NO_PEDESTAL_IDENTIFIABLE"
    """H5/H7/H8: ordinary noise / circular-buffer phase / overlapping pulses
    leave no identifiable quiet pedestal region."""


@dataclass
class PedestalResult:
    """Result of estimating the pedestal of one waveform.

    Attributes:
        method: identifier of the estimator that produced this result
            (e.g. ``"v1_first_four_median"``, ``"dynamic_range"``).
        validity: :class:`PedestalValidity` state of the pedestal region.
        pedestal_adc: estimated pedestal level (float) if one could be
            identified, else ``np.nan``.
        first_four_samples: the raw samples 0:4 used by the v1 estimator.
        full_waveform: the complete waveform (read-only reference).
    """

    method: str
    validity: PedestalValidity
    pedestal_adc: float = float("nan")
    first_four_samples: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=float)
    )
    full_waveform: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=float)
    )


@dataclass
class AmplitudeResult:
    """Result of computing a selected-pulse amplitude for one waveform.

    Attributes:
        method: estimator identifier.
        amplitude_adc: computed amplitude above the pedestal.
        pedestal: the :class:`PedestalResult` this amplitude derives from.
        selected: whether ``amplitude_adc > cut_adc``.
        cut_adc: the selection threshold applied.
        validity: the pedestal validity state (convenience alias).
    """

    method: str
    amplitude_adc: float
    pedestal: PedestalResult
    selected: bool
    cut_adc: float

    @property
    def validity(self) -> PedestalValidity:
        return self.pedestal.validity


# ---------------------------------------------------------------------------
# S00_selector_v1 — the historical, immutable first-four-median gate
# ---------------------------------------------------------------------------


def estimate_pedestal_v1(waveform: np.ndarray) -> PedestalResult:
    """Historical S00 selector: ``pedestal = median(waveform[0:4])``.

    This is the exact estimator the canonical S00 pulse table was built with.
    It is *frozen*: it must never be changed in place, because downstream count
    reproduction (``configs/s00_reproduction.yaml`` expected counts) depends on
    it. New/candidate estimators are separate functions.

    The validity classification here is *descriptive only* — it does not alter
    the returned pedestal value. It exists so a downstream migration analysis
    can decompose which records this selector may have censored.

    Inputs outside the named map's closed domain (non-1-D, fewer than four
    samples, or non-finite ADC values) raise :class:`SelectorInputError` rather
    than silently becoming ordinary physics rejections.
    """
    wave = _validate_v1_waveforms(waveform, scalar=True)
    first_four = wave[list(S00_SELECTOR_V1_BASELINE_INDICES)]
    pedestal = float(np.median(first_four))
    validity = classify_pedestal_validity(wave, first_four, pedestal)
    return PedestalResult(
        method=S00_SELECTOR_V1_ID,
        validity=validity,
        pedestal_adc=pedestal,
        first_four_samples=first_four.copy(),
        full_waveform=wave,
    )


def estimate_pedestal_v1_batched(
    waveforms: np.ndarray,
    baseline_indices: Iterable[int] | None = None,
) -> np.ndarray:
    """Batched form of the frozen historical v1 selector.

    ``baseline_indices`` is retained only as a compatibility assertion for
    existing callers. Any value other than exactly ``(0, 1, 2, 3)`` raises
    :class:`SelectorInputError`. The v1 identity therefore cannot execute a
    different mathematical map through the batched production path.
    """
    indices = _validate_v1_baseline_indices(baseline_indices)
    wave = _validate_v1_waveforms(waveforms, scalar=False)
    return np.median(wave[..., list(indices)], axis=-1)


# ---------------------------------------------------------------------------
# Candidate estimators (additive, declared validity domain)
# ---------------------------------------------------------------------------


def _is_saturated(wave: np.ndarray, code_max: float = 16383.0) -> bool:
    """H6: upper saturation (hit the 14-bit max code) or lower rail (0)."""
    return bool(np.any(wave >= code_max) or np.all(wave <= 1.0))


def estimate_pedestal_dynamic_range(waveform: np.ndarray) -> PedestalResult:
    """Candidate: dynamic-range pedestal ``b = min(waveform)`` produces the
    S00c dynamic comparator ``Adyn = max(w) - min(w)``.

    Validity domain: quiet or recovery-shaped waveforms where the minimum tracks
    the true baseline. This is the estimator that reproduced 706,373 records in
    the S00c study (vs 640,737 for v1).
    """
    wave = np.asarray(waveform, dtype=float)
    pedestal = float(np.min(wave))
    validity = (
        PedestalValidity.QUIET_VALID
        if _is_saturated(wave) is False
        else PedestalValidity.SATURATED
    )
    return PedestalResult(
        method="dynamic_range",
        validity=validity,
        pedestal_adc=pedestal,
        first_four_samples=wave[0:4].copy(),
        full_waveform=wave,
    )


def estimate_pedestal_rolling_min(waveform: np.ndarray) -> PedestalResult:
    """Candidate: rolling-minimum pedestal over the full window.

    Robust to a single early pulse (H1) and to prior-pulse recovery (H2) that
    only raises the first samples, because the baseline floor is taken over the
    whole window. Declared validity domain: waveforms with a genuine quiet
    floor somewhere in the window.

    Because the estimator is *by construction* robust to H1/H2, the validity is
    estimator-aware rather than shape-based: it flags only the failure modes the
    rolling-minimum itself cannot absorb (saturation clipping the floor, a
    polarity ambiguity chasing the negative dip, or an early region so noisy it
    spans most of the dynamic range).
    """
    wave = np.asarray(waveform, dtype=float)
    pedestal = float(np.min(wave))
    first_four = wave[0:4]
    dyn = float(np.max(wave) - np.min(wave))
    if _is_saturated(wave):
        validity = PedestalValidity.SATURATED
    elif (
        first_four.size > 0
        and float(np.min(wave)) < float(np.min(first_four)) - 300.0
    ):
        validity = PedestalValidity.BIPOLAR_OR_POLARITY_UNKNOWN
    elif (
        first_four.size > 0
        and dyn > 0
        and (float(np.max(first_four)) - float(np.min(first_four))) / dyn > 0.9
    ):
        validity = PedestalValidity.NO_PEDESTAL_IDENTIFIABLE
    else:
        validity = PedestalValidity.QUIET_VALID
    return PedestalResult(
        method="rolling_min",
        validity=validity,
        pedestal_adc=pedestal,
        first_four_samples=first_four.copy(),
        full_waveform=wave,
    )


def estimate_pedestal_early_robust(waveform: np.ndarray) -> PedestalResult:
    """Candidate: robust low-percentile pedestal over the *early* window.

    Contract (ARU-S00-P10-PEDESTAL-001 / #1137):
    - Estimation window is the first four samples (same indices as v1), **not**
      the full acquisition window.
    - Estimator is ``P10(early_window)``.
    - Validity uses :func:`classify_pedestal_validity` so early-active /
      recovery / bipolar contamination is not silently treated as a quiet
      baseline. Translation equivariance alone does not identify an electronic
      pedestal when the early window is pulse-dominated.

    Historical bug: this function previously computed ``percentile(full_wave, 10)``
    while advertising an early-window estimator.
    """
    wave = np.asarray(waveform, dtype=float)
    if wave.ndim != 1:
        raise SelectorInputError("estimate_pedestal_early_robust expects a 1-D waveform")
    if wave.size < 4:
        raise SelectorInputError("estimate_pedestal_early_robust requires >= 4 samples")
    early = wave[list(S00_SELECTOR_V1_BASELINE_INDICES)]
    pedestal = float(np.percentile(early, 10))
    validity = classify_pedestal_validity(wave, early, pedestal)
    # Additional quiet-noise identifiability: if the early-window IQR spans most
    # of the early dynamic range, the P10 is a noise quantile, not a location.
    early_dyn = float(np.max(early) - np.min(early))
    if early_dyn > 0 and (np.percentile(early, 90) - np.percentile(early, 10)) / early_dyn > 0.9:
        validity = PedestalValidity.NO_PEDESTAL_IDENTIFIABLE
    return PedestalResult(
        method="early_robust_p10",
        validity=validity,
        pedestal_adc=pedestal,
        first_four_samples=early.copy(),
        full_waveform=wave,
    )


# ---------------------------------------------------------------------------
# Waveform-class classification (H1-H8 mechanism decomposition)
# ---------------------------------------------------------------------------


def classify_pedestal_validity(
    wave: np.ndarray,
    first_four: np.ndarray,
    pedestal: float,
    *,
    amp_cut_adc: float = 1000.0,
    code_max: float = 16383.0,
) -> PedestalValidity:
    """Classify a waveform into one of the seven :class:`PedestalValidity`
    states, prioritizing the distinct censoring mechanisms (H1-H8).

    The classifier is a *diagnosis*, not a selector: it returns the state that
    best explains why the first-four median may mis-estimate the true baseline.
    It is deliberately conservative — when multiple mechanisms could apply, the
    more censoring-relevant state wins so the migration analysis never hides a
    record behind a benign label.

    Order of checks (highest-censoring-risk first):
      1. Saturation (H6) — the whole amplitude reading is capped.
      2. Bipolar / negative excursion (H3) — polarity ambiguous.
      3. Early activity in samples 0-3 (H1) — raises the pedestal.
      4. Recovery / baseline relaxation (H2) — a decaying tail after a prior
         pulse, detected as monotone fall across the first samples.
      5. Jagged single-sample dropout (H4) — a lone outlier in the first four.
      6. Noise / window-phase / overlap (H5, H7, H8) — no identifiable quiet
         region.
      7. Otherwise quiet and valid (H0).
    """
    wave = np.asarray(wave, dtype=float)
    first_four = np.asarray(first_four, dtype=float)
    if first_four.size == 0:
        return PedestalValidity.NO_PEDESTAL_IDENTIFIABLE

    # H6: saturation clips the dynamic range, capping the computed amplitude.
    if _is_saturated(wave, code_max):
        return PedestalValidity.SATURATED

    # H3: a strong negative excursion (polarity opposite to the positive pulse)
    # makes the pedestal polarity ambiguous.
    dyn = float(np.max(wave) - np.min(wave))
    if (
        dyn > amp_cut_adc
        and float(np.min(wave))
        < float(np.min(first_four)) - 0.5 * amp_cut_adc
    ):
        return PedestalValidity.BIPOLAR_OR_POLARITY_UNKNOWN

    median = float(np.median(first_four))
    early_span = float(np.max(first_four) - np.min(first_four))

    # H1: the first samples are actively rising (early pulse onset) rather than
    # the peak of a pulse; the first-four median is then pulled above baseline.
    # We require the actual pulse peak to be well above the first-four max so
    # that a noisy waveform spanning no real dynamic range (H5/H7/H8) is not
    # misclassified as early activity.
    if (
        early_span > 150.0
        and float(np.max(first_four)) > median + 150.0
        and first_four[-1] > first_four[0]
        and float(np.max(wave)) > float(np.max(first_four)) + 150.0
    ):
        return PedestalValidity.EARLY_ACTIVE

    # H2: a recovery tail — the first samples are above the later quiet portion
    # AND fall monotonically (prior-pulse baseline relaxation, not noise).
    # Requiring a monotone descent keeps a merely-noisy early region
    # (H5/H7/H8) from being mislabelled as recovery.
    if (
        wave.size >= 8
        and median > float(np.median(wave[-4:])) + 150.0
        and first_four[0] >= first_four[1] >= first_four[2] >= first_four[3]
        and first_four[0] > first_four[3]
    ):
        return PedestalValidity.RECOVERY_CONTAMINATED

    # H4: a single jagged/dropout sample among otherwise-quiet first four.
    # The non-outlier samples must be tightly clustered (ordered[2]-ordered[0]
    # small) so a rising ramp (H1) or falling tail (H2) is not misclassified.
    ordered = np.sort(first_four)
    if (
        ordered.size >= 4
        and (ordered[3] - ordered[2]) > 150.0
        and (ordered[2] - ordered[0]) < 150.0
        and early_span > 150.0
    ):
        return PedestalValidity.JAGGED

    # H5/H7/H8: the early region is too noisy relative to a clean baseline for
    # any pedestal to be identified.
    if early_span > 1.0 and dyn > 0 and (early_span / dyn) > 0.9:
        return PedestalValidity.NO_PEDESTAL_IDENTIFIABLE

    return PedestalValidity.QUIET_VALID


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def select_amplitude(
    waveform: np.ndarray,
    cut_adc: float = 1000.0,
    method: str = "v1",
) -> AmplitudeResult:
    """Compute the selected-pulse amplitude for one waveform under a named
    selector method.

    Args:
        waveform: the 1-D raw waveform (18 samples for the B-stack, 8 channels).
        cut_adc: the amplitude selection threshold (``AMP_CUT``).
        method: selector method name. ``"v1"`` (default) uses the historical
            first-four-median gate; ``"dynamic_range"``, ``"rolling_min"``, and
            ``"early_robust_p10"`` are the candidate estimators.

    Returns:
        An :class:`AmplitudeResult`. ``selected`` is ``amplitude_adc > cut_adc``
        where ``amplitude_adc = max(waveform) - pedestal_adc``.
    """
    estimators = {
        "v1": estimate_pedestal_v1,
        "dynamic_range": estimate_pedestal_dynamic_range,
        "rolling_min": estimate_pedestal_rolling_min,
        "early_robust_p10": estimate_pedestal_early_robust,
    }
    if method not in estimators:
        raise KeyError(
            f"unknown selector method {method!r}; choices={sorted(estimators)}"
        )
    wave = np.asarray(waveform, dtype=float)
    ped = estimators[method](wave)
    amplitude = float(np.max(wave) - ped.pedestal_adc)
    return AmplitudeResult(
        method=method,
        amplitude_adc=amplitude,
        pedestal=ped,
        selected=amplitude > cut_adc,
        cut_adc=cut_adc,
    )


def selectors_available() -> list[str]:
    """Names of every selector method usable by :func:`select_amplitude`."""
    return ["v1", "dynamic_range", "rolling_min", "early_robust_p10"]
