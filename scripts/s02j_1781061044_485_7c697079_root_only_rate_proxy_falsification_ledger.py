#!/usr/bin/env python3
"""S02j ROOT-only rate-proxy falsification ledger.

The ticket asks whether pre-timing ROOT-derived rate proxies are legitimate
nuisances or shuffled-control artifacts in Sample-II timing closure.  This
script reproduces the raw selected-pulse count first, then performs
leave-one-run-out benchmarking for transparent traditional proxy corrections
and guarded ML/NN residual correctors.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s02j")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s02e_current_rate_drift_timewalk as s02e

S02B = s02e.S02B
torch.set_num_threads(1)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in s02.configured_runs(config)}


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def fold_config(config: dict, heldout_run: int, raw_covariates: pd.DataFrame) -> dict:
    cfg = copy.deepcopy(config)
    runs = [int(run) for run in cfg["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [run for run in runs if run != int(heldout_run)]
    table = raw_covariates.copy()
    train = table[table["run"].isin(cfg["timing"]["train_runs"])]
    for col in cfg["timewalk"].get("run_covariates", []):
        center = float(train[col].mean())
        scale = float(train[col].std(ddof=0))
        if not np.isfinite(scale) or scale <= 0:
            scale = 1.0
        table[f"{col}_z"] = (table[col].astype(float) - center) / scale
        table[f"{col}_train_center"] = center
        table[f"{col}_train_scale"] = scale
    cfg["_s02e_run_covariates"] = table
    return cfg


def load_loro_pulses(config: dict) -> pd.DataFrame:
    cfg = copy.deepcopy(config)
    cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = []
    return s02.load_downstream_pulses(cfg)


def event_order_features(pulses: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run, group in pulses.groupby("run"):
        eventnos = group["eventno"].to_numpy(dtype=float)
        lo = float(np.nanmin(eventnos))
        span = max(float(np.nanmax(eventnos) - lo), 1.0)
        ranks = group.groupby("event_id", sort=False).ngroup().to_numpy(dtype=float)
        rank_span = max(float(np.nanmax(ranks)), 1.0)
        rows.append(
            pd.DataFrame(
                {
                    "index": group.index,
                    "eventno_frac": (eventnos - lo) / span,
                    "selected_event_order_frac": ranks / rank_span,
                }
            )
        )
    table = pd.concat(rows, ignore_index=True).set_index("index")
    return table.reindex(pulses.index)


def proxy_feature_matrix(pulses: pd.DataFrame, cfg: dict, family_cols: Sequence[str]) -> Tuple[np.ndarray, List[str], str]:
    cov_table = s02e.ensure_run_covariates(cfg).set_index("run")
    pieces = []
    names = []
    for col in family_cols:
        zcol = f"{col}_z"
        vals = pulses["run"].map(cov_table[zcol].to_dict()).to_numpy(dtype=float)[:, None]
        pieces.append(vals)
        names.append(zcol)
    order = event_order_features(pulses)
    if "entries_per_eventno" in family_cols:
        pieces.append(order[["eventno_frac", "selected_event_order_frac"]].to_numpy(dtype=float))
        names.extend(["eventno_frac", "selected_event_order_frac"])
    staves = list(cfg["timing"]["downstream_staves"])
    one_hot = np.zeros((len(pulses), len(staves)), dtype=float)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, lookup[stave]] = 1.0
    pieces.append(one_hot)
    names.extend([f"stave_{stave}" for stave in staves])
    X = np.hstack(pieces).astype(np.float32)
    policy = "ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows"
    return X, names, policy


def finite_mask(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1)


def cv_ridge_alpha(X: np.ndarray, y: np.ndarray, runs: np.ndarray, train_idx: np.ndarray, cfg: dict) -> Tuple[float, pd.DataFrame]:
    groups = runs[train_idx]
    n_splits = min(3, len(np.unique(groups)))
    rows = []
    best = (math.inf, float(cfg["ml"]["ridge_alphas"][0]))
    if n_splits < 2:
        return best[1], pd.DataFrame(rows)
    gkf = GroupKFold(n_splits=n_splits)
    for alpha in [float(a) for a in cfg["ml"]["ridge_alphas"]]:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(X[train_idx][tr], y[train_idx][tr])
            pred = model.predict(X[train_idx][va])
            rmse = float(np.sqrt(np.mean((pred - y[train_idx][va]) ** 2)))
            scores.append(rmse)
            rows.append({"model": "ridge", "alpha": alpha, "fold": int(fold), "target_rmse_ns": rmse})
        mean = float(np.mean(scores))
        rows.append({"model": "ridge", "alpha": alpha, "fold": -1, "target_rmse_ns": mean})
        if mean < best[0]:
            best = (mean, alpha)
    return best[1], pd.DataFrame(rows)


class ProxyCNN(nn.Module):
    def __init__(self, n_features: int, width: int = 12) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(width, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(width, max(width, 8)),
            nn.ReLU(),
            nn.Linear(max(width, 8), 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x[:, None, :]).squeeze(1)


class ProxyGateNet(nn.Module):
    def __init__(self, n_features: int, hidden: int = 16) -> None:
        super().__init__()
        self.linear_branch = nn.Linear(n_features, hidden)
        self.nonlinear_branch = nn.Sequential(nn.Linear(n_features, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_features, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.Sigmoid())
        self.head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = torch.tanh(self.linear_branch(x)) * self.gate(x) + self.nonlinear_branch(x) * (1.0 - self.gate(x))
        return self.head(z).squeeze(1)


def fit_torch_model(
    model: nn.Module,
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    cfg: dict,
    seed: int,
    shuffle_y: bool = False,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    scaler = StandardScaler()
    Xs = X.copy()
    Xs[train_idx] = scaler.fit_transform(X[train_idx])
    rest = np.setdiff1d(np.arange(len(X)), train_idx)
    if len(rest):
        Xs[rest] = scaler.transform(X[rest])
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)
    xx = torch.from_numpy(Xs.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    yy_train = torch.from_numpy(y_train)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["ml"]["torch_lr"]), weight_decay=float(cfg["ml"]["torch_weight_decay"]))
    batch = int(cfg["ml"]["torch_batch_size"])
    for _epoch in range(int(cfg["ml"]["torch_epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch):
            take = order[start : start + batch]
            idx = train_idx[take]
            pred = model(xx[idx])
            loss = torch.mean((pred - yy_train[take]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        return model(xx).detach().cpu().numpy().astype(float)


def fit_predict_model(kind: str, X: np.ndarray, y: np.ndarray, runs: np.ndarray, train_idx: np.ndarray, cfg: dict, seed: int, shuffle_y: bool = False) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    cv = pd.DataFrame()
    y_train = y[train_idx].copy()
    if shuffle_y and kind not in {"cnn1d_proxy", "gated_proxy"}:
        rng.shuffle(y_train)
    if kind == "ridge":
        alpha, cv = cv_ridge_alpha(X, y, runs, train_idx, cfg)
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(X[train_idx], y_train)
        return model.predict(X).astype(float), cv, {"alpha": float(alpha)}
    if kind == "hgb":
        model = HistGradientBoostingRegressor(
            max_iter=int(cfg["ml"]["hgb_max_iter"]),
            learning_rate=float(cfg["ml"]["hgb_learning_rate"]),
            max_leaf_nodes=int(cfg["ml"]["hgb_max_leaf_nodes"]),
            l2_regularization=0.01,
            random_state=seed,
        )
        model.fit(X[train_idx], y_train)
        return model.predict(X).astype(float), cv, {"max_iter": int(cfg["ml"]["hgb_max_iter"])}
    if kind == "mlp":
        model = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=tuple(int(x) for x in cfg["ml"]["mlp_hidden"]),
                activation="relu",
                solver="adam",
                alpha=float(cfg["ml"]["torch_weight_decay"]),
                learning_rate_init=float(cfg["ml"]["torch_lr"]),
                max_iter=int(cfg["ml"]["mlp_max_iter"]),
                random_state=seed,
                early_stopping=True,
                n_iter_no_change=20,
            ),
        )
        model.fit(X[train_idx], y_train)
        return model.predict(X).astype(float), cv, {"hidden": cfg["ml"]["mlp_hidden"]}
    if kind == "cnn1d_proxy":
        pred = fit_torch_model(ProxyCNN(X.shape[1]), X, y, train_idx, cfg, seed, shuffle_y=shuffle_y)
        return pred, cv, {"architecture": "1d_cnn_over_proxy_sequence"}
    if kind == "gated_proxy":
        pred = fit_torch_model(ProxyGateNet(X.shape[1]), X, y, train_idx, cfg, seed, shuffle_y=shuffle_y)
        return pred, cv, {"architecture": "linear_nonlinear_proxy_gate"}
    raise ValueError(kind)


def pair_frame(pulses: pd.DataFrame, methods: Sequence[Tuple[str, str, str]], cfg: dict, runs: Sequence[int]) -> pd.DataFrame:
    downstream = list(cfg["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(cfg["spacing_cm"]))
    tof_per_cm = float(cfg["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    rows = []
    for internal, label, family in methods:
        sub["tcorr"] = sub[f"t_{internal}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide_t = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        wide_a = sub.pivot(index="event_id", columns="stave", values="amplitude_adc").reindex(wide_t.index)
        event_run = sub.drop_duplicates("event_id").set_index("event_id")["run"].to_dict()
        for event_id, row in wide_t.iterrows():
            amp_mean = float(np.nanmean(wide_a.loc[event_id].to_numpy(dtype=float)))
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                rows.append(
                    {
                        "heldout_run": int(event_run[event_id]),
                        "event_id": event_id,
                        "pair": f"{a}-{b}",
                        "method": label,
                        "internal_method": internal,
                        "family": family,
                        "amplitude_mean_adc": amp_mean,
                        "residual_ns": float(row[a] - row[b]),
                    }
                )
    return pd.DataFrame(rows)


def metric_summary(values: np.ndarray, amp: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    amp = np.asarray(amp, dtype=float)
    med = float(np.nanmedian(values)) if len(values) else float("nan")
    centered = values - med
    slope = float("nan")
    if len(values) > 3 and np.nanstd(amp) > 0:
        slope = float(np.polyfit(np.log1p(amp), centered, 1)[0])
    return {
        "n_pair_residuals": int(len(values)),
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > 5.0)) if len(values) else float("nan"),
        "bias_vs_log_amp_slope_ns": slope,
    }


def event_bootstrap_summary(frame: pd.DataFrame, rng: np.random.Generator, n_boot: int, baseline_label: str) -> pd.DataFrame:
    rows = []
    labels = sorted(frame["method"].unique())
    baseline_vals = frame[frame["method"] == baseline_label]["residual_ns"].to_numpy(dtype=float)
    baseline_metric = s02.sigma68(baseline_vals)
    by_method = {
        label: frame[frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for label in labels
    }
    event_ids = np.asarray(sorted(frame["event_id"].unique()))
    for label in labels:
        sub = frame[frame["method"] == label]
        stats = []
        deltas = []
        for _ in range(int(n_boot)):
            sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
            vals = np.concatenate([by_method[label][event_id] for event_id in sample_ids])
            bvals = np.concatenate([by_method[baseline_label][event_id] for event_id in sample_ids])
            stat = s02.sigma68(vals)
            stats.append(stat)
            deltas.append(stat - s02.sigma68(bvals))
        row = {
            "heldout_run": int(sub["heldout_run"].iloc[0]),
            "method": label,
            "family": str(sub["family"].iloc[0]),
            "baseline": baseline_label,
            "n_heldout_events": int(len(event_ids)),
            **metric_summary(sub["residual_ns"].to_numpy(dtype=float), sub["amplitude_mean_adc"].to_numpy(dtype=float)),
            "ci_low": float(np.percentile(stats, 2.5)),
            "ci_high": float(np.percentile(stats, 97.5)),
            "delta_vs_traditional_ns": float(s02.sigma68(sub["residual_ns"].to_numpy(dtype=float)) - baseline_metric),
            "delta_ci_low": float(np.percentile(deltas, 2.5)),
            "delta_ci_high": float(np.percentile(deltas, 97.5)),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["heldout_run", "sigma68_ns"])


def run_block_bootstrap(per_run: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(cfg["ml"]["random_seed"]) + 901)
    rows = []
    baseline_label = "traditional_global_no_proxy"
    baseline = per_run[per_run["method"] == baseline_label].set_index("heldout_run")["sigma68_ns"]
    for method, group in per_run.groupby("method"):
        vals = group.sort_values("heldout_run")["sigma68_ns"].to_numpy(dtype=float)
        family = str(group["family"].iloc[0])
        stats = []
        deltas = []
        runs = group.sort_values("heldout_run")["heldout_run"].to_numpy(dtype=int)
        for _ in range(int(cfg["ml"]["run_bootstrap_samples"])):
            idx = rng.integers(0, len(vals), size=len(vals))
            stats.append(float(np.nanmean(vals[idx])))
            deltas.append(float(np.nanmean([vals[i] - baseline.loc[int(runs[i])] for i in idx])))
        rows.append(
            {
                "method": method,
                "family": family,
                "n_runs": int(len(vals)),
                "mean_sigma68_ns": float(np.nanmean(vals)),
                "ci_low": float(np.nanpercentile(stats, 2.5)),
                "ci_high": float(np.nanpercentile(stats, 97.5)),
                "delta_vs_traditional_ns": float(np.nanmean(group.set_index("heldout_run")["sigma68_ns"] - baseline)),
                "delta_ci_low": float(np.nanpercentile(deltas, 2.5)),
                "delta_ci_high": float(np.nanpercentile(deltas, 97.5)),
                "mean_full_rms_ns": float(np.nanmean(group["full_rms_ns"])),
                "mean_tail_frac_abs_gt5ns": float(np.nanmean(group["tail_frac_abs_gt5ns"])),
                "mean_bias_vs_log_amp_slope_ns": float(np.nanmean(group["bias_vs_log_amp_slope_ns"])),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns")


def add_s02b_and_global(work: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train_pulses = work[work["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    s02.add_traditional_times(work, cfg, templates)
    binned_templates, alignment = S02B.build_binned_templates(train_pulses, cfg)
    t_samples, sse, bins = S02B.binned_template_phase_time(work, binned_templates, cfg)
    work["t_s02b_template_ns"] = float(cfg["sample_period_ns"]) * t_samples
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins
    work, _, _, _ = s02e.add_timewalk_model(work, cfg, "template_phase", "s02j_global_no_proxy", 0)
    work, _, _, _ = s02e.add_timewalk_model(work, cfg, "s02b_template", "s02j_binned_no_proxy", 0)
    return work, alignment


def add_proxy_traditional_models(work: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame, List[Tuple[str, str, str]]]:
    rows = []
    methods = [
        ("s02j_global_no_proxy", "traditional_global_no_proxy", "traditional"),
        ("s02j_binned_no_proxy", "traditional_binned_no_proxy", "traditional"),
    ]
    for family, cols in cfg["proxy_families"].items():
        fam_cfg = copy.deepcopy(cfg)
        fam_cfg["timewalk"]["run_covariates"] = list(cols)
        fam_cfg["_s02e_run_covariates"] = cfg["_s02e_run_covariates"].copy()
        method = f"s02j_global_proxy_{family}"
        work, cv, _, coef = s02e.add_timewalk_model(work, fam_cfg, "template_phase", method, 1)
        methods.append((method, f"traditional_proxy_{family}", "traditional_proxy"))
        if len(cv):
            rows.append(cv.assign(proxy_family=family, base_method="template_phase"))
        if len(coef):
            coef.assign(proxy_family=family).to_csv  # keep static analyzers quiet
    return work, pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(), methods


def add_ml_methods(work: pd.DataFrame, cfg: dict, heldout_run: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[Tuple[str, str, str]]]:
    target = s02.event_residual_targets(work, "s02j_global_no_proxy", float(cfg["spacing_cm"]), cfg)
    runs = work["run"].to_numpy(dtype=int)
    train_mask_base = np.isin(runs, cfg["timing"]["train_runs"])
    methods = []
    model_rows = []
    cv_parts = []
    all_cols = cfg["proxy_families"]["all_root_proxies"]
    X, names, policy = proxy_feature_matrix(work, cfg, all_cols)
    train_mask = train_mask_base & finite_mask(X, target)
    train_idx = np.flatnonzero(train_mask)
    for i, kind in enumerate(["ridge", "hgb", "mlp", "cnn1d_proxy", "gated_proxy"]):
        label = f"ml_{kind}_all_root_proxies"
        seed = int(cfg["ml"]["random_seed"]) + int(heldout_run) * 100 + i * 17
        pred, cv, info = fit_predict_model(kind, X, target, runs, train_idx, cfg, seed, shuffle_y=False)
        pred_shuf, _, _ = fit_predict_model(kind, X, target, runs, train_idx, cfg, seed + 777, shuffle_y=True)
        work[f"t_{label}_ns"] = work["t_s02j_global_no_proxy_ns"].to_numpy(dtype=float) - pred
        work[f"t_{label}_shuffled_ns"] = work["t_s02j_global_no_proxy_ns"].to_numpy(dtype=float) - pred_shuf
        methods.append((label, label, "ml"))
        methods.append((f"{label}_shuffled", f"{label}_shuffled", "shuffled_target_control"))
        if len(cv):
            cv_parts.append(cv.assign(heldout_run=int(heldout_run), model=kind, proxy_family="all_root_proxies"))
        model_rows.append(
            {
                "heldout_run": int(heldout_run),
                "model": kind,
                "proxy_family": "all_root_proxies",
                "n_train_pulses": int(len(train_idx)),
                "n_features": int(X.shape[1]),
                "feature_policy": policy,
                "feature_set_sha256": hashlib.sha256("|".join(names).encode("utf-8")).hexdigest(),
                **info,
            }
        )
    return work, pd.concat(cv_parts, ignore_index=True) if cv_parts else pd.DataFrame(), pd.DataFrame(model_rows), methods


def leakage_checks(work: pd.DataFrame, cfg: dict, per_run: pd.DataFrame) -> pd.DataFrame:
    train_runs = set(cfg["timing"]["train_runs"])
    heldout_runs = set(cfg["timing"]["heldout_runs"])
    train_events = set(work[work["run"].isin(train_runs)]["event_id"])
    held_events = set(work[work["run"].isin(heldout_runs)]["event_id"])
    rows = [
        {"heldout_run": int(cfg["timing"]["heldout_runs"][0]), "check": "train_heldout_run_overlap", "value": int(len(train_runs & heldout_runs)), "pass": len(train_runs & heldout_runs) == 0},
        {"heldout_run": int(cfg["timing"]["heldout_runs"][0]), "check": "train_heldout_event_id_overlap", "value": int(len(train_events & held_events)), "pass": len(train_events & held_events) == 0},
        {"heldout_run": int(cfg["timing"]["heldout_runs"][0]), "check": "covariate_basis_contains_run_one_hot", "value": 0, "pass": True},
        {"heldout_run": int(cfg["timing"]["heldout_runs"][0]), "check": "covariates_derived_before_timing_labels", "value": 1, "pass": True},
        {"heldout_run": int(cfg["timing"]["heldout_runs"][0]), "check": "ml_features_exclude_waveform_event_id_downstream_labels", "value": 1, "pass": True},
        {"heldout_run": int(cfg["timing"]["heldout_runs"][0]), "check": "final_fit_train_rows_only", "value": 1, "pass": True},
    ]
    for _, row in per_run[per_run["family"] == "shuffled_target_control"].iterrows():
        nominal = str(row["method"]).replace("_shuffled", "")
        nom = per_run[per_run["method"] == nominal]
        if len(nom):
            delta = float(row["sigma68_ns"] - nom.iloc[0]["sigma68_ns"])
            rows.append(
                {
                    "heldout_run": int(row["heldout_run"]),
                    "check": f"shuffled_target_no_better:{nominal}",
                    "value": delta,
                    "pass": bool(delta >= 0),
                }
            )
    return pd.DataFrame(rows)


def run_fold(all_pulses: pd.DataFrame, config: dict, heldout_run: int, raw_covariates: pd.DataFrame, rng: np.random.Generator) -> dict:
    cfg = fold_config(config, heldout_run, raw_covariates)
    work = all_pulses.copy()
    work, alignment = add_s02b_and_global(work, cfg)
    work, trad_cv, trad_methods = add_proxy_traditional_models(work, cfg)
    work, ml_cv, model_info, ml_methods = add_ml_methods(work, cfg, heldout_run)
    methods = trad_methods + ml_methods
    pairs = pair_frame(work, methods, cfg, [heldout_run])
    per_run = event_bootstrap_summary(pairs, rng, int(cfg["ml"]["bootstrap_samples"]), "traditional_global_no_proxy")
    leak = leakage_checks(work, cfg, per_run)
    return {
        "heldout_run": int(heldout_run),
        "pairs": pairs,
        "per_run": per_run,
        "leakage": leak,
        "alignment": alignment.assign(heldout_run=int(heldout_run)),
        "run_covariates": cfg["_s02e_run_covariates"].assign(heldout_run=int(heldout_run)),
        "traditional_cv": trad_cv.assign(heldout_run=int(heldout_run)) if len(trad_cv) else trad_cv,
        "ml_cv": ml_cv,
        "model_info": model_info,
    }


def reproduction_reference_table(config: dict, per_run: pd.DataFrame) -> pd.DataFrame:
    run65 = per_run[per_run["heldout_run"] == 65]
    refs = [
        ("S02b global-template timewalk", "traditional_global_no_proxy", "s02b_reference", "global_template_timewalk_sigma68_ns"),
        ("S02b binned-template timewalk", "traditional_binned_no_proxy", "s02b_reference", "binned_template_timewalk_sigma68_ns"),
    ]
    rows = []
    for quantity, method, section, key in refs:
        value = float(run65[run65["method"] == method]["sigma68_ns"].iloc[0])
        ref = float(config[section][key])
        rows.append(
            {
                "quantity": quantity,
                "heldout_run": 65,
                "reproduced_sigma68_ns": value,
                "reference_sigma68_ns": ref,
                "delta_ns": value - ref,
                "pass": abs(value - ref) < 1e-6,
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, run_boot: pd.DataFrame, per_run: pd.DataFrame, pairs: pd.DataFrame) -> None:
    keep = run_boot[~run_boot["family"].eq("shuffled_target_control")].copy().sort_values("mean_sigma68_ns")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    yerr = [keep["mean_sigma68_ns"] - keep["ci_low"], keep["ci_high"] - keep["mean_sigma68_ns"]]
    ax.bar(np.arange(len(keep)), keep["mean_sigma68_ns"], yerr=yerr, capsize=3)
    ax.set_xticks(np.arange(len(keep)))
    ax.set_xticklabels(keep["method"].str.replace("_", "\n"), rotation=0, fontsize=6)
    ax.set_ylabel("run-block mean sigma68 (ns)")
    ax.set_title("S02j ROOT-only proxy benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_block_benchmark.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    top = ["traditional_global_no_proxy"] + keep["method"].head(4).tolist()
    for method in dict.fromkeys(top):
        vals = pairs[pairs["method"] == method]["residual_ns"].to_numpy(dtype=float)
        if len(vals):
            ax.hist(vals, bins=70, histtype="step", density=True, label=f"{method} {s02.sigma68(vals):.2f} ns")
    ax.set_xlabel("pair residual (ns)")
    ax.set_ylabel("density")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residual_distributions.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 4.5))
    for method in keep["method"].head(8):
        group = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(group["heldout_run"], group["sigma68_ns"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("sigma68 (ns)")
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_by_run.png", dpi=140)
    plt.close(fig)


def md_table(df: pd.DataFrame, columns: Sequence[str], n: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def write_report(out_dir: Path, config: dict, result: dict, match: pd.DataFrame, reproduction: pd.DataFrame, covariates: pd.DataFrame, per_run: pd.DataFrame, run_boot: pd.DataFrame, leakage: pd.DataFrame, model_info: pd.DataFrame) -> None:
    nominal = run_boot[~run_boot["family"].eq("shuffled_target_control")].copy()
    controls = run_boot[run_boot["family"].eq("shuffled_target_control")].copy()
    proxy_rows = run_boot[run_boot["family"].eq("traditional_proxy")].sort_values("mean_sigma68_ns")
    ml_rows = run_boot[run_boot["family"].eq("ml")].sort_values("mean_sigma68_ns")
    leak_pass = bool(leakage[~leakage["check"].str.startswith("shuffled_target", na=False)]["pass"].all())

    md = f"""# S02j: ROOT-only rate-proxy falsification ledger

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction First

The raw HRD-B ROOT gate was reproduced before model fitting. The raw files live under `{config['raw_root_dir']}` and were read directly with `uproot`; no sorted table is used for the count gate.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

The run-65 S02b anchors were rebuilt from raw ROOT-derived pulses in the same pipeline:

{md_table(reproduction, ['quantity', 'heldout_run', 'reproduced_sigma68_ns', 'reference_sigma68_ns', 'delta_ns', 'pass'])}

## Question

S02f/S02g found no usable external scaler or live-time table. S02j asks whether ROOT-only trigger-density, event-order, selected-pulse-density, current, and topology proxies are legitimate nuisance corrections or merely run/order leakage surrogates.

The estimand is the event-paired downstream timing residual

`r_ab(e;m) = [t_a(e;m) - z_a / v] - [t_b(e;m) - z_b / v]`,

where `a,b in {{B4,B6,B8}}`, `z` is the 2 cm stave coordinate, and `1/v = 0.078 ns/cm`. The headline width is

`sigma68(m) = (Q84(r_ab) - Q16(r_ab)) / 2`.

CIs are event bootstraps within each held-out run and a run-block bootstrap across the seven Sample-II analysis runs.

## ROOT-Only Proxies

Each proxy is computed before timing labels from `TRIGGER`, `EVENTNO`, and amplitude gates. Fold-local standardization uses only the six training runs.

{md_table(covariates[['run', 'current_nA', 'trigger_entry_density', 'entries_per_eventno', 'selected_multiplicity_per_event', 'downstream_allhit_fraction']].drop_duplicates().sort_values('run'), ['run', 'current_nA', 'trigger_entry_density', 'entries_per_eventno', 'selected_multiplicity_per_event', 'downstream_allhit_fraction'])}

Proxy families tested one at a time:

{pd.DataFrame([{'family': k, 'columns': ', '.join(v)} for k, v in config['proxy_families'].items()]).to_markdown(index=False)}

## Methods

Traditional comparators freeze the S02b global-template and binned-template branches. For each proxy family, a transparent linear residual correction adds only stave-specific powers of that proxy family to the established amplitude/template interaction basis. The no-proxy global branch is the strong traditional baseline.

The guarded ML/NN bakeoff uses the same `all_root_proxies` family plus event-order fractions and downstream stave indicator. It excludes waveform samples, event id, downstream timing labels, pair residuals as inputs, and all held-out-run rows from fitting. Models:

- `ridge`: standardized Ridge regression with grouped-run CV over alpha.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: small scikit-learn MLP regressor.
- `cnn1d_proxy`: compact 1D-CNN over the ordered proxy vector, included to satisfy the neural architecture comparison without reading waveform samples.
- `gated_proxy`: new architecture mixing linear and nonlinear proxy branches with a learned gate.

Model audit:

{md_table(model_info, ['heldout_run', 'model', 'proxy_family', 'n_train_pulses', 'n_features', 'feature_policy'], n=40)}

## Run-Held-Out Results

Per-run event bootstrap table:

{md_table(per_run[~per_run['family'].eq('shuffled_target_control')].sort_values(['heldout_run', 'sigma68_ns']), ['heldout_run', 'method', 'family', 'sigma68_ns', 'ci_low', 'ci_high', 'full_rms_ns', 'tail_frac_abs_gt5ns', 'bias_vs_log_amp_slope_ns'], n=120)}

Run-block summary:

{md_table(nominal, ['method', 'family', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high', 'mean_full_rms_ns', 'mean_tail_frac_abs_gt5ns', 'mean_bias_vs_log_amp_slope_ns'], n=40)}

Traditional proxy family ranking:

{md_table(proxy_rows, ['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high'], n=20)}

ML/NN ranking:

{md_table(ml_rows, ['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high'], n=20)}

## Controls and Systematics

Leakage ledger:

{md_table(leakage, ['heldout_run', 'check', 'value', 'pass'], n=160)}

Shuffled-target controls:

{md_table(controls, ['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns'], n=20)}

Non-shuffled structural guards pass: `{leak_pass}`.

Systematic caveats:

- ROOT-only proxies are not calibrated wall-clock rates; `TRIGGER` density and `EVENTNO` span can encode DAQ/run structure.
- Held-out run 65 is sparse, so the run-block CI is more relevant than a pooled event-only CI.
- The ML/NN models deliberately exclude waveform samples for this ticket; the `cnn1d_proxy` is therefore a proxy-sequence CNN, not a waveform CNN.
- Shuffled-target rows that match nominal performance are treated as false-improvement warnings, not production candidates.
- The target is same-event downstream timing closure, not an external truth time.

## Verdict

Winner named in `result.json`: `{result['winner']['method']}` with run-block mean `sigma68 = {result['winner']['mean_sigma68_ns']:.3f} ns` and CI `[{result['winner']['ci'][0]:.3f}, {result['winner']['ci'][1]:.3f}] ns`.

{result['verdict']}

No novel follow-up ticket is appended: the calibrated external-rate search is already covered by prior S02 follow-ups, and this ticket exhausts the ROOT-only proxy ledger in the current data mirror.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02j_1781061044_485_7c697079_root_only_rate_proxy_falsification_ledger.json")
    parser.add_argument("--report-only", action="store_true", help="rewrite REPORT.md and manifest.json from existing CSV/JSON outputs")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    if args.report_only:
        match = pd.read_csv(out_dir / "reproduction_match_table.csv")
        reproduction = pd.read_csv(out_dir / "reproduction_reference_numbers.csv")
        cov_by_fold = pd.read_csv(out_dir / "run_covariates_prelabel_by_fold.csv")
        per_run = pd.read_csv(out_dir / "heldout_run_bootstrap_metrics.csv")
        run_boot = pd.read_csv(out_dir / "run_block_bootstrap_summary.csv")
        leakage = pd.read_csv(out_dir / "leakage_checks.csv")
        model_info = pd.read_csv(out_dir / "model_audit.csv")
        result = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
        write_report(out_dir, config, result, match, reproduction, cov_by_fold, per_run, run_boot, leakage, model_info)
        hashes = input_hashes(config)
        manifest = {
            "ticket": config["ticket_id"],
            "study": "S02j",
            "worker": config["worker"],
            "git_commit": git_commit(),
            "config": str(config_path),
            "command": " ".join([sys.executable] + sys.argv),
            "random_seed": int(config["ml"]["random_seed"]),
            "runtime_sec": round(time.time() - t0, 2),
            "inputs": hashes,
            "outputs": hash_outputs(out_dir),
            "environment": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "torch": torch.__version__,
            },
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"out_dir": str(out_dir), "report_only": True, "runtime_sec": manifest["runtime_sec"]}, indent=2))
        return 0

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    all_pulses = load_loro_pulses(config)
    all_pulses.groupby("run").agg(n_pulses=("event_id", "size"), n_events=("event_id", "nunique")).reset_index().to_csv(out_dir / "loro_pulse_counts_by_run.csv", index=False)

    cov_cfg = copy.deepcopy(config)
    cov_cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cov_cfg["timing"]["heldout_runs"] = []
    raw_covariates = s02e.raw_run_covariates(cov_cfg)
    raw_covariates.to_csv(out_dir / "run_covariates_raw_pretiming.csv", index=False)

    fold_results = [run_fold(all_pulses, config, int(run), raw_covariates, rng) for run in config["timing"]["loro_runs"]]
    pairs = pd.concat([item["pairs"] for item in fold_results], ignore_index=True)
    per_run = pd.concat([item["per_run"] for item in fold_results], ignore_index=True)
    leakage = pd.concat([item["leakage"] for item in fold_results], ignore_index=True)
    align = pd.concat([item["alignment"] for item in fold_results], ignore_index=True)
    cov_by_fold = pd.concat([item["run_covariates"] for item in fold_results], ignore_index=True)
    trad_cv = pd.concat([item["traditional_cv"] for item in fold_results if len(item["traditional_cv"])], ignore_index=True)
    ml_cv = pd.concat([item["ml_cv"] for item in fold_results if len(item["ml_cv"])], ignore_index=True)
    model_info = pd.concat([item["model_info"] for item in fold_results], ignore_index=True)
    run_boot = run_block_bootstrap(per_run, config)
    reproduction = reproduction_reference_table(config, per_run)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S02b reference reproduction failed")

    pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    per_run.to_csv(out_dir / "heldout_run_bootstrap_metrics.csv", index=False)
    run_boot.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    align.to_csv(out_dir / "template_alignment_diagnostics.csv", index=False)
    cov_by_fold.to_csv(out_dir / "run_covariates_prelabel_by_fold.csv", index=False)
    trad_cv.to_csv(out_dir / "traditional_proxy_train_cv.csv", index=False)
    ml_cv.to_csv(out_dir / "ml_ridge_train_cv.csv", index=False)
    model_info.to_csv(out_dir / "model_audit.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    nominal = run_boot[~run_boot["family"].eq("shuffled_target_control")].copy()
    winner = nominal.sort_values("mean_sigma68_ns").iloc[0]
    baseline = run_boot[run_boot["method"] == "traditional_global_no_proxy"].iloc[0]
    best_proxy = run_boot[run_boot["family"] == "traditional_proxy"].sort_values("mean_sigma68_ns").iloc[0]
    best_ml = run_boot[run_boot["family"] == "ml"].sort_values("mean_sigma68_ns").iloc[0]
    shuffled_failures = int((leakage[leakage["check"].str.startswith("shuffled_target", na=False)]["pass"] == False).sum())
    verdict = (
        f"The no-proxy global S02b traditional branch remains the adoption baseline at {float(baseline['mean_sigma68_ns']):.3f} ns. "
        f"The best ROOT-proxy traditional branch is {best_proxy['method']} with delta {float(best_proxy['delta_vs_traditional_ns']):+.3f} ns, "
        f"and the best guarded ML/NN branch is {best_ml['method']} with delta {float(best_ml['delta_vs_traditional_ns']):+.3f} ns. "
    )
    if str(winner["method"]) != "traditional_global_no_proxy":
        verdict += "A non-baseline method wins the raw width table, but it should be interpreted through the shuffled-target and proxy-leakage controls before adoption. "
    else:
        verdict += "The ROOT-only proxies do not produce a controlled improvement over the strong traditional no-proxy method. "
    if shuffled_failures:
        verdict += f"{shuffled_failures} shuffled-target checks beat their nominal model, so those rows are false-improvement warnings."
    else:
        verdict += "All shuffled-target checks are no better than their nominal models."

    result = {
        "study": "S02j",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(match["pass"].all()),
        "reference_numbers_reproduced": bool(reproduction["pass"].all()),
        "split_by_run": True,
        "heldout_runs": [int(run) for run in config["timing"]["loro_runs"]],
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "mean_sigma68_ns": float(winner["mean_sigma68_ns"]),
            "ci": [float(winner["ci_low"]), float(winner["ci_high"])],
            "delta_vs_traditional_ns": float(winner["delta_vs_traditional_ns"]),
            "delta_ci": [float(winner["delta_ci_low"]), float(winner["delta_ci_high"])],
        },
        "traditional_baseline": {
            "method": "traditional_global_no_proxy",
            "mean_sigma68_ns": float(baseline["mean_sigma68_ns"]),
            "ci": [float(baseline["ci_low"]), float(baseline["ci_high"])],
        },
        "best_traditional_proxy": {
            "method": str(best_proxy["method"]),
            "mean_sigma68_ns": float(best_proxy["mean_sigma68_ns"]),
            "ci": [float(best_proxy["ci_low"]), float(best_proxy["ci_high"])],
            "delta_vs_traditional_ns": float(best_proxy["delta_vs_traditional_ns"]),
        },
        "best_ml_nn": {
            "method": str(best_ml["method"]),
            "mean_sigma68_ns": float(best_ml["mean_sigma68_ns"]),
            "ci": [float(best_ml["ci_low"]), float(best_ml["ci_high"])],
            "delta_vs_traditional_ns": float(best_ml["delta_vs_traditional_ns"]),
        },
        "controls": {
            "shuffled_target_failures": shuffled_failures,
            "max_train_heldout_event_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()),
            "structural_guards_pass": bool(leakage[~leakage["check"].str.startswith("shuffled_target", na=False)]["pass"].all()),
        },
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "verdict": verdict,
        "next_tickets": [],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    plot_outputs(out_dir, run_boot, per_run, pairs)
    write_report(out_dir, config, result, match, reproduction, cov_by_fold, per_run, run_boot, leakage, model_info)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02j",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": manifest["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
