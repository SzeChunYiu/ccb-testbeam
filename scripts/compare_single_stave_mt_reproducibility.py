#!/usr/bin/env python3
"""Validate event-keyed reproducibility of two single-stave Geant4 ROOT runs.

Row order is not a reproducibility criterion in Geant4 MT: worker scheduling can
change it. This program sorts the ``events`` trees by the integer ``event`` key,
checks schema and event-ID integrity, compares every branch, verifies metadata,
and creates a JSON record plus a diagnostic PDF.
"""

from __future__ import annotations

import argparse
import json
import math
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


DEFAULT_PLOT_BRANCHES = (
    "edep_scint_MeV",
    "edep_scint_raw_MeV",
    "track_len_scint_mm",
    "n_scint_generated",
    "arrival_readout",
    "detected_readout",
    "pe_sat_readout",
)

PHYSICS_PROVENANCE_KEYS = (
    "schema",
    "git_commit",
    "geometry_hash",
    "seed",
    "particle",
    "kinetic_energy_MeV",
    "n_events",
    "mode",
    "birks_kB_mm_per_MeV",
    "reflectivity_scale",
    "attenuation_scale",
    "scintillator_absorption_scale",
    "y11_bulk_attenuation_scale",
    "pde_scale",
    "collection_efficiency",
    "optical_interface_model",
    "sipm_n_cells",
    "optical_tables",
)

THREAD_KEYS = (
    "threads_requested",
    "threads_effective",
    "G4FORCENUMBEROFTHREADS",
)


@dataclass(frozen=True)
class BranchResult:
    branch: str
    reference_dtype: str
    candidate_dtype: str
    entries: int
    exact_equal: bool
    allclose: bool
    n_mismatched: int
    max_abs_diff: float | None
    mean_abs_diff: float | None
    rms_diff: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reference-meta", required=True, type=Path)
    parser.add_argument("--candidate-meta", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-pdf", required=True, type=Path)
    parser.add_argument("--tree", default="events")
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--atol", type=float, default=0.0)
    parser.add_argument("--plot-branches", nargs="*", default=list(DEFAULT_PLOT_BRANCHES))
    parser.add_argument(
        "--allow-different-git-commit",
        action="store_true",
        help="Permit git_commit to differ while requiring all other physics provenance to match",
    )
    return parser.parse_args()


def load_metadata(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"metadata must be a JSON object: {path}")
    return data


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


def validate_event_ids(ids: np.ndarray, expected_count: int) -> dict[str, Any]:
    if ids.ndim != 1:
        raise ValueError(f"event branch must be one-dimensional, got {ids.shape}")
    if not np.issubdtype(ids.dtype, np.integer):
        raise TypeError(f"event branch must be integer-valued, got {ids.dtype}")
    unique, counts = np.unique(ids, return_counts=True)
    expected = np.arange(expected_count, dtype=unique.dtype)
    duplicate = unique[counts > 1]
    missing = np.setdiff1d(expected, unique)
    unexpected = np.setdiff1d(unique, expected)
    valid = bool(
        ids.size == expected_count
        and unique.size == expected_count
        and duplicate.size == 0
        and missing.size == 0
        and unexpected.size == 0
    )
    return {
        "entries": int(ids.size),
        "unique_entries": int(unique.size),
        "expected_entries": expected_count,
        "duplicate_ids": duplicate.astype(int).tolist(),
        "missing_ids": missing.astype(int).tolist(),
        "unexpected_ids": unexpected.astype(int).tolist(),
        "valid": valid,
    }


def sort_by_event(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    if "event" not in arrays:
        raise KeyError("events tree is missing required branch 'event'")
    order = np.argsort(arrays["event"], kind="stable")
    return {name: values[order] for name, values in arrays.items()}


def compare_branch(
    name: str,
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    rtol: float,
    atol: float,
) -> BranchResult:
    if reference.shape != candidate.shape:
        return BranchResult(
            name,
            str(reference.dtype),
            str(candidate.dtype),
            int(max(reference.size, candidate.size)),
            False,
            False,
            int(max(reference.size, candidate.size)),
            None,
            None,
            None,
        )

    numeric = np.issubdtype(reference.dtype, np.number) and np.issubdtype(
        candidate.dtype, np.number
    )
    if not numeric:
        equal_mask = reference == candidate
        exact = bool(np.all(equal_mask))
        return BranchResult(
            name,
            str(reference.dtype),
            str(candidate.dtype),
            int(reference.size),
            exact,
            exact,
            int(np.count_nonzero(~equal_mask)),
            None,
            None,
            None,
        )

    ref = reference.astype(np.float64, copy=False)
    cand = candidate.astype(np.float64, copy=False)
    exact = bool(np.array_equal(ref, cand, equal_nan=True))
    close = np.isclose(ref, cand, rtol=rtol, atol=atol, equal_nan=True)
    finite = np.isfinite(ref) & np.isfinite(cand)
    diff = np.abs(ref[finite] - cand[finite])
    return BranchResult(
        name,
        str(reference.dtype),
        str(candidate.dtype),
        int(reference.size),
        exact,
        bool(np.all(close)),
        int(np.count_nonzero(~close)),
        float(np.max(diff)) if diff.size else 0.0,
        float(np.mean(diff)) if diff.size else 0.0,
        float(math.sqrt(float(np.mean(diff**2)))) if diff.size else 0.0,
    )


def compare_metadata(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    allow_different_git_commit: bool,
) -> dict[str, Any]:
    physics: dict[str, dict[str, Any]] = {}
    valid = True
    for key in PHYSICS_PROVENANCE_KEYS:
        ref_value = reference.get(key)
        cand_value = candidate.get(key)
        equal = ref_value == cand_value
        required_equal = not (key == "git_commit" and allow_different_git_commit)
        physics[key] = {
            "reference": ref_value,
            "candidate": cand_value,
            "equal": equal,
            "required_equal": required_equal,
        }
        if required_equal and not equal:
            valid = False
    return {
        "valid": valid,
        "physics_provenance": physics,
        "thread_provenance": {
            key: {"reference": reference.get(key), "candidate": candidate.get(key)}
            for key in THREAD_KEYS
        },
    }


def histogram_edges(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    values = np.concatenate((reference.ravel(), candidate.ravel())).astype(float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return np.linspace(0.0, 1.0, 21)
    low, high = float(np.min(values)), float(np.max(values))
    if low == high:
        pad = max(abs(low) * 0.05, 0.5)
        return np.linspace(low - pad, high + pad, 21)
    edges = np.histogram_bin_edges(values, bins="fd")
    return edges if edges.size >= 2 else np.linspace(low, high, 21)


def plot_branch(
    pdf: PdfPages,
    name: str,
    reference: np.ndarray,
    candidate: np.ndarray,
    result: BranchResult,
) -> None:
    if not (
        np.issubdtype(reference.dtype, np.number)
        and np.issubdtype(candidate.dtype, np.number)
    ):
        return
    edges = histogram_edges(reference, candidate)
    ref_hist, _ = np.histogram(reference, bins=edges)
    cand_hist, _ = np.histogram(candidate, bins=edges)
    centers = (edges[:-1] + edges[1:]) / 2.0
    ratio = np.divide(
        cand_hist,
        ref_hist,
        out=np.full(cand_hist.shape, np.nan, dtype=float),
        where=ref_hist > 0,
    )
    differences = candidate.astype(float) - reference.astype(float)
    differences = differences[np.isfinite(differences)]

    figure, axes = plt.subplots(3, 1, figsize=(8.5, 11), constrained_layout=True)
    axes[0].stairs(ref_hist, edges, label="reference")
    axes[0].stairs(cand_hist, edges, label="candidate")
    axes[0].set_title(f"{name}: distribution after event-ID alignment")
    axes[0].set_ylabel("Events / bin")
    axes[0].legend()
    axes[1].plot(centers, ratio, marker="o", linestyle="none", markersize=3)
    axes[1].axhline(1.0, linestyle="--")
    axes[1].set_ylabel("Candidate / reference")
    axes[1].set_xlabel(name)
    axes[2].hist(differences, bins="fd" if differences.size > 1 else 20)
    axes[2].set_xlabel(f"candidate - reference ({name})")
    axes[2].set_ylabel("Events / bin")
    axes[2].set_title(
        f"mismatches={result.n_mismatched}; max|Δ|={result.max_abs_diff:.6g}; "
        f"RMS(Δ)={result.rms_diff:.6g}"
    )
    pdf.savefig(figure)
    plt.close(figure)


def plot_summary(pdf: PdfPages, summary: dict[str, Any]) -> None:
    figure = plt.figure(figsize=(8.5, 11))
    lines = [
        "Single-stave Geant4 MT reproducibility audit",
        "",
        f"Reference: {summary['inputs']['reference']}",
        f"Candidate: {summary['inputs']['candidate']}",
        f"Overall pass: {summary['pass']}",
        f"Schema match: {summary['schema']['match']}",
        f"Reference IDs valid: {summary['event_ids']['reference']['valid']}",
        f"Candidate IDs valid: {summary['event_ids']['candidate']['valid']}",
        f"Physics provenance valid: {summary['metadata']['valid']}",
        f"Branches passing: {sum(row['allclose'] for row in summary['branches'])}/"
        f"{len(summary['branches'])}",
        "",
        "PASS requires complete unique event IDs, identical schemas, matching",
        "physics provenance, and every event-keyed branch within tolerance.",
        "Thread provenance is reported and is allowed to differ.",
    ]
    figure.text(0.07, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=10)
    pdf.savefig(figure)
    plt.close(figure)


def main() -> int:
    args = parse_args()
    if args.rtol < 0 or args.atol < 0:
        raise SystemExit("--rtol and --atol must be non-negative")

    reference_meta = load_metadata(args.reference_meta)
    candidate_meta = load_metadata(args.candidate_meta)
    reference = read_tree(args.reference, args.tree)
    candidate = read_tree(args.candidate, args.tree)

    reference_ids = validate_event_ids(reference["event"], int(reference_meta["n_events"]))
    candidate_ids = validate_event_ids(candidate["event"], int(candidate_meta["n_events"]))
    reference = sort_by_event(reference)
    candidate = sort_by_event(candidate)

    ref_names, cand_names = set(reference), set(candidate)
    common = sorted(ref_names & cand_names)
    branch_results = [
        compare_branch(
            name,
            reference[name],
            candidate[name],
            rtol=args.rtol,
            atol=args.atol,
        )
        for name in common
    ]
    metadata = compare_metadata(
        reference_meta,
        candidate_meta,
        allow_different_git_commit=args.allow_different_git_commit,
    )
    passed = bool(
        ref_names == cand_names
        and reference_ids["valid"]
        and candidate_ids["valid"]
        and metadata["valid"]
        and all(result.allclose for result in branch_results)
    )
    summary = {
        "schema_version": "ccb-g4-mt-reproducibility/1",
        "inputs": {
            "reference": str(args.reference),
            "candidate": str(args.candidate),
            "reference_meta": str(args.reference_meta),
            "candidate_meta": str(args.candidate_meta),
            "tree": args.tree,
            "rtol": args.rtol,
            "atol": args.atol,
        },
        "pass": passed,
        "schema": {
            "match": ref_names == cand_names,
            "reference_only": sorted(ref_names - cand_names),
            "candidate_only": sorted(cand_names - ref_names),
        },
        "event_ids": {"reference": reference_ids, "candidate": candidate_ids},
        "metadata": metadata,
        "branches": [asdict(result) for result in branch_results],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_str = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    args.output_json.write_text(output_str, encoding="utf-8")

    by_name = {result.branch: result for result in branch_results}
    with PdfPages(args.output_pdf) as pdf:
        plot_summary(pdf, summary)
        for name in args.plot_branches:
            if name in reference and name in candidate:
                plot_branch(pdf, name, reference[name], candidate[name], by_name[name])

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
