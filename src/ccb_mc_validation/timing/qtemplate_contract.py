"""qtemplate score contract (#965).

qtemplate is a useful ranking/diagnostic score, not a calibrated probability.
Until a held-out calibration exists, any authorising claim that treats a
qtemplate threshold as a validated acceptance probability must fail closed.
No operating-point numbers are invented here.
"""

from __future__ import annotations

from typing import Any, Mapping

QTEMPLATE_STATUS = "HEURISTIC_SCORE"
QTEMPLATE_AUDIT_ISSUE = 965
QTEMPLATE_CALIBRATION_STATUS = "UNCALIBRATED_NO_HELD_OUT_TRANSPORT"


def qtemplate_provenance(**extra: Any) -> dict[str, Any]:
    payload = {
        "score_id": "qtemplate",
        "status": QTEMPLATE_STATUS,
        "calibration_status": QTEMPLATE_CALIBRATION_STATUS,
        "authorising": False,
        "audit_issue": QTEMPLATE_AUDIT_ISSUE,
        "note": (
            "qtemplate remains a heuristic ranking score until thresholds are "
            "frozen on calibration data and evaluated on held-out runs (#965/#962)."
        ),
    }
    payload.update(extra)
    return payload


def assert_qtemplate_non_authorising(context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Fail closed if a caller attempts to mark qtemplate authorising."""
    ctx = dict(context or {})
    if bool(ctx.get("authorising")) or bool(ctx.get("authorising_claim")):
        raise ValueError(
            "qtemplate thresholds are HEURISTIC_SCORE only (#965); "
            "refusing authorising=True without held-out calibration provenance"
        )
    return qtemplate_provenance(**{k: v for k, v in ctx.items() if k not in {"authorising", "authorising_claim"}})
