"""Step-size convergence contracts for Geant4 visible-energy response (#1095)."""

from ccb_mc_validation.step_convergence.registry import (
    REGISTRY_VERSION,
    StepConvergenceProfile,
    list_profile_ids,
    load_registry_index,
    load_step_convergence_profile,
    require_step_convergence_profile,
)

__all__ = [
    "REGISTRY_VERSION",
    "StepConvergenceProfile",
    "list_profile_ids",
    "load_registry_index",
    "load_step_convergence_profile",
    "require_step_convergence_profile",
]
