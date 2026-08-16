#!/usr/bin/env python3
"""
Comprehensive QA and plotting for CCB single-stave Geant4 event/photon outputs.

Key design goals
----------------
* Reads the actual current Geant4 event-tree schema:
  event, particle, ke_MeV, edep_scint_MeV, edep_scint_raw_MeV,
  arrival_readout, detected_readout, and the three control sensors.
* Also accepts the normalized analysis schema used by the older Python analyzer.
* Accepts CSV, CSV.GZ, Parquet, or ROOT files. ROOT support requires uproot.
* Treats hard physical impossibilities separately from warnings/diagnostics.
* Writes one source-data CSV per plot, JSON results, and a SHA-256 manifest.
* Every figure is generated separately; no dashboard-only plots hide source data.

Examples
--------
python scripts/single_stave_diagnostics.py \
  --events data/events.csv.gz \
  --photons data/photons.csv.gz \
  --output report

python scripts/single_stave_diagnostics.py \
  --events "/path/grid/*.root" --tree events --photon-tree photons \
  --output report
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SENSOR_SUFFIXES = ("readout", "f1far", "f2near", "f2far")
PDG_MAP = {"proton": 2212, "deuteron": 1000010020}
SPECIES_MAP = {2212: "proton", 1000010020: "deuteron"}


@dataclass
class PlotRecord:
    plot_id: str
    title: str
    figure_png: str
    source_csv: str
    status: str
    notes: str = ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--events",
        nargs="+",
        required=True,
        help="Event files or glob patterns (CSV/CSV.GZ/Parquet/ROOT).",
    )
    p.add_argument(
        "--photons",
        nargs="*",
        default=[],
        help="Optional photon CSV/Parquet files. For ROOT, photon tree is read from event files.",
    )
    p.add_argument("--tree", default="events", help="ROOT event tree name.")
    p.add_argument("--photon-tree", default="photons", help="ROOT photon tree name.")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--seed", type=int, default=20260723)
    p.add_argument("--bins", type=int, default=12)
    p.add_argument("--max-display-points", type=int, default=150_000)
    p.add_argument(
        "--strict",
        action="store_true",
        help="Return nonzero when warnings are present, not only hard failures.",
    )
    return p.parse_args()


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                return h.hexdigest()
            h.update(b)


def expand_paths(items: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for item in items:
        matches = sorted(glob.glob(item))
        if matches:
            paths.extend(Path(x) for x in matches)
        else:
            paths.append(Path(item))
    unique: list[Path] = []
    seen: set[str] = set()
    for p in paths:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    missing = [str(p) for p in unique if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing input files:\n" + "\n".join(missing))
    return unique


def read_flat(path: Path) -> pd.DataFrame:
    name = path.name.lower()
    if name.endswith(".csv") or name.endswith(".csv.gz"):
        return pd.read_csv(path)
    if name.endswith(".parquet") or name.endswith(".pq"):
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported flat-table extension: {path}")


def read_root_tree(path: Path, tree: str) -> pd.DataFrame:
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError("ROOT input requires: pip install uproot awkward") from exc
    with uproot.open(path) as f:
        if tree not in {k.split(";")[0] for k in f.keys()}:
            raise KeyError(f"{tree!r} not found in {path}; trees={list(f.keys())}")
        return f[tree].arrays(library="pd")


def load_events(paths: list[Path], tree: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        if path.suffix.lower() == ".root":
            frame = read_root_tree(path, tree)
        else:
            frame = read_flat(path)
        frame = frame.copy()
        frame["_source_file"] = str(path.resolve())
        frame["_run_file"] = path.stem
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False)


def load_photons(
    event_paths: list[Path],
    photon_paths: list[Path],
    photon_tree: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in event_paths:
        if path.suffix.lower() != ".root":
            continue
        try:
            frame = read_root_tree(path, photon_tree)
        except KeyError:
            continue
        frame = frame.copy()
        frame["_source_file"] = str(path.resolve())
        frame["_run_file"] = path.stem
        frames.append(frame)
    for path in photon_paths:
        frame = read_flat(path).copy()
        frame["_source_file"] = str(path.resolve())
        frame["_run_file"] = path.stem
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def normalize_events(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    aliases = {
        "event": "event_id",
        "ke_MeV": "kinetic_energy_MeV",
        "track_len_scint_mm": "track_length_scint_mm",
        "arrival_readout": "n_end_selected",
        "detected_readout": "n_detected_pe",
        "pe_sat_readout": "n_saturated_pe",
    }
    for old, new in aliases.items():
        if old in out.columns and new not in out.columns:
            out[new] = out[old]

    if "species" not in out.columns:
        if "particle" in out.columns:
            out["species"] = out["particle"].astype(str).str.lower()
        elif "particle_pdg" in out.columns:
            pdg = pd.to_numeric(out["particle_pdg"], errors="coerce")
            out["species"] = pdg.map(SPECIES_MAP).fillna("pdg_" + pdg.astype("Int64").astype(str))
        else:
            out["species"] = "unknown"

    if "particle_pdg" not in out.columns:
        out["particle_pdg"] = out["species"].map(PDG_MAP)

    if "run_id" not in out.columns:
        out["run_id"] = out.get("_run_file", "run0").astype(str)

    if "track_length_scint_cm" not in out.columns and "track_length_scint_mm" in out.columns:
        out["track_length_scint_cm"] = pd.to_numeric(
            out["track_length_scint_mm"], errors="coerce"
        ) / 10.0

    # Preserve all four current Geant4 sensor branches and ensure numeric type.
    numeric_candidates = [
        "event_id",
        "particle_pdg",
        "kinetic_energy_MeV",
        "edep_scint_MeV",
        "edep_scint_raw_MeV",
        "track_length_scint_mm",
        "track_length_scint_cm",
        "entry_x_cm",
        "entry_y_cm",
        "entry_z_cm",
        "exit_x_cm",
        "exit_y_cm",
        "exit_z_cm",
        "incidence_angle_deg",
        "n_scint_generated",
        "n_wls_generated",
        "n_cerenkov_generated",
        "n_end_selected",
        "n_detected_pe",
        "n_saturated_pe",
        "birks_kB_mm_per_MeV",
    ]
    for suffix in SENSOR_SUFFIXES:
        numeric_candidates.extend(
            [f"arrival_{suffix}", f"detected_{suffix}", f"pe_sat_{suffix}"]
        )
    for col in numeric_candidates:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    required = [
        "event_id",
        "kinetic_energy_MeV",
        "edep_scint_MeV",
        "n_scint_generated",
        "n_end_selected",
        "n_detected_pe",
    ]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(
            "Missing required normalized columns: "
            + ", ".join(missing)
            + ". Current Geant4 aliases arrival_readout/detected_readout are supported."
        )
    return out


def normalize_photons(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    aliases = {"event": "event_id", "path_len_mm": "path_length_mm"}
    for old, new in aliases.items():
        if old in out.columns and new not in out.columns:
            out[new] = out[old]
    if "run_id" not in out.columns:
        out["run_id"] = out.get("_run_file", "run0").astype(str)
    for c in [
        "event_id",
        "sensor",
        "wavelength_nm",
        "time_ns",
        "path_length_mm",
        "detected",
    ]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    required = {"event_id", "sensor", "wavelength_nm", "time_ns", "path_length_mm", "detected"}
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError("Photon table missing columns: " + ", ".join(missing))
    return out


def validate_events(df: pd.DataFrame) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, object] = {}

    required = [
        "event_id",
        "kinetic_energy_MeV",
        "edep_scint_MeV",
        "n_scint_generated",
        "n_end_selected",
        "n_detected_pe",
    ]
    for c in required:
        n_bad = int((~np.isfinite(df[c])).sum())
        if n_bad:
            failures.append(f"{c}: {n_bad} non-finite values")

    for c in [
        "kinetic_energy_MeV",
        "edep_scint_MeV",
        "n_scint_generated",
        "n_end_selected",
        "n_detected_pe",
    ]:
        if c in df and (df[c] < 0).any():
            failures.append(f"{c}: negative values present")

    duplicates = int(df.duplicated(["run_id", "event_id"]).sum())
    metrics["duplicate_event_keys"] = duplicates
    if duplicates:
        failures.append(f"{duplicates} duplicate (run_id,event_id) keys")

    # Event-ID coverage is evaluated per input run/file.
    coverage_rows = []
    for run_id, g in df.groupby("run_id", dropna=False):
        ids = pd.to_numeric(g["event_id"], errors="coerce").dropna().astype(int)
        if ids.empty:
            continue
        expected = set(range(int(ids.min()), int(ids.max()) + 1))
        actual = set(ids.tolist())
        missing = len(expected - actual)
        coverage_rows.append(
            {
                "run_id": str(run_id),
                "n_rows": int(len(g)),
                "n_unique": int(ids.nunique()),
                "id_min": int(ids.min()),
                "id_max": int(ids.max()),
                "n_missing_inside_range": int(missing),
            }
        )
        if missing:
            warnings.append(f"run {run_id}: {missing} event IDs missing inside observed range")
    metrics["event_id_coverage"] = coverage_rows

    if (df["n_detected_pe"] > df["n_end_selected"]).any():
        failures.append("n_detected_pe exceeds selected-end arrivals")

    # Defensible optical-chain bound: readout-end arrivals cannot exceed the
    # TOTAL generated optical-track population, summed across every creator
    # process the simulation records:
    #   * scintillation (n_scint_generated)  -- always present
    #   * wavelength-shifting re-emission (n_wls_generated)
    #   * Cherenkov (n_cerenkov_generated)
    # The older n_end_selected <= n_scint_generated inequality is NOT a general
    # contract because WLS and Cerenkov tracks also feed the readout end. We sum
    # only the categories actually present. When WLS/Cerenkov are recorded the
    # total is a complete inventory and a violation is a hard failure; when only
    # scintillation is present the comparison is necessarily partial (unrecorded
    # WLS/Cerenkov could explain an excess), so it is downgraded to a warning.
    total_generated_cols = [
        c for c in ["n_scint_generated", "n_wls_generated", "n_cerenkov_generated"] if c in df
    ]
    categories_present = list(total_generated_cols)
    complete_bound = any(c in df for c in ("n_wls_generated", "n_cerenkov_generated"))
    total_generated = df[total_generated_cols].sum(axis=1)
    bounded = total_generated > 0
    if bounded.any():
        ratio = df.loc[bounded, "n_end_selected"] / total_generated[bounded]
        metrics["n_end_over_total_generated_max"] = float(ratio.max())
        metrics["optical_bound_categories"] = categories_present
    if (df["n_end_selected"] > total_generated).any():
        msg = (
            "selected-end arrivals exceed total generated optical tracks ("
            + "+".join(c.replace("_generated", "").replace("n_", "") for c in categories_present)
            + ")"
        )
        if complete_bound:
            failures.append(msg)
        else:
            warnings.append(msg + " -- only scintillation category recorded; bound is partial")

    for suffix in SENSOR_SUFFIXES:
        a, d, s = f"arrival_{suffix}", f"detected_{suffix}", f"pe_sat_{suffix}"
        if a in df and d in df and (df[d] > df[a]).any():
            failures.append(f"{d} exceeds {a}")
        if d in df and s in df:
            if (df[s] > df[d] + 1e-9).any():
                failures.append(f"{s} exceeds unsaturated detected PE")
            if (df[s] < -1e-9).any():
                failures.append(f"{s} has negative values")

    energy_depositing = df["edep_scint_MeV"] > 1e-9
    metrics["n_events"] = int(len(df))
    metrics["n_energy_depositing"] = int(energy_depositing.sum())
    metrics["zero_pe_fraction_among_depositing"] = float(
        (df.loc[energy_depositing, "n_detected_pe"] == 0).mean()
    ) if energy_depositing.any() else None

    if "edep_scint_raw_MeV" in df:
        finite = np.isfinite(df["edep_scint_raw_MeV"]) & np.isfinite(df["edep_scint_MeV"])
        exact_equal = np.isclose(
            df.loc[finite, "edep_scint_raw_MeV"],
            df.loc[finite, "edep_scint_MeV"],
            rtol=0.0,
            atol=0.0,
        )
        frac_equal = float(exact_equal.mean()) if exact_equal.size else None
        metrics["raw_visible_exact_equal_fraction"] = frac_equal
        if frac_equal is not None and frac_equal > 0.999:
            warnings.append(
                "edep_scint_MeV and edep_scint_raw_MeV are exactly equal for >99.9% "
                "of events; current C++ fills both from GetTotalEnergyDeposit, so the "
                "'Birks-quenched visible energy' label is not supported."
            )
        if (df.loc[finite, "edep_scint_MeV"] > df.loc[finite, "edep_scint_raw_MeV"] + 1e-9).any():
            warnings.append("visible deposited energy exceeds raw deposited energy")

    # edep > KE is not a universal hard failure because nuclear Q-values may contribute.
    if (df["edep_scint_MeV"] > df["kinetic_energy_MeV"] * 1.02).any():
        warnings.append(
            "Some scintillator deposits exceed primary kinetic energy by >2%; inspect "
            "hadronic secondaries/Q-values and event bookkeeping."
        )

    if "track_length_scint_mm" in df and "incidence_angle_deg" in df:
        g = df[
            np.isfinite(df["track_length_scint_mm"])
            & np.isfinite(df["incidence_angle_deg"])
            & (np.abs(df["incidence_angle_deg"]) < 80)
        ]
        if len(g) > 20:
            expected = 20.0 / np.cos(np.deg2rad(g["incidence_angle_deg"]))
            rel = np.abs(g["track_length_scint_mm"] - expected) / expected
            metrics["track_length_geometry_median_abs_fraction"] = float(np.median(rel))
            if np.median(rel) > 0.05:
                warnings.append("track length disagrees with 20 mm / cos(theta) by >5% median")

    return {
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "metrics": metrics,
    }


def validate_photons(ph: pd.DataFrame, events: pd.DataFrame) -> dict:
    if ph.empty:
        return {"available": False, "passed": True, "failures": [], "warnings": []}
    failures: list[str] = []
    warnings: list[str] = []
    for c in ["event_id", "sensor", "wavelength_nm", "time_ns", "path_length_mm", "detected"]:
        if (~np.isfinite(ph[c])).any():
            failures.append(f"photon {c}: non-finite values")
    if (~ph["sensor"].isin(range(4))).any():
        failures.append("photon sensor outside [0,3]")
    if (~ph["detected"].isin([0, 1])).any():
        failures.append("photon detected flag outside {0,1}")
    if (ph["wavelength_nm"] <= 0).any():
        failures.append("non-positive photon wavelength")
    if (ph["time_ns"] < 0).any() or (ph["path_length_mm"] < 0).any():
        failures.append("negative photon time/path length")

    event_keys = set(zip(events["run_id"].astype(str), events["event_id"].astype(int)))
    ph_keys = set(zip(ph["run_id"].astype(str), ph["event_id"].astype(int)))
    foreign = len(ph_keys - event_keys)
    if foreign:
        failures.append(f"{foreign} photon event keys absent from event tree")

    detected_fraction = float(ph["detected"].mean())
    if not (0 <= detected_fraction <= 1):
        failures.append("invalid detected fraction")
    if detected_fraction == 0:
        warnings.append("photon tree has zero detected photons")
    return {
        "available": True,
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "n_rows": int(len(ph)),
        "detected_fraction": detected_fraction,
    }


def set_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "savefig.dpi": 220,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "font.size": 10,
        }
    )


def save_plot(fig, figdir: Path, plot_id: str, slug: str) -> str:
    path = figdir / f"{plot_id}_{slug}.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return str(path)


def source_table(tabdir: Path, plot_id: str, df: pd.DataFrame) -> str:
    path = tabdir / f"{plot_id}_source.csv"
    df.to_csv(path, index=False)
    return str(path)


def quantile_profile(df: pd.DataFrame, x: str, y: str, bins: int) -> pd.DataFrame:
    d = df[[x, y]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) < max(30, bins * 4) or d[x].nunique() < 3:
        return pd.DataFrame()
    edges = np.unique(np.quantile(d[x], np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return pd.DataFrame()
    b = pd.cut(d[x], edges, include_lowest=True, duplicates="drop")
    return (
        d.groupby(b, observed=True)
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


def downsample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if len(df) <= n:
        return df
    return df.sample(n=n, random_state=seed)


def group_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (species, ke), g in df.groupby(["species", "kinetic_energy_MeV"], dropna=False):
        pe = g["n_detected_pe"].to_numpy(float)
        ed = g["edep_scint_MeV"].to_numpy(float)
        arr = g["n_end_selected"].to_numpy(float)
        rows.append(
            {
                "species": species,
                "kinetic_energy_MeV": float(ke),
                "n": int(len(g)),
                "edep_mean_MeV": float(np.mean(ed)),
                "edep_std_MeV": float(np.std(ed, ddof=1)) if len(ed) > 1 else np.nan,
                "arrival_mean": float(np.mean(arr)),
                "pe_mean": float(np.mean(pe)),
                "pe_std": float(np.std(pe, ddof=1)) if len(pe) > 1 else np.nan,
                "pe_sem": float(np.std(pe, ddof=1) / math.sqrt(len(pe))) if len(pe) > 1 else np.nan,
                "pe_over_edep_ratio_of_means": float(np.mean(pe) / np.mean(ed)) if np.mean(ed) > 0 else np.nan,
                "relative_resolution": float(np.std(pe, ddof=1) / np.mean(pe)) if len(pe) > 1 and np.mean(pe) > 0 else np.nan,
                "zero_pe_fraction": float(np.mean(pe == 0)),
                "effective_detection_fraction": float(np.sum(pe) / np.sum(arr)) if np.sum(arr) > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["species", "kinetic_energy_MeV"])


def _sigma68(x: np.ndarray) -> float:
    """Half the central 68th-percentile width — a robust 1-sigma-like spread."""
    if x.size == 0:
        return float("nan")
    return float((np.quantile(x, 0.84) - np.quantile(x, 0.16)) / 2.0)


def _linear_fit_uncertain(x: np.ndarray, y: np.ndarray) -> dict:
    """Unconstrained OLS y = slope*x + intercept with parameter standard errors.

    Uncertainties come from numpy.polyfit's covariance (scaled by chi2/dof); a
    closed-form OLS fallback is used if the covariance is unavailable.
    """
    n = int(len(x))
    slope, intercept = np.polyfit(x, y, 1)
    slope_se = math.nan
    intercept_se = math.nan
    if n > 2:
        try:
            (_s, _i), cov = np.polyfit(x, y, 1, cov=True)
            if cov is not None and np.all(np.isfinite(cov)):
                slope_se = float(np.sqrt(cov[0, 0]))
                intercept_se = float(np.sqrt(cov[1, 1]))
        except (TypeError, ValueError, np.linalg.LinAlgError):
            pass
    if not (np.isfinite(slope_se) and np.isfinite(intercept_se)):
        xbar = float(np.mean(x))
        sxx = float(np.sum((x - xbar) ** 2))
        resid = y - (slope * x + intercept)
        if n > 2 and sxx > 0:
            sigma2 = float(np.dot(resid, resid) / (n - 2))
            slope_se = float(np.sqrt(sigma2 / sxx))
            intercept_se = float(np.sqrt(sigma2 * (1.0 / n + xbar**2 / sxx)))
    return {
        "slope_pe_per_MeV": float(slope),
        "intercept_pe": float(intercept),
        "slope_se": slope_se,
        "intercept_se": intercept_se,
        "n": n,
    }


def _origin_fit_uncertain(x: np.ndarray, y: np.ndarray) -> dict:
    """Through-origin OLS y = slope*x with the standard error on the slope."""
    n = int(len(x))
    sxx = float(np.dot(x, x))
    slope = float(np.dot(x, y) / sxx) if sxx > 0 else float("nan")
    slope_se = math.nan
    if n > 1 and sxx > 0:
        resid = y - slope * x
        sigma2 = float(np.dot(resid, resid) / (n - 1))
        slope_se = float(np.sqrt(sigma2 / sxx))
    return {"slope_pe_per_MeV": slope, "slope_se": slope_se, "n": n}


def _position_aware_fit(x: np.ndarray, pos: np.ndarray, y: np.ndarray) -> dict | None:
    """Multivariate OLS y = a*edep + b*position + c (position-decorrelated yield).

    Returns None when the design matrix is rank-deficient (e.g. single position).
    """
    n = int(len(x))
    if n <= 3 or np.ptp(pos) == 0:
        return None
    X = np.column_stack([x, pos, np.ones(n)])
    try:
        xtX = X.T @ X
        cov_scale = np.linalg.inv(xtX)
    except np.linalg.LinAlgError:
        return None
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = X @ coef - y
    dof = max(n - 3, 1)
    sigma2 = float(np.dot(resid, resid) / dof)
    se = np.sqrt(np.maximum(np.diag(sigma2 * cov_scale), 0.0))
    return {
        "edep_slope_pe_per_MeV": float(coef[0]),
        "position_slope_pe_per_cm": float(coef[1]),
        "intercept_pe": float(coef[2]),
        "edep_slope_se": float(se[0]),
        "position_slope_se": float(se[1]),
        "intercept_se": float(se[2]),
        "n": n,
    }


def heldout_calibration(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Held-out PE<->Edep calibration with several models and a comparison line.

    Models fit on a deterministic train split and compared on the held-out test
    fraction by PE-space RMSE:
      * pooled unconstrained linear  (PE = slope*E + intercept)
      * pooled through-origin        (PE = slope*E)
      * species-aware unconstrained  (one line per species)
      * position-aware multivariate  (PE = a*E + b*x + c)
    All reported fits carry parameter standard errors, and a human-readable
    model-comparison line is returned for logging.
    """
    d = df[
        np.isfinite(df["edep_scint_MeV"])
        & np.isfinite(df["n_detected_pe"])
        & (df["edep_scint_MeV"] > 0)
    ].copy()
    if len(d) < 100:
        return d, {
            "status": "insufficient_events",
            "model_comparison": {
                "line": "insufficient events for calibration (<100 depositing)",
                "models": {},
            },
        }

    # Run-aware deterministic split. Whole runs are held out when >=4 runs exist.
    run_values = sorted(d["run_id"].astype(str).unique())
    if len(run_values) >= 4:
        test_runs = {r for i, r in enumerate(run_values) if i % 4 == 0}
        train = ~d["run_id"].astype(str).isin(test_runs)
        split = "run-held-out"
    else:
        key = pd.util.hash_pandas_object(
            d[["run_id", "event_id"]].astype(str), index=False
        ).to_numpy(dtype=np.uint64)
        train = (key % 5) != 0
        split = "event-key-held-out"

    d["is_calibration_train"] = train
    x_tr = d.loc[train, "edep_scint_MeV"].to_numpy(float)
    y_tr = d.loc[train, "n_detected_pe"].to_numpy(float)

    # --- Pooled unconstrained + through-origin (with parameter uncertainties) ---
    lin = _linear_fit_uncertain(x_tr, y_tr)
    ori = _origin_fit_uncertain(x_tr, y_tr)
    d["reco_edep_linear_MeV"] = (d["n_detected_pe"] - lin["intercept_pe"]) / lin["slope_pe_per_MeV"]
    d["reco_edep_origin_MeV"] = d["n_detected_pe"] / ori["slope_pe_per_MeV"]
    for model in ("linear", "origin"):
        reco = d[f"reco_edep_{model}_MeV"]
        d[f"relative_residual_{model}"] = (reco - d["edep_scint_MeV"]) / d["edep_scint_MeV"]

    # Build train/test views AFTER the derived residual columns exist on d.
    tr = d.loc[train]
    te = d.loc[~train].copy()

    def _pe_rmse(pred: np.ndarray) -> float:
        return float(np.sqrt(np.mean((pred - te["n_detected_pe"].to_numpy(float)) ** 2)))

    models: dict[str, dict] = {}

    # Pooled unconstrained.
    lin_pred = lin["slope_pe_per_MeV"] * te["edep_scint_MeV"].to_numpy(float) + lin["intercept_pe"]
    lin_rel = te["relative_residual_linear"].to_numpy(float)
    models["pooled_linear"] = {
        **lin,
        "test_rmse_pe": _pe_rmse(lin_pred),
        "test_bias_median_fraction": float(np.median(lin_rel)),
        "test_resolution_sigma68_fraction": _sigma68(lin_rel),
    }

    # Pooled through-origin.
    ori_pred = ori["slope_pe_per_MeV"] * te["edep_scint_MeV"].to_numpy(float)
    ori_rel = te["relative_residual_origin"].to_numpy(float)
    models["through_origin"] = {
        **ori,
        "test_rmse_pe": _pe_rmse(ori_pred),
        "test_bias_median_fraction": float(np.median(ori_rel)),
        "test_resolution_sigma68_fraction": _sigma68(ori_rel),
    }

    # --- Species-aware unconstrained (one fit per species, >=30 train events) ---
    species_fits: dict[str, dict] = {}
    sp_pred = np.full(len(te), np.nan)
    for species, g in tr.groupby("species", dropna=False):
        if len(g) < 30:
            continue
        xf = g["edep_scint_MeV"].to_numpy(float)
        yf = g["n_detected_pe"].to_numpy(float)
        fit = _linear_fit_uncertain(xf, yf)
        species_fits[str(species)] = fit
        mask = te["species"].to_numpy() == species
        if mask.any():
            sp_pred[mask] = fit["slope_pe_per_MeV"] * te.loc[mask, "edep_scint_MeV"].to_numpy(float) + fit["intercept_pe"]
    if species_fits and np.isfinite(sp_pred).any():
        finite = np.isfinite(sp_pred)
        sp_rel = ((sp_pred[finite] - te["n_detected_pe"].to_numpy(float)[finite])
                  / sp_pred[finite])  # fractional PE residual (symmetric form)
        models["species_aware"] = {
            "per_species": species_fits,
            "test_rmse_pe": float(np.sqrt(np.mean((sp_pred[finite] - te["n_detected_pe"].to_numpy(float)[finite]) ** 2))),
            "test_bias_median_fraction": float(np.median(sp_rel)),
        }

    # --- Position-aware multivariate (PE = a*E + b*x + c) ---
    if "entry_x_cm" in tr.columns:
        pos_fit = _position_aware_fit(
            x_tr, tr["entry_x_cm"].to_numpy(float), y_tr
        )
        if pos_fit is not None:
            pa_pred = (
                pos_fit["edep_slope_pe_per_MeV"] * te["edep_scint_MeV"].to_numpy(float)
                + pos_fit["position_slope_pe_per_cm"] * te["entry_x_cm"].to_numpy(float)
                + pos_fit["intercept_pe"]
            )
            models["position_aware"] = {
                **pos_fit,
                "test_rmse_pe": _pe_rmse(pa_pred),
            }

    comparison = " | ".join(
        f"{name}: RMSE={m.get('test_rmse_pe', float('nan')):.1f} PE"
        for name, m in models.items()
    )
    return d, {
        "status": "ok",
        "split": split,
        "n_train": int(train.sum()),
        "n_test": int((~train).sum()),
        "unconstrained": models["pooled_linear"],
        "through_origin": models["through_origin"],
        "species_aware": models.get("species_aware", {"status": "insufficient_per_species"}),
        "position_aware": models.get("position_aware", {"status": "position_column_absent"}),
        "model_comparison": {"line": comparison, "models": models},
    }


def make_event_plots(
    df: pd.DataFrame,
    out: Path,
    bins: int,
    max_points: int,
    seed: int,
) -> tuple[list[PlotRecord], pd.DataFrame, dict]:
    set_style()
    figdir = out / "figures"
    tabdir = out / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    records: list[PlotRecord] = []
    summary = group_summary(df)
    summary.to_csv(out / "group_summary.csv", index=False)

    def add(pid: str, title: str, fig, slug: str, src: pd.DataFrame, notes: str = ""):
        figpath = save_plot(fig, figdir, pid, slug)
        srcpath = source_table(tabdir, pid, src)
        records.append(
            PlotRecord(
                pid,
                title,
                str(Path(figpath).relative_to(out)),
                str(Path(srcpath).relative_to(out)),
                "generated",
                notes,
            )
        )

    # SS-01 raw/visible deposited energy distributions
    fig, ax = plt.subplots(figsize=(8, 5))
    rows = []
    for species, g in df.groupby("species"):
        vals = g["edep_scint_MeV"].dropna()
        ax.hist(vals, bins=50, histtype="step", linewidth=1.5, label=f"{species} (n={len(vals)})")
        rows.extend({"species": species, "edep_scint_MeV": float(v)} for v in vals)
    ax.set_xlabel("Recorded scintillator deposited energy [MeV]")
    ax.set_ylabel("Events")
    ax.set_yscale("log")
    ax.legend()
    add("SS-01", "Deposited-energy distributions", fig, "edep_distributions", pd.DataFrame(rows))

    # SS-02 raw-vs-visible diagnostic
    if "edep_scint_raw_MeV" in df:
        d = df[
            np.isfinite(df["edep_scint_raw_MeV"])
            & np.isfinite(df["edep_scint_MeV"])
            & (df["edep_scint_raw_MeV"] > 0)
        ].copy()
        d["visible_over_raw"] = d["edep_scint_MeV"] / d["edep_scint_raw_MeV"]
        if "track_length_scint_mm" in d:
            d["dEdx_raw_MeV_per_mm"] = d["edep_scint_raw_MeV"] / d["track_length_scint_mm"]
        else:
            d["dEdx_raw_MeV_per_mm"] = np.nan
        ds = downsample(d, max_points, seed)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(ds["dEdx_raw_MeV_per_mm"], ds["visible_over_raw"], s=4, alpha=0.25)
        ax.set_xlabel("Raw dE/dx [MeV/mm]")
        ax.set_ylabel("Recorded visible/raw deposited energy")
        add(
            "SS-02",
            "Birks/raw-visible bookkeeping diagnostic",
            fig,
            "raw_visible_ratio",
            d[["species", "kinetic_energy_MeV", "edep_scint_raw_MeV", "edep_scint_MeV", "dEdx_raw_MeV_per_mm", "visible_over_raw"]],
            "A flat value of exactly 1 indicates the current C++ raw/visible bookkeeping bug.",
        )

    # SS-03 detected PE versus deposited energy
    d = df[np.isfinite(df["edep_scint_MeV"]) & np.isfinite(df["n_detected_pe"])].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    ds = downsample(d, max_points, seed)
    hb = ax.hexbin(ds["edep_scint_MeV"], ds["n_detected_pe"], gridsize=60, mincnt=1, bins="log")
    fig.colorbar(hb, ax=ax, label="log10(events/bin)")
    slope, intercept = np.polyfit(d["edep_scint_MeV"], d["n_detected_pe"], 1)
    xline = np.linspace(d["edep_scint_MeV"].min(), d["edep_scint_MeV"].max(), 100)
    ax.plot(xline, slope * xline + intercept, label=f"pooled fit: {slope:.2f} PE/MeV, b={intercept:.1f}")
    ax.set_xlabel("Recorded deposited energy [MeV]")
    ax.set_ylabel("Detected readout PE")
    ax.legend()
    add("SS-03", "PE response versus deposited energy", fig, "pe_vs_edep", d[["species", "kinetic_energy_MeV", "edep_scint_MeV", "n_detected_pe"]])

    # SS-04 arrivals versus generated optical tracks
    total_cols = [c for c in ["n_scint_generated", "n_wls_generated", "n_cerenkov_generated"] if c in df]
    d = df.copy()
    d["n_optical_generated_total"] = d[total_cols].sum(axis=1)
    fig, ax = plt.subplots(figsize=(8, 5))
    ds = downsample(d, max_points, seed)
    hb = ax.hexbin(ds["n_optical_generated_total"], ds["n_end_selected"], gridsize=60, mincnt=1, bins="log")
    fig.colorbar(hb, ax=ax, label="log10(events/bin)")
    ax.set_xlabel("Generated optical tracks (scintillation + WLS + Cerenkov)")
    ax.set_ylabel("Readout-end arrivals")
    add("SS-04", "Optical collection chain", fig, "arrival_vs_generated", d[["species", "kinetic_energy_MeV", "n_optical_generated_total", "n_end_selected"]])

    # SS-05 detected versus arrived
    d = df[np.isfinite(df["n_end_selected"]) & np.isfinite(df["n_detected_pe"])].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    ds = downsample(d, max_points, seed)
    hb = ax.hexbin(ds["n_end_selected"], ds["n_detected_pe"], gridsize=60, mincnt=1, bins="log")
    fig.colorbar(hb, ax=ax, label="log10(events/bin)")
    lim = max(float(d["n_end_selected"].max()), 1)
    ax.plot([0, lim], [0, lim], linestyle="--", label="100%")
    ax.set_xlabel("Readout-end arrivals")
    ax.set_ylabel("Detected readout PE")
    ax.legend()
    add("SS-05", "Detection stage response", fig, "detected_vs_arrival", d[["species", "kinetic_energy_MeV", "n_end_selected", "n_detected_pe"]])

    # SS-06 collection efficiency
    d = df[d["n_scint_generated"] > 0].copy()
    d["collection_efficiency"] = d["n_end_selected"] / d["n_scint_generated"]
    fig, ax = plt.subplots(figsize=(8, 5))
    for species, g in d.groupby("species"):
        ax.hist(g["collection_efficiency"], bins=50, histtype="step", linewidth=1.5, label=species)
    ax.set_xlabel("Readout arrivals / generated scintillation photons")
    ax.set_ylabel("Events")
    ax.set_yscale("log")
    ax.legend()
    add("SS-06", "Optical collection-efficiency distribution", fig, "collection_efficiency", d[["species", "kinetic_energy_MeV", "collection_efficiency"]])

    # SS-07 effective detection fraction
    d = df[df["n_end_selected"] > 0].copy()
    d["effective_detection_fraction"] = d["n_detected_pe"] / d["n_end_selected"]
    fig, ax = plt.subplots(figsize=(8, 5))
    for species, g in d.groupby("species"):
        ax.hist(g["effective_detection_fraction"], bins=50, histtype="step", linewidth=1.5, label=species)
    ax.set_xlabel("Detected PE / readout arrivals")
    ax.set_ylabel("Events")
    ax.legend()
    add("SS-07", "Effective PDE × coupling distribution", fig, "effective_detection", d[["species", "kinetic_energy_MeV", "effective_detection_fraction"]])

    # SS-08 position response
    if "entry_x_cm" in df:
        d = df[
            np.isfinite(df["entry_x_cm"])
            & (df["edep_scint_MeV"] > 0)
        ].copy()
        d["pe_per_MeV"] = d["n_detected_pe"] / d["edep_scint_MeV"]
        rows = []
        fig, ax = plt.subplots(figsize=(8, 5))
        for species, g in d.groupby("species"):
            p = quantile_profile(g, "entry_x_cm", "pe_per_MeV", bins)
            if p.empty:
                continue
            p["species"] = species
            rows.append(p)
            ax.plot(p["x_median"], p["y_median"], marker="o", label=species)
            ax.fill_between(p["x_median"], p["y_p16"], p["y_p84"], alpha=0.2)
        ax.set_xlabel("Entry x along stave [cm]")
        ax.set_ylabel("Detected PE / recorded deposited MeV")
        ax.legend()
        src = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
        add("SS-08", "Longitudinal position response", fig, "position_response", src)

    # SS-09 sensor means
    sensor_cols = [f"detected_{s}" for s in SENSOR_SUFFIXES if f"detected_{s}" in df]
    if sensor_cols:
        means = df[sensor_cols].mean().rename_axis("sensor_branch").reset_index(name="mean_detected_pe")
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(means["sensor_branch"], means["mean_detected_pe"])
        ax.set_ylabel("Mean detected PE")
        ax.tick_params(axis="x", rotation=25)
        add("SS-09", "Mean response of all four sensors", fig, "sensor_means", means)

    # SS-10 near/far asymmetry versus position
    if {"detected_readout", "detected_f1far", "entry_x_cm"}.issubset(df.columns):
        d = df[np.isfinite(df["entry_x_cm"])].copy()
        den = d["detected_readout"] + d["detected_f1far"]
        d = d[den > 0].copy()
        d["f1_asymmetry"] = (
            d["detected_readout"] - d["detected_f1far"]
        ) / (d["detected_readout"] + d["detected_f1far"])
        p = quantile_profile(d, "entry_x_cm", "f1_asymmetry", bins)
        fig, ax = plt.subplots(figsize=(8, 5))
        if not p.empty:
            ax.plot(p["x_median"], p["y_median"], marker="o")
            ax.fill_between(p["x_median"], p["y_p16"], p["y_p84"], alpha=0.2)
        ax.axhline(0, linewidth=1)
        ax.set_xlabel("Entry x [cm]")
        ax.set_ylabel("(F1 +x − F1 −x) / sum")
        add("SS-10", "Fibre-end asymmetry versus position", fig, "fibre_asymmetry", p)

    # SS-11 track-length geometry closure
    if {"track_length_scint_mm", "incidence_angle_deg"}.issubset(df.columns):
        d = df[
            np.isfinite(df["track_length_scint_mm"])
            & np.isfinite(df["incidence_angle_deg"])
            & (np.abs(df["incidence_angle_deg"]) < 80)
        ].copy()
        d["expected_track_length_mm"] = 20.0 / np.cos(np.deg2rad(d["incidence_angle_deg"]))
        fig, ax = plt.subplots(figsize=(8, 5))
        ds = downsample(d, max_points, seed)
        ax.scatter(ds["incidence_angle_deg"], ds["track_length_scint_mm"], s=5, alpha=0.25, label="events")
        xline = np.linspace(d["incidence_angle_deg"].min(), d["incidence_angle_deg"].max(), 100)
        ax.plot(xline, 20.0 / np.cos(np.deg2rad(xline)), label="20 mm / cos(theta)")
        ax.set_xlabel("Incidence angle [deg]")
        ax.set_ylabel("Track length in scintillator [mm]")
        ax.legend()
        add("SS-11", "Geometry/path-length closure", fig, "track_length_closure", d[["species", "kinetic_energy_MeV", "incidence_angle_deg", "track_length_scint_mm", "expected_track_length_mm"]])

    # SS-12 SiPM saturation transfer
    if "n_saturated_pe" in df:
        d = df[np.isfinite(df["n_saturated_pe"])].copy()
        fig, ax = plt.subplots(figsize=(8, 5))
        ds = downsample(d, max_points, seed)
        ax.scatter(ds["n_detected_pe"], ds["n_saturated_pe"], s=5, alpha=0.25)
        lim = max(float(d["n_detected_pe"].max()), 1)
        ax.plot([0, lim], [0, lim], linestyle="--", label="no saturation")
        ax.set_xlabel("Detected PE before saturation")
        ax.set_ylabel("Fired-cell equivalent after saturation")
        ax.legend()
        add("SS-12", "SiPM saturation transfer", fig, "saturation_transfer", d[["species", "kinetic_energy_MeV", "n_detected_pe", "n_saturated_pe"]])

    # SS-13 mean PE versus KE
    fig, ax = plt.subplots(figsize=(8, 5))
    for species, g in summary.groupby("species"):
        ax.errorbar(
            g["kinetic_energy_MeV"],
            g["pe_mean"],
            yerr=g["pe_sem"],
            marker="o",
            capsize=3,
            label=species,
        )
    ax.set_xlabel("Primary kinetic energy [MeV]")
    ax.set_ylabel("Mean detected readout PE")
    ax.legend()
    add("SS-13", "Mean PE versus beam energy", fig, "mean_pe_vs_ke", summary)

    # SS-14 resolution versus KE
    fig, ax = plt.subplots(figsize=(8, 5))
    for species, g in summary.groupby("species"):
        ax.plot(g["kinetic_energy_MeV"], 100 * g["relative_resolution"], marker="o", label=species)
    ax.set_xlabel("Primary kinetic energy [MeV]")
    ax.set_ylabel("PE RMS / mean [%]")
    ax.legend()
    add("SS-14", "Relative PE resolution versus beam energy", fig, "resolution_vs_ke", summary)

    # Held-out calibration and SS-15/16
    cal, cal_result = heldout_calibration(df)
    if cal_result.get("status") == "ok":
        test = cal.loc[~cal["is_calibration_train"]].copy()
        for model, pid, title in [
            ("linear", "SS-15", "Held-out calibration bias"),
            ("origin", "SS-16", "Through-origin calibration bias"),
        ]:
            col = f"relative_residual_{model}"
            p = quantile_profile(test.assign(residual_percent=100 * test[col]), "edep_scint_MeV", "residual_percent", bins)
            fig, ax = plt.subplots(figsize=(8, 5))
            if not p.empty:
                ax.plot(p["x_median"], p["y_median"], marker="o")
                ax.fill_between(p["x_median"], p["y_p16"], p["y_p84"], alpha=0.2)
            ax.axhline(0, linewidth=1)
            ax.set_xlabel("True recorded deposited energy [MeV]")
            ax.set_ylabel("Reconstruction residual [%]")
            add(pid, title, fig, f"calibration_bias_{model}", p)

    # SS-17 zero-PE fractions
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = summary["species"] + " " + summary["kinetic_energy_MeV"].map(lambda x: f"{x:g}")
    ax.bar(labels, 100 * summary["zero_pe_fraction"])
    ax.set_ylabel("Zero detected-PE events [%]")
    ax.tick_params(axis="x", rotation=35)
    add("SS-17", "Zero-response fraction by grid point", fig, "zero_fraction", summary)

    # SS-18 correlation matrix
    corr_cols = [
        c for c in [
            "kinetic_energy_MeV",
            "edep_scint_MeV",
            "edep_scint_raw_MeV",
            "track_length_scint_mm",
            "entry_x_cm",
            "n_scint_generated",
            "n_wls_generated",
            "n_end_selected",
            "n_detected_pe",
            "n_saturated_pe",
        ] if c in df
    ]
    corr = df[corr_cols].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1)
    fig.colorbar(im, ax=ax, label="Pearson correlation")
    ax.set_xticks(range(len(corr_cols)), corr_cols, rotation=60, ha="right")
    ax.set_yticks(range(len(corr_cols)), corr_cols)
    add("SS-18", "Event-variable correlation matrix", fig, "correlation_matrix", corr.reset_index(names="variable"))

    # SS-19 raw-visible difference distribution
    if "edep_scint_raw_MeV" in df:
        d = df[np.isfinite(df["edep_scint_raw_MeV"]) & np.isfinite(df["edep_scint_MeV"])].copy()
        d["raw_minus_recorded_MeV"] = d["edep_scint_raw_MeV"] - d["edep_scint_MeV"]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(d["raw_minus_recorded_MeV"], bins=60, histtype="step", linewidth=1.5)
        ax.set_xlabel("Raw Edep − recorded 'visible' Edep [MeV]")
        ax.set_ylabel("Events")
        ax.set_yscale("log")
        add("SS-19", "Raw-visible equality check", fig, "raw_minus_visible", d[["species", "kinetic_energy_MeV", "edep_scint_raw_MeV", "edep_scint_MeV", "raw_minus_recorded_MeV"]])

    # SS-20 sensor arrival shares
    arrival_cols = [f"arrival_{s}" for s in SENSOR_SUFFIXES if f"arrival_{s}" in df]
    if arrival_cols:
        totals = df[arrival_cols].sum()
        shares = (totals / totals.sum()).rename_axis("sensor_branch").reset_index(name="arrival_share")
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(shares["sensor_branch"], 100 * shares["arrival_share"])
        ax.set_ylabel("Share of all sensor arrivals [%]")
        ax.tick_params(axis="x", rotation=25)
        add("SS-20", "Optical-arrival sharing among sensors", fig, "sensor_arrival_shares", shares)

    # SS-27 detected-PE response distribution (fundamental response shape per species)
    d = df[np.isfinite(df["n_detected_pe"]) & (df["n_detected_pe"] >= 0)].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    rows = []
    for species, g in d.groupby("species"):
        vals = g["n_detected_pe"].to_numpy(float)
        ax.hist(vals, bins=60, histtype="step", linewidth=1.5, label=f"{species} (n={len(vals)})")
        rows.extend({"species": species, "n_detected_pe": float(v)} for v in vals)
    ax.set_xlabel("Detected readout PE")
    ax.set_ylabel("Events")
    ax.set_yscale("log")
    ax.legend()
    add("SS-27", "Detected-PE response distribution", fig, "pe_distribution", pd.DataFrame(rows))

    # SS-28 Birks suppression profile: binned visible/raw vs raw dE/dx, with the
    # theoretical Birks factor 1/(1+kB*dE/dx) overlaid. Directly exercises the
    # defect-2 separation between edep_scint_MeV (visible) and edep_scint_raw_MeV.
    if {"edep_scint_raw_MeV", "track_length_scint_mm"}.issubset(df.columns):
        d = df[
            np.isfinite(df["edep_scint_raw_MeV"])
            & np.isfinite(df["edep_scint_MeV"])
            & np.isfinite(df["track_length_scint_mm"])
            & (df["edep_scint_raw_MeV"] > 0)
            & (df["track_length_scint_mm"] > 0)
        ].copy()
        d["dEdx_raw_MeV_per_mm"] = d["edep_scint_raw_MeV"] / d["track_length_scint_mm"]
        d["visible_over_raw"] = d["edep_scint_MeV"] / d["edep_scint_raw_MeV"]
        prof = quantile_profile(d, "dEdx_raw_MeV_per_mm", "visible_over_raw", bins)
        fig, ax = plt.subplots(figsize=(8, 5))
        ds = downsample(d, max_points, seed)
        ax.scatter(ds["dEdx_raw_MeV_per_mm"], ds["visible_over_raw"], s=4, alpha=0.2, label="events")
        theoretical_label = None
        if not prof.empty:
            ax.plot(prof["x_median"], prof["y_median"], color="crimson", marker="o", lw=2, label="median profile")
            ax.fill_between(prof["x_median"], prof["y_p16"], prof["y_p84"], color="crimson", alpha=0.15)
            # Theoretical Birks factor. Prefer the run's own kB if recorded per
            # event; otherwise the polystyrene simulation default (AppConfig.hh).
            if "birks_kB_mm_per_MeV" in d.columns and d["birks_kB_mm_per_MeV"].notna().any():
                kB = float(d["birks_kB_mm_per_MeV"].dropna().median())
                theoretical_label = f"Birks 1/(1+kB·dE/dx), kB={kB:g}"
            else:
                kB = 0.126  # AppConfig.hh polystyrene default (mm/MeV)
                theoretical_label = "Birks 1/(1+kB·dE/dx), kB=0.126 (sim default)"
            xs = np.linspace(float(d["dEdx_raw_MeV_per_mm"].min()), float(d["dEdx_raw_MeV_per_mm"].max()), 200)
            ax.plot(xs, 1.0 / (1.0 + kB * xs), color="black", linestyle="--", label=theoretical_label)
        ax.axhline(1.0, color="grey", linewidth=0.8)
        ax.set_xlabel("Raw dE/dx [MeV/mm]")
        ax.set_ylabel("Recorded visible/raw deposited energy")
        ax.legend()
        src = prof if not prof.empty else d[["species", "kinetic_energy_MeV", "edep_scint_raw_MeV", "edep_scint_MeV", "dEdx_raw_MeV_per_mm", "visible_over_raw"]]
        add(
            "SS-28", "Birks suppression profile", fig, "birks_suppression_profile", src,
            "Median visible/raw should track 1/(1+kB·dE/dx); a flat 1.0 exposes the raw/visible bookkeeping bug.",
        )

    return records, summary, cal_result


def make_photon_plots(
    ph: pd.DataFrame,
    out: Path,
    bins: int,
    max_points: int,
    seed: int,
) -> list[PlotRecord]:
    if ph.empty:
        return []
    set_style()
    figdir = out / "figures"
    tabdir = out / "tables"
    records: list[PlotRecord] = []

    def add(pid: str, title: str, fig, slug: str, src: pd.DataFrame, notes: str = ""):
        figpath = save_plot(fig, figdir, pid, slug)
        srcpath = source_table(tabdir, pid, src)
        records.append(
            PlotRecord(
                pid,
                title,
                str(Path(figpath).relative_to(out)),
                str(Path(srcpath).relative_to(out)),
                "generated",
                notes,
            )
        )

    # SS-21 wavelength spectra
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(ph["wavelength_nm"], bins=70, histtype="step", linewidth=1.5, label="all arrivals")
    det = ph[ph["detected"] == 1]
    ax.hist(det["wavelength_nm"], bins=70, histtype="step", linewidth=1.5, label="detected")
    ax.set_xlabel("Photon wavelength [nm]")
    ax.set_ylabel("Photon arrivals")
    ax.set_yscale("log")
    ax.legend()
    add("SS-21", "Arrival and detected wavelength spectra", fig, "wavelength_spectra", ph[["run_id", "event_id", "sensor", "wavelength_nm", "detected"]])

    # SS-22 inferred detection fraction versus wavelength
    d = ph[np.isfinite(ph["wavelength_nm"])].copy()
    edges = np.linspace(d["wavelength_nm"].quantile(0.005), d["wavelength_nm"].quantile(0.995), 25)
    d["wavelength_bin"] = pd.cut(d["wavelength_nm"], edges, include_lowest=True)
    p = (
        d.groupby("wavelength_bin", observed=True)
        .agg(
            wavelength_nm=("wavelength_nm", "mean"),
            detected_fraction=("detected", "mean"),
            n=("detected", "size"),
        )
        .reset_index(drop=True)
    )
    p["binomial_sem"] = np.sqrt(p["detected_fraction"] * (1 - p["detected_fraction"]) / p["n"])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(p["wavelength_nm"], p["detected_fraction"], yerr=p["binomial_sem"], marker="o", capsize=3)
    ax.set_xlabel("Photon wavelength [nm]")
    ax.set_ylabel("Detected fraction")
    add("SS-22", "Effective spectral detection probability", fig, "detection_vs_wavelength", p)

    # SS-23 photon-time distributions by sensor
    fig, ax = plt.subplots(figsize=(8, 5))
    rows = []
    for sensor, g in ph.groupby("sensor"):
        ax.hist(g["time_ns"], bins=70, histtype="step", linewidth=1.5, label=f"sensor {int(sensor)}")
        rows.extend({"sensor": int(sensor), "time_ns": float(v)} for v in g["time_ns"])
    ax.set_xlabel("Arrival time [ns]")
    ax.set_ylabel("Photon arrivals")
    ax.set_yscale("log")
    ax.legend()
    add("SS-23", "Photon arrival-time distributions", fig, "arrival_times", pd.DataFrame(rows))

    # SS-24 time versus path
    ds = downsample(ph, max_points, seed)
    fig, ax = plt.subplots(figsize=(8, 5))
    hb = ax.hexbin(ds["path_length_mm"], ds["time_ns"], gridsize=65, mincnt=1, bins="log")
    fig.colorbar(hb, ax=ax, label="log10(arrivals/bin)")
    ax.set_xlabel("Optical track path length [mm]")
    ax.set_ylabel("Arrival time [ns]")
    add("SS-24", "Photon time versus path length", fig, "time_vs_path", ds[["sensor", "path_length_mm", "time_ns", "wavelength_nm", "detected"]])

    # SS-25 detection fraction versus time
    d = ph.copy()
    edges = np.unique(np.quantile(d["time_ns"], np.linspace(0, 1, bins + 1)))
    d["time_bin"] = pd.cut(d["time_ns"], edges, include_lowest=True, duplicates="drop")
    p = (
        d.groupby("time_bin", observed=True)
        .agg(time_ns=("time_ns", "mean"), detected_fraction=("detected", "mean"), n=("detected", "size"))
        .reset_index(drop=True)
    )
    p["binomial_sem"] = np.sqrt(p["detected_fraction"] * (1 - p["detected_fraction"]) / p["n"])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(p["time_ns"], p["detected_fraction"], yerr=p["binomial_sem"], marker="o", capsize=3)
    ax.set_xlabel("Arrival time [ns]")
    ax.set_ylabel("Detected fraction")
    add("SS-25", "Detection probability versus arrival time", fig, "detection_vs_time", p)

    # SS-26 wavelength versus arrival time
    ds = downsample(ph, max_points, seed)
    fig, ax = plt.subplots(figsize=(8, 5))
    hb = ax.hexbin(ds["wavelength_nm"], ds["time_ns"], gridsize=60, mincnt=1, bins="log")
    fig.colorbar(hb, ax=ax, label="log10(arrivals/bin)")
    ax.set_xlabel("Wavelength [nm]")
    ax.set_ylabel("Arrival time [ns]")
    add("SS-26", "Photon wavelength-time structure", fig, "wavelength_vs_time", ds[["sensor", "wavelength_nm", "time_ns", "path_length_mm", "detected"]])

    return records


def write_manifest(out: Path, inputs: list[Path], args: argparse.Namespace) -> None:
    outputs = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            outputs.append(
                {"path": str(p.relative_to(out)), "sha256": sha256(p), "bytes": p.stat().st_size}
            )
    manifest = {
        "schema": "ccb-single-stave-diagnostics/2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv,
        "args": vars(args) | {"output": str(args.output)},
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "inputs": [
            {"path": str(p.resolve()), "sha256": sha256(p), "bytes": p.stat().st_size}
            for p in inputs
        ],
        "outputs": outputs,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    event_paths = expand_paths(args.events)
    photon_paths = expand_paths(args.photons) if args.photons else []

    raw_events = load_events(event_paths, args.tree)
    events = normalize_events(raw_events)
    raw_photons = load_photons(event_paths, photon_paths, args.photon_tree)
    photons = normalize_photons(raw_photons) if not raw_photons.empty else pd.DataFrame()

    event_validation = validate_events(events)
    photon_validation = validate_photons(photons, events)
    plot_records, summary, calibration = make_event_plots(
        events, args.output, args.bins, args.max_display_points, args.seed
    )
    plot_records.extend(
        make_photon_plots(photons, args.output, args.bins, args.max_display_points, args.seed)
    )

    events.to_csv(args.output / "events_normalized.csv.gz", index=False)
    if not photons.empty:
        photons.to_csv(args.output / "photons_normalized.csv.gz", index=False)

    result = {
        "schema": "ccb-single-stave-diagnostics-result/2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "event_validation": event_validation,
        "photon_validation": photon_validation,
        "calibration": calibration,
        "n_events": int(len(events)),
        "n_photons": int(len(photons)),
        "plot_records": [r.__dict__ for r in plot_records],
        "status": (
            "FAIL"
            if not event_validation["passed"] or not photon_validation["passed"]
            else "WARN"
            if event_validation["warnings"] or photon_validation["warnings"]
            else "PASS"
        ),
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    write_manifest(args.output, event_paths + photon_paths, args)

    if calibration.get("model_comparison", {}).get("line"):
        print("MODEL_COMPARISON " + calibration["model_comparison"]["line"], file=sys.stderr)

    print(json.dumps(result, indent=2))
    if result["status"] == "FAIL":
        return 2
    if args.strict and result["status"] == "WARN":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
