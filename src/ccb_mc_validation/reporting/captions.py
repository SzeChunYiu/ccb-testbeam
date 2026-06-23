"""Figure caption validation."""

from __future__ import annotations

import re

from ccb_mc_validation.exceptions import ReportValidationError

_MAX_CAPTION_LEN = 500
_FORBIDDEN_PATTERNS = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bfake\b", re.IGNORECASE),
)


def validate_caption(caption: str) -> str:
    """Validate and return a trimmed caption string."""
    text = caption.strip()
    if not text:
        raise ReportValidationError("caption must be non-empty")
    if len(text) > _MAX_CAPTION_LEN:
        raise ReportValidationError(f"caption exceeds {_MAX_CAPTION_LEN} characters")
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(text):
            raise ReportValidationError(f"caption contains forbidden token: {pattern.pattern}")
    return text
