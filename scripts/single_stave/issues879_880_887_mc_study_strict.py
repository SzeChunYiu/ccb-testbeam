#!/usr/bin/env python3
"""Fail-closed replacement entry point for the issue #879/#880/#887 MC study.

The historical producer is retained for provenance, but it silently coerces or
falls back when event weights are invalid.  This entry point validates exactly
one finite, nonnegative PrimaryWeight per event, installs strict weighted
estimators for all three studies, reports direction-explicit issue #880
comparisons, and writes a content-addressed result atomically.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
LEGACY_PATH = SCRIPT_DIR / "issues879_880_887_mc_study.py"
STRICT_PATH = SCRIPT_DIR / "strict_event_weights.py"
EXPECTED_OUTPUT_NAMES = (
    "issues879_880_887_result.json",
    "fig_879_readout_pattern_compare.png",
    "fig_879_readout_pattern_compare.pdf",
    "fig_879_layer_edep_profile.png",
    "fig_879_layer_edep_profile.pdf",
    "fig_880_weighted_vs_unweighted.png",
    "fig_880_weighted_vs_unweighted.pdf",
    "fig_887_amplitude_cut_scan.png",
    "fig_887_amplitude_cut_scan.pdf",
    "fig_887_deltaE_E_per_cut.png",
    "fig_887_deltaE_E_per_cut.pdf",
)
PRODUCER_POLICY = "ISSUE880_STRICT_CONTENT_ADDRESSED_WEIGHTED_RERUN"
PRODUCER_VERSION = "1.0.0"


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


strict = _load_module(STRICT_PATH, "ccb_strict_event_weights")
legacy = _load_module(LEGACY_PATH, "ccb_issues879_880_887_legacy")


def _strict_wfrac(values: Any, weights: Any, threshold: float) -> float:
    value_array = np.asarray(values, dtype=float)
    return strict.weighted_fraction(value_array > float(threshold), weights)


def _strict_bhattacharyya_overlap(
    x_p: Any,
    x_d: Any,
    w_p: Any,
    w_d: Any,
    bins: Any,
    _rng: Any,
) -> float:
    proton = np.asarray(x_p, dtype=float)
    deuteron = np.asarray(x_d, dtype=float)
    if proton.ndim != 1 or deuteron.ndim != 1:
        raise strict.WeightValidationError("PID samples must be one-dimensional")
    if proton.size == 0 or deuteron.size == 0:
        raise strict.WeightValidationError("PID samples must not be empty")
    if not np.all(np.isfinite(proton)) or not np.all(np.isfinite(deuteron)):
        raise strict.WeightValidationError("PID samples contain nonfinite values")
    proton_weights = strict.validate_event_weights(w_p, expected_length=proton.size)
    deuteron_weights = strict.validate_event_weights(w_d, expected_length=deuteron.size)
    edges = np.asarray(bins, dtype=float)
    if edges.ndim != 1 or edges.size < 2:
        raise strict.WeightValidationError("histogram edges must be a one-dimensional vector")
    if not np.all(np.isfinite(edges)) or not np.all(np.diff(edges) > 0.0):
        raise strict.WeightValidationError("histogram edges must be finite and strictly increasing")
    hp, _ = np.histogram(proton, bins=edges, weights=proton_weights)
    hd, _ = np.histogram(deuteron, bins=edges, weights=deuteron_weights)
    hp_total = float(np.sum(hp))
    hd_total = float(np.sum(hd))
    if hp_total <= 0.0 or hd_total <= 0.0:
        raise strict.WeightValidationError("PID histograms have nonpositive total weight")
    proton_probability = hp / hp_total
    deuteron_probability = hd / hd_total
    coefficient = float(np.sum(np.sqrt(proton_probability * deuteron_probability)))
    result = 1.0 - coefficient
    if not np.isfinite(result) or result < -1e-12 or result > 1.0 + 1e-12:
        raise strict.WeightValidationError(f"invalid Bhattacharyya separation: {result}")
    return float(min(1.0, max(0.0, result)))


def _install_strict_estimators() -> None:
    legacy.wmean = strict.weighted_mean
    legacy.wmedian = strict.weighted_median
    legacy.wfrac = _strict_wfrac
    legacy.wcorr = strict.weighted_correlation
    legacy.ess = strict.effective_sample_size
    legacy.bhattacharyya_overlap = _strict_bhattacharyya_overlap


def _require_one_per_event(array: Any, *, name: str, awkward_module: Any) -> None:
    counts = awkward_module.to_numpy(awkward_module.num(array, axis=1))
    invalid = np.flatnonzero(counts != 1)
    if invalid.size:
        sample = invalid[:5].tolist()
        values = counts[invalid[:5]].tolist()
        raise strict.WeightValidationError(
            f"{name} must contain exactly one value per event; indices={sample}, counts={values}"
        )


def load_mc_strict(root: Path, tree: str, entry_stop: int | None):
    """Load exact ROOT bytes with strict event-cardinality and weight validation."""
    import awkward as ak
    import uproot

    root_path = Path(root).expanduser().resolve(strict=True)
    before = strict.file_sha256(root_path)
    file_handle = uproot.open(root_path)
    try:
        tree_handle = file_handle[tree]
        available_entries = int(tree_handle.num_entries)
        expected_entries = (
            min(available_entries, int(entry_stop))
            if entry_stop is not None
            else available_entries
        )
        branches = [
            "Sci_bar_LayerID",
            "Sci_bar_LayerID1",
            "Sci_bar_EDep",
            "Sci_bar_PDG",
            "PrimaryWeight",
            "PrimaryPDG",
            "PrimaryEkin",
        ]
        arrays = tree_handle.arrays(branches, entry_stop=entry_stop, library="ak")
    finally:
        file_handle.close()

    event_count = len(arrays["PrimaryWeight"])
    if event_count != expected_entries:
        raise strict.WeightValidationError(
            f"loaded {event_count} events; expected {expected_entries} from tree metadata"
        )
    primary_weights = arrays["PrimaryWeight"]
    primary_pdg = arrays["PrimaryPDG"]
    _require_one_per_event(primary_weights, name="PrimaryWeight", awkward_module=ak)
    _require_one_per_event(primary_pdg, name="PrimaryPDG", awkward_module=ak)
    weights = strict.validate_event_weights(
        ak.to_numpy(ak.firsts(primary_weights, axis=1)).astype(float),
        expected_length=event_count,
        name="PrimaryWeight",
    )
    primary_pdg_values = ak.to_numpy(ak.firsts(primary_pdg, axis=1)).astype(int)

    arm = arrays["Sci_bar_LayerID1"]
    layer = arrays["Sci_bar_LayerID"]
    energy_deposit = arrays["Sci_bar_EDep"]
    hit_pdg = arrays["Sci_bar_PDG"]
    flat_energy = ak.to_numpy(ak.flatten(energy_deposit)).astype(float)
    if not np.all(np.isfinite(flat_energy)):
        raise strict.WeightValidationError("Sci_bar_EDep contains nonfinite values")
    if np.any(flat_energy < 0.0):
        raise strict.WeightValidationError("Sci_bar_EDep contains negative energy deposit")

    per_layer_energy: dict[int, np.ndarray] = {}
    for layer_id in range(8):
        mask = (arm == legacy.B_ARM) & (layer == layer_id)
        values = ak.to_numpy(ak.sum(energy_deposit[mask], axis=1)).astype(float)
        if values.shape != (event_count,) or not np.all(np.isfinite(values)):
            raise strict.WeightValidationError(
                f"per-event LayerID {layer_id} energy vector is invalid: shape={values.shape}"
            )
        per_layer_energy[layer_id] = values
    total_b_energy = np.sum([per_layer_energy[index] for index in range(8)], axis=0)

    flat_pdg = ak.to_numpy(ak.flatten(hit_pdg)).astype(np.int64)
    absolute_pdg = np.abs(flat_pdg)
    is_nucleus = absolute_pdg >= 1_000_000_000
    nucleus_charge = ((absolute_pdg - 1_000_000_000) // 10_000).astype(int)
    charged_flat = np.zeros(len(flat_pdg), dtype=bool)
    charged_known = np.array(
        [2212, 11, 211, 321, 13, 1000010030, 1000020030, 1000020040],
        dtype=np.int64,
    )
    charged_flat[~is_nucleus] = np.isin(absolute_pdg[~is_nucleus], charged_known)
    charged_flat[is_nucleus] = nucleus_charge[is_nucleus] > 0
    counts = ak.to_numpy(ak.num(hit_pdg, axis=1))
    charged_hit = ak.unflatten(ak.from_numpy(charged_flat), counts)
    entering_mask = (arm == legacy.B_ARM) & (layer == 0) & charged_hit
    entering_charged = ak.to_numpy(ak.any(entering_mask, axis=1)).astype(bool)
    entering_pdg_jagged = hit_pdg[entering_mask]
    has_entering = ak.to_numpy(ak.num(entering_pdg_jagged, axis=1)) > 0
    first_entering = ak.to_numpy(ak.firsts(entering_pdg_jagged, axis=1))
    entering_pdg = np.zeros(event_count, dtype=int)
    entering_pdg[has_entering] = first_entering[has_entering].astype(int)

    after = strict.file_sha256(root_path)
    if before["bytes"] != after["bytes"] or before["sha256"] != after["sha256"]:
        raise strict.WeightValidationError("ROOT input changed while the study was reading it")
    root_provenance = {
        **before,
        "hash_read_policy": "SHA256_BEFORE_AND_AFTER_ROOT_READ_MUST_MATCH",
        "tree": tree,
        "tree_entries_available": available_entries,
        "tree_entries_loaded": event_count,
        "entry_stop": entry_stop,
    }
    return (
        per_layer_energy,
        weights,
        primary_pdg_values,
        entering_pdg,
        entering_charged,
        total_b_energy,
        event_count,
        root_provenance,
    )


def study_880_strict(
    energy_by_layer: dict[int, np.ndarray],
    weights: np.ndarray,
    entering_pdg: np.ndarray,
    entering_charged: np.ndarray,
) -> dict[str, Any]:
    first_b = np.asarray(energy_by_layer[0], dtype=float)
    weight_array = strict.validate_event_weights(weights, expected_length=first_b.size)
    entering_pdg_array = np.asarray(entering_pdg)
    charged_array = np.asarray(entering_charged, dtype=bool)
    if entering_pdg_array.shape != first_b.shape or charged_array.shape != first_b.shape:
        raise strict.WeightValidationError("entering-B labels must be event-aligned")
    if not np.any(charged_array):
        raise strict.WeightValidationError("no charged entering-B events; fraction is undefined")
    deuteron = (entering_pdg_array == legacy.D_PDG) & charged_array

    mean_unweighted = float(np.mean(first_b))
    mean_weighted = strict.weighted_mean(first_b, weight_array)
    median_unweighted = float(np.median(first_b))
    median_weighted = strict.weighted_median(first_b, weight_array)
    deuteron_unweighted = float(np.mean(deuteron[charged_array]))
    deuteron_weighted = strict.weighted_fraction(
        deuteron[charged_array], weight_array[charged_array]
    )
    layer_zero = np.asarray(energy_by_layer[0], dtype=float)
    layer_one = np.asarray(energy_by_layer[1], dtype=float)
    if float(np.var(layer_zero)) <= 0.0 or float(np.var(layer_one)) <= 0.0:
        raise strict.WeightValidationError("LayerID 0/1 correlation has zero variance")
    correlation_unweighted = float(np.corrcoef(layer_zero, layer_one)[0, 1])
    if not np.isfinite(correlation_unweighted):
        raise strict.WeightValidationError("unweighted LayerID 0/1 correlation is nonfinite")
    correlation_weighted = strict.weighted_correlation(
        energy_by_layer[0], energy_by_layer[1], weight_array
    )
    return {
        "n_events": int(first_b.size),
        "weight_validation": strict.summarize_weights(
            weight_array, expected_length=first_b.size
        ),
        "first_B_layer_mean": strict.direction_explicit_comparison(
            mean_unweighted, mean_weighted, unit="MeV"
        ),
        "first_B_layer_median": strict.direction_explicit_comparison(
            median_unweighted, median_weighted, unit="MeV"
        ),
        "deuteron_fraction_entering_B": strict.fraction_comparison(
            deuteron_unweighted, deuteron_weighted
        ),
        "deltaE_E_corr_layer0_vs_layer1": {
            "unweighted_legacy": correlation_unweighted,
            "weighted": correlation_weighted,
            "weighted_minus_unweighted": correlation_weighted - correlation_unweighted,
        },
        "comparison_policy": (
            "Every signed change names its direction. Relative changes name their denominator; "
            "a zero denominator is represented by null, never by an epsilon substitution."
        ),
        "species_definition": (
            "Entering-B species is the first charged Sci_bar hit at B-arm LayerID 0. "
            "This is a simulation label and not an empirical detector species tag."
        ),
    }


def plot_880_strict(
    energy_by_layer: dict[int, np.ndarray],
    weights: np.ndarray,
    output_directory: Path,
    study: dict[str, Any],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    first_b = energy_by_layer[0]
    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    bins = np.linspace(0, 80, 60)
    unweighted_density, _ = np.histogram(first_b, bins=bins, density=True)
    weighted_density, _ = np.histogram(first_b, bins=bins, weights=weights, density=True)
    centers = 0.5 * (bins[:-1] + bins[1:])
    axes[0].step(centers, unweighted_density, where="mid", color="k", lw=2, label="unweighted")
    axes[0].step(
        centers,
        weighted_density,
        where="mid",
        color="C3",
        lw=2,
        label="PrimaryWeighted",
    )
    comparison = study["first_B_layer_mean"]
    axes[0].set_xlabel("first B-layer (LayerID 0) EDep [MeV]")
    axes[0].set_ylabel("normalised density")
    axes[0].set_title(
        "First-B-layer EDep\n"
        f"weighted−unweighted = {comparison['weighted_minus_unweighted']:+.3f} MeV "
        f"({comparison['weighted_minus_unweighted_pct_of_abs_unweighted']:+.1f}% of |unweighted|)"
    )
    axes[0].legend()
    axes[1].hist(weights, bins=60, color="#4c72b0", alpha=0.85)
    axes[1].axvline(1.0, color="k", ls="--", label="weight=1")
    axes[1].axvline(float(np.mean(weights)), color="C3", label=f"mean={np.mean(weights):.2f}")
    weight_summary = study["weight_validation"]
    axes[1].set_xlabel("PrimaryWeight (exactly one per event)")
    axes[1].set_ylabel("events")
    axes[1].set_title(
        f"Strict weight vector — ESS={weight_summary['ess']:.0f} "
        f"({100.0 * weight_summary['ess_fraction']:.1f}% of nominal)"
    )
    axes[1].legend()
    figure.suptitle(
        "#880 — direction-explicit weighted versus unweighted diagnostic",
        fontweight="bold",
    )
    figure.tight_layout()
    for extension in ("png", "pdf"):
        figure.savefig(output_directory / f"fig_880_weighted_vs_unweighted.{extension}", dpi=160)
    plt.close(figure)


def _git_provenance(repo_root: Path) -> dict[str, Any]:
    def run(*arguments: str) -> str:
        process = subprocess.run(
            ["git", *arguments],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return process.stdout.strip()

    commit = run("rev-parse", "HEAD")
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise strict.WeightValidationError(f"invalid git commit identity: {commit!r}")
    dirty = run("status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise strict.WeightValidationError(
            "tracked working tree is dirty; commit or restore changes before a scientific rerun"
        )
    return {
        "commit": commit,
        "tracked_worktree_clean": True,
        "describe": run("describe", "--always", "--dirty", "--tags"),
    }


def _ensure_output_contract(output_directory: Path, *, overwrite: bool) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    existing = [name for name in EXPECTED_OUTPUT_NAMES if (output_directory / name).exists()]
    if existing and not overwrite:
        raise strict.WeightValidationError(
            "refusing to overwrite existing study artifacts without --overwrite: "
            + ", ".join(existing)
        )


def _artifact_provenance(output_directory: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for name in EXPECTED_OUTPUT_NAMES:
        if name.endswith("result.json"):
            continue
        path = output_directory / name
        if not path.is_file():
            raise strict.WeightValidationError(f"expected plot artifact was not produced: {path}")
        artifacts.append(strict.file_sha256(path))
    return artifacts


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.environ.get("CCB_MC_ROOT", legacy.DEFAULT_ROOT))
    parser.add_argument("--tree", default="hibeam")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--entry-stop", type=int, default=0, help="0 = all events")
    parser.add_argument(
        "--mev-to-adc",
        type=float,
        default=legacy._env_float(legacy.ENV_MEV_TO_ADC, legacy.DEFAULT_MEV_TO_ADC),
    )
    parser.add_argument(
        "--cuts",
        default=os.environ.get("CCB_AMPLITUDE_CUTS", legacy.DEFAULT_AMPLITUDE_CUTS),
        help="Comma-separated amplitude cuts [ADC] (default 500,1000,1500).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace a complete prior artifact set after all strict input checks pass.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        _install_strict_estimators()
        repo_root = SCRIPT_DIR.parents[1]
        git = _git_provenance(repo_root)
        root_path = Path(args.root).expanduser().resolve(strict=True)
        output_directory = args.out.expanduser().resolve()
        _ensure_output_contract(output_directory, overwrite=args.overwrite)
        cuts = [float(value) for value in str(args.cuts).split(",") if value.strip()]
        if not cuts or not np.all(np.isfinite(cuts)) or np.any(np.asarray(cuts) < 0.0):
            raise strict.WeightValidationError("amplitude cuts must be finite and nonnegative")
        if not np.isfinite(args.mev_to_adc) or args.mev_to_adc <= 0.0:
            raise strict.WeightValidationError("MeV-to-ADC scale must be finite and positive")
        entry_stop = args.entry_stop if args.entry_stop > 0 else None
        loaded = load_mc_strict(root_path, args.tree, entry_stop)
        (
            energy_by_layer,
            weights,
            _primary_pdg,
            entering_pdg,
            entering_charged,
            _total_b_energy,
            event_count,
            root_provenance,
        ) = loaded
        study_879 = legacy.study_879(energy_by_layer, weights, entering_pdg)
        study_880 = study_880_strict(
            energy_by_layer, weights, entering_pdg, entering_charged
        )
        study_887 = legacy.study_887(
            energy_by_layer,
            weights,
            entering_pdg,
            entering_charged,
            args.mev_to_adc,
            cuts,
        )
        legacy.plot_879(energy_by_layer, weights, output_directory, study_879)
        plot_880_strict(energy_by_layer, weights, output_directory, study_880)
        legacy.plot_887(
            energy_by_layer,
            weights,
            entering_pdg,
            entering_charged,
            args.mev_to_adc,
            cuts,
            output_directory,
            study_887,
        )
        command_argv = [sys.executable, str(Path(__file__).resolve()), *(argv or sys.argv[1:])]
        result = {
            "study": "issues879_880_887_mc_analysis_strict",
            "status": "DIAGNOSTIC_NOT_DATA_MC_CLOSURE",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "producer": {
                "policy": PRODUCER_POLICY,
                "version": PRODUCER_VERSION,
                "git": git,
                "command_argv": command_argv,
                "command_shell_escaped": shlex.join(command_argv),
                "python": sys.version,
                "platform": platform.platform(),
                "numpy_version": np.__version__,
                "strict_weight_module": strict.file_sha256(STRICT_PATH),
                "strict_wrapper": strict.file_sha256(Path(__file__)),
                "historical_producer": strict.file_sha256(LEGACY_PATH),
            },
            "root_input": root_provenance,
            "n_events": int(event_count),
            "primary_weight": study_880["weight_validation"],
            "issue_879_readout_pattern": study_879,
            "issue_880_weight_audit": study_880,
            "issue_887_amplitude_cut_scan": study_887,
            "plot_artifacts": _artifact_provenance(output_directory),
            "scientific_boundary": (
                "Simulation-only weighted diagnostic. It does not establish detector calibration, "
                "real-data species identification, uncertainty coverage, or data/MC closure."
            ),
        }
        result_path = output_directory / "issues879_880_887_result.json"
        result_file = strict.atomic_write_json(
            result_path,
            result,
            protected_paths=[root_path, LEGACY_PATH, STRICT_PATH, Path(__file__)],
        )
        print(
            json.dumps(
                {
                    "status": "OK",
                    "n_events": event_count,
                    "root_sha256": root_provenance["sha256"],
                    "result": result_file,
                    "weight_policy": strict.POLICY,
                    "first_B_weighted_minus_unweighted_pct": study_880[
                        "first_B_layer_mean"
                    ]["weighted_minus_unweighted_pct_of_abs_unweighted"],
                    "first_B_legacy_overstatement_pct": study_880[
                        "first_B_layer_mean"
                    ]["legacy_overstatement_pct_of_abs_weighted"],
                },
                indent=2,
                allow_nan=False,
            )
        )
        return 0
    except (OSError, RuntimeError, ValueError, strict.WeightValidationError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
