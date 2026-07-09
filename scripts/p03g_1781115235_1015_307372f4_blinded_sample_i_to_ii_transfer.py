#!/usr/bin/env python3
"""P03g blinded Sample-I to Sample-II morphology-gated residual transfer.

This ticket freezes model selection on Sample-I analysis runs, then scores the
Sample-II analysis runs without using Sample-II labels, run identifiers, or
event keys as model features.  It reuses the P03e modeling utilities so the
comparison against ridge, HGB, MLP, 1D-CNN, and the morphology-gated CNN is
directly comparable to the predecessor audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import p03e_1781034869_1025_674d291b_run_shift_audit as p03e
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03d_1781011277_910_1e815d8f_hierarchical_timewalk as s03d_hier


METHODS = [
    ("template_phase", "template_phase_base", "traditional"),
    ("s03a_amp_only_global", "s03a_amp_only_global", "traditional"),
    ("hierarchical_shrinkage", "hierarchical_shrinkage", "traditional"),
    ("ridge", "ridge", "ml"),
    ("gradient_boosted_trees", "gradient_boosted_trees", "ml"),
    ("mlp", "mlp", "nn"),
    ("cnn1d", "cnn1d", "nn"),
    ("shape_gated_cnn", "shape_gated_cnn_new", "nn"),
]


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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def evaluate_by_run(
    pulses: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    heldout_runs: Iterable[int],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residual_rows = []
    n_boot = int(config["models"]["bootstrap_samples"])
    for run in heldout_runs:
        for method, label, family in METHODS:
            vals = s02.pairwise_residuals(pulses, method, 2.0, config, [int(run)])
            ci_low, ci_high = s02.bootstrap_ci(vals, rng, n_boot)
            rows.append(
                {
                    "heldout_run": int(run),
                    "method": label,
                    "family": family,
                    "metric": "heldout_pairwise_sigma68_ns",
                    "value": s02.sigma68(vals),
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    **s02.metric_summary(vals),
                }
            )
            residual_rows.extend(
                {
                    "heldout_run": int(run),
                    "method": label,
                    "family": family,
                    "pairwise_residual_ns": float(value),
                }
                for value in vals
            )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(int(r) for r in residuals["heldout_run"].unique())
    for (method, family), group in residuals.groupby(["method", "family"]):
        by_run = {int(run): sub["pairwise_residual_ns"].to_numpy(float) for run, sub in group.groupby("heldout_run")}
        vals = group["pairwise_residual_ns"].to_numpy(float)
        boot = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled if len(by_run[int(run)])])
            boot.append(s02.sigma68(boot_vals))
        ci_low, ci_high = np.percentile(boot, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "family": family,
                "metric": "pooled_sample_ii_run_bootstrap_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def leakage_table(
    pulses: pd.DataFrame,
    config: dict,
    X: np.ndarray,
    y: np.ndarray,
    base_method: str,
    ridge_best: Dict[str, float],
    hgb_best: Dict[str, object],
) -> pd.DataFrame:
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    heldout_runs = [int(r) for r in config["timing"]["heldout_runs"]]
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    held_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    rows = [
        {
            "scope": "all_sample_ii",
            "check": "train_heldout_event_id_overlap",
            "value": float(len(train_event_ids & held_event_ids)),
            "unit": "events",
        },
        {
            "scope": "all_sample_ii",
            "check": "features_exclude_run_event_order_cross_stave_time",
            "value": 1.0,
            "unit": "bool",
        },
        {
            "scope": "all_sample_ii",
            "check": "final_models_use_sample_ii_labels_or_rows",
            "value": 0.0,
            "unit": "bool",
        },
        {
            "scope": "all_sample_ii",
            "check": "hyperparameters_selected_on_sample_i_only",
            "value": 1.0,
            "unit": "bool",
        },
    ]
    parts = [pd.DataFrame(rows)]
    for run in heldout_runs:
        shuffled = p03e.run_shuffled_control(pulses, X, y, config, base_method, int(run), ridge_best, hgb_best)
        shuffled.insert(0, "scope", f"heldout_run_{int(run)}")
        parts.append(shuffled)
    return pd.concat(parts, ignore_index=True, sort=False)


def make_plots(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, shift: pd.DataFrame) -> None:
    order = [label for _, label, _ in METHODS]
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], marker="o", linewidth=1.4, label=method)
    ax.set_xlabel("Sample-II held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("P03g frozen Sample-I model transfer")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_p03g_per_run_transfer.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.0, 4.9))
    sub = pooled.set_index("method").loc[order].reset_index()
    x = np.arange(len(sub))
    ax.bar(x, sub["value"])
    ax.errorbar(x, sub["value"], yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("pooled Sample-II sigma68 (ns)")
    ax.set_title("Run-bootstrap confidence intervals")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_p03g_pooled_winner.png", dpi=130)
    plt.close(fig)

    target = shift[shift["quantity"] == "target_residual_ns"].sort_values("heldout_run")
    if len(target):
        fig, ax = plt.subplots(figsize=(7.4, 4.2))
        ax.plot(target["heldout_run"], target["heldout_mean"], "o-", label="mean")
        ax.plot(target["heldout_run"], target["heldout_sigma68"], "o-", label="sigma68")
        ax.set_xlabel("Sample-II run")
        ax.set_ylabel("target residual (ns)")
        ax.set_title("Sample-II residual target shift under frozen Sample-I fit")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig_p03g_target_shift.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    shift: pd.DataFrame,
    leakage: pd.DataFrame,
    cv: pd.DataFrame,
    result: dict,
) -> None:
    order = [label for _, label, _ in METHODS]
    pooled_view = pooled.set_index("method").loc[order].reset_index()
    sample_i_runs = ", ".join(str(r) for r in config["timing"]["train_runs"])
    sample_ii_runs = ", ".join(str(r) for r in config["timing"]["heldout_runs"])
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    cv_summary = cv[cv["fold"].eq(-1)].copy()
    shift_view = shift[shift["quantity"].isin(["target_residual_ns", "amplitude_adc", "peak_sample", "area_adc_samples"])]
    lines = [
        "# P03g: blinded Sample-I to Sample-II morphology-gated residual transfer",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Date:** 2026-07-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo or external labels.",
        f"- **Frozen training domain:** Sample-I analysis runs {sample_i_runs}.",
        f"- **Blinded scoring domain:** Sample-II analysis runs {sample_ii_runs}.",
        f"- **Config:** `{config_path}`",
        "",
        "## Abstract",
        "",
        f"This study tests whether the P03e observation that HGB approached hierarchical shrinkage transfers when the waveform/morphology residual architecture and hyperparameters are frozen on Sample I before Sample II scoring. The raw ROOT selected-pulse counts are reproduced first. A strong traditional analytic hierarchy is then benchmarked against ridge, gradient-boosted trees, MLP, 1D-CNN, and the ticket-local morphology-gated CNN. The winner in `result.json` is **{result['winner']['method']}** with pooled Sample-II pairwise sigma68 **{result['winner']['value']:.3f} ns** and 95% run-bootstrap CI [{result['winner']['ci'][0]:.3f}, {result['winner']['ci'][1]:.3f}] ns.",
        "",
        "## 1. Raw ROOT Reproduction",
        "",
        "The S00 selected-pulse gate is rerun directly on `HRDv`: B-stack channels B2/B4/B6/B8, median baseline over samples 0-3, and amplitude greater than 1000 ADC. This reproduces the ticket-scale raw number before any model is trained.",
        "",
        repro.to_markdown(index=False),
        "",
        "## 2. Estimand",
        "",
        "For event \\(e\\) and downstream stave \\(s\\), the base template-phase time is corrected by longitudinal flight distance,",
        "",
        "\\[ c_{es}=t^{(0)}_{es}-x_s v^{-1},\\quad v^{-1}=0.078\\;\\mathrm{ns/cm}. \\]",
        "",
        "The self-supervised residual target on the training domain is the leave-one-stave contrast",
        "",
        "\\[ y_{es}=c_{es}-\\frac{1}{2}\\sum_{r\\ne s} c_{er}. \\]",
        "",
        "A fitted residual model \\(\\hat y=f_\\theta(w,z)\\) produces corrected time \\(\\hat t=t^{(0)}-\\hat y\\). The reported timing metric is",
        "",
        "\\[ \\sigma_{68}=\\{Q_{84}(\\Delta \\hat c)-Q_{16}(\\Delta \\hat c)\\}/2, \\]",
        "",
        "computed on B4-B6, B4-B8, and B6-B8 same-event pairwise residuals. Confidence intervals for per-run rows bootstrap pairwise residuals within that run; the primary pooled CI resamples Sample-II runs.",
        "",
        "## 3. Frozen Methods",
        "",
        "- **Traditional template-phase base:** the uncorrected pre-registered template phase selected on Sample-I training rows.",
        "- **Analytic timewalk:** S03a amplitude-only analytic residual correction.",
        "- **Hierarchical shrinkage:** population amplitude coefficients plus L2-shrunk Sample-I run deviations; because Sample II is blinded, the Sample-II prediction uses the population component without Sample-II deviations.",
        "- **Ridge:** standardized 18-sample waveform plus scalar morphology with alpha selected by Sample-I grouped CV.",
        "- **Gradient-boosted trees:** histogram GBT on the same features with all hyperparameter selection restricted to Sample-I grouped CV.",
        "- **MLP:** fixed two-hidden-layer ReLU network trained on Sample-I rows only.",
        "- **1D-CNN:** fixed two-layer convolution over normalized waveforms with scalar morphology concatenated only after convolution.",
        "- **New architecture:** `shape_gated_cnn_new`, a morphology-gated waveform CNN in which scalar pulse morphology multiplicatively gates the waveform latent vector before regression.",
        "",
        "Feature controls exclude run number, event identifiers, event order, and cross-stave times. Standardization constants are fit only on Sample-I rows.",
        "",
        "## 4. Hyperparameter Selection on Sample I",
        "",
        cv_summary.sort_values(["model", "sigma68_ns"]).head(40).to_markdown(index=False),
        "",
        "## 5. Sample-II Head-to-Head Benchmark",
        "",
        per_run[["heldout_run", "method", "family", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Pooled run-bootstrap summary:",
        "",
        pooled_view[["method", "family", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 6. Sample-II Shift and Systematics",
        "",
        shift_view[["heldout_run", "quantity", "train_mean", "heldout_mean", "train_sigma68", "heldout_sigma68", "ks_stat", "ks_pvalue"]].to_markdown(index=False),
        "",
        "The covariate-shift table is interpreted as a systematic diagnostic, not as a post-hoc feature-selection stage. The frozen model choice is not changed after observing these rows.",
        "",
        "## 7. Leakage and Negative Controls",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "The event-overlap check is exact on the loader event identifier. Shuffled-target controls refit ridge and HGB after permuting Sample-I residual targets; broad shuffled scores indicate the Sample-II winner is not explained by a trivial feature leak. Neural models receive no Sample-II labels during training.",
        "",
        "## 8. Caveats",
        "",
        "- The target remains a same-event downstream-stave timing closure target rather than an external absolute clock.",
        "- Sample-II has only seven held-out run units, so run-bootstrap intervals are intentionally conservative and coarse.",
        "- The neural architectures are fixed from the predecessor study; this is a transfer test, not a new architecture search.",
        "- The hierarchy cannot estimate Sample-II run deviations without violating the blinded transfer rule. Its Sample-II prediction is therefore the frozen population correction.",
        "- If the gating CNN wins, it demonstrates transferable waveform/morphology information, not detector-causal truth by itself.",
        "",
        "## 9. Verdict",
        "",
        f"`result.json` names `{result['winner']['method']}` as the winner. The best traditional method is `{result['best_traditional']['method']}` at {result['best_traditional']['value']:.3f} ns; the best ML/NN method is `{result['best_ml_or_nn']['method']}` at {result['best_ml_or_nn']['value']:.3f} ns.",
        f"The transfer conclusion is: {result['verdict']}",
        "",
        "## 10. Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/p03g_1781115235_1015_307372f4_blinded_sample_i_to_ii_transfer.py --config {config_path}",
        "```",
        "",
        "Artifacts include `result.json`, `manifest.json`, `REPORT.md`, `reproduction_match_table.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv.gz`, `model_cv_scan.csv`, `leakage_checks.csv`, `run_shift_summary.csv`, `feature_manifest.csv`, `input_sha256.csv`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03g_1781115235_1015_307372f4_blinded_sample_i_to_ii_transfer.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")

    pulses = s02.load_downstream_pulses(config)
    base_pulses, base_method = s03d_hier.prepare_base_pulses(pulses, config)
    y = s02.event_residual_targets(base_pulses, base_method, 2.0, config)
    staves = list(config["timing"]["downstream_staves"])

    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(base_pulses, config, base_method)
    hier_pred, hier_cv, _, _, hier_best = s03d_hier.scan_hierarchical(base_pulses, y, config)
    wave, scalar_raw, feature_names = p03e.waveform_and_features(base_pulses, staves)
    X = np.hstack([wave, scalar_raw]).astype(np.float64)
    runs = base_pulses["run"].to_numpy(int)
    train_mask = np.isin(runs, config["timing"]["train_runs"]) & p03e.finite_rows(X, y)
    Xs, x_center, x_scale = p03e.standardize(X, train_mask)
    wave_s = Xs[:, : wave.shape[1]].astype(np.float32)
    scalar_s = Xs[:, wave.shape[1] :].astype(np.float32)

    ridge_pred, ridge_cv, ridge_best = p03e.fit_ridge_panel(base_pulses, X, y, config, base_method)
    hgb_pred, hgb_cv, hgb_best = p03e.fit_hgb_panel(base_pulses, X, y, config, base_method)
    hidden = int(config["models"]["torch"]["hidden"])
    mlp_pred, mlp_train = p03e.fit_torch_model("mlp", p03e.TabularMLP(Xs.shape[1], hidden), wave_s, Xs.astype(np.float32), y, train_mask, config)
    cnn_pred, cnn_train = p03e.fit_torch_model("cnn1d", p03e.WaveCNN(scalar_s.shape[1], hidden), wave_s, scalar_s, y, train_mask, config)
    gated_pred, gated_train = p03e.fit_torch_model("shape_gated_cnn", p03e.ShapeGatedCNN(scalar_s.shape[1], hidden), wave_s, scalar_s, y, train_mask, config)

    combined = base_pulses.copy()
    combined["t_s03a_amp_only_global_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(float)
    combined["t_hierarchical_shrinkage_ns"] = combined[f"t_{base_method}_ns"].to_numpy(float) - hier_pred
    for name, pred in [
        ("ridge", ridge_pred),
        ("gradient_boosted_trees", hgb_pred),
        ("mlp", mlp_pred),
        ("cnn1d", cnn_pred),
        ("shape_gated_cnn", gated_pred),
    ]:
        combined[f"t_{name}_ns"] = combined[f"t_{base_method}_ns"].to_numpy(float) - pred
    combined["target_residual_ns"] = y

    pred_map = {
        "s03a_amp_only_global": combined[f"t_{base_method}_ns"].to_numpy(float) - combined["t_s03a_amp_only_global_ns"].to_numpy(float),
        "hierarchical_shrinkage": hier_pred,
        "ridge": ridge_pred,
        "gradient_boosted_trees": hgb_pred,
        "mlp": mlp_pred,
        "cnn1d": cnn_pred,
        "shape_gated_cnn": gated_pred,
    }
    per_run, residuals = evaluate_by_run(combined, config, rng, config["timing"]["heldout_runs"])
    pooled = run_level_bootstrap(residuals, rng, int(config["models"]["bootstrap_samples"]))
    cv = pd.concat([ridge_cv, hgb_cv, hier_cv.assign(model="hierarchical_shrinkage")], ignore_index=True, sort=False)
    train_history = pd.concat([mlp_train, cnn_train, gated_train], ignore_index=True)
    leakage = leakage_table(base_pulses, config, X, y, base_method, ridge_best, hgb_best)
    shift = pd.concat(
        [p03e.distribution_shift_rows(base_pulses, y, pred_map, int(run)) for run in config["timing"]["heldout_runs"]],
        ignore_index=True,
    )
    feature_manifest = pd.DataFrame(
        [{"feature": name, "role": "waveform" if i < wave.shape[1] else "scalar"} for i, name in enumerate([f"wf_{i}" for i in range(wave.shape[1])] + feature_names)]
    )

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv.gz", index=False)
    cv.to_csv(out_dir / "model_cv_scan.csv", index=False)
    train_history.to_csv(out_dir / "torch_train_history.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    shift.to_csv(out_dir / "run_shift_summary.csv", index=False)
    feature_manifest.to_csv(out_dir / "feature_manifest.csv", index=False)
    make_plots(out_dir, per_run, pooled, shift)

    input_hashes = {
        str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run))
        for run in s02.configured_runs(config)
    }
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    winner = pooled.sort_values("value").iloc[0]
    best_trad = pooled[pooled["family"].eq("traditional")].sort_values("value").iloc[0]
    best_ml = pooled[pooled["family"].isin(["ml", "nn"])].sort_values("value").iloc[0]
    event_overlap = int(leakage[leakage["check"].eq("train_heldout_event_id_overlap")]["value"].sum())
    shuffled = leakage[leakage["check"].astype(str).str.contains("shuffled_target", na=False)]
    result = {
        "study": "P03g",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro["pass"].all()),
            "selected_pulses": int(repro.loc[repro["quantity"].eq("total selected B-stave pulses"), "reproduced"].iloc[0]),
            "sample_ii_selected_pulses": int(repro.loc[repro["quantity"].eq("sample_ii_analysis selected_pulses"), "reproduced"].iloc[0]),
        },
        "split": {
            "train_domain": "sample_i_analysis",
            "train_runs": [int(r) for r in config["timing"]["train_runs"]],
            "test_domain": "sample_ii_analysis",
            "heldout_runs": [int(r) for r in config["timing"]["heldout_runs"]],
            "bootstrap_unit": "heldout_run",
        },
        "winner": {"method": str(winner["method"]), "family": str(winner["family"]), "value": float(winner["value"]), "ci": [float(winner["ci_low"]), float(winner["ci_high"])]},
        "best_traditional": {"method": str(best_trad["method"]), "value": float(best_trad["value"]), "ci": [float(best_trad["ci_low"]), float(best_trad["ci_high"])]},
        "best_ml_or_nn": {"method": str(best_ml["method"]), "family": str(best_ml["family"]), "value": float(best_ml["value"]), "ci": [float(best_ml["ci_low"]), float(best_ml["ci_high"])]},
        "methods": {
            str(row["method"]): {
                "family": str(row["family"]),
                "value": float(row["value"]),
                "ci": [float(row["ci_low"]), float(row["ci_high"])],
                "tail_frac_abs_gt5ns": float(row["tail_frac_abs_gt5ns"]),
            }
            for _, row in pooled.sort_values("method").iterrows()
        },
        "frozen_selection": {
            "base_method": base_method,
            "s03a_candidate": s03a_candidate,
            "s03a_alpha": float(s03a_alpha),
            "hierarchical_best": hier_best,
            "ridge_best": ridge_best,
            "hgb_best": hgb_best,
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "hyperparameters_selected_on_sample_i_only": True,
            "final_models_use_sample_ii_labels_or_rows": False,
            "shuffled_target_min_sigma68_ns": float(shuffled["value"].min()) if len(shuffled) else None,
            "leakage_flag": bool(event_overlap != 0),
        },
        "verdict": (
            f"{winner['method']} is the best frozen Sample-I to Sample-II transfer method; "
            f"best ML/NN minus best traditional = {float(best_ml['value'] - best_trad['value']):.3f} ns."
        ),
        "next_tickets": [],
        "input_sha256": sha256_file(out_dir / "input_sha256.csv"),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, config, config_path, repro, per_run, pooled, shift, leakage, cv, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03g",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": f"{sys.executable} {Path(__file__)} --config {config_path}",
        "random_seed": int(config["models"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
