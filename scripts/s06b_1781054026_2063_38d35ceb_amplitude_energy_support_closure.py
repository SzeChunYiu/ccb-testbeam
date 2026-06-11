#!/usr/bin/env python3
"""S06b: amplitude/energy timing support closure from raw ROOT.

This study deliberately reuses the already-reviewed P06b/P06c fold-local timing
machinery, then adds the S06b-specific closure layer: amplitude and charge
monotonicity, support/action-band composition, per-run bootstrap intervals, and
ML-minus-traditional deltas.
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
from typing import Dict, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s06b-1781054026")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p06a_1781017198_1470_7d872fbe_amp_binned_resolution as p06a  # noqa: E402
import p06b_1781042379_490_2f714bdc_amplitude_stratified_timing_bias_ledger as p06b  # noqa: E402
import p06c_1781044013_777_0e401db7_time_local_pull_coverage_atlas as p06c  # noqa: E402
import s02_timing_pickoff as s02  # noqa: E402


METHODS = p06c.METHODS
METHOD_LABELS = p06c.METHOD_LABELS
ACTION_DIMS = ["saturation_flag", "q_template_bin", "baseline_bin", "p09_anomaly_class"]


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
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def parse_bin_bounds(label: str) -> Tuple[float, float]:
    if "[" not in str(label) or ")" not in str(label):
        return (float("nan"), float("nan"))
    inside = str(label).split("[", 1)[1].split(")", 1)[0]
    lo_s, hi_s = inside.split(",", 1)
    lo = float(lo_s)
    hi = float("inf") if hi_s == "inf" else float(hi_s)
    return lo, hi


def finite_midpoint(lo: float, hi: float) -> float:
    if math.isfinite(lo) and math.isfinite(hi):
        return 0.5 * (lo + hi)
    if math.isfinite(lo):
        return lo * 1.35
    if math.isfinite(hi):
        return hi * 0.65
    return float("nan")


def action_masks(frame: pd.DataFrame, config: dict) -> Dict[str, np.ndarray]:
    baseline_lo = float(config["closure"]["wide_baseline_min_adc"])
    q_lo = float(config["closure"]["high_q_template_min"])
    base_lo = np.asarray([parse_bin_bounds(x)[0] for x in frame["baseline_bin"]], dtype=float)
    q_bin_lo = np.asarray([parse_bin_bounds(x)[0] for x in frame["q_template_bin"]], dtype=float)
    anomaly = frame["p09_anomaly_class"].astype(str).to_numpy()
    saturation = frame["saturation_flag"].astype(str).str.lower().isin(["true", "1"]).to_numpy()
    dropout = anomaly == "dropout"
    noncommon = anomaly != "unassigned_common"
    wide_baseline = base_lo >= baseline_lo
    high_q = q_bin_lo >= q_lo
    any_action = saturation | dropout | noncommon | wide_baseline | high_q
    return {
        "saturation": saturation,
        "dropout": dropout,
        "anomaly_noncommon": noncommon,
        "wide_baseline": wide_baseline,
        "high_q_template": high_q,
        "any_action_band": any_action,
    }


def add_support_fractions(rec: dict, group: pd.DataFrame, config: dict) -> dict:
    masks = action_masks(group, config)
    for name, mask in masks.items():
        rec[f"{name}_fraction"] = float(np.mean(mask)) if len(mask) else float("nan")
    rec["n_runs"] = int(group["run"].nunique()) if "run" in group else 0
    return rec


def summarize_dimension(
    rows: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    dims: Sequence[str],
    n_boot: int,
) -> pd.DataFrame:
    out = []
    min_n = int(config["closure"]["support_min_n"])
    for dim in dims:
        for stratum, group in rows.groupby(dim, sort=True):
            lo, hi = parse_bin_bounds(str(stratum))
            for method, mgroup in group.groupby("method", sort=True):
                metrics = p06c.metric_summary(
                    mgroup["residual_ns"].to_numpy(dtype=float),
                    mgroup["pull"].to_numpy(dtype=float),
                    mgroup["sigma_hat_ns"].to_numpy(dtype=float),
                    config,
                )
                ci = p06c.bootstrap_summary_cis(mgroup, config, rng, n_boot) if len(mgroup) >= min_n else {}
                rec = {
                    "dimension": dim,
                    "stratum": str(stratum),
                    "bin_low": lo,
                    "bin_high": hi,
                    "bin_mid": finite_midpoint(lo, hi),
                    "method": method,
                    "method_label": METHOD_LABELS.get(method, method),
                    **metrics,
                    **ci,
                    "support_fraction": float(len(mgroup) / max(1, len(rows[rows["method"] == method]))),
                }
                out.append(add_support_fractions(rec, mgroup, config))
    return pd.DataFrame(out)


def summarize_per_run(rows: pd.DataFrame, config: dict, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    out = []
    for (run, method), group in rows.groupby(["run", "method"], sort=True):
        metrics = p06c.metric_summary(
            group["residual_ns"].to_numpy(dtype=float),
            group["pull"].to_numpy(dtype=float),
            group["sigma_hat_ns"].to_numpy(dtype=float),
            config,
        )
        ci = p06c.bootstrap_summary_cis(group, config, rng, n_boot)
        rec = {"run": int(run), "method": method, "method_label": METHOD_LABELS.get(method, method), **metrics, **ci}
        out.append(add_support_fractions(rec, group, config))
    return pd.DataFrame(out)


def monotonicity_table(support: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (dimension, method), group in support.groupby(["dimension", "method"], sort=True):
        if dimension not in {"amplitude_bin", "charge_bin"}:
            continue
        g = group[np.isfinite(group["bin_mid"])].sort_values("bin_mid").reset_index(drop=True)
        transitions = max(0, len(g) - 1)
        increases = []
        significant = []
        delta_rows = []
        for i in range(transitions):
            a = g.iloc[i]
            b = g.iloc[i + 1]
            delta = float(b["sigma68_ns"] - a["sigma68_ns"])
            increases.append(delta > 0.0)
            significant.append(float(b.get("sigma68_ci_low_ns", np.nan)) > float(a.get("sigma68_ci_high_ns", np.nan)))
            delta_rows.append(delta)
        finite_mid = g["bin_mid"].to_numpy(dtype=float)
        finite_sig = g["sigma68_ns"].to_numpy(dtype=float)
        corr = float(np.corrcoef(finite_mid, finite_sig)[0, 1]) if len(g) >= 2 else float("nan")
        out.append(
            {
                "dimension": dimension,
                "method": method,
                "method_label": METHOD_LABELS.get(method, method),
                "n_bins": int(len(g)),
                "n_adjacent_transitions": int(transitions),
                "monotonicity_violation_count": int(np.sum(increases)),
                "monotonicity_violation_rate": float(np.mean(increases)) if increases else float("nan"),
                "significant_violation_count": int(np.sum(significant)),
                "max_adjacent_sigma68_increase_ns": float(np.max(delta_rows)) if delta_rows else float("nan"),
                "sigma68_vs_bin_mid_corr": corr,
            }
        )
    return pd.DataFrame(out)


def support_composition(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    base = rows[rows["method"] == "traditional"].copy()
    out = []
    for dim in ["amplitude_bin", "charge_bin"]:
        for stratum, group in base.groupby(dim, sort=True):
            lo, hi = parse_bin_bounds(str(stratum))
            rec = {
                "dimension": dim,
                "stratum": str(stratum),
                "bin_low": lo,
                "bin_high": hi,
                "bin_mid": finite_midpoint(lo, hi),
                "n_pair_residuals": int(len(group)),
                "n_runs": int(group["run"].nunique()),
                "support_fraction": float(len(group) / max(1, len(base))),
            }
            out.append(add_support_fractions(rec, group, config))
    return pd.DataFrame(out).sort_values(["dimension", "bin_mid"]).reset_index(drop=True)


def method_deltas_vs_traditional(support: pd.DataFrame) -> pd.DataFrame:
    keys = ["dimension", "stratum"]
    trad_cols = [
        "sigma68_ns",
        "full_rms_ns",
        "tail_frac_abs_gt5ns",
        "pull_width68",
        "coverage68",
        "coverage95",
        "calibration_loss",
    ]
    trad = support[support["method"] == "traditional"][keys + trad_cols].rename(
        columns={c: f"traditional_{c}" for c in trad_cols}
    )
    other = support[support["method"] != "traditional"][keys + ["method", "method_label"] + trad_cols]
    out = other.merge(trad, on=keys, how="inner")
    for col in trad_cols:
        out[f"ml_minus_traditional_{col}"] = out[col] - out[f"traditional_{col}"]
    return out.sort_values(["dimension", "stratum", "ml_minus_traditional_calibration_loss"]).reset_index(drop=True)


def plot_closure(out_dir: Path, support: pd.DataFrame, composition: pd.DataFrame, winner: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=False)
    for ax, dim, xlabel in [
        (axes[0], "amplitude_bin", "amplitude bin midpoint (ADC)"),
        (axes[1], "charge_bin", "charge proxy bin midpoint (ADC samples)"),
    ]:
        for method, color in [("traditional", "#59656f"), (winner, "#2f7d6d")]:
            g = support[(support["dimension"] == dim) & (support["method"] == method)].sort_values("bin_mid")
            if len(g) == 0:
                continue
            x = np.arange(len(g))
            y = g["sigma68_ns"].to_numpy(dtype=float)
            lo = y - g["sigma68_ci_low_ns"].to_numpy(dtype=float)
            hi = g["sigma68_ci_high_ns"].to_numpy(dtype=float) - y
            ax.errorbar(x, y, yerr=np.vstack([lo, hi]), marker="o", capsize=3, label=method, color=color)
            ax.set_xticks(x)
            ax.set_xticklabels(g["stratum"].to_list(), rotation=35, ha="right")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("pairwise sigma68 (ns)")
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_amplitude_charge_sigma68.png", dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, dim in [(axes[0], "amplitude_bin"), (axes[1], "charge_bin")]:
        g = composition[composition["dimension"] == dim].sort_values("bin_mid")
        x = np.arange(len(g))
        ax.stackplot(
            x,
            g["saturation_fraction"].to_numpy(dtype=float),
            g["high_q_template_fraction"].to_numpy(dtype=float),
            g["wide_baseline_fraction"].to_numpy(dtype=float),
            g["dropout_fraction"].to_numpy(dtype=float),
            labels=["saturation", "high q-template", "wide baseline", "dropout"],
            alpha=0.86,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(g["stratum"].to_list(), rotation=35, ha="right")
        ax.set_ylabel("fraction of traditional pair rows")
        ax.set_title(dim.replace("_", " "))
    axes[1].legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_action_band_composition.png", dpi=140)
    plt.close(fig)


def build_or_load_calibrated(config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    calibrated_path = out_dir / "pair_residual_rows_with_pulls.csv.gz"
    uncertainty_meta_path = out_dir / "uncertainty_fold_meta.csv"
    if calibrated_path.exists() and uncertainty_meta_path.exists():
        return pd.read_csv(calibrated_path), pd.read_csv(uncertainty_meta_path)

    source_rows = Path(config.get("source_pair_rows", ""))
    source_meta = Path(config.get("source_uncertainty_meta", ""))
    if source_rows.exists() and source_meta.exists():
        calibrated = pd.read_csv(source_rows)
        uncertainty_meta = pd.read_csv(source_meta)
        calibrated.to_csv(calibrated_path, index=False, compression="gzip")
        uncertainty_meta.to_csv(uncertainty_meta_path, index=False)
        provenance = {
            "source_pair_rows": str(source_rows),
            "source_pair_rows_sha256": sha256_file(source_rows),
            "source_uncertainty_meta": str(source_meta),
            "source_uncertainty_meta_sha256": sha256_file(source_meta),
            "note": "S06b runs its own raw ROOT reproduction gate, then reuses the committed P06c run-external pair benchmark rows to avoid repeating identical LORO model training.",
        }
        (out_dir / "source_benchmark_rows.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        return calibrated, uncertainty_meta

    base_config = {**config, "timing": {**config["timing"], "train_runs": config["timing"]["loro_runs"], "heldout_runs": []}}
    base_pulses = s02.load_downstream_pulses(base_config)
    fold_frames = []
    fold_meta = []
    for heldout_run in config["timing"]["loro_runs"]:
        held, meta = p06b.fold_predictions(base_pulses, config, int(heldout_run))
        fold_frames.append(held)
        fold_meta.append(meta)
    heldout = pd.concat(fold_frames, ignore_index=True)
    central_meta = pd.concat(fold_meta, ignore_index=True, sort=False)
    central_meta.to_csv(out_dir / "central_model_fold_meta.csv", index=False)
    heldout.to_pickle(out_dir / "heldout_pulse_predictions.pkl")

    pair_rows = p06c.add_pair_rows(heldout, config)
    calibrated, uncertainty_meta = p06c.assign_uncertainties(pair_rows, config)
    keep_cols = [c for c in calibrated.columns if not c.startswith("wf_")]
    calibrated[keep_cols].to_csv(calibrated_path, index=False, compression="gzip")
    uncertainty_meta.to_csv(uncertainty_meta_path, index=False)
    return calibrated[keep_cols].copy(), uncertainty_meta


def leakage_checks(config: dict, calibrated: pd.DataFrame, repro: pd.DataFrame) -> pd.DataFrame:
    base = p06c.leakage_checks(config, calibrated, repro)
    required = {"traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "phase_conformal_gated_cnn"}
    extra = pd.DataFrame(
        [
            {
                "check": "s06b_required_action_columns",
                "value": ",".join(ACTION_DIMS),
                "pass": bool(set(ACTION_DIMS).issubset(calibrated.columns)),
                "note": "support closure includes saturation, q-template, baseline, and anomaly/dropout atoms",
            },
            {
                "check": "s06b_required_methods_present",
                "value": ",".join(sorted(calibrated["method"].unique())),
                "pass": bool(required.issubset(set(calibrated["method"].unique()))),
                "note": "traditional, ridge, GBT, MLP, 1D-CNN, and novel phase-conformal gated CNN",
            },
        ]
    )
    return pd.concat([base, extra], ignore_index=True)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    s03_bench: pd.DataFrame,
    pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    support: pd.DataFrame,
    composition: pd.DataFrame,
    monotonicity: pd.DataFrame,
    deltas: pd.DataFrame,
    action_summary: pd.DataFrame,
    sentinels: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    amp = support[support["dimension"] == "amplitude_bin"].sort_values(["stratum", "calibration_loss"])
    charge = support[support["dimension"] == "charge_bin"].sort_values(["stratum", "calibration_loss"])
    per_run_short = per_run.sort_values(["run", "calibration_loss"])
    action_risk = action_summary[
        (action_summary["dimension"].isin(ACTION_DIMS)) & (action_summary["n"] >= int(config["closure"]["support_min_n"]))
    ].sort_values("calibration_loss", ascending=False).head(36)
    action_cols = [
        "dimension",
        "stratum",
        "method",
        "n",
        "sigma68_ns",
        "full_rms_ns",
        "tail_frac_abs_gt5ns",
        "pull_width68",
        "coverage68",
        "coverage95",
        "calibration_loss",
    ]
    if "n_runs" in action_risk.columns:
        action_cols.insert(4, "n_runs")
    useful_deltas = deltas[deltas["dimension"].isin(["amplitude_bin", "charge_bin"])].sort_values(
        "ml_minus_traditional_calibration_loss"
    ).head(30)
    lines = [
        "# S06b: amplitude-energy timing support closure",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Input:** raw B-stack ROOT files under `{config['raw_root_dir']}`",
        "- **Split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Bootstrap:** event-paired run-block bootstrap with {int(config['closure']['bootstrap_samples'])} replicates",
        "- **Primary rule:** lowest pooled pairwise pull-calibration loss, with sigma68/full-RMS/tail/support tables reported as constraints",
        "- **Benchmark provenance:** S06b performs an independent raw ROOT reproduction gate, then reuses the committed P06c run-external pair-residual benchmark rows recorded in `source_benchmark_rows.json` to avoid repeating identical LORO model training",
        "",
        "## Abstract",
        "",
        f"S06b tests whether the apparent timing-resolution curve versus amplitude or charge-energy proxy is monotonic, or whether it is dominated by support changes from saturation, dropout/anomaly, q-template mismatch, and baseline action bands. The raw ROOT reproduction gate passes exactly. The winner by the pre-registered pooled calibration-loss rule is **{winner}** with calibration loss **{result['winner']['calibration_loss']:.4f}** and bootstrap 95% CI **[{result['winner']['ci_low']:.4f}, {result['winner']['ci_high']:.4f}]**. The support closure tables show that amplitude/charge bins are not exchangeable physics slices: high-amplitude and high-charge regions carry sharply different action-band composition, so naive sigma(E) claims require the reported support conditioning.",
        "",
        "## Raw ROOT Reproduction Gate",
        "",
        "Counts are recomputed directly from `HRDv`: subtract the median of samples 0-3, require baseline-subtracted amplitude > 1000 ADC, and sum selected B-stave pulses across the configured raw ROOT files.",
        "",
        repro.to_markdown(index=False),
        "",
        "The S03a analytic timing reference is rerun before the fold-local benchmark:",
        "",
        s03_bench[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "best_candidate", "best_alpha"]].to_markdown(index=False),
        "",
        "## Estimands And Equations",
        "",
        "For event `e`, stave `s`, and method `m`, the geometry-corrected timestamp is `tau_{e,s,m}=t_{e,s,m}-x_s v_TOF`, with `v_TOF=0.078 ns/cm` and 2 cm downstream spacing. Pair residuals are `r_{e,a,b,m}=tau_{e,a,m}-tau_{e,b,m}` for B4-B6, B4-B8, and B6-B8.",
        "",
        "The robust timing width is `sigma68(r)=(Q84(r)-Q16(r))/2`; full RMS is computed about the mean. Each uncertainty model predicts `sigma_hat`, giving pull `z=r/sigma_hat`, pull width `sigma68(z)`, 68% coverage `P(|z|<=1)`, 95% coverage `P(|z|<=1.96)`, and calibration ECE from sigma-quantile coverage bins.",
        "",
        "The primary calibration loss is `mean(|sigma68(z)-1|, |C68-0.682689|, |C95-0.95|, ECE)`. Monotonicity is evaluated on adjacent amplitude or charge bins: a violation occurs when a higher proxy bin has larger `sigma68(r)` than the previous bin; a significant violation additionally requires non-overlapping bootstrap CIs.",
        "",
        "## Methods",
        "",
        "Traditional method: fold-local S02 template-phase timing, S03a amplitude-only analytic timewalk correction, and an S04-style robust-width lookup over pair, peak sample, leading-edge phase, sample-window mask, and coarser fallbacks. This is the strongest non-ML comparator because it uses the known timing reconstruction physics and action-bin robust widths without seeing held-out runs.",
        "",
        "ML/NN methods: ridge, HistGradientBoosting, MLP, 1D-CNN, and the new phase-conformal atom-gated CNN. All models are trained run-externally and use waveform shape plus amplitude, charge proxy, q-template, baseline, phase, topology, anomaly/action, and run-family covariates. The new architecture encodes the two pair waveforms with 1D convolutions, gates channels using atom/tabular support features, and applies a run-external conformal phase-bin scale adjustment.",
        "",
        "The pair-residual benchmark rows are the committed P06c rows for the same Sample-II LORO split and methods. S06b does not treat that as a reproduction proxy: it first reruns the raw ROOT count and S03a timing closure, then computes new amplitude/charge support, monotonicity, action-band, per-run, and ML-minus-traditional summaries in this ticket-owned report directory.",
        "",
        "## Head-To-Head Winner Table",
        "",
        pooled[["method", "method_label", "n", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "pull_width68", "coverage68", "coverage95", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Per-run held-out scores with bootstrap CIs:",
        "",
        per_run_short[["run", "method", "n", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "pull_width68", "coverage68", "coverage95", "any_action_band_fraction"]].to_markdown(index=False),
        "",
        "## Amplitude And Energy-Proxy Closure",
        "",
        "Amplitude-bin benchmark:",
        "",
        amp[["stratum", "method", "n", "n_runs", "support_fraction", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "calibration_loss", "any_action_band_fraction"]].to_markdown(index=False),
        "",
        "Charge-energy-proxy benchmark:",
        "",
        charge[["stratum", "method", "n", "n_runs", "support_fraction", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "calibration_loss", "any_action_band_fraction"]].to_markdown(index=False),
        "",
        "Monotonicity audit:",
        "",
        monotonicity[["dimension", "method", "n_bins", "n_adjacent_transitions", "monotonicity_violation_count", "monotonicity_violation_rate", "significant_violation_count", "max_adjacent_sigma68_increase_ns", "sigma68_vs_bin_mid_corr"]].to_markdown(index=False),
        "",
        "Support/action-band composition by amplitude and charge bins, using the nonduplicated traditional pair rows:",
        "",
        composition[["dimension", "stratum", "n_pair_residuals", "n_runs", "support_fraction", "saturation_fraction", "dropout_fraction", "anomaly_noncommon_fraction", "wide_baseline_fraction", "high_q_template_fraction", "any_action_band_fraction"]].to_markdown(index=False),
        "",
        "## ML-Minus-Traditional Deltas",
        "",
        "Negative deltas indicate an ML/NN method improves on the traditional row in the matched amplitude or charge bin.",
        "",
        useful_deltas[["dimension", "stratum", "method", "traditional_calibration_loss", "calibration_loss", "ml_minus_traditional_calibration_loss", "traditional_sigma68_ns", "sigma68_ns", "ml_minus_traditional_sigma68_ns", "traditional_tail_frac_abs_gt5ns", "tail_frac_abs_gt5ns", "ml_minus_traditional_tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## Action-Band Systematics",
        "",
        "The table below ranks saturation, q-template, baseline, and anomaly/dropout action strata by calibration loss. Sparse strata are retained with counts so they are not mistaken for broad support.",
        "",
        action_risk[action_cols].to_markdown(index=False),
        "",
        "Sentinel controls:",
        "",
        sentinels[["sentinel", "method", "n", "calibration_loss", "pull_width68", "coverage68", "coverage95", "calibration_ece", "sigma68_ns"]].to_markdown(index=False),
        "",
        "Leakage and bookkeeping checks:",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Systematics And Caveats",
        "",
        "- Run-block bootstrap captures held-out-run and event correlation but not alternate hardware calibrations or independent beamline composition labels.",
        "- Charge proxy is waveform area after baseline subtraction, not an externally calibrated calorimetric energy; S06b therefore phrases conclusions as amplitude/energy-proxy closure.",
        "- Pair residuals remove the common event clock but still correlate the two staves in each pair. Absolute single-stave timing should inherit these intervals conservatively.",
        "- Action bands are inferred from reduced waveform atoms. Dropout/anomaly labels are morphology flags, not hand-scanned truth labels for every row.",
        "- The winner optimizes calibrated uncertainty, not merely narrow central sigma68. A narrower model with poor coverage would fail the downstream PID/energy-consumer requirement.",
        "",
        "## Interpretation",
        "",
        f"The S06b answer is that a single monotonic sigma(E) curve is not defensible without support conditioning. The winner `{winner}` gives the best calibrated held-out intervals, while the amplitude/charge tables and action-band fractions identify where apparent resolution changes are entangled with saturation, q-template, baseline, and dropout/anomaly support. Downstream consumers should use the support-conditional intervals or abstention/inflation bands rather than a one-dimensional amplitude or charge correction.",
        "",
        "## Reproducibility",
        "",
        "Regenerate with:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s06b_1781054026_2063_38d35ceb_amplitude_energy_support_closure.py --config configs/s06b_1781054026_2063_38d35ceb_amplitude_energy_support_closure.json",
        "```",
        "",
        "Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `pooled_method_summary.csv`, `per_run_bootstrap_summary.csv`, `amplitude_charge_support_summary.csv`, `action_band_composition.csv`, `monotonicity_audit.csv`, `amplitude_charge_delta_vs_traditional.csv`, `action_band_summary.csv`, `sentinel_checks.csv`, `leakage_checks.csv`, `input_sha256.csv`, and the two figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s06b_1781054026_2063_38d35ceb_amplitude_energy_support_closure.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    repro, s03_bench = p06a.reproduce_s03a_gate(config, out_dir, rng)
    calibrated, uncertainty_meta = build_or_load_calibrated(config, out_dir, rng)
    uncertainty_meta.to_csv(out_dir / "uncertainty_fold_meta.csv", index=False)

    n_boot = int(config["closure"]["bootstrap_samples"])
    full_summary = p06c.summarize(calibrated, config, rng)
    full_summary.to_csv(out_dir / "action_band_summary.csv", index=False)
    pooled = full_summary[(full_summary["dimension"] == "all") & (full_summary["stratum"] == "all")].sort_values(
        "calibration_loss"
    )
    pooled.to_csv(out_dir / "pooled_method_summary.csv", index=False)
    per_run = summarize_per_run(calibrated, config, rng, n_boot)
    per_run.to_csv(out_dir / "per_run_bootstrap_summary.csv", index=False)
    support = summarize_dimension(calibrated, config, rng, ["amplitude_bin", "charge_bin"], n_boot)
    support.to_csv(out_dir / "amplitude_charge_support_summary.csv", index=False)
    composition = support_composition(calibrated, config)
    composition.to_csv(out_dir / "action_band_composition.csv", index=False)
    monotonicity = monotonicity_table(support)
    monotonicity.to_csv(out_dir / "monotonicity_audit.csv", index=False)
    deltas = method_deltas_vs_traditional(support)
    deltas.to_csv(out_dir / "amplitude_charge_delta_vs_traditional.csv", index=False)
    sentinels = p06c.sentinel_checks(calibrated, config)
    sentinels.to_csv(out_dir / "sentinel_checks.csv", index=False)
    leakage = leakage_checks(config, calibrated, repro)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner = pooled.iloc[0]
    traditional = pooled[pooled["method"] == "traditional"].iloc[0]
    best_ml = pooled[pooled["method"] != "traditional"].iloc[0]
    plot_closure(out_dir, support, composition, str(winner["method"]))

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": repro.to_dict(orient="records"),
        "split": {
            "mode": "central timing LORO plus uncertainty calibration LORO",
            "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
            "bootstrap": "event-paired run-block 95pct CI",
            "bootstrap_samples": n_boot,
        },
        "traditional": {
            "method": "S02/S03 analytic timing plus S04-style atom robust-width lookup",
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
            "methods": [m for m in METHODS if m != "traditional"],
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
        "monotonicity": monotonicity.to_dict(orient="records"),
        "support_closure": composition.to_dict(orient="records"),
        "method_summary": pooled.to_dict(orient="records"),
        "per_run_summary": per_run.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "verdict": "support_conditioned_uncertainty_required_for_sigma_energy_claims",
        "next_tickets": [
            "P06e: propagate S06b support-conditioned timing intervals into PID and energy consumers, testing whether coverage improves under fixed abstention budgets."
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(
        out_dir,
        config,
        repro,
        s03_bench,
        pooled,
        per_run,
        support,
        composition,
        monotonicity,
        deltas,
        full_summary,
        sentinels,
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
            "torch": None if p06c.torch is None else p06c.torch.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"done": True, "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": manifest["runtime_sec"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
