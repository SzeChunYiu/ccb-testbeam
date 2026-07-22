#!/usr/bin/env python3
"""Classify legacy amplitude_adc tables with explicit provenance."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

import pandas as pd

TOOL_VERSION = "2.1.0"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(value: float, net_max: float, absolute_min: float) -> str:
    if net_max >= absolute_min:
        raise ValueError("net_max must be less than absolute_min")
    if value <= net_max:
        return "NET"
    if value >= absolute_min:
        return "ABSOLUTE"
    return "AMBIGUOUS"


def audit(
    path: Path,
    max_rows: int | None,
    net_max: float,
    absolute_min: float,
) -> dict:
    header = pd.read_csv(path, nrows=0)
    common = {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }
    if "amplitude_adc" not in header.columns:
        return {**common, "status": "SKIPPED", "reason": "NO_AMPLITUDE_ADC"}

    baseline_columns = [c for c in header.columns if "baseline" in c.lower()]
    baseline = baseline_columns[0] if len(baseline_columns) == 1 else None
    usecols = ["amplitude_adc"] + ([baseline] if baseline else [])
    read_rows = max_rows + 1 if max_rows is not None else None
    loaded = pd.read_csv(path, usecols=usecols, nrows=read_rows)
    truncated = max_rows is not None and len(loaded) > max_rows
    frame = loaded.iloc[:max_rows].copy() if truncated else loaded
    amplitude = pd.to_numeric(frame["amplitude_adc"], errors="coerce").dropna()
    if amplitude.empty:
        raise ValueError("amplitude_adc has no numeric values")

    median = float(amplitude.median())
    convention = classify(median, net_max, absolute_min)
    result = {
        **common,
        "status": "CLASSIFIED",
        "classification_scope": "PREFIX_SAMPLE" if max_rows is not None else "FULL_TABLE",
        "rows_read": len(frame),
        "input_truncated": truncated,
        "finite_amplitude_rows": len(amplitude),
        "amplitude_adc_median": median,
        "baseline_column": baseline,
        "baseline_candidate_count": len(baseline_columns),
        "convention": convention,
        "subtract_baseline_correct": (
            True if convention == "ABSOLUTE" and baseline else
            False if convention == "NET" else None
        ),
    }
    if max_rows is not None:
        result["max_rows_requested"] = max_rows
        result["warning"] = "PREFIX_SAMPLE_ROW_ORDER_DEPENDENT"
    if baseline:
        pair = frame[["amplitude_adc", baseline]].apply(
            pd.to_numeric, errors="coerce"
        ).dropna()
        result["baseline_median"] = (
            float(pair[baseline].median()) if not pair.empty else None
        )
        result["median_abs_amplitude_minus_baseline"] = (
            float((pair["amplitude_adc"] - pair[baseline]).abs().median())
            if not pair.empty else None
        )
    elif len(baseline_columns) > 1:
        result["warning_baseline"] = "MULTIPLE_BASELINE_COLUMNS"
    elif convention == "ABSOLUTE":
        result["warning_baseline"] = "ABSOLUTE_WITHOUT_BASELINE"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Paths or glob patterns")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help=(
            "Explicitly classify only the first N rows. This mode is row-order "
            "dependent, is marked PREFIX_SAMPLE, and returns nonzero. By default "
            "the complete amplitude column is evaluated."
        ),
    )
    parser.add_argument("--net-max-adc", type=float, default=3500.0)
    parser.add_argument("--absolute-min-adc", type=float, default=5000.0)
    args = parser.parse_args(argv)
    if args.max_rows is not None and args.max_rows <= 0:
        raise ValueError("max_rows must be positive")
    classify(0.0, args.net_max_adc, args.absolute_min_adc)

    paths = sorted({Path(p) for pattern in args.inputs for p in glob.glob(pattern, recursive=True) if Path(p).is_file()})
    if not paths:
        raise FileNotFoundError("no input files matched")

    tables, errors = [], []
    for path in paths:
        try:
            tables.append(audit(path, args.max_rows, args.net_max_adc, args.absolute_min_adc))
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    classified = [row for row in tables if row["status"] == "CLASSIFIED"]
    counts = {name: sum(row["convention"] == name for row in classified) for name in ("ABSOLUTE", "NET", "AMBIGUOUS")}
    n_partial = sum(row["classification_scope"] != "FULL_TABLE" for row in classified)
    payload = {
        "tool": "tools/audit/amplitude_convention_audit.py",
        "tool_version": TOOL_VERSION,
        "classification_rule": {
            "NET": f"median <= {args.net_max_adc}",
            "ABSOLUTE": f"median >= {args.absolute_min_adc}",
            "AMBIGUOUS": "between thresholds; manual review required",
        },
        "max_rows": args.max_rows,
        "n_inputs": len(paths),
        "n_classified": len(classified),
        "n_partial": n_partial,
        "n_skipped": sum(row["status"] == "SKIPPED" for row in tables),
        "n_errors": len(errors),
        "counts": counts,
        "tables": tables,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"inputs={len(paths)} absolute={counts['ABSOLUTE']} "
        f"net={counts['NET']} ambiguous={counts['AMBIGUOUS']} "
        f"partial={n_partial} errors={len(errors)}"
    )
    return 1 if errors or counts["AMBIGUOUS"] or n_partial else 0


if __name__ == "__main__":
    raise SystemExit(main())
