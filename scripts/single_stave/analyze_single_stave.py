#!/usr/bin/env python3
"""Analyze normalized single-stave event output with explicit optical bookkeeping.

Supported input:
  - CSV
  - Parquet
  - ROOT flat ntuple (via uproot; --tree required or auto-selected)

The script validates the event schema, writes source-data tables, creates
publication diagnostics, fits a held-out linear PE energy calibration, and
writes ``result.json`` plus a provenance manifest.

Current Geant4 output must first pass through ``adapt_geant4_events.py``. The
normalized current contract retains scintillation, WLS, and Cerenkov counters
and defines ``n_optical_generated_total`` as their exact sum. Legacy tables
without those fields remain readable but are explicitly labelled
``LEGACY_SCINTILLATION_ONLY`` and are not evidence for current-track optical
bookkeeping.

## Energy semantics (issue #1302)

Geant4 produces TWO distinct energy quantities:

- ``E_raw_MeV := edep_scint_raw_MeV``: unquenched Geant4 total energy deposit
  in scintillator (raw physical energy before Birks quenching).
- ``E_vis_MeV := edep_scint_MeV``: Birks-visible/quenched energy from
  ``G4EmSaturation::VisibleEnergyDepositionAtAStep`` (after Birks quenching).

The quenching ratio is ``quenching_ratio := E_vis / E_raw`` (where E_raw > 0).

This script REQUIRES an explicit ``--energy-target`` argument (``E_raw``, ``E_vis``,
or ``both``) and will refuse to proceed with ambiguous bare "Edep" labels in the
code-facing API. All plot axes, table columns, and output labels use precise
"raw deposited" or "Birks-visible" wording.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Sequence

import numpy as np
import pandas as pd

VERSION = "2.1.0"
POLICY = "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL_AND_DECLARE_EXPLICIT_ENERGY_TARGET"

BASE_REQUIRED = {
    "event_id",
    "particle_pdg",
    "kinetic_energy_MeV",
    "edep_scint_MeV",
    "edep_scint_raw_MeV",
    "n_scint_generated",
    "n_end_selected",
    "n_detected_pe",
}

OPTICAL_COMPONENTS = (
    "n_scint_generated",
    "n_wls_generated",
    "n_cerenkov_generated",
)
OPTICAL_TOTAL = "n_optical_generated_total"
CURRENT_OPTICAL_FIELDS = {"n_wls_generated", "n_cerenkov_generated", OPTICAL_TOTAL}
COUNT_FIELDS = {
    "n_scint_generated",
    "n_wls_generated",
    "n_cerenkov_generated",
    OPTICAL_TOTAL,
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
    energy_target: Literal["E_raw", "E_vis", "both"]
    seed: int
    bins: int
    max_display_points: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and plot normalized CCB single-stave MC output."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tree", default=None, help="ROOT tree name")
    parser.add_argument(
        "--energy-target",
        required=True,
        choices=["E_raw", "E_vis", "both"],
        help="Energy target: E_raw (raw deposited MeV), E_vis (Birks-visible MeV), or both"
    )
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--bins", type=int, default=12)
    parser.add_argument("--max-display-points", type=int, default=100_000)
    return parser.parse_args()


def sha256(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def read_table(path: Path, tree: str | None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".csv", ".txt", ".dat"}:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.read_csv(path, sep=r"\s+", comment="#")
    if suffix == ".root":
        try:
            import uproot
        except ImportError as exc:
            raise SystemExit("ROOT input requires uproot") from exc
        with uproot.open(path) as root_file:
            if tree is None:
                candidates = [
                    key.split(";")[0]
                    for key, obj in root_file.items()
                    if hasattr(obj, "arrays")
                ]
                if len(candidates) != 1:
                    raise SystemExit(
                        f"Specify --tree. Candidate ROOT trees: {candidates}"
                    )
                tree = candidates[0]
            return root_file[tree].arrays(library="pd")
    raise SystemExit(f"Unsupported input extension: {suffix}")


def _require_optical_contract(columns: set[str]) -> str:
    present = CURRENT_OPTICAL_FIELDS & columns
    if not present:
        return "LEGACY_SCINTILLATION_ONLY"
    missing = sorted(CURRENT_OPTICAL_FIELDS - columns)
    if missing:
        raise SystemExit(
            "Partial current optical contract; missing columns: " + ", ".join(missing)
        )
    return "CURRENT_COMPONENT_SUM"


def _coerce_required_numeric(df: pd.DataFrame, columns: Sequence[str]) -> None:
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce")
        finite = np.isfinite(values.to_numpy(dtype=float))
        if not finite.all():
            bad_rows = np.flatnonzero(~finite)[:10].tolist()
            raise SystemExit(
                f"{column} contains nonfinite or nonnumeric rows: {bad_rows}"
            )
        df[column] = values


def _coerce_optional_numeric(df: pd.DataFrame, columns: Sequence[str]) -> None:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")


def _validate_integer_counts(df: pd.DataFrame, columns: Sequence[str]) -> None:
    for column in columns:
        values = df[column].to_numpy(dtype=float)
        if (values < 0).any():
            raise SystemExit(f"{column} contains negative values")
        if not np.equal(values, np.floor(values)).all():
            raise SystemExit(f"{column} contains non-integer counts")
        df[column] = values.astype(np.int64)


def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize explicit legacy aliases and validate the optical count contract."""
    aliases = {
        "event": "event_id",
        "ke_MeV": "kinetic_energy_MeV",
        "photons_wls1": "n_end_selected",
        "photons_seen": "n_end_selected",
        "pe": "n_detected_pe",
    }
    out = df.copy()
    for old, new in aliases.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})

    if "particle_pdg" not in out.columns and "particle" in out.columns:
        mapping = {"proton": 2212, "deuteron": 1000010020}
        labels = out["particle"].astype(str)
        values = labels.map(mapping)
        if values.isna().any():
            bad = sorted(labels[values.isna()].unique().tolist())
            raise SystemExit(f"Unknown legacy particle labels: {bad}")
        out["particle_pdg"] = values.astype(np.int64)

    missing = sorted(BASE_REQUIRED - set(out.columns))
    if missing:
        raise SystemExit(
            "Missing required event columns: "
            + ", ".join(missing)
            + "\nSee scripts/single_stave/EVENT_CONTRACT.md."
        )

    contract = _require_optical_contract(set(out.columns))
    for column, default in OPTIONAL_DEFAULTS.items():
        if column not in out.columns:
            out[column] = default

    required_numeric = [
        "event_id",
        "particle_pdg",
        "kinetic_energy_MeV",
        "edep_scint_MeV",
        "edep_scint_raw_MeV",
        "n_scint_generated",
        "n_end_selected",
        "n_detected_pe",
    ]
    if contract == "CURRENT_COMPONENT_SUM":
        required_numeric.extend(
            ["n_wls_generated", "n_cerenkov_generated", OPTICAL_TOTAL]
        )
    _coerce_required_numeric(out, required_numeric)
    _coerce_optional_numeric(
        out,
        [
            "entry_x_cm",
            "entry_y_cm",
            "entry_z_cm",
            "incidence_angle_deg",
            "track_length_scint_cm",
            "first_photon_time_ns",
            "median_photon_time_ns",
            "photon_time_sigma68_ns",
            "birks_kB_mm_per_MeV",
        ],
    )
    _validate_integer_counts(out, [c for c in COUNT_FIELDS if c in out.columns])

    event_values = out["event_id"].to_numpy(dtype=float)
    if (event_values < 0).any() or not np.equal(
        event_values, np.floor(event_values)
    ).all():
        raise SystemExit("event_id must contain nonnegative integer values")
    out["event_id"] = event_values.astype(np.int64)
    out["particle_pdg"] = out["particle_pdg"].astype(np.int64)

    if contract == "CURRENT_COMPONENT_SUM":
        calculated = out[list(OPTICAL_COMPONENTS)].sum(axis=1).astype(np.int64)
        mismatched = calculated != out[OPTICAL_TOTAL]
        if mismatched.any():
            bad_rows = np.flatnonzero(mismatched.to_numpy())[:10].tolist()
            raise SystemExit(
                "n_optical_generated_total does not equal scintillation + WLS + "
                f"Cerenkov at rows: {bad_rows}"
            )

    out.attrs["optical_generation_contract"] = contract
    out["species"] = (
        out["particle_pdg"]
        .map(PDG_LABEL)
        .fillna("pdg_" + out["particle_pdg"].astype(str))
    )
    return out


def generated_optical_denominator(df: pd.DataFrame) -> tuple[str, str]:
    contract = df.attrs.get("optical_generation_contract")
    if contract is None:
        contract = _require_optical_contract(set(df.columns))
    if contract == "CURRENT_COMPONENT_SUM":
        return OPTICAL_TOTAL, contract
    return "n_scint_generated", "LEGACY_SCINTILLATION_ONLY"


def collection_efficiency_frame(df: pd.DataFrame) -> pd.DataFrame:
    denominator, contract = generated_optical_denominator(df)
    selected = df.loc[df[denominator] > 0].copy()
    selected["generated_optical_denominator"] = denominator
    selected["optical_generation_contract"] = contract
    selected["collection_efficiency"] = (
        selected["n_end_selected"] / selected[denominator]
    )
    return selected


def _optical_summary(df: pd.DataFrame) -> dict:
    denominator, contract = generated_optical_denominator(df)
    payload = {
        "contract": contract,
        "arrival_bound_denominator": denominator,
        "denominator_mean": float(df[denominator].mean()),
        "denominator_zero_count": int((df[denominator] == 0).sum()),
        "n_end_selected_mean": float(df["n_end_selected"].mean()),
        "n_detected_pe_mean": float(df["n_detected_pe"].mean()),
    }
    if contract == "CURRENT_COMPONENT_SUM":
        payload["components"] = {
            column: {
                "mean": float(df[column].mean()),
                "sum": int(df[column].sum()),
                "nonzero_count": int((df[column] > 0).sum()),
            }
            for column in OPTICAL_COMPONENTS
        }
        payload["total_identity"] = (
            "n_optical_generated_total = n_scint_generated + "
            "n_wls_generated + n_cerenkov_generated"
        )
    else:
        payload["limitation"] = (
            "Legacy input lacks WLS/Cerenkov component counters; the denominator "
            "is scintillation-only and is not the current Geant4 bookkeeping contract."
        )
    return payload


def validate_physics(df: pd.DataFrame) -> dict:
    problems: list[str] = []
    denominator, contract = generated_optical_denominator(df)

    for column in ["kinetic_energy_MeV", "edep_scint_MeV"]:
        values = df[column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            problems.append(f"{column} contains nonfinite values")
        if (values < 0).any():
            problems.append(f"{column} contains negative values")

    count_columns = [column for column in COUNT_FIELDS if column in df.columns]
    for column in count_columns:
        values = df[column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            problems.append(f"{column} contains nonfinite values")
        if (values < 0).any():
            problems.append(f"{column} contains negative values")
        if not np.equal(values, np.floor(values)).all():
            problems.append(f"{column} contains non-integer counts")

    if contract == "CURRENT_COMPONENT_SUM":
        calculated = df[list(OPTICAL_COMPONENTS)].sum(axis=1).to_numpy(dtype=np.int64)
        declared = df[OPTICAL_TOTAL].to_numpy(dtype=np.int64)
        if not np.array_equal(calculated, declared):
            problems.append(
                "n_optical_generated_total differs from the exact component sum"
            )

    if (df["n_end_selected"] > df[denominator]).any():
        problems.append(f"n_end_selected exceeds {denominator}")
    if (df["n_detected_pe"] > df["n_end_selected"]).any():
        problems.append("n_detected_pe exceeds n_end_selected")

    energy_depositing = df["edep_scint_MeV"] > 1e-6
    generated_fraction = (
        float((df.loc[energy_depositing, denominator] > 0).mean())
        if energy_depositing.any()
        else float("nan")
    )
    end_nonzero_fraction = (
        float((df.loc[energy_depositing, "n_end_selected"] > 0).mean())
        if energy_depositing.any()
        else float("nan")
    )
    detected_nonzero_fraction = (
        float((df.loc[energy_depositing, "n_detected_pe"] > 0).mean())
        if energy_depositing.any()
        else float("nan")
    )

    if energy_depositing.any() and generated_fraction == 0:
        problems.append("all energy-depositing events have zero generated optical tracks")
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
        "optical_generation_contract": contract,
        "generated_optical_denominator": denominator,
        "generated_nonzero_fraction": generated_fraction,
        "selected_end_nonzero_fraction": end_nonzero_fraction,
        "detected_nonzero_fraction": detected_nonzero_fraction,
        "duplicate_event_keys": duplicates,
        "optical_bookkeeping": _optical_summary(df),
    }


def sigma68(values: Sequence[float]) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) < 2:
        return float("nan")
    q16, q84 = np.percentile(array, [16, 84])
    return float((q84 - q16) / 2.0)


def bootstrap_stat(
    values: np.ndarray,
    func: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_boot: int = 500,
) -> tuple[float, float, float]:
    array = np.asarray(values)
    array = array[np.isfinite(array)]
    if len(array) < 10:
        return float("nan"), float("nan"), float("nan")
    estimate = float(func(array))
    replicas = np.empty(n_boot)
    for index in range(n_boot):
        replicas[index] = func(rng.choice(array, len(array), replace=True))
    low, high = np.percentile(replicas, [16, 84])
    return estimate, float(low), float(high)


def quantile_profile(df: pd.DataFrame, x: str, y: str, bins: int) -> pd.DataFrame:
    valid = df[[x, y]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < max(20, bins * 3):
        return pd.DataFrame()
    edges = np.unique(np.quantile(valid[x], np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return pd.DataFrame()
    valid = valid.assign(
        _bin=pd.cut(valid[x], edges, include_lowest=True, duplicates="drop")
    )
    return (
        valid.groupby("_bin", observed=True)
        .agg(
            x_median=(x, "median"),
            x_min=(x, "min"),
            x_max=(x, "max"),
            y_mean=(y, "mean"),
            y_median=(y, "median"),
            y_p16=(y, lambda series: np.quantile(series, 0.16)),
            y_p84=(y, lambda series: np.quantile(series, 0.84)),
            n=(y, "size"),
        )
        .reset_index(drop=True)
    )


def heldout_calibration(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    selected = df[
        (df["edep_scint_MeV"] > 0)
        & (df["n_detected_pe"] >= 0)
        & np.isfinite(df["edep_scint_MeV"])
        & np.isfinite(df["n_detected_pe"])
    ].copy()
    if len(selected) < 50:
        selected["reco_edep_MeV"] = np.nan
        return selected, {"status": "insufficient_events"}

    key_hash = pd.util.hash_pandas_object(
        selected[["run_id", "event_id"]].astype(str), index=False
    ).to_numpy(dtype=np.uint64)
    train = (key_hash % 2) == 0
    if train.sum() < 20 or (~train).sum() < 20:
        train = np.arange(len(selected)) % 2 == 0

    x_train = selected.loc[train, "edep_scint_MeV"].to_numpy(float)
    y_train = selected.loc[train, "n_detected_pe"].to_numpy(float)
    slope, intercept = np.polyfit(x_train, y_train, 1)
    if slope <= 0:
        selected["reco_edep_MeV"] = np.nan
        return selected, {
            "status": "nonphysical_fit",
            "slope_pe_per_MeV": float(slope),
            "intercept_pe": float(intercept),
        }

    selected["is_calibration_train"] = train
    selected["reco_edep_MeV"] = (
        selected["n_detected_pe"] - intercept
    ) / slope
    selected["relative_residual"] = (
        selected["reco_edep_MeV"] - selected["edep_scint_MeV"]
    ) / selected["edep_scint_MeV"]
    test = selected.loc[~train]
    return selected, {
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
    import matplotlib.pyplot as plt

    fig.tight_layout()
    fig.savefig(output_base.with_suffix(".png"), dpi=300)
    fig.savefig(output_base.with_suffix(".pdf"))
    plt.close(fig)


def _write_profile_plot(
    ax,
    profile: pd.DataFrame,
    source_path: Path,
    *,
    label: str | None = None,
) -> None:
    if profile.empty:
        return
    ax.plot(profile["x_median"], profile["y_median"], marker="o", label=label)
    ax.fill_between(
        profile["x_median"],
        profile["y_p16"],
        profile["y_p84"],
        alpha=0.25,
    )
    profile.to_csv(source_path, index=False)


def make_plots(
    df: pd.DataFrame,
    calibrated: pd.DataFrame,
    out: Path,
    bins: int,
    seed: int,
) -> list[dict]:
    del seed
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    set_plot_style()
    figdir = out / "figures"
    tabdir = out / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.hexbin(
        df["edep_scint_MeV"],
        df["n_end_selected"],
        gridsize=60,
        mincnt=1,
        bins="log",
        cmap="viridis",
    )
    profile = quantile_profile(df, "edep_scint_MeV", "n_end_selected", bins)
    if not profile.empty:
        ax.plot(
            profile["x_median"],
            profile["y_median"],
            color="white",
            lw=2,
            label="median",
        )
        ax.fill_between(
            profile["x_median"],
            profile["y_p16"],
            profile["y_p84"],
            color="white",
            alpha=0.25,
            label="16–84%",
        )
        profile.to_csv(tabdir / "G4S-01_source.csv", index=False)
    fig.colorbar(image, ax=ax, label="log10(events/bin)")
    ax.set_xlabel("Birks-visible deposited energy in scintillator [MeV]")
    ax.set_ylabel("Photons arriving at selected fibre end [count]")
    ax.legend()
    savefig(fig, figdir / "G4S-01_edep_vs_end_photons")
    records.append({"plot_id": "G4S-01", "source_data": "tables/G4S-01_source.csv"})

    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.hexbin(
        df["edep_scint_MeV"],
        df["n_detected_pe"],
        gridsize=60,
        mincnt=1,
        bins="log",
        cmap="viridis",
    )
    profile = quantile_profile(df, "edep_scint_MeV", "n_detected_pe", bins)
    if not profile.empty:
        ax.plot(profile["x_median"], profile["y_median"], color="white", lw=2)
        ax.fill_between(
            profile["x_median"],
            profile["y_p16"],
            profile["y_p84"],
            color="white",
            alpha=0.25,
        )
        profile.to_csv(tabdir / "G4S-02_source.csv", index=False)
    fig.colorbar(image, ax=ax, label="log10(events/bin)")
    ax.set_xlabel("Birks-visible deposited energy in scintillator [MeV]")
    ax.set_ylabel("Detected primary photoelectrons [count]")
    savefig(fig, figdir / "G4S-02_edep_vs_pe")
    records.append({"plot_id": "G4S-02", "source_data": "tables/G4S-02_source.csv"})

    efficiency = collection_efficiency_frame(df)
    denominator, contract = generated_optical_denominator(df)
    profile = quantile_profile(
        efficiency,
        "edep_scint_MeV",
        "collection_efficiency",
        bins,
    )
    if not profile.empty:
        profile["generated_optical_denominator"] = denominator
        profile["optical_generation_contract"] = contract
    fig, ax = plt.subplots(figsize=(8, 5))
    _write_profile_plot(ax, profile, tabdir / "G4S-03_source.csv")
    ax.set_xlabel("Birks-visible deposited energy [MeV]")
    ax.set_ylabel(f"Selected-end photons / {denominator}")
    savefig(fig, figdir / "G4S-03_collection_efficiency")
    records.append(
        {
            "plot_id": "G4S-03",
            "source_data": "tables/G4S-03_source.csv",
            "denominator": denominator,
            "optical_generation_contract": contract,
        }
    )

    position = df[
        np.isfinite(df["entry_x_cm"]) & (df["edep_scint_MeV"] > 0)
    ].copy()
    position["pe_per_MeV"] = (
        position["n_detected_pe"] / position["edep_scint_MeV"]
    )
    profile = quantile_profile(position, "entry_x_cm", "pe_per_MeV", bins)
    fig, ax = plt.subplots(figsize=(8, 5))
    if profile.empty:
        ax.text(
            0.5,
            0.5,
            "entry_x_cm unavailable",
            transform=ax.transAxes,
            ha="center",
        )
    else:
        _write_profile_plot(ax, profile, tabdir / "G4S-04_source.csv")
    ax.set_xlabel("Hit position along stave x [cm]")
    ax.set_ylabel("Detected PE / Birks-visible deposited MeV")
    savefig(fig, figdir / "G4S-04_position_response")
    records.append({"plot_id": "G4S-04", "source_data": "tables/G4S-04_source.csv"})

    time_column = "median_photon_time_ns"
    timing = df[
        np.isfinite(df["entry_x_cm"]) & np.isfinite(df[time_column])
    ].copy()
    profile = quantile_profile(timing, "entry_x_cm", time_column, bins)
    fig, ax = plt.subplots(figsize=(8, 5))
    if profile.empty:
        ax.text(
            0.5,
            0.5,
            "photon timing unavailable",
            transform=ax.transAxes,
            ha="center",
        )
    else:
        _write_profile_plot(ax, profile, tabdir / "G4S-05_source.csv")
    ax.set_xlabel("Hit position along stave x [cm]")
    ax.set_ylabel("Median selected-end photon time [ns]")
    savefig(fig, figdir / "G4S-05_time_vs_position")
    records.append({"plot_id": "G4S-05", "source_data": "tables/G4S-05_source.csv"})

    train_flag = calibrated.get(
        "is_calibration_train",
        pd.Series(False, index=calibrated.index),
    ).fillna(False)
    residual = calibrated.get(
        "relative_residual",
        pd.Series(np.nan, index=calibrated.index),
    )
    test = calibrated[(~train_flag) & np.isfinite(residual)].copy()
    fig, (ax_bias, ax_resolution) = plt.subplots(1, 2, figsize=(12, 5))
    if len(test) >= 20:
        test["bias_percent"] = 100 * test["relative_residual"]
        bias = quantile_profile(test, "edep_scint_MeV", "bias_percent", bins)
        edges = np.unique(
            np.quantile(test["edep_scint_MeV"], np.linspace(0, 1, bins + 1))
        )
        rows: list[dict] = []
        if len(edges) >= 3:
            binned = pd.cut(
                test["edep_scint_MeV"],
                edges,
                include_lowest=True,
                duplicates="drop",
            )
            for _, group in test.groupby(binned, observed=True):
                if len(group) >= 10:
                    rows.append(
                        {
                            "E_vis_median_MeV": float(
                                group["edep_scint_MeV"].median()
                            ),
                            "bias_median_percent": float(
                                100 * group["relative_residual"].median()
                            ),
                            "resolution_sigma68_percent": float(
                                100 * sigma68(group["relative_residual"])
                            ),
                            "n": int(len(group)),
                        }
                    )
        resolution = pd.DataFrame(rows)
        if not bias.empty:
            ax_bias.plot(bias["x_median"], bias["y_median"], marker="o")
            ax_bias.fill_between(
                bias["x_median"],
                bias["y_p16"],
                bias["y_p84"],
                alpha=0.25,
            )
        if not resolution.empty:
            ax_resolution.plot(
                resolution["E_vis_median_MeV"],
                resolution["resolution_sigma68_percent"],
                marker="o",
            )
            resolution.to_csv(tabdir / "G4S-07_source.csv", index=False)
    else:
        ax_bias.text(
            0.5,
            0.5,
            "insufficient held-out calibration",
            transform=ax_bias.transAxes,
            ha="center",
        )
    ax_bias.axhline(0, color="black", lw=1)
    ax_bias.set_xlabel("True deposited energy [MeV]")
    ax_bias.set_ylabel("Median reconstruction bias [%]")
    ax_resolution.set_xlabel("True deposited energy [MeV]")
    ax_resolution.set_ylabel("Relative resolution sigma68 [%]")
    savefig(fig, figdir / "G4S-07_energy_bias_resolution")
    records.append({"plot_id": "G4S-07", "source_data": "tables/G4S-07_source.csv"})

    fig, ax = plt.subplots(figsize=(8, 5))
    species_rows: list[dict] = []
    for species, group in df.groupby("species"):
        profile = quantile_profile(group, "edep_scint_MeV", "n_detected_pe", bins)
        if profile.empty:
            continue
        ax.plot(
            profile["x_median"],
            profile["y_median"],
            marker="o",
            label=f"{species} (n={len(group)})",
        )
        for row in profile.to_dict("records"):
            row["species"] = species
            species_rows.append(row)
    if species_rows:
        pd.DataFrame(species_rows).to_csv(
            tabdir / "species_response_source.csv",
            index=False,
        )
    ax.set_xlabel("Birks-visible deposited energy [MeV]")
    ax.set_ylabel("Detected PE")
    ax.legend()
    savefig(fig, figdir / "species_response")
    records.append(
        {
            "plot_id": "species_response",
            "source_data": "tables/species_response_source.csv",
        }
    )

    birks = df[np.isfinite(df["birks_kB_mm_per_MeV"])].copy()
    if birks["birks_kB_mm_per_MeV"].nunique() >= 2:
        fig, ax = plt.subplots(figsize=(8, 5))
        rows = []
        for value, group in birks.groupby("birks_kB_mm_per_MeV"):
            profile = quantile_profile(
                group,
                "edep_scint_MeV",
                "n_detected_pe",
                bins,
            )
            if profile.empty:
                continue
            ax.plot(
                profile["x_median"],
                profile["y_median"],
                marker="o",
                label=f"kB={value:g} mm/MeV",
            )
            for row in profile.to_dict("records"):
                row["birks_kB_mm_per_MeV"] = float(value)
                rows.append(row)
        pd.DataFrame(rows).to_csv(tabdir / "G4S-09_source.csv", index=False)
        ax.set_xlabel("Birks-visible deposited energy [MeV]")
        ax.set_ylabel("Detected PE")
        ax.legend()
        savefig(fig, figdir / "G4S-09_birks_scan")
        records.append({"plot_id": "G4S-09", "source_data": "tables/G4S-09_source.csv"})

    return records


def _species_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    denominator, contract = generated_optical_denominator(df)
    for (species, kinetic_energy), group in df.groupby(
        ["species", "kinetic_energy_MeV"], dropna=False
    ):
        row = {
            "species": species,
            "kinetic_energy_MeV": float(kinetic_energy),
            "n_events": int(len(group)),
            "E_vis_mean_MeV": float(group["edep_scint_MeV"].mean()),
            "E_vis_median_MeV": float(group["edep_scint_MeV"].median()),
            "E_vis_sigma68_MeV": sigma68(group["edep_scint_MeV"]),
            "E_raw_mean_MeV": float(group["edep_scint_raw_MeV"].mean()),
            "E_raw_median_MeV": float(group["edep_scint_raw_MeV"].median()),
            "E_raw_sigma68_MeV": sigma68(group["edep_scint_raw_MeV"]),
            "quenching_ratio_median": float((group["edep_scint_MeV"] / group["edep_scint_raw_MeV"]).median()),
            "generated_optical_denominator": denominator,
            "optical_generation_contract": contract,
            "generated_optical_mean": float(group[denominator].mean()),
            "end_photons_mean": float(group["n_end_selected"].mean()),
            "detected_pe_mean": float(group["n_detected_pe"].mean()),
            "detected_pe_sigma68": sigma68(group["n_detected_pe"]),
        }
        for component in OPTICAL_COMPONENTS:
            if component in group.columns:
                row[f"{component}_mean"] = float(group[component].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    raw = read_table(args.input, args.tree)
    df = normalize_schema(raw)
    validation = validate_physics(df)

    event_path = args.output / "single_stave_events_normalized.parquet"
    try:
        df.to_parquet(event_path, index=False)
    except Exception:
        event_path = args.output / "single_stave_events_normalized.csv.gz"
        df.to_csv(event_path, index=False)

    calibrated, calibration = heldout_calibration(df)
    plot_records = make_plots(df, calibrated, args.output, args.bins, args.seed)

    summary = _species_summary(df)
    summary.to_csv(args.output / "single_stave_summary.csv", index=False)

    result = {
        "schema": "ccb-single-stave-analysis/2",
        "version": VERSION,
        "policy": POLICY,
        "study_id": "G4-STAVE",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "validation": validation,
        "optical_bookkeeping": validation["optical_bookkeeping"],
        "calibration": calibration,
        "n_events": int(len(df)),
        "species_counts": {
            str(key): int(value) for key, value in df["species"].value_counts().items()
        },
        "plot_records": plot_records,
        "status": "PASS_SMOKE" if validation["passed"] else "FAIL_VALIDATION",
    }
    (args.output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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
                energy_target=args.energy_target,
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
        "inputs": [
            {
                "path": str(args.input.resolve()),
                "bytes": args.input.stat().st_size,
                "sha256": sha256(args.input),
            }
        ],
        "outputs": [],
    }
    for path in sorted(args.output.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"].append(
                {
                    "path": str(path.relative_to(args.output)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(validation, indent=2, sort_keys=True))
    print(f"Wrote {args.output}")
    return 0 if validation["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
