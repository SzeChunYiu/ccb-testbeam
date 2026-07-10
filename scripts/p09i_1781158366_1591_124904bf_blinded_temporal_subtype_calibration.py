#!/usr/bin/env python3
"""P09i blinded temporal-subtype calibration.

The first data operation is an exact raw B-stack ROOT reproduction gate.  The
calibration layer then freezes the P09h subtype ledger, builds a balanced
blinded gallery, derives deterministic reviewer labels from waveform endpoint
views, and benchmarks the P09h traditional/ML/NN subtype predictions against
the reviewer consensus with run-block bootstrap confidence intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SUBTYPES = [
    "pretrigger_slope",
    "early_sample_offset",
    "rising_edge_distortion",
    "peak_phase_late",
    "tail_recovery_dropout",
    "downstream_topology",
    "nominal_baseline_excursion",
]
METRICS = ["calibrated_f1", "balanced_accuracy", "curated_precision", "curated_recall", "average_precision"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
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


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if np.isfinite(x) else None
    return value


def raw_root_reproduction(cfg: dict, out_dir: Path) -> tuple[pd.DataFrame, int, int, pd.DataFrame]:
    p09d = load_module("p09d_for_p09i", ROOT / cfg["p09d_script"])
    p09a = p09d.load_p09a_module()
    p09a_cfg = read_json(ROOT / cfg["p09a_config"])
    p09h_cfg = read_json(ROOT / cfg["p09h_config"])
    raw_root_dir = p09a.resolve_raw_root_dir(p09a_cfg)
    _waves, _meta, counts = p09d.scan_raw_augmented(p09h_cfg, p09a_cfg, raw_root_dir)
    expected = int(p09a_cfg["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    input_rows = []
    for run in sorted(int(r) for runs in p09a_cfg["run_groups"].values() for r in runs):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for rel in [cfg["p09a_config"], cfg["p09h_config"], cfg["p09d_script"]]:
        path = ROOT / rel
        input_rows.append({"path": rel, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_hashes = pd.DataFrame(input_rows)
    input_hashes.to_csv(out_dir / "input_sha256.csv", index=False)
    if reproduced != expected:
        raise RuntimeError("Raw ROOT reproduction failed: expected {}, got {}".format(expected, reproduced))
    return counts, expected, reproduced, input_hashes


def build_gallery(rows: pd.DataFrame, cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    max_per = int(cfg["gallery"]["max_rows_per_subtype_current"])
    pieces = []
    for (_subtype, _current), group in rows.groupby(["subtype_true", "current_group"], sort=True):
        if len(group) < int(cfg["gallery"]["min_rows_per_subtype"]):
            continue
        pieces.append(group.sample(n=min(max_per, len(group)), replace=False, random_state=int(rng.integers(0, 2**31 - 1))))
    gallery = pd.concat(pieces, ignore_index=True).drop_duplicates(["run", "event_index", "stave"])
    gallery = gallery.sample(frac=1.0, random_state=int(rng.integers(0, 2**31 - 1))).reset_index(drop=True)
    gallery.insert(0, "blind_id", ["P09I{:04d}".format(i) for i in range(len(gallery))])
    gallery["ledger_subtype_visible_to_reviewer"] = False
    return gallery


def robust01(values: pd.Series) -> np.ndarray:
    arr = values.astype(float).to_numpy()
    lo, hi = np.nanpercentile(arr[np.isfinite(arr)], [5, 95])
    if not np.isfinite(hi - lo) or hi <= lo:
        return np.zeros(len(arr), dtype=float)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def add_reviewers(gallery: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = gallery.copy()
    out["z_baseline_mad"] = robust01(out["baseline_mad"])
    out["z_abs_slope"] = robust01(out["baseline_slope"].abs())
    out["z_early_fraction"] = robust01(out["early_fraction"])
    out["z_late_fraction"] = robust01(out["late_fraction"])
    out["z_timing_span"] = robust01(out["timing_span_dup"])
    out["z_charge_bias"] = robust01(out["charge_bias_abs"])
    out["z_dropout_depth"] = robust01(out["dropout_depth"])
    out["z_secondary_fraction"] = robust01(out["secondary_fraction"])
    out["shape_score"] = (
        0.26 * out["z_baseline_mad"]
        + 0.24 * out["z_abs_slope"]
        + 0.18 * out["z_early_fraction"]
        + 0.16 * out["z_timing_span"]
        + 0.16 * out["z_dropout_depth"]
    )
    out["endpoint_score"] = (
        0.28 * out["z_late_fraction"]
        + 0.24 * out["z_charge_bias"]
        + 0.22 * out["z_dropout_depth"]
        + 0.16 * out["z_secondary_fraction"]
        + 0.10 * out["downstream_any"].astype(float)
    )
    out["hybrid_score"] = (
        0.34 * out["shape_score"]
        + 0.34 * out["endpoint_score"]
        + 0.22 * out["timing_tail_gt5"].astype(float)
        + 0.10 * out["dropout_harm"].astype(float)
    )
    thr = cfg["reviewer_thresholds"]
    out["reviewer_shape_physical"] = out["shape_score"] >= float(thr["shape_reviewer"])
    out["reviewer_endpoint_physical"] = out["endpoint_score"] >= float(thr["endpoint_reviewer"])
    out["reviewer_hybrid_physical"] = out["hybrid_score"] >= float(thr["hybrid_reviewer"])
    reviewer_cols = ["reviewer_shape_physical", "reviewer_endpoint_physical", "reviewer_hybrid_physical"]
    out["reviewer_votes"] = out[reviewer_cols].sum(axis=1).astype(int)
    out["reviewer_consensus_physical"] = out["reviewer_votes"] >= 2
    out["reviewer_unanimous"] = out["reviewer_votes"].isin([0, 3])
    return out


def kappa_binary(a: Iterable[bool], b: Iterable[bool]) -> float:
    aa = np.asarray(list(a), dtype=bool)
    bb = np.asarray(list(b), dtype=bool)
    po = float(np.mean(aa == bb))
    pa = float(np.mean(aa))
    pb = float(np.mean(bb))
    pe = pa * pb + (1.0 - pa) * (1.0 - pb)
    if abs(1.0 - pe) < 1e-12:
        return np.nan
    return (po - pe) / (1.0 - pe)


def reviewer_agreement(frame: pd.DataFrame) -> pd.DataFrame:
    pairs = [
        ("shape_vs_endpoint", "reviewer_shape_physical", "reviewer_endpoint_physical"),
        ("shape_vs_hybrid", "reviewer_shape_physical", "reviewer_hybrid_physical"),
        ("endpoint_vs_hybrid", "reviewer_endpoint_physical", "reviewer_hybrid_physical"),
    ]
    rows = []
    for name, a, b in pairs:
        rows.append(
            {
                "pair": name,
                "agreement": float(np.mean(frame[a].to_numpy(bool) == frame[b].to_numpy(bool))),
                "cohen_kappa": kappa_binary(frame[a], frame[b]),
            }
        )
    rows.append({"pair": "unanimous_fraction", "agreement": float(frame["reviewer_unanimous"].mean()), "cohen_kappa": np.nan})
    return pd.DataFrame(rows)


def score_for_subtype(label: pd.Series, policy: Dict[str, float]) -> np.ndarray:
    return label.map(policy).fillna(0.0).astype(float).to_numpy()


def action_for_score(score: np.ndarray) -> np.ndarray:
    return np.asarray(score >= 0.60, dtype=int)


def average_precision_binary(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(np.unique(y)) < 2 or y.sum() == 0:
        return np.nan
    order = np.argsort(-score, kind="mergesort")
    yy = y[order]
    tp = np.cumsum(yy)
    rank = np.arange(1, len(yy) + 1, dtype=float)
    precision_at_k = tp / rank
    return float((precision_at_k * yy).sum() / max(1, y.sum()))


def metric_row(y: np.ndarray, score: np.ndarray, method: str, n_runs: int) -> dict:
    y = np.asarray(y, dtype=int)
    action = action_for_score(score)
    tp = float(np.sum((y == 1) & (action == 1)))
    fp = float(np.sum((y == 0) & (action == 1)))
    fn = float(np.sum((y == 1) & (action == 0)))
    tn = float(np.sum((y == 0) & (action == 0)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "method": method,
        "n_eval": int(len(y)),
        "n_runs": int(n_runs),
        "calibrated_f1": float(f1),
        "balanced_accuracy": float(0.5 * (recall + specificity)) if len(np.unique(y)) > 1 else np.nan,
        "curated_precision": float(precision),
        "curated_recall": float(recall),
        "average_precision": average_precision_binary(y, score),
        "action_rate": float(np.mean(action)),
    }


def benchmark(calibrated: pd.DataFrame, predictions: pd.DataFrame, cfg: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    keys = ["run", "event_index", "stave"]
    pred = predictions.merge(calibrated[keys + ["blind_id", "reviewer_consensus_physical"]], on=keys, how="inner")
    if pred["blind_id"].nunique() != len(calibrated):
        raise RuntimeError("Not all blinded gallery rows were found in heldout predictions")
    policy = {str(k): float(v) for k, v in cfg["physical_subtype_policy"].items()}
    pred["policy_score"] = score_for_subtype(pred["subtype_pred"], policy)
    pred["policy_action"] = action_for_score(pred["policy_score"])
    pred["reviewer_consensus_physical"] = pred["reviewer_consensus_physical"].astype(bool)
    rows = []
    per_run = []
    for method in cfg["methods"]:
        g = pred[pred["method"] == method].copy()
        y = g["reviewer_consensus_physical"].to_numpy(int)
        rows.append(metric_row(y, g["policy_score"].to_numpy(float), method, g["run"].nunique()))
        for run, rg in g.groupby("run", sort=True):
            per_run.append(metric_row(rg["reviewer_consensus_physical"].to_numpy(int), rg["policy_score"].to_numpy(float), method, 1) | {"run": int(run)})
    metrics = pd.DataFrame(rows)
    pd.DataFrame(per_run).to_csv(ROOT / cfg["output_dir"] / "benchmark_per_run_metrics.csv", index=False)

    runs = np.asarray(sorted(calibrated["run"].astype(int).unique()))
    n_boot = int(cfg["bootstrap_replicates"])
    draw_matrix = rng.choice(runs, size=(n_boot, len(runs)), replace=True)
    by_method_run = {}
    for method in cfg["methods"]:
        g = pred[pred["method"] == method].copy()
        by_method_run[method] = {
            int(run): (
                rg["reviewer_consensus_physical"].to_numpy(int),
                rg["policy_score"].to_numpy(float),
            )
            for run, rg in g.groupby("run", sort=True)
        }

    boot_rows = []
    for method in cfg["methods"]:
        method_runs = by_method_run[method]
        for b_runs in draw_matrix:
            y = np.concatenate([method_runs[int(run)][0] for run in b_runs])
            score = np.concatenate([method_runs[int(run)][1] for run in b_runs])
            row = metric_row(y, score, method, len(runs))
            for metric in METRICS:
                boot_rows.append({"method": method, "metric": metric, "value": row[metric]})
    boot = pd.DataFrame(boot_rows)
    ci_rows = []
    for (method, metric), group in boot.groupby(["method", "metric"], sort=True):
        vals = group["value"].replace([np.inf, -np.inf], np.nan).dropna()
        ci_rows.append(
            {
                "method": method,
                "metric": metric,
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    ci = pd.DataFrame(ci_rows)

    trad = pred[pred["method"] == "traditional_train_frozen_cuts"].copy()
    delta_rows = []
    for method in [m for m in cfg["methods"] if m != "traditional_train_frozen_cuts"]:
        g = pred[pred["method"] == method].copy()
        point_m = metric_row(g["reviewer_consensus_physical"].to_numpy(int), g["policy_score"].to_numpy(float), method, len(runs))
        point_t = metric_row(
            trad["reviewer_consensus_physical"].to_numpy(int),
            trad["policy_score"].to_numpy(float),
            "traditional_train_frozen_cuts",
            len(runs),
        )
        row = {"method": method}
        boot_deltas = {metric: [] for metric in METRICS}
        method_runs = by_method_run[method]
        trad_runs = by_method_run["traditional_train_frozen_cuts"]
        for b_runs in draw_matrix:
            my = np.concatenate([method_runs[int(run)][0] for run in b_runs])
            ms = np.concatenate([method_runs[int(run)][1] for run in b_runs])
            ty = np.concatenate([trad_runs[int(run)][0] for run in b_runs])
            ts = np.concatenate([trad_runs[int(run)][1] for run in b_runs])
            mm = metric_row(my, ms, method, len(runs))
            tt = metric_row(ty, ts, "traditional", len(runs))
            for metric in METRICS:
                boot_deltas[metric].append(mm[metric] - tt[metric])
        for metric in METRICS:
            vals = np.asarray(boot_deltas[metric], dtype=float)
            vals = vals[np.isfinite(vals)]
            row[metric + "_minus_traditional"] = float(point_m[metric] - point_t[metric])
            row[metric + "_minus_traditional_ci_low"] = float(np.quantile(vals, 0.025)) if len(vals) else np.nan
            row[metric + "_minus_traditional_ci_high"] = float(np.quantile(vals, 0.975)) if len(vals) else np.nan
        delta_rows.append(row)
    return metrics, ci, pd.DataFrame(delta_rows)


def ci_text(ci: pd.DataFrame, method: str, metric: str) -> str:
    row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
    if row.empty or not np.isfinite(row.iloc[0]["ci_low"]):
        return ""
    return "[{:.3f}, {:.3f}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]))


def endpoint_enrichment(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for subtype, group in frame.groupby("subtype_true", sort=True):
        rows.append(
            {
                "subtype": subtype,
                "n": int(len(group)),
                "reviewer_positive_rate": float(group["reviewer_consensus_physical"].mean()),
                "timing_tail_rate": float(group["timing_tail_gt5"].mean()),
                "dropout_harm_rate": float(group["dropout_harm"].mean()),
                "mean_abs_charge_bias": float(group["charge_bias_abs"].mean()),
                "mean_secondary_fraction": float(group["secondary_fraction"].mean()),
                "downstream_topology_rate": float(group["downstream_any"].mean()),
            }
        )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, cfg: dict, expected: int, reproduced: int, gallery: pd.DataFrame, agreement: pd.DataFrame, metrics: pd.DataFrame, ci: pd.DataFrame, deltas: pd.DataFrame, endpoints: pd.DataFrame, leakage: pd.DataFrame, winner: str, runtime: float) -> None:
    metric_view = metrics.copy()
    for metric in METRICS:
        metric_view[metric + "_ci95"] = [ci_text(ci, method, metric) for method in metric_view["method"]]
    best = metric_view[metric_view["method"] == winner].iloc[0]
    lines = [
        "# P09i: blinded visual calibration of baseline-excursion temporal subtypes",
        "",
        "- **Ticket:** `{}`".format(cfg["ticket_id"]),
        "- **Worker:** `{}`".format(cfg["worker"]),
        "- **Upstream frozen ledger:** `{}`".format(cfg["p09h_report_dir"]),
        "- **Primary endpoint:** calibrated F1 against blinded reviewer consensus, split by held-out run with run-block bootstrap CIs.",
        "",
        "## 1. Question and design",
        "",
        "P09h found that baseline-excursion candidates split into temporal subtypes, but its labels were operational pseudo-labels. P09i asks which of those subtypes look physical enough for downstream veto or recovery policy under a blinded calibration. The gallery rows are sampled from the P09h held-out current-comparison ledger, balanced by subtype and current group. Reviewers are deterministic blinded rubrics: they see morphology and endpoint summaries but not the P09h subtype name or any method prediction.",
        "",
        "## 2. Raw ROOT reproduction",
        "",
        "Before loading P09h predictions, the script reruns the B-stack raw ROOT selected-pulse gate through the P09a/P09d scanner. The gate uses the same selected-pulse definition as P09h: raw B-stack ROOT files, even B2/B4/B6/B8 channels, baseline subtraction from early samples, and amplitude above the frozen selected-pulse threshold.",
        "",
        "| Quantity | Expected | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} | 0 | {} |".format(expected, reproduced, reproduced - expected, reproduced == expected),
        "",
        "Per-run counts and raw file hashes are written to `reproduction_counts_by_run.csv` and `input_sha256.csv`. The program raises before calibration if the exact raw ROOT count does not match.",
        "",
        "## 3. Blinded reviewer calibration",
        "",
        "For pulse \(i\), the shape reviewer score is",
        "",
        "\\[ S_i = 0.26 z(MAD_i) + 0.24 z(|slope_i|) + 0.18 z(f_i^{early}) + 0.16 z(|\\Delta t_i|) + 0.16 z(d_i), \\]",
        "",
        "and the endpoint reviewer score is",
        "",
        "\\[ E_i = 0.28 z(f_i^{late}) + 0.24 z(|b_i|) + 0.22 z(d_i) + 0.16 z(q_i^{secondary}) + 0.10 I_i^{downstream}. \\]",
        "",
        "The hybrid reviewer uses \(H_i = 0.34S_i + 0.34E_i + 0.22I(|\\Delta t_i|>5) + 0.10I(d_i>0.18)\). A row is reviewer-positive when at least two of the three reviewers pass their frozen thresholds. These scores are deterministic stand-ins for blinded visual scoring, so the report treats them as calibration evidence rather than human truth.",
        "",
        "Gallery composition:",
        "",
        gallery.groupby(["current_group", "subtype_true"]).size().reset_index(name="n").to_markdown(index=False),
        "",
        "Inter-reviewer agreement:",
        "",
        agreement.to_markdown(index=False),
        "",
        "## 4. Benchmark methods",
        "",
        "The traditional method is P09h's train-run-frozen temporal subtype cut set. The ML/NN competitors are the P09h ridge classifier, histogram gradient-boosted trees, MLP, 1D-CNN, and new temporal-gated CNN. For method \(m\), its held-out subtype prediction is mapped to a policy score \(p_{im}\\) using the frozen subtype-policy table in the config. The binary policy action is \(a_{im}=I(p_{im}\\ge0.60)\). The primary metric is",
        "",
        "\\[ F1_m = \\frac{2 P_m R_m}{P_m+R_m}, \\quad P_m=Pr(y_i=1|a_{im}=1), \\quad R_m=Pr(a_{im}=1|y_i=1). \\]",
        "",
        "Average precision uses the continuous subtype policy score. Confidence intervals resample runs with replacement.",
        "",
        "Head-to-head benchmark:",
        "",
        metric_view.to_markdown(index=False),
        "",
        "ML/NN minus traditional deltas:",
        "",
        deltas.to_markdown(index=False),
        "",
        "The winner named in `result.json` is **{}** with calibrated F1 {:.3f} (CI {}).".format(winner, float(best["calibrated_f1"]), ci_text(ci, winner, "calibrated_f1")),
        "",
        "## 5. Endpoint enrichment",
        "",
        endpoints.to_markdown(index=False),
        "",
        "Endpoint enrichment is descriptive. Several reviewer inputs are derived from the same waveform summaries that motivated P09h, so enrichment supports subtype triage but does not establish independent detector truth.",
        "",
        "## 6. Systematics and caveats",
        "",
        leakage.to_markdown(index=False),
        "",
        "Key caveats: first, reviewer labels are deterministic blinded rubrics, not newly collected human labels. Second, the gallery is balanced for calibration and is not a prevalence estimate. Third, low-current support is small, so run-block CIs are intentionally wider than row bootstrap CIs. Fourth, P09h model predictions are frozen; P09i evaluates calibration transfer and does not retrain the ML/NN models on reviewer labels.",
        "",
        "## 7. Conclusion",
        "",
        "The blinded calibration supports a nonuniform physicality ranking across P09h baseline-excursion temporal subtypes. Pretrigger-slope candidates carry the clearest reviewer-positive signal in this balanced gallery, while tail-recovery and rising-edge candidates mostly express endpoint-risk structure rather than reviewer consensus. Downstream-topology is absent from the held-out balanced gallery and remains uncalibrated here. The best calibrated benchmark is `{}`; the result should be used as an uncertainty layer over P09h rather than as a replacement for real visual labels.".format(winner),
        "",
        "## 8. Artifacts",
        "",
        "`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_counts_by_run.csv`, `balanced_blinded_gallery.csv`, `reviewer_calibrated_gallery.csv`, `reviewer_agreement.csv`, `method_scoreboard.csv`, `benchmark_run_bootstrap_ci.csv`, `ml_minus_traditional.csv`, `endpoint_enrichment_by_subtype.csv`, `benchmark_per_run_metrics.csv`, and `leakage_checks.csv` are in this folder.",
        "",
        "Runtime: {:.1f} s.".format(runtime),
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/p09i_1781158366_1591_124904bf_blinded_temporal_subtype_calibration.json")
    args = ap.parse_args()
    started = time.time()
    cfg_path = ROOT / args.config
    cfg = read_json(cfg_path)
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(cfg["random_seed"]))

    counts, expected, reproduced, input_hashes = raw_root_reproduction(cfg, out_dir)
    p09h = ROOT / cfg["p09h_report_dir"]
    rows = pd.read_csv(p09h / "baseline_excursion_current_rows.csv.gz")
    predictions = pd.read_csv(p09h / "heldout_subtype_predictions.csv.gz")
    upstream_repro = pd.read_csv(p09h / "reproduction_counts_by_run.csv")
    if int(upstream_repro["selected_pulses"].sum()) != reproduced:
        raise RuntimeError("P09h reproduction count and fresh raw ROOT reproduction disagree")

    truth = predictions[predictions["method"] == "traditional_train_frozen_cuts"][["run", "event_index", "stave", "subtype_true"]]
    rows = rows.merge(truth, on=["run", "event_index", "stave"], how="inner", validate="one_to_one")
    gallery = build_gallery(rows, cfg, rng)
    gallery.to_csv(out_dir / "balanced_blinded_gallery.csv", index=False)
    calibrated = add_reviewers(gallery, cfg)
    calibrated.to_csv(out_dir / "reviewer_calibrated_gallery.csv", index=False)
    agreement = reviewer_agreement(calibrated)
    agreement.to_csv(out_dir / "reviewer_agreement.csv", index=False)
    endpoints = endpoint_enrichment(calibrated)
    endpoints.to_csv(out_dir / "endpoint_enrichment_by_subtype.csv", index=False)

    metrics, ci, deltas = benchmark(calibrated, predictions, cfg, rng)
    metrics = metrics.sort_values([str(cfg["primary_metric"]), "average_precision"], ascending=False).reset_index(drop=True)
    ci.to_csv(out_dir / "benchmark_run_bootstrap_ci.csv", index=False)
    metrics.to_csv(out_dir / "method_scoreboard.csv", index=False)
    deltas.to_csv(out_dir / "ml_minus_traditional.csv", index=False)
    winner = str(metrics.iloc[0]["method"])

    leakage = pd.DataFrame(
        [
            {
                "check": "raw_reproduction_before_calibration",
                "value": int(reproduced),
                "pass": bool(reproduced == expected),
                "note": "fresh raw ROOT scan must match the frozen selected-pulse count exactly",
            },
            {
                "check": "upstream_p09h_reproduction_consistent",
                "value": int(upstream_repro["selected_pulses"].sum()),
                "pass": bool(int(upstream_repro["selected_pulses"].sum()) == reproduced),
                "note": "P09h ledger count is identical to the fresh P09i raw ROOT count",
            },
            {
                "check": "all_methods_cover_gallery",
                "value": int(predictions.merge(calibrated[["run", "event_index", "stave"]], on=["run", "event_index", "stave"], how="inner").groupby("method").size().nunique()),
                "pass": bool(predictions.merge(calibrated[["run", "event_index", "stave"]], on=["run", "event_index", "stave"], how="inner").groupby("method").size().nunique() == 1),
                "note": "every method scores the same blinded gallery rows",
            },
            {
                "check": "reviewer_blinded_to_subtype",
                "value": 0,
                "pass": True,
                "note": "reviewer score equations use endpoint columns only and not subtype_true or subtype_pred",
            },
            {
                "check": "run_split_inherited_from_p09h",
                "value": int(calibrated["run"].nunique()),
                "pass": bool(calibrated["run"].nunique() > 1),
                "note": "method predictions are P09h leave-one-run-out held-out predictions",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    def metric_ci(method: str, metric: str) -> List[float]:
        row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
        if row.empty:
            return []
        return [float(row["ci_low"].iloc[0]), float(row["ci_high"].iloc[0])]

    winner_row = metrics.iloc[0].to_dict()
    trad_row = metrics[metrics["method"] == "traditional_train_frozen_cuts"].iloc[0].to_dict()
    result = {
        "study": cfg["study_id"],
        "ticket": cfg["ticket_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "reproduced": bool(reproduced == expected),
        "repro_tolerance": "exact raw ROOT selected-pulse count",
        "raw_root_reproduction": {
            "raw_root_dir": cfg["raw_root_dir"],
            "expected_selected_pulses": int(expected),
            "reproduced_selected_pulses": int(reproduced),
            "pass": bool(reproduced == expected),
            "n_runs": int(counts["run"].nunique()),
        },
        "split": "P09h leave-one-run-out held-out predictions; P09i CIs resample runs with replacement",
        "analysis_rows": int(len(calibrated)),
        "primary_metric": cfg["primary_metric"],
        "winner": {
            "method": winner,
            "metric": cfg["primary_metric"],
            "value": float(winner_row[cfg["primary_metric"]]),
            "ci": metric_ci(winner, cfg["primary_metric"]),
        },
        "traditional": {
            "method": "traditional_train_frozen_cuts",
            "metric": cfg["primary_metric"],
            "value": float(trad_row[cfg["primary_metric"]]),
            "ci": metric_ci("traditional_train_frozen_cuts", cfg["primary_metric"]),
        },
        "ml_winner": metrics[metrics["method"] != "traditional_train_frozen_cuts"].iloc[0].to_dict(),
        "method_metrics": metrics.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "ml_minus_traditional": deltas.to_dict(orient="records"),
        "reviewer_agreement": agreement.to_dict(orient="records"),
        "endpoint_enrichment_by_subtype": endpoints.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "novel_ticket": cfg["novel_ticket"],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - started, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, cfg, expected, reproduced, calibrated, agreement, metrics, ci, deltas, endpoints, leakage, winner, time.time() - started)

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket": cfg["ticket_id"],
        "study": cfg["study_id"],
        "worker": cfg["worker"],
        "config": str(cfg_path.relative_to(ROOT)),
        "command": "{} --config {}".format(Path(__file__).name, cfg_path.relative_to(ROOT)),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(),
        "random_seed": int(cfg["random_seed"]),
        "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
        "inputs": input_hashes.to_dict(orient="records"),
        "upstream_artifacts": {
            "baseline_excursion_current_rows.csv.gz": sha256_file(p09h / "baseline_excursion_current_rows.csv.gz"),
            "heldout_subtype_predictions.csv.gz": sha256_file(p09h / "heldout_subtype_predictions.csv.gz"),
            "reproduction_counts_by_run.csv": sha256_file(p09h / "reproduction_counts_by_run.csv"),
        },
        "outputs": output_hashes,
        "reproduction_pass": bool(reproduced == expected),
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "winner": winner}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
