"""Template-phase grid quantization contract (#1064).

The SSE template-phase estimator evaluates a discrete shift lattice (default
0.05 sample). Sub-grid continuous fits are alternate hypotheses and must not
be silently treated as the production estimator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ccb_mc_validation.exceptions import DataContractError, StudyBlockedError

DEFAULT_GRID_STEP_SAMPLES = 0.05
NOMINAL_SAMPLE_PERIOD_NS = 10.0  # analysis assumption; hardware lock is #1014


@dataclass(frozen=True)
class TemplateGridContract:
    grid_step_samples: float
    sample_period_ns: float
    interpolation: str  # "none" | "local_parabola" | "continuous_optimizer" | ...
    claims_authorized: bool

    @property
    def grid_step_ns(self) -> float:
        return float(self.grid_step_samples) * float(self.sample_period_ns)

    def as_dict(self) -> dict[str, Any]:
        return {
            "grid_step_samples": self.grid_step_samples,
            "sample_period_ns": self.sample_period_ns,
            "grid_step_ns": self.grid_step_ns,
            "interpolation": self.interpolation,
            "claims_authorized": self.claims_authorized,
            "issue": 1064,
            "note": (
                "Discrete template-phase lattice; sub-grid resolution is not "
                "authorized without an explicit interpolation hypothesis and "
                "held-out closure (#1064)."
            ),
        }


def grid_step_ns(
    grid_step_samples: float = DEFAULT_GRID_STEP_SAMPLES,
    sample_period_ns: float = NOMINAL_SAMPLE_PERIOD_NS,
) -> float:
    if grid_step_samples <= 0 or sample_period_ns <= 0:
        raise DataContractError("template grid step and sample period must be positive")
    return float(grid_step_samples) * float(sample_period_ns)


def assert_authorizing_resolution_compatible(
    claimed_resolution_ns: float,
    *,
    config: Mapping[str, Any] | None = None,
) -> TemplateGridContract:
    """Refuse authorizing timing claims finer than the discrete grid without interpolation.

    Does not invent a continuous fit. Selecting interpolation != "none" without
    an implemented estimator still leaves claims_authorized=false.
    """
    cfg = dict(config or {})
    step_s = float(cfg.get("template_grid_step_samples", DEFAULT_GRID_STEP_SAMPLES))
    period = float(cfg.get("sample_period_ns", NOMINAL_SAMPLE_PERIOD_NS))
    interp = str(cfg.get("template_phase_interpolation", "none")).strip().lower()
    step_ns = grid_step_ns(step_s, period)
    # Only the currently implemented discrete-min estimator may authorize, and
    # only for claimed resolutions that do not pretend to beat the lattice.
    implemented = interp == "none"
    authorized = implemented  # still subject to resolution check below
    contract = TemplateGridContract(
        grid_step_samples=step_s,
        sample_period_ns=period,
        interpolation=interp,
        claims_authorized=authorized,
    )
    if not implemented:
        raise StudyBlockedError(
            f"template_phase_interpolation={interp!r} is not an implemented "
            f"production estimator (#1064); discrete-grid claims only. "
            f"Contract={contract.as_dict()}"
        )
    if claimed_resolution_ns < step_ns:
        raise StudyBlockedError(
            f"claimed timing resolution {claimed_resolution_ns} ns is finer than "
            f"the discrete template grid step {step_ns} ns "
            f"({step_s} sample × {period} ns/sample) without sub-grid "
            f"interpolation (#1064)"
        )
    return contract
