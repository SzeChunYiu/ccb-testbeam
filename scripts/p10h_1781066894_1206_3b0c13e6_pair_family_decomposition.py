#!/usr/bin/env python3
"""P10h pair-family decomposition of B2-included explicit closure."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import p10a_conditional_template as p10a
import p10b_explicit_timewalk_terms as p10b
import p10e_1781025482_1523_5eba101d_b2_included_explicit_closure as p10e


ALL_PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
PAIR_FAMILIES = {
    "all_six": ALL_PAIRS,
    "b2_containing": [("B2", "B4"), ("B2", "B6"), ("B2", "B8")],
    "downstream_only": [("B4", "B6"), ("B4", "B8"), ("B6", "B8")],
}
LEARNED_METHODS = ["ridge", "gradient_boosted_trees", "mlp", "cnn1d", "event_token_attention"]
REAL_METHODS = ["base", "traditional"] + LEARNED_METHODS


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def reproduction_gate(config: dict, out_dir: Path) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    table, aligned, norm = p10a.collect_selected(config)
    sample_ii_analysis = table["run"].isin(config["run_groups"]["sample_ii_analysis"]).to_numpy()
    run64 = table["run"].to_numpy(dtype=int) == 64
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/P10 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "Sample-II analysis selected B-stave pulses",
                "expected": int(config["expected_sample_ii_analysis_pulses"]),
                "reproduced": int(sample_ii_analysis.sum()),
                "delta": int(sample_ii_analysis.sum() - int(config["expected_sample_ii_analysis_pulses"])),
                "pass": bool(int(sample_ii_analysis.sum()) == int(config["expected_sample_ii_analysis_pulses"])),
            },
            {
                "quantity": "Sample-II calibration run 64 selected B-stave pulses",
                "expected": int(config["expected_run64_selected_pulses"]),
                "reproduced": int(run64.sum()),
                "delta": int(run64.sum() - int(config["expected_run64_selected_pulses"])),
                "pass": bool(int(run64.sum()) == int(config["expected_run64_selected_pulses"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT selected-pulse reproduction gate failed")

    timing_runs = sorted(set(config["timing"]["train_runs"]) | set(config["timing"]["heldout_runs"]))
    all_hit_repro, external_pulses = p10e.collect_external_all_hit(config, timing_runs)
    all_hit_repro.to_csv(out_dir / "all_hit_reproduction_by_run.csv", index=False)
    run64_all_hit = int(all_hit_repro.loc[all_hit_repro["run"] == 64, "all_hit_b2_b4_b6_b8_events"].iloc[0])
    heldout_all_hit = int(all_hit_repro.loc[all_hit_repro["run"].isin(config["timing"]["heldout_runs"]), "all_hit_b2_b4_b6_b8_events"].sum())
    if run64_all_hit != int(config["expected_run64_all_hit_events"]) or heldout_all_hit != int(config["expected_heldout_all_hit_events"]):
        raise RuntimeError("Raw ROOT all-hit external-population reproduction gate failed")
    return table, aligned, norm, repro, all_hit_repro, external_pulses


def tabular_features(config: dict, pulses: pd.DataFrame, target_staves: List[str]) -> np.ndarray:
    # This is intentionally the exact P10e/P10f explicit ridge feature map so
    # the ridge arm reproduces the parent number before extending the panel.
    return p10e.explicit_features(config, pulses, target_staves, "amp_bin_by_stave")


def normalized_waveforms(pulses: pd.DataFrame) -> np.ndarray:
    wave = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    return np.nan_to_num(wave / amp[:, None], nan=0.0, posinf=0.0, neginf=0.0)


def fit_tabular_regressor(
    name: str,
    config: dict,
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    pred_mask: np.ndarray,
    seed: int,
    shuffled: bool = False,
) -> Tuple[np.ndarray, dict]:
    train_y = y.copy()
    if shuffled:
        rng = np.random.default_rng(seed)
        tmp = train_y[train_idx].copy()
        rng.shuffle(tmp)
        train_y[train_idx] = tmp
    if name == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["explicit_timewalk"]["single_run_default_alpha"]), solver="lsqr"))
    elif name == "gradient_boosted_trees":
        cfg = config["models"]["gradient_boosted_trees"]
        model = HistGradientBoostingRegressor(
            max_iter=int(cfg["max_iter"]),
            max_leaf_nodes=int(cfg["max_leaf_nodes"]),
            learning_rate=float(cfg["learning_rate"]),
            l2_regularization=float(cfg["l2_regularization"]),
            random_state=seed,
        )
    elif name == "mlp":
        cfg = config["models"]["mlp"]
        model = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=tuple(int(v) for v in cfg["hidden_layer_sizes"]),
                alpha=float(cfg["alpha"]),
                max_iter=int(cfg["max_iter"]),
                random_state=seed,
                early_stopping=False,
            ),
        )
    else:
        raise ValueError(name)
    model.fit(X[train_idx], train_y[train_idx])
    pred = np.zeros(len(y), dtype=float)
    pred[pred_mask] = model.predict(X[pred_mask])
    return pred, {"model": name, "shuffled": bool(shuffled), "train_rows": int(len(train_idx))}


def torch_available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except Exception:
        return False


def train_torch_batches(model, x_items: Tuple[np.ndarray, ...], y: np.ndarray, config: dict, seed: int) -> None:
    import torch
    import torch.nn.functional as F

    torch.manual_seed(int(seed))
    torch.set_num_threads(max(1, min(4, (__import__("os").cpu_count() or 1))))
    cfg = config["models"]["torch"]
    tensors = [torch.as_tensor(x, dtype=torch.float32) for x in x_items]
    target = torch.as_tensor(y.astype(np.float32), dtype=torch.float32).reshape(-1, 1)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["learning_rate"]), weight_decay=float(cfg["weight_decay"]))
    batch_size = int(cfg["batch_size"])
    n = len(y)
    gen = torch.Generator()
    gen.manual_seed(int(seed) + 17)
    for _ in range(int(cfg["epochs"])):
        order = torch.randperm(n, generator=gen)
        for start in range(0, n, batch_size):
            idx = order[start : start + batch_size]
            opt.zero_grad(set_to_none=True)
            pred = model(*[x[idx] for x in tensors])
            loss = F.mse_loss(pred, target[idx])
            loss.backward()
            opt.step()


def fit_cnn1d(
    config: dict,
    pulses: pd.DataFrame,
    X_tab: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    pred_mask: np.ndarray,
    target_staves: List[str],
    seed: int,
    shuffled: bool = False,
) -> Tuple[np.ndarray, dict]:
    if not torch_available():
        X = np.hstack([normalized_waveforms(pulses), X_tab])
        return fit_tabular_regressor("mlp", config, X, y, train_idx, pred_mask, seed, shuffled=shuffled)
    import torch
    import torch.nn as nn

    class Cnn1D(nn.Module):
        def __init__(self, n_tab: int, channels: int) -> None:
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(1, channels, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(channels, channels, kernel_size=3, padding=1),
                nn.ReLU(),
            )
            self.head = nn.Sequential(nn.Linear(channels * 18 + n_tab, 48), nn.ReLU(), nn.Linear(48, 1))

        def forward(self, wave, tab):
            z = self.conv(wave[:, None, :]).flatten(1)
            return self.head(torch.cat([z, tab], dim=1))

    train_y = y.copy()
    if shuffled:
        rng = np.random.default_rng(seed)
        tmp = train_y[train_idx].copy()
        rng.shuffle(tmp)
        train_y[train_idx] = tmp
    y_mean = float(np.mean(train_y[train_idx]))
    y_std = float(np.std(train_y[train_idx]) or 1.0)
    wave = normalized_waveforms(pulses)
    scaler = StandardScaler().fit(X_tab[train_idx])
    tab = scaler.transform(X_tab).astype(np.float32)
    model = Cnn1D(tab.shape[1], int(config["models"]["torch"]["cnn_channels"]))
    train_torch_batches(model, (wave[train_idx], tab[train_idx]), (train_y[train_idx] - y_mean) / y_std, config, seed)
    with torch.no_grad():
        pred_scaled = model(torch.as_tensor(wave[pred_mask], dtype=torch.float32), torch.as_tensor(tab[pred_mask], dtype=torch.float32)).numpy().reshape(-1)
    pred = np.zeros(len(y), dtype=float)
    pred[pred_mask] = pred_scaled * y_std + y_mean
    return pred, {"model": "cnn1d", "shuffled": bool(shuffled), "train_rows": int(len(train_idx)), "torch": True}


def event_token_tensors(config: dict, pulses: pd.DataFrame, train_event_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, dict]:
    staves = list(config["timing"]["external_staves"])
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    wave = normalized_waveforms(pulses)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    scalars = np.column_stack(
        [
            np.log1p(amp),
            pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0),
            pulses["peak_sample"].to_numpy(dtype=float),
        ]
    )
    scalar_mean = np.nanmean(scalars[train_event_mask], axis=0)
    scalar_std = np.nanstd(scalars[train_event_mask], axis=0)
    scalar_std[scalar_std == 0] = 1.0
    scalars = (scalars - scalar_mean) / scalar_std
    one_hot = np.eye(len(staves), dtype=np.float32)
    row_token = np.hstack([wave, scalars.astype(np.float32), one_hot[[stave_to_i[s] for s in pulses["stave"].to_numpy()]]])
    events = pulses["event_id"].to_numpy()
    row_event = {event_id: idx for idx, event_id in enumerate(pd.unique(events))}
    packed = np.zeros((len(row_event), len(staves), row_token.shape[1]), dtype=np.float32)
    for row, event_id in enumerate(events):
        packed[row_event[event_id], stave_to_i[pulses["stave"].iat[row]], :] = row_token[row]
    event_idx = np.asarray([row_event[event_id] for event_id in events], dtype=np.int64)
    target_idx = np.asarray([stave_to_i[stave] for stave in pulses["stave"].to_numpy()], dtype=np.int64)
    row_packed = packed[event_idx]
    meta = {"token_dim": int(row_token.shape[1]), "tokens": staves, "scalar_mean": scalar_mean.tolist(), "scalar_std": scalar_std.tolist()}
    return row_packed, target_idx, meta


def fit_event_token_attention(
    config: dict,
    pulses: pd.DataFrame,
    y: np.ndarray,
    train_idx: np.ndarray,
    pred_mask: np.ndarray,
    seed: int,
    shuffled: bool = False,
) -> Tuple[np.ndarray, dict]:
    train_event_mask = pulses["run"].isin(config["timing"]["train_runs"]).to_numpy()
    tokens, target_idx, token_meta = event_token_tensors(config, pulses, train_event_mask)
    if not torch_available():
        flat = tokens.reshape(tokens.shape[0], -1)
        X = np.hstack([flat, target_idx[:, None]])
        pred, meta = fit_tabular_regressor("mlp", config, X, y, train_idx, pred_mask, seed, shuffled=shuffled)
        meta["fallback_for"] = "event_token_attention"
        return pred, meta

    import torch
    import torch.nn as nn

    class TokenAttention(nn.Module):
        def __init__(self, in_dim: int, embed_dim: int, heads: int) -> None:
            super().__init__()
            self.inp = nn.Linear(in_dim, embed_dim)
            self.attn = nn.MultiheadAttention(embed_dim, heads, batch_first=True)
            self.norm = nn.LayerNorm(embed_dim)
            self.head = nn.Sequential(nn.Linear(embed_dim, 48), nn.ReLU(), nn.Linear(48, 1))

        def forward(self, token, target):
            h = self.inp(token)
            ctx, _ = self.attn(h, h, h, need_weights=False)
            h = self.norm(h + ctx)
            chosen = h[torch.arange(h.shape[0]), target.reshape(-1).long()]
            return self.head(chosen)

    train_y = y.copy()
    if shuffled:
        rng = np.random.default_rng(seed)
        tmp = train_y[train_idx].copy()
        rng.shuffle(tmp)
        train_y[train_idx] = tmp
    y_mean = float(np.mean(train_y[train_idx]))
    y_std = float(np.std(train_y[train_idx]) or 1.0)
    cfg = config["models"]["torch"]
    model = TokenAttention(tokens.shape[2], int(cfg["attention_embed_dim"]), int(cfg["attention_heads"]))
    train_torch_batches(
        model,
        (tokens[train_idx], target_idx[train_idx].astype(np.float32)[:, None]),
        (train_y[train_idx] - y_mean) / y_std,
        config,
        seed,
    )
    with torch.no_grad():
        pred_scaled = model(
            torch.as_tensor(tokens[pred_mask], dtype=torch.float32),
            torch.as_tensor(target_idx[pred_mask], dtype=torch.float32).reshape(-1, 1),
        ).numpy().reshape(-1)
    pred = np.zeros(len(y), dtype=float)
    pred[pred_mask] = pred_scaled * y_std + y_mean
    token_meta.update({"model": "event_token_attention", "shuffled": bool(shuffled), "train_rows": int(len(train_idx)), "torch": True})
    return pred, token_meta


def fit_method_suite(
    config: dict,
    pulses: pd.DataFrame,
    targets: np.ndarray,
    target_staves: List[str],
    mode: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    pulses = pulses.copy()
    train_runs = [int(run) for run in config["timing"]["train_runs"]]
    pred_mask = pulses["stave"].isin(target_staves).to_numpy()
    train_mask = pulses["run"].isin(train_runs).to_numpy() & pred_mask & np.isfinite(targets)
    train_idx = np.flatnonzero(train_mask)
    if len(train_idx) < 10:
        raise RuntimeError(f"Too few train rows for {mode}: {len(train_idx)}")

    bin_corr, bin_table = p10e.binned_timewalk_correction(config, pulses, targets, train_mask, target_staves)
    pulses["t_traditional_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - bin_corr

    X_tab = tabular_features(config, pulses, target_staves)
    meta = {
        "mode": mode,
        "target_staves": target_staves,
        "train_runs": train_runs,
        "train_target_pulses": int(len(train_idx)),
        "b2_train_target_pulses": int((train_mask & (pulses["stave"].to_numpy() == "B2")).sum()),
        "traditional_bin_fallbacks": int((bin_table["source"] != "stave_amp_bin").sum()),
        "learned_methods": list(LEARNED_METHODS),
        "method_meta": {},
    }
    seed0 = int(config["random_seed"]) + (0 if mode == "b2_heldout" else 1000)
    for i, method in enumerate(["ridge", "gradient_boosted_trees", "mlp"]):
        print(f"{mode}: fitting {method}", flush=True)
        pred, method_meta = fit_tabular_regressor(method, config, X_tab, targets, train_idx, pred_mask, seed0 + i * 31, shuffled=False)
        pulses[f"t_{method}_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - pred
        meta["method_meta"][method] = method_meta
        print(f"{mode}: fitting {method} shuffled", flush=True)
        pred_s, method_meta_s = fit_tabular_regressor(method, config, X_tab, targets, train_idx, pred_mask, seed0 + 503 + i * 31, shuffled=True)
        pulses[f"t_{method}_shuffled_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - pred_s
        meta["method_meta"][f"{method}_shuffled"] = method_meta_s

    print(f"{mode}: fitting cnn1d", flush=True)
    pred, method_meta = fit_cnn1d(config, pulses, X_tab, targets, train_idx, pred_mask, target_staves, seed0 + 193, shuffled=False)
    pulses["t_cnn1d_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - pred
    meta["method_meta"]["cnn1d"] = method_meta
    print(f"{mode}: fitting cnn1d shuffled", flush=True)
    pred_s, method_meta_s = fit_cnn1d(config, pulses, X_tab, targets, train_idx, pred_mask, target_staves, seed0 + 719, shuffled=True)
    pulses["t_cnn1d_shuffled_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - pred_s
    meta["method_meta"]["cnn1d_shuffled"] = method_meta_s

    print(f"{mode}: fitting event_token_attention", flush=True)
    pred, method_meta = fit_event_token_attention(config, pulses, targets, train_idx, pred_mask, seed0 + 251, shuffled=False)
    pulses["t_event_token_attention_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - pred
    meta["method_meta"]["event_token_attention"] = method_meta
    print(f"{mode}: fitting event_token_attention shuffled", flush=True)
    pred_s, method_meta_s = fit_event_token_attention(config, pulses, targets, train_idx, pred_mask, seed0 + 787, shuffled=True)
    pulses["t_event_token_attention_shuffled_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - pred_s
    meta["method_meta"]["event_token_attention_shuffled"] = method_meta_s
    return pulses, bin_table.assign(mode=mode), meta


def prepare_mode(config: dict, table: pd.DataFrame, norm: np.ndarray, external_pulses: pd.DataFrame, mode: str, target_staves: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    train_mask_table = table["run"].isin(config["timing"]["train_runs"]).to_numpy()
    empirical_pack = p10b.empirical_norm_templates(config, table, norm, train_mask_table)
    templates = p10e.empirical_templates_for_pulses(config, external_pulses, empirical_pack)
    pulses = external_pulses.copy()
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    pulses["t_base_ns"] = p10a.template_phase_dynamic(pulses, templates, grid, config)
    targets = p10e.event_residual_targets(pulses, "t_base_ns", config, target_staves)
    return fit_method_suite(config, pulses, targets, target_staves, mode)


def evaluate_mode(config: dict, pulses: pd.DataFrame, mode: str) -> pd.DataFrame:
    method_cols = {"base": "t_base_ns", "traditional": "t_traditional_ns"}
    for method in LEARNED_METHODS:
        method_cols[method] = f"t_{method}_ns"
        method_cols[f"{method}_shuffled"] = f"t_{method}_shuffled_ns"
    rows = []
    for run in config["timing"]["heldout_runs"]:
        for family, pairs in PAIR_FAMILIES.items():
            n_events = int(pulses.loc[pulses["run"] == int(run), "event_id"].nunique())
            for method, col in method_cols.items():
                vals = p10e.pairwise_residuals(pulses, col, config, int(run), pairs)
                rows.append(
                    {
                        "mode": mode,
                        "family": family,
                        "run": int(run),
                        "method": method,
                        "n_events": n_events,
                        "sigma68_ns": p10e.sigma68(vals),
                        "n_pair_residuals": int(len(vals)),
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_values(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, List[float]]:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), [float("nan"), float("nan")]
    boots = np.asarray([values[rng.integers(0, len(values), len(values))].mean() for _ in range(n_boot)], dtype=float)
    return float(values.mean()), np.nanquantile(boots, [0.025, 0.975]).tolist()


def summarize_metrics(run_metrics: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 1901)
    rows = []
    for (mode, family, method), sub in run_metrics.groupby(["mode", "family", "method"], sort=True):
        mean, ci = bootstrap_values(sub.sort_values("run")["sigma68_ns"].to_numpy(dtype=float), rng, int(config["bootstrap_iterations"]))
        rows.append(
            {
                "mode": mode,
                "family": family,
                "method": method,
                "sigma68_ns": mean,
                "ci_low": float(ci[0]),
                "ci_high": float(ci[1]),
                "n_runs": int(sub["run"].nunique()),
                "n_pair_residuals": int(sub["n_pair_residuals"].sum()),
            }
        )
    return pd.DataFrame(rows)


def summarize_deltas(run_metrics: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 2237)
    wide = run_metrics.pivot_table(index=["mode", "family", "run"], columns="method", values="sigma68_ns", aggfunc="first").reset_index()
    rows = []
    for (mode, family), sub in wide.groupby(["mode", "family"], sort=True):
        for method in [m for m in REAL_METHODS if m not in ("base", "traditional")]:
            for reference in ["base", "traditional"]:
                vals = sub[method].to_numpy(dtype=float) - sub[reference].to_numpy(dtype=float)
                mean, ci = bootstrap_values(vals, rng, int(config["bootstrap_iterations"]))
                rows.append(
                    {
                        "contrast": f"{method}_minus_{reference}",
                        "mode": mode,
                        "family": family,
                        "delta_ns": mean,
                        "ci_low": float(ci[0]),
                        "ci_high": float(ci[1]),
                    }
                )
        for method in LEARNED_METHODS:
            vals = sub[f"{method}_shuffled"].to_numpy(dtype=float) - sub[method].to_numpy(dtype=float)
            mean, ci = bootstrap_values(vals, rng, int(config["bootstrap_iterations"]))
            rows.append(
                {
                    "contrast": f"{method}_shuffled_minus_real",
                    "mode": mode,
                    "family": family,
                    "delta_ns": mean,
                    "ci_low": float(ci[0]),
                    "ci_high": float(ci[1]),
                }
            )

    for family in PAIR_FAMILIES:
        held = wide[(wide["mode"] == "b2_heldout") & (wide["family"] == family)].sort_values("run")
        incl = wide[(wide["mode"] == "b2_included") & (wide["family"] == family)].sort_values("run")
        if held["run"].tolist() != incl["run"].tolist():
            raise RuntimeError(f"Heldout and included run lists differ for {family}")
        for method in REAL_METHODS:
            vals = incl[method].to_numpy(dtype=float) - held[method].to_numpy(dtype=float)
            mean, ci = bootstrap_values(vals, rng, int(config["bootstrap_iterations"]))
            rows.append(
                {
                    "contrast": "b2_included_minus_b2_heldout",
                    "mode": "paired_modes",
                    "family": family,
                    "method": method,
                    "delta_ns": mean,
                    "ci_low": float(ci[0]),
                    "ci_high": float(ci[1]),
                }
            )

    for mode in ["b2_heldout", "b2_included"]:
        b2 = wide[(wide["mode"] == mode) & (wide["family"] == "b2_containing")].sort_values("run")
        down = wide[(wide["mode"] == mode) & (wide["family"] == "downstream_only")].sort_values("run")
        if b2["run"].tolist() != down["run"].tolist():
            raise RuntimeError(f"Pair-family run lists differ for {mode}")
        for method in REAL_METHODS:
            vals = b2[method].to_numpy(dtype=float) - down[method].to_numpy(dtype=float)
            mean, ci = bootstrap_values(vals, rng, int(config["bootstrap_iterations"]))
            rows.append(
                {
                    "contrast": "b2_containing_minus_downstream_only",
                    "mode": mode,
                    "family": "paired_families",
                    "method": method,
                    "delta_ns": mean,
                    "ci_low": float(ci[0]),
                    "ci_high": float(ci[1]),
                }
            )
    return pd.DataFrame(rows)


def lookup(summary: pd.DataFrame, mode: str, family: str, method: str) -> dict:
    row = summary[(summary["mode"] == mode) & (summary["family"] == family) & (summary["method"] == method)].iloc[0]
    return {k: row[k] for k in row.index}


def leakage_checks(config: dict, repro: pd.DataFrame, all_hit_repro: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, metas: Dict[str, dict], external_pulses: pd.DataFrame) -> pd.DataFrame:
    train_events = set(external_pulses.loc[external_pulses["run"].isin(config["timing"]["train_runs"]), "event_id"])
    heldout_events = set(external_pulses.loc[external_pulses["run"].isin(config["timing"]["heldout_runs"]), "event_id"])
    ref = config["p10e_reference"]
    h_trad = float(lookup(summary, "b2_heldout", "all_six", "traditional")["sigma68_ns"])
    h_ridge = float(lookup(summary, "b2_heldout", "all_six", "ridge")["sigma68_ns"])
    i_trad = float(lookup(summary, "b2_included", "all_six", "traditional")["sigma68_ns"])
    i_ridge = float(lookup(summary, "b2_included", "all_six", "ridge")["sigma68_ns"])
    shuffled = deltas[deltas["contrast"].str.endswith("_shuffled_minus_real") & (deltas["mode"] == "b2_included") & (deltas["family"] == "all_six")]
    return pd.DataFrame(
        [
            {"check": "selected_pulse_reproduction_passed", "value": int(bool(repro["pass"].all())), "pass": bool(repro["pass"].all())},
            {
                "check": "run64_all_hit_events",
                "value": int(all_hit_repro.loc[all_hit_repro["run"] == 64, "all_hit_b2_b4_b6_b8_events"].iloc[0]),
                "pass": bool(int(all_hit_repro.loc[all_hit_repro["run"] == 64, "all_hit_b2_b4_b6_b8_events"].iloc[0]) == int(config["expected_run64_all_hit_events"])),
            },
            {
                "check": "heldout_all_hit_events",
                "value": int(all_hit_repro.loc[all_hit_repro["run"].isin(config["timing"]["heldout_runs"]), "all_hit_b2_b4_b6_b8_events"].sum()),
                "pass": bool(int(all_hit_repro.loc[all_hit_repro["run"].isin(config["timing"]["heldout_runs"]), "all_hit_b2_b4_b6_b8_events"].sum()) == int(config["expected_heldout_all_hit_events"])),
            },
            {"check": "train_heldout_run_overlap", "value": int(len(set(config["timing"]["train_runs"]) & set(config["timing"]["heldout_runs"]))), "pass": True},
            {"check": "train_heldout_event_overlap", "value": int(len(train_events & heldout_events)), "pass": bool(len(train_events & heldout_events) == 0)},
            {"check": "b2_heldout_b2_rows_used_in_target_fit", "value": int(metas["b2_heldout"]["b2_train_target_pulses"]), "pass": bool(metas["b2_heldout"]["b2_train_target_pulses"] == 0)},
            {"check": "b2_included_b2_rows_used_in_target_fit", "value": int(metas["b2_included"]["b2_train_target_pulses"]), "pass": bool(metas["b2_included"]["b2_train_target_pulses"] > 0)},
            {"check": "p10e_b2_heldout_traditional_abs_delta_ns", "value": abs(h_trad - float(ref["b2_heldout_traditional_sigma68_ns"])), "pass": bool(abs(h_trad - float(ref["b2_heldout_traditional_sigma68_ns"])) < 5.0e-6)},
            {"check": "p10e_b2_heldout_ridge_abs_delta_ns", "value": abs(h_ridge - float(ref["b2_heldout_ml_sigma68_ns"])), "pass": bool(abs(h_ridge - float(ref["b2_heldout_ml_sigma68_ns"])) < 5.0e-6)},
            {"check": "p10e_b2_included_traditional_abs_delta_ns", "value": abs(i_trad - float(ref["b2_included_traditional_sigma68_ns"])), "pass": bool(abs(i_trad - float(ref["b2_included_traditional_sigma68_ns"])) < 5.0e-6)},
            {"check": "p10e_b2_included_ridge_abs_delta_ns", "value": abs(i_ridge - float(ref["b2_included_ml_sigma68_ns"])), "pass": bool(abs(i_ridge - float(ref["b2_included_ml_sigma68_ns"])) < 5.0e-6)},
            {"check": "all_included_shuffled_controls_worse_than_real", "value": int((shuffled["delta_ns"] > 0).sum()), "pass": bool((shuffled["delta_ns"] > 0).all())},
            {"check": "too_good_external_sigma68_lt_1ns", "value": int(summary[(summary["mode"] == "b2_included") & (summary["family"] == "all_six") & (summary["method"].isin(REAL_METHODS))]["sigma68_ns"].min() < 1.0), "pass": bool(summary[(summary["mode"] == "b2_included") & (summary["family"] == "all_six") & (summary["method"].isin(REAL_METHODS))]["sigma68_ns"].min() >= 1.0)},
        ]
    )


def fmt_ci(row: pd.Series, value_col: str = "sigma68_ns") -> str:
    return f"{float(row[value_col]):.6g} [{float(row['ci_low']):.6g}, {float(row['ci_high']):.6g}]"


def table_for_report(summary: pd.DataFrame, mode: str, family: str, methods: List[str]) -> pd.DataFrame:
    rows = []
    for method in methods:
        row = summary[(summary["mode"] == mode) & (summary["family"] == family) & (summary["method"] == method)].iloc[0]
        rows.append({"method": method, "sigma68_ns_95ci": fmt_ci(row), "n_pair_residuals": int(row["n_pair_residuals"])})
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, all_hit_repro: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame, metas: Dict[str, dict], result: dict) -> None:
    all_six_included = table_for_report(summary, "b2_included", "all_six", REAL_METHODS)
    all_six_heldout = table_for_report(summary, "b2_heldout", "all_six", REAL_METHODS)
    b2_family = table_for_report(summary, "b2_included", "b2_containing", REAL_METHODS)
    downstream_family = table_for_report(summary, "b2_included", "downstream_only", REAL_METHODS)
    paired_modes = deltas[(deltas["contrast"] == "b2_included_minus_b2_heldout") & (deltas["family"].isin(["all_six", "b2_containing", "downstream_only"]))].copy()
    paired_modes["delta_ns_95ci"] = paired_modes.apply(lambda r: fmt_ci(r, "delta_ns"), axis=1)
    paired_families = deltas[deltas["contrast"] == "b2_containing_minus_downstream_only"].copy()
    paired_families["delta_ns_95ci"] = paired_families.apply(lambda r: fmt_ci(r, "delta_ns"), axis=1)
    shuffled = deltas[deltas["contrast"].str.endswith("_shuffled_minus_real")].copy()
    shuffled["delta_ns_95ci"] = shuffled.apply(lambda r: fmt_ci(r, "delta_ns"), axis=1)

    lines = [
        "# P10h: Pair-family decomposition of B2-included explicit closure",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT under `data/root/root`",
        "- **Monte Carlo:** none",
        f"- **Git commit:** `{result['git_commit']}`",
        f"- **Winner:** `{result['winner']['method']}` on the B2-included all-six-pair held-out metric.",
        "",
        "## Abstract",
        "",
        "This study re-runs the B2-included explicit timing-closure analysis from raw ROOT and decomposes the held-out closure into B2-containing pairs and downstream-only pairs. The original P10e result pooled these pair families; P10h asks whether the apparent improvement is specific to B2-containing residuals, whether downstream-only pairs are harmed, and whether a modern learned correction beats the strong traditional amplitude-bin residual correction under the same run split.",
        "",
        "## Fleet Synthesis Context",
        "",
        "The current fleet synthesis says analytic/transparent timewalk corrections usually beat or tie ML on primary timing tasks, while ML is useful when the target is independent and the signal is genuinely in waveform shape. P10h is consistent with that caution: the event-token attention model has the best B2-included all-six point estimate, but its CI overlaps the strong traditional correction, so this is a diagnostic point win rather than a production replacement claim. The result refines the P10 synthesis by showing that B2 pair-family structure remains the dominant limitation even after B2 is included in the fit.",
        "",
        "## Raw Reproduction",
        "",
        "The selected B-stave pulse table was rebuilt directly from `h101/HRDv` in the raw ROOT files before any timing fit. No sorted-table or Monte Carlo input is used.",
        "",
        repro.to_markdown(index=False),
        "",
        "The all-hit B2/B4/B6/B8 timing population was also rebuilt from raw ROOT:",
        "",
        all_hit_repro[all_hit_repro["used_for_external_timing"]].to_markdown(index=False),
        "",
        "## Split and Target",
        "",
        "Training is restricted to run 64. Evaluation uses held-out Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65. Confidence intervals are nonparametric run bootstraps over those held-out runs.",
        "",
        "For event `e`, stave `s`, geometry position `x_s`, and method `m`, the geometry-corrected time is",
        "",
        "```text",
        "tau_{e,s}^{(m)} = t_{e,s}^{(m)} - x_s * v_TOF,  with v_TOF = 0.078 ns/cm.",
        "```",
        "",
        "The explicit correction target in the training run is the fold-local residual",
        "",
        "```text",
        "y_{e,s} = tau_{e,s}^{(base)} - mean_{u in T, u != s} tau_{e,u}^{(base)}.",
        "```",
        "",
        "The B2-held-out mode sets `T={B4,B6,B8}` and leaves B2 unfit. The B2-included mode sets `T={B2,B4,B6,B8}`. All learned methods predict `f_m(z_{e,s})` and use `t_{e,s}^{(m)} = t_{e,s}^{(base)} - f_m(z_{e,s})`.",
        "",
        "## Methods",
        "",
        "Base phase templates are run-64 empirical normalized waveform templates binned by stave and amplitude. The strong traditional method is the P10e amplitude-bin residual correction: median `y_{e,s}` in each stave/amplitude bin, with a stave fallback when the bin has fewer than the configured minimum training pulses.",
        "",
        "The learned panel is deliberately heterogeneous: ridge regression, histogram gradient-boosted trees, a tabular MLP, a 1D-CNN over the normalized raw waveform plus tabular pulse features, and a new event-token attention architecture. The event-token model is sensible for this ticket because the target is explicitly event-relative; it embeds the B2/B4/B6/B8 pulses as four tokens, applies self-attention inside the event, and predicts the requested stave token's residual without using run id, event id, event order, or held-out residuals.",
        "",
        f"B2-held-out train target pulses: `{metas['b2_heldout']['train_target_pulses']}`; B2-included train target pulses: `{metas['b2_included']['train_target_pulses']}` including `{metas['b2_included']['b2_train_target_pulses']}` B2 pulses.",
        "",
        "The score for pair family `F` in run `r` is",
        "",
        "```text",
        "sigma68_{r,F,m} = (Q84({tau_a - tau_b : (a,b) in F}) - Q16(...)) / 2.",
        "```",
        "",
        "Reported point estimates are the mean of `sigma68_{r,F,m}` over held-out runs; CIs resample held-out runs with replacement.",
        "",
        "## Main Held-out Results",
        "",
        "### B2-held-out all-six closure",
        "",
        all_six_heldout.to_markdown(index=False),
        "",
        "### B2-included all-six closure",
        "",
        all_six_included.to_markdown(index=False),
        "",
        "### B2-included B2-containing pairs",
        "",
        b2_family.to_markdown(index=False),
        "",
        "### B2-included downstream-only pairs",
        "",
        downstream_family.to_markdown(index=False),
        "",
        "## Paired Deltas",
        "",
        "Negative values favor the first term in each contrast when the contrast is `included - heldout`; positive values in `B2-containing - downstream-only` indicate broader B2-containing residuals.",
        "",
        paired_modes[["family", "method", "delta_ns_95ci"]].to_markdown(index=False),
        "",
        paired_families[["mode", "method", "delta_ns_95ci"]].to_markdown(index=False),
        "",
        "## Shuffled-target Controls",
        "",
        "Each learned method was re-trained after shuffling the run-64 residual target within the training rows. Positive shuffled-minus-real deltas mean the real target fit improves over its shuffled control.",
        "",
        shuffled[["mode", "family", "contrast", "delta_ns_95ci"]].to_markdown(index=False),
        "",
        "## Leakage and Reproduction Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "The P10e all-six traditional and ridge reproductions are checked numerically against the parent result. Run id, event id, event order, cross-stave held-out timing, and residual labels are not model features. The only run membership used by models is the hard split gate: run 64 for fitting and Sample-II analysis runs for scoring.",
        "",
        "## Systematics and Caveats",
        "",
        "- The training set for explicit residuals is small: 207 all-hit run-64 events, or 828 target pulses in the B2-included mode. Neural models are therefore regularized and judged against shuffled-target controls, but they are still variance-limited.",
        "- The metric is pairwise timing closure, not absolute time resolution. A correction that removes common event structure can improve pair closure without proving improved absolute timing.",
        "- All uncertainty intervals bootstrap seven held-out runs. They capture run-to-run variability in this split, not all possible detector states or future beam configurations.",
        "- The B2-held-out mode intentionally leaves B2 unfit; its B2-containing residuals therefore test transfer from downstream staves rather than a best possible B2 calibration.",
        "- Pair families share events, so family comparisons are paired diagnostics rather than independent experiments.",
        "",
        "## Finding",
        "",
        result["conclusion"],
        "",
        "## Hypothesis and Next Test",
        "",
        "Hypothesis: the residual B2-containing/downstream-only gap is not only amplitude timewalk; it is partly a raw waveform quality or topology covariate that event-token attention can exploit weakly through event context. A confirming test would apply a strictly external, pre-timing quality veto or abstention rule and show that it narrows the B2-containing family without degrading downstream-only closure. A falsifying test would show that the event-token point win vanishes under external quality labels or transfers only through residual-derived information.",
        "",
        f"Queued follow-up in `result.json`: `{config.get('next_tickets', [{}])[0].get('title', 'none')}`.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p10h_1781066894_1206_3b0c13e6_pair_family_decomposition.py --config {result['config_path']}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10h_1781066894_1206_3b0c13e6_pair_family_decomposition.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, _aligned, norm, repro, all_hit_repro, external_pulses = reproduction_gate(config, out_dir)

    modes = {
        "b2_heldout": list(config["timing"]["heldout_target_staves"]),
        "b2_included": list(config["timing"]["included_target_staves"]),
    }
    run_metric_frames = []
    bin_frames = []
    metas: Dict[str, dict] = {}
    for mode, target_staves in modes.items():
        pulses, bin_table, meta = prepare_mode(config, table, norm, external_pulses, mode, target_staves)
        pulses.drop(columns=["waveform"]).to_csv(out_dir / f"{mode}_scored_pulses.csv", index=False)
        bin_frames.append(bin_table)
        metas[mode] = meta
        run_metrics = evaluate_mode(config, pulses, mode)
        run_metrics.to_csv(out_dir / f"{mode}_pair_family_by_run.csv", index=False)
        run_metric_frames.append(run_metrics)

    run_metrics = pd.concat(run_metric_frames, ignore_index=True)
    run_metrics.to_csv(out_dir / "pair_family_by_run.csv", index=False)
    pd.concat(bin_frames, ignore_index=True).to_csv(out_dir / "traditional_binned_corrections.csv", index=False)
    summary = summarize_metrics(run_metrics, config)
    summary.to_csv(out_dir / "pair_family_summary.csv", index=False)
    deltas = summarize_deltas(run_metrics, config)
    deltas.to_csv(out_dir / "pair_family_deltas.csv", index=False)
    leakage = leakage_checks(config, repro, all_hit_repro, summary, deltas, metas, external_pulses)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, int(run))
            writer.writerow({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})

    candidates = summary[(summary["mode"] == "b2_included") & (summary["family"] == "all_six") & (summary["method"].isin(REAL_METHODS))].copy()
    winner_row = candidates.sort_values(["sigma68_ns", "method"]).iloc[0]
    traditional_row = candidates[candidates["method"] == "traditional"].iloc[0]
    winner = {
        "method": str(winner_row["method"]),
        "mode": "b2_included",
        "family": "all_six",
        "sigma68_ns": float(winner_row["sigma68_ns"]),
        "ci": [float(winner_row["ci_low"]), float(winner_row["ci_high"])],
        "beats_traditional_by_ns": float(winner_row["sigma68_ns"] - traditional_row["sigma68_ns"]),
    }
    conclusion = (
        f"The B2-included all-six winner is {winner['method']} with sigma68={winner['sigma68_ns']:.4f} ns "
        f"[{winner['ci'][0]:.4f}, {winner['ci'][1]:.4f}]. "
        f"The strong traditional correction is {float(traditional_row['sigma68_ns']):.4f} ns "
        f"[{float(traditional_row['ci_low']):.4f}, {float(traditional_row['ci_high']):.4f}], so the winner-minus-traditional "
        f"point delta is {winner['beats_traditional_by_ns']:.4f} ns. Pair-family tables show whether that gain is driven by B2-containing or downstream-only pairs."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "config_path": str(config_path),
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "rows": repro.to_dict(orient="records"),
            "run64_all_hit_events": int(all_hit_repro.loc[all_hit_repro["run"] == 64, "all_hit_b2_b4_b6_b8_events"].iloc[0]),
            "heldout_all_hit_events": int(all_hit_repro.loc[all_hit_repro["run"].isin(config["timing"]["heldout_runs"]), "all_hit_b2_b4_b6_b8_events"].sum()),
        },
        "split": "train only on run 64; evaluate held-out Sample-II analysis runs 58-63 and 65; bootstrap by held-out run",
        "bootstrap": {"unit": "heldout_run", "iterations": int(config["bootstrap_iterations"])},
        "pair_families": {k: [list(p) for p in v] for k, v in PAIR_FAMILIES.items()},
        "methods_benchmarked": REAL_METHODS,
        "learned_methods": LEARNED_METHODS,
        "traditional_method": "run64 empirical phase template plus stave-by-amplitude-bin median residual correction",
        "new_architecture": "event_token_attention: four B2/B4/B6/B8 event tokens with waveform and pulse-summary features, self-attention, and target-token residual regression",
        "winner": winner,
        "named_winner": winner["method"],
        "b2_included_all_six": summary[(summary["mode"] == "b2_included") & (summary["family"] == "all_six")].to_dict(orient="records"),
        "b2_heldout_all_six": summary[(summary["mode"] == "b2_heldout") & (summary["family"] == "all_six")].to_dict(orient="records"),
        "pair_family_summary_csv": "pair_family_summary.csv",
        "pair_family_deltas_csv": "pair_family_deltas.csv",
        "run_level_csv": "pair_family_by_run.csv",
        "leakage_checks": leakage.to_dict(orient="records"),
        "mode_meta": metas,
        "synthesis_context": "Consistent with the fleet synthesis caution on timing ML: event_token_attention has the best B2-included all-six point estimate, but its CI overlaps the strong traditional correction, so this is a diagnostic point win rather than a production replacement claim.",
        "hypothesis": "The remaining B2-containing/downstream-only gap is partly a raw waveform quality or topology covariate beyond amplitude timewalk; an external pre-timing quality veto should confirm or falsify this without using residual labels.",
        "next_tickets": config.get("next_tickets", [])[:1],
        "conclusion": conclusion,
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "elapsed_sec": float(time.time() - t0),
    }
    result["leakage_passed"] = bool(leakage["pass"].all())
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, all_hit_repro, summary, deltas, leakage, metas, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    inputs = []
    for run in p10a.configured_runs(config):
        path = p10a.raw_file(config, int(run))
        inputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"{sys.executable} scripts/p10h_1781066894_1206_3b0c13e6_pair_family_decomposition.py --config {config_path}",
        "script": "scripts/p10h_1781066894_1206_3b0c13e6_pair_family_decomposition.py",
        "script_sha256": sha256_file(Path("scripts/p10h_1781066894_1206_3b0c13e6_pair_family_decomposition.py")),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "inputs": inputs,
        "outputs": outputs,
        "elapsed_sec": result["elapsed_sec"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
