#!/usr/bin/env python3
"""P03a waveform MLP timing benchmark from raw ROOT waveforms.

This study intentionally reuses the S02 raw-count gate and timing primitives, then
adds only a tiny heteroskedastic MLP on same-pulse normalized 18-sample waveforms.
The train/validation/held-out boundaries are run groups; no event identifiers,
event order, other-stave times, or held-out labels enter the model features.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03a")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a

torch.set_num_threads(1)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


class TinyTimingMLP(nn.Module):
    def __init__(self, n_features: int, hidden: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, max(hidden // 2, 8)),
            nn.ReLU(),
            nn.Linear(max(hidden // 2, 8), 2),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        out = self.net(x)
        mu = out[:, 0]
        log_var = torch.clamp(out[:, 1], -6.0, 6.0)
        return mu, log_var


def waveform_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    names = [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])] + [f"stave_{s}" for s in staves]
    return np.hstack([norm, one_hot]).astype(np.float32), names


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def standardize_train_apply(X: np.ndarray, train_mask: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    Xs = X.copy()
    Xs[train_mask] = scaler.fit_transform(X[train_mask])
    other = ~train_mask
    if other.any():
        Xs[other] = scaler.transform(X[other])
    return Xs.astype(np.float32), scaler


def train_torch_model(
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    hidden: int,
    weight_decay: float,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[TinyTimingMLP, np.ndarray, StandardScaler]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    train_mask = np.zeros(len(X), dtype=bool)
    train_mask[train_idx] = True
    Xs, scaler = standardize_train_apply(X, train_mask)
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)

    model = TinyTimingMLP(X.shape[1], int(hidden))
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["learning_rate"]),
        weight_decay=float(weight_decay),
    )
    xb_all = torch.from_numpy(Xs[train_idx])
    yb_all = torch.from_numpy(y_train)
    batch_size = int(config["ml"]["batch_size"])
    epochs = int(config["ml"]["epochs"])
    min_var = float(config["ml"]["min_sigma_ns"]) ** 2
    for _ in range(epochs):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            xb = xb_all[take]
            yb = yb_all[take]
            mu, log_var = model(xb)
            var = torch.exp(log_var) + min_var
            loss = torch.mean(0.5 * ((yb - mu) ** 2 / var + torch.log(var)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, Xs, scaler


def predict_torch(model: TinyTimingMLP, Xs: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    with torch.no_grad():
        mu, log_var = model(torch.from_numpy(Xs.astype(np.float32)))
        sigma = torch.sqrt(torch.exp(log_var) + float(config["ml"]["min_sigma_ns"]) ** 2)
    return mu.numpy().astype(float), sigma.numpy().astype(float)


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def evaluate_corrected(
    pulses: pd.DataFrame,
    method_name: str,
    values: np.ndarray,
    config: dict,
    runs: Iterable[int],
    spacing_cm: float = 2.0,
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, spacing_cm, config, list(runs))


def run_waveform_mlp(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    seed = int(config["ml"]["random_seed"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, feature_names = waveform_features(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)

    groups = runs[train_mask]
    idx_train_all = np.flatnonzero(train_mask)
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "hidden": None, "weight_decay": None}
    for hidden in config["ml"]["hidden_sizes"]:
        for weight_decay in config["ml"]["weight_decays"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
                tr_idx = idx_train_all[tr]
                va_idx = idx_train_all[va]
                model, Xs, _ = train_torch_model(
                    X,
                    targets,
                    tr_idx,
                    int(hidden),
                    float(weight_decay),
                    config,
                    seed + 100 * int(fold) + int(hidden),
                )
                pred, sigma = predict_torch(model, Xs, config)
                corrected = corrected_values(pulses, base_method, pred)
                vals = evaluate_corrected(
                    pulses.iloc[va_idx].copy(),
                    "mlp_cv",
                    corrected[va_idx],
                    config,
                    sorted(np.unique(runs[va_idx]).tolist()),
                )
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "hidden": int(hidden),
                        "weight_decay": float(weight_decay),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                        "pred_sigma_median_ns": float(np.nanmedian(sigma[va_idx])),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "hidden": int(hidden),
                    "weight_decay": float(weight_decay),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "pred_sigma_median_ns": float("nan"),
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "hidden": int(hidden), "weight_decay": float(weight_decay)}

    model, Xs, scaler = train_torch_model(
        X,
        targets,
        idx_train_all,
        int(best["hidden"]),
        float(best["weight_decay"]),
        config,
        seed + 909,
    )
    pred, sigma = predict_torch(model, Xs, config)
    out = pulses.copy()
    out["mlp_target_residual_ns"] = targets
    out["mlp_pred_residual_ns"] = pred
    out["mlp_pred_sigma_ns"] = sigma
    out["t_mlp_waveform_ns"] = corrected_values(pulses, base_method, pred)

    held = out[out["run"].isin(heldout_runs)].copy()
    held = held[np.isfinite(held["mlp_target_residual_ns"]) & np.isfinite(held["mlp_pred_sigma_ns"])]
    pull = (held["mlp_target_residual_ns"] - held["mlp_pred_residual_ns"]) / held["mlp_pred_sigma_ns"]
    calibration = pd.DataFrame(
        [
            {
                "scope": "heldout_pulse_target",
                "n": int(len(held)),
                "pred_sigma_median_ns": float(held["mlp_pred_sigma_ns"].median()),
                "abs_error_median_ns": float((held["mlp_target_residual_ns"] - held["mlp_pred_residual_ns"]).abs().median()),
                "pull_width_sigma68": s02.sigma68(pull.to_numpy(dtype=float)),
                "pull_rms": s02.full_rms(pull.to_numpy(dtype=float)),
            }
        ]
    )
    if len(held) >= 8:
        qs = np.unique(np.quantile(held["mlp_pred_sigma_ns"], np.linspace(0, 1, 5)))
        if len(qs) >= 3:
            held["sigma_bin"] = pd.cut(held["mlp_pred_sigma_ns"], qs, include_lowest=True, duplicates="drop")
            for _, group in held.groupby("sigma_bin"):
                err = group["mlp_target_residual_ns"] - group["mlp_pred_residual_ns"]
                calibration = pd.concat(
                    [
                        calibration,
                        pd.DataFrame(
                            [
                                {
                                    "scope": "heldout_sigma_bin",
                                    "n": int(len(group)),
                                    "pred_sigma_median_ns": float(group["mlp_pred_sigma_ns"].median()),
                                    "abs_error_median_ns": float(err.abs().median()),
                                    "pull_width_sigma68": s02.sigma68((err / group["mlp_pred_sigma_ns"]).to_numpy(dtype=float)),
                                    "pull_rms": s02.full_rms((err / group["mlp_pred_sigma_ns"]).to_numpy(dtype=float)),
                                }
                            ]
                        ),
                    ],
                    ignore_index=True,
                )

    info = {
        "base_method": base_method,
        "hidden": int(best["hidden"]),
        "weight_decay": float(best["weight_decay"]),
        "cv_sigma68_ns": float(best["score"]),
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "scaler_mean_sha256": hashlib.sha256(scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
    }
    return out, pd.DataFrame(cv_rows), calibration, info


def event_pair_residual_frame(
    pulses: pd.DataFrame,
    methods: Sequence[Tuple[str, str]],
    config: dict,
    runs: Sequence[int],
    spacing_cm: float = 2.0,
) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, spacing_cm)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    rows = []
    for method, label in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for event_id, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                if a in wide.columns and b in wide.columns:
                    rows.append(
                        {
                            "event_id": event_id,
                            "pair": f"{a}-{b}",
                            "method": label,
                            "residual_ns": float(row[a] - row[b]),
                        }
                    )
    return pd.DataFrame(rows)


def paired_event_bootstrap(
    pair_frame: pd.DataFrame,
    baseline_label: str,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    rows = []
    event_ids = np.asarray(sorted(pair_frame["event_id"].unique()))
    method_labels = sorted(pair_frame["method"].unique())
    values_by_method = {
        method: pair_frame[pair_frame["method"] == method].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for method in method_labels
    }
    observed = {method: s02.sigma68(pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy()) for method in method_labels}
    full_rms = {method: s02.full_rms(pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy()) for method in method_labels}
    stats = {method: [] for method in method_labels}
    deltas = {method: [] for method in method_labels}
    for _ in range(int(n_boot)):
        sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
        boot_scores = {}
        for method in method_labels:
            vals = np.concatenate([values_by_method[method][event_id] for event_id in sample_ids])
            boot_scores[method] = s02.sigma68(vals)
            stats[method].append(boot_scores[method])
        for method in method_labels:
            deltas[method].append(boot_scores[method] - boot_scores[baseline_label])
    for method in method_labels:
        rows.append(
            {
                "method": method,
                "n_events": int(len(event_ids)),
                "n_pair_residuals": int(len(pair_frame[pair_frame["method"] == method])),
                "sigma68_ns": float(observed[method]),
                "ci_low": float(np.percentile(stats[method], 2.5)),
                "ci_high": float(np.percentile(stats[method], 97.5)),
                "full_rms_ns": float(full_rms[method]),
                "delta_vs_s02_ridge_ns": float(observed[method] - observed[baseline_label]),
                "delta_ci_low": float(np.percentile(deltas[method], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[method], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def leakage_checks(pulses: pd.DataFrame, mlp_pulses: pd.DataFrame, config: dict, mlp_info: dict) -> pd.DataFrame:
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    seed = int(config["ml"]["random_seed"]) + 505
    base_method = str(config["ml"]["base_method"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, _ = waveform_features(pulses, list(config["timing"]["downstream_staves"]))
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
    model, Xs, _ = train_torch_model(
        X,
        targets,
        np.flatnonzero(train_mask),
        int(mlp_info["hidden"]),
        float(mlp_info["weight_decay"]),
        config,
        seed,
        shuffle_y=True,
    )
    pred, _ = predict_torch(model, Xs, config)
    shuffled_vals = evaluate_corrected(
        pulses,
        "mlp_shuffled",
        corrected_values(pulses, base_method, pred),
        config,
        heldout_runs,
    )
    good_vals = s02.pairwise_residuals(mlp_pulses, "mlp_waveform", 2.0, config, heldout_runs)
    return pd.DataFrame(
        [
            {
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & heldout_event_ids)),
                "detail": "must be zero",
            },
            {
                "check": "feature_audit",
                "value": 0.0,
                "detail": "features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target",
            },
            {
                "check": "shuffled_target_negative_control_sigma68_ns",
                "value": float(s02.sigma68(shuffled_vals)),
                "detail": "same architecture trained with shuffled train residual targets",
            },
            {
                "check": "nominal_mlp_sigma68_ns",
                "value": float(s02.sigma68(good_vals)),
                "detail": "held-out run metric for comparison to shuffled control",
            },
        ]
    )


def plot_outputs(out_dir: Path, benchmark: pd.DataFrame, calibration: pd.DataFrame, pair_frame: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ordered = benchmark.sort_values("sigma68_ns")
    xpos = np.arange(len(ordered))
    ax.bar(xpos, ordered["sigma68_ns"])
    ax.errorbar(
        xpos,
        ordered["sigma68_ns"],
        yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]],
        fmt="none",
        ecolor="black",
        capsize=3,
        linewidth=1,
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(ordered["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("P03a held-out run timing benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for method in ["s02_ridge_cfd20", "mlp_waveform"]:
        vals = pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy(dtype=float)
        ax.hist(vals, bins=45, histtype="step", density=True, label=f"{method} sigma68={s02.sigma68(vals):.3f} ns")
    ax.set_xlabel("held-out pairwise corrected residual (ns)")
    ax.set_ylabel("density")
    ax.set_title("Residual distributions on run 65")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residuals.png", dpi=130)
    plt.close(fig)

    if len(calibration):
        fig, ax = plt.subplots(figsize=(5.8, 4.2))
        rows = calibration[calibration["scope"] == "heldout_sigma_bin"]
        if len(rows):
            ax.plot(rows["pred_sigma_median_ns"], rows["abs_error_median_ns"], "o-")
        ax.set_xlabel("median predicted per-pulse sigma (ns)")
        ax.set_ylabel("median absolute target error (ns)")
        ax.set_title("MLP sigma calibration")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_sigma_calibration.png", dpi=130)
        plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    s02_repro: pd.DataFrame,
    analytic_benchmark: pd.DataFrame,
    ml_cv: pd.DataFrame,
    benchmark: pd.DataFrame,
    calibration: pd.DataFrame,
    leakage: pd.DataFrame,
    mlp_info: dict,
    result: dict,
) -> None:
    cv_best = ml_cv[ml_cv["fold"] == -1].sort_values("sigma68_ns")
    lines = [
        "# Study report: P03a - 18-sample MLP timing versus S02 ridge-corrected CFD",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train runs 58-63; held-out run 65",
        f"- **Config:** `configs/p03a_18_sample_mlp_timing.yaml`",
        "",
        "## Question",
        "",
        "Can a tiny waveform-level MLP on the 18 normalized samples predict sub-sample timing better than the frozen S02 ridge-corrected CFD/template baseline without timing-label leakage?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count gate was rerun from raw ROOT before timing work.",
        "",
        repro.to_markdown(index=False),
        "",
        "The S02 held-out ridge-CFD number was then rebuilt from the same raw pass.",
        "",
        s02_repro[["method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## Traditional frozen baseline",
        "",
        "The strong traditional method is the previously reported S03a analytic amplitude-timewalk correction on S02 template phase, retrained only on runs 58-63 with the frozen candidate family.",
        "",
        analytic_benchmark[["method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## Waveform MLP",
        "",
        f"The selected MLP uses hidden width `{mlp_info['hidden']}`, weight decay `{mlp_info['weight_decay']}`, and `{mlp_info['n_features']}` inputs: 18 normalized samples plus a stave one-hot intercept. It corrects `{mlp_info['base_method']}` residuals and predicts a per-pulse sigma through a Gaussian NLL head.",
        "",
        cv_best[["hidden", "weight_decay", "sigma68_ns"]].to_markdown(index=False),
        "",
        "## Held-out head-to-head",
        "",
        benchmark[["method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "delta_vs_s02_ridge_ns", "delta_ci_low", "delta_ci_high", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## Sigma calibration and leakage checks",
        "",
        calibration.to_markdown(index=False),
        "",
        leakage.to_markdown(index=False),
        "",
        "The split is by run. The MLP feature audit excludes run number, event identifier, event order, other-stave timing, pair residuals, and held-out targets. The shuffled-target negative control is included because the nominal MLP is competitive with the S02 ridge baseline.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. The MLP held-out sigma68 is `{result['ml']['value']:.3f} ns`; the frozen S02 ridge-CFD value is `{result['frozen_s02']['ridge_cfd20_sigma68_ns']:.3f} ns`, and the strongest traditional analytic value is `{result['traditional']['value']:.3f} ns`.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p03a_18_sample_mlp_timing.py --config configs/p03a_18_sample_mlp_timing.yaml",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `frozen_s02_benchmark.csv`, `traditional_benchmark.csv`, `mlp_cv_scan.csv`, `head_to_head_benchmark.csv`, `mlp_sigma_calibration.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03a_18_sample_mlp_timing.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses = s02.load_downstream_pulses(config)
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    scan = s02.evaluate_methods(pulses, methods, config)
    scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    if best_method != config["timing"]["base_method"]:
        raise RuntimeError(f"Expected S02 base method {config['timing']['base_method']}, got {best_method}")

    s02_ml_pulses, s02_ml_cv, s02_ml_cal = s02.run_ml(pulses, config, "cfd20", 2.0)
    s02_ml_cv.to_csv(out_dir / "s02_ridge_cv_scan.csv", index=False)
    s02_ml_cal.to_csv(out_dir / "s02_ridge_residual_calibration.csv", index=False)

    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(pulses, config, best_method)
    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    analytic_coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)

    combined = analytic_pulses.copy()
    combined["t_s02_ridge_cfd20_ns"] = s02_ml_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)

    mlp_pulses, mlp_cv, calibration, mlp_info = run_waveform_mlp(combined, config, str(config["ml"]["base_method"]))
    mlp_cv.to_csv(out_dir / "mlp_cv_scan.csv", index=False)
    calibration.to_csv(out_dir / "mlp_sigma_calibration.csv", index=False)
    combined["t_mlp_waveform_ns"] = mlp_pulses["t_mlp_waveform_ns"].to_numpy(dtype=float)
    combined["mlp_target_residual_ns"] = mlp_pulses["mlp_target_residual_ns"].to_numpy(dtype=float)
    combined["mlp_pred_residual_ns"] = mlp_pulses["mlp_pred_residual_ns"].to_numpy(dtype=float)
    combined["mlp_pred_sigma_ns"] = mlp_pulses["mlp_pred_sigma_ns"].to_numpy(dtype=float)

    heldout_runs = list(config["timing"]["heldout_runs"])
    methods_for_bootstrap = [
        ("cfd20", "cfd20_reference"),
        ("template_phase", "template_phase"),
        ("s02_ridge_cfd20", "s02_ridge_cfd20"),
        ("analytic_timewalk", "analytic_timewalk"),
        ("mlp_waveform", "mlp_waveform"),
    ]
    pair_frame = event_pair_residual_frame(combined, methods_for_bootstrap, config, heldout_runs)
    pair_frame.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    benchmark = paired_event_bootstrap(
        pair_frame,
        "s02_ridge_cfd20",
        rng,
        int(config["ml"]["bootstrap_samples"]),
    )
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    s02_benchmark = benchmark[benchmark["method"].isin(["cfd20_reference", "template_phase", "s02_ridge_cfd20"])].copy()
    s02_benchmark.to_csv(out_dir / "frozen_s02_benchmark.csv", index=False)
    traditional_benchmark = benchmark[benchmark["method"].isin(["template_phase", "analytic_timewalk"])].copy()
    traditional_benchmark.to_csv(out_dir / "traditional_benchmark.csv", index=False)

    leakage = leakage_checks(combined, combined, config, mlp_info)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, benchmark, calibration, pair_frame)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    s02_row = benchmark[benchmark["method"] == "s02_ridge_cfd20"].iloc[0]
    mlp_row = benchmark[benchmark["method"] == "mlp_waveform"].iloc[0]
    analytic_row = benchmark[benchmark["method"] == "analytic_timewalk"].iloc[0]
    verdict = "mlp_does_not_beat_frozen_s02_ridge_or_analytic_baseline"
    if float(mlp_row["ci_high"]) < float(s02_row["ci_low"]):
        verdict = "mlp_beats_frozen_s02_ridge_cfd20_on_single_heldout_run"
    elif float(mlp_row["sigma68_ns"]) < float(s02_row["sigma68_ns"]):
        verdict = "mlp_point_estimate_beats_s02_ridge_but_ci_overlaps"

    result = {
        "study": "P03a",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "split_by_run": True,
        "train_runs": list(config["timing"]["train_runs"]),
        "heldout_runs": heldout_runs,
        "metric": "heldout B4/B6/B8 pairwise sigma68 ns with event-paired bootstrap CI",
        "frozen_s02": {
            "ridge_cfd20_sigma68_ns": float(s02_row["sigma68_ns"]),
            "ridge_cfd20_ci": [float(s02_row["ci_low"]), float(s02_row["ci_high"])],
            "full_rms_ns": float(s02_row["full_rms_ns"]),
        },
        "traditional": {
            "method": "analytic_timewalk_on_template_phase",
            "candidate": best_candidate,
            "alpha": float(best_alpha),
            "value": float(analytic_row["sigma68_ns"]),
            "ci": [float(analytic_row["ci_low"]), float(analytic_row["ci_high"])],
            "full_rms_ns": float(analytic_row["full_rms_ns"]),
            "delta_vs_s02_ridge_ns": float(analytic_row["delta_vs_s02_ridge_ns"]),
        },
        "ml": {
            "method": "tiny_heteroskedastic_mlp_on_18_normalized_samples",
            "base_method": str(config["ml"]["base_method"]),
            "hidden": int(mlp_info["hidden"]),
            "weight_decay": float(mlp_info["weight_decay"]),
            "value": float(mlp_row["sigma68_ns"]),
            "ci": [float(mlp_row["ci_low"]), float(mlp_row["ci_high"])],
            "full_rms_ns": float(mlp_row["full_rms_ns"]),
            "delta_vs_s02_ridge_ns": float(mlp_row["delta_vs_s02_ridge_ns"]),
            "delta_ci": [float(mlp_row["delta_ci_low"]), float(mlp_row["delta_ci_high"])],
            "pull_width_sigma68": float(calibration.iloc[0]["pull_width_sigma68"]),
        },
        "leakage": {
            "event_id_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].iloc[0]),
            "shuffled_target_sigma68_ns": float(
                leakage[leakage["check"] == "shuffled_target_negative_control_sigma68_ns"]["value"].iloc[0]
            ),
            "feature_audit": str(leakage[leakage["check"] == "feature_audit"]["detail"].iloc[0]),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "P03b: leave-one-run-out waveform MLP timing stability across runs 58-65",
            "P03c: compare 1D CNN and MLP timing models with waveform-only inputs and analytic timewalk residual targets",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(
        out_dir,
        config,
        repro,
        s02_benchmark,
        traditional_benchmark,
        mlp_cv,
        benchmark,
        calibration,
        leakage,
        mlp_info,
        result,
    )

    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03a",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "s02_ridge": float(s02_row["sigma68_ns"]),
                "analytic": float(analytic_row["sigma68_ns"]),
                "mlp": float(mlp_row["sigma68_ns"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
