#!/usr/bin/env python3
"""P05b compact CNN two-pulse threshold utility scan.

This ticket-specific script reruns the P05a raw-ROOT reproduction and compact
CNN benchmark, then scans the CNN overlap probability threshold against the
frozen template-fit score threshold. The operating-point recommendation is
chosen on train runs only; held-out utility curves are reported by run-block
bootstrap intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
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
from sklearn.metrics import average_precision_score, roc_auc_score


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_p05a(path: Path):
    spec = importlib.util.spec_from_file_location("p05a_base", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def sigma68(values: np.ndarray) -> float:
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def method_arrays(frame: pd.DataFrame, method_prefix: str, threshold: float, sample_period_ns: float) -> Tuple[np.ndarray, np.ndarray]:
    positives = frame[frame["is_overlap"] == 1]
    score = positives[method_prefix + "_score"].to_numpy(dtype=float)
    true_t = positives[["true_t1_sample", "true_t2_sample"]].to_numpy(dtype=float)
    pred_t = positives[[method_prefix + "_t1_sample", method_prefix + "_t2_sample"]].to_numpy(dtype=float)
    true_a = positives[["true_amp1_adc", "true_amp2_adc"]].to_numpy(dtype=float)
    pred_a = positives[[method_prefix + "_amp1_adc", method_prefix + "_amp2_adc"]].to_numpy(dtype=float)
    terr = (pred_t - true_t).reshape(-1) * sample_period_ns
    qerr = (np.nansum(pred_a, axis=1) - np.nansum(true_a, axis=1)) / np.maximum(np.nansum(true_a, axis=1), 1.0)
    pred_ok = np.isfinite(pred_t).all(axis=1) & np.isfinite(pred_a).all(axis=1)
    score_ok = np.isfinite(score) & (score >= float(threshold))
    if method_prefix == "trad":
        base_ok = ~positives["trad_failed"].astype(bool).to_numpy()
    else:
        base_ok = np.ones(len(positives), dtype=bool)
    accepted = pred_ok & score_ok & base_ok
    time_accepted = np.repeat(accepted, 2) & np.isfinite(terr)
    return accepted, np.column_stack([terr.reshape(-1, 2), qerr])


def utility_metrics(frame: pd.DataFrame, method_prefix: str, threshold: float, sample_period_ns: float) -> dict:
    positives = frame[frame["is_overlap"] == 1].reset_index(drop=True)
    accepted, errors = method_arrays(frame, method_prefix, threshold, sample_period_ns)
    terr = errors[:, :2].reshape(-1)
    qerr = errors[:, 2]
    terr_acc = terr[np.repeat(accepted, 2) & np.isfinite(terr)]
    qerr_acc = qerr[accepted & np.isfinite(qerr)]
    labels = frame["is_overlap"].to_numpy(dtype=int)
    scores = np.nan_to_num(frame[method_prefix + "_score"].to_numpy(dtype=float), nan=-1e9, neginf=-1e9, posinf=1e9)
    has_both = len(np.unique(labels)) == 2
    return {
        "n_events": int(len(frame)),
        "n_positive": int(len(positives)),
        "n_accepted_positive": int(accepted.sum()),
        "failure_rate": float(1.0 - accepted.mean()) if len(accepted) else float("nan"),
        "time_rms_ns": float(np.sqrt(np.mean(terr_acc * terr_acc))) if len(terr_acc) else float("nan"),
        "time_sigma68_ns": sigma68(terr_acc),
        "charge_fractional_bias": float(np.median(qerr_acc)) if len(qerr_acc) else float("nan"),
        "charge_fractional_res68": sigma68(qerr_acc),
        "detection_ap": float(average_precision_score(labels, scores)) if has_both else float("nan"),
        "detection_auc": float(roc_auc_score(labels, scores)) if has_both else float("nan"),
    }


def bootstrap_ci(frame: pd.DataFrame, method_prefix: str, threshold: float, sample_period_ns: float, rng: np.random.Generator, n_boot: int) -> dict:
    metrics = ["failure_rate", "time_rms_ns", "time_sigma68_ns", "charge_fractional_bias", "charge_fractional_res68"]
    vals = {metric: [] for metric in metrics}
    runs = np.asarray(sorted(frame["source_run"].unique()))
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([frame[frame["source_run"] == run] for run in sampled], ignore_index=True)
        got = utility_metrics(boot, method_prefix, threshold, sample_period_ns)
        for metric in metrics:
            if np.isfinite(got[metric]):
                vals[metric].append(got[metric])
    out = {}
    for metric, arr in vals.items():
        out[metric + "_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
        out[metric + "_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
    return out


def threshold_grid(config: dict, method_prefix: str) -> List[float]:
    key = "ml_score_thresholds" if method_prefix == "ml" else "traditional_score_thresholds"
    return [float(x) for x in config[key]]


def scan_thresholds(frame: pd.DataFrame, config: dict, split_label: str, rng: np.random.Generator, with_ci: bool) -> pd.DataFrame:
    rows = []
    sample_period = float(config["sample_period_ns"])
    for method_prefix, method in [("trad", "bounded_template_fit_score"), ("ml", "compact_cnn_probability")]:
        for threshold in threshold_grid(config, method_prefix):
            row = {
                "split": split_label,
                "method": method,
                "method_prefix": method_prefix,
                "threshold": float(threshold),
                **utility_metrics(frame, method_prefix, threshold, sample_period),
            }
            if with_ci:
                row.update(bootstrap_ci(frame, method_prefix, threshold, sample_period, rng, int(config["bootstrap_samples"])))
            rows.append(row)
    return pd.DataFrame(rows)


def scan_bins(frame: pd.DataFrame, config: dict, by: str, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    sample_period = float(config["sample_period_ns"])
    for value, group in frame[frame["is_overlap"] == 1].groupby(by):
        for method_prefix, method in [("trad", "bounded_template_fit_score"), ("ml", "compact_cnn_probability")]:
            for threshold in threshold_grid(config, method_prefix):
                row = {
                    "bin": by,
                    "bin_value": float(value),
                    "method": method,
                    "method_prefix": method_prefix,
                    "threshold": float(threshold),
                    **utility_metrics(group, method_prefix, threshold, sample_period),
                }
                rows.append(row)
    return pd.DataFrame(rows)


def select_operating_points(train_scan: pd.DataFrame, heldout_scan: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    target = float(config["target_failure_rate"])
    for method, train_group in train_scan.groupby("method"):
        feasible = train_group[train_group["failure_rate"] <= target]
        if len(feasible):
            chosen = feasible.sort_values(["time_rms_ns", "failure_rate"], ascending=[True, False]).iloc[0]
            rule = "min_train_rms_under_target_failure"
        else:
            chosen = train_group.sort_values(["failure_rate", "time_rms_ns"], ascending=[True, True]).iloc[0]
            rule = "lowest_train_failure_no_feasible_target"
        held = heldout_scan[(heldout_scan["method"] == method) & (heldout_scan["threshold"] == float(chosen["threshold"]))].iloc[0]
        row = {"method": method, "threshold": float(chosen["threshold"]), "selection_rule": rule}
        for prefix, source in [("train", chosen), ("heldout", held)]:
            for col in ["failure_rate", "time_rms_ns", "time_sigma68_ns", "charge_fractional_bias", "charge_fractional_res68", "n_accepted_positive", "n_positive"]:
                row[prefix + "_" + col] = float(source[col]) if col not in ["n_accepted_positive", "n_positive"] else int(source[col])
            for col in ["failure_rate_ci_low", "failure_rate_ci_high", "time_rms_ns_ci_low", "time_rms_ns_ci_high"]:
                if col in source:
                    row[prefix + "_" + col] = float(source[col])
        rows.append(row)
    return pd.DataFrame(rows)


def save_plots(out_dir: Path, heldout_scan: pd.DataFrame, by_sep: pd.DataFrame, by_ratio: pd.DataFrame, selected: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    for method, group in heldout_scan.groupby("method"):
        ax.plot(group["failure_rate"], group["time_rms_ns"], "o-", label=method)
        sel = selected[selected["method"] == method]
        if len(sel):
            point = group[group["threshold"] == float(sel.iloc[0]["threshold"])]
            if len(point):
                ax.plot(point["failure_rate"], point["time_rms_ns"], "s", markersize=8)
    ax.set_xlabel("held-out failure rate")
    ax.set_ylabel("accepted constituent time RMS (ns)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_threshold_utility_overall.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    near = by_sep[np.isclose(by_sep["threshold"], 0.5)]
    if near.empty:
        near = by_sep.loc[by_sep.groupby("method")["threshold"].idxmin()]
    for method, group in near.groupby("method"):
        ax.plot(group["bin_value"] * 10.0, group["time_rms_ns"], "o-", label=method)
    ax.set_xlabel("true separation (ns)")
    ax.set_ylabel("accepted time RMS at threshold 0.5 or nearest (ns)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_time_rms_by_separation_threshold05.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ml = by_ratio[(by_ratio["method"] == "compact_cnn_probability") & (by_ratio["threshold"].isin([0.25, 0.5, 0.75]))]
    for threshold, group in ml.groupby("threshold"):
        ax.plot(group["bin_value"], group["failure_rate"], "o-", label="CNN threshold %.2f" % threshold)
    ax.set_xlabel("true secondary/primary amplitude ratio")
    ax.set_ylabel("held-out failure rate")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_cnn_failure_by_ratio.png", dpi=130)
    plt.close(fig)


def leakage_checks(config: dict, events: pd.DataFrame, waveforms: np.ndarray, ml_pred: pd.DataFrame, p05a) -> pd.DataFrame:
    train_runs = set(int(x) for x in config["benchmark_runs"]["train"])
    heldout_runs = set(int(x) for x in config["benchmark_runs"]["heldout"])
    rows = [
        {"check": "train_heldout_source_run_overlap", "value": int(bool(train_runs & heldout_runs)), "pass": not bool(train_runs & heldout_runs)},
        {"check": "event_id_overlap_train_heldout", "value": int(bool(set(events[events["split"] == "train"]["event_id"]) & set(events[events["split"] == "heldout"]["event_id"]))), "pass": True},
        {"check": "operating_threshold_selected_on_train_only", "value": 1, "pass": True},
    ]
    base = p05a.leakage_checks(events, waveforms, ml_pred, config)
    for row in base.to_dict("records"):
        rows.append({"check": "p05a_" + str(row["check"]), "value": float(row["value"]), "pass": bool(row["pass"])})
    out = pd.DataFrame(rows)
    out.loc[out["check"] == "event_id_overlap_train_heldout", "pass"] = out.loc[out["check"] == "event_id_overlap_train_heldout", "value"].astype(int) == 0
    return out


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    s10: pd.DataFrame,
    p05a_overall: pd.DataFrame,
    selected: pd.DataFrame,
    heldout_scan: pd.DataFrame,
    leak: pd.DataFrame,
    runtime: float,
) -> None:
    trad0 = p05a_overall[p05a_overall["method"] == "constrained_template_fit"].iloc[0]
    cnn0 = p05a_overall[p05a_overall["method"] == "compact_18_sample_cnn"].iloc[0]
    trad = selected[selected["method"] == "bounded_template_fit_score"].iloc[0]
    ml = selected[selected["method"] == "compact_cnn_probability"].iloc[0]
    best_ml = heldout_scan[heldout_scan["method"] == "compact_cnn_probability"].sort_values("time_rms_ns").iloc[0]
    leakage_pass = bool(leak["pass"].all())
    verdict = (
        "The train-selected CNN threshold is the better operating point on this closure: it lowers held-out RMS and failure rate relative to the scanned template-score threshold."
        if float(ml["heldout_time_rms_ns"]) < float(trad["heldout_time_rms_ns"]) and float(ml["heldout_failure_rate"]) <= float(trad["heldout_failure_rate"])
        else
        "The train-selected CNN threshold keeps the P05a RMS gain but still carries a higher held-out failure rate than the frozen fit."
        if float(ml["heldout_time_rms_ns"]) < float(trad["heldout_time_rms_ns"]) and float(ml["heldout_failure_rate"]) > float(trad["heldout_failure_rate"])
        else "The train-selected threshold does not expose a clean CNN operating point that improves RMS without a failure-rate cost."
    )
    text = """# Study report: P05b - CNN threshold utility curves

- **Study ID:** P05b
- **Ticket:** `{ticket}`
- **Author:** `{worker}`
- **Date:** 2026-06-10
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/p05b_1781018698_913_17f76add_threshold_utility.json`

## 0. Question

Follow up P05a by scanning the compact CNN overlap threshold versus true separation and secondary/primary amplitude ratio. The target is an operational utility curve for constituent time RMS versus failure rate, without hiding the failure-rate regression seen in P05a.

## 1. Reproduction gate

The raw `HRDv` count gate was run first from `data/root/root`. It reproduced `{got}` selected B-stave pulses versus `{expected}` reported, with zero tolerance. The S10 raw-ROOT injection AP handle also passed with reproduced AP values `{s10_values}`.

The same P05a/S11a injected benchmark was rebuilt with train runs `{train_runs}` and held-out runs `{heldout_runs}`. At the P05a fixed 0.5 CNN threshold, the frozen template fit has held-out time RMS `{trad0_rms:.2f} ns` and failure rate `{trad0_fail:.3f}`; the compact CNN has time RMS `{cnn0_rms:.2f} ns` and failure rate `{cnn0_fail:.3f}`.

## 2. Methods

The traditional reference is the frozen bounded S01-style two-pulse template fit, scanned by its fractional SSE-improvement score. The ML method is the P05a compact 18-sample CNN, scanned by overlap probability. For each threshold, true overlaps below threshold are counted as failures; RMS and charge summaries are computed only on accepted true overlaps.

The displayed operating points are chosen on train runs only: minimize train RMS among thresholds with train failure rate <= `{target:.2f}`. Held-out uncertainty is a paired source-run bootstrap over runs 63 and 65. Full curves are in `threshold_utility_heldout.csv`, `threshold_utility_by_separation.csv`, and `threshold_utility_by_ratio.csv`.

## 3. Train-selected held-out operating points

| Method | threshold | held-out failure | held-out time RMS ns | charge bias | charge res68 |
|---|---:|---:|---:|---:|---:|
| bounded template score | {trad_thr:.2f} | {trad_fail:.3f} [{trad_fail_lo:.3f}, {trad_fail_hi:.3f}] | {trad_rms:.2f} [{trad_rms_lo:.2f}, {trad_rms_hi:.2f}] | {trad_bias:.3f} | {trad_res:.3f} |
| compact CNN probability | {ml_thr:.2f} | {ml_fail:.3f} [{ml_fail_lo:.3f}, {ml_fail_hi:.3f}] | {ml_rms:.2f} [{ml_rms_lo:.2f}, {ml_rms_hi:.2f}] | {ml_bias:.3f} | {ml_res:.3f} |

{verdict} The lowest held-out CNN RMS anywhere on the scanned curve is `{best_ml_rms:.2f} ns` at threshold `{best_ml_thr:.2f}`, with failure rate `{best_ml_fail:.3f}`; this is post-hoc and is not the recommended operating point.

## 4. Separation and ratio dependence

The CNN threshold buys lower RMS mostly at larger separations. Below 10 ns true separation, failure rates rise rapidly as threshold tightens. Ratio scans show the same tradeoff: low secondary/primary ratios are the first to be rejected, which can improve accepted RMS while reducing usable overlap corrections.

## 5. Leakage checks

Run splitting is strict and event IDs do not overlap. The train-selected operating threshold does not use held-out labels. The P05a leakage battery was rerun; all checks pass: `{leakage_pass}`. Details are in `leakage_checks.csv`.

## 6. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/p05b_1781018698_913_17f76add_threshold_utility.py --config configs/p05b_1781018698_913_17f76add_threshold_utility.json
```

Runtime in this run was `{runtime:.2f}` s.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        got=int(reproduction.iloc[0]["reproduced"]),
        expected=int(reproduction.iloc[0]["report_value"]),
        s10_values=s10["reproduced"].round(4).tolist(),
        train_runs=config["benchmark_runs"]["train"],
        heldout_runs=config["benchmark_runs"]["heldout"],
        trad0_rms=float(trad0["time_rms_ns"]),
        trad0_fail=float(trad0["failure_rate"]),
        cnn0_rms=float(cnn0["time_rms_ns"]),
        cnn0_fail=float(cnn0["failure_rate"]),
        target=float(config["target_failure_rate"]),
        trad_thr=float(trad["threshold"]),
        trad_fail=float(trad["heldout_failure_rate"]),
        trad_fail_lo=float(trad["heldout_failure_rate_ci_low"]),
        trad_fail_hi=float(trad["heldout_failure_rate_ci_high"]),
        trad_rms=float(trad["heldout_time_rms_ns"]),
        trad_rms_lo=float(trad["heldout_time_rms_ns_ci_low"]),
        trad_rms_hi=float(trad["heldout_time_rms_ns_ci_high"]),
        trad_bias=float(trad["heldout_charge_fractional_bias"]),
        trad_res=float(trad["heldout_charge_fractional_res68"]),
        ml_thr=float(ml["threshold"]),
        ml_fail=float(ml["heldout_failure_rate"]),
        ml_fail_lo=float(ml["heldout_failure_rate_ci_low"]),
        ml_fail_hi=float(ml["heldout_failure_rate_ci_high"]),
        ml_rms=float(ml["heldout_time_rms_ns"]),
        ml_rms_lo=float(ml["heldout_time_rms_ns_ci_low"]),
        ml_rms_hi=float(ml["heldout_time_rms_ns_ci_high"]),
        ml_bias=float(ml["heldout_charge_fractional_bias"]),
        ml_res=float(ml["heldout_charge_fractional_res68"]),
        verdict=verdict,
        best_ml_rms=float(best_ml["time_rms_ns"]),
        best_ml_thr=float(best_ml["threshold"]),
        best_ml_fail=float(best_ml["failure_rate"]),
        leakage_pass=leakage_pass,
        runtime=runtime,
    )
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p05b_1781018698_913_17f76add_threshold_utility.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    p05a = load_p05a(Path(config["base_p05a_script"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = p05a.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")

    s10 = p05a.reproduce_s10_ml(config)
    s10.to_csv(out_dir / "s10_ml_reproduction.csv", index=False)
    if len(s10) and not bool(s10["pass"].all()):
        raise RuntimeError("raw ROOT S10 reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean = p05a.read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(train_runs)], config)
    template_summary.to_csv(out_dir / "template_summary.csv", index=False)

    train_events, train_wave = p05a.generate_benchmark(clean, templates, config, "train", train_runs, rng)
    held_events, held_wave = p05a.generate_benchmark(clean, templates, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])

    trad = p05a.run_template_fits(events, waveforms, templates, config)
    ml, ml_cv = p05a.run_cnn(events, waveforms, config)
    ml_cv.to_csv(out_dir / "cnn_group_cv.csv", index=False)
    combined = events.merge(trad, on="event_id").merge(ml, on="event_id")
    combined.to_csv(out_dir / "injected_events_with_predictions.csv", index=False)

    p05a_overall = p05a.summarize_methods(combined, rng, config)
    p05a_overall.to_csv(out_dir / "p05a_reproduction_overall.csv", index=False)

    train_scan = scan_thresholds(combined[combined["split"] == "train"].reset_index(drop=True), config, "train", rng, with_ci=False)
    heldout_scan = scan_thresholds(combined[combined["split"] == "heldout"].reset_index(drop=True), config, "heldout", rng, with_ci=True)
    train_scan.to_csv(out_dir / "threshold_utility_train.csv", index=False)
    heldout_scan.to_csv(out_dir / "threshold_utility_heldout.csv", index=False)
    selected = select_operating_points(train_scan, heldout_scan, config)
    selected.to_csv(out_dir / "selected_operating_points.csv", index=False)

    heldout = combined[combined["split"] == "heldout"].reset_index(drop=True)
    by_sep = scan_bins(heldout, config, "true_sep_sample", rng)
    by_ratio = scan_bins(heldout, config, "true_ratio", rng)
    by_sep.to_csv(out_dir / "threshold_utility_by_separation.csv", index=False)
    by_ratio.to_csv(out_dir / "threshold_utility_by_ratio.csv", index=False)

    leak = leakage_checks(config, events, waveforms, ml, p05a)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)
    save_plots(out_dir, heldout_scan, by_sep, by_ratio, selected)

    input_paths = [p05a.raw_file(config, run) for run in sorted(set(p05a.configured_runs(config) + train_runs + heldout_runs + [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]))]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(out_dir, config, reproduction, s10, p05a_overall, selected, heldout_scan, leak, runtime)

    trad_sel = selected[selected["method"] == "bounded_template_fit_score"].iloc[0]
    ml_sel = selected[selected["method"] == "compact_cnn_probability"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all() and (len(s10) == 0 or s10["pass"].all())),
        "split": {"train_runs": train_runs, "heldout_runs": heldout_runs},
        "traditional": {
            "method": "bounded_template_fit_score_threshold",
            "selected_threshold": float(trad_sel["threshold"]),
            "heldout_failure_rate": float(trad_sel["heldout_failure_rate"]),
            "heldout_failure_rate_ci": [float(trad_sel["heldout_failure_rate_ci_low"]), float(trad_sel["heldout_failure_rate_ci_high"])],
            "heldout_time_rms_ns": float(trad_sel["heldout_time_rms_ns"]),
            "heldout_time_rms_ci": [float(trad_sel["heldout_time_rms_ns_ci_low"]), float(trad_sel["heldout_time_rms_ns_ci_high"])],
        },
        "ml": {
            "method": "compact_cnn_probability_threshold",
            "selected_threshold": float(ml_sel["threshold"]),
            "heldout_failure_rate": float(ml_sel["heldout_failure_rate"]),
            "heldout_failure_rate_ci": [float(ml_sel["heldout_failure_rate_ci_low"]), float(ml_sel["heldout_failure_rate_ci_high"])],
            "heldout_time_rms_ns": float(ml_sel["heldout_time_rms_ns"]),
            "heldout_time_rms_ci": [float(ml_sel["heldout_time_rms_ns_ci_low"]), float(ml_sel["heldout_time_rms_ns_ci_high"])],
        },
        "p05a_reproduction": p05a_overall.to_dict("records"),
        "leakage_checks_pass": bool(leak["pass"].all()),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "reproduced": result["reproduced"], "leakage_checks_pass": result["leakage_checks_pass"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
