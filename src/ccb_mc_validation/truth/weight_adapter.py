"""Source-aware raw→event weight adapters (issue #880).

A branch named ``PrimaryWeight`` is not by itself a physical event measure.
Callers must bind a versioned ``generator_measure_mode`` and matching
``weight_adapter_id``. Arbitrary ``weights[0]`` extraction is rejected.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.exceptions import DataContractError

WEIGHT_ADAPTER_SCHEMA = "ccb-raw-event-weight-adapter/v1"

# Supported adapter identities. Each maps to a distinct generator world.
ADAPTER_SCALAR_EVENT = "scalar_event_weight_v1"
ADAPTER_COMMON_REPLICATED = "common_replicated_primary_weight_v1"
ADAPTER_DIRECT_UNIT = "direct_sampling_unit_weight_v1"
ADAPTER_LEGACY_CM_IMPORTANCE = "legacy_cm_importance_weight_v1"

MODE_SCALAR = "scalar_event_weight"
MODE_COMMON_REPLICATED = "common_replicated_primary"
MODE_DIRECT_UNIT = "direct_sampling_unit_weight"
MODE_LEGACY_CM_IMPORTANCE = "legacy_cm_importance_weight"

_MODE_TO_ADAPTER = {
    MODE_SCALAR: ADAPTER_SCALAR_EVENT,
    MODE_COMMON_REPLICATED: ADAPTER_COMMON_REPLICATED,
    MODE_DIRECT_UNIT: ADAPTER_DIRECT_UNIT,
    MODE_LEGACY_CM_IMPORTANCE: ADAPTER_LEGACY_CM_IMPORTANCE,
}

# Legacy CM importance: exact constants from S21b reconstruction (#1053).
LEGACY_CM_M1 = 938.2720813  # proton mass MeV/c^2
LEGACY_CM_M2 = 1875.6129426  # deuteron mass MeV/c^2
LEGACY_CM_EKIN_BEAM = 190.0  # MeV
LEGACY_CM_OFFSET = 0.115  # cm, z_cm offset for z_mm = (z_cm + 0.115) * 10.0

# Reference cross-section 28-row table path (relative to repo root).
DEFAULT_SIGMA_TABLE_PATH = "geant4/src_patch/sigma_pd_cm_190.txt"


def _as_1d(name: str, values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim != 1:
        raise DataContractError(f"{name} must be 1-D, got shape {arr.shape}")
    return arr


def _read_sigma_table(path: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read the 28-row Ermish cross-section table (angle_deg, sigma, stat_uncertainty)."""
    data = np.loadtxt(str(path), comments="#")
    if data.ndim != 2 or data.shape[1] != 3:
        raise DataContractError(
            f"sigma table must have 3 columns, got shape {data.shape}"
        )
    angles_deg = data[:, 0]
    sigma = data[:, 1]
    stat_uncertainty = data[:, 2]
    if not np.all(np.diff(angles_deg) > 0):
        raise DataContractError("sigma table angles must be strictly increasing")
    if not np.all(np.isfinite(sigma)) or not np.all(sigma > 0):
        raise DataContractError("sigma table values must be finite and positive")
    return angles_deg, sigma, stat_uncertainty


def _interp_s21b(
    x: np.ndarray, xp: np.ndarray, fp: np.ndarray
) -> np.ndarray:
    """S21b-style linear interpolation with endpoint-slope extrapolation.

    Matches ``np.interp`` for ``xp[0] <= x <= xp[-1]``.  Outside the
    measured support, the last two points define the slope used to
    extrapolate outward (no clipping).
    """
    # Interior uses np.interp (linear interpolation, no extrapolation).
    lo = x < xp[0]
    hi = x > xp[-1]
    inside = ~(lo | hi)
    y = np.empty_like(x)
    y[inside] = np.interp(x[inside], xp, fp)
    if np.any(lo):
        # Left extrapolation: slope from first two points.
        slope = (fp[1] - fp[0]) / (xp[1] - xp[0])
        y[lo] = fp[0] + (x[lo] - xp[0]) * slope
    if np.any(hi):
        # Right extrapolation: slope from last two points.
        slope = (fp[-1] - fp[-2]) / (xp[-1] - xp[-2])
        y[hi] = fp[-1] + (x[hi] - xp[-1]) * slope
    return y


def _reconstruct_cm_theta(
    ekin_mev: np.ndarray,
    px: np.ndarray,
    py: np.ndarray,
    pz: np.ndarray,
    pos_z_mm: np.ndarray | None = None,
    *,
    m1: float = LEGACY_CM_M1,
    m2: float = LEGACY_CM_M2,
    ekin_beam: float = LEGACY_CM_EKIN_BEAM,
    offset: float = LEGACY_CM_OFFSET,
) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct theta_cm (degrees) and theta_lab (degrees) from S21b kinematics.

    Follows the exact S21b ``reconstruct_cm()`` method (#1053).
    Returns (theta_cm_deg, theta_lab_deg) arrays.
    """
    # --- theta_lab from momentum ---
    p = np.sqrt(px**2 + py**2 + pz**2)
    # Clip to avoid domain errors from tiny rounding.
    cos_lab = np.clip(pz / p, -1.0, 1.0)
    theta_lab_deg = np.degrees(np.arccos(cos_lab))

    # --- CM kinematics (S21b exact) ---
    e1 = ekin_beam + m1
    p1 = np.sqrt(ekin_beam**2 + 2.0 * ekin_beam * m1)
    beta = p1 / (e1 + m2)
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    ecm = np.sqrt((e1 + m2) ** 2 - p1**2)
    ekincm = ecm - m1 - m2
    ekin3cm = (ekincm / 2.0) * (ekincm + 2.0 * m2) / ecm
    e3cm = ekin3cm + m1
    pcm = np.sqrt(e3cm**2 - m1**2)

    # Per-primary boost from lab -> CM frame.
    a = (gamma - 1.0) * m1 + gamma * ekin3cm
    b = gamma * beta * pcm
    coscm = np.clip((ekin_mev - a) / b, -1.0, 1.0)
    theta_cm_deg = np.degrees(np.arccos(coscm))

    return theta_cm_deg, theta_lab_deg


def resolve_adapter_id(
    *,
    generator_measure_mode: str | None,
    weight_adapter_id: str | None = None,
) -> str:
    if not generator_measure_mode:
        raise DataContractError(
            "generator_measure_mode is required to adapt PrimaryWeight; "
            "arbitrary weights[0] is unauthorized (#880)"
        )
    mode = str(generator_measure_mode)
    if mode not in _MODE_TO_ADAPTER:
        raise DataContractError(
            f"unsupported generator_measure_mode {mode!r}; "
            f"supported={sorted(_MODE_TO_ADAPTER)}"
        )
    expected = _MODE_TO_ADAPTER[mode]
    if weight_adapter_id is not None and str(weight_adapter_id) != expected:
        raise DataContractError(
            f"weight_adapter_id {weight_adapter_id!r} does not match "
            f"generator_measure_mode {mode!r} (expected {expected!r})"
        )
    return expected


def adapt_raw_primary_weight(
    primary_weights: Any,
    *,
    generator_measure_mode: str | None,
    weight_adapter_id: str | None = None,
    apply_weight: bool = True,
    primary_ekin: Any = None,
    primary_mom_x: Any = None,
    primary_mom_y: Any = None,
    primary_mom_z: Any = None,
    primary_pos_z: Any = None,
    sigma_table_path: str | None = None,
) -> dict[str, Any]:
    """Return one derived event weight with adapter provenance.

    Parameters
    ----------
    primary_weights
        Raw generator payload for one event (scalar or vector).
    generator_measure_mode
        Declared generator world; required whenever ``apply_weight`` is true.
    primary_ekin, primary_mom_x/y/z, primary_pos_z
        Per-primary kinematics arrays; required for ``legacy_cm_importance_weight``
        mode (issue #1053).
    sigma_table_path
        Cross-section table path; defaults to ``DEFAULT_SIGMA_TABLE_PATH``
        resolved relative to the repository root.
    """
    if not apply_weight:
        return {
            "schema_version": WEIGHT_ADAPTER_SCHEMA,
            "generator_measure_mode": "unweighted_diagnostic",
            "weight_adapter_id": "unit_weight_diagnostic_v1",
            "event_weight": 1.0,
            "authorising": False,
        }

    adapter = resolve_adapter_id(
        generator_measure_mode=generator_measure_mode,
        weight_adapter_id=weight_adapter_id,
    )
    mode = str(generator_measure_mode)
    weights = _as_1d("PrimaryWeight", primary_weights)

    if adapter == ADAPTER_DIRECT_UNIT:
        # Direct-sampling world: analysis weight is identically 1; a stale
        # non-unit raw branch must not be consumed as a measure.
        if weights.size == 0:
            raise DataContractError("PrimaryWeight empty under direct-sampling mode")
        if not np.all(np.isfinite(weights)):
            raise DataContractError("PrimaryWeight non-finite under direct-sampling mode")
        if np.any(np.abs(weights - 1.0) > 0.0):
            raise DataContractError(
                "direct_sampling_unit_weight mode forbids non-unit raw PrimaryWeight "
                f"(got min={float(np.min(weights))}, max={float(np.max(weights))})"
            )
        event_weight = 1.0
    elif adapter == ADAPTER_SCALAR_EVENT:
        if weights.size != 1:
            raise DataContractError(
                "scalar_event_weight mode requires exactly one PrimaryWeight value; "
                f"got {weights.size}"
            )
        event_weight = float(weights[0])
    elif adapter == ADAPTER_COMMON_REPLICATED:
        if weights.size == 0:
            raise DataContractError("PrimaryWeight empty under common-replicated mode")
        if not np.all(np.isfinite(weights)):
            raise DataContractError("PrimaryWeight non-finite under common-replicated mode")
        # Collapse only after proving every sibling value is identical.
        if not np.all(weights == weights[0]):
            raise DataContractError(
                "common_replicated_primary mode requires identical sibling weights; "
                f"got unique={sorted({float(x) for x in weights})}"
            )
        event_weight = float(weights[0])
    elif adapter == ADAPTER_LEGACY_CM_IMPORTANCE:
        # Legacy CM importance weight: correct the uniform-theta_cm generator
        # to the target density p(theta_cm) ∝ sigma_cm(theta_cm) * sin(theta_cm).
        # Per-primary correction: r = sigma_cm(theta_cm) * sin(theta_cm) / sigma_lab(theta_lab).
        # Event weight = sum(r) across primaries.
        if primary_ekin is None or primary_mom_x is None or primary_mom_y is None or primary_mom_z is None:
            raise DataContractError(
                "legacy_cm_importance_weight mode requires primary_ekin, "
                "primary_mom_x, primary_mom_y, primary_mom_z"
            )
        # Resolve sigma table path.
        if sigma_table_path is None:
            sigma_table_path = DEFAULT_SIGMA_TABLE_PATH
        table_path = Path(sigma_table_path)
        if not table_path.is_absolute():
            # Try relative to repo root (cwd convention).
            table_path = Path.cwd() / table_path
        if not table_path.is_file():
            raise DataContractError(
                f"sigma table not found: {table_path}"
            )
        angles_deg, sigma, _ = _read_sigma_table(table_path)

        # Convert to radians for interpolation.
        ang_rad = np.radians(angles_deg)
        sig = sigma  # mb/sr

        ekin = _as_1d("PrimaryEkin", primary_ekin)
        px = _as_1d("PrimaryMomX", primary_mom_x)
        py = _as_1d("PrimaryMomY", primary_mom_y)
        pz = _as_1d("PrimaryMomZ", primary_mom_z)
        if not (ekin.size == px.size == py.size == pz.size):
            raise DataContractError(
                f"kinematics array size mismatch: ekin={ekin.size}, "
                f"px={px.size}, py={py.size}, pz={pz.size}"
            )
        if not np.all(np.isfinite(ekin)) or not np.all(np.isfinite(px)) or not np.all(np.isfinite(py)) or not np.all(np.isfinite(pz)):
            raise DataContractError("legacy_cm_importance_weight kinematics must be finite")
        if not np.all(ekin >= 0.0):
            raise DataContractError("legacy_cm_importance_weight ekin must be non-negative")

        # Reconstruct theta_cm and theta_lab per primary.
        theta_cm_deg, theta_lab_deg = _reconstruct_cm_theta(ekin, px, py, pz)

        # Fail-closed: theta_cm outside measured support (reference-law probability 0).
        support_lo = float(angles_deg[0])  # 26.49 deg
        support_hi = float(angles_deg[-1])  # 169.78 deg
        outside_support = (theta_cm_deg < support_lo) | (theta_cm_deg > support_hi)
        if np.any(outside_support):
            bad = theta_cm_deg[outside_support].tolist()
            raise DataContractError(
                f"legacy_cm_importance_weight: theta_cm outside measured support "
                f"[{support_lo:.2f}, {support_hi:.2f}] deg: {bad}"
            )

        # Evaluate sigma_cm(theta_cm) and sigma_lab(theta_lab) via S21b interp.
        theta_cm_rad = np.radians(theta_cm_deg)
        theta_lab_rad = np.radians(theta_lab_deg)
        sigma_cm = _interp_s21b(theta_cm_rad, ang_rad, sig)
        sigma_lab = _interp_s21b(theta_lab_rad, ang_rad, sig)

        # Per-primary ratio.
        sin_theta_cm = np.sin(theta_cm_rad)
        if not np.all(np.isfinite(sigma_cm)) or not np.all(np.isfinite(sigma_lab)):
            raise DataContractError("legacy_cm_importance_weight: non-finite sigma evaluation")
        if np.any(sigma_lab <= 0.0):
            raise DataContractError("legacy_cm_importance_weight: non-positive sigma_lab")
        if np.any(sigma_cm <= 0.0):
            raise DataContractError("legacy_cm_importance_weight: non-positive sigma_cm")

        w = sigma_cm * sin_theta_cm / sigma_lab
        if not np.all(np.isfinite(w)):
            raise DataContractError("legacy_cm_importance_weight: non-finite per-primary ratio")
        if np.any(w < 0.0):
            raise DataContractError("legacy_cm_importance_weight: negative per-primary ratio")

        event_weight = float(np.sum(w))
    else:  # pragma: no cover - resolve_adapter_id already gates
        raise DataContractError(f"unhandled weight_adapter_id {adapter!r}")

    if not np.isfinite(event_weight):
        raise DataContractError("adapted event_weight is non-finite")
    if event_weight < 0.0:
        raise DataContractError("adapted event_weight is negative")

    return {
        "schema_version": WEIGHT_ADAPTER_SCHEMA,
        "generator_measure_mode": mode,
        "weight_adapter_id": adapter,
        "event_weight": float(event_weight),
        "authorising": True,
    }


def require_weight_provenance(meta: Mapping[str, Any]) -> tuple[str, str]:
    """Extract and validate weight provenance fields from run/product metadata."""
    mode = meta.get("generator_measure_mode")
    adapter = meta.get("weight_adapter_id")
    resolved = resolve_adapter_id(
        generator_measure_mode=None if mode is None else str(mode),
        weight_adapter_id=None if adapter is None else str(adapter),
    )
    return str(mode), resolved
