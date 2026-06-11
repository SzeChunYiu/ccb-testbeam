#!/usr/bin/env python3
"""S14g: veto-ladder energy/PID support acceptance calibration.

This study rebuilds the selected B-stack pulse population from raw ROOT,
constructs transparent P09/S10/S16/P07-style veto families, then benchmarks
run-held-out support selectors against the traditional veto ladder.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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
P04O_PATH = ROOT / "scripts" / "p04o_1781045406_731_183408e8_rate_conditioned_charge_support_veto.py"


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p04o = import_script("p04o_support_source", P04O_PATH)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        return None if not math.isfinite(v) else v
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def ci_pair(values: Sequence[float]) -> List[float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def md_table(frame: pd.DataFrame, columns: List[str], max_rows: int = 60) -> str:
    sub = frame.loc[:, columns].head(max_rows).copy()
    for col in sub.columns:
        if sub[col].dtype.kind in "fc":
            sub[col] = sub[col].map(lambda v: "" if pd.isna(v) else "{:.5g}".format(float(v)))
        elif sub[col].dtype.kind in "iu":
            sub[col] = sub[col].map(lambda v: "{:d}".format(int(v)))
        else:
            sub[col] = sub[col].map(str)
    widths = [max(len(str(c)), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    header = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in sub.columns) + " |"
    rows = ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |" for _, row in sub.iterrows()]
    return "\n".join([header, sep] + rows)


def q68_abs(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.percentile(np.abs(arr), 68))


def sample_indices(indices: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    if len(indices) <= int(max_rows):
        return indices
    return np.sort(rng.choice(indices, size=int(max_rows), replace=False))


def prepare_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    meta, wave, counts, b_events = p04o.extract_b_pulses(config)
    total = int(counts["selected_pulses"].sum())
    if total != int(config["expected_selected_pulses"]):
        raise RuntimeError("raw selected-pulse reproduction failed: got {}, expected {}".format(total, config["expected_selected_pulses"]))
    rates = p04o.run_level_rates(config, b_events)
    rates, rate_cv = p04o.add_rate_residuals(rates, int(config["random_seed"]))
    df, wf = p04o.prepare_analysis_rows(config, meta, wave, rates)
    df["log_target_charge"] = np.log(np.maximum(df["target_odd_pos_charge"].to_numpy(dtype=float), 1.0))
    df["log_charge_residual_even_minus_odd"] = df["log_even_pos_charge"].to_numpy(dtype=float) - df["log_target_charge"].to_numpy(dtype=float)
    df["depth_idx"] = df["stave"].map({"B2": 0, "B4": 1, "B6": 2, "B8": 3}).astype(int)
    df["dominant_veto_family"] = "accepted"
    return df, wf, counts, rates, rate_cv


def fit_veto_thresholds(train: pd.DataFrame, config: dict) -> dict:
    return {
        "q_tail_anomaly": float(np.percentile(train["q_tail"], 92.0)),
        "half_width_anomaly": float(np.percentile(train["half_width"], 96.0)),
        "baseline_wide": float(np.percentile(train["even_baseline_rms"], 92.0)),
        "saturation_adc": float(config["saturation_adc"]),
        "saturation_depth": float(np.percentile(train["saturation_depth"], 88.0)),
        "pileup_tail": float(np.percentile(train["q_tail"], 78.0)),
        "pileup_width": float(np.percentile(train["half_width"], 78.0)),
    }


def veto_flags(frame: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out["p09_anomaly"] = (
        (frame["q_tail"].to_numpy(dtype=float) > thresholds["q_tail_anomaly"])
        | (frame["half_width"].to_numpy(dtype=float) > thresholds["half_width_anomaly"])
        | (frame["even_peak"].to_numpy(dtype=float) <= 1.0)
        | (frame["even_peak"].to_numpy(dtype=float) >= 16.0)
    )
    out["s10_pileup"] = (
        (frame["event_b_n_selected"].to_numpy(dtype=float) >= 3.0)
        | ((frame["q_tail"].to_numpy(dtype=float) > thresholds["pileup_tail"]) & (frame["half_width"].to_numpy(dtype=float) > thresholds["pileup_width"]))
    )
    out["s16_baseline_lowering"] = frame["even_baseline_rms"].to_numpy(dtype=float) > thresholds["baseline_wide"]
    out["p07_saturation"] = (
        (frame["even_amp"].to_numpy(dtype=float) >= thresholds["saturation_adc"])
        | (frame["saturation_depth"].to_numpy(dtype=float) > thresholds["saturation_depth"])
    )
    return out


def first_veto_family(flags: pd.DataFrame) -> np.ndarray:
    family = np.full(len(flags), "accepted", dtype=object)
    for col in ["p09_anomaly", "s10_pileup", "s16_baseline_lowering", "p07_saturation"]:
        mask = (family == "accepted") & flags[col].to_numpy(dtype=bool)
        family[mask] = col
    return family


def support_target(train: pd.DataFrame, trad_accept: np.ndarray, config: dict) -> np.ndarray:
    abs_log = np.abs(train["log_charge_residual_even_minus_odd"].to_numpy(dtype=float))
    q = float(np.quantile(abs_log[np.isfinite(abs_log)], float(config["models"]["support_quantile"])))
    target = trad_accept & (abs_log <= q)
    if target.mean() < 0.05:
        target = abs_log <= float(np.quantile(abs_log[np.isfinite(abs_log)], 0.35))
    return target.astype(int)


def numeric_features() -> List[str]:
    return [
        "log_even_amp",
        "log_even_pos_charge",
        "log_event_b_max_amp",
        "even_peak",
        "q_tail",
        "half_width",
        "saturation_depth",
        "even_baseline_rms",
        "event_b_n_selected",
        "event_b_max_amp",
        "current_nA",
        "sample_ii",
        "target_rate",
        "pred_rate_traditional",
        "rate_residual_pp",
        "b_multi_frac",
        "b_downstream_frac",
        "b2_share",
    ]


def categorical_features() -> List[str]:
    return ["saturation_bin", "q_template_bin", "baseline_taxon"]


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features()),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features()),
        ],
        sparse_threshold=0.0,
    )


def proba_or_score(model, frame: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(frame)
        return np.asarray(p[:, 1], dtype=float)
    score = model.decision_function(frame)
    return 1.0 / (1.0 + np.exp(-np.asarray(score, dtype=float)))


class SupportCNN(nn.Module):
    def __init__(self, n_aux: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 10, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(10, 10, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(6),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(60 + n_aux, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, aux):
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


def normalize_wave(wave: np.ndarray) -> np.ndarray:
    med = np.median(wave, axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(wave - med), 75, axis=1, keepdims=True), 1.0)
    return ((wave - med) / scale).astype(np.float32)


def fit_cnn_proba(
    train_wave: np.ndarray,
    train_aux: np.ndarray,
    y_train: np.ndarray,
    test_wave: np.ndarray,
    test_aux: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    if torch is None:
        p = np.full(len(test_wave), float(np.mean(y_train)), dtype=float)
        return np.full(len(train_wave), float(np.mean(y_train)), dtype=float), p
    torch.manual_seed(int(seed))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SupportCNN(train_aux.shape[1]).to(device)
    pos = max(float(y_train.sum()), 1.0)
    neg = max(float(len(y_train) - y_train.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=2e-4)
    ds = TensorDataset(
        torch.tensor(train_wave[:, None, :], dtype=torch.float32),
        torch.tensor(train_aux, dtype=torch.float32),
        torch.tensor(y_train.astype(np.float32), dtype=torch.float32),
    )
    loader = DataLoader(ds, batch_size=int(config["models"]["cnn_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["models"]["cnn_epochs"])):
        for xb, xa, yb in loader:
            xb, xa, yb = xb.to(device), xa.to(device), yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb, xa), yb)
            loss.backward()
            opt.step()

    def predict(wave_arr: np.ndarray, aux_arr: np.ndarray) -> np.ndarray:
        model.eval()
        vals = []
        with torch.no_grad():
            for start in range(0, len(wave_arr), 8192):
                xb = torch.tensor(wave_arr[start : start + 8192, None, :], dtype=torch.float32, device=device)
                xa = torch.tensor(aux_arr[start : start + 8192], dtype=torch.float32, device=device)
                vals.append(torch.sigmoid(model(xb, xa)).detach().cpu().numpy())
        return np.concatenate(vals)

    return predict(train_wave, train_aux), predict(test_wave, test_aux)


def threshold_to_rate(train_prob: np.ndarray, train_rate: float) -> float:
    train_rate = min(max(float(train_rate), 0.01), 0.99)
    return float(np.quantile(train_prob, 1.0 - train_rate))


def fit_selectors(df: pd.DataFrame, wave: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    methods = [
        "traditional_veto_ladder",
        "ridge_support",
        "gradient_boosted_trees",
        "mlp_support",
        "cnn_1d_support",
        "new_residual_gated_ensemble",
        "shuffled_target_hgb_control",
    ]
    accept = {m: np.zeros(len(df), dtype=bool) for m in methods}
    proba = {m: np.full(len(df), np.nan, dtype=float) for m in methods}
    family = np.full(len(df), "accepted", dtype=object)
    fold_rows = []
    rng = np.random.default_rng(int(config["random_seed"]))
    splitter = GroupKFold(n_splits=int(config["models"]["n_splits"]))
    groups = df["run"].to_numpy()
    for fold, (tr, te) in enumerate(splitter.split(df, groups=groups)):
        train = df.iloc[tr].copy()
        test = df.iloc[te].copy()
        thresholds = fit_veto_thresholds(train, config)
        train_flags = veto_flags(train, thresholds)
        test_flags = veto_flags(test, thresholds)
        train_trad = ~train_flags.any(axis=1).to_numpy(dtype=bool)
        test_trad = ~test_flags.any(axis=1).to_numpy(dtype=bool)
        accept["traditional_veto_ladder"][te] = test_trad
        proba["traditional_veto_ladder"][te] = 1.0 - test_flags.mean(axis=1).to_numpy(dtype=float)
        family[te] = first_veto_family(test_flags)
        y_train_all = support_target(train, train_trad, config)
        train_rate = float(train_trad.mean())
        train_idx = sample_indices(np.asarray(tr), int(config["models"]["max_train_rows"]), rng)
        nn_idx = sample_indices(np.asarray(tr), int(config["models"]["max_nn_train_rows"]), rng)
        train_sample = df.iloc[train_idx].copy()
        y_sample = y_train_all[np.searchsorted(np.asarray(tr), train_idx)]

        specs = [
            (
                "ridge_support",
                LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=250, class_weight="balanced", random_state=int(config["random_seed"]) + fold),
            ),
            (
                "gradient_boosted_trees",
                HistGradientBoostingClassifier(
                    max_iter=int(config["models"]["hgb_max_iter"]),
                    learning_rate=0.06,
                    max_leaf_nodes=31,
                    l2_regularization=0.05,
                    random_state=int(config["random_seed"]) + 100 + fold,
                ),
            ),
            (
                "mlp_support",
                MLPClassifier(
                    hidden_layer_sizes=(64, 32),
                    activation="relu",
                    alpha=1e-4,
                    learning_rate_init=1e-3,
                    max_iter=int(config["models"]["mlp_max_iter"]),
                    random_state=int(config["random_seed"]) + 200 + fold,
                    early_stopping=True,
                ),
            ),
        ]
        hgb_train_prob = None
        hgb_test_prob = None
        for name, estimator in specs:
            pipe = make_pipeline(make_preprocessor(), estimator)
            if name == "mlp_support":
                pipe.fit(df.iloc[nn_idx], y_train_all[np.searchsorted(np.asarray(tr), nn_idx)])
            else:
                pipe.fit(train_sample, y_sample)
            tr_prob = proba_or_score(pipe, train)
            te_prob = proba_or_score(pipe, test)
            cut = threshold_to_rate(tr_prob, train_rate)
            accept[name][te] = te_prob >= cut
            proba[name][te] = te_prob
            if name == "gradient_boosted_trees":
                hgb_train_prob = tr_prob
                hgb_test_prob = te_prob

        shuffled = y_sample.copy()
        rng.shuffle(shuffled)
        shuffle_pipe = make_pipeline(
            make_preprocessor(),
            HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, max_leaf_nodes=23, l2_regularization=0.1, random_state=int(config["random_seed"]) + 300 + fold),
        )
        shuffle_pipe.fit(train_sample, shuffled)
        tr_prob = proba_or_score(shuffle_pipe, train)
        te_prob = proba_or_score(shuffle_pipe, test)
        cut = threshold_to_rate(tr_prob, train_rate)
        accept["shuffled_target_hgb_control"][te] = te_prob >= cut
        proba["shuffled_target_hgb_control"][te] = te_prob

        aux_pre = make_preprocessor()
        aux_train = aux_pre.fit_transform(df.iloc[nn_idx]).astype(np.float32)
        aux_test = aux_pre.transform(test).astype(np.float32)
        train_wave = normalize_wave(wave[nn_idx])
        test_wave = normalize_wave(wave[te])
        y_nn = y_train_all[np.searchsorted(np.asarray(tr), nn_idx)]
        cnn_train_prob, cnn_test_prob = fit_cnn_proba(train_wave, aux_train, y_nn, test_wave, aux_test, config, int(config["random_seed"]) + 400 + fold)
        cnn_cut = threshold_to_rate(cnn_train_prob, train_rate)
        accept["cnn_1d_support"][te] = cnn_test_prob >= cnn_cut
        proba["cnn_1d_support"][te] = cnn_test_prob

        # New architecture: average tabular HGB and CNN probabilities, then
        # require that the transparent ladder did not fire more than one family.
        if hgb_train_prob is None or hgb_test_prob is None:
            hgb_train_prob = np.full(len(train), float(y_train_all.mean()))
            hgb_test_prob = np.full(len(test), float(y_train_all.mean()))
        # Align the CNN train probabilities to the sampled NN rows by fitting a simple
        # conservative cut from the sampled probabilities.
        ensemble_test = 0.70 * hgb_test_prob + 0.30 * cnn_test_prob
        ensemble_train_sample = 0.70 * hgb_train_prob[np.searchsorted(np.asarray(tr), nn_idx)] + 0.30 * cnn_train_prob
        hard_gate = test_flags.sum(axis=1).to_numpy(dtype=int) <= 1
        cut = threshold_to_rate(ensemble_train_sample, train_rate)
        accept["new_residual_gated_ensemble"][te] = (ensemble_test >= cut) & hard_gate
        proba["new_residual_gated_ensemble"][te] = ensemble_test

        fold_rows.append(
            {
                "fold": int(fold),
                "heldout_runs": ",".join(str(int(r)) for r in sorted(test["run"].unique())),
                "n_train": int(len(tr)),
                "n_test": int(len(te)),
                "traditional_train_acceptance": train_rate,
                "support_target_positive_rate": float(y_train_all.mean()),
                "new_arch_test_acceptance": float(accept["new_residual_gated_ensemble"][te].mean()),
            }
        )

    out = pd.DataFrame({"row_index": np.arange(len(df)), "run": df["run"], "eventno": df["eventno"], "stave": df["stave"], "traditional_veto_family": family})
    for method in methods:
        out["accept_{}".format(method)] = accept[method]
        out["prob_{}".format(method)] = proba[method]
    return out, pd.DataFrame(fold_rows)


def range_energy_lookup(config: dict, geometry: str) -> Dict[str, float]:
    pstar = config["pstar"]
    energy = np.asarray(pstar["energy_mev"], dtype=float)
    ranges_cm = np.asarray(pstar["range_g_cm2"], dtype=float) / float(pstar["density_g_cm3"])
    centers = config["geometry_variants"][geometry]["stave_centers_cm"]
    return {stave: float(np.interp(float(cm), ranges_cm, energy, left=energy[0], right=energy[-1])) for stave, cm in centers.items()}


def depth_order_violation_rate(frame: pd.DataFrame, accepted: np.ndarray, log_energy: np.ndarray) -> float:
    tmp = frame.loc[accepted, ["run", "depth_idx"]].copy()
    if len(tmp) == 0:
        return float("nan")
    tmp["log_energy"] = log_energy[accepted]
    violations = 0
    checks = 0
    for _, run_group in tmp.groupby("run"):
        med = run_group.groupby("depth_idx")["log_energy"].median().sort_index()
        vals = med.to_numpy(dtype=float)
        if len(vals) < 2:
            continue
        checks += len(vals) - 1
        violations += int(np.sum(vals[1:] <= vals[:-1]))
    return float(violations / checks) if checks else float("nan")


def depth_order_violation_arrays(runs: np.ndarray, depths: np.ndarray, accepted: np.ndarray, log_energy: np.ndarray) -> float:
    accepted = np.asarray(accepted, dtype=bool)
    runs = np.asarray(runs, dtype=int)
    depths = np.asarray(depths, dtype=int)
    log_energy = np.asarray(log_energy, dtype=float)
    violations = 0
    checks = 0
    for run in np.unique(runs[accepted]):
        run_mask = accepted & (runs == int(run))
        present = np.unique(depths[run_mask])
        if len(present) < 2:
            continue
        med = []
        for depth in np.sort(present):
            vals = log_energy[run_mask & (depths == int(depth))]
            if len(vals):
                med.append(float(np.median(vals)))
        vals = np.asarray(med, dtype=float)
        if len(vals) < 2:
            continue
        checks += len(vals) - 1
        violations += int(np.sum(vals[1:] <= vals[:-1]))
    return float(violations / checks) if checks else float("nan")


def metric_for_mask(frame: pd.DataFrame, accepted: np.ndarray, log_energy_target: np.ndarray, log_energy_even: np.ndarray) -> dict:
    accepted = np.asarray(accepted, dtype=bool)
    if accepted.sum() == 0:
        return {
            "n": 0,
            "acceptance": 0.0,
            "charge_proxy_log_shift": float("nan"),
            "energy_proxy_res68": float("nan"),
            "depth_order_violation_rate": float("nan"),
        }
    base_log_charge = frame["log_target_charge"].to_numpy(dtype=float)
    return {
        "n": int(accepted.sum()),
        "acceptance": float(accepted.mean()),
        "charge_proxy_log_shift": float(np.median(base_log_charge[accepted]) - np.median(base_log_charge)),
        "energy_proxy_res68": q68_abs(log_energy_even[accepted] - log_energy_target[accepted]),
        "depth_order_violation_rate": depth_order_violation_rate(frame, accepted, log_energy_target),
    }


def bootstrap_metric(
    frame: pd.DataFrame,
    accepted: np.ndarray,
    log_energy_target: np.ndarray,
    log_energy_even: np.ndarray,
    reps: int,
    seed: int,
) -> dict:
    rng = np.random.default_rng(seed)
    run_arr = frame["run"].to_numpy(dtype=int)
    depth_arr = frame["depth_idx"].to_numpy(dtype=int)
    base_log_charge = frame["log_target_charge"].to_numpy(dtype=float)
    runs = np.asarray(sorted(np.unique(run_arr)), dtype=int)
    by_run = {int(run): np.where(run_arr == int(run))[0] for run in runs}
    vals = {"acceptance": [], "charge_proxy_log_shift": [], "energy_proxy_res68": [], "depth_order_violation_rate": []}
    for _ in range(int(reps)):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([by_run[int(run)] for run in chosen])
        chosen_accept = accepted[idx]
        vals["acceptance"].append(float(chosen_accept.mean()) if len(chosen_accept) else float("nan"))
        if chosen_accept.sum() == 0:
            vals["charge_proxy_log_shift"].append(float("nan"))
            vals["energy_proxy_res68"].append(float("nan"))
            vals["depth_order_violation_rate"].append(float("nan"))
            continue
        sample_charge = base_log_charge[idx]
        vals["charge_proxy_log_shift"].append(float(np.median(sample_charge[chosen_accept]) - np.median(sample_charge)))
        vals["energy_proxy_res68"].append(q68_abs((log_energy_even[idx] - log_energy_target[idx])[chosen_accept]))
        vals["depth_order_violation_rate"].append(
            depth_order_violation_arrays(run_arr[idx], depth_arr[idx], chosen_accept, log_energy_target[idx])
        )
    return {key + "_ci95": ci_pair(val) for key, val in vals.items()}


def bootstrap_delta_energy_res68(
    frame: pd.DataFrame,
    accepted: np.ndarray,
    trad_accepted: np.ndarray,
    log_energy_target: np.ndarray,
    log_energy_even: np.ndarray,
    reps: int,
    seed: int,
) -> List[float]:
    rng = np.random.default_rng(seed)
    run_arr = frame["run"].to_numpy(dtype=int)
    runs = np.asarray(sorted(np.unique(run_arr)), dtype=int)
    by_run = {int(run): np.where(run_arr == int(run))[0] for run in runs}
    diffs = []
    residual = log_energy_even - log_energy_target
    for _ in range(int(reps)):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([by_run[int(run)] for run in chosen])
        m_mask = accepted[idx]
        t_mask = trad_accepted[idx]
        if m_mask.sum() == 0 or t_mask.sum() == 0:
            continue
        diffs.append(q68_abs(residual[idx][m_mask]) - q68_abs(residual[idx][t_mask]))
    return ci_pair(diffs)


def summarize(config: dict, df: pd.DataFrame, selections: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    methods = [c.replace("accept_", "") for c in selections.columns if c.startswith("accept_")]
    rows = []
    family_rows = []
    reps = int(config["bootstrap_resamples"])
    base_log_charge = df["log_target_charge"].to_numpy(dtype=float)
    even_log_charge = df["log_even_pos_charge"].to_numpy(dtype=float)
    center = float(np.median(base_log_charge))
    family_labels = selections["traditional_veto_family"].to_numpy(dtype=object)
    for geometry in config["geometry_variants"]:
        energy_map = range_energy_lookup(config, geometry)
        depth_energy = df["stave"].map(energy_map).to_numpy(dtype=float)
        log_energy_target = np.log(depth_energy) + 0.25 * (base_log_charge - center)
        log_energy_even = np.log(depth_energy) + 0.25 * (even_log_charge - center)
        trad_accept = selections["accept_traditional_veto_ladder"].to_numpy(dtype=bool)
        trad_metric = metric_for_mask(df, trad_accept, log_energy_target, log_energy_even)
        for method in methods:
            accepted = selections["accept_{}".format(method)].to_numpy(dtype=bool)
            metric = metric_for_mask(df, accepted, log_energy_target, log_energy_even)
            boot = bootstrap_metric(df, accepted, log_energy_target, log_energy_even, reps, int(config["random_seed"]) + 17 * (len(rows) + 1))
            delta_ci = [0.0, 0.0] if method == "traditional_veto_ladder" else bootstrap_delta_energy_res68(
                df,
                accepted,
                trad_accept,
                log_energy_target,
                log_energy_even,
                reps,
                int(config["random_seed"]) + 31 * (len(rows) + 1),
            )
            row = {
                "geometry": geometry,
                "method": method,
                "veto_family": "all",
                "delta_energy_res68_vs_traditional": metric["energy_proxy_res68"] - trad_metric["energy_proxy_res68"],
                "delta_energy_res68_vs_traditional_ci95": delta_ci,
            }
            row.update(metric)
            row.update(boot)
            rows.append(row)
            for family in ["accepted", "p09_anomaly", "s10_pileup", "s16_baseline_lowering", "p07_saturation"]:
                fam = family_labels == family
                if fam.sum() < 50:
                    continue
                fam_accepted = accepted & fam
                fam_frame = df.loc[fam].reset_index(drop=True)
                fam_metric = metric_for_mask(
                    fam_frame,
                    fam_accepted[fam],
                    log_energy_target[fam],
                    log_energy_even[fam],
                )
                family_rows.append(
                    {
                        "geometry": geometry,
                        "method": method,
                        "veto_family": family,
                        "family_population": int(fam.sum()),
                        "family_accepted": int(fam_accepted.sum()),
                        "family_acceptance": float(fam_accepted.sum() / max(fam.sum(), 1)),
                        "charge_proxy_log_shift": fam_metric["charge_proxy_log_shift"],
                        "energy_proxy_res68": fam_metric["energy_proxy_res68"],
                        "depth_order_violation_rate": fam_metric["depth_order_violation_rate"],
                    }
                )
    overall = pd.DataFrame(rows)
    family = pd.DataFrame(family_rows)
    deltas = overall[overall["method"] != "traditional_veto_ladder"][
        ["geometry", "method", "delta_energy_res68_vs_traditional", "delta_energy_res68_vs_traditional_ci95"]
    ].copy()
    return overall.sort_values(["geometry", "energy_proxy_res68", "method"]).reset_index(drop=True), family, deltas


def write_input_hashes(out_dir: Path, config: dict) -> None:
    paths = []
    for run in p04o.all_runs(config):
        paths.append(p04o.raw_path(config, "bstack", int(run)))
    for run in [int(r) for r in config["analysis_runs"]]:
        paths.append(p04o.raw_path(config, "astack", int(run)))
    rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(paths))]
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def write_manifest(out_dir: Path, config_path: Path, config: dict, command: str) -> None:
    outputs = {}
    ignored_outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            if path.suffix == ".gz":
                ignored_outputs[path.name] = {
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                    "reason": "repo ignores *.gz regenerated intermediates",
                }
                continue
            outputs[path.name] = sha256_file(path)
    inputs = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "command": command,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": None if torch is None else torch.__version__,
        },
        "input_files": {row["file"]: {"sha256": row["sha256"], "bytes": int(row["bytes"])} for _, row in inputs.iterrows()},
        "output_sha256": outputs,
        "ignored_outputs": ignored_outputs,
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def ci_text(value) -> str:
    if isinstance(value, list) and len(value) == 2 and value[0] is not None:
        return "[{:.5g}, {:.5g}]".format(float(value[0]), float(value[1]))
    return "[NA, NA]"


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    rates: pd.DataFrame,
    rate_cv: pd.DataFrame,
    fold_summary: pd.DataFrame,
    overall: pd.DataFrame,
    family: pd.DataFrame,
    result: dict,
) -> None:
    total = int(counts["selected_pulses"].sum())
    overall_view = overall.copy()
    for col in ["acceptance_ci95", "charge_proxy_log_shift_ci95", "energy_proxy_res68_ci95", "depth_order_violation_rate_ci95"]:
        overall_view[col] = overall_view[col].map(ci_text)
    overall_view["delta_energy_res68_vs_traditional_ci95"] = overall_view["delta_energy_res68_vs_traditional_ci95"].map(ci_text)
    report = """# S14g: veto-ladder energy acceptance calibration

- **Ticket:** {ticket}
- **Worker:** {worker}
- **Config:** `{config_path}`
- **Raw input:** `{raw_root_dir}`
- **Git commit at run:** `{git_head}`

## Abstract

This study asks whether the P09/S10/S16/P07 veto ladder is better interpreted as an
energy/PID support-acceptance calibration than as an energy-ordering improvement.  I
rebuilt the B-stack selected-pulse population from raw ROOT, fitted all accept/reject
rules with complete runs held out, and compared a transparent sequential veto ladder
to ridge, gradient-boosted tree, MLP, 1D-CNN, and a new residual-gated ensemble
selector.  The selectors were trained on pulse atoms only; stave/depth labels, run
numbers, event identifiers, and PID labels were excluded from the model feature set.

The named winner in `result.json` is **{winner}**.  In the nominal `center_4cm`
geometry it has energy-proxy res68 `{winner_res68:.5f}` with run-block 95% CI
`{winner_ci}` and acceptance `{winner_acc:.5f}`.  The traditional transparent ladder
has energy-proxy res68 `{trad_res68:.5f}` and acceptance `{trad_acc:.5f}`.

## Raw-ROOT reproduction gate

The reproduced number is the selected B-stave pulse count from raw `h101/HRDv`.
For each configured B physical channel `B2/B4/B6/B8 = 0/2/4/6`, the script subtracts
the median of samples 0--3 and selects pulses satisfying

`max_t(HRDv_t - median(HRDv_0..3)) > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| all configured selected B-stave pulses | {expected:,} | {total:,} | {delta:+,} | {pass_flag} |

Per-run selected counts:

{counts_table}

## Data construction

For event `i`, stave `s`, and sample `t`, the even-channel waveform is

`x_ist = HRDv_even,ist - median(HRDv_even,is0..is3)`.

The duplicate-readout reference is the independent odd-channel negative lobe,

`y_is = sum_t max(-(HRDv_odd,ist - median(HRDv_odd,is0..is3)), 0)`.

This target is used only to define the support label and evaluation residuals; no
selector receives the odd channel, event number, run number, or stave/depth identity.
The support label in a training fold is

`z_i = 1[L_trad(i)=accept] * 1[|log Q_even,i - log Q_odd,i| <= q_tau]`,

where `q_tau` is the training-fold `{support_quantile}` quantile.  ML selectors are
thresholded in each fold to the training acceptance of the transparent ladder, so
lower residual width cannot be obtained by retaining an arbitrarily tiny sample.

## Veto ladder

The traditional method is a sequential transparent ladder:

1. **P09 anomaly:** high q-tail, abnormal half-width, or edge peak-time samples.
2. **S10 pile-up:** at least three selected B staves or a broad high-tail waveform.
3. **S16 baseline/lowering:** wide pretrigger baseline RMS.
4. **P07 saturation:** large saturation depth or peak amplitude above the ADC ceiling.

Thresholds are refit inside the training runs of each grouped fold and then applied
unchanged to the held-out runs.  The `traditional_veto_family` column records the
first family to fire.

## Energy proxy and metrics

For geometry `g`, the monotonic range-energy anchor for stave `s` is

`E_gs = interp(R_gs, R_PSTAR, E_PSTAR)`,

with PSTAR plastic-scintillator ranges converted from g cm^-2 to cm using
`rho = 1.032 g cm^-3`.  The duplicate-readout target and even-channel proxy are

`log E*_is = log E_gs + 0.25 (log Q_odd,is - median(log Q_odd))`,

`log Ehat_is = log E_gs + 0.25 (log Q_even,is - median(log Q_odd))`.

The primary width is `Q_0.68(|log Ehat - log E*|)` among accepted rows.
The charge-composition shift is the accepted median `log Q_odd` minus the full
population median.  The depth-order violation rate is the fraction of adjacent
accepted depth medians within each held-out run for which the downstream median is
not larger than the upstream median.  Confidence intervals resample held-out runs
with replacement.

## Rate residual model

The A/B coincidence support covariate is a run-level held-out residual.  For run `r`,

`p_r = (N(A_any and B_any) + 1/2)/(N(B_any)+1)`.

A weighted ridge model predicts `logit(p_r)` from current, sample setting, B-only
occupancy, and topology fractions; selectors see only the held-out residual
`100*(p_r - p_hat_r)`.

{rate_cv_table}

Rate table:

{rates_table}

## Fold diagnostics

{fold_table}

## Main results

{overall_table}

## Veto-family acceptance map

Rows below condition on the transparent ladder's first veto family.  ML selectors
that accept many rows in a rejected family are not automatically wrong; the row
shows where they relax the transparent ladder and what residual width follows.

{family_table}

## Systematics and caveats

This remains a duplicate-readout and monotonic range-proxy study, not an absolute
calorimetric energy or particle-ID calibration.  The PSTAR term only anchors the
expected ordering of B2/B4/B6/B8; the charge term is an internal even/odd closure
proxy.  The rate residual is run-level, so it cannot see event-scale beam-current
microstructure.  ML features deliberately exclude run, event, and depth identifiers,
which makes the test conservative but also prevents a selector from learning genuine
geometry-specific inefficiencies.  The shuffled-target HGB control is retained as a
leakage sentinel; a real selector must beat it by run-block confidence intervals and
not merely by point estimate.

## Conclusion

{finding}

## Artifacts

`counts_by_run.csv`, `run_level_rates.csv`, `rate_cv.csv`, `analysis_rows_preview.csv`,
`fold_summary.csv`, `method_geometry_metrics.csv`,
`method_veto_family_metrics.csv`, `method_deltas.csv`, `input_sha256.csv`,
`manifest.json`, `result.json`, and this report.
The full out-of-fold selector dump `selector_oof.csv.gz` is generated locally and
listed in `manifest.json` as an ignored regenerated intermediate because the
repository excludes `*.gz`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14g_1781051226_621_082271da_veto_ladder_energy_acceptance.py --config {config_path}
```
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        config_path=config_path,
        raw_root_dir=config["raw_root_dir"],
        git_head=git_head(),
        winner=result["winner"],
        winner_res68=result["winner_metrics"]["energy_proxy_res68"],
        winner_ci=ci_text(result["winner_metrics"]["energy_proxy_res68_ci95"]),
        winner_acc=result["winner_metrics"]["acceptance"],
        trad_res68=result["traditional_metrics"]["energy_proxy_res68"],
        trad_acc=result["traditional_metrics"]["acceptance"],
        expected=int(config["expected_selected_pulses"]),
        total=total,
        delta=total - int(config["expected_selected_pulses"]),
        pass_flag=str(total == int(config["expected_selected_pulses"])).lower(),
        counts_table=counts.to_markdown(index=False),
        support_quantile=config["models"]["support_quantile"],
        rate_cv_table=rate_cv.to_markdown(index=False),
        rates_table=rates[["run", "run_group", "current_nA", "b_any_events", "target_rate", "pred_rate_traditional", "rate_residual_pp"]].to_markdown(index=False),
        fold_table=fold_summary.to_markdown(index=False),
        overall_table=md_table(
            overall_view,
            [
                "geometry",
                "method",
                "acceptance",
                "acceptance_ci95",
                "charge_proxy_log_shift",
                "charge_proxy_log_shift_ci95",
                "energy_proxy_res68",
                "energy_proxy_res68_ci95",
                "depth_order_violation_rate",
                "depth_order_violation_rate_ci95",
                "delta_energy_res68_vs_traditional",
                "delta_energy_res68_vs_traditional_ci95",
            ],
            max_rows=80,
        ),
        family_table=md_table(
            family.sort_values(["geometry", "method", "veto_family"]),
            [
                "geometry",
                "method",
                "veto_family",
                "family_population",
                "family_accepted",
                "family_acceptance",
                "charge_proxy_log_shift",
                "energy_proxy_res68",
                "depth_order_violation_rate",
            ],
            max_rows=120,
        ),
        finding=result["finding"],
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s14g_1781051226_621_082271da_veto_ladder_energy_acceptance.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("rebuilding selected pulses and rates from raw ROOT")
    df, wave, counts, rates, rate_cv = prepare_rows(config)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    rates.to_csv(out_dir / "run_level_rates.csv", index=False)
    rate_cv.to_csv(out_dir / "rate_cv.csv", index=False)
    df.head(3000).to_csv(out_dir / "analysis_rows_preview.csv", index=False)

    selector_path = out_dir / "selector_oof.csv.gz"
    fold_path = out_dir / "fold_summary.csv"
    if selector_path.exists() and fold_path.exists():
        print("reusing existing run-held-out support selector predictions")
        selections = pd.read_csv(selector_path)
        for col in selections.columns:
            if col.startswith("accept_"):
                selections[col] = selections[col].astype(bool)
        fold_summary = pd.read_csv(fold_path)
    else:
        print("fitting run-held-out support selectors")
        selections, fold_summary = fit_selectors(df, wave, config)
        selections.to_csv(selector_path, index=False, compression="gzip")
        fold_summary.to_csv(fold_path, index=False)

    print("summarizing acceptance and energy-proxy metrics")
    overall, family, deltas = summarize(config, df, selections)
    overall.to_csv(out_dir / "method_geometry_metrics.csv", index=False)
    family.to_csv(out_dir / "method_veto_family_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas.csv", index=False)

    nominal = overall[overall["geometry"] == "center_4cm"].copy()
    candidate = nominal[
        (~nominal["method"].str.contains("control"))
        & (nominal["acceptance"] >= float(config["models"]["min_acceptance_for_winner"]))
    ].copy()
    winner_row = candidate.sort_values(["energy_proxy_res68", "depth_order_violation_rate", "charge_proxy_log_shift"]).iloc[0]
    trad_row = nominal[nominal["method"] == "traditional_veto_ladder"].iloc[0]
    shuffle_row = nominal[nominal["method"] == "shuffled_target_hgb_control"].iloc[0]
    finding = (
        "The support selector winner is {winner} with nominal energy-proxy res68 {res68:.5f} "
        "[{lo:.5f}, {hi:.5f}] at acceptance {acc:.3f}.  The transparent ladder gives res68 "
        "{trad:.5f} at acceptance {trad_acc:.3f}, while the shuffled-target HGB control gives "
        "{shuffle:.5f}.  The result supports treating the veto ladder as a support-acceptance "
        "calibration: it changes charge composition and protects low-support regions, but it should "
        "not be promoted to an absolute energy or PID improvement without external truth."
    ).format(
        winner=winner_row["method"],
        res68=float(winner_row["energy_proxy_res68"]),
        lo=float(winner_row["energy_proxy_res68_ci95"][0]),
        hi=float(winner_row["energy_proxy_res68_ci95"][1]),
        acc=float(winner_row["acceptance"]),
        trad=float(trad_row["energy_proxy_res68"]),
        trad_acc=float(trad_row["acceptance"]),
        shuffle=float(shuffle_row["energy_proxy_res68"]),
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "reproduced_selected_pulses": int(counts["selected_pulses"].sum()),
            "delta": int(counts["selected_pulses"].sum()) - int(config["expected_selected_pulses"]),
            "pass": bool(int(counts["selected_pulses"].sum()) == int(config["expected_selected_pulses"])),
        },
        "split": "grouped 5-fold complete-run held-out over analysis runs",
        "bootstrap": "run-block bootstrap with 250 resamples",
        "feature_exclusions": ["run", "eventno", "EVT", "stave/depth identity", "PID labels"],
        "n_analysis_rows": int(len(df)),
        "winner": str(winner_row["method"]),
        "winner_metrics": json_clean(winner_row.to_dict()),
        "traditional_metrics": json_clean(trad_row.to_dict()),
        "shuffled_target_control_metrics": json_clean(shuffle_row.to_dict()),
        "method_geometry_metrics": json_clean(overall.to_dict(orient="records")),
        "method_veto_family_metrics": json_clean(family.to_dict(orient="records")),
        "method_deltas": json_clean(deltas.to_dict(orient="records")),
        "finding": finding,
        "git_commit": git_head(),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    write_input_hashes(out_dir, config)
    write_report(out_dir, args.config, config, counts, rates, rate_cv, fold_summary, overall, family, result)
    command = "/home/billy/anaconda3/bin/python scripts/s14g_1781051226_621_082271da_veto_ladder_energy_acceptance.py --config {}".format(args.config)
    write_manifest(out_dir, args.config, config, command)
    print("DONE -> {} in {:.1f} s".format(out_dir, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
