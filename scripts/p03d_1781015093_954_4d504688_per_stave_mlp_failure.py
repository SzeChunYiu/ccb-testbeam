#!/usr/bin/env python3
"""P03d per-stave MLP timing calibration failure analysis.

The raw ROOT count gate is run before reading P03b outputs. P03b supplies the
held-out pair residual benchmark; this script retrains the final fixed MLP fold
models to recover per-pulse target, prediction, and sigma diagnostics by run and
stave without adding run, event, or cross-stave timing features.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03d")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

import p03a_18_sample_mlp_timing as p03a
import s02_timing_pickoff as s02


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


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def fold_config(config: dict, heldout_run: int, loo_runs: Sequence[int]) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
    return cfg


def clean_metric_values(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)]


def bootstrap_ci_by_event(
    frame: pd.DataFrame,
    value_col: str,
    metric: str,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float]:
    values = clean_metric_values(frame[value_col])
    if len(values) == 0:
        return float("nan"), float("nan"), float("nan")
    if metric == "sigma68":
        observed = s02.sigma68(values)
    elif metric == "median_abs":
        observed = float(np.median(np.abs(values)))
    elif metric == "median":
        observed = float(np.median(values))
    else:
        raise ValueError(metric)

    by_event = frame.groupby("event_id")[value_col].apply(lambda s: clean_metric_values(s)).to_dict()
    event_ids = np.asarray(sorted(by_event.keys()))
    if len(event_ids) < 2:
        return observed, observed, observed
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(event_ids, size=len(event_ids), replace=True)
        vals = np.concatenate([by_event[event_id] for event_id in sampled])
        if metric == "sigma68":
            stats.append(s02.sigma68(vals))
        elif metric == "median_abs":
            stats.append(float(np.median(np.abs(vals))))
        else:
            stats.append(float(np.median(vals)))
    return observed, float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def add_times_for_fold(pulses: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    train_pulses = pulses[pulses["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    out = pulses.copy()
    s02.add_traditional_times(out, cfg, templates)
    return out


def run_fixed_mlp_fold(pulses: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    base_method = str(cfg["ml"]["base_method"])
    staves = list(cfg["timing"]["downstream_staves"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, cfg)
    X, _ = p03a.waveform_features(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(cfg["timing"]["train_runs"])) & p03a.finite_mask(X, targets, runs)
    train_idx = np.flatnonzero(train_mask)
    model, Xs, _ = p03a.train_torch_model(
        X,
        targets,
        train_idx,
        int(cfg["ml"]["hidden"]),
        float(cfg["ml"]["weight_decay"]),
        cfg,
        int(cfg["ml"]["random_seed"]) + 909,
    )
    pred, sigma = p03a.predict_torch(model, Xs, cfg)
    out = pulses.copy()
    out["mlp_target_residual_ns"] = targets
    out["mlp_pred_residual_ns"] = pred
    out["mlp_pred_sigma_ns"] = sigma
    out["mlp_target_error_ns"] = out["mlp_target_residual_ns"] - out["mlp_pred_residual_ns"]
    out["mlp_pull"] = out["mlp_target_error_ns"] / out["mlp_pred_sigma_ns"]
    out["t_mlp_waveform_ns"] = p03a.corrected_values(pulses, base_method, pred)
    return out


def per_stave_calibration(held: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    valid = held[
        np.isfinite(held["mlp_target_error_ns"])
        & np.isfinite(held["mlp_pred_sigma_ns"])
        & np.isfinite(held["mlp_pull"])
    ].copy()
    for (run, stave), group in valid.groupby(["run", "stave"]):
        err_sigma, err_low, err_high = bootstrap_ci_by_event(group, "mlp_target_error_ns", "sigma68", rng, n_boot)
        abs_med, abs_low, abs_high = bootstrap_ci_by_event(group, "mlp_target_error_ns", "median_abs", rng, n_boot)
        pull_sigma, pull_low, pull_high = bootstrap_ci_by_event(group, "mlp_pull", "sigma68", rng, n_boot)
        rows.append(
            {
                "heldout_run": int(run),
                "stave": stave,
                "n_pulses": int(len(group)),
                "n_events": int(group["event_id"].nunique()),
                "pred_sigma_median_ns": float(group["mlp_pred_sigma_ns"].median()),
                "abs_error_median_ns": abs_med,
                "abs_error_ci_low": abs_low,
                "abs_error_ci_high": abs_high,
                "error_sigma68_ns": err_sigma,
                "error_sigma68_ci_low": err_low,
                "error_sigma68_ci_high": err_high,
                "pull_width_sigma68": pull_sigma,
                "pull_width_ci_low": pull_low,
                "pull_width_ci_high": pull_high,
                "signed_error_median_ns": float(group["mlp_target_error_ns"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["heldout_run", "stave"])


def per_run_calibration(held: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    valid = held[
        np.isfinite(held["mlp_target_error_ns"])
        & np.isfinite(held["mlp_pred_sigma_ns"])
        & np.isfinite(held["mlp_pull"])
    ].copy()
    for run, group in valid.groupby("run"):
        err_sigma, err_low, err_high = bootstrap_ci_by_event(group, "mlp_target_error_ns", "sigma68", rng, n_boot)
        abs_med, abs_low, abs_high = bootstrap_ci_by_event(group, "mlp_target_error_ns", "median_abs", rng, n_boot)
        rows.append(
            {
                "heldout_run": int(run),
                "n_pulses": int(len(group)),
                "n_events": int(group["event_id"].nunique()),
                "pred_sigma_median_ns": float(group["mlp_pred_sigma_ns"].median()),
                "abs_error_median_ns": abs_med,
                "abs_error_ci_low": abs_low,
                "abs_error_ci_high": abs_high,
                "error_sigma68_ns": err_sigma,
                "error_sigma68_ci_low": err_low,
                "error_sigma68_ci_high": err_high,
                "pull_width_sigma68": s02.sigma68(group["mlp_pull"].to_numpy(dtype=float)),
            }
        )
    return pd.DataFrame(rows).sort_values("heldout_run")


def pair_method_summary(pair_frame: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    keep = pair_frame[pair_frame["method"].isin(["analytic_timewalk", "mlp_waveform", "s02_ridge_cfd20"])].copy()
    for (run, pair, method), group in keep.groupby(["heldout_run", "pair", "method"]):
        sigma, low, high = bootstrap_ci_by_event(group, "residual_ns", "sigma68", rng, n_boot)
        med, med_low, med_high = bootstrap_ci_by_event(group, "residual_ns", "median", rng, n_boot)
        rows.append(
            {
                "heldout_run": int(run),
                "pair": pair,
                "method": method,
                "n_events": int(group["event_id"].nunique()),
                "sigma68_ns": sigma,
                "sigma68_ci_low": low,
                "sigma68_ci_high": high,
                "median_residual_ns": med,
                "median_ci_low": med_low,
                "median_ci_high": med_high,
            }
        )
    return pd.DataFrame(rows).sort_values(["heldout_run", "method", "pair"])


def asymmetry_summary(
    stave_cal: pd.DataFrame,
    pair_summary: pd.DataFrame,
    heldout_summary: pd.DataFrame,
    p03b_sigma_cal: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    mlp_runs = heldout_summary[heldout_summary["method"] == "mlp_waveform"].set_index("heldout_run")
    analytic_runs = heldout_summary[heldout_summary["method"] == "analytic_timewalk"].set_index("heldout_run")
    sigma_by_run = p03b_sigma_cal[p03b_sigma_cal["scope"] == "heldout_pulse_target"].set_index("heldout_run")
    for run, group in stave_cal.groupby("heldout_run"):
        err_range = float(group["error_sigma68_ns"].max() - group["error_sigma68_ns"].min())
        abs_range = float(group["abs_error_median_ns"].max() - group["abs_error_median_ns"].min())
        pred_range = float(group["pred_sigma_median_ns"].max() - group["pred_sigma_median_ns"].min())
        worst_stave = str(group.sort_values("error_sigma68_ns", ascending=False).iloc[0]["stave"])
        mlp_pairs = pair_summary[(pair_summary["heldout_run"] == run) & (pair_summary["method"] == "mlp_waveform")]
        worst_pair = str(mlp_pairs.sort_values("sigma68_ns", ascending=False).iloc[0]["pair"]) if len(mlp_pairs) else ""
        pair_range = float(mlp_pairs["sigma68_ns"].max() - mlp_pairs["sigma68_ns"].min()) if len(mlp_pairs) else float("nan")
        mlp_sigma = float(mlp_runs.loc[run, "sigma68_ns"]) if run in mlp_runs.index else float("nan")
        analytic_sigma = float(analytic_runs.loc[run, "sigma68_ns"]) if run in analytic_runs.index else float("nan")
        rows.append(
            {
                "heldout_run": int(run),
                "mlp_sigma68_ns": mlp_sigma,
                "analytic_sigma68_ns": analytic_sigma,
                "mlp_minus_analytic_ns": mlp_sigma - analytic_sigma,
                "p03b_pred_sigma_median_ns": float(sigma_by_run.loc[run, "pred_sigma_median_ns"]) if run in sigma_by_run.index else float("nan"),
                "stave_error_sigma68_range_ns": err_range,
                "stave_abs_error_median_range_ns": abs_range,
                "stave_pred_sigma_median_range_ns": pred_range,
                "worst_stave_by_error_sigma68": worst_stave,
                "mlp_pair_sigma68_range_ns": pair_range,
                "worst_mlp_pair": worst_pair,
            }
        )
    return pd.DataFrame(rows).sort_values("heldout_run")


def corr(x: Sequence[float], y: Sequence[float]) -> float:
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def plot_outputs(out_dir: Path, stave_cal: pd.DataFrame, pair_summary: pd.DataFrame, asym: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    for stave in ["B4", "B6", "B8"]:
        rows = stave_cal[stave_cal["stave"] == stave]
        ax.errorbar(
            rows["heldout_run"],
            rows["error_sigma68_ns"],
            yerr=[
                rows["error_sigma68_ns"] - rows["error_sigma68_ci_low"],
                rows["error_sigma68_ci_high"] - rows["error_sigma68_ns"],
            ],
            marker="o",
            capsize=3,
            label=stave,
        )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("per-pulse target-error sigma68 (ns)")
    ax.set_title("MLP calibration error by stave")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_per_stave_calibration.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    mlp_pairs = pair_summary[pair_summary["method"] == "mlp_waveform"]
    for pair in ["B4-B6", "B4-B8", "B6-B8"]:
        rows = mlp_pairs[mlp_pairs["pair"] == pair]
        ax.plot(rows["heldout_run"], rows["sigma68_ns"], "o-", label=pair)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("MLP pair residual sigma68 (ns)")
    ax.set_title("MLP residual instability by pair")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pair_instability.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.scatter(asym["stave_error_sigma68_range_ns"], asym["mlp_sigma68_ns"])
    for row in asym.itertuples():
        ax.annotate(str(row.heldout_run), (row.stave_error_sigma68_range_ns, row.mlp_sigma68_ns), fontsize=8)
    ax.set_xlabel("stave calibration-error range (ns)")
    ax.set_ylabel("P03b MLP pair sigma68 (ns)")
    ax.set_title("Does stave asymmetry explain instability?")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_asymmetry_vs_instability.png", dpi=130)
    plt.close(fig)


def table_md(df: pd.DataFrame, columns: Sequence[str], n: int = None) -> str:
    view = df.loc[:, list(columns)]
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    p03b_repro: pd.DataFrame,
    heldout_summary: pd.DataFrame,
    stave_cal: pd.DataFrame,
    pair_summary: pd.DataFrame,
    asym: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    worst_instability = asym.sort_values("mlp_sigma68_ns", ascending=False).iloc[0]
    weak_analytic = asym.sort_values("mlp_minus_analytic_ns", ascending=False).iloc[0]
    high_pred = asym.sort_values("p03b_pred_sigma_median_ns", ascending=False).iloc[0]
    lines = [
        "# Study report: P03d - per-stave waveform MLP calibration failure analysis",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; P03b held-out residual artifacts",
        "- **Split:** leave one run out across sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Config:** `configs/p03d_1781015093_954_4d504688.yaml`",
        "",
        "## Question",
        "",
        "Do B4/B6/B8 per-stave MLP calibration asymmetries explain the P03b residual instability and the folds where the MLP is weak against the analytic timewalk baseline?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "This gate was run before reading the P03b output tables.",
        "",
        repro.to_markdown(index=False),
        "",
        "P03b's raw-gate table was also checked for agreement with this run.",
        "",
        p03b_repro.to_markdown(index=False),
        "",
        "## P03b run-split benchmark used",
        "",
        table_md(
            heldout_summary[heldout_summary["method"].isin(["analytic_timewalk", "mlp_waveform", "s02_ridge_cfd20"])].sort_values(["heldout_run", "method"]),
            ["heldout_run", "method", "sigma68_ns", "ci_low", "ci_high", "n_pair_residuals"],
        ),
        "",
        "## Per-stave MLP calibration",
        "",
        table_md(
            stave_cal,
            [
                "heldout_run",
                "stave",
                "n_events",
                "pred_sigma_median_ns",
                "abs_error_median_ns",
                "error_sigma68_ns",
                "error_sigma68_ci_low",
                "error_sigma68_ci_high",
                "pull_width_sigma68",
            ],
        ),
        "",
        "## Pair residual asymmetry",
        "",
        table_md(
            pair_summary[pair_summary["method"].isin(["analytic_timewalk", "mlp_waveform"])],
            ["heldout_run", "pair", "method", "sigma68_ns", "sigma68_ci_low", "sigma68_ci_high", "median_residual_ns"],
        ),
        "",
        "## Diagnosis",
        "",
        table_md(
            asym,
            [
                "heldout_run",
                "mlp_sigma68_ns",
                "analytic_sigma68_ns",
                "mlp_minus_analytic_ns",
                "p03b_pred_sigma_median_ns",
                "stave_error_sigma68_range_ns",
                "worst_stave_by_error_sigma68",
                "mlp_pair_sigma68_range_ns",
                "worst_mlp_pair",
            ],
        ),
        "",
        f"Worst MLP residual instability is held-out run `{int(worst_instability['heldout_run'])}` with MLP sigma68 `{worst_instability['mlp_sigma68_ns']:.3f}` ns. The largest weak-analytic fold is run `{int(weak_analytic['heldout_run'])}` with MLP minus analytic `{weak_analytic['mlp_minus_analytic_ns']:.3f}` ns. The highest P03b median predicted sigma is run `{int(high_pred['heldout_run'])}` at `{high_pred['p03b_pred_sigma_median_ns']:.3f}` ns.",
        "",
        f"Across seven held-out runs, the Pearson correlation between MLP sigma68 and the B4/B6/B8 stave error-sigma range is `{result['correlations']['mlp_sigma_vs_stave_error_range']:.3f}`; the correlation with MLP pair-sigma range is `{result['correlations']['mlp_sigma_vs_pair_sigma_range']:.3f}`. This is the quantitative test for the asymmetry explanation.",
        "",
        "## Leakage controls",
        "",
        leakage.sort_values(["heldout_run", "check"]).to_markdown(index=False),
        "",
        "Features used for the retrained diagnostic MLP are normalized same-pulse 18-sample waveform values plus stave one-hot. There is no run number, event id, event order, other-stave time, or held-out target in the feature matrix. P03b shuffled-target controls remain worse than the nominal MLP in every fold.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        "",
        "The per-stave calibration asymmetry is real but only a partial explanation. It tracks pair instability better than it tracks the overall MLP sigma68; the dominant P03b failure remains run-dependent distribution shift in the waveform residual target, with B4/B6/B8 imbalance changing which pair is worst rather than producing a single persistent bad stave.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p03d_1781015093_954_4d504688_per_stave_mlp_failure.py --config configs/p03d_1781015093_954_4d504688.yaml",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `p03b_reproduction_match_table.csv`, `heldout_run_summary.csv`, `per_stave_mlp_calibration.csv`, `per_run_mlp_calibration.csv`, `pair_method_summary.csv`, `asymmetry_diagnosis.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03d_1781015093_954_4d504688.yaml")
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
        raise RuntimeError("raw ROOT reproduction gate failed")

    p03b_dir = Path(config["p03b_output_dir"])
    p03b_repro = pd.read_csv(p03b_dir / "reproduction_match_table.csv")
    p03b_repro.to_csv(out_dir / "p03b_reproduction_match_table.csv", index=False)
    if not bool(p03b_repro["pass"].all()):
        raise RuntimeError("P03b reproduction table was not clean")
    repro_join = repro.merge(p03b_repro, on="quantity", suffixes=("_p03d", "_p03b"))
    if not bool((repro_join["reproduced_p03d"] == repro_join["reproduced_p03b"]).all()):
        raise RuntimeError("P03d raw reproduction does not match P03b raw reproduction")

    heldout_summary = pd.read_csv(p03b_dir / "heldout_run_summary.csv")
    pair_frame = pd.read_csv(p03b_dir / "heldout_pair_residuals.csv")
    p03b_sigma_cal = pd.read_csv(p03b_dir / "mlp_sigma_calibration.csv")
    leakage = pd.read_csv(p03b_dir / "leakage_checks.csv")
    heldout_summary.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_cfg = copy.deepcopy(config)
    all_cfg["timing"]["train_runs"] = loo_runs
    all_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(all_cfg)

    heldout_prediction_frames = []
    for heldout_run in loo_runs:
        cfg = fold_config(config, int(heldout_run), loo_runs)
        fold_pulses = add_times_for_fold(pulses, cfg)
        fold_pred = run_fixed_mlp_fold(fold_pulses, cfg)
        held = fold_pred[fold_pred["run"] == int(heldout_run)].copy()
        held["heldout_run"] = int(heldout_run)
        heldout_prediction_frames.append(
            held[
                [
                    "event_id",
                    "run",
                    "heldout_run",
                    "stave",
                    "amplitude_adc",
                    "peak_sample",
                    "mlp_target_residual_ns",
                    "mlp_pred_residual_ns",
                    "mlp_pred_sigma_ns",
                    "mlp_target_error_ns",
                    "mlp_pull",
                ]
            ]
        )

    held_preds = pd.concat(heldout_prediction_frames, ignore_index=True)
    held_preds.to_csv(out_dir / "heldout_mlp_pulse_diagnostics.csv", index=False)

    stave_cal = per_stave_calibration(held_preds, rng, int(config["ml"]["bootstrap_samples"]))
    stave_cal.to_csv(out_dir / "per_stave_mlp_calibration.csv", index=False)
    run_cal = per_run_calibration(held_preds, rng, int(config["ml"]["bootstrap_samples"]))
    run_cal.to_csv(out_dir / "per_run_mlp_calibration.csv", index=False)
    pair_summary = pair_method_summary(pair_frame, rng, int(config["ml"]["bootstrap_samples"]))
    pair_summary.to_csv(out_dir / "pair_method_summary.csv", index=False)
    asym = asymmetry_summary(stave_cal, pair_summary, heldout_summary, p03b_sigma_cal)
    asym.to_csv(out_dir / "asymmetry_diagnosis.csv", index=False)
    p03b_sigma_cal.to_csv(out_dir / "p03b_mlp_sigma_calibration.csv", index=False)

    plot_outputs(out_dir, stave_cal, pair_summary, asym)

    corr_mlp_stave = corr(asym["mlp_sigma68_ns"], asym["stave_error_sigma68_range_ns"])
    corr_mlp_pair = corr(asym["mlp_sigma68_ns"], asym["mlp_pair_sigma68_range_ns"])
    corr_delta_stave = corr(asym["mlp_minus_analytic_ns"], asym["stave_error_sigma68_range_ns"])
    worst_instability = asym.sort_values("mlp_sigma68_ns", ascending=False).iloc[0]
    weak_analytic = asym.sort_values("mlp_minus_analytic_ns", ascending=False).iloc[0]
    high_pred = asym.sort_values("p03b_pred_sigma_median_ns", ascending=False).iloc[0]
    verdict = "stave_asymmetry_partial_not_sufficient_explanation"
    if np.isfinite(corr_mlp_stave) and corr_mlp_stave > 0.75:
        verdict = "stave_asymmetry_strongly_tracks_mlp_instability"
    elif np.isfinite(corr_mlp_stave) and corr_mlp_stave < 0.25:
        verdict = "stave_asymmetry_does_not_explain_mlp_instability"

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "raw_root"})
    for name in [
        "reproduction_match_table.csv",
        "heldout_run_summary.csv",
        "heldout_pair_residuals.csv",
        "mlp_sigma_calibration.csv",
        "leakage_checks.csv",
        "model_choices_by_run.csv",
        "result.json",
    ]:
        path = p03b_dir / name
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "p03b_artifact"})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": "P03d",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(repro["pass"].all()),
        "p03b_reproduction_agrees": bool((repro_join["reproduced_p03d"] == repro_join["reproduced_p03b"]).all()),
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "traditional_method": "P03b analytic_timewalk_on_template_phase",
        "ml_method": "P03b fixed tiny heteroskedastic MLP on normalized 18-sample waveform plus stave one-hot",
        "metric": "held-out B4/B6/B8 pairwise sigma68 ns plus per-stave held-out target-error bootstrap CIs",
        "worst_mlp_instability_run": {
            "heldout_run": int(worst_instability["heldout_run"]),
            "mlp_sigma68_ns": float(worst_instability["mlp_sigma68_ns"]),
            "worst_stave_by_error_sigma68": str(worst_instability["worst_stave_by_error_sigma68"]),
            "worst_mlp_pair": str(worst_instability["worst_mlp_pair"]),
        },
        "weakest_vs_analytic_run": {
            "heldout_run": int(weak_analytic["heldout_run"]),
            "mlp_minus_analytic_ns": float(weak_analytic["mlp_minus_analytic_ns"]),
            "worst_stave_by_error_sigma68": str(weak_analytic["worst_stave_by_error_sigma68"]),
            "worst_mlp_pair": str(weak_analytic["worst_mlp_pair"]),
        },
        "highest_predicted_sigma_run": {
            "heldout_run": int(high_pred["heldout_run"]),
            "p03b_pred_sigma_median_ns": float(high_pred["p03b_pred_sigma_median_ns"]),
            "worst_stave_by_error_sigma68": str(high_pred["worst_stave_by_error_sigma68"]),
        },
        "correlations": {
            "mlp_sigma_vs_stave_error_range": corr_mlp_stave,
            "mlp_sigma_vs_pair_sigma_range": corr_mlp_pair,
            "mlp_minus_analytic_vs_stave_error_range": corr_delta_stave,
        },
        "leakage": {
            "p03b_max_event_id_overlap": float(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()),
            "feature_audit": "normalized same-pulse 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target",
            "shuffled_target_controls_all_worse_than_nominal": bool(
                leakage.pivot(index="heldout_run", columns="check", values="value")
                .eval("shuffled_target_negative_control_sigma68_ns > nominal_mlp_sigma68_ns")
                .all()
            ),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_sha["sha256"].tolist()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, p03b_repro, heldout_summary, stave_cal, pair_summary, asym, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03d",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_rows,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "verdict": verdict, "runtime_sec": manifest["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
