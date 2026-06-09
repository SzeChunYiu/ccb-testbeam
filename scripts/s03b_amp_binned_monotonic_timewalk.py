#!/usr/bin/env python3
"""S03b amplitude-binned monotonic timewalk closure from raw ROOT waveforms."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
import yaml
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a


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


def finite_design(amp_log: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(amp_log) & np.isfinite(y) & np.isfinite(runs)


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


def bootstrap_method_rows(
    pulses: pd.DataFrame, config: dict, methods: List[Tuple[str, str]], rng: np.random.Generator
) -> pd.DataFrame:
    rows = []
    heldout_runs = list(config["timing"]["heldout_runs"])
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, 2.0, config, heldout_runs)
        ci = s02.bootstrap_ci(vals, rng, int(config["binned"]["bootstrap_samples"]))
        rows.append(
            {
                "method": label,
                "metric": "heldout pairwise sigma68 ns",
                "value": s02.sigma68(vals),
                "ci_low": ci[0],
                "ci_high": ci[1],
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def _bin_centers_values(
    x: np.ndarray, y: np.ndarray, n_bins: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if len(x) == 0:
        return np.asarray([0.0]), np.asarray([0.0]), np.asarray([0.0])
    edges = np.unique(np.quantile(x, np.linspace(0.0, 1.0, int(n_bins) + 1)))
    if len(edges) < 3:
        return np.asarray([float(np.median(x))]), np.asarray([float(np.median(y))]), np.asarray([float(len(y))])
    labels = np.digitize(x, edges[1:-1], right=True)
    centers, values, counts = [], [], []
    for label in range(len(edges) - 1):
        in_bin = labels == label
        if not np.any(in_bin):
            continue
        centers.append(float(np.median(x[in_bin])))
        values.append(float(np.median(y[in_bin])))
        counts.append(float(np.sum(in_bin)))
    if len(centers) == 0:
        return np.asarray([float(np.median(x))]), np.asarray([float(np.median(y))]), np.asarray([float(len(y))])
    order = np.argsort(centers)
    return np.asarray(centers)[order], np.asarray(values)[order], np.asarray(counts)[order]


def fit_binned_model(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    n_bins: int,
    mode: str,
    direction: str,
) -> Dict[str, dict]:
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    staves = list(config["timing"]["downstream_staves"])
    stave_arr = pulses["stave"].to_numpy()
    models: Dict[str, dict] = {}
    for stave in staves:
        mask = train_mask & (stave_arr == stave)
        centers, values, counts = _bin_centers_values(amp_log[mask], targets[mask], int(n_bins))
        if mode == "monotonic" and len(centers) >= 2:
            iso = IsotonicRegression(increasing=(direction == "increasing"), out_of_bounds="clip")
            iso.fit(centers, values, sample_weight=counts)
            fitted = iso.predict(centers)
            models[stave] = {
                "mode": mode,
                "direction": direction,
                "centers": centers,
                "values": values,
                "counts": counts,
                "fitted_values": fitted,
                "iso": iso,
            }
        else:
            models[stave] = {
                "mode": mode,
                "direction": "none",
                "centers": centers,
                "values": values,
                "counts": counts,
                "fitted_values": values,
                "iso": None,
            }
    return models


def predict_binned_model(pulses: pd.DataFrame, models: Dict[str, dict]) -> np.ndarray:
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    stave_arr = pulses["stave"].to_numpy()
    pred = np.full(len(pulses), np.nan, dtype=float)
    for stave, model in models.items():
        idx = np.flatnonzero(stave_arr == stave)
        if len(idx) == 0:
            continue
        centers = np.asarray(model["centers"], dtype=float)
        values = np.asarray(model["fitted_values"], dtype=float)
        if len(centers) == 1:
            pred[idx] = values[0]
        elif model["iso"] is not None:
            pred[idx] = model["iso"].predict(amp_log[idx])
        else:
            pred[idx] = np.interp(amp_log[idx], centers, values, left=values[0], right=values[-1])
    return pred


def binned_model_table(models: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for stave, model in models.items():
        for center, raw, fitted, count in zip(
            model["centers"], model["values"], model["fitted_values"], model["counts"]
        ):
            rows.append(
                {
                    "stave": stave,
                    "mode": model["mode"],
                    "direction": model["direction"],
                    "log_amp_center": float(center),
                    "raw_bin_target_median_ns": float(raw),
                    "fitted_target_ns": float(fitted),
                    "n_train_pulses": int(count),
                }
            )
    return pd.DataFrame(rows)


def scan_binned_candidates(
    pulses: pd.DataFrame, config: dict, base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, dict], dict]:
    spacing_cm = 2.0
    targets = s02.event_residual_targets(pulses, base_method, spacing_cm, config)
    runs = pulses["run"].to_numpy(dtype=float)
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    train_runs = list(config["timing"]["train_runs"])
    train_mask = np.isin(runs, train_runs) & finite_design(amp_log, targets, runs)
    groups = runs[train_mask].astype(int)
    n_splits = min(int(config["binned"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    idx_train = np.flatnonzero(train_mask)
    cv_rows = []
    best = {"score": math.inf, "mode": None, "direction": None, "n_bins": None}

    for mode in config["binned"]["modes"]:
        directions = ["none"] if mode == "unconstrained" else list(config["binned"]["monotonic_directions"])
        for n_bins in config["binned"]["n_bins"]:
            for direction in directions:
                fold_scores = []
                for fold, (tr, va) in enumerate(gkf.split(idx_train, targets[train_mask], groups=groups)):
                    fold_train_mask = np.zeros(len(pulses), dtype=bool)
                    fold_train_mask[idx_train[tr]] = True
                    models = fit_binned_model(pulses, targets, fold_train_mask, config, int(n_bins), mode, direction)
                    pred = predict_binned_model(pulses, models)
                    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
                    va_idx = idx_train[va]
                    va_runs = sorted(np.unique(runs[va_idx]).astype(int).tolist())
                    vals = evaluate_corrected(
                        pulses.iloc[va_idx].copy(), "binned_cv", corrected[va_idx], config, va_runs, spacing_cm
                    )
                    score = s02.sigma68(vals)
                    fold_scores.append(score)
                    cv_rows.append(
                        {
                            "mode": mode,
                            "direction": direction,
                            "n_bins": int(n_bins),
                            "fold": int(fold),
                            "sigma68_ns": score,
                            "n_pair_residuals": int(len(vals)),
                        }
                    )
                mean_score = float(np.nanmean(fold_scores))
                cv_rows.append(
                    {
                        "mode": mode,
                        "direction": direction,
                        "n_bins": int(n_bins),
                        "fold": -1,
                        "sigma68_ns": mean_score,
                        "n_pair_residuals": 0,
                    }
                )
                if mean_score < best["score"]:
                    best = {"score": mean_score, "mode": mode, "direction": direction, "n_bins": int(n_bins)}

    models = fit_binned_model(
        pulses, targets, train_mask, config, int(best["n_bins"]), str(best["mode"]), str(best["direction"])
    )
    pred = predict_binned_model(pulses, models)
    out = pulses.copy()
    out["binned_target_residual_ns"] = targets
    out["binned_pred_residual_ns"] = pred
    out["t_binned_timewalk_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(cv_rows), models, best


def run_shuffled_binned_control(
    pulses: pd.DataFrame, config: dict, base_method: str, best: dict
) -> float:
    rng = np.random.default_rng(int(config["binned"]["random_seed"]) + 31)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=float)
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & finite_design(amp_log, targets, runs)
    shuffled = targets.copy()
    train_vals = shuffled[train_mask].copy()
    rng.shuffle(train_vals)
    shuffled[train_mask] = train_vals
    models = fit_binned_model(
        pulses, shuffled, train_mask, config, int(best["n_bins"]), str(best["mode"]), str(best["direction"])
    )
    pred = predict_binned_model(pulses, models)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    vals = evaluate_corrected(pulses, "binned_shuffled", corrected, config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def run_shuffled_ml_control(
    pulses: pd.DataFrame, config: dict, base_method: str, ml_cv: pd.DataFrame
) -> float:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 43)
    staves = list(config["timing"]["downstream_staves"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=float)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & np.isfinite(targets)
    shuffled_target = targets[train_mask].copy()
    rng.shuffle(shuffled_target)
    best_alpha = float(ml_cv[ml_cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["alpha"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_mask], shuffled_target)
    pred = model.predict(X)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    vals = evaluate_corrected(pulses, "ml_shuffled", corrected, config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def run_heldout_by_run(pulses: pd.DataFrame, config: dict, methods: List[Tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for run in config["timing"]["heldout_runs"]:
        for method, label in methods:
            vals = s02.pairwise_residuals(pulses, method, 2.0, config, [int(run)])
            rows.append({"run": int(run), "method": label, **s02.metric_summary(vals)})
    return pd.DataFrame(rows)


def calibration_table(pulses: pd.DataFrame, pred_col: str, target_col: str, heldout_runs: List[int], prefix: str) -> pd.DataFrame:
    held = pulses[pulses["run"].isin(heldout_runs)].copy()
    held = held[np.isfinite(held[pred_col]) & np.isfinite(held[target_col])]
    if len(held) < 8:
        return pd.DataFrame()
    qs = np.unique(np.quantile(held[pred_col], np.linspace(0, 1, 8)))
    if len(qs) < 3:
        return pd.DataFrame()
    held["bin"] = pd.cut(held[pred_col], qs, include_lowest=True, duplicates="drop")
    rows = []
    for _, group in held.groupby("bin"):
        rows.append(
            {
                "method": prefix,
                "n": int(len(group)),
                "pred_mean_ns": float(group[pred_col].mean()),
                "target_mean_ns": float(group[target_col].mean()),
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, benchmark: pd.DataFrame, cv: pd.DataFrame, calibration: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ordered = benchmark.sort_values("value")
    xpos = np.arange(len(ordered))
    ax.bar(xpos, ordered["value"])
    ax.errorbar(
        xpos,
        ordered["value"],
        yerr=[ordered["value"] - ordered["ci_low"], ordered["ci_high"] - ordered["value"]],
        fmt="none",
        ecolor="black",
        capsize=3,
        linewidth=1,
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(ordered["method"], rotation=30, ha="right")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S03b run-held-out correction benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03b_head_to_head.png", dpi=130)
    plt.close(fig)

    means = cv[cv["fold"] == -1].copy()
    means["candidate"] = means["mode"] + "/" + means["direction"] + "/" + means["n_bins"].astype(str)
    means = means.sort_values("sigma68_ns").head(12)
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.bar(np.arange(len(means)), means["sigma68_ns"])
    ax.set_xticks(np.arange(len(means)))
    ax.set_xticklabels(means["candidate"], rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("train grouped-CV sigma68 (ns)")
    ax.set_title("Amplitude-binned candidate scan")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03b_cv_scan.png", dpi=130)
    plt.close(fig)

    if len(calibration):
        fig, ax = plt.subplots(figsize=(5.8, 4.2))
        for method, group in calibration.groupby("method"):
            ax.plot(group["pred_mean_ns"], group["target_mean_ns"], "o-", label=method)
        lim = np.nanmax(np.abs(np.r_[calibration["pred_mean_ns"], calibration["target_mean_ns"]]))
        ax.plot([-lim, lim], [-lim, lim], "k--", lw=1)
        ax.set_xlabel("mean predicted residual (ns)")
        ax.set_ylabel("mean observed residual (ns)")
        ax.set_title("Held-out residual calibration")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig_s03b_calibration.png", dpi=130)
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
    s03a_repro: pd.DataFrame,
    benchmark: pd.DataFrame,
    cv: pd.DataFrame,
    model_table: pd.DataFrame,
    heldout_by_run: pd.DataFrame,
    leakage: pd.DataFrame,
    best: dict,
    result: dict,
) -> None:
    base = benchmark[benchmark["method"] == "s02_template_phase_base"].iloc[0]
    s03a_amp = benchmark[benchmark["method"] == "s03a_amp_only_reference"].iloc[0]
    binned = benchmark[benchmark["method"] == "s03b_binned_timewalk"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_ridge_on_template_phase"].iloc[0]
    cv_best = cv[cv["fold"] == -1].sort_values("sigma68_ns").head(8)
    model_preview = model_table.groupby(["stave", "mode", "direction"], as_index=False).agg(
        n_bins=("log_amp_center", "count"),
        min_fit_ns=("fitted_target_ns", "min"),
        max_fit_ns=("fitted_target_ns", "max"),
    )
    lines = [
        "# Study report: S03b - Amplitude-binned monotonic timewalk",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train runs 58-63; held-out run 65",
        "- **Config:** `configs/s03b_amp_binned_monotonic_timewalk.yaml`",
        "",
        "## 0. Question",
        "",
        "Does an amplitude-binned or monotonic per-stave analytic timewalk closure improve on the S03a amp-only model without increasing leakage risk?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse counts were rerun from raw ROOT before any S03b modeling.",
        "",
        repro.to_markdown(index=False),
        "",
        "The S03a held-out numbers were then rebuilt in this run from the same raw-derived pulse table.",
        "",
        s03a_repro.to_markdown(index=False),
        "",
        "## 2. Traditional constrained scan",
        "",
        "The S03b traditional candidates fit per-stave median residual-vs-amplitude bins on train runs only. The monotonic variants pass those bin medians through isotonic regression, separately for each stave.",
        "",
        cv_best[["mode", "direction", "n_bins", "sigma68_ns"]].to_markdown(index=False),
        "",
        f"Selected by grouped CV on train runs: mode `{best['mode']}`, direction `{best['direction']}`, bins `{best['n_bins']}`.",
        "",
        model_preview.to_markdown(index=False),
        "",
        "## 3. Held-out head-to-head",
        "",
        benchmark[["method", "value", "ci_low", "ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        heldout_by_run[["run", "method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "Feature audit: the traditional model uses only same-pulse amplitude and stave identity; the ML comparator uses same-pulse waveform/amplitude/shape plus stave identity. No run number, event id, event order, other-stave timing, or held-out labels are model inputs. Bin centers and isotonic fits are learned only from train runs inside each CV fold and from train runs for the final held-out evaluation.",
        "",
        "## 5. Verdict",
        "",
        f"S03a amp-only changes held-out sigma68 from `{base['value']:.3f} ns` to `{s03a_amp['value']:.3f} ns`. The selected S03b binned model gives `{binned['value']:.3f} ns`, a delta of `{s03a_amp['value'] - binned['value']:.3f} ns` versus S03a amp-only. The ML comparator gives `{ml['value']:.3f} ns`.",
        "",
        f"Conclusion: {result['verdict']}.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s03b_amp_binned_monotonic_timewalk.py --config configs/s03b_amp_binned_monotonic_timewalk.yaml",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `binned_cv_scan.csv`, `binned_model_table.csv`, `head_to_head_benchmark.csv`, `heldout_by_run.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03b_amp_binned_monotonic_timewalk.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["binned"]["random_seed"]))

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
        raise RuntimeError(f"Expected base method {config['timing']['base_method']}, got {best_method}")

    s03a_pulses, s03a_cv, s03a_coef, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, best_method)
    s03a_cv.to_csv(out_dir / "s03a_analytic_cv_scan.csv", index=False)
    s03a_coef.to_csv(out_dir / "s03a_analytic_coefficients.csv", index=False)

    binned_pulses, binned_cv, binned_models, binned_best = scan_binned_candidates(pulses, config, best_method)
    binned_cv.to_csv(out_dir / "binned_cv_scan.csv", index=False)
    binned_table = binned_model_table(binned_models)
    binned_table.to_csv(out_dir / "binned_model_table.csv", index=False)

    ml_template_pulses, ml_template_cv, ml_template_cal = s02.run_ml(pulses, config, best_method, 2.0)
    ml_template_cv.to_csv(out_dir / "ml_template_ridge_cv.csv", index=False)
    ml_template_cal.to_csv(out_dir / "ml_template_residual_calibration.csv", index=False)

    combined = pulses.copy()
    combined["t_s03a_amp_only_reference_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["s03a_target_residual_ns"] = s03a_pulses["analytic_target_residual_ns"].to_numpy(dtype=float)
    combined["s03a_pred_residual_ns"] = s03a_pulses["analytic_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_s03b_binned_timewalk_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["s03b_target_residual_ns"] = binned_pulses["binned_target_residual_ns"].to_numpy(dtype=float)
    combined["s03b_pred_residual_ns"] = binned_pulses["binned_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_ml_template_ridge_ns"] = ml_template_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)
    combined["ml_template_target_residual_ns"] = ml_template_pulses["ml_target_residual_ns"].to_numpy(dtype=float)
    combined["ml_template_pred_residual_ns"] = ml_template_pulses["ml_pred_residual_ns"].to_numpy(dtype=float)

    benchmark = bootstrap_method_rows(
        combined,
        config,
        [
            (best_method, "s02_template_phase_base"),
            ("s03a_amp_only_reference", "s03a_amp_only_reference"),
            ("s03b_binned_timewalk", "s03b_binned_timewalk"),
            ("ml_template_ridge", "ml_ridge_on_template_phase"),
        ],
        rng,
    )
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    heldout_by_run = run_heldout_by_run(
        combined,
        config,
        [
            (best_method, "s02_template_phase_base"),
            ("s03a_amp_only_reference", "s03a_amp_only_reference"),
            ("s03b_binned_timewalk", "s03b_binned_timewalk"),
            ("ml_template_ridge", "ml_ridge_on_template_phase"),
        ],
    )
    heldout_by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)

    ref = config["reference_numbers"]
    s03a_repro = benchmark[
        benchmark["method"].isin(["s02_template_phase_base", "s03a_amp_only_reference", "ml_ridge_on_template_phase"])
    ][["method", "value"]].copy()
    expected_lookup = {
        "s02_template_phase_base": float(ref["s03a_template_phase_sigma68_ns"]),
        "s03a_amp_only_reference": float(ref["s03a_analytic_amp_only_sigma68_ns"]),
        "ml_ridge_on_template_phase": float(ref["s03a_ml_template_ridge_sigma68_ns"]),
    }
    s03a_repro["reference_value"] = s03a_repro["method"].map(expected_lookup)
    s03a_repro["delta"] = s03a_repro["value"] - s03a_repro["reference_value"]
    s03a_repro["pass"] = s03a_repro["delta"].abs() < 1.0e-9
    s03a_repro.to_csv(out_dir / "s03a_reproduction_benchmark.csv", index=False)
    if not bool(s03a_repro["pass"].all()):
        raise RuntimeError("S03a reproduction gate failed")

    train_event_ids = set(combined[combined["run"].isin(config["timing"]["train_runs"])]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin(config["timing"]["heldout_runs"])]["event_id"])
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & heldout_event_ids)),
                "unit": "events",
            },
            {
                "check": "s03b_shuffled_target_sigma68",
                "value": run_shuffled_binned_control(pulses, config, best_method, binned_best),
                "unit": "ns",
            },
            {
                "check": "ml_shuffled_target_sigma68",
                "value": run_shuffled_ml_control(pulses, config, best_method, ml_template_cv),
                "unit": "ns",
            },
            {"check": "traditional_uses_run_or_event_features", "value": 0.0, "unit": "bool"},
            {"check": "final_binned_fit_uses_heldout_rows", "value": 0.0, "unit": "bool"},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    calibration = pd.concat(
        [
            calibration_table(
                combined,
                "s03b_pred_residual_ns",
                "s03b_target_residual_ns",
                list(config["timing"]["heldout_runs"]),
                "s03b_binned_timewalk",
            ),
            calibration_table(
                combined,
                "ml_template_pred_residual_ns",
                "ml_template_target_residual_ns",
                list(config["timing"]["heldout_runs"]),
                "ml_ridge_on_template_phase",
            ),
        ],
        ignore_index=True,
    )
    calibration.to_csv(out_dir / "calibration_table.csv", index=False)
    plot_outputs(out_dir, benchmark, binned_cv, calibration)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    base = benchmark[benchmark["method"] == "s02_template_phase_base"].iloc[0]
    s03a_amp = benchmark[benchmark["method"] == "s03a_amp_only_reference"].iloc[0]
    binned = benchmark[benchmark["method"] == "s03b_binned_timewalk"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_ridge_on_template_phase"].iloc[0]
    binned_delta_vs_s03a = float(s03a_amp["value"] - binned["value"])
    improves_s03a = bool(binned["value"] < s03a_amp["value"])
    verdict = (
        "s03b_binned_monotonic_improves_on_s03a_amp_only"
        if improves_s03a
        else "s03b_binned_monotonic_does_not_improve_on_s03a_amp_only"
    )
    result = {
        "study": "S03b",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()) and bool(s03a_repro["pass"].all()),
        "s03a_reproduction": {
            row["method"]: {"value": float(row["value"]), "reference": float(row["reference_value"])}
            for _, row in s03a_repro.iterrows()
        },
        "traditional": {
            "metric": "heldout_pairwise_sigma68_ns",
            "method": "per_stave_amplitude_binned_timewalk",
            "mode": str(binned_best["mode"]),
            "direction": str(binned_best["direction"]),
            "n_bins": int(binned_best["n_bins"]),
            "cv_sigma68_ns": float(binned_best["score"]),
            "value": float(binned["value"]),
            "ci": [float(binned["ci_low"]), float(binned["ci_high"])],
            "delta_vs_s03a_amp_only_ns": binned_delta_vs_s03a,
            "improves_s03a_amp_only": improves_s03a,
        },
        "baselines": {
            "template_phase_sigma68_ns": float(base["value"]),
            "s03a_amp_only_sigma68_ns": float(s03a_amp["value"]),
        },
        "ml": {
            "metric": "heldout_pairwise_sigma68_ns",
            "method": "ridge_residual_corrector_on_template_phase",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "delta_vs_s03a_amp_only_ns": float(s03a_amp["value"] - ml["value"]),
        },
        "leakage": {
            "split_by_run": True,
            "train_runs": list(config["timing"]["train_runs"]),
            "heldout_runs": list(config["timing"]["heldout_runs"]),
            "event_id_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].iloc[0]),
            "s03b_shuffled_target_sigma68_ns": float(
                leakage[leakage["check"] == "s03b_shuffled_target_sigma68"]["value"].iloc[0]
            ),
            "ml_shuffled_target_sigma68_ns": float(
                leakage[leakage["check"] == "ml_shuffled_target_sigma68"]["value"].iloc[0]
            ),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S03c: multi-heldout-run timing correction stability with leave-one-run-out intervals",
            "S03d: physically signed per-stave amplitude timewalk prior versus isotonic fit",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(
        out_dir,
        config,
        repro,
        s03a_repro,
        benchmark,
        binned_cv,
        binned_table,
        heldout_by_run,
        leakage,
        binned_best,
        result,
    )

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03b",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["binned"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "base": float(base["value"]),
                "s03a_amp_only": float(s03a_amp["value"]),
                "s03b_binned": float(binned["value"]),
                "ml_template": float(ml["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
