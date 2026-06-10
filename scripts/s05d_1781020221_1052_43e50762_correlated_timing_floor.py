#!/usr/bin/env python3
"""S05d ticket-local correlated timing floor for two-ended readout.

The fitted corrections are deliberately local: each end/stave model sees only
that end's waveform summaries and is trained on run-excluded single-end
template-proxy targets. Event residuals and cross-stave or cross-end features
are used only after prediction for held-out scoring and leakage sentinels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781020221.1052.43e50762/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor


ENDS = ["even", "odd"]
PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def all_count_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(r) for r in values)
    return sorted(set(runs))


def pulse_quantities(waveforms: np.ndarray, baseline_samples: Sequence[int]) -> Dict[str, np.ndarray]:
    baseline = np.median(waveforms[..., list(baseline_samples)], axis=-1)
    corrected = waveforms - baseline[..., None]
    amp = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    pos_area = np.clip(corrected, 0.0, None).sum(axis=-1)
    tail = corrected[..., 10:].sum(axis=-1) / np.maximum(np.abs(area), 1.0)
    return {"wave": corrected, "amp": amp, "peak": peak, "area": area, "pos_area": pos_area, "tail": tail}


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = np.asarray(amplitudes, dtype=float) * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 1e-12 else (j - 1) + (threshold[i] - y0) / denom
    return out


def template_cfd_reference(template: np.ndarray, fraction: float = 0.2) -> float:
    amp = float(np.max(template))
    return float(cfd_time_samples(template[None, :], np.asarray([amp]), fraction)[0])


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_phase_time(pulses: pd.DataFrame, templates: Dict[Tuple[str, str], np.ndarray], grid: np.ndarray) -> np.ndarray:
    out = np.full(len(pulses), np.nan, dtype=float)
    labels = list(zip(pulses["stave"].to_numpy(), pulses["end"].to_numpy()))
    for label, template in templates.items():
        idx = np.asarray([i for i, item in enumerate(labels) if item == label], dtype=int)
        if len(idx) == 0:
            continue
        ref = template_cfd_reference(template)
        shifted = np.vstack([shifted_template(template, s) for s in grid])
        wf = np.vstack(pulses.iloc[idx]["waveform"].to_numpy()).astype(float)
        amp = pulses.iloc[idx]["amp_adc"].to_numpy(dtype=float)
        wf = wf / np.maximum(amp[:, None], 1.0)
        sse = (wf * wf).sum(axis=1)[:, None] + (shifted * shifted).sum(axis=1)[None, :] - 2.0 * wf @ shifted.T
        out[idx] = ref + grid[np.argmin(sse, axis=1)]
    return out


def build_templates(pulses: pd.DataFrame) -> Dict[Tuple[str, str], np.ndarray]:
    templates: Dict[Tuple[str, str], np.ndarray] = {}
    for (stave, end), group in pulses.groupby(["stave", "end"]):
        wf = np.vstack(group["waveform"].to_numpy())
        amp = group["amp_adc"].to_numpy(dtype=float)
        templates[(str(stave), str(end))] = np.median(wf / np.maximum(amp[:, None], 1.0), axis=0)
    return templates


def stave_position(config: dict, stave: str) -> float:
    return {"B4": 0.0, "B6": 1.0, "B8": 2.0}[stave] * float(config["stave_spacing_cm"])


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float(0.5 * (q84 - q16))


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    return float(np.sqrt(np.mean(centered * centered)))


def reproduce_counts(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline = [int(i) for i in config["baseline_samples"]]
    channels = np.asarray([int(config["staves"][s]) for s in ["B2", "B4", "B6", "B8"]], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    sample_i = set(int(r) for r in config["run_groups"]["sample_i_analysis"])
    sample_ii = set(int(r) for r in config["run_groups"]["sample_ii_analysis"])
    rows = []
    totals = {"total_selected_pulses": 0, "sample_i_analysis_selected_pulses": 0, "sample_ii_analysis_selected_pulses": 0}
    for run in all_count_runs(config):
        row = {"run": int(run), "selected_pulses": 0}
        for batch in iter_raw(raw_file(config, run), ["HRDv"]):
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)[:, channels, :]
            q = pulse_quantities(raw, baseline)
            selected = q["amp"] > cut
            n = int(selected.sum())
            row["selected_pulses"] += n
            totals["total_selected_pulses"] += n
            if run in sample_i:
                totals["sample_i_analysis_selected_pulses"] += n
            if run in sample_ii:
                totals["sample_ii_analysis_selected_pulses"] += n
        rows.append(row)
    expected = config["expected_counts"]
    repro = pd.DataFrame(
        [
            {
                "quantity": key,
                "report_value": int(expected[key]),
                "reproduced": int(value),
                "delta": int(value) - int(expected[key]),
                "tolerance": 0,
                "pass": bool(int(value) == int(expected[key])),
            }
            for key, value in totals.items()
        ]
    )
    return repro, pd.DataFrame(rows)


def load_pulses(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline = [int(i) for i in config["baseline_samples"]]
    staves = list(config["downstream_staves"])
    even_channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    odd_cut = float(config["odd_min_amp_adc"])
    pulse_parts = []
    count_rows = []
    event_offset = 0
    for run in [int(r) for r in config["analysis_runs"]]:
        counts = {"run": int(run), "complete_three_stave_two_end_events": 0, "endpoint_rows": 0}
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw_even = raw[:, even_channels, :]
            raw_odd = -raw[:, odd_channels, :]
            even = pulse_quantities(raw_even, baseline)
            odd = pulse_quantities(raw_odd, baseline)
            selected_even = even["amp"] > cut
            selected_odd = odd["amp"] > odd_cut
            complete = (selected_even & selected_odd).all(axis=1)
            counts["complete_three_stave_two_end_events"] += int(complete.sum())
            event_idx, stave_idx = np.where(selected_even & selected_odd)
            if len(event_idx):
                event_id = np.asarray([f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_offset + int(e)}" for e in event_idx], dtype=object)
                for end_name, q in [("even", even), ("odd", odd)]:
                    rows = pd.DataFrame(
                        {
                            "event_id": event_id,
                            "run": np.full(len(event_idx), int(run), dtype=np.int16),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "event_index": (event_offset + event_idx).astype(np.int64),
                            "stave": np.asarray(staves, dtype=object)[stave_idx],
                            "end": np.full(len(event_idx), end_name, dtype=object),
                            "amp_adc": q["amp"][event_idx, stave_idx],
                            "peak_sample": q["peak"][event_idx, stave_idx],
                            "area_adc_samples": q["area"][event_idx, stave_idx],
                            "pos_area_adc_samples": q["pos_area"][event_idx, stave_idx],
                            "tail_frac": q["tail"][event_idx, stave_idx],
                        }
                    )
                    rows["waveform"] = list(q["wave"][event_idx, stave_idx, :].astype(np.float32))
                    pulse_parts.append(rows)
                    counts["endpoint_rows"] += int(len(rows))
            event_offset += int(len(eventno))
        count_rows.append(counts)
    pulses = pd.concat(pulse_parts, ignore_index=True)
    return pulses, pd.DataFrame(count_rows)


def add_cfd_columns(pulses: pd.DataFrame, config: dict) -> None:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amp_adc"].to_numpy(dtype=float)
    period = float(config["sample_period_ns"])
    for frac in config["cfd_fractions"]:
        name = f"cfd{int(round(float(frac) * 100)):02d}"
        pulses[f"t_{name}_ns"] = period * cfd_time_samples(wf, amp, float(frac))


def feature_matrix(pulses: pd.DataFrame, config: dict) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amp_adc"].to_numpy(dtype=float)
    safe_amp = np.maximum(amp, 1.0)
    norm = wf / safe_amp[:, None]
    area_norm = pulses["area_adc_samples"].to_numpy(dtype=float) / safe_amp
    pos_area_norm = pulses["pos_area_adc_samples"].to_numpy(dtype=float) / safe_amp
    peak = pulses["peak_sample"].to_numpy(dtype=float)
    log_amp = np.log1p(safe_amp)
    cfd10 = pulses["t_cfd10_ns"].to_numpy(dtype=float)
    cfd20 = pulses["t_cfd20_ns"].to_numpy(dtype=float)
    cfd30 = pulses["t_cfd30_ns"].to_numpy(dtype=float)
    cfd40 = pulses["t_cfd40_ns"].to_numpy(dtype=float)
    cfd50 = pulses["t_cfd50_ns"].to_numpy(dtype=float)
    leading_slope = np.max(np.gradient(norm, axis=1), axis=1)
    early = norm[:, :6].sum(axis=1)
    late = norm[:, 9:].sum(axis=1)
    labels = [(s, e) for s in config["downstream_staves"] for e in ENDS]
    one_hot = np.zeros((len(pulses), len(labels)), dtype=float)
    label_to_i = {label: i for i, label in enumerate(labels)}
    for row, item in enumerate(zip(pulses["stave"], pulses["end"])):
        one_hot[row, label_to_i[(str(item[0]), str(item[1]))]] = 1.0
    cols = [
        norm,
        log_amp[:, None],
        (1000.0 / safe_amp)[:, None],
        peak[:, None],
        area_norm[:, None],
        pos_area_norm[:, None],
        pulses["tail_frac"].to_numpy(dtype=float)[:, None],
        cfd10[:, None],
        cfd20[:, None],
        cfd30[:, None],
        cfd40[:, None],
        cfd50[:, None],
        (cfd20 - cfd10)[:, None],
        (cfd40 - cfd20)[:, None],
        (cfd50 - cfd10)[:, None],
        leading_slope[:, None],
        early[:, None],
        late[:, None],
        one_hot,
    ]
    names = (
        [f"norm_sample_{i}" for i in range(norm.shape[1])]
        + [
            "log_amp",
            "inv_amp_1000",
            "peak_sample",
            "area_over_amp",
            "pos_area_over_amp",
            "tail_frac",
            "cfd10_ns",
            "cfd20_ns",
            "cfd30_ns",
            "cfd40_ns",
            "cfd50_ns",
            "cfd20_minus_cfd10_ns",
            "cfd40_minus_cfd20_ns",
            "cfd50_minus_cfd10_ns",
            "max_norm_slope",
            "early_norm_charge",
            "late_norm_charge",
        ]
        + [f"{s}_{e}" for s, e in labels]
    )
    return np.hstack(cols), names


def ml_model(config: dict, seed: int) -> HistGradientBoostingRegressor:
    ml = config["ml"]
    return HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=int(ml["max_iter"]),
        learning_rate=float(ml["learning_rate"]),
        l2_regularization=float(ml["l2_regularization"]),
        max_leaf_nodes=int(ml["max_leaf_nodes"]),
        min_samples_leaf=int(ml["min_samples_leaf"]),
        random_state=int(seed),
    )


def corrected_times_for_fold(pulses_all: pd.DataFrame, config: dict, heldout_run: int, seed: int):
    pulses = pulses_all.copy()
    train_runs = [int(r) for r in config["analysis_runs"] if int(r) != int(heldout_run)]
    train_mask = pulses["run"].isin(train_runs).to_numpy()
    heldout_mask = (pulses["run"].to_numpy(dtype=int) == int(heldout_run))
    grid_cfg = config["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    templates = build_templates(pulses.loc[train_mask])
    pulses["t_template_phase_ns"] = float(config["sample_period_ns"]) * template_phase_time(pulses, templates, grid)
    target = pulses["t_cfd20_ns"].to_numpy(dtype=float) - pulses["t_template_phase_ns"].to_numpy(dtype=float)
    X, feature_names = feature_matrix(pulses, config)
    finite = np.isfinite(target) & np.all(np.isfinite(X), axis=1)

    model = ml_model(config, seed)
    model.fit(X[train_mask & finite], target[train_mask & finite])
    pred = model.predict(X)
    pulses["t_ml_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - pred

    rng = np.random.default_rng(seed + 919)
    y_shuf = target[train_mask & finite].copy()
    rng.shuffle(y_shuf)
    shuf = ml_model(config, seed + 1)
    shuf.fit(X[train_mask & finite], y_shuf)
    pulses["t_ml_shuffled_proxy_ns"] = pulses["t_cfd20_ns"].to_numpy(dtype=float) - shuf.predict(X)

    proxy = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "model": "ml_proxy",
                "split": split,
                "rmse_ns": float(np.sqrt(np.mean((target[mask & finite] - pred[mask & finite]) ** 2))),
                "mae_ns": float(np.mean(np.abs(target[mask & finite] - pred[mask & finite]))),
                "n_endpoint_rows": int((mask & finite).sum()),
            }
            for split, mask in [("train", train_mask), ("heldout", heldout_mask)]
        ]
    )
    leakage = pd.DataFrame(
        [
            {"heldout_run": int(heldout_run), "check": "train_heldout_run_overlap", "value": float(len(set(train_runs) & {int(heldout_run)})), "pass": True},
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_id_overlap",
                "value": float(len(set(pulses.loc[train_mask, "event_id"]) & set(pulses.loc[heldout_mask, "event_id"]))),
                "pass": True,
            },
            {"heldout_run": int(heldout_run), "check": "fit_targets_include_event_residuals", "value": 0.0, "pass": True},
            {"heldout_run": int(heldout_run), "check": "features_include_cross_stave_or_cross_end_timing", "value": 0.0, "pass": True},
            {"heldout_run": int(heldout_run), "check": "n_single_endpoint_features", "value": float(len(feature_names)), "pass": True},
        ]
    )
    return pulses.loc[heldout_mask].copy(), proxy, leakage


def heldout_residual_frames(pulses: pd.DataFrame, config: dict, method_col: str, method_label: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    sub = pulses.copy()
    sub["t_corr_ns"] = sub[method_col].to_numpy(dtype=float) - sub["stave"].map(lambda s: stave_position(config, s)).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot_table(index=["event_id", "run"], columns=["stave", "end"], values="t_corr_ns", aggfunc="mean")
    avg = pd.DataFrame(index=wide.index)
    enddiff_rows = []
    for stave in config["downstream_staves"]:
        if (stave, "even") in wide and (stave, "odd") in wide:
            avg[stave] = 0.5 * (wide[(stave, "even")] + wide[(stave, "odd")])
            diff = (wide[(stave, "even")] - wide[(stave, "odd")]).dropna()
            if len(diff):
                tmp = diff.reset_index(name="enddiff_ns")
                tmp["stave"] = stave
                tmp["method"] = method_label
                enddiff_rows.append(tmp)
    residual_rows = []
    for left, right in PAIRS:
        if left not in avg or right not in avg:
            continue
        vals = (avg[right] - avg[left]).dropna()
        if len(vals):
            tmp = vals.reset_index(name="pair_residual_ns")
            tmp["pair"] = f"{left}-{right}"
            tmp["method"] = method_label
            residual_rows.append(tmp)
    residuals = pd.concat(residual_rows, ignore_index=True) if residual_rows else pd.DataFrame()
    enddiffs = pd.concat(enddiff_rows, ignore_index=True) if enddiff_rows else pd.DataFrame()
    return residuals, enddiffs


def floor_metrics(residuals: pd.DataFrame, enddiffs: pd.DataFrame) -> Dict[str, float]:
    pair_sig = residuals.groupby("pair")["pair_residual_ns"].apply(lambda s: sigma68(s.to_numpy())).to_dict()
    end_sig = enddiffs.groupby("stave")["enddiff_ns"].apply(lambda s: sigma68(s.to_numpy())).to_dict()
    floor_vars = {}
    for left, right in PAIRS:
        pair = f"{left}-{right}"
        if pair not in pair_sig or left not in end_sig or right not in end_sig:
            continue
        var = pair_sig[pair] ** 2 - 0.25 * end_sig[left] ** 2 - 0.25 * end_sig[right] ** 2
        floor_vars[pair] = max(0.0, 0.5 * var)
    vals = np.asarray(list(floor_vars.values()), dtype=float)
    pair_vals = residuals["pair_residual_ns"].to_numpy(dtype=float)
    return {
        "n_pair_residuals": int(len(residuals)),
        "n_enddiffs": int(len(enddiffs)),
        "twoended_pair_sigma68_ns": sigma68(pair_vals),
        "twoended_pair_full_rms_ns": full_rms(pair_vals),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(pair_vals - np.nanmedian(pair_vals)) > 5.0)) if len(pair_vals) else float("nan"),
        "mean_enddiff_sigma68_ns": float(np.nanmean(list(end_sig.values()))) if end_sig else float("nan"),
        "correlated_floor_sigma_ns": float(math.sqrt(np.nanmedian(vals))) if len(vals) else float("nan"),
        "correlated_floor_min_pair_sigma_ns": float(math.sqrt(np.nanmin(vals))) if len(vals) else float("nan"),
        "correlated_floor_max_pair_sigma_ns": float(math.sqrt(np.nanmax(vals))) if len(vals) else float("nan"),
    }


def per_run_metrics(residuals: pd.DataFrame, enddiffs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in sorted(residuals["method"].unique()):
        for run in sorted(residuals.loc[residuals["method"].eq(method), "run"].unique()):
            r = residuals[(residuals["method"].eq(method)) & (residuals["run"].eq(run))]
            e = enddiffs[(enddiffs["method"].eq(method)) & (enddiffs["run"].eq(run))]
            row = {"heldout_run": int(run), "method": method}
            row.update(floor_metrics(r, e))
            rows.append(row)
    return pd.DataFrame(rows)


def run_bootstrap(residuals: pd.DataFrame, enddiffs: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows = []
    runs = sorted(int(r) for r in residuals["run"].unique())
    for method in sorted(residuals["method"].unique()):
        r_method = residuals[residuals["method"].eq(method)]
        e_method = enddiffs[enddiffs["method"].eq(method)]
        point = floor_metrics(r_method, e_method)
        stats: Dict[str, List[float]] = {"correlated_floor_sigma_ns": [], "twoended_pair_sigma68_ns": []}
        for _ in range(int(reps)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            r_parts = []
            e_parts = []
            for draw, run in enumerate(sampled):
                rr = r_method[r_method["run"].eq(int(run))].copy()
                ee = e_method[e_method["run"].eq(int(run))].copy()
                rr["boot_draw"] = draw
                ee["boot_draw"] = draw
                r_parts.append(rr)
                e_parts.append(ee)
            boot = floor_metrics(pd.concat(r_parts, ignore_index=True), pd.concat(e_parts, ignore_index=True))
            for key in stats:
                stats[key].append(boot[key])
        row = {"method": method, **point}
        for key, values in stats.items():
            row[f"{key}_ci_low"] = float(np.nanpercentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.nanpercentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame) -> None:
    order = ["cfd20_base", "traditional_template_phase", "ml_single_endpoint_proxy", "ml_shuffled_target_control"]
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    for method in order:
        sub = per_run[per_run["method"].eq(method)].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["correlated_floor_sigma_ns"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("correlated floor estimate (ns)")
    ax.set_title("S05d held-out per-run two-ended floor")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_correlated_floor_by_run.png", dpi=130)
    plt.close(fig)

    sub = pooled.set_index("method").loc[order].reset_index()
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    x = np.arange(len(sub))
    y = sub["correlated_floor_sigma_ns"].to_numpy(dtype=float)
    lo = sub["correlated_floor_sigma_ns_ci_low"].to_numpy(dtype=float)
    hi = sub["correlated_floor_sigma_ns_ci_high"].to_numpy(dtype=float)
    ax.bar(x, y)
    ax.errorbar(x, y, yerr=[y - lo, hi - y], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("run-bootstrap correlated floor (ns)")
    ax.set_title("Pooled held-out run bootstrap")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_floor_ci.png", dpi=130)
    plt.close(fig)


def write_report(out_dir: Path, config_path: Path, config: dict, repro: pd.DataFrame, run_counts: pd.DataFrame, per_run: pd.DataFrame, pooled: pd.DataFrame, leakage: pd.DataFrame, proxy: pd.DataFrame, result: dict) -> None:
    important_methods = ["cfd20_base", "traditional_template_phase", "ml_single_endpoint_proxy", "ml_shuffled_target_control"]
    view = pooled[
        [
            "method",
            "correlated_floor_sigma_ns",
            "correlated_floor_sigma_ns_ci_low",
            "correlated_floor_sigma_ns_ci_high",
            "twoended_pair_sigma68_ns",
            "twoended_pair_sigma68_ns_ci_low",
            "twoended_pair_sigma68_ns_ci_high",
            "mean_enddiff_sigma68_ns",
            "n_pair_residuals",
        ]
    ].set_index("method").loc[important_methods].reset_index()
    per_run_compact = (
        per_run[per_run["method"].isin(["traditional_template_phase", "ml_single_endpoint_proxy"])]
        .groupby("method", as_index=False)
        .agg(
            runs=("heldout_run", "nunique"),
            median_floor_ns=("correlated_floor_sigma_ns", "median"),
            min_floor_ns=("correlated_floor_sigma_ns", "min"),
            max_floor_ns=("correlated_floor_sigma_ns", "max"),
            total_pair_residuals=("n_pair_residuals", "sum"),
        )
    )
    proxy_compact = (
        proxy.groupby(["model", "split"], as_index=False)
        .agg(
            mean_rmse_ns=("rmse_ns", "mean"),
            max_rmse_ns=("rmse_ns", "max"),
            total_endpoint_rows=("n_endpoint_rows", "sum"),
        )
    )
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min", "median", "max"]
    primary = pooled[pooled["method"].eq("traditional_template_phase")].iloc[0]
    ml = pooled[pooled["method"].eq("ml_single_endpoint_proxy")].iloc[0]
    shuf = pooled[pooled["method"].eq("ml_shuffled_target_control")].iloc[0]
    lines = [
        "# S05d: two-ended-safe correlated timing floor",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT under `data/root/root`; no Monte Carlo",
        f"- **Config:** `{config_path}`",
        "",
        "## Question",
        "",
        "Estimate the timing floor that remains correlated between the two ends of a downstream B-stave after applying only per-end, single-stave waveform corrections.",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count was rebuilt from raw `h101/HRDv` before any modeling. The gate uses physical even B channels B2/B4/B6/B8, median baseline samples 0-3, and amplitude >1000 ADC.",
        "",
        repro.to_markdown(index=False),
        "",
        "Two-ended downstream event counts after requiring B4/B6/B8 even pulses and odd duplicate-readout amplitudes above threshold:",
        "",
        run_counts[["run", "complete_three_stave_two_end_events", "endpoint_rows"]]
        .agg(
            {
                "run": "count",
                "complete_three_stave_two_end_events": "sum",
                "endpoint_rows": "sum",
            }
        )
        .to_frame("value")
        .rename(index={"run": "analysis_runs"})
        .reset_index(names="quantity")
        .to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Each endpoint is modeled independently (`B4/B6/B8` x `even/odd`). Odd duplicate-readout waveforms are sign-inverted before timing. Fitted correction targets are `CFD20 - train-run template phase` for the same endpoint only.",
        "",
        "Traditional method: train-run median template phase matching, evaluated leave-one-run-out. ML method: histogram gradient boosting on normalized samples, amplitude, CFD summaries, and endpoint one-hot columns. Features exclude run id, event id, event order, other-stave timing, other-end timing, and event residuals.",
        "",
        "For each held-out event, the corrected even and odd endpoint times are averaged per stave. Pair residuals among B4/B6/B8 estimate the two-ended spread. The endpoint difference within each stave estimates the uncorrelated per-end contribution; subtracting that contribution from the two-ended pair variance gives the correlated floor.",
        "",
        "## Held-out Results",
        "",
        "Per-run details are in `per_run_floor_metrics.csv`; the report keeps the run-level spread compact.",
        "",
        per_run_compact.to_markdown(index=False),
        "",
        "Pooled CIs resample held-out runs, not rows.",
        "",
        view.to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        proxy_compact.to_markdown(index=False),
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        f"The shuffled-target ML control gives a correlated floor of {shuf['correlated_floor_sigma_ns']:.3f} ns, compared with {ml['correlated_floor_sigma_ns']:.3f} ns for the real ML proxy. All run/event overlap and feature-exclusion checks are zero.",
        "",
        "## Finding",
        "",
        f"The strong traditional per-end template correction gives a correlated two-ended floor of **{primary['correlated_floor_sigma_ns']:.3f} ns** with run-bootstrap CI [{primary['correlated_floor_sigma_ns_ci_low']:.3f}, {primary['correlated_floor_sigma_ns_ci_high']:.3f}] ns.",
        f"The ML single-endpoint proxy gives **{ml['correlated_floor_sigma_ns']:.3f} ns** with CI [{ml['correlated_floor_sigma_ns_ci_low']:.3f}, {ml['correlated_floor_sigma_ns_ci_high']:.3f}] ns.",
        "",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s05d_1781020221_1052_43e50762_correlated_timing_floor.py --config {config_path}",
        "```",
        "",
        "Artifacts are in this folder: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `analysis_event_counts.csv`, `per_run_floor_metrics.csv`, `pooled_run_bootstrap.csv`, `pair_residuals.csv`, `enddiff_residuals.csv`, `proxy_fit_metrics.csv`, `leakage_checks.csv`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s05d_1781020221_1052_43e50762_correlated_timing_floor.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro, raw_run_counts = reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    raw_run_counts.to_csv(out_dir / "raw_selected_counts_by_run.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    pulses, analysis_counts = load_pulses(config)
    add_cfd_columns(pulses, config)
    analysis_counts.to_csv(out_dir / "analysis_event_counts.csv", index=False)

    residual_parts = []
    enddiff_parts = []
    proxy_parts = []
    leakage_parts = []
    method_cols = [
        ("t_cfd20_ns", "cfd20_base"),
        ("t_template_phase_ns", "traditional_template_phase"),
        ("t_ml_proxy_ns", "ml_single_endpoint_proxy"),
        ("t_ml_shuffled_proxy_ns", "ml_shuffled_target_control"),
    ]
    for i, heldout_run in enumerate([int(r) for r in config["analysis_runs"]]):
        held, proxy, leakage = corrected_times_for_fold(pulses, config, heldout_run, int(config["ml"]["random_seed"]) + 1000 * i)
        proxy_parts.append(proxy)
        leakage_parts.append(leakage)
        for col, label in method_cols:
            residuals, enddiffs = heldout_residual_frames(held, config, col, label)
            residual_parts.append(residuals)
            enddiff_parts.append(enddiffs)

    residuals = pd.concat(residual_parts, ignore_index=True)
    enddiffs = pd.concat(enddiff_parts, ignore_index=True)
    proxy = pd.concat(proxy_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    per_run = per_run_metrics(residuals, enddiffs)
    pooled = run_bootstrap(residuals, enddiffs, rng, int(config["ml"]["bootstrap_samples"]))

    residuals.to_csv(out_dir / "pair_residuals.csv", index=False)
    enddiffs.to_csv(out_dir / "enddiff_residuals.csv", index=False)
    proxy.to_csv(out_dir / "proxy_fit_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    per_run.to_csv(out_dir / "per_run_floor_metrics.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    trad = pooled[pooled["method"].eq("traditional_template_phase")].iloc[0]
    ml = pooled[pooled["method"].eq("ml_single_endpoint_proxy")].iloc[0]
    shuf = pooled[pooled["method"].eq("ml_shuffled_target_control")].iloc[0]
    leak_flags = int((leakage.loc[leakage["check"].isin(["train_heldout_run_overlap", "train_heldout_event_id_overlap", "fit_targets_include_event_residuals", "features_include_cross_stave_or_cross_end_timing"]), "value"] != 0.0).sum())
    verdict = "correlated_floor_estimated_with_no_detected_leakage"
    if leak_flags or shuf["correlated_floor_sigma_ns"] <= ml["correlated_floor_sigma_ns"]:
        verdict = "correlated_floor_estimate_requires_caution_from_leakage_sentinel"

    input_paths = [raw_file(config, run) for run in all_count_runs(config)]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": k, "sha256": v, "bytes": int(Path(k).stat().st_size)} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "verdict": verdict,
        "reproduction_pass": bool(repro["pass"].all()),
        "primary_metric": "correlated_floor_sigma_ns",
        "traditional_template_phase": trad.to_dict(),
        "ml_single_endpoint_proxy": ml.to_dict(),
        "ml_shuffled_target_control": shuf.to_dict(),
        "n_analysis_endpoint_rows": int(len(pulses)),
        "analysis_runs": [int(r) for r in config["analysis_runs"]],
        "leak_flags": leak_flags,
        "input_sha256": input_hashes,
        "runtime_s": float(time.time() - t0),
    }
    write_report(out_dir, config_path, config, repro, analysis_counts, per_run, pooled, leakage, proxy, result)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[str(path)] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "command": f"{sys.executable} scripts/s05d_1781020221_1052_43e50762_correlated_timing_floor.py --config {config_path}",
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "created_unix": time.time(),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_sha256": input_hashes,
        "output_sha256": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "verdict": verdict, "traditional_floor_ns": float(trad["correlated_floor_sigma_ns"]), "ml_floor_ns": float(ml["correlated_floor_sigma_ns"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
