#!/usr/bin/env python3
"""Validate issue #885 campaign coverage and calibration-fit independence.

The validator is intentionally usable on partial campaigns. Partial coverage is not
an error by itself. It fails only when observed configurations do not match the
campaign manifest, published coverage text is inconsistent with the manifest/data,
or calibration fits treat repeated seeds as independent energy points.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TOOL_VERSION = "1.1.0"
CONFIG_KEY = ("particle", "energy_MeV", "hit_x_cm", "hit_y_cm", "seed")
MANIFEST_COLUMNS = (
    "particle",
    "energy_MeV",
    "hit_x_cm",
    "hit_y_cm",
    "seed",
    "nevents",
)
OBSERVED_REQUIRED = {"particle", "energy_MeV", "hit_x_cm", "seed", "n_events"}
FIT_BASIS = "seed_averaged_unique_energy"
MIN_ENERGY_POINTS_FOR_LINEAR_FIT = 3


class CampaignValidationError(ValueError):
    """Raised for unreadable or structurally invalid campaign inputs."""


@dataclass(frozen=True)
class InputProvenance:
    path: str
    size_bytes: int
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def provenance(path: Path) -> InputProvenance:
    return InputProvenance(
        path=str(path),
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def parse_int(value: str, *, field: str, row_number: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CampaignValidationError(
            f"row {row_number}: {field} must be an integer, got {value!r}"
        ) from exc
    return parsed


def parse_float(value: str, *, field: str, row_number: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise CampaignValidationError(
            f"row {row_number}: {field} must be numeric, got {value!r}"
        ) from exc
    if not math.isfinite(parsed):
        raise CampaignValidationError(
            f"row {row_number}: {field} must be finite, got {value!r}"
        )
    return parsed


def canonical_key(row: dict[str, Any]) -> tuple[str, int, float, float, int]:
    return (
        str(row["particle"]),
        int(row["energy_MeV"]),
        float(row["hit_x_cm"]),
        float(row.get("hit_y_cm", 0.0)),
        int(row["seed"]),
    )


def ensure_unique(
    rows: Iterable[dict[str, Any]], *, label: str
) -> set[tuple[str, int, float, float, int]]:
    seen: set[tuple[str, int, float, float, int]] = set()
    duplicates: list[tuple[str, int, float, float, int]] = []
    for row in rows:
        key = canonical_key(row)
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        rendered = ", ".join(map(str, sorted(set(duplicates))))
        raise CampaignValidationError(f"duplicate {label} configuration keys: {rendered}")
    return seen


def read_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(line for line in handle if not line.lstrip().startswith("#"))
        for row_number, values in enumerate(reader, start=1):
            if not values:
                continue
            if len(values) != len(MANIFEST_COLUMNS):
                raise CampaignValidationError(
                    f"manifest row {row_number}: expected {len(MANIFEST_COLUMNS)} fields, "
                    f"found {len(values)}"
                )
            raw = dict(zip(MANIFEST_COLUMNS, values, strict=True))
            rows.append(
                {
                    "particle": raw["particle"].strip(),
                    "energy_MeV": parse_int(
                        raw["energy_MeV"], field="energy_MeV", row_number=row_number
                    ),
                    "hit_x_cm": parse_float(
                        raw["hit_x_cm"], field="hit_x_cm", row_number=row_number
                    ),
                    "hit_y_cm": parse_float(
                        raw["hit_y_cm"], field="hit_y_cm", row_number=row_number
                    ),
                    "seed": parse_int(raw["seed"], field="seed", row_number=row_number),
                    "nevents": parse_int(
                        raw["nevents"], field="nevents", row_number=row_number
                    ),
                }
            )
    if not rows:
        raise CampaignValidationError("campaign manifest contains no configurations")
    ensure_unique(rows, label="manifest")
    return rows


def read_observed(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = OBSERVED_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise CampaignValidationError(
                "observed CSV missing required columns: " + ", ".join(sorted(missing))
            )
        for row_number, raw in enumerate(reader, start=2):
            hit_y_raw = raw.get("hit_y_cm", "0.0")
            if hit_y_raw is None or str(hit_y_raw).strip() == "":
                hit_y_raw = "0.0"
            rows.append(
                {
                    "particle": str(raw["particle"]).strip(),
                    "energy_MeV": parse_int(
                        raw["energy_MeV"], field="energy_MeV", row_number=row_number
                    ),
                    "hit_x_cm": parse_float(
                        raw["hit_x_cm"], field="hit_x_cm", row_number=row_number
                    ),
                    "hit_y_cm": parse_float(
                        hit_y_raw, field="hit_y_cm", row_number=row_number
                    ),
                    "seed": parse_int(raw["seed"], field="seed", row_number=row_number),
                    "n_events": parse_int(
                        raw["n_events"], field="n_events", row_number=row_number
                    ),
                }
            )
    if not rows:
        raise CampaignValidationError("observed campaign CSV contains no configurations")
    ensure_unique(rows, label="observed")
    return rows


def infer_main_hit_x(manifest: list[dict[str, Any]]) -> float:
    counts: dict[float, int] = {}
    for row in manifest:
        x = float(row["hit_x_cm"])
        counts[x] = counts.get(x, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        raise CampaignValidationError(
            "cannot infer main-grid hit_x_cm because multiple positions have equal maximum coverage"
        )
    return ranked[0][0]


def energies_by_particle(
    rows: Iterable[dict[str, Any]],
    *,
    hit_x_cm: float,
    hit_y_cm: float = 0.0,
) -> dict[str, list[int]]:
    values: dict[str, set[int]] = {}
    for row in rows:
        if float(row["hit_x_cm"]) != hit_x_cm:
            continue
        if float(row.get("hit_y_cm", 0.0)) != hit_y_cm:
            continue
        values.setdefault(str(row["particle"]), set()).add(int(row["energy_MeV"]))
    return {particle: sorted(energies) for particle, energies in sorted(values.items())}


def audit_summary(
    text: str,
    *,
    observed_main_files: int,
    expected_main_files: int,
    observed_energies: dict[str, list[int]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    coverage_match = re.search(
        r"(?:PARTIAL|COMPLETE)\s*\((\d+)(?:/(\d+))?\s+main-grid files\)", text
    )
    if not coverage_match:
        issues.append(
            {
                "code": "SUMMARY_MAIN_GRID_COVERAGE_MISSING",
                "message": "summary does not contain a machine-checkable main-grid file count",
            }
        )
    else:
        reported_observed = int(coverage_match.group(1))
        reported_expected = (
            int(coverage_match.group(2)) if coverage_match.group(2) is not None else None
        )
        if reported_observed != observed_main_files:
            issues.append(
                {
                    "code": "SUMMARY_MAIN_GRID_NUMERATOR_MISMATCH",
                    "reported": reported_observed,
                    "measured": observed_main_files,
                    "message": "summary main-grid numerator disagrees with observed configurations",
                }
            )
        if reported_expected != expected_main_files:
            issues.append(
                {
                    "code": "SUMMARY_MAIN_GRID_DENOMINATOR_MISMATCH",
                    "reported": reported_expected,
                    "measured": expected_main_files,
                    "message": "summary uses the wrong main-grid denominator",
                }
            )

    collapsed_match = re.search(r"Covered:\s*([^\n]+?)\s*@\s*(\d+)-(\d+)\s*MeV", text)
    if collapsed_match and len(observed_energies) > 1:
        energy_sets = {tuple(values) for values in observed_energies.values()}
        if len(energy_sets) != 1:
            issues.append(
                {
                    "code": "SUMMARY_COLLAPSED_SPECIES_COVERAGE",
                    "reported": collapsed_match.group(0),
                    "measured": observed_energies,
                    "message": (
                        "summary collapses unequal per-species energy coverage "
                        "into one shared range"
                    ),
                }
            )
    return issues


def fit_particle(name: str) -> str | None:
    for particle in ("proton", "deuteron"):
        if name.endswith("_" + particle):
            return particle
    return None


def audit_fits(
    payload: dict[str, Any],
    *,
    observed_main_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    fits = payload.get("fits")
    if not isinstance(fits, dict):
        raise CampaignValidationError("fits JSON must contain an object named 'fits'")

    for name, record in sorted(fits.items()):
        if not isinstance(record, dict):
            issues.append(
                {
                    "code": "FIT_RECORD_NOT_OBJECT",
                    "fit": name,
                    "message": "fit record is not a JSON object",
                }
            )
            continue
        particle = fit_particle(name)
        if particle is None:
            issues.append(
                {
                    "code": "FIT_PARTICLE_UNRESOLVED",
                    "fit": name,
                    "message": "fit name does not identify proton or deuteron",
                }
            )
            continue
        rows = [row for row in observed_main_rows if row["particle"] == particle]
        n_files = len(rows)
        n_energy_points = len({int(row["energy_MeV"]) for row in rows})
        fit_detail = {
            "particle": particle,
            "observed_files": n_files,
            "independent_energy_points": n_energy_points,
            "reported_n": record.get("n"),
            "reported_n_files": record.get("n_files"),
            "reported_n_energy_points": record.get("n_energy_points"),
            "fit_basis": record.get("fit_basis"),
        }
        details[name] = fit_detail

        if n_energy_points < MIN_ENERGY_POINTS_FOR_LINEAR_FIT:
            issues.append(
                {
                    "code": "FIT_UNDERDETERMINED_CALIBRATION",
                    "fit": name,
                    "independent_energy_points": n_energy_points,
                    "minimum": MIN_ENERGY_POINTS_FOR_LINEAR_FIT,
                    "message": (
                        "linear calibration fit has fewer than three independent energy points; "
                        "R-squared has no residual-degree-of-freedom interpretation"
                    ),
                }
            )
        if record.get("fit_basis") != FIT_BASIS:
            issues.append(
                {
                    "code": "FIT_BASIS_NOT_SEED_AVERAGED",
                    "fit": name,
                    "reported": record.get("fit_basis"),
                    "required": FIT_BASIS,
                    "message": "fit does not declare seed-averaged unique-energy inputs",
                }
            )
        if record.get("n_energy_points") != n_energy_points:
            issues.append(
                {
                    "code": "FIT_INDEPENDENT_COUNT_MISSING_OR_WRONG",
                    "fit": name,
                    "reported": record.get("n_energy_points"),
                    "measured": n_energy_points,
                    "message": "fit does not report the measured independent energy-point count",
                }
            )
        if record.get("n_files") != n_files:
            issues.append(
                {
                    "code": "FIT_FILE_COUNT_MISSING_OR_WRONG",
                    "fit": name,
                    "reported": record.get("n_files"),
                    "measured": n_files,
                    "message": "fit does not report the contributing file count",
                }
            )
        if record.get("n") != n_energy_points:
            issues.append(
                {
                    "code": "FIT_N_COUNTS_FILES_NOT_INDEPENDENT_ENERGIES",
                    "fit": name,
                    "reported": record.get("n"),
                    "required": n_energy_points,
                    "message": (
                        "fit n must count independent seed-averaged energy points, not seed files"
                    ),
                }
            )
    return issues, details


def validate(
    *,
    manifest_path: Path,
    observed_path: Path,
    fits_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    manifest = read_manifest(manifest_path)
    observed = read_observed(observed_path)
    manifest_keys = ensure_unique(manifest, label="manifest")
    observed_keys = ensure_unique(observed, label="observed")

    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    unexpected = sorted(observed_keys - manifest_keys)
    if unexpected:
        issues.append(
            {
                "code": "OBSERVED_CONFIG_NOT_IN_MANIFEST",
                "configurations": [list(key) for key in unexpected],
                "message": "observed output contains configurations absent from the manifest",
            }
        )

    main_hit_x = infer_main_hit_x(manifest)
    # Central-track response (issue #1092): main grid is y=0, not a stave average.
    main_hit_y = 0.0
    expected_main_rows = [
        row
        for row in manifest
        if float(row["hit_x_cm"]) == main_hit_x
        and float(row.get("hit_y_cm", 0.0)) == main_hit_y
    ]
    observed_main_rows = [
        row
        for row in observed
        if float(row["hit_x_cm"]) == main_hit_x
        and float(row.get("hit_y_cm", 0.0)) == main_hit_y
    ]
    expected_energies = energies_by_particle(
        manifest, hit_x_cm=main_hit_x, hit_y_cm=main_hit_y
    )
    observed_energies = energies_by_particle(
        observed, hit_x_cm=main_hit_x, hit_y_cm=main_hit_y
    )

    missing = sorted(manifest_keys - observed_keys)
    if missing:
        warnings.append(
            {
                "code": "CAMPAIGN_PARTIAL",
                "missing_configurations": len(missing),
                "message": "campaign is incomplete; partial data are allowed but must be labelled",
            }
        )

    summary_text = summary_path.read_text(encoding="utf-8")
    issues.extend(
        audit_summary(
            summary_text,
            observed_main_files=len(observed_main_rows),
            expected_main_files=len(expected_main_rows),
            observed_energies=observed_energies,
        )
    )

    with fits_path.open(encoding="utf-8") as handle:
        fits_payload = json.load(handle)
    fit_issues, fit_details = audit_fits(
        fits_payload,
        observed_main_rows=observed_main_rows,
    )
    issues.extend(fit_issues)

    result = {
        "tool": "tools/audit/validate_i885_campaign_results.py",
        "tool_version": TOOL_VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "accepted": not issues,
        "inputs": {
            "manifest": provenance(manifest_path).__dict__,
            "observed": provenance(observed_path).__dict__,
            "fits": provenance(fits_path).__dict__,
            "summary": provenance(summary_path).__dict__,
        },
        "coverage": {
            "main_hit_x_cm": main_hit_x,
            "main_hit_y_cm": main_hit_y,
            "phase_space_support": "central_track_y0_not_stave_average",
            "expected_total_files": len(manifest),
            "observed_total_files": len(observed),
            "expected_main_grid_files": len(expected_main_rows),
            "observed_main_grid_files": len(observed_main_rows),
            "expected_main_energy_points": sum(len(v) for v in expected_energies.values()),
            "observed_main_energy_points": sum(len(v) for v in observed_energies.values()),
            "expected_energies_by_particle": expected_energies,
            "observed_energies_by_particle": observed_energies,
        },
        "fit_audit": fit_details,
        "issues": issues,
        "warnings": warnings,
    }
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--observed", required=True, type=Path)
    parser.add_argument("--fits", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate(
            manifest_path=args.manifest,
            observed_path=args.observed,
            fits_path=args.fits,
            summary_path=args.summary,
        )
    except (OSError, json.JSONDecodeError, CampaignValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    print(
        "i885 campaign validation: "
        f"status={result['status']} issues={len(result['issues'])} "
        f"warnings={len(result['warnings'])}",
        file=sys.stderr,
    )
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
