"""Primary vs event-total stopping-power estimator contract (#1007).

PSTAR / primary dE/dx validation may only consume primary-only estimators and
must fail closed when secondary scintillator activity is present. The legacy
all-particle Edep/path ratio is retained only as a named calorimetric diagnostic.
"""

from __future__ import annotations

from typing import Any, Mapping

PRIMARY_STOPPING_ESTIMATOR_ID = "primary_local_edep_over_path_v1"
EVENT_CALORIMETRIC_DIAGNOSTIC_ID = "all_particle_edep_over_path_diagnostic_v1"


class StoppingPowerEstimatorError(ValueError):
    """Fail-closed contract violation for stopping-power estimators."""


def _finite_nonneg(name: str, value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise StoppingPowerEstimatorError(f"{name} must be numeric, got {value!r}") from exc
    if x != x or x in (float("inf"), float("-inf")):
        raise StoppingPowerEstimatorError(f"{name} must be finite, got {x!r}")
    if x < 0.0:
        raise StoppingPowerEstimatorError(f"{name} must be >= 0, got {x}")
    return x


def primary_stopping_ratio_mev_per_mm(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the primary stopping-power ratio or raise if the row is ineligible.

    Required fields:
    - primary_edep_scint_raw_MeV
    - primary_track_len_scint_mm
    - secondary_scint_activity (bool/0/1)
    """
    if "primary_edep_scint_raw_MeV" not in row or "primary_track_len_scint_mm" not in row:
        raise StoppingPowerEstimatorError(
            "primary stopping-power validation requires primary_edep_scint_raw_MeV "
            "and primary_track_len_scint_mm; legacy track_len_scint_mm/edep_scint_raw_MeV "
            "are all-particle calorimetric fields and are not authorising (#1007)"
        )
    activity = row.get("secondary_scint_activity")
    if activity is None:
        raise StoppingPowerEstimatorError("secondary_scint_activity is required")
    active = bool(int(activity)) if not isinstance(activity, bool) else activity
    if active:
        raise StoppingPowerEstimatorError(
            "secondary_scint_activity=true: event excluded from primary stopping-power average"
        )
    edep = _finite_nonneg("primary_edep_scint_raw_MeV", row["primary_edep_scint_raw_MeV"])
    path = _finite_nonneg("primary_track_len_scint_mm", row["primary_track_len_scint_mm"])
    if path <= 0.0:
        raise StoppingPowerEstimatorError("primary_track_len_scint_mm must be > 0")
    return {
        "estimator_id": PRIMARY_STOPPING_ESTIMATOR_ID,
        "edep_MeV": edep,
        "path_mm": path,
        "ratio_MeV_per_mm": edep / path,
        "authorising": True,
    }


def event_calorimetric_ratio_mev_per_mm(row: Mapping[str, Any]) -> dict[str, Any]:
    """Named non-authorising all-particle diagnostic ratio."""
    edep = _finite_nonneg("edep_scint_raw_MeV", row["edep_scint_raw_MeV"])
    path = _finite_nonneg("track_len_scint_mm", row["track_len_scint_mm"])
    if path <= 0.0:
        raise StoppingPowerEstimatorError("track_len_scint_mm must be > 0 for diagnostic ratio")
    return {
        "estimator_id": EVENT_CALORIMETRIC_DIAGNOSTIC_ID,
        "edep_MeV": edep,
        "path_mm": path,
        "ratio_MeV_per_mm": edep / path,
        "authorising": False,
    }
