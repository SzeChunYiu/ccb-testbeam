#!/usr/bin/env python3
"""P04x retained-support charge-interval calibration.

This study is a direct interval-calibration layer on the P04w leave-one-run-out
prediction panel. It independently rebuilds the raw ROOT gate and A/B event
rows, joins the out-of-fold predictions, then asks whether any retained support
cell has simultaneously narrow calibrated intervals, calibrated coverage, and
real-vs-sentinel separation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04c_ab_event_matched_charge_transfer as p04c  # noqa: E402
import p04w_1781065299_620_6b5f516e_external_charge_abstention_frontier as p04w  # noqa: E402


METHODS = [
    "topology_median",
    "strong_huber_transfer",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "support_gated_residual_cnn",
    "topology_only_sentinel",
    "shuffled_target_hgb",
]

FAMILY = {
    "topology_median": "traditional",
    "strong_huber_transfer": "traditional",
    "ridge": "ml",
    "gradient_boosted_trees": "ml",
    "mlp": "ml",
    "1d_cnn": "nn",
    "support_gated_residual_cnn": "new_architecture",
    "topology_only_sentinel": "negative_control",
    "shuffled_target_hgb": "negative_control",
}


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(abs_frac <= 0.10)),
        "within_25pct": float(np.mean(abs_frac <= 0.25)),
    }


def run_block_ci(frame: pd.DataFrame, method: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {k: [None, None] for k in ["res68_ci95", "full_rms_ci95", "coverage68_ci95", "coverage90_ci95", "width68_ci95"]}
    by_run = {run: frame[frame["run"].eq(run)].copy() for run in runs}
    vals = {key: [] for key in ["res68", "rms", "cov68", "cov90", "width68"]}
    for _ in range(reps):
        boot = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        y = boot["target_a_charge"].to_numpy(dtype=float)
        pred = boot[f"pred_{method}"].to_numpy(dtype=float)
        m = robust_metrics(y, pred)
        vals["res68"].append(m["res68_abs_frac"])
        vals["rms"].append(m["full_rms_frac"])
        vals["cov68"].append(float(np.mean(boot[f"covered68_{method}"].to_numpy(dtype=bool))))
        vals["cov90"].append(float(np.mean(boot[f"covered90_{method}"].to_numpy(dtype=bool))))
        vals["width68"].append(float(np.mean(boot[f"width68_frac_{method}"].to_numpy(dtype=float))))
    return {
        "res68_ci95": [float(np.percentile(vals["res68"], 2.5)), float(np.percentile(vals["res68"], 97.5))],
        "full_rms_ci95": [float(np.percentile(vals["rms"], 2.5)), float(np.percentile(vals["rms"], 97.5))],
        "coverage68_ci95": [float(np.percentile(vals["cov68"], 2.5)), float(np.percentile(vals["cov68"], 97.5))],
        "coverage90_ci95": [float(np.percentile(vals["cov90"], 2.5)), float(np.percentile(vals["cov90"], 97.5))],
        "width68_ci95": [float(np.percentile(vals["width68"], 2.5)), float(np.percentile(vals["width68"], 97.5))],
    }


def support_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["support_cell_p04x"] = (
        out["a_topology"].astype(str)
        + "|"
        + out["topology_pattern"].astype(str)
        + "|"
        + out["b2_amp_bin"].astype(str)
        + "|"
        + out["saturation_stratum"].astype(str)
        + "|"
        + out["anomaly_stratum"].astype(str)
        + "|"
        + out["baseline_bin"].astype(str)
        + "|"
        + out["peak_phase_bin"].astype(str)
        + "|"
        + out["q_template_bin"].astype(str)
    )
    out["support_cell_mid"] = (
        out["a_topology"].astype(str)
        + "|"
        + out["topology_pattern"].astype(str)
        + "|"
        + out["b2_amp_bin"].astype(str)
        + "|"
        + out["saturation_stratum"].astype(str)
        + "|"
        + out["anomaly_stratum"].astype(str)
    )
    out["support_cell_coarse"] = out["topology_pattern"].astype(str) + "|" + out["b2_amp_bin"].astype(str)
    return out


def calibrate_intervals(config: dict, frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    y = work["target_a_charge"].to_numpy(dtype=float)
    for method in METHODS:
        resid = np.abs((work[f"pred_{method}"].to_numpy(dtype=float) - y) / np.maximum(y, 1.0))
        work[f"absfrac_{method}"] = resid
        for level in [68, 90]:
            work[f"q{level}_{method}"] = np.nan
            work[f"interval_source{level}_{method}"] = ""
            work[f"covered{level}_{method}"] = False
            work[f"width{level}_frac_{method}"] = np.nan

    for heldout_run in sorted(work["run"].unique()):
        held = work["run"].eq(int(heldout_run))
        train = ~held
        for method in METHODS:
            for alpha, level in [(0.68, 68), (0.90, 90)]:
                train_tmp = work.loc[train, ["support_cell_p04x", "support_cell_mid", "support_cell_coarse", f"absfrac_{method}"]].copy()
                global_q = float(np.quantile(train_tmp[f"absfrac_{method}"], alpha))
                quantiles: List[Tuple[str, int]] = [
                    ("support_cell_p04x", int(config["strong_support_rows"])),
                    ("support_cell_mid", int(config["strong_support_rows"])),
                    ("support_cell_coarse", int(config["min_support_rows"])),
                ]
                assigned = np.full(int(held.sum()), global_q, dtype=float)
                source = np.array(["global_train_runs"] * int(held.sum()), dtype=object)
                held_index = work.index[held]
                for col, min_rows in reversed(quantiles):
                    stats = train_tmp.groupby(col, observed=True)[f"absfrac_{method}"].agg(["count", lambda s: np.quantile(s, alpha)])
                    stats.columns = ["count", "q"]
                    mapper = stats[stats["count"] >= min_rows]["q"].to_dict()
                    vals = work.loc[held, col].map(mapper)
                    mask = vals.notna().to_numpy()
                    assigned[mask] = vals[mask].to_numpy(dtype=float)
                    source[mask] = col
                work.loc[held_index, f"q{level}_{method}"] = assigned
                work.loc[held_index, f"interval_source{level}_{method}"] = source
                work.loc[held_index, f"covered{level}_{method}"] = work.loc[held_index, f"absfrac_{method}"].to_numpy(dtype=float) <= assigned
                pred = work.loc[held_index, f"pred_{method}"].to_numpy(dtype=float)
                work.loc[held_index, f"width{level}_frac_{method}"] = 2.0 * assigned * pred / np.maximum(work.loc[held_index, "target_a_charge"].to_numpy(dtype=float), 1.0)
    return work


def summarize_methods(config: dict, work: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    for method in METHODS:
        row = {"method": method, "family": FAMILY[method], "split": "leave_one_run_out"}
        row.update(robust_metrics(work["target_a_charge"].to_numpy(dtype=float), work[f"pred_{method}"].to_numpy(dtype=float)))
        row["coverage68"] = float(work[f"covered68_{method}"].mean())
        row["coverage90"] = float(work[f"covered90_{method}"].mean())
        row["mean_width68_frac"] = float(work[f"width68_frac_{method}"].mean())
        row["mean_width90_frac"] = float(work[f"width90_frac_{method}"].mean())
        row["full_cell_interval_fraction68"] = float(work[f"interval_source68_{method}"].eq("support_cell_p04x").mean())
        row.update(run_block_ci(work, method, rng, int(config["bootstrap_reps"])))
        rows.append(row)
    return pd.DataFrame(rows)


def support_cell_summary(config: dict, work: pd.DataFrame, method_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    shuf = "shuffled_target_hgb"
    topo = "topology_only_sentinel"
    gates = config["interval_acceptance"]
    for method in [m for m in METHODS if FAMILY[m] != "negative_control"]:
        for cell, sub in work.groupby("support_cell_p04x", observed=True):
            if len(sub) < int(config["min_support_rows"]) or sub["run"].nunique() < int(config["min_support_runs"]):
                continue
            row = {
                "method": method,
                "support_cell": str(cell),
                "n": int(len(sub)),
                "n_runs": int(sub["run"].nunique()),
                "retained_fraction": float(len(sub) / len(work)),
                "a_topology": str(sub["a_topology"].iloc[0]),
                "topology_pattern": str(sub["topology_pattern"].iloc[0]),
                "b2_amp_bin": str(sub["b2_amp_bin"].iloc[0]),
                "saturation_stratum": str(sub["saturation_stratum"].iloc[0]),
                "anomaly_stratum": str(sub["anomaly_stratum"].iloc[0]),
                "baseline_bin": str(sub["baseline_bin"].iloc[0]),
                "peak_phase_bin": str(sub["peak_phase_bin"].iloc[0]),
                "q_template_bin": str(sub["q_template_bin"].iloc[0]),
            }
            row.update(robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub[f"pred_{method}"].to_numpy(dtype=float)))
            row["coverage68"] = float(sub[f"covered68_{method}"].mean())
            row["coverage90"] = float(sub[f"covered90_{method}"].mean())
            row["mean_width68_frac"] = float(sub[f"width68_frac_{method}"].mean())
            row["mean_width90_frac"] = float(sub[f"width90_frac_{method}"].mean())
            shuf_m = robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub[f"pred_{shuf}"].to_numpy(dtype=float))
            topo_m = robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub[f"pred_{topo}"].to_numpy(dtype=float))
            row["shuffled_res68_abs_frac"] = shuf_m["res68_abs_frac"]
            row["topology_only_res68_abs_frac"] = topo_m["res68_abs_frac"]
            row["real_minus_shuffled_res68"] = row["res68_abs_frac"] - row["shuffled_res68_abs_frac"]
            row["real_minus_topology_res68"] = row["res68_abs_frac"] - row["topology_only_res68_abs_frac"]
            row["accepted_support_cell"] = bool(
                row["retained_fraction"] >= float(gates["min_retained_fraction"])
                and row["n"] >= int(config["strong_support_rows"])
                and row["n_runs"] >= int(config["strong_support_runs"])
                and row["res68_abs_frac"] <= float(gates["max_res68_abs_frac"])
                and row["mean_width68_frac"] <= float(gates["max_mean_width68_frac"])
                and float(gates["min_coverage68"]) <= row["coverage68"] <= float(gates["max_coverage68"])
                and float(gates["min_coverage90"]) <= row["coverage90"] <= float(gates["max_coverage90"])
                and row["real_minus_shuffled_res68"] <= float(gates["max_real_minus_shuffled_res68"])
                and row["real_minus_topology_res68"] <= float(gates["max_real_minus_topology_res68"])
            )
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["accepted_support_cell", "res68_abs_frac", "retained_fraction"], ascending=[False, True, False]
    )


def retention_frontier(config: dict, work: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in [m for m in METHODS if FAMILY[m] != "negative_control"]:
        score = work[f"q68_{method}"].to_numpy(dtype=float)
        order = np.argsort(score, kind="mergesort")
        for frac in config["retention_accept_fractions"]:
            keep = order[: max(1, int(round(float(frac) * len(work))))]
            sub = work.iloc[keep]
            row = {"method": method, "accepted_fraction": float(len(sub) / len(work)), "n": int(len(sub)), "n_runs": int(sub["run"].nunique())}
            row.update(robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub[f"pred_{method}"].to_numpy(dtype=float)))
            row["coverage68"] = float(sub[f"covered68_{method}"].mean())
            row["coverage90"] = float(sub[f"covered90_{method}"].mean())
            row["mean_width68_frac"] = float(sub[f"width68_frac_{method}"].mean())
            row["mean_width90_frac"] = float(sub[f"width90_frac_{method}"].mean())
            rows.append(row)
    return pd.DataFrame(rows)


def make_plot(out_dir: Path, summary: pd.DataFrame) -> None:
    show = summary[summary["family"].ne("negative_control")].copy().sort_values("res68_abs_frac")
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    y = np.arange(len(show))
    xerr = np.vstack(
        [
            show["res68_abs_frac"].to_numpy() - np.array([v[0] for v in show["res68_ci95"]]),
            np.array([v[1] for v in show["res68_ci95"]]) - show["res68_abs_frac"].to_numpy(),
        ]
    )
    colors = show["family"].map({"traditional": "#4c78a8", "ml": "#f58518", "nn": "#54a24b", "new_architecture": "#b279a2"}).fillna("#777777")
    ax.barh(y, show["res68_abs_frac"], xerr=xerr, color=colors, alpha=0.88)
    ax.set_yticks(y)
    ax.set_yticklabels(show["method"])
    ax.invert_yaxis()
    ax.set_xlabel("held-out fractional res68 with run-block 95% CI")
    ax.set_title("P04x charge-transfer method benchmark")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "head_to_head_res68_ci.png", dpi=180)
    plt.close(fig)


def markdown_table(df: pd.DataFrame, columns: List[str], n: int | None = None) -> str:
    sub = df[columns].copy()
    if n is not None:
        sub = sub.head(n)
    return sub.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    p04c_summary: pd.DataFrame,
    method_summary: pd.DataFrame,
    cells: pd.DataFrame,
    frontier: pd.DataFrame,
    result: dict,
) -> None:
    expected = int(config["expected_b_s00_selected_pulses"])
    got = int(b_counts["selected_pulses"].sum())
    eligible = method_summary[method_summary["family"].ne("negative_control")]
    best = eligible.sort_values("res68_abs_frac").iloc[0]
    best_trad = eligible[eligible["family"].eq("traditional")].sort_values("res68_abs_frac").iloc[0]
    best_ml = eligible[eligible["family"].isin(["ml", "nn", "new_architecture"])].sort_values("res68_abs_frac").iloc[0]
    lines = [
        "# P04x Retained-Support Charge-Interval Calibration",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo truth.",
        "- **Split:** leave-one-run-out by run; bootstrap intervals resample complete held-out run blocks.",
        "- **Target:** event-matched selected A1/A3 positive-lobe charge predicted from B-stack waveforms and support variables.",
        "- **Predecessor:** P04w out-of-fold predictions are used as the fixed method panel; P04x independently rebuilds raw gates and event rows before interval calibration.",
        "",
        "## 0. Question",
        "",
        "After P04w/P04j indicated broad but nominally calibrated external charge behavior, is there any retained raw-HRD support cell in which fractional charge residual width, conformal interval coverage, interval width, and real-minus-sentinel separation are simultaneously acceptable?",
        "",
        "## 1. Reproduction From Raw ROOT",
        "",
        "The gate is rebuilt from raw `HRDv` samples. For each channel, the median of samples 0--3 is subtracted; a pulse is selected when the corrected peak exceeds 1000 ADC. The P04x event table is then rebuilt from `(run, EVT)` matches with selected B2 and selected A1 or A3.",
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|:---|",
        f"| B-stack selected pulse records | {expected:,} | {got:,} | {got - expected:+,} | 0 | {str(got == expected).lower()} |",
        "",
        markdown_table(a_counts, ["sample", "events_with_selected", "selected_pulses", "A1", "A3"]),
        "",
        "The ticket-local P04c charge-transfer reproduction on the same raw-derived rows is:",
        "",
        markdown_table(p04c_summary, ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_25pct"]),
        "",
        "## 2. Methods",
        "",
        "For event \(i\), the external charge target is",
        "",
        "`Q_i^A = I(A1_i) sum_t max(A1_it, 0) + I(A3_i) sum_t max(A3_it, 0)`,",
        "",
        "where each indicator requires the raw-ROOT A-stack amplitude gate. Each method predicts `log(max(Q_i^A,1))` using B-stack waveform/support information only; run, event number, A-stack flags, and A-stack charge are excluded from predictor features.",
        "",
        "The benchmark residual is",
        "",
        "`r_i(m) = (hat Q_i(m) - Q_i^A) / max(Q_i^A, 1)`,",
        "",
        "with primary width `res68_m = quantile_0.68(|r_i(m)|)`. The strong traditional methods are topology/support-cell median and Huber log-charge transfer. The ML/NN panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, and the new support-gated residual CNN. The new architecture is included because P04x is explicitly a support-cell question: it gates convolutional B-waveform residual channels by scalar support features before regression.",
        "",
        "For intervals, P04x uses split conformal residual calibration. For held-out run `h`, only rows from runs `!= h` estimate `q_alpha(c,m)`, the alpha quantile of `|r_i(m)|` in the most specific support cell with enough training support. The evaluated interval is the fractional band",
        "",
        "`[hat Q_i(m) (1 - q_alpha), hat Q_i(m) (1 + q_alpha)]`,",
        "",
        "clipped only by reporting denominators; coverage is tested by `|r_i(m)| <= q_alpha`. The hierarchy is full support cell, mid support cell, topology/amplitude cell, then global training-run fallback.",
        "",
        "## 3. Head-To-Head Benchmark",
        "",
        markdown_table(
            method_summary,
            [
                "method",
                "family",
                "n",
                "bias_median_frac",
                "res68_abs_frac",
                "res68_ci95",
                "full_rms_frac",
                "coverage68",
                "coverage68_ci95",
                "coverage90",
                "mean_width68_frac",
            ],
        ),
        "",
        f"Point-estimate winner among real methods: `{best['method']}` with res68 `{best['res68_abs_frac']:.4f}`. Best traditional method: `{best_trad['method']}` at `{best_trad['res68_abs_frac']:.4f}`. Best ML/NN method: `{best_ml['method']}` at `{best_ml['res68_abs_frac']:.4f}`. Winner recorded in `result.json`: `{result['winner']}`.",
        "",
        "The benchmark plot is `head_to_head_res68_ci.png`.",
        "",
        "## 4. Retained-Support Interval Frontier",
        "",
        "A support cell is accepted only if it has at least 150 rows, at least 5 runs, retained fraction >= 0.25, res68 <= 0.40, mean 68% interval width <= 0.90, coverage68 in [0.60, 0.76], coverage90 in [0.84, 0.96], and both real-minus-shuffled and real-minus-topology res68 <= -0.03. These thresholds were copied into the config before reading P04x results.",
        "",
        markdown_table(
            cells,
            [
                "method",
                "support_cell",
                "n",
                "n_runs",
                "retained_fraction",
                "res68_abs_frac",
                "coverage68",
                "coverage90",
                "mean_width68_frac",
                "shuffled_res68_abs_frac",
                "topology_only_res68_abs_frac",
                "real_minus_shuffled_res68",
                "real_minus_topology_res68",
                "accepted_support_cell",
            ],
            n=20,
        ),
        "",
        "Risk-ranked retained fractions by model:",
        "",
        markdown_table(frontier.sort_values(["method", "accepted_fraction"], ascending=[True, False]), ["method", "accepted_fraction", "n", "res68_abs_frac", "coverage68", "coverage90", "mean_width68_frac"], n=28),
        "",
        "## 5. Falsification",
        "",
        "Pre-registered metric: res68, full RMS, within-10/25%, coverage68/90, mean interval width, retained support fraction, real-minus-shuffled delta, and ML-minus-best-traditional deltas with run-block bootstrap 95% CIs. The decisive falsification test is whether a retained support cell beats both shuffled-target HGB and topology-only sentinels while maintaining calibrated interval coverage and nontrivial retained support.",
        "",
        f"Result: `{result['winner']}`. Accepted retained support cells: `{result['accepted_support_cells']}`. The best real point-estimate method minus shuffled-target res68 is `{result['falsification']['best_minus_shuffled_res68']:.4f}` and minus topology-only res68 is `{result['falsification']['best_minus_topology_res68']:.4f}`. Because the retained-cell acceptance gate considers {result['falsification']['tested_model_count']} real model families, the report treats isolated cell wins as descriptive unless they pass all preconfigured gates.",
        "",
        "## 6. Systematics And Caveats",
        "",
        "- The target is selected A-stack charge, not deposited energy, particle ID, or Geant4 truth.",
        "- P04x inherits the P04w fixed out-of-fold predictions; it does not re-tune model hyperparameters after looking at interval results.",
        "- Run-block bootstrap intervals cover the observed run family, not unobserved detector configurations.",
        "- Conformal residuals are exchangeability approximations inside support cells; drift within a support cell can produce nominal coverage with unusably broad intervals.",
        "- The topology-only sentinel is a strong control. If a waveform method ties it, the result is not an independent charge-transfer measurement even when shuffled-target separation looks favorable.",
        "- The largest support cells are dominated by B2-only topologies; retained fractions below 25% are not treated as operationally useful.",
        "",
        "## 7. Findings And Next Steps",
        "",
        result["finding"],
        "",
        "No follow-up ticket is appended. The conclusion is a negative operational gate: without new external truth or a changed detector acceptance definition, another charge-interval refinement would mostly retest the same topology-control limitation.",
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config {config['config_path_for_report']}",
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `joined_predictions.csv`, `method_interval_summary.csv`, `retained_support_cells.csv`, `retention_frontier.csv`, `leakage_checks.csv`, and `head_to_head_res68_ci.png`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04x_1781069576_790_606924bd_retained_support_charge_interval_calibration.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    config["config_path_for_report"] = str(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/7 reproducing raw ROOT gates ...", flush=True)
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack S00 gate reproduction failed: {got_b} != {expected_b}")
    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("2/7 extracting raw A/B rows ...", flush=True)
    frame, wave, ab_counts = p04c.extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)
    frame = p04w.add_frontier_strata(frame, wave, config)
    frame = support_columns(frame)

    print("3/7 reproducing P04c benchmark from raw rows ...", flush=True)
    p04c_summary, p04c_by_run, p04c_by_amp, _ = p04c.fit_leave_one_run(config, frame.copy(), wave)
    p04c_summary.to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    p04c_by_run.to_csv(out_dir / "p04c_reproduction_by_run.csv", index=False)
    p04c_by_amp.to_csv(out_dir / "p04c_reproduction_by_b2_amp.csv", index=False)

    print("4/7 joining fixed out-of-fold method panel ...", flush=True)
    preds = pd.read_csv(config["predecessor_prediction_csv"])
    pred_cols = ["run", "evt"] + [f"pred_{m}" for m in METHODS]
    risk_cols = [f"risk_{m}" for m in METHODS if f"risk_{m}" in preds.columns]
    joined = frame.merge(preds[pred_cols + risk_cols], on=["run", "evt"], how="inner", validate="one_to_one")
    if len(joined) != len(frame):
        raise RuntimeError(f"prediction join lost rows: raw={len(frame)} joined={len(joined)}")
    joined = calibrate_intervals(config, joined)
    joined.to_csv(out_dir / "joined_predictions.csv", index=False)

    print("5/7 summarizing intervals and retained cells ...", flush=True)
    method_summary = summarize_methods(config, joined)
    method_summary.to_csv(out_dir / "method_interval_summary.csv", index=False)
    cells = support_cell_summary(config, joined, method_summary)
    cells.to_csv(out_dir / "retained_support_cells.csv", index=False)
    frontier = retention_frontier(config, joined)
    frontier.to_csv(out_dir / "retention_frontier.csv", index=False)
    make_plot(out_dir, method_summary)

    eligible = method_summary[method_summary["family"].ne("negative_control")]
    best = eligible.sort_values("res68_abs_frac").iloc[0]
    shuf = method_summary[method_summary["method"].eq("shuffled_target_hgb")].iloc[0]
    topo = method_summary[method_summary["method"].eq("topology_only_sentinel")].iloc[0]
    accepted = cells[cells["accepted_support_cell"] == True]
    best_minus_shuffled = float(best["res68_abs_frac"] - shuf["res68_abs_frac"])
    best_minus_topology = float(best["res68_abs_frac"] - topo["res68_abs_frac"])
    winner = str(accepted.sort_values(["res68_abs_frac", "mean_width68_frac"]).iloc[0]["method"]) if len(accepted) else "none_no_retained_support_cell_passed"
    if len(accepted):
        cell = accepted.sort_values(["res68_abs_frac", "mean_width68_frac"]).iloc[0]
        finding = (
            f"{winner} passes the retained-support interval gate in support cell {cell['support_cell']} "
            f"(n={int(cell['n'])}, res68={cell['res68_abs_frac']:.4f}, coverage68={cell['coverage68']:.3f}, "
            f"mean width68={cell['mean_width68_frac']:.3f})."
        )
    else:
        finding = (
            f"No retained support cell passes the preconfigured interval gate. The point-estimate winner is {best['method']} "
            f"(res68 {best['res68_abs_frac']:.4f}), but the topology-only sentinel is {topo['res68_abs_frac']:.4f}; "
            f"best-minus-topology is {best_minus_topology:.4f}. Interval calibration can produce nominal coverage, "
            "but acceptable width, support fraction, and real-minus-sentinel separation do not coexist."
        )
    leakage = {
        "split": "leave-one-run-out by run",
        "features_exclude": ["run", "evt", "target_a_charge", "A1_charge", "A3_charge", "A1_selected", "A3_selected"],
        "prediction_join_rows": int(len(joined)),
        "train_heldout_run_overlap": 0,
        "topology_only_res68": float(topo["res68_abs_frac"]),
        "shuffled_target_res68": float(shuf["res68_abs_frac"]),
        "best_method": str(best["method"]),
        "best_res68": float(best["res68_abs_frac"]),
        "best_minus_shuffled_res68": best_minus_shuffled,
        "best_minus_topology_res68": best_minus_topology,
        "accepted_support_cells": int(len(accepted)),
        "winner": winner,
    }
    pd.DataFrame([leakage]).to_csv(out_dir / "leakage_checks.csv", index=False)

    print("6/7 writing result and report ...", flush=True)
    best_traditional = eligible[eligible["family"].eq("traditional")].sort_values("res68_abs_frac").iloc[0]
    best_ml = eligible[eligible["family"].isin(["ml", "nn", "new_architecture"])].sort_values("res68_abs_frac").iloc[0]
    result = {
        "study": "P04x",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "repro_tolerance": "exact B-stack selected-pulse count; exact A-stack selected gate counts; P04c reproduction rerun",
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "astack_gate_counts": json.loads(a_counts.to_json(orient="records")),
            "p04c_reproduction_summary": json.loads(p04c_summary.to_json(orient="records")),
        },
        "traditional": {
            "metric": "charge_interval_res68_abs_frac",
            "method": str(best_traditional["method"]),
            "value": float(best_traditional["res68_abs_frac"]),
            "coverage68": float(best_traditional["coverage68"]),
            "mean_width68_frac": float(best_traditional["mean_width68_frac"]),
        },
        "ml": {
            "metric": "charge_interval_res68_abs_frac",
            "method": str(best_ml["method"]),
            "value": float(best_ml["res68_abs_frac"]),
            "coverage68": float(best_ml["coverage68"]),
            "mean_width68_frac": float(best_ml["mean_width68_frac"]),
        },
        "winner": winner,
        "point_estimate_winner": str(best["method"]),
        "ml_beats_baseline": bool(float(best_ml["res68_abs_frac"]) < float(best_traditional["res68_abs_frac"])),
        "accepted_support_cells": int(len(accepted)),
        "falsification": {
            "preregistered_metric": "res68, full RMS, within-10/25%, coverage68/90, mean interval width, retained support fraction, real-minus-shuffled and ML-minus-best-traditional deltas with run-block bootstrap 95% CIs",
            "tested_model_count": int(len(eligible)),
            "shuffled_target_res68": float(shuf["res68_abs_frac"]),
            "topology_only_res68": float(topo["res68_abs_frac"]),
            "best_minus_shuffled_res68": best_minus_shuffled,
            "best_minus_topology_res68": best_minus_topology,
        },
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "head_to_head": json.loads(method_summary.to_json(orient="records")),
        "retained_support_cells_top": json.loads(cells.head(50).to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
        "critic": "pending",
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, p04c_summary, method_summary, cells, frontier, clean_json(result))

    print("7/7 writing provenance manifest ...", flush=True)
    input_runs = sorted(set(p04c.configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": "P04x",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/{Path(__file__).name} --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
            "predecessor_prediction_sha256": sha256_file(Path(config["predecessor_prediction_csv"])),
            "predecessor_method_summary_sha256": sha256_file(Path(config["predecessor_method_summary_csv"])),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
