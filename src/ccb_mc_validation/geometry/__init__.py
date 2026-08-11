"""Versioned geometry / mapping / kinematics hypothesis registry (Wave A Lane 03).

Physical contradictions (#987, #989, #991, #992) are recorded as named
HYPOTHESIS profiles. Callers must select ``geometry_profile_id`` explicitly;
there is no silent default. See ``docs/adr/ADR-0002-geometry-kinematics-hypotheses.md``.
"""

from ccb_mc_validation.geometry.beam_intersection import (
    BeamIntersectionResult,
    validate_beam_intersection,
)
from ccb_mc_validation.geometry.registry import (
    REGISTRY_VERSION,
    GeometryProfile,
    geometry_profile_digest,
    list_profile_ids,
    load_registry_index,
    require_geometry_profile,
    require_spacing_hypothesis_for_tof,
)

__all__ = [
    "REGISTRY_VERSION",
    "BeamIntersectionResult",
    "GeometryProfile",
    "geometry_profile_digest",
    "list_profile_ids",
    "load_registry_index",
    "require_geometry_profile",
    "validate_beam_intersection",
]
