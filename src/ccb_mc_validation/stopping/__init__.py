"""Stopping-power estimator identity contracts."""

from ccb_mc_validation.stopping.primary_track_contract import (
    EVENT_TOTAL_SCOPE,
    PRIMARY_SCOPE,
    classify_track_length_scope,
    require_primary_scope_for_pstar,
)

__all__ = [
    "EVENT_TOTAL_SCOPE",
    "PRIMARY_SCOPE",
    "classify_track_length_scope",
    "require_primary_scope_for_pstar",
]
