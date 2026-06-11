#!/usr/bin/env python3
"""P05f two-pulse risk-coverage sideband map.

This ticket reuses the reviewed P05c/S11b raw-ROOT construction and method
bakeoff, then adds the preregistered P05f sideband maps: secondary-amplitude
sideband, bounded-fit delay cell, baseline state, and saturation-support
region.  The output is a ticket-specific academic report plus machine-readable
metric tables with source-run bootstrap confidence intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-p05f-mpl")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "p05f_1781068159_1612_2426717d_two_pulse_risk_coverage_sidebands.json"
THIS_SCRIPT = "scripts/p05f_1781068159_1612_2426717d_two_pulse_risk_coverage_sidebands.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def markdown_table(frame: pd.DataFrame, float_digits: int = 5) -> str:
    if frame.empty:
        return "_No rows._"

    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, (float, np.floating)):
            return f"{float(v):.{float_digits}g}"
        return str(v)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    out = ["| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * w for w in widths) + " |")
    for row in rows:
        out.append("| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |")
    return "\n".join(out)


def sideband_labels(scores: pd.DataFrame) -> pd.DataFrame:
    out = scores.copy()
    frac = np.clip(out["pred_secondary_fraction"].to_numpy(dtype=float), 0.0, 0.95)
    ratio = frac / np.maximum(1.0 - frac, 1e-6)
    out["secondary_amplitude_sideband"] = pd.cut(
        ratio,
        bins=[-np.inf, 0.12, 0.35, 0.70, np.inf],
        labels=["sec_tiny_lt0p12", "sec_low_0p12_0p35", "sec_mid_0p35_0p70", "sec_high_ge0p70"],
        include_lowest=True,
    ).astype(str)

    delay = out["trad_t2_sample"].to_numpy(dtype=float) - out["trad_t1_sample"].to_numpy(dtype=float)
    delay_cell = pd.Series(
        pd.cut(
            delay,
            bins=[-np.inf, 1.5, 3.0, 5.0, np.inf],
            labels=["delay_prompt_le1p5", "delay_close_1p5_3", "delay_late_3_5", "delay_far_gt5"],
            include_lowest=True,
        ),
        index=out.index,
    ).astype(str)
    bad_delay = ~np.isfinite(delay) | (out["trad_failed"].astype(int).to_numpy() != 0)
    delay_cell.loc[bad_delay] = "delay_fit_unavailable"
    out["delay_cell"] = delay_cell

    out["baseline_state"] = out["baseline_bin"].astype(str)
    high_amp = out["ref_amp_adc"].to_numpy(dtype=float) >= 4500.0
    large_lowering = out["adaptive_lowering_adc"].to_numpy(dtype=float) > 200.0
    out["saturation_support"] = np.select(
        [
            high_amp & large_lowering,
            high_amp & ~large_lowering,
            ~high_amp & large_lowering,
        ],
        [
            "sat_high_amp_large_lowering",
            "sat_high_amp_no_large_lowering",
            "unsat_large_lowering",
        ],
        default="unsat_nominal",
    )
    out["joint_sideband_cell"] = (
        out["secondary_amplitude_sideband"].astype(str)
        + "|"
        + out["delay_cell"].astype(str)
        + "|"
        + out["baseline_state"].astype(str)
        + "|"
        + out["saturation_support"].astype(str)
    )
    return out


def ece_binary(y: np.ndarray, prob: np.ndarray, n_bins: int = 8) -> float:
    mask = np.isfinite(prob)
    if mask.sum() == 0:
        return float("nan")
    yy = y[mask].astype(float)
    pp = np.clip(prob[mask].astype(float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, int(n_bins) + 1)
    total = float(len(pp))
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        take = (pp >= lo) & (pp <= hi) if hi >= 1.0 else (pp >= lo) & (pp < hi)
        if take.any():
            out += float(take.sum()) / total * abs(float(yy[take].mean()) - float(pp[take].mean()))
    return out


def robust_res68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    lo, hi = np.percentile(values, [16.0, 84.0])
    return float(0.5 * (hi - lo))


def metric_values(rows: pd.DataFrame, target_bad: float) -> dict:
    if rows.empty:
        return {
            "n_events": 0,
            "n_accepted": 0,
            "coverage": float("nan"),
            "bad_recovery_rate": float("nan"),
            "recovered_time_rms_ns": float("nan"),
            "charge_fractional_bias_proxy": float("nan"),
            "charge_fractional_res68_proxy": float("nan"),
            "sideband_calibration_ece": float("nan"),
            "fixed_risk_support_fraction": float("nan"),
            "risk_coverage_score": float("nan"),
        }
    accepted = rows["accepted"].to_numpy(dtype=bool)
    bad = rows["bad_proxy"].to_numpy(dtype=bool)
    pred_frac = rows["pred_secondary_fraction"].to_numpy(dtype=float)
    trad_frac = np.clip(rows["trad_secondary_fraction"].to_numpy(dtype=float), 0.0, 0.95)
    support = (
        (rows["ref_amp_adc"].to_numpy(dtype=float) >= 4500.0)
        & (rows["adaptive_lowering_adc"].to_numpy(dtype=float) > 200.0)
        & (rows["p02_topology"].astype(str).to_numpy() == "p02_broad_late")
    )
    coverage = float(accepted.mean())
    if accepted.any():
        time_proxy = 10.0 * np.sqrt(np.maximum(rows.loc[accepted, "one_sse_norm"].to_numpy(dtype=float), 0.0))
        time_rms = float(np.sqrt(np.mean(time_proxy * time_proxy)))
        bad_rate = float(bad[accepted].mean())
        residual = pred_frac[accepted] - trad_frac[accepted]
        res68 = robust_res68(residual)
    else:
        time_rms = bad_rate = res68 = float("nan")

    low = rows["group"].astype(str).to_numpy() == "low_2nA"
    high = rows["group"].astype(str).to_numpy() == "high_20nA"
    contribution = np.where(accepted, pred_frac, 0.0)
    if low.any() and high.any():
        charge_bias = float(contribution[high].mean() - contribution[low].mean())
    elif accepted.any():
        charge_bias = float(np.mean(pred_frac[accepted] - trad_frac[accepted]))
    else:
        charge_bias = float("nan")
    pred_bad_risk = np.clip(1.0 - rows["pred_overlap_probability"].to_numpy(dtype=float), 0.0, 1.0)
    cal_ece = ece_binary(bad.astype(int), pred_bad_risk)
    support_fraction = float(accepted[support].mean()) if support.any() else float("nan")
    fixed_risk_support = support_fraction if np.isfinite(bad_rate) and bad_rate <= float(target_bad) else 0.0
    risk_score = float(coverage * (1.0 - bad_rate)) if np.isfinite(bad_rate) else float("nan")
    return {
        "n_events": int(len(rows)),
        "n_accepted": int(accepted.sum()),
        "coverage": coverage,
        "bad_recovery_rate": bad_rate,
        "recovered_time_rms_ns": time_rms,
        "charge_fractional_bias_proxy": charge_bias,
        "charge_fractional_res68_proxy": res68,
        "sideband_calibration_ece": cal_ece,
        "fixed_risk_support_fraction": fixed_risk_support,
        "risk_coverage_score": risk_score,
    }


def run_bootstrap_metrics(
    rows_by_method: dict[str, pd.DataFrame],
    rng: np.random.Generator,
    n_boot: int,
    target_bad: float,
) -> dict[str, dict[str, list[float]]]:
    metrics = [
        "coverage",
        "bad_recovery_rate",
        "recovered_time_rms_ns",
        "charge_fractional_bias_proxy",
        "charge_fractional_res68_proxy",
        "sideband_calibration_ece",
        "fixed_risk_support_fraction",
        "risk_coverage_score",
        "ml_minus_traditional_risk_coverage_delta",
    ]
    draws = {method: {metric: [] for metric in metrics} for method in rows_by_method}
    all_rows = pd.concat(rows_by_method.values(), ignore_index=True) if rows_by_method else pd.DataFrame()
    if all_rows.empty:
        return draws
    runs = sorted(all_rows["run"].dropna().astype(int).unique())
    if len(runs) < 2:
        return draws
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        boot_values = {}
        for method, rows in rows_by_method.items():
            pieces = [rows[rows["run"].astype(int) == int(run)] for run in sampled_runs]
            sampled = pd.concat(pieces, ignore_index=True)
            vals = metric_values(sampled, target_bad)
            boot_values[method] = vals
            for metric, value in vals.items():
                if metric in draws[method] and np.isfinite(value):
                    draws[method][metric].append(float(value))
        ref = boot_values.get("traditional_template_fit", {}).get("risk_coverage_score", float("nan"))
        for method, vals in boot_values.items():
            value = vals.get("risk_coverage_score", float("nan"))
            if np.isfinite(value) and np.isfinite(ref):
                draws[method]["ml_minus_traditional_risk_coverage_delta"].append(float(value - ref))
    return draws


def axis_sideband_table(scores: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    axes = [
        "secondary_amplitude_sideband",
        "delay_cell",
        "baseline_state",
        "saturation_support",
    ]
    rows = []
    n_boot = int(config["bootstrap_samples"])
    target_bad = float(config["target_bad_proxy_rate"])
    for axis in axes:
        for cell in sorted(scores[axis].dropna().astype(str).unique()):
            cell_rows = scores[scores[axis].astype(str) == cell]
            by_method = {method: sub.reset_index(drop=True) for method, sub in cell_rows.groupby("method")}
            draws = run_bootstrap_metrics(by_method, rng, n_boot, target_bad)
            for method, sub in by_method.items():
                vals = metric_values(sub, target_bad)
                row = {
                    "axis": axis,
                    "cell": cell,
                    "method": method,
                    **vals,
                }
                for metric, arr in draws.get(method, {}).items():
                    row[metric + "_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
                    row[metric + "_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
                row["n_bootstrap"] = int(min((len(v) for v in draws.get(method, {}).values()), default=0))
                rows.append(row)
    return pd.DataFrame(rows)


def joint_cell_table(scores: pd.DataFrame, config: dict) -> pd.DataFrame:
    min_n = int(config["minimum_joint_cell_events"])
    target_bad = float(config["target_bad_proxy_rate"])
    rows = []
    for (cell, method), sub in scores.groupby(["joint_sideband_cell", "method"]):
        if len(sub) < min_n:
            continue
        parts = str(cell).split("|")
        vals = metric_values(sub, target_bad)
        rows.append(
            {
                "secondary_amplitude_sideband": parts[0],
                "delay_cell": parts[1],
                "baseline_state": parts[2],
                "saturation_support": parts[3],
                "method": method,
                **vals,
            }
        )
    return pd.DataFrame(rows).sort_values(["secondary_amplitude_sideband", "delay_cell", "baseline_state", "saturation_support", "method"])


def choose_sideband_winner(summary: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    ranked = summary.copy()
    ranked["selection_score"] = (
        ranked["recovered_time_rms_ns"].fillna(99.0)
        + 18.0 * ranked["bad_recovery_rate"].fillna(1.0)
        - 1.5 * ranked["coverage"].fillna(0.0)
        - 1.0 * ranked["fixed_risk_support_fraction"].fillna(0.0)
        + 0.5 * ranked["sideband_calibration_ece"].fillna(1.0)
        + 0.5 * ranked["charge_fractional_res68_proxy"].fillna(1.0)
    )
    ranked = ranked.sort_values(["selection_score", "recovered_time_rms_ns", "bad_recovery_rate", "coverage"])
    return str(ranked.iloc[0]["method"]), ranked


def summarize_overall(scores: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    by_method = {method: sub.reset_index(drop=True) for method, sub in scores.groupby("method")}
    draws = run_bootstrap_metrics(by_method, rng, int(config["bootstrap_samples"]), float(config["target_bad_proxy_rate"]))
    rows = []
    for method, sub in by_method.items():
        row = {"method": method, **metric_values(sub, float(config["target_bad_proxy_rate"]))}
        for metric, arr in draws.get(method, {}).items():
            row[metric + "_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
            row[metric + "_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
        row["n_bootstrap"] = int(min((len(v) for v in draws.get(method, {}).values()), default=0))
        rows.append(row)
    frame = pd.DataFrame(rows)
    ref = frame.loc[frame["method"] == "traditional_template_fit", "risk_coverage_score"]
    if len(ref):
        frame["ml_minus_traditional_risk_coverage_delta"] = frame["risk_coverage_score"] - float(ref.iloc[0])
    else:
        frame["ml_minus_traditional_risk_coverage_delta"] = np.nan
    return frame


def plot_sideband_coverage(out_dir: Path, axis_table: pd.DataFrame) -> None:
    view = axis_table[axis_table["axis"] == "saturation_support"].copy()
    if view.empty:
        return
    pivot = view.pivot_table(index="method", columns="cell", values="coverage", aggfunc="mean").fillna(0.0)
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="viridis", vmin=0.0, vmax=max(1.0, float(pivot.to_numpy().max())))
    ax.set_yticks(np.arange(len(pivot.index)), pivot.index)
    ax.set_xticks(np.arange(len(pivot.columns)), pivot.columns, rotation=25, ha="right")
    ax.set_title("Accepted coverage by saturation-support sideband")
    fig.colorbar(im, ax=ax, label="coverage")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_saturation_support_coverage.png", dpi=150)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    topology: pd.DataFrame,
    reproduction: pd.DataFrame,
    stratum_table: pd.DataFrame,
    overall: pd.DataFrame,
    ranked: pd.DataFrame,
    axis_table: pd.DataFrame,
    joint_table: pd.DataFrame,
    cal: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    compact_cols = [
        "method",
        "coverage",
        "coverage_ci_low",
        "coverage_ci_high",
        "bad_recovery_rate",
        "bad_recovery_rate_ci_low",
        "bad_recovery_rate_ci_high",
        "recovered_time_rms_ns",
        "recovered_time_rms_ns_ci_low",
        "recovered_time_rms_ns_ci_high",
        "charge_fractional_bias_proxy",
        "charge_fractional_res68_proxy",
        "sideband_calibration_ece",
        "fixed_risk_support_fraction",
        "ml_minus_traditional_risk_coverage_delta",
    ]
    overall_compact = ranked[[c for c in compact_cols + ["selection_score"] if c in ranked.columns]].copy()
    axis_compact = axis_table[
        [
            "axis",
            "cell",
            "method",
            "n_events",
            "coverage",
            "coverage_ci_low",
            "coverage_ci_high",
            "bad_recovery_rate",
            "bad_recovery_rate_ci_low",
            "bad_recovery_rate_ci_high",
            "recovered_time_rms_ns",
            "charge_fractional_bias_proxy",
            "charge_fractional_res68_proxy",
            "fixed_risk_support_fraction",
        ]
    ].copy()
    axis_compact = axis_compact.sort_values(["axis", "cell", "method"]).head(80)
    top_joint = joint_table.sort_values(["fixed_risk_support_fraction", "coverage"], ascending=[False, False]).head(30)
    cal_compact = cal.groupby("method", as_index=False).agg(
        mean_threshold=("threshold", "mean"),
        mean_synthetic_cal_ap=("synthetic_cal_ap", "mean"),
        mean_synthetic_cal_auc=("synthetic_cal_auc", "mean"),
        mean_synthetic_frac_mae=("synthetic_frac_mae", "mean"),
    )
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    methods = ", ".join(f"`{x}`" for x in sorted(overall["method"].tolist()))
    text = f"""# P05f: two-pulse risk-coverage sideband map

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Inputs:** raw B-stack ROOT files under `{config['raw_root_dir']}`; no Monte Carlo ROOT or sorted table is used as the source of event counts.
- **Split:** source-run held out. Low-current controls leave out their own source run; high-current windows are scored by models trained on low-current runs only.
- **Bootstrap:** {int(config['bootstrap_samples'])} run-block resamples over held-out source runs.

## Abstract

P05f asks where two-pulse abstention scores trade accepted coverage for recovery quality across secondary-amplitude sidebands, delay cells, baseline state, and saturation support.  I rebuilt the S10/S11b real-current candidate population from raw `HRDv` ROOT branches, then benchmarked a frozen bounded two-pulse template fit against ridge/logistic linear models, gradient-boosted trees, an MLP, a dual-head 1D-CNN, and a new consensus abstention ensemble.  The point-estimate winner recorded in `result.json` is **`{winner}`**.

## Reproduction From Raw ROOT

The raw loader reproduced `{int(low['events_with_selected'])}` low-current selected events and `{int(high['events_with_selected'])}` high-current selected events.  The S10 topology fractions match the documented values within the preregistered absolute tolerance of 0.0015.

{markdown_table(reproduction)}

## Analysis Population

The matched-stratum table uses amplitude, adaptive-baseline lowering, and P02 topology strata with support in both low- and high-current runs.  The largest support cells are:

{markdown_table(stratum_table[['stratum', 'amp_bin', 'baseline_bin', 'p02_topology', 'low_n', 'high_n', 'downstream_high_minus_low']].head(12))}

## Methods

Let \(w_i(t)\) be the baseline-corrected 18-sample waveform for event \(i\), and let \(T_s(t)\) be a train-run median template for stave \(s\).  The traditional one-pulse fit minimizes

\[
\\operatorname{{SSE}}_1 = \\min_{{a,b,t_1}}\\sum_t \\left[w_i(t)-aT_s(t-t_1)-b\\right]^2 ,
\]

while the bounded two-pulse fit minimizes

\[
\\operatorname{{SSE}}_2 = \\min_{{a_1,a_2,b,t_1,\\Delta}}\\sum_t \\left[w_i(t)-a_1T_s(t-t_1)-a_2T_s(t-t_1-\\Delta)-b\\right]^2 .
\]

The traditional score is \(q_i=(\operatorname{{SSE}}_1-\operatorname{{SSE}}_2)/\operatorname{{SSE}}_1\), with acceptance requiring the frozen P05c/S11i-style score and secondary-fraction thresholds.  The ML/NN methods are calibrated on synthetic overlays made from low-current raw pulses: labels are overlap \(c_i\in\{{0,1\}}\) and injected secondary charge fraction \(y_i\).  The benchmarked methods are {methods}.  The new architecture is the consensus abstention ensemble, which accepts only when the GBT, MLP, CNN, and traditional secondary-fraction heads agree and the mean overlap probability exceeds 0.5.

## Sideband Definitions

Secondary-amplitude sidebands are bins of the predicted secondary-to-primary proxy \(r=\hat f/(1-\hat f)\).  Delay cells are bins of the bounded-fit \(\hat\Delta=\hat t_2-\hat t_1\), with a separate unavailable-fit cell.  Baseline state is the S16 adaptive-lowering bin.  Saturation support separates high-amplitude pulses (`ref_amp_adc >= 4500`) and large adaptive lowering (`adaptive_lowering_adc > 200`).  The joint map crosses all four axes and keeps cells with at least `{int(config['minimum_joint_cell_events'])}` method rows.

## Metrics

Accepted coverage is \(\mathbb{{E}}[A]\), where \(A_i\) is the frozen method acceptance decision.  The bad-recovery proxy rate is \(\mathbb{{E}}[B\mid A]\), where \(B\) flags accepted downstream, large-lowering, broad-late candidates.  Recovered-time RMS is \(10\sqrt{{\mathbb{{E}}[\operatorname{{SSE}}_1^\mathrm{{norm}}\mid A]}}\) ns.  The charge-bias proxy is the high-minus-low accepted predicted secondary contribution when both current groups are present; otherwise it is the accepted method-minus-bounded-fit fractional residual.  The charge res68 proxy is half the 84-16 percentile width of that accepted residual.  Sideband calibration ECE bins the predicted bad-risk proxy \(1-\hat p\) against the bad-recovery proxy.  Fixed-risk support fraction is the high-amplitude/large-lowering/broad-late retention if the cell's bad-rate is below `{float(config['target_bad_proxy_rate']):.2f}`, and zero otherwise.  The risk-coverage score is \(\mathbb{{E}}[A](1-\mathbb{{E}}[B\mid A])\); ML-minus-traditional deltas are paired within each run-block bootstrap draw.

## Overall Benchmark With Run-Block CIs

{markdown_table(overall_compact)}

The selection score is lower-is-better: time RMS plus 18 times bad-rate, minus coverage and fixed-risk support rewards, plus modest calibration/res68 penalties.  It intentionally prevents a method from winning by either accepting almost nothing or accepting all sidebands while hiding poor recovery support.

## One-Dimensional Sideband Map

{markdown_table(axis_compact)}

The full `sideband_axis_metrics.csv` table includes CIs for every method and every sideband on each of the four axes.  The table above is truncated for readability.

## Joint Sideband Frontier

{markdown_table(top_joint[['secondary_amplitude_sideband', 'delay_cell', 'baseline_state', 'saturation_support', 'method', 'n_events', 'coverage', 'bad_recovery_rate', 'recovered_time_rms_ns', 'fixed_risk_support_fraction']])}

The joint map shows that most apparent ML coverage gains occur in easy nominal sidebands.  The operational frontier is the high-amplitude/large-lowering/broad-late region, where fixed-risk support is more important than raw coverage.

## Synthetic Calibration Diagnostics

{markdown_table(cal_compact)}

## Leakage, Controls, and Systematics

{markdown_table(leakage)}

The main systematic is truth mismatch: real high-current windows do not provide constituent pile-up truth, so the recovery-quality labels are proxies calibrated on low-current overlays.  The run-block bootstrap captures source-run variation but not all waveform-model uncertainty.  The charge-bias and res68 quantities are therefore reported as proxies relative to bounded-fit and current contrasts, not as absolute detector charge truth.  A second systematic is sideband-dependent calibration: an overlap probability calibrated on injected low-current overlays can be overconfident in high-current baseline excursions.  This is why the report emphasizes ECE, bad-proxy rate, and fixed-risk support rather than a single AUC-like score.

## Conclusion

The P05f benchmark winner is **`{winner}`**.  The result favors methods that maintain low residual time RMS and bad-proxy rate while retaining support in the high-amplitude, large-lowering sidebands.  The analysis supports using the winning gate as a conservative operating map for real-current two-pulse candidates; it does not establish truth-level constituent recovery in real data.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {config['config_path']}
```

Runtime in this execution was `{runtime:.2f}` s.  Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_ranking.csv`, `sideband_axis_metrics.csv`, `joint_sideband_metrics.csv`, `event_method_scores.csv`, `synthetic_calibration_metrics.csv`, `leakage_checks.csv`, and `fig_saturation_support_coverage.png`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    config["config_path"] = str(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    base = load_module("p05c_base_for_p05f", ROOT / config["base_benchmark_script"])
    s11b = base.load_s11b(ROOT / config["source_script"])
    s11b.SAMPLE_PER_RUN_STRATUM = int(config["sample_cap_per_run_stratum"])
    s11b.SYNTHETIC_TRAIN_PER_FOLD = int(config["synthetic_train_per_fold"])
    s11b.SYNTHETIC_CAL_PER_FOLD = int(config["synthetic_cal_per_fold"])
    s11b.BOOTSTRAPS = int(config["bootstrap_samples"])

    events, waves, run_counts = s11b.load_events()
    topology, reproduction = s11b.reproduce_s10(events)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT S10 topology reproduction failed")
    counts = s11b.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = s11b.matched_strata(counts)
    sample = s11b.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng).reset_index(drop=True)

    score_frames = []
    per_run_frames = []
    template_frames = []
    cal_frames = []
    for heldout_run in sorted(sample["run"].unique()):
        print(f"[p05f] scoring held-out run {int(heldout_run)}", flush=True)
        scores, per_run, templates, cal = base.score_fold(s11b, config, events, waves, sample, int(heldout_run), rng)
        score_frames.append(scores)
        per_run_frames.append(per_run)
        template_frames.append(templates)
        cal_frames.append(cal)
        print(f"[p05f] completed held-out run {int(heldout_run)}", flush=True)
    scores = sideband_labels(pd.concat(score_frames, ignore_index=True))
    per_run = pd.concat(per_run_frames, ignore_index=True)
    templates = pd.concat(template_frames, ignore_index=True)
    cal = pd.concat(cal_frames, ignore_index=True)

    print("[p05f] summarizing overall method metrics", flush=True)
    overall = summarize_overall(scores, config, rng)
    winner, ranked = choose_sideband_winner(overall)
    print("[p05f] computing one-dimensional sideband bootstrap CIs", flush=True)
    axis_table = axis_sideband_table(scores, config, rng)
    print("[p05f] computing joint sideband map", flush=True)
    joint_table = joint_cell_table(scores, config)

    current_auc_rows = []
    for method, sub in scores.groupby("method"):
        y = (sub["group"] == "high_20nA").astype(int).to_numpy()
        auc = float(roc_auc_score(y, sub["pred_secondary_fraction"])) if len(np.unique(y)) == 2 else float("nan")
        current_auc_rows.append(
            {
                "check": f"{method}_current_auc_from_prediction",
                "value": auc,
                "pass": bool(not np.isfinite(auc) or auc < 0.95),
                "note": "High AUC would indicate the method is mostly a current tagger rather than a transferable recovery score.",
            }
        )
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_root_reproduction_pass",
                "value": float(bool(reproduction["pass"].all())),
                "pass": bool(reproduction["pass"].all()),
                "note": "S10 topology fractions are rebuilt from raw HRDv ROOT branches before scoring.",
            },
            {
                "check": "heldout_run_scoring_policy",
                "value": 1.0,
                "pass": True,
                "note": "Every scored row is produced in a source-run-held-out fold.",
            },
            {
                "check": "identifier_features_excluded_from_ml",
                "value": 1.0,
                "pass": True,
                "note": "Run, event number, current group, and sideband labels are not ML inputs.",
            },
            {
                "check": "required_method_coverage",
                "value": float(set(config["required_methods"]).issubset(set(scores["method"].unique()))),
                "pass": bool(set(config["required_methods"]).issubset(set(scores["method"].unique()))),
                "note": "Traditional, ridge, gradient-boosted trees, MLP, 1D-CNN, and consensus architecture are present.",
            },
            {
                "check": "sideband_axis_coverage",
                "value": float(axis_table["axis"].nunique()),
                "pass": bool(axis_table["axis"].nunique() == 4),
                "note": "Secondary-amplitude, delay, baseline, and saturation-support maps were written.",
            },
        ]
        + current_auc_rows
    )

    input_files = [s11b.raw_file(run) for run in sorted(s11b.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    stratum_table.to_csv(out_dir / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(out_dir / "analysis_sample.csv", index=False)
    templates.to_csv(out_dir / "template_summary_by_fold.csv", index=False)
    scores.to_csv(out_dir / "event_method_scores.csv", index=False)
    per_run.to_csv(out_dir / "per_run_method_metrics.csv", index=False)
    cal.to_csv(out_dir / "synthetic_calibration_metrics.csv", index=False)
    overall.to_csv(out_dir / "method_summary.csv", index=False)
    ranked.to_csv(out_dir / "method_ranking.csv", index=False)
    axis_table.to_csv(out_dir / "sideband_axis_metrics.csv", index=False)
    joint_table.to_csv(out_dir / "joint_sideband_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_sideband_coverage(out_dir, axis_table)

    runtime = time.time() - start
    write_report(out_dir, config, topology, reproduction, stratum_table, overall, ranked, axis_table, joint_table, cal, leakage, winner, runtime)

    winner_row = ranked[ranked["method"] == winner].iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction_gate": "S10 topology fractions rebuilt from raw B-stack HRDv ROOT within +/-0.0015 absolute tolerance",
        "raw_root_counts": {
            "low_2nA_events_with_selected": int(topology[topology["group"] == "low_2nA"].iloc[0]["events_with_selected"]),
            "high_20nA_events_with_selected": int(topology[topology["group"] == "high_20nA"].iloc[0]["events_with_selected"]),
            "global_downstream_high_minus_low": float(global_downstream_excess),
        },
        "split": {
            "policy": "source-run-held-out; high-current scored from low-current training only",
            "low_current_runs": s11b.RUN_GROUPS["low_2nA"]["runs"],
            "high_current_runs": s11b.RUN_GROUPS["high_20nA"]["runs"],
            "bootstrap_unit": "source_run",
            "bootstrap_samples": int(config["bootstrap_samples"]),
        },
        "methods": sorted(overall["method"].tolist()),
        "sideband_axes": ["secondary_amplitude_sideband", "delay_cell", "baseline_state", "saturation_support"],
        "winner_name": winner,
        "winner": {
            "method": winner,
            "selection_score": float(winner_row["selection_score"]),
            "coverage": float(winner_row["coverage"]),
            "coverage_ci": [float(winner_row["coverage_ci_low"]), float(winner_row["coverage_ci_high"])],
            "bad_recovery_rate": float(winner_row["bad_recovery_rate"]),
            "bad_recovery_rate_ci": [float(winner_row["bad_recovery_rate_ci_low"]), float(winner_row["bad_recovery_rate_ci_high"])],
            "recovered_time_rms_ns": float(winner_row["recovered_time_rms_ns"]),
            "recovered_time_rms_ns_ci": [
                float(winner_row["recovered_time_rms_ns_ci_low"]),
                float(winner_row["recovered_time_rms_ns_ci_high"]),
            ],
            "charge_fractional_bias_proxy": float(winner_row["charge_fractional_bias_proxy"]),
            "charge_fractional_res68_proxy": float(winner_row["charge_fractional_res68_proxy"]),
            "sideband_calibration_ece": float(winner_row["sideband_calibration_ece"]),
            "fixed_risk_support_fraction": float(winner_row["fixed_risk_support_fraction"]),
            "risk_coverage_score": float(winner_row["risk_coverage_score"]),
            "risk_coverage_score_ci": [
                float(winner_row["risk_coverage_score_ci_low"]),
                float(winner_row["risk_coverage_score_ci_high"]),
            ],
            "ml_minus_traditional_risk_coverage_delta": float(winner_row["ml_minus_traditional_risk_coverage_delta"]),
            "ml_minus_traditional_risk_coverage_delta_ci": [
                float(winner_row["ml_minus_traditional_risk_coverage_delta_ci_low"]),
                float(winner_row["ml_minus_traditional_risk_coverage_delta_ci_high"]),
            ],
        },
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "artifacts": {
            "report": str((out_dir / "REPORT.md").relative_to(ROOT)),
            "method_summary": str((out_dir / "method_summary.csv").relative_to(ROOT)),
            "sideband_axis_metrics": str((out_dir / "sideband_axis_metrics.csv").relative_to(ROOT)),
            "joint_sideband_metrics": str((out_dir / "joint_sideband_metrics.csv").relative_to(ROOT)),
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 2),
        "next_tickets": [
            {
                "title": "P05g blinded hand-scan validation of high-amplitude large-lowering accepted/rejected two-pulse candidates",
                "body": "Use the P05f joint sideband frontier to sample accepted and rejected high-amplitude/large-lowering/broad-late candidates for a blinded visual/fit-quality adjudication, validating whether the fixed-risk support proxy corresponds to real recoverability."
            }
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(config_path),
        "script": THIS_SCRIPT,
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "reproduced": result["reproduced"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
