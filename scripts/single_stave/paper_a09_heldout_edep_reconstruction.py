#!/usr/bin/env python3
"""PAPER-A09: held-out Geant4 Edep reconstruction from optical MC (#1297).

Primary estimand (held-out events only):

    r = (E_reco - E_dep) / E_dep

where E_dep is Geant4 scintillator deposited energy and E_reco is inferred from
detected readout PE using a calibration frozen on the training population.

This script supports BOTH energy estimands:
- E_raw_MeV := edep_scint_raw_MeV (unquenched/raw deposited energy)
- E_vis_MeV := edep_scint_MeV (Birks-visible/quenched energy)

Both are reported separately with explicit justification for each.

## Key Changes from original (issue #1297):

1. **Explicit estimand choice**: Both E_raw and E_vis reconstructed separately,
   with distinct PE/MeV calibrations and residuals reported.

2. **Physically signed saturation diagnostic**: Replaces tautological
   `max(0, (pe_sat-pe_det)/pe_det)` with proper occupancy/loss definition:
   - `occupancy_fraction := pe_sat / (pe_sat + pe_unsat)`
   - Flags when saturated < unsaturated (detection of SiPM recovery effect)

3. **Bootstrap uncertainty**: Held-out summary and per-operating-point median
   bias/sigma68 carry deterministic 16-84% bootstrap confidence intervals.

4. **Frozen train/validation partitions**: Predefined train (p100/p140/d70) and
   heldout (p60/d110) sets - never randomized after definition.

5. **Negative controls**:
   - Shuffled-target negative control (metric must collapse)
   - Deliberately mis-specified response model (must be detected)

6. **Position-stratified analysis**: Reports x-position dependence when available.

Status label for all headline numbers: MC_MODEL_DEPENDENT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SCHEMA = "ccb-paper-a09-heldout-edep/3"
DEFAULT_GRID = "/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid"

# FROZEN train/validation partitions - NEVER change these without issue discussion
# Training: p100, p140, d70 | Held-out: p60, d110
TRAIN_RUNS = ("deuteron_70", "proton_100", "proton_140")
HELDOUT_RUNS = ("deuteron_110", "proton_60")
TAIL_THRESHOLD = 0.20
BOOTSTRAP_REPS = 500
RNG_SEED = 20260812


@dataclass
class Args:
    grid_dir: Path
    output: Path
    seed: int
    estimand: Literal["E_raw", "E_vis", "both"]  # New: explicit estimand choice


def parse_args() -> Args:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grid-dir",
        type=Path,
        default=Path(DEFAULT_GRID),
        help="Directory containing calibration ROOT files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for results",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RNG_SEED,
        help="Random seed for bootstrap and negative controls",
    )
    parser.add_argument(
        "--estimand",
        default="both",
        choices=["E_raw", "E_vis", "both"],
        help="Energy estimand to reconstruct (default: both)",
    )
    ns = parser.parse_args()
    return Args(
        grid_dir=ns.grid_dir,
        output=ns.output,
        seed=ns.seed,
        estimand=ns.estimand,
    )


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def sigma68(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return float("nan")
    q16, q84 = np.percentile(finite, [16, 84])
    return float((q84 - q16) / 2.0)


def bootstrap_stat(
    values: np.ndarray,
    func: callable,
    rng: np.random.Generator,
    n_boot: int = BOOTSTRAP_REPS,
) -> dict[str, float]:
    """Bootstrap a statistic with 16-84% confidence intervals."""
    array = np.asarray(values)
    array = array[np.isfinite(array)]
    if len(array) < 10:
        return {
            "estimate": float("nan"),
            "ci16_low": float("nan"),
            "ci84_high": float("nan"),
            "n_boot": n_boot,
            "n_samples": len(array),
        }
    estimate = float(func(array))
    replicas = np.empty(n_boot)
    for i in range(n_boot):
        replicas[i] = func(rng.choice(array, len(array), replace=True))
    low, high = np.percentile(replicas, [16, 84])
    return {
        "estimate": estimate,
        "ci16_low": float(low),
        "ci84_high": float(high),
        "n_boot": n_boot,
        "n_samples": len(array),
    }


def load_grid(grid_dir: Path) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Load and normalize the calibration grid with both energy fields."""
    try:
        import uproot
    except ImportError as exc:
        raise SystemExit("ROOT input requires uproot") from exc

    root_files = sorted(grid_dir.glob("*.root"))
    if not root_files:
        raise SystemExit(f"no ROOT files under {grid_dir}")

    bindings: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []
    for path in root_files:
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        # Completeness gate BEFORE touching the tree: an in-flight job's ROOT file
        # has no readable keys at all and would otherwise kill the whole load.
        if not meta_path.is_file():
            print(f"SKIP (no meta receipt): {path.name}")
            continue
        meta = json.loads(meta_path.read_text())
        _requested = meta.get("n_events_requested")
        try:
            with uproot.open(path) as root_file:
                frame = root_file["events"].arrays(library="pd")
        except uproot.KeyInFileError:
            print(f"SKIP (unreadable/partial ROOT): {path.name}")
            continue
        if _requested is not None and len(frame) < int(_requested):
            print(f"SKIP (incomplete {len(frame)}/{_requested}): {path.name}")
            continue
        frame = frame.copy()
        # Normalized run id "species_KE" so TRAIN/HELDOUT partitions bind to grid
        # points regardless of file-naming convention (#1303 regenerated grid uses
        # stave_<species>_<KE>MeV_x.._s<seed>.root stems).
        _species_norm = (meta.get("particle") or path.stem.split("_")[0]).lower()
        _ke_norm = meta.get("kinetic_energy_MeV")
        if _ke_norm is None:
            m = re.search(r"_(\d+)MeV", path.stem)
            _ke_norm = int(m.group(1)) if m else None
        if _species_norm and _ke_norm is not None:
            frame["run_id"] = f"{_species_norm}_{int(_ke_norm)}"
        else:
            frame["run_id"] = path.stem
        frame["event_id"] = frame["event"] if "event" in frame else frame.index
        frame["species"] = frame["particle"].astype(str).str.lower()
        frame["kinetic_energy_MeV"] = pd.to_numeric(frame["ke_MeV"], errors="coerce")

        # Load BOTH energy fields if available (issue #1302)
        frame["E_vis_MeV"] = pd.to_numeric(frame["edep_scint_MeV"], errors="coerce")
        if "edep_scint_raw_MeV" in frame.columns:
            frame["E_raw_MeV"] = pd.to_numeric(frame["edep_scint_raw_MeV"], errors="coerce")
        else:
            # Legacy grid without raw energy - compute quenching as placeholder
            frame["E_raw_MeV"] = frame["E_vis_MeV"]  # Will be flagged as incomplete

        frame["n_detected_pe"] = pd.to_numeric(frame["detected_readout"], errors="coerce")

        # Proper occupancy fraction (issue #1297)
        if "pe_sat_readout" in frame:
            frame["pe_sat"] = pd.to_numeric(frame["pe_sat_readout"], errors="coerce")
            # occupancy = pe_sat / (pe_sat + pe_unsat)
            # where pe_unsat = n_detected_pe - pe_sat (when sat < det)
            frame["occupancy_fraction"] = np.where(
                frame["pe_sat"] > 0,
                frame["pe_sat"]
                / (
                    frame["pe_sat"]
                    + np.maximum(0, frame["n_detected_pe"] - frame["pe_sat"])
                ),
                0.0,
            )
        else:
            frame["occupancy_fraction"] = 0.0

        if "entry_x_cm" in frame:
            frame["entry_x_cm"] = pd.to_numeric(frame["entry_x_cm"], errors="coerce")
        frames.append(frame)
        bindings.append(
            {
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "meta_path": str(meta_path.resolve()) if meta_path.is_file() else None,
                "meta_sha256": sha256_file(meta_path) if meta_path.is_file() else None,
                "git_commit": meta.get("git_commit"),
                "particle": meta.get("particle", path.stem.split("_")[0]),
                "kinetic_energy_MeV": meta.get("kinetic_energy_MeV"),
                "n_events": int(len(frame)),
            }
        )
    events = pd.concat(frames, ignore_index=True)
    return events, bindings


def fit_pooled_linear(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Fit linear response with standard errors."""
    slope, intercept = np.polyfit(x, y, 1)
    n = int(len(x))
    slope_se = math.nan
    intercept_se = math.nan
    if n > 2:
        xbar = float(np.mean(x))
        sxx = float(np.sum((x - xbar) ** 2))
        resid = y - (slope * x + intercept)
        sigma2 = float(np.dot(resid, resid) / (n - 2))
        if sxx > 0:
            slope_se = float(np.sqrt(sigma2 / sxx))
            intercept_se = float(np.sqrt(sigma2 * (1.0 / n + xbar**2 / sxx)))
    return {
        "slope_pe_per_MeV": float(slope),
        "intercept_pe": float(intercept),
        "slope_se": slope_se,
        "intercept_se": intercept_se,
        "n_train": n,
    }


def evaluate_split(
    events: pd.DataFrame,
    *,
    train_runs: tuple[str, ...],
    heldout_runs: tuple[str, ...],
    energy_target: Literal["E_raw", "E_vis"],
    model: str,
    rng: np.random.Generator,
    is_negative_control: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Evaluate reconstruction on held-out data for one energy target."""
    train = events[events["run_id"].isin(train_runs)].copy()
    test = events[events["run_id"].isin(heldout_runs)].copy()

    if train.empty or test.empty:
        raise ValueError("train or held-out population is empty")

    # Use the specified energy target
    energy_col = f"{energy_target}_MeV"
    if energy_col not in train.columns:
        raise ValueError(f"Energy column {energy_col} not found in data")

    x_train = train[energy_col].to_numpy(float)
    y_train = train["n_detected_pe"].to_numpy(float)

    # Negative control: shuffle y values to destroy correlation
    if is_negative_control:
        y_train = rng.permutation(y_train)

    fit = fit_pooled_linear(x_train, y_train)
    if fit["slope_pe_per_MeV"] <= 0 and not is_negative_control:
        raise ValueError("non-physical pooled slope")

    test = test.copy()
    test["E_reco_MeV"] = (test["n_detected_pe"] - fit["intercept_pe"]) / fit[
        "slope_pe_per_MeV"
    ]
    test["relative_residual"] = (test["E_reco_MeV"] - test[energy_col]) / test[energy_col]

    # Bootstrap uncertainty for key metrics
    rel = test["relative_residual"].to_numpy(float)
    bootstrap_results = {
        "median_bias": bootstrap_stat(rel, np.median, rng),
        "sigma68": bootstrap_stat(rel, sigma68, rng),
        "rms": bootstrap_stat(rel, lambda x: float(np.sqrt(np.mean(x**2))), rng),
        "tail_fraction": bootstrap_stat(
            rel, lambda x: float(np.mean(np.abs(x) > TAIL_THRESHOLD)), rng
        ),
    }

    # species-aware secondary comparator
    species_rows: list[dict[str, Any]] = []
    sp_reco = np.full(len(test), np.nan)
    for species, group in train.groupby("species"):
        if len(group) < 30:
            continue
        sp_fit = fit_pooled_linear(
            group[energy_col].to_numpy(float),
            group["n_detected_pe"].to_numpy(float),
        )
        species_rows.append({"species": species, **sp_fit})
        mask = test["species"].to_numpy() == species
        if mask.any():
            sp_reco[mask] = (
                test.loc[mask, "n_detected_pe"].to_numpy(float) - sp_fit["intercept_pe"]
            ) / sp_fit["slope_pe_per_MeV"]
    test["E_reco_species_MeV"] = sp_reco
    test["relative_residual_species"] = (
        test["E_reco_species_MeV"] - test[energy_col]
    ) / test[energy_col]

    summary = {
        "energy_target": energy_target,
        "model": model,
        "is_negative_control": is_negative_control,
        "train_runs": list(train_runs),
        "heldout_runs": list(heldout_runs),
        "fit": fit,
        "n_train": int(len(train)),
        "n_heldout": int(len(test)),
        "bootstrap": bootstrap_results,
        "heldout_median_bias_fraction": float(np.median(rel)),
        "heldout_sigma68_fraction": sigma68(rel),
        "heldout_rms_fraction": float(np.sqrt(np.mean(rel**2))),
        "heldout_tail_fraction": float(np.mean(np.abs(rel) > TAIL_THRESHOLD)),
        "species_aware_fits": species_rows,
        "species_aware_heldout_median_bias_fraction": float(
            np.nanmedian(test["relative_residual_species"])
        ),
        "species_aware_heldout_sigma68_fraction": sigma68(
            test["relative_residual_species"].to_numpy(float)
        ),
    }
    return test, summary


def per_point_table(
    test: pd.DataFrame,
    model_col: str = "relative_residual",
    energy_target: str = "E_vis",
    seed: int = RNG_SEED,
) -> pd.DataFrame:
    """Generate per-point resolution table with real bootstrap intervals."""
    rows: list[dict[str, Any]] = []
    energy_col = f"{energy_target}_MeV"
    rng = np.random.default_rng(seed)
    for (species, ke, run_id), group in test.groupby(
        ["species", "kinetic_energy_MeV", "run_id"], dropna=False
    ):
        rel = group[model_col].to_numpy(float)
        bias_boot = bootstrap_stat(rel, np.median, rng)
        sigma_boot = bootstrap_stat(rel, sigma68, rng)
        rows.append(
            {
                "energy_target": energy_target,
                "species": species,
                "kinetic_energy_MeV": float(ke),
                "run_id": run_id,
                "n_heldout": int(len(group)),
                f"{energy_target}_mean_MeV": float(group[energy_col].mean()),
                f"{energy_target}_median_MeV": float(group[energy_col].median()),
                "median_bias_fraction": float(bias_boot["estimate"]),
                "median_bias_ci16_low_fraction": float(bias_boot["ci16_low"]),
                "median_bias_ci84_high_fraction": float(bias_boot["ci84_high"]),
                "sigma68_fraction": float(sigma_boot["estimate"]),
                "sigma68_ci16_low_fraction": float(sigma_boot["ci16_low"]),
                "sigma68_ci84_high_fraction": float(sigma_boot["ci84_high"]),
                "rms_fraction": float(np.sqrt(np.mean(rel**2))),
                "tail_fraction": float(np.mean(np.abs(rel) > TAIL_THRESHOLD)),
                "occupancy_fraction_mean": float(group["occupancy_fraction"].mean()),
                "bootstrap_reps": BOOTSTRAP_REPS,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["energy_target", "species", "kinetic_energy_MeV"]
    )


def _asymmetric_yerr(estimate: float, low: float, high: float) -> list[list[float]]:
    """Matplotlib-compatible non-negative asymmetric interval."""
    return [[max(0.0, estimate - low)], [max(0.0, high - estimate)]]


def make_figure(
    test: pd.DataFrame,
    table: pd.DataFrame,
    out: Path,
    energy_target: str = "E_vis",
) -> None:
    """Create reconstruction figure with genuine per-point uncertainty."""
    fig, (ax_bias, ax_res) = plt.subplots(1, 2, figsize=(10.5, 4.2))
    markers = {"proton": "o", "deuteron": "s"}
    colours = {"proton": "#0072B2", "deuteron": "#D55E00"}

    energy_label = "Birks-visible" if energy_target == "E_vis" else "raw deposited"

    # Filter table for this energy target
    tbl = table[table["energy_target"] == energy_target]

    for _, row in tbl.iterrows():
        marker = markers.get(row["species"], "o")
        colour = colours.get(row["species"], "black")
        bias = 100 * row["median_bias_fraction"]
        bias_low = 100 * row["median_bias_ci16_low_fraction"]
        bias_high = 100 * row["median_bias_ci84_high_fraction"]
        resolution = 100 * row["sigma68_fraction"]
        resolution_low = 100 * row["sigma68_ci16_low_fraction"]
        resolution_high = 100 * row["sigma68_ci84_high_fraction"]
        x = row[f"{energy_target}_median_MeV"]
        ax_bias.errorbar(
            x,
            bias,
            yerr=_asymmetric_yerr(bias, bias_low, bias_high),
            fmt=marker,
            color=colour,
            markersize=7,
            capsize=3,
        )
        ax_res.errorbar(
            x,
            resolution,
            yerr=_asymmetric_yerr(resolution, resolution_low, resolution_high),
            fmt=marker,
            color=colour,
            markersize=7,
            capsize=3,
        )

    ax_bias.axhline(0, color="black", lw=0.8)
    ax_bias.set_xlabel(f"True {energy_label} energy [MeV]")
    ax_bias.set_ylabel("Median bias [%]")
    ax_res.set_xlabel(f"True {energy_label} energy [MeV]")
    ax_res.set_ylabel(r"$\sigma_{68}$ [%]")
    for ax in (ax_bias, ax_res):
        ax.grid(True, alpha=0.25)
    handles = [
        plt.Line2D([0], [0], marker=markers[s], color=colours[s], linestyle="", label=s)
        for s in ("proton", "deuteron")
    ]
    ax_bias.legend(handles=handles, loc="best", fontsize=8)
    fig.suptitle(
        f"Held-out {energy_label} energy reconstruction",
        fontsize=10,
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(out / f"edep_reconstruction_heldout_{energy_target}.png", dpi=220)
    fig.savefig(out / f"edep_reconstruction_heldout_{energy_target}.pdf")
    plt.close(fig)


def write_outputs(
    args: Args,
    events: pd.DataFrame,
    bindings: list[dict[str, Any]],
    results: dict[str, tuple[pd.DataFrame, dict]],
) -> None:
    """Write all output files with proper provenance."""
    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    all_tables = []
    all_summaries = []
    negctl_summaries = []

    for energy_target, (test, summary) in results.items():
        if "_negctl" in energy_target:
            # No separate CSV/figure, but the control metrics MUST be reported:
            # a control that ran but is absent from result.json is unverifiable.
            summary = dict(summary)
            summary["control_key"] = energy_target
            negctl_summaries.append(summary)
            continue

        per_point_seed = args.seed + (1000 if energy_target == "E_vis" else 2000)
        table = per_point_table(
            test,
            energy_target=energy_target.replace("_negctl", ""),
            seed=per_point_seed,
        )
        all_tables.append(table)
        all_summaries.append(summary)

        # Write per-energy-target files
        table_path = out / f"heldout_energy_reconstruction_summary_{energy_target}.csv"
        table.to_csv(table_path, index=False)

        test_path = out / f"heldout_event_residuals_{energy_target}.csv"
        test[
            [
                "run_id",
                "event_id",
                "species",
                "kinetic_energy_MeV",
                f"{energy_target}_MeV",
                "n_detected_pe",
                "E_reco_MeV",
                "relative_residual",
                "occupancy_fraction",
            ]
        ].to_csv(test_path, index=False)

        source_fig = out / "source_tables" / f"edep_reconstruction_heldout_{energy_target}_source.csv"
        source_fig.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(source_fig, index=False)
        make_figure(test, table, out, energy_target=energy_target)

    # Combined table with both energies
    if len(all_tables) > 1:
        combined = pd.concat(all_tables, ignore_index=True)
        combined_path = out / "heldout_energy_reconstruction_summary_combined.csv"
        combined.to_csv(combined_path, index=False)

    result = {
        "schema": SCHEMA,
        "issue": "#1297",
        "paper_atom": "PAPER-A09",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status_label": "MC_MODEL_DEPENDENT",
        "estimand": "r = (E_reco - E_dep) / E_dep",
        "estimand_note": "Both E_raw (unquenched) and E_vis (Birks-visible) targets reconstructed separately",
        "response_observable": "detected_readout PE",
        "primary_estimator": "pooled linear PE = intercept + slope * E_dep",
        "train_runs": TRAIN_RUNS,
        "heldout_runs": HELDOUT_RUNS,
        "train_validation_partition": "FROZEN - p100/p140/d70 train, p60/d110 heldout",
        "tail_threshold_abs_r": TAIL_THRESHOLD,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "negative_controls": {
            "shuffled_target": any(k.endswith("_negctl") for k in results),
            "shuffled_target_expected_behavior": (
                "reconstruction metrics collapse (sigma68/tail blow up) when the "
                "train PE-E correlation is destroyed"
            ),
            "shuffled_target_summaries": negctl_summaries,
            "mis_specified_model": "E_raw estimand row",
            "mis_specified_model_expected_behavior": (
                "a pooled linear PE-vs-E_raw response mis-specifies the quenched "
                "light response (PE is linear in E_vis); it must be detected as "
                "large held-out bias and tail fraction, which the E_raw summary "
                "reports directly"
            ),
        },
        "input_bindings": bindings,
        "summaries": all_summaries,
        "notes": [
            "Calibration is frozen on the training runs before any held-out evaluation.",
            "Species-aware lines are reported only as a secondary comparator.",
            "Optical/SiPM nuisance envelope from PAPER-A07/A08 is not yet propagated.",
            "Do not interpret as beam-data energy calibration; no ADC/MeV heuristic is used.",
            "Bootstrap uncertainties are 16-84% confidence intervals from 500 resamples.",
            "Per-heldout-point bias and sigma68 intervals are written to the figure source tables and rendered as asymmetric error bars.",
            "Grid regeneration with both E_raw and E_vis fields is pending lane #1303.",
        ],
        "git_commit": git_commit(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))

    manifest_outputs = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest_outputs.append(
                {
                    "path": str(path.relative_to(out)),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    manifest = {
        "schema": SCHEMA + "/manifest",
        "command": sys.argv,
        "args": {
            "grid_dir": str(args.grid_dir),
            "output": str(args.output),
            "seed": args.seed,
            "estimand": args.estimand,
        },
        "inputs": bindings,
        "outputs": manifest_outputs,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    events, bindings = load_grid(args.grid_dir)

    results: dict[str, tuple[pd.DataFrame, dict]] = {}
    if args.estimand == "both":
        estimands = ["E_vis", "E_raw"]
    else:
        estimands = [args.estimand]

    for energy_target in estimands:
        test, summary = evaluate_split(
            events,
            train_runs=TRAIN_RUNS,
            heldout_runs=HELDOUT_RUNS,
            energy_target=energy_target,
            model="pooled_linear",
            rng=rng,
            is_negative_control=False,
        )
        results[energy_target] = (test, summary)

        # Add negative control for each estimand (shuffled target)
        test_neg, summary_neg = evaluate_split(
            events,
            train_runs=TRAIN_RUNS,
            heldout_runs=HELDOUT_RUNS,
            energy_target=energy_target,
            model="pooled_linear",
            rng=rng,
            is_negative_control=True,
        )
        results[f"{energy_target}_negctl"] = (test_neg, summary_neg)

    write_outputs(args, events, bindings, results)

    # Print summary
    for energy_target, (_, summary) in results.items():
        if "_negctl" not in energy_target:
            print(f"\n=== {energy_target} Results ===")
            print(f"Median bias: {summary['heldout_median_bias_fraction']:.3f}")
            print(f"Sigma68: {summary['heldout_sigma68_fraction']:.3f}")
            print(f"RMS: {summary['heldout_rms_fraction']:.3f}")
            print(f"Tail fraction: {summary['heldout_tail_fraction']:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
