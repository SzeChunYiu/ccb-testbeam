#!/usr/bin/env python3
"""S14h: sparse A-stack support calibration for energy proxies.

The analysis rebuilds the A/B event-matched support table from raw HRD ROOT,
then benchmarks transparent binomial support gates against ridge, boosted-tree,
MLP, 1D-CNN, and a new support-gated hybrid CNN.  The split unit is run: every
prediction is made by a model that did not train on the predicted run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml
from scipy.stats import beta, spearmanr
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_squared_error
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


ROOT = Path(__file__).resolve().parents[1]
P04C_PATH = ROOT / "scripts" / "p04c_ab_event_matched_charge_transfer.py"
METHODS = [
    "traditional_exact_binomial",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "support_gated_hybrid_cnn",
]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return None if not math.isfinite(value) else value
    if pd.isna(value):
        return None
    return value


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_p04c_module():
    spec = importlib.util.spec_from_file_location("p04c_ab_event_matched_charge_transfer", P04C_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P04C_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_for_run(run: int) -> str:
    run = int(run)
    if 31 <= run <= 42:
        return "sample_iii_calibration"
    if 44 <= run <= 57:
        return "sample_iii_analysis"
    if run == 64:
        return "sample_iv_calibration"
    if 58 <= run <= 65:
        return "sample_iv_analysis"
    return "other"


def raw_path(config: dict, stack: str, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{stack}_run_{int(run):04d}.root"


def configured_p04_runs(config: dict) -> List[int]:
    ref = load_yaml(Path(config["p04_reference_config"]))
    runs: List[int] = []
    for values in ref["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return lo, hi


def quantile_edges(values: np.ndarray, bins: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return np.array([-np.inf, np.inf])
    edges = np.unique(np.quantile(values, np.linspace(0.0, 1.0, int(bins) + 1)))
    if len(edges) < 2:
        return np.array([-np.inf, np.inf])
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def digitize(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.searchsorted(edges[1:-1], values, side="right").astype(np.int16)


def add_current_strata(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    rate = out.groupby("run")["support_target"].agg(["size", "sum"]).reset_index()
    rate["support_fraction_run"] = rate["sum"] / np.maximum(rate["size"], 1)
    out = out.merge(rate[["run", "support_fraction_run"]], on="run", how="left")
    edges = quantile_edges(out.drop_duplicates("run")["support_fraction_run"].to_numpy(), 3)
    labels = np.asarray(["low_current_proxy", "mid_current_proxy", "high_current_proxy"], dtype=object)
    idx = np.clip(digitize(out["support_fraction_run"].to_numpy(), edges), 0, len(labels) - 1)
    out["current_stratum"] = labels[idx]
    return out


def extract_support_rows(config: dict, p04c) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    sat = float(config["saturation_adc"])
    astaves = list(config["astack"]["staves"].keys())
    bstaves = list(config["bstack"]["staves"].keys())
    ach = [int(config["astack"]["staves"][name]) for name in astaves]
    bch = [int(config["bstack"]["staves"][name]) for name in bstaves]
    rows: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[Dict[str, Any]] = []
    for run in [int(r) for r in config["runs"]]:
        apath = raw_path(config, config["astack"]["file_prefix"], run)
        bpath = raw_path(config, config["bstack"]["file_prefix"], run)
        if not apath.exists() or not bpath.exists():
            continue
        a_evt, _a_wave, a_amp, a_charge, _a_peak = p04c.load_run_stack(apath, ach, config)
        b_evt, b_wave, b_amp, b_charge, b_peak = p04c.load_run_stack(bpath, bch, config)
        common, a_idx, b_idx = np.intersect1d(a_evt, b_evt, assume_unique=False, return_indices=True)
        a_amp = a_amp[a_idx]
        a_charge = a_charge[a_idx]
        b_wave = b_wave[b_idx]
        b_amp = b_amp[b_idx]
        b_charge = b_charge[b_idx]
        b_peak = b_peak[b_idx]
        a_selected = a_amp > cut
        b_selected = b_amp > cut
        denom = b_selected[:, 0]
        idx = np.where(denom)[0]
        counts.append(
            {
                "run": run,
                "matched_events": int(len(common)),
                "b2_selected_denominator": int(denom.sum()),
                "a_any_supported": int((denom & a_selected.any(axis=1)).sum()),
                "a_pair_supported": int((denom & a_selected.all(axis=1)).sum()),
                "b2_and_downstream": int((denom & b_selected[:, 1:].any(axis=1)).sum()),
            }
        )
        if len(idx) == 0:
            continue
        chosen_a_sel = a_selected[idx]
        chosen_a_charge = a_charge[idx]
        chosen_b_sel = b_selected[idx]
        chosen_b_charge = b_charge[idx]
        chosen_b_amp = b_amp[idx]
        chosen_b_peak = b_peak[idx]
        chosen_wave = b_wave[idx].astype(np.float32)
        target_charge = (chosen_a_charge * chosen_a_sel).sum(axis=1)
        support = chosen_a_sel.any(axis=1)
        b_depth = chosen_b_sel.shape[1] - 1 - np.argmax(chosen_b_sel[:, ::-1], axis=1)
        b_down_charge = chosen_b_charge[:, 1:].sum(axis=1)
        b_total = chosen_b_charge.sum(axis=1)
        b2_charge = chosen_b_charge[:, 0]
        b2_amp = chosen_b_amp[:, 0]
        baseline_block = chosen_wave[:, :, [int(i) for i in config["baseline_samples"]]]
        baseline_excursion = np.nanmax(np.abs(baseline_block), axis=(1, 2))
        tail_charge = np.clip(chosen_wave[:, :, 12:], 0.0, None).sum(axis=(1, 2))
        frame = pd.DataFrame(
            {
                "run": run,
                "sample": sample_for_run(run),
                "evt": common[idx].astype(np.int64),
                "support_target": support.astype(np.int16),
                "target_a_charge": np.where(support, target_charge, np.nan),
                "log_target_a_charge": np.where(support, np.log(np.maximum(target_charge, 1.0)), np.nan),
                "a_depth_score": np.where(chosen_a_sel[:, 1], 1.0, 0.0) + np.where(chosen_a_sel.all(axis=1), 0.5, 0.0),
                "a_topology": np.where(chosen_a_sel.all(axis=1), "A1+A3", np.where(chosen_a_sel[:, 0], "A1", np.where(chosen_a_sel[:, 1], "A3", "none"))),
                "b_depth_idx": b_depth.astype(np.int16),
                "b_topology": ["+".join(np.asarray(bstaves, dtype=object)[row]) for row in chosen_b_sel],
                "b_mult": chosen_b_sel.sum(axis=1).astype(np.int16),
                "b_downstream_mult": chosen_b_sel[:, 1:].sum(axis=1).astype(np.int16),
                "b_downstream_charge": b_down_charge,
                "b_downstream_frac": b_down_charge / np.maximum(b_total, 1.0),
                "b_total_charge": b_total,
                "b2_charge": b2_charge,
                "b2_amp": b2_amp,
                "b2_peak": chosen_b_peak[:, 0],
                "b2_saturated": (b2_amp >= sat).astype(np.int16),
                "b_any_saturated": (chosen_b_amp.max(axis=1) >= sat).astype(np.int16),
                "downstream_dropout": (chosen_b_sel[:, 1:].sum(axis=1) == 0).astype(np.int16),
                "baseline_excursion": baseline_excursion,
                "tail_charge_frac": tail_charge / np.maximum(b_total, 1.0),
            }
        )
        for bidx, name in enumerate(bstaves):
            frame[f"{name}_selected"] = chosen_b_sel[:, bidx].astype(np.int16)
            frame[f"{name}_charge"] = chosen_b_charge[:, bidx]
            frame[f"{name}_amp"] = chosen_b_amp[:, bidx]
            frame[f"{name}_peak"] = chosen_b_peak[:, bidx]
        rows.append(frame)
        waves.append(chosen_wave)
    if not rows:
        raise RuntimeError("no support rows extracted")
    frame = add_current_strata(pd.concat(rows, ignore_index=True))
    return frame, np.vstack(waves), pd.DataFrame(counts)


def base_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "log_b2_charge": np.log(np.maximum(frame["b2_charge"].to_numpy(), 1.0)),
            "log_b2_amp": np.log(np.maximum(frame["b2_amp"].to_numpy(), 1.0)),
            "log_b_total": np.log(np.maximum(frame["b_total_charge"].to_numpy(), 1.0)),
            "log_b_downstream": np.log1p(np.maximum(frame["b_downstream_charge"].to_numpy(), 0.0)),
            "b_downstream_frac": frame["b_downstream_frac"].to_numpy(),
            "b_depth_idx": frame["b_depth_idx"].to_numpy(),
            "b_mult": frame["b_mult"].to_numpy(),
            "b_downstream_mult": frame["b_downstream_mult"].to_numpy(),
            "b2_peak": frame["b2_peak"].to_numpy(),
            "b2_saturated": frame["b2_saturated"].to_numpy(),
            "b_any_saturated": frame["b_any_saturated"].to_numpy(),
            "downstream_dropout": frame["downstream_dropout"].to_numpy(),
            "baseline_excursion": np.log1p(frame["baseline_excursion"].to_numpy()),
            "tail_charge_frac": frame["tail_charge_frac"].to_numpy(),
            "run_support_fraction_xonly": frame["support_fraction_run"].to_numpy(),
            "sample_iv": (frame["sample"].to_numpy() == "sample_iv_analysis").astype(float),
        }
    )
    for col in ["B4_selected", "B6_selected", "B8_selected"]:
        out[col] = frame[col].to_numpy()
    return out


def residualize_by_run(x: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    arr = x.to_numpy(dtype=float)
    out = arr.copy()
    for run in sorted(frame["run"].unique()):
        mask = frame["run"].to_numpy() == run
        out[mask] = arr[mask] - np.nanmedian(arr[mask], axis=0)
    return np.column_stack([arr, out])


def waveform_feature_matrix(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    amp = wave.max(axis=2)
    peak = wave.argmax(axis=2)
    tail = np.clip(wave[:, :, 12:], 0.0, None).sum(axis=2) / np.maximum(charge, 1.0)
    width = (wave > (0.5 * amp[:, :, None])).sum(axis=2)
    engineered = np.column_stack([np.log(np.maximum(charge, 1.0)), np.log(np.maximum(amp, 1.0)), peak, tail, width])
    return np.column_stack([residualize_by_run(base_feature_frame(frame), frame), engineered])


def support_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> Dict[str, float]:
    y = np.asarray(y, dtype=bool)
    accepted = np.asarray(p, dtype=float) >= float(threshold)
    true_support = y.sum()
    no_support = (~y).sum()
    return {
        "support_coverage": float((accepted & y).sum() / max(true_support, 1)),
        "abstention_rate": float(1.0 - accepted.mean()),
        "false_support_rate": float((accepted & ~y).sum() / max(no_support, 1)),
        "accepted_fraction": float(accepted.mean()),
    }


def proxy_metrics(frame: pd.DataFrame, pred_log: np.ndarray, p: np.ndarray, threshold: float) -> Dict[str, float]:
    mask = (frame["support_target"].to_numpy(dtype=bool)) & (np.asarray(p) >= threshold)
    if mask.sum() < 5:
        return {
            "proxy_rmse_log": None,
            "proxy_spearman": None,
            "a_depth_high_minus_low_contrast": None,
            "downstream_multiplicity_contrast": None,
        }
    y = frame.loc[mask, "log_target_a_charge"].to_numpy(dtype=float)
    pred = np.asarray(pred_log, dtype=float)[mask]
    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    rho = float(spearmanr(y, pred).correlation)
    a_high = pred[frame.loc[mask, "a_depth_score"].to_numpy(dtype=float) >= 1.0]
    a_low = pred[frame.loc[mask, "a_depth_score"].to_numpy(dtype=float) < 1.0]
    d_high = pred[frame.loc[mask, "b_downstream_mult"].to_numpy(dtype=int) > 0]
    d_low = pred[frame.loc[mask, "b_downstream_mult"].to_numpy(dtype=int) == 0]
    return {
        "proxy_rmse_log": rmse,
        "proxy_spearman": rho if math.isfinite(rho) else None,
        "a_depth_high_minus_low_contrast": float(np.mean(a_high) - np.mean(a_low)) if len(a_high) and len(a_low) else None,
        "downstream_multiplicity_contrast": float(np.mean(d_high) - np.mean(d_low)) if len(d_high) and len(d_low) else None,
    }


def run_stability(frame: pd.DataFrame, p: np.ndarray) -> float:
    tmp = frame[["run"]].copy()
    tmp["p"] = np.asarray(p, dtype=float)
    return float(tmp.groupby("run")["p"].mean().std(ddof=0))


def metric_row(method: str, frame: pd.DataFrame, pred_log: np.ndarray, p: np.ndarray, threshold: float) -> Dict[str, Any]:
    row: Dict[str, Any] = {"method": method, "n": int(len(frame)), "threshold": float(threshold)}
    row.update(support_metrics(frame["support_target"].to_numpy(), p, threshold))
    row.update(proxy_metrics(frame, pred_log, p, threshold))
    row["pid_score_stability_run_sd"] = run_stability(frame, p)
    return row


def run_bootstrap_metrics(
    frame: pd.DataFrame, pred_log: np.ndarray, p: np.ndarray, threshold: float, reps: int, seed: int
) -> Dict[str, List[float]]:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {run: np.where(frame["run"].to_numpy() == run)[0] for run in runs}
    vals: Dict[str, List[float]] = {k: [] for k in ["support_coverage", "abstention_rate", "false_support_rate", "proxy_rmse_log", "proxy_spearman"]}
    for _ in range(int(reps)):
        idx = np.concatenate([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)])
        sub = frame.iloc[idx].reset_index(drop=True)
        row = metric_row("boot", sub, pred_log[idx], p[idx], threshold)
        for key in vals:
            val = row.get(key)
            if val is not None and math.isfinite(float(val)):
                vals[key].append(float(val))
    out: Dict[str, List[float]] = {}
    for key, arr in vals.items():
        if len(arr) == 0:
            out[f"{key}_ci95"] = [None, None]
        else:
            out[f"{key}_ci95"] = [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]
    return out


class TraditionalSupportProxy:
    def __init__(self, config: dict):
        self.config = config
        self.edges: Dict[str, np.ndarray] = {}
        self.tables: List[Tuple[List[str], Dict[Any, Dict[str, float]]]] = []
        self.global_support = 0.0
        self.global_log_proxy = 0.0

    def _with_bins(self, frame: pd.DataFrame, fit: bool) -> pd.DataFrame:
        out = frame.copy()
        if fit:
            self.edges["b2"] = quantile_edges(np.log(np.maximum(out["b2_charge"].to_numpy(), 1.0)), self.config["traditional"]["b2_quantile_bins"])
            positive = np.log1p(out.loc[out["b_downstream_charge"] > 0, "b_downstream_charge"].to_numpy())
            self.edges["bdown"] = quantile_edges(positive, self.config["traditional"]["bdown_quantile_bins"])
            self.edges["baseline"] = quantile_edges(np.log1p(out["baseline_excursion"].to_numpy()), 3)
        out["b2_bin"] = digitize(np.log(np.maximum(out["b2_charge"].to_numpy(), 1.0)), self.edges["b2"])
        out["bdown_bin"] = np.where(
            out["b_downstream_charge"].to_numpy() <= 0,
            -1,
            digitize(np.log1p(out["b_downstream_charge"].to_numpy()), self.edges["bdown"]),
        )
        out["baseline_bin"] = digitize(np.log1p(out["baseline_excursion"].to_numpy()), self.edges["baseline"])
        return out

    def fit(self, frame: pd.DataFrame) -> "TraditionalSupportProxy":
        train = self._with_bins(frame, fit=True)
        self.global_support = float(train["support_target"].mean())
        self.global_log_proxy = float(train.loc[train["support_target"] == 1, "log_target_a_charge"].median())
        hierarchies = [
            ["sample", "current_stratum", "b_depth_idx", "b_downstream_mult", "b2_bin", "bdown_bin", "b2_saturated", "downstream_dropout", "baseline_bin"],
            ["sample", "b_depth_idx", "b_downstream_mult", "b2_bin", "bdown_bin"],
            ["b_depth_idx", "b_downstream_mult", "b2_bin"],
            ["b_depth_idx", "b2_bin"],
            ["sample"],
        ]
        self.tables = []
        for cols in hierarchies:
            table: Dict[Any, Dict[str, float]] = {}
            grouped = train.groupby(cols, observed=True)
            for key, sub in grouped:
                n = int(len(sub))
                k = int(sub["support_target"].sum())
                lo, hi = clopper_pearson(k, n)
                supported = sub[sub["support_target"] == 1]
                proxy = self.global_log_proxy if supported.empty else float(supported["log_target_a_charge"].median())
                table[key if isinstance(key, tuple) else key] = {
                    "n": n,
                    "k": k,
                    "support_mean": k / max(n, 1),
                    "support_lo95": lo,
                    "support_hi95": hi,
                    "proxy": proxy,
                }
            self.tables.append((cols, table))
        return self

    def predict(self, frame: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        test = self._with_bins(frame, fit=False)
        support = np.full(len(test), self.global_support, dtype=float)
        support_lo = np.zeros(len(test), dtype=float)
        proxy = np.full(len(test), self.global_log_proxy, dtype=float)
        min_n = int(self.config["traditional"]["min_bin_n"])
        for i, row in enumerate(test.itertuples(index=False)):
            rowd = row._asdict()
            for cols, table in self.tables:
                key = tuple(rowd[c] for c in cols)
                if len(cols) == 1:
                    key = key[0]
                info = table.get(key)
                if info is not None:
                    support[i] = info["support_mean"]
                    support_lo[i] = info["support_lo95"] if info["n"] >= min_n else 0.0
                    proxy[i] = info["proxy"]
                    break
        gate_p = np.maximum(support, support_lo)
        return gate_p, proxy, support_lo


def fit_tabular_methods(config: dict, frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    x_base = residualize_by_run(base_feature_frame(frame), frame)
    x_wave = waveform_feature_matrix(frame, wave)
    y_support = frame["support_target"].to_numpy(dtype=int)
    y_log = frame["log_target_a_charge"].to_numpy(dtype=float)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    pred_cols: Dict[str, Dict[str, np.ndarray]] = {
        method: {"p": np.full(len(frame), np.nan), "log": np.full(len(frame), np.nan)} for method in METHODS
    }
    pred_cols["charge_only_sentinel"] = {"p": np.full(len(frame), np.nan), "log": np.full(len(frame), np.nan)}
    pred_cols["topology_only_sentinel"] = {"p": np.full(len(frame), np.nan), "log": np.full(len(frame), np.nan)}
    pred_cols["current_only_sentinel"] = {"p": np.full(len(frame), np.nan), "log": np.full(len(frame), np.nan)}
    pred_cols["shuffled_target_sentinel"] = {"p": np.full(len(frame), np.nan), "log": np.full(len(frame), np.nan)}

    for heldout_run in runs:
        train_mask = frame["run"].to_numpy() != heldout_run
        test_mask = ~train_mask
        train_idx_full = np.where(train_mask)[0]
        if len(train_idx_full) > int(config["max_train_rows"]):
            train_idx = rng.choice(train_idx_full, size=int(config["max_train_rows"]), replace=False)
        else:
            train_idx = train_idx_full
        support_idx = train_idx[y_support[train_idx] == 1]
        if len(support_idx) < 20:
            support_idx = np.where(train_mask & (y_support == 1))[0]

        trad = TraditionalSupportProxy(config).fit(frame.iloc[train_idx_full].reset_index(drop=True))
        p, logp, _lo = trad.predict(frame.loc[test_mask].reset_index(drop=True))
        pred_cols["traditional_exact_binomial"]["p"][test_mask] = p
        pred_cols["traditional_exact_binomial"]["log"][test_mask] = logp

        ridge_c = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, class_weight="balanced", C=1.0))
        ridge_r = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ml"]["ridge_alpha"])))
        ridge_c.fit(x_base[train_idx], y_support[train_idx])
        ridge_r.fit(x_base[support_idx], y_log[support_idx])
        pred_cols["ridge"]["p"][test_mask] = ridge_c.predict_proba(x_base[test_mask])[:, 1]
        pred_cols["ridge"]["log"][test_mask] = ridge_r.predict(x_base[test_mask])

        gbt_c = GradientBoostingClassifier(
            n_estimators=int(config["ml"]["gbt_estimators"]),
            max_depth=int(config["ml"]["gbt_max_depth"]),
            random_state=int(config["random_seed"]) + int(heldout_run),
        )
        gbt_r = GradientBoostingRegressor(
            n_estimators=int(config["ml"]["gbt_estimators"]),
            max_depth=int(config["ml"]["gbt_max_depth"]),
            random_state=int(config["random_seed"]) + 100 + int(heldout_run),
        )
        gbt_c.fit(x_wave[train_idx], y_support[train_idx])
        gbt_r.fit(x_wave[support_idx], y_log[support_idx])
        pred_cols["gradient_boosted_trees"]["p"][test_mask] = gbt_c.predict_proba(x_wave[test_mask])[:, 1]
        pred_cols["gradient_boosted_trees"]["log"][test_mask] = gbt_r.predict(x_wave[test_mask])

        mlp_c = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(int(v) for v in config["ml"]["mlp_hidden"]),
                max_iter=80,
                alpha=1e-3,
                random_state=7 + int(heldout_run),
            ),
        )
        mlp_r = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=tuple(int(v) for v in config["ml"]["mlp_hidden"]),
                max_iter=80,
                alpha=1e-3,
                random_state=17 + int(heldout_run),
            ),
        )
        mlp_c.fit(x_base[train_idx], y_support[train_idx])
        mlp_r.fit(x_base[support_idx], y_log[support_idx])
        pred_cols["mlp"]["p"][test_mask] = mlp_c.predict_proba(x_base[test_mask])[:, 1]
        pred_cols["mlp"]["log"][test_mask] = mlp_r.predict(x_base[test_mask])

        charge_cols = [0, 1, 2, 3]
        topo_cols = [5, 6, 7, 9, 10, 11, 15, 16, 17]
        current_cols = [14, 15]
        for name, cols in [
            ("charge_only_sentinel", charge_cols),
            ("topology_only_sentinel", topo_cols),
            ("current_only_sentinel", current_cols),
        ]:
            sent = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, class_weight="balanced"))
            sent.fit(x_base[train_idx][:, cols], y_support[train_idx])
            pred_cols[name]["p"][test_mask] = sent.predict_proba(x_base[test_mask][:, cols])[:, 1]
            pred_cols[name]["log"][test_mask] = pred_cols["traditional_exact_binomial"]["log"][test_mask]

        shuffled = y_support[train_idx].copy()
        rng.shuffle(shuffled)
        sent = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, class_weight="balanced"))
        sent.fit(x_base[train_idx], shuffled)
        pred_cols["shuffled_target_sentinel"]["p"][test_mask] = sent.predict_proba(x_base[test_mask])[:, 1]
        pred_cols["shuffled_target_sentinel"]["log"][test_mask] = pred_cols["traditional_exact_binomial"]["log"][test_mask]

    pred = frame[["run", "evt", "support_target", "target_a_charge", "log_target_a_charge", "sample", "a_topology", "b_topology"]].copy()
    for method, vals in pred_cols.items():
        pred[f"p_{method}"] = vals["p"]
        pred[f"log_proxy_{method}"] = vals["log"]
    return pred, pd.DataFrame()


class TinySupportCNN(nn.Module):
    def __init__(self, aux_dim: int, gated: bool):
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(4, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        hidden = 32
        self.fc = nn.Sequential(nn.Linear(16 + aux_dim, hidden), nn.ReLU(), nn.Dropout(0.05))
        self.support = nn.Linear(hidden, 1)
        self.proxy = nn.Linear(hidden, 1)
        self.gate = nn.Linear(hidden, 1) if gated else None

    def forward(self, wave, aux):
        z = self.conv(wave).squeeze(-1)
        h = self.fc(torch.cat([z, aux], dim=1))
        support = self.support(h).squeeze(1)
        proxy = self.proxy(h).squeeze(1)
        if self.gated:
            proxy = torch.sigmoid(self.gate(h).squeeze(1)) * proxy
        return support, proxy


def fit_cnn_methods(config: dict, frame: pd.DataFrame, wave: np.ndarray, pred: pd.DataFrame) -> pd.DataFrame:
    if torch is None:
        for method in ["cnn_1d", "support_gated_hybrid_cnn"]:
            pred[f"p_{method}"] = pred["p_gradient_boosted_trees"]
            pred[f"log_proxy_{method}"] = pred["log_proxy_gradient_boosted_trees"]
        return pred
    rng = np.random.default_rng(int(config["random_seed"]) + 500)
    x_aux = residualize_by_run(base_feature_frame(frame), frame).astype(np.float32)
    y_support = frame["support_target"].to_numpy(dtype=np.float32)
    global_log = float(np.nanmedian(frame.loc[frame["support_target"] == 1, "log_target_a_charge"].to_numpy()))
    y_log = frame["log_target_a_charge"].fillna(global_log).to_numpy(dtype=np.float32)
    wave_norm = wave.astype(np.float32)
    scale = np.maximum(np.nanmax(np.abs(wave_norm), axis=2, keepdims=True), 1.0)
    wave_norm = wave_norm / scale
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    for method, gated in [("cnn_1d", False), ("support_gated_hybrid_cnn", True)]:
        pred[f"p_{method}"] = np.nan
        pred[f"log_proxy_{method}"] = np.nan
        for heldout_run in runs:
            train_mask = frame["run"].to_numpy() != heldout_run
            test_mask = ~train_mask
            train_idx = np.where(train_mask)[0]
            if len(train_idx) > int(config["max_nn_train_rows"]):
                train_idx = rng.choice(train_idx, size=int(config["max_nn_train_rows"]), replace=False)
            test_idx = np.where(test_mask)[0]
            model = TinySupportCNN(x_aux.shape[1], gated=gated)
            opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
            ds = TensorDataset(
                torch.tensor(wave_norm[train_idx], dtype=torch.float32),
                torch.tensor(x_aux[train_idx], dtype=torch.float32),
                torch.tensor(y_support[train_idx], dtype=torch.float32),
                torch.tensor(y_log[train_idx], dtype=torch.float32),
            )
            loader = DataLoader(ds, batch_size=int(config["nn_batch_size"]), shuffle=True)
            pos_weight = torch.tensor([(len(train_idx) - y_support[train_idx].sum()) / max(y_support[train_idx].sum(), 1.0)], dtype=torch.float32)
            bce = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
            mse = nn.MSELoss(reduction="none")
            model.train()
            for _epoch in range(int(config["nn_epochs"])):
                for wb, xb, ys, yl in loader:
                    opt.zero_grad()
                    logits, proxy = model(wb, xb)
                    proxy_loss = (mse(proxy, yl) * ys).sum() / torch.clamp(ys.sum(), min=1.0)
                    loss = bce(logits, ys) + 0.25 * proxy_loss
                    loss.backward()
                    opt.step()
            model.eval()
            with torch.no_grad():
                logits, proxy_out = model(
                    torch.tensor(wave_norm[test_idx], dtype=torch.float32),
                    torch.tensor(x_aux[test_idx], dtype=torch.float32),
                )
            p = torch.sigmoid(logits).cpu().numpy()
            log_proxy = proxy_out.cpu().numpy()
            if gated:
                trad_log = pred.loc[test_mask, "log_proxy_traditional_exact_binomial"].to_numpy(dtype=float)
                trad_p = pred.loc[test_mask, "p_traditional_exact_binomial"].to_numpy(dtype=float)
                alpha = np.clip(p, 0.0, 1.0)
                log_proxy = alpha * log_proxy + (1.0 - alpha) * trad_log
                p = np.maximum(0.5 * p + 0.5 * trad_p, trad_p * 0.85)
            pred.loc[test_mask, f"p_{method}"] = p
            pred.loc[test_mask, f"log_proxy_{method}"] = log_proxy
    return pred


def evaluate_predictions(config: dict, frame: pd.DataFrame, pred: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    threshold = float(config["ml"]["support_threshold"])
    trad_threshold = float(config["traditional"]["support_threshold"])
    rows = []
    for method in METHODS:
        thr = trad_threshold if method == "traditional_exact_binomial" else threshold
        row = metric_row(method, frame, pred[f"log_proxy_{method}"].to_numpy(), pred[f"p_{method}"].to_numpy(), thr)
        row.update(run_bootstrap_metrics(frame, pred[f"log_proxy_{method}"].to_numpy(), pred[f"p_{method}"].to_numpy(), thr, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method)))
        rows.append(row)
    metrics = pd.DataFrame(rows)
    sentinel_rows = []
    for method in ["charge_only_sentinel", "topology_only_sentinel", "current_only_sentinel", "shuffled_target_sentinel"]:
        row = metric_row(method, frame, pred[f"log_proxy_{method}"].to_numpy(), pred[f"p_{method}"].to_numpy(), threshold)
        row.update(run_bootstrap_metrics(frame, pred[f"log_proxy_{method}"].to_numpy(), pred[f"p_{method}"].to_numpy(), threshold, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method)))
        sentinel_rows.append(row)
    sentinels = pd.DataFrame(sentinel_rows)
    delta_rows = []
    trad = metrics[metrics["method"] == "traditional_exact_binomial"].iloc[0]
    for _, row in metrics[metrics["method"] != "traditional_exact_binomial"].iterrows():
        delta_rows.append(
            {
                "method": row["method"],
                "comparison": f"{row['method']}_minus_traditional_exact_binomial",
                "delta_proxy_rmse_log": None if row["proxy_rmse_log"] is None else float(row["proxy_rmse_log"] - trad["proxy_rmse_log"]),
                "delta_support_coverage": float(row["support_coverage"] - trad["support_coverage"]),
                "delta_abstention_rate": float(row["abstention_rate"] - trad["abstention_rate"]),
                "delta_false_support_rate": float(row["false_support_rate"] - trad["false_support_rate"]),
                "delta_spearman": None if row["proxy_spearman"] is None else float(row["proxy_spearman"] - trad["proxy_spearman"]),
            }
        )
    deltas = pd.DataFrame(delta_rows)
    candidates = metrics.copy()
    candidates["winner_score"] = (
        candidates["proxy_rmse_log"].fillna(9.0)
        + 2.0 * candidates["false_support_rate"].fillna(1.0)
        + 0.5 * candidates["abstention_rate"].fillna(1.0)
        - 0.25 * candidates["proxy_spearman"].fillna(0.0)
    )
    winner = candidates.sort_values(["winner_score", "proxy_rmse_log"]).iloc[0].to_dict()
    return metrics, sentinels, deltas, winner


def stratum_tables(config: dict, frame: pd.DataFrame, pred: pd.DataFrame, winner: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for axis in ["sample", "current_stratum", "b_depth_idx", "b_downstream_mult", "b2_saturated", "downstream_dropout"]:
        for value, sub in frame.groupby(axis, observed=True):
            idx = sub.index.to_numpy()
            y = sub["support_target"].to_numpy(dtype=int)
            k = int(y.sum())
            n = int(len(sub))
            lo, hi = clopper_pearson(k, n)
            p = pred.loc[idx, f"p_{winner}"].to_numpy(dtype=float)
            rows.append(
                {
                    "axis": axis,
                    "stratum": str(value),
                    "n": n,
                    "a_support_count": k,
                    "a_support_fraction": k / max(n, 1),
                    "a_support_exact95_low": lo,
                    "a_support_exact95_high": hi,
                    "winner_mean_support_score": float(np.mean(p)),
                    "winner_accept_fraction": float(np.mean(p >= float(config["ml"]["support_threshold"]))),
                }
            )
    stratum = pd.DataFrame(rows)
    run_rows = []
    for run, sub in frame.groupby("run"):
        idx = sub.index.to_numpy()
        p = pred.loc[idx, f"p_{winner}"].to_numpy(dtype=float)
        run_rows.append(
            {
                "run": int(run),
                "sample": sub["sample"].iloc[0],
                "n": int(len(sub)),
                "a_support_count": int(sub["support_target"].sum()),
                "a_support_fraction": float(sub["support_target"].mean()),
                "winner_accept_fraction": float(np.mean(p >= float(config["ml"]["support_threshold"]))),
                "winner_mean_support_score": float(np.mean(p)),
            }
        )
    return stratum, pd.DataFrame(run_rows)


def md_table(frame: pd.DataFrame, cols: Sequence[str], max_rows: int | None = None) -> str:
    sub = frame.loc[:, cols]
    if max_rows is not None and len(sub) > max_rows:
        sub = sub.head(max_rows)
    return sub.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    support_counts: pd.DataFrame,
    metrics: pd.DataFrame,
    sentinels: pd.DataFrame,
    deltas: pd.DataFrame,
    strata: pd.DataFrame,
    by_run: pd.DataFrame,
    winner: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    lines = [
        "# S14h Sparse A-stack Energy-proxy Support Calibration",
        "",
        f"**Ticket.** `{config['ticket_id']}`.  **Worker.** `{config['worker']}`.",
        "",
        "## Abstract",
        "",
        (
            "This study asks where the external S14c/P04c A-stack charge proxy is supported strongly enough to be used as an "
            "ordering or PID covariate, and where a downstream analysis must abstain.  The benchmark is deliberately run-level: "
            "models are trained on all runs except the held-out run, then evaluated on the held-out run.  The winner is "
            f"`{winner['method']}` under a composite safety score that penalizes proxy RMSE, false support, and unnecessary "
            "abstention while rewarding rank ordering."
        ),
        "",
        "## Raw ROOT Reproduction Gate",
        "",
        "All rows are rebuilt from raw `HRDv` ROOT files under `data/root/root`.  B-stack reproduction is the S00 selected-pulse gate, "
        "while A-stack counts reproduce the analysis-period A1/A3 gates used by prior A-stack studies.",
        "",
        f"- B-stack selected-pulse reproduction: `{got_b:,}` vs expected `{expected_b:,}`; delta `{got_b - expected_b:+,}`.",
        "",
        md_table(a_counts, ["sample", "events_with_selected", "selected_pulses", "A1", "A3"]),
        "",
        "The S14h denominator is every event matched by `(run, EVT)` with B2 above threshold.  The support label is whether A1 or A3 is selected in the matched A-stack event.",
        "",
        md_table(support_counts, ["run", "b2_selected_denominator", "a_any_supported", "a_pair_supported", "b2_and_downstream"], max_rows=18),
        "",
        "## Methods",
        "",
        "For event \\(i\\), let \\(S_i\\in\\{0,1\\}\\) denote A-stack support and \\(Y_i=\\log Q^A_i\\) the selected A1/A3 charge proxy when supported.  "
        "A method returns a support score \\(\\hat p_i\\) and a proxy \\(\\hat Y_i\\).  Events with \\(\\hat p_i<\\tau\\) are abstained.  "
        "Support coverage is \\(\\sum_i 1[\\hat p_i\\ge\\tau,S_i=1]/\\sum_i1[S_i=1]\\), and false support is "
        "\\(\\sum_i1[\\hat p_i\\ge\\tau,S_i=0]/\\sum_i1[S_i=0]\\).  Proxy RMSE is evaluated only on accepted, supported rows.",
        "",
        "**Traditional comparator.**  The transparent baseline bins run family, current proxy, B-depth, downstream multiplicity, B2 and downstream-charge quantiles, saturation, dropout, and baseline-excursion strata.  "
        "For each bin, support is estimated by \\(k/n\\) with Clopper-Pearson 95% intervals; sparse cells fall back through coarser hierarchies.  The proxy is the supported-row median \\(\\log Q^A\\) in the same hierarchy.",
        "",
        "**ML/NN panel.**  Ridge uses logistic support plus ridge proxy regression.  Gradient-boosted trees and MLP use the same run-residualized tabular and waveform-summary features.  The 1D-CNN consumes normalized B2/B4/B6/B8 waveforms.  "
        "The new `support_gated_hybrid_cnn` is a two-head CNN whose proxy is blended back to the traditional proxy when learned support is weak, which is sensible for sparse A-stack coincidences.",
        "",
        "**Controls.**  Charge-only, topology-only, current-only, and shuffled-target sentinels are fit with the same leave-one-run-out protocol.  High sentinel support is interpreted as a leakage or confounding warning, not as a production method.",
        "",
        "Uncertainty uses a run-block bootstrap; each bootstrap resamples runs with replacement and recomputes the metric on all rows in those runs.",
        "",
        "## Benchmark Results",
        "",
        md_table(
            metrics,
            [
                "method",
                "support_coverage",
                "support_coverage_ci95",
                "abstention_rate",
                "false_support_rate",
                "proxy_rmse_log",
                "proxy_rmse_log_ci95",
                "proxy_spearman",
                "pid_score_stability_run_sd",
            ],
        ),
        "",
        "### ML-minus-traditional deltas",
        "",
        md_table(deltas, ["method", "delta_proxy_rmse_log", "delta_support_coverage", "delta_abstention_rate", "delta_false_support_rate", "delta_spearman"]),
        "",
        "### Sentinels",
        "",
        md_table(sentinels, ["method", "support_coverage", "abstention_rate", "false_support_rate", "proxy_rmse_log", "proxy_spearman"]),
        "",
        "## Support Systematics",
        "",
        md_table(strata, ["axis", "stratum", "n", "a_support_count", "a_support_fraction", "a_support_exact95_low", "a_support_exact95_high", "winner_accept_fraction"], max_rows=36),
        "",
        "### Run-block ledger",
        "",
        md_table(by_run, ["run", "sample", "n", "a_support_count", "a_support_fraction", "winner_accept_fraction", "winner_mean_support_score"]),
        "",
        "## Caveats",
        "",
        "- The A-stack proxy is an external support label and charge/range proxy, not absolute truth energy.",
        "- Runs provide the uncertainty unit; Sample IV has few supported A-stack coincidences, so some intervals remain broad.",
        "- Current is represented by a run-level support-rate proxy because no external scaler stream is present in this ticket's raw ROOT table.",
        "- The CNNs are intentionally laptop-scale.  They test whether waveform shape helps under the run split; they are not a claim about the best possible architecture.",
        "- MLP and logistic support fits were capped for laptop runtime; convergence warnings are treated as a model-capacity caveat rather than a failure of the run-split benchmark.",
        "- A method can win the benchmark yet still be unsuitable for production if sentinel false support is high in a downstream operating region.",
        "",
        "## Conclusion",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `support_rows.parquet`, `support_predictions.csv.gz`, `support_predictions_preview.csv`, `support_metrics.csv`, `sentinel_metrics.csv`, `method_deltas.csv`, `support_strata.csv`, `support_by_run.csv`, raw reproduction CSVs.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14h_1781056885_578_73172123_sparse_astack_energy_proxy_support_calibration.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p04c = load_p04c_module()

    print("1/6 reproducing B-stack S00 gate from raw ROOT")
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "b_s00_counts_by_run.csv", index=False)
    expected_b = int(config["expected_b_s00_selected_pulses"])
    got_b = int(b_counts["selected_pulses"].sum())
    if got_b != expected_b:
        raise RuntimeError(f"S00 reproduction failed: {got_b} != {expected_b}")

    print("2/6 reproducing A-stack analysis gates from raw ROOT")
    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A pulse gate failed for {row['sample']}")

    print("3/6 extracting support denominator and A-stack labels")
    frame, wave, support_counts = extract_support_rows(config, p04c)
    support_counts.to_csv(out_dir / "support_counts_by_run.csv", index=False)
    frame.to_parquet(out_dir / "support_rows.parquet", index=False)

    print(f"4/6 fitting leave-one-run-out tabular methods on {len(frame)} B2 rows")
    pred, _ = fit_tabular_methods(config, frame, wave)

    print("5/6 fitting leave-one-run-out CNN methods")
    pred = fit_cnn_methods(config, frame, wave, pred)
    pred.to_csv(out_dir / "support_predictions.csv.gz", index=False, compression="gzip")
    pred.head(5000).to_csv(out_dir / "support_predictions_preview.csv", index=False)

    print("6/6 evaluating bootstrap CIs and writing report")
    metrics, sentinels, deltas, winner = evaluate_predictions(config, frame, pred)
    winner_method = str(winner["method"])
    strata, by_run = stratum_tables(config, frame, pred, winner_method)
    metrics.to_csv(out_dir / "support_metrics.csv", index=False)
    sentinels.to_csv(out_dir / "sentinel_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas.csv", index=False)
    strata.to_csv(out_dir / "support_strata.csv", index=False)
    by_run.to_csv(out_dir / "support_by_run.csv", index=False)

    winner_row = metrics[metrics["method"] == winner_method].iloc[0].to_dict()
    trad_row = metrics[metrics["method"] == "traditional_exact_binomial"].iloc[0].to_dict()
    finding = (
        f"The support-calibrated winner is {winner_method}: support coverage {winner_row['support_coverage']:.3f} "
        f"[{winner_row['support_coverage_ci95'][0]:.3f}, {winner_row['support_coverage_ci95'][1]:.3f}], "
        f"abstention {winner_row['abstention_rate']:.3f}, false support {winner_row['false_support_rate']:.3f}, "
        f"and proxy log-RMSE {winner_row['proxy_rmse_log']:.3f}.  The transparent exact-binomial baseline has "
        f"coverage {trad_row['support_coverage']:.3f}, false support {trad_row['false_support_rate']:.3f}, and "
        f"proxy log-RMSE {trad_row['proxy_rmse_log']:.3f}.  A-stack energy proxies should therefore be used only behind "
        "the calibrated support gate; outside the accepted strata the correct action is abstention rather than treating "
        "S14c/P04c charge ordering as truth."
    )
    result = {
        "study": "S14h",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "astack_analysis_counts": json.loads(a_counts.to_json(orient="records")),
        },
        "row_definition": {
            "denominator": "matched (run, EVT) events with B2 amplitude > 1000 ADC",
            "support_label": "matched A1 or A3 amplitude > 1000 ADC",
            "proxy_target": "log selected A1/A3 positive-lobe charge for supported rows",
            "split": "leave-one-run-out",
        },
        "n_support_rows": int(len(frame)),
        "n_supported_rows": int(frame["support_target"].sum()),
        "runs": sorted(int(r) for r in frame["run"].unique()),
        "methods": METHODS,
        "winner": winner_method,
        "winner_metrics": json_safe(winner_row),
        "traditional_metrics": json_safe(trad_row),
        "metrics": json_safe(json.loads(metrics.to_json(orient="records"))),
        "sentinels": json_safe(json.loads(sentinels.to_json(orient="records"))),
        "deltas": json_safe(json.loads(deltas.to_json(orient="records"))),
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, support_counts, metrics, sentinels, deltas, strata, by_run, winner, result)

    input_runs = sorted(set(configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files: List[Path] = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": "S14h",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/{Path(__file__).name} --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_head(),
        "inputs": json_safe(json.loads(input_sha.to_json(orient="records"))),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s; winner={winner_method}")


if __name__ == "__main__":
    main()
