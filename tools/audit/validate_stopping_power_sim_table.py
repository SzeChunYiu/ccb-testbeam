#!/usr/bin/env python3
"""Fail-closed validation for stopping-power simulation event CSV inputs.

The parser in this module is the canonical simulation-table ingestion path for
``scripts/single_stave/compare_stopping_power.py``. It validates every
noncomment event row before any aggregation or PSTAR comparison is allowed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

TOOL_VERSION = "1.1.0"
ENERGY_ALIASES = ("ke_MeV", "kinetic_energy_MeV", "energy_MeV")
RAW_EDEP_ALIASES = ("edep_scint_raw_MeV", "edep_raw_MeV")
QUENCHED_EDEP_ALIASES = ("edep_scint_MeV", "edep_MeV")
TRACK_MM_ALIASES = ("track_len_scint_mm", "track_length_scint_mm")
TRACK_CM_ALIASES = ("track_length_scint_cm", "track_len_scint_cm")
PARTICLE_NAMES = {
    "p": "proton",
    "proton": "proton",
    "d": "deuteron",
    "deuteron": "deuteron",
}
RAW_BASIS = "UNQUENCHED_RAW"
QUENCHED_BASIS = "QUENCHED_PROXY"
NormalizedRow = tuple[str, float, float, float]


class SimulationTableError(ValueError):
    """Raised when a simulation table cannot support a traceable comparison."""


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest of the exact input bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def populated_aliases(
    row: dict[str | None, str | None], aliases: Iterable[str]
) -> list[str]:
    """Return aliases with nonempty values in the current CSV row."""
    return [
        alias
        for alias in aliases
        if alias in row and row[alias] is not None and row[alias].strip() != ""
    ]


def require_single_alias(
    row: dict[str | None, str | None],
    aliases: Iterable[str],
    *,
    path: Path,
    line_no: int,
    quantity: str,
) -> str:
    """Require exactly one populated alias for one physical quantity."""
    populated = populated_aliases(row, aliases)
    if not populated:
        raise SimulationTableError(
            f"simulation table {path} line {line_no} has no {quantity} value"
        )
    if len(populated) > 1:
        raise SimulationTableError(
            f"simulation table {path} line {line_no} has ambiguous {quantity} aliases: "
            + ", ".join(populated)
        )
    return populated[0]


def parse_finite(
    row: dict[str | None, str | None],
    column: str,
    *,
    path: Path,
    line_no: int,
    quantity: str,
) -> float:
    """Parse one required finite numeric field."""
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise SimulationTableError(
            f"simulation table {path} line {line_no} has nonnumeric {quantity} "
            f"in column {column}"
        ) from exc
    if not math.isfinite(value):
        raise SimulationTableError(
            f"simulation table {path} line {line_no} has nonfinite {quantity} "
            f"in column {column}"
        )
    return value


def _read_data_lines(path: Path) -> list[tuple[int, str]]:
    try:
        raw_lines = path.read_text().splitlines(keepends=True)
    except OSError as exc:
        raise SimulationTableError(f"cannot read simulation table {path}: {exc}") from exc
    data_lines = [
        (line_no, line)
        for line_no, line in enumerate(raw_lines, start=1)
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not data_lines:
        raise SimulationTableError(f"simulation table has no CSV header: {path}")
    return data_lines


def _validate_header(path: Path, data_lines: list[tuple[int, str]]) -> list[str]:
    header_line, header_text = data_lines[0]
    try:
        header = next(csv.reader([header_text]))
    except csv.Error as exc:
        raise SimulationTableError(
            f"simulation table {path} line {header_line} has an invalid CSV header"
        ) from exc
    if not header or any(column.strip() == "" for column in header):
        raise SimulationTableError(
            f"simulation table {path} line {header_line} has an empty header field"
        )
    if len(header) != len(set(header)):
        raise SimulationTableError(
            f"simulation table {path} line {header_line} has duplicate header fields"
        )
    if "particle" not in header:
        raise SimulationTableError(f"simulation table {path} is missing particle column")
    for quantity, aliases in [
        ("energy", ENERGY_ALIASES),
        ("energy-deposit", RAW_EDEP_ALIASES + QUENCHED_EDEP_ALIASES),
        ("track-length", TRACK_MM_ALIASES + TRACK_CM_ALIASES),
    ]:
        if not set(aliases).intersection(header):
            raise SimulationTableError(
                f"simulation table {path} is missing a supported {quantity} column"
            )
    return header


def read_validated_simulation_table(
    path: Path,
    *,
    allow_quenched_proxy: bool = False,
) -> tuple[list[NormalizedRow], dict[str, object]]:
    """Return normalized rows plus provenance after validating every event row."""
    path = Path(path)
    data_lines = _read_data_lines(path)
    header = _validate_header(path, data_lines)

    particles: Counter[str] = Counter()
    energies: list[float] = []
    bases: set[str] = set()
    normalized_rows: list[NormalizedRow] = []
    reader = csv.DictReader([line for _, line in data_lines])
    for (line_no, _), row in zip(data_lines[1:], reader, strict=True):
        if None in row:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has excess fields"
            )
        particle_text = (row.get("particle") or "").strip().lower()
        if not particle_text:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has no particle value"
            )
        if particle_text not in PARTICLE_NAMES:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has unsupported particle "
                f"{particle_text!r}; use proton|deuteron (or p|d)"
            )
        particle = PARTICLE_NAMES[particle_text]

        energy_column = require_single_alias(
            row,
            ENERGY_ALIASES,
            path=path,
            line_no=line_no,
            quantity="energy",
        )
        energy = parse_finite(
            row,
            energy_column,
            path=path,
            line_no=line_no,
            quantity="energy",
        )
        if energy <= 0:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has nonpositive energy {energy!r}"
            )

        raw_columns = populated_aliases(row, RAW_EDEP_ALIASES)
        quenched_columns = populated_aliases(row, QUENCHED_EDEP_ALIASES)
        if len(raw_columns) > 1 or len(quenched_columns) > 1:
            columns = raw_columns if len(raw_columns) > 1 else quenched_columns
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has ambiguous energy-deposit "
                "aliases: " + ", ".join(columns)
            )
        if raw_columns and quenched_columns:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} populates raw and quenched "
                "energy-deposit fields simultaneously"
            )
        if raw_columns:
            deposit_column = raw_columns[0]
            basis = RAW_BASIS
        elif quenched_columns:
            if not allow_quenched_proxy:
                raise SimulationTableError(
                    f"simulation table {path} line {line_no} provides only quenched "
                    "energy deposit; use --allow-quenched-proxy for a labelled, "
                    "non-accepting diagnostic preflight"
                )
            deposit_column = quenched_columns[0]
            basis = QUENCHED_BASIS
        else:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has no energy-deposit value"
            )
        deposit = parse_finite(
            row,
            deposit_column,
            path=path,
            line_no=line_no,
            quantity="energy deposit",
        )
        if deposit < 0:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has negative energy deposit "
                f"{deposit!r}"
            )

        track_column = require_single_alias(
            row,
            TRACK_MM_ALIASES + TRACK_CM_ALIASES,
            path=path,
            line_no=line_no,
            quantity="track length",
        )
        track_value = parse_finite(
            row,
            track_column,
            path=path,
            line_no=line_no,
            quantity="track length",
        )
        track_mm = track_value * 10.0 if track_column in TRACK_CM_ALIASES else track_value
        if track_mm <= 0:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has nonpositive track length "
                f"{track_mm!r} mm"
            )

        particles[particle] += 1
        energies.append(energy)
        bases.add(basis)
        normalized_rows.append((particle, energy, deposit, track_mm))

    if not normalized_rows:
        raise SimulationTableError(f"simulation table has no event rows: {path}")
    if len(bases) != 1:
        raise SimulationTableError(
            f"simulation table {path} mixes unquenched and quenched energy-deposit "
            "semantics across rows"
        )
    basis = next(iter(bases))
    summary: dict[str, object] = {
        "schema_version": 1,
        "tool": "tools/audit/validate_stopping_power_sim_table.py",
        "tool_version": TOOL_VERSION,
        "status": "VALIDATED" if basis == RAW_BASIS else "DIAGNOSTIC_ONLY",
        "input_path": str(path),
        "input_bytes": path.stat().st_size,
        "input_sha256": sha256_file(path),
        "header": header,
        "rows_validated": len(normalized_rows),
        "particle_counts": dict(sorted(particles.items())),
        "energy_min_MeV": min(energies),
        "energy_max_MeV": max(energies),
        "energy_deposit_basis": basis,
        "raw_pstar_comparable": basis == RAW_BASIS,
        "all_noncomment_rows_validated": True,
        "silent_row_skipping_permitted": False,
        "normalized_rows_returned": len(normalized_rows),
    }
    return normalized_rows, summary


def validate_simulation_table(
    path: Path,
    *,
    allow_quenched_proxy: bool = False,
) -> dict[str, object]:
    """Validate every event row and return provenance without returning row data."""
    _, summary = read_validated_simulation_table(
        path,
        allow_quenched_proxy=allow_quenched_proxy,
    )
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="simulation event CSV")
    parser.add_argument("--output", type=Path, help="write validation JSON")
    parser.add_argument(
        "--allow-quenched-proxy",
        action="store_true",
        help="permit quenched-only tables as labelled DIAGNOSTIC_ONLY input",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_simulation_table(
            args.input,
            allow_quenched_proxy=args.allow_quenched_proxy,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except (OSError, SimulationTableError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "stopping-power sim table: "
        f"status={result['status']} rows={result['rows_validated']} "
        f"basis={result['energy_deposit_basis']} sha256={result['input_sha256']}"
    )
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
