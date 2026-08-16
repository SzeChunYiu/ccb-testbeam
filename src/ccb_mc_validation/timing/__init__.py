"""Timing contracts, template-grid gates, and TOF surrogate gates."""

from ccb_mc_validation.timing.b2_broad_residual_mechanisms import (
    AUTHORISING_PILEUP_LIKE,
    BroadResidualMechanism,
    DiscriminantEvidence,
    REQUIRED_DISCRIMINANTS,
    authorize_pileup_like_wording,
    classify_b2_broad_residual_support,
)
from ccb_mc_validation.timing.template_grid_contract import (
    DEFAULT_GRID_STEP_SAMPLES,
    NOMINAL_SAMPLE_PERIOD_NS,
    TemplateGridContract,
    assert_authorizing_resolution_compatible,
    grid_step_ns,
)

__all__ = [
    "AUTHORISING_PILEUP_LIKE",
    "BroadResidualMechanism",
    "DEFAULT_GRID_STEP_SAMPLES",
    "DiscriminantEvidence",
    "NOMINAL_SAMPLE_PERIOD_NS",
    "REQUIRED_DISCRIMINANTS",
    "TemplateGridContract",
    "assert_authorizing_resolution_compatible",
    "authorize_pileup_like_wording",
    "classify_b2_broad_residual_support",
    "grid_step_ns",
]
