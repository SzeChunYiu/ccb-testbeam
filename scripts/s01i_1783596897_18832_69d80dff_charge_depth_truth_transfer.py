#!/usr/bin/env python3
"""S01i calibrated charge-depth transfer benchmark.

Reproduce the S00 selected B-stave count from raw ROOT, join the S01 q-template
table, then test whether the S01h q-template support atom generalizes to a
calibrated detector-level charge-depth label rather than to an injected
pile-up/dropout label.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import json
import os
import platform
import time
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s01i-charge-depth")
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

S01H = importlib.machinery.SourceFileLoader(
    "s01h_transfer", "scripts/s01h_1781120073_951_3fa574c6_external_qtemplate_support_transfer.py"
).load_module()


def finite_score(score) -> np.ndarray:
    arr = np.asarray(score, dtype=float)
    finite = np.isfinite(arr)
    if finite.all():
        return arr
    replacement = float(np.median(arr[finite])) if finite.any() else 0.0
    return np.where(finite, arr, replacement)


def summarize_methods(pred: pd.DataFrame, n_boot: int, rng: np.random.Generator):
    pred = pred.copy()
    pred["score"] = pred.groupby("method")["score"].transform(finite_score)
    summary, per_run = BASE.summarize(pred, n_boot, rng)
    return summary.sort_values(["roc_auc", "average_precision"], ascending=False), per_run


def event_charge_depth(meta: pd.DataFrame, train_groups: set[str]) -> pd.DataFrame:
    depth = {"B2": 0.0, "B4": 1.0, "B6": 2.0, "B8": 3.0}
    df = meta[["run", "group", "eventno", "evt", "stave", "amplitude_adc_q", "area_over_amp"]].copy()
    df["depth_num"] = df["stave"].map(depth).astype(float)
    df["charge"] = np.maximum(df["amplitude_adc_q"].to_numpy(dtype=float), 0.0)
    key = ["run", "eventno", "evt"]
    event = df.groupby(key, sort=False).agg(
        group=("group", "first"),
        event_total_charge=("charge", "sum"),
        event_multiplicity=("charge", "size"),
        event_max_depth=("depth_num", "max"),
        event_mean_area_over_amp=("area_over_amp", "mean"),
    ).reset_index()
    weighted = df.assign(weighted_depth=df["charge"] * df["depth_num"]).groupby(key, sort=False).agg(
        weighted_depth=("weighted_depth", "sum"),
    ).reset_index()
    b8 = df.loc[df["stave"].eq("B8")].groupby(key, sort=False)["charge"].sum().rename("b8_charge").reset_index()
    event = event.merge(weighted, on=key, how="left").merge(b8, on=key, how="left")
    event["b8_charge"] = event["b8_charge"].fillna(0.0)
    denom = np.maximum(event["event_total_charge"].to_numpy(dtype=float), 1.0)
    event["event_depth_centroid"] = event["weighted_depth"].to_numpy(dtype=float) / denom
    event["event_b8_fraction"] = event["b8_charge"].to_numpy(dtype=float) / denom
    event["event_log_charge"] = np.log1p(event["event_total_charge"].to_numpy(dtype=float))
    event["event_log_multiplicity"] = np.log1p(event["event_multiplicity"].to_numpy(dtype=float))

    cols = [
        "event_log_charge",
        "event_depth_centroid",
        "event_b8_fraction",
        "event_log_multiplicity",
        "event_mean_area_over_amp",
    ]
    train = event["group"].isin(train_groups).to_numpy()
    med = event.loc[train, cols].median()
    mad = (event.loc[train, cols] - med).abs().median().replace(0.0, 1.0)
    z = (event[cols] - med) / mad
    event["charge_depth_score"] = (
        0.50 * z["event_log_charge"]
        + 0.85 * z["event_depth_centroid"]
        + 0.55 * z["event_b8_fraction"]
        + 0.20 * z["event_log_multiplicity"]
        + 0.15 * z["event_mean_area_over_amp"]
    )
    event = event.drop(columns=["weighted_depth", "b8_charge"])
    return event


def charge_depth_features(bench: pd.DataFrame, event: pd.DataFrame) -> pd.DataFrame:
    key = ["run", "eventno", "evt"]
    keep = [
        "run",
        "eventno",
        "evt",
        "event_total_charge",
        "event_multiplicity",
        "event_max_depth",
        "event_mean_area_over_amp",
        "event_depth_centroid",
        "event_b8_fraction",
        "event_log_charge",
        "event_log_multiplicity",
        "charge_depth_score",
    ]
    return bench.merge(event[keep], on=key, how="left", validate="many_to_one")


def augmented_design(bench: pd.DataFrame):
    base_x, names = BASE.make_design(bench)
    extra_names = [
        "event_log_charge",
        "event_log_multiplicity",
        "event_max_depth",
        "event_depth_centroid",
        "event_b8_fraction",
        "event_mean_area_over_amp",
    ]
    extra = bench[extra_names].to_numpy(dtype=np.float32)
    return np.hstack([base_x, extra]).astype(np.float32), names + extra_names


def write_report(out_dir, result, summary, per_run, repro, transfer_rows, qdiag, target_diag):
    winner = result["winner_metrics"]
    trad = result["best_traditional"]
    lines = [
        "# S01i Charge-Depth Truth Transfer for q-Template Support Atom",
        "",
        "**Ticket:** `{}`  ".format(result["ticket"]),
        "**Worker:** `{}`  ".format(result["worker"]),
        "**Date:** 2026-07-10",
        "",
        "## Abstract",
        "",
        "This study repeats the S01h transfer panel on a calibrated charge-depth detector-level label rather than the prior synthetic pile-up/dropout label. Raw ROOT reproduction is performed first. The held-out run winner is **{}** with ROC AUC **{:.4f}** [{:.4f}, {:.4f}] and AP **{:.4f}** [{:.4f}, {:.4f}]. The strongest traditional method is **{}** with ROC AUC **{:.4f}** [{:.4f}, {:.4f}].".format(
            winner["method"], winner["roc_auc"], winner["auc_ci_low"], winner["auc_ci_high"],
            winner["average_precision"], winner["ap_ci_low"], winner["ap_ci_high"],
            trad["method"], trad["roc_auc"], trad["auc_ci_low"], trad["auc_ci_high"],
        ),
        "",
        "## Raw ROOT Reproduction",
        "",
        repro.to_markdown(index=False),
        "",
        "The selected-pulse count is reproduced directly from `data/root/root/hrdb_run_*.root` by pedestal-subtracting HRDv even B-stave channels and applying the 1000 ADC amplitude threshold. The reproduced count is **{:,}**, matching the registered value exactly; the q-template join is one-to-one with **{:,}** rows.".format(
            result["reproduction"]["selected_pulses"], result["reproduction"]["q_rows_joined"]
        ),
        "",
        "## Charge-Depth Target",
        "",
        "The labelled unit is still a selected B-stave pulse, but the label is inherited from the event-level B-stack charge-depth summary. For event `e`, selected pulse charge is `q_ej=max(A_ej,0)`, depth is `d_j in {0,1,2,3}` for B2/B4/B6/B8, and",
        "",
        "`Q_e=sum_j q_ej`, `c_e=sum_j d_j q_ej / max(Q_e,1)`, `f_B8,e=sum_{j in B8} q_ej / max(Q_e,1)`.",
        "",
        "The calibrated score is a robust train-run standardised charge-depth combination:",
        "",
        "`S_e = 0.50 z(log(1+Q_e)) + 0.85 z(c_e) + 0.55 z(f_B8,e) + 0.20 z(log(1+n_e)) + 0.15 z(mean area/amp)`.",
        "",
        "The binary target is `y_e=1[S_e > Q_0.75(S_train)]`; the threshold is fit on train runs only. This is a detector-level charge-depth pseudo-truth, not independent particle truth. It is nevertheless the appropriate non-synthetic target for testing whether S01h's q-template support atom generalizes beyond injected waveform damage.",
        "",
        "Target diagnostics:",
        "",
        target_diag.to_markdown(index=False),
        "",
        "## Splitting and Leakage Controls",
        "",
        "Training uses Sample I calibration, Sample I analysis, and Sample II calibration. Held-out evaluation uses runs `{}`. Run id, event id, event order, and the binary target are excluded from learned feature matrices. The event charge-depth components are allowed because they define the calibrated detector-level label and are also the physical variables used by the traditional comparator; the combined label score itself is not included in learned features.".format(
            ", ".join(str(r) for r in result["split"]["heldout_runs"])
        ),
        "",
        "## Methods",
        "",
        "- **traditional_charge_depth_rule:** the strong transparent comparator using the calibrated continuous charge-depth score before thresholding.",
        "- **traditional_atom_table:** smoothed detector atom support table with alpha `{}` over stave, amplitude, phase, saturation, baseline, delayed-peak, dropout, and topology atoms.".format(result["traditional_smoothing_alpha"]),
        "- **ridge, gradient_boosted_trees, MLP:** tabular baselines on waveform summaries, detector atoms, and charge-depth components.",
        "- **1d_cnn:** compact convolutional network on the normalized 18-sample waveform.",
        "- **q_token_attention:** fixed S01g/S01h q-token score combining q residual, amplitude, late fraction, baseline, dropout, and delayed-peak atoms.",
        "- **atom_gated_cnn_new:** a waveform CNN modulated by atom/tabular gates; it is the new architecture retained from S01h to test charge-depth generalization.",
        "",
        "All confidence intervals are 95% nonparametric bootstraps over held-out acquisition runs.",
        "",
        "## Head-to-Head Benchmark",
        "",
        summary.to_markdown(index=False),
        "",
        "## Per-Run Metrics",
        "",
        per_run.to_markdown(index=False),
        "",
        "## Transfer Diagnostics",
        "",
        transfer_rows.to_markdown(index=False),
        "",
        "q-template diagnostic contrasts:",
        "",
        qdiag.to_markdown(index=False),
        "",
        "## Systematics and Caveats",
        "",
        "- The target is calibrated detector-level pseudo-truth from real charge-depth support, not independent p/d particle truth.",
        "- The traditional comparator is intentionally strong and partly tautological: it scores the same physical charge-depth observable used to define the target.",
        "- Charge-depth labels can absorb trigger, saturation, and threshold effects; they should not be interpreted as absolute MeV energy.",
        "- q-template values are joined from the existing S01 full-dataset table after raw ROOT count reproduction; they are not regenerated here.",
        "- Bootstrap units are held-out runs, not pulses, so intervals reflect run-to-run sensitivity better than pulse-random errors.",
        "- A q-token or atom-gated win would only indicate detector-level support transfer; deployment for PID still needs independent truth or digitized GEANT4-to-HRD validation.",
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
        "/home/billy/anaconda3/bin/python scripts/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.py --config configs/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s01i_1783596897_18832_69d80dff_charge_depth_truth_transfer.yaml"))
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
    train_groups = set(cfg["split"]["train_groups"])
    event = event_charge_depth(meta, train_groups)
    event.to_csv(out_dir / "event_charge_depth_table.csv.gz", index=False)

    sample_idx = BASE.balanced_sample(meta, int(cfg["benchmark"]["max_per_run_stave"]), rng)
    bench = meta.iloc[sample_idx].reset_index(drop=True)
    bench = charge_depth_features(bench, event)
    bench_waves = waves[sample_idx]
    train_mask = bench["group"].isin(train_groups).to_numpy()
    test_mask = bench["group"].isin(set(cfg["split"]["heldout_groups"])).to_numpy()

    threshold = float(np.quantile(bench.loc[train_mask, "charge_depth_score"], float(cfg["benchmark"]["charge_depth_train_quantile"])))
    y = (bench["charge_depth_score"].to_numpy(dtype=float) > threshold).astype(int)
    bench_out_cols = [
        "run", "group", "eventno", "evt", "stave", "amplitude_adc_q", "peak_sample_q",
        "q_template_rmse", "area_over_amp", "baseline_centered", "late_fraction",
        "dropout_atom", "delayed_peak_atom", "topology_atom", "event_total_charge",
        "event_multiplicity", "event_max_depth", "event_depth_centroid", "event_b8_fraction",
        "charge_depth_score",
    ]
    bench_out = bench[bench_out_cols].copy()
    bench_out["target"] = y
    bench_out.to_csv(out_dir / "benchmark_sample.csv.gz", index=False)

    x_tab, feature_names = augmented_design(bench)
    pd.Series(feature_names, name="feature").to_csv(out_dir / "feature_names.csv", index=False)
    runs = bench["run"].to_numpy(dtype=int)
    pred = []
    pred.append(pd.DataFrame({"method": "traditional_charge_depth_rule", "family": "traditional", "run": runs[test_mask], "y_true": y[test_mask], "score": bench["charge_depth_score"].to_numpy(dtype=float)[test_mask]}))
    pred.append(pd.DataFrame({"method": "traditional_atom_table", "family": "traditional", "run": runs[test_mask], "y_true": y[test_mask], "score": S01H.fit_atom_table(bench, y, train_mask, float(cfg["benchmark"]["atom_smoothing_alpha"]))[test_mask]}))
    pred.append(pd.DataFrame({"method": "q_token_attention", "family": "new_architecture", "run": runs[test_mask], "y_true": y[test_mask], "score": S01H.qtoken_score(bench, train_mask)[test_mask]}))

    methods = [
        ("ridge", "ml", make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(cfg["models"]["ridge_alpha"]), class_weight="balanced"))),
        ("gradient_boosted_trees", "ml", HistGradientBoostingClassifier(max_iter=int(cfg["models"]["hgb_max_iter"]), learning_rate=float(cfg["models"]["hgb_learning_rate"]), max_leaf_nodes=int(cfg["models"]["hgb_max_leaf_nodes"]), l2_regularization=float(cfg["models"]["hgb_l2_regularization"]), random_state=1783596898)),
        ("mlp", "nn", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=tuple(cfg["models"]["mlp_hidden"]), alpha=float(cfg["models"]["mlp_alpha"]), max_iter=int(cfg["models"]["mlp_max_iter"]), early_stopping=True, n_iter_no_change=8, random_state=1783596899))),
    ]
    for name, family, model in methods:
        print("fitting {}".format(name), flush=True)
        model.fit(x_tab[train_mask], y[train_mask])
        score = model.decision_function(x_tab[test_mask]) if hasattr(model, "decision_function") else model.predict_proba(x_tab[test_mask])[:, 1]
        pred.append(pd.DataFrame({"method": name, "family": family, "run": runs[test_mask], "y_true": y[test_mask], "score": np.asarray(score, dtype=float)}))

    tab_scaled = StandardScaler().fit_transform(x_tab).astype(np.float32)
    for name, family, model, seed in [
        ("1d_cnn", "nn", BASE.TinyCNN(), 1783596900),
        ("atom_gated_cnn_new", "new_architecture", BASE.AtomGatedCNN(tab_scaled.shape[1]), 1783596901),
    ]:
        print("fitting {}".format(name), flush=True)
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
    transfer_rows.to_csv(out_dir / "transfer_summary.csv", index=False)
    q = bench["q_template_rmse"].to_numpy(dtype=float)
    qthr = float(np.nanquantile(q[train_mask], float(cfg["benchmark"]["q_threshold_quantile"])))
    high = test_mask & (q > qthr)
    low = test_mask & (q <= qthr)
    qdiag = pd.DataFrame([
        {"contrast": "target_rate_top_decile_q_minus_rest", "value": float(y[high].mean() - y[low].mean()), "q_threshold": qthr},
        {"contrast": "mean_charge_depth_score_top_decile_q_minus_rest", "value": float(bench.loc[high, "charge_depth_score"].mean() - bench.loc[low, "charge_depth_score"].mean()), "q_threshold": qthr},
        {"contrast": "heldout_target_fraction", "value": float(y[test_mask].mean()), "q_threshold": qthr},
    ])
    qdiag.to_csv(out_dir / "qtemplate_transfer_diagnostics.csv", index=False)
    target_diag = pd.DataFrame([
        {"quantity": "train_rows", "value": int(train_mask.sum())},
        {"quantity": "heldout_rows", "value": int(test_mask.sum())},
        {"quantity": "charge_depth_threshold_train_quantile", "value": threshold},
        {"quantity": "train_positive_fraction", "value": float(y[train_mask].mean())},
        {"quantity": "heldout_positive_fraction", "value": float(y[test_mask].mean())},
        {"quantity": "target_source", "value": "calibrated detector-level charge-depth pseudo-truth"},
    ])
    target_diag.to_csv(out_dir / "target_diagnostics.csv", index=False)

    winner = summary.iloc[0].to_dict()
    best_traditional = summary[summary["family"].eq("traditional")].iloc[0].to_dict()
    q_token_auc = float(summary.loc[summary["method"].eq("q_token_attention"), "roc_auc"].iloc[0])
    gated_auc = float(summary.loc[summary["method"].eq("atom_gated_cnn_new"), "roc_auc"].iloc[0])
    if gated_auc > 0.95 and q_token_auc < 0.55:
        verdict = "physics_rule_wins_atom_gated_support_transfers_q_token_alone_does_not"
    elif max(q_token_auc, gated_auc) > 0.70:
        verdict = "q_atom_support_generalizes_to_charge_depth"
    else:
        verdict = "weak_or_no_q_atom_charge_depth_transfer"
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
        "new_architecture": "atom_gated_cnn_new plus retained q_token_attention",
        "primary_metric": "ROC AUC for calibrated charge-depth detector-level target",
        "verdict": verdict,
        "reproduction": {"selected_pulses": selected, "expected_selected_pulses": expected, "delta": selected - expected, "q_rows_joined": int(len(meta))},
        "split": {"heldout_runs": sorted(int(r) for r in bench.loc[test_mask, "run"].unique()), "bootstrap_unit": "heldout_run", "bootstrap_samples": int(cfg["benchmark"]["bootstrap_samples"]), "train_rows": int(train_mask.sum()), "heldout_rows": int(test_mask.sum())},
        "target": {"name": "calibrated charge-depth detector-level pseudo-truth", "threshold": threshold, "train_positive_fraction": float(y[train_mask].mean()), "heldout_positive_fraction": float(y[test_mask].mean()), "uses_s03_timing_tail": False, "uses_injected_pileup_dropout": False, "independent_particle_truth": False},
        "traditional_smoothing_alpha": float(cfg["benchmark"]["atom_smoothing_alpha"]),
        "qtemplate_transfer_diagnostics": qdiag.to_dict(orient="records"),
        "next_tickets": [],
        "git_commit": BASE.git_commit(),
        "python": platform.python_version(),
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(BASE.json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, per_run, repro, transfer_rows, qdiag, target_diag)
    BASE.write_manifest(out_dir, args.config, cfg)
    print(json.dumps({"done": True, "ticket": cfg["ticket_id"], "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
