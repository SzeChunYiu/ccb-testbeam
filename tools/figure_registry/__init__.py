"""CCB test-beam paper-figure result registry + validated figure builder.

Replaces the pattern where ``scripts/generate_publication_figures.py`` embedded
headline values as Python constants and mixed illustrative schematics with
quantitative figures (KNOWN_CODE_DEFECTS.md + v2 governance finding #10).

Public API::

    from tools.figure_registry import (
        Entry, load_registry, validate_registry,
        build, FigureRegistryError,
        ALLOWED_STATUSES, ALLOWED_KINDS, sha256_file,
    )
"""
from __future__ import annotations

from .builder import FigureRegistryError, build, main, sha256_file
from .registry import (
    ALLOWED_KINDS,
    ALLOWED_STATUSES,
    DEFAULT_UNCERTAINTY_KEY,
    Entry,
    load_registry,
    validate_registry,
)

__all__ = [
    "Entry",
    "load_registry",
    "validate_registry",
    "build",
    "main",
    "sha256_file",
    "FigureRegistryError",
    "ALLOWED_STATUSES",
    "ALLOWED_KINDS",
    "DEFAULT_UNCERTAINTY_KEY",
]
