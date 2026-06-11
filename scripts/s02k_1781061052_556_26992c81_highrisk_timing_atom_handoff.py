#!/usr/bin/env python3
"""S02k high-risk timing atom handoff table.

The script starts from raw ROOT count reproduction, then reuses the S02e
leave-one-run-out timing-tail benchmark as the event-risk backbone.  S02k adds
an auditable atom table that separates pulse-shape handoff candidates from
charge/topology artifacts and reports ML-minus-traditional paired bootstrap
deltas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s02k-1781061052")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, roc_auc_score

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels as s02e


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
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


def output_hashes(out_dir: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def input_hashes(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in s02e.configured_runs(config):
        path = s02e.raw_file(config, run)
        rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "input_sha256.csv", index=False)
    return frame


def sigma68(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    q16, q84 = np.percentile(arr, [16, 84])
    return float(0.5 * (q84 - q16))


def normalized_template_rmse(pulses: pd.DataFrame) -> pd.DataFrame:
    rows = []
    templates: Dict[str, np.ndarray] = {}
    for stave, group in pulses.groupby("stave", sort=True):
        waves = np.vstack([(np.asarray(w, dtype=float) / max(float(a), 1.0)) for w, a in zip(group["waveform"], group["amplitude_adc"])])
        templates[str(stave)] = np.median(waves, axis=0)
    for idx, row in pulses.iterrows():
        stave = str(row["stave"])
        norm = np.asarray(row["waveform"], dtype=float) / max(float(row["amplitude_adc"]), 1.0)
        rows.append({"_idx": idx, "q_template_rmse": float(np.sqrt(np.mean((norm - templates[stave]) ** 2)))})
    return pd.DataFrame(rows).set_index("_idx")


def event_atom_table(pulses: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    q = normalized_template_rmse(pulses)
    work = pulses.join(q, how="left")
    rows = []
    downstream = ["B4", "B6", "B8"]
    for event_id, group in work.groupby("event_id", sort=False):
        group = group.set_index("stave").reindex(downstream)
        amps = group["amplitude_adc"].to_numpy(dtype=float)
        qvals = group["q_template_rmse"].to_numpy(dtype=float)
        peak = group["peak_sample"].to_numpy(dtype=float)
        tail = group["tail_area_frac"].to_numpy(dtype=float)
        secondary = group["secondary_peak_frac"].to_numpy(dtype=float)
        width = group["width20_samples"].to_numpy(dtype=float)
        lowering = group["adaptive_lowering_adc"].to_numpy(dtype=float)
        preabs = group["pretrigger_absmax_adc"].to_numpy(dtype=float)
        dominant_i = int(np.nanargmax(qvals)) if np.isfinite(qvals).any() else 0
        rows.append(
            {
                "event_id": event_id,
                "run": int(group["run"].iloc[0]),
                "max_q_template_rmse": float(np.nanmax(qvals)),
                "dominant_q_stave": downstream[dominant_i],
                "dominant_q_stave_index": dominant_i,
                "max_peak_sample": float(np.nanmax(peak)),
                "max_tail_area_frac": float(np.nanmax(tail)),
                "max_secondary_peak_frac": float(np.nanmax(secondary)),
                "max_width20_samples": float(np.nanmax(width)),
                "max_adaptive_lowering_adc": float(np.nanmax(lowering)),
                "max_pretrigger_absmax_adc": float(np.nanmax(preabs)),
                "min_over_max_amp": float(np.nanmin(amps) / max(np.nanmax(amps), 1.0)),
                "amp_cv": float(np.nanstd(amps) / max(np.nanmean(amps), 1.0)),
                "mean_log_amp": float(np.nanmean(np.log1p(np.maximum(amps, 0.0)))),
            }
        )
    atoms = pd.DataFrame(rows).merge(predictions[["event_id", "dt_span_ns", "tail_label"]], on="event_id", how="inner")
    q95 = atoms["max_q_template_rmse"].quantile(0.95)
    tail90 = atoms["max_tail_area_frac"].quantile(0.90)
    width95 = atoms["max_width20_samples"].quantile(0.95)
    secondary95 = atoms["max_secondary_peak_frac"].quantile(0.95)
    pre95 = atoms["max_pretrigger_absmax_adc"].quantile(0.95)
    lower95 = atoms["max_adaptive_lowering_adc"].quantile(0.95)
    amp05 = atoms["min_over_max_amp"].quantile(0.05)
    ampcv95 = atoms["amp_cv"].quantile(0.95)

    delayed = (atoms["max_peak_sample"] >= 14) | (atoms["max_secondary_peak_frac"] >= max(0.35, secondary95))
    broad = (atoms["max_tail_area_frac"] >= tail90) | (atoms["max_width20_samples"] >= width95)
    baseline = (atoms["max_pretrigger_absmax_adc"] >= pre95) | (atoms["max_adaptive_lowering_adc"] >= lower95)
    charge_artifact = (atoms["min_over_max_amp"] <= amp05) | (atoms["amp_cv"] >= ampcv95)
    q_only = atoms["max_q_template_rmse"] >= q95

    labels = np.full(len(atoms), "common_shape", dtype=object)
    labels[charge_artifact.to_numpy()] = "low_charge_pair_artifact"
    labels[(q_only & ~charge_artifact).to_numpy()] = "q_template_mismatch"
    labels[(baseline & ~charge_artifact).to_numpy()] = "pretrigger_baseline_shape"
    labels[(broad & ~charge_artifact).to_numpy()] = "broad_late_shape"
    labels[(delayed & ~charge_artifact).to_numpy()] = "delayed_peak_shape"
    atoms["atom_class"] = labels
    atoms["pulse_shape_handoff"] = atoms["atom_class"].isin(
        ["delayed_peak_shape", "broad_late_shape", "pretrigger_baseline_shape", "q_template_mismatch"]
    )
    atoms["artifact_handoff"] = atoms["atom_class"].isin(["low_charge_pair_artifact"])
    return atoms


def finite_metrics(y: np.ndarray, score: np.ndarray) -> Dict[str, float]:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    out = {"average_precision": float(average_precision_score(y, score)) if len(y) else float("nan")}
    out["roc_auc"] = float(roc_auc_score(y, score)) if len(np.unique(y)) > 1 else float("nan")
    return out


def sentinel_summary(atoms: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 33)
    frame = atoms.copy()
    y = frame["tail_label"].astype(int).to_numpy()
    runs = sorted(frame["run"].unique())
    train_tail_mean = {}
    for r in runs:
        train = frame[frame["run"] != r]
        train_tail_mean[int(r)] = float(train["tail_label"].mean())
    sentinels = {
        "charge_only_sentinel": frame["amp_cv"].to_numpy(dtype=float) + (1.0 - frame["min_over_max_amp"].to_numpy(dtype=float)),
        "topology_only_sentinel": frame["dominant_q_stave_index"].to_numpy(dtype=float),
        "run_only_sentinel": frame["run"].map(train_tail_mean).to_numpy(dtype=float),
        "q_template_only_sentinel": frame["max_q_template_rmse"].to_numpy(dtype=float),
        "shuffled_risk_sentinel": rng.permutation(y).astype(float) + 1e-3 * rng.normal(size=len(y)),
    }
    rows = []
    run_values = np.asarray(runs, dtype=int)
    by_run = {int(r): np.flatnonzero(frame["run"].to_numpy(dtype=int) == int(r)) for r in runs}
    for name, score in sentinels.items():
        point = finite_metrics(y, score)
        boot = {"average_precision": [], "roc_auc": []}
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            idx = np.concatenate([by_run[int(r)] for r in rng.choice(run_values, size=len(run_values), replace=True)])
            vals = finite_metrics(y[idx], score[idx])
            for key in boot:
                boot[key].append(vals[key])
        row = {"sentinel": name, **point}
        for key, vals in boot.items():
            row[f"{key}_ci_low"] = float(np.nanpercentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.nanpercentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("average_precision", ascending=False)


def atom_metrics(atoms: pd.DataFrame) -> pd.DataFrame:
    total = len(atoms)
    base_tail = float(atoms["tail_label"].mean())
    base_sigma = sigma68(atoms["dt_span_ns"])
    rows = []
    for atom, sub in atoms.groupby("atom_class", sort=True):
        mask = atoms["atom_class"] == atom
        kept = atoms[~mask]
        by_run = sub.groupby("run").size()
        rows.append(
            {
                "atom_class": atom,
                "n_events": int(len(sub)),
                "prevalence": float(len(sub) / max(total, 1)),
                "tail_precision": float(sub["tail_label"].mean()),
                "tail_enrichment": float(sub["tail_label"].mean() / max(base_tail, 1e-12)),
                "tail_rate_after_exclusion": float(kept["tail_label"].mean()) if len(kept) else float("nan"),
                "kept_pair_fraction": float(len(kept) / max(total, 1)),
                "max_pair_share_concentration": float(by_run.max() / max(len(sub), 1)),
                "downstream_sigma68_delta_ns": sigma68(kept["dt_span_ns"]) - base_sigma if len(kept) else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values(["tail_precision", "n_events"], ascending=False)


def method_metrics(frame: pd.DataFrame, flag_col: str, name: str) -> Dict[str, float]:
    y = frame["tail_label"].astype(bool).to_numpy()
    flag = frame[flag_col].astype(bool).to_numpy()
    kept = frame.loc[~flag]
    base_sigma = sigma68(frame["dt_span_ns"])
    flagged = frame.loc[flag]
    by_run = flagged.groupby("run").size()
    return {
        "method": name,
        "flagged_events": int(flag.sum()),
        "kept_pair_fraction": float(np.mean(~flag)),
        "tail_precision": float(np.mean(y[flag])) if flag.any() else float("nan"),
        "tail_rejection": float(np.mean(flag[y])) if y.any() else float("nan"),
        "tail_rate_after_exclusion": float(kept["tail_label"].mean()) if len(kept) else float("nan"),
        "downstream_sigma68_delta_ns": sigma68(kept["dt_span_ns"]) - base_sigma if len(kept) else float("nan"),
        "max_pair_share_concentration": float(by_run.max() / max(flag.sum(), 1)) if flag.any() else 0.0,
    }


def method_summary_and_delta(predictions: pd.DataFrame, summary: pd.DataFrame, config: dict) -> tuple:
    winner = str(summary.iloc[0]["model"])
    winner_score_col = str(summary.iloc[0]["score_column"])
    winner_veto_col = winner_score_col.replace("score_", "veto_", 1)
    trad_col = "veto_traditional_s16f_scorecard"
    if winner_veto_col not in predictions:
        raise RuntimeError("missing winner veto column {}".format(winner_veto_col))
    rows = [
        method_metrics(predictions, trad_col, "traditional_s16f_scorecard"),
        method_metrics(predictions, winner_veto_col, winner),
    ]
    metric_frame = pd.DataFrame(rows)
    rng = np.random.default_rng(int(config["random_seed"]) + 901)
    runs = np.asarray(sorted(predictions["run"].unique()), dtype=int)
    by_run = {int(run): sub.copy() for run, sub in predictions.groupby("run")}
    boot_rows = []
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        trad = method_metrics(sample, trad_col, "traditional_s16f_scorecard")
        ml = method_metrics(sample, winner_veto_col, winner)
        row = {"ml_model": winner}
        for metric in [
            "kept_pair_fraction",
            "tail_precision",
            "tail_rejection",
            "tail_rate_after_exclusion",
            "downstream_sigma68_delta_ns",
            "max_pair_share_concentration",
        ]:
            row[metric + "_ml_minus_traditional"] = float(ml[metric] - trad[metric])
        boot_rows.append(row)
    boot = pd.DataFrame(boot_rows)
    delta_rows = []
    for col in [c for c in boot.columns if c.endswith("_ml_minus_traditional")]:
        delta_rows.append(
            {
                "metric": col.replace("_ml_minus_traditional", ""),
                "ml_minus_traditional": float(boot[col].mean()),
                "ci_low": float(boot[col].quantile(0.025)),
                "ci_high": float(boot[col].quantile(0.975)),
            }
        )
    return metric_frame, pd.DataFrame(delta_rows), winner


def write_plots(out_dir: Path, model_summary: pd.DataFrame, atom_table: pd.DataFrame) -> None:
    plot = model_summary.sort_values("average_precision", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    y = plot["average_precision"].to_numpy(dtype=float)
    yerr = np.vstack([y - plot["average_precision_ci_low"].to_numpy(dtype=float), plot["average_precision_ci_high"].to_numpy(dtype=float) - y])
    ax.barh(np.arange(len(plot)), y, xerr=yerr, capsize=3)
    ax.set_yticks(np.arange(len(plot)))
    ax.set_yticklabels(plot["model"])
    ax.set_xlabel("held-out average precision")
    ax.set_title("S02k timing-tail classifier benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_model_average_precision.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    atom_plot = atom_table.sort_values("tail_precision", ascending=True)
    ax.barh(atom_plot["atom_class"], atom_plot["tail_precision"])
    ax.set_xlabel("tail precision")
    ax.set_title("High-risk timing atom classes")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_atom_tail_precision.png", dpi=150)
    plt.close(fig)


def md_table(frame: pd.DataFrame, cols: Sequence[str], fmt: Dict[str, str] = None) -> str:
    fmt = fmt or {}
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            vals.append(fmt[col].format(value) if col in fmt and pd.notna(value) else str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, model_summary: pd.DataFrame, sentinel: pd.DataFrame, atom_table: pd.DataFrame, method_table: pd.DataFrame, delta: pd.DataFrame, leakage: pd.DataFrame, runtime: float, winner: str) -> None:
    repro_rows = repro.copy()
    repro_rows["pass"] = repro_rows["pass"].map(lambda v: "yes" if bool(v) else "no")
    model = model_summary.copy()
    for metric in ["average_precision", "roc_auc", "tail_rejection_at_90_clean", "clean_acceptance"]:
        model[metric + "_ci"] = model.apply(lambda r: "{:.3f} [{:.3f}, {:.3f}]".format(r[metric], r[metric + "_ci_low"], r[metric + "_ci_high"]), axis=1)
    sent = sentinel.copy()
    for metric in ["average_precision", "roc_auc"]:
        sent[metric + "_ci"] = sent.apply(lambda r: "{:.3f} [{:.3f}, {:.3f}]".format(r[metric], r[metric + "_ci_low"], r[metric + "_ci_high"]), axis=1)
    leak = leakage.copy()
    leak["pass"] = leak["pass"].map(lambda v: "yes" if bool(v) else "no")
    best = model_summary.iloc[0]
    report = """# S02k: high-risk timing atom handoff table

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Input:** raw B-stack ROOT files under `{raw}`
- **Split:** leave-one-run-out over Sample-II analysis runs `{runs}`
- **Primary target:** downstream all-hit `D_t > {tail:.1f} ns`
- **Git commit at run time:** `{commit}`

## 1. Question

S02e identified a high-support timing-risk population, but the downstream consumers need atom labels rather than a single opaque risk flag. This study asks which high-risk candidates are pulse-shape atoms worth handing to S03/S04/S10 consumers and which are charge-pair or topology artifacts that should remain diagnostic only.

## 2. Raw-ROOT Reproduction Gate

The first operation is an independent scan of `HRDv` in the raw ROOT files. Pulses are selected from B2/B4/B6/B8 with median baseline samples 0-3 and amplitude `A > 1000 ADC`.

{repro_table}

The zero-tolerance count gate reproduces the S00 anchor before any atom labels, timing spans, or classifiers are fit.

## 3. Methods and Estimands

For event `e` and downstream stave `i`, the fold-local template time is geometry corrected as

`t'_(i,e) = t_template(i,e) - x_i / v`,

with `v^-1 = {tof:.3f} ns/cm`. The timing-risk label is

`y_e = 1[max_i t'_(i,e) - min_i t'_(i,e) > {tail:.1f} ns]`.

The traditional handoff method is a frozen S16f-style scorecard using q-template-like residuals, amplitude/log-amplitude imbalance, adaptive lowering, pre-trigger excursion, width, late fraction, secondary peak, stave identity, and downstream topology summaries. Its threshold is selected on non-held-out runs to retain `{accept:.0f}%` of clean training events.

The ML/NN benchmark uses ridge logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, and a dilated temporal CNN (`tcn`) as the new architecture. Classifiers are trained strictly leave-one-run-out. They do not receive event id, event order, run id, the timing span, or corrected times. Sentinels score charge-only, topology-only, run-only, q-template-only, and shuffled-risk controls.

Atom classes are descriptive handoff strata: `delayed_peak_shape`, `broad_late_shape`, `pretrigger_baseline_shape`, `q_template_mismatch`, `low_charge_pair_artifact`, and `common_shape`. Reported confidence intervals are non-parametric run-block bootstraps, and ML-minus-traditional deltas are paired by event inside each sampled run block.

## 4. Model Benchmark

{model_table}

Winner by held-out average precision is **`{winner}`** with AP `{ap:.3f}` [{ap_lo:.3f}, {ap_hi:.3f}].

## 5. Sentinel Controls

{sentinel_table}

The sentinels are not production candidates. They bound how much of the apparent signal is recoverable from nuisance-only summaries before waveform-shape models are credited.

## 6. Atom Handoff Ledger

{atom_table}

`tail_rate_after_exclusion` and `downstream_sigma68_delta_ns` are recomputed after dropping the atom class. Negative sigma68 deltas mean the kept sample narrows after that atom is excluded.

## 7. Traditional vs ML Handoff Operating Point

{method_table}

Paired run-block bootstrap ML-minus-traditional deltas:

{delta_table}

## 8. Leakage Checks

{leak_table}

## 9. Systematics and Caveats

- The `D_t > {tail:.1f} ns` target is an internal timing-span label, not external truth. It is a risk label for triage, not proof of pile-up or bad detector response.
- The q-template residual in the atom table is a fold-independent descriptive proxy built from normalized downstream shapes; the classifier benchmark itself is split by run.
- The all-hit Sample-II support is only `{n_events}` events, so run-block intervals dominate several atom classes.
- Charge-pair artifacts are identified from amplitude imbalance and should not be passed as pulse-shape vetoes without the proposed external control validation.
- CNN and TCN capacities are intentionally laptop-safe. Larger architectures are possible but would be a separate capacity study.

## 10. Verdict

The raw-count gate passes exactly and the best held-out classifier is `{winner}`. The handoff table supports using delayed-peak, broad-late, pre-trigger/baseline, and q-template-mismatch classes as provisional pulse-shape atoms, while low-charge-pair rows should be treated as artifacts. The result names `{winner}` as the benchmark winner in `result.json` and queues at most one follow-up: external validation of the frozen S02k atom table.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02k_1781061052_556_26992c81_highrisk_timing_atom_handoff.py --config configs/s02k_1781061052_556_26992c81_highrisk_timing_atom_handoff.yaml
```

Runtime in this execution was `{runtime:.2f}` s.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        raw=config["raw_root_dir"],
        runs=config["timing"]["loro_runs"],
        tail=float(config["tail_threshold_ns"]),
        commit=git_commit(),
        repro_table=md_table(repro_rows, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        tof=float(config["tof_per_cm_ns"]),
        accept=100 * float(config["target_clean_acceptance"]),
        model_table=md_table(model, ["model", "n_events", "n_tail", "average_precision_ci", "roc_auc_ci", "tail_rejection_at_90_clean_ci", "clean_acceptance_ci"]),
        winner=winner,
        ap=float(best["average_precision"]),
        ap_lo=float(best["average_precision_ci_low"]),
        ap_hi=float(best["average_precision_ci_high"]),
        sentinel_table=md_table(sent, ["sentinel", "average_precision_ci", "roc_auc_ci"]),
        atom_table=md_table(atom_table, ["atom_class", "n_events", "prevalence", "tail_precision", "tail_enrichment", "tail_rate_after_exclusion", "kept_pair_fraction", "max_pair_share_concentration", "downstream_sigma68_delta_ns"], {"prevalence": "{:.3f}", "tail_precision": "{:.3f}", "tail_enrichment": "{:.3f}", "tail_rate_after_exclusion": "{:.3f}", "kept_pair_fraction": "{:.3f}", "max_pair_share_concentration": "{:.3f}", "downstream_sigma68_delta_ns": "{:.3f}"}),
        method_table=md_table(method_table, ["method", "flagged_events", "kept_pair_fraction", "tail_precision", "tail_rejection", "tail_rate_after_exclusion", "downstream_sigma68_delta_ns", "max_pair_share_concentration"], {"kept_pair_fraction": "{:.3f}", "tail_precision": "{:.3f}", "tail_rejection": "{:.3f}", "tail_rate_after_exclusion": "{:.3f}", "downstream_sigma68_delta_ns": "{:.3f}", "max_pair_share_concentration": "{:.3f}"}),
        delta_table=md_table(delta, ["metric", "ml_minus_traditional", "ci_low", "ci_high"], {"ml_minus_traditional": "{:.3f}", "ci_low": "{:.3f}", "ci_high": "{:.3f}"}),
        leak_table=md_table(leak, ["check", "value", "pass"]),
        n_events=int(best["n_events"]),
        runtime=runtime,
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02k_1781061052_556_26992c81_highrisk_timing_atom_handoff.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw selected-pulse reproduction gate failed")
    hash_frame = input_hashes(config, out_dir)

    pulses = s02e.load_downstream_pulses_with_s16_features(config)
    pulses.groupby(["run", "stave"]).size().reset_index(name="selected_allhit_pulses").to_csv(out_dir / "allhit_pulse_counts_by_run_stave.csv", index=False)
    fold_metrics, choices, predictions, model_summary, feature_names = s02e.run_loro_benchmark(pulses, config, out_dir)
    leakage = s02e.leakage_checks(pulses, predictions, feature_names, config)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    atoms = event_atom_table(pulses, predictions)
    atoms.to_csv(out_dir / "atom_handoff_events.csv", index=False)
    atom_table = atom_metrics(atoms)
    atom_table.to_csv(out_dir / "atom_handoff_table.csv", index=False)
    sentinel = sentinel_summary(atoms, config)
    sentinel.to_csv(out_dir / "sentinel_benchmark.csv", index=False)
    method_table, delta, winner = method_summary_and_delta(predictions, model_summary, config)
    method_table.to_csv(out_dir / "method_handoff_summary.csv", index=False)
    delta.to_csv(out_dir / "ml_minus_traditional_bootstrap_delta.csv", index=False)
    write_plots(out_dir, model_summary, atom_table)

    runtime = time.time() - t0
    next_ticket = config.get("next_ticket")
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "reproduced": bool(repro["pass"].all()),
        "split": "leave-one-run-out over Sample-II runs {}".format(config["timing"]["loro_runs"]),
        "tail_threshold_ns": float(config["tail_threshold_ns"]),
        "traditional": "fixed S16f/q-template/charge-pair morphology scorecard at 90% train clean acceptance",
        "models": sorted(model_summary["model"].tolist()),
        "sentinels": sorted(sentinel["sentinel"].tolist()),
        "winner": {
            "model": winner,
            "metric": "held-out average precision",
            "average_precision": float(model_summary.iloc[0]["average_precision"]),
            "ci": [float(model_summary.iloc[0]["average_precision_ci_low"]), float(model_summary.iloc[0]["average_precision_ci_high"])],
            "tail_rejection_at_90_clean": float(model_summary.iloc[0]["tail_rejection_at_90_clean"]),
        },
        "handoff": {
            "pulse_shape_atoms": ["delayed_peak_shape", "broad_late_shape", "pretrigger_baseline_shape", "q_template_mismatch"],
            "artifact_atoms": ["low_charge_pair_artifact"],
            "event_rows": int(len(atoms)),
        },
        "scientific_summary": "S02k freezes a run-held-out atom handoff ledger for S02e high-risk timing candidates; {} wins the ML/NN benchmark, while charge-pair artifacts are separated from provisional pulse-shape atoms.".format(winner),
        "next_tickets": [next_ticket] if next_ticket else [],
        "runtime_seconds": runtime,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, model_summary, sentinel, atom_table, method_table, delta, leakage, runtime, winner)
    manifest = {
        "script": str(Path(__file__).resolve().relative_to(Path.cwd())),
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "input_files": int(len(hash_frame)),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
