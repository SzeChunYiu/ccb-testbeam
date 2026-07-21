#!/usr/bin/env python3
"""Compare single-stave Geant4 ROOT outputs across thread configurations.

The validator is intentionally event-keyed: Geant4 worker scheduling may change row
order even when the physical event histories are reproducible. It therefore sorts
both ``events`` trees by the integer ``event`` column before comparing branches.

Outputs
-------
* machine-readable JSON summary;
* a multi-page PDF containing overlays, ratios, and absolute-difference plots;
* non-zero exit status when structural or configured numerical checks fail.

Example
-------
python scripts/compare_single_stave_mt_reproducibility.py \
  --reference mt_rng_t1.root \
  --candidate mt_rng_t4.root \
  --reference-meta mt_rng_t1.root.meta.json \
  --candidate-meta mt_rng_t4.root.meta.json \
  --output-json results/g4_mt_rng_comparison.json \
  --output-pdf docs/figures/g4_mt_rng_reproducibility.pdf
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

try:
    import uproot
except ImportError as exc:  # pragma: no cover - environment-dependent failure path
    raise SystemExit(
        "uproot is required; install the repository ROOT extra with "
        "`pip install -e '.[root]'`"
    ) from exc


DEFAULT_PLOT_BRANCHES = (
    "edep_scint_MeV",
    "edep_scint_raw_MeV",
    "track_len_scint_mm",
    "n_scint_generated",
    "arrival_readout",
    "detected_readout",
    "pe_sat_readout",
)

EXACT_INTEGER_BRANCHES = {
    "event",
    "n_scint_generated",
    "n_wls_generated",
    "n_cerenkov_generated",
    "arrival_readout",
    "arrival_f1far",
    "arrival_f2near",
    "arrival_f2far",
    "detected_readout",
    "detected_f1far",
    "detected_f2near",
    "detected_f2far",
}

PROVENANCE_KEYS = (
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
    "pde_scale",
    "coupling_efficiency",
    "sipm_n_cells",
)

THREAD_KEYS = (
    "threads_requested",
    "threads_effective",
    "G4FORCENUMBEROFTHREADS",
)


@dataclass(frozen=True)
class BranchResult:
    branch: str
    dtype: str
    entries: int
    exact_equal: bool
    n_mismatched: int
    max_abs_diff: float | None
    mean_abs_diff: float | None
    rms_diff: float | None
    allclose: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path, help="Reference ROOT file")
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate ROOT file")
    parser.add_argument("--reference-meta", type=Path, help="Reference metadata JSON sidecar")
    parser.add_argument("--candidate-meta", type=Path, help="Candidate metadata JSON sidecar")
    parser.add_argument("--output-json", required=True, type=Path, help="Summary JSON path")
    parser.add_argument("--output-pdf", required=True, type=Path, help="Diagnostic PDF path")
    parser.add_argument("--tree", default="events", help="Event-tree name (default: events)")
    parser.add_argument(
        "--rtol", type=float, default=0.0, help="Relative tolerance for floating branches"
    )
    parser.add_argument(
        "--atol", type=float, default=0.0, help="Absolute tolerance for floating branches"
    )
    parser.add_argument(
        "--plot-branches",
        nargs="*",
        default=list(DEFAULT_PLOT_BRANCHES),
        help="Branches to visualize",
    )
    parser.add_argument(
        "--allow-different-git-commit",
        action="store_true",
        help="Do not fail when metadata git_commit values differ",
    )
    return parser.parse_args()


def load_metadata(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"metadata must be a JSON object: {path}")
    return data


def normalize_branch_name(name: str) -> str:
    return name.split(";", maxsplit=1)[0]


def read_event_tree(path: Path, tree_name: str) -> dict[str, np.ndarray]:
    with uproot.open(path) as root_file:
        if tree_name not in root_file:
            available = sorted(normalize_branch_name(key) for key in root_file.keys())
            raise KeyError(f"tree {tree_name!r} absent from {path}; available={available}")
        tree = root_file[tree_name]
        arrays = tree.arrays(library="np")
    return {str(name): np.asarray(values) for name, values in arrays.items()}


def validate_event_ids(event_ids: np.ndarray, expected_events: int | None) -> dict[str, Any]:
    ids = np.asarray(event_ids)
    if ids.ndim != 1:
        raise ValueError(f"event branch must be one-dimensional, got shape={ids.shape}")
    if not np.issubdtype(ids.dtype, np.integer):
        raise TypeError(f"event branch must be integer-valued, got dtype={ids.dtype}")

    unique, counts = np.unique(ids, return_counts=True)
    duplicates = unique[counts > 1]
    observed_count = int(ids.size)
    expected_count = expected_events if expected_events is not None else observed_count
    expected = np.arange(expected_count, dtype=unique.dtype)
    missing = np.setdiff1d(expected, unique, assume_unique=False)
    unexpected = np.setdiff1d(unique, expected, assume_unique=False)

    return {
        "entries": observed_count,
        "unique_entries": int(unique.size),
        "expected_entries": int(expected_count),
        "duplicate_ids": duplicates.astype(int).tolist(),
        "missing_ids": missing.astype(int).tolist(),
        "unexpected_ids": unexpected.astype(int).tolist(),
        "valid": bool(
            observed_count == expected_count
            and unique.size == expected_count
            and duplicates.size == 0
            and missing.size == 0
            and unexpected.size == 0
        ),
    }


def sorted_arrays(arrays: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], np.ndarray]:
    if "event" not in arrays:
        raise KeyError("events tree is missing required integer branch 'event'")
    order = np.argsort(arrays["event"], kind="stable")
    return {name: values[order] for name, values in arrays.items()}, order


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
            branch=name,
            dtype=f"{reference.dtype}/{candidate.dtype}",
            entries=int(max(reference.size, candidate.size)),
            exact_equal=False,
            n_mismatched=int(max(reference.size, candidate.size)),
            max_abs_diff=None,
            mean_abs_diff=None,
            rms_diff=None,
            allclose=False,
        )

    exact = np.array_equal(reference, candidate, equal_nan=True)
    numeric = np.issubdtype(reference.dtype, np.number) and np.issubdtype(
        candidate.dtype, np.number
    )
    if not numeric:
        mismatched = int(np.count_nonzero(reference != candidate))
        return BranchResult(
            branch=name,
            dtype=str(reference.dtype),
            entries=int(reference.size),
            exact_equal=bool(exact),
            n_mismatched=mismatched,
            max_abs_diff=None,
            mean_abs_diff=None,
            rms_diff=None,
            allclose=bool(exact),
        )

    ref_float = reference.astype(np.float64, copy=False)
    cand_float = candidate.astype(np.float64, copy=False)
    finite_pair = np.isfinite(ref_float) & np.isfinite(cand_float)
    same_nonfinite = np.array_equal(np.isnan(ref_float), np.isnan(cand_float)) and np.array_equal(
        np.isposinf(ref_float), np.isposinf(cand_float)
    ) and np.array_equal(np.isneginf(ref_float), np.isneginf(cand_float))

    diffs = np.abs(ref_float[finite_pair] - cand_float[finite_pair])
    close_mask = np.isclose(ref_float, cand_float, rtol=rtol, atol=atol, equal_nan=True)
    allclose = bool(np.all(close_mask) and same_nonfinite)
    mismatched = int(np.count_nonzero(~close_mask))

    return BranchResult(
        branch=name,
        dtype=str(reference.dtype),
        entries=int(reference.size),
        exact_equal=bool(exact),
        n_mismatched=mismatched,
        max_abs_diff=float(np.max(diffs)) if diffs.size else 0.0,
        mean_abs_diff=float(np.mean(diffs)) if diffs.size else 0.0,
        rms_diff=float(math.sqrt(float(np.mean(diffs**2)))) if diffs.size else 0.0,
        allclose=allclose,
    )


def compare_metadata(
    reference: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    *,
    allow_different_git_commit: bool,
) -> dict[str, Any]:
    if reference is None or candidate is None:
        return {
            "provided": False,
            "valid": False,
            "reason": "both metadata sidecars are required for provenance validation",
        }

    comparisons: dict[str, dict[str, Any]] = {}
    valid = True
    for key in PROVENANCE_KEYS:
        ref_value = reference.get(key)
        cand_value = candidate.get(key)
        equal = ref_value == cand_value
        required_equal = not (key == "git_commit" and allow_different_git_commit)
        comparisons[key] = {
            "reference": ref_value,
            "candidate": cand_value,
            "equal": equal,
            "required_equal": required_equal,
        }
        if required_equal and not equal:
            valid = False

    thread_provenance = {
        key: {"reference": reference.get(key), "candidate": candidate.get(key)}
        for key in THREAD_KEYS
    }
    return {
        "provided": True,
        "valid": valid,
        "physics_provenance": comparisons,
        "thread_provenance": thread_provenance,
    }


def choose_bins(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    values = np.concatenate((reference.ravel(), candidate.ravel())).astype(np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return np.linspace(0.0, 1.0, 21)
    low, high = np.min(values), np.max(values)
    if low == high:
        pad = max(abs(low) * 0.05, 0.5)
        return np.linspace(low - pad, high + pad, 21)
    return np.histogram_bin_edges(values, bins="fd")


def add_branch_plot(
    pdf: PdfPages,
    name: str,
    reference: np.ndarray,
    candidate: np.ndarray,
    result: BranchResult,
) -> None:
    if not np.issubdtype(reference.dtype, np.number):
        return
    bins = choose_bins(reference, candidate)
    ref_hist, _ = np.histogram(reference, bins=bins)
    cand_hist, _ = np.histogram(candidate, bins=bins)
    centers = 0.5 * (bins[:-1] + bins[1:])
    widths = np.diff(bins)
    ratio = np.divide(
        cand_hist,
        ref_hist,
        out=np.full(cand_hist.shape, np.nan, dtype=float),
        where=ref_hist != 0,
    )
    differences = candidate.astype(float) - reference.astype(float)

    figure, axes = plt.subplots(3, 1, figsize=(8.5, 11), constrained_layout=True)
    axes[0].stairs(ref_hist, bins, label="reference")
    axes[0].stairs(cand_hist, bins, label="candidate")
    axes[0].set_ylabel("Events / bin")
    axes[0].set_title(f"{name}: event distribution")
    axes[0].legend()

    axes[1].errorbar(centers, ratio, xerr=widths / 2.0, fmt="o", markersize=3)
    axes[1].axhline(1.0, linestyle="--")
    axes[1].set_ylabel("Candidate / reference")
    axes[1].set_xlabel(name)

    finite_diffs = differences[np.isfinite(differences)]
    diff_bins = np.histogram_bin_edges(finite_diffs, bins="fd") if finite_diffs.size else 20
    axes[2].hist(finite_diffs, bins=diff_bins)
    axes[2].set_xlabel(f"candidate - reference ({name})")
    axes[2].set_ylabel("Events / bin")
    axes[2].set_title(
        "Event-keyed differences: "
        f"mismatch={result.n_mismatched}, max|Δ|={result.max_abs_diff:.6g}, "
        f"RMS(Δ)={result.rms_diff:.6g}"
    )
    pdf.savefig(figure)
    plt.close(figure)


def write_summary_page(pdf: PdfPages, summary: dict[str, Any]) -> None:
    figure = plt.figure(figsize=(8.5, 11))
    figure.text(0.08, 0.95, "Single-stave Geant4 MT reproducibility audit", fontsize=16)
    lines = [
        f"Reference: {summary['inputs']['reference']}",
        f"Candidate: {summary['inputs']['candidate']}",
        f"Tree: {summary['inputs']['tree']}",
        f"Overall pass: {summary['pass']}",
        f"Schema match: {summary['schema']['match']}",
        f"Reference event IDs valid: {summary['event_ids']['reference']['valid']}",
        f"Candidate event IDs valid: {summary['event_ids']['candidate']['valid']}",
        f"Metadata physics provenance valid: {summary['metadata']['valid']}",
        f"Branches compared: {len(summary['branches'])}",
        f"Branches passing tolerance: {sum(item['allclose'] for item in summary['branches'])}",
        "",
        "Acceptance meaning:",
        "PASS requires complete/unique event IDs, identical branch schemas,",
        "matching physics provenance, and every event-keyed branch within",
        "the configured numerical tolerances. Thread provenance is reported",
        "but is expected to differ between the compared runs.",
    ]
    figure.text(0.08, 0.88, "\n".join(lines), va="top", family="monospace", fontsize=10)
    pdf.savefig(figure)
    plt.close(figure)


def main() -> int:
    args = parse_args()
    if args.rtol < 0 or args.atol < 0:
        raise SystemExit("--rtol and --atol must be non-negative")

    reference_meta = load_metadata(args.reference_meta)
    candidate_meta = load_metadata(args.candidate_meta)
    reference_arrays = read_event_tree(args.reference, args.tree)
    candidate_arrays = read_event_tree(args.candidate, args.tree)

    expected_reference = (
        int(reference_meta["n_events"])
        if reference_meta is not None and "n_events" in reference_meta
        else None
    )
    expected_candidate = (
        int(candidate_meta["n_events"])
        if candidate_meta is not None and "n_events" in candidate_meta
        else None
    )
    reference_id_check = validate_event_ids(reference_arrays["event"], expected_reference)
    candidate_id_check = validate_event_ids(candidate_arrays["event"], expected_candidate)

    reference_sorted, _ = sorted_arrays(reference_arrays)
    candidate_sorted, _ = sorted_arrays(candidate_arrays)
    reference_branches = set(reference_sorted)
    candidate_branches = set(candidate_sorted)
    common_branches = sorted(reference_branches & candidate_branches)
    schema_match = reference_branches == candidate_branches

    branch_results = [
        compare_branch(
            name,
            reference_sorted[name],
            candidate_sorted[name],
            rtol=args.rtol,
            atol=args.atol,
        )
        for name in common_branches
    ]
    metadata_result = compare_metadata(
        reference_meta,
        candidate_meta,
        allow_different_git_commit=args.allow_different_git_commit,
    )

    overall_pass = bool(
        schema_match
        and reference_id_check["valid"]
        and candidate_id_check["valid"]
        and metadata_result["valid"]
        and all(result.allclose for result in branch_results)
    )
    summary = {
        "schema_version": "ccb-g4-mt-reproducibility/1",
        "inputs": {
            "reference": str(args.reference),
            "candidate": str(args.candidate),
            "reference_meta": str(args.reference_meta) if args.reference_meta else None,
            "candidate_meta": str(args.candidate_meta) if args.candidate_meta else None,
            "tree": args.tree,
            "rtol": args.rtol,
            "atol": args.atol,
        },
        "pass": overall_pass,
        "schema": {
            "match": schema_match,
            "reference_only": sorted(reference_branches - candidate_branches),
            "candidate_only": sorted(candidate_branches - reference_branches),
        },
        "event_ids": {
            "reference": reference_id_check,
            "candidate": candidate_id_check,
        },
        "metadata": metadata_result,
        "branches": [result.__dict__ for result in branch_results],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    result_by_name = {result.branch: result for result in branch_results}
    with PdfPages(args.output_pdf) as pdf:
        write_summary_page(pdf, summary)
        for branch in args.plot_branches:
            if branch not in reference_sorted or branch not in candidate_sorted:
                continue
            add_branch_plot(
                pdf,
                branch,
                reference_sorted[branch],
                candidate_sorted[branch],
                result_by_name[branch],
            )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
