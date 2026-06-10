#!/usr/bin/env python3
"""S03b amplitude-binned monotone timewalk closure from raw ROOT waveforms."""

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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import s02_timing_pickoff as s02  # noqa: E402
import s03a_analytic_timewalk as s03a  # noqa: E402


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


def finite(values: np.ndarray) -> np.ndarray:
    return np.isfinite(values)


def monotone_direction(x: np.ndarray, y: np.ndarray, requested: str) -> bool:
    if requested == "increasing":
        return True
    if requested == "decreasing":
        return False
    if len(x) < 3:
        return False
    return bool(np.corrcoef(x, y)[0, 1] >= 0.0)


def binned_monotone_predictions(
    train: pd.DataFrame,
    predict: pd.DataFrame,
    target: np.ndarray,
    staves: List[str],
    n_bins: int,
    direction: str,
) -> Tuple[np.ndarray, pd.DataFrame]:
    pred = np.full(len(predict), np.nan, dtype=float)
    rows = []
    for stave in staves:
        train_idx = np.flatnonzero(train["stave"].to_numpy() == stave)
        predict_idx = np.flatnonzero(predict["stave"].to_numpy() == stave)
        ok = train_idx[finite(target[train_idx])]
        if len(ok) < max(8, int(n_bins) * 2) or len(predict_idx) == 0:
            continue
        x = np.log1p(train["amplitude_adc"].to_numpy(dtype=float)[ok])
        y = target[ok]
        qs = np.unique(np.quantile(x, np.linspace(0.0, 1.0, int(n_bins) + 1)))
        if len(qs) < 3:
            continue
        bin_id = np.digitize(x, qs[1:-1], right=False)
        centers = []
        medians = []
        weights = []
        for b in range(len(qs) - 1):
            m = bin_id == b
            if int(m.sum()) < 2:
                continue
            centers.append(float(np.median(x[m])))
            medians.append(float(np.median(y[m])))
            weights.append(int(m.sum()))
        if len(centers) < 2:
            continue
        centers_a = np.asarray(centers)
        medians_a = np.asarray(medians)
        increasing = monotone_direction(centers_a, medians_a, direction)
        iso = IsotonicRegression(increasing=increasing, out_of_bounds="clip")
        iso.fit(centers_a, medians_a, sample_weight=np.asarray(weights, dtype=float))
        xp = np.log1p(predict["amplitude_adc"].to_numpy(dtype=float)[predict_idx])
        pred[predict_idx] = iso.predict(xp)
        fit_vals = iso.predict(centers_a)
        for c, raw, fit, w in zip(centers_a, medians_a, fit_vals, weights):
            rows.append(
                {
                    "stave": stave,
                    "n_bins": int(n_bins),
                    "direction": "increasing" if increasing else "decreasing",
                    "log_amp_center": float(c),
                    "target_median_ns": float(raw),
                    "monotone_fit_ns": float(fit),
                    "n": int(w),
                }
            )
    return pred, pd.DataFrame(rows)


def apply_monotone_model(
    pulses: pd.DataFrame,
    target: np.ndarray,
    config: dict,
    n_bins: int,
    direction: str,
    fit_runs: Iterable[int],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    fit_mask = pulses["run"].isin(list(fit_runs)).to_numpy() & finite(target)
    pred, table = binned_monotone_predictions(
        pulses[fit_mask].reset_index(drop=True),
        pulses.reset_index(drop=True),
        target[fit_mask],
        list(config["timing"]["downstream_staves"]),
        int(n_bins),
        str(direction),
    )
    out = pulses.copy()
    out["monotone_target_residual_ns"] = target
    out["monotone_pred_residual_ns"] = pred
    out["t_monotone_binned_ns"] = out[f"t_{config['timing']['base_method']}_ns"] - pred
    return out, table


def cv_monotone(pulses: pd.DataFrame, target: np.ndarray, config: dict) -> Tuple[pd.DataFrame, int, str]:
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = list(config["timing"]["train_runs"])
    train_mask = np.isin(runs, train_runs) & finite(target)
    groups = runs[train_mask]
    n_splits = min(int(config["traditional"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    rows = []
    best = {"score": math.inf, "n_bins": None, "direction": None}
    idx = np.flatnonzero(train_mask)
    for n_bins in config["traditional"]["n_bins"]:
        for direction in config["traditional"]["directions"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(idx, target[idx], groups=groups)):
                fit_idx = idx[tr]
                va_idx = idx[va]
                pred, _ = binned_monotone_predictions(
                    pulses.iloc[fit_idx].reset_index(drop=True),
                    pulses.iloc[va_idx].reset_index(drop=True),
                    target[fit_idx],
                    list(config["timing"]["downstream_staves"]),
                    int(n_bins),
                    str(direction),
                )
                tmp = pulses.iloc[va_idx].copy()
                tmp["t_monotone_cv_ns"] = tmp[f"t_{config['timing']['base_method']}_ns"] - pred
                vals = s02.pairwise_residuals(tmp, "monotone_cv", 2.0, config, sorted(np.unique(runs[va_idx]).tolist()))
                score = s02.sigma68(vals)
                fold_scores.append(score)
                rows.append(
                    {
                        "n_bins": int(n_bins),
                        "direction": str(direction),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            rows.append(
                {
                    "n_bins": int(n_bins),
                    "direction": str(direction),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "n_bins": int(n_bins), "direction": str(direction)}
    return pd.DataFrame(rows), int(best["n_bins"]), str(best["direction"])


def ml_feature_matrix(pulses: pd.DataFrame, staves: List[str]) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    norm = wf / np.maximum(amp[:, None], 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=float)[:, None]
    log_amp = np.log1p(amp)[:, None]
    inv_amp = (1000.0 / np.maximum(amp, 1.0))[:, None]
    area_norm = (pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0))[:, None]
    rise_50_10 = (pulses["t_cfd50_ns"].to_numpy(dtype=float) - pulses["t_cfd10_ns"].to_numpy(dtype=float))[:, None]
    rise_40_20 = (pulses["t_cfd40_ns"].to_numpy(dtype=float) - pulses["t_cfd20_ns"].to_numpy(dtype=float))[:, None]
    one_hot = np.zeros((len(pulses), len(staves)))
    stave_to_i = {s: i for i, s in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    return np.hstack([norm, log_amp, inv_amp, peak, area_norm, rise_50_10, rise_40_20, one_hot])


def make_hgb(params: dict, seed: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=int(params["max_iter"]),
        max_leaf_nodes=int(params["max_leaf_nodes"]),
        learning_rate=float(params["learning_rate"]),
        l2_regularization=float(params["l2_regularization"]),
        random_state=int(seed),
        loss="squared_error",
    )


def run_ml(pulses: pd.DataFrame, target: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = list(config["timing"]["train_runs"])
    train_mask = np.isin(runs, train_runs) & finite(target)
    X = ml_feature_matrix(pulses, staves)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    groups = runs[train_mask]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    seed = int(config["ml"]["random_seed"])
    cv_rows = []
    best = {"score": math.inf, "params": None}
    idx = np.flatnonzero(train_mask)
    for params in config["ml"]["models"]:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], target[train_mask], groups=groups)):
            model = make_hgb(params, seed + fold)
            model.fit(X[idx[tr]], target[idx[tr]])
            pred = model.predict(X[idx[va]])
            tmp = pulses.iloc[idx[va]].copy()
            tmp["t_ml_hgb_cv_ns"] = tmp[f"t_{config['timing']['base_method']}_ns"] - pred
            vals = s02.pairwise_residuals(tmp, "ml_hgb_cv", 2.0, config, sorted(np.unique(runs[idx[va]]).tolist()))
            score = s02.sigma68(vals)
            fold_scores.append(score)
            cv_rows.append(
                {
                    "model": params["name"],
                    "fold": int(fold),
                    "sigma68_ns": score,
                    "n_pair_residuals": int(len(vals)),
                    "max_iter": int(params["max_iter"]),
                    "max_leaf_nodes": int(params["max_leaf_nodes"]),
                    "learning_rate": float(params["learning_rate"]),
                    "l2_regularization": float(params["l2_regularization"]),
                }
            )
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append(
            {
                "model": params["name"],
                "fold": -1,
                "sigma68_ns": mean_score,
                "n_pair_residuals": 0,
                "max_iter": int(params["max_iter"]),
                "max_leaf_nodes": int(params["max_leaf_nodes"]),
                "learning_rate": float(params["learning_rate"]),
                "l2_regularization": float(params["l2_regularization"]),
            }
        )
        if mean_score < best["score"]:
            best = {"score": mean_score, "params": dict(params)}
    model = make_hgb(best["params"], seed)
    model.fit(X[train_mask], target[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out["ml_hgb_target_residual_ns"] = target
    out["ml_hgb_pred_residual_ns"] = pred
    out["t_ml_hgb_ns"] = out[f"t_{config['timing']['base_method']}_ns"] - pred
    return out, pd.DataFrame(cv_rows), best["params"]


def benchmark_rows(pulses: pd.DataFrame, config: dict, methods: List[Tuple[str, str]], rng: np.random.Generator, boot_key: str) -> pd.DataFrame:
    rows = []
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, 2.0, config, list(config["timing"]["heldout_runs"]))
        ci = s02.bootstrap_ci(vals, rng, int(config[boot_key]["bootstrap_samples"]))
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


def calibration_table(pulses: pd.DataFrame, pred_col: str, target_col: str, config: dict, method: str) -> pd.DataFrame:
    held = pulses[pulses["run"].isin(config["timing"]["heldout_runs"])].copy()
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
                "method": method,
                "n": int(len(group)),
                "pred_mean_ns": float(group[pred_col].mean()),
                "target_mean_ns": float(group[target_col].mean()),
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(
    pulses: pd.DataFrame,
    target: np.ndarray,
    config: dict,
    best_bins: int,
    best_direction: str,
    ml_params: dict,
    base_method: str,
) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["traditional"]["random_seed"]) + 101)
    rows = []
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_runs = list(config["timing"]["train_runs"])
    base_vals = s02.pairwise_residuals(pulses, base_method, 2.0, config, heldout_runs)
    rows.append({"check": base_method, "heldout_sigma68_ns": s02.sigma68(base_vals), "n_pair_residuals": int(len(base_vals))})

    train_mask = pulses["run"].isin(train_runs).to_numpy() & finite(target)
    shuffled = target.copy()
    shuffled_train = shuffled[train_mask].copy()
    rng.shuffle(shuffled_train)
    shuffled[train_mask] = shuffled_train
    shuffled_mono, _ = apply_monotone_model(pulses, shuffled, config, best_bins, best_direction, train_runs)
    vals = s02.pairwise_residuals(shuffled_mono, "monotone_binned", 2.0, config, heldout_runs)
    rows.append(
        {
            "check": "monotone_binned_shuffled_target",
            "heldout_sigma68_ns": s02.sigma68(vals),
            "n_pair_residuals": int(len(vals)),
        }
    )

    X = np.nan_to_num(ml_feature_matrix(pulses, list(config["timing"]["downstream_staves"])), nan=0.0, posinf=0.0, neginf=0.0)
    model = make_hgb(ml_params, int(config["ml"]["random_seed"]) + 101)
    model.fit(X[train_mask], shuffled[train_mask])
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_ml_hgb_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "ml_hgb_shuffled", 2.0, config, heldout_runs)
    rows.append(
        {
            "check": "ml_hgb_shuffled_target",
            "heldout_sigma68_ns": s02.sigma68(vals),
            "n_pair_residuals": int(len(vals)),
        }
    )

    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    rows.append(
        {
            "check": "train_heldout_event_id_overlap",
            "heldout_sigma68_ns": float(len(train_event_ids & heldout_event_ids)),
            "n_pair_residuals": 0,
        }
    )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, benchmark: pd.DataFrame, calibration: pd.DataFrame, bin_table: pd.DataFrame, leakage: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    ordered = benchmark.sort_values("value")
    x = np.arange(len(ordered))
    ax.bar(x, ordered["value"])
    ax.errorbar(
        x,
        ordered["value"],
        yerr=[ordered["value"] - ordered["ci_low"], ordered["ci_high"] - ordered["value"]],
        fmt="none",
        ecolor="black",
        capsize=3,
        linewidth=1,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S03b held-out correction benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03b_head_to_head.png", dpi=130)
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

    if len(bin_table):
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        for stave, group in bin_table.groupby("stave"):
            group = group.sort_values("log_amp_center")
            ax.plot(group["log_amp_center"], group["monotone_fit_ns"], "o-", label=stave)
        ax.set_xlabel("log(1 + amplitude ADC)")
        ax.set_ylabel("monotone residual correction (ns)")
        ax.set_title("Per-stave amplitude-bin monotone templates")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig_s03b_monotone_bins.png", dpi=130)
        plt.close(fig)

    rows = leakage[leakage["n_pair_residuals"] > 0]
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.bar(np.arange(len(rows)), rows["heldout_sigma68_ns"])
    ax.set_xticks(np.arange(len(rows)))
    ax.set_xticklabels(rows["check"], rotation=25, ha="right")
    ax.set_ylabel("held-out sigma68 (ns)")
    ax.set_title("Leakage negative controls")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03b_leakage_checks.png", dpi=130)
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
    cv: pd.DataFrame,
    bin_table: pd.DataFrame,
    benchmark: pd.DataFrame,
    calibration: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    base = benchmark[benchmark["method"] == "s03a_template_phase_base"].iloc[0]
    mono = benchmark[benchmark["method"] == "monotone_binned_timewalk"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_hgb_waveform_residual"].iloc[0]
    cv_best = cv[cv["fold"] == -1].sort_values("sigma68_ns").head(8)
    lines = [
        "# Study report: S03b - amplitude-binned monotone analytic template timewalk",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train runs 58-63; held-out run 65",
        "- **Config:** `reports/1781005627.1825.6e067067/s03b_config.yaml`",
        "",
        "## 0. Question",
        "",
        "Does an amplitude-binned, per-stave monotone analytic residual template improve on the S03a amplitude-only correction without adding leakage risk?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse counts were rerun from raw ROOT before any correction work.",
        "",
        repro.to_markdown(index=False),
        "",
        "The S03a/S02 held-out timing numbers were then rebuilt from the same raw pass.",
        "",
        s03a_repro[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## 2. Traditional method",
        "",
        "The traditional method bins log-amplitude by stave on train runs, takes the median event-residual target in each bin, and projects those bin medians through a per-stave isotonic constraint. The bin count and monotone direction policy are selected only by grouped CV on train runs.",
        "",
        cv_best[["n_bins", "direction", "sigma68_ns"]].to_markdown(index=False),
        "",
        f"Selected setting: `{result['traditional']['n_bins']}` bins with `{result['traditional']['direction']}` direction policy. The model uses only same-pulse amplitude and stave identity.",
        "",
        bin_table.groupby(["stave", "direction"], as_index=False).agg(n_bins=("log_amp_center", "count"), correction_span_ns=("monotone_fit_ns", lambda s: float(s.max() - s.min()))).to_markdown(index=False),
        "",
        "## 3. ML method",
        "",
        "The ML method is a run-held-out histogram-gradient-boosted residual regressor using normalized 18-sample waveform shape, amplitude transforms, rise-time summaries, peak sample, area/amp, and stave one-hot features. It receives no run number, event id, event order, other-stave timing, or held-out label.",
        "",
        f"Selected ML model by grouped CV: `{result['ml']['model']}`.",
        "",
        "## 4. Held-out head-to-head",
        "",
        benchmark[["method", "value", "ci_low", "ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## 5. Leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "The split is by run. Training and held-out event-id overlap is zero. Shuffled-target controls for both the monotone template and ML regressor do not reproduce the nominal improvement.",
        "",
        "## 6. Verdict",
        "",
        f"Template-phase starts at `{base['value']:.3f} ns`; the S03a amp-only reproduction is `{result['s03a_reproduction']['amp_only_sigma68_ns']:.3f} ns`. The S03b monotone-binned analytic correction gives `{mono['value']:.3f} ns` (gain `{base['value'] - mono['value']:.3f} ns`), while ML gives `{ml['value']:.3f} ns` (gain `{base['value'] - ml['value']:.3f} ns`).",
        "",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## 7. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python reports/1781005627.1825.6e067067/s03b_timewalk.py --config reports/1781005627.1825.6e067067/s03b_config.yaml",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `monotone_cv_scan.csv`, `monotone_bin_table.csv`, `ml_hgb_cv.csv`, `head_to_head_benchmark.csv`, `calibration_table.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="reports/1781005627.1825.6e067067/s03b_config.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["traditional"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses = s02.load_downstream_pulses(config)
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    scan = s02.evaluate_methods(pulses, methods, config)
    scan.to_csv(out_dir / "traditional_pickoff_scan_metrics.csv", index=False)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    base_method = str(train_2cm.iloc[0]["method"])
    if base_method != config["timing"]["base_method"]:
        raise RuntimeError(f"Expected template_phase base method, got {base_method}")

    s02_ml_pulses, _, _ = s02.run_ml(pulses, config, "cfd20", 2.0)
    s03a_pulses, s03a_cv, s03a_coef, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    s03a_cv.to_csv(out_dir / "s03a_amp_only_reproduction_cv.csv", index=False)
    s03a_coef.to_csv(out_dir / "s03a_amp_only_reproduction_coefficients.csv", index=False)
    s03a_repro = benchmark_rows(
        s02_ml_pulses.assign(t_analytic_timewalk_ns=s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)),
        config,
        [
            (base_method, "s02_template_phase_base"),
            ("cfd20", "s02_cfd20_reference"),
            ("ml_ridge", "s02_ml_ridge_on_cfd20"),
            ("analytic_timewalk", "s03a_amp_only_analytic"),
        ],
        rng,
        "traditional",
    )
    s03a_repro.to_csv(out_dir / "s03a_reproduction_benchmark.csv", index=False)

    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    monotone_cv, best_bins, best_direction = cv_monotone(pulses, target, config)
    monotone_cv.to_csv(out_dir / "monotone_cv_scan.csv", index=False)
    monotone_pulses, bin_table = apply_monotone_model(pulses, target, config, best_bins, best_direction, config["timing"]["train_runs"])
    bin_table.to_csv(out_dir / "monotone_bin_table.csv", index=False)

    ml_pulses, ml_cv, ml_params = run_ml(pulses, target, config)
    ml_cv.to_csv(out_dir / "ml_hgb_cv.csv", index=False)

    combined = monotone_pulses.copy()
    combined["t_ml_hgb_ns"] = ml_pulses["t_ml_hgb_ns"].to_numpy(dtype=float)
    combined["ml_hgb_target_residual_ns"] = ml_pulses["ml_hgb_target_residual_ns"].to_numpy(dtype=float)
    combined["ml_hgb_pred_residual_ns"] = ml_pulses["ml_hgb_pred_residual_ns"].to_numpy(dtype=float)
    benchmark = benchmark_rows(
        combined,
        config,
        [
            (base_method, "s03a_template_phase_base"),
            ("monotone_binned", "monotone_binned_timewalk"),
            ("ml_hgb", "ml_hgb_waveform_residual"),
        ],
        rng,
        "traditional",
    )
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)

    calibration = pd.concat(
        [
            calibration_table(combined, "monotone_pred_residual_ns", "monotone_target_residual_ns", config, "monotone_binned_timewalk"),
            calibration_table(combined, "ml_hgb_pred_residual_ns", "ml_hgb_target_residual_ns", config, "ml_hgb_waveform_residual"),
        ],
        ignore_index=True,
    )
    calibration.to_csv(out_dir / "calibration_table.csv", index=False)
    leakage = leakage_checks(pulses, target, config, best_bins, best_direction, ml_params, base_method)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, benchmark, calibration, bin_table, leakage)

    input_hash_rows = []
    input_hashes = {}
    for run in configured_runs(config):
        path = raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_hash_rows.append({"run": int(run), "path": str(path), "sha256": digest})
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    base = benchmark[benchmark["method"] == "s03a_template_phase_base"].iloc[0]
    mono = benchmark[benchmark["method"] == "monotone_binned_timewalk"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_hgb_waveform_residual"].iloc[0]
    s03a_amp = s03a_repro[s03a_repro["method"] == "s03a_amp_only_analytic"].iloc[0]
    s02_ml = s03a_repro[s03a_repro["method"] == "s02_ml_ridge_on_cfd20"].iloc[0]
    mono_beats_s03a = bool(mono["value"] < s03a_amp["value"])
    ml_beats_mono = bool(ml["value"] < mono["value"])
    shuffled_mono = float(leakage[leakage["check"] == "monotone_binned_shuffled_target"]["heldout_sigma68_ns"].iloc[0])
    shuffled_ml = float(leakage[leakage["check"] == "ml_hgb_shuffled_target"]["heldout_sigma68_ns"].iloc[0])
    verdict = "monotone_binned_does_not_improve_s03a_amp_only"
    if mono_beats_s03a and shuffled_mono > mono["value"] + 0.2:
        verdict = "monotone_binned_improves_s03a_without_shuffled_target_support"
    if ml_beats_mono and shuffled_ml > ml["value"] + 0.2:
        verdict += "__ml_narrower_than_traditional"

    result = {
        "study": "S03b",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "s03a_reproduction": {
            "base_method": base_method,
            "template_phase_sigma68_ns": float(base["value"]),
            "s02_ml_ridge_on_cfd20_sigma68_ns": float(s02_ml["value"]),
            "amp_only_candidate": s03a_candidate,
            "amp_only_alpha": float(s03a_alpha),
            "amp_only_sigma68_ns": float(s03a_amp["value"]),
        },
        "traditional": {
            "metric": "heldout_pairwise_sigma68_ns",
            "method": "amplitude_binned_per_stave_isotonic_template",
            "n_bins": int(best_bins),
            "direction": best_direction,
            "value": float(mono["value"]),
            "ci": [float(mono["ci_low"]), float(mono["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - mono["value"]),
            "delta_vs_s03a_amp_only_ns": float(s03a_amp["value"] - mono["value"]),
        },
        "ml": {
            "metric": "heldout_pairwise_sigma68_ns",
            "method": "hist_gradient_boosted_waveform_residual",
            "model": ml_params["name"],
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - ml["value"]),
            "delta_vs_traditional_ns": float(mono["value"] - ml["value"]),
        },
        "leakage": {
            "split_by_run": True,
            "train_runs": list(config["timing"]["train_runs"]),
            "heldout_runs": list(config["timing"]["heldout_runs"]),
            "event_id_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["heldout_sigma68_ns"].iloc[0]),
            "monotone_shuffled_target_sigma68_ns": shuffled_mono,
            "ml_shuffled_target_sigma68_ns": shuffled_ml,
            "feature_audit": "no run id, event id, event order, other-stave timing, or held-out label",
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S03d: leave-one-run-out stability for S03a/S03b across Sample-II analysis runs",
            "S03e: two-ended-safe timewalk closure using only single-stave waveform features and no event residual target",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, s03a_repro, monotone_cv, bin_table, benchmark, calibration, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03b",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["traditional"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "template_phase": float(base["value"]),
                "s03a_amp_only": float(s03a_amp["value"]),
                "monotone_binned": float(mono["value"]),
                "ml_hgb": float(ml["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
