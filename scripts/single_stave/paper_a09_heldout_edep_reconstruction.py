#!/usr/bin/env python3
"""PAPER-A09: held-out Geant4 Edep reconstruction from optical MC (#1297).

Primary estimand (held-out events only):

    r = (E_reco - E_dep) / E_dep

where E_dep is Geant4 scintillator deposited energy (edep_scint_MeV) and E_reco
is inferred from detected readout PE using a calibration frozen on the training
population. Proton and deuteron share one pooled linear response unless a
species-aware model is explicitly compared as a secondary baseline.

Status label for all headline numbers: MC_MODEL_DEPENDENT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SCHEMA = "ccb-paper-a09-heldout-edep/1"
DEFAULT_GRID = "/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid"
TRAIN_RUNS = ("deuteron_70", "proton_100", "proton_140")
HELDOUT_RUNS = ("deuteron_110", "proton_60")
TAIL_THRESHOLD = 0.20


@dataclass
class Args:
    grid_dir: Path
    output: Path
    seed: int


def parse_args() -> Args:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid-dir", type=Path, default=Path(DEFAULT_GRID))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260812)
    ns = parser.parse_args()
    return Args(grid_dir=ns.grid_dir, output=ns.output, seed=ns.seed)


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


def load_grid(grid_dir: Path) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
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
        meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        with uproot.open(path) as root_file:
            frame = root_file["events"].arrays(library="pd")
        frame = frame.copy()
        frame["run_id"] = path.stem
        frame["event_id"] = frame["event"] if "event" in frame else frame.index
        frame["species"] = frame["particle"].astype(str).str.lower()
        frame["kinetic_energy_MeV"] = pd.to_numeric(frame["ke_MeV"], errors="coerce")
        frame["edep_scint_MeV"] = pd.to_numeric(frame["edep_scint_MeV"], errors="coerce")
        frame["n_detected_pe"] = pd.to_numeric(frame["detected_readout"], errors="coerce")
        if "pe_sat_readout" in frame:
            frame["n_saturated_pe"] = pd.to_numeric(frame["pe_sat_readout"], errors="coerce")
            frame["saturation_fraction"] = np.maximum(
                0.0,
                (frame["n_saturated_pe"] - frame["n_detected_pe"])
                / np.maximum(frame["n_detected_pe"], 1e-9),
            )
        else:
            frame["saturation_fraction"] = 0.0
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
    model: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    train = events[events["run_id"].isin(train_runs)].copy()
    test = events[events["run_id"].isin(heldout_runs)].copy()
    if train.empty or test.empty:
        raise ValueError("train or held-out population is empty")

    x_train = train["edep_scint_MeV"].to_numpy(float)
    y_train = train["n_detected_pe"].to_numpy(float)
    fit = fit_pooled_linear(x_train, y_train)
    if fit["slope_pe_per_MeV"] <= 0:
        raise ValueError("non-physical pooled slope")

    test = test.copy()
    test["E_reco_MeV"] = (test["n_detected_pe"] - fit["intercept_pe"]) / fit["slope_pe_per_MeV"]
    test["relative_residual"] = (test["E_reco_MeV"] - test["edep_scint_MeV"]) / test["edep_scint_MeV"]

    # species-aware secondary comparator (fit per species on train only)
    species_rows: list[dict[str, Any]] = []
    sp_reco = np.full(len(test), np.nan)
    for species, group in train.groupby("species"):
        if len(group) < 30:
            continue
        sp_fit = fit_pooled_linear(
            group["edep_scint_MeV"].to_numpy(float),
            group["n_detected_pe"].to_numpy(float),
        )
        species_rows.append({"species": species, **sp_fit})
        mask = test["species"].to_numpy() == species
        if mask.any():
            sp_reco[mask] = (
                test.loc[mask, "n_detected_pe"].to_numpy(float) - sp_fit["intercept_pe"]
            ) / sp_fit["slope_pe_per_MeV"]
    test["E_reco_species_MeV"] = sp_reco
    test["relative_residual_species"] = (test["E_reco_species_MeV"] - test["edep_scint_MeV"]) / test[
        "edep_scint_MeV"
    ]

    rel = test["relative_residual"].to_numpy(float)
    summary = {
        "model": model,
        "train_runs": list(train_runs),
        "heldout_runs": list(heldout_runs),
        "fit": fit,
        "n_train": int(len(train)),
        "n_heldout": int(len(test)),
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


def per_point_table(test: pd.DataFrame, model_col: str = "relative_residual") -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (species, ke, run_id), group in test.groupby(
        ["species", "kinetic_energy_MeV", "run_id"], dropna=False
    ):
        rel = group[model_col].to_numpy(float)
        rows.append(
            {
                "species": species,
                "kinetic_energy_MeV": float(ke),
                "run_id": run_id,
                "n_heldout": int(len(group)),
                "edep_mean_MeV": float(group["edep_scint_MeV"].mean()),
                "edep_median_MeV": float(group["edep_scint_MeV"].median()),
                "median_bias_fraction": float(np.median(rel)),
                "sigma68_fraction": sigma68(rel),
                "rms_fraction": float(np.sqrt(np.mean(rel**2))),
                "tail_fraction": float(np.mean(np.abs(rel) > TAIL_THRESHOLD)),
                "saturation_fraction_mean": float(group["saturation_fraction"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["species", "kinetic_energy_MeV"])


def make_figure(test: pd.DataFrame, table: pd.DataFrame, out: Path) -> None:
    fig, (ax_bias, ax_res) = plt.subplots(1, 2, figsize=(10.5, 4.2))
    markers = {"proton": "o", "deuteron": "s"}
    colours = {"proton": "#0072B2", "deuteron": "#D55E00"}
    for _, row in table.iterrows():
        marker = markers.get(row["species"], "o")
        colour = colours.get(row["species"], "black")
        ax_bias.errorbar(
            row["edep_median_MeV"],
            100 * row["median_bias_fraction"],
            yerr=[[0], [0]],
            fmt=marker,
            color=colour,
            markersize=7,
            capsize=3,
        )
        ax_res.plot(
            row["edep_median_MeV"],
            100 * row["sigma68_fraction"],
            marker=marker,
            color=colour,
            markersize=7,
        )
    ax_bias.axhline(0, color="black", lw=0.8)
    ax_bias.set_xlabel(r"True $E_{\mathrm{dep}}$ [MeV]")
    ax_bias.set_ylabel("Median bias [%]")
    ax_res.set_xlabel(r"True $E_{\mathrm{dep}}$ [MeV]")
    ax_res.set_ylabel(r"$\sigma_{68}$ [%]")
    for ax in (ax_bias, ax_res):
        ax.grid(True, alpha=0.25)
    handles = [
        plt.Line2D([0], [0], marker=markers[s], color=colours[s], linestyle="", label=s)
        for s in ("proton", "deuteron")
    ]
    ax_bias.legend(handles=handles, loc="best", fontsize=8)
    fig.suptitle(
        "Held-out deposited-energy reconstruction (MODEL-DEPENDENT OPTICAL MC)",
        fontsize=10,
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(out / "edep_reconstruction_heldout.png", dpi=220)
    fig.savefig(out / "edep_reconstruction_heldout.pdf")
    plt.close(fig)


def write_outputs(
    args: Args,
    events: pd.DataFrame,
    bindings: list[dict[str, Any]],
    test: pd.DataFrame,
    summary: dict[str, Any],
    table: pd.DataFrame,
) -> None:
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    table_path = out / "heldout_energy_reconstruction_summary.csv"
    table.to_csv(table_path, index=False)
    test_path = out / "heldout_event_residuals.csv"
    test[
        [
            "run_id",
            "event_id",
            "species",
            "kinetic_energy_MeV",
            "edep_scint_MeV",
            "n_detected_pe",
            "E_reco_MeV",
            "relative_residual",
            "saturation_fraction",
        ]
    ].to_csv(test_path, index=False)

    source_fig = out / "source_tables" / "edep_reconstruction_heldout_source.csv"
    source_fig.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(source_fig, index=False)
    make_figure(test, table, out)

    result = {
        "schema": SCHEMA,
        "issue": "#1297",
        "paper_atom": "PAPER-A09",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status_label": "MC_MODEL_DEPENDENT",
        "estimand": "r = (E_reco - E_dep) / E_dep",
        "target_energy": "Geant4 scintillator deposited energy (edep_scint_MeV)",
        "response_observable": "detected_readout PE",
        "primary_estimator": "pooled linear PE = intercept + slope * E_dep",
        "train_runs": summary["train_runs"],
        "heldout_runs": summary["heldout_runs"],
        "tail_threshold_abs_r": TAIL_THRESHOLD,
        "input_bindings": bindings,
        "summary": summary,
        "per_point": table.to_dict(orient="records"),
        "notes": [
            "Calibration is frozen on the training runs before any held-out evaluation.",
            "Species-aware lines are reported only as a secondary comparator.",
            "Optical/SiPM nuisance envelope from PAPER-A07/A08 is not yet propagated.",
            "Do not interpret as beam-data energy calibration; no ADC/MeV heuristic is used.",
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
        },
        "inputs": bindings,
        "outputs": manifest_outputs,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    events, bindings = load_grid(args.grid_dir)
    test, summary = evaluate_split(
        events,
        train_runs=TRAIN_RUNS,
        heldout_runs=HELDOUT_RUNS,
        model="pooled_linear",
    )
    table = per_point_table(test)
    write_outputs(args, events, bindings, test, summary, table)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
