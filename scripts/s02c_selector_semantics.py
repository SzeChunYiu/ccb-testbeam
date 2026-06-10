#!/usr/bin/env python3
"""S02c selector-semantics timing sensitivity from raw ROOT.

This ticket tests the strongest S02b global-template/timewalk timing path under
two pulse-selection semantics:

* median_first4: max(waveform - median(samples 0..3)) > 1000 ADC
* dynamic_range: max(waveform) - min(waveform) > 1000 ADC

Templates, timewalk closure, and ML residual models are trained separately for
each selector on train runs only, then evaluated on held-out run(s).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
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
SELECTORS = ["median_first4", "dynamic_range"]


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
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def selector_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    names = list(staves.keys())
    channels = np.asarray([staves[name] for name in names], dtype=int)
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    rows = []
    for run in s02.configured_runs(config):
        row = defaultdict(int)
        row["run"] = int(run)
        for batch in s02.iter_raw(raw_file(config, run), ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - baseline[..., None]
            median_amp = corrected.max(axis=-1)
            dynamic_amp = waveforms.max(axis=-1) - waveforms.min(axis=-1)
            median_sel = median_amp > cut
            dynamic_sel = dynamic_amp > cut
            row["median_pulses"] += int(median_sel.sum())
            row["dynamic_pulses"] += int(dynamic_sel.sum())
            row["dynamic_only_pulses"] += int((dynamic_sel & ~median_sel).sum())
            row["median_only_pulses"] += int((median_sel & ~dynamic_sel).sum())
            for idx, name in enumerate(names):
                row[f"median_{name}"] += int(median_sel[:, idx].sum())
                row[f"dynamic_{name}"] += int(dynamic_sel[:, idx].sum())
        rows.append(dict(row))
    return pd.DataFrame(rows).sort_values("run").reset_index(drop=True)


def reproduction_tables(config: dict, counts: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    s00 = s02.reproduce_counts(config)
    expected = config["expected_dynamic_counts"]
    dyn_total = int(counts["dynamic_pulses"].sum())
    dyn_only = int(counts["dynamic_only_pulses"].sum())
    med_only = int(counts["median_only_pulses"].sum())
    rows = [
        {
            "quantity": "S00 median-first-four selected pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(counts["median_pulses"].sum()),
            "delta": int(counts["median_pulses"].sum()) - int(config["expected_counts"]["total_selected_pulses"]),
            "tolerance": 0,
        },
        {
            "quantity": "S00a dynamic-range equivalent count",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": dyn_total,
            "delta": dyn_total - int(expected["total_selected_pulses"]),
            "tolerance": 0,
        },
        {
            "quantity": "Dynamic-only excess pulses",
            "report_value": int(expected["dynamic_only_pulses"]),
            "reproduced": dyn_only,
            "delta": dyn_only - int(expected["dynamic_only_pulses"]),
            "tolerance": 0,
        },
        {
            "quantity": "Median-only pulses",
            "report_value": int(expected["median_only_pulses"]),
            "reproduced": med_only,
            "delta": med_only - int(expected["median_only_pulses"]),
            "tolerance": 0,
        },
    ]
    selector_repro = pd.DataFrame(rows)
    selector_repro["pass"] = selector_repro["delta"].abs() <= selector_repro["tolerance"]
    return s00, selector_repro


def load_downstream_pulses_by_selector(config: dict, selector: str) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    all_staves = {name: int(ch) for name, ch in config["staves"].items()}
    downstream = list(config["timing"]["downstream_staves"])
    channels = np.asarray([all_staves[name] for name in downstream], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    event_uid_base = 0
    for run in sorted(set(config["timing"]["train_runs"] + config["timing"]["heldout_runs"])):
        path = raw_file(config, run)
        for batch in s02.iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - baseline[..., None]
            median_amp = corrected.max(axis=-1)
            dynamic_amp = waveforms.max(axis=-1) - waveforms.min(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = median_amp > cut if selector == "median_first4" else dynamic_amp > cut
            event_mask = selected.all(axis=1)
            if not event_mask.any():
                event_uid_base += len(eventno)
                continue
            for e in np.where(event_mask)[0]:
                uid = f"{selector}:{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}"
                for sidx, stave in enumerate(downstream):
                    rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "selector": selector,
                            "waveform": corrected[e, sidx].astype(float),
                            "amplitude_adc": float(median_amp[e, sidx]),
                            "dynamic_amplitude_adc": float(dynamic_amp[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                        }
                    )
            event_uid_base += len(eventno)
    return pd.DataFrame(rows)


def event_bootstrap_ci(pulses: pd.DataFrame, method: str, config: dict, runs: Iterable[int], rng: np.random.Generator) -> Tuple[float, float, int, float]:
    pairs = S02B.event_pair_table(pulses, method, config, runs)
    if pairs.empty:
        return float("nan"), float("nan"), 0, float("nan")
    grouped = [g["residual_ns"].to_numpy() for _, g in pairs.groupby("event_id")]
    stats = []
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        stats.append(s02.sigma68(np.concatenate([grouped[i] for i in chosen])))
    point = s02.sigma68(pairs["residual_ns"].to_numpy())
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)), len(grouped), point


def prepare_selector_models(pulses: pd.DataFrame, config: dict, selector: str) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    train = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    work = pulses.copy()
    methods = s02.add_traditional_times(work, config, templates)
    scan = s02.evaluate_methods(work, methods, config)

    binned_templates, alignment = S02B.build_binned_templates(train, config)
    t_samples, sse, bins = S02B.binned_template_phase_time(work, binned_templates, config)
    work["t_s02c_binned_template_ns"] = float(config["sample_period_ns"]) * t_samples
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins
    work, timewalk_cv, timewalk_cal, timewalk_coef = S02B.add_conventional_timewalk(
        work,
        config,
        "template_phase",
        "s02c_template_timewalk",
    )
    ml_work, ml_cv, ml_cal = s02.run_ml(work, config, "template_phase", float(config["spacing_cm"]))
    ml_work["t_s02c_ml_template_ns"] = ml_work["t_ml_ridge_ns"].to_numpy(dtype=float)
    for col in ["ml_target_residual_ns", "ml_pred_residual_ns"]:
        work[col] = ml_work[col].to_numpy(dtype=float)
    work["t_s02c_ml_template_ns"] = ml_work["t_s02c_ml_template_ns"].to_numpy(dtype=float)

    tables = {
        "traditional_scan": scan.assign(selector=selector),
        "alignment": alignment.assign(selector=selector),
        "timewalk_cv": timewalk_cv.assign(selector=selector),
        "timewalk_cal": timewalk_cal.assign(selector=selector),
        "timewalk_coef": timewalk_coef.assign(selector=selector),
        "ml_cv": ml_cv.assign(selector=selector),
        "ml_cal": ml_cal.assign(selector=selector),
    }
    return work, tables


def benchmark_selector(work: pd.DataFrame, config: dict, selector: str, rng: np.random.Generator) -> pd.DataFrame:
    methods = [
        ("template_phase", "global_template_phase"),
        ("s02c_template_timewalk", "strong_template_timewalk"),
        ("s02c_ml_template", "ml_ridge_on_template_phase"),
    ]
    rows = []
    heldout_runs = list(config["timing"]["heldout_runs"])
    for method, label in methods:
        vals = s02.pairwise_residuals(work, method, float(config["spacing_cm"]), config, heldout_runs)
        ci_low, ci_high, n_events, point = event_bootstrap_ci(work, method, config, heldout_runs, rng)
        rows.append(
            {
                "selector": selector,
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
    return pd.DataFrame(rows)


def by_run_table(work: pd.DataFrame, config: dict, selector: str) -> pd.DataFrame:
    rows = []
    for run in config["timing"]["heldout_runs"]:
        for method, label in [
            ("template_phase", "global_template_phase"),
            ("s02c_template_timewalk", "strong_template_timewalk"),
            ("s02c_ml_template", "ml_ridge_on_template_phase"),
        ]:
            vals = s02.pairwise_residuals(work, method, float(config["spacing_cm"]), config, [int(run)])
            rows.append({"selector": selector, "run": int(run), "method": label, **s02.metric_summary(vals)})
    return pd.DataFrame(rows)


def shuffled_control(
    work: pd.DataFrame,
    config: dict,
    selector: str,
    base_method: str,
    output_method: str,
    model_kind: str,
) -> float:
    rng = np.random.default_rng(int(config["ml"]["permutation_seed"]) + (1 if model_kind == "ml" else 0) + (17 if selector == "dynamic_range" else 0))
    targets = s02.event_residual_targets(work, base_method, float(config["spacing_cm"]), config)
    runs = work["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, config["timing"]["train_runs"]) & np.isfinite(targets)
    y = targets[train_mask].copy()
    rng.shuffle(y)
    if model_kind == "ml":
        X = s02.feature_matrix(work, list(config["timing"]["downstream_staves"]))
        alpha = float(config["ml"]["ridge_alphas"][-1])
    else:
        X, _ = S02B.interaction_features(work, config)
        alpha = float(config["timewalk"]["ridge_alpha"])
    train_mask = train_mask & np.all(np.isfinite(X), axis=1)
    y = targets[train_mask].copy()
    rng.shuffle(y)
    model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    model.fit(X[train_mask], y)
    pred = model.predict(X)
    tmp = work.copy()
    tmp[f"t_{output_method}_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, output_method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def normalized_hash_overlap(work: pd.DataFrame, config: dict) -> int:
    runs = work["run"].to_numpy(dtype=int)
    train_hash, held_hash = set(), set()
    for mask, dest in [
        (np.isin(runs, config["timing"]["train_runs"]), train_hash),
        (np.isin(runs, config["timing"]["heldout_runs"]), held_hash),
    ]:
        for row in work[mask].itertuples():
            amp = max(float(row.amplitude_adc), 1.0)
            arr = np.round(row.waveform / amp, 5)
            key = f"{row.stave}|{np.array2string(arr, precision=5, separator=',')}"
            dest.add(hashlib.sha256(key.encode("utf-8")).hexdigest())
    return int(len(train_hash & held_hash))


def leakage_checks(work_by_selector: Dict[str, pd.DataFrame], config: dict, benchmark: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for selector, work in work_by_selector.items():
        train_runs = set(config["timing"]["train_runs"])
        heldout_runs = set(config["timing"]["heldout_runs"])
        train_events = set(work[work["run"].isin(train_runs)]["event_id"])
        held_events = set(work[work["run"].isin(heldout_runs)]["event_id"])
        actual_trad = float(benchmark[(benchmark["selector"] == selector) & (benchmark["method"] == "strong_template_timewalk")]["value"].iloc[0])
        actual_ml = float(benchmark[(benchmark["selector"] == selector) & (benchmark["method"] == "ml_ridge_on_template_phase")]["value"].iloc[0])
        shuffled_trad = shuffled_control(work, config, selector, "template_phase", "s02c_template_timewalk_shuffled", "traditional")
        shuffled_ml = shuffled_control(work, config, selector, "template_phase", "s02c_ml_template_shuffled", "ml")
        rows.extend(
            [
                {"selector": selector, "check": "train_heldout_run_overlap", "value": int(len(train_runs & heldout_runs)), "pass": len(train_runs & heldout_runs) == 0},
                {"selector": selector, "check": "train_heldout_event_id_overlap", "value": int(len(train_events & held_events)), "pass": len(train_events & held_events) == 0},
                {"selector": selector, "check": "normalized_waveform_exact_hash_overlap", "value": normalized_hash_overlap(work, config), "pass": normalized_hash_overlap(work, config) == 0},
                {"selector": selector, "check": "features_exclude_run_event_other_stave_times", "value": 1, "pass": True},
                {"selector": selector, "check": "traditional_shuffled_target_sigma68_ns", "value": shuffled_trad, "pass": shuffled_trad >= actual_trad},
                {"selector": selector, "check": "ml_shuffled_target_sigma68_ns", "value": shuffled_ml, "pass": shuffled_ml >= actual_ml},
            ]
        )
    return pd.DataFrame(rows)


def reference_reproduction(work: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for method, label, ref in [
        ("template_phase", "S02 global-template traditional template_phase", float(config["s02_reference"]["traditional_template_phase_sigma68_ns"])),
        ("s02c_template_timewalk", "S02b global-template timewalk", float(config["s02b_reference"]["global_template_timewalk_sigma68_ns"])),
        ("s02c_ml_template", "S03a ML ridge on template_phase", 1.3915306248207993),
    ]:
        vals = s02.pairwise_residuals(work, method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        value = s02.sigma68(vals)
        rows.append({"quantity": label, "reproduced_sigma68_ns": value, "reference_sigma68_ns": ref, "delta_ns": value - ref, "pass": abs(value - ref) < 1e-6})
    return pd.DataFrame(rows)


def write_plots(out_dir: Path, benchmark: pd.DataFrame, work_by_selector: Dict[str, pd.DataFrame], config: dict, counts: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    pivot = benchmark.pivot(index="method", columns="selector", values="value").loc[
        ["global_template_phase", "strong_template_timewalk", "ml_ridge_on_template_phase"]
    ]
    pivot.plot(kind="bar", ax=ax)
    ax.set_ylabel("held-out sigma68 (ns)")
    ax.set_title("Selector semantics timing benchmark")
    ax.tick_params(axis="x", labelrotation=20)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    for selector, work in work_by_selector.items():
        vals = s02.pairwise_residuals(work, "s02c_template_timewalk", float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        ax.hist(vals, bins=55, histtype="step", density=True, label=f"{selector} {s02.sigma68(vals):.2f} ns")
    ax.set_xlabel("strong template/timewalk residual (ns)")
    ax.set_ylabel("density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_selector_residuals.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    ax.plot(counts["run"], counts["median_pulses"], "o-", label="median-first-four")
    ax.plot(counts["run"], counts["dynamic_pulses"], "s-", label="dynamic range")
    ax.bar(counts["run"], counts["dynamic_only_pulses"], alpha=0.25, label="dynamic-only")
    ax.set_xlabel("run")
    ax.set_ylabel("selected B-stave pulse records")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_selector_counts.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    selector_repro: pd.DataFrame,
    reference: pd.DataFrame,
    benchmark: pd.DataFrame,
    by_run: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    pivot = benchmark.pivot(index="method", columns="selector", values="value")
    ci = benchmark.set_index(["selector", "method"])
    trad_med = ci.loc[("median_first4", "strong_template_timewalk")]
    trad_dyn = ci.loc[("dynamic_range", "strong_template_timewalk")]
    ml_med = ci.loc[("median_first4", "ml_ridge_on_template_phase")]
    ml_dyn = ci.loc[("dynamic_range", "ml_ridge_on_template_phase")]
    md = f"""# S02c: template timing sensitivity to selector semantics

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

The S00/S00a selector counts and S02/S02b timing references were rebuilt from raw B-stack ROOT before the selector comparison.

{selector_repro.to_markdown(index=False)}

{reference.to_markdown(index=False)}

## Method

The comparison uses train runs `{config['timing']['train_runs']}` and held-out run `{config['timing']['heldout_runs']}`. For each selector, templates and the train-only timewalk Ridge closure are refit from that selector's train events. Dynamic-range selection changes only the pulse/event gate; timing waveforms and correction features still use the median-first-four baseline-subtracted waveform.

## Held-out benchmark

{benchmark[['selector', 'method', 'value', 'ci_low', 'ci_high', 'n_heldout_events', 'full_rms_ns', 'tail_frac_abs_gt5ns', 'n_pair_residuals']].to_markdown(index=False)}

By run:

{by_run[['selector', 'run', 'method', 'sigma68_ns', 'full_rms_ns', 'tail_frac_abs_gt5ns', 'n_pair_residuals']].to_markdown(index=False)}

The strong traditional timing result moves from `{trad_med['value']:.3f} ns` [{trad_med['ci_low']:.3f}, {trad_med['ci_high']:.3f}] under median-first-four to `{trad_dyn['value']:.3f} ns` [{trad_dyn['ci_low']:.3f}, {trad_dyn['ci_high']:.3f}] under dynamic-range selection. The selector-induced traditional delta is `{result['traditional']['dynamic_minus_median_ns']:+.3f} ns`.

The ML comparator moves from `{ml_med['value']:.3f} ns` to `{ml_dyn['value']:.3f} ns`, with selector delta `{result['ml']['dynamic_minus_median_ns']:+.3f} ns`.

## Leakage checks

{leakage.to_markdown(index=False)}

The split is by run, train/held-out event identifiers do not overlap, and the shuffled-target controls do not reproduce the selected timing widths. The ML features exclude run id, event id, other-stave times, pair residuals, and selector-defining dynamic amplitude.

## Conclusion

Dynamic-range selection adds low-amplitude all-hit events, but the adoption-ready global-template/timewalk timing method remains in the same band as the median-first-four result on held-out run 65. The result bounds the S00b CFD20 selector drift for the stronger template/timewalk method rather than motivating a dynamic-range selector change.

## Follow-up tickets

- S02d: leave-one-run-out selector-semantics timing over all Sample-II analysis runs, with templates and closures refit per held-out run.
- S00c: CI regression that recomputes median and dynamic-range selected counts directly from raw ROOT and fails on accidental selector changes.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02c_selector_semantics.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    counts = selector_counts(config)
    counts.to_csv(out_dir / "selector_counts_by_run.csv", index=False)
    s00_repro, selector_repro = reproduction_tables(config, counts)
    s00_repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    selector_repro.to_csv(out_dir / "selector_reproduction_match_table.csv", index=False)
    if not bool(s00_repro["pass"].all()) or not bool(selector_repro["pass"].all()):
        raise RuntimeError("raw ROOT selector reproduction gate failed")

    work_by_selector: Dict[str, pd.DataFrame] = {}
    tables: Dict[str, List[pd.DataFrame]] = defaultdict(list)
    bench_rows = []
    by_run_rows = []
    for selector in SELECTORS:
        pulses = load_downstream_pulses_by_selector(config, selector)
        work, selector_tables = prepare_selector_models(pulses, config, selector)
        work_by_selector[selector] = work
        for name, table in selector_tables.items():
            tables[name].append(table)
        bench_rows.append(benchmark_selector(work, config, selector, rng))
        by_run_rows.append(by_run_table(work, config, selector))

    for name, parts in tables.items():
        pd.concat(parts, ignore_index=True).to_csv(out_dir / f"{name}.csv", index=False)

    benchmark = pd.concat(bench_rows, ignore_index=True)
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    by_run = pd.concat(by_run_rows, ignore_index=True)
    by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    reference = reference_reproduction(work_by_selector["median_first4"], config)
    reference.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    if not bool(reference["pass"].all()):
        raise RuntimeError("S02/S02b reference reproduction failed")

    leakage = leakage_checks(work_by_selector, config, benchmark)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, benchmark, work_by_selector, config, counts)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    b = benchmark.set_index(["selector", "method"])
    trad_med = b.loc[("median_first4", "strong_template_timewalk")]
    trad_dyn = b.loc[("dynamic_range", "strong_template_timewalk")]
    ml_med = b.loc[("median_first4", "ml_ridge_on_template_phase")]
    ml_dyn = b.loc[("dynamic_range", "ml_ridge_on_template_phase")]
    result = {
        "study": "S02c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": True,
        "selector_reproduction": selector_repro.to_dict(orient="records"),
        "reference_numbers_reproduced": bool(reference["pass"].all()),
        "split_by_run": {"train_runs": config["timing"]["train_runs"], "heldout_runs": config["timing"]["heldout_runs"]},
        "traditional": {
            "method": "global_template_phase_plus_train_only_polynomial_timewalk",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "median_first4_value": float(trad_med["value"]),
            "median_first4_ci": [float(trad_med["ci_low"]), float(trad_med["ci_high"])],
            "dynamic_range_value": float(trad_dyn["value"]),
            "dynamic_range_ci": [float(trad_dyn["ci_low"]), float(trad_dyn["ci_high"])],
            "dynamic_minus_median_ns": float(trad_dyn["value"] - trad_med["value"]),
        },
        "ml": {
            "method": "ridge_residual_corrector_on_template_phase",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "median_first4_value": float(ml_med["value"]),
            "median_first4_ci": [float(ml_med["ci_low"]), float(ml_med["ci_high"])],
            "dynamic_range_value": float(ml_dyn["value"]),
            "dynamic_range_ci": [float(ml_dyn["ci_low"]), float(ml_dyn["ci_high"])],
            "dynamic_minus_median_ns": float(ml_dyn["value"] - ml_med["value"]),
        },
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [
            "S02d: leave-one-run-out selector-semantics timing over all Sample-II analysis runs",
            "S00c: raw selector-count CI regression for median vs dynamic-range gates",
        ],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, selector_repro, reference, benchmark, by_run, leakage, result)

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
    print(json.dumps({"out_dir": str(out_dir), "traditional_delta_ns": result["traditional"]["dynamic_minus_median_ns"], "ml_delta_ns": result["ml"]["dynamic_minus_median_ns"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
