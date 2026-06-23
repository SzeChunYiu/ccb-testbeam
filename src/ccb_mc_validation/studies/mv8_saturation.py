"""MV8: saturation recovery — Tier-2 NOT_RUN skeleton."""

from __future__ import annotations

from typing import Any

from ccb_mc_validation.studies.common import StudyResult, not_run_template


def run_mv8(config: dict[str, Any] | None = None) -> StudyResult:
    return not_run_template(
        "MV8",
        "MV8 natural saturation recovery study not implemented — requires MV0 with saturation flag.",
        dependency="MV0",
        tier=2,
        adc_ceiling=config.get("adc_ceiling", 7000) if config else 7000,
    )
