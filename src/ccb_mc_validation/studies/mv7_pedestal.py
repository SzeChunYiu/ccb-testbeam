"""MV7: pedestal / baseline — Tier-2 NOT_RUN skeleton."""

from __future__ import annotations

from typing import Any

from ccb_mc_validation.studies.common import StudyResult, not_run_template


def run_mv7(config: dict[str, Any] | None = None) -> StudyResult:
    return not_run_template(
        "MV7",
        "MV7 forced/random pedestal validation not implemented — requires MV0 with known pedestal injection.",
        dependency="MV0",
        tier=2,
        target_mae_adc=config.get("target_mae_adc", 49) if config else 49,
    )
