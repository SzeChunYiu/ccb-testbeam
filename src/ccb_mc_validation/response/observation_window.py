"""Observation-domain semantic tags for full-transport vs acquisition window (#1090)."""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from ccb_mc_validation.exceptions import ConfigurationError, DataContractError


class ObservationSemanticClass(str, Enum):
    FULL_TRANSPORT = "FULL_TRANSPORT"
    ACQUISITION_WINDOW = "ACQUISITION_WINDOW"
    UNKNOWN = "UNKNOWN"


# Name prefixes / exact tokens used in Geant4 + sipm-core surfaces.
_FULL_TRANSPORT_HINTS = (
    "edep_scint_raw",
    "edep_scint_MeV",
    "edep_scint_mev",
    "track_len_scint",
    "n_scint_generated",
    "n_wls_generated",
    "n_cerenkov_generated",
    "n_end_arrival",
    "n_detected",
    "pe_saturated",
    "pe_sat",
    "full_transport_",
    "FULL_TRANSPORT",
)

_ACQ_WINDOW_HINTS = (
    "production_adc",
    "daq_window_",
    "acquisition_window",
    "ACQUISITION_WINDOW",
    "avalanche",
    "waveform_adc",
)


def classify_quantity_name(name: str) -> ObservationSemanticClass:
    """Best-effort semantic class from a persisted quantity name."""
    if not isinstance(name, str) or not name:
        return ObservationSemanticClass.UNKNOWN
    lower = name.lower()
    for hint in _ACQ_WINDOW_HINTS:
        if hint.lower() in lower or hint in name:
            return ObservationSemanticClass.ACQUISITION_WINDOW
    for hint in _FULL_TRANSPORT_HINTS:
        if hint.lower() in lower or hint in name:
            return ObservationSemanticClass.FULL_TRANSPORT
    if name.startswith("full_transport_") or name.startswith("FULL_TRANSPORT"):
        return ObservationSemanticClass.FULL_TRANSPORT
    if name.startswith("daq_window_") or name.startswith("ACQUISITION_WINDOW"):
        return ObservationSemanticClass.ACQUISITION_WINDOW
    return ObservationSemanticClass.UNKNOWN


def require_matched_observation_domains(
    numerator_name: str,
    denominator_name: str,
    *,
    allow_explicit_cross_domain: bool = False,
) -> None:
    """Fail closed if ADC/Edep-style ratios mix unmatched observation domains.

    Calibration such as ``ADC / full-event Edep`` is a different estimand from
    ``ADC / windowed Edep``. Cross-domain ratios require an explicit opt-in.
    """
    num = classify_quantity_name(numerator_name)
    den = classify_quantity_name(denominator_name)
    if num == ObservationSemanticClass.UNKNOWN or den == ObservationSemanticClass.UNKNOWN:
        raise ConfigurationError(
            "observation-domain classification UNKNOWN for "
            f"numerator={numerator_name!r} ({num.value}) "
            f"denominator={denominator_name!r} ({den.value}). "
            "Rename with full_transport_* / daq_window_* or register an "
            "observation_window_profile_id (#1090)."
        )
    if num != den and not allow_explicit_cross_domain:
        raise DataContractError(
            "refusing unmatched observation domains for calibration/ratio: "
            f"{numerator_name!r}={num.value} vs {denominator_name!r}={den.value}. "
            "Pass allow_explicit_cross_domain=True only with a documented estimand "
            "(issue #1090)."
        )


def assert_all_quantities_tagged(names: Iterable[str]) -> None:
    """Require every name to classify as FULL_TRANSPORT or ACQUISITION_WINDOW."""
    unknown = [
        n
        for n in names
        if classify_quantity_name(n) == ObservationSemanticClass.UNKNOWN
    ]
    if unknown:
        raise ConfigurationError(
            "untagged observation quantities (need FULL_TRANSPORT or "
            f"ACQUISITION_WINDOW semantics): {unknown}"
        )
