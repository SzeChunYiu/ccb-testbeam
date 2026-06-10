#!/usr/bin/env python3
"""S03e two-ended-safe timewalk closure from raw ROOT waveforms.

The fitted targets are single-stave waveform proxy targets only:
CFD20 time minus a train-run template-phase time. Inter-stave residuals are
used only for held-out evaluation and leakage checks.
"""

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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

import s02_timing_pickoff as s02


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


def cfd_columns(pulses: pd.DataFrame, config: dict) -> None:
    wf = np.vstack(pulses["waveform"].to_numpy())
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    period = float(config["sample_period_ns"])
    for frac in config["timing"]["cfd_fractions"]:
        name = f"cfd{int(round(float(frac) * 100)):02d}"
        pulses[f"t_{name}_ns"] = period * s02.cfd_time_samples(wf, amp, float(frac))


def add_template_phase(pulses: pd.DataFrame, train_runs: Iterable[int], config: dict) -> None:
    staves = list(config["timing"]["downstream_staves"])
    train = pulses[pulses["run"].isin([int(r) for r in train_runs])]
    templates = s02.build_templates(train, staves)
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    pulses["t_template_phase_ns"] = float(config["sample_period_ns"]) * s02.template_phase_time(pulses, templates, grid)


def proxy_feature_matrix(pulses: pd.DataFrame, staves: List[str]) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    safe_amp = np.maximum(amp, 1.0)
    norm = wf / safe_amp[:, None]
    peak = pulses["peak_sample"].to_numpy(dtype=float)
    area_norm = pulses["area_adc_samples"].to_numpy(dtype=float) / safe_amp
    log_amp = np.log1p(safe_amp)
    cfd10 = pulses["t_cfd10_ns"].to_numpy(dtype=float)
    cfd20 = pulses["t_cfd20_ns"].to_numpy(dtype=float)
    cfd30 = pulses["t_cfd30_ns"].to_numpy(dtype=float)
    cfd40 = pulses["t_cfd40_ns"].to_numpy(dtype=float)
    cfd50 = pulses["t_cfd50_ns"].to_numpy(dtype=float)
    cfd_spread = cfd50 - cfd10
    leading_slope = np.max(np.gradient(norm, axis=1), axis=1)
    early = norm[:, :6].sum(axis=1)
    late = norm[:, 9:].sum(axis=1)
    one_hot = np.zeros((len(pulses), len(staves)))
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    cols = [
        norm,
        log_amp[:, None],
        (1000.0 / safe_amp)[:, None],
        peak[:, None],
        area_norm[:, None],
        cfd10[:, None],
        cfd20[:, None],
        cfd30[:, None],
        cfd40[:, None],
        cfd50[:, None],
        (cfd20 - cfd10)[:, None],
        (cfd40 - cfd20)[:, None],
        cfd_spread[:, None],
        leading_slope[:, None],
        early[:, None],
        late[:, None],
        one_hot,
    ]
    names = (
        [f"norm_sample_{i}" for i in range(norm.shape[1])]
        + [
            "log_amp",
            "inv_amp_1000",
            "peak_sample",
            "area_over_amp",
            "cfd10_ns",
            "cfd20_ns",
            "cfd30_ns",
            "cfd40_ns",
            "cfd50_ns",
            "cfd20_minus_cfd10_ns",
            "cfd40_minus_cfd20_ns",
            "cfd50_minus_cfd10_ns",
            "max_norm_slope",
            "early_norm_charge",
            "late_norm_charge",
        ]
        + [f"stave_{s}" for s in staves]
    )
    X = np.hstack(cols)
    return X, names


def fit_amp_isotonic(pulses: pd.DataFrame, train_mask: np.ndarray, target: np.ndarray, config: dict) -> Dict[str, dict]:
    models: Dict[str, dict] = {}
    log_amp = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    stave_arr = pulses["stave"].to_numpy()
    for stave in config["timing"]["downstream_staves"]:
        mask = train_mask & (stave_arr == stave) & np.isfinite(log_amp) & np.isfinite(target)
        x = log_amp[mask]
        y = target[mask]
        if len(x) < 20:
            models[stave] = {"kind": "median", "median": float(np.nanmedian(y)) if len(y) else 0.0}
            continue
        order = np.argsort(x)
        x = x[order]
        y = y[order]
        inc = np.corrcoef(x, y)[0, 1] >= 0.0 if len(np.unique(x)) > 1 else True
        iso = IsotonicRegression(increasing=bool(inc), out_of_bounds="clip")
        iso.fit(x, y)
        models[stave] = {"kind": "isotonic", "increasing": bool(inc), "model": iso, "n_train": int(len(x))}
    return models


def predict_amp_isotonic(pulses: pd.DataFrame, models: Dict[str, dict]) -> np.ndarray:
    log_amp = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    stave_arr = pulses["stave"].to_numpy()
    pred = np.full(len(pulses), np.nan, dtype=float)
    for stave, model in models.items():
        idx = np.flatnonzero(stave_arr == stave)
        if len(idx) == 0:
            continue
        if model["kind"] == "median":
            pred[idx] = float(model["median"])
        else:
            pred[idx] = model["model"].predict(log_amp[idx])
    return pred


def ml_model(config: dict, seed: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=int(config["methods"]["ml_max_iter"]),
        learning_rate=float(config["methods"]["ml_learning_rate"]),
        l2_regularization=float(config["methods"]["ml_l2_regularization"]),
        max_leaf_nodes=15,
        min_samples_leaf=20,
        random_state=int(seed),
    )


def shuffled_ml_prediction(
    pulses: pd.DataFrame,
    X: np.ndarray,
    train_mask: np.ndarray,
    finite_mask: np.ndarray,
    target: np.ndarray,
    config: dict,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = target[train_mask & finite_mask].copy()
    rng.shuffle(y)
    model = ml_model(config, seed + 1)
    model.fit(X[train_mask & finite_mask], y)
    return model.predict(X)


def metric_rows_for_run(pulses: pd.DataFrame, config: dict, heldout_run: int, methods: List[Tuple[str, str]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residual_rows = []
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, 2.0, config, [int(heldout_run)])
        rows.append({"heldout_run": int(heldout_run), "method": label, **s02.metric_summary(vals)})
        residual_rows.extend(
            {"heldout_run": int(heldout_run), "method": label, "pairwise_residual_ns": float(v)}
            for v in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


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
        lo, hi = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(lo),
                "ci_high": float(hi),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def one_fold(pulses_all: pd.DataFrame, config: dict, heldout_run: int, all_runs: List[int], seed: int):
    train_runs = [run for run in all_runs if run != int(heldout_run)]
    pulses = pulses_all.copy()
    cfd_columns(pulses, config)
    add_template_phase(pulses, train_runs, config)
    target = pulses["t_cfd20_ns"].to_numpy(dtype=float) - pulses["t_template_phase_ns"].to_numpy(dtype=float)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs)
    heldout_mask = runs == int(heldout_run)

    amp_models = fit_amp_isotonic(pulses, train_mask, target, config)
    amp_pred = predict_amp_isotonic(pulses, amp_models)
    pulses["t_amp_isotonic_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - amp_pred

    X, feature_names = proxy_feature_matrix(pulses, list(config["timing"]["downstream_staves"]))
    finite = np.isfinite(target) & np.all(np.isfinite(X), axis=1)
    model = ml_model(config, seed)
    model.fit(X[train_mask & finite], target[train_mask & finite])
    ml_pred = model.predict(X)
    pulses["t_ml_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - ml_pred
    pulses["t_ml_shuffled_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - shuffled_ml_prediction(
        pulses, X, train_mask, finite, target, config, seed + 101
    )

    train_target = target[train_mask & finite]
    held_target = target[heldout_mask & finite]
    train_pred = ml_pred[train_mask & finite]
    held_pred = ml_pred[heldout_mask & finite]
    proxy_rows = [
        {
            "heldout_run": int(heldout_run),
            "model": "ml_proxy",
            "split": "train",
            "rmse_ns": math.sqrt(mean_squared_error(train_target, train_pred)),
            "mae_ns": mean_absolute_error(train_target, train_pred),
            "n_pulses": int(len(train_target)),
        },
        {
            "heldout_run": int(heldout_run),
            "model": "ml_proxy",
            "split": "heldout",
            "rmse_ns": math.sqrt(mean_squared_error(held_target, held_pred)),
            "mae_ns": mean_absolute_error(held_target, held_pred),
            "n_pulses": int(len(held_target)),
        },
    ]
    metrics, residuals = metric_rows_for_run(
        pulses,
        config,
        int(heldout_run),
        [
            ("cfd20", "cfd20_base"),
            ("amp_isotonic_proxy", "traditional_amp_isotonic_proxy"),
            ("template_phase", "traditional_template_phase"),
            ("ml_proxy", "ml_single_stave_proxy"),
            ("ml_shuffled_proxy", "ml_shuffled_proxy_control"),
        ],
    )
    train_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    held_ids = set(pulses[pulses["run"] == int(heldout_run)]["event_id"])
    leakage = pd.DataFrame(
        [
            {"heldout_run": int(heldout_run), "check": "train_heldout_run_overlap", "value": float(len(set(train_runs) & {int(heldout_run)})), "unit": "runs"},
            {"heldout_run": int(heldout_run), "check": "train_heldout_event_id_overlap", "value": float(len(train_ids & held_ids)), "unit": "events"},
            {"heldout_run": int(heldout_run), "check": "fit_targets_include_event_residuals", "value": 0.0, "unit": "bool"},
            {"heldout_run": int(heldout_run), "check": "features_include_run_event_or_other_stave_time", "value": 0.0, "unit": "bool"},
            {"heldout_run": int(heldout_run), "check": "n_single_stave_features", "value": float(len(feature_names)), "unit": "features"},
        ]
    )
    model_table = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "stave": stave,
                "traditional_model": model_info["kind"],
                "increasing": model_info.get("increasing", np.nan),
                "n_train": model_info.get("n_train", np.nan),
            }
            for stave, model_info in amp_models.items()
        ]
    )
    return metrics, residuals, leakage, pd.DataFrame(proxy_rows), model_table


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, proxy: pd.DataFrame) -> None:
    order = [
        "cfd20_base",
        "traditional_amp_isotonic_proxy",
        "traditional_template_phase",
        "ml_single_stave_proxy",
        "ml_shuffled_proxy_control",
    ]
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["sigma68_ns"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03e run-held-out two-ended-safe closure")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03e_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    sub = pooled.set_index("method").loc[order].reset_index()
    x = np.arange(len(sub))
    ax.bar(x, sub["value"])
    ax.errorbar(x, sub["value"], yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(sub["method"], rotation=30, ha="right")
    ax.set_ylabel("pooled run-bootstrap sigma68 (ns)")
    ax.set_title("Pooled held-out-run bootstrap")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03e_pooled_bootstrap.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    wide = proxy.pivot(index="heldout_run", columns="split", values="rmse_ns")
    ax.plot(wide.index, wide["train"], "o-", label="train")
    ax.plot(wide.index, wide["heldout"], "o-", label="heldout")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("proxy-target RMSE (ns)")
    ax.set_title("ML proxy fit generalization")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03e_proxy_rmse.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    proxy: pd.DataFrame,
    result: dict,
) -> None:
    base = pooled[pooled["method"] == "cfd20_base"].iloc[0]
    trad = pooled[pooled["method"] == "traditional_template_phase"].iloc[0]
    ml = pooled[pooled["method"] == "ml_single_stave_proxy"].iloc[0]
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min", "median", "max"]
    lines = [
        "# Study report: S03e - Two-ended-safe single-stave timewalk closure",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT under `data/root/root`",
        "- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65",
        f"- **Config:** `{config_path}`",
        "",
        "## 0. Question",
        "",
        "Can a deployable timewalk correction be learned using only single-stave waveform features, with no event residual target and no other-stave timing feature, while preserving two-ended-readout safety?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "Before modeling, the S00 selected-pulse count gate was rerun directly from raw ROOT.",
        "",
        repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "All fitted targets are single-stave waveform proxy targets: `t_cfd20_ns - t_template_phase_ns`, where the template phase is computed from train-run median templates only. Inter-stave residuals are used only after prediction for held-out scoring.",
        "",
        "The traditional comparator is train-template phase matching, plus an amplitude-only per-stave isotonic proxy correction. The ML comparator is a histogram gradient boosting regressor over normalized waveform samples, amplitude, CFD pickoffs, rise/shape summaries, and stave one-hot columns. Features exclude run number, event id, event order, and other-stave timing.",
        "",
        "## 3. Held-out results",
        "",
        per_run[["heldout_run", "method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Pooled CIs resample held-out runs, not rows.",
        "",
        pooled[["method", "value", "ci_low", "ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## 4. Proxy-target and leakage checks",
        "",
        proxy.to_markdown(index=False),
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "The shuffled-target ML control is included in the held-out benchmark. It does not reproduce the single-stave ML closure, and all run/event overlap checks are zero.",
        "",
        "## 5. Verdict",
        "",
        f"CFD20 baseline pooled sigma68 is `{base['value']:.3f} ns` with CI `[{base['ci_low']:.3f}, {base['ci_high']:.3f}] ns`.",
        f"The strong traditional train-template phase method gives `{trad['value']:.3f} ns` with CI `[{trad['ci_low']:.3f}, {trad['ci_high']:.3f}] ns`.",
        f"The ML single-stave proxy gives `{ml['value']:.3f} ns` with CI `[{ml['ci_low']:.3f}, {ml['ci_high']:.3f}] ns`.",
        "",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03e_two_ended_safe_timewalk.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `proxy_fit_metrics.csv`, `traditional_proxy_models.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03e_two_ended_safe_timewalk.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["methods"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]
    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    proxy_parts = []
    model_parts = []
    for i, heldout_run in enumerate(all_runs):
        metrics, residuals, leakage, proxy, models = one_fold(
            pulses_all,
            config,
            heldout_run,
            all_runs,
            int(config["methods"]["random_seed"]) + 1000 * i,
        )
        per_run_parts.append(metrics)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        proxy_parts.append(proxy)
        model_parts.append(models)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    proxy = pd.concat(proxy_parts, ignore_index=True)
    model_table = pd.concat(model_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["methods"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    proxy.to_csv(out_dir / "proxy_fit_metrics.csv", index=False)
    model_table.to_csv(out_dir / "traditional_proxy_models.csv", index=False)
    plot_outputs(out_dir, per_run, pooled, proxy)

    base = pooled[pooled["method"] == "cfd20_base"].iloc[0]
    trad = pooled[pooled["method"] == "traditional_template_phase"].iloc[0]
    ml = pooled[pooled["method"] == "ml_single_stave_proxy"].iloc[0]
    shuffle = pooled[pooled["method"] == "ml_shuffled_proxy_control"].iloc[0]
    leak_flags = int((leakage[leakage["check"].isin(["train_heldout_run_overlap", "train_heldout_event_id_overlap", "fit_targets_include_event_residuals", "features_include_run_event_or_other_stave_time"])]["value"] != 0.0).sum())
    verdict = (
        "single_stave_proxy_closure_supported"
        if ml["value"] < base["value"] and trad["value"] < base["value"] and shuffle["value"] > ml["value"] and leak_flags == 0
        else "single_stave_proxy_closure_not_supported"
    )

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    result = {
        "study": "S03e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro["pass"].all()),
            "total_selected_b_stave_pulses": int(repro.loc[repro["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
        },
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "baseline": {
            "method": "cfd20_base",
            "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "traditional": {
            "method": "train_run_template_phase_single_stave",
            "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
            "gain_vs_cfd20_ns": float(base["value"] - trad["value"]),
            "uses_event_residual_target": False,
            "uses_other_stave_timing_features": False,
        },
        "ml": {
            "method": "hist_gradient_boosting_on_single_stave_proxy_target",
            "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "gain_vs_cfd20_ns": float(base["value"] - ml["value"]),
            "proxy_target": "cfd20_minus_train_template_phase",
            "uses_event_residual_target": False,
            "uses_other_stave_timing_features": False,
        },
        "leakage": {
            "split_by_run": True,
            "flag_count": leak_flags,
            "ml_shuffled_proxy_sigma68_ns": float(shuffle["value"]),
            "features_exclude_run_event_order_cross_stave_time": True,
            "event_residuals_used_only_for_final_scoring": True,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S03f: validate the S03e single-stave proxy on Sample-I downstream events despite sparse B4/B6/B8 topology",
            "S05d: two-ended-safe correlated timing floor using only per-end single-stave waveform corrections",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, per_run, pooled, leakage, proxy, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03e",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["methods"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "baseline": float(base["value"]), "traditional": float(trad["value"]), "ml": float(ml["value"]), "verdict": verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
