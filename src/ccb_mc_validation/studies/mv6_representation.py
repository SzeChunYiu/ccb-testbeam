"""MV6: pulse-shape & representation — Tier-2 NOT_RUN skeleton."""

from __future__ import annotations

from typing import Any

from ccb_mc_validation.studies.common import StudyResult, not_run_template


def run_mv6(config: dict[str, Any] | None = None) -> StudyResult:
    return not_run_template(
        "MV6",
        "MV6 pulse-shape low-dimensionality study not implemented — requires MV0 digitizer.",
        dependency="MV0",
        tier=2,
        methods=config.get("methods", ["pca", "autoencoder"]) if config else ["pca", "autoencoder"],
    )
