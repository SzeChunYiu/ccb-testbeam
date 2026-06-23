"""MV5: pile-up & two-pulse recovery — Tier-2 NOT_RUN skeleton."""

from __future__ import annotations

from typing import Any

from ccb_mc_validation.studies.common import StudyResult, not_run_template


def run_mv5(config: dict[str, Any] | None = None) -> StudyResult:
    """Return NOT_RUN skeleton with overlay grid configuration."""
    config = config or {}
    overlay_grid = config.get(
        "overlay_grid",
        {
            "beam_rate_MHz": [0.5, 1.0, 2.0, 3.0],
            "tau_eff_ns": [200, 350, 500],
            "max_pileup_fraction": 0.15,
        },
    )
    return not_run_template(
        "MV5",
        "MV5 pile-up overlay study not implemented — requires MV0 digitizer + event overlay.",
        dependency="MV0",
        tier=2,
        overlay_grid=overlay_grid,
    )
