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
  * Deepest-active / deepest-edep proxies use the DEEPEST layer whose signal
    passes the threshold (strict ``>``), not "any deposit". DATA reports
    ``deepest_active_stave``; MC deposit proxy reports ``deepest_edep_layer``
    (not primary-stop truth).
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

#: Per-event MC generator/importance weight (issue #880 / #1022).
MC_WEIGHT_COL: str = "PrimaryWeight"
#: Accepted aliases for the MC weight column (first present wins after PrimaryWeight).
MC_WEIGHT_ALIASES: tuple[str, ...] = ("PrimaryWeight", "event_weight", "weight")

#: Shared hit/reach comparison rule for DATA+MC (issue #1048).
#: Supervisor wording is "Edep > threshold"; canonical path must match.
THRESHOLD_COMPARISON_RULE: str = ">"
THRESHOLD_COMPARISON_SCHEMA_VERSION: str = "dee-threshold-cmp-v1"

#: Sample-label grammar schema version (issue #1024).
SAMPLE_LABEL_SCHEMA_VERSION: str = "dee-sample-label-v1"

#: Boolean flag schema version (issue #1025).
FLAG_SCHEMA_VERSION: str = "dee-bool-flag-v1"

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
#:   data ADC thresholds 500–1500 (#618/#887/#1026 physics scan; S00 cut is 1000).
#: The multi-value default lets result.json store a stopping distribution at
#: several thresholds so the monotonic-reach guarantee is exercised.
DEFAULT_STOP_THRESHOLDS_MEV: tuple[float, ...] = (0.05, 0.15, 0.30)
DEFAULT_DATA_THRESHOLDS_ADC: tuple[float, ...] = (500.0, 750.0, 1000.0, 1500.0)  # #618/#887/#1026

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
    """Parse a comma-separated threshold string into a sorted tuple of floats.

    Rejects NaN/Inf/overflow-to-Inf (issue #1030): a nonfinite threshold makes
    every comparison false and can still pass structural invariants.
    """
    if isinstance(text, (list, tuple)):
        vals = [float(v) for v in text]
    else:
        vals = [float(tok) for tok in str(text).split(",") if tok.strip() != ""]
    if not vals:
        raise ValueError("empty threshold list")
    if any(not np.isfinite(v) for v in vals):
        raise ValueError(f"thresholds must be finite: {vals}")
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


_TRUE_TOKENS = frozenset({"1", "TRUE", "T", "YES", "Y"})
_FALSE_TOKENS = frozenset({"0", "FALSE", "F", "NO", "N"})


def parse_bool_flag(value) -> bool:
    """Parse one saturation/threshold flag under a finite schema (issue #1025).

    Accepted: native bool, integer/float 0/1, and exact lexical tokens
    true/false/t/f/yes/no/y/n (case-insensitive). Rejects truthiness traps
    such as the string ``"False"`` being coerced via ``astype(bool)``.
    """
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        if int(value) in (0, 1):
            return bool(int(value))
        raise ValueError(f"invalid boolean flag integer: {value!r}")
    if isinstance(value, (float, np.floating)):
        if float(value) in (0.0, 1.0):
            return bool(int(value))
        raise ValueError(f"invalid boolean flag float: {value!r}")
    tok = str(value).strip().upper()
    if tok == "":
        return False
    if tok in _TRUE_TOKENS:
        return True
    if tok in _FALSE_TOKENS:
        return False
    raise ValueError(f"invalid boolean flag token: {value!r}")


def fill_missing_flags(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    """Ensure boolean flag columns exist (default False). POST-validation only.

    Missing whole columns default to False under the current producer contract
    (absence means not flagged). Present cells are parsed by ``parse_bool_flag``.
    """
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = False
            continue
        parsed = []
        for idx, raw in enumerate(df[c].tolist()):
            try:
                if raw is None or (isinstance(raw, float) and not np.isfinite(raw)):
                    parsed.append(False)
                elif isinstance(raw, str) and raw.strip() == "":
                    parsed.append(False)
                else:
                    # pandas NA
                    try:
                        if pd.isna(raw):
                            parsed.append(False)
                            continue
                    except (TypeError, ValueError):
                        pass
                    parsed.append(parse_bool_flag(raw))
            except ValueError as exc:
                raise ValueError(f"column {c!r} row {idx}: {exc}") from exc
        df[c] = np.asarray(parsed, dtype=bool)
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

def passes_threshold(value, threshold: float) -> bool | np.ndarray:
    """Shared hit/reach comparator (issue #1048). Rule: strict ``>``."""
    if THRESHOLD_COMPARISON_RULE != ">":
        raise ValueError(
            f"unsupported THRESHOLD_COMPARISON_RULE={THRESHOLD_COMPARISON_RULE!r}"
        )
    return np.asarray(value) > threshold


def stopping_layers(values: np.ndarray, threshold: float) -> np.ndarray:
    """Deepest passing-layer index per event (-1 = no layer passes).

    ``values`` is (n_events, n_layers) ordered shallow->deep. Passing means
    ``value > threshold`` (strict; matches supervisor / issue #1048). Raising
    the threshold can only turn ``passing`` from True to False, so the deepest
    passing index is non-increasing in the threshold -- cumulative reach is
    monotone.
    """
    values = np.asarray(values, dtype=float)
    passing = passes_threshold(values, threshold)
    n_layers = values.shape[1]
    idx_grid = np.broadcast_to(np.arange(n_layers), values.shape)
    return np.where(passing, idx_grid, -1).max(axis=1)


def _normalized_weights(weights: np.ndarray | None, n: int) -> np.ndarray:
    if weights is None:
        return np.ones(n, dtype=float)
    w = np.asarray(weights, dtype=float)
    if w.shape != (n,):
        raise ValueError(f"weight length {w.shape} != n_events {n}")
    return w


def weighted_mean_indicator(mask: np.ndarray, weights: np.ndarray) -> float:
    """Weighted fraction ``sum(w I) / sum(w)`` for nonnegative finite weights."""
    w = np.asarray(weights, dtype=float)
    m = np.asarray(mask, dtype=bool)
    denom = float(w.sum())
    if denom <= 0.0:
        return 0.0
    return float(w[m].sum() / denom)


def stopping_distribution(
    df: pd.DataFrame,
    value_cols: Sequence[str],
    layers: Sequence[str],
    threshold: float,
    weights: np.ndarray | Sequence[float] | None = None,
) -> dict:
    """Cumulative reach + category fractions at one threshold.

    When ``weights`` is provided (MC measure, issue #1022), fractions are
    ``sum(w I)/sum(w)``. Unweighted DATA paths leave ``weights=None``.
    """
    layers = list(layers)
    values = df[list(value_cols)].to_numpy(dtype=float)
    deepest = stopping_layers(values, threshold)
    n = len(df)
    w = _normalized_weights(None if weights is None else np.asarray(weights, dtype=float), n)
    reach = {
        layers[j]: weighted_mean_indicator(deepest >= j, w) if n else 0.0
        for j in range(len(layers))
    }
    cats = np.where(
        deepest >= 0,
        np.array(layers + [NO_REACH_CATEGORY])[deepest],
        NO_REACH_CATEGORY,
    )
    frac = {
        c: weighted_mean_indicator(cats == c, w) if n else 0.0
        for c in list(layers) + [NO_REACH_CATEGORY]
    }
    n_no = int((deepest < 0).sum())
    w_no = float(w[deepest < 0].sum()) if n else 0.0
    out = {
        "threshold": float(threshold),
        "n_events": int(n),
        "reach_by_layer": reach,
        "stop_category_fractions": frac,
        "n_no_layer_passes": n_no,
        "comparison_rule": THRESHOLD_COMPARISON_RULE,
        "comparison_rule_schema": THRESHOLD_COMPARISON_SCHEMA_VERSION,
    }
    if weights is not None:
        out["weighted_no_layer_passes_mass"] = w_no
        out["sum_w"] = float(w.sum())
    return out


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
# Finite authorised grammar only (issue #1024). No character-set lstrip.
_SAMPLE_EXACT = {
    "I": "I",
    "1": "I",
    "SAMPLEI": "I",
    "SAMPLE-I": "I",
    "SAMPLE_I": "I",
    "II": "II",
    "2": "II",
    "SAMPLEII": "II",
    "SAMPLE-II": "II",
    "SAMPLE_II": "II",
}


def sample_tokens(value) -> set[str]:
    """Normalize a ``sample`` cell into ``{I, II}`` under a finite grammar.

    Authorised forms (case-insensitive, optional surrounding whitespace):
    ``I``, ``II``, ``1``, ``2``, ``Sample I``, ``Sample-II``, ``SAMPLE_I``, …
    Malformed tokens such as ``P1`` / ``L2`` (formerly accepted via
    ``lstrip("SAMPLE")`` charset stripping) are ignored / invalid.
    """
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return set()
    out = set()
    for tok in _SAMPLE_TOKEN.split(str(value).strip()):
        raw = tok.strip()
        if not raw:
            continue
        key = re.sub(r"[\s]+", "", raw.upper())
        # Allow a single hyphen/underscore between SAMPLE and roman/digit only
        # via the explicit map keys; do not strip arbitrary SAMPLE charset chars.
        mapped = _SAMPLE_EXACT.get(key)
        if mapped is None:
            # Also accept "SAMPLE I" after removing internal spaces already done;
            # reject everything else (no fuzzy repair).
            continue
        out.add(mapped)
    return out


def sample_token_census(df: pd.DataFrame) -> dict:
    """Count valid/invalid sample labels for provenance (issue #1024)."""
    n_invalid = 0
    examples: list[str] = []
    if "sample" not in df.columns:
        return {
            "schema_version": SAMPLE_LABEL_SCHEMA_VERSION,
            "n_invalid_labels": 0,
            "invalid_examples": [],
        }
    for raw in df["sample"].tolist():
        if raw is None or (isinstance(raw, float) and not np.isfinite(raw)):
            continue
        text_v = str(raw).strip()
        if text_v == "":
            continue
        parts = [p for p in _SAMPLE_TOKEN.split(text_v) if p.strip()]
        if not parts:
            continue
        ok = True
        for part in parts:
            key = re.sub(r"[\s]+", "", part.strip().upper())
            if key not in _SAMPLE_EXACT:
                ok = False
                break
        if not ok:
            n_invalid += 1
            if len(examples) < 5:
                examples.append(text_v)
    return {
        "schema_version": SAMPLE_LABEL_SCHEMA_VERSION,
        "n_invalid_labels": int(n_invalid),
        "invalid_examples": examples,
    }


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

    weights = None
    if "weights" in df.columns and x.size:
        # Align weights to finite (x,y) mask used above.
        w_all = df["weights"].to_numpy(dtype=float)
        if w_all.shape[0] == ok.shape[0]:
            weights = w_all[ok]
    if x.size:
        if weights is not None and np.all(np.isfinite(weights)) and float(np.sum(weights)) > 0:
            hb = ax.hexbin(
                x, y, C=weights, reduce_C_function=np.sum,
                gridsize=45, mincnt=1, bins="log", cmap="viridis",
            )
            fig.colorbar(hb, ax=ax_right, label="log10(Σ weight / bin)", fraction=0.15, pad=0.02)
        else:
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

    # Data-side (ADC). Axis-specific saturation onset (issue #1027):
    # Y(dE) from saturation_B2; X(E) from any of B4/B6/B8 saturated.
    sat_y = data.loc[data["saturation_B2"]]
    sat_x = data.loc[data[["saturation_B4", "saturation_B6", "saturation_B8"]].any(axis=1)]
    y_sat = float(sat_y["deltaE_data_adc"].min()) if len(sat_y) else None
    x_sat = float(sat_x["E_data_adc"].min()) if len(sat_x) else None
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

    # MC-side (MeV, 4-layer E). Weighted density when PrimaryWeight present (#1022).
    mc_plot = mc.copy()
    if MC_WEIGHT_COL in mc_plot.columns:
        mc_plot["weights"] = mc_plot[MC_WEIGHT_COL]
    _panel(
        mc_plot, "E_mc_4layer_mev", "deltaE_mc_mev",
        "E = edep_B4 + edep_B6 + edep_B8  [MeV]", "dE = edep_B2  [MeV]",
        "CCB dE-E : MC (MeV, PrimaryWeight-weighted)", bins,
        figdir / "deltaE_E_mc_mev", tabdir / "deltaE_E_mc_mev_profile.csv",
    )
    records.append({"plot_id": "deltaE_E_mc_mev",
                    "units": "MeV",
                    "source_data": "tables/deltaE_E_mc_mev_profile.csv"})
    return records




def resolve_mc_weight_column(df: pd.DataFrame) -> str:
    """Return the declared MC weight column name or raise (issue #1022)."""
    for name in MC_WEIGHT_ALIASES:
        if name in df.columns:
            return name
    raise SystemExit(
        f"MC table missing required weight column; expected one of {MC_WEIGHT_ALIASES} "
        f"(issue #880/#1022). Unweighted MC is not authorising for ΔE–E."
    )


def attach_mc_weights(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and canonicalise ``PrimaryWeight`` on the prepared MC table."""
    df = df.copy()
    src = resolve_mc_weight_column(df)
    raw = pd.to_numeric(df[src], errors="coerce").to_numpy(dtype=float)
    if raw.size == 0:
        raise SystemExit("MC weight vector is empty")
    if not np.all(np.isfinite(raw)):
        bad = np.flatnonzero(~np.isfinite(raw))[:5].tolist()
        raise SystemExit(f"MC weights contain nonfinite values at rows {bad}")
    if np.any(raw < 0.0):
        raise SystemExit(
            "MC weights contain negative values; ordinary probability estimators "
            "are rejected for signed weights (issue #1022)"
        )
    if float(raw.sum()) <= 0.0:
        raise SystemExit("MC weights have non-positive total mass")
    df[MC_WEIGHT_COL] = raw
    return df


def mc_weight_diagnostics(weights: np.ndarray) -> dict:
    """Machine-readable weight census: sum(w), sum(w²), ESS (issue #1022)."""
    w = np.asarray(weights, dtype=float)
    sum_w = float(w.sum())
    sum_w2 = float(np.dot(w, w))
    ess = float(sum_w * sum_w / sum_w2) if sum_w2 > 0 else 0.0
    return {
        "weight_variable": MC_WEIGHT_COL,
        "weight_semantics": "per-event generator/importance weight (PrimaryWeight)",
        "n_events": int(w.size),
        "sum_w": sum_w,
        "sum_w2": sum_w2,
        "ess": ess,
        "n_zero": int((w == 0.0).sum()),
        "min_w": float(w.min()) if w.size else None,
        "max_w": float(w.max()) if w.size else None,
        "all_unit_weights": bool(w.size > 0 and np.allclose(w, 1.0)),
    }

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
    # Weight required for authorising MC measure (issue #1022); checked explicitly
    # so the error names the weight contract even when REQUIRED_MC is extended.
    resolve_mc_weight_column(raw)
    validate_event_keys(raw, "MC")                       # 1. validate keys FIRST
    df = fill_missing_layers(raw, FILLABLE_MC_LAYERS)    # 2. then fill bars -> 0
    df["edep_B2"] = pd.to_numeric(df["edep_B2"], errors="coerce").fillna(0.0)
    df = derive_mc_columns(df)
    return attach_mc_weights(df)


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
    # DATA: deepest active readout is not a measured physical stop (#1028).
    data["deepest_active_stave"] = assign_stop_category(
        data, data_layers_cols, DATA_LAYERS, primary_data_t
    )
    data["stop_threshold_adc"] = primary_data_t
    # MC: deposit-threshold proxy (not primary-stop truth; #1028/#1029).
    mc["deepest_edep_layer"] = assign_stop_category(
        mc, mc_layers_cols, mc_layer_names, primary_mc_t
    )
    mc["stop_threshold_mev"] = primary_mc_t

    mc_w = mc[MC_WEIGHT_COL].to_numpy(dtype=float)
    wdiag = mc_weight_diagnostics(mc_w)

    # Full distributions across all thresholds -> monotonicity check.
    data_dists = [
        stopping_distribution(data, data_layers_cols, DATA_LAYERS, t)
        for t in sorted(data_thresholds)
    ]
    mc_dists = [
        stopping_distribution(mc, mc_layers_cols, mc_layer_names, t, weights=mc_w)
        for t in sorted(stop_thresholds)
    ]

    merged = composite_merge(data, mc)
    jreport = join_report(data, mc, merged)

    scounts = sample_counts(data)
    sample_census = sample_token_census(data)

    result = {
        "study_id": "CCB-DELTAE-E",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "seed": int(seed),
        "sample_selected": sample,
        "unit_labels": UNIT_LABELS,
        "n_data_events": int(len(data)),
        "n_mc_events": int(len(mc)),
        "sample_counts": scounts,
        "sample_label_census": sample_census,
        "mc_weights": wdiag,
        "threshold_comparison": {
            "rule": THRESHOLD_COMPARISON_RULE,
            "schema_version": THRESHOLD_COMPARISON_SCHEMA_VERSION,
        },
        "measurand_names": {
            "data_deepest_proxy": "deepest_active_stave",
            "mc_deposit_proxy": "deepest_edep_layer",
            "mc_primary_stop_truth": None,
            "note": (
                "DATA deepest_active_stave is the deepest readout above threshold; "
                "MC deepest_edep_layer is event-level deposit proxy, not primary stop."
            ),
        },
        "flag_schema_version": FLAG_SCHEMA_VERSION,
        "thresholds": {
            "data_thresholds_adc": [float(t) for t in sorted(data_thresholds)],
            "stop_thresholds_mev": [float(t) for t in sorted(stop_thresholds)],
            "primary_data_threshold_adc": primary_data_t,
            "primary_stop_threshold_mev": primary_mc_t,
        },
        "stopping": {
            "data_adc": {
                "layers": list(DATA_LAYERS),
                "proxy_name": "deepest_active_stave",
                "distributions": data_dists,
                "monotonic_reach": check_monotonic_reach(data_dists),
            },
            "mc_mev": {
                "layers": mc_layer_names,
                "proxy_name": "deepest_edep_layer",
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
                  *DATA_SAT_COLS, "saturated_any", "deepest_active_stave", "stop_threshold_adc"]],
        args.out / "deltaE_E_events_data",
    )
    mp = _write_table(
        mc_sel[[*KEY_COLS,
                "deltaE_mc_mev", "E_mc_4layer_mev", "E_mc_full_mev",
                *mc_layer_columns(mc_sel), MC_WEIGHT_COL, "deepest_edep_layer", "stop_threshold_mev"]],
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
