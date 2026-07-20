#!/usr/bin/env python3
"""
Analyze event-level output from the repaired CCB single-stave simulation.

Supported input:
  - CSV
  - Parquet
  - ROOT flat ntuple (via uproot; --tree required or auto-selected)

The script validates the event schema, writes source-data tables, creates
publication diagnostics, fits a held-out linear PE energy calibration, and
writes result.json plus a provenance manifest.

This script does not invent missing optical fields. It fails with a clear
message when required columns are absent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

REQUIRED = {
    "event_id",
    "particle_pdg",
    "kinetic_energy_MeV",
    "edep_scint_MeV",
    "n_scint_generated",
    "n_end_selected",
    "n_detected_pe",
}

OPTIONAL_DEFAULTS = {
    "run_id": "run0",
    "entry_x_cm": np.nan,
    "entry_y_cm": np.nan,
    "entry_z_cm": np.nan,
    "incidence_angle_deg": 0.0,
    "track_length_scint_cm": np.nan,
    "first_photon_time_ns": np.nan,
    "median_photon_time_ns": np.nan,
    "photon_time_sigma68_ns": np.nan,
    "birks_kB_mm_per_MeV": np.nan,
    "geometry_hash": "",
    "optical_config_hash": "",
}

PDG_LABEL = {
    2212: "proton",
    1000010020: "deuteron",
}


@dataclass
class ArgsRecord:
    input: str
    output: str
    tree: str | None
    seed: int
    bins: int
    max_display_points: int


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Validate and plot repaired CCB single-stave MC output."
    )
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--tree", default=None, help="ROOT tree name")
    p.add_argument("--seed", type=int, default=20260720)
    p.add_argument("--bins", type=int, default=12)
    p.add_argument("--max-display-points", type=int, default=100_000)
    return p.parse_args()


def sha256(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def read_table(path: Path, tree: str | None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".csv", ".txt", ".dat"}:
        # CSV is the production recommendation. Whitespace fallback helps legacy output.
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.read_csv(path, sep=r"\s+", comment="#")
    if suffix == ".root":
        try:
            import uproot
        except ImportError as exc:
            raise SystemExit("ROOT input requires uproot") from exc
        f = uproot.open(path)
        if tree is None:
            candidates = [
                k.split(";")[0]
                for k, obj in f.items()
                if hasattr(obj, "arrays")
            ]
            if len(candidates) != 1:
                raise SystemExit(
                    f"Specify --tree. Candidate ROOT trees: {candidates}"
                )
            tree = candidates[0]
        return f[tree].arrays(library="pd")
    raise SystemExit(f"Unsupported input extension: {suffix}")


def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    # Legacy aliases can be mapped explicitly, never by fuzzy guessing.
    aliases = {
        "event": "event_id",
        "ke_MeV": "kinetic_energy_MeV",
        "edep_scint_MeV": "edep_scint_MeV",
        "photons_wls1": "n_end_selected",  # only for diagnostic legacy import
        "photons_seen": "n_end_selected",
        "pe": "n_detected_pe",
    }
    for old, new in aliases.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})

    if "particle_pdg" not in df.columns and "particle" in df.columns:
        mapping = {"proton": 2212, "deuteron": 1000010020}
        values = df["particle"].map(mapping)
        if values.isna().any():
            bad = sorted(df.loc[values.isna(), "particle"].astype(str).unique())
            raise SystemExit(f"Unknown legacy particle labels: {bad}")
        df["particle_pdg"] = values.astype(np.int64)

    missing = sorted(REQUIRED - set(df.columns))
    if missing:
        raise SystemExit(
            "Missing required event columns: "
            + ", ".join(missing)
            + "\nSee research/DETECTOR_PARAMETERS.md."
        )

    for col, default in OPTIONAL_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default

    numeric = [
        "event_id",
        "particle_pdg",
        "kinetic_energy_MeV",
        "edep_scint_MeV",
        "n_scint_generated",
        "n_end_selected",
        "n_detected_pe",
        "entry_x_cm",
        "entry_y_cm",
        "entry_z_cm",
        "incidence_angle_deg",
        "track_length_scint_cm",
        "first_photon_time_ns",
        "median_photon_time_ns",
        "photon_time_sigma68_ns",
        "birks_kB_mm_per_MeV",
    ]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if df[list(REQUIRED)].isna().any().any():
        bad = df[list(REQUIRED)].isna().sum()
        raise SystemExit(f"NaNs in required columns:\n{bad[bad > 0]}")

    df["species"] = (
        df["particle_pdg"].astype(int).map(PDG_LABEL).fillna(
            "pdg_" + df["particle_pdg"].astype(int).astype(str)
        )
    )
    return df


def validate_physics(df: pd.DataFrame) -> dict:
    problems: list[str] = []

    for c in ["kinetic_energy_MeV", "edep_scint_MeV"]:
        if (df[c] < 0).any():
            problems.append(f"{c} contains negative values")
    for c in ["n_scint_generated", "n_end_selected", "n_detected_pe"]:
        if (df[c] < 0).any():
            problems.append(f"{c} contains negative values")

    if (df["n_end_selected"] > df["n_scint_generated"]).any():
        problems.append("n_end_selected exceeds n_scint_generated")
    if (df["n_detected_pe"] > df["n_end_selected"]).any():
        problems.append("n_detected_pe exceeds n_end_selected")

    energy_depositing = df["edep_scint_MeV"] > 1e-6
    generated_fraction = float(
        (df.loc[energy_depositing, "n_scint_generated"] > 0).mean()
    ) if energy_depositing.any() else float("nan")
    end_nonzero_fraction = float(
        (df.loc[energy_depositing, "n_end_selected"] > 0).mean()
    ) if energy_depositing.any() else float("nan")
    detected_nonzero_fraction = float(
        (df.loc[energy_depositing, "n_detected_pe"] > 0).mean()
    ) if energy_depositing.any() else float("nan")

    if energy_depositing.any() and generated_fraction == 0:
        problems.append("all energy-depositing events have zero generated photons")
    if energy_depositing.any() and end_nonzero_fraction == 0:
        problems.append("all energy-depositing events have zero selected-end photons")
    if energy_depositing.any() and detected_nonzero_fraction == 0:
        problems.append("all energy-depositing events have zero detected PE")

    duplicates = int(df.duplicated(["run_id", "event_id"]).sum())
    if duplicates:
        problems.append(f"{duplicates} duplicate (run_id,event_id) rows")

    return {
        "passed": not problems,
        "problems": problems,
        "n_events": int(len(df)),
        "n_energy_depositing": int(energy_depositing.sum()),
        "generated_nonzero_fraction": generated_fraction,
        "selected_end_nonzero_fraction": end_nonzero_fraction,
        "detected_nonzero_fraction": detected_nonzero_fraction,
        "duplicate_event_keys": duplicates,
    }


def sigma68(x: Sequence[float]) -> float:
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < 2:
        return float("nan")
    q16, q84 = np.percentile(a, [16, 84])
    return float((q84 - q16) / 2.0)


def bootstrap_stat(
    x: np.ndarray,
    func,
    rng: np.random.Generator,
    n_boot: int = 500,
) -> tuple[float, float, float]:
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        return float("nan"), float("nan"), float("nan")
    estimate = float(func(x))
    vals = np.empty(n_boot)
    for i in range(n_boot):
        vals[i] = func(rng.choice(x, len(x), replace=True))
    lo, hi = np.percentile(vals, [16, 84])
    return estimate, float(lo), float(hi)


def quantile_profile(
    df: pd.DataFrame, x: str, y: str, bins: int
) -> pd.DataFrame:
    valid = df[[x, y]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < max(20, bins * 3):
        return pd.DataFrame()
    edges = np.unique(np.quantile(valid[x], np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return pd.DataFrame()
    # include rightmost edge
    valid = valid.assign(
        _bin=pd.cut(valid[x], edges, include_lowest=True, duplicates="drop")
    )
    out = (
        valid.groupby("_bin", observed=True)
        .agg(
            x_median=(x, "median"),
            x_min=(x, "min"),
            x_max=(x, "max"),
            y_mean=(y, "mean"),
            y_median=(y, "median"),
            y_p16=(y, lambda s: np.quantile(s, 0.16)),
            y_p84=(y, lambda s: np.quantile(s, 0.84)),
            n=(y, "size"),
        )
        .reset_index(drop=True)
    )
    return out


def heldout_calibration(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = df[
        (df["edep_scint_MeV"] > 0)
        & (df["n_detected_pe"] >= 0)
        & np.isfinite(df["edep_scint_MeV"])
        & np.isfinite(df["n_detected_pe"])
    ].copy()
    if len(d) < 50:
        d["reco_edep_MeV"] = np.nan
        return d, {"status": "insufficient_events"}

    # Deterministic event-key split. A run-aware split should replace this when
    # multiple production runs/configurations are available.
    key_hash = pd.util.hash_pandas_object(
        d[["run_id", "event_id"]].astype(str), index=False
    ).to_numpy(dtype=np.uint64)
    train = (key_hash % 2) == 0
    if train.sum() < 20 or (~train).sum() < 20:
        train = np.arange(len(d)) % 2 == 0

    x = d.loc[train, "edep_scint_MeV"].to_numpy(float)
    y = d.loc[train, "n_detected_pe"].to_numpy(float)
    slope, intercept = np.polyfit(x, y, 1)
    if slope <= 0:
        d["reco_edep_MeV"] = np.nan
        return d, {
            "status": "nonphysical_fit",
            "slope_pe_per_MeV": float(slope),
            "intercept_pe": float(intercept),
        }

    d["is_calibration_train"] = train
    d["reco_edep_MeV"] = (d["n_detected_pe"] - intercept) / slope
    d["relative_residual"] = (
        d["reco_edep_MeV"] - d["edep_scint_MeV"]
    ) / d["edep_scint_MeV"]
    test = d.loc[~train]
    return d, {
        "status": "ok",
        "model": "n_detected_pe = intercept + slope * edep",
        "slope_pe_per_MeV": float(slope),
        "intercept_pe": float(intercept),
        "n_train": int(train.sum()),
        "n_test": int((~train).sum()),
        "test_bias_median_fraction": float(np.median(test["relative_residual"])),
        "test_resolution_sigma68_fraction": sigma68(test["relative_residual"]),
    }


def set_plot_style() -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.color": "#e8e8e8",
            "grid.linewidth": 0.5,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def savefig(fig, output_base: Path) -> None:
    fig.tight_layout()
    fig.savefig(output_base.with_suffix(".png"), dpi=300)
    fig.savefig(output_base.with_suffix(".pdf"))
    import matplotlib.pyplot as plt
    plt.close(fig)


def make_plots(
    df: pd.DataFrame,
    calibrated: pd.DataFrame,
    out: Path,
    bins: int,
    seed: int,
) -> list[dict]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    set_plot_style()
    figdir = out / "figures"
    tabdir = out / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    # G4S-01
    fig, ax = plt.subplots(figsize=(8, 5))
    h = ax.hexbin(
        df["edep_scint_MeV"],
        df["n_end_selected"],
        gridsize=60,
        mincnt=1,
        bins="log",
        cmap="viridis",
    )
    prof = quantile_profile(df, "edep_scint_MeV", "n_end_selected", bins)
    if not prof.empty:
        ax.plot(prof["x_median"], prof["y_median"], color="white", lw=2, label="median")
        ax.fill_between(
            prof["x_median"], prof["y_p16"], prof["y_p84"],
            color="white", alpha=0.25, label="16–84%"
        )
        prof.to_csv(tabdir / "G4S-01_source.csv", index=False)
    fig.colorbar(h, ax=ax, label="log10(events/bin)")
    ax.set_xlabel("Deposited energy in scintillator [MeV]")
    ax.set_ylabel("Photons arriving at selected fibre end [count]")
    ax.legend()
    savefig(fig, figdir / "G4S-01_edep_vs_end_photons")
    records.append({"plot_id": "G4S-01", "source_data": "tables/G4S-01_source.csv"})

    # G4S-02
    fig, ax = plt.subplots(figsize=(8, 5))
    h = ax.hexbin(
        df["edep_scint_MeV"],
        df["n_detected_pe"],
        gridsize=60,
        mincnt=1,
        bins="log",
        cmap="viridis",
    )
    prof2 = quantile_profile(df, "edep_scint_MeV", "n_detected_pe", bins)
    if not prof2.empty:
        ax.plot(prof2["x_median"], prof2["y_median"], color="white", lw=2)
        ax.fill_between(
            prof2["x_median"], prof2["y_p16"], prof2["y_p84"],
            color="white", alpha=0.25
        )
        prof2.to_csv(tabdir / "G4S-02_source.csv", index=False)
    fig.colorbar(h, ax=ax, label="log10(events/bin)")
    ax.set_xlabel("Deposited energy in scintillator [MeV]")
    ax.set_ylabel("Detected primary photoelectrons [count]")
    savefig(fig, figdir / "G4S-02_edep_vs_pe")
    records.append({"plot_id": "G4S-02", "source_data": "tables/G4S-02_source.csv"})

    # G4S-03
    eff = df.loc[df["n_scint_generated"] > 0].copy()
    eff["collection_efficiency"] = (
        eff["n_end_selected"] / eff["n_scint_generated"]
    )
    peff = quantile_profile(eff, "edep_scint_MeV", "collection_efficiency", bins)
    fig, ax = plt.subplots(figsize=(8, 5))
    if not peff.empty:
        ax.plot(peff["x_median"], peff["y_median"], marker="o")
        ax.fill_between(peff["x_median"], peff["y_p16"], peff["y_p84"], alpha=0.25)
        peff.to_csv(tabdir / "G4S-03_source.csv", index=False)
    ax.set_xlabel("Deposited energy [MeV]")
    ax.set_ylabel("Selected-end photons / generated photons")
    savefig(fig, figdir / "G4S-03_collection_efficiency")
    records.append({"plot_id": "G4S-03", "source_data": "tables/G4S-03_source.csv"})

    # G4S-04 position response
    pos = df[np.isfinite(df["entry_x_cm"]) & (df["edep_scint_MeV"] > 0)].copy()
    pos["pe_per_MeV"] = pos["n_detected_pe"] / pos["edep_scint_MeV"]
    ppos = quantile_profile(pos, "entry_x_cm", "pe_per_MeV", bins)
    fig, ax = plt.subplots(figsize=(8, 5))
    if not ppos.empty:
        ax.plot(ppos["x_median"], ppos["y_median"], marker="o")
        ax.fill_between(ppos["x_median"], ppos["y_p16"], ppos["y_p84"], alpha=0.25)
        ppos.to_csv(tabdir / "G4S-04_source.csv", index=False)
    else:
        ax.text(0.5, 0.5, "entry_x_cm unavailable", transform=ax.transAxes, ha="center")
    ax.set_xlabel("Hit position along stave x [cm]")
    ax.set_ylabel("Detected PE / deposited MeV")
    savefig(fig, figdir / "G4S-04_position_response")
    records.append({"plot_id": "G4S-04", "source_data": "tables/G4S-04_source.csv"})

    # G4S-05 photon time profile
    timecol = "median_photon_time_ns"
    tdf = df[np.isfinite(df["entry_x_cm"]) & np.isfinite(df[timecol])].copy()
    pt = quantile_profile(tdf, "entry_x_cm", timecol, bins)
    fig, ax = plt.subplots(figsize=(8, 5))
    if not pt.empty:
        ax.plot(pt["x_median"], pt["y_median"], marker="o")
        ax.fill_between(pt["x_median"], pt["y_p16"], pt["y_p84"], alpha=0.25)
        pt.to_csv(tabdir / "G4S-05_source.csv", index=False)
    else:
        ax.text(0.5, 0.5, "photon timing unavailable", transform=ax.transAxes, ha="center")
    ax.set_xlabel("Hit position along stave x [cm]")
    ax.set_ylabel("Median selected-end photon time [ns]")
    savefig(fig, figdir / "G4S-05_time_vs_position")
    records.append({"plot_id": "G4S-05", "source_data": "tables/G4S-05_source.csv"})

    # G4S-07 held-out bias/resolution
    test = calibrated[
        (~calibrated.get("is_calibration_train", pd.Series(False, index=calibrated.index)).fillna(False))
        & np.isfinite(calibrated.get("relative_residual", np.nan))
    ].copy()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    if len(test) >= 20:
        test["bias_percent"] = 100 * test["relative_residual"]
        pbias = quantile_profile(test, "edep_scint_MeV", "bias_percent", bins)
        # Resolution per energy bin
        edges = np.unique(np.quantile(test["edep_scint_MeV"], np.linspace(0, 1, bins + 1)))
        rows = []
        if len(edges) >= 3:
            binned = pd.cut(test["edep_scint_MeV"], edges, include_lowest=True, duplicates="drop")
            for _, g in test.groupby(binned, observed=True):
                if len(g) >= 10:
                    rows.append({
                        "edep_median_MeV": float(g["edep_scint_MeV"].median()),
                        "bias_median_percent": float(100 * g["relative_residual"].median()),
                        "resolution_sigma68_percent": float(100 * sigma68(g["relative_residual"])),
                        "n": int(len(g)),
                    })
        pres = pd.DataFrame(rows)
        if not pbias.empty:
            ax1.plot(pbias["x_median"], pbias["y_median"], marker="o")
            ax1.fill_between(pbias["x_median"], pbias["y_p16"], pbias["y_p84"], alpha=0.25)
        if not pres.empty:
            ax2.plot(pres["edep_median_MeV"], pres["resolution_sigma68_percent"], marker="o")
            pres.to_csv(tabdir / "G4S-07_source.csv", index=False)
    else:
        ax1.text(0.5, 0.5, "insufficient held-out calibration", transform=ax1.transAxes, ha="center")
    ax1.axhline(0, color="black", lw=1)
    ax1.set_xlabel("True deposited energy [MeV]")
    ax1.set_ylabel("Median reconstruction bias [%]")
    ax2.set_xlabel("True deposited energy [MeV]")
    ax2.set_ylabel("Relative resolution sigma68 [%]")
    savefig(fig, figdir / "G4S-07_energy_bias_resolution")
    records.append({"plot_id": "G4S-07", "source_data": "tables/G4S-07_source.csv"})

    # Species response
    fig, ax = plt.subplots(figsize=(8, 5))
    species_rows = []
    for species, g in df.groupby("species"):
        p = quantile_profile(g, "edep_scint_MeV", "n_detected_pe", bins)
        if p.empty:
            continue
        ax.plot(p["x_median"], p["y_median"], marker="o", label=f"{species} (n={len(g)})")
        for row in p.to_dict("records"):
            row["species"] = species
            species_rows.append(row)
    if species_rows:
        pd.DataFrame(species_rows).to_csv(tabdir / "species_response_source.csv", index=False)
    ax.set_xlabel("Deposited energy [MeV]")
    ax.set_ylabel("Detected PE")
    ax.legend()
    savefig(fig, figdir / "species_response")
    records.append({"plot_id": "species_response", "source_data": "tables/species_response_source.csv"})

    # Birks response when scan exists
    kb = df[np.isfinite(df["birks_kB_mm_per_MeV"])].copy()
    if kb["birks_kB_mm_per_MeV"].nunique() >= 2:
        fig, ax = plt.subplots(figsize=(8, 5))
        rows = []
        for kval, g in kb.groupby("birks_kB_mm_per_MeV"):
            p = quantile_profile(g, "edep_scint_MeV", "n_detected_pe", bins)
            if p.empty:
                continue
            ax.plot(p["x_median"], p["y_median"], marker="o", label=f"kB={kval:g} mm/MeV")
            for row in p.to_dict("records"):
                row["birks_kB_mm_per_MeV"] = float(kval)
                rows.append(row)
        pd.DataFrame(rows).to_csv(tabdir / "G4S-09_source.csv", index=False)
        ax.set_xlabel("Deposited energy [MeV]")
        ax.set_ylabel("Detected PE")
        ax.legend()
        savefig(fig, figdir / "G4S-09_birks_scan")
        records.append({"plot_id": "G4S-09", "source_data": "tables/G4S-09_source.csv"})

    return records


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    raw = read_table(args.input, args.tree)
    df = normalize_schema(raw)
    validation = validate_physics(df)

    # Always write normalized event source data before plotting.
    event_path = args.output / "single_stave_events_normalized.parquet"
    try:
        df.to_parquet(event_path, index=False)
    except Exception:
        event_path = args.output / "single_stave_events_normalized.csv.gz"
        df.to_csv(event_path, index=False)

    calibrated, calibration = heldout_calibration(df)
    plot_records = make_plots(
        df, calibrated, args.output, args.bins, args.seed
    )

    summaries = []
    for (species, ke), g in df.groupby(["species", "kinetic_energy_MeV"], dropna=False):
        summaries.append(
            {
                "species": species,
                "kinetic_energy_MeV": float(ke),
                "n_events": int(len(g)),
                "edep_mean_MeV": float(g["edep_scint_MeV"].mean()),
                "edep_median_MeV": float(g["edep_scint_MeV"].median()),
                "edep_sigma68_MeV": sigma68(g["edep_scint_MeV"]),
                "end_photons_mean": float(g["n_end_selected"].mean()),
                "detected_pe_mean": float(g["n_detected_pe"].mean()),
                "detected_pe_sigma68": sigma68(g["n_detected_pe"]),
            }
        )
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(args.output / "single_stave_summary.csv", index=False)

    result = {
        "study_id": "G4-STAVE",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "validation": validation,
        "calibration": calibration,
        "n_events": int(len(df)),
        "species_counts": {
            str(k): int(v) for k, v in df["species"].value_counts().items()
        },
        "plot_records": plot_records,
        "status": "PASS_SMOKE" if validation["passed"] else "FAIL_VALIDATION",
    }
    (args.output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )

    manifest = {
        "generated_utc": result["generated_utc"],
        "git_commit": git_commit(),
        "command": sys.argv,
        "args": asdict(
            ArgsRecord(
                input=str(args.input),
                output=str(args.output),
                tree=args.tree,
                seed=args.seed,
                bins=args.bins,
                max_display_points=args.max_display_points,
            )
        ),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": [{"path": str(args.input.resolve()), "sha256": sha256(args.input)}],
        "outputs": [],
    }
    for p in sorted(args.output.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            manifest["outputs"].append(
                {"path": str(p.relative_to(args.output)), "sha256": sha256(p)}
            )
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(json.dumps(validation, indent=2))
    print(f"Wrote {args.output}")
    return 0 if validation["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
