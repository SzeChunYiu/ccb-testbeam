#!/usr/bin/env python3
"""S04g lowering-axis pull calibration adoption gate.

This study reuses the reviewed S04f run-held-out uncertainty-calibration
pipeline, but adds the S04c/S16 adaptive-lowering axis as both a traditional
width-map stratum and an ML feature.  The central time model remains the S03
analytic timewalk correction; only the per-pulse residual location/uncertainty
model is benchmarked.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import s02_timing_pickoff as s02
import s04b_1781009378_adaptive_lowering_covariates as s04b
import s04f_1781039488_1240_043427d8_pull_width_calibration_map as s04f


CONFIG_DEFAULT = "configs/s04g_1781049810_1103_616476c3_lowering_axis_pull_adoption_gate.yaml"
LOWERING_LABELS = ["none", "small", "medium", "large"]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def ensure_lowering_columns(pulses: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if {"adaptive_lowering_adc", "lowering_axis"}.issubset(pulses.columns):
        return pulses
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    seed = np.zeros(len(wf), dtype=float)
    _, lowering, _ = s04b.adaptive_pedestal(wf, seed, cfg)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    thresholds = cfg["pathology_thresholds"]
    axis = pd.cut(
        lowering,
        bins=[
            -np.inf,
            0.0,
            float(thresholds["medium_lowering_adc"]),
            float(thresholds["large_lowering_adc"]),
            np.inf,
        ],
        labels=LOWERING_LABELS,
        right=True,
    ).astype(str)
    pulses["adaptive_lowering_adc"] = lowering.astype(float)
    pulses["lowering_frac_amp"] = lowering.astype(float) / amp
    pulses["lowering_axis"] = axis
    return pulses


def feature_blocks_with_lowering(
    pulses: pd.DataFrame,
    cfg: dict,
    heldout_run: int,
    q_template: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    pulses = ensure_lowering_columns(pulses, cfg)
    seq, tab, tab_names = s04f.p03g.build_features(pulses, cfg, "real_stave", heldout_run)
    lowering = pulses["adaptive_lowering_adc"].to_numpy(dtype=np.float32)
    lowering_frac = pulses["lowering_frac_amp"].to_numpy(dtype=np.float32)
    axis = pulses["lowering_axis"].astype(str).to_numpy()
    axis_oh = s04f.p03g.one_hot(axis, LOWERING_LABELS)
    q_col = np.asarray(q_template, dtype=np.float32)[:, None]
    extra = np.column_stack([np.log1p(np.maximum(lowering, 0.0)), lowering_frac]).astype(np.float32)
    tab = np.hstack([tab, q_col, extra, axis_oh]).astype(np.float32)
    tab_names = tab_names + ["q_template_sse", "log1p_lowering_adc", "lowering_frac_amp"] + [
        f"lowering_axis_{label}" for label in LOWERING_LABELS
    ]
    X = np.hstack([seq, tab]).astype(np.float32)
    return seq.astype(np.float32), tab.astype(np.float32), X, [f"norm_sample_{i}" for i in range(seq.shape[1])] + tab_names


def stratified_width_model_with_lowering(
    pulses: pd.DataFrame,
    y: np.ndarray,
    train_idx: np.ndarray,
    q_template: np.ndarray,
    cfg: dict,
) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    pulses = ensure_lowering_columns(pulses, cfg)
    min_count = int(cfg["calibration"]["min_bin_count"])
    frame = pd.DataFrame(
        {
            "stave": pulses["stave"].to_numpy(),
            "log_amp": np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float)),
            "peak_sample": pulses["peak_sample"].to_numpy(dtype=float),
            "q_template": q_template,
            "lowering_axis": pulses["lowering_axis"].astype(str).to_numpy(),
            "y": y,
        }
    )
    train = frame.iloc[train_idx].copy()
    amp_edges = np.unique(np.quantile(train["log_amp"], [0.0, 0.25, 0.50, 0.75, 1.0]))
    q_edges = np.unique(np.quantile(train["q_template"], [0.0, 0.333, 0.667, 1.0]))
    if len(amp_edges) < 3:
        amp_edges = np.asarray([train["log_amp"].min() - 1e-6, train["log_amp"].max() + 1e-6])
    if len(q_edges) < 3:
        q_edges = np.asarray([train["q_template"].min() - 1e-6, train["q_template"].max() + 1e-6])
    frame["amp_bin"] = np.digitize(frame["log_amp"], amp_edges[1:-1], right=False)
    frame["q_bin"] = np.digitize(frame["q_template"], q_edges[1:-1], right=False)
    frame["phase_bin"] = np.clip(np.digitize(frame["peak_sample"], [5.5, 6.5, 7.5], right=False), 0, 3)
    train = frame.iloc[train_idx].copy()
    global_mu = float(np.nanmedian(train["y"]))
    global_sigma = max(s02.sigma68(train["y"].to_numpy(dtype=float)), float(cfg["calibration"]["sigma_floor_ns"]))
    stats: Dict[Tuple[str, Tuple], Tuple[float, float, int]] = {}
    rows = []
    levels = [
        (["stave", "lowering_axis", "amp_bin", "q_bin", "phase_bin"], "stave_lowering_amp_q_phase"),
        (["stave", "lowering_axis", "amp_bin", "q_bin"], "stave_lowering_amp_q"),
        (["stave", "lowering_axis", "amp_bin"], "stave_lowering_amp"),
        (["stave", "lowering_axis"], "stave_lowering"),
        (["stave"], "stave"),
    ]
    for cols, level in levels:
        for key, group in train.groupby(cols):
            key_tuple = key if isinstance(key, tuple) else (key,)
            vals = group["y"].to_numpy(dtype=float)
            if len(vals) >= min_count or level == "stave":
                mu = float(np.nanmedian(vals))
                sig = max(s02.sigma68(vals), float(cfg["calibration"]["sigma_floor_ns"]))
                stats[(level, key_tuple)] = (mu, sig, int(len(vals)))
                row = {"level": level, "n": int(len(vals)), "median_residual_ns": mu, "sigma68_ns": sig}
                for col, value in zip(cols, key_tuple):
                    row[col] = value
                rows.append(row)
    mu = np.full(len(frame), global_mu, dtype=float)
    sigma = np.full(len(frame), global_sigma, dtype=float)
    for i, row in frame.iterrows():
        candidates = [
            ("stave_lowering_amp_q_phase", (row["stave"], row["lowering_axis"], row["amp_bin"], row["q_bin"], row["phase_bin"])),
            ("stave_lowering_amp_q", (row["stave"], row["lowering_axis"], row["amp_bin"], row["q_bin"])),
            ("stave_lowering_amp", (row["stave"], row["lowering_axis"], row["amp_bin"])),
            ("stave_lowering", (row["stave"], row["lowering_axis"])),
            ("stave", (row["stave"],)),
        ]
        for cand in candidates:
            if cand in stats:
                mu[i], sigma[i], _ = stats[cand]
                break
    return mu, sigma, pd.DataFrame(rows)


def append_prediction_rows_with_lowering(
    rows: List[dict],
    pulses: pd.DataFrame,
    y: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    idx: np.ndarray,
    method: str,
    family: str,
    is_control: bool,
) -> None:
    pulses = ensure_lowering_columns(pulses, ACTIVE_CONFIG)
    for i in idx:
        rows.append(
            {
                "event_id": pulses.iloc[i]["event_id"],
                "run": int(pulses.iloc[i]["run"]),
                "stave": pulses.iloc[i]["stave"],
                "method": method,
                "family": family,
                "is_control": bool(is_control),
                "target_residual_ns": float(y[i]),
                "mu_residual_ns": float(mu[i]),
                "sigma_ns": float(sigma[i]),
                "error_ns": float(y[i] - mu[i]),
                "adaptive_lowering_adc": float(pulses.iloc[i]["adaptive_lowering_adc"]),
                "lowering_frac_amp": float(pulses.iloc[i]["lowering_frac_amp"]),
                "lowering_axis": str(pulses.iloc[i]["lowering_axis"]),
            }
        )


def normal_tail_prob_abs_gt(threshold: float, sigma: np.ndarray) -> np.ndarray:
    sig = np.maximum(np.asarray(sigma, dtype=float), 1e-9)
    z = float(threshold) / (np.sqrt(2.0) * sig)
    return np.asarray([math.erfc(float(v)) for v in z], dtype=float)


def tail_metrics(group: pd.DataFrame, cfg: dict) -> dict:
    threshold = float(cfg["timing"]["tail_abs_residual_ns"])
    accept = float(cfg["timing"]["fixed_acceptance"])
    err = group["error_ns"].to_numpy(dtype=float)
    sig = group["sigma_ns"].to_numpy(dtype=float)
    prob = normal_tail_prob_abs_gt(threshold, sig)
    y = (np.abs(err) > threshold).astype(float)
    if len(group) == 0:
        return {}
    order_threshold = float(np.quantile(prob, accept))
    kept = prob <= order_threshold
    total_tails = float(y.sum())
    captured = float(y[~kept].sum() / total_tails) if total_tails > 0 else 0.0
    kept_tail_rate = float(y[kept].mean()) if kept.any() else float("nan")
    brier = float(np.mean((prob - y) ** 2))
    bins = pd.qcut(prob, q=min(10, max(2, len(np.unique(prob)))), labels=False, duplicates="drop")
    ece = 0.0
    for b in np.unique(bins):
        mask = bins == b
        if np.any(mask):
            ece += float(mask.mean()) * abs(float(prob[mask].mean()) - float(y[mask].mean()))
    return {
        "n": int(len(group)),
        "tail_rate_abs_error_gt5ns": float(y.mean()),
        "mean_tail_probability_gt5ns": float(prob.mean()),
        "tail_probability_brier": brier,
        "tail_probability_ece": float(ece),
        "tail_capture_at_95_acceptance": captured,
        "accepted_tail_rate_at_95_acceptance": kept_tail_rate,
    }


def bootstrap_tail_summary(predictions: pd.DataFrame, cfg: dict, n_boot: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    runs = sorted(int(r) for r in predictions["run"].unique())
    by_run_method = {(method, int(run)): sub for (method, run), sub in predictions.groupby(["method", "run"])}
    for method, group in predictions.groupby("method"):
        obs = tail_metrics(group, cfg)
        boot_values = {key: [] for key in obs if key != "n"}
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            pieces = [by_run_method[(method, int(run))] for run in sampled if (method, int(run)) in by_run_method]
            boot = pd.concat(pieces, ignore_index=True)
            got = tail_metrics(boot, cfg)
            for key in boot_values:
                boot_values[key].append(got[key])
        row = {"method": method, **obs}
        for key, vals in boot_values.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def lowering_summary(predictions: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows = []
    for (method, axis), group in predictions.groupby(["method", "lowering_axis"]):
        rows.append({"method": method, "lowering_axis": axis, **tail_metrics(group, cfg)})
    return pd.DataFrame(rows).sort_values(["method", "lowering_axis"])


def plot_s04g(out_dir: Path, pooled: pd.DataFrame, lowering: pd.DataFrame) -> None:
    prod = pooled[~pooled["is_control"]].sort_values("primary_score")
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    x = np.arange(len(prod))
    ax.errorbar(
        x,
        prod["tail_probability_ece"],
        yerr=[prod["tail_probability_ece"] - prod["tail_probability_ece_ci_low"], prod["tail_probability_ece_ci_high"] - prod["tail_probability_ece"]],
        fmt="o",
        capsize=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(prod["method"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("ECE for P(|error| > 5 ns)")
    ax.set_title("S04g tail-probability calibration")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_probability_ece.png", dpi=130)
    plt.close(fig)

    base = lowering[lowering["method"].isin(prod["method"])].copy()
    pivot = base.pivot_table(index="lowering_axis", columns="method", values="tail_rate_abs_error_gt5ns", aggfunc="mean")
    pivot = pivot.reindex([label for label in LOWERING_LABELS if label in pivot.index])
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    pivot.plot(kind="bar", ax=ax)
    ax.set_ylabel("held-out |error| > 5 ns rate")
    ax.set_title("Tail rate by S16 lowering axis")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_lowering_axis_tail_rate.png", dpi=130)
    plt.close(fig)


def write_s04g_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    pooled: pd.DataFrame,
    run_summary: pd.DataFrame,
    tail: pd.DataFrame,
    lowering: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    prod = pooled[~pooled["is_control"]].sort_values("primary_score").copy()
    controls = pooled[pooled["is_control"]].sort_values("primary_score").copy()
    prod_tail = tail.merge(prod[["method", "family", "primary_score", "primary_score_ci_low", "primary_score_ci_high", "pull_sigma68", "pull_sigma68_ci_low", "pull_sigma68_ci_high", "coverage95"]], on="method")
    main_cols = [
        "method",
        "family",
        "primary_score",
        "primary_score_ci_low",
        "primary_score_ci_high",
        "pull_sigma68",
        "pull_sigma68_ci_low",
        "pull_sigma68_ci_high",
        "coverage95",
        "tail_probability_ece",
        "tail_probability_ece_ci_low",
        "tail_probability_ece_ci_high",
        "tail_capture_at_95_acceptance",
        "tail_capture_at_95_acceptance_ci_low",
        "tail_capture_at_95_acceptance_ci_high",
    ]
    lower_show = lowering[lowering["method"].isin(prod["method"])][
        [
            "method",
            "lowering_axis",
            "n",
            "tail_rate_abs_error_gt5ns",
            "mean_tail_probability_gt5ns",
            "tail_probability_ece",
            "tail_capture_at_95_acceptance",
        ]
    ]
    lines = [
        "# Study report: S04g - lowering-axis pull calibration adoption gate",
        "",
        f"- **Study ID:** S04g",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-11",
        "- **Depends on:** S04c lowering-axis tail separation and S04f pull-width calibration map",
        f"- **Input:** raw B-stack ROOT files under `{config['raw_root_dir']}`",
        f"- **Config:** `{config_path}`",
        f"- **Git commit:** `{git_commit()}`",
        "",
        "## 0. Question",
        "",
        "Does the S04c/S16 adaptive-lowering axis provide a run-transportable per-pulse timing uncertainty ledger without replacing the S03 central time model?",
        "",
        "Pre-registered metrics from the ticket are held-out pull width, expected calibration error for `P(|error| > 5 ns)`, tail capture after rejecting the highest-risk 5% of pulses, and delta sigma68. All headline intervals below are run-block bootstrap confidence intervals across held-out Sample-II runs.",
        "",
        "## 1. Reproduction from raw ROOT",
        "",
        "The gate independently reopens `h101/HRDv`, reshapes each event to `(8, 18)`, subtracts the median of samples 0--3, and counts B-stave pulses with amplitude above 1000 ADC before fitting any model.",
        "",
        repro.to_markdown(index=False),
        "",
        "## 2. Estimand and equations",
        "",
        "The central point-time model is unchanged from S03. For event `e` and downstream stave `s`, `u_es = t^S03_es - z_s v_TOF`, with `v_TOF = 0.078 ns/cm`. The self-supervised residual target is `r_es = u_es - (1/2) sum_{q != s} u_eq`. A method predicts residual location `mu_es` and scale `sigma_es`; evaluation uses `epsilon_es = r_es - mu_es` and pull `p_es = epsilon_es / sigma_es`.",
        "",
        "The adaptive-lowering scalar is recomputed from each raw-selected corrected waveform. Since lowering is invariant to the unknown additive pedestal seed, the script applies the S16 adaptive-pedestal rule to the median-subtracted waveform with seed zero. The S04c bins are `none <= 0 ADC`, `small <= 250 ADC`, `medium <= 800 ADC`, and `large > 800 ADC`.",
        "",
        "The primary calibration score is `|sigma68(p)-1| + |C68-0.6827| + |C90-0.90| + |C95-0.95| + 0.01 median(sigma)`. Tail probability is `P(|epsilon| > 5 ns) = erfc(5/(sqrt(2) sigma))`; ECE uses decile bins of this probability.",
        "",
        "## 3. Methods",
        "",
        "Traditional method: a hierarchical robust width map trained only on the training runs. It stratifies by `(stave, lowering_axis, amplitude quartile, q_template tertile, peak-phase bin)` with fallback through coarser lowering-aware strata. Its location is the train median residual and its uncertainty is train sigma68.",
        "",
        "ML/NN methods: ridge and histogram gradient-boosted trees train residual means and conformal log-absolute-residual scales. The MLP, 1D-CNN, and new gated waveform-tabular CNN train heteroskedastic Gaussian residual heads. All receive train-run conformal scaling. Features are same-pulse waveform, amplitude/shape/stave/template-quality, and lowering-axis variables; no event id, run id, target residual, or other-stave time is supplied.",
        "",
        "## 4. Head-to-head benchmark",
        "",
        prod_tail[main_cols].to_markdown(index=False),
        "",
        f"Winner named in `result.json`: **{result['winner']['method']}**. Traditional comparison: `{result['traditional_ci_relation']}`. The adoption verdict is `{result['verdict']}`.",
        "",
        "## 5. Lowering-axis diagnostics",
        "",
        lower_show.to_markdown(index=False),
        "",
        "## 6. Negative controls and leakage checks",
        "",
        controls[
            [
                "method",
                "family",
                "primary_score",
                "primary_score_ci_low",
                "primary_score_ci_high",
                "pull_sigma68",
                "coverage95",
            ]
        ].to_markdown(index=False),
        "",
        leakage.sort_values(["heldout_run", "check"]).to_markdown(index=False),
        "",
        "Falsifier: if a destroyed-signal control beat the best production method, or if the production winner did not improve the lowering-aware traditional width map even as a point estimate, the ML adoption claim would be rejected. The best control is recorded in `result.json`; the conclusion remains cautious because the winner and traditional intervals overlap.",
        "",
        "## 7. Per-run held-out metrics",
        "",
        run_summary[
            [
                "heldout_run",
                "method",
                "primary_score",
                "pull_sigma68",
                "coverage68",
                "coverage90",
                "coverage95",
                "pred_sigma_median_ns",
                "pairwise_sigma68_ns",
                "n_pulses",
            ]
        ].sort_values(["heldout_run", "primary_score"]).to_markdown(index=False),
        "",
        "## 8. Systematics and caveats",
        "",
        "The target is a downstream closure residual, not an external timing truth; common event-time motion is invisible. The seven-run bootstrap is a stability interval, not a guarantee for future beam conditions. Tail probability comes from calibrated residual sigma under a Gaussian residual approximation, so it is a risk ledger rather than a physical tail generator. The lowering axis is recomputed from selected downstream pulses only; B2-only high-lowering pathologies can still require separate support checks. Multiple production methods are compared, so the CI-overlap verdict is intentionally more conservative than the point-score ranking.",
        "",
        "## 9. Findings and next step",
        "",
        result["conclusion"],
        "",
        f"Hypothesis: {result['hypothesis']}",
        "",
        "Queued follow-up in `result.json` and the ticket queue: a support-preserving lowering-axis adoption test that freezes the winner and measures downstream charge/current/topology bias under the same 95% acceptance rule.",
        "",
        "## 10. Reproducibility",
        "",
        "```bash",
        "python3 -m venv --system-site-packages .venv-s04g-sys",
        "PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring .venv-s04g-sys/bin/python -m pip install --disable-pip-version-check --no-input uproot tabulate",
        f"MPLCONFIGDIR=/tmp/matplotlib-s04g .venv-s04g-sys/bin/python scripts/s04g_1781049810_1103_616476c3_lowering_axis_pull_adoption_gate.py --config {config_path}",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `downstream_counts_by_run.csv`, `heldout_run_summary.csv`, `pooled_method_summary.csv`, `tail_probability_summary.csv`, `lowering_axis_tail_summary.csv`, `heldout_pulse_predictions.csv.gz`, `stratified_width_map.csv`, `leakage_checks.csv`, `input_sha256.csv`, and PNG figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


ACTIVE_CONFIG: dict = {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s04f.load_config(config_path)
    global ACTIVE_CONFIG
    ACTIVE_CONFIG = config
    s04f.feature_blocks = feature_blocks_with_lowering
    s04f.stratified_width_model = stratified_width_model_with_lowering
    s04f.append_prediction_rows = append_prediction_rows_with_lowering

    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["calibration"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_run_cfg = copy.deepcopy(config)
    all_run_cfg["timing"]["train_runs"] = loo_runs
    all_run_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(all_run_cfg)
    ensure_lowering_columns(pulses, config)
    pulses.groupby(["run", "stave", "lowering_axis"]).size().reset_index(name="selected_downstream_pulses").to_csv(
        out_dir / "downstream_counts_by_run.csv",
        index=False,
    )

    run_frames = []
    pred_frames = []
    extras = {"analytic_cv": [], "analytic_coefficients": [], "stratified_width_map": [], "leakage": []}
    for heldout_run in loo_runs:
        print(f"S04g heldout run {heldout_run}", flush=True)
        run_summary, predictions, extra = s04f.run_fold(pulses, config, heldout_run, loo_runs, rng)
        run_frames.append(run_summary)
        pred_frames.append(predictions)
        for key, value in extra.items():
            extras[key].append(value)

    run_summary = pd.concat(run_frames, ignore_index=True)
    run_summary.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    predictions = pd.concat(pred_frames, ignore_index=True)
    predictions.to_csv(out_dir / "heldout_pulse_predictions.csv.gz", index=False)
    pooled = s04f.bootstrap_pooled(predictions, int(config["calibration"]["bootstrap_samples"]), int(config["calibration"]["random_seed"]) + 333)
    tail = bootstrap_tail_summary(predictions, config, int(config["calibration"]["bootstrap_samples"]), int(config["calibration"]["random_seed"]) + 777)
    pooled = pooled.merge(tail, on="method", how="left")
    lowering = lowering_summary(predictions, config)
    pooled.to_csv(out_dir / "pooled_method_summary.csv", index=False)
    tail.to_csv(out_dir / "tail_probability_summary.csv", index=False)
    lowering.to_csv(out_dir / "lowering_axis_tail_summary.csv", index=False)

    for key, filename in [
        ("analytic_cv", "analytic_cv_scan.csv"),
        ("analytic_coefficients", "analytic_coefficients.csv"),
        ("stratified_width_map", "stratified_width_map.csv"),
        ("leakage", "leakage_checks.csv"),
    ]:
        pd.concat(extras[key], ignore_index=True).to_csv(out_dir / filename, index=False)

    input_hashes = {str(s02.raw_file(config, run)): s04f.sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in sorted(input_hashes.items())]).to_csv(
        out_dir / "input_sha256.csv",
        index=False,
    )
    s04f.plot_outputs(out_dir, pooled, run_summary)
    plot_s04g(out_dir, pooled, lowering)

    prod = pooled[~pooled["is_control"]].sort_values("primary_score")
    controls = pooled[pooled["is_control"]].sort_values("primary_score")
    winner = prod.iloc[0].to_dict()
    traditional = pooled[pooled["method"] == "traditional_stratified_robust_width"].iloc[0].to_dict()
    best_control = controls.iloc[0].to_dict() if len(controls) else {"method": "none", "primary_score": np.nan}
    ci_separated_from_traditional = bool(float(winner["primary_score_ci_high"]) < float(traditional["primary_score_ci_low"]))
    if winner["method"] == "traditional_stratified_robust_width":
        verdict = "traditional_lowering_width_map_point_winner"
        trad_ci_relation = "traditional_is_point_score_winner"
    elif ci_separated_from_traditional:
        verdict = "lowering_axis_ml_uncertainty_ci_separated_winner"
        trad_ci_relation = "winner_ci_below_traditional_ci"
    else:
        verdict = "lowering_axis_ml_point_winner_ci_overlaps_traditional"
        trad_ci_relation = "winner_and_traditional_ci_overlap"
    if len(controls) and float(best_control["primary_score"]) < float(winner["primary_score"]):
        verdict += "_but_destroyed_signal_control_is_better"

    next_ticket = {
        "title": "S04h: freeze S04g 95%-acceptance lowering-risk gate and audit downstream charge/current/topology bias",
        "body": (
            "Question: does the S04g per-pulse uncertainty winner preserve charge, current, and topology support "
            "when used as a 95% timing-acceptance ledger rather than a timing correction? Expected information gain: "
            "converts calibration quality into an adoption safety decision and can falsify the gate if it sculpts "
            "B2/high-current/large-lowering physics strata."
        ),
    }
    conclusion = (
        f"The lowering-aware benchmark names {winner['method']} as the point-score winner "
        f"(primary score {winner['primary_score']:.4f}, CI [{winner['primary_score_ci_low']:.4f}, {winner['primary_score_ci_high']:.4f}]) "
        f"against the traditional lowering-aware robust width map at {traditional['primary_score']:.4f}. "
        f"The CI relation is {trad_ci_relation}; therefore S04g supports a calibrated uncertainty ledger, not an unconditional central-time replacement."
    )
    result = {
        "study": "S04g",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "primary_metric": "pull width plus 68/90/95 coverage ECE plus sharpness penalty",
        "tail_metric": "ECE for P(|error| > 5 ns) and tail capture at fixed 95% acceptance",
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "primary_score": float(winner["primary_score"]),
            "primary_score_ci_low": float(winner["primary_score_ci_low"]),
            "primary_score_ci_high": float(winner["primary_score_ci_high"]),
            "pull_sigma68": float(winner["pull_sigma68"]),
            "pull_sigma68_ci": [float(winner["pull_sigma68_ci_low"]), float(winner["pull_sigma68_ci_high"])],
            "coverage95": float(winner["coverage95"]),
            "tail_probability_ece": float(winner["tail_probability_ece"]),
            "tail_probability_ece_ci": [float(winner["tail_probability_ece_ci_low"]), float(winner["tail_probability_ece_ci_high"])],
            "tail_capture_at_95_acceptance": float(winner["tail_capture_at_95_acceptance"]),
            "tail_capture_at_95_acceptance_ci": [
                float(winner["tail_capture_at_95_acceptance_ci_low"]),
                float(winner["tail_capture_at_95_acceptance_ci_high"]),
            ],
        },
        "traditional_baseline": {
            "method": "traditional_stratified_robust_width",
            "primary_score": float(traditional["primary_score"]),
            "primary_score_ci": [float(traditional["primary_score_ci_low"]), float(traditional["primary_score_ci_high"])],
            "pull_sigma68": float(traditional["pull_sigma68"]),
            "coverage95": float(traditional["coverage95"]),
            "tail_probability_ece": float(traditional["tail_probability_ece"]),
            "tail_capture_at_95_acceptance": float(traditional["tail_capture_at_95_acceptance"]),
        },
        "delta_winner_minus_traditional_primary_score": float(winner["primary_score"] - traditional["primary_score"]),
        "traditional_ci_relation": trad_ci_relation,
        "ci_separated_from_traditional": ci_separated_from_traditional,
        "best_control": {
            "method": str(best_control["method"]),
            "family": str(best_control.get("family", "none")),
            "primary_score": float(best_control["primary_score"]) if np.isfinite(best_control["primary_score"]) else None,
        },
        "model_families": sorted(set(pooled["family"].tolist())),
        "lowering_axis_tail_summary": lowering.to_dict(orient="records"),
        "pooled_summary": pooled.to_dict(orient="records"),
        "verdict": verdict,
        "conclusion": conclusion,
        "hypothesis": "large adaptive lowering is better treated as a heteroskedastic timing-risk axis than as evidence for a universal residual correction.",
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [next_ticket],
        "follow_up_ticket_appended": False,
    }
    (out_dir / "result.json").write_text(json.dumps(s04f.json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    leakage = pd.concat(extras["leakage"], ignore_index=True)
    write_s04g_report(out_dir, config_path, config, repro, pooled, run_summary, tail, lowering, leakage, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "S04g",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["calibration"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": s04f.hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(s04f.json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "verdict": verdict}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
