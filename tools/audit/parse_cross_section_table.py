"""Fail-closed CM cross-section table parsing (issue #1056).

Mirrors the validated ScatteringGenerator::LoadCrossSection contract:
finite angles in (0, 180) deg, nonnegative sigma, strictly increasing angles,
at least two rows. Malformed / nonfinite / nonmonotonic tables raise.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path


class CrossSectionTableError(ValueError):
    """Raised when a cross-section table fails closed validation."""


@dataclass(frozen=True)
class CrossSectionTable:
    angles_rad: tuple[float, ...]
    sigma: tuple[float, ...]
    path: str | None = None

    @property
    def n_rows(self) -> int:
        return len(self.angles_rad)


def parse_cross_section_table_text(text: str, *, path: str | None = None) -> CrossSectionTable:
    """Parse a whitespace-delimited (angle_deg, sigma[, ...]) table fail-closed."""
    angles: list[float] = []
    sigma: list[float] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            raise CrossSectionTableError(
                f"CCB_CS_PARSE: malformed cross-section row {line_no}"
            )
        try:
            angle_deg = float(fields[0])
            cross_section = float(fields[1])
        except ValueError as exc:
            raise CrossSectionTableError(
                f"CCB_CS_PARSE: malformed cross-section row {line_no}"
            ) from exc
        if (
            not math.isfinite(angle_deg)
            or not math.isfinite(cross_section)
            or not (angle_deg > 0.0)
            or not (angle_deg < 180.0)
            or cross_section < 0.0
        ):
            raise CrossSectionTableError(
                f"CCB_CS_DOMAIN: invalid cross-section values at row {line_no}"
            )
        angle_rad = angle_deg * math.pi / 180.0
        if angles and not (angle_rad > angles[-1]):
            raise CrossSectionTableError(
                f"CCB_CS_ORDER: cross-section angles must be strictly increasing; row {line_no}"
            )
        angles.append(angle_rad)
        sigma.append(cross_section)
    if len(angles) < 2 or len(sigma) != len(angles):
        raise CrossSectionTableError(
            "CCB_CS_CARDINALITY: configured cross-section table requires at least two valid rows"
        )
    return CrossSectionTable(tuple(angles), tuple(sigma), path=path)


def parse_cross_section_table_file(path: Path) -> CrossSectionTable:
    return parse_cross_section_table_text(path.read_text(encoding="ascii"), path=str(path))


def assert_scattering_generator_fail_closed_parser(source_text: str) -> None:
    """Freeze the C++ LoadCrossSection fail-closed tokens (issue #1056)."""
    required = (
        "CCB_CS_PARSE",
        "CCB_CS_DOMAIN",
        "CCB_CS_ORDER",
        "CCB_CS_CARDINALITY",
        "FatalSourceError",
    )
    missing = [token for token in required if token not in source_text]
    if missing:
        raise AssertionError(f"missing fail-closed tokens: {missing}")
    if re.search(
        r'sscanf\s*\(\s*line\s*,\s*"%lf\\t%lf\\t%\*f\\n"\s*,\s*&tmpA\s*,\s*&tmpCS\s*\)\s*;',
        source_text,
    ):
        raise AssertionError("legacy unchecked sscanf parser is still present")
