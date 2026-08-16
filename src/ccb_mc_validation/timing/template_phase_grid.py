"""Template-phase shift-grid quantization contract (#1064).

The real-data template branch evaluates a discrete shift lattice. Sub-grid
interpolation is not applied. Any authorising claim that implies finer timing
resolution than half the grid step must fail closed until numerical closure
exists. No continuous-fit physics is invented here.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

TEMPLATE_PHASE_GRID_STEP_SAMPLES = 0.05
TEMPLATE_PHASE_GRID_LO = -1.5
TEMPLATE_PHASE_GRID_HI = 1.55  # stop of np.arange(-1.5, 1.55, 0.05)
TEMPLATE_PHASE_SOLVER_ID = "sse_argmin_uniform_grid_v1"
TEMPLATE_PHASE_AUDIT_ISSUE = 1064


def default_template_phase_grid(step: float = TEMPLATE_PHASE_GRID_STEP_SAMPLES) -> np.ndarray:
    step = float(step)
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError(f"template phase grid step must be finite and > 0, got {step!r}")
    return np.arange(TEMPLATE_PHASE_GRID_LO, TEMPLATE_PHASE_GRID_HI, step)


def template_phase_grid_contract(
    *,
    sample_period_ns: float,
    grid_step_samples: float = TEMPLATE_PHASE_GRID_STEP_SAMPLES,
) -> dict[str, Any]:
    period = float(sample_period_ns)
    step = float(grid_step_samples)
    if not np.isfinite(period) or period <= 0.0:
        raise ValueError(f"sample_period_ns must be finite and > 0, got {sample_period_ns!r}")
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError(f"grid_step_samples must be finite and > 0, got {grid_step_samples!r}")
    step_ns = step * period
    return {
        "solver_id": TEMPLATE_PHASE_SOLVER_ID,
        "grid_step_samples": step,
        "grid_step_ns": step_ns,
        "grid_half_step_ns": 0.5 * step_ns,
        "grid_lo_samples": TEMPLATE_PHASE_GRID_LO,
        "grid_hi_exclusive_samples": TEMPLATE_PHASE_GRID_HI,
        "interpolation": "NONE",
        "authorising_sub_grid_claims": False,
        "audit_issue": TEMPLATE_PHASE_AUDIT_ISSUE,
        "note": (
            "Phase is quantized to the SSE argmin on a uniform sample grid; "
            "sub-grid continuous minimization is not applied (#1064)."
        ),
    }


def assert_template_resolution_authorised(
    claimed_resolution_ns: float,
    *,
    sample_period_ns: float,
    grid_step_samples: float = TEMPLATE_PHASE_GRID_STEP_SAMPLES,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed when an authorising claim is finer than half the grid step."""
    contract = template_phase_grid_contract(
        sample_period_ns=sample_period_ns,
        grid_step_samples=grid_step_samples,
    )
    ctx = dict(context or {})
    authorising = bool(ctx.get("authorising", True))
    claimed = float(claimed_resolution_ns)
    if not np.isfinite(claimed) or claimed <= 0.0:
        raise ValueError(f"claimed_resolution_ns must be finite and > 0, got {claimed_resolution_ns!r}")
    if authorising and claimed < contract["grid_half_step_ns"]:
        raise ValueError(
            f"authorising timing resolution {claimed} ns is finer than half the "
            f"template-phase grid step ({contract['grid_half_step_ns']} ns); "
            f"blocked pending numerical closure (#1064)"
        )
    contract = dict(contract)
    contract["claimed_resolution_ns"] = claimed
    contract["authorising"] = authorising
    return contract
