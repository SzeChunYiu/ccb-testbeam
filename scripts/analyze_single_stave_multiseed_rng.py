#!/usr/bin/env python3
"""Audit a multiseed ensemble of single-stave Geant4 ROOT outputs.

The input manifest is JSON with a ``runs`` list. Each run requires ``root`` and
``meta`` paths; optional labels are preserved. The program validates comparable
physics provenance, complete event IDs, unique seeds within each effective-thread
group, duplicated event streams across different seeds, event-indexed cross-seed
correlations, seed-to-seed stability, and thread-group consistency. It writes a
machine-readable JSON summary and a diagnostic PDF.

Example manifest::

  {
    "runs": [
      {"root": "seed1_t1.root", "meta": "seed1_t1.root.meta.json", "label": "s1-t1"},
      {"root": "seed2_t1.root", "meta": "seed2_t1.root.meta.json", "label": "s2-t1"},
      {"root": "seed1_t4.root", "meta": "seed1_t4.root.meta.json", "label": "s1-t4"},
      {"root": "seed2_t4.root", "meta": "seed2_t4.root.meta.json", "label": "s2-t4"}
    ]
  }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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


DEFAULT_OBSERVABLES = (
    "edep_scint_MeV",
    "n_scint_generated",
    "arrival_readout",
    "detected_readout",
    "pe_sat_readout",
)

PHYSICS_KEYS = (
    "schema",
    "git_commit",
    "geometry_hash",
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


@dataclass(frozen=True)
class RunSummary:
    label: str
    root: str
    meta: str
    seed: int
    threads_requested: int | None
    threads_effective: int | None
    forced_threads: str | None
    n_events: int
    stream_hash: str
    observables: dict[str, dict[str, float]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-pdf", required=True, type=Path)
    parser.add_argument("--tree", default="events")
    parser.add_argument("--observables", nargs="*", default=list(DEFAULT_OBSERVABLES))
    parser.add_argument("--minimum-seeds-per-thread", type=int, default=4)
    parser.add_argument(
        "--max-thread-effect-z",
        type=float,
        default=3.0,
        help="Maximum absolute two-sample z score for thread-group mean differences",
    )
    parser.add_argument(
        "--max-seed-outlier-z",
        type=float,
        default=4.0,
        help="Maximum absolute robust z score for a run mean within an observable",
    )
    parser.add_argument(
        "--max-cross-seed-correlation-z",
        type=float,
        default=4.0,
        help="Maximum absolute Fisher-z significance for event-indexed correlation",
    )
    parser.add_argument(
        "--allow-different-git-commit",
        action="store_true",
        help="Permit git_commit to differ while requiring other physics provenance",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("manifest must contain a non-empty 'runs' list")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(runs):
        if not isinstance(row, dict):
            raise TypeError(f"manifest runs[{index}] must be an object")
        if "root" not in row or "meta" not in row:
            raise KeyError(f"manifest runs[{index}] requires root and meta")
        normalized.append(
            {
                "root": Path(row["root"]),
                "meta": Path(row["meta"]),
                "label": str(row.get("label", f"run-{index:03d}")),
            }
        )
    return normalized


def read_events(path: Path, tree_name: str, observables: list[str]) -> dict[str, np.ndarray]:
    with uproot.open(path) as root_file:
        if tree_name not in root_file:
            raise KeyError(f"tree {tree_name!r} absent from {path}")
        tree = root_file[tree_name]
        required = ["event", *observables]
        missing = sorted(set(required) - set(tree.keys()))
        if missing:
            raise KeyError(f"{path} missing branches: {missing}")
        arrays = tree.arrays(required, library="np")
        if isinstance(arrays, np.ndarray) and arrays.dtype.names is not None:
            arrays = {name: np.asarray(arrays[name]) for name in arrays.dtype.names}
        elif isinstance(arrays, np.ndarray):
            arrays = {required[0]: arrays}
    return {str(name): np.asarray(values) for name, values in arrays.items()}


def validate_event_ids(ids: np.ndarray, n_events: int) -> None:
    if ids.ndim != 1 or not np.issubdtype(ids.dtype, np.integer):
        raise TypeError("event IDs must be a one-dimensional integer array")
    expected = np.arange(n_events, dtype=ids.dtype)
    if ids.size != n_events or not np.array_equal(np.sort(ids), expected):
        raise ValueError("event IDs must be complete and unique in [0, n_events)")


def sort_by_event(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    order = np.argsort(arrays["event"], kind="stable")
    return {name: values[order] for name, values in arrays.items()}


def stream_hash(arrays: dict[str, np.ndarray], observables: list[str]) -> str:
    digest = hashlib.sha256()
    for name in ["event", *sorted(observables)]:
        values = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("utf-8"))
        digest.update(str(values.dtype).encode("ascii"))
        digest.update(np.asarray(values.shape, dtype=np.int64).tobytes())
        digest.update(values.tobytes())
    return digest.hexdigest()


def observable_stats(values: np.ndarray) -> dict[str, float]:
    if values.ndim != 1 or not np.issubdtype(values.dtype, np.number):
        raise TypeError("ensemble observables must be one-dimensional numeric branches")
    numeric = values.astype(np.float64, copy=False)
    if not np.all(np.isfinite(numeric)):
        raise ValueError("ensemble observables must contain only finite values")
    n = int(numeric.size)
    mean = float(np.mean(numeric)) if n else math.nan
    std = float(np.std(numeric, ddof=1)) if n > 1 else 0.0
    sem = std / math.sqrt(n) if n > 0 else math.nan
    return {
        "n": float(n),
        "mean": mean,
        "std": std,
        "sem": sem,
        "minimum": float(np.min(numeric)) if n else math.nan,
        "maximum": float(np.max(numeric)) if n else math.nan,
    }


def compare_physics_metadata(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    allow_different_git_commit: bool,
) -> list[str]:
    mismatches: list[str] = []
    for key in PHYSICS_KEYS:
        if key == "git_commit" and allow_different_git_commit:
            continue
        if reference.get(key) != candidate.get(key):
            mismatches.append(key)
    return mismatches


def robust_zscores(values: np.ndarray) -> np.ndarray:
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    if mad == 0:
        std = np.std(values, ddof=1) if values.size > 1 else 0.0
        return np.zeros_like(values) if std == 0 else (values - np.mean(values)) / std
    return 0.6744897501960817 * (values - median) / mad


def two_sample_z(mean_a: float, sem_a: float, mean_b: float, sem_b: float) -> float:
    denominator = math.sqrt(sem_a**2 + sem_b**2)
    if denominator == 0:
        return 0.0 if mean_a == mean_b else math.inf
    return (mean_a - mean_b) / denominator


def build_summary(
    manifest_rows: list[dict[str, Any]],
    tree_name: str,
    observables: list[str],
    *,
    minimum_seeds_per_thread: int,
    max_thread_effect_z: float,
    max_seed_outlier_z: float,
    max_cross_seed_correlation_z: float,
    allow_different_git_commit: bool,
) -> dict[str, Any]:
    if minimum_seeds_per_thread < 2:
        raise ValueError("minimum seeds per thread group must be at least 2")
    if (
        max_thread_effect_z <= 0
        or max_seed_outlier_z <= 0
        or max_cross_seed_correlation_z <= 0
    ):
        raise ValueError("z-score thresholds must be positive")

    runs: list[RunSummary] = []
    arrays_by_label: dict[str, dict[str, np.ndarray]] = {}
    baseline_meta: dict[str, Any] | None = None
    provenance_mismatches: dict[str, list[str]] = {}

    for row in manifest_rows:
        meta = load_json(row["meta"])
        n_events = int(meta["n_events"])
        arrays = sort_by_event(read_events(row["root"], tree_name, observables))
        validate_event_ids(arrays["event"], n_events)
        if baseline_meta is None:
            baseline_meta = meta
        else:
            mismatch = compare_physics_metadata(
                baseline_meta,
                meta,
                allow_different_git_commit=allow_different_git_commit,
            )
            if mismatch:
                provenance_mismatches[row["label"]] = mismatch
        stats = {name: observable_stats(arrays[name]) for name in observables}
        runs.append(
            RunSummary(
                label=row["label"],
                root=str(row["root"]),
                meta=str(row["meta"]),
                seed=int(meta["seed"]),
                threads_requested=(
                    int(meta["threads_requested"])
                    if meta.get("threads_requested") is not None
                    else None
                ),
                threads_effective=(
                    int(meta["threads_effective"])
                    if meta.get("threads_effective") is not None
                    else None
                ),
                forced_threads=(
                    str(meta["G4FORCENUMBEROFTHREADS"])
                    if meta.get("G4FORCENUMBEROFTHREADS") not in (None, "")
                    else None
                ),
                n_events=n_events,
                stream_hash=stream_hash(arrays, observables),
                observables=stats,
            )
        )
        arrays_by_label[row["label"]] = arrays

    labels = [run.label for run in runs]
    if len(set(labels)) != len(labels):
        raise ValueError("manifest labels must be unique")

    duplicate_streams: list[dict[str, Any]] = []
    for index, left in enumerate(runs):
        for right in runs[index + 1 :]:
            if left.stream_hash == right.stream_hash and left.seed != right.seed:
                duplicate_streams.append(
                    {
                        "left": left.label,
                        "right": right.label,
                        "left_seed": left.seed,
                        "right_seed": right.seed,
                        "stream_hash": left.stream_hash,
                    }
                )

    by_thread: dict[int, list[RunSummary]] = {}
    for run in runs:
        if run.threads_effective is None:
            continue
        by_thread.setdefault(run.threads_effective, []).append(run)

    seed_coverage = {
        str(thread): {
            "run_count": len(group),
            "unique_seed_count": len({run.seed for run in group}),
            "minimum_required": minimum_seeds_per_thread,
            "pass": len({run.seed for run in group}) >= minimum_seeds_per_thread,
        }
        for thread, group in sorted(by_thread.items())
    }

    outliers: list[dict[str, Any]] = []
    for observable in observables:
        means = np.asarray([run.observables[observable]["mean"] for run in runs])
        zscores = robust_zscores(means)
        for run, zscore in zip(runs, zscores, strict=True):
            if abs(float(zscore)) > max_seed_outlier_z:
                outliers.append(
                    {
                        "label": run.label,
                        "seed": run.seed,
                        "threads_effective": run.threads_effective,
                        "observable": observable,
                        "mean": run.observables[observable]["mean"],
                        "robust_z": float(zscore),
                    }
                )

    thread_effects: list[dict[str, Any]] = []
    thread_ids = sorted(by_thread)
    for observable in observables:
        for index, left_thread in enumerate(thread_ids):
            for right_thread in thread_ids[index + 1 :]:
                left_runs = by_thread[left_thread]
                right_runs = by_thread[right_thread]
                left_means = np.asarray(
                    [run.observables[observable]["mean"] for run in left_runs], dtype=float
                )
                right_means = np.asarray(
                    [run.observables[observable]["mean"] for run in right_runs], dtype=float
                )
                left_mean = float(np.mean(left_means))
                right_mean = float(np.mean(right_means))
                left_sem = (
                    float(np.std(left_means, ddof=1) / math.sqrt(left_means.size))
                    if left_means.size > 1
                    else math.inf
                )
                right_sem = (
                    float(np.std(right_means, ddof=1) / math.sqrt(right_means.size))
                    if right_means.size > 1
                    else math.inf
                )
                zscore = two_sample_z(left_mean, left_sem, right_mean, right_sem)
                thread_effects.append(
                    {
                        "observable": observable,
                        "left_threads": left_thread,
                        "right_threads": right_thread,
                        "left_seed_count": int(left_means.size),
                        "right_seed_count": int(right_means.size),
                        "left_mean": left_mean,
                        "right_mean": right_mean,
                        "difference": left_mean - right_mean,
                        "z_score": zscore,
                        "pass": bool(abs(zscore) <= max_thread_effect_z),
                    }
                )

    cross_seed_correlations: list[dict[str, Any]] = []
    for observable in observables:
        for index, left in enumerate(runs):
            for right in runs[index + 1 :]:
                if left.seed == right.seed:
                    continue
                left_values = arrays_by_label[left.label][observable].astype(float)
                right_values = arrays_by_label[right.label][observable].astype(float)
                if left_values.size != right_values.size or left_values.size < 4:
                    correlation = math.nan
                    fisher_z = math.inf
                elif np.std(left_values) == 0 or np.std(right_values) == 0:
                    correlation = 1.0 if np.array_equal(left_values, right_values) else 0.0
                    fisher_z = math.inf if abs(correlation) == 1.0 else 0.0
                else:
                    correlation = float(np.corrcoef(left_values, right_values)[0, 1])
                    clipped = float(np.clip(correlation, -0.999999999999, 0.999999999999))
                    fisher_z = float(np.arctanh(clipped) * math.sqrt(left_values.size - 3))
                cross_seed_correlations.append(
                    {
                        "observable": observable,
                        "left": left.label,
                        "right": right.label,
                        "left_seed": left.seed,
                        "right_seed": right.seed,
                        "n_events": int(left_values.size),
                        "pearson_r": correlation,
                        "fisher_z": fisher_z,
                        "pass": bool(
                            math.isfinite(fisher_z)
                            and abs(fisher_z) <= max_cross_seed_correlation_z
                        ),
                    }
                )

    duplicate_seeds_within_thread: list[dict[str, Any]] = []
    for thread, group in sorted(by_thread.items()):
        seen: dict[int, str] = {}
        for run in group:
            if run.seed in seen:
                duplicate_seeds_within_thread.append(
                    {
                        "threads_effective": thread,
                        "seed": run.seed,
                        "first_label": seen[run.seed],
                        "duplicate_label": run.label,
                    }
                )
            else:
                seen[run.seed] = run.label

    all_groups_covered = bool(seed_coverage) and all(
        row["pass"] for row in seed_coverage.values()
    )
    passed = bool(
        not provenance_mismatches
        and not duplicate_seeds_within_thread
        and not duplicate_streams
        and all_groups_covered
        and not outliers
        and all(row["pass"] for row in thread_effects)
        and all(row["pass"] for row in cross_seed_correlations)
    )

    return {
        "pass": passed,
        "criteria": {
            "minimum_seeds_per_thread": minimum_seeds_per_thread,
            "max_thread_effect_z": max_thread_effect_z,
            "max_seed_outlier_z": max_seed_outlier_z,
            "max_cross_seed_correlation_z": max_cross_seed_correlation_z,
            "exact_stream_hash_fields": ["event", *sorted(observables)],
        },
        "runs": [asdict(run) for run in runs],
        "physics_provenance_mismatches": provenance_mismatches,
        "duplicate_seeds_within_effective_thread_group": duplicate_seeds_within_thread,
        "duplicate_streams_across_different_seeds": duplicate_streams,
        "seed_coverage_by_effective_thread_count": seed_coverage,
        "seed_mean_outliers": outliers,
        "cross_seed_event_index_correlations": cross_seed_correlations,
        "thread_group_effects": thread_effects,
    }


def plot_summary(pdf: PdfPages, summary: dict[str, Any]) -> None:
    figure = plt.figure(figsize=(8.5, 11))
    lines = [
        "Single-stave Geant4 multiseed ensemble audit",
        "",
        f"Overall pass: {summary['pass']}",
        f"Runs: {len(summary['runs'])}",
        "Duplicate seeds within thread groups: "
        f"{len(summary['duplicate_seeds_within_effective_thread_group'])}",
        "Duplicate streams across different seeds: "
        f"{len(summary['duplicate_streams_across_different_seeds'])}",
        f"Physics provenance mismatches: {len(summary['physics_provenance_mismatches'])}",
        f"Seed-mean outliers: {len(summary['seed_mean_outliers'])}",
        "Failing cross-seed correlations: "
        f"{sum(not row['pass'] for row in summary['cross_seed_event_index_correlations'])}",
        "Failing thread effects: "
        f"{sum(not row['pass'] for row in summary['thread_group_effects'])}",
        "",
        "PASS requires comparable physics provenance, unique seeds within each",
        "effective-thread group, no exact duplicate streams across different seeds,",
        "adequate seed coverage in every effective-thread group, no extreme",
        "seed-mean outliers, no event-indexed cross-seed correlation beyond the",
        "configured Fisher-z threshold, and no thread-group mean difference beyond the",
        "configured z threshold.",
        "",
        "This is a diagnostic ensemble test, not proof of full RNG independence.",
    ]
    figure.text(0.07, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=10)
    pdf.savefig(figure)
    plt.close(figure)


def plot_observables(pdf: PdfPages, summary: dict[str, Any], observables: list[str]) -> None:
    runs = summary["runs"]
    thread_values = sorted(
        {run["threads_effective"] for run in runs if run["threads_effective"] is not None}
    )
    for observable in observables:
        figure, axes = plt.subplots(2, 1, figsize=(8.5, 11), constrained_layout=True)
        for thread in thread_values:
            group = [run for run in runs if run["threads_effective"] == thread]
            seeds = np.asarray([run["seed"] for run in group])
            means = np.asarray([run["observables"][observable]["mean"] for run in group])
            sems = np.asarray([run["observables"][observable]["sem"] for run in group])
            order = np.argsort(seeds)
            axes[0].errorbar(
                seeds[order],
                means[order],
                yerr=sems[order],
                marker="o",
                linestyle="none",
                label=f"{thread} effective threads",
            )
        axes[0].set_title(f"{observable}: run means by seed")
        axes[0].set_xlabel("Configured seed")
        axes[0].set_ylabel(f"Mean {observable} ± within-run SEM")
        axes[0].legend()

        labels = [run["label"] for run in runs]
        means = np.asarray([run["observables"][observable]["mean"] for run in runs])
        zscores = robust_zscores(means)
        axes[1].axhline(0.0, linestyle="--")
        axes[1].scatter(np.arange(len(runs)), zscores)
        axes[1].set_xticks(np.arange(len(runs)), labels, rotation=45, ha="right")
        axes[1].set_ylabel("Robust z score of run mean")
        axes[1].set_title("Seed-level outlier diagnostic")
        pdf.savefig(figure)
        plt.close(figure)


def main() -> int:
    args = parse_args()
    rows = load_manifest(args.manifest)
    summary = build_summary(
        rows,
        args.tree,
        list(args.observables),
        minimum_seeds_per_thread=args.minimum_seeds_per_thread,
        max_thread_effect_z=args.max_thread_effect_z,
        max_seed_outlier_z=args.max_seed_outlier_z,
        max_cross_seed_correlation_z=args.max_cross_seed_correlation_z,
        allow_different_git_commit=args.allow_different_git_commit,
    )
    summary["inputs"] = {
        "manifest": str(args.manifest),
        "tree": args.tree,
        "observables": list(args.observables),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with PdfPages(args.output_pdf) as pdf:
        plot_summary(pdf, summary)
        plot_observables(pdf, summary, list(args.observables))

    print(
        json.dumps(
            {
                "pass": summary["pass"],
                "output_json": str(args.output_json),
                "output_pdf": str(args.output_pdf),
            },
            sort_keys=True,
        )
    )
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
