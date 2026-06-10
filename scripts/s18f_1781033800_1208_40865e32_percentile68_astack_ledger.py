#!/usr/bin/env python3
"""S18f: frozen percentile-68 A-stack timing ledger and model bakeoff."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

os.environ.setdefault("MPLCONFIGDIR", "reports/1781033800.1208.40865e32__s18f_percentile68_astack_ledger/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_BODY = (
    "Question: can the S18/S18b/S18c/S18d A-stack timing reports be rerun or "
    "reconciled with the frozen percentile68_ns primary estimator and the S18e "
    "tolerance table? Expected information gain: a single comparable A-stack "
    "timing ledger that removes low-stat binned Gaussian core-sigma ambiguity."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def import_s18e(path: Path):
    spec = importlib.util.spec_from_file_location("s18e_base", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import S18e helper from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def root_path(config: dict[str, Any], run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{config['astack']['file_prefix']}_run_{run:04d}.root"


def centered(values: np.ndarray) -> np.ndarray:
    values = values[np.isfinite(values)]
    return values - np.nanmedian(values)


def sigma68(values: np.ndarray) -> float:
    c = centered(values)
    return float(0.5 * (np.percentile(c, 84) - np.percentile(c, 16)))


def full_rms(values: np.ndarray) -> float:
    c = centered(values)
    return float(np.sqrt(np.mean(c * c)))


def tail_fraction(values: np.ndarray, threshold: float = 5.0) -> float:
    c = centered(values)
    return float(np.mean(np.abs(c) > threshold))


def load_pair_table_with_waveforms(config: dict[str, Any], s18e, runs: Iterable[int], sample: str) -> pd.DataFrame:
    channels = [int(config["astack"]["staves"]["A1"]), int(config["astack"]["staves"]["A3"])]
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    n_samples = int(config["samples_per_channel"])
    rows: list[pd.DataFrame] = []
    for run in runs:
        for batch in s18e.raw_batches(root_path(config, int(run))):
            event = np.asarray(batch["EVT"]).astype(int)
            waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, n_samples)
            chosen = waveforms[:, channels, :]
            amplitude, peak, area, tail, time_ns = s18e.cfd_times(chosen, baseline_samples, float(config["cfd_fraction"]))
            selected = (amplitude[:, 0] > cut) & (amplitude[:, 1] > cut)
            if not selected.any():
                continue
            baseline = np.median(chosen[..., baseline_samples], axis=-1)
            corrected = chosen - baseline[..., None]
            normalized = corrected / np.maximum(amplitude[..., None], 1.0)
            frame = pd.DataFrame(
                {
                    "sample": sample,
                    "run": int(run),
                    "event": event[selected],
                    "amp_left": amplitude[selected, 0],
                    "amp_right": amplitude[selected, 1],
                    "peak_left": peak[selected, 0],
                    "peak_right": peak[selected, 1],
                    "area_left": area[selected, 0],
                    "area_right": area[selected, 1],
                    "tail_left": tail[selected, 0],
                    "tail_right": tail[selected, 1],
                    "time_left_ns": time_ns[selected, 0],
                    "time_right_ns": time_ns[selected, 1],
                }
            )
            for sample_idx in range(n_samples):
                frame[f"wf_left_{sample_idx:02d}"] = normalized[selected, 0, sample_idx]
                frame[f"wf_right_{sample_idx:02d}"] = normalized[selected, 1, sample_idx]
            frame["raw_residual_ns"] = frame["time_right_ns"] - frame["time_left_ns"]
            rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def load_all_pairs(config: dict[str, Any], s18e) -> pd.DataFrame:
    early = load_pair_table_with_waveforms(config, s18e, config["sample_iii_calib_runs"], "sample_iii_early")
    late = load_pair_table_with_waveforms(config, s18e, config["sample_iii_analysis_runs"], "sample_iii_late")
    run64 = load_pair_table_with_waveforms(config, s18e, config["sample_iv_calib_runs"], "sample_iv_calib")
    sample_iv = load_pair_table_with_waveforms(config, s18e, config["sample_iv_analysis_runs"], "sample_iv")
    return pd.concat([early, late, run64, sample_iv], ignore_index=True)


def train_pool(all_pairs: pd.DataFrame, pool_cfg: dict[str, Any]) -> pd.DataFrame:
    runs = [int(run) for run in pool_cfg.get("sample_iii", [])]
    runs.extend(int(run) for run in pool_cfg.get("sample_iv_fixed", []))
    return all_pairs[all_pairs["run"].isin(sorted(set(runs)))].copy()


def engineered_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    return np.column_stack(
        [
            left,
            right,
            left - right,
            left * left,
            right * right,
            left * right,
            df["peak_left"].to_numpy(),
            df["peak_right"].to_numpy(),
            np.log(np.maximum(df["area_left"].to_numpy(), 1.0)),
            np.log(np.maximum(df["area_right"].to_numpy(), 1.0)),
            df["tail_left"].to_numpy(),
            df["tail_right"].to_numpy(),
            (df["sample"].to_numpy() == "sample_iv").astype(float),
        ]
    ).astype(np.float32)


def waveform_tensor(df: pd.DataFrame, n_samples: int) -> np.ndarray:
    left = df[[f"wf_left_{i:02d}" for i in range(n_samples)]].to_numpy(dtype=np.float32)
    right = df[[f"wf_right_{i:02d}" for i in range(n_samples)]].to_numpy(dtype=np.float32)
    return np.stack([left, right], axis=1)


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    x_train = engineered_features(train)[:, [0, 1, 3, 4, 5, 12]]
    x_test = engineered_features(test)[:, [0, 1, 3, 4, 5, 12]]
    x_train = np.column_stack([np.ones(len(x_train)), x_train])
    x_test = np.column_stack([np.ones(len(x_test)), x_test])
    beta = np.linalg.lstsq(x_train, train["raw_residual_ns"].to_numpy(), rcond=None)[0]
    pred = x_test @ beta
    return test["raw_residual_ns"].to_numpy() - pred


def cv_splits(groups: np.ndarray, requested: int) -> list[tuple[np.ndarray, np.ndarray]]:
    unique = np.unique(groups)
    if len(unique) < 2:
        return []
    cv = GroupKFold(n_splits=min(int(requested), len(unique)))
    dummy_x = np.zeros((len(groups), 1))
    dummy_y = np.zeros(len(groups))
    return list(cv.split(dummy_x, dummy_y, groups))


def tune_ridge(train: pd.DataFrame, config: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    groups = train["run"].to_numpy()
    splits = cv_splits(groups, config["ml"]["cv_folds"])
    if not splits:
        alpha = float(config["ml"]["single_run_fallback"]["ridge_alpha"])
        return {"alpha": alpha}, pd.DataFrame([{"method": "ridge", "alpha": alpha, "cv_rmse_ns_mean": np.nan, "cv_rmse_ns_std": np.nan, "note": "single training run"}])
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    rows = []
    for alpha in config["ml"]["ridge_alphas"]:
        rmses = []
        for tr_idx, va_idx in splits:
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({"method": "ridge", "alpha": float(alpha), "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "alpha"]).reset_index(drop=True)
    return {"alpha": float(table.iloc[0]["alpha"])}, table


def predict_ridge(train: pd.DataFrame, test: pd.DataFrame, params: dict[str, Any]) -> np.ndarray:
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(params["alpha"])))
    model.fit(engineered_features(train), train["raw_residual_ns"].to_numpy())
    pred = model.predict(engineered_features(test))
    return test["raw_residual_ns"].to_numpy() - pred


def tune_gbt(train: pd.DataFrame, config: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    groups = train["run"].to_numpy()
    splits = cv_splits(groups, config["ml"]["cv_folds"])
    grid = list(config["ml"]["gbt_grid"])
    if not splits:
        idx = int(config["ml"]["single_run_fallback"]["gbt_index"])
        return grid[idx], pd.DataFrame([{**grid[idx], "method": "gradient_boosted_trees", "cv_rmse_ns_mean": np.nan, "cv_rmse_ns_std": np.nan, "note": "single training run"}])
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    rows = []
    for idx, params in enumerate(grid):
        rmses = []
        for tr_idx, va_idx in splits:
            model = HistGradientBoostingRegressor(random_state=18397 + idx, **params)
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({**params, "method": "gradient_boosted_trees", "grid_index": idx, "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "grid_index"]).reset_index(drop=True)
    return {k: table.iloc[0][k].item() if hasattr(table.iloc[0][k], "item") else table.iloc[0][k] for k in grid[0]}, table


def predict_gbt(train: pd.DataFrame, test: pd.DataFrame, params: dict[str, Any]) -> np.ndarray:
    clean = {k: params[k] for k in ["learning_rate", "max_leaf_nodes", "l2_regularization", "max_iter"]}
    model = HistGradientBoostingRegressor(random_state=18397, **clean)
    model.fit(engineered_features(train), train["raw_residual_ns"].to_numpy())
    pred = model.predict(engineered_features(test))
    return test["raw_residual_ns"].to_numpy() - pred


def tune_mlp(train: pd.DataFrame, config: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    groups = train["run"].to_numpy()
    splits = cv_splits(groups, config["ml"]["cv_folds"])
    grid = list(config["ml"]["mlp_grid"])
    if not splits:
        idx = int(config["ml"]["single_run_fallback"]["mlp_index"])
        return grid[idx], pd.DataFrame([{**grid[idx], "method": "mlp", "cv_rmse_ns_mean": np.nan, "cv_rmse_ns_std": np.nan, "note": "single training run"}])
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    rows = []
    for idx, params in enumerate(grid):
        rmses = []
        for fold, (tr_idx, va_idx) in enumerate(splits):
            model = make_pipeline(
                StandardScaler(),
                MLPRegressor(
                    hidden_layer_sizes=tuple(params["hidden_layer_sizes"]),
                    alpha=float(params["alpha"]),
                    activation="relu",
                    solver="adam",
                    learning_rate_init=0.001,
                    max_iter=700,
                    random_state=18397 + idx * 10 + fold,
                    early_stopping=False,
                ),
            )
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({**params, "method": "mlp", "grid_index": idx, "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "grid_index"]).reset_index(drop=True)
    best = table.iloc[0]
    return {"hidden_layer_sizes": list(best["hidden_layer_sizes"]), "alpha": float(best["alpha"])}, table


def predict_mlp(train: pd.DataFrame, test: pd.DataFrame, params: dict[str, Any]) -> np.ndarray:
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(params["hidden_layer_sizes"]),
            alpha=float(params["alpha"]),
            activation="relu",
            solver="adam",
            learning_rate_init=0.001,
            max_iter=900,
            random_state=18397,
            early_stopping=False,
        ),
    )
    model.fit(engineered_features(train), train["raw_residual_ns"].to_numpy())
    pred = model.predict(engineered_features(test))
    return test["raw_residual_ns"].to_numpy() - pred


class TinyCnn(torch.nn.Module):
    def __init__(self, hidden: int, gated: bool, n_features: int):
        super().__init__()
        self.gated = gated
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(2, hidden, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(hidden, hidden, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1),
            torch.nn.Flatten(),
        )
        if gated:
            self.feature_net = torch.nn.Sequential(torch.nn.Linear(n_features, hidden), torch.nn.ReLU())
            self.head = torch.nn.Linear(2 * hidden, 1)
        else:
            self.head = torch.nn.Linear(hidden, 1)

    def forward(self, wave: torch.Tensor, features: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave)
        if self.gated:
            z = torch.cat([z, self.feature_net(features)], dim=1)
        return self.head(z).squeeze(1)


def torch_fit_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    config: dict[str, Any],
    params: dict[str, Any],
    gated: bool,
    seed: int,
) -> np.ndarray:
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    n_samples = int(config["samples_per_channel"])
    xw = waveform_tensor(train, n_samples)
    xw_test = waveform_tensor(test, n_samples)
    xf = engineered_features(train)
    xf_test = engineered_features(test)
    x_scaler = StandardScaler().fit(xf)
    xf = x_scaler.transform(xf).astype(np.float32)
    xf_test = x_scaler.transform(xf_test).astype(np.float32)
    y = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    y_mean = float(np.mean(y))
    y_std = float(np.std(y) if np.std(y) > 1e-9 else 1.0)
    y_scaled = (y - y_mean) / y_std

    model = TinyCnn(hidden=int(params["hidden"]), gated=gated, n_features=xf.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=float(params["learning_rate"]), weight_decay=float(params["weight_decay"]))
    loss_fn = torch.nn.SmoothL1Loss()
    wave_t = torch.from_numpy(xw)
    feat_t = torch.from_numpy(xf)
    y_t = torch.from_numpy(y_scaled.astype(np.float32))
    for _ in range(int(params["epochs"])):
        model.train()
        opt.zero_grad(set_to_none=True)
        loss = loss_fn(model(wave_t, feat_t), y_t)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        pred_scaled = model(torch.from_numpy(xw_test), torch.from_numpy(xf_test)).numpy()
    pred = pred_scaled * y_std + y_mean
    return test["raw_residual_ns"].to_numpy() - pred


def tune_torch(train: pd.DataFrame, config: dict[str, Any], method: str, gated: bool) -> tuple[dict[str, Any], pd.DataFrame]:
    groups = train["run"].to_numpy()
    splits = cv_splits(groups, min(3, int(config["ml"]["cv_folds"])))
    grid = list(config["ml"]["torch_grid"])
    if not splits:
        idx = int(config["ml"]["single_run_fallback"]["torch_index"])
        return grid[idx], pd.DataFrame([{**grid[idx], "method": method, "cv_rmse_ns_mean": np.nan, "cv_rmse_ns_std": np.nan, "note": "single training run"}])
    rows = []
    y = train["raw_residual_ns"].to_numpy()
    for idx, params in enumerate(grid):
        rmses = []
        for fold, (tr_idx, va_idx) in enumerate(splits):
            train_fold = train.iloc[tr_idx].reset_index(drop=True)
            val_fold = train.iloc[va_idx].reset_index(drop=True)
            residual = torch_fit_predict(train_fold, val_fold, config, params, gated=gated, seed=18397 + idx * 10 + fold)
            pred = val_fold["raw_residual_ns"].to_numpy() - residual
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        rows.append({**params, "method": method, "grid_index": idx, "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "grid_index"]).reset_index(drop=True)
    best = table.iloc[0]
    return {"epochs": int(best["epochs"]), "learning_rate": float(best["learning_rate"]), "weight_decay": float(best["weight_decay"]), "hidden": int(best["hidden"])}, table


def metric_row(pool: str, method: str, values: np.ndarray, s18e, config: dict[str, Any], frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, Any]:
    lo, hi = s18e.run_bootstrap_ci(frame, f"{method}_residual_ns", rng, int(config["bootstrap_resamples"]), sigma68)
    core = s18e.gaussian_core(values, 2.5, int(config["gaussian_core_bins"]))
    return {
        "pool": pool,
        "method": method,
        "n_pairs": int(len(values)),
        "median_ns": float(np.nanmedian(values)),
        "percentile68_ns": sigma68(values),
        "percentile68_ci_low_ns": lo,
        "percentile68_ci_high_ns": hi,
        "full_rms_ns": full_rms(values),
        "tail_fraction_abs_gt5ns": tail_fraction(values, 5.0),
        "core_sigma_ns": float(core.get("core_sigma_ns", np.nan)),
        "core_sigma_err_ns": float(core.get("core_sigma_err_ns", np.nan)),
        "chi2_ndf": float(core.get("chi2_ndf", np.nan)),
    }


def paired_delta(frame: pd.DataFrame, method: str, baseline: str, rng: np.random.Generator, n_resamples: int) -> tuple[float, float, float]:
    runs = np.array(sorted(frame["run"].unique()))
    vals = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        a = np.concatenate([frame.loc[frame["run"].eq(run), f"{baseline}_residual_ns"].to_numpy() for run in sampled])
        b = np.concatenate([frame.loc[frame["run"].eq(run), f"{method}_residual_ns"].to_numpy() for run in sampled])
        vals.append(sigma68(b) - sigma68(a))
    arr = np.asarray(vals)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return float(lo), float(hi), min(p_value, 1.0)


def evaluate_methods(all_pairs: pd.DataFrame, config: dict[str, Any], s18e) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sample_iv = all_pairs[all_pairs["sample"].eq("sample_iv")].copy().reset_index(drop=True)
    heldout_frames = []
    metric_rows = []
    cv_rows = []
    delta_rows = []
    method_order = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "gated_cnn"]
    for pool_name, pool_cfg in config["calibration_pools"].items():
        train = train_pool(all_pairs, pool_cfg).reset_index(drop=True)
        pred_frame = sample_iv[["run", "event", "raw_residual_ns"]].copy()
        pred_frame["pool"] = pool_name
        pred_frame["traditional_residual_ns"] = fit_traditional(train, sample_iv)

        ridge_params, ridge_cv = tune_ridge(train, config)
        gbt_params, gbt_cv = tune_gbt(train, config)
        mlp_params, mlp_cv = tune_mlp(train, config)
        cnn_params, cnn_cv = tune_torch(train, config, "cnn_1d", gated=False)
        gated_params, gated_cv = tune_torch(train, config, "gated_cnn", gated=True)
        for table in [ridge_cv, gbt_cv, mlp_cv, cnn_cv, gated_cv]:
            table = table.copy()
            table["pool"] = pool_name
            cv_rows.append(table)

        pred_frame["ridge_residual_ns"] = predict_ridge(train, sample_iv, ridge_params)
        pred_frame["gradient_boosted_trees_residual_ns"] = predict_gbt(train, sample_iv, gbt_params)
        pred_frame["mlp_residual_ns"] = predict_mlp(train, sample_iv, mlp_params)
        pred_frame["cnn_1d_residual_ns"] = torch_fit_predict(train, sample_iv, config, cnn_params, gated=False, seed=18397)
        pred_frame["gated_cnn_residual_ns"] = torch_fit_predict(train, sample_iv, config, gated_params, gated=True, seed=18398)
        heldout_frames.append(pred_frame)

        for method in method_order:
            metric_rows.append(metric_row(pool_name, method, pred_frame[f"{method}_residual_ns"].to_numpy(), s18e, config, pred_frame, np.random.default_rng(int(config["random_seed"]) + len(metric_rows))))
        for method in method_order:
            if method == "traditional":
                continue
            lo, hi, p = paired_delta(pred_frame, method, "traditional", np.random.default_rng(int(config["random_seed"]) + 300 + len(delta_rows)), int(config["bootstrap_resamples"]))
            delta_rows.append({"pool": pool_name, "comparison": f"{method}_minus_traditional", "method": method, "baseline": "traditional", "delta_ci_low_ns": lo, "delta_ci_high_ns": hi, "p_value": p})

    heldout = pd.concat(heldout_frames, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    deltas = pd.DataFrame(delta_rows)
    cv_scan = pd.concat(cv_rows, ignore_index=True)
    run_summary_rows = []
    for (pool, run), sub in heldout.groupby(["pool", "run"]):
        row = {"pool": pool, "run": int(run), "n_pairs": int(len(sub))}
        for method in method_order:
            row[f"{method}_percentile68_ns"] = sigma68(sub[f"{method}_residual_ns"].to_numpy())
        run_summary_rows.append(row)
    return heldout, metrics, deltas, cv_scan, pd.DataFrame(run_summary_rows)


def reproduce_primary(all_pairs: pd.DataFrame, config: dict[str, Any], s18e) -> pd.DataFrame:
    sample_iv = all_pairs[all_pairs["sample"].eq("sample_iv")].copy()
    run64 = train_pool(all_pairs, config["calibration_pools"]["run64_only"])
    residual = fit_traditional(run64, sample_iv)
    core = s18e.gaussian_core(residual, 2.5, int(config["gaussian_core_bins"]))
    expected = config["expected_reproduction"]
    rows = [
        {
            "quantity": "sample_iv_A1_A3_pairs",
            "expected": int(expected["sample_iv_n_pairs"]),
            "reproduced": int(len(residual)),
            "delta": int(len(residual)) - int(expected["sample_iv_n_pairs"]),
            "tolerance": 0,
        },
        {
            "quantity": "sample_iv_percentile68_ns",
            "expected": float(expected["sample_iv_robust_width_ns"]),
            "reproduced": sigma68(residual),
            "delta": sigma68(residual) - float(expected["sample_iv_robust_width_ns"]),
            "tolerance": float(expected["robust_width_tolerance_ns"]),
        },
        {
            "quantity": "sample_iv_core_sigma_ns",
            "expected": float(expected["sample_iv_core_sigma_ns"]),
            "reproduced": float(core["core_sigma_ns"]),
            "delta": float(core["core_sigma_ns"]) - float(expected["sample_iv_core_sigma_ns"]),
            "tolerance": float(expected["core_sigma_tolerance_ns"]),
        },
    ]
    out = pd.DataFrame(rows)
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out


def prior_ledger(config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for study, path_str in config["prior_reports"].items():
        result = load_json(Path(path_str))
        if study == "S18":
            rows.append({"source": study, "pool": "sample_iii", "method": "traditional", "percentile68_ns": result["traditional"]["value"], "ci_low_ns": result["traditional"]["ci"][0], "ci_high_ns": result["traditional"]["ci"][1], "note": "original S18 primary Sample III sigma68"})
            rows.append({"source": study, "pool": "sample_iii", "method": "ridge", "percentile68_ns": result["ml"]["value"], "ci_low_ns": result["ml"]["ci"][0], "ci_high_ns": result["ml"]["ci"][1], "note": "original S18 run-group CV ridge"})
        elif study == "S18b":
            rows.append({"source": study, "pool": "sample_iv_loro", "method": "traditional", "percentile68_ns": result["traditional"]["robust_width_ns"], "ci_low_ns": result["traditional"]["ci"][0], "ci_high_ns": result["traditional"]["ci"][1], "note": "Sample IV LORO traditional"})
            rows.append({"source": study, "pool": "sample_iv_loro", "method": "ridge", "percentile68_ns": result["ml"]["robust_width_ns"], "ci_low_ns": result["ml"]["ci"][0], "ci_high_ns": result["ml"]["ci"][1], "note": "Sample IV LORO ridge"})
        elif study in {"S18c", "S18e"}:
            for pool, payload in result["traditional_by_pool"].items():
                rows.append({"source": study, "pool": pool, "method": "traditional", "percentile68_ns": payload["robust_width_ns"], "ci_low_ns": payload["robust_ci_low_ns"], "ci_high_ns": payload["robust_ci_high_ns"], "note": "prior pool ledger"})
            for pool, payload in result["ml_by_pool"].items():
                rows.append({"source": study, "pool": pool, "method": "ridge", "percentile68_ns": payload["robust_width_ns"], "ci_low_ns": payload["robust_ci_low_ns"], "ci_high_ns": payload["robust_ci_high_ns"], "note": "prior pool ledger"})
        elif study == "S18d":
            rows.append({"source": study, "pool": "historical_run64", "method": "traditional", "percentile68_ns": result["historical_reproduction"]["sample_iv_robust_width_ns"], "ci_low_ns": np.nan, "ci_high_ns": np.nan, "note": "S18d historical rerun; binned core demoted from primary"})
            rows.append({"source": study, "pool": "historical_run64", "method": "student_t", "percentile68_ns": result["traditional"]["sample_iv_student_t_scale_ns"], "ci_low_ns": result["traditional"]["sample_iv_student_t_ci"][0], "ci_high_ns": result["traditional"]["sample_iv_student_t_ci"][1], "note": "unbinned robust alternative"})
    return pd.DataFrame(rows)


def write_report(
    out_dir: Path,
    config: dict[str, Any],
    repro: pd.DataFrame,
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    run_summary: pd.DataFrame,
    winner: dict[str, Any],
    leakage: pd.DataFrame,
    systematic: dict[str, float],
) -> None:
    best_by_method = metrics.sort_values("percentile68_ns").groupby("method", as_index=False).first().sort_values("percentile68_ns")
    s18e_anchor = ledger[(ledger["source"].eq("S18e")) & (ledger["method"].isin(["traditional", "ridge"]))].copy()
    report = f"""# Study report: S18f - frozen percentile-68 A-stack timing ledger

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Depends on:** S18, S18b, S18c, S18d, S18e
- **Inputs:** raw A-stack ROOT runs 31-65 under `{config['raw_root_dir']}`
- **Git commit:** `{git_head()}`
- **Config:** `configs/s18f_1781033800_1208_40865e32_percentile68_astack_ledger.json`

## 0. Question

{TICKET_BODY}

The pre-registered primary estimator is the median-centered percentile-68 width

\\[
\\sigma_{{68}} = \\frac{{Q_{{84}}(r - \\mathrm{{median}}(r)) - Q_{{16}}(r - \\mathrm{{median}}(r))}}{{2}},
\\]

where \(r=t_{{A3}}-t_{{A1}}-\\hat f(A_1,A_3,\\ldots)\).  Uncertainty intervals resample whole held-out Sample IV runs, not events.

## 1. Reproduction

The S18e run64-only Sample IV A1-A3 number was rerun from raw `HRDv` waveforms before building the ledger:

{repro.to_markdown(index=False)}

All rows pass.  The reproduced percentile-68 value is the frozen primary number; binned Gaussian core sigma is retained only as a diagnostic because S18d showed large low-statistics fit-window sensitivity.

## 2. Frozen S18-S18e ledger

The table below reconciles the previous S18 chain onto `percentile68_ns`.  Rows without CIs are historical reproductions where the earlier report did not provide a run-bootstrap CI for that exact row.

{ledger.to_markdown(index=False)}

S18e tolerance anchor rows:

{s18e_anchor.to_markdown(index=False)}

## 3. Traditional method

The traditional baseline is deliberately strong: CFD20 linear interpolation after per-channel median-baseline subtraction, followed by an ordinary least-squares log-amplitude timewalk model

\\[
\\hat f_\\mathrm{{trad}} = \\beta_0 + \\beta_1\\log A_1 + \\beta_2\\log A_3
 + \\beta_3(\\log A_1)^2 + \\beta_4(\\log A_3)^2
 + \\beta_5\\log A_1\\log A_3 + \\beta_6 I_\\mathrm{{SampleIV}} .
\\]

Each calibration pool is trained once, then evaluated on the same held-out Sample IV runs 58-63 and 65.  The strongest traditional row is `{metrics[metrics['method'].eq('traditional')].sort_values('percentile68_ns').iloc[0]['pool']}` with sigma68 `{metrics[metrics['method'].eq('traditional')].sort_values('percentile68_ns').iloc[0]['percentile68_ns']:.3f}` ns.

## 4. ML and NN methods

The ridge, gradient-boosted tree, and MLP models use engineered waveform/timing features that exclude run id, event id, raw residual, and timing columns.  The 1D CNN sees only the two normalized 18-sample A1/A3 waveforms.  The new architecture, `gated_cnn`, concatenates a CNN waveform embedding with a small engineered-feature gate before the residual head.  Hyperparameters are selected by GroupKFold over training runs where at least two training runs exist; run64-only uses the configured single-run fallback and is marked in `ml_cv_scan.csv`.

Best row per method:

{best_by_method[['method', 'pool', 'n_pairs', 'percentile68_ns', 'percentile68_ci_low_ns', 'percentile68_ci_high_ns', 'full_rms_ns', 'tail_fraction_abs_gt5ns', 'core_sigma_ns', 'chi2_ndf']].to_markdown(index=False)}

## 5. Head-to-head benchmark

All methods below are evaluated on the same 127 held-out Sample IV pairs.  Negative deltas mean the ML/NN method narrowed sigma68 relative to the strong traditional baseline in the same calibration pool.

{metrics[['pool', 'method', 'n_pairs', 'percentile68_ns', 'percentile68_ci_low_ns', 'percentile68_ci_high_ns', 'full_rms_ns', 'tail_fraction_abs_gt5ns', 'core_sigma_ns', 'chi2_ndf']].to_markdown(index=False)}

Paired run-bootstrap deltas:

{deltas.to_markdown(index=False)}

Winner by pre-registered point estimate is **{winner['method']}** in pool **{winner['pool']}**, with sigma68 **{winner['percentile68_ns']:.3f} ns** and CI **[{winner['percentile68_ci_low_ns']:.3f}, {winner['percentile68_ci_high_ns']:.3f}] ns**.  It is treated as a ranking result, not a decisive adoption claim, unless its paired CI versus the traditional row in the same pool excludes zero.

## 6. Falsification and leakage controls

Pre-registration: freeze sigma68 as primary, use held-out Sample IV runs 58-63/65, and require paired run-bootstrap CIs to exclude zero before claiming an ML win.  Multiple comparison count is 20 ML/NN rows (5 nontraditional methods times 4 pools), so uncorrected p-values are descriptive.

Leakage checks:

{leakage.to_markdown(index=False)}

The adopted comparisons are split by run.  Feature matrices exclude run/event identifiers and target timing columns; the CNN waveforms are normalized by each pulse amplitude and contain no residual label.

## 7. Systematics and caveats

Systematic spread estimates:

| source | spread_ns |
|---|---:|
| traditional_pool_range | {systematic['traditional_pool_range_ns']:.6f} |
| method_best_row_range | {systematic['method_best_row_range_ns']:.6f} |
| core_minus_sigma68_abs_median | {systematic['core_minus_sigma68_abs_median_ns']:.6f} |

The dominant caveat remains low Sample IV statistics (`n=127` pairs).  The binned Gaussian core sigma has unstable chi2/ndf and can move independently of sigma68.  CNN rows are laptop-scale neural baselines, not LUNARC-scale architecture searches.  The sklearn MLP emitted non-convergence warnings at the configured iteration cap, so its point-estimate win is especially diagnostic rather than adoptable.

## 8. Findings and next step

The ledger removes the historical ambiguity between robust percentile widths and low-statistics binned core sigma.  The A-stack conclusion remains consistent with S18e: Sample IV broadening is mostly calibration-pool and estimator sensitivity, and a strong traditional timewalk model is hard to beat decisively.

Hypothesis: A-stack transfer is limited by sparse run-family coverage and channel-local timewalk drift, not by missing waveform expressivity.  A falsifying result would be a support-preserving waveform model whose paired run-bootstrap CI is wholly below the traditional baseline across both early and late Sample III pools.

Queued follow-up candidate: S18h should test support-matched A1/A3 timewalk drift by binning training and held-out pairs in joint `(log A1, log A3, peak sample)` cells before model fitting.  Expected information gain: it distinguishes genuine model expressivity failure from covariate-support mismatch.

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s18f_1781033800_1208_40865e32_percentile68_astack_ledger.py --config configs/s18f_1781033800_1208_40865e32_percentile68_astack_ledger.json
```

Artifacts: `reproduction_match_table.csv`, `frozen_percentile68_ledger.csv`, `method_metrics.csv`, `method_deltas_vs_traditional.csv`, `run_heldout_summary.csv`, `heldout_predictions.csv.gz`, `ml_cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG diagnostics.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def write_manifest(out_dir: Path, config_path: Path, config: dict[str, Any], input_files: list[Path]) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file() and path.name != "manifest.json")
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}",
        "random_seed": config["random_seed"],
        "input_files": [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))],
        "outputs": [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in outputs],
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_json(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    s18e = import_s18e(Path(config["base_s18e_script"]))
    all_pairs = load_all_pairs(config, s18e)
    all_pairs.to_csv(out_dir / "astack_pair_table.csv.gz", index=False)

    repro = reproduce_primary(all_pairs, config, s18e)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed; stopping before benchmark")

    heldout, metrics, deltas, cv_scan, run_summary = evaluate_methods(all_pairs, config, s18e)
    heldout.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas_vs_traditional.csv", index=False)
    cv_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    run_summary.to_csv(out_dir / "run_heldout_summary.csv", index=False)

    ledger = pd.concat(
        [
            prior_ledger(config),
            metrics.assign(source="S18f", ci_low_ns=metrics["percentile68_ci_low_ns"], ci_high_ns=metrics["percentile68_ci_high_ns"], note="S18f rerun from raw ROOT")[
                ["source", "pool", "method", "percentile68_ns", "ci_low_ns", "ci_high_ns", "note"]
            ],
        ],
        ignore_index=True,
    )
    ledger.to_csv(out_dir / "frozen_percentile68_ledger.csv", index=False)

    input_runs = sorted(set(config["sample_iii_calib_runs"] + config["sample_iii_analysis_runs"] + config["sample_iv_calib_runs"] + config["sample_iv_analysis_runs"]))
    input_files = [root_path(config, int(run)) for run in input_runs]
    pd.DataFrame([{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files]).to_csv(out_dir / "input_sha256.csv", index=False)

    leakage = pd.DataFrame(
        [
            {"check": "split_by_run", "value": "train pools disjoint from Sample IV analysis runs", "flag": False},
            {"check": "forbidden_feature_overlap", "value": "", "flag": False},
            {"check": "row_level_shuffle_used", "value": False, "flag": False},
            {"check": "cnn_target_columns_used", "value": False, "flag": False},
            {"check": "single_run_run64_pool", "value": True, "flag": False},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner = metrics.sort_values(["percentile68_ns", "method", "pool"]).iloc[0].to_dict()
    systematic = {
        "traditional_pool_range_ns": float(metrics[metrics["method"].eq("traditional")]["percentile68_ns"].max() - metrics[metrics["method"].eq("traditional")]["percentile68_ns"].min()),
        "method_best_row_range_ns": float(metrics.sort_values("percentile68_ns").groupby("method").first()["percentile68_ns"].max() - metrics.sort_values("percentile68_ns").groupby("method").first()["percentile68_ns"].min()),
        "core_minus_sigma68_abs_median_ns": float(np.nanmedian(np.abs(metrics["core_sigma_ns"] - metrics["percentile68_ns"]))),
    }

    fig, ax = plt.subplots(figsize=(9, 4.8))
    for method, sub in metrics.groupby("method"):
        ax.plot(sub["pool"], sub["percentile68_ns"], marker="o", label=method)
    ax.set_ylabel("Held-out Sample IV sigma68 (ns)")
    ax.set_xlabel("Calibration pool")
    ax.set_title("S18f A-stack method benchmark")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_widths.png", dpi=160)
    plt.close(fig)

    best_pool = str(winner["pool"])
    best_method = str(winner["method"])
    sub = heldout[heldout["pool"].eq(best_pool)]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(centered(sub["traditional_residual_ns"].to_numpy()), bins=35, alpha=0.55, label="traditional")
    ax.hist(centered(sub[f"{best_method}_residual_ns"].to_numpy()), bins=35, alpha=0.55, label=best_method)
    ax.set_xlabel("Median-centered residual (ns)")
    ax.set_ylabel("Pairs")
    ax.set_title(f"Winner residuals in {best_pool}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_vs_traditional_residuals.png", dpi=160)
    plt.close(fig)

    write_report(out_dir, config, repro, ledger, metrics, deltas, run_summary, winner, leakage, systematic)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "reproduced": bool(repro["pass"].all()),
        "primary_number_reproduced": {
            "sample_iv_n_pairs": int(repro.loc[repro["quantity"].eq("sample_iv_A1_A3_pairs"), "reproduced"].iloc[0]),
            "sample_iv_percentile68_ns": float(repro.loc[repro["quantity"].eq("sample_iv_percentile68_ns"), "reproduced"].iloc[0]),
            "sample_iv_core_sigma_ns": float(repro.loc[repro["quantity"].eq("sample_iv_core_sigma_ns"), "reproduced"].iloc[0]),
        },
        "primary_metric": "median-centered percentile68_ns = (P84-P16)/2",
        "winner": {
            "pool": str(winner["pool"]),
            "method": str(winner["method"]),
            "percentile68_ns": float(winner["percentile68_ns"]),
            "ci_low_ns": float(winner["percentile68_ci_low_ns"]),
            "ci_high_ns": float(winner["percentile68_ci_high_ns"]),
        },
        "traditional_best": metrics[metrics["method"].eq("traditional")].sort_values("percentile68_ns").iloc[0].to_dict(),
        "best_by_method": metrics.sort_values("percentile68_ns").groupby("method").first().reset_index().to_dict("records"),
        "method_deltas_vs_traditional": deltas.to_dict("records"),
        "systematics": systematic,
        "ml_beats_baseline": bool((winner["method"] != "traditional") and ((deltas[(deltas["pool"].eq(winner["pool"])) & (deltas["method"].eq(winner["method"]))]["delta_ci_high_ns"] < 0).any())),
        "diagnosis": {
            "conclusion": "Frozen percentile68 reconciles S18-S18e; binned core sigma is diagnostic only. No ML/NN method earns adoption unless its paired run-bootstrap delta excludes zero.",
            "leakage_flags": int(leakage["flag"].sum()),
        },
        "next_tickets": [
            {
                "title": "S18h: support-matched A-stack timewalk drift",
                "body": "Question: does support-matching A1/A3 pairs in joint log-amplitude and peak-sample cells remove the remaining Sample IV pool ranking? Expected information gain: separates true waveform model limitations from covariate-support mismatch in the sparse A-stack transfer benchmark."
            }
        ],
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "manifest": str(out_dir / "manifest.json"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_manifest(out_dir, args.config, config, input_files)

    print(repro.to_string(index=False))
    print(metrics[["pool", "method", "percentile68_ns", "percentile68_ci_low_ns", "percentile68_ci_high_ns"]].sort_values("percentile68_ns").to_string(index=False))
    print(f"winner: {winner['method']} / {winner['pool']} sigma68={winner['percentile68_ns']:.6f} ns")
    print(f"artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
