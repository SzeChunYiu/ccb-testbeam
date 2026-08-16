#!/usr/bin/env python3
"""Regenerate issue #885 calibration fits from seed-averaged energy points.

This post-processing tool consumes the committed per-configuration summary CSV. It
never treats repeated simulation seeds as independent calibration energies. A linear
fit is emitted only when a particle has at least three unique energies, leaving at
least one residual degree of freedom.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "i885-seed-averaged-v1"
matplotlib.rcParams["svg.fonttype"] = "none"
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2 as chi2_distribution

TOOL_VERSION = "1.0.0"
FIT_BASIS = "seed_averaged_unique_energy"
MIN_ENERGY_POINTS = 3
KEY_COLUMNS = ["particle", "energy_MeV", "hit_x_cm", "seed"]
METRICS = {
    "pe_sat_readout_vs_KE": ("pe_sat_readout_mean", "pe_sat_readout_sem", "SiPM photoelectrons"),
    "edep_scint_MeV_vs_KE": (
        "edep_scint_MeV_mean",
        "edep_scint_MeV_sem",
        "Birks-visible energy (MeV)",
    ),
}
REQUIRED_COLUMNS = set(KEY_COLUMNS) | {
    "n_events",
    *(column for pair in METRICS.values() for column in pair[:2]),
}
COLORS = {"proton": "#1f77b4", "deuteron": "#d62728"}
MARKERS = {"proton": "o", "deuteron": "s"}


class CampaignFitError(ValueError):
    """Raised when the per-configuration campaign table is unsafe to fit."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_provenance(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def read_observed(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise CampaignFitError("observed CSV missing required columns: " + ", ".join(missing))
    if frame.empty:
        raise CampaignFitError("observed CSV contains no configurations")

    frame = frame.copy()
    for column in ["energy_MeV", "hit_x_cm", "seed", "n_events"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for mean_column, sem_column, _ in METRICS.values():
        frame[mean_column] = pd.to_numeric(frame[mean_column], errors="coerce")
        frame[sem_column] = pd.to_numeric(frame[sem_column], errors="coerce")

    required_numeric = ["energy_MeV", "hit_x_cm", "seed", "n_events"] + [
        column for pair in METRICS.values() for column in pair[:2]
    ]
    finite = np.isfinite(frame[required_numeric].to_numpy(dtype=float)).all(axis=1)
    if not bool(finite.all()):
        bad_rows = [int(index) + 2 for index in frame.index[~finite]]
        raise CampaignFitError(f"nonnumeric or nonfinite required values in CSV rows {bad_rows}")
    if (frame["n_events"] <= 0).any():
        raise CampaignFitError("n_events must be positive for every configuration")
    if (frame[[pair[1] for pair in METRICS.values()]] < 0).any().any():
        raise CampaignFitError("reported standard errors must be nonnegative")

    duplicate = frame.duplicated(KEY_COLUMNS, keep=False)
    if duplicate.any():
        records = frame.loc[duplicate, KEY_COLUMNS].to_dict(orient="records")
        raise CampaignFitError(f"duplicate configuration keys: {records}")
    return frame


def infer_main_hit_x(frame: pd.DataFrame) -> float:
    counts = frame.groupby("hit_x_cm").size().sort_values(ascending=False)
    if len(counts) > 1 and counts.iloc[0] == counts.iloc[1]:
        raise CampaignFitError("cannot infer main-grid hit_x_cm because coverage is tied")
    return float(counts.index[0])


def combine_uncertainty(values: np.ndarray, within_sem: np.ndarray) -> tuple[float, float, float]:
    n_files = len(values)
    propagated_within = float(np.sqrt(np.sum(within_sem**2)) / n_files)
    between_seed = (
        float(np.std(values, ddof=1) / np.sqrt(n_files)) if n_files >= 2 else float("nan")
    )
    components = [propagated_within]
    if math.isfinite(between_seed):
        components.append(between_seed)
    combined = float(np.sqrt(np.sum(np.square(components))))
    return propagated_within, between_seed, combined


def seed_average(frame: pd.DataFrame, mean_column: str, sem_column: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for energy, group in frame.groupby("energy_MeV", sort=True):
        values = group[mean_column].to_numpy(dtype=float)
        within = group[sem_column].to_numpy(dtype=float)
        propagated, between, combined = combine_uncertainty(values, within)
        rows.append(
            {
                "energy_MeV": float(energy),
                "value": float(np.mean(values)),
                "uncertainty": combined,
                "within_file_sem": propagated,
                "between_seed_sem": between,
                "n_files": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def linear_fit(points: pd.DataFrame, *, n_files: int) -> dict[str, Any] | None:
    n_points = len(points)
    if n_points < MIN_ENERGY_POINTS:
        return None
    x = points["energy_MeV"].to_numpy(dtype=float)
    y = points["value"].to_numpy(dtype=float)
    sigma = points["uncertainty"].to_numpy(dtype=float)
    weighted = bool(np.isfinite(sigma).all() and (sigma > 0).all())

    design = np.column_stack([x, np.ones_like(x)])
    if weighted:
        weights = 1.0 / np.square(sigma)
        normal = design.T @ (weights[:, None] * design)
        covariance_base = np.linalg.inv(normal)
        coefficients = covariance_base @ (design.T @ (weights * y))
    else:
        coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
        covariance_base = np.linalg.inv(design.T @ design)

    slope, intercept = map(float, coefficients)
    predicted = design @ coefficients
    residuals = y - predicted
    residual_dof = n_points - 2
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt(np.mean(residuals**2)))
    max_abs_residual = float(np.max(np.abs(residuals)))

    if weighted:
        chi2 = float(np.sum(np.square(residuals / sigma)))
        reduced_chi2 = chi2 / residual_dof
        covariance = covariance_base * reduced_chi2
    else:
        chi2 = None
        reduced_chi2 = None
        residual_variance = ss_res / residual_dof
        covariance = covariance_base * residual_variance

    goodness_of_fit_p_value = (
        float(chi2_distribution.sf(chi2, residual_dof)) if weighted else None
    )
    fit_status = (
        "ACCEPTED"
        if weighted and goodness_of_fit_p_value >= 0.01
        else "LINEAR_MODEL_REJECTED" if weighted else "DIAGNOSTIC_ONLY_NO_UNCERTAINTY"
    )

    return {
        "slope": slope,
        "intercept": intercept,
        "slope_std": float(np.sqrt(covariance[0, 0])),
        "intercept_std": float(np.sqrt(covariance[1, 1])),
        "r2": r2,
        "rmse": rmse,
        "max_abs_residual": max_abs_residual,
        "chi2": chi2,
        "reduced_chi2": reduced_chi2,
        "goodness_of_fit_p_value": goodness_of_fit_p_value,
        "goodness_of_fit_p_value_underflow": goodness_of_fit_p_value == 0.0,
        "goodness_of_fit_assumptions": (
            "independent Gaussian seed-averaged uncertainties; no model/systematic term"
        ),
        "fit_status": fit_status,
        "accepted": fit_status == "ACCEPTED",
        "residual_dof": residual_dof,
        "n": n_points,
        "n_energy_points": n_points,
        "n_files": int(n_files),
        "energy_min_MeV": float(np.min(x)),
        "energy_max_MeV": float(np.max(x)),
        "fit_basis": FIT_BASIS,
        "weighted": weighted,
        "uncertainty_method": (
            "quadrature(propagated_within_file_sem, between_seed_sem)"
        ),
    }


def analyze(
    frame: pd.DataFrame, *, main_hit_x_cm: float | None = None
) -> tuple[dict[str, Any], pd.DataFrame]:
    hit_x = infer_main_hit_x(frame) if main_hit_x_cm is None else float(main_hit_x_cm)
    scan = frame[frame["hit_x_cm"] == hit_x].copy()
    if scan.empty:
        raise CampaignFitError(f"no configurations found at main hit_x_cm={hit_x}")

    fits: dict[str, dict[str, Any]] = {}
    rejected: dict[str, dict[str, Any]] = {}
    skipped: dict[str, dict[str, Any]] = {}
    point_frames: list[pd.DataFrame] = []
    particles = sorted(scan["particle"].astype(str).unique())
    for particle in particles:
        particle_rows = scan[scan["particle"] == particle]
        for metric_name, (mean_column, sem_column, _) in METRICS.items():
            points = seed_average(particle_rows, mean_column, sem_column)
            points.insert(0, "particle", particle)
            points.insert(1, "metric", metric_name)
            point_frames.append(points)
            fit_name = f"{metric_name}_{particle}"
            fit = linear_fit(points, n_files=len(particle_rows))
            if fit is None:
                skipped[fit_name] = {
                    "status": "SKIPPED_INSUFFICIENT_ENERGY_POINTS",
                    "n_files": int(len(particle_rows)),
                    "n_energy_points": int(len(points)),
                    "minimum_energy_points": MIN_ENERGY_POINTS,
                    "fit_basis": FIT_BASIS,
                }
            elif fit["accepted"]:
                fits[fit_name] = fit
            else:
                rejected[fit_name] = fit

    point_table = pd.concat(point_frames, ignore_index=True)
    result = {
        "tool": "scripts/single_stave/refit_i885_campaign.py",
        "tool_version": TOOL_VERSION,
        "status": "PARTIAL" if skipped or rejected else "VALIDATED",
        "main_hit_x_cm": hit_x,
        "n_configs": int(len(frame)),
        "n_main_grid_files": int(len(scan)),
        "n_events_total": int(frame["n_events"].sum()),
        "fit_basis": FIT_BASIS,
        "minimum_energy_points": MIN_ENERGY_POINTS,
        "fits": fits,
        "fit_rejections": rejected,
        "fit_skips": skipped,
    }
    return result, point_table


def plot_results(result: dict[str, Any], points: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
    for axis, (metric_name, (_, _, ylabel)) in zip(axes, METRICS.items(), strict=True):
        for particle in sorted(points["particle"].unique()):
            subset = points[(points["metric"] == metric_name) & (points["particle"] == particle)]
            color = COLORS.get(str(particle), None)
            marker = MARKERS.get(str(particle), "o")
            axis.errorbar(
                subset["energy_MeV"],
                subset["value"],
                yerr=subset["uncertainty"],
                marker=marker,
                linestyle="none",
                capsize=3,
                color=color,
                label=f"{particle}: seed-averaged points",
            )
            fit_name = f"{metric_name}_{particle}"
            fit = result["fits"].get(fit_name) or result["fit_rejections"].get(fit_name)
            if fit is not None:
                x = np.linspace(fit["energy_min_MeV"], fit["energy_max_MeV"], 100)
                axis.plot(
                    x,
                    fit["slope"] * x + fit["intercept"],
                    color=color,
                    label=(
                        f"{particle}: {fit['fit_status'].lower()}, "
                        f"{fit['n_energy_points']} energies, "
                        f"p={fit['goodness_of_fit_p_value']:.2g}"
                    ),
                )
            else:
                skip = result["fit_skips"][fit_name]
                axis.text(
                    0.03,
                    0.93 if particle == "proton" else 0.84,
                    (
                        f"{particle}: fit skipped "
                        f"({skip['n_energy_points']} < {MIN_ENERGY_POINTS} energies)"
                    ),
                    transform=axis.transAxes,
                    fontsize=8,
                )
        axis.set_xlabel("kinetic energy (MeV)")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.3)
        axis.legend(fontsize=7)
    axes[0].set_title("P5 corrected: SiPM response vs KE")
    axes[1].set_title("P5b corrected: Birks-visible response vs KE")
    fig.suptitle(
        "Issue #885 partial Geant4 campaign — seed-averaged independent energies\n"
        "Error bars combine propagated within-file SEM and between-seed SEM; not detector data",
        fontsize=10,
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        format="svg",
        metadata={"Date": None, "Creator": "refit_i885_campaign.py v1.0.0"},
    )
    plt.close(fig)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-svg", required=True, type=Path)
    parser.add_argument("--output-points", type=Path)
    parser.add_argument("--main-hit-x-cm", type=float)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        frame = read_observed(args.observed)
        result, points = analyze(frame, main_hit_x_cm=args.main_hit_x_cm)
        result["input"] = input_provenance(args.observed)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        plot_results(result, points, args.output_svg)
        if args.output_points:
            args.output_points.parent.mkdir(parents=True, exist_ok=True)
            points.to_csv(args.output_points, index=False)
    except (OSError, CampaignFitError, ValueError, np.linalg.LinAlgError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        "i885 refit: "
        f"status={result['status']} accepted={len(result['fits'])} "
        f"rejected={len(result['fit_rejections'])} "
        f"skipped={len(result['fit_skips'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
