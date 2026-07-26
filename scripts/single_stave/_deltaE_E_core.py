#!/usr/bin/env python3
"""
Canonical Delta-E versus E (dE/dx particle-identification) analysis for the CCB
test-beam single-stave / B-stack data and Monte Carlo.

This module is the correct replacement for the absent / unsafe
``supervisor_deltaE_E.py`` (audit finding A-002, audit item #8). It fixes the
concrete defects that motivated the re-audit:

  * The event key is COMPOSITE ``(source_file_id, run_id, event_id)``. Joins are
    NEVER performed on ``event_id`` alone. Two different runs that happen to
    reuse the same event number must never merge into a single row.
  * ``--stop-thresholds`` / ``--data-thresholds`` are actually USED to define the
    stored stopping distributions (the old code declared them and ignored them).
  * The stopping layer is the DEEPEST layer whose signal passes the threshold,
    not "the deepest layer with any deposit" (which is noise / secondary
    sensitive).
  * Missing downstream bars are mapped to zero ONLY AFTER event-key validation.
  * Units are kept strictly distinct: data ADC amplitudes are never relabeled as
    MeV; MC energy deposits are never relabeled as ADC.

Everything is offline-testable through a deterministic synthetic fixture
(see ``make_deltaE_fixture.py``). Real data / MC wide event tables live on
LUNARC fs10; this CLI reads them as Parquet or CSV.

Outputs (into ``--out``):
  deltaE_E_events_data.parquet   data-side event table (ADC) + derived cols
  deltaE_E_events_mc.parquet     MC-side event table (MeV) + derived cols
  result.json                    counts, stopping fractions, join report, units
  manifest.json                  provenance (hashes, env, git, args)
  figures/deltaE_E_data_adc.*    hexbin + conditional-median ADC panel
  figures/deltaE_E_mc_mev.*      hexbin + conditional-median MeV panel
  tables/*_profile.csv           per-plot source data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Contract constants
# --------------------------------------------------------------------------- #

#: The event key is composite. Joining on ``event_id`` alone is the bug A-002
#: fixes: different runs reuse event numbers, so a bare-``event_id`` join
#: silently cross-contaminates runs.
KEY_COLS: tuple[str, ...] = ("source_file_id", "run_id", "event_id")

#: Ordered shallow -> deep B layers instrumented on the data side.
DATA_LAYERS: tuple[str, ...] = ("B2", "B4", "B6", "B8")
#: The Delta-E ("thin") layer.
DELTAE_LAYER: str = "B2"
#: The 4-layer E ("thick"/downstream) definition.
E_LAYERS_4: tuple[str, ...] = ("B4", "B6", "B8")

#: Columns that MUST be present (event-key validation happens against these
#: before any missing-bar->0 substitution).
REQUIRED_DATA: tuple[str, ...] = KEY_COLS + ("amp_B2", "sample", "trigger_definition")
REQUIRED_MC: tuple[str, ...] = KEY_COLS + ("edep_B2",)

#: Downstream bars that are FILLED WITH ZERO only *after* key validation.
FILLABLE_DATA_LAYERS: tuple[str, ...] = ("amp_B4", "amp_B6", "amp_B8")
FILLABLE_MC_LAYERS: tuple[str, ...] = ("edep_B4", "edep_B6", "edep_B8")

#: Boolean/flag families that are propagated into the output tables. Missing
#: flags default to False (only after key validation).
DATA_SAT_COLS: tuple[str, ...] = tuple(f"saturation_{b}" for b in DATA_LAYERS)
DATA_THRPASS_COLS: tuple[str, ...] = tuple(f"threshold_pass_{b}" for b in DATA_LAYERS)

#: Default stopping thresholds. Both are CLI-overridable; the defaults are
#: documented, not arbitrary:
#:   MC edep threshold 0.05 MeV ~ a conservative plastic-scintillator hit floor;
#:   data ADC threshold 20 counts ~ pedestal + a few sigma of electronics noise.
#: The multi-value default lets result.json store a stopping distribution at
#: several thresholds so the monotonic-reach guarantee is exercised.
DEFAULT_STOP_THRESHOLDS_MEV: tuple[float, ...] = (0.05, 0.15, 0.30)
DEFAULT_DATA_THRESHOLDS_ADC: tuple[float, ...] = (20.0, 40.0, 80.0)

#: Explicit category label for events where no layer passes the threshold
#: (all-zero / all-subthreshold / missing-downstream reduced to zero).
NO_REACH_CATEGORY: str = "no_layer_passes"

#: Unit labels published in result.json. ADC is NEVER relabeled MeV.
UNIT_LABELS: dict[str, str] = {
    "deltaE_data_adc": "ADC",
    "E_data_adc": "ADC",
    "deltaE_mc_mev": "MeV",
    "E_mc_4layer_mev": "MeV",
    "E_mc_full_mev": "MeV",
}

DEFAULT_SEED = 20260720


class EventKeyError(ValueError):
    """Raised when the composite event key is absent or non-unique."""


# --------------------------------------------------------------------------- #
# CLI parsing / small utilities
# --------------------------------------------------------------------------- #

def parse_thresholds(text: str | Sequence[float]) -> tuple[float, ...]:
    """Parse a comma-separated threshold string into a sorted tuple of floats."""
    if isinstance(text, (list, tuple)):
        vals = [float(v) for v in text]
    else:
        vals = [float(tok) for tok in str(text).split(",") if tok.strip() != ""]
    if not vals:
        raise ValueError("empty threshold list")
    if any(v < 0 for v in vals):
        raise ValueError(f"thresholds must be non-negative: {vals}")
    return tuple(sorted(dict.fromkeys(vals)))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="deltaE_E.py",
        description="Canonical Delta-E vs E analysis for CCB single-stave data + MC.",
    )
    p.add_argument("--data-table", required=True, type=Path,
                   help="Wide DATA event table (parquet/csv) with amp_B*/saturation_B*.")
    p.add_argument("--mc-table", required=True, type=Path,
                   help="Wide MC event table (parquet/csv) with edep_B*.")
    p.add_argument("--out", required=True, type=Path, help="Output directory.")
    p.add_argument("--stop-thresholds", default=",".join(map(str, DEFAULT_STOP_THRESHOLDS_MEV)),
                   help="Comma-separated MC edep thresholds [MeV] defining MC stopping.")
    p.add_argument("--data-thresholds", default=",".join(map(str, DEFAULT_DATA_THRESHOLDS_ADC)),
                   help="Comma-separated data amp thresholds [ADC] defining data stopping.")
    p.add_argument("--sample", default="all", choices=["I", "II", "all"],
                   help="Which sample to select for event tables/figures. Counts for "
                        "BOTH samples are always reported.")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED,
                   help="Deterministic seed for any subsampling.")
    p.add_argument("--bins", type=int, default=16, help="Conditional-profile bin count.")
    return p.parse_args(argv)


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Input table not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".csv", ".txt", ".dat"}:
        return pd.read_csv(path)
    raise SystemExit(f"Unsupported input extension: {suffix} (use .parquet or .csv)")


def _json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


# --------------------------------------------------------------------------- #
# Event-key validation  ->  missing-bar fill  (order matters, see contract)
# --------------------------------------------------------------------------- #

def validate_event_keys(df: pd.DataFrame, name: str) -> None:
    """Assert the composite key exists and is unique. Raises EventKeyError.

    This runs BEFORE any missing-bar -> 0 substitution, so a malformed key can
    never be masked by a downstream fill.
    """
    missing = [c for c in KEY_COLS if c not in df.columns]
    if missing:
        raise EventKeyError(
            f"{name}: missing composite key column(s) {missing}; "
            f"the event key is {KEY_COLS} and must never be event_id alone."
        )
    if df[list(KEY_COLS)].isna().any().any():
        raise EventKeyError(f"{name}: null values present in composite key {KEY_COLS}.")
    dup = int(df.duplicated(list(KEY_COLS)).sum())
    if dup:
        raise EventKeyError(
            f"{name}: {dup} duplicate composite keys {KEY_COLS}; a one-to-one "
            f"join requires the composite key to be unique within each table."
        )


def fill_missing_layers(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    """Ensure ``cols`` exist and are numeric with NaN -> 0. POST-validation only."""
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def fill_missing_flags(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    """Ensure boolean flag columns exist (default False). POST-validation only."""
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = False
        df[c] = df[c].fillna(False).astype(bool)
    return df


# --------------------------------------------------------------------------- #
# Derived quantities  (units strictly separated)
# --------------------------------------------------------------------------- #

def mc_layer_columns(df: pd.DataFrame) -> list[str]:
    """Return edep_B* columns present, ordered shallow->deep by layer number."""
    found = []
    for c in df.columns:
        m = re.fullmatch(r"edep_B(\d+)", str(c))
        if m:
            found.append((int(m.group(1)), c))
    return [c for _, c in sorted(found)]


def derive_data_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add data-side ADC observables. amp_B* stay ADC; never relabeled MeV."""
    df = df.copy()
    df["deltaE_data_adc"] = df[f"amp_{DELTAE_LAYER}"].astype(float)
    df["E_data_adc"] = df[[f"amp_{b}" for b in E_LAYERS_4]].sum(axis=1).astype(float)
    df["saturated_any"] = df[list(DATA_SAT_COLS)].any(axis=1)
    return df


def derive_mc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add MC-side MeV observables (both 4-layer and full-downstream E)."""
    df = df.copy()
    df["deltaE_mc_mev"] = df[f"edep_{DELTAE_LAYER}"].astype(float)
    df["E_mc_4layer_mev"] = df[[f"edep_{b}" for b in E_LAYERS_4]].sum(axis=1).astype(float)
    # Full-downstream: every edep_B layer deeper than the Delta-E layer B2.
    full_cols = [c for c in mc_layer_columns(df) if c != f"edep_{DELTAE_LAYER}"]
    df["E_mc_full_mev"] = (
        df[full_cols].sum(axis=1).astype(float) if full_cols else 0.0
    )
    return df


# --------------------------------------------------------------------------- #
# Stopping layer / reach  (threshold-defined, monotone by construction)
# --------------------------------------------------------------------------- #

def stopping_layers(values: np.ndarray, threshold: float) -> np.ndarray:
    """Deepest passing-layer index per event (-1 = no layer passes).

    ``values`` is (n_events, n_layers) ordered shallow->deep. Passing means
    ``value >= threshold``. Because raising the threshold can only turn
    ``passing`` from True to False, the deepest passing index is non-increasing
    in the threshold -- this is what makes cumulative reach monotone.
    """
    values = np.asarray(values, dtype=float)
    passing = values >= threshold
    n_layers = values.shape[1]
    idx_grid = np.broadcast_to(np.arange(n_layers), values.shape)
    return np.where(passing, idx_grid, -1).max(axis=1)


def stopping_distribution(
    df: pd.DataFrame, value_cols: Sequence[str], layers: Sequence[str], threshold: float
) -> dict:
    """Cumulative reach + stop-category fractions at one threshold."""
    layers = list(layers)
    values = df[list(value_cols)].to_numpy(dtype=float)
    deepest = stopping_layers(values, threshold)
    n = len(df)
    # Cumulative reach: fraction of events with a passing layer at depth >= j.
    reach = {layers[j]: float((deepest >= j).mean()) if n else 0.0
             for j in range(len(layers))}
    cats = np.where(deepest >= 0, np.array(layers + [NO_REACH_CATEGORY])[deepest], NO_REACH_CATEGORY)
    cat_series = pd.Series(cats)
    frac = {c: float((cat_series == c).mean()) if n else 0.0
            for c in list(layers) + [NO_REACH_CATEGORY]}
    return {
        "threshold": float(threshold),
        "n_events": int(n),
        "reach_by_layer": reach,
        "stop_category_fractions": frac,
        "n_no_layer_passes": int((deepest < 0).sum()),
    }


def assign_stop_category(
    df: pd.DataFrame, value_cols: Sequence[str], layers: Sequence[str], threshold: float
) -> pd.Series:
    """Per-event stopping-layer label (or NO_REACH_CATEGORY)."""
    layers = list(layers)
    values = df[list(value_cols)].to_numpy(dtype=float)
    deepest = stopping_layers(values, threshold)
    labels = np.array(layers + [NO_REACH_CATEGORY])
    return pd.Series(np.where(deepest >= 0, labels[deepest], NO_REACH_CATEGORY), index=df.index)


def check_monotonic_reach(dists: Sequence[dict]) -> bool:
    """True iff cumulative reach is non-increasing as the threshold increases."""
    ordered = sorted(dists, key=lambda d: d["threshold"])
    for lo, hi in zip(ordered, ordered[1:]):
        for layer, r_lo in lo["reach_by_layer"].items():
            if hi["reach_by_layer"].get(layer, 0.0) > r_lo + 1e-12:
                return False
    return True


# --------------------------------------------------------------------------- #
# Sample I / II bookkeeping
# --------------------------------------------------------------------------- #

_SAMPLE_TOKEN = re.compile(r"[,;/\s]+")


def sample_tokens(value) -> set[str]:
    """Normalize a ``sample`` cell into the set of sample tags it belongs to."""
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return set()
    out = set()
    for tok in _SAMPLE_TOKEN.split(str(value).strip()):
        t = tok.strip().upper().lstrip("SAMPLE").strip().lstrip("-_ ").strip()
        if t in {"I", "1"}:
            out.add("I")
        elif t in {"II", "2"}:
            out.add("II")
    return out


def sample_membership(df: pd.DataFrame) -> tuple[set, set]:
    """Return (keys_in_I, keys_in_II) as sets of composite-key tuples."""
    keys = list(map(tuple, df[list(KEY_COLS)].to_numpy()))
    in_i, in_ii = set(), set()
    for key, raw in zip(keys, df["sample"].tolist()):
        tags = sample_tokens(raw)
        if "I" in tags:
            in_i.add(key)
        if "II" in tags:
            in_ii.add(key)
    return in_i, in_ii


def sample_counts(df: pd.DataFrame) -> dict:
    in_i, in_ii = sample_membership(df)
    return {
        "sample_I_inclusive": len(in_i),
        "sample_II_inclusive": len(in_ii),
        "sample_I_exclusive": len(in_i - in_ii),
        "sample_II_exclusive": len(in_ii - in_i),
        "in_both": len(in_i & in_ii),
        "sample_I_subset_of_II": in_i.issubset(in_ii),
    }


def select_sample(df: pd.DataFrame, which: str) -> pd.DataFrame:
    if which == "all":
        return df
    tag = "I" if which == "I" else "II"
    mask = df["sample"].map(lambda v: tag in sample_tokens(v))
    return df.loc[mask].copy()


# --------------------------------------------------------------------------- #
# Composite-key join
# --------------------------------------------------------------------------- #

def composite_merge(data: pd.DataFrame, mc: pd.DataFrame) -> pd.DataFrame:
    """One-to-one merge on the COMPOSITE key.

    Merging on all of ``(source_file_id, run_id, event_id)`` guarantees that two
    runs reusing the same ``event_id`` stay as separate rows. ``validate`` makes
    pandas raise if either side is not unique on the composite key.
    """
    return data.merge(
        mc, on=list(KEY_COLS), how="outer", validate="one_to_one",
        suffixes=("_data", "_mc"), indicator=True,
    )


def join_report(data: pd.DataFrame, mc: pd.DataFrame, merged: pd.DataFrame) -> dict:
    ind = merged["_merge"].value_counts()
    # event_ids that recur across >1 run within the data side.
    per_eid_runs = data.groupby("event_id")["run_id"].nunique()
    shared = per_eid_runs[per_eid_runs > 1]
    shared_rows = int(data["event_id"].isin(shared.index).sum())
    return {
        "key": list(KEY_COLS),
        "validate": "one_to_one",
        "n_data": int(len(data)),
        "n_mc": int(len(mc)),
        "n_matched": int(ind.get("both", 0)),
        "n_data_only": int(ind.get("left_only", 0)),
        "n_mc_only": int(ind.get("right_only", 0)),
        "event_ids_shared_across_runs": int(len(shared)),
        "data_rows_for_shared_event_ids": shared_rows,
        # Composite key keeps those rows separate; collapsing them would be the bug.
        "cross_run_collision": bool(len(merged) < len(data) and len(shared) > 0
                                    and int(ind.get("both", 0)) < shared_rows),
    }


# --------------------------------------------------------------------------- #
# Plotting  (density, not raw scatter)
# --------------------------------------------------------------------------- #

def conditional_profile(df: pd.DataFrame, xcol: str, ycol: str, bins: int) -> pd.DataFrame:
    valid = df[[xcol, ycol]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < max(10, bins):
        return pd.DataFrame()
    edges = np.unique(np.quantile(valid[xcol], np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return pd.DataFrame()
    binned = pd.cut(valid[xcol], edges, include_lowest=True, duplicates="drop")
    return (
        valid.groupby(binned, observed=True)
        .agg(
            x_median=(xcol, "median"),
            y_median=(ycol, "median"),
            y_p16=(ycol, lambda s: float(np.quantile(s, 0.16))),
            y_p84=(ycol, lambda s: float(np.quantile(s, 0.84))),
            n=(ycol, "size"),
        )
        .reset_index(drop=True)
    )


def _panel(df, xcol, ycol, xlabel, ylabel, title, bins, fig_base, tab_path,
           sat_lines: tuple[float | None, float | None] = (None, None)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    x = df[xcol].to_numpy(float)
    y = df[ycol].to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]

    fig = plt.figure(figsize=(9, 7))
    gs = GridSpec(4, 4, hspace=0.05, wspace=0.05)
    ax = fig.add_subplot(gs[1:, :3])
    ax_top = fig.add_subplot(gs[0, :3], sharex=ax)
    ax_right = fig.add_subplot(gs[1:, 3], sharey=ax)

    prof = conditional_profile(df.loc[ok if len(df) == len(ok) else df.index], xcol, ycol, bins) \
        if len(df) == ok.size else conditional_profile(df, xcol, ycol, bins)

    if x.size:
        hb = ax.hexbin(x, y, gridsize=45, mincnt=1, bins="log", cmap="viridis")
        fig.colorbar(hb, ax=ax_right, label="log10(events / bin)", fraction=0.15, pad=0.02)
    if not prof.empty:
        ax.plot(prof["x_median"], prof["y_median"], color="white", lw=2.2, label="median")
        ax.fill_between(prof["x_median"], prof["y_p16"], prof["y_p84"],
                        color="white", alpha=0.28, label="16-84%")
        prof.to_csv(tab_path, index=False)
        ax.legend(loc="upper right", framealpha=0.7)
    y_sat, x_sat = sat_lines
    if x_sat is not None and np.isfinite(x_sat):
        ax.axvline(x_sat, color="crimson", ls="--", lw=1.2)
        ax.text(x_sat, ax.get_ylim()[1], " E saturation onset", color="crimson",
                va="top", ha="left", fontsize=8)
    if y_sat is not None and np.isfinite(y_sat):
        ax.axhline(y_sat, color="darkorange", ls="--", lw=1.2)
        ax.text(ax.get_xlim()[1], y_sat, "dE saturation onset ", color="darkorange",
                va="bottom", ha="right", fontsize=8)

    if x.size:
        ax_top.hist(x, bins=40, color="#4c72b0")
        ax_right.hist(y, bins=40, orientation="horizontal", color="#4c72b0")
    ax_top.tick_params(labelbottom=False)
    ax_right.tick_params(labelleft=False)
    ax_top.set_ylabel("count")
    ax_right.set_xlabel("count")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax_top.set_title(title)

    fig.savefig(fig_base.with_suffix(".png"), dpi=200, bbox_inches="tight")
    fig.savefig(fig_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def make_figures(data: pd.DataFrame, mc: pd.DataFrame, out: Path, bins: int) -> list[dict]:
    figdir = out / "figures"
    tabdir = out / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    # Data-side (ADC). Saturation onset = smallest amplitude among flagged events.
    sat = data.loc[data["saturated_any"]]
    y_sat = float(sat["deltaE_data_adc"].min()) if len(sat) else None
    x_sat = float(sat["E_data_adc"].min()) if len(sat) else None
    _panel(
        data, "E_data_adc", "deltaE_data_adc",
        "E = amp_B4 + amp_B6 + amp_B8  [ADC]", "dE = amp_B2  [ADC]",
        "CCB dE-E : DATA (ADC, units never MeV)", bins,
        figdir / "deltaE_E_data_adc", tabdir / "deltaE_E_data_adc_profile.csv",
        sat_lines=(y_sat, x_sat),
    )
    records.append({"plot_id": "deltaE_E_data_adc",
                    "units": "ADC",
                    "source_data": "tables/deltaE_E_data_adc_profile.csv"})

    # MC-side (MeV, 4-layer E). Truth energy: no saturation lines.
    _panel(
        mc, "E_mc_4layer_mev", "deltaE_mc_mev",
        "E = edep_B4 + edep_B6 + edep_B8  [MeV]", "dE = edep_B2  [MeV]",
        "CCB dE-E : MC (MeV, truth energy)", bins,
        figdir / "deltaE_E_mc_mev", tabdir / "deltaE_E_mc_mev_profile.csv",
    )
    records.append({"plot_id": "deltaE_E_mc_mev",
                    "units": "MeV",
                    "source_data": "tables/deltaE_E_mc_mev_profile.csv"})
    return records


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def prepare_data_side(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_DATA if c not in raw.columns]
    if missing:
        raise SystemExit(f"DATA table missing required columns: {missing}")
    validate_event_keys(raw, "DATA")                     # 1. validate keys FIRST
    df = fill_missing_layers(raw, FILLABLE_DATA_LAYERS)  # 2. then fill bars -> 0
    df["amp_B2"] = pd.to_numeric(df["amp_B2"], errors="coerce").fillna(0.0)
    df = fill_missing_flags(df, DATA_SAT_COLS)
    df = fill_missing_flags(df, DATA_THRPASS_COLS)
    return derive_data_columns(df)


def prepare_mc_side(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_MC if c not in raw.columns]
    if missing:
        raise SystemExit(f"MC table missing required columns: {missing}")
    validate_event_keys(raw, "MC")                       # 1. validate keys FIRST
    df = fill_missing_layers(raw, FILLABLE_MC_LAYERS)    # 2. then fill bars -> 0
    df["edep_B2"] = pd.to_numeric(df["edep_B2"], errors="coerce").fillna(0.0)
    return derive_mc_columns(df)


def analyze(
    data_raw: pd.DataFrame,
    mc_raw: pd.DataFrame,
    stop_thresholds: Sequence[float],
    data_thresholds: Sequence[float],
    sample: str,
    seed: int,
) -> dict:
    """Pure, file-free core: returns (result, prepared_data, prepared_mc, merged)."""
    data = prepare_data_side(data_raw)
    mc = prepare_mc_side(mc_raw)

    # Stopping category on the PRIMARY (lowest) threshold, stored per event.
    data_layers_cols = [f"amp_{b}" for b in DATA_LAYERS]
    mc_layers_cols = mc_layer_columns(mc)
    mc_layer_names = [c.replace("edep_", "") for c in mc_layers_cols]

    primary_data_t = float(sorted(data_thresholds)[0])
    primary_mc_t = float(sorted(stop_thresholds)[0])
    data["stop_layer"] = assign_stop_category(data, data_layers_cols, DATA_LAYERS, primary_data_t)
    data["stop_threshold_adc"] = primary_data_t
    mc["stop_layer"] = assign_stop_category(mc, mc_layers_cols, mc_layer_names, primary_mc_t)
    mc["stop_threshold_mev"] = primary_mc_t

    # Full stopping distributions across all thresholds -> monotonicity check.
    data_dists = [stopping_distribution(data, data_layers_cols, DATA_LAYERS, t)
                  for t in sorted(data_thresholds)]
    mc_dists = [stopping_distribution(mc, mc_layers_cols, mc_layer_names, t)
                for t in sorted(stop_thresholds)]

    merged = composite_merge(data, mc)
    jreport = join_report(data, mc, merged)

    scounts = sample_counts(data)

    result = {
        "study_id": "CCB-DELTAE-E",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "seed": int(seed),
        "sample_selected": sample,
        "unit_labels": UNIT_LABELS,
        "n_data_events": int(len(data)),
        "n_mc_events": int(len(mc)),
        "sample_counts": scounts,
        "thresholds": {
            "data_thresholds_adc": [float(t) for t in sorted(data_thresholds)],
            "stop_thresholds_mev": [float(t) for t in sorted(stop_thresholds)],
            "primary_data_threshold_adc": primary_data_t,
            "primary_stop_threshold_mev": primary_mc_t,
        },
        "stopping": {
            "data_adc": {
                "layers": list(DATA_LAYERS),
                "distributions": data_dists,
                "monotonic_reach": check_monotonic_reach(data_dists),
            },
            "mc_mev": {
                "layers": mc_layer_names,
                "distributions": mc_dists,
                "monotonic_reach": check_monotonic_reach(mc_dists),
            },
        },
        "saturation": {
            "any_saturation_events": int(data["saturated_any"].sum()),
            "per_layer": {b: int(data[f"saturation_{b}"].sum()) for b in DATA_LAYERS},
        },
        "join_cardinality": jreport,
    }
    result["status"] = (
        "PASS" if (result["stopping"]["data_adc"]["monotonic_reach"]
                   and result["stopping"]["mc_mev"]["monotonic_reach"]
                   and not jreport["cross_run_collision"])
        else "FAIL_INVARIANT"
    )
    return {"result": result, "data": data, "mc": mc, "merged": merged}


def write_manifest(out: Path, args: argparse.Namespace, inputs: list[Path]) -> None:
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "command": sys.argv,
        "args": {
            "data_table": str(args.data_table),
            "mc_table": str(args.mc_table),
            "out": str(args.out),
            "stop_thresholds": args.stop_thresholds,
            "data_thresholds": args.data_thresholds,
            "sample": args.sample,
            "seed": args.seed,
            "bins": args.bins,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": [{"path": str(p.resolve()), "sha256": sha256(p)} for p in inputs],
        "outputs": [],
    }
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            manifest["outputs"].append(
                {"path": str(p.relative_to(out)), "sha256": sha256(p)}
            )
    (out / "manifest.json").write_text(json.dumps(_json_safe(manifest), indent=2, sort_keys=True),
                                       encoding="utf-8")


def _write_table(df: pd.DataFrame, base: Path) -> Path:
    try:
        path = base.with_suffix(".parquet")
        df.to_parquet(path, index=False)
        return path
    except Exception:
        path = base.with_suffix(".csv.gz")
        df.to_csv(path, index=False)
        return path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        stop_thresholds = parse_thresholds(args.stop_thresholds)
        data_thresholds = parse_thresholds(args.data_thresholds)
    except ValueError as exc:
        raise SystemExit(f"Invalid thresholds: {exc}")

    args.out.mkdir(parents=True, exist_ok=True)
    data_raw = read_table(args.data_table)
    mc_raw = read_table(args.mc_table)

    try:
        bundle = analyze(data_raw, mc_raw, stop_thresholds, data_thresholds,
                         args.sample, args.seed)
    except EventKeyError as exc:
        raise SystemExit(f"Event-key validation failed: {exc}")

    result = bundle["result"]
    data, mc = bundle["data"], bundle["mc"]

    # --sample selects what is stored / plotted; counts already cover both.
    data_sel = select_sample(data, args.sample)
    # MC selection follows data-side sample membership via composite key.
    if args.sample != "all":
        sel_keys = set(map(tuple, data_sel[list(KEY_COLS)].to_numpy()))
        mc_sel = mc[mc[list(KEY_COLS)].apply(tuple, axis=1).isin(sel_keys)].copy()
    else:
        mc_sel = mc

    result["plot_records"] = make_figures(data_sel, mc_sel, args.out, args.bins)

    dp = _write_table(
        data_sel[[*KEY_COLS, "sample", "trigger_definition",
                  "deltaE_data_adc", "E_data_adc", *[f"amp_{b}" for b in DATA_LAYERS],
                  *DATA_SAT_COLS, "saturated_any", "stop_layer", "stop_threshold_adc"]],
        args.out / "deltaE_E_events_data",
    )
    mp = _write_table(
        mc_sel[[*KEY_COLS,
                "deltaE_mc_mev", "E_mc_4layer_mev", "E_mc_full_mev",
                *mc_layer_columns(mc_sel), "stop_layer", "stop_threshold_mev"]],
        args.out / "deltaE_E_events_mc",
    )
    result["event_tables"] = {"data": dp.name, "mc": mp.name}

    (args.out / "result.json").write_text(
        json.dumps(_json_safe(result), indent=2, sort_keys=True), encoding="utf-8"
    )
    write_manifest(args.out, args, [args.data_table, args.mc_table])

    print(json.dumps(_json_safe({
        "status": result["status"],
        "n_data_events": result["n_data_events"],
        "n_mc_events": result["n_mc_events"],
        "sample_counts": result["sample_counts"],
        "join_cardinality": result["join_cardinality"],
    }), indent=2))
    print(f"Wrote {args.out}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
