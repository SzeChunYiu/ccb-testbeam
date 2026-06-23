"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone


class _UtcFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z"


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with UTC timestamps."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        _UtcFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(numeric)
    root.addHandler(handler)
