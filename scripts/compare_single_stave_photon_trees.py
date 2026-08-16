#!/usr/bin/env python3
"""Validate optical-photon tree integrity and MT reproducibility.

Photon rows have no persistent photon identifier, so file row order is not a
valid comparison key. This tool validates each tree, canonicalizes rows by all
recorded fields, compares the resulting multisets, and writes JSON and PDF
artifacts suitable for scientific review.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

try:
    import uproot
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install ROOT support with `pip install -e '.[root]'`") from exc


REQUIRED_BRANCHES = (
    "event",
    "sensor",
    "wavelength_nm",
    "time_ns",
    "path_len_mm",
    "detected",
)
SENSOR_IDS = (0, 1, 2, 3)


@dataclass(frozen=True)
class FieldComparison:
    field: str
    entries: int
    exact_equal: bool
    n_mismatched: int
    max_abs_diff: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reference-meta", required=True, type=Path)
    parser.add_argument("--candidate-meta", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-pdf", required=True, type=Path)
    parser.add_argument("--tree", default="photons")
    return parser.parse_args()


def load_metadata(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"metadata must be a JSON object: {path}")
    return payload


def read_tree(path: Path, tree_name: str) -> dict[str, np.ndarray]:
    with uproot.open(path) as root_file:
        if tree_name not in root_file:
            available = sorted(str(key).split(";", 1)[0] for key in root_file.keys())
            raise KeyError(f"tree {tree_name!r} absent from {path}; available={available}")
        tree = root_file[tree_name]
        arrays = tree.arrays(tree.keys(), library="np")
        if isinstance(arrays, np.ndarray) and arrays.dtype.names is not None:
            arrays = {name: np.asarray(arrays[name]) for name in arrays.dtype.names}
        elif isinstance(arrays, np.ndarray):
            arrays = {tree.keys()[0]: arrays}
    return {str(name): np.asarray(values) for name, values in arrays.items()}


def validate_schema(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    names = set(arrays)
    missing = sorted(set(REQUIRED_BRANCHES) - names)
    extra = sorted(names - set(REQUIRED_BRANCHES))
    lengths = {name: int(values.size) for name, values in arrays.items()}
    consistent_lengths = len(set(lengths.values())) <= 1
    one_dimensional = all(values.ndim == 1 for values in arrays.values())
    return {
        "valid": not missing and consistent_lengths and one_dimensional,
        "missing": missing,
        "extra": extra,
        "lengths": lengths,
        "consistent_lengths": consistent_lengths,
        "one_dimensional": one_dimensional,
    }


def _integer_domain(values: np.ndarray, *, name: str) -> None:
    if not np.issubdtype(values.dtype, np.integer):
        raise TypeError(f"{name} must be integer-valued, got {values.dtype}")


def validate_photons(arrays: dict[str, np.ndarray], n_events: int) -> dict[str, Any]:
    schema = validate_schema(arrays)
    if not schema["valid"]:
        return {"valid": False, "schema": schema, "checks": {}}

    event = arrays["event"]
    sensor = arrays["sensor"]
    wavelength = arrays["wavelength_nm"]
    time = arrays["time_ns"]
    path = arrays["path_len_mm"]
    detected = arrays["detected"]

    _integer_domain(event, name="event")
    _integer_domain(sensor, name="sensor")
    _integer_domain(detected, name="detected")

    checks = {
        "event_foreign_keys": {
            "valid": bool(np.all((event >= 0) & (event < n_events))),
            "min": int(np.min(event)) if event.size else None,
            "max": int(np.max(event)) if event.size else None,
            "invalid_rows": int(np.count_nonzero((event < 0) | (event >= n_events))),
        },
        "sensor_domain": {
            "valid": bool(np.all(np.isin(sensor, SENSOR_IDS))),
            "allowed": list(SENSOR_IDS),
            "observed": np.unique(sensor).astype(int).tolist(),
            "invalid_rows": int(np.count_nonzero(~np.isin(sensor, SENSOR_IDS))),
        },
        "detected_domain": {
            "valid": bool(np.all(np.isin(detected, (0, 1)))),
            "observed": np.unique(detected).astype(int).tolist(),
            "invalid_rows": int(np.count_nonzero(~np.isin(detected, (0, 1)))),
        },
        "wavelength_domain": {
            "valid": bool(np.all(np.isfinite(wavelength)) and np.all(wavelength > 0.0)),
            "nonfinite_rows": int(np.count_nonzero(~np.isfinite(wavelength))),
            "nonpositive_rows": int(np.count_nonzero(wavelength <= 0.0)),
        },
        "time_domain": {
            "valid": bool(np.all(np.isfinite(time)) and np.all(time >= 0.0)),
            "nonfinite_rows": int(np.count_nonzero(~np.isfinite(time))),
            "negative_rows": int(np.count_nonzero(time < 0.0)),
        },
        "path_domain": {
            "valid": bool(np.all(np.isfinite(path)) and np.all(path >= 0.0)),
            "nonfinite_rows": int(np.count_nonzero(~np.isfinite(path))),
            "negative_rows": int(np.count_nonzero(path < 0.0)),
        },
    }
    return {
        "valid": bool(schema["valid"] and all(item["valid"] for item in checks.values())),
        "schema": schema,
        "checks": checks,
        "rows": int(event.size),
        "events_with_photons": int(np.unique(event).size),
    }


def canonical_order(arrays: dict[str, np.ndarray]) -> np.ndarray:
    """Return a deterministic multiset ordering using every recorded field."""
    return np.lexsort(
        (
            arrays["detected"],
            arrays["path_len_mm"],
            arrays["time_ns"],
            arrays["wavelength_nm"],
            arrays["sensor"],
            arrays["event"],
        )
    )


def canonicalize(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    order = canonical_order(arrays)
    return {name: values[order] for name, values in arrays.items()}


def compare_field(name: str, reference: np.ndarray, candidate: np.ndarray) -> FieldComparison:
    if reference.shape != candidate.shape:
        return FieldComparison(
            field=name,
            entries=int(max(reference.size, candidate.size)),
            exact_equal=False,
            n_mismatched=int(max(reference.size, candidate.size)),
            max_abs_diff=None,
        )
    equal = reference == candidate
    numeric = np.issubdtype(reference.dtype, np.number) and np.issubdtype(
        candidate.dtype, np.number
    )
    max_abs_diff: float | None = None
    if numeric and reference.size:
        ref = reference.astype(np.float64, copy=False)
        cand = candidate.astype(np.float64, copy=False)
        finite = np.isfinite(ref) & np.isfinite(cand)
        diff = np.abs(ref[finite] - cand[finite])
        max_abs_diff = float(np.max(diff)) if diff.size else 0.0
        equal = (reference == candidate) | (np.isnan(ref) & np.isnan(cand))
    return FieldComparison(
        field=name,
        entries=int(reference.size),
        exact_equal=bool(np.all(equal)),
        n_mismatched=int(np.count_nonzero(~equal)),
        max_abs_diff=max_abs_diff,
    )


def aggregate(arrays: dict[str, np.ndarray], n_events: int) -> dict[str, Any]:
    event = arrays["event"].astype(np.int64, copy=False)
    sensor = arrays["sensor"].astype(np.int64, copy=False)
    detected = arrays["detected"].astype(np.int64, copy=False)
    event_counts = np.bincount(event, minlength=n_events)
    by_sensor = {
        str(sensor_id): {
            "rows": int(np.count_nonzero(sensor == sensor_id)),
            "detected": int(np.count_nonzero((sensor == sensor_id) & (detected == 1))),
        }
        for sensor_id in SENSOR_IDS
    }
    return {
        "rows": int(event.size),
        "event_count_min": int(np.min(event_counts)) if event_counts.size else 0,
        "event_count_max": int(np.max(event_counts)) if event_counts.size else 0,
        "event_count_mean": float(np.mean(event_counts)) if event_counts.size else 0.0,
        "event_count_zero_events": int(np.count_nonzero(event_counts == 0)),
        "detected_rows": int(np.count_nonzero(detected == 1)),
        "detected_fraction": float(np.mean(detected == 1)) if detected.size else 0.0,
        "by_sensor": by_sensor,
    }


def plot_summary(pdf: PdfPages, summary: dict[str, Any]) -> None:
    figure = plt.figure(figsize=(8.5, 11))
    lines = [
        "Single-stave optical-photon MT reproducibility audit",
        "",
        f"Reference: {summary['inputs']['reference']}",
        f"Candidate: {summary['inputs']['candidate']}",
        f"Overall pass: {summary['pass']}",
        f"Reference integrity: {summary['integrity']['reference']['valid']}",
        f"Candidate integrity: {summary['integrity']['candidate']['valid']}",
        f"Schema match: {summary['schema_match']}",
        f"Row counts match: {summary['row_counts_match']}",
        f"Fields exact: {sum(item['exact_equal'] for item in summary['fields'])}/"
        f"{len(summary['fields'])}",
        "",
        "Photon rows lack persistent IDs. PASS therefore compares the exact",
        "multiset after canonical ordering by event, sensor, wavelength, time,",
        "path length, and detection flag; original ROOT row order is ignored.",
    ]
    figure.text(0.07, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=10)
    pdf.savefig(figure)
    plt.close(figure)


def plot_diagnostics(
    pdf: PdfPages,
    reference: dict[str, np.ndarray],
    candidate: dict[str, np.ndarray],
    n_events: int,
) -> None:
    ref_counts = np.bincount(reference["event"].astype(int), minlength=n_events)
    cand_counts = np.bincount(candidate["event"].astype(int), minlength=n_events)
    figure, axes = plt.subplots(2, 1, figsize=(8.5, 11), constrained_layout=True)
    axes[0].hist(ref_counts, bins="fd", histtype="step", label="reference")
    axes[0].hist(cand_counts, bins="fd", histtype="step", label="candidate")
    axes[0].set_title("Photon rows per event")
    axes[0].set_xlabel("Rows / event")
    axes[0].set_ylabel("Events / bin")
    axes[0].legend()
    axes[1].hist(cand_counts - ref_counts, bins="fd" if n_events > 1 else 20)
    axes[1].set_title("Candidate minus reference photon rows per event")
    axes[1].set_xlabel("Δ rows / event")
    axes[1].set_ylabel("Events / bin")
    pdf.savefig(figure)
    plt.close(figure)

    for field, unit in (
        ("wavelength_nm", "nm"),
        ("time_ns", "ns"),
        ("path_len_mm", "mm"),
    ):
        values = np.concatenate((reference[field], candidate[field])).astype(float)
        values = values[np.isfinite(values)]
        bins = np.histogram_bin_edges(values, bins="fd") if values.size > 1 else 20
        figure, axis = plt.subplots(figsize=(8.5, 6), constrained_layout=True)
        axis.hist(reference[field], bins=bins, histtype="step", label="reference")
        axis.hist(candidate[field], bins=bins, histtype="step", label="candidate")
        axis.set_title(f"Photon {field} distribution")
        axis.set_xlabel(f"{field} [{unit}]")
        axis.set_ylabel("Photon rows / bin")
        axis.legend()
        pdf.savefig(figure)
        plt.close(figure)


def main() -> int:
    args = parse_args()
    reference_meta = load_metadata(args.reference_meta)
    candidate_meta = load_metadata(args.candidate_meta)
    reference = read_tree(args.reference, args.tree)
    candidate = read_tree(args.candidate, args.tree)

    reference_n_events = int(reference_meta["n_events"])
    candidate_n_events = int(candidate_meta["n_events"])
    reference_integrity = validate_photons(reference, reference_n_events)
    candidate_integrity = validate_photons(candidate, candidate_n_events)

    ref_names = set(reference)
    cand_names = set(candidate)
    schema_match = ref_names == cand_names
    row_counts_match = bool(
        reference_integrity.get("rows") == candidate_integrity.get("rows")
    )

    comparisons: list[FieldComparison] = []
    if reference_integrity["valid"] and candidate_integrity["valid"] and schema_match:
        reference = canonicalize(reference)
        candidate = canonicalize(candidate)
        comparisons = [
            compare_field(name, reference[name], candidate[name]) for name in sorted(ref_names)
        ]

    same_event_count = reference_n_events == candidate_n_events
    passed = bool(
        reference_integrity["valid"]
        and candidate_integrity["valid"]
        and schema_match
        and row_counts_match
        and same_event_count
        and comparisons
        and all(item.exact_equal for item in comparisons)
    )
    summary = {
        "schema_version": "ccb-g4-photon-reproducibility/1",
        "inputs": {
            "reference": str(args.reference),
            "candidate": str(args.candidate),
            "reference_meta": str(args.reference_meta),
            "candidate_meta": str(args.candidate_meta),
            "tree": args.tree,
        },
        "pass": passed,
        "schema_match": schema_match,
        "row_counts_match": row_counts_match,
        "event_counts_match": same_event_count,
        "integrity": {
            "reference": reference_integrity,
            "candidate": candidate_integrity,
        },
        "aggregates": {
            "reference": aggregate(reference, reference_n_events)
            if reference_integrity["valid"]
            else None,
            "candidate": aggregate(candidate, candidate_n_events)
            if candidate_integrity["valid"]
            else None,
        },
        "fields": [asdict(item) for item in comparisons],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_str = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    args.output_json.write_text(output_str, encoding="utf-8")
    with PdfPages(args.output_pdf) as pdf:
        plot_summary(pdf, summary)
        if reference_integrity["valid"] and candidate_integrity["valid"] and same_event_count:
            plot_diagnostics(pdf, reference, candidate, reference_n_events)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
