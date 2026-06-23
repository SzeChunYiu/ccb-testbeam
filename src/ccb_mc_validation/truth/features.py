"""Truth feature vectors for MV1 (PID) and MV2 (range-energy) studies."""

from __future__ import annotations

from typing import Any

import numpy as np

MV1_FEATURE_NAMES = ("edep_l0", "edep_l1", "edep_tot", "stop_layer")
MV2_FEATURE_NAMES = ("stop_layer", "edep_tot", "edep_l0", "nlayers", "tracklen_sum", "ekin")


def extract_mv1_features(track: dict[str, Any]) -> np.ndarray:
    """Return MV1 dE-E / stopping-depth feature vector for one track record."""
    return np.array(
        [
            float(track["edep_l0"]),
            float(track["edep_l1"]),
            float(track["edep_tot"]),
            float(track["stop_layer"]),
        ],
        dtype=np.float64,
    )


def extract_mv2_features(track: dict[str, Any]) -> np.ndarray:
    """Return MV2 range-energy feature vector for one track record."""
    return np.array(
        [
            float(track["stop_layer"]),
            float(track["edep_tot"]),
            float(track["edep_l0"]),
            float(track["nlayers"]),
            float(track["tracklen_sum"]),
            float(track["ekin"]),
        ],
        dtype=np.float64,
    )


def extract_mv1_matrix(tracks: list[dict[str, Any]]) -> np.ndarray:
    """Stack MV1 features for many track records."""
    if not tracks:
        return np.empty((0, len(MV1_FEATURE_NAMES)), dtype=np.float64)
    return np.vstack([extract_mv1_features(t) for t in tracks])


def extract_mv2_matrix(tracks: list[dict[str, Any]]) -> np.ndarray:
    """Stack MV2 features for many track records."""
    if not tracks:
        return np.empty((0, len(MV2_FEATURE_NAMES)), dtype=np.float64)
    return np.vstack([extract_mv2_features(t) for t in tracks])
