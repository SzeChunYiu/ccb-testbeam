#!/usr/bin/env python3
"""Validate that PSTAR total stopping power matches rounded component sums.

NIST defines proton total stopping power as the sum of electronic and nuclear
stopping powers. This validator preserves the decimal precision written in the
CSV and accepts a row only when the rounding intervals of the declared total
and the component sum overlap.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

TOOL_VERSION = "1.0.0"
REQUIRED_COLUMNS = (
    "energy_MeV",
    "electronic_MeV_cm2_g",
    "nuclear_MeV_cm2_g",
    "total_MeV_cm2_g",
)


class PstarComponentError(ValueError):
    """Raised when a PSTAR row cannot support a component-sum check."""


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of exact file bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_data_lines(path: Path) -> list[tuple[int, str]]:
    try:
        lines = path.read_text().splitlines(keepends=True)
    except OSError as exc:
        raise PstarComponentError(f"cannot read PSTAR table {path}: {exc}") from exc
    data_lines = [
        (line_no, line)
        for line_no, line in enumerate(lines, start=1)
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not data_lines:
        raise PstarComponentError(f"PSTAR table has no CSV header: {path}")
    return data_lines


def _parse_decimal(
    row: dict[str | None, str | None],
    column: str,
    *,
    path: Path,
    line_no: int,
) -> tuple[Decimal, Decimal]:
    token = row.get(column)
    if token is None or token.strip() == "":
        raise PstarComponentError(
            f"PSTAR table {path} line {line_no} has no value in {column}"
        )
    token = token.strip()
    try:
        value = Decimal(token)
    except InvalidOperation as exc:
        raise PstarComponentError(
            f"PSTAR table {path} line {line_no} has nonnumeric value {token!r} "
            f"in {column}"
        ) from exc
    if not value.is_finite():
        raise PstarComponentError(
            f"PSTAR table {path} line {line_no} has nonfinite value {token!r} "
            f"in {column}"
        )
    half_unit = abs(Decimal(1).scaleb(value.as_tuple().exponent)) / 2
    return value, half_unit


def _interval(value: Decimal, half_unit: Decimal) -> tuple[Decimal, Decimal]:
    return value - half_unit, value + half_unit


def validate_pstar_component_sum(path: Path) -> dict[str, object]:
    """Validate every PSTAR row against decimal-rounding component intervals."""
    path = Path(path)
    data_lines = _read_data_lines(path)
    header_line, header_text = data_lines[0]
    try:
        header = next(csv.reader([header_text]))
    except csv.Error as exc:
        raise PstarComponentError(
            f"PSTAR table {path} line {header_line} has an invalid CSV header"
        ) from exc
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise PstarComponentError(
            f"PSTAR table {path} line {header_line} is missing required column(s): "
            + ", ".join(missing)
        )

    rows_validated = 0
    previous_energy: Decimal | None = None
    minimum_overlap_margin: Decimal | None = None
    maximum_overlap_margin = Decimal("0")
    reader = csv.DictReader([line for _, line in data_lines])
    for (line_no, _), row in zip(data_lines[1:], reader, strict=True):
        if None in row:
            raise PstarComponentError(
                f"PSTAR table {path} line {line_no} has excess fields"
            )
        energy, _ = _parse_decimal(
            row, "energy_MeV", path=path, line_no=line_no
        )
        electronic, electronic_half = _parse_decimal(
            row, "electronic_MeV_cm2_g", path=path, line_no=line_no
        )
        nuclear, nuclear_half = _parse_decimal(
            row, "nuclear_MeV_cm2_g", path=path, line_no=line_no
        )
        total, total_half = _parse_decimal(
            row, "total_MeV_cm2_g", path=path, line_no=line_no
        )
        if energy <= 0 or electronic < 0 or nuclear < 0 or total <= 0:
            raise PstarComponentError(
                f"PSTAR table {path} line {line_no} has nonphysical values "
                f"energy={energy}, electronic={electronic}, nuclear={nuclear}, "
                f"total={total}"
            )
        if previous_energy is not None and energy <= previous_energy:
            raise PstarComponentError(
                f"PSTAR table {path} line {line_no} energy {energy} MeV is not "
                f"strictly greater than previous energy {previous_energy} MeV"
            )

        component_sum = electronic + nuclear
        component_half = electronic_half + nuclear_half
        sum_low, sum_high = _interval(component_sum, component_half)
        total_low, total_high = _interval(total, total_half)
        overlap_low = max(sum_low, total_low)
        overlap_high = min(sum_high, total_high)
        if overlap_low > overlap_high:
            gap = overlap_low - overlap_high
            raise PstarComponentError(
                f"PSTAR table {path} line {line_no} total stopping power is "
                f"inconsistent with electronic+nuclear after declared rounding: "
                f"sum_interval=[{sum_low}, {sum_high}], "
                f"total_interval=[{total_low}, {total_high}], gap={gap}"
            )
        overlap_margin = overlap_high - overlap_low
        if minimum_overlap_margin is None:
            minimum_overlap_margin = overlap_margin
        else:
            minimum_overlap_margin = min(minimum_overlap_margin, overlap_margin)
        maximum_overlap_margin = max(maximum_overlap_margin, overlap_margin)
        rows_validated += 1
        previous_energy = energy

    if rows_validated < 2:
        raise PstarComponentError(
            f"PSTAR table must contain at least two validated rows: {path}"
        )

    return {
        "schema_version": 1,
        "tool": "tools/audit/validate_pstar_component_sum.py",
        "tool_version": TOOL_VERSION,
        "status": "VALIDATED",
        "input_path": str(path),
        "input_bytes": path.stat().st_size,
        "input_sha256": sha256_file(path),
        "rows_validated": rows_validated,
        "required_columns": list(REQUIRED_COLUMNS),
        "component_identity": "total = electronic + nuclear",
        "rounding_model": "half unit in the last written decimal place",
        "all_rows_component_consistent": True,
        "minimum_interval_overlap_width_MeV_cm2_g": str(minimum_overlap_margin),
        "maximum_interval_overlap_width_MeV_cm2_g": str(maximum_overlap_margin),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="PSTAR CSV table")
    parser.add_argument("--output", type=Path, help="write validation JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_pstar_component_sum(args.input)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except (OSError, PstarComponentError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "PSTAR component sum: "
        f"status={result['status']} rows={result['rows_validated']} "
        f"sha256={result['input_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
