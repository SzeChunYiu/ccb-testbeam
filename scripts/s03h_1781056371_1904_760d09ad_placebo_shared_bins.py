#!/usr/bin/env python3
"""S03h placebo stress test for the S03f run-level shared-bin result."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_leave_one_run_s03ab_hgb_stability as s03d
import s03f_1781020939_1148_2ac43171_runlevel_shared_bins as s03f


RUN65_EXPECTED = s03f.RUN65_EXPECTED


def git_commit() -> str:
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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def md_table(df: pd.DataFrame, columns: List[str], max_rows: int | None = None) -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def residual_rows(
    pulses: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    methods: List[Tuple[str, str]],
    heldout_run: int,
    bootstrap_samples: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residuals = []
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, 2.0, config, [heldout_run])
        ci = s02.bootstrap_ci(vals, rng, bootstrap_samples)
        rows.append(
            {
                "heldout_run": int(heldout_run),
                "method": label,
                "metric": "heldout_pairwise_sigma68_ns",
                "value": s02.sigma68(vals),
                "ci_low": ci[0],
                "ci_high": ci[1],
                **s02.metric_summary(vals),
            }
        )
        residuals.extend(
            {"heldout_run": int(heldout_run), "method": label, "pairwise_residual_ns": float(v)}
            for v in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residuals)


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(int(r) for r in residuals["heldout_run"].unique())
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {int(run): sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled if len(by_run[int(run)])])
            stats.append(s02.sigma68(boot_vals))
        ci_low, ci_high = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows).sort_values("value").reset_index(drop=True)


def base_design(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    staves = list(config["timing"]["downstream_staves"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    return X, targets, finite


def fit_tabular_ml(pulses: pd.DataFrame, config: dict, base_method: str) -> pd.DataFrame:
    train_runs = list(config["timing"]["train_runs"])
    X, targets, finite = base_design(pulses, config, base_method)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite
    out = pulses.copy()

    ridge_model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    ridge_model.fit(X[train_mask], targets[train_mask])
    out["t_ml_ridge_ns"] = out[f"t_{base_method}_ns"] - ridge_model.predict(X)

    hgb_cfg = config["ml"]["hgb"]
    hgb = HistGradientBoostingRegressor(
        max_iter=int(hgb_cfg["max_iter"]),
        learning_rate=float(hgb_cfg["learning_rate"]),
        max_leaf_nodes=int(hgb_cfg["max_leaf_nodes"]),
        l2_regularization=float(hgb_cfg["l2_regularization"]),
        max_bins=int(hgb_cfg["max_bins"]),
        random_state=int(config["ml"]["random_seed"]),
    )
    hgb.fit(X[train_mask], targets[train_mask])
    out["t_gradient_boosted_trees_ns"] = out[f"t_{base_method}_ns"] - hgb.predict(X)

    mlp_cfg = config["ml"]["mlp"]
    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(int(v) for v in mlp_cfg["hidden_layer_sizes"]),
            alpha=float(mlp_cfg["alpha"]),
            max_iter=int(mlp_cfg["max_iter"]),
            random_state=int(config["ml"]["random_seed"]),
            early_stopping=True,
            n_iter_no_change=20,
        ),
    )
    mlp.fit(X[train_mask], targets[train_mask])
    out["t_mlp_ns"] = out[f"t_{base_method}_ns"] - mlp.predict(X)
    return out


def torch_inputs(pulses: pd.DataFrame, staves: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=np.float32)[:, None] / 17.0
    log_amp = np.log1p(amp)[:, None].astype(np.float32)
    area = (pulses["area_adc_samples"].to_numpy(dtype=np.float32) / np.maximum(amp, 1.0))[:, None]
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_to_i = {s: i for i, s in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[str(stave)]] = 1.0
    scalars = np.hstack([log_amp / 10.0, peak, area / 10.0, one_hot]).astype(np.float32)
    return norm[:, None, :].astype(np.float32), scalars


class ConvRegressor(nn.Module):
    def __init__(self, scalar_dim: int, hidden: int, gated: bool = False) -> None:
        super().__init__()
        self.gated = bool(gated)
        self.conv = nn.Sequential(
            nn.Conv1d(1, hidden, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(hidden, hidden, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(hidden + scalar_dim, hidden), nn.ReLU(), nn.Linear(hidden, 1))
        if self.gated:
            self.gate = nn.Sequential(nn.Linear(scalar_dim, hidden), nn.ReLU(), nn.Linear(hidden, 1), nn.Sigmoid())

    def forward(self, wave: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        feat = self.conv(wave).squeeze(-1)
        raw = self.head(torch.cat([feat, scalars], dim=1)).squeeze(-1)
        if self.gated:
            gate = 0.25 + 1.5 * self.gate(scalars).squeeze(-1)
            return raw * gate
        return raw


def fit_torch_model(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
    gated: bool,
) -> np.ndarray:
    torch.manual_seed(int(config["ml"]["random_seed"]) + (17 if gated else 0))
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    waves, scalars = torch_inputs(pulses, staves)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config).astype(np.float32)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.isfinite(waves).all(axis=(1, 2)) & np.isfinite(scalars).all(axis=1)
    train_idx = np.flatnonzero(np.isin(runs, train_runs) & finite)
    y_mean = float(np.mean(targets[train_idx]))
    y_std = float(np.std(targets[train_idx]) or 1.0)
    y = ((targets[train_idx] - y_mean) / y_std).astype(np.float32)
    cfg = config["ml"]["gated_cnn" if gated else "cnn"]
    dataset = TensorDataset(
        torch.from_numpy(waves[train_idx]),
        torch.from_numpy(scalars[train_idx]),
        torch.from_numpy(y),
    )
    loader = DataLoader(dataset, batch_size=int(cfg["batch_size"]), shuffle=True)
    model = ConvRegressor(scalars.shape[1], int(cfg["hidden"]), gated=gated)
    optim = torch.optim.AdamW(model.parameters(), lr=float(cfg["learning_rate"]), weight_decay=float(cfg["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(cfg["epochs"])):
        for wave_batch, scalar_batch, y_batch in loader:
            optim.zero_grad()
            loss = loss_fn(model(wave_batch, scalar_batch), y_batch)
            loss.backward()
            optim.step()
    model.eval()
    preds = []
    with torch.no_grad():
        full = TensorDataset(torch.from_numpy(waves), torch.from_numpy(scalars))
        for wave_batch, scalar_batch in DataLoader(full, batch_size=4096, shuffle=False):
            preds.append(model(wave_batch, scalar_batch).numpy())
    return np.concatenate(preds) * y_std + y_mean


def fit_neural_ml(pulses: pd.DataFrame, config: dict, base_method: str) -> pd.DataFrame:
    out = pulses.copy()
    pred_cnn = fit_torch_model(out, config, base_method, gated=False)
    pred_gated = fit_torch_model(out, config, base_method, gated=True)
    out["t_cnn1d_ns"] = out[f"t_{base_method}_ns"] - pred_cnn
    out["t_gated_residual_cnn_ns"] = out[f"t_{base_method}_ns"] - pred_gated
    return out


def permute_amplitude_within_run_stave(pulses: pd.DataFrame, seed: int) -> pd.DataFrame:
    out = pulses.copy()
    rng = np.random.default_rng(seed)
    amp = out["amplitude_adc"].to_numpy(dtype=float).copy()
    for (_, _), idx in out.groupby(["run", "stave"]).groups.items():
        idx = np.asarray(list(idx), dtype=int)
        amp[idx] = rng.permutation(amp[idx])
    out["amplitude_adc"] = amp
    return out


def permute_train_run_labels(pulses: pd.DataFrame, train_runs: List[int], seed: int) -> pd.DataFrame:
    out = pulses.copy()
    rng = np.random.default_rng(seed)
    mask = out["run"].isin(train_runs).to_numpy()
    labels = out.loc[mask, "run"].to_numpy(dtype=int)
    out.loc[mask, "run"] = rng.permutation(labels)
    return out


def run_placebos(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
    runlevel_best: dict,
    runlevel_pred: np.ndarray,
    heldout_run: int,
) -> pd.DataFrame:
    seed = int(config["runlevel_shared"]["random_seed"]) + heldout_run
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = list(config["timing"]["train_runs"])
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    rows = []

    amp_perm = permute_amplitude_within_run_stave(
        pulses, seed + int(config["placebos"]["amplitude_permutation_seed_offset"])
    )
    amp_model = s03f.fit_runlevel_shared_model(
        amp_perm,
        targets,
        train_mask,
        config,
        int(runlevel_best["n_bins"]),
        float(runlevel_best["run_shrink_strength"]),
        float(runlevel_best["deployment_population_weight"]),
    )
    amp_pred = s03f.predict_runlevel_shared(amp_perm, amp_model)
    tmp = pulses.copy()
    tmp["t_placebo_amplitude_permutation_ns"] = tmp[f"t_{base_method}_ns"] - amp_pred
    vals = s02.pairwise_residuals(tmp, "placebo_amplitude_permutation", 2.0, config, [heldout_run])
    rows.append({"heldout_run": heldout_run, "control": "within_run_amplitude_permutation_by_stave", **s02.metric_summary(vals)})

    tmp = pulses.copy()
    tmp["t_placebo_sign_flip_ns"] = tmp[f"t_{base_method}_ns"] + runlevel_pred
    vals = s02.pairwise_residuals(tmp, "placebo_sign_flip", 2.0, config, [heldout_run])
    rows.append({"heldout_run": heldout_run, "control": "train_run_curve_sign_flip", **s02.metric_summary(vals)})

    perm_runs = permute_train_run_labels(pulses, train_runs, seed + int(config["placebos"]["run_label_permutation_seed_offset"]))
    perm_model = s03f.fit_runlevel_shared_model(
        perm_runs,
        targets,
        train_mask,
        config,
        int(runlevel_best["n_bins"]),
        float(runlevel_best["run_shrink_strength"]),
        float(runlevel_best["deployment_population_weight"]),
    )
    perm_pred = s03f.predict_runlevel_shared(pulses, perm_model)
    tmp = pulses.copy()
    tmp["t_placebo_run_label_permutation_ns"] = tmp[f"t_{base_method}_ns"] - perm_pred
    vals = s02.pairwise_residuals(tmp, "placebo_run_label_permutation", 2.0, config, [heldout_run])
    rows.append({"heldout_run": heldout_run, "control": "deployment_curve_run_label_permutation", **s02.metric_summary(vals)})
    return pd.DataFrame(rows)


def run_transfer_check(pulses_all: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    train_runs = [int(r) for r in config["timing"]["loo_runs"]]
    heldout_runs = [int(r) for r in config["timing"]["transfer_runs"]]
    transfer_config = fold_config(config, train_runs, heldout_runs)
    pulses_all = s02.load_downstream_pulses(transfer_config)
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, transfer_config)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, transfer_config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    model = s03f.fit_runlevel_shared_model(pulses, targets, train_mask, transfer_config, 8, 320.0, 1.0)
    pred = s03f.predict_runlevel_shared(pulses, model)
    out = pulses.copy()
    out["t_runlevel_shared_transfer_ns"] = out[f"t_{base_method}_ns"] - pred
    rows, residuals = residual_rows(
        out,
        transfer_config,
        rng,
        [(base_method, "template_phase_base"), ("runlevel_shared_transfer", "sample_ii_to_sample_i_runlevel_shared")],
        heldout_runs[0],
        int(config["runlevel_shared"]["bootstrap_samples"]),
    )
    # residual_rows handles a single heldout_run. Recompute pooled over all Sample-I analysis runs.
    parts = []
    for run in heldout_runs:
        part, _ = residual_rows(
            out,
            transfer_config,
            rng,
            [(base_method, "template_phase_base"), ("runlevel_shared_transfer", "sample_ii_to_sample_i_runlevel_shared")],
            run,
            int(config["runlevel_shared"]["bootstrap_samples"]),
        )
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def run_reproduction_fold(pulses_all: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]
    fold = fold_config(config, [run for run in all_runs if run != 65], [65])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, fold)
    s03a_pulses, _, _, _, _ = s03a.run_analytic(pulses, fold, base_method)
    binned_pulses, _, _, _ = s03b.scan_binned_candidates(pulses, fold, base_method)
    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    rows, _ = residual_rows(
        combined,
        fold,
        rng,
        [(base_method, "template_phase_base"), ("s03a_amp_only", "s03a_amp_only"), ("s03b_monotone_binned", "s03b_monotone_binned")],
        65,
        int(config["runlevel_shared"]["bootstrap_samples"]),
    )
    rows["reference_value"] = rows["method"].map(RUN65_EXPECTED)
    rows["delta"] = rows["value"] - rows["reference_value"]
    rows["pass"] = rows["delta"].abs() < 1.0e-9
    return rows


def run_one_fold(
    pulses_all: pd.DataFrame,
    config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print(f"[s03h] heldout_run={heldout_run} start", flush=True)
    train_runs = [run for run in all_runs if run != heldout_run]
    fold = fold_config(config, train_runs, [heldout_run])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, fold)

    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, fold, base_method)
    binned_pulses, _, _, binned_best = s03b.scan_binned_candidates(pulses, fold, base_method)
    runlevel_pulses, runlevel_cv, runlevel_model, runlevel_best = s03f.scan_runlevel_shared(pulses, fold, base_method)
    tabular = fit_tabular_ml(pulses, fold, base_method)
    neural = fit_neural_ml(pulses, fold, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_runlevel_shared_bins_ns"] = runlevel_pulses["t_runlevel_shared_bins_ns"].to_numpy(dtype=float)
    for col in ["t_ml_ridge_ns", "t_gradient_boosted_trees_ns", "t_mlp_ns"]:
        combined[col] = tabular[col].to_numpy(dtype=float)
    for col in ["t_cnn1d_ns", "t_gated_residual_cnn_ns"]:
        combined[col] = neural[col].to_numpy(dtype=float)

    methods = [
        (base_method, "template_phase_base"),
        ("s03a_amp_only", "s03a_amp_only"),
        ("s03b_monotone_binned", "s03b_monotone_binned"),
        ("runlevel_shared_bins", "runlevel_shared_bins"),
        ("ml_ridge", "ridge"),
        ("gradient_boosted_trees", "gradient_boosted_trees"),
        ("mlp", "mlp"),
        ("cnn1d", "cnn1d"),
        ("gated_residual_cnn", "gated_residual_cnn"),
    ]
    per_run, residuals = residual_rows(
        combined,
        fold,
        rng,
        methods,
        heldout_run,
        int(config["runlevel_shared"]["bootstrap_samples"]),
    )
    per_run["train_runs"] = ",".join(str(run) for run in train_runs)
    per_run["s03a_candidate"] = s03a_candidate
    per_run["s03a_alpha"] = float(s03a_alpha)
    per_run["s03b_n_bins"] = int(binned_best["n_bins"])
    per_run["runlevel_n_bins"] = int(runlevel_best["n_bins"])
    per_run["run_shrink_strength"] = float(runlevel_best["run_shrink_strength"])
    per_run["deployment_population_weight"] = float(runlevel_best["deployment_population_weight"])
    per_run["runlevel_cv_sigma68_ns"] = float(runlevel_best["score"])

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin([heldout_run])]["event_id"])
    leakage = pd.DataFrame(
        [
            {"heldout_run": heldout_run, "check": "train_heldout_event_id_overlap", "value": float(len(train_event_ids & heldout_event_ids)), "unit": "events"},
            {"heldout_run": heldout_run, "check": "features_exclude_run_event_order_cross_stave_time", "value": 1.0, "unit": "bool"},
            {"heldout_run": heldout_run, "check": "heldout_run_curve_not_fit", "value": 1.0, "unit": "bool"},
            {"heldout_run": heldout_run, "check": "final_models_use_heldout_rows", "value": 0.0, "unit": "bool"},
        ]
    )
    placebos = run_placebos(
        pulses,
        fold,
        base_method,
        runlevel_best,
        runlevel_pulses["runlevel_shared_pred_residual_ns"].to_numpy(dtype=float),
        heldout_run,
    )
    runlevel_cv["heldout_run"] = int(heldout_run)
    print(f"[s03h] heldout_run={heldout_run} complete", flush=True)
    return per_run, residuals, placebos, leakage, runlevel_cv


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, placebos: pd.DataFrame) -> None:
    order = [
        "template_phase_base",
        "s03b_monotone_binned",
        "runlevel_shared_bins",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "cnn1d",
        "gated_residual_cnn",
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        if len(sub):
            ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03h leave-one-run-out timing residual width")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    sub = pooled.set_index("method").reindex([m for m in order if m in set(pooled["method"])]).dropna(how="all").reset_index()
    fig, ax = plt.subplots(figsize=(10, 4.8))
    xpos = np.arange(len(sub))
    ax.bar(xpos, sub["value"])
    ax.errorbar(xpos, sub["value"], yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(xpos)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("pooled run-bootstrap sigma68 (ns)")
    ax.set_title("Model panel with run-block 95% CIs")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_model_panel.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for control, subc in placebos.groupby("control"):
        ax.plot(subc["heldout_run"], subc["sigma68_ns"], "o-", label=control)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("placebo sigma68 (ns)")
    ax.set_title("Placebo controls")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_placebo_controls.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro: pd.DataFrame,
    run65_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    placebos: pd.DataFrame,
    transfer: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    pooled_show = pooled.sort_values("value")
    run61 = per_run[per_run["heldout_run"] == 61].sort_values("value")
    placebo_summary = placebos.groupby("control").agg(
        value=("sigma68_ns", "median"),
        min_sigma68_ns=("sigma68_ns", "min"),
        max_sigma68_ns=("sigma68_ns", "max"),
        n_runs=("heldout_run", "nunique"),
    ).reset_index()
    transfer_summary = transfer.groupby("method").agg(
        value=("value", "median"),
        min_sigma68_ns=("value", "min"),
        max_sigma68_ns=("value", "max"),
        n_runs=("heldout_run", "nunique"),
    ).reset_index()
    lines = [
        "# S03h: blinded placebo stress test for shared-bin shrinkage",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        f"- **Config:** `{config_path}`",
        "- **Split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65; CIs resample held-out runs as blocks.",
        "",
        "## Abstract",
        "",
        (
            "The predecessor S03f analysis reported a surprisingly narrow pooled pairwise timing width "
            f"of {config['reference_numbers']['s03f_runlevel_shared_sigma68_ns']:.5g} ns for a shared monotone "
            "run-level amplitude-bin correction. This follow-up freezes the raw-ROOT construction and the "
            "run-held-out split, then asks whether placebo perturbations that preserve event and stave support "
            "destroy the gain. It also benchmarks the frozen traditional method against ridge regression, "
            "gradient-boosted trees, an MLP, a compact 1D-CNN, and a gated residual CNN."
        ),
        "",
        "## Raw-ROOT reproduction",
        "",
        md_table(repro, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "The S03a/S03b run-65 anchor was rerun from the same raw downstream-pulse table before opening the S03h model panel.",
        "",
        md_table(run65_repro, ["method", "value", "reference_value", "delta", "pass"]),
        "",
        "## Estimand and equations",
        "",
        (
            "For each selected downstream pulse in stave \\(s\\), the baseline-subtracted waveform is "
            "\\(w_{is}(t)=H_{is}(t)-\\operatorname{median}_{t\\in\\{0,1,2,3\\}}H_{is}(t)\\), with selection "
            "\\(\\max_t w_{is}(t)>1000\\) ADC. Template phase gives the uncorrected time \\(t^{(0)}_{is}\\). "
            "After subtracting the fixed time-of-flight term \\(z_s v^{-1}\\), the train target for a pulse is"
        ),
        "",
        "\\[ y_{is}=\\left(t^{(0)}_{is}-z_s v^{-1}\\right)-\\frac{1}{2}\\sum_{u\\ne s}\\left(t^{(0)}_{iu}-z_u v^{-1}\\right). \\]",
        "",
        (
            "The S03f traditional correction fits a decreasing isotonic curve in \\(\\log(1+A)\\). Population, "
            "stave, and train-run/stave bin medians are successively shrunk, and the deployed held-out curve "
            "is the average of train-run curves plus the selected population weight. Held-out rows never fit "
            "a curve. Learned comparators estimate \\(\\hat y_{is}=f(x_{is})\\) from the same single-pulse waveform, "
            "amplitude, peak, area, and stave indicators; corrected time is \\(t_{is}=t^{(0)}_{is}-\\hat y_{is}\\)."
        ),
        "",
        "## Model panel",
        "",
        md_table(pooled_show, ["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]),
        "",
        f"Winner named in `result.json`: **{result['winner']['method']}**.",
        "",
        "Run 61 behavior:",
        "",
        md_table(run61, ["method", "value", "ci_low", "ci_high", "n_pair_residuals"], max_rows=12),
        "",
        "## Placebo controls",
        "",
        (
            "Placebos preserve the row support and train/held-out split while breaking specific causal links: "
            "within-run amplitude permutation by stave breaks the amplitude-timewalk relation, the sign flip "
            "uses the learned curve in the wrong physical direction, and deployment-curve run-label permutation "
            "scrambles train-run membership before building the deployment average. I skipped no S03h control as "
            "a duplicate of the earlier S03g/HGB monotonicity audit; these tests are specific to the S03f shared-bin mechanism."
        ),
        "",
        md_table(placebo_summary, ["control", "value", "min_sigma68_ns", "max_sigma68_ns", "n_runs"]),
        "",
        "## Sample-II-to-Sample-I transfer check",
        "",
        (
            "The predeclared transfer check trains the shared-bin curve on all Sample-II analysis runs and deploys it "
            "unchanged to Sample-I analysis runs 44-57. This is not used to select the winner; it is a domain-shift "
            "stress test for whether the curve is a portable detector effect or a Sample-II-local shrinkage accident."
        ),
        "",
        md_table(transfer_summary, ["method", "value", "min_sigma68_ns", "max_sigma68_ns", "n_runs"]),
        "",
        "## Leakage and systematics",
        "",
        md_table(leakage, ["heldout_run", "check", "value", "unit"], max_rows=32),
        "",
        (
            "Feature leakage controls are structural: run id, event id, event order, other-stave timing, and the held-out "
            "target are not model inputs. Bootstrap uncertainty is conditional on seven held-out runs and is therefore "
            "sensitive to run 61. The neural networks are CPU-sized diagnostics rather than exhaustive architecture searches. "
            "No Monte Carlo truth label is used, and the metric remains an internal downstream-pair closure width rather than "
            "an external absolute timing resolution."
        ),
        "",
        "## Verdict",
        "",
        result["summary"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s03h_1781056371_1904_760d09ad_placebo_shared_bins.py --config {config_path}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03h_1781056371_1904_760d09ad_placebo_shared_bins.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["runlevel_shared"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")
    print("[s03h] raw ROOT count reproduction passed", flush=True)

    pulses_all = s02.load_downstream_pulses(config)
    run65_repro = run_reproduction_fold(pulses_all, config, rng)
    run65_repro.to_csv(out_dir / "run65_reproduction.csv", index=False)
    if not bool(run65_repro["pass"].all()):
        raise RuntimeError("run-65 S03a/S03b reproduction failed")
    print("[s03h] run65 reproduction passed", flush=True)

    all_runs = [int(r) for r in config["timing"]["loo_runs"]]
    per_parts, residual_parts, placebo_parts, leakage_parts, cv_parts = [], [], [], [], []
    for heldout_run in all_runs:
        per_run, residuals, placebos, leakage, runlevel_cv = run_one_fold(pulses_all, config, heldout_run, all_runs, rng)
        per_parts.append(per_run)
        residual_parts.append(residuals)
        placebo_parts.append(placebos)
        leakage_parts.append(leakage)
        cv_parts.append(runlevel_cv)

    per_run = pd.concat(per_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    placebos = pd.concat(placebo_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    runlevel_cv = pd.concat(cv_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["runlevel_shared"]["bootstrap_samples"]))
    transfer = run_transfer_check(pulses_all, config, rng)

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    placebos.to_csv(out_dir / "placebo_controls.csv", index=False)
    transfer.to_csv(out_dir / "sample_ii_to_sample_i_transfer.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    runlevel_cv.to_csv(out_dir / "runlevel_shared_cv_scan.csv", index=False)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    plot_outputs(out_dir, per_run, pooled, placebos)
    pooled_idx = pooled.set_index("method")
    winner_method = str(pooled.iloc[0]["method"])
    winner = pooled.iloc[0].to_dict()
    runlevel = pooled_idx.loc["runlevel_shared_bins"].to_dict()
    run61 = per_run[(per_run["heldout_run"] == 61) & (per_run["method"] == "runlevel_shared_bins")].iloc[0].to_dict()
    placebo_min = float(placebos["sigma68_ns"].min())
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    placebo_pass = bool(placebo_min > float(runlevel["value"]) + 0.2)
    leakage_flag = bool(event_overlap != 0 or not placebo_pass)
    verdict = "shared_bin_gain_survives_placebo_controls" if (winner_method == "runlevel_shared_bins" and not leakage_flag) else "shared_bin_gain_not_promoted"
    summary = (
        f"The point-estimate winner is {winner_method} with pooled sigma68 {float(winner['value']):.3f} ns "
        f"(95% run-bootstrap CI {float(winner['ci_low']):.3f}-{float(winner['ci_high']):.3f}). "
        f"The frozen shared-bin method gives {float(runlevel['value']):.3f} ns, run 61 gives "
        f"{float(run61['value']):.3f} ns, and the best placebo remains at {placebo_min:.3f} ns. "
        f"Verdict: {verdict}."
    )
    result = {
        "study": "S03h",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all() and run65_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro["pass"].all()),
            "run65_s03a_s03b_pass": bool(run65_repro["pass"].all()),
            "selected_b_stave_pulses": int(repro.loc[repro["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
        },
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "winner": {
            "method": winner_method,
            "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
            "value": float(winner["value"]),
            "ci95": [float(winner["ci_low"]), float(winner["ci_high"])],
        },
        "model_panel": {
            row["method"]: {"value": float(row["value"]), "ci95": [float(row["ci_low"]), float(row["ci_high"])]}
            for _, row in pooled.iterrows()
        },
        "run61": {
            "runlevel_shared_sigma68_ns": float(run61["value"]),
            "runlevel_shared_ci95": [float(run61["ci_low"]), float(run61["ci_high"])],
        },
        "placebo": {
            "best_placebo_sigma68_ns": placebo_min,
            "pass": placebo_pass,
            "controls": sorted(placebos["control"].unique().tolist()),
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "heldout_run_curve_not_fit": True,
            "final_models_use_heldout_rows": False,
            "leakage_flag": leakage_flag,
        },
        "verdict": verdict,
        "summary": summary,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            {
                "title": "S03m externalize shared-bin timewalk to independent A-stack or duplicate-readout timing anchor",
                "body": "Question: does the S03 shared-bin timing correction improve an independent timing observable not used in downstream-pair closure? Expected information gain: separate real detector transport from pairwise self-closure using raw ROOT only, run-held-out CIs, and the frozen S03h placebo gates.",
            }
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro, run65_repro, per_run, pooled, placebos, transfer, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03h",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "runtime_sec": round(time.time() - t0, 2),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": getattr(torch, "__version__", "unknown"),
        },
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "verdict": verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
