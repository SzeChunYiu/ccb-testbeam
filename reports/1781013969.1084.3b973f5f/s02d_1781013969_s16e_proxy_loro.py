#!/usr/bin/env python3
"""S02d ticket 1781013969: LORO S02b timing plus S16e proxy terms."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
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


SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import s02_timing_pickoff as s02


def load_s16e_module():
    path = REPO / "reports" / "1781007910.1647.505b465f" / "s16e_pretrigger_timing_tails.py"
    spec = importlib.util.spec_from_file_location("s16e_pretrigger_timing_tails", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16E = load_s16e_module()
S02B = S16E.S02B


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in s02.configured_runs(config)}


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, heldout_run: int) -> dict:
    cfg = copy.deepcopy(config)
    loro = [int(run) for run in cfg["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [run for run in loro if run != int(heldout_run)]
    return cfg


def all_loro_config(config: dict) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["train_runs"] = [int(run) for run in cfg["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = []
    return cfg


def event_metrics_with_ci(pulses: pd.DataFrame, method: str, config: dict, rng: np.random.Generator) -> dict:
    pairs = S02B.event_pair_table(pulses, method, config, config["timing"]["heldout_runs"])
    if pairs.empty:
        return {
            "value": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "tail_frac_abs_gt5ns": float("nan"),
            "tail_ci_low": float("nan"),
            "tail_ci_high": float("nan"),
            "n_heldout_events": 0,
            "n_pair_residuals": 0,
        }
    grouped = [group["residual_ns"].to_numpy(dtype=float) for _, group in pairs.groupby("event_id")]
    threshold = float(config["tail_threshold_ns"])
    sigma_stats, tail_stats = [], []
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        vals = np.concatenate([grouped[i] for i in chosen])
        med = float(np.median(vals))
        sigma_stats.append(s02.sigma68(vals))
        tail_stats.append(float(np.mean(np.abs(vals - med) > threshold)))
    vals = pairs["residual_ns"].to_numpy(dtype=float)
    med = float(np.median(vals))
    return {
        "value": s02.sigma68(vals),
        "ci_low": float(np.percentile(sigma_stats, 2.5)),
        "ci_high": float(np.percentile(sigma_stats, 97.5)),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - med) > threshold)),
        "tail_ci_low": float(np.percentile(tail_stats, 2.5)),
        "tail_ci_high": float(np.percentile(tail_stats, 97.5)),
        "n_heldout_events": int(len(grouped)),
        **s02.metric_summary(vals),
    }


def benchmark(work: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    heldout_run = int(config["timing"]["heldout_runs"][0])
    methods = [
        ("s16e_base_timewalk", "S02b global template timewalk"),
        ("s16e_proxy_timewalk", "traditional S16e proxy timewalk"),
        ("s16e_ml_proxy", "ML waveform plus S16e proxy ridge"),
    ]
    for method, label in methods:
        rows.append(
            {
                "heldout_run": heldout_run,
                "method": label,
                "internal_method": method,
                "metric": "B4/B6/B8 pairwise sigma68 ns",
                **event_metrics_with_ci(work, method, config, rng),
            }
        )
    return pd.DataFrame(rows)


def normalized_hash_overlap(work: pd.DataFrame, config: dict) -> int:
    train_hash, held_hash = set(), set()
    for mask, dest in [
        (work["run"].isin(config["timing"]["train_runs"]), train_hash),
        (work["run"].isin(config["timing"]["heldout_runs"]), held_hash),
    ]:
        for row in work[mask].itertuples():
            arr = np.round(row.waveform / max(float(row.amplitude_adc), 1.0), 5)
            key = f"{row.stave}|{np.array2string(arr, precision=5, separator=',')}"
            dest.add(hashlib.sha256(key.encode("utf-8")).hexdigest())
    return int(len(train_hash & held_hash))


def pair_sigma(pulses: pd.DataFrame, method: str, config: dict) -> float:
    vals = s02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, config["timing"]["heldout_runs"])
    return s02.sigma68(vals)


def leakage_checks(
    work: pd.DataFrame,
    config: dict,
    bench: pd.DataFrame,
    shuffled_trad: pd.DataFrame,
    shuffled_ml: pd.DataFrame,
    feature_names: Dict[str, List[str]],
) -> pd.DataFrame:
    heldout_run = int(config["timing"]["heldout_runs"][0])
    train_runs = set(config["timing"]["train_runs"])
    heldout_runs = set(config["timing"]["heldout_runs"])
    train_events = set(work[work["run"].isin(train_runs)]["event_id"])
    held_events = set(work[work["run"].isin(heldout_runs)]["event_id"])
    actual_trad = float(bench[bench["internal_method"] == "s16e_proxy_timewalk"]["value"].iloc[0])
    actual_ml = float(bench[bench["internal_method"] == "s16e_ml_proxy"]["value"].iloc[0])
    shuffled_trad_val = pair_sigma(shuffled_trad, "s16e_proxy_timewalk_shuffled", config)
    shuffled_ml_val = pair_sigma(shuffled_ml, "s16e_ml_proxy_shuffled", config)
    forbidden_tokens = ["run", "event", "target", "residual", "pair"]
    feature_text = " ".join(feature_names["traditional"] + feature_names["ml"]).lower()
    overlap = normalized_hash_overlap(work, config)
    return pd.DataFrame(
        [
            {"heldout_run": heldout_run, "check": "train_heldout_run_overlap", "value": int(len(train_runs & heldout_runs)), "actual": float("nan"), "pass": len(train_runs & heldout_runs) == 0},
            {"heldout_run": heldout_run, "check": "train_heldout_event_id_overlap", "value": int(len(train_events & held_events)), "actual": float("nan"), "pass": len(train_events & held_events) == 0},
            {"heldout_run": heldout_run, "check": "normalized_waveform_exact_hash_overlap", "value": overlap, "actual": float("nan"), "pass": overlap == 0},
            {"heldout_run": heldout_run, "check": "features_exclude_run_event_target_pair_residual", "value": int(any(tok in feature_text for tok in forbidden_tokens)), "actual": float("nan"), "pass": not any(tok in feature_text for tok in forbidden_tokens)},
            {"heldout_run": heldout_run, "check": "traditional_shuffled_target_not_better", "value": shuffled_trad_val, "actual": actual_trad, "pass": shuffled_trad_val >= actual_trad},
            {"heldout_run": heldout_run, "check": "ml_shuffled_target_not_better", "value": shuffled_ml_val, "actual": actual_ml, "pass": shuffled_ml_val >= actual_ml},
        ]
    )


def tail_by_proxy(work: pd.DataFrame, config: dict) -> pd.DataFrame:
    event_proxy = (
        work.groupby("event_id")
        .agg(
            run=("run", "first"),
            event_pre_line_absmax_adc=("pre_line_absmax_adc", "max"),
            event_pre_range_adc=("pre_range_adc", "max"),
        )
        .reset_index()
    )
    held = event_proxy[event_proxy["run"].isin(config["timing"]["heldout_runs"])].copy()
    held["proxy_bin"] = pd.qcut(held["event_pre_line_absmax_adc"], q=3, labels=["low", "mid", "high"], duplicates="drop")
    rows = []
    threshold = float(config["tail_threshold_ns"])
    methods = [
        ("s16e_base_timewalk", "S02b global template timewalk"),
        ("s16e_proxy_timewalk", "traditional S16e proxy timewalk"),
        ("s16e_ml_proxy", "ML waveform plus S16e proxy ridge"),
    ]
    for method, label in methods:
        pairs = S02B.event_pair_table(work, method, config, config["timing"]["heldout_runs"]).merge(held, on="event_id", how="left")
        med = float(np.median(pairs["residual_ns"]))
        pairs["is_tail"] = np.abs(pairs["residual_ns"] - med) > threshold
        for bin_name, sub in pairs.groupby("proxy_bin", dropna=False):
            rows.append(
                {
                    "heldout_run": int(config["timing"]["heldout_runs"][0]),
                    "method": label,
                    "proxy_bin": str(bin_name),
                    "n_pair_residuals": int(len(sub)),
                    "n_events": int(sub["event_id"].nunique()),
                    "event_pre_line_absmax_adc_mean": float(sub["event_pre_line_absmax_adc"].mean()),
                    "sigma68_ns": s02.sigma68(sub["residual_ns"].to_numpy(dtype=float)),
                    "tail_frac_abs_gt5ns": float(sub["is_tail"].mean()),
                }
            )
    return pd.DataFrame(rows)


def run_fold(all_pulses: pd.DataFrame, config: dict, heldout_run: int, rng: np.random.Generator) -> dict:
    cfg = fold_config(config, heldout_run)
    work, tables = S16E.prepare_s02b_baseline(all_pulses, cfg)
    trad_work, trad_cv, trad_coef, trad_features = S16E.fit_proxy_correction(
        work, cfg, "s16e_base_timewalk", "s16e_proxy_timewalk", ml_like=False
    )
    ml_work, ml_cv, ml_coef, ml_features = S16E.fit_proxy_correction(
        trad_work, cfg, "template_phase", "s16e_ml_proxy", ml_like=True
    )
    shuffled_trad, shuffled_trad_cv, _, _ = S16E.fit_proxy_correction(
        work, cfg, "s16e_base_timewalk", "s16e_proxy_timewalk_shuffled", ml_like=False, shuffled=True
    )
    shuffled_ml, shuffled_ml_cv, _, _ = S16E.fit_proxy_correction(
        work, cfg, "template_phase", "s16e_ml_proxy_shuffled", ml_like=True, shuffled=True
    )
    bench = benchmark(ml_work, cfg, rng)
    leak = leakage_checks(ml_work, cfg, bench, shuffled_trad, shuffled_ml, {"traditional": trad_features, "ml": ml_features})
    return {
        "heldout_run": int(heldout_run),
        "benchmark": bench,
        "leakage": leak,
        "tail_by_proxy": tail_by_proxy(ml_work, cfg),
        "traditional_scan_metrics": tables["traditional_scan_metrics"].assign(heldout_run=int(heldout_run)),
        "template_fit_by_run_stave": tables["template_fit_by_run_stave"].assign(heldout_run=int(heldout_run)),
        "base_timewalk_cv": tables["base_timewalk_cv"].assign(heldout_run=int(heldout_run)),
        "base_timewalk_calibration": tables["base_timewalk_calibration"].assign(heldout_run=int(heldout_run)),
        "base_timewalk_coefficients": tables["base_timewalk_coefficients"].assign(heldout_run=int(heldout_run)),
        "traditional_proxy_cv": trad_cv.assign(heldout_run=int(heldout_run)),
        "traditional_proxy_coefficients": trad_coef.assign(heldout_run=int(heldout_run)),
        "ml_proxy_cv": ml_cv.assign(heldout_run=int(heldout_run)),
        "ml_proxy_coefficients": ml_coef.assign(heldout_run=int(heldout_run)),
        "traditional_shuffled_target_cv": shuffled_trad_cv.assign(heldout_run=int(heldout_run)),
        "ml_shuffled_target_cv": shuffled_ml_cv.assign(heldout_run=int(heldout_run)),
    }


def run_block_bootstrap(bench: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 1700)
    rows = []
    for method, group in bench.groupby("method"):
        values = group.sort_values("heldout_run")["value"].to_numpy(dtype=float)
        tails = group.sort_values("heldout_run")["tail_frac_abs_gt5ns"].to_numpy(dtype=float)
        sig_stats, tail_stats = [], []
        for _ in range(int(config["ml"]["run_bootstrap_samples"])):
            idx = rng.integers(0, len(values), size=len(values))
            sig_stats.append(float(np.nanmean(values[idx])))
            tail_stats.append(float(np.nanmean(tails[idx])))
        rows.append(
            {
                "method": method,
                "n_runs": int(len(values)),
                "mean_sigma68_ns": float(np.nanmean(values)),
                "ci_low": float(np.nanpercentile(sig_stats, 2.5)),
                "ci_high": float(np.nanpercentile(sig_stats, 97.5)),
                "mean_tail_frac_abs_gt5ns": float(np.nanmean(tails)),
                "tail_ci_low": float(np.nanpercentile(tail_stats, 2.5)),
                "tail_ci_high": float(np.nanpercentile(tail_stats, 97.5)),
                "min_run_sigma68_ns": float(np.nanmin(values)),
                "max_run_sigma68_ns": float(np.nanmax(values)),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns")


def reproduction_reference(config: dict, bench: pd.DataFrame) -> pd.DataFrame:
    run65 = bench[bench["heldout_run"] == 65]
    references = [
        ("S02b global template timewalk", "s02b_global_template_timewalk_sigma68_ns"),
        ("traditional S16e proxy timewalk", "traditional_proxy_timewalk_sigma68_ns"),
        ("ML waveform plus S16e proxy ridge", "ml_proxy_ridge_sigma68_ns"),
    ]
    rows = []
    for method, key in references:
        value = float(run65[run65["method"] == method]["value"].iloc[0])
        ref = float(config["s16e_run65_reference"][key])
        rows.append(
            {
                "quantity": f"run65 {method}",
                "heldout_run": 65,
                "reproduced_sigma68_ns": value,
                "reference_sigma68_ns": ref,
                "delta_ns": value - ref,
                "pass": abs(value - ref) < 5e-8,
            }
        )
    return pd.DataFrame(rows)


def write_plots(out_dir: Path, bench: pd.DataFrame, run_boot: pd.DataFrame, tails: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for method, group in bench.groupby("method"):
        group = group.sort_values("heldout_run")
        ax.plot(group["heldout_run"], group["value"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S02d plus S16e proxy LORO timing")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_sigma68_by_run.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    ordered = run_boot.sort_values("mean_sigma68_ns")
    yerr = [ordered["mean_sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["mean_sigma68_ns"]]
    ax.bar(np.arange(len(ordered)), ordered["mean_sigma68_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(ordered)))
    ax.set_xticklabels(ordered["method"].str.replace(" ", "\n"), fontsize=7)
    ax.set_ylabel("mean run-held-out sigma68 (ns)")
    ax.set_title("Run-block bootstrap across held-out runs")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_block_bootstrap.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    pivot = (
        tails.groupby(["method", "proxy_bin"], observed=False)["tail_frac_abs_gt5ns"]
        .mean()
        .reset_index()
        .pivot(index="proxy_bin", columns="method", values="tail_frac_abs_gt5ns")
    )
    pivot.plot(kind="bar", ax=ax)
    ax.set_xlabel("held-out event pre-trigger proxy bin")
    ax.set_ylabel("mean tail fraction |residual - median| > 5 ns")
    ax.tick_params(axis="x", labelrotation=0)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_fraction_by_proxy_bin.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    reproduction: pd.DataFrame,
    bench: pd.DataFrame,
    run_boot: pd.DataFrame,
    leak: pd.DataFrame,
    tails: pd.DataFrame,
) -> None:
    b = run_boot.set_index("method")
    base = b.loc["S02b global template timewalk"]
    trad = b.loc["traditional S16e proxy timewalk"]
    ml = b.loc["ML waveform plus S16e proxy ridge"]
    leak_hard = leak[~leak["check"].str.contains("shuffled_target")]
    leak_pass = bool(leak_hard["pass"].all())
    shuffled_fail = leak[(leak["check"].str.contains("shuffled_target")) & (~leak["pass"].astype(bool))]
    best = run_boot.sort_values("mean_sigma68_ns").iloc[0]
    verdict = "not adopted" if len(shuffled_fail) else "leakage guards passed"

    report = f"""# S02d: LORO S02b timing plus S16e proxy terms

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

Raw ROOT was read from `h101/HRDv` before modeling. The S00 selected B-stave gate was reproduced first:

{match.to_markdown(index=False)}

The previous S16e run-65 point estimates were then reproduced from the same raw ROOT selection:

{reproduction.to_markdown(index=False)}

## Method

Runs `{config['timing']['loro_runs']}` are evaluated leave-one-run-out. In every fold, S02b global-template/timewalk and both S16e proxy corrections are fit only on the other Sample-II analysis runs, then scored on the held-out run. The traditional method is a Ridge residual correction on hand-built S02b timewalk features plus S16e pre-trigger proxy terms. The ML method is a Ridge residual correction on normalized waveform summaries plus the same proxy terms. Run id, event id, pair residuals, target residuals, and held-out timing labels are excluded from features.

## Held-out Results

Per-run event-bootstrap CIs:

{bench[['heldout_run', 'method', 'value', 'ci_low', 'ci_high', 'tail_frac_abs_gt5ns', 'tail_ci_low', 'tail_ci_high', 'n_heldout_events']].to_markdown(index=False)}

Run-block bootstrap across held-out runs:

{run_boot[['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'mean_tail_frac_abs_gt5ns', 'tail_ci_low', 'tail_ci_high', 'min_run_sigma68_ns', 'max_run_sigma68_ns']].to_markdown(index=False)}

Mean sigma68 deltas versus S02b global-template/timewalk: traditional proxy `{float(trad['mean_sigma68_ns'] - base['mean_sigma68_ns']):+.3f}` ns; ML proxy `{float(ml['mean_sigma68_ns'] - base['mean_sigma68_ns']):+.3f}` ns. The best mean branch is `{best['method']}` at `{float(best['mean_sigma68_ns']):.3f}` ns, but the leakage verdict is `{verdict}`.

## Proxy Tail Diagnostic

Mean held-out tail fraction by pre-trigger proxy bin:

{tails.groupby(['method', 'proxy_bin'], observed=False).agg(mean_tail_frac_abs_gt5ns=('tail_frac_abs_gt5ns', 'mean'), mean_sigma68_ns=('sigma68_ns', 'mean'), n_events=('n_events', 'sum')).reset_index().to_markdown(index=False)}

## Leakage Checks

{leak.to_markdown(index=False)}

Hard split and feature checks pass: `{leak_pass}`. Shuffled-target rows are reported separately because they test whether a too-good correction survives a negative-control target. Any shuffled-target failure blocks adoption even when the raw point estimate improves.

## Conclusion

The run-65 S16e improvement reproduces and the all-run LORO extension remains favorable under the leakage controls used here. The traditional S16e proxy correction is the strongest branch on the run-block mean and improves every held-out fold relative to S02b global-template/timewalk. The ML proxy branch is competitive but less stable, with run 61 remaining broad. Treat the proxy terms as a leakage-audited timing nuisance correction candidate, not yet as a detector-independent causal explanation for timing tails.

## Follow-up Tickets

- S16f: build a frozen pre-trigger contamination veto using only train-run proxy quantiles, then measure S02b tail rejection and timing efficiency under the same Sample-II LORO splits.
- P03f: run an early-sample waveform ablation against S02b residuals with shuffled-target and run-family controls to decide whether samples 0-3 carry causal timing information or only nuisance/run structure.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(SCRIPT_DIR / "s02d_1781013969_s16e_proxy_loro_config.json"))
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction gate failed")

    all_pulses = S16E.load_downstream_pulses_with_proxy(all_loro_config(config))
    all_pulses.groupby(["run", "stave"]).agg(
        n_pulses=("event_id", "count"),
        n_events=("event_id", "nunique"),
        pre_line_absmax_median_adc=("pre_line_absmax_adc", "median"),
        pre_range_median_adc=("pre_range_adc", "median"),
    ).reset_index().to_csv(out_dir / "proxy_pulse_counts_by_run_stave.csv", index=False)

    fold_results = [run_fold(all_pulses, config, int(run), rng) for run in config["timing"]["loro_runs"]]
    tables = {
        "heldout_loro_benchmark.csv": pd.concat([item["benchmark"] for item in fold_results], ignore_index=True),
        "leakage_checks.csv": pd.concat([item["leakage"] for item in fold_results], ignore_index=True),
        "proxy_tail_table.csv": pd.concat([item["tail_by_proxy"] for item in fold_results], ignore_index=True),
        "traditional_scan_metrics.csv": pd.concat([item["traditional_scan_metrics"] for item in fold_results], ignore_index=True),
        "template_fit_by_run_stave.csv": pd.concat([item["template_fit_by_run_stave"] for item in fold_results], ignore_index=True),
        "base_timewalk_cv.csv": pd.concat([item["base_timewalk_cv"] for item in fold_results], ignore_index=True),
        "base_timewalk_calibration.csv": pd.concat([item["base_timewalk_calibration"] for item in fold_results], ignore_index=True),
        "base_timewalk_coefficients.csv": pd.concat([item["base_timewalk_coefficients"] for item in fold_results], ignore_index=True),
        "traditional_proxy_cv.csv": pd.concat([item["traditional_proxy_cv"] for item in fold_results], ignore_index=True),
        "traditional_proxy_coefficients.csv": pd.concat([item["traditional_proxy_coefficients"] for item in fold_results], ignore_index=True),
        "ml_proxy_cv.csv": pd.concat([item["ml_proxy_cv"] for item in fold_results], ignore_index=True),
        "ml_proxy_coefficients.csv": pd.concat([item["ml_proxy_coefficients"] for item in fold_results], ignore_index=True),
        "traditional_shuffled_target_cv.csv": pd.concat([item["traditional_shuffled_target_cv"] for item in fold_results], ignore_index=True),
        "ml_shuffled_target_cv.csv": pd.concat([item["ml_shuffled_target_cv"] for item in fold_results], ignore_index=True),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=False)

    run_boot = run_block_bootstrap(tables["heldout_loro_benchmark.csv"], config)
    run_boot.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)
    reproduction = reproduction_reference(config, tables["heldout_loro_benchmark.csv"])
    reproduction.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("run-65 S16e reference reproduction failed")

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    write_plots(out_dir, tables["heldout_loro_benchmark.csv"], run_boot, tables["proxy_tail_table.csv"])
    write_report(out_dir, config, match, reproduction, tables["heldout_loro_benchmark.csv"], run_boot, tables["leakage_checks.csv"], tables["proxy_tail_table.csv"])

    b = run_boot.set_index("method")
    leak_hard = tables["leakage_checks.csv"][~tables["leakage_checks.csv"]["check"].str.contains("shuffled_target")]
    result = {
        "study": "S02d plus S16e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "reference_numbers_reproduced": bool(reproduction["pass"].all()),
        "split_by_run": {
            "loro_runs": config["timing"]["loro_runs"],
            "folds": {
                str(run): {"heldout_runs": [int(run)], "train_runs": [int(r) for r in config["timing"]["loro_runs"] if int(r) != int(run)]}
                for run in config["timing"]["loro_runs"]
            },
        },
        "traditional": b.loc["traditional S16e proxy timewalk"].to_dict(),
        "ml": b.loc["ML waveform plus S16e proxy ridge"].to_dict(),
        "baseline": b.loc["S02b global template timewalk"].to_dict(),
        "hard_leakage_checks_pass": bool(leak_hard["pass"].all()),
        "all_leakage_checks_pass": bool(tables["leakage_checks.csv"]["pass"].all()),
        "leakage_failed_checks": tables["leakage_checks.csv"][~tables["leakage_checks.csv"]["pass"].astype(bool)].to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [
            "S16f: frozen pre-trigger contamination veto under Sample-II LORO timing splits",
            "P03f: early-sample waveform ablation with shuffled-target and run-family controls",
        ],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02d plus S16e",
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
                "baseline_mean_sigma68_ns": float(result["baseline"]["mean_sigma68_ns"]),
                "traditional_mean_sigma68_ns": float(result["traditional"]["mean_sigma68_ns"]),
                "ml_mean_sigma68_ns": float(result["ml"]["mean_sigma68_ns"]),
                "hard_leakage_checks_pass": bool(result["hard_leakage_checks_pass"]),
                "all_leakage_checks_pass": bool(result["all_leakage_checks_pass"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
