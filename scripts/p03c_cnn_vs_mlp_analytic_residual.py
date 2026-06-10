#!/usr/bin/env python3
"""P03c CNN-vs-MLP waveform timing after analytic timewalk correction.

The raw-ROOT reproduction gate and the prior P03a MLP number are rebuilt before
the P03c analytic-residual models are evaluated. P03c features are only the 18
baseline-subtracted waveform samples normalized by same-pulse amplitude.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03c")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

import p03a_18_sample_mlp_timing as p03a
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


def waveform_only_features(pulses: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    x = wf / np.maximum(amp[:, None], 1.0)
    return x.astype(np.float32), [f"sample_{i:02d}_over_amp" for i in range(x.shape[1])]


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


class MLPResidual(nn.Module):
    def __init__(self, n_samples: int, hidden: int) -> None:
        super().__init__()
        mid = max(int(hidden) // 2, 8)
        self.net = nn.Sequential(
            nn.Linear(n_samples, int(hidden)),
            nn.ReLU(),
            nn.Linear(int(hidden), mid),
            nn.ReLU(),
            nn.Linear(mid, 2),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        out = self.net(x)
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


class CNNResidual(nn.Module):
    def __init__(self, n_samples: int, channels: int) -> None:
        super().__init__()
        c = int(channels)
        self.features = nn.Sequential(
            nn.Conv1d(1, c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(c, 2 * c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(2 * c, max(2 * c, 8)), nn.ReLU(), nn.Linear(max(2 * c, 8), 2))
        self.n_samples = int(n_samples)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if x.ndim == 2:
            x = x[:, None, :]
        out = self.head(self.features(x))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


def standardize_by_train(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    train_mask = np.zeros(len(X), dtype=bool)
    train_mask[train_idx] = True
    scaler = StandardScaler()
    Xs = X.copy()
    Xs[train_mask] = scaler.fit_transform(X[train_mask])
    if (~train_mask).any():
        Xs[~train_mask] = scaler.transform(X[~train_mask])
    return Xs.astype(np.float32), scaler


def build_model(kind: str, n_samples: int, size: int) -> nn.Module:
    if kind == "mlp_analytic_residual":
        return MLPResidual(n_samples, size)
    if kind == "cnn_analytic_residual":
        return CNNResidual(n_samples, size)
    raise ValueError(f"unknown model kind: {kind}")


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    kind: str,
    size: int,
    weight_decay: float,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[nn.Module, np.ndarray, StandardScaler]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    Xs, scaler = standardize_by_train(X, train_idx)
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)
    model = build_model(kind, X.shape[1], int(size))
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["learning_rate"]),
        weight_decay=float(weight_decay),
    )
    xb_all = torch.from_numpy(Xs[train_idx])
    yb_all = torch.from_numpy(y_train)
    batch_size = int(config["ml"]["batch_size"])
    min_var = float(config["ml"]["min_sigma_ns"]) ** 2
    for _ in range(int(config["ml"]["epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            mu, log_var = model(xb_all[take])
            var = torch.exp(log_var) + min_var
            loss = torch.mean(0.5 * ((yb_all[take] - mu) ** 2 / var + torch.log(var)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, Xs, scaler


def predict_model(model: nn.Module, Xs: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
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
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, list(runs))


def run_waveform_model(
    pulses: pd.DataFrame,
    config: dict,
    kind: str,
    size_values: Sequence[int],
    base_method: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    seed = int(config["ml"]["random_seed"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, feature_names = waveform_only_features(pulses)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
    idx_train_all = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    gkf = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    cv_rows = []
    best = {"score": np.inf, "size": None, "weight_decay": None}
    for size in size_values:
        for weight_decay in config["ml"]["weight_decays"]:
            scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
                tr_idx = idx_train_all[tr]
                va_idx = idx_train_all[va]
                model, Xs, _ = train_model(
                    X,
                    targets,
                    tr_idx,
                    kind,
                    int(size),
                    float(weight_decay),
                    config,
                    seed + 1009 * fold + 17 * int(size),
                )
                pred, sigma = predict_model(model, Xs, config)
                vals = evaluate_corrected(
                    pulses.iloc[va_idx].copy(),
                    f"{kind}_cv",
                    corrected_values(pulses, base_method, pred)[va_idx],
                    config,
                    sorted(np.unique(runs[va_idx]).tolist()),
                )
                score = s02.sigma68(vals)
                scores.append(score)
                cv_rows.append(
                    {
                        "model": kind,
                        "size": int(size),
                        "weight_decay": float(weight_decay),
                        "fold": int(fold),
                        "sigma68_ns": float(score),
                        "n_pair_residuals": int(len(vals)),
                        "pred_sigma_median_ns": float(np.nanmedian(sigma[va_idx])),
                    }
                )
            mean_score = float(np.nanmean(scores))
            cv_rows.append(
                {
                    "model": kind,
                    "size": int(size),
                    "weight_decay": float(weight_decay),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "pred_sigma_median_ns": float("nan"),
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "size": int(size), "weight_decay": float(weight_decay)}
    model, Xs, scaler = train_model(
        X,
        targets,
        idx_train_all,
        kind,
        int(best["size"]),
        float(best["weight_decay"]),
        config,
        seed + (301 if kind.startswith("mlp") else 601),
    )
    pred, sigma = predict_model(model, Xs, config)
    out = pulses.copy()
    out[f"{kind}_target_residual_ns"] = targets
    out[f"{kind}_pred_residual_ns"] = pred
    out[f"{kind}_pred_sigma_ns"] = sigma
    out[f"t_{kind}_ns"] = corrected_values(pulses, base_method, pred)

    held = out[out["run"].isin(heldout_runs)].copy()
    held = held[np.isfinite(held[f"{kind}_target_residual_ns"]) & np.isfinite(held[f"{kind}_pred_sigma_ns"])]
    err = held[f"{kind}_target_residual_ns"] - held[f"{kind}_pred_residual_ns"]
    pull = err / held[f"{kind}_pred_sigma_ns"]
    cal_rows = [
        {
            "model": kind,
            "scope": "heldout_pulse_target",
            "n": int(len(held)),
            "pred_sigma_median_ns": float(held[f"{kind}_pred_sigma_ns"].median()),
            "abs_error_median_ns": float(err.abs().median()),
            "pull_width_sigma68": s02.sigma68(pull.to_numpy(dtype=float)),
            "pull_rms": s02.full_rms(pull.to_numpy(dtype=float)),
        }
    ]
    if len(held) >= 8:
        qs = np.unique(np.quantile(held[f"{kind}_pred_sigma_ns"], np.linspace(0, 1, 5)))
        if len(qs) >= 3:
            held["sigma_bin"] = pd.cut(held[f"{kind}_pred_sigma_ns"], qs, include_lowest=True, duplicates="drop")
            for _, group in held.groupby("sigma_bin"):
                gerr = group[f"{kind}_target_residual_ns"] - group[f"{kind}_pred_residual_ns"]
                cal_rows.append(
                    {
                        "model": kind,
                        "scope": "heldout_sigma_bin",
                        "n": int(len(group)),
                        "pred_sigma_median_ns": float(group[f"{kind}_pred_sigma_ns"].median()),
                        "abs_error_median_ns": float(gerr.abs().median()),
                        "pull_width_sigma68": s02.sigma68((gerr / group[f"{kind}_pred_sigma_ns"]).to_numpy(dtype=float)),
                        "pull_rms": s02.full_rms((gerr / group[f"{kind}_pred_sigma_ns"]).to_numpy(dtype=float)),
                    }
                )
    info = {
        "model": kind,
        "base_method": base_method,
        "size": int(best["size"]),
        "weight_decay": float(best["weight_decay"]),
        "cv_sigma68_ns": float(best["score"]),
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "scaler_mean_sha256": hashlib.sha256(scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
    }
    return out, pd.DataFrame(cv_rows), pd.DataFrame(cal_rows), info


def event_pair_residual_frame(
    pulses: pd.DataFrame,
    methods: Sequence[Tuple[str, str]],
    config: dict,
    runs: Sequence[int],
) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    rows = []
    for method, label in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for event_id, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                if a in wide.columns and b in wide.columns:
                    rows.append({"event_id": event_id, "pair": f"{a}-{b}", "method": label, "residual_ns": float(row[a] - row[b])})
    return pd.DataFrame(rows)


def paired_event_bootstrap(
    pair_frame: pd.DataFrame,
    baseline_label: str,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    rows = []
    event_ids = np.asarray(sorted(pair_frame["event_id"].unique()))
    labels = sorted(pair_frame["method"].unique())
    by_method = {
        label: pair_frame[pair_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for label in labels
    }
    observed = {label: s02.sigma68(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    full_rms = {label: s02.full_rms(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
        boot = {}
        for label in labels:
            vals = np.concatenate([by_method[label][event_id] for event_id in sample_ids])
            boot[label] = s02.sigma68(vals)
            stats[label].append(boot[label])
        for label in labels:
            deltas[label].append(boot[label] - boot[baseline_label])
    for label in labels:
        rows.append(
            {
                "method": label,
                "n_events": int(len(event_ids)),
                "n_pair_residuals": int(len(pair_frame[pair_frame["method"] == label])),
                "sigma68_ns": float(observed[label]),
                "ci_low": float(np.percentile(stats[label], 2.5)),
                "ci_high": float(np.percentile(stats[label], 97.5)),
                "full_rms_ns": float(full_rms[label]),
                "delta_vs_analytic_ns": float(observed[label] - observed[baseline_label]),
                "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def leakage_checks(
    pulses: pd.DataFrame,
    config: dict,
    model_infos: Sequence[dict],
) -> pd.DataFrame:
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    base_method = str(config["ml"]["base_method"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, _ = waveform_only_features(pulses)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
    rows = [
        {
            "check": "train_heldout_event_id_overlap",
            "model": "all",
            "value": float(len(train_event_ids & heldout_event_ids)),
            "detail": "must be zero",
        },
        {
            "check": "feature_audit",
            "model": "all",
            "value": 0.0,
            "detail": "18 normalized same-pulse waveform samples only; no run, event id, event order, stave id, amplitude scalar, other-stave time, or held-out target",
        },
    ]
    for i, info in enumerate(model_infos):
        kind = str(info["model"])
        model, Xs, _ = train_model(
            X,
            targets,
            np.flatnonzero(train_mask),
            kind,
            int(info["size"]),
            float(info["weight_decay"]),
            config,
            int(config["ml"]["random_seed"]) + 701 + i,
            shuffle_y=True,
        )
        pred, _ = predict_model(model, Xs, config)
        vals = evaluate_corrected(pulses, f"{kind}_shuffled", corrected_values(pulses, base_method, pred), config, heldout_runs)
        good = s02.pairwise_residuals(pulses, kind, 2.0, config, heldout_runs)
        rows.extend(
            [
                {
                    "check": "shuffled_target_negative_control_sigma68_ns",
                    "model": kind,
                    "value": float(s02.sigma68(vals)),
                    "detail": "same architecture trained with shuffled train residual targets",
                },
                {
                    "check": "nominal_sigma68_ns",
                    "model": kind,
                    "value": float(s02.sigma68(good)),
                    "detail": "held-out run metric for comparison to shuffled control",
                },
            ]
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, benchmark: pd.DataFrame, pair_frame: pd.DataFrame, cv: pd.DataFrame) -> None:
    ordered = benchmark.sort_values("sigma68_ns")
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    x = np.arange(len(ordered))
    ax.bar(x, ordered["sigma68_ns"])
    ax.errorbar(
        x,
        ordered["sigma68_ns"],
        yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]],
        fmt="none",
        ecolor="black",
        capsize=3,
        linewidth=1,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("P03c held-out run timing benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for method in ["analytic_timewalk", "mlp_analytic_residual", "cnn_analytic_residual"]:
        vals = pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy(dtype=float)
        ax.hist(vals, bins=45, histtype="step", density=True, label=f"{method} sigma68={s02.sigma68(vals):.3f} ns")
    ax.set_xlabel("held-out pairwise corrected residual (ns)")
    ax.set_ylabel("density")
    ax.set_title("Residual distributions on run 65")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residuals.png", dpi=130)
    plt.close(fig)

    best_cv = cv[cv["fold"] == -1].copy()
    if len(best_cv):
        fig, ax = plt.subplots(figsize=(6.5, 4.1))
        labels = best_cv["model"] + " size=" + best_cv["size"].astype(str) + " wd=" + best_cv["weight_decay"].astype(str)
        order = np.argsort(best_cv["sigma68_ns"].to_numpy())
        ax.bar(np.arange(len(best_cv)), best_cv.iloc[order]["sigma68_ns"])
        ax.set_xticks(np.arange(len(best_cv)))
        ax.set_xticklabels(labels.iloc[order], rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("run-CV sigma68 (ns)")
        ax.set_title("P03c grouped-run CV")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_cv_scan.png", dpi=130)
        plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    p03a_benchmark: pd.DataFrame,
    p03a_mlp_info: dict,
    benchmark: pd.DataFrame,
    cv: pd.DataFrame,
    calibration: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    best_cv = cv[cv["fold"] == -1].sort_values(["model", "sigma68_ns"])
    lines = [
        "# Study report: P03c - CNN versus MLP timing with analytic residual targets",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train runs 58-63; held-out run 65",
        f"- **Config:** `{config_path}`",
        "",
        "## Question",
        "",
        "Does a tiny 1D CNN add held-out timing information beyond the P03a MLP architecture when both see only normalized waveform samples and correct residuals left by the analytic timewalk baseline?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count gate was rerun from raw ROOT before timing work.",
        "",
        repro.to_markdown(index=False),
        "",
        "The prior P03a waveform-MLP number was then rebuilt before the P03c models.",
        "",
        p03a_benchmark[["method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        f"P03a MLP reproduction used hidden `{p03a_mlp_info['hidden']}`, weight decay `{p03a_mlp_info['weight_decay']}`, and `{p03a_mlp_info['n_features']}` inputs.",
        "",
        "## Methods",
        "",
        "Traditional baseline: S03a analytic amplitude-timewalk correction on S02 template phase, trained only on runs 58-63.",
        "",
        "ML methods: the P03a heteroskedastic MLP architecture and a tiny two-layer 1D CNN. Both use only the 18 same-pulse waveform samples divided by pulse amplitude, target analytic-timewalk residuals on train runs, and are selected by grouped run CV.",
        "",
        best_cv[["model", "size", "weight_decay", "sigma68_ns"]].to_markdown(index=False),
        "",
        "## Held-out head-to-head",
        "",
        benchmark[["method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "delta_vs_analytic_ns", "delta_ci_low", "delta_ci_high", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## Calibration and leakage checks",
        "",
        calibration.to_markdown(index=False),
        "",
        leakage.to_markdown(index=False),
        "",
        "The split is by run. The feature audit excludes run number, event identifier, event order, stave id, explicit amplitude scalars, other-stave timing, pair residuals, and held-out targets. Shuffled-target controls were run for both learned models.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. The CNN held-out sigma68 is `{result['ml']['cnn']['value']:.3f} ns`, the P03c MLP is `{result['ml']['mlp']['value']:.3f} ns`, and the analytic traditional baseline is `{result['traditional']['value']:.3f} ns`.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/p03c_cnn_vs_mlp_analytic_residual.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `p03a_reproduction_benchmark.csv`, `p03c_cv_scan.csv`, `p03c_calibration.csv`, `head_to_head_benchmark.csv`, `heldout_pair_residuals.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03c_cnn_vs_mlp_analytic_residual.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    p03a_config = load_config(Path(config["p03a_config"]))
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

    s02_ml_pulses, s02_ml_cv, s02_ml_cal = s02.run_ml(pulses, p03a_config, "cfd20", 2.0)
    s02_ml_cv.to_csv(out_dir / "s02_ridge_cv_scan.csv", index=False)
    s02_ml_cal.to_csv(out_dir / "s02_ridge_residual_calibration.csv", index=False)

    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(pulses, config, best_method)
    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    analytic_coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)

    combined = analytic_pulses.copy()
    combined["t_s02_ridge_cfd20_ns"] = s02_ml_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)

    p03a_mlp_pulses, p03a_mlp_cv, p03a_mlp_cal, p03a_mlp_info = p03a.run_waveform_mlp(combined, p03a_config, str(p03a_config["ml"]["base_method"]))
    p03a_mlp_cv.to_csv(out_dir / "p03a_mlp_cv_scan.csv", index=False)
    p03a_mlp_cal.to_csv(out_dir / "p03a_mlp_sigma_calibration.csv", index=False)
    combined["t_p03a_mlp_waveform_ns"] = p03a_mlp_pulses["t_mlp_waveform_ns"].to_numpy(dtype=float)

    mlp_pulses, mlp_cv, mlp_cal, mlp_info = run_waveform_model(
        combined,
        config,
        "mlp_analytic_residual",
        config["ml"]["mlp_hidden_sizes"],
        str(config["ml"]["base_method"]),
    )
    combined["t_mlp_analytic_residual_ns"] = mlp_pulses["t_mlp_analytic_residual_ns"].to_numpy(dtype=float)

    cnn_pulses, cnn_cv, cnn_cal, cnn_info = run_waveform_model(
        combined,
        config,
        "cnn_analytic_residual",
        config["ml"]["cnn_channels"],
        str(config["ml"]["base_method"]),
    )
    combined["t_cnn_analytic_residual_ns"] = cnn_pulses["t_cnn_analytic_residual_ns"].to_numpy(dtype=float)

    cv = pd.concat([mlp_cv, cnn_cv], ignore_index=True)
    calibration = pd.concat([mlp_cal, cnn_cal], ignore_index=True)
    cv.to_csv(out_dir / "p03c_cv_scan.csv", index=False)
    calibration.to_csv(out_dir / "p03c_calibration.csv", index=False)

    heldout_runs = list(config["timing"]["heldout_runs"])
    methods_for_bootstrap = [
        ("s02_ridge_cfd20", "s02_ridge_cfd20"),
        ("analytic_timewalk", "analytic_timewalk"),
        ("p03a_mlp_waveform", "p03a_mlp_waveform"),
        ("mlp_analytic_residual", "mlp_analytic_residual"),
        ("cnn_analytic_residual", "cnn_analytic_residual"),
    ]
    pair_frame = event_pair_residual_frame(combined, methods_for_bootstrap, config, heldout_runs)
    pair_frame.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    benchmark = paired_event_bootstrap(pair_frame, "analytic_timewalk", rng, int(config["ml"]["bootstrap_samples"]))
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    p03a_benchmark = benchmark[benchmark["method"].isin(["s02_ridge_cfd20", "analytic_timewalk", "p03a_mlp_waveform"])].copy()
    p03a_benchmark.to_csv(out_dir / "p03a_reproduction_benchmark.csv", index=False)

    leakage = leakage_checks(combined, config, [mlp_info, cnn_info])
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, benchmark, pair_frame, cv)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    analytic_row = benchmark[benchmark["method"] == "analytic_timewalk"].iloc[0]
    p03a_row = benchmark[benchmark["method"] == "p03a_mlp_waveform"].iloc[0]
    mlp_row = benchmark[benchmark["method"] == "mlp_analytic_residual"].iloc[0]
    cnn_row = benchmark[benchmark["method"] == "cnn_analytic_residual"].iloc[0]
    cnn_better_than_mlp = float(cnn_row["ci_high"]) < float(mlp_row["ci_low"])
    cnn_better_than_analytic = float(cnn_row["ci_high"]) < float(analytic_row["ci_low"])
    if cnn_better_than_mlp and cnn_better_than_analytic:
        verdict = "cnn_beats_mlp_and_analytic_baseline_with_nonoverlapping_ci"
    elif float(cnn_row["sigma68_ns"]) < float(mlp_row["sigma68_ns"]):
        verdict = "cnn_point_estimate_beats_mlp_but_ci_overlaps"
    else:
        verdict = "cnn_does_not_add_to_mlp_or_analytic_baseline"

    result = {
        "study": "P03c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "p03a_reproduced_first": {
            "method": "p03a_mlp_waveform",
            "sigma68_ns": float(p03a_row["sigma68_ns"]),
            "ci": [float(p03a_row["ci_low"]), float(p03a_row["ci_high"])],
            "reported_p03a_sigma68_ns": 1.92723,
            "delta_from_reported_ns": float(p03a_row["sigma68_ns"] - 1.92723),
            "hidden": int(p03a_mlp_info["hidden"]),
            "weight_decay": float(p03a_mlp_info["weight_decay"]),
        },
        "split_by_run": True,
        "train_runs": list(config["timing"]["train_runs"]),
        "heldout_runs": heldout_runs,
        "metric": "heldout B4/B6/B8 pairwise sigma68 ns with event-paired bootstrap CI",
        "traditional": {
            "method": "analytic_timewalk_on_template_phase",
            "candidate": best_candidate,
            "alpha": float(best_alpha),
            "value": float(analytic_row["sigma68_ns"]),
            "ci": [float(analytic_row["ci_low"]), float(analytic_row["ci_high"])],
            "full_rms_ns": float(analytic_row["full_rms_ns"]),
        },
        "ml": {
            "mlp": {
                "method": "p03a_mlp_architecture_on_analytic_residual",
                "size": int(mlp_info["size"]),
                "weight_decay": float(mlp_info["weight_decay"]),
                "value": float(mlp_row["sigma68_ns"]),
                "ci": [float(mlp_row["ci_low"]), float(mlp_row["ci_high"])],
                "delta_vs_analytic_ns": float(mlp_row["delta_vs_analytic_ns"]),
            },
            "cnn": {
                "method": "tiny_1d_cnn_on_analytic_residual",
                "channels": int(cnn_info["size"]),
                "weight_decay": float(cnn_info["weight_decay"]),
                "value": float(cnn_row["sigma68_ns"]),
                "ci": [float(cnn_row["ci_low"]), float(cnn_row["ci_high"])],
                "delta_vs_analytic_ns": float(cnn_row["delta_vs_analytic_ns"]),
            },
        },
        "leakage": {
            "event_id_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].iloc[0]),
            "feature_audit": str(leakage[leakage["check"] == "feature_audit"]["detail"].iloc[0]),
            "shuffled_controls": leakage[leakage["check"] == "shuffled_target_negative_control_sigma68_ns"][
                ["model", "value"]
            ].to_dict(orient="records"),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "P03d: leave-one-heldout-run repetition of analytic-residual CNN versus MLP across all sample-II runs",
            "P03e: waveform-only residual models with stave-blind versus stave-aware feature ablation after analytic timewalk correction",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, p03a_benchmark, p03a_mlp_info, benchmark, cv, calibration, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03c",
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
                "p03a_mlp_reproduction": float(p03a_row["sigma68_ns"]),
                "analytic": float(analytic_row["sigma68_ns"]),
                "mlp_analytic_residual": float(mlp_row["sigma68_ns"]),
                "cnn_analytic_residual": float(cnn_row["sigma68_ns"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
