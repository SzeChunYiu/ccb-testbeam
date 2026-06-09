#!/usr/bin/env python3
"""P03e stave-blind versus stave-aware analytic-residual waveform ablation."""

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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03e")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

import p03c_cnn_vs_mlp_analytic_residual as p03c
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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def waveform_block(pulses: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    return norm.astype(np.float32), [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])]


def shape_block(pulses: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    wf, _ = waveform_block(pulses)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    safe_amp = np.maximum(amp, 1.0)
    rise_50_10 = pulses["t_cfd50_ns"].to_numpy(dtype=np.float32) - pulses["t_cfd10_ns"].to_numpy(dtype=np.float32)
    rise_40_20 = pulses["t_cfd40_ns"].to_numpy(dtype=np.float32) - pulses["t_cfd20_ns"].to_numpy(dtype=np.float32)
    cols = [
        np.log1p(safe_amp),
        1000.0 / safe_amp,
        np.sqrt(1000.0 / safe_amp),
        pulses["peak_sample"].to_numpy(dtype=np.float32),
        pulses["area_adc_samples"].to_numpy(dtype=np.float32) / safe_amp,
        rise_50_10,
        rise_40_20,
        np.max(np.gradient(wf, axis=1), axis=1),
        wf[:, :6].sum(axis=1),
        wf[:, 9:].sum(axis=1),
        wf.max(axis=1),
    ]
    names = [
        "log_amp",
        "inv_amp_1000",
        "inv_sqrt_amp_1000",
        "peak_sample",
        "area_over_amp",
        "cfd50_minus_cfd10_ns",
        "cfd40_minus_cfd20_ns",
        "max_norm_slope",
        "early_norm_charge",
        "late_norm_charge",
        "norm_peak_height",
    ]
    return np.column_stack(cols).astype(np.float32), names


def stave_block(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    return one_hot, [f"stave_{stave}" for stave in staves]


def feature_matrix(pulses: pd.DataFrame, variant: str, staves: Sequence[str]) -> Tuple[np.ndarray, List[str], str]:
    wf, wf_names = waveform_block(pulses)
    pieces = [wf]
    names = wf_names[:]
    policy = "no run, event id, event order, stave id, other-stave time, or held-out target"
    if variant in {"waveform_stave_onehot", "waveform_amp_shape_stave"}:
        stv, stv_names = stave_block(pulses, staves)
        pieces.append(stv)
        names.extend(stv_names)
        policy = "same as blind variants, except explicit downstream stave one-hot is intentionally included"
    if variant in {"waveform_amp_shape", "waveform_amp_shape_stave"}:
        shp, shp_names = shape_block(pulses)
        pieces.append(shp)
        names.extend(shp_names)
    return np.hstack(pieces).astype(np.float32), names, policy


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def standardize_by_train(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    train_mask = np.zeros(len(X), dtype=bool)
    train_mask[train_idx] = True
    scaler = StandardScaler()
    Xs = X.copy()
    Xs[train_mask] = scaler.fit_transform(X[train_mask])
    if (~train_mask).any():
        Xs[~train_mask] = scaler.transform(X[~train_mask])
    return Xs.astype(np.float32), scaler


def train_mlp(
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    hidden: int,
    weight_decay: float,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[p03c.MLPResidual, np.ndarray, StandardScaler]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    Xs, scaler = standardize_by_train(X, train_idx)
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)
    model = p03c.MLPResidual(X.shape[1], int(hidden))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["learning_rate"]), weight_decay=float(weight_decay))
    xb_all = torch.from_numpy(Xs[train_idx])
    yb_all = torch.from_numpy(y_train)
    min_var = float(config["ml"]["min_sigma_ns"]) ** 2
    batch_size = int(config["ml"]["batch_size"])
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


def predict_mlp(model: p03c.MLPResidual, Xs: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    with torch.no_grad():
        mu, log_var = model(torch.from_numpy(Xs.astype(np.float32)))
        sigma = torch.sqrt(torch.exp(log_var) + float(config["ml"]["min_sigma_ns"]) ** 2)
    return mu.numpy().astype(float), sigma.numpy().astype(float)


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def evaluate_corrected(pulses: pd.DataFrame, method_name: str, values: np.ndarray, config: dict, runs: Iterable[int]) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, list(runs))


def run_variant_model(pulses: pd.DataFrame, config: dict, variant: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    base_method = str(config["ml"]["base_method"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    seed = int(config["ml"]["random_seed"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, feature_names, policy = feature_matrix(pulses, variant, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
    idx_train_all = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    gkf = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    cv_rows = []
    best = {"score": np.inf, "hidden": None, "weight_decay": None}
    for hidden in config["ml"]["hidden_sizes"]:
        for weight_decay in config["ml"]["weight_decays"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
                tr_idx = idx_train_all[tr]
                va_idx = idx_train_all[va]
                model, Xs, _ = train_mlp(
                    X, targets, tr_idx, int(hidden), float(weight_decay), config, seed + 1009 * fold + 17 * int(hidden)
                )
                pred, sigma = predict_mlp(model, Xs, config)
                vals = evaluate_corrected(
                    pulses.iloc[va_idx].copy(),
                    f"{variant}_cv",
                    corrected_values(pulses, base_method, pred)[va_idx],
                    config,
                    sorted(np.unique(runs[va_idx]).tolist()),
                )
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "variant": variant,
                        "hidden": int(hidden),
                        "weight_decay": float(weight_decay),
                        "fold": int(fold),
                        "sigma68_ns": float(score),
                        "n_pair_residuals": int(len(vals)),
                        "pred_sigma_median_ns": float(np.nanmedian(sigma[va_idx])),
                        "n_features": int(X.shape[1]),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "variant": variant,
                    "hidden": int(hidden),
                    "weight_decay": float(weight_decay),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "pred_sigma_median_ns": float("nan"),
                    "n_features": int(X.shape[1]),
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "hidden": int(hidden), "weight_decay": float(weight_decay)}

    model, Xs, scaler = train_mlp(
        X,
        targets,
        idx_train_all,
        int(best["hidden"]),
        float(best["weight_decay"]),
        config,
        seed + 307 + len(feature_names),
    )
    pred, sigma = predict_mlp(model, Xs, config)
    method = f"p03e_{variant}"
    out = pulses.copy()
    out[f"{method}_target_residual_ns"] = targets
    out[f"{method}_pred_residual_ns"] = pred
    out[f"{method}_pred_sigma_ns"] = sigma
    out[f"t_{method}_ns"] = corrected_values(pulses, base_method, pred)

    held = out[out["run"].isin(heldout_runs)].copy()
    held = held[np.isfinite(held[f"{method}_target_residual_ns"]) & np.isfinite(held[f"{method}_pred_sigma_ns"])]
    err = held[f"{method}_target_residual_ns"] - held[f"{method}_pred_residual_ns"]
    pull = err / held[f"{method}_pred_sigma_ns"]
    calibration = pd.DataFrame(
        [
            {
                "variant": variant,
                "scope": "heldout_pulse_target",
                "n": int(len(held)),
                "pred_sigma_median_ns": float(held[f"{method}_pred_sigma_ns"].median()),
                "abs_error_median_ns": float(err.abs().median()),
                "pull_width_sigma68": float(s02.sigma68(pull.to_numpy(dtype=float))),
                "pull_rms": float(s02.full_rms(pull.to_numpy(dtype=float))),
            }
        ]
    )
    info = {
        "variant": variant,
        "method": method,
        "base_method": base_method,
        "hidden": int(best["hidden"]),
        "weight_decay": float(best["weight_decay"]),
        "cv_sigma68_ns": float(best["score"]),
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "feature_policy": policy,
        "scaler_mean_sha256": hashlib.sha256(scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
    }
    return out, pd.DataFrame(cv_rows), calibration, info


def add_stave_offset_guardrail(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    base_method = str(config["ml"]["base_method"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    tmp = pulses.copy()
    tmp["target"] = targets
    train = tmp[tmp["run"].isin(train_runs) & np.isfinite(tmp["target"])].copy()
    means = train.groupby("stave")["target"].mean().to_dict()
    pred = tmp["stave"].map(means).astype(float).to_numpy()
    out = pulses.copy()
    out["t_p03e_stave_offset_only_ns"] = out[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    rows = [{"stave": stave, "train_mean_target_residual_ns": float(value)} for stave, value in sorted(means.items())]
    rows.append({"stave": "ALL", "train_mean_target_residual_ns": float(np.nanmean(targets[np.isin(runs, train_runs)]))})
    return out, pd.DataFrame(rows)


def leakage_checks(pulses: pd.DataFrame, config: dict, infos: Sequence[dict], benchmark: pd.DataFrame) -> pd.DataFrame:
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    rows = [
        {
            "check": "train_heldout_event_id_overlap",
            "variant": "all",
            "value": float(len(train_event_ids & heldout_event_ids)),
            "detail": "must be zero",
        },
        {
            "check": "detector_label_only_guardrail_sigma68_ns",
            "variant": "stave_offset_only",
            "value": float(benchmark[benchmark["method"] == "p03e_stave_offset_only"]["sigma68_ns"].iloc[0]),
            "detail": "train-run mean analytic residual per stave, applied to held-out run with no waveform samples",
        },
        {
            "check": "split_policy",
            "variant": "all",
            "value": 1.0,
            "detail": "all CV, tuning, and final scoring are grouped or split by run; held-out run is 65",
        },
    ]
    base_method = str(config["ml"]["base_method"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    analytic_value = float(benchmark[benchmark["method"] == "analytic_timewalk"]["sigma68_ns"].iloc[0])
    for i, info in enumerate(infos):
        variant = str(info["variant"])
        rows.append(
            {
                "check": "feature_audit",
                "variant": variant,
                "value": float(info["n_features"]),
                "detail": str(info["feature_policy"]),
            }
        )
        delta = float(benchmark[benchmark["method"] == info["method"]]["sigma68_ns"].iloc[0]) - analytic_value
        rows.append(
            {
                "check": "too_good_trigger_delta_vs_analytic_ns",
                "variant": variant,
                "value": delta,
                "detail": "negative values improve on analytic; shuffled-target control is required for every variant",
            }
        )
        X, _, _ = feature_matrix(pulses, variant, list(config["timing"]["downstream_staves"]))
        train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
        model, Xs, _ = train_mlp(
            X,
            targets,
            np.flatnonzero(train_mask),
            int(info["hidden"]),
            float(info["weight_decay"]),
            config,
            int(config["ml"]["random_seed"]) + 701 + i,
            shuffle_y=True,
        )
        pred, _ = predict_mlp(model, Xs, config)
        vals = evaluate_corrected(pulses, f"{variant}_shuffled", corrected_values(pulses, base_method, pred), config, heldout_runs)
        rows.append(
            {
                "check": "shuffled_target_negative_control_sigma68_ns",
                "variant": variant,
                "value": float(s02.sigma68(vals)),
                "detail": "same selected architecture trained with train residual targets shuffled within the run-split training pool",
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, benchmark: pd.DataFrame, cv: pd.DataFrame) -> None:
    ordered = benchmark.sort_values("sigma68_ns")
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
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
    ax.set_title("P03e held-out feature ablation")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head.png", dpi=130)
    plt.close(fig)

    best_cv = cv[cv["fold"] == -1].copy()
    if len(best_cv):
        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        labels = best_cv["variant"] + " h=" + best_cv["hidden"].astype(str) + " wd=" + best_cv["weight_decay"].astype(str)
        order = np.argsort(best_cv["sigma68_ns"].to_numpy())
        ax.bar(np.arange(len(best_cv)), best_cv.iloc[order]["sigma68_ns"])
        ax.set_xticks(np.arange(len(best_cv)))
        ax.set_xticklabels(labels.iloc[order], rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("grouped-run CV sigma68 (ns)")
        ax.set_title("P03e grouped-run CV")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_cv_scan.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    p03c_repro: pd.DataFrame,
    benchmark: pd.DataFrame,
    cv: pd.DataFrame,
    calibration: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    best_cv = cv[cv["fold"] == -1].sort_values(["variant", "sigma68_ns"])
    lines = [
        "# Study report: P03e - stave-blind versus stave-aware waveform residual ablation",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train runs 58-63; held-out run 65; grouped-run CV inside training",
        f"- **Config:** `{config_path}`",
        "",
        "## Question",
        "",
        "After the P03c analytic timewalk correction, does explicit detector identity or scalar amplitude/shape information improve a waveform residual MLP, or does it mainly expose run/detector-label leakage risk?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count gate was rerun from raw ROOT before the ablation.",
        "",
        repro.to_markdown(index=False),
        "",
        "The P03c strict waveform residual number was then rebuilt before new variants were scored.",
        "",
        p03c_repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional baseline: S03a analytic amplitude-timewalk correction on S02 template phase, trained only on runs 58-63.",
        "",
        "ML variants: heteroskedastic MLPs trained on analytic residual targets. The strict variant uses only 18 normalized waveform samples; the other variants append stave one-hot, amplitude/shape scalars, or both. Hyperparameters are selected by grouped-run CV.",
        "",
        best_cv[["variant", "hidden", "weight_decay", "sigma68_ns", "n_features"]].to_markdown(index=False),
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
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. Best held-out ML variant is `{result['ml']['best_variant']}` at `{result['ml']['best_sigma68_ns']:.3f} ns`; analytic baseline is `{result['traditional']['value']:.3f} ns`.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/p03e_stave_blind_residual_ablation.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `p03c_reproduction_benchmark.csv`, `p03e_cv_scan.csv`, `p03e_calibration.csv`, `head_to_head_benchmark.csv`, `heldout_pair_residuals.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03e_1781014997_939_20a36ed3.yaml")
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

    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(pulses, config, best_method)
    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    analytic_coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    combined = analytic_pulses.copy()

    strict_pulses, strict_cv, strict_cal, strict_info = p03c.run_waveform_model(
        combined,
        config,
        "mlp_analytic_residual",
        config["ml"]["hidden_sizes"],
        str(config["ml"]["base_method"]),
    )
    combined["t_p03e_waveform_only_ns"] = strict_pulses["t_mlp_analytic_residual_ns"].to_numpy(dtype=float)
    strict_info = {
        "variant": "waveform_only",
        "method": "p03e_waveform_only",
        "base_method": strict_info["base_method"],
        "hidden": int(strict_info["size"]),
        "weight_decay": float(strict_info["weight_decay"]),
        "cv_sigma68_ns": float(strict_info["cv_sigma68_ns"]),
        "n_features": int(strict_info["n_features"]),
        "feature_names": list(strict_info["feature_names"]),
        "feature_policy": "18 normalized same-pulse waveform samples only; no run, event id, event order, stave id, amplitude scalar, other-stave time, or held-out target",
    }
    strict_cv = strict_cv.rename(columns={"model": "variant", "size": "hidden"})
    strict_cv["variant"] = "waveform_only"
    strict_cv["n_features"] = int(strict_info["n_features"])
    strict_cal = strict_cal.rename(columns={"model": "variant"})
    strict_cal["variant"] = "waveform_only"

    infos = [strict_info]
    cv_frames = [strict_cv]
    cal_frames = [strict_cal]
    for variant in ["waveform_stave_onehot", "waveform_amp_shape", "waveform_amp_shape_stave"]:
        variant_pulses, variant_cv, variant_cal, variant_info = run_variant_model(combined, config, variant)
        combined[f"t_{variant_info['method']}_ns"] = variant_pulses[f"t_{variant_info['method']}_ns"].to_numpy(dtype=float)
        infos.append(variant_info)
        cv_frames.append(variant_cv)
        cal_frames.append(variant_cal)

    guard_pulses, guardrail = add_stave_offset_guardrail(combined, config)
    combined["t_p03e_stave_offset_only_ns"] = guard_pulses["t_p03e_stave_offset_only_ns"].to_numpy(dtype=float)
    guardrail.to_csv(out_dir / "stave_offset_guardrail.csv", index=False)

    cv = pd.concat(cv_frames, ignore_index=True)
    calibration = pd.concat(cal_frames, ignore_index=True)
    cv.to_csv(out_dir / "p03e_cv_scan.csv", index=False)
    calibration.to_csv(out_dir / "p03e_calibration.csv", index=False)

    heldout_runs = list(config["timing"]["heldout_runs"])
    methods_for_bootstrap = [
        ("analytic_timewalk", "analytic_timewalk"),
        ("p03e_stave_offset_only", "p03e_stave_offset_only"),
    ] + [(info["method"], info["method"]) for info in infos]
    pair_frame = p03c.event_pair_residual_frame(combined, methods_for_bootstrap, config, heldout_runs)
    pair_frame.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    benchmark = p03c.paired_event_bootstrap(pair_frame, "analytic_timewalk", rng, int(config["ml"]["bootstrap_samples"]))
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)

    strict_row = benchmark[benchmark["method"] == "p03e_waveform_only"].iloc[0]
    p03c_repro = pd.DataFrame(
        [
            {
                "quantity": "P03c strict waveform residual sigma68_ns",
                "report_value": float(config["p03c_reported_strict_sigma68_ns"]),
                "reproduced": float(strict_row["sigma68_ns"]),
                "delta": float(strict_row["sigma68_ns"] - float(config["p03c_reported_strict_sigma68_ns"])),
                "tolerance": 1.0e-6,
                "pass": abs(float(strict_row["sigma68_ns"]) - float(config["p03c_reported_strict_sigma68_ns"])) < 1.0e-6,
            }
        ]
    )
    p03c_repro.to_csv(out_dir / "p03c_reproduction_benchmark.csv", index=False)
    if not bool(p03c_repro["pass"].all()):
        raise RuntimeError("P03c strict waveform reproduction failed")

    leakage = leakage_checks(combined, config, infos, benchmark)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, benchmark, cv)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    analytic_row = benchmark[benchmark["method"] == "analytic_timewalk"].iloc[0]
    ml_rows = benchmark[benchmark["method"].str.startswith("p03e_")].copy().sort_values("sigma68_ns")
    best_ml = ml_rows.iloc[0]
    variant_results = {}
    for info in infos:
        row = benchmark[benchmark["method"] == info["method"]].iloc[0]
        variant_results[info["variant"]] = {
            "method": info["method"],
            "hidden": int(info["hidden"]),
            "weight_decay": float(info["weight_decay"]),
            "n_features": int(info["n_features"]),
            "sigma68_ns": float(row["sigma68_ns"]),
            "ci": [float(row["ci_low"]), float(row["ci_high"])],
            "delta_vs_analytic_ns": float(row["delta_vs_analytic_ns"]),
        }
    stave_gain = variant_results["waveform_stave_onehot"]["sigma68_ns"] - variant_results["waveform_only"]["sigma68_ns"]
    scalar_gain = variant_results["waveform_amp_shape"]["sigma68_ns"] - variant_results["waveform_only"]["sigma68_ns"]
    best_delta = float(best_ml["sigma68_ns"] - analytic_row["sigma68_ns"])
    guardrail_row = benchmark[benchmark["method"] == "p03e_stave_offset_only"].iloc[0]
    guardrail_gap = float(best_ml["sigma68_ns"] - guardrail_row["sigma68_ns"])
    if best_delta < float(config["ml"]["leakage_delta_trigger_ns"]) and abs(guardrail_gap) < 0.10:
        verdict = "large_stave_aware_gain_is_explained_by_detector_label_offset_guardrail"
    elif best_delta < float(config["ml"]["leakage_delta_trigger_ns"]):
        verdict = "large_ml_gain_requires_followup_even_after_negative_controls"
    elif stave_gain < -0.05:
        verdict = "stave_identity_has_small_point_gain_but_ci_and_controls_limit_claim"
    elif scalar_gain < -0.05:
        verdict = "scalar_shape_features_have_small_point_gain_but_ci_and_controls_limit_claim"
    else:
        verdict = "stave_and_scalar_features_do_not_materially_improve_strict_waveform_residual_mlp"

    result = {
        "study": "P03e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all() and p03c_repro["pass"].all()),
        "p03c_reproduced_first": {
            "method": "p03e_waveform_only",
            "sigma68_ns": float(strict_row["sigma68_ns"]),
            "reported_p03c_sigma68_ns": float(config["p03c_reported_strict_sigma68_ns"]),
            "delta_from_reported_ns": float(strict_row["sigma68_ns"] - float(config["p03c_reported_strict_sigma68_ns"])),
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
            "best_variant": str(best_ml["method"]).replace("p03e_", ""),
            "best_sigma68_ns": float(best_ml["sigma68_ns"]),
            "best_ci": [float(best_ml["ci_low"]), float(best_ml["ci_high"])],
            "variants": variant_results,
            "stave_onehot_delta_vs_waveform_only_ns": float(stave_gain),
            "amp_shape_delta_vs_waveform_only_ns": float(scalar_gain),
        },
        "leakage": {
            "event_id_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].iloc[0]),
            "detector_label_only_guardrail_sigma68_ns": float(guardrail_row["sigma68_ns"]),
            "best_ml_minus_guardrail_ns": float(guardrail_gap),
            "feature_audits": leakage[leakage["check"] == "feature_audit"][["variant", "value", "detail"]].to_dict(orient="records"),
            "shuffled_controls": leakage[leakage["check"] == "shuffled_target_negative_control_sigma68_ns"][
                ["variant", "value"]
            ].to_dict(orient="records"),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "P03f: leave-one-heldout-run repetition of P03e feature ablations across each sample-II analysis run",
            "P03g: detector-label permutation stress test for stave-aware residual timing models",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, p03c_repro, benchmark, cv, calibration, leakage, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03e",
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
                "p03c_strict_reproduction": float(strict_row["sigma68_ns"]),
                "analytic": float(analytic_row["sigma68_ns"]),
                "best_ml": str(best_ml["method"]),
                "best_ml_sigma68_ns": float(best_ml["sigma68_ns"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
