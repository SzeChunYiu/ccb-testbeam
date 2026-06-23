"""Unit validation and energy conversion helpers."""

from __future__ import annotations

from typing import Final

from ccb_mc_validation.exceptions import UnitValidationError

ENERGY_UNITS: Final[frozenset[str]] = frozenset({"MeV", "keV", "GeV", "eV", "ADC"})
TIME_UNITS: Final[frozenset[str]] = frozenset({"ns", "us", "ps", "s"})
ALL_UNITS: Final[frozenset[str]] = ENERGY_UNITS | TIME_UNITS

# Energy expressed relative to MeV.
_TO_MEV: Final[dict[str, float]] = {
    "eV": 1.0e-6,
    "keV": 1.0e-3,
    "MeV": 1.0,
    "GeV": 1.0e3,
}


def validate_unit(unit: str, *, kind: str = "energy") -> str:
    """Validate and normalize a unit string.

    Parameters
    ----------
    unit:
        Unit label such as ``MeV`` or ``ns``.
    kind:
        ``energy`` or ``time``.

    Returns
    -------
    str
        Canonical unit string.

    Raises
    ------
    UnitValidationError
        If the unit is empty or not registered for the requested kind.
    """
    if not unit or not isinstance(unit, str):
        raise UnitValidationError("unit must be a non-empty string")

    canonical = unit.strip()
    if kind == "energy":
        allowed = ENERGY_UNITS
    elif kind == "time":
        allowed = TIME_UNITS
    else:
        raise UnitValidationError(f"unknown unit kind: {kind}")

    if canonical not in allowed:
        raise UnitValidationError(
            f"unsupported {kind} unit {canonical!r}; allowed: {sorted(allowed)}"
        )
    return canonical


def convert_energy(
    value: float,
    from_unit: str,
    to_unit: str,
    *,
    adc_per_mev: float | None = None,
) -> float:
    """Convert an energy-like quantity between supported units.

    MeV-family units convert via fixed factors. ``ADC`` conversions require
    ``adc_per_mev`` (counts per MeV) in at least one direction.
    """
    src = validate_unit(from_unit, kind="energy")
    dst = validate_unit(to_unit, kind="energy")

    if src == dst:
        return float(value)

    if src == "ADC" or dst == "ADC":
        if adc_per_mev is None or adc_per_mev <= 0:
            raise UnitValidationError(
                "adc_per_mev must be a positive float when converting to or from ADC"
            )
        mev_value = float(value) / adc_per_mev if src == "ADC" else float(value) * _TO_MEV[src]
        if dst == "ADC":
            return mev_value * adc_per_mev
        return mev_value / _TO_MEV[dst]

    mev_value = float(value) * _TO_MEV[src]
    return mev_value / _TO_MEV[dst]
