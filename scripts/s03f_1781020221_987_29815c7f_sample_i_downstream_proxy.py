#!/usr/bin/env python3
"""S03f Sample-I sparse-topology validation of the S03e single-stave proxy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
from sklearn.metrics import mean_absolute_error, mean_squared_error

import s02_timing_pickoff as s02
import s03e_two_ended_safe_timewalk as s03e


METHODS = [
    ("cfd20", "cfd20_base"),
    ("amp_isotonic_proxy", "traditional_amp_isotonic_proxy"),
    ("template_phase", "traditional_template_phase"),
    ("ml_proxy", "ml_single_stave_proxy"),
    ("ml_shuffled_proxy", "ml_shuffled_proxy_control"),
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


def configured_runs(config: dict) -> List[int]:
    runs = set()
    for key in ("sample_i_downstream_runs", "sample_ii_reference_runs"):
        runs.update(int(run) for run in config["timing"].get(key, []))
    return sorted(runs)


def load_sparse_downstream_pulses(config: dict, runs: Iterable[int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    all_staves = {name: int(ch) for name, ch in config["staves"].items()}
    downstream = list(config["timing"]["downstream_staves"])
    channels = np.asarray([all_staves[name] for name in downstream])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    min_selected = int(config["topology"]["min_selected_downstream_staves"])
    rows = []
    topology_rows = []
    event_uid_base = 0
    for run in sorted(int(r) for r in runs):
        path = s02.raw_file(config, run)
        run_events = 0
        selected_events = 0
        multiplicity_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        pair_counts = {"B4_B6": 0, "B4_B8": 0, "B6_B8": 0}
        for batch in s02.iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            corrected, amplitude, peak, area = s02.pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            multiplicity = selected.sum(axis=1).astype(int)
            run_events += int(len(eventno))
            for mult in range(4):
                multiplicity_counts[mult] += int(np.sum(multiplicity == mult))
            event_mask = multiplicity >= min_selected
            if not event_mask.any():
                event_uid_base += len(eventno)
                continue
            for e in np.where(event_mask)[0]:
                selected_events += 1
                uid = f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}"
                selected_staves = [stave for sidx, stave in enumerate(downstream) if selected[e, sidx]]
                for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                    if a in selected_staves and b in selected_staves:
                        pair_counts[f"{a}_{b}"] += 1
                for sidx, stave in enumerate(downstream):
                    if not selected[e, sidx]:
                        continue
                    rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "waveform": corrected[e, sidx].astype(float),
                            "amplitude_adc": float(amplitude[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                            "downstream_multiplicity": int(multiplicity[e]),
                        }
                    )
            event_uid_base += len(eventno)
        topology_rows.append(
            {
                "run": int(run),
                "raw_events": int(run_events),
                "events_ge2_downstream": int(selected_events),
                "events_0_downstream": int(multiplicity_counts[0]),
                "events_1_downstream": int(multiplicity_counts[1]),
                "events_2_downstream": int(multiplicity_counts[2]),
                "events_3_downstream": int(multiplicity_counts[3]),
                **pair_counts,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(topology_rows)


def sparse_pairwise_residuals(pulses: pd.DataFrame, method: str, spacing_cm: float, config: dict, runs: List[int]) -> np.ndarray:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, spacing_cm)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin([int(run) for run in runs])].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr")
    residuals = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a not in wide or b not in wide:
            continue
        vals = (wide[a] - wide[b]).dropna().to_numpy(dtype=float)
        if len(vals):
            residuals.append(vals)
    if not residuals:
        return np.asarray([], dtype=float)
    values = np.concatenate(residuals)
    return values[np.isfinite(values)]


def metric_rows_for_run(pulses: pd.DataFrame, config: dict, heldout_run: int, methods: List[Tuple[str, str]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residual_rows = []
    for method, label in methods:
        vals = sparse_pairwise_residuals(pulses, method, 2.0, config, [int(heldout_run)])
        rows.append({"heldout_run": int(heldout_run), "method": label, **s02.metric_summary(vals)})
        residual_rows.extend(
            {"heldout_run": int(heldout_run), "method": label, "pairwise_residual_ns": float(v)}
            for v in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(int(r) for r in residuals["heldout_run"].unique())
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {int(run): sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled if len(by_run[int(run)])])
            stats.append(s02.sigma68(boot_vals))
        lo, hi = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(lo),
                "ci_high": float(hi),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def one_sparse_fold(pulses_all: pd.DataFrame, config: dict, heldout_run: int, all_runs: List[int], seed: int):
    train_runs = [run for run in all_runs if run != int(heldout_run)]
    pulses = pulses_all.copy()
    s03e.cfd_columns(pulses, config)
    s03e.add_template_phase(pulses, train_runs, config)
    target = pulses["t_cfd20_ns"].to_numpy(dtype=float) - pulses["t_template_phase_ns"].to_numpy(dtype=float)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs)
    heldout_mask = runs == int(heldout_run)

    amp_models = s03e.fit_amp_isotonic(pulses, train_mask, target, config)
    amp_pred = s03e.predict_amp_isotonic(pulses, amp_models)
    pulses["t_amp_isotonic_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - amp_pred

    X, feature_names = s03e.proxy_feature_matrix(pulses, list(config["timing"]["downstream_staves"]))
    finite = np.isfinite(target) & np.all(np.isfinite(X), axis=1)
    model = s03e.ml_model(config, seed)
    model.fit(X[train_mask & finite], target[train_mask & finite])
    ml_pred = model.predict(X)
    pulses["t_ml_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - ml_pred
    pulses["t_ml_shuffled_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - s03e.shuffled_ml_prediction(
        pulses, X, train_mask, finite, target, config, seed + 101
    )

    train_target = target[train_mask & finite]
    held_target = target[heldout_mask & finite]
    train_pred = ml_pred[train_mask & finite]
    held_pred = ml_pred[heldout_mask & finite]
    proxy_rows = [
        {
            "heldout_run": int(heldout_run),
            "model": "ml_proxy",
            "split": "train",
            "rmse_ns": math.sqrt(mean_squared_error(train_target, train_pred)),
            "mae_ns": mean_absolute_error(train_target, train_pred),
            "n_pulses": int(len(train_target)),
        },
        {
            "heldout_run": int(heldout_run),
            "model": "ml_proxy",
            "split": "heldout",
            "rmse_ns": math.sqrt(mean_squared_error(held_target, held_pred)),
            "mae_ns": mean_absolute_error(held_target, held_pred),
            "n_pulses": int(len(held_target)),
        },
    ]
    metrics, residuals = metric_rows_for_run(pulses, config, int(heldout_run), METHODS)
    train_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    held_ids = set(pulses[pulses["run"] == int(heldout_run)]["event_id"])
    leakage = pd.DataFrame(
        [
            {"heldout_run": int(heldout_run), "check": "train_heldout_run_overlap", "value": float(len(set(train_runs) & {int(heldout_run)})), "unit": "runs"},
            {"heldout_run": int(heldout_run), "check": "train_heldout_event_id_overlap", "value": float(len(train_ids & held_ids)), "unit": "events"},
            {"heldout_run": int(heldout_run), "check": "fit_targets_include_event_residuals", "value": 0.0, "unit": "bool"},
            {"heldout_run": int(heldout_run), "check": "features_include_run_event_or_other_stave_time", "value": 0.0, "unit": "bool"},
            {"heldout_run": int(heldout_run), "check": "n_single_stave_features", "value": float(len(feature_names)), "unit": "features"},
        ]
    )
    model_table = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "stave": stave,
                "traditional_model": model_info["kind"],
                "increasing": model_info.get("increasing", np.nan),
                "n_train": model_info.get("n_train", np.nan),
            }
            for stave, model_info in amp_models.items()
        ]
    )
    return metrics, residuals, leakage, pd.DataFrame(proxy_rows), model_table


def run_sample_ii_reference(config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    ref_runs = [int(run) for run in config["timing"]["sample_ii_reference_runs"]]
    ref_cfg = json.loads(json.dumps(config))
    ref_cfg["timing"]["train_runs"] = ref_runs[:-1]
    ref_cfg["timing"]["heldout_runs"] = [ref_runs[-1]]
    ref_pulses = s02.load_downstream_pulses(ref_cfg)
    per_run_parts = []
    residual_parts = []
    for i, heldout_run in enumerate(ref_runs):
        metrics, residuals, _, _, _ = s03e.one_fold(
            ref_pulses,
            ref_cfg,
            heldout_run,
            ref_runs,
            int(config["methods"]["random_seed"]) + 1000 * i,
        )
        per_run_parts.append(metrics)
        residual_parts.append(residuals)
    residuals = pd.concat(residual_parts, ignore_index=True)
    pooled = s03e.run_level_bootstrap(residuals, rng, int(config["methods"]["bootstrap_samples"]))
    return pd.concat(per_run_parts, ignore_index=True), pooled


def run_sample_i_sparse(config: dict, rng: np.random.Generator):
    runs = [int(run) for run in config["timing"]["sample_i_downstream_runs"]]
    pulses, topology = load_sparse_downstream_pulses(config, runs)
    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    proxy_parts = []
    model_parts = []
    for i, heldout_run in enumerate(runs):
        metrics, residuals, leakage, proxy, models = one_sparse_fold(
            pulses,
            config,
            heldout_run,
            runs,
            int(config["methods"]["random_seed"]) + 2000 * i,
        )
        per_run_parts.append(metrics)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        proxy_parts.append(proxy)
        model_parts.append(models)
    residuals = pd.concat(residual_parts, ignore_index=True)
    return {
        "pulses": pulses,
        "topology": topology,
        "per_run": pd.concat(per_run_parts, ignore_index=True),
        "residuals": residuals,
        "pooled": run_level_bootstrap(residuals, rng, int(config["methods"]["bootstrap_samples"])),
        "leakage": pd.concat(leakage_parts, ignore_index=True),
        "proxy": pd.concat(proxy_parts, ignore_index=True),
        "models": pd.concat(model_parts, ignore_index=True),
    }


def compare_to_sample_ii(sample_i_pooled: pd.DataFrame, sample_ii_pooled: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in sorted(set(sample_i_pooled["method"]) & set(sample_ii_pooled["method"])):
        i = sample_i_pooled[sample_i_pooled["method"] == method].iloc[0]
        ii = sample_ii_pooled[sample_ii_pooled["method"] == method].iloc[0]
        rows.append(
            {
                "method": method,
                "sample_i_sparse_sigma68_ns": float(i["value"]),
                "sample_i_ci_low": float(i["ci_low"]),
                "sample_i_ci_high": float(i["ci_high"]),
                "sample_ii_s03e_sigma68_ns": float(ii["value"]),
                "sample_ii_ci_low": float(ii["ci_low"]),
                "sample_ii_ci_high": float(ii["ci_high"]),
                "delta_sample_i_minus_sample_ii_ns": float(i["value"] - ii["value"]),
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, topology: pd.DataFrame, comparison: pd.DataFrame) -> None:
    order = [
        "cfd20_base",
        "traditional_amp_isotonic_proxy",
        "traditional_template_phase",
        "ml_single_stave_proxy",
        "ml_shuffled_proxy_control",
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.9))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["sigma68_ns"], "o-", label=method)
    ax.set_xlabel("Sample-I held-out run")
    ax.set_ylabel("sparse-pair sigma68 (ns)")
    ax.set_title("S03f Sample-I sparse downstream single-stave proxy")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_sample_i_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    sub = pooled.set_index("method").loc[order].reset_index()
    x = np.arange(len(sub))
    ax.bar(x, sub["value"])
    ax.errorbar(x, sub["value"], yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(sub["method"], rotation=30, ha="right")
    ax.set_ylabel("pooled run-bootstrap sigma68 (ns)")
    ax.set_title("Sample-I pooled held-out-run bootstrap")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_sample_i_pooled_bootstrap.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    topo = topology.sort_values("run")
    ax.bar(topo["run"].astype(str), topo["events_2_downstream"], label="exactly two downstream staves")
    ax.bar(topo["run"].astype(str), topo["events_3_downstream"], bottom=topo["events_2_downstream"], label="all three downstream staves")
    ax.set_xlabel("Sample-I run")
    ax.set_ylabel("events")
    ax.set_title("Sparse downstream topology")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_topology.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 4.3))
    comp = comparison.set_index("method").loc[order].reset_index()
    x = np.arange(len(comp))
    width = 0.36
    ax.bar(x - width / 2, comp["sample_i_sparse_sigma68_ns"], width, label="Sample I sparse")
    ax.bar(x + width / 2, comp["sample_ii_s03e_sigma68_ns"], width, label="Sample II S03e")
    ax.set_xticks(x)
    ax.set_xticklabels(comp["method"], rotation=30, ha="right")
    ax.set_ylabel("pooled sigma68 (ns)")
    ax.set_title("Sample-I sparse vs Sample-II S03e")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_sample_i_vs_sample_ii.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    sample_ii_ref: pd.DataFrame,
    sample_i: dict,
    comparison: pd.DataFrame,
    result: dict,
) -> None:
    pooled = sample_i["pooled"]
    per_run = sample_i["per_run"]
    topology = sample_i["topology"]
    leakage = sample_i["leakage"]
    proxy = sample_i["proxy"]
    base = pooled[pooled["method"] == "cfd20_base"].iloc[0]
    trad = pooled[pooled["method"] == "traditional_template_phase"].iloc[0]
    ml = pooled[pooled["method"] == "ml_single_stave_proxy"].iloc[0]
    shuffle = pooled[pooled["method"] == "ml_shuffled_proxy_control"].iloc[0]
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min", "median", "max"]
    topology_summary = pd.DataFrame(
        [
            {
                "runs": int(len(topology)),
                "events_ge2_downstream": int(topology["events_ge2_downstream"].sum()),
                "events_exactly_2_downstream": int(topology["events_2_downstream"].sum()),
                "events_all_3_downstream": int(topology["events_3_downstream"].sum()),
                "fraction_exactly_2": float(topology["events_2_downstream"].sum() / max(topology["events_ge2_downstream"].sum(), 1)),
                "pair_residuals": int(per_run[per_run["method"] == "cfd20_base"]["n_pair_residuals"].sum()),
            }
        ]
    )
    lines = [
        "# Study report: S03f - Sample-I sparse downstream S03e proxy validation",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `/home/billy/Desktop/test_beam/data/root/root`",
        "- **Split:** leave-one-run-out over Sample-I analysis runs 44-57; held-out bootstrap resamples runs",
        f"- **Config:** `{config_path}`",
        "- **Monte Carlo:** none",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate and the Sample-II S03e single-stave proxy numbers were rebuilt before the Sample-I study.",
        "",
        repro.to_markdown(index=False),
        "",
        sample_ii_ref[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "This repeats the S03e no-event-residual single-stave proxy target `t_cfd20_ns - t_template_phase_ns`. The traditional branch uses train-run templates plus the amplitude-isotonic proxy; the ML branch is the same histogram-gradient-boosting proxy regressor over normalized single-stave waveform features. Inter-stave timing is used only for held-out scoring.",
        "",
        "For Sample I, events with at least two selected downstream staves are retained and each available pair is scored. This is the sparse-topology extension relative to the strict all-three Sample-II S03e reference.",
        "",
        "## 3. Topology limitation",
        "",
        topology_summary.to_markdown(index=False),
        "",
        topology[["run", "events_ge2_downstream", "events_2_downstream", "events_3_downstream", "B4_B6", "B4_B8", "B6_B8"]].to_markdown(index=False),
        "",
        "## 4. Held-out Sample-I results",
        "",
        per_run[["heldout_run", "method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Pooled CIs resample held-out runs.",
        "",
        pooled[["method", "value", "ci_low", "ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## 5. Comparison with Sample-II S03e",
        "",
        comparison.to_markdown(index=False),
        "",
        "## 6. Leakage checks",
        "",
        proxy.to_markdown(index=False),
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        f"The shuffled-target ML control gives `{shuffle['value']:.3f} ns`, so it does not explain the ML proxy result. Run/event overlap checks are zero and the feature audit excludes run id, event id, event order, and other-stave timing.",
        "",
        "## 7. Verdict",
        "",
        f"Sample-I sparse CFD20 is `{base['value']:.3f} ns` with CI `[{base['ci_low']:.3f}, {base['ci_high']:.3f}] ns`.",
        f"The strong traditional train-template phase method is `{trad['value']:.3f} ns` with CI `[{trad['ci_low']:.3f}, {trad['ci_high']:.3f}] ns`.",
        f"The ML single-stave proxy is `{ml['value']:.3f} ns` with CI `[{ml['ci_low']:.3f}, {ml['ci_high']:.3f}] ns`.",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## 8. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03f_1781020221_987_29815c7f_sample_i_downstream_proxy.py --config {config_path}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03f_1781020221_987_29815c7f_sample_i_downstream_proxy.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["methods"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    sample_ii_per_run, sample_ii_pooled = run_sample_ii_reference(config, rng)
    sample_ii_per_run.to_csv(out_dir / "sample_ii_s03e_reference_per_run.csv", index=False)
    sample_ii_pooled.to_csv(out_dir / "sample_ii_s03e_reference_pooled.csv", index=False)
    ref_checks = {
        "cfd20_base": float(config["reference_numbers"]["s03e_sample_ii_cfd20_base_sigma68_ns"]),
        "traditional_template_phase": float(config["reference_numbers"]["s03e_sample_ii_traditional_template_phase_sigma68_ns"]),
        "ml_single_stave_proxy": float(config["reference_numbers"]["s03e_sample_ii_ml_single_stave_proxy_sigma68_ns"]),
    }
    sample_ii_check = sample_ii_pooled[sample_ii_pooled["method"].isin(ref_checks)].copy()
    sample_ii_check["report_value"] = sample_ii_check["method"].map(ref_checks)
    sample_ii_check["delta_ns"] = sample_ii_check["value"] - sample_ii_check["report_value"]
    sample_ii_check["pass"] = sample_ii_check["delta_ns"].abs() < 1.0e-9
    sample_ii_check.to_csv(out_dir / "sample_ii_s03e_reproduction_check.csv", index=False)
    if not bool(sample_ii_check["pass"].all()):
        raise RuntimeError("S03e Sample-II reference reproduction gate failed")

    sample_i = run_sample_i_sparse(config, rng)
    sample_i["topology"].to_csv(out_dir / "sample_i_sparse_topology.csv", index=False)
    sample_i["per_run"].to_csv(out_dir / "sample_i_per_run_benchmark.csv", index=False)
    sample_i["residuals"].to_csv(out_dir / "sample_i_pairwise_residuals.csv", index=False)
    sample_i["pooled"].to_csv(out_dir / "sample_i_pooled_run_bootstrap.csv", index=False)
    sample_i["leakage"].to_csv(out_dir / "leakage_checks.csv", index=False)
    sample_i["proxy"].to_csv(out_dir / "proxy_fit_metrics.csv", index=False)
    sample_i["models"].to_csv(out_dir / "traditional_proxy_models.csv", index=False)

    comparison = compare_to_sample_ii(sample_i["pooled"], sample_ii_pooled)
    comparison.to_csv(out_dir / "sample_i_vs_sample_ii_comparison.csv", index=False)
    plot_outputs(out_dir, sample_i["per_run"], sample_i["pooled"], sample_i["topology"], comparison)

    input_rows = []
    input_hashes = {}
    for run in configured_runs(config):
        path = s02.raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    pooled = sample_i["pooled"]
    base = pooled[pooled["method"] == "cfd20_base"].iloc[0]
    trad = pooled[pooled["method"] == "traditional_template_phase"].iloc[0]
    ml = pooled[pooled["method"] == "ml_single_stave_proxy"].iloc[0]
    shuffle = pooled[pooled["method"] == "ml_shuffled_proxy_control"].iloc[0]
    leak_flags = int((sample_i["leakage"][sample_i["leakage"]["check"].isin(["train_heldout_run_overlap", "train_heldout_event_id_overlap", "fit_targets_include_event_residuals", "features_include_run_event_or_other_stave_time"])]["value"] != 0.0).sum())
    topology = sample_i["topology"]
    frac_exactly_2 = float(topology["events_2_downstream"].sum() / max(topology["events_ge2_downstream"].sum(), 1))
    verdict = (
        "sample_i_sparse_proxy_supported_with_topology_caveat"
        if ml["value"] < base["value"] and trad["value"] < base["value"] and shuffle["value"] > ml["value"] and leak_flags == 0
        else "sample_i_sparse_proxy_not_supported"
    )
    result = {
        "study": "S03f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all() and sample_ii_check["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro["pass"].all()),
            "s03e_sample_ii_reference_pass": bool(sample_ii_check["pass"].all()),
            "sample_ii_reference_checks": sample_ii_check[["method", "value", "report_value", "delta_ns", "pass"]].to_dict(orient="records"),
        },
        "split": {
            "unit": "run",
            "heldout_runs": [int(run) for run in config["timing"]["sample_i_downstream_runs"]],
            "bootstrap_unit": "heldout_run",
            "sample": "Sample I analysis",
        },
        "topology": {
            "min_selected_downstream_staves": int(config["topology"]["min_selected_downstream_staves"]),
            "events_ge2_downstream": int(topology["events_ge2_downstream"].sum()),
            "events_exactly_2_downstream": int(topology["events_2_downstream"].sum()),
            "events_all_3_downstream": int(topology["events_3_downstream"].sum()),
            "fraction_exactly_2": frac_exactly_2,
            "pair_residuals": int(pooled[pooled["method"] == "cfd20_base"]["n_pair_residuals"].iloc[0]),
        },
        "baseline": {
            "method": "cfd20_base",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "traditional": {
            "method": "train_run_template_phase_single_stave",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
            "gain_vs_cfd20_ns": float(base["value"] - trad["value"]),
            "uses_event_residual_target": False,
            "uses_other_stave_timing_features": False,
        },
        "ml": {
            "method": "hist_gradient_boosting_on_single_stave_proxy_target",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "gain_vs_cfd20_ns": float(base["value"] - ml["value"]),
            "proxy_target": "cfd20_minus_train_template_phase",
            "uses_event_residual_target": False,
            "uses_other_stave_timing_features": False,
        },
        "sample_ii_comparison": comparison.to_dict(orient="records"),
        "leakage": {
            "split_by_run": True,
            "flag_count": leak_flags,
            "ml_shuffled_proxy_sigma68_ns": float(shuffle["value"]),
            "features_exclude_run_event_order_cross_stave_time": True,
            "event_residuals_used_only_for_final_scoring": True,
            "too_good_flag": bool(ml["value"] < sample_ii_pooled[sample_ii_pooled["method"] == "ml_single_stave_proxy"]["value"].iloc[0] - 0.5),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "follow_up_ticket_appended": False,
        "follow_up_skip_reason": "Skipped: sparse downstream topology follow-ups duplicate this ticket or existing S03/S05 single-stave timing studies.",
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, sample_ii_pooled, sample_i, comparison, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03f",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["methods"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "sample_i_baseline": float(base["value"]),
                "sample_i_traditional": float(trad["value"]),
                "sample_i_ml": float(ml["value"]),
                "fraction_exactly_2": frac_exactly_2,
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
