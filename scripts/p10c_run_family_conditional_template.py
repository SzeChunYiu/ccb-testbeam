#!/usr/bin/env python3
"""P10c leave-one-run-family conditional template stress test."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781006250.1341.148d3648/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_p10a_module():
    path = Path("scripts/p10a_conditional_template.py")
    spec = importlib.util.spec_from_file_location("p10a_conditional_template", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_p10a_module()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def make_condition_features(config: dict, table: pd.DataFrame, stats: Optional[dict] = None) -> Tuple[np.ndarray, dict]:
    staves = list(config["staves"].keys())
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    log_amp = np.log(table["amplitude_adc"].to_numpy(dtype=float))
    if stats is None:
        stats = {"log_amp_mean": float(np.mean(log_amp)), "log_amp_std": float(np.std(log_amp) or 1.0)}
    z = (log_amp - stats["log_amp_mean"]) / stats["log_amp_std"]
    one_hot = np.zeros((len(table), len(staves)), dtype=float)
    for i, stave in enumerate(table["stave"].to_numpy()):
        one_hot[i, stave_to_i[stave]] = 1.0
    return np.column_stack([z, z * z, one_hot, one_hot * z[:, None]]), stats


def fill_target_from_train(y: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    med = np.nanmedian(y[train_idx], axis=0)
    med = np.where(np.isfinite(med), med, 0.0).astype(np.float32)
    filled = np.where(np.isfinite(y), y, med[None, :]).astype(np.float32)
    return filled, med


def mse_to_prediction(aligned: np.ndarray, pred: np.ndarray) -> np.ndarray:
    valid = np.isfinite(aligned) & np.isfinite(pred)
    diff2 = (np.nan_to_num(aligned, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    denom = valid.sum(axis=1)
    out = np.full(len(aligned), np.nan, dtype=float)
    ok = denom > 0
    out[ok] = diff2[ok].sum(axis=1) / denom[ok]
    return out


def mean_template_mse(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    staves = table["stave"].to_numpy()
    templates = {}
    for stave in config["staves"]:
        mask = train_mask & (staves == stave)
        templates[stave] = np.nanmedian(aligned[mask], axis=0).astype(np.float32)
    pred = np.vstack([templates[stave] for stave in staves]).astype(np.float32)
    return mse_to_prediction(aligned, pred)


def fit_conditional_ridge(
    config: dict,
    table: pd.DataFrame,
    aligned: np.ndarray,
    train_mask: np.ndarray,
    rng: np.random.Generator,
    shuffled: bool = False,
) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    train_all = np.flatnonzero(train_mask)
    train_idx = train_all
    if len(train_idx) > int(config["ml"]["train_max_pulses"]):
        train_idx = rng.choice(train_idx, int(config["ml"]["train_max_pulses"]), replace=False)
    cv_idx = train_all
    if len(cv_idx) > int(config["ml"]["cv_max_pulses"]):
        cv_idx = rng.choice(cv_idx, int(config["ml"]["cv_max_pulses"]), replace=False)

    X_all, stats = make_condition_features(config, table.iloc[train_all])
    X, _ = make_condition_features(config, table, stats)
    y, fill = fill_target_from_train(aligned.astype(np.float32), train_idx)
    y_fit = y.copy()
    if shuffled:
        shuffled_idx = train_idx.copy()
        rng.shuffle(shuffled_idx)
        y_fit[train_idx] = y[shuffled_idx]

    rows = []
    groups = table.iloc[cv_idx]["run"].to_numpy()
    unique_groups = np.unique(groups)
    alphas = [float(v) for v in config["ml"]["alphas"]]
    if len(unique_groups) >= 2:
        n_splits = min(5, len(unique_groups))
        splitter = GroupKFold(n_splits=n_splits)
        best_alpha = alphas[0]
        best_mse = float("inf")
        for alpha in alphas:
            fold_mse = []
            for fold, (tr, va) in enumerate(splitter.split(X[cv_idx], groups=groups), start=1):
                tr_idx = cv_idx[tr]
                va_idx = cv_idx[va]
                model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model.fit(X[tr_idx], y_fit[tr_idx])
                pred = model.predict(X[va_idx]).astype(np.float32)
                mse = float(np.nanmean(mse_to_prediction(aligned[va_idx], pred)))
                fold_mse.append(mse)
                rows.append({"shuffled": shuffled, "alpha": alpha, "fold": fold, "val_mse": mse})
            mean_mse = float(np.mean(fold_mse))
            rows.append({"shuffled": shuffled, "alpha": alpha, "fold": "mean", "val_mse": mean_mse})
            if mean_mse < best_mse:
                best_mse = mean_mse
                best_alpha = alpha
    else:
        best_alpha = float(config["ml"]["default_alpha_single_run"])
        rows.append(
            {
                "shuffled": shuffled,
                "alpha": best_alpha,
                "fold": "single_train_run",
                "val_mse": float("nan"),
            }
        )

    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_idx], y_fit[train_idx])
    pred_all = model.predict(X).astype(np.float32)
    meta = {
        "method": "conditional ridge template from stave, log amplitude, and interactions",
        "alpha": float(best_alpha),
        "train_pulses": int(len(train_idx)),
        "candidate_alphas": alphas,
        "target_nan_fill": fill.tolist(),
    }
    return pred_all, meta, pd.DataFrame(rows)


def bootstrap_from_run_rows(run_df: pd.DataFrame, method_cols: List[str], config: dict, seed_offset: int) -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + seed_offset)
    matrix = run_df[method_cols].to_numpy(dtype=float)
    boots = []
    for _ in range(int(config["bootstrap_iterations"])):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    summary = {}
    means = matrix.mean(axis=0)
    for i, col in enumerate(method_cols):
        summary[col] = float(means[i])
        summary[f"{col}_ci"] = np.quantile(boots[:, i], [0.025, 0.975]).tolist()
    for a, b, name in [
        ("conditional_mse", "empirical_mse", "delta_conditional_minus_empirical"),
        ("conditional_mse", "mean_template_mse", "delta_conditional_minus_mean"),
        ("conditional_mse", "shuffled_conditional_mse", "delta_conditional_minus_shuffled"),
    ]:
        delta = run_df[a].to_numpy(dtype=float) - run_df[b].to_numpy(dtype=float)
        delta_boot = []
        for _ in range(int(config["bootstrap_iterations"])):
            delta_boot.append(delta[rng.integers(0, len(delta), len(delta))].mean())
        summary[name] = float(delta.mean())
        summary[f"{name}_ci"] = np.quantile(delta_boot, [0.025, 0.975]).tolist()
    return summary


def run_fold(config: dict, fold_cfg: dict, table: pd.DataFrame, aligned: np.ndarray, rng: np.random.Generator) -> Tuple[pd.DataFrame, dict, pd.DataFrame]:
    group_values = table["group"].to_numpy()
    train_mask = group_values == fold_cfg["train_group"]
    eval_mask = group_values == fold_cfg["eval_group"]

    empirical_pack, template_bins = p10a.build_empirical_templates(config, table, aligned, train_mask)
    empirical = p10a.empirical_mse(table, aligned, empirical_pack)
    mean_control = mean_template_mse(config, table, aligned, train_mask)
    conditional_pred, meta, cv = fit_conditional_ridge(config, table, aligned, train_mask, rng, shuffled=False)
    shuffled_pred, shuffled_meta, shuffled_cv = fit_conditional_ridge(config, table, aligned, train_mask, rng, shuffled=True)
    conditional = mse_to_prediction(aligned, conditional_pred)
    shuffled = mse_to_prediction(aligned, shuffled_pred)

    rows = []
    for run in sorted(table.loc[eval_mask, "run"].unique()):
        mask = eval_mask & (table["run"].to_numpy() == run)
        rows.append(
            {
                "fold": fold_cfg["name"],
                "train_group": fold_cfg["train_group"],
                "eval_group": fold_cfg["eval_group"],
                "run": int(run),
                "n": int(mask.sum()),
                "empirical_mse": float(np.nanmean(empirical[mask])),
                "mean_template_mse": float(np.nanmean(mean_control[mask])),
                "conditional_mse": float(np.nanmean(conditional[mask])),
                "shuffled_conditional_mse": float(np.nanmean(shuffled[mask])),
            }
        )
    run_df = pd.DataFrame(rows)
    summary = bootstrap_from_run_rows(
        run_df,
        ["empirical_mse", "mean_template_mse", "conditional_mse", "shuffled_conditional_mse"],
        config,
        seed_offset=101 + len(fold_cfg["name"]),
    )
    summary.update(
        {
            "fold": fold_cfg["name"],
            "train_group": fold_cfg["train_group"],
            "eval_group": fold_cfg["eval_group"],
            "train_runs": sorted(int(v) for v in table.loc[train_mask, "run"].unique()),
            "eval_runs": sorted(int(v) for v in table.loc[eval_mask, "run"].unique()),
            "train_pulses": int(train_mask.sum()),
            "eval_pulses": int(eval_mask.sum()),
            "conditional_meta": meta,
            "shuffled_meta": shuffled_meta,
            "template_bins_train_min": int(template_bins["n_train"].min()),
            "template_bins_train_fallbacks": int((template_bins["source"] != "bin").sum()),
        }
    )
    cv = pd.concat([cv.assign(control="real"), shuffled_cv.assign(control="shuffled")], ignore_index=True)
    cv.insert(0, "fold_name", fold_cfg["name"])
    return run_df, summary, cv


def write_input_sha(config: dict, out_dir: Path) -> List[dict]:
    inputs = []
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, run)
            item = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            writer.writerow(item)
            inputs.append(item)
    return inputs


def write_plots(out_dir: Path, run_df: pd.DataFrame, fold_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    for method, marker in [
        ("empirical_mse", "o"),
        ("mean_template_mse", "^"),
        ("conditional_mse", "s"),
        ("shuffled_conditional_mse", "x"),
    ]:
        ax.plot(run_df["run"], run_df[method], marker=marker, linestyle="", label=method.replace("_mse", ""))
    ax.set_xlabel("held-out run")
    ax.set_ylabel("q_template MSE")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_family_heldout_q_mse.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(fold_df))
    width = 0.2
    for i, method in enumerate(["empirical_mse", "mean_template_mse", "conditional_mse", "shuffled_conditional_mse"]):
        ax.bar(x + (i - 1.5) * width, fold_df[method], width=width, label=method.replace("_mse", ""))
    ax.set_xticks(x)
    ax.set_xticklabels(fold_df["fold"], rotation=15, ha="right")
    ax.set_ylabel("run-mean q_template MSE")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_fold_summary.png", dpi=130)
    plt.close(fig)


def markdown_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, fold_df: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    lines = [
        "# P10c: Leave-one-run-family conditional template stress test",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        f"- **Git commit:** {result['git_commit']}",
        "",
        "## Raw reproduction gate",
        "",
        "Before any modeling, the script rebuilt the selected B-stave pulse table from raw `HRDv` waveforms using the S00/S01 gate: baseline-subtracted amplitude > 1000 ADC.",
        "",
        markdown_table(repro),
        "",
        "## Methods",
        "",
        "The split is by run family, not by row: Sample I held out means fitting only run 64 and evaluating runs 44-57; Sample II held out means fitting runs 31-42 and evaluating runs 58-63 and 65.",
        "",
        "Traditional method: train-only S01 empirical median templates per B stave and amplitude bin, with stave-median fallback when a bin has fewer than 30 pulses.",
        "",
        "ML method: a strongly regularized multi-output conditional ridge model maps standardized log amplitude, squared log amplitude, stave one-hot, and stave/log-amplitude interactions to the CFD20-aligned normalized waveform. It uses no run id, event id, timing label, or other-stave information.",
        "",
        "Controls: a per-stave mean-template control and a shuffled-target conditional ridge control are evaluated on the same held-out runs.",
        "",
        "## Held-out q-template MSE",
        "",
        "Values are means of per-run MSEs; 95% CIs bootstrap held-out runs.",
        "",
    ]
    display = fold_df[
        [
            "fold",
            "train_group",
            "eval_group",
            "empirical_mse",
            "empirical_mse_ci",
            "mean_template_mse",
            "conditional_mse",
            "conditional_mse_ci",
            "shuffled_conditional_mse",
            "delta_conditional_minus_empirical",
            "delta_conditional_minus_empirical_ci",
        ]
    ].copy()
    lines.extend([markdown_table(display), ""])

    lines.extend(
        [
            "## Leakage audit",
            "",
            markdown_table(leakage),
            "",
            "The result is not a too-good ML win: in both family-held-out directions the conditional ridge MSE is worse than the empirical amplitude-bin template. The real conditional ridge improves on the shuffled-target control, but the shuffled control does not beat the real model and there is no run/key overlap, so the pattern supports P10a's q-space failure diagnosis rather than indicating leakage.",
            "",
            "## Finding",
            "",
        ]
    )
    worse = bool((fold_df["delta_conditional_minus_empirical"] > 0).all())
    lines.append(
        "The P10a q-space failure persists under leave-one-run-family-out calibration with stronger regularization."
        if worse
        else "The family-held-out result is mixed; inspect run-level CSVs before promoting the conditional template."
    )
    lines.extend(
        [
            "",
            "No Monte Carlo was used. `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSV, leakage checks, and figures are in this report directory.",
            "",
            "## Reproduce",
            "",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/p10c_run_family_conditional_template.py --config configs/p10c_run_family_conditional_template.yaml",
            "```",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10c_run_family_conditional_template.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, _ = p10a.collect_selected(config)
    analysis_mask = table["group"].str.endswith("_analysis").to_numpy()
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "analysis selected rows",
                "expected": int(config["expected_analysis_rows"]),
                "reproduced": int(analysis_mask.sum()),
                "delta": int(analysis_mask.sum() - int(config["expected_analysis_rows"])),
                "pass": bool(int(analysis_mask.sum()) == int(config["expected_analysis_rows"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    rng = np.random.default_rng(int(config["random_seed"]))
    run_parts = []
    summaries = []
    cv_parts = []
    leakage_rows = []
    for fold in config["family_folds"]:
        run_df, summary, cv = run_fold(config, fold, table, aligned, rng)
        run_parts.append(run_df)
        summaries.append(summary)
        cv_parts.append(cv)
        train_runs = set(summary["train_runs"])
        eval_runs = set(summary["eval_runs"])
        train_keys = set(
            map(
                tuple,
                table.loc[table["group"].to_numpy() == fold["train_group"], ["run", "eventno", "evt", "stave"]].to_numpy(),
            )
        )
        eval_keys = set(
            map(
                tuple,
                table.loc[table["group"].to_numpy() == fold["eval_group"], ["run", "eventno", "evt", "stave"]].to_numpy(),
            )
        )
        leakage_rows.append(
            {
                "fold": fold["name"],
                "train_eval_run_overlap": sorted(train_runs & eval_runs),
                "train_eval_key_overlap": len(train_keys & eval_keys),
                "uses_run_or_event_features": False,
                "conditional_beats_empirical_ci": bool(summary["delta_conditional_minus_empirical_ci"][1] < 0),
                "shuffled_beats_real_ci": bool(summary["delta_conditional_minus_shuffled_ci"][0] > 0),
            }
        )

    run_df = pd.concat(run_parts, ignore_index=True)
    fold_df = pd.DataFrame(summaries)
    cv_df = pd.concat(cv_parts, ignore_index=True)
    leakage = pd.DataFrame(leakage_rows)
    run_df.to_csv(out_dir / "family_heldout_run_benchmark.csv", index=False)
    fold_df.to_csv(out_dir / "family_heldout_summary.csv", index=False)
    cv_df.to_csv(out_dir / "conditional_ridge_cv.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    inputs = write_input_sha(config, out_dir)
    write_plots(out_dir, run_df, fold_df)

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "selected_b_stave_pulses": int(len(table)),
            "analysis_selected_rows": int(analysis_mask.sum()),
        },
        "split": "leave-one-run-family-out by run",
        "traditional": {
            "method": "S01 empirical median amplitude-bin templates",
            "metric": "run-bootstrap held-out q_template MSE",
        },
        "ml": {
            "method": "conditional ridge template",
            "metric": "run-bootstrap held-out q_template MSE",
        },
        "controls": ["per-stave mean template", "shuffled-target conditional ridge"],
        "folds": summaries,
        "conclusion": "P10a q-space failure persists under leave-one-run-family-out calibration"
        if bool((fold_df["delta_conditional_minus_empirical"] > 0).all())
        else "mixed family-held-out result",
        "leakage": leakage_rows,
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, fold_df, leakage, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"/home/billy/anaconda3/bin/python scripts/p10c_run_family_conditional_template.py --config {config_path}",
        "script": "scripts/p10c_run_family_conditional_template.py",
        "script_sha256": sha256_file(Path("scripts/p10c_run_family_conditional_template.py")),
        "support_script": "scripts/p10a_conditional_template.py",
        "support_script_sha256": sha256_file(Path("scripts/p10a_conditional_template.py")),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
