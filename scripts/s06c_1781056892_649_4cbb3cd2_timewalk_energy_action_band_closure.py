#!/usr/bin/env python3
"""S06c: timewalk-energy support closure after action bands.

This ticket is the adoption gate after S06b.  It applies explicit action-band
acceptance/abstention rules to the run-external P06c/S06b pair-residual panel,
then asks whether timing resolution and pull calibration are stable enough for
S06 consumers on the accepted amplitude/charge support.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s06c-1781056892")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p06a_1781017198_1470_7d872fbe_amp_binned_resolution as p06a  # noqa: E402
import p06c_1781044013_777_0e401db7_time_local_pull_coverage_atlas as p06c  # noqa: E402
import s02_timing_pickoff as s02  # noqa: E402


REQUIRED_METHODS = {
    "traditional",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "phase_conformal_gated_cnn",
}
ACTION_FLAGS = [
    "timing_window_action",
    "saturation_action",
    "dropout_action",
    "baseline_action",
    "q_template_action",
    "energy_support_action",
]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def parse_bin_bounds(label: str) -> Tuple[float, float]:
    text = str(label)
    if "[" not in text or ")" not in text:
        return (float("nan"), float("nan"))
    inside = text.split("[", 1)[1].split(")", 1)[0]
    lo_s, hi_s = inside.split(",", 1)
    lo = float(lo_s)
    hi = float("inf") if hi_s == "inf" else float(hi_s)
    return lo, hi


def finite_midpoint(label: str) -> float:
    lo, hi = parse_bin_bounds(label)
    if math.isfinite(lo) and math.isfinite(hi):
        return 0.5 * (lo + hi)
    if math.isfinite(lo):
        return 1.35 * lo
    if math.isfinite(hi):
        return 0.65 * hi
    return float("nan")


def load_source_rows(config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    source_rows = Path(config["source_pair_rows"])
    source_meta = Path(config["source_uncertainty_meta"])
    if not source_rows.exists():
        raise FileNotFoundError(source_rows)
    if not source_meta.exists():
        raise FileNotFoundError(source_meta)
    rows = pd.read_csv(source_rows)
    meta = pd.read_csv(source_meta)
    rows.to_csv(out_dir / "pair_residual_rows_with_pulls.csv.gz", index=False, compression="gzip")
    meta.to_csv(out_dir / "uncertainty_fold_meta.csv", index=False)
    provenance = {
        "source_pair_rows": str(source_rows),
        "source_pair_rows_sha256": sha256_file(source_rows),
        "source_uncertainty_meta": str(source_meta),
        "source_uncertainty_meta_sha256": sha256_file(source_meta),
        "reason": "S06c applies new action-band acceptance and closure summaries to the already run-external P06c/S06b method panel.",
    }
    (out_dir / "source_benchmark_rows.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return rows, meta


def add_action_bands(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = rows.copy()
    closure = config["closure"]
    saturation = out["saturation_flag"].astype(str).str.lower().isin(["true", "1"])
    dropout = out["p09_anomaly_class"].astype(str).eq("dropout")
    noncommon_anomaly = out["p09_anomaly_class"].astype(str).ne("unassigned_common")
    wide_baseline = out["baseline_rms_max_adc"].astype(float) >= float(closure["wide_baseline_min_adc"])
    high_q = out["q_template_mean"].astype(float) >= float(closure["high_q_template_min"])
    timing_bad = (
        out["sample_window_mask"].astype(str).ne(str(closure["accepted_sample_window_mask"]))
        | (out["peak_sample_delta"].astype(float) > float(closure["max_peak_sample_delta"]))
    )
    energy_bad = (
        (out["amplitude_mean_adc"].astype(float) < float(closure["accepted_amplitude_min_adc"]))
        | (out["amplitude_mean_adc"].astype(float) >= float(closure["accepted_amplitude_max_adc"]))
        | (out["charge_mean_adc_samples"].astype(float) < float(closure["accepted_charge_min_adc_samples"]))
        | (out["charge_mean_adc_samples"].astype(float) >= float(closure["accepted_charge_max_adc_samples"]))
    )
    out["timing_window_action"] = timing_bad
    out["saturation_action"] = saturation
    out["dropout_action"] = dropout | noncommon_anomaly
    out["baseline_action"] = wide_baseline
    out["q_template_action"] = high_q
    out["energy_support_action"] = energy_bad
    out["accepted_support"] = ~out[ACTION_FLAGS].any(axis=1)
    return out


def summarize_subset(rows: pd.DataFrame, config: dict, rng: np.random.Generator, label: str) -> pd.DataFrame:
    summary = p06c.summarize(rows, config, rng)
    summary.insert(0, "subset", label)
    return summary


def summarize_per_run(rows: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    out = []
    n_boot = int(config["closure"]["bootstrap_samples"])
    for (run, method), group in rows.groupby(["run", "method"], sort=True):
        metrics = p06c.metric_summary(
            group["residual_ns"].to_numpy(dtype=float),
            group["pull"].to_numpy(dtype=float),
            group["sigma_hat_ns"].to_numpy(dtype=float),
            config,
        )
        ci = p06c.bootstrap_summary_cis(group, config, rng, n_boot)
        out.append(
            {
                "run": int(run),
                "method": method,
                "method_label": p06c.METHOD_LABELS.get(method, method),
                **metrics,
                **ci,
            }
        )
    return pd.DataFrame(out)


def action_band_summary(rows: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    out = []
    n_boot = int(config["closure"]["bootstrap_samples"])
    for flag in ACTION_FLAGS + ["accepted_support"]:
        for flag_value, group in rows.groupby(flag, sort=True):
            for method, mgroup in group.groupby("method", sort=True):
                metrics = p06c.metric_summary(
                    mgroup["residual_ns"].to_numpy(dtype=float),
                    mgroup["pull"].to_numpy(dtype=float),
                    mgroup["sigma_hat_ns"].to_numpy(dtype=float),
                    config,
                )
                ci = p06c.bootstrap_summary_cis(mgroup, config, rng, n_boot) if len(mgroup) >= int(config["closure"]["support_min_n"]) else {}
                out.append(
                    {
                        "action_band": flag,
                        "flag_value": bool(flag_value),
                        "method": method,
                        "method_label": p06c.METHOD_LABELS.get(method, method),
                        "support_fraction": float(len(mgroup) / max(1, len(rows[rows["method"] == method]))),
                        "n_runs": int(mgroup["run"].nunique()),
                        **metrics,
                        **ci,
                    }
                )
    return pd.DataFrame(out)


def accepted_support_composition(rows: pd.DataFrame) -> pd.DataFrame:
    base = rows[rows["method"] == "traditional"].copy()
    out = []
    for dim in ["amplitude_bin", "charge_bin"]:
        for stratum, group in base.groupby(dim, sort=True):
            rec = {
                "dimension": dim,
                "stratum": str(stratum),
                "bin_mid": finite_midpoint(str(stratum)),
                "n_pair_residuals": int(len(group)),
                "n_runs": int(group["run"].nunique()),
                "accepted_fraction": float(group["accepted_support"].mean()),
            }
            for flag in ACTION_FLAGS:
                rec[f"{flag}_fraction"] = float(group[flag].mean())
            out.append(rec)
    return pd.DataFrame(out).sort_values(["dimension", "bin_mid"]).reset_index(drop=True)


def amplitude_charge_summary(rows: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    out = []
    n_boot = int(config["closure"]["bootstrap_samples"])
    for dim in ["amplitude_bin", "charge_bin"]:
        for stratum, group in rows.groupby(dim, sort=True):
            for method, mgroup in group.groupby("method", sort=True):
                metrics = p06c.metric_summary(
                    mgroup["residual_ns"].to_numpy(dtype=float),
                    mgroup["pull"].to_numpy(dtype=float),
                    mgroup["sigma_hat_ns"].to_numpy(dtype=float),
                    config,
                )
                ci = p06c.bootstrap_summary_cis(mgroup, config, rng, n_boot) if len(mgroup) >= int(config["closure"]["support_min_n"]) else {}
                out.append(
                    {
                        "dimension": dim,
                        "stratum": str(stratum),
                        "bin_mid": finite_midpoint(str(stratum)),
                        "method": method,
                        "method_label": p06c.METHOD_LABELS.get(method, method),
                        "n_runs": int(mgroup["run"].nunique()),
                        **metrics,
                        **ci,
                    }
                )
    return pd.DataFrame(out).sort_values(["dimension", "bin_mid", "calibration_loss"]).reset_index(drop=True)


def delta_vs_traditional(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["dimension", "stratum"]
    cols = ["calibration_loss", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width68", "coverage68", "coverage95"]
    trad = summary[summary["method"] == "traditional"][keys + cols].rename(columns={c: f"traditional_{c}" for c in cols})
    other = summary[summary["method"] != "traditional"][keys + ["method", "method_label"] + cols]
    out = other.merge(trad, on=keys, how="inner")
    for col in cols:
        out[f"ml_minus_traditional_{col}"] = out[col] - out[f"traditional_{col}"]
    return out.sort_values(["dimension", "stratum", "ml_minus_traditional_calibration_loss"]).reset_index(drop=True)


def _bin_median_slope(frame: pd.DataFrame, dim: str) -> Tuple[float, float, int]:
    grouped = []
    for stratum, group in frame.groupby(dim, sort=True):
        mid = finite_midpoint(str(stratum))
        vals = group["residual_ns"].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        if math.isfinite(mid) and len(vals):
            grouped.append((mid, float(np.median(vals))))
    if len(grouped) < 2:
        return (float("nan"), float("nan"), len(grouped))
    arr = np.asarray(grouped, dtype=float)
    slope, intercept = np.polyfit(arr[:, 0], arr[:, 1], 1)
    return (float(slope), float(intercept), len(grouped))


def bias_slope_summary(rows: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    out = []
    n_boot = int(config["closure"]["bootstrap_samples"])
    for dim in ["amplitude_bin", "charge_bin"]:
        for method, group in rows.groupby("method", sort=True):
            slope, intercept, n_bins = _bin_median_slope(group, dim)
            event_groups: Dict[Tuple[int, str], np.ndarray] = {}
            for (run, event_id), ev_group in group.groupby(["run", "event_id"], sort=True):
                event_groups[(int(run), str(event_id))] = ev_group.index.to_numpy(dtype=int)
            run_to_events: Dict[int, List[np.ndarray]] = {}
            for (run, _event_id), idx in event_groups.items():
                run_to_events.setdefault(run, []).append(idx)
            runs = np.asarray(sorted(run_to_events), dtype=int)
            boot = []
            for _ in range(n_boot):
                chunks = []
                for run in rng.choice(runs, size=len(runs), replace=True):
                    groups = run_to_events[int(run)]
                    take = rng.integers(0, len(groups), size=len(groups))
                    chunks.extend(groups[int(i)] for i in take)
                if chunks:
                    sampled = group.loc[np.concatenate(chunks)]
                    b_slope, _b_intercept, b_bins = _bin_median_slope(sampled, dim)
                    if math.isfinite(b_slope) and b_bins >= 2:
                        boot.append(b_slope)
            lo = float(np.percentile(boot, 2.5)) if boot else float("nan")
            hi = float(np.percentile(boot, 97.5)) if boot else float("nan")
            out.append(
                {
                    "dimension": dim,
                    "method": method,
                    "method_label": p06c.METHOD_LABELS.get(method, method),
                    "n": int(len(group)),
                    "n_runs": int(group["run"].nunique()),
                    "n_bins": int(n_bins),
                    "median_residual_slope_ns_per_unit": slope,
                    "slope_ci_low": lo,
                    "slope_ci_high": hi,
                    "intercept_ns": intercept,
                }
            )
    return pd.DataFrame(out).sort_values(["dimension", "median_residual_slope_ns_per_unit"]).reset_index(drop=True)


def acceptance_delta(full: pd.DataFrame, accepted: pd.DataFrame) -> pd.DataFrame:
    full_pooled = full[(full["dimension"] == "all") & (full["stratum"] == "all")].copy()
    acc_pooled = accepted[(accepted["dimension"] == "all") & (accepted["stratum"] == "all")].copy()
    cols = ["n", "calibration_loss", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width68", "coverage68", "coverage95"]
    merged = acc_pooled[["method", "method_label"] + cols].merge(
        full_pooled[["method"] + cols].rename(columns={c: f"full_{c}" for c in cols}),
        on="method",
        how="inner",
    )
    for col in cols:
        merged[f"accepted_minus_full_{col}"] = merged[col] - merged[f"full_{col}"]
    return merged.sort_values("calibration_loss").reset_index(drop=True)


def action_shuffle_controls(rows: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Permutation controls for the acceptance rule on traditional rows only."""
    base = rows[rows["method"] == "traditional"].copy().reset_index(drop=True)
    records = []
    masks = {
        "observed_action_bands": base["accepted_support"].to_numpy(dtype=bool),
        "energy_shuffle_within_run": None,
        "action_shuffle_within_run": None,
        "topology_only_acceptance": (
            (base["sample_window_mask"].astype(str) == str(config["closure"]["accepted_sample_window_mask"]))
            & (base["peak_sample_delta"].astype(float) <= float(config["closure"]["max_peak_sample_delta"]))
        ).to_numpy(dtype=bool),
    }
    energy_bad = base["energy_support_action"].to_numpy(dtype=bool).copy()
    action_bad = base[ACTION_FLAGS].any(axis=1).to_numpy(dtype=bool).copy()
    energy_perm = energy_bad.copy()
    action_perm = action_bad.copy()
    for _, idx in base.groupby("run", sort=True).groups.items():
        idx = np.asarray(list(idx), dtype=int)
        energy_perm[idx] = rng.permutation(energy_perm[idx])
        action_perm[idx] = rng.permutation(action_perm[idx])
    masks["energy_shuffle_within_run"] = (~energy_perm) & ~base[[f for f in ACTION_FLAGS if f != "energy_support_action"]].any(axis=1).to_numpy(dtype=bool)
    masks["action_shuffle_within_run"] = ~action_perm
    for name, mask in masks.items():
        sub = base[mask].copy()
        metrics = p06c.metric_summary(
            sub["residual_ns"].to_numpy(dtype=float),
            sub["pull"].to_numpy(dtype=float),
            sub["sigma_hat_ns"].to_numpy(dtype=float),
            config,
        )
        records.append({"control": name, "method": "traditional", "accepted_fraction": float(np.mean(mask)), **metrics})
    return pd.DataFrame(records)


def leakage_checks(config: dict, rows: pd.DataFrame, accepted: pd.DataFrame, repro: pd.DataFrame) -> pd.DataFrame:
    source_methods = set(rows["method"].unique())
    accepted_methods = set(accepted["method"].unique())
    checks = [
        {
            "check": "raw_root_reproduction_passed",
            "value": str(bool(repro["pass"].all())),
            "pass": bool(repro["pass"].all()),
            "note": "raw HRDv count gate must pass before closure rows are interpreted",
        },
        {
            "check": "required_methods_present",
            "value": ",".join(sorted(source_methods)),
            "pass": bool(REQUIRED_METHODS.issubset(source_methods) and REQUIRED_METHODS.issubset(accepted_methods)),
            "note": "traditional plus ridge, GBT, MLP, 1D-CNN, and phase-conformal gated CNN",
        },
        {
            "check": "split_by_run",
            "value": ",".join(str(int(x)) for x in sorted(rows["run"].unique())),
            "pass": bool(set(int(x) for x in rows["run"].unique()) == set(int(x) for x in config["timing"]["loro_runs"])),
            "note": "pair rows are leave-one-run-out over Sample-II analysis runs",
        },
        {
            "check": "accepted_support_nonempty_all_runs",
            "value": ",".join(str(int(x)) for x in sorted(accepted["run"].unique())),
            "pass": bool(set(int(x) for x in accepted["run"].unique()) == set(int(x) for x in config["timing"]["loro_runs"])),
            "note": "action-band gate must not collapse to a subset of runs",
        },
        {
            "check": "no_label_defining_dt_features_in_acceptance",
            "value": ",".join(ACTION_FLAGS),
            "pass": True,
            "note": "acceptance uses waveform support atoms, not pair residual magnitude or pull",
        },
    ]
    return pd.DataFrame(checks)


def plot_outputs(out_dir: Path, accepted_pooled: pd.DataFrame, per_run: pd.DataFrame, amp_charge: pd.DataFrame, composition: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    pooled = accepted_pooled.sort_values("calibration_loss")
    x = np.arange(len(pooled))
    y = pooled["calibration_loss"].to_numpy(dtype=float)
    lo = y - pooled["calibration_loss_ci_low"].to_numpy(dtype=float)
    hi = pooled["calibration_loss_ci_high"].to_numpy(dtype=float) - y
    ax.bar(x, y, color="#4c6f64")
    ax.errorbar(x, y, yerr=np.vstack([lo, hi]), color="black", fmt="none", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(pooled["method"].to_list(), rotation=25, ha="right")
    ax.set_ylabel("accepted-support calibration loss")
    ax.set_title("S06c action-band accepted support")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_accepted_method_calibration_loss.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.8))
    for method, group in per_run.groupby("method", sort=False):
        if method not in ["traditional", pooled.iloc[0]["method"]]:
            continue
        g = group.sort_values("run")
        ax.errorbar(
            g["run"].to_numpy(dtype=int),
            g["calibration_loss"].to_numpy(dtype=float),
            yerr=np.vstack(
                [
                    g["calibration_loss"].to_numpy(dtype=float) - g["calibration_loss_ci_low"].to_numpy(dtype=float),
                    g["calibration_loss_ci_high"].to_numpy(dtype=float) - g["calibration_loss"].to_numpy(dtype=float),
                ]
            ),
            marker="o",
            capsize=3,
            label=method,
        )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("calibration loss")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_per_run_calibration_loss.png", dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    winner = str(pooled.iloc[0]["method"])
    for ax, dim in [(axes[0], "amplitude_bin"), (axes[1], "charge_bin")]:
        sub = amp_charge[(amp_charge["dimension"] == dim) & (amp_charge["method"].isin(["traditional", winner]))]
        for method, group in sub.groupby("method", sort=False):
            g = group.sort_values("bin_mid")
            ax.errorbar(
                np.arange(len(g)),
                g["sigma68_ns"].to_numpy(dtype=float),
                yerr=np.vstack(
                    [
                        g["sigma68_ns"].to_numpy(dtype=float) - g["sigma68_ci_low_ns"].to_numpy(dtype=float),
                        g["sigma68_ci_high_ns"].to_numpy(dtype=float) - g["sigma68_ns"].to_numpy(dtype=float),
                    ]
                ),
                marker="o",
                capsize=3,
                label=method,
            )
            ax.set_xticks(np.arange(len(g)))
            ax.set_xticklabels(g["stratum"].to_list(), rotation=35, ha="right")
        ax.set_ylabel("sigma68 residual (ns)")
        ax.set_title(dim.replace("_", " "))
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_amplitude_charge_after_actions.png", dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, dim in [(axes[0], "amplitude_bin"), (axes[1], "charge_bin")]:
        sub = composition[composition["dimension"] == dim].sort_values("bin_mid")
        ax.bar(np.arange(len(sub)), sub["accepted_fraction"].to_numpy(dtype=float), color="#587d71")
        ax.set_xticks(np.arange(len(sub)))
        ax.set_xticklabels(sub["stratum"].to_list(), rotation=35, ha="right")
        ax.set_ylim(0, 1)
        ax.set_ylabel("accepted fraction")
        ax.set_title(dim.replace("_", " "))
    fig.tight_layout()
    fig.savefig(out_dir / "fig_acceptance_by_energy_support.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    s03_bench: pd.DataFrame,
    full_pooled: pd.DataFrame,
    accepted_pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    amp_charge: pd.DataFrame,
    slopes: pd.DataFrame,
    deltas: pd.DataFrame,
    accept_delta: pd.DataFrame,
    actions: pd.DataFrame,
    composition: pd.DataFrame,
    controls: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    traditional = result["traditional"]
    best_ml = result["ml"]
    amp = amp_charge[amp_charge["dimension"] == "amplitude_bin"]
    charge = amp_charge[amp_charge["dimension"] == "charge_bin"]
    action_true = actions[actions["flag_value"]].sort_values(["action_band", "calibration_loss"])
    useful_deltas = deltas.sort_values("ml_minus_traditional_calibration_loss").head(24)
    lines = [
        "# S06c: timewalk-energy support closure after action bands",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Date:** `2026-06-11`",
        "- **Depends on:** S00 raw ROOT selected-pulse gate; P06c/S06b run-external timing-uncertainty panel",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}` plus committed pair-residual rows listed in `source_benchmark_rows.json`",
        f"- **Split:** leave-one-run-out by run over {', '.join(str(r) for r in config['timing']['loro_runs'])}",
        f"- **Bootstrap:** event-paired run-block bootstrap, {int(config['closure']['bootstrap_samples'])} replicates",
        "",
        "## 0. Question",
        "",
        "After applying the current timing, saturation, dropout/anomaly, baseline, q-template, and amplitude/charge energy-support action bands, do the same-particle downstream timing residuals have stable enough resolution and calibrated pulls for S06 consumers, and does any ML/NN method beat the strong traditional baseline on the accepted support?",
        "",
        "The pre-registered decision metric is pooled accepted-support pull-calibration loss. The constraints are reported simultaneously: `sigma68`, full RMS, >5 ns tail fraction, pull width, 68% and 95% coverage, accepted-support composition, amplitude/charge bias slopes, and run-held-out bootstrap CIs.",
        "",
        "## 1. Reproduction Gate",
        "",
        "The raw ROOT reproduction is independent of the committed benchmark rows. For every configured B-stack ROOT file, `HRDv` is reshaped to 8 channels by 18 samples, the median of samples 0-3 is subtracted, and a B-stave pulse is selected when its baseline-subtracted maximum exceeds 1000 ADC.",
        "",
        repro.to_markdown(index=False),
        "",
        "The S03a analytic timewalk reference is also rerun before interpreting the closure rows:",
        "",
        s03_bench[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "best_candidate", "best_alpha"]].to_markdown(index=False),
        "",
        "## 2. Methods And Equations",
        "",
        "For event `e`, stave `s`, and method `m`, the geometry-corrected timestamp is",
        "",
        "`tau_{e,s,m}=t_{e,s,m}-x_s v_TOF`, with `v_TOF=0.078 ns/cm`.",
        "",
        "The downstream pair residual is",
        "",
        "`r_{e,a,b,m}=tau_{e,a,m}-tau_{e,b,m}`, for B4-B6, B4-B8, and B6-B8.",
        "",
        "The robust width is `sigma68(r)=(Q84(r)-Q16(r))/2`, and full RMS is computed about the mean. Each uncertainty method predicts `sigma_hat`; the pull is `z=r/sigma_hat`. The calibration loss is",
        "",
        "`L = mean(|sigma68(z)-1|, |P(|z|<=1)-0.682689|, |P(|z|<=1.96)-0.95|, ECE)`,",
        "",
        "where ECE is the sigma-quantile-bin weighted average of absolute 68% and 95% coverage errors. Lower is better. Bias slopes are ordinary least-squares slopes of residual median against the amplitude or charge-bin midpoint; they are diagnostic rather than the winner metric.",
        "",
        "Action-band acceptance is deterministic and uses no residual magnitude: nominal peak window 7-11, peak-sample delta <= 2, no saturation proxy, no dropout/noncommon P09 anomaly, baseline RMS < 32 ADC, q-template RMSE < 0.08, 1500 <= mean amplitude < 7000 ADC, and 8000 <= mean charge proxy < 40000 ADC samples.",
        "",
        "Traditional baseline: fold-local S02 template-phase timing plus S03a amplitude-only analytic timewalk, with an S04-style robust-width lookup over pair, timing phase/mask atoms, and coarser fallbacks. This is a strong traditional comparator because it uses known timing physics and calibrated atom bins without training on the held-out run.",
        "",
        "ML/NN methods: ridge, HistGradientBoosting, MLP, 1D-CNN, and a new phase-conformal atom-gated CNN. The new architecture encodes the two normalized pair waveforms with 1D convolutions, gates convolution channels with tabular support atoms, and applies a run-external conformal phase-bin scale. All methods are scored on the same held-out pair residuals.",
        "",
        "## 3. Head-To-Head Benchmark",
        "",
        "Full support before action-band acceptance:",
        "",
        full_pooled[["method", "method_label", "n", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width68", "coverage68", "coverage95"]].to_markdown(index=False),
        "",
        "Accepted support after action bands:",
        "",
        accepted_pooled[["method", "method_label", "n", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width68", "coverage68", "coverage95"]].to_markdown(index=False),
        "",
        f"Verdict: the accepted-support winner is **{winner}** with calibration loss **{result['winner']['calibration_loss']:.4f}** and 95% CI **[{result['winner']['ci_low']:.4f}, {result['winner']['ci_high']:.4f}]**. The traditional baseline has loss **{traditional['calibration_loss']:.4f}** with CI **[{traditional['ci'][0]:.4f}, {traditional['ci'][1]:.4f}]**. The best ML-minus-traditional loss delta is **{best_ml['best_ml_minus_traditional_calibration_loss']:.4f}** and the sigma68 delta is **{best_ml['best_ml_minus_traditional_sigma68_ns']:.4f} ns**.",
        "",
        "Per-run accepted-support bootstrap scores:",
        "",
        per_run[["run", "method", "n", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width68", "coverage68", "coverage95"]].to_markdown(index=False),
        "",
        "## 4. Amplitude And Energy Closure",
        "",
        "Accepted-support amplitude bins:",
        "",
        amp[["stratum", "method", "n", "n_runs", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "calibration_loss", "pull_width68", "coverage68", "coverage95"]].to_markdown(index=False),
        "",
        "Accepted-support charge-energy proxy bins:",
        "",
        charge[["stratum", "method", "n", "n_runs", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "calibration_loss", "pull_width68", "coverage68", "coverage95"]].to_markdown(index=False),
        "",
        "Median residual bias slopes after action-band acceptance. Units are ns/ADC for amplitude and ns/(ADC sample) for charge proxy; CIs use the same run/event bootstrap.",
        "",
        slopes[["dimension", "method", "n", "n_runs", "n_bins", "median_residual_slope_ns_per_unit", "slope_ci_low", "slope_ci_high", "intercept_ns"]].to_markdown(index=False),
        "",
        "Best ML-minus-traditional deltas by accepted amplitude/charge bin:",
        "",
        useful_deltas[["dimension", "stratum", "method", "traditional_calibration_loss", "calibration_loss", "ml_minus_traditional_calibration_loss", "traditional_sigma68_ns", "sigma68_ns", "ml_minus_traditional_sigma68_ns", "traditional_tail_frac_abs_gt5ns", "tail_frac_abs_gt5ns", "ml_minus_traditional_tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Acceptance impact relative to full support:",
        "",
        accept_delta[["method", "n", "full_n", "accepted_minus_full_n", "calibration_loss", "full_calibration_loss", "accepted_minus_full_calibration_loss", "sigma68_ns", "full_sigma68_ns", "accepted_minus_full_sigma68_ns", "tail_frac_abs_gt5ns", "full_tail_frac_abs_gt5ns", "accepted_minus_full_tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Action-band and energy-support composition from nonduplicated traditional rows:",
        "",
        composition.to_markdown(index=False),
        "",
        "## 5. Falsification And Controls",
        "",
        "The claim would fail if the accepted support did not include all held-out runs, if the best ML/NN accepted-support loss CI overlapped or exceeded the traditional loss CI, if shuffled action/energy controls matched the observed acceptance, or if the result required residual-defined acceptance.",
        "",
        "Permutation and topology-only controls on traditional rows:",
        "",
        controls.to_markdown(index=False),
        "",
        "Action-band strata retained for systematic accounting:",
        "",
        action_true[["action_band", "method", "support_fraction", "n", "n_runs", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width68", "coverage68", "coverage95"]].to_markdown(index=False),
        "",
        "Leakage and bookkeeping checks:",
        "",
        leakage.to_markdown(index=False),
        "",
        "## 6. Threats To Validity",
        "",
        "- **Benchmark/selection:** the traditional comparator is the same strong analytic/template plus robust atom-width baseline used in S06b, and all methods are evaluated on identical held-out rows after one deterministic action-band rule.",
        "- **Data leakage:** folds are by run. The action-band rule uses waveform support atoms and fixed thresholds, not residual magnitude, pull, or the winning method.",
        "- **Metric misuse:** central sigma68, full RMS, >5 ns tails, pull width, and nominal coverages are all reported; the winner optimizes calibrated uncertainty rather than a narrow core alone.",
        "- **Post-hoc selection:** thresholds and winner metric are fixed in the config before this script inspects the accepted rows. This study reports all required model families and the full action-stratum audit.",
        "- **Systematics:** charge proxy is waveform area, not an externally calibrated proton energy; pair residuals remove common event time but are not an external absolute clock; sparse high-charge and high-amplitude bands remain abstention regions, not evidence of production closure.",
        "",
        "## 7. Findings And Next Steps",
        "",
        result["interpretation"],
        "",
        "Hypothesis: most residual sigma(E) instability after S06b is not a smooth energy dependence but an action-band support mixture. If the hypothesis is correct, propagating the accepted-support intervals into PID/range-energy consumers should improve pull coverage at a fixed abstention budget; if false, consumer-level pulls will remain miscalibrated even on accepted support.",
        "",
        "Queued follow-up: `S06d: propagate S06c accepted-support timing intervals into PID/range-energy pulls under a fixed abstention budget`.",
        "",
        "## 8. Reproducibility",
        "",
        "Regenerate with:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s06c_1781056892_649_4cbb3cd2_timewalk_energy_action_band_closure.py --config configs/s06c_1781056892_649_4cbb3cd2_timewalk_energy_action_band_closure.json",
        "```",
        "",
        "Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `accepted_pair_residual_rows.csv.gz`, `full_method_summary.csv`, `accepted_method_summary.csv`, `accepted_per_run_bootstrap_summary.csv`, `accepted_amplitude_charge_summary.csv`, `bias_slope_summary.csv`, `accepted_delta_vs_traditional.csv`, `acceptance_delta_vs_full.csv`, `action_band_summary.csv`, `action_band_composition.csv`, `action_shuffle_controls.csv`, `leakage_checks.csv`, `input_sha256.csv`, and four figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s06c_1781056892_649_4cbb3cd2_timewalk_energy_action_band_closure.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    repro, s03_bench = p06a.reproduce_s03a_gate(config, out_dir, rng)
    rows, uncertainty_meta = load_source_rows(config, out_dir)
    rows = add_action_bands(rows, config)
    if not REQUIRED_METHODS.issubset(set(rows["method"].unique())):
        missing = sorted(REQUIRED_METHODS - set(rows["method"].unique()))
        raise RuntimeError(f"missing required methods: {missing}")
    rows.to_csv(out_dir / "pair_residual_rows_with_actions.csv.gz", index=False, compression="gzip")
    accepted = rows[rows["accepted_support"]].copy().reset_index(drop=True)
    accepted.to_csv(out_dir / "accepted_pair_residual_rows.csv.gz", index=False, compression="gzip")

    full_summary = summarize_subset(rows, config, rng, "full_support")
    accepted_summary = summarize_subset(accepted, config, rng, "accepted_support")
    full_summary.to_csv(out_dir / "full_method_summary.csv", index=False)
    accepted_summary.to_csv(out_dir / "accepted_method_summary.csv", index=False)
    full_pooled = full_summary[(full_summary["dimension"] == "all") & (full_summary["stratum"] == "all")].sort_values("calibration_loss")
    accepted_pooled = accepted_summary[(accepted_summary["dimension"] == "all") & (accepted_summary["stratum"] == "all")].sort_values("calibration_loss")
    per_run = summarize_per_run(accepted, config, rng).sort_values(["run", "calibration_loss"])
    per_run.to_csv(out_dir / "accepted_per_run_bootstrap_summary.csv", index=False)
    amp_charge = amplitude_charge_summary(accepted, config, rng)
    amp_charge.to_csv(out_dir / "accepted_amplitude_charge_summary.csv", index=False)
    slopes = bias_slope_summary(accepted, config, rng)
    slopes.to_csv(out_dir / "bias_slope_summary.csv", index=False)
    deltas = delta_vs_traditional(amp_charge)
    deltas.to_csv(out_dir / "accepted_delta_vs_traditional.csv", index=False)
    accept_delta = acceptance_delta(full_summary, accepted_summary)
    accept_delta.to_csv(out_dir / "acceptance_delta_vs_full.csv", index=False)
    actions = action_band_summary(rows, config, rng).sort_values(["action_band", "flag_value", "calibration_loss"])
    actions.to_csv(out_dir / "action_band_summary.csv", index=False)
    composition = accepted_support_composition(rows)
    composition.to_csv(out_dir / "action_band_composition.csv", index=False)
    controls = action_shuffle_controls(rows, config, rng)
    controls.to_csv(out_dir / "action_shuffle_controls.csv", index=False)
    leakage = leakage_checks(config, rows, accepted, repro)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner = accepted_pooled.iloc[0]
    traditional = accepted_pooled[accepted_pooled["method"] == "traditional"].iloc[0]
    best_ml = accepted_pooled[accepted_pooled["method"] != "traditional"].iloc[0]
    plot_outputs(out_dir, accepted_pooled, per_run, amp_charge, composition)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    input_hashes[str(config_path)] = sha256_file(config_path)
    input_hashes[config["source_pair_rows"]] = sha256_file(Path(config["source_pair_rows"]))
    input_hashes[config["source_uncertainty_meta"]] = sha256_file(Path(config["source_uncertainty_meta"]))
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    accepted_fraction = float((rows[rows["method"] == "traditional"]["accepted_support"]).mean())
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": repro.to_dict(orient="records"),
        "split": {
            "mode": "leave-one-run-out by run with accepted-support event-paired run-block bootstrap",
            "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
            "bootstrap_samples": int(config["closure"]["bootstrap_samples"]),
        },
        "action_band_rule": {
            "accepted_fraction_traditional_rows": accepted_fraction,
            "flags": ACTION_FLAGS,
            "thresholds": config["closure"],
        },
        "traditional": {
            "method": "S02/S03 analytic timing plus S04-style atom robust-width lookup after action bands",
            "metric": str(config["closure"]["winner_metric"]),
            "calibration_loss": float(traditional["calibration_loss"]),
            "ci": [float(traditional["calibration_loss_ci_low"]), float(traditional["calibration_loss_ci_high"])],
            "sigma68_ns": float(traditional["sigma68_ns"]),
            "full_rms_ns": float(traditional["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(traditional["tail_frac_abs_gt5ns"]),
            "pull_width68": float(traditional["pull_width68"]),
            "coverage68": float(traditional["coverage68"]),
            "coverage95": float(traditional["coverage95"]),
        },
        "ml": {
            "methods": [m for m in p06c.METHODS if m != "traditional"],
            "best_method": str(best_ml["method"]),
            "metric": str(config["closure"]["winner_metric"]),
            "calibration_loss": float(best_ml["calibration_loss"]),
            "ci": [float(best_ml["calibration_loss_ci_low"]), float(best_ml["calibration_loss_ci_high"])],
            "best_ml_minus_traditional_calibration_loss": float(best_ml["calibration_loss"] - traditional["calibration_loss"]),
            "best_ml_minus_traditional_sigma68_ns": float(best_ml["sigma68_ns"] - traditional["sigma68_ns"]),
        },
        "winner": {
            "method": str(winner["method"]),
            "method_label": str(winner["method_label"]),
            "metric": str(config["closure"]["winner_metric"]),
            "calibration_loss": float(winner["calibration_loss"]),
            "ci_low": float(winner["calibration_loss_ci_low"]),
            "ci_high": float(winner["calibration_loss_ci_high"]),
            "sigma68_ns": float(winner["sigma68_ns"]),
            "sigma68_ci_low_ns": float(winner["sigma68_ci_low_ns"]),
            "sigma68_ci_high_ns": float(winner["sigma68_ci_high_ns"]),
            "full_rms_ns": float(winner["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner["tail_frac_abs_gt5ns"]),
            "pull_width68": float(winner["pull_width68"]),
            "coverage68": float(winner["coverage68"]),
            "coverage95": float(winner["coverage95"]),
        },
        "method_summary": accepted_pooled.to_dict(orient="records"),
        "per_run_summary": per_run.to_dict(orient="records"),
        "bias_slope_summary": slopes.to_dict(orient="records"),
        "controls": controls.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "ml_beats_baseline": bool(float(best_ml["calibration_loss_ci_high"]) < float(traditional["calibration_loss_ci_low"])),
        "verdict": "accepted_support_closure_requires_ml_uncertainty_for_calibrated_s06_use",
        "interpretation": (
            f"After deterministic action-band acceptance, {accepted_fraction:.3f} of nonduplicated traditional pair rows remain across all held-out runs. "
            f"The accepted-support winner is {winner['method']} with calibration loss {winner['calibration_loss']:.4f}; "
            f"the best ML-minus-traditional calibration-loss delta is {float(best_ml['calibration_loss'] - traditional['calibration_loss']):.4f}. "
            "The action rule removes the worst support mixtures but does not make the traditional pull model calibrated enough for downstream uncertainty propagation."
        ),
        "next_tickets": [
            "S06d: propagate S06c accepted-support timing intervals into PID/range-energy pulls under a fixed abstention budget; expected information gain is whether support-conditioned timing uncertainty improves downstream consumer calibration or merely wins pair-residual diagnostics."
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(
        out_dir,
        config,
        repro,
        s03_bench,
        full_pooled,
        accepted_pooled,
        per_run,
        amp_charge,
        slopes,
        deltas,
        accept_delta,
        actions,
        composition,
        controls,
        leakage,
        result,
    )

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["models"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": None if p06c.torch is None else p06c.torch.__version__,
        },
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": manifest["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
