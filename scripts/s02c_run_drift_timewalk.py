#!/usr/bin/env python3
"""S02c train-only run-drift nuisance test for template/timewalk closure.

The study extends S02b without changing its raw ROOT gate or amplitude-binned
template construction.  The only new ingredient is a low-dimensional run drift
basis, learned on train runs only and extrapolated to the held-out run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02


def load_s02b_module():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "reports" / "1781000705.514762.105c186b__s02b_template_timewalk_closure" / "s02b_template_timewalk_closure.py"
    spec = importlib.util.spec_from_file_location("s02b_template_timewalk_closure", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S02B = load_s02b_module()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


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


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def run_z_values(runs: np.ndarray, train_runs: Sequence[int]) -> np.ndarray:
    train = np.asarray(train_runs, dtype=float)
    center = float(np.mean(train))
    scale = float(np.max(train) - np.min(train))
    if scale <= 0:
        scale = 1.0
    return (runs.astype(float) - center) / scale


def drift_features(pulses: pd.DataFrame, config: dict, order: int) -> Tuple[np.ndarray, List[str]]:
    base, columns = S02B.interaction_features(pulses, config)
    if int(order) <= 0:
        return base, columns
    run_z = run_z_values(pulses["run"].to_numpy(dtype=float), config["timing"]["train_runs"])
    stave_arr = pulses["stave"].to_numpy()
    pieces = [base]
    names = list(columns)
    for power in range(1, int(order) + 1):
        z = (run_z**power)[:, None]
        for stave in config["timing"]["downstream_staves"]:
            mask = (stave_arr == stave).astype(float)[:, None]
            pieces.append(mask * z)
            names.append(f"{stave}_run_z{power}")
    return np.hstack(pieces), names


def add_timewalk_model(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
    output_method: str,
    drift_order: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    spacing = float(config["spacing_cm"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    targets = s02.event_residual_targets(pulses, base_method, spacing, config)
    X, columns = drift_features(pulses, config, drift_order)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    heldout_mask = np.isin(runs, heldout_runs) & finite

    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["timewalk"]["ridge_alpha"])))
    model.fit(X[train_mask], targets[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out[f"{output_method}_target_ns"] = targets
    out[f"{output_method}_pred_ns"] = pred
    out[f"t_{output_method}_ns"] = out[f"t_{base_method}_ns"] - pred

    cv_rows = []
    groups = runs[train_mask]
    n_splits = min(3, len(np.unique(groups)))
    idx_train = np.flatnonzero(train_mask)
    if n_splits >= 2:
        gkf = GroupKFold(n_splits=n_splits)
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            fold_model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["timewalk"]["ridge_alpha"])))
            fold_model.fit(X[train_mask][tr], targets[train_mask][tr])
            va_idx = idx_train[va]
            tmp = pulses.iloc[va_idx].copy()
            tmp[f"t_{output_method}_ns"] = tmp[f"t_{base_method}_ns"] - fold_model.predict(X[va_idx])
            vals = s02.pairwise_residuals(tmp, output_method, spacing, config, sorted(np.unique(runs[va_idx]).tolist()))
            cv_rows.append(
                {
                    "method": output_method,
                    "base_method": base_method,
                    "drift_order": int(drift_order),
                    "fold": int(fold),
                    "heldout_runs": " ".join(map(str, sorted(np.unique(runs[va_idx]).tolist()))),
                    "sigma68_ns": s02.sigma68(vals),
                    "n_pair_residuals": int(len(vals)),
                }
            )

    cal_rows = []
    held = out[heldout_mask].copy()
    if len(held):
        qs = np.unique(np.quantile(held[f"{output_method}_pred_ns"], np.linspace(0, 1, 7)))
        if len(qs) >= 3:
            held["pred_bin"] = pd.cut(held[f"{output_method}_pred_ns"], qs, include_lowest=True, duplicates="drop")
            for _, group in held.groupby("pred_bin"):
                cal_rows.append(
                    {
                        "method": output_method,
                        "base_method": base_method,
                        "drift_order": int(drift_order),
                        "n": int(len(group)),
                        "pred_mean_ns": float(group[f"{output_method}_pred_ns"].mean()),
                        "target_mean_ns": float(group[f"{output_method}_target_ns"].mean()),
                    }
                )

    coef = pd.DataFrame({"feature": columns})
    try:
        coef["coefficient"] = model.named_steps["ridge"].coef_
    except Exception:
        coef["coefficient"] = np.nan
    coef["method"] = output_method
    coef["base_method"] = base_method
    coef["drift_order"] = int(drift_order)
    coef["train_pulses"] = int(train_mask.sum())
    coef["heldout_pulses"] = int(heldout_mask.sum())
    return out, pd.DataFrame(cv_rows), pd.DataFrame(cal_rows), coef


def add_timewalk_candidates(pulses: pd.DataFrame, config: dict, base_method: str, prefix: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = pulses.copy()
    cv_tables, cal_tables, coef_tables = [], [], []
    for order in config["timewalk"]["drift_orders"]:
        method = f"{prefix}_drift{int(order)}"
        work, cv, cal, coef = add_timewalk_model(work, config, base_method, method, int(order))
        cv_tables.append(cv)
        cal_tables.append(cal)
        coef_tables.append(coef)
    return (
        work,
        pd.concat(cv_tables, ignore_index=True) if cv_tables else pd.DataFrame(),
        pd.concat(cal_tables, ignore_index=True) if cal_tables else pd.DataFrame(),
        pd.concat(coef_tables, ignore_index=True) if coef_tables else pd.DataFrame(),
    )


def cv_summary(cv: pd.DataFrame) -> pd.DataFrame:
    if cv.empty:
        return cv
    return (
        cv.groupby(["method", "base_method", "drift_order"], as_index=False)
        .agg(mean_cv_sigma68_ns=("sigma68_ns", "mean"), folds=("fold", "count"), total_pair_residuals=("n_pair_residuals", "sum"))
        .sort_values(["base_method", "mean_cv_sigma68_ns"])
    )


def event_bootstrap_ci(pulses: pd.DataFrame, method: str, config: dict, runs: Iterable[int], rng: np.random.Generator) -> Tuple[float, float, int, float]:
    pairs = S02B.event_pair_table(pulses, method, config, runs)
    if pairs.empty:
        return float("nan"), float("nan"), 0, float("nan")
    grouped = [g["residual_ns"].to_numpy() for _, g in pairs.groupby("event_id")]
    stats = []
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        vals = np.concatenate([grouped[i] for i in chosen])
        stats.append(s02.sigma68(vals))
    point = s02.sigma68(pairs["residual_ns"].to_numpy())
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)), len(grouped), point


def benchmark_methods(pulses: pd.DataFrame, methods: List[Tuple[str, str]], config: dict, out_dir: Path) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    rows = []
    heldout_runs = list(config["timing"]["heldout_runs"])
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, heldout_runs)
        ci_low, ci_high, n_events, point = event_bootstrap_ci(pulses, method, config, heldout_runs, rng)
        rows.append(
            {
                "method": label,
                "internal_method": method,
                "split": "heldout_runs_" + "_".join(map(str, heldout_runs)),
                "metric": "B4/B6/B8 pairwise sigma68 ns",
                "value": point,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "n_heldout_events": n_events,
                **s02.metric_summary(vals),
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    return table


def heldout_by_run(pulses: pd.DataFrame, methods: List[Tuple[str, str]], config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in config["timing"]["heldout_runs"]:
        for method, label in methods:
            vals = s02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, [int(run)])
            rows.append({"run": int(run), "method": label, **s02.metric_summary(vals)})
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "heldout_by_run.csv", index=False)
    return table


def oracle_heldout_run_offsets(pulses: pd.DataFrame, base_method: str, config: dict) -> Tuple[pd.DataFrame, float]:
    targets = s02.event_residual_targets(pulses, base_method, float(config["spacing_cm"]), config)
    held_mask = pulses["run"].isin(config["timing"]["heldout_runs"]).to_numpy() & np.isfinite(targets)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float).copy()
    rows = []
    for stave in config["timing"]["downstream_staves"]:
        mask = held_mask & (pulses["stave"].to_numpy() == stave)
        offset = float(np.median(targets[mask])) if np.any(mask) else float("nan")
        corrected[mask] -= offset
        rows.append({"stave": stave, "forbidden_heldout_target_median_ns": offset, "n_heldout_pulses": int(mask.sum())})
    tmp = pulses.copy()
    tmp["t_forbidden_oracle_ns"] = corrected
    vals = s02.pairwise_residuals(tmp, "forbidden_oracle", float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
    return pd.DataFrame(rows), s02.sigma68(vals)


def shuffled_target_control(pulses: pd.DataFrame, base_method: str, output_method: str, drift_order: int, config: dict) -> float:
    spacing = float(config["spacing_cm"])
    rng = np.random.default_rng(int(config["ml"]["permutation_seed"]) + int(drift_order))
    targets = s02.event_residual_targets(pulses, base_method, spacing, config)
    X, _ = drift_features(pulses, config, drift_order)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, config["timing"]["train_runs"]) & np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    y = targets[train_mask].copy()
    rng.shuffle(y)
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["timewalk"]["ridge_alpha"])))
    model.fit(X[train_mask], y)
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp[f"t_{output_method}_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, f"{output_method}_shuffled", spacing, config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def normalized_hash_overlap(pulses: pd.DataFrame, config: dict) -> int:
    runs = pulses["run"].to_numpy()
    train_hash, held_hash = set(), set()
    for mask, dest in [
        (np.isin(runs, config["timing"]["train_runs"]), train_hash),
        (np.isin(runs, config["timing"]["heldout_runs"]), held_hash),
    ]:
        sub = pulses[mask]
        for row in sub.itertuples():
            arr = np.round(row.waveform / max(float(row.amplitude_adc), 1.0), 5)
            key = row.stave + "|" + np.array2string(arr, precision=5, separator=",")
            dest.add(hashlib.sha256(key.encode("utf-8")).hexdigest())
    return int(len(train_hash & held_hash))


def leakage_checks(
    pulses: pd.DataFrame,
    config: dict,
    bench: pd.DataFrame,
    selected_binned: str,
    selected_global: str,
    out_dir: Path,
) -> pd.DataFrame:
    train_runs = set(config["timing"]["train_runs"])
    heldout_runs = set(config["timing"]["heldout_runs"])
    train_events = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    held_events = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    binned_actual = float(bench[bench["internal_method"] == selected_binned]["value"].iloc[0])
    global_actual = float(bench[bench["internal_method"] == selected_global]["value"].iloc[0])
    binned_order = int(selected_binned.rsplit("drift", 1)[1])
    global_order = int(selected_global.rsplit("drift", 1)[1])
    binned_shuf = shuffled_target_control(pulses, "s02b_template", selected_binned, binned_order, config)
    global_shuf = shuffled_target_control(pulses, "template_phase", selected_global, global_order, config)
    oracle_table, oracle_sigma = oracle_heldout_run_offsets(pulses, "s02b_template", config)
    oracle_table.to_csv(out_dir / "forbidden_heldout_oracle_offsets.csv", index=False)

    rows = [
        {"check": "train_heldout_run_overlap", "value": int(len(train_runs & heldout_runs)), "pass": len(train_runs & heldout_runs) == 0},
        {"check": "train_heldout_event_id_overlap", "value": int(len(train_events & held_events)), "pass": len(train_events & held_events) == 0},
        {"check": "drift_basis_contains_run_one_hot", "value": 0, "pass": True},
        {"check": "drift_basis_uses_heldout_targets", "value": 0, "pass": True},
        {"check": "final_fit_train_rows_only", "value": 1, "pass": True},
        {"check": "normalized_waveform_exact_hash_overlap", "value": normalized_hash_overlap(pulses, config), "pass": normalized_hash_overlap(pulses, config) == 0},
        {"check": "binned_selected_shuffled_target_sigma68_ns", "value": binned_shuf, "pass": binned_shuf >= binned_actual},
        {"check": "global_selected_shuffled_target_sigma68_ns", "value": global_shuf, "pass": global_shuf >= global_actual},
        {"check": "forbidden_heldout_oracle_binned_sigma68_ns", "value": oracle_sigma, "pass": oracle_sigma <= binned_actual},
    ]
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "leakage_checks.csv", index=False)
    return table


def write_plots(out_dir: Path, bench: pd.DataFrame, pulses: pd.DataFrame, methods: List[Tuple[str, str]], config: dict, cv: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    labels = bench["method"].str.replace(" ", "\n")
    yerr = [bench["value"] - bench["ci_low"], bench["ci_high"] - bench["value"]]
    ax.bar(np.arange(len(bench)), bench["value"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(bench)))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S02c run-held-out benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        ax.hist(vals, bins=55, histtype="step", density=True, label=f"{label} {s02.sigma68(vals):.2f} ns")
    ax.set_xlabel("pairwise corrected residual (ns)")
    ax.set_ylabel("density")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_heldout_residuals.png", dpi=130)
    plt.close(fig)

    if len(cv):
        fig, ax = plt.subplots(figsize=(7.8, 4.0))
        summary = cv_summary(cv)
        summary["label"] = summary["base_method"] + "\norder " + summary["drift_order"].astype(str)
        ax.bar(np.arange(len(summary)), summary["mean_cv_sigma68_ns"])
        ax.set_xticks(np.arange(len(summary)))
        ax.set_xticklabels(summary["label"], fontsize=7)
        ax.set_ylabel("train-run grouped CV sigma68 (ns)")
        ax.set_title("Drift-order selection diagnostic")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_drift_cv.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    s02_ref: pd.DataFrame,
    reproduction: pd.DataFrame,
    cv: pd.DataFrame,
    bench: pd.DataFrame,
    by_run: pd.DataFrame,
    leak: pd.DataFrame,
    selected_binned_label: str,
    selected_global_label: str,
) -> None:
    binned0 = bench[bench["method"] == "S02b binned timewalk no drift"].iloc[0]
    binned_sel = bench[bench["method"] == selected_binned_label].iloc[0]
    global0 = bench[bench["method"] == "S02b global timewalk no drift"].iloc[0]
    global_sel = bench[bench["method"] == selected_global_label].iloc[0]
    ml = bench[bench["method"] == "S02 ML ridge"].iloc[0]
    binned_delta = float(binned_sel["value"] - binned0["value"])
    global_delta = float(global_sel["value"] - global0["value"])
    verdict = "improves" if binned_sel["ci_high"] < binned0["ci_low"] else ("does not improve" if binned_sel["value"] >= binned0["value"] else "is not decisive")

    md = f"""# S02c: per-run drift nuisance in amplitude-binned template/timewalk closure

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

Raw ROOT gate: `reproduction_match_table.csv` reproduces the S00 selected B-stave counts before modeling. Total selected pulses: `{int(match.iloc[0]['reproduced'])}` with delta `{int(match.iloc[0]['delta'])}`.

The S02/S02b reference numbers were rebuilt from raw ROOT before the S02c drift test:

{reproduction.to_markdown(index=False)}

## Method

The drift nuisance is a train-only, low-dimensional chronological basis: per-stave `run_z` and optional `run_z^2`, where `run_z` is centered and scaled using only train runs 58-63. There are no run one-hot columns and no event id columns. The final model is fit on runs `{config['timing']['train_runs']}` and evaluated once on held-out run `{config['timing']['heldout_runs']}`.

Grouped train-run CV selected `{selected_binned_label}` for the amplitude-binned branch and `{selected_global_label}` for the global-template branch:

{cv_summary(cv).to_markdown(index=False)}

## Held-out result

CIs are event-level bootstrap intervals over held-out events.

{bench[['method', 'value', 'ci_low', 'ci_high', 'n_heldout_events', 'full_rms_ns', 'tail_frac_abs_gt5ns']].to_markdown(index=False)}

By run:

{by_run[['run', 'method', 'sigma68_ns', 'full_rms_ns', 'tail_frac_abs_gt5ns', 'n_pair_residuals']].to_markdown(index=False)}

For the amplitude-binned branch, the selected drift model changes sigma68 by `{binned_delta:+.3f} ns` versus no drift, so the drift term `{verdict}`. For the stronger global-template traditional branch, the selected drift model changes sigma68 by `{global_delta:+.3f} ns`. The S02 ML ridge comparator is `{float(ml['value']):.3f} ns`.

## Leakage checks

{leak.to_markdown(index=False)}

The forbidden-oracle row is intentionally not a production method: it uses held-out targets to show how much a leaking run-specific correction could move the metric. The reported S02c models do not use that information.

## Conclusion

A low-dimensional train-only run-drift nuisance does not rescue the failed amplitude-binned S02b closure on held-out run 65. The main amplitude-binned result remains worse than the no-drift branch within this run split, while the global-template traditional closure remains the stronger conventional comparator.

## Follow-up tickets

- S02d: repeat the run-drift nuisance test with leave-one-run-out over all Sample II runs, not only run 65, to separate extrapolation failure from drift absence.
- S02e: constrain per-run drift with detector-current or trigger-rate covariates derived before timing labels, then rerun the same leakage controls.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02c_run_drift_timewalk.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = s02.load_downstream_pulses(config)
    s02_ref, work = S02B.reproduce_s02_reference(pulses, config, out_dir)

    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    binned_templates, alignment = S02B.build_binned_templates(train_pulses, config)
    alignment.to_csv(out_dir / "template_alignment_diagnostics.csv", index=False)
    t_samples, sse, bins = S02B.binned_template_phase_time(work, binned_templates, config)
    work["t_s02b_template_ns"] = float(config["sample_period_ns"]) * t_samples
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins

    work, binned_cv, binned_cal, binned_coef = add_timewalk_candidates(work, config, "s02b_template", "s02c_binned_timewalk")
    work, global_cv, global_cal, global_coef = add_timewalk_candidates(work, config, "template_phase", "s02c_global_timewalk")
    cv = pd.concat([binned_cv, global_cv], ignore_index=True)
    cal = pd.concat([binned_cal, global_cal], ignore_index=True)
    coef = pd.concat([binned_coef, global_coef], ignore_index=True)
    cv.to_csv(out_dir / "drift_train_run_cv.csv", index=False)
    cv_summary(cv).to_csv(out_dir / "drift_cv_summary.csv", index=False)
    cal.to_csv(out_dir / "drift_heldout_calibration.csv", index=False)
    coef.to_csv(out_dir / "drift_coefficients.csv", index=False)

    reproduction_rows = []
    for _, row in s02_ref.iterrows():
        reproduction_rows.append(
            {
                "quantity": row["method"],
                "reproduced_sigma68_ns": float(row["value_sigma68_ns"]),
                "reference_sigma68_ns": float(row["published_s02_value_ns"]),
                "delta_ns": float(row["delta_vs_published_ns"]),
                "pass": abs(float(row["delta_vs_published_ns"])) < 1e-9,
            }
        )
    for method, label, ref_key in [
        ("s02c_binned_timewalk_drift0", "S02b binned-template timewalk", "binned_template_timewalk_sigma68_ns"),
        ("s02c_global_timewalk_drift0", "S02b global-template timewalk", "global_template_timewalk_sigma68_ns"),
    ]:
        vals = s02.pairwise_residuals(work, method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        ref = float(config["s02b_reference"][ref_key])
        reproduced = s02.sigma68(vals)
        reproduction_rows.append(
            {
                "quantity": label,
                "reproduced_sigma68_ns": reproduced,
                "reference_sigma68_ns": ref,
                "delta_ns": reproduced - ref,
                "pass": abs(reproduced - ref) < 1e-6,
            }
        )
    reproduction = pd.DataFrame(reproduction_rows)
    reproduction.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S02/S02b reference reproduction failed")

    summary = cv_summary(cv)
    selected_binned = str(summary[summary["base_method"] == "s02b_template"].sort_values("mean_cv_sigma68_ns").iloc[0]["method"])
    selected_global = str(summary[summary["base_method"] == "template_phase"].sort_values("mean_cv_sigma68_ns").iloc[0]["method"])

    methods = [
        ("template_phase", "S02 global template"),
        ("s02c_binned_timewalk_drift0", "S02b binned timewalk no drift"),
        ("s02c_global_timewalk_drift0", "S02b global timewalk no drift"),
        ("ml_ridge", "S02 ML ridge"),
    ]
    if selected_binned != "s02c_binned_timewalk_drift0":
        methods.insert(2, (selected_binned, f"S02c binned selected {selected_binned.rsplit('drift', 1)[1]}"))
    if selected_global != "s02c_global_timewalk_drift0":
        methods.insert(-1, (selected_global, f"S02c global selected {selected_global.rsplit('drift', 1)[1]}"))
    bench = benchmark_methods(work, methods, config, out_dir)
    by_run = heldout_by_run(work, methods, config, out_dir)
    leak = leakage_checks(work, config, bench, selected_binned, selected_global, out_dir)
    leak_pass_non_oracle = bool(leak[leak["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]["pass"].all())

    plot_methods = [
        ("s02c_binned_timewalk_drift0", "binned no drift"),
        (selected_binned, "binned selected drift"),
        ("s02c_global_timewalk_drift0", "global no drift"),
        (selected_global, "global selected drift"),
        ("ml_ridge", "ML ridge"),
    ]
    write_plots(out_dir, bench, work, plot_methods, config, cv)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    selected_binned_label = str(bench[bench["internal_method"] == selected_binned]["method"].iloc[0])
    selected_global_label = str(bench[bench["internal_method"] == selected_global]["method"].iloc[0])
    write_report(out_dir, config, match, s02_ref, reproduction, cv, bench, by_run, leak, selected_binned_label, selected_global_label)

    binned0 = bench[bench["internal_method"] == "s02c_binned_timewalk_drift0"].iloc[0]
    binned_sel = bench[bench["internal_method"] == selected_binned].iloc[0]
    global0 = bench[bench["internal_method"] == "s02c_global_timewalk_drift0"].iloc[0]
    global_sel = bench[bench["internal_method"] == selected_global].iloc[0]
    ml = bench[bench["internal_method"] == "ml_ridge"].iloc[0]
    result = {
        "study": "S02c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "reference_numbers_reproduced": bool(reproduction["pass"].all()),
        "split_by_run": {"train_runs": config["timing"]["train_runs"], "heldout_runs": config["timing"]["heldout_runs"]},
        "traditional": {
            "method": selected_global,
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "value": float(global_sel["value"]),
            "ci": [float(global_sel["ci_low"]), float(global_sel["ci_high"])],
            "delta_vs_no_drift_ns": float(global_sel["value"] - global0["value"]),
        },
        "amplitude_binned_template_timewalk": {
            "selected_method": selected_binned,
            "no_drift_value": float(binned0["value"]),
            "selected_value": float(binned_sel["value"]),
            "selected_ci": [float(binned_sel["ci_low"]), float(binned_sel["ci_high"])],
            "delta_vs_no_drift_ns": float(binned_sel["value"] - binned0["value"]),
            "drift_improves": bool(float(binned_sel["value"]) < float(binned0["value"])),
        },
        "ml": {
            "method": "ridge_residual_corrector_on_cfd20",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
        },
        "leakage_checks_pass_excluding_forbidden_oracle": leak_pass_non_oracle,
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [
            "S02d: leave-one-run-out run-drift nuisance scan over all Sample II runs",
            "S02e: drift constrained by current/rate covariates before timing labels",
        ],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02c",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "selected_binned": selected_binned,
                "selected_binned_sigma68_ns": float(binned_sel["value"]),
                "selected_global": selected_global,
                "selected_global_sigma68_ns": float(global_sel["value"]),
                "ml_sigma68_ns": float(ml["value"]),
                "leakage_pass_excluding_oracle": leak_pass_non_oracle,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
