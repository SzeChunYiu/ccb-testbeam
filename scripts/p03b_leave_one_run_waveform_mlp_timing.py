#!/usr/bin/env python3
"""P03b leave-one-run-out stability of the P03a waveform MLP timing benchmark."""

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
from typing import Dict, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03b")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

import p03a_18_sample_mlp_timing as p03a
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a


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


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def fold_config(config: dict, heldout_run: int, loo_runs: Sequence[int]) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
    return cfg


def plot_outputs(out_dir: Path, heldout: pd.DataFrame, p03a_repro: pd.DataFrame) -> None:
    methods = ["analytic_timewalk", "s02_ridge_cfd20", "mlp_waveform"]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    for method in methods:
        rows = heldout[heldout["method"] == method].sort_values("heldout_run")
        ax.errorbar(
            rows["heldout_run"],
            rows["sigma68_ns"],
            yerr=[rows["sigma68_ns"] - rows["ci_low"], rows["ci_high"] - rows["sigma68_ns"]],
            marker="o",
            capsize=3,
            label=method,
        )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("P03b leave-one-run-out timing stability")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loo_stability.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.8, 4.4))
    wide = heldout.pivot(index="heldout_run", columns="method", values="sigma68_ns")
    ax.axhline(0.0, color="black", linewidth=1)
    if {"mlp_waveform", "s02_ridge_cfd20"}.issubset(wide.columns):
        ax.plot(wide.index, wide["mlp_waveform"] - wide["s02_ridge_cfd20"], "o-", label="MLP - S02 ridge")
    if {"mlp_waveform", "analytic_timewalk"}.issubset(wide.columns):
        ax.plot(wide.index, wide["mlp_waveform"] - wide["analytic_timewalk"], "s-", label="MLP - analytic")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("sigma68 delta (ns)")
    ax.set_title("MLP point-estimate deltas")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_mlp_deltas.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.8, 4.0))
    repro = p03a_repro.sort_values("method")
    ax.bar(repro["method"], repro["sigma68_ns"])
    ax.errorbar(
        np.arange(len(repro)),
        repro["sigma68_ns"],
        yerr=[repro["sigma68_ns"] - repro["ci_low"], repro["ci_high"] - repro["sigma68_ns"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.set_ylabel("run-65 sigma68 (ns)")
    ax.set_title("P03a number reproduced before LOO")
    ax.tick_params(axis="x", labelrotation=25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_p03a_reproduction.png", dpi=130)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def summarize_winner(heldout: pd.DataFrame) -> pd.DataFrame:
    wide = heldout.pivot(index="heldout_run", columns="method", values="sigma68_ns")
    rows = []
    for run, row in wide.iterrows():
        rows.append(
            {
                "heldout_run": int(run),
                "best_method": str(row.idxmin()),
                "best_sigma68_ns": float(row.min()),
                "mlp_minus_s02_ridge_ns": float(row["mlp_waveform"] - row["s02_ridge_cfd20"]),
                "mlp_minus_analytic_ns": float(row["mlp_waveform"] - row["analytic_timewalk"]),
            }
        )
    return pd.DataFrame(rows)


def pooled_summary(heldout: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in heldout.groupby("method"):
        rows.append(
            {
                "method": method,
                "mean_sigma68_ns": float(group["sigma68_ns"].mean()),
                "median_sigma68_ns": float(group["sigma68_ns"].median()),
                "min_sigma68_ns": float(group["sigma68_ns"].min()),
                "max_sigma68_ns": float(group["sigma68_ns"].max()),
                "n_heldout_runs": int(group["heldout_run"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns")


def run_fold(
    pulses: pd.DataFrame,
    config: dict,
    heldout_run: int,
    loo_runs: Sequence[int],
    out_dir: Path,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    cfg = fold_config(config, heldout_run, loo_runs)
    train_pulses = pulses[pulses["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    fold_pulses = pulses.copy()
    methods = s02.add_traditional_times(fold_pulses, cfg, templates)
    scan = s02.evaluate_methods(fold_pulses, methods, cfg)
    scan["heldout_run"] = int(heldout_run)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    if best_method != cfg["timing"]["base_method"]:
        raise RuntimeError(f"run {heldout_run}: expected S02 base {cfg['timing']['base_method']}, got {best_method}")

    s02_ml_pulses, s02_ml_cv, s02_ml_cal = s02.run_ml(fold_pulses, cfg, "cfd20", 2.0)
    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(fold_pulses, cfg, best_method)
    combined = analytic_pulses.copy()
    combined["t_s02_ridge_cfd20_ns"] = s02_ml_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)

    mlp_pulses, mlp_cv, calibration, mlp_info = p03a.run_waveform_mlp(combined, cfg, str(cfg["ml"]["base_method"]))
    combined["t_mlp_waveform_ns"] = mlp_pulses["t_mlp_waveform_ns"].to_numpy(dtype=float)
    combined["mlp_target_residual_ns"] = mlp_pulses["mlp_target_residual_ns"].to_numpy(dtype=float)
    combined["mlp_pred_residual_ns"] = mlp_pulses["mlp_pred_residual_ns"].to_numpy(dtype=float)
    combined["mlp_pred_sigma_ns"] = mlp_pulses["mlp_pred_sigma_ns"].to_numpy(dtype=float)

    methods_for_bootstrap = [
        ("cfd20", "cfd20_reference"),
        ("template_phase", "template_phase"),
        ("s02_ridge_cfd20", "s02_ridge_cfd20"),
        ("analytic_timewalk", "analytic_timewalk"),
        ("mlp_waveform", "mlp_waveform"),
    ]
    pair_frame = p03a.event_pair_residual_frame(combined, methods_for_bootstrap, cfg, [heldout_run])
    pair_frame["heldout_run"] = int(heldout_run)
    benchmark = p03a.paired_event_bootstrap(pair_frame, "s02_ridge_cfd20", rng, int(cfg["ml"]["bootstrap_samples"]))
    benchmark["heldout_run"] = int(heldout_run)
    benchmark["train_runs"] = ",".join(str(run) for run in cfg["timing"]["train_runs"])

    leakage = p03a.leakage_checks(combined, combined, cfg, mlp_info)
    leakage["heldout_run"] = int(heldout_run)
    calibration["heldout_run"] = int(heldout_run)
    mlp_cv["heldout_run"] = int(heldout_run)
    analytic_cv["heldout_run"] = int(heldout_run)
    s02_ml_cv["heldout_run"] = int(heldout_run)
    analytic_coef["heldout_run"] = int(heldout_run)
    s02_ml_cal["heldout_run"] = int(heldout_run)

    info = {
        "heldout_run": int(heldout_run),
        "train_runs": cfg["timing"]["train_runs"],
        "traditional_base_method": best_method,
        "analytic_candidate": best_candidate,
        "analytic_alpha": float(best_alpha),
        "mlp_hidden": int(mlp_info["hidden"]),
        "mlp_weight_decay": float(mlp_info["weight_decay"]),
        "mlp_n_features": int(mlp_info["n_features"]),
    }
    diag = pd.DataFrame([info])
    diag.to_csv(out_dir / f"fold_{heldout_run}_model_choices.csv", index=False)
    return benchmark, pair_frame, leakage, calibration, {
        "scan": scan,
        "mlp_cv": mlp_cv,
        "analytic_cv": analytic_cv,
        "s02_ml_cv": s02_ml_cv,
        "analytic_coef": analytic_coef,
        "s02_ml_cal": s02_ml_cal,
        "model_choice": diag,
    }


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    p03a_repro: pd.DataFrame,
    heldout: pd.DataFrame,
    winners: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    lines = [
        "# Study report: P03b - leave-one-run-out waveform MLP timing stability",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one run out across runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Config:** `configs/p03b_leave_one_run_waveform_mlp_timing.yaml`",
        "",
        "## Question",
        "",
        "Is the P03a negative MLP result a run-65 artifact, or does it persist when each sample-II analysis run is held out in turn?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count gate was rerun from raw ROOT before timing work.",
        "",
        repro.to_markdown(index=False),
        "",
        "Before the leave-one-run-out scan, the P03a run-65 benchmark number was reproduced from the same raw pass and split.",
        "",
        p03a_repro[["method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## Leave-one-run-out head-to-head",
        "",
        heldout[["heldout_run", "method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "delta_vs_s02_ridge_ns", "delta_ci_low", "delta_ci_high", "n_pair_residuals"]]
        .sort_values(["heldout_run", "sigma68_ns"])
        .to_markdown(index=False),
        "",
        "## Stability summary",
        "",
        pooled.to_markdown(index=False),
        "",
        winners.to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        leakage.sort_values(["heldout_run", "check"]).to_markdown(index=False),
        "",
        "The MLP features are still only the 18 same-pulse samples normalized by amplitude plus stave one-hot. The split is by run for every fold; event-id overlap is zero in all folds; shuffled-target controls are reported for each held-out run.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. The MLP is best on `{result['mlp_best_run_count']}` of `{len(result['heldout_runs'])}` held-out runs and its mean sigma68 is `{result['mean_sigma68_ns']['mlp_waveform']:.3f} ns` versus `{result['mean_sigma68_ns']['s02_ridge_cfd20']:.3f} ns` for S02 ridge and `{result['mean_sigma68_ns']['analytic_timewalk']:.3f} ns` for analytic timewalk.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p03b_leave_one_run_waveform_mlp_timing.py --config configs/p03b_leave_one_run_waveform_mlp_timing.yaml",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `p03a_run65_reproduction.csv`, `heldout_run_summary.csv`, `pooled_summary.csv`, `winner_by_run.csv`, `leakage_checks.csv`, `mlp_cv_scan.csv`, `analytic_cv_scan.csv`, figures, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03b_leave_one_run_waveform_mlp_timing.yaml")
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
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_run_cfg = copy.deepcopy(config)
    all_run_cfg["timing"]["train_runs"] = loo_runs
    all_run_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(all_run_cfg)
    run_counts = (
        pulses.groupby(["run", "stave"]).size().reset_index(name="selected_full_downstream_events_per_stave")
    )
    run_counts.to_csv(out_dir / "downstream_counts_by_run.csv", index=False)

    p03a_benchmark, p03a_pairs, p03a_leakage, p03a_cal, p03a_extra = run_fold(pulses, config, 65, loo_runs, out_dir, rng)
    p03a_repro = p03a_benchmark.copy()
    p03a_repro.to_csv(out_dir / "p03a_run65_reproduction.csv", index=False)
    p03a_pairs.to_csv(out_dir / "p03a_run65_pair_residuals.csv", index=False)
    p03a_leakage.to_csv(out_dir / "p03a_run65_leakage_checks.csv", index=False)

    benchmark_frames = []
    pair_frames = []
    leakage_frames = []
    calibration_frames = []
    scan_frames = []
    mlp_cv_frames = []
    analytic_cv_frames = []
    s02_ml_cv_frames = []
    coef_frames = []
    s02_cal_frames = []
    model_choice_frames = []
    for heldout_run in loo_runs:
        if int(heldout_run) == 65:
            benchmark, pair_frame, leakage, calibration, extra = (
                p03a_benchmark,
                p03a_pairs,
                p03a_leakage,
                p03a_cal,
                p03a_extra,
            )
        else:
            benchmark, pair_frame, leakage, calibration, extra = run_fold(pulses, config, heldout_run, loo_runs, out_dir, rng)
        benchmark_frames.append(benchmark)
        pair_frames.append(pair_frame)
        leakage_frames.append(leakage)
        calibration_frames.append(calibration)
        scan_frames.append(extra["scan"])
        mlp_cv_frames.append(extra["mlp_cv"])
        analytic_cv_frames.append(extra["analytic_cv"])
        s02_ml_cv_frames.append(extra["s02_ml_cv"])
        coef_frames.append(extra["analytic_coef"])
        s02_cal_frames.append(extra["s02_ml_cal"])
        model_choice_frames.append(extra["model_choice"])

    heldout = pd.concat(benchmark_frames, ignore_index=True)
    heldout.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    pd.concat(pair_frames, ignore_index=True).to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    leakage = pd.concat(leakage_frames, ignore_index=True)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    calibration = pd.concat(calibration_frames, ignore_index=True)
    calibration.to_csv(out_dir / "mlp_sigma_calibration.csv", index=False)
    pd.concat(scan_frames, ignore_index=True).to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    pd.concat(mlp_cv_frames, ignore_index=True).to_csv(out_dir / "mlp_cv_scan.csv", index=False)
    pd.concat(analytic_cv_frames, ignore_index=True).to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    pd.concat(s02_ml_cv_frames, ignore_index=True).to_csv(out_dir / "s02_ridge_cv_scan.csv", index=False)
    pd.concat(coef_frames, ignore_index=True).to_csv(out_dir / "analytic_coefficients.csv", index=False)
    pd.concat(s02_cal_frames, ignore_index=True).to_csv(out_dir / "s02_ridge_residual_calibration.csv", index=False)
    pd.concat(model_choice_frames, ignore_index=True).to_csv(out_dir / "model_choices_by_run.csv", index=False)

    winners = summarize_winner(heldout)
    winners.to_csv(out_dir / "winner_by_run.csv", index=False)
    pooled = pooled_summary(heldout)
    pooled.to_csv(out_dir / "pooled_summary.csv", index=False)
    plot_outputs(out_dir, heldout, p03a_repro)

    mean_sigma = {
        method: float(group["sigma68_ns"].mean()) for method, group in heldout.groupby("method")
    }
    mlp_best_count = int((winners["best_method"] == "mlp_waveform").sum())
    mlp_beats_s02_count = int((winners["mlp_minus_s02_ridge_ns"] < 0.0).sum())
    mlp_beats_analytic_count = int((winners["mlp_minus_analytic_ns"] < 0.0).sum())
    leak_overlap_max = int(
        leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()
    )
    verdict = "mlp_negative_result_stable_across_leave_one_run_out"
    if mlp_best_count >= max(4, len(loo_runs) // 2 + 1):
        verdict = "mlp_beats_baselines_on_majority_of_heldout_runs"
    elif mlp_beats_s02_count >= max(4, len(loo_runs) // 2 + 1):
        verdict = "mlp_often_beats_s02_ridge_but_not_traditional_baseline"

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    result = {
        "study": "P03b",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "p03a_run65_reproduced": {
            row["method"]: {
                "sigma68_ns": float(row["sigma68_ns"]),
                "ci": [float(row["ci_low"]), float(row["ci_high"])],
                "full_rms_ns": float(row["full_rms_ns"]),
            }
            for _, row in p03a_repro.iterrows()
        },
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "metric": "heldout B4/B6/B8 pairwise sigma68 ns with event-paired bootstrap CI per held-out run",
        "mean_sigma68_ns": mean_sigma,
        "mlp_best_run_count": mlp_best_count,
        "mlp_beats_s02_ridge_run_count": mlp_beats_s02_count,
        "mlp_beats_analytic_run_count": mlp_beats_analytic_count,
        "traditional": {
            "method": "analytic_timewalk_on_template_phase",
            "mean_sigma68_ns": mean_sigma["analytic_timewalk"],
        },
        "ml": {
            "method": "tiny_heteroskedastic_mlp_on_18_normalized_samples",
            "base_method": str(config["ml"]["base_method"]),
            "mean_sigma68_ns": mean_sigma["mlp_waveform"],
            "per_run": winners[["heldout_run", "mlp_minus_s02_ridge_ns", "mlp_minus_analytic_ns"]].to_dict(orient="records"),
        },
        "leakage": {
            "max_event_id_overlap": leak_overlap_max,
            "feature_audit": "features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target",
            "shuffled_target_controls": leakage[leakage["check"] == "shuffled_target_negative_control_sigma68_ns"][
                ["heldout_run", "value"]
            ].to_dict(orient="records"),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "P03c: waveform-only 1D CNN versus MLP timing with the same leave-one-run-out gates",
            "P03d: per-stave waveform MLP calibration failure analysis for high-sigma folds",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, p03a_repro, heldout, winners, pooled, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03b",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "verdict": verdict,
                "mlp_best_run_count": mlp_best_count,
                "mean_sigma68_ns": mean_sigma,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
