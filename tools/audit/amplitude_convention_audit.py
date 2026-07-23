#!/usr/bin/env python3
"""Classify legacy amplitude_adc tables with explicit, hash-bound provenance."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from tools.audit.validate_amplitude_evidence_map import (
        ACCEPTED_EVIDENCE_BASES,
        ValidatedEvidenceMap,
        validate_payload,
    )
except ModuleNotFoundError:  # Direct script execution from tools/audit.
    from validate_amplitude_evidence_map import (
        ACCEPTED_EVIDENCE_BASES,
        ValidatedEvidenceMap,
        validate_payload,
    )

TOOL_VERSION = "3.1.0"
BASELINE_DISPERSION_TOKENS = (
    "rms", "std", "sigma", "noise", "width", "variance", "var",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(value: float, net_max: float, absolute_min: float) -> str:
    if net_max >= absolute_min:
        raise ValueError("net_max must be less than absolute_min")
    if not np.isfinite(value):
        raise ValueError("classification value must be finite")
    if value <= net_max:
        return "NET"
    if value >= absolute_min:
        return "ABSOLUTE"
    return "AMBIGUOUS"


def identify_baseline_columns(columns: list[str]) -> tuple[list[str], list[str]]:
    """Separate pedestal-level candidates from baseline dispersion diagnostics."""
    baseline_like = [column for column in columns if "baseline" in column.lower()]
    level_candidates = [
        column for column in baseline_like
        if not any(token in column.lower() for token in BASELINE_DISPERSION_TOKENS)
    ]
    auxiliary = [column for column in baseline_like if column not in level_candidates]
    return level_candidates, auxiliary


def load_evidence_map(
    path: Path | None,
    evidence_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load and verify traceable, hash-bound convention evidence and its source bytes."""
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_payload(payload, evidence_root=evidence_root or path.parent)


def audit(
    path: Path,
    max_rows: int | None,
    net_max: float,
    absolute_min: float,
    evidence_map: dict[str, dict[str, Any]] | None = None,
) -> dict:
    # Raw programmatic maps receive schema validation, but cannot authorize physics use
    # because their evidence-reference bytes have not been independently resolved.
    if isinstance(evidence_map, ValidatedEvidenceMap):
        validated_evidence_map = evidence_map
    else:
        validated_evidence_map = validate_payload(evidence_map or {})
    header = pd.read_csv(path, nrows=0)
    digest = file_sha256(path)
    common = {"path": str(path), "size_bytes": path.stat().st_size, "sha256": digest}
    if "amplitude_adc" not in header.columns:
        return {**common, "status": "SKIPPED", "reason": "NO_AMPLITUDE_ADC"}

    baseline_columns, auxiliary_baseline_columns = identify_baseline_columns(list(header.columns))
    baseline = baseline_columns[0] if len(baseline_columns) == 1 else None
    usecols = ["amplitude_adc"] + ([baseline] if baseline else [])
    read_rows = max_rows + 1 if max_rows is not None else None
    loaded = pd.read_csv(path, usecols=usecols, nrows=read_rows)
    truncated = max_rows is not None and len(loaded) > max_rows
    frame = loaded.iloc[:max_rows].copy() if truncated else loaded

    numeric_amplitude = pd.to_numeric(frame["amplitude_adc"], errors="coerce")
    finite_mask = np.isfinite(numeric_amplitude.to_numpy(dtype=float, na_value=np.nan))
    amplitude = numeric_amplitude[finite_mask]
    nonfinite_amplitude_rows = int((numeric_amplitude.notna() & ~finite_mask).sum())
    nonnumeric_amplitude_rows = int(numeric_amplitude.isna().sum())
    if amplitude.empty:
        raise ValueError("amplitude_adc has no finite numeric values")

    median = float(amplitude.median())
    heuristic_convention = classify(median, net_max, absolute_min)
    baseline_resolution = (
        "RESOLVED" if baseline else "MISSING" if not baseline_columns else "AMBIGUOUS"
    )
    evidence_record = validated_evidence_map.get(digest)
    verified_evidence_record = (
        evidence_record
        if (
            evidence_record
            and isinstance(validated_evidence_map, ValidatedEvidenceMap)
            and validated_evidence_map.references_verified
            and evidence_record.get("evidence_reference_verified") is True
        )
        else None
    )
    accepted_convention = (
        verified_evidence_record.get("convention") if verified_evidence_record else None
    )
    convention = heuristic_convention
    convention_evidence = "PEDESTAL_ANCHORED" if baseline else "RAW_MEDIAN_HEURISTIC"
    convention_acceptance = "ACCEPTABLE" if baseline else "UNANCHORED"

    result = {
        **common,
        "status": "CLASSIFIED",
        "classification_scope": "PREFIX_SAMPLE" if max_rows is not None else "FULL_TABLE",
        "rows_read": len(frame),
        "input_truncated": truncated,
        "finite_amplitude_rows": len(amplitude),
        "nonfinite_amplitude_rows": nonfinite_amplitude_rows,
        "nonnumeric_amplitude_rows": nonnumeric_amplitude_rows,
        "amplitude_adc_median": median,
        "heuristic_convention": heuristic_convention,
        "baseline_column": baseline,
        "baseline_candidate_count": len(baseline_columns),
        "baseline_candidates": baseline_columns,
        "auxiliary_baseline_columns": auxiliary_baseline_columns,
        "baseline_resolution": baseline_resolution,
        "convention": convention,
        "convention_evidence": convention_evidence,
        "convention_acceptance": convention_acceptance,
        "evidence_record": evidence_record,
        "physics_convention": accepted_convention,
        "physics_convention_evidence": (
            verified_evidence_record.get("evidence_basis")
            if verified_evidence_record else None
        ),
        "physics_evidence_reference": (
            verified_evidence_record.get("evidence_reference")
            if verified_evidence_record else None
        ),
        "physics_evidence_reference_sha256": (
            verified_evidence_record.get("evidence_reference_sha256")
            if verified_evidence_record else None
        ),
        "physics_evidence_reference_verified": bool(verified_evidence_record),
        "physics_acceptance": "UNVERIFIED",
        "subtract_baseline_correct": (
            True if heuristic_convention == "ABSOLUTE" and baseline
            else False if heuristic_convention == "NET" and baseline
            else None
        ),
        "physics_subtract_baseline_correct": None,
    }
    warnings: list[str] = []
    if max_rows is not None:
        result["max_rows_requested"] = max_rows
        warnings.append("PREFIX_SAMPLE_ROW_ORDER_DEPENDENT")
    if nonfinite_amplitude_rows:
        warnings.append("NONFINITE_AMPLITUDE_VALUES_EXCLUDED")
    if nonnumeric_amplitude_rows:
        warnings.append("NONNUMERIC_AMPLITUDE_VALUES_EXCLUDED")
    if not evidence_record:
        warnings.append("NO_HASH_BOUND_CONVENTION_EVIDENCE")
    elif not verified_evidence_record:
        warnings.append("EVIDENCE_REFERENCE_BYTES_UNVERIFIED")

    if baseline:
        numeric_pair = frame[["amplitude_adc", baseline]].apply(pd.to_numeric, errors="coerce")
        pair = numeric_pair.replace([np.inf, -np.inf], np.nan).dropna()
        finite_pairs = len(pair)
        missing_baseline_for_finite_amplitude = len(amplitude) - finite_pairs
        result["baseline_median"] = float(pair[baseline].median()) if not pair.empty else None
        result["median_abs_amplitude_minus_baseline"] = (
            float((pair["amplitude_adc"] - pair[baseline]).abs().median())
            if not pair.empty else None
        )
        result["finite_amplitude_baseline_pairs"] = finite_pairs
        result["finite_amplitude_rows_without_finite_baseline"] = (
            missing_baseline_for_finite_amplitude
        )
        result["baseline_pair_coverage"] = finite_pairs / len(amplitude)
        if missing_baseline_for_finite_amplitude:
            result["baseline_data_quality"] = "INCOMPLETE"
            result["convention_acceptance"] = "BASELINE_DATA_INVALID"
            result["subtract_baseline_correct"] = None
            warnings.append("INCOMPLETE_BASELINE_FOR_FINITE_AMPLITUDES")
        else:
            result["baseline_data_quality"] = "COMPLETE"
    elif len(baseline_columns) > 1:
        result["warning_baseline"] = "MULTIPLE_BASELINE_LEVEL_COLUMNS"
        result["baseline_data_quality"] = "AMBIGUOUS_COLUMN"
    else:
        result["warning_baseline"] = "AMPLITUDE_CONVENTION_WITHOUT_BASELINE_LEVEL"
        result["baseline_data_quality"] = "MISSING_COLUMN"

    if verified_evidence_record:
        if accepted_convention == "NET":
            result["physics_acceptance"] = "ACCEPTABLE"
            result["physics_subtract_baseline_correct"] = False
        elif baseline_resolution != "RESOLVED":
            result["physics_acceptance"] = "BASELINE_SCHEMA_UNRESOLVED"
            warnings.append("HASH_BOUND_ABSOLUTE_WITHOUT_UNIQUE_BASELINE")
        elif result.get("baseline_data_quality") != "COMPLETE":
            result["physics_acceptance"] = "BASELINE_DATA_INVALID"
            warnings.append("HASH_BOUND_ABSOLUTE_WITH_INVALID_BASELINE_DATA")
        else:
            result["physics_acceptance"] = "ACCEPTABLE"
            result["physics_subtract_baseline_correct"] = True

    if warnings:
        result["warnings"] = warnings
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Paths or glob patterns")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-map", type=Path, default=None)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=None,
        help=(
            "Root directory for evidence_reference paths. Defaults to the evidence-map "
            "directory. References must resolve beneath this root."
        ),
    )
    parser.add_argument(
        "--max-rows", type=int, default=None,
        help=(
            "Explicitly classify only the first N rows. This mode is row-order dependent, "
            "is marked PREFIX_SAMPLE, and returns nonzero. By default the complete "
            "amplitude column is evaluated."
        ),
    )
    parser.add_argument("--net-max-adc", type=float, default=3500.0)
    parser.add_argument("--absolute-min-adc", type=float, default=5000.0)
    args = parser.parse_args(argv)
    if args.max_rows is not None and args.max_rows <= 0:
        raise ValueError("max_rows must be positive")
    classify(0.0, args.net_max_adc, args.absolute_min_adc)
    evidence_map = load_evidence_map(args.evidence_map, args.evidence_root)

    paths = sorted({
        Path(p) for pattern in args.inputs for p in glob.glob(pattern, recursive=True)
        if Path(p).is_file()
    })
    if not paths:
        raise FileNotFoundError("no input files matched")

    tables, errors = [], []
    for path in paths:
        try:
            tables.append(
                audit(path, args.max_rows, args.net_max_adc, args.absolute_min_adc, evidence_map)
            )
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    classified = [row for row in tables if row["status"] == "CLASSIFIED"]
    counts = {
        name: sum(row["convention"] == name for row in classified)
        for name in ("ABSOLUTE", "NET", "AMBIGUOUS")
    }
    n_partial = sum(row["classification_scope"] != "FULL_TABLE" for row in classified)
    n_nonfinite_tables = sum(row["nonfinite_amplitude_rows"] > 0 for row in classified)
    n_nonnumeric_tables = sum(row["nonnumeric_amplitude_rows"] > 0 for row in classified)
    n_unresolved_absolute_baselines = sum(
        row["convention"] == "ABSOLUTE" and row["baseline_resolution"] != "RESOLVED"
        for row in classified
    )
    n_unanchored_conventions = sum(
        row["convention_acceptance"] == "UNANCHORED" for row in classified
    )
    n_unverified_conventions = sum(
        row["physics_acceptance"] == "UNVERIFIED" for row in classified
    )
    n_invalid_baseline_data_tables = sum(
        row.get("convention_acceptance") == "BASELINE_DATA_INVALID"
        and row.get("convention") != "NET"
        for row in classified
    )
    n_nonaccepted_physics_conventions = sum(
        row["physics_acceptance"] != "ACCEPTABLE" for row in classified
    )
    payload = {
        "tool": "tools/audit/amplitude_convention_audit.py",
        "tool_version": TOOL_VERSION,
        "classification_rule": {
            "heuristic_NET": f"median <= {args.net_max_adc}",
            "heuristic_ABSOLUTE": f"median >= {args.absolute_min_adc}",
            "heuristic_AMBIGUOUS": "between thresholds; manual review required",
            "accepted_convention": (
                "requires validated SHA-256 keyed evidence and measured equality of the "
                "referenced artifact bytes"
            ),
            "finite_numeric_values_only": True,
        },
        "accepted_evidence_bases": sorted(ACCEPTED_EVIDENCE_BASES),
        "evidence_map": str(args.evidence_map) if args.evidence_map else None,
        "evidence_root": (
            str((args.evidence_root or args.evidence_map.parent).resolve())
            if args.evidence_map else None
        ),
        "max_rows": args.max_rows,
        "n_inputs": len(paths),
        "n_classified": len(classified),
        "n_partial": n_partial,
        "n_nonfinite_tables": n_nonfinite_tables,
        "n_nonnumeric_tables": n_nonnumeric_tables,
        "n_unresolved_absolute_baselines": n_unresolved_absolute_baselines,
        "n_unanchored_conventions": n_unanchored_conventions,
        "n_unverified_conventions": n_unverified_conventions,
        "n_invalid_baseline_data_tables": n_invalid_baseline_data_tables,
        "n_nonaccepted_physics_conventions": n_nonaccepted_physics_conventions,
        "n_skipped": sum(row["status"] == "SKIPPED" for row in tables),
        "n_errors": len(errors),
        "counts": counts,
        "tables": tables,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"inputs={len(paths)} absolute={counts['ABSOLUTE']} net={counts['NET']} "
        f"ambiguous={counts['AMBIGUOUS']} partial={n_partial} nonfinite={n_nonfinite_tables} "
        f"nonnumeric={n_nonnumeric_tables} unanchored={n_unanchored_conventions} "
        f"unverified_physics={n_unverified_conventions} "
        f"nonaccepted_physics={n_nonaccepted_physics_conventions} "
        f"invalid_baseline_data={n_invalid_baseline_data_tables} errors={len(errors)}"
    )
    return 1 if (
        errors or counts["AMBIGUOUS"] or n_partial or n_nonfinite_tables
        or n_nonnumeric_tables or n_nonaccepted_physics_conventions
        or n_invalid_baseline_data_tables
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
