"""MV4: timing resolution & timewalk — Tier-2, requires MV0 digitizer."""

from __future__ import annotations

from typing import Any

from ccb_mc_validation.studies.common import (
    StudyBlockedError,
    StudyResult,
    StudyStatus,
    blocked_template,
    not_run_template,
)


def run_mv4(
    config: dict[str, Any] | None = None,
    *,
    digitizer_ready: bool = False,
    raise_if_blocked: bool = False,
) -> StudyResult:
    """
    MV4 timing study placeholder.

    Raises StudyBlockedError when ``raise_if_blocked=True`` and MV0 digitizer
    is not available; otherwise returns a NOT_RUN template.
    """
    config = config or {}
    reason = config.get(
        "block_reason",
        "MV4 requires MV0 digitizer (Tier-2): truth hits must be converted to "
        "18-sample ADC waveforms before CFD/OF/template pickoff comparison.",
    )
    if not digitizer_ready:
        if raise_if_blocked:
            raise StudyBlockedError(reason)
        return not_run_template(
            "MV4",
            reason,
            dependency="MV0",
            tier=2,
        )
    return blocked_template("MV4", "digitizer_ready flag set but MV4 implementation pending")
