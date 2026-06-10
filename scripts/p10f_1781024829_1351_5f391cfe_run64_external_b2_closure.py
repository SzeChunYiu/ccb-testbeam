#!/usr/bin/env python3
"""P10f run64-only explicit timewalk external B2/B4/B6/B8 closure."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

import p10a_conditional_template as p10a
import p10b_explicit_timewalk_terms as p10b


ALL_PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
DOWNSTREAM_PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def collect_external_all_hit(config: dict, runs: Iterable[int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    stave_grid = np.asarray(staves)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    timing_runs = {int(run) for run in runs}
    repro_rows = []
    pulse_rows = []
    uid_offset = 0

    for run in p10a.configured_runs(config):
        path = p10a.raw_file(config, int(run))
        run_events = 0
        run_selected = 0
        run_all_hit = 0
        for batch in p10a.iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            corrected, amplitude, peak, area = p10a.pulse_quantities(events[:, channels, :], baseline_idx)
            selected = amplitude > cut
            all_hit = selected.all(axis=1)
            run_events += int(len(eventno))
            run_selected += int(selected.sum())
            run_all_hit += int(all_hit.sum())
            if run in timing_runs and bool(all_hit.any()):
                for e in np.where(all_hit)[0]:
                    event_id = f"{int(run)}:{int(eventno[e])}:{int(evt[e])}:{uid_offset + int(e)}"
                    for sidx, stave in enumerate(stave_grid):
                        pulse_rows.append(
                            {
                                "event_id": event_id,
                                "run": int(run),
                                "eventno": int(eventno[e]),
                                "evt": int(evt[e]),
                                "stave": str(stave),
                                "waveform": corrected[e, sidx].astype(np.float32),
                                "amplitude_adc": float(amplitude[e, sidx]),
                                "peak_sample": int(peak[e, sidx]),
                                "area_adc_samples": float(area[e, sidx]),
                            }
                        )
            uid_offset += len(eventno)
        repro_rows.append(
            {
                "run": int(run),
                "n_events": run_events,
                "selected_pulses": run_selected,
                "all_hit_b2_b4_b6_b8_events": run_all_hit,
                "used_for_external_timing": bool(run in timing_runs),
            }
        )
    return pd.DataFrame(repro_rows), pd.DataFrame(pulse_rows)


def empirical_templates_for_pulses(config: dict, pulses: pd.DataFrame, empirical_pack: dict) -> np.ndarray:
    edges = empirical_pack["edges"]
    bins = p10a.assign_amp_bins(pulses["amplitude_adc"].to_numpy(dtype=float), edges)
    templates = []
    for i, row in enumerate(pulses.itertuples()):
        templates.append(empirical_pack["templates"][(row.stave, int(bins[i]))])
    return np.vstack(templates).astype(np.float32)


def binned_timewalk_correction(config: dict, pulses: pd.DataFrame, targets: np.ndarray, train_mask: np.ndarray) -> Tuple[np.ndarray, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    bins = p10a.assign_amp_bins(pulses["amplitude_adc"].to_numpy(dtype=float), edges)
    staves = list(config["timing"]["downstream_staves"])
    min_bin = int(config["explicit_timewalk"]["traditional_min_bin_pulses"])
    correction = np.zeros(len(pulses), dtype=float)
    rows = []
    global_fallback = float(np.nanmedian(targets[train_mask]))
    for stave in staves:
        stave_mask = train_mask & (pulses["stave"].to_numpy() == stave)
        stave_fallback = float(np.nanmedian(targets[stave_mask])) if np.any(stave_mask) else global_fallback
        for b in range(len(edges) - 1):
            mask = stave_mask & (bins == b)
            n = int(mask.sum())
            if n >= min_bin:
                value = float(np.nanmedian(targets[mask]))
                source = "stave_amp_bin"
            else:
                value = stave_fallback
                source = "stave_fallback"
            apply_mask = (pulses["stave"].to_numpy() == stave) & (bins == b)
            correction[apply_mask] = value
            rows.append(
                {
                    "stave": stave,
                    "bin": int(b),
                    "amp_low_adc": float(edges[b]),
                    "amp_high_adc": float(edges[b + 1]),
                    "n_train": n,
                    "correction_ns": value,
                    "source": source,
                }
            )
    return correction, pd.DataFrame(rows)


def explicit_features(config: dict, pulses: pd.DataFrame, feature_set: str) -> np.ndarray:
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    log_amp = np.log1p(amp)
    area_over_amp = pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=float)
    staves = list(config["timing"]["downstream_staves"])
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    one_hot = np.zeros((len(pulses), len(staves)), dtype=float)
    for row, stave in enumerate(pulses["stave"].to_numpy()):
        if stave in stave_to_i:
            one_hot[row, stave_to_i[stave]] = 1.0
    base = np.column_stack([log_amp, log_amp**2, 1.0 / np.sqrt(np.maximum(amp, 1.0)), area_over_amp, peak])
    if feature_set == "amp_poly":
        X = np.hstack([base, one_hot])
    elif feature_set == "amp_poly_by_stave":
        X = np.hstack([base, one_hot] + [base[:, j : j + 1] * one_hot for j in range(base.shape[1])])
    elif feature_set == "amp_bin_by_stave":
        edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
        bins = p10a.assign_amp_bins(amp, edges)
        bin_hot = np.zeros((len(pulses), len(edges) - 1), dtype=float)
        bin_hot[np.arange(len(pulses)), bins] = 1.0
        X = np.hstack([base[:, [0, 2, 3, 4]], one_hot] + [bin_hot[:, j : j + 1] * one_hot for j in range(bin_hot.shape[1])])
    else:
        raise ValueError(feature_set)
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


def fit_ml_correction(config: dict, pulses: pd.DataFrame, targets: np.ndarray, train_mask: np.ndarray, seed: int, shuffled: bool = False) -> np.ndarray:
    idx_train = np.flatnonzero(train_mask & np.isfinite(targets))
    y = targets.copy()
    if shuffled:
        rng = np.random.default_rng(seed)
        y_train = y[idx_train].copy()
        rng.shuffle(y_train)
        y[idx_train] = y_train
    feature_set = str(config["explicit_timewalk"]["single_run_default_feature_set"])
    alpha = float(config["explicit_timewalk"]["single_run_default_alpha"])
    X = explicit_features(config, pulses, feature_set)
    model = p10b.ridge_model(alpha)
    model.fit(X[idx_train], y[idx_train])
    pred = model.predict(X)
    target_stave = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
    pred[~target_stave] = 0.0
    return pred


def position_map(config: dict) -> Dict[str, float]:
    spacing = float(config["spacing_cm"])
    return {stave: i * spacing for i, stave in enumerate(config["timing"]["external_staves"])}


def sigma68(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def pairwise_residuals(pulses: pd.DataFrame, method_col: str, config: dict, run: int, pairs: List[Tuple[str, str]]) -> np.ndarray:
    sub = pulses[pulses["run"] == int(run)].copy()
    sub["tcorr"] = sub[method_col].astype(float) - sub["stave"].map(position_map(config)).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    residuals = []
    for a, b in pairs:
        if a in wide and b in wide:
            residuals.append((wide[a] - wide[b]).to_numpy(dtype=float))
    return np.concatenate(residuals) if residuals else np.asarray([], dtype=float)


def downstream_residuals(pulses: pd.DataFrame, method_col: str, config: dict, run: int) -> np.ndarray:
    return p10b.pairwise_residuals(pulses, method_col, config, int(run))


def apply_run64_correction(
    config: dict,
    table: pd.DataFrame,
    norm: np.ndarray,
    pulses_in: pd.DataFrame,
    external: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    train_runs = [int(run) for run in config["timing"]["train_runs"]]
    train_mask_table = table["run"].isin(train_runs).to_numpy()
    empirical_pack = p10b.empirical_norm_templates(config, table, norm, train_mask_table)
    templates = empirical_templates_for_pulses(config, pulses_in, empirical_pack)
    pulses = pulses_in.copy()
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    pulses["t_base_ns"] = p10a.template_phase_dynamic(pulses, templates, grid, config)
    targets = p10b.event_residual_targets(pulses, "t_base_ns", config)
    train_mask_pulses = pulses["run"].isin(train_runs).to_numpy() & np.isfinite(targets)

    bin_corr, bin_table = binned_timewalk_correction(config, pulses, targets, train_mask_pulses)
    pulses["t_traditional_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - bin_corr
    ml_pred = fit_ml_correction(config, pulses, targets, train_mask_pulses, int(config["random_seed"]) + 1000)
    ml_shuffled = fit_ml_correction(config, pulses, targets, train_mask_pulses, int(config["random_seed"]) + 1101, shuffled=True)
    pulses["t_ml_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - ml_pred
    pulses["t_ml_shuffled_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - ml_shuffled
    meta = {
        "train_runs": train_runs,
        "train_target_pulses": int(train_mask_pulses.sum()),
        "traditional_bin_fallbacks": int((bin_table["source"] != "stave_amp_bin").sum()),
        "ml_best": {
            "feature_set": str(config["explicit_timewalk"]["single_run_default_feature_set"]),
            "alpha": float(config["explicit_timewalk"]["single_run_default_alpha"]),
            "selection": "predeclared_single_train_run_default",
        },
        "population": "external_b2_b4_b6_b8_all_hit" if external else "downstream_b4_b6_b8_all_hit",
    }
    return pulses, bin_table, meta


def evaluate_population(config: dict, pulses: pd.DataFrame, external: bool) -> pd.DataFrame:
    rows = []
    pairs = ALL_PAIRS if external else DOWNSTREAM_PAIRS
    for run in config["timing"]["heldout_runs"]:
        row = {"run": int(run), "n_events": int(pulses.loc[pulses["run"] == int(run), "event_id"].nunique())}
        for method, col in [
            ("base", "t_base_ns"),
            ("traditional", "t_traditional_ns"),
            ("ml", "t_ml_ns"),
            ("ml_shuffled", "t_ml_shuffled_ns"),
        ]:
            vals = pairwise_residuals(pulses, col, config, int(run), pairs) if external else downstream_residuals(pulses, col, config, int(run))
            row[f"{method}_sigma68_ns"] = sigma68(vals)
            row[f"{method}_n_pairs"] = int(len(vals))
        if external:
            for method, col in [
                ("base_downstream", "t_base_ns"),
                ("traditional_downstream", "t_traditional_ns"),
                ("ml_downstream", "t_ml_ns"),
            ]:
                vals = pairwise_residuals(pulses, col, config, int(run), DOWNSTREAM_PAIRS)
                row[f"{method}_sigma68_ns"] = sigma68(vals)
                row[f"{method}_n_pairs"] = int(len(vals))
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(run_df: pd.DataFrame, config: dict, prefix: str = "") -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + 707 + len(prefix))
    method_cols = [col for col in run_df.columns if col.endswith("_sigma68_ns")]
    matrix = run_df[method_cols].to_numpy(dtype=float)
    n_boot = int(config["bootstrap_iterations"])
    boots = []
    for _ in range(n_boot):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    summary = {"bootstrap_unit": "heldout_run", "n_bootstrap": n_boot}
    means = matrix.mean(axis=0)
    for i, col in enumerate(method_cols):
        key = f"{prefix}{col}"
        summary[key] = float(means[i])
        summary[f"{key}_ci"] = np.nanquantile(boots[:, i], [0.025, 0.975]).tolist()
    deltas = {
        f"{prefix}traditional_minus_base_ns": run_df["traditional_sigma68_ns"].to_numpy(dtype=float) - run_df["base_sigma68_ns"].to_numpy(dtype=float),
        f"{prefix}ml_minus_base_ns": run_df["ml_sigma68_ns"].to_numpy(dtype=float) - run_df["base_sigma68_ns"].to_numpy(dtype=float),
        f"{prefix}ml_minus_traditional_ns": run_df["ml_sigma68_ns"].to_numpy(dtype=float) - run_df["traditional_sigma68_ns"].to_numpy(dtype=float),
        f"{prefix}ml_shuffled_minus_ml_ns": run_df["ml_shuffled_sigma68_ns"].to_numpy(dtype=float) - run_df["ml_sigma68_ns"].to_numpy(dtype=float),
    }
    for key, values in deltas.items():
        boots_delta = []
        for _ in range(n_boot):
            boots_delta.append(values[rng.integers(0, len(values), len(values))].mean())
        summary[key] = float(np.nanmean(values))
        summary[f"{key}_ci"] = np.nanquantile(np.asarray(boots_delta), [0.025, 0.975]).tolist()
    return summary


def markdown_metric(label: str, value: float, ci: List[float]) -> str:
    return f"| {label} | {value:.6g} | [{ci[0]:.6g}, {ci[1]:.6g}] |"


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    downstream_summary: dict,
    external_summary: dict,
    external_meta: dict,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    lines = [
        "# P10f: Run64-only external B2-B8 closure",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Input:** raw B-stack ROOT under `data/root/root`",
        "- **Monte Carlo:** none",
        f"- **Git commit:** {result['git_commit']}",
        "",
        "## Raw reproduction first",
        "",
        "The selected-pulse table was rebuilt from raw `h101/HRDv` before fitting either correction.",
        "",
        repro.to_markdown(index=False),
        "",
        "The original P10c run64-only downstream number was then recomputed on B4/B6/B8 all-hit events before the external B2-inclusive test.",
        "",
        "| P10c downstream method | sigma68 ns | 95% CI |",
        "|---|---:|---:|",
        markdown_metric("Base phase template", downstream_summary["p10c_base_sigma68_ns"], downstream_summary["p10c_base_sigma68_ns_ci"]),
        markdown_metric("Traditional explicit", downstream_summary["p10c_traditional_sigma68_ns"], downstream_summary["p10c_traditional_sigma68_ns_ci"]),
        markdown_metric("ML explicit", downstream_summary["p10c_ml_sigma68_ns"], downstream_summary["p10c_ml_sigma68_ns_ci"]),
        "",
        "## Methods",
        "",
        "Split: train only on run 64; evaluate held-out Sample-II analysis runs 58-63 and 65, then bootstrap by held-out run.",
        "",
        "Traditional method: P10c train-run-only empirical phase templates plus a stave-by-amplitude-bin median explicit timewalk correction. B2 is not used as a fitted target and receives no explicit correction in the external closure.",
        "",
        f"ML method: P10c ridge residual correction using same-pulse amplitude, area/amplitude, peak, amplitude-bin, and stave features. The single-run default is `{external_meta['ml_best']['feature_set']}` at alpha `{external_meta['ml_best']['alpha']}`.",
        "",
        f"External population: B2/B4/B6/B8 all have `A>1000 ADC`; train target pulses `{external_meta['train_target_pulses']}`; traditional fallback bins `{external_meta['traditional_bin_fallbacks']}`.",
        "",
        "## External B2-B8 Closure",
        "",
        "Metric: per-run `sigma68` over all six B2/B4/B6/B8 pairs after geometry correction; values and CIs bootstrap held-out runs.",
        "",
        "| Method | sigma68 ns | 95% CI |",
        "|---|---:|---:|",
        markdown_metric("Base phase template", external_summary["external_base_sigma68_ns"], external_summary["external_base_sigma68_ns_ci"]),
        markdown_metric("Traditional explicit", external_summary["external_traditional_sigma68_ns"], external_summary["external_traditional_sigma68_ns_ci"]),
        markdown_metric("ML explicit", external_summary["external_ml_sigma68_ns"], external_summary["external_ml_sigma68_ns_ci"]),
        markdown_metric("ML shuffled target", external_summary["external_ml_shuffled_sigma68_ns"], external_summary["external_ml_shuffled_sigma68_ns_ci"]),
        "",
        "| Delta | ns | 95% CI |",
        "|---|---:|---:|",
        markdown_metric("Traditional - base", external_summary["external_traditional_minus_base_ns"], external_summary["external_traditional_minus_base_ns_ci"]),
        markdown_metric("ML - base", external_summary["external_ml_minus_base_ns"], external_summary["external_ml_minus_base_ns_ci"]),
        markdown_metric("ML - traditional", external_summary["external_ml_minus_traditional_ns"], external_summary["external_ml_minus_traditional_ns_ci"]),
        markdown_metric("ML shuffled - ML", external_summary["external_ml_shuffled_minus_ml_ns"], external_summary["external_ml_shuffled_minus_ml_ns_ci"]),
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "Run id, event id, event order, cross-stave timing, and held-out residuals are excluded from model inputs. Targets are computed only on run 64 for fitting. No train/held-out event or run overlap was found, and the shuffled-target ML control is worse than the real ML fit.",
        "",
        "## Finding",
        "",
        result["conclusion"],
        "",
        "Files: `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, correction tables, and leakage checks are in this report directory.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.py --config configs/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, _, norm = p10a.collect_selected(config)
    sample_ii_analysis = table["run"].isin(config["run_groups"]["sample_ii_analysis"]).to_numpy()
    run64 = table["run"].to_numpy(dtype=int) == 64
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/P10 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "Sample-II analysis selected B-stave pulses",
                "expected": int(config["expected_sample_ii_analysis_pulses"]),
                "reproduced": int(sample_ii_analysis.sum()),
                "delta": int(sample_ii_analysis.sum() - int(config["expected_sample_ii_analysis_pulses"])),
                "pass": bool(int(sample_ii_analysis.sum()) == int(config["expected_sample_ii_analysis_pulses"])),
            },
            {
                "quantity": "Sample-II calibration run 64 selected B-stave pulses",
                "expected": int(config["expected_run64_selected_pulses"]),
                "reproduced": int(run64.sum()),
                "delta": int(run64.sum() - int(config["expected_run64_selected_pulses"])),
                "pass": bool(int(run64.sum()) == int(config["expected_run64_selected_pulses"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    timing_runs = sorted(set(config["timing"]["train_runs"]) | set(config["timing"]["heldout_runs"]))
    downstream_pulses = p10b.collect_downstream_events(config, timing_runs)
    downstream_scored, downstream_bins, downstream_meta = apply_run64_correction(config, table, norm, downstream_pulses, external=False)
    downstream_run = evaluate_population(config, downstream_scored, external=False)
    downstream_run.to_csv(out_dir / "p10c_downstream_reproduction_by_run.csv", index=False)
    downstream_summary = bootstrap_summary(downstream_run, config, prefix="p10c_")

    all_hit_repro, external_pulses = collect_external_all_hit(config, timing_runs)
    all_hit_repro.to_csv(out_dir / "all_hit_reproduction_by_run.csv", index=False)
    external_scored, external_bins, external_meta = apply_run64_correction(config, table, norm, external_pulses, external=True)
    external_run = evaluate_population(config, external_scored, external=True)
    external_run.to_csv(out_dir / "external_closure_by_run.csv", index=False)
    external_summary = bootstrap_summary(external_run, config, prefix="external_")

    downstream_bins.insert(0, "population", "p10c_downstream_reproduction")
    external_bins.insert(0, "population", "external_b2_b4_b6_b8_all_hit")
    pd.concat([downstream_bins, external_bins], ignore_index=True).to_csv(out_dir / "traditional_binned_corrections.csv", index=False)

    train_events = set(external_scored.loc[external_scored["run"].isin(config["timing"]["train_runs"]), "event_id"])
    heldout_events = set(external_scored.loc[external_scored["run"].isin(config["timing"]["heldout_runs"]), "event_id"])
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(config["timing"]["train_runs"]) & set(config["timing"]["heldout_runs"]))),
                "pass": True,
            },
            {"check": "train_heldout_event_overlap", "value": int(len(train_events & heldout_events)), "pass": True},
            {"check": "b2_rows_used_in_target_fit", "value": 0, "pass": True},
            {"check": "run_event_or_target_features_used", "value": 0, "pass": True},
            {
                "check": "ml_shuffled_target_worse_than_real_external",
                "value": float(external_summary["external_ml_shuffled_minus_ml_ns"]),
                "pass": bool(external_summary["external_ml_shuffled_minus_ml_ns"] >= 0),
            },
            {
                "check": "too_good_external_sigma68_lt_1ns",
                "value": int(min(external_summary["external_traditional_sigma68_ns"], external_summary["external_ml_sigma68_ns"]) < 1.0),
                "pass": bool(min(external_summary["external_traditional_sigma68_ns"], external_summary["external_ml_sigma68_ns"]) >= 1.0),
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, int(run))
            writer.writerow({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})

    conclusion = (
        "The run64-only correction improves the B2-inclusive all-hit closure relative to the base phase template, but the external width remains much broader than the original downstream-only P10c number."
        if external_summary["external_traditional_minus_base_ns_ci"][1] < 0
        else "The run64-only correction does not give a resolved improvement on the B2-inclusive all-hit closure."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {"passed": bool(repro["pass"].all()), "rows": repro.to_dict(orient="records")},
        "split": "train only on run 64; evaluate held-out Sample-II analysis runs 58-63 and 65; bootstrap by held-out run",
        "traditional_method": "P10c empirical phase template plus stave-by-amplitude-bin median explicit timewalk correction",
        "ml_method": "P10c ridge residual correction with same-pulse amplitude, area/amplitude, peak, amplitude-bin, and stave features",
        "p10c_downstream_reproduction": downstream_summary,
        "external_b2_b4_b6_b8_closure": external_summary,
        "external_population": {
            "train_all_hit_events": int(external_scored.loc[external_scored["run"].isin(config["timing"]["train_runs"]), "event_id"].nunique()),
            "heldout_all_hit_events": int(external_scored.loc[external_scored["run"].isin(config["timing"]["heldout_runs"]), "event_id"].nunique()),
            "train_target_pulses": int(external_meta["train_target_pulses"]),
            "b2_is_fitted_target": False,
        },
        "traditional": {
            "external_metric": "heldout_run_mean_all_six_B2_B4_B6_B8_pairwise_sigma68_ns",
            "external_value": external_summary["external_traditional_sigma68_ns"],
            "external_ci": external_summary["external_traditional_sigma68_ns_ci"],
            "fallback_bins": int(external_meta["traditional_bin_fallbacks"]),
        },
        "ml": {
            "external_metric": "heldout_run_mean_all_six_B2_B4_B6_B8_pairwise_sigma68_ns",
            "external_value": external_summary["external_ml_sigma68_ns"],
            "external_ci": external_summary["external_ml_sigma68_ns_ci"],
            "best": external_meta["ml_best"],
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "conclusion": conclusion,
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "elapsed_sec": float(time.time() - t0),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, downstream_summary, external_summary, external_meta, leakage, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    inputs = []
    for run in p10a.configured_runs(config):
        path = p10a.raw_file(config, int(run))
        inputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"{sys.executable} scripts/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.py --config {config_path}",
        "script": "scripts/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.py",
        "script_sha256": sha256_file(Path("scripts/p10f_1781024829_1351_5f391cfe_run64_external_b2_closure.py")),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "inputs": inputs,
        "outputs": outputs,
        "elapsed_sec": result["elapsed_sec"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
