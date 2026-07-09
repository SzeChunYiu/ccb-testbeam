#!/usr/bin/env python3
"""S01h external q-template support transfer benchmark.

Reproduce the S00 selected B-stave count from raw ROOT, then test whether the
S01g/S01h q-template risk atom transfers to an injected pile-up/dropout support
target rather than an S03 timing-tail proxy.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s01h-transfer")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

BASE = importlib.machinery.SourceFileLoader(
    "s01h_base", "scripts/s01h_1781040960_832_1c8e6dee_qtemplate_atom_grid.py"
).load_module()


def qtoken_score(meta: pd.DataFrame, train_mask: np.ndarray) -> np.ndarray:
    cols = [
        "q_template_rmse",
        "log_amp",
        "area_over_amp",
        "late_fraction",
        "baseline_abs_centered",
        "post_peak_min",
        "dropout_atom",
        "delayed_peak_atom",
    ]
    x = meta[cols].to_numpy(dtype=float)
    med = np.nanmedian(x[train_mask], axis=0)
    scale = np.nanmedian(np.abs(x[train_mask] - med), axis=0) + 1e-6
    z = (x - med) / scale
    weights = np.asarray([1.2, -0.15, -0.35, 0.45, 0.35, -0.45, 0.45, 0.25])
    return z.dot(weights)


def injected_support_delta(waves: np.ndarray, cfg: dict) -> np.ndarray:
    inj = cfg["injection"]
    sec = float(inj["pileup_secondary_fraction"])
    shift = int(inj["pileup_shift_samples"])
    drop_cols = [int(v) for v in inj["dropout_samples"]]
    drop_scale = float(inj["dropout_scale"])
    mixed_weight = float(inj["mixed_weight"])

    pile = waves.copy()
    pile[:, shift:] = pile[:, shift:] + sec * waves[:, :-shift]
    pile = pile / np.maximum(pile.max(axis=1, keepdims=True), 1e-6)

    drop = waves.copy()
    drop[:, drop_cols] *= drop_scale
    drop = drop / np.maximum(drop.max(axis=1, keepdims=True), 1e-6)

    mixed = mixed_weight * pile + (1.0 - mixed_weight) * drop
    mixed = mixed / np.maximum(mixed.max(axis=1, keepdims=True), 1e-6)

    # Shape-support damage is the increase in normalized-waveform roughness and
    # mismatch caused by deterministic pile-up and dropout perturbations.
    base_slope = np.diff(waves, axis=1)
    inj_slope = np.diff(mixed, axis=1)
    rmse = np.sqrt(np.mean((mixed - waves) ** 2, axis=1))
    rough = np.sqrt(np.mean((inj_slope - base_slope) ** 2, axis=1))
    late = np.clip(mixed[:, 10:], 0.0, None).sum(axis=1) - np.clip(waves[:, 10:], 0.0, None).sum(axis=1)
    return rmse + 0.35 * rough + 0.06 * np.maximum(late, 0.0)


def fit_atom_table(meta, y, train_mask, alpha):
    cols = [
        "stave",
        "amp_bin",
        "peak_phase_bin",
        "saturation_atom",
        "baseline_atom",
        "delayed_peak_atom",
        "dropout_atom",
        "topology_atom",
    ]
    train = meta.loc[train_mask, cols].copy()
    train["y"] = y[train_mask]
    global_rate = float(train["y"].mean())
    stats = train.groupby(cols)["y"].agg(["sum", "count"]).reset_index()
    stats["score"] = (stats["sum"] + alpha * global_rate) / (stats["count"] + alpha)
    return meta[cols].merge(stats[cols + ["score"]], on=cols, how="left")["score"].fillna(global_rate).to_numpy(dtype=float)


def finite_score(score) -> np.ndarray:
    arr = np.asarray(score, dtype=float)
    finite = np.isfinite(arr)
    if finite.all():
        return arr
    replacement = float(np.median(arr[finite])) if finite.any() else 0.0
    return np.where(finite, arr, replacement)


def summarize_methods(pred, n_boot, rng):
    pred = pred.copy()
    pred["score"] = pred.groupby("method")["score"].transform(finite_score)
    summary, per_run = BASE.summarize(pred, n_boot, rng)
    return summary.sort_values(["roc_auc", "average_precision"], ascending=False), per_run


def write_report(out_dir, result, summary, per_run, repro, transfer_rows, qdiag):
    winner = result["winner_metrics"]
    trad = result["best_traditional"]
    lines = [
        "# S01h external q-template support transfer",
        "",
        "**Ticket:** `{}`  ".format(result["ticket"]),
        "**Worker:** `{}`  ".format(result["worker"]),
        "**Date:** 2026-07-09",
        "",
        "## Abstract",
        "",
        "This study tests whether the S01g q-template risk atom transfers to an externally labeled support target. The external target is deterministic injected pile-up plus local dropout applied to raw-derived normalized B-stave waveforms; no S03 timing residual or timing-tail label is used. Raw ROOT reproduction is performed first. The held-out run winner is **{}** with ROC AUC **{:.4f}** [{:.4f}, {:.4f}] and AP **{:.4f}** [{:.4f}, {:.4f}]. The strongest traditional method is **{}** with ROC AUC **{:.4f}** [{:.4f}, {:.4f}].".format(
            winner["method"], winner["roc_auc"], winner["auc_ci_low"], winner["auc_ci_high"],
            winner["average_precision"], winner["ap_ci_low"], winner["ap_ci_high"],
            trad["method"], trad["roc_auc"], trad["auc_ci_low"], trad["auc_ci_high"],
        ),
        "",
        "## Raw ROOT reproduction",
        "",
        repro.to_markdown(index=False),
        "",
        "The reproduced selected-pulse count is **{:,}**, matching the registered raw B-stave count exactly. The q-template table join is one-to-one with **{:,}** rows.".format(
            result["reproduction"]["selected_pulses"], result["reproduction"]["q_rows_joined"]
        ),
        "",
        "## Target and equations",
        "",
        "For pulse waveform `x_i(t)`, a deterministic external perturbation is formed as a mixture of a delayed secondary-pulse overlay and a local dropout:",
        "",
        "`p_i(t)=norm[x_i(t)+a x_i(t-d)]`, `d_i(t)=norm[x_i(t) * m(t)]`, and `z_i(t)=w p_i(t)+(1-w)d_i(t)`.",
        "",
        "The injected support-damage score is",
        "",
        "`D_i = RMSE(z_i,x_i) + 0.35 RMSE(Delta z_i, Delta x_i) + 0.06 max(sum_{t>=10} z_i(t)-x_i(t),0)`.",
        "",
        "The binary target is `y_i=1[D_i > Q_0.85(D_train)]`; the threshold is fit on train runs only. This makes the target an injected pile-up/dropout support label rather than an S03b timing-tail proxy. All confidence intervals are 95% nonparametric bootstraps over held-out runs.",
        "",
        "## Splitting and leakage controls",
        "",
        "Training uses Sample I calibration, Sample I analysis, and Sample II calibration. Held-out evaluation uses runs `{}`. Run id, event id, event order, and the binary target are excluded from all learned feature matrices. The traditional q-threshold and q-token attention rows intentionally receive q-template summaries because the ticket asks whether that risk atom transfers; the other ML baselines are reported with the same observable scalar/waveform support features.".format(
            ", ".join(str(r) for r in result["split"]["heldout_runs"])
        ),
        "",
        "## Methods",
        "",
        "- **traditional_q_threshold:** train-run 90th-percentile threshold on `q_template_rmse`, scored directly as the q residual.",
        "- **traditional_atom_table:** smoothed detector atom support table with alpha `{}` over stave, amplitude, phase, saturation, baseline, delayed-peak, dropout, and topology atoms.".format(result["traditional_smoothing_alpha"]),
        "- **ridge, gradient_boosted_trees, MLP:** tabular baselines on waveform summaries and detector atoms.",
        "- **1d_cnn:** compact convolutional network on the normalized 18-sample waveform.",
        "- **q_token_attention:** fixed S01g-style q-token score combining q residual, amplitude, late fraction, baseline, dropout, and delayed-peak atoms.",
        "- **atom_gated_cnn_new:** a waveform CNN modulated by atom/tabular gates; it is the new architecture because injected support failures are waveform-local but amplitude/stave/baseline conditional.",
        "",
        "## Head-to-head benchmark",
        "",
        summary.to_markdown(index=False),
        "",
        "## Per-run metrics",
        "",
        per_run.to_markdown(index=False),
        "",
        "## Transfer diagnostics",
        "",
        transfer_rows.to_markdown(index=False),
        "",
        "q-template diagnostic contrasts:",
        "",
        qdiag.to_markdown(index=False),
        "",
        "## Systematics and caveats",
        "",
        "- The external target is injected, not independent beam truth. It tests transfer away from S03 timing residuals but not absolute pile-up rates.",
        "- The injection kernel is deterministic and laptop-safe; larger perturbation grids could change absolute AUCs.",
        "- The q-template source table is reused after raw ROOT count reproduction, so q values are not regenerated from scratch in this script.",
        "- Bootstrap units are runs, not pulses; this intentionally gives wider and more honest intervals.",
        "- A model win on injected support damage is diagnostic unless confirmed on real labeled pile-up/dropout or calibrated charge-depth truth.",
        "",
        "## Verdict",
        "",
        "`result.json` names **{}** as the winner. The transfer result is summarized as `{}`.".format(
            result["winner"], result["verdict"]
        ),
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s01h_1781120073_951_3fa574c6_external_qtemplate_support_transfer.py --config configs/s01h_1781120073_951_3fa574c6_external_qtemplate_support_transfer.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s01h_1781120073_951_3fa574c6_external_qtemplate_support_transfer.yaml"))
    args = parser.parse_args()
    t0 = time.time()
    cfg = BASE.load_config(args.config)
    rng = np.random.default_rng(int(cfg["random_seed"]))
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, raw_meta, counts = BASE.scan_raw(cfg)
    selected = int(len(raw_meta))
    expected = int(cfg["expected_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw reproduction failed: {} != {}".format(selected, expected))
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    repro = pd.DataFrame([{
        "quantity": "selected B-stave pulses with amplitude >1000 ADC",
        "report_value": expected,
        "reproduced": selected,
        "delta": selected - expected,
        "tolerance": 0,
        "pass": selected == expected,
    }])
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    meta, waves = BASE.merge_q_table(raw_meta, waves, cfg)
    meta = BASE.add_atoms(meta, waves)
    sample_idx = BASE.balanced_sample(meta, int(cfg["benchmark"]["max_per_run_stave"]), rng)
    bench = meta.iloc[sample_idx].reset_index(drop=True)
    bench_waves = waves[sample_idx]
    train_mask = bench["group"].isin(set(cfg["split"]["train_groups"])).to_numpy()
    test_mask = bench["group"].isin(set(cfg["split"]["heldout_groups"])).to_numpy()

    damage = injected_support_delta(bench_waves, cfg)
    threshold = float(np.quantile(damage[train_mask], float(cfg["benchmark"]["injected_support_train_quantile"])))
    y = (damage > threshold).astype(int)
    bench_out = bench[["run", "group", "eventno", "evt", "stave", "amplitude_adc_q", "peak_sample_q", "q_template_rmse", "area_over_amp", "baseline_centered", "late_fraction", "dropout_atom", "delayed_peak_atom", "topology_atom"]].copy()
    bench_out["injected_support_damage"] = damage
    bench_out["target"] = y
    bench_out.to_csv(out_dir / "benchmark_sample.csv.gz", index=False)

    x_tab, _ = BASE.make_design(bench)
    runs = bench["run"].to_numpy(dtype=int)
    pred = []
    pred.append(pd.DataFrame({"method": "traditional_atom_table", "family": "traditional", "run": runs[test_mask], "y_true": y[test_mask], "score": fit_atom_table(bench, y, train_mask, float(cfg["benchmark"]["atom_smoothing_alpha"]))[test_mask]}))
    pred.append(pd.DataFrame({"method": "traditional_q_threshold", "family": "traditional", "run": runs[test_mask], "y_true": y[test_mask], "score": bench["q_template_rmse"].to_numpy(dtype=float)[test_mask]}))
    pred.append(pd.DataFrame({"method": "q_token_attention", "family": "new_architecture", "run": runs[test_mask], "y_true": y[test_mask], "score": qtoken_score(bench, train_mask)[test_mask]}))

    methods = [
        ("ridge", "ml", make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(cfg["models"]["ridge_alpha"]), class_weight="balanced"))),
        ("gradient_boosted_trees", "ml", HistGradientBoostingClassifier(max_iter=int(cfg["models"]["hgb_max_iter"]), learning_rate=float(cfg["models"]["hgb_learning_rate"]), max_leaf_nodes=int(cfg["models"]["hgb_max_leaf_nodes"]), l2_regularization=float(cfg["models"]["hgb_l2_regularization"]), random_state=1781120074)),
        ("mlp", "nn", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=tuple(cfg["models"]["mlp_hidden"]), alpha=float(cfg["models"]["mlp_alpha"]), max_iter=int(cfg["models"]["mlp_max_iter"]), early_stopping=True, n_iter_no_change=8, random_state=1781120075))),
    ]
    for name, family, model in methods:
        print("fitting {}".format(name))
        model.fit(x_tab[train_mask], y[train_mask])
        score = model.decision_function(x_tab[test_mask]) if hasattr(model, "decision_function") else model.predict_proba(x_tab[test_mask])[:, 1]
        pred.append(pd.DataFrame({"method": name, "family": family, "run": runs[test_mask], "y_true": y[test_mask], "score": np.asarray(score, dtype=float)}))

    tab_scaled = StandardScaler().fit_transform(x_tab).astype(np.float32)
    for name, family, model, seed in [
        ("1d_cnn", "nn", BASE.TinyCNN(), 1781120076),
        ("atom_gated_cnn_new", "new_architecture", BASE.AtomGatedCNN(tab_scaled.shape[1]), 1781120077),
    ]:
        print("fitting {}".format(name))
        fit = BASE.train_torch(model, bench_waves.astype(np.float32), tab_scaled, y, train_mask, cfg, seed)
        score = BASE.predict_torch(fit, bench_waves.astype(np.float32), tab_scaled, test_mask)
        pred.append(pd.DataFrame({"method": name, "family": family, "run": runs[test_mask], "y_true": y[test_mask], "score": score}))

    pred = pd.concat(pred, ignore_index=True)
    pred["score"] = pred.groupby("method")["score"].transform(finite_score)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    summary, per_run = summarize_methods(pred, int(cfg["benchmark"]["bootstrap_samples"]), rng)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)
    BASE.plot_summary(out_dir, summary)

    transfer_rows = summary[["method", "family", "roc_auc", "auc_ci_low", "auc_ci_high", "average_precision", "ap_ci_low", "ap_ci_high"]].copy()
    q = bench["q_template_rmse"].to_numpy(dtype=float)
    qthr = float(np.nanquantile(q[train_mask], float(cfg["benchmark"]["q_threshold_quantile"])))
    qdiag = pd.DataFrame([
        {"contrast": "target_rate_top_decile_q_minus_rest", "value": float(y[test_mask & (q > qthr)].mean() - y[test_mask & (q <= qthr)].mean()), "q_threshold": qthr},
        {"contrast": "mean_damage_top_decile_q_minus_rest", "value": float(damage[test_mask & (q > qthr)].mean() - damage[test_mask & (q <= qthr)].mean()), "q_threshold": qthr},
        {"contrast": "heldout_target_fraction", "value": float(y[test_mask].mean()), "q_threshold": qthr},
    ])
    transfer_rows.to_csv(out_dir / "transfer_summary.csv", index=False)
    qdiag.to_csv(out_dir / "qtemplate_transfer_diagnostics.csv", index=False)

    winner = summary.iloc[0].to_dict()
    best_traditional = summary[summary["family"].eq("traditional")].iloc[0].to_dict()
    verdict = "q_template_transfers_to_injected_support" if qdiag.loc[0, "value"] > 0 and summary.iloc[0]["roc_auc"] > 0.70 else "weak_or_no_q_template_transfer"
    result = {
        "study": cfg["study_id"],
        "ticket": cfg["ticket_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "reproduced": selected == expected and len(meta) == int(cfg["expected_q_rows"]),
        "winner": winner["method"],
        "winner_family": winner["family"],
        "winner_metrics": winner,
        "best_traditional": best_traditional,
        "models_benchmarked": summary["method"].tolist(),
        "new_architecture": "atom_gated_cnn_new and q_token_attention",
        "primary_metric": "ROC AUC for injected pile-up/dropout support target",
        "verdict": verdict,
        "reproduction": {"selected_pulses": selected, "expected_selected_pulses": expected, "delta": selected - expected, "q_rows_joined": int(len(meta))},
        "split": {"heldout_runs": sorted(int(r) for r in bench.loc[test_mask, "run"].unique()), "bootstrap_unit": "heldout_run", "bootstrap_samples": int(cfg["benchmark"]["bootstrap_samples"]), "train_rows": int(train_mask.sum()), "heldout_rows": int(test_mask.sum())},
        "target": {"name": "injected pile-up/dropout support damage", "threshold": threshold, "train_positive_fraction": float(y[train_mask].mean()), "heldout_positive_fraction": float(y[test_mask].mean()), "uses_s03_timing_tail": False},
        "traditional_smoothing_alpha": float(cfg["benchmark"]["atom_smoothing_alpha"]),
        "qtemplate_transfer_diagnostics": qdiag.to_dict(orient="records"),
        "next_tickets": [
            {
                "title": "S01i charge-depth truth transfer for q-template support atom",
                "body": "Repeat the S01h external-transfer panel on calibrated charge-depth or simulation-truth labels, keeping run-block bootstrap CIs and the same q-token/atom-gated architecture, to test whether the injected support-transfer winner generalizes beyond synthetic pile-up/dropout.",
            }
        ],
        "git_commit": BASE.git_commit(),
        "python": platform.python_version(),
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(BASE.json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, per_run, repro, transfer_rows, qdiag)
    BASE.write_manifest(out_dir, args.config, cfg)
    print(json.dumps({"done": True, "ticket": cfg["ticket_id"], "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
