#!/usr/bin/env python3
"""P13c rare-atom external steering dry run.

Freeze the P13b rare-atom promotion gates and test them as actual steering
variables for one downstream consumer at a time: timing, pile-up, charge, and
PID.  The script reproduces the S00 selected-pulse count from raw ROOT, reuses
the P13b atom ledger construction, benchmarks the frozen traditional scorecard
against ridge, HGB, MLP, 1D-CNN, and support-gated CNN models with leave-one-run
splits, and adds shuffled-atom controls.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p13c-1781164722")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
P13B_PATH = ROOT / "scripts/p13b_1781055420_689_3cc21a6b_rare_atom_bootstrap_promotion_threshold.py"


def import_p13b():
    spec = importlib.util.spec_from_file_location("p13b_bootstrap_promotion_threshold", P13B_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["p13b_bootstrap_promotion_threshold"] = module
    spec.loader.exec_module(module)
    return module


P13B = import_p13b()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def ci95(values: Iterable[float]) -> Tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def md_table(frame: pd.DataFrame, columns: Sequence[str], formats: Dict[str, str] | None = None) -> str:
    formats = formats or {}
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in columns:
            val = row[col]
            vals.append(formats[col].format(val) if col in formats and pd.notna(val) else str(val))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join(rows)


def frozen_gate_cells(cells: pd.DataFrame, support: pd.DataFrame) -> pd.DataFrame:
    gate = support[["atom", "stave", "traditional_pass", "traditional_decision"]].copy()
    out = cells.merge(gate, on=["atom", "stave"], how="left")
    out["traditional_pass"] = out["traditional_pass"].fillna(False).astype(bool)
    out["traditional_decision"] = out["traditional_decision"].fillna("defer")
    return out


def add_consumer_label(cells: pd.DataFrame, consumer: str, cfg: dict) -> pd.DataFrame:
    out = cells.copy()
    limit = cfg["consumer_limits"][consumer]
    metric = str(limit["metric"])
    max_value = float(limit["max"])
    out["consumer"] = consumer
    out["consumer_metric"] = metric
    out["consumer_metric_value"] = out[metric].to_numpy(dtype=float)
    out["consumer_pass"] = out["consumer_metric_value"] <= max_value
    out["promotion_label"] = (
        (out["traditional_pass"])
        & (out["is_rare_atom"].to_numpy(dtype=int) == 1)
        & (out["n"].to_numpy(dtype=float) >= 20.0)
        & (out["consumer_pass"])
    ).astype(int)
    return out


def shuffled_atom_controls(cells: pd.DataFrame, support: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(cfg["random_seed"]) + 7701)
    key = support[["atom", "stave", "traditional_pass"]].copy()
    rows = []
    for (run, stave), sub in cells.groupby(["run", "stave"], sort=False):
        atoms = sub["atom"].to_numpy(dtype=object).copy()
        if len(atoms) > 1:
            rng.shuffle(atoms)
        tmp = sub[["atom", "run", "stave", "n", "timing_tail_rate", "pileup_excess_proxy", "charge_res68_proxy", "qshape_abs_mean"]].copy()
        tmp["shuffled_atom"] = atoms
        tmp = tmp.merge(key.rename(columns={"atom": "shuffled_atom", "traditional_pass": "shuffled_gate_pass"}), on=["shuffled_atom", "stave"], how="left")
        tmp["shuffled_gate_pass"] = tmp["shuffled_gate_pass"].fillna(False).astype(bool)
        rows.append(tmp)
    shuffled = pd.concat(rows, ignore_index=True)
    for consumer, limit in cfg["consumer_limits"].items():
        metric = str(limit["metric"])
        max_value = float(limit["max"])
        shuffled[consumer + "_shuffled_label"] = (
            (shuffled["shuffled_gate_pass"])
            & (shuffled["shuffled_atom"] != "nominal_control")
            & (shuffled["n"].to_numpy(dtype=float) >= 20.0)
            & (shuffled[metric].to_numpy(dtype=float) <= max_value)
        ).astype(int)
    return shuffled


def summarize_shuffled(pred: pd.DataFrame, summary: pd.DataFrame, shuffled: pd.DataFrame, consumer: str, cfg: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(cfg["random_seed"]) + 8300 + sum(ord(c) for c in consumer))
    runs = np.asarray(sorted(pred["run"].unique()), dtype=int)
    variant_by_method = summary.set_index("method")["method_variant"].to_dict()
    merged = pred[["atom", "run", "stave"]].copy()
    merged["row_number"] = np.arange(len(merged))
    ctrl = shuffled.copy()
    ctrl["row_number"] = np.arange(len(ctrl))
    rows = []
    for method, variant in variant_by_method.items():
        col = "pred_" + str(variant)
        frame = pd.DataFrame(
            {
                "run": pred["run"].to_numpy(dtype=int),
                "pred": pred[col].to_numpy(dtype=bool),
                "shuffled_label": ctrl[consumer + "_shuffled_label"].to_numpy(dtype=int),
                "atom_changed": ctrl["shuffled_atom"].to_numpy(dtype=object) != ctrl["atom"].to_numpy(dtype=object),
            }
        )
        eligible = frame["atom_changed"] & (frame["shuffled_label"] == 0)
        point = float(frame.loc[eligible, "pred"].mean()) if eligible.any() else 0.0
        boot = []
        by_run = {int(r): g for r, g in frame.groupby("run")}
        for _ in range(int(cfg["ml"]["bootstrap_samples"])):
            sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            mask = sample["atom_changed"] & (sample["shuffled_label"] == 0)
            boot.append(float(sample.loc[mask, "pred"].mean()) if mask.any() else 0.0)
        lo, hi = ci95(boot)
        rows.append(
            {
                "consumer": consumer,
                "method": method,
                "method_variant": variant,
                "shuffled_false_steer_rate": point,
                "shuffled_false_steer_rate_ci_low": lo,
                "shuffled_false_steer_rate_ci_high": hi,
                "n_shuffled_negative": int(eligible.sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("shuffled_false_steer_rate")


def copy_core_artifacts(src: Path, dst: Path) -> None:
    for name in [
        "input_sha256.csv",
        "reproduction_counts_by_run.csv",
        "reproduction_match_table.csv",
        "atom_run_cells.csv",
        "atom_support_ledger.csv",
        "endpoint_systematics_by_atom.csv",
        "atom_mean_waveforms.npy",
        "pulse_atom_assignments_sample.csv",
    ]:
        path = src / name
        if path.exists():
            shutil.copy2(path, dst / name)


def write_report(
    out_dir: Path,
    cfg_path: Path,
    cfg: dict,
    reproduction: pd.DataFrame,
    support: pd.DataFrame,
    consumer_summary: pd.DataFrame,
    all_methods: pd.DataFrame,
    shuffled_summary: pd.DataFrame,
    endpoint_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    show_support = support[support["atom"] != "nominal_control"].sort_values(["traditional_pass", "n_total"], ascending=[False, False]).head(14).copy()
    show_support["harm_ci"] = show_support.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["harm_ci_low"], r["harm_ci_high"]), axis=1)
    method_show = all_methods.sort_values(["consumer", "promotion_utility"], ascending=[True, False]).groupby("consumer").head(6).copy()
    method_show["utility_ci"] = method_show.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["promotion_utility_ci_low"], r["promotion_utility_ci_high"]), axis=1)
    shuffled_show = shuffled_summary.copy()
    shuffled_show["shuffled_ci"] = shuffled_show.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["shuffled_false_steer_rate_ci_low"], r["shuffled_false_steer_rate_ci_high"]), axis=1)
    endpoint_show = endpoint_summary.head(12).copy()

    lines = [
        "# P13c rare-atom external steering dry run",
        "",
        "- **Study ID:** P13c",
        "- **Ticket:** `{}`".format(cfg["ticket"]),
        "- **Author:** {}".format(cfg["worker"]),
        "- **Date:** 2026-07-10",
        "- **Depends on:** P13b frozen rare-atom promotion gates",
        "- **Config:** `{}`".format(cfg_path),
        "- **Git commit:** `{}`".format(git_commit()),
        "",
        "## Abstract",
        "",
        "This dry run asks whether the P13b rare-atom promotion gates remain conservative when a promoted atom is used as an external steering variable for exactly one downstream consumer at a time.  The raw B-stack selected-pulse number is reproduced from ROOT before modeling.  The frozen P13b support, stability, harm, CI-width, and sample-balance gates are not retuned.  The overall winner named in `result.json` is **{}** for the **{}** consumer with utility {:.3f} [{:.3f}, {:.3f}] and shuffled-atom false-steering rate {:.3f}.".format(
            winner["method"],
            winner["consumer"],
            winner["promotion_utility"],
            winner["promotion_utility_ci"][0],
            winner["promotion_utility_ci"][1],
            winner["shuffled_false_steer_rate"],
        ),
        "",
        "## 1. Raw ROOT Reproduction",
        "",
        md_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "The reproduced count scans `HRDv` in `data/root/root/hrdb_run_*.root`, subtracts the median of samples 0--3 per channel, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.  This matches the P13b/S00 selected-pulse anchor and prevents downstream steering results from being detached from the raw data.",
        "",
        "## 2. Frozen Traditional Gate",
        "",
        "For atom `a`, stave `s`, and run `r`, the support ledger uses `n_{a,s,r}` and the effective run count",
        "",
        "`N_eff(a,s) = (sum_r n_{a,s,r})^2 / sum_r n_{a,s,r}^2`.",
        "",
        "The P13b gate is frozen: total support >= {min_total_support}, `N_eff >= {min_effective_runs}`, runs present >= {min_runs_present}, max run fraction <= {max_run_fraction}, exact-binomial support CI width <= {max_support_ci_width}, harm rate <= {max_harm_rate}, harm CI high <= {max_harm_ci_high}, and Sample-I/Sample-II support imbalance <= {max_sample_balance_absdiff}.  P13c only intersects that frozen gate with one consumer endpoint at a time.".format(
            **cfg["promotion_criteria"]
        ),
        "",
        md_table(
            show_support,
            ["atom", "stave", "n_total", "runs_present", "effective_runs", "max_run_fraction", "support_ci_width", "harm_rate", "harm_ci", "traditional_decision"],
            {"effective_runs": "{:.2f}", "max_run_fraction": "{:.3f}", "support_ci_width": "{:.4f}", "harm_rate": "{:.3f}"},
        ),
        "",
        "## 3. Consumer Targets",
        "",
        "A held-out atom/run/stave cell is labelled steering-safe for consumer `c` only if it is rare, passes the frozen P13b gate, has at least 20 selected pulses in the held-out run cell, and satisfies the consumer endpoint limit.  Timing uses `timing_tail_rate <= 0.25`; pile-up uses `pileup_excess_proxy <= 1.30`; charge uses `charge_res68_proxy <= 0.38`; PID uses `qshape_abs_mean <= 0.30`.  These limits are declared in the config before training and are not fitted per method.",
        "",
        md_table(
            consumer_summary,
            ["consumer", "winner_method", "winner_variant", "positive_cells", "best_utility", "utility_ci", "false_control", "shuffled_false_steer_rate"],
            {"best_utility": "{:.3f}", "false_control": "{:.3f}", "shuffled_false_steer_rate": "{:.3f}"},
        ),
        "",
        "## 4. Benchmarked Methods",
        "",
        "Each consumer benchmark uses leave-one-run-out folds.  The tested families are the frozen traditional support scorecard, ridge logistic regression, histogram gradient-boosted trees, one-hidden-layer MLP, a 1D convolutional network over the mean normalized atom waveform, and a new support-gated CNN whose convolutional waveform embedding is multiplicatively gated by the scalar support vector.  Scalar features exclude run identifiers, event identifiers, and labels.",
        "",
        "The primary utility is",
        "",
        "`U = AP + 0.25 recall - 2 false_control - 0.25 ECE - 1 shuffled_false_steer`.",
        "",
        "The shuffled term is evaluated by permuting atom identities within run/stave blocks and measuring how often a method would steer when the shuffled atom no longer satisfies the frozen gate and endpoint label.  Confidence intervals are run-block bootstrap intervals.",
        "",
        md_table(
            method_show,
            ["consumer", "method", "method_variant", "average_precision", "promotion_utility", "utility_ci", "false_promotion_control_rate", "shuffled_false_steer_rate"],
            {"average_precision": "{:.3f}", "promotion_utility": "{:.3f}", "false_promotion_control_rate": "{:.3f}", "shuffled_false_steer_rate": "{:.3f}"},
        ),
        "",
        "## 5. Shuffled-Atom Controls",
        "",
        md_table(
            shuffled_show.sort_values(["consumer", "shuffled_false_steer_rate"]).groupby("consumer").head(6),
            ["consumer", "method", "method_variant", "shuffled_false_steer_rate", "shuffled_ci", "n_shuffled_negative"],
            {"shuffled_false_steer_rate": "{:.3f}"},
        ),
        "",
        "## 6. Endpoint Systematics",
        "",
        "Endpoint summaries are weighted over atom/run/stave cells and uncertainty is estimated by resampling complete runs.  The proxies are deliberately conservative: timing uses wide inter-stave timing spans, pile-up uses delayed secondary and late-area excess, charge uses within-cell log-amplitude spread, and PID uses q-template residual magnitude.",
        "",
        md_table(
            endpoint_show,
            ["consumer", "n_cells", "n_positive", "metric", "promoted_metric_mean", "promoted_metric_ci_low", "promoted_metric_ci_high", "control_metric_mean"],
            {"promoted_metric_mean": "{:.3f}", "promoted_metric_ci_low": "{:.3f}", "promoted_metric_ci_high": "{:.3f}", "control_metric_mean": "{:.3f}"},
        ),
        "",
        "## 7. Leakage And Caveats",
        "",
        md_table(leakage, ["consumer", "check", "value", "pass"]),
        "",
        "- The dry run is a consumer-level false-promotion bound, not a claim that any atom is a physical causal variable.",
        "- The strongest protection is the frozen P13b gate; ML methods are rejected if they buy utility by increasing nominal-control or shuffled-atom false steering.",
        "- Only one atom source is externally steered at a time.  Correlated multi-consumer steering remains outside this ticket.",
        "- The positive label is sparse because the frozen gate is intentionally conservative; AP and utility are therefore more informative than accuracy.",
        "",
        "## 8. Result",
        "",
        "The named winner is **{}** (`{}`) on **{}**.  The result does not append a new ticket; P13c is a closure dry run of the P13b promotion policy.".format(winner["method"], winner["method_variant"], winner["consumer"]),
        "",
        "## 9. Reproducibility",
        "",
        "Run command:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p13c_1781164722_1110_69a0219b_rare_atom_external_steering.py --config {}".format(cfg_path),
        "```",
        "",
        "Artifacts include `result.json`, `REPORT.md`, `manifest.json`, `consumer_method_summary.csv`, `consumer_winners.csv`, `shuffled_atom_controls.csv`, `endpoint_systematics_by_consumer.csv`, `leakage_checks.csv`, raw reproduction tables, and per-consumer benchmark subdirectories.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    cfg_path = args.config
    cfg = load_config(cfg_path)
    out_dir = ROOT / Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    np.random.seed(int(cfg["random_seed"]))
    if P13B.torch is not None:
        P13B.torch.manual_seed(int(cfg["random_seed"]))
        P13B.torch.set_num_threads(1)

    with tempfile.TemporaryDirectory(prefix="p13c_core_build_") as tmp_build:
        build_dir = Path(tmp_build)
        pulses, waves, counts_by_run, input_hashes = P13B.load_selected_pulses(cfg, build_dir)
        reproduced = int(counts_by_run["selected_pulses"].sum())
        expected = int(cfg["expected_counts"]["total_selected_pulses"])
        reproduction = pd.DataFrame(
            [{"quantity": "S00 selected B-stave pulse records", "report_value": expected, "reproduced": reproduced, "delta": reproduced - expected, "tolerance": 0, "pass": reproduced == expected}]
        )
        reproduction.to_csv(build_dir / "reproduction_match_table.csv", index=False)
        if reproduced != expected:
            raise RuntimeError("raw ROOT reproduction failed: {} != {}".format(reproduced, expected))

        pulses = P13B.add_shape_and_timing_columns(pulses, waves, cfg)
        cells, support = P13B.build_atom_cells(pulses, waves, cfg, build_dir)
        cells = frozen_gate_cells(cells, support)
        endpoints = P13B.endpoint_systematics(cells, cfg, build_dir)
        mean_wave = np.load(build_dir / "atom_mean_waveforms.npy")
        copy_core_artifacts(build_dir, out_dir)
    shuffled = shuffled_atom_controls(cells, support, cfg)
    shuffled.to_csv(out_dir / "shuffled_atom_controls.csv", index=False)

    method_frames: List[pd.DataFrame] = []
    winner_rows: List[dict] = []
    shuffled_frames: List[pd.DataFrame] = []
    leakage_frames: List[pd.DataFrame] = []
    endpoint_rows: List[dict] = []
    for consumer in cfg["consumer_limits"]:
        consumer_dir = out_dir / ("consumer_" + consumer)
        consumer_dir.mkdir(parents=True, exist_ok=True)
        consumer_cells = add_consumer_label(cells, consumer, cfg)
        consumer_cells.to_csv(consumer_dir / "consumer_atom_run_cells.csv", index=False)
        fold_metrics, predictions, summary = P13B.run_benchmark(consumer_cells, mean_wave, cfg, consumer_dir)
        shuffle_summary = summarize_shuffled(predictions, summary, shuffled, consumer, cfg)
        shuffle_summary.to_csv(consumer_dir / "shuffled_control_summary.csv", index=False)
        summary = summary.merge(shuffle_summary[["method", "shuffled_false_steer_rate", "shuffled_false_steer_rate_ci_low", "shuffled_false_steer_rate_ci_high"]], on="method", how="left")
        summary["consumer"] = consumer
        summary["consumer_utility"] = summary["promotion_utility"] - summary["shuffled_false_steer_rate"].fillna(0.0)
        summary.to_csv(consumer_dir / "method_summary_with_shuffled.csv", index=False)
        method_frames.append(summary)
        shuffled_frames.append(shuffle_summary)
        leak = P13B.leakage_checks(predictions, consumer_cells, cfg)
        leak.insert(0, "consumer", consumer)
        leak.to_csv(consumer_dir / "leakage_checks.csv", index=False)
        leakage_frames.append(leak)
        best = summary.sort_values(["consumer_utility", "average_precision"], ascending=False).iloc[0]
        winner_rows.append(
            {
                "consumer": consumer,
                "winner_method": best["method"],
                "winner_variant": best["method_variant"],
                "positive_cells": int(consumer_cells["promotion_label"].sum()),
                "best_utility": float(best["consumer_utility"]),
                "utility_ci": "[{:.3f}, {:.3f}]".format(best["promotion_utility_ci_low"], best["promotion_utility_ci_high"]),
                "false_control": float(best["false_promotion_control_rate"]),
                "shuffled_false_steer_rate": float(best["shuffled_false_steer_rate"]),
            }
        )
        metric = cfg["consumer_limits"][consumer]["metric"]
        promoted = consumer_cells[consumer_cells["promotion_label"] == 1]
        controls = consumer_cells[consumer_cells["atom"] == "nominal_control"]
        rng = np.random.default_rng(int(cfg["random_seed"]) + sum(ord(c) for c in consumer))
        runs = sorted(consumer_cells["run"].unique())
        by_run = {int(run): promoted[promoted["run"] == run] for run in runs}
        boot = []
        for _ in range(int(cfg["ml"]["bootstrap_samples"])):
            sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, len(runs), replace=True)], ignore_index=True)
            boot.append(float(np.average(sample[metric], weights=np.maximum(sample["n"], 1.0))) if len(sample) else float("nan"))
        lo, hi = ci95(boot)
        endpoint_rows.append(
            {
                "consumer": consumer,
                "n_cells": int(len(consumer_cells)),
                "n_positive": int(consumer_cells["promotion_label"].sum()),
                "metric": metric,
                "promoted_metric_mean": float(np.average(promoted[metric], weights=np.maximum(promoted["n"], 1.0))) if len(promoted) else float("nan"),
                "promoted_metric_ci_low": lo,
                "promoted_metric_ci_high": hi,
                "control_metric_mean": float(np.average(controls[metric], weights=np.maximum(controls["n"], 1.0))) if len(controls) else float("nan"),
            }
        )

    all_methods = pd.concat(method_frames, ignore_index=True)
    winners = pd.DataFrame(winner_rows)
    shuffled_summary = pd.concat(shuffled_frames, ignore_index=True)
    leakage = pd.concat(leakage_frames, ignore_index=True)
    endpoint_summary = pd.DataFrame(endpoint_rows)
    all_methods.to_csv(out_dir / "consumer_method_summary.csv", index=False)
    winners.to_csv(out_dir / "consumer_winners.csv", index=False)
    shuffled_summary.to_csv(out_dir / "shuffled_control_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    endpoint_summary.to_csv(out_dir / "endpoint_systematics_by_consumer.csv", index=False)

    overall = all_methods.sort_values(["consumer_utility", "average_precision"], ascending=False).iloc[0].to_dict()
    runtime = time.time() - t0
    result = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "reproduction_pass": bool(reproduction["pass"].all()),
        "split": {"unit": "run", "type": "leave-one-run-out", "runs": P13B.configured_runs(cfg), "bootstrap_samples": int(cfg["ml"]["bootstrap_samples"])},
        "frozen_gate_source": "P13b promotion_criteria, unchanged in configs/p13c_1781164722_1110_69a0219b_rare_atom_external_steering.json",
        "consumers": list(cfg["consumer_limits"].keys()),
        "methods_benchmarked": P13B.METHOD_ORDER,
        "winner_name": overall["method"],
        "winner": {
            "consumer": overall["consumer"],
            "method": overall["method"],
            "method_variant": overall["method_variant"],
            "promotion_utility": overall["consumer_utility"],
            "promotion_utility_ci": [overall["promotion_utility_ci_low"], overall["promotion_utility_ci_high"]],
            "average_precision": overall["average_precision"],
            "average_precision_ci": [overall["average_precision_ci_low"], overall["average_precision_ci_high"]],
            "false_promotion_control_rate": overall["false_promotion_control_rate"],
            "shuffled_false_steer_rate": overall["shuffled_false_steer_rate"],
            "ece": overall["ece"],
        },
        "consumer_winners": winners.to_dict(orient="records"),
        "shuffled_control_summary": shuffled_summary.to_dict(orient="records"),
        "endpoint_systematics_by_consumer": endpoint_summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "next_tickets": [],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_sec": runtime,
    }
    write_report(out_dir, cfg_path, cfg, reproduction, support, winners, all_methods, shuffled_summary, endpoint_summary, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__).resolve().relative_to(ROOT), cfg_path),
        "config": str(cfg_path),
        "random_seed": int(cfg["random_seed"]),
        "runtime_sec": runtime,
        "inputs": input_hashes.to_dict(orient="records"),
        "outputs": P13B.output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": cfg["ticket"], "winner": result["winner"], "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
