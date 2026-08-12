"""Timing contracts, template-grid gates, and TOF surrogate gates."""

from ccb_mc_validation.timing.template_grid_contract import (
    DEFAULT_GRID_STEP_SAMPLES,
    NOMINAL_SAMPLE_PERIOD_NS,
    TemplateGridContract,
    assert_authorizing_resolution_compatible,
    grid_step_ns,
)

__all__ = [
    "DEFAULT_GRID_STEP_SAMPLES",
    "NOMINAL_SAMPLE_PERIOD_NS",
    "TemplateGridContract",
    "assert_authorizing_resolution_compatible",
    "grid_step_ns",
]
