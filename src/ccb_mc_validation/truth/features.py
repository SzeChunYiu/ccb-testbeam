"""Truth feature vectors for MV1 (PID) and MV2 (range-energy) studies.

Feature/target separation (ML-005)
----------------------------------
Model feature vectors **never** include the regression target ``ekin`` (or any
label/target column).  The MV2 range-energy target is exposed through the
dedicated :func:`extract_mv2_target` API; :func:`assert_no_target_leakage`
guards every feature path so a future edit cannot silently re-introduce label
leakage.
"""

from __future__ import annotations

from typing import Any

import numpy as np

#: Columns that must never appear in a *feature* vector (regression / class
#: labels).  Any feature-name tuple containing one of these is a defect.
FORBIDDEN_FEATURE_KEYS: frozenset[str] = frozenset({"ekin", "label", "target", "y"})

# MV1 (PID / dE-E) uses only observable energy deposits + observed depth.
MV1_FEATURE_NAMES: tuple[str, ...] = (
    "edep_l0",
    "edep_l1",
    "edep_tot",
    "last_observed_layer",
)

# MV2 (range-energy) features: observed range + deposits.  The target (ekin) is
# deliberately excluded and exposed via MV2_TARGET_NAME.
MV2_FEATURE_NAMES: tuple[str, ...] = (
    "last_observed_layer",
    "edep_tot",
    "edep_l0",
    "nlayers",
    "tracklen_sum",
)

MV2_TARGET_NAME: str = "ekin"


def assert_no_target_leakage(feature_names: tuple[str, ...]) -> None:
    """Raise if any feature name is a known target/label column (ML-005)."""
    leaked = [k for k in feature_names if k in FORBIDDEN_FEATURE_KEYS]
    if leaked:
        raise ValueError(
            f"label/target leakage: feature vector includes {leaked}; "
            f"forbidden keys = {sorted(FORBIDDEN_FEATURE_KEYS)}"
        )


# Guard the module-level contracts at import time so a bad edit fails loudly.
assert_no_target_leakage(MV1_FEATURE_NAMES)
assert_no_target_leakage(MV2_FEATURE_NAMES)


def extract_mv1_features(track: dict[str, Any]) -> np.ndarray:
    """Return MV1 dE-E / stopping-depth feature vector for one track record."""
    return np.array(
        [
            float(track["edep_l0"]),
            float(track["edep_l1"]),
            float(track["edep_tot"]),
            float(track["last_observed_layer"]),
        ],
        dtype=np.float64,
    )


def extract_mv2_features(track: dict[str, Any]) -> np.ndarray:
    """Return MV2 range-energy feature vector for one track record (no target)."""
    return np.array(
        [
            float(track["last_observed_layer"]),
            float(track["edep_tot"]),
            float(track["edep_l0"]),
            float(track["nlayers"]),
            float(track["tracklen_sum"]),
        ],
        dtype=np.float64,
    )


def extract_mv2_target(track: dict[str, Any]) -> float:
    """Return the MV2 regression target (entry kinetic energy [MeV])."""
    return float(track[MV2_TARGET_NAME])


def extract_mv1_matrix(tracks: list[dict[str, Any]]) -> np.ndarray:
    """Stack MV1 features for many track records."""
    if not tracks:
        return np.empty((0, len(MV1_FEATURE_NAMES)), dtype=np.float64)
    return np.vstack([extract_mv1_features(t) for t in tracks])


def extract_mv2_matrix(tracks: list[dict[str, Any]]) -> np.ndarray:
    """Stack MV2 features (X) for many track records."""
    if not tracks:
        return np.empty((0, len(MV2_FEATURE_NAMES)), dtype=np.float64)
    return np.vstack([extract_mv2_features(t) for t in tracks])


def extract_mv2_target_vector(tracks: list[dict[str, Any]]) -> np.ndarray:
    """Stack the MV2 target (y) for many track records."""
    if not tracks:
        return np.empty((0,), dtype=np.float64)
    return np.array([extract_mv2_target(t) for t in tracks], dtype=np.float64)
