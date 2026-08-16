"""CCB paper-figure registry and fail-closed builder."""
from __future__ import annotations

from .builder import FigureRegistryError, build, main, sha256_file
from .registry import (
    ALLOWED_KINDS,
    ALLOWED_STATUSES,
    DEFAULT_UNCERTAINTY_KEY,
    REGISTRY_SNAPSHOT_METHOD,
    STATUS_DISPOSITIONS,
    Entry,
    RegistryFormatError,
    RegistrySnapshot,
    load_registry,
    load_registry_snapshot,
    validate_registry,
)

__all__ = [
    "Entry",
    "RegistryFormatError",
    "RegistrySnapshot",
    "load_registry",
    "load_registry_snapshot",
    "validate_registry",
    "build",
    "main",
    "sha256_file",
    "FigureRegistryError",
    "ALLOWED_STATUSES",
    "ALLOWED_KINDS",
    "STATUS_DISPOSITIONS",
    "DEFAULT_UNCERTAINTY_KEY",
    "REGISTRY_SNAPSHOT_METHOD",
]
