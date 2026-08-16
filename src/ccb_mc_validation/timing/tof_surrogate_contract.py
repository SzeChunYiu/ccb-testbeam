"""Chord/arithmetic-beta TOF surrogate contract (#1127)."""

from __future__ import annotations

from ccb_mc_validation.exceptions import ConfigurationError

TOF_PREDICTOR_SURROGATE = "chord_arithmetic_beta_surrogate_v1"
TOF_PREDICTOR_PATH_INTEGRAL = "path_integral_lab_time_v1"  # not implemented


def require_authorising_tof_predictor(predictor_id: str) -> str:
    """Refuse authorising claims that still depend on the chord surrogate."""
    predictor_id = str(predictor_id)
    if predictor_id == TOF_PREDICTOR_SURROGATE:
        raise ConfigurationError(
            "chord/arithmetic-beta TOF predictor is a SURROGATE and cannot authorise "
            "truth-timing claims (#1127); path-integral closure remains BLOCKED"
        )
    if predictor_id != TOF_PREDICTOR_PATH_INTEGRAL:
        raise ConfigurationError(f"unknown TOF predictor id: {predictor_id!r}")
    raise ConfigurationError(
        "path-integral TOF predictor is not implemented; #1127 remains BLOCKED"
    )


def surrogate_tof_metadata() -> dict[str, str]:
    return {
        "predictor_id": TOF_PREDICTOR_SURROGATE,
        "claims_authorized": "false",
        "status": "SURROGATE",
        "issue": "#1127",
    }
