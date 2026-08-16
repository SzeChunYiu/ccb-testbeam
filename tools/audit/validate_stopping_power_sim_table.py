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

TOOL_VERSION = "1.3.0-waveC-lane05"
INPUT_SNAPSHOT_METHOD = "SINGLE_READ_EXACT_BYTES"
ENERGY_ALIASES = ("ke_MeV", "kinetic_energy_MeV", "energy_MeV")
RAW_EDEP_ALIASES = ("edep_scint_raw_MeV", "edep_raw_MeV")
QUENCHED_EDEP_ALIASES = ("edep_scint_MeV", "edep_MeV")
TRACK_MM_ALIASES = ("track_len_scint_mm", "track_length_scint_mm")
TRACK_CM_ALIASES = ("track_length_scint_cm", "track_len_scint_cm")
PRIMARY_TRACK_MM_ALIASES = (
    "primary_track_len_scint_mm",
    "primary_track_length_scint_mm",
)
PRIMARY_TRACK_CM_ALIASES = (
    "primary_track_length_scint_cm",
    "primary_track_len_scint_cm",
)
PRIMARY_RAW_EDEP_ALIASES = (
    "primary_edep_scint_raw_MeV",
    "primary_edep_raw_MeV",
)
PRIMARY_QUENCHED_EDEP_ALIASES = (
    "primary_edep_scint_MeV",
    "primary_edep_MeV",
)
PRIMARY_SCOPE = "PRIMARY_TRACK"
EVENT_TOTAL_SCOPE = "EVENT_TOTAL_ALL_NON_OPTICAL"
PARTICLE_NAMES = {
    "p": "proton",
    "proton": "proton",
    "d": "deuteron",
    "deuteron": "deuteron",
}
RAW_BASIS = "UNQUENCHED_RAW"
QUENCHED_BASIS = "QUENCHED_PROXY"
PRIMARY_STOPPING_ESTIMATOR_ID = "primary_local_edep_over_path_v1"
EVENT_CALORIMETRIC_DIAGNOSTIC_ID = "all_particle_edep_over_path_diagnostic_v1"
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


def _read_input_bytes(path: Path) -> bytes:
    """Read the exact input bytes once for parsing and provenance."""
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SimulationTableError(f"cannot read simulation table {path}: {exc}") from exc


def _read_data_lines(path: Path, input_bytes: bytes) -> list[tuple[int, str]]:
    try:
        text = input_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SimulationTableError(
            f"simulation table {path} is not valid UTF-8: {exc}"
        ) from exc
    raw_lines = text.splitlines(keepends=True)
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
        (
            "energy-deposit",
            PRIMARY_RAW_EDEP_ALIASES
            + PRIMARY_QUENCHED_EDEP_ALIASES
            + RAW_EDEP_ALIASES
            + QUENCHED_EDEP_ALIASES,
        ),
        (
            "track-length",
            PRIMARY_TRACK_MM_ALIASES
            + PRIMARY_TRACK_CM_ALIASES
            + TRACK_MM_ALIASES
            + TRACK_CM_ALIASES,
        ),
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
    input_bytes = _read_input_bytes(path)
    data_lines = _read_data_lines(path, input_bytes)
    header = _validate_header(path, data_lines)

    particles: Counter[str] = Counter()
    energies: list[float] = []
    bases: set[str] = set()
    scopes: set[str] = set()
    wave_c_scopes: set[str] = set()
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

        # Prefer primary-only columns when present (#1007). Mixing primary and
        # event-total deposit aliases in one row is rejected.
        primary_raw = populated_aliases(row, PRIMARY_RAW_EDEP_ALIASES)
        primary_quenched = populated_aliases(row, PRIMARY_QUENCHED_EDEP_ALIASES)
        raw_columns = populated_aliases(row, RAW_EDEP_ALIASES)
        quenched_columns = populated_aliases(row, QUENCHED_EDEP_ALIASES)
        using_primary_edep = bool(primary_raw or primary_quenched)
        if using_primary_edep and (raw_columns or quenched_columns):
            raise SimulationTableError(
                f"simulation table {path} line {line_no} mixes primary and "
                "event-total energy-deposit columns (#1007)"
            )
        if using_primary_edep:
            if len(primary_raw) > 1 or len(primary_quenched) > 1:
                columns = primary_raw if len(primary_raw) > 1 else primary_quenched
                raise SimulationTableError(
                    f"simulation table {path} line {line_no} has ambiguous primary "
                    "energy-deposit aliases: " + ", ".join(columns)
                )
            if primary_raw and primary_quenched:
                raise SimulationTableError(
                    f"simulation table {path} line {line_no} populates primary raw "
                    "and quenched energy-deposit fields simultaneously"
                )
            if primary_raw:
                deposit_column = primary_raw[0]
                basis = RAW_BASIS
            else:
                if not allow_quenched_proxy:
                    raise SimulationTableError(
                        f"simulation table {path} line {line_no} provides only "
                        "primary quenched energy deposit; use --allow-quenched-proxy "
                        "for a labelled, non-accepting diagnostic preflight"
                    )
                deposit_column = primary_quenched[0]
                basis = QUENCHED_BASIS
        else:
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

        primary_track = populated_aliases(
            row, PRIMARY_TRACK_MM_ALIASES + PRIMARY_TRACK_CM_ALIASES
        )
        event_track = populated_aliases(row, TRACK_MM_ALIASES + TRACK_CM_ALIASES)
        if primary_track and event_track:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} mixes primary and "
                "event-total track-length columns (#1007)"
            )
        if primary_track:
            if len(primary_track) != 1:
                raise SimulationTableError(
                    f"simulation table {path} line {line_no} has ambiguous primary "
                    "track-length aliases: " + ", ".join(primary_track)
                )
            track_column = primary_track[0]
            track_scope = PRIMARY_SCOPE
        else:
            track_column = require_single_alias(
                row,
                TRACK_MM_ALIASES + TRACK_CM_ALIASES,
                path=path,
                line_no=line_no,
                quantity="track length",
            )
            track_scope = EVENT_TOTAL_SCOPE
        track_value = parse_finite(
            row,
            track_column,
            path=path,
            line_no=line_no,
            quantity="track length",
        )
        cm_aliases = TRACK_CM_ALIASES + PRIMARY_TRACK_CM_ALIASES
        track_mm = track_value * 10.0 if track_column in cm_aliases else track_value
        if track_mm <= 0:
            raise SimulationTableError(
                f"simulation table {path} line {line_no} has nonpositive track length "
                f"{track_mm!r} mm"
            )

        particles[particle] += 1
        energies.append(energy)
        bases.add(basis)
        # Main #1007 provenance from column aliases.
        scopes.add(track_scope)
        # Lane07 Wave C optional explicit track_scope column (extras).
        if "track_scope" in row and row["track_scope"] is not None and str(row["track_scope"]).strip() != "":
            wave_c_scopes.add(str(row["track_scope"]).strip())
        normalized_rows.append((particle, energy, deposit, track_mm))

    if not normalized_rows:
        raise SimulationTableError(f"simulation table has no event rows: {path}")
    if len(bases) != 1:
        raise SimulationTableError(
            f"simulation table {path} mixes unquenched and quenched energy-deposit "
            "semantics across rows"
        )
    if len(scopes) != 1:
        raise SimulationTableError(
            f"simulation table {path} mixes primary and event-total track-length "
            f"scopes across rows (#1007): {sorted(scopes)}"
        )
    if len(wave_c_scopes) > 1:
        raise SimulationTableError(
            f"simulation table {path} mixes track_scope values: {sorted(wave_c_scopes)}"
        )
    basis = next(iter(bases))
    track_length_scope = next(iter(scopes))
    primary_identity = track_length_scope == PRIMARY_SCOPE
    wave_c_scope = next(iter(wave_c_scopes)) if len(wave_c_scopes) == 1 else None
    summary: dict[str, object] = {
        "schema_version": 1,
        "tool": "tools/audit/validate_stopping_power_sim_table.py",
        "tool_version": TOOL_VERSION,
        "status": "VALIDATED" if basis == RAW_BASIS else "DIAGNOSTIC_ONLY",
        "input_path": str(path),
        "input_bytes": len(input_bytes),
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "input_snapshot_method": INPUT_SNAPSHOT_METHOD,
        "header": header,
        "rows_validated": len(normalized_rows),
        "particle_counts": dict(sorted(particles.items())),
        "energy_min_MeV": min(energies),
        "energy_max_MeV": max(energies),
        "energy_deposit_basis": basis,
        "track_length_scope": track_length_scope,
        "primary_track_identity": primary_identity,
        "raw_pstar_comparable": basis == RAW_BASIS,
        # Event-total path length is not the PSTAR single-particle measurand (#1007).
        "pstar_primary_identity_ok": bool(primary_identity and basis == RAW_BASIS),
        # Lane 04 Wave B coexistence aliases for the same #1007 gate (now on main).
        "estimator_id": (
            PRIMARY_STOPPING_ESTIMATOR_ID
            if primary_identity
            else EVENT_CALORIMETRIC_DIAGNOSTIC_ID
        ),
        "primary_stopping_authorising": bool(primary_identity and basis == RAW_BASIS),
        # Lane07 Wave C extras coexist with main summary keys.
        "track_scope": wave_c_scope,
        "track_scope_values": sorted(wave_c_scopes),
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
